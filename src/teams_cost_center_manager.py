"""
Teams-based Cost Center Manager for GitHub Teams integration.
"""

import logging
from typing import Dict, List, Set, Tuple, Optional
from .github_api import BudgetsAPIUnavailableError




class TeamsCostCenterManager:
    """Manages cost center assignments based on GitHub team membership."""
    
    def __init__(self, config, github_manager, create_budgets: bool = False):
        """
        Initialize the teams cost center manager.
        
        Args:
            config: ConfigManager instance with teams configuration
            github_manager: GitHubCopilotManager instance for API calls
            create_budgets: Whether to create budgets for new cost centers (requires unreleased APIs)
        """
        self.config = config
        self.github_manager = github_manager
        self.create_budgets = create_budgets
        self.logger = logging.getLogger(__name__)
        

        
        # Teams configuration
        self.teams_scope = config.teams_scope  # "organization" or "enterprise"
        self.teams_mode = config.teams_mode  # "auto" or "manual"
        self.organizations = config.teams_organizations
        self.auto_create = config.teams_auto_create
        self.team_mappings = config.teams_mappings or {}
        
        # Cache for team data
        self.teams_cache: Dict[str, List[Dict]] = {}  # org/enterprise -> list of teams
        self.members_cache: Dict[str, List[str]] = {}  # "org/team_slug" or "team_slug" -> list of usernames
        self.team_cost_center_cache: Dict[str, str] = {}  # "org/team_slug" or "team_slug" -> cost_center_id
        
        self.logger.info(f"Initialized TeamsCostCenterManager in '{self.teams_mode}' mode, scope '{self.teams_scope}'")
        if self.teams_scope == "organization":
            self.logger.info(f"Organizations: {', '.join(self.organizations) if self.organizations else 'None configured'}")
        else:
            self.logger.info(f"Enterprise scope: teams will be fetched from enterprise level")
    
    def fetch_all_teams(self) -> Dict[str, List[Dict]]:
        """
        Fetch all teams based on configured scope (organization or enterprise).
        
        Returns:
            Dict mapping org/enterprise name -> list of team dicts
        """
        all_teams = {}
        
        if self.teams_scope == "enterprise":
            # Fetch enterprise-level teams
            enterprise_name = self.config.github_enterprise
            self.logger.info(f"Fetching enterprise teams from: {enterprise_name}")
            teams = self.github_manager.list_enterprise_teams()
            all_teams[enterprise_name] = teams
            self.teams_cache[enterprise_name] = teams
            self.logger.info(f"Found {len(teams)} enterprise teams")
            
        else:  # organization scope
            if not self.organizations:
                self.logger.warning("No organizations configured for organization scope")
                return {}
            
            for org in self.organizations:
                self.logger.info(f"Fetching teams from organization: {org}")
                teams = self.github_manager.list_org_teams(org)
                all_teams[org] = teams
                self.teams_cache[org] = teams
                self.logger.info(f"Found {len(teams)} teams in {org}")
        
        total_teams = sum(len(teams) for teams in all_teams.values())
        self.logger.info(f"Total teams: {total_teams}")
        
        return all_teams
    
    def fetch_team_members(self, org_or_enterprise: str, team_slug: str) -> List[str]:
        """
        Fetch members of a specific team based on scope.
        
        Args:
            org_or_enterprise: Organization or enterprise name
            team_slug: Team slug
            
        Returns:
            List of usernames (login names)
        """
        if self.teams_scope == "enterprise":
            # For enterprise teams, cache key is just the team slug
            cache_key = team_slug
        else:
            # For org teams, cache key includes org
            cache_key = f"{org_or_enterprise}/{team_slug}"
        
        if cache_key in self.members_cache:
            return self.members_cache[cache_key]
        
        # Fetch members based on scope
        if self.teams_scope == "enterprise":
            members = self.github_manager.get_enterprise_team_members(team_slug)
        else:
            members = self.github_manager.get_team_members(org_or_enterprise, team_slug)
        
        usernames = [member.get('login') for member in members if member.get('login')]
        
        self.members_cache[cache_key] = usernames
        return usernames
    
    def get_cost_center_for_team(self, org_or_enterprise: str, team: Dict) -> Optional[str]:
        """
        Determine the cost center ID or name for a given team.
        
        Args:
            org_or_enterprise: Organization or enterprise name
            team: Team dictionary with name, slug, etc.
            
        Returns:
            Cost center ID or name (for auto-creation)
        """
        team_slug = team.get('slug')
        team_name = team.get('name')
        
        # Build team key based on scope
        if self.teams_scope == "enterprise":
            team_key = team_slug  # Enterprise teams don't need org prefix
        else:
            team_key = f"{org_or_enterprise}/{team_slug}"
        
        # Check cache first
        if team_key in self.team_cost_center_cache:
            return self.team_cost_center_cache[team_key]
        
        cost_center = None
        
        if self.teams_mode == "manual":
            # Use manual mappings
            cost_center = self.team_mappings.get(team_key)
            
            if not cost_center:
                self.logger.warning(
                    f"No mapping found for team {team_key} in manual mode. "
                    "Team will be skipped. Add mapping to config.teams.team_mappings"
                )
                return None
        
        elif self.teams_mode == "auto":
            # Generate cost center name based on scope and naming standards
            if self.teams_scope == "enterprise":
                # Enterprise team mode: [enterprise team] {team-name}
                cost_center = f"[enterprise team] {team_name}"
            else:
                # Organization team mode: [org team] {org-name}/{team-name}
                cost_center = f"[org team] {org_or_enterprise}/{team_name}"
        
        else:
            self.logger.error(f"Invalid teams mode: {self.teams_mode}. Must be 'auto' or 'manual'")
            return None
        
        # Cache the result
        self.team_cost_center_cache[team_key] = cost_center
        return cost_center
    
    def build_team_assignments(self) -> Dict[str, List[Tuple[str, str, str]]]:
        """
        Build complete team-to-members mapping with cost centers.
        
        IMPORTANT: Users can only belong to ONE cost center. If a user is in multiple teams,
        assignment depends on their current cost center status (existing assignments are preserved by default).
        
        Returns:
            Dict mapping cost_center -> list of (username, org, team_slug) tuples
        """
        self.logger.info("Building team-based cost center assignments...")
        
        # Fetch all teams
        all_teams = self.fetch_all_teams()
        
        if not all_teams:
            self.logger.warning("No teams found in any configured organization")
            return {}
        
        # Track final assignment per user (only ONE cost center per user)
        user_assignments: Dict[str, Tuple[str, str, str]] = {}  # username -> (cost_center, org, team_slug)
        
        # Track users across teams for conflict reporting
        user_team_map: Dict[str, List[Tuple[str, str]]] = {}  # username -> list of (org/team, cost_center)
        
        for org_or_enterprise, teams in all_teams.items():
            source_label = "enterprise" if self.teams_scope == "enterprise" else "organization"
            self.logger.info(f"Processing {len(teams)} teams from {source_label}: {org_or_enterprise}")
            
            for team in teams:
                team_name = team.get('name', 'Unknown')
                team_slug = team.get('slug', 'unknown')
                
                # Build team key based on scope
                if self.teams_scope == "enterprise":
                    team_key = team_slug
                else:
                    team_key = f"{org_or_enterprise}/{team_slug}"
                
                # Get cost center for this team
                cost_center = self.get_cost_center_for_team(org_or_enterprise, team)
                
                if not cost_center:
                    self.logger.debug(f"Skipping team {team_key} (no cost center mapping)")
                    continue
                
                # Fetch team members
                self.logger.debug(f"Fetching members for team: {team_name} ({team_key})")
                members = self.fetch_team_members(org_or_enterprise, team_slug)
                
                if not members:
                    self.logger.info(f"Team {team_key} has no members, skipping")
                    continue
                
                # Assign members to this cost center (will overwrite previous assignment)
                for username in members:
                    # Track all teams this user belongs to for reporting
                    if username not in user_team_map:
                        user_team_map[username] = []
                    user_team_map[username].append((team_key, cost_center))
                    
                    # Set/overwrite the user's cost center assignment (last one wins)
                    user_assignments[username] = (cost_center, org_or_enterprise, team_slug)
                
                self.logger.info(
                    f"Team {team_name} ({team_key}) → Cost Center '{cost_center}': "
                    f"{len(members)} members"
                )
        
        # Report on multi-team users (conflicts where assignment depends on current cost center status)
        multi_team_users = {user: teams for user, teams in user_team_map.items() if len(teams) > 1}
        if multi_team_users:
            self.logger.warning(
                f"⚠️  Found {len(multi_team_users)} users who are members of multiple teams. "
                "Each user can only belong to ONE cost center - assignment depends on their current cost center status."
            )
            for username, team_cc_list in list(multi_team_users.items())[:10]:  # Show first 10
                teams_str = ", ".join([f"{team}" for team, cc in team_cc_list])
                final_cc = user_assignments[username][0]
                self.logger.warning(
                    f"  ⚠️  {username} is in multiple teams [{teams_str}] → "
                    f"will be assigned to '{final_cc}'"
                )
            if len(multi_team_users) > 10:
                self.logger.warning(f"  ... and {len(multi_team_users) - 10} more multi-team users")
        
        # Convert to cost_center -> users mapping
        assignments: Dict[str, List[Tuple[str, str, str]]] = {}
        for username, (cost_center, org, team_slug) in user_assignments.items():
            if cost_center not in assignments:
                assignments[cost_center] = []
            assignments[cost_center].append((username, org, team_slug))
        
        # Summary
        total_users = len(user_assignments)
        
        self.logger.info(
            f"Team assignment summary: {len(assignments)} cost centers, "
            f"{total_users} unique users (each assigned to exactly ONE cost center)"
        )
        
        return assignments
    
    def _preload_active_cost_centers(self) -> Dict[str, str]:
        """
        Preload all active cost centers from the enterprise for performance optimization.
        
        Returns:
            Dict mapping cost center name -> cost center ID
        """
        try:
            active_centers_map = self.github_manager.get_all_active_cost_centers()
            self.logger.info(f"Preloaded {len(active_centers_map)} active cost centers for performance optimization")
            return active_centers_map
        except Exception as e:
            self.logger.warning(f"Failed to preload cost centers: {e}")
            self.logger.info("Falling back to individual cost center creation approach")
            return {}
    
    def ensure_cost_centers_exist(self, cost_centers: Set[str]) -> Tuple[Dict[str, str], Set[str]]:
        """
        Ensure all required cost centers exist, creating them if needed.
        Uses preload optimization with fallback to individual creation for performance.
        
        Args:
            cost_centers: Set of cost center names or IDs
            
        Returns:
            Tuple of:
            - Dict mapping original name/ID -> actual cost center ID
            - Set of cost center IDs that were newly created in this run
        """
        if not self.auto_create:
            self.logger.info("Auto-creation disabled, assuming cost center IDs are valid")
            # Return identity mapping (assume they're already IDs) and empty set for newly created
            return {cc: cc for cc in cost_centers}, set()
        
        self.logger.info(f"Ensuring {len(cost_centers)} cost centers exist...")
        
        cost_center_map = {}
        newly_created_ids = set()
        preload_hits = 0
        api_calls = 0
        
        # Step 1: Preload all active cost centers for performance optimization
        self.logger.info(f"Preloading active cost centers for {len(cost_centers)} cost centers...")
        active_centers_map = self._preload_active_cost_centers()
        
        # Step 2: Check preloaded map for existing cost centers
        still_need_creation = set()
        for cost_center_name in cost_centers:
            if cost_center_name in active_centers_map:
                cost_center_id = active_centers_map[cost_center_name]
                cost_center_map[cost_center_name] = cost_center_id
                preload_hits += 1
                self.logger.debug(f"Preload hit: '{cost_center_name}' → {cost_center_id}")
                
                # If budget creation is enabled and cost center already exists, check/create budget
                if self.create_budgets:
                    self.logger.debug(f"Checking/creating budget for existing cost center: {cost_center_name}")
                    try:
                        budget_success = self.github_manager.create_cost_center_budget(cost_center_id, cost_center_name)
                        if budget_success:
                            self.logger.debug(f"Budget ready for: {cost_center_name}")
                        else:
                            self.logger.warning(f"Failed to ensure budget for: {cost_center_name}")
                    except BudgetsAPIUnavailableError as e:
                        self.logger.warning(f"Budgets API not available - skipping budget creation: {str(e)}")
                        # Disable budget creation for remaining cost centers to avoid repeated errors
                        self.create_budgets = False
            else:
                still_need_creation.add(cost_center_name)
        
        # Step 3: Create cost centers that don't exist yet
        for cost_center_name in still_need_creation:
            api_calls += 1
            cost_center_id = self.github_manager.create_cost_center_with_preload_fallback(
                cost_center_name, active_centers_map
            )
            
            if cost_center_id:
                cost_center_map[cost_center_name] = cost_center_id
                newly_created_ids.add(cost_center_id)  # Track newly created cost center
                self.logger.debug(f"API call: '{cost_center_name}' → {cost_center_id}")
                
                # Create budget if requested (and if this is a newly created cost center)
                if self.create_budgets:
                    self.logger.info(f"Creating budget for cost center: {cost_center_name}")
                    try:
                        budget_success = self.github_manager.create_cost_center_budget(cost_center_id, cost_center_name)
                        if budget_success:
                            self.logger.info(f"Successfully created budget for: {cost_center_name}")
                        else:
                            self.logger.warning(f"Failed to create budget for: {cost_center_name}")
                    except BudgetsAPIUnavailableError as e:
                        self.logger.warning(f"Budgets API not available - skipping budget creation: {str(e)}")
                        # Disable budget creation for remaining cost centers to avoid repeated errors
                        self.create_budgets = False
            else:
                self.logger.error(f"Failed to create/find cost center: {cost_center_name}")
                # Use the name as fallback (will likely fail assignment but won't crash)
                cost_center_map[cost_center_name] = cost_center_name
        
        # Log performance metrics
        total_requests = preload_hits + api_calls
        preload_hit_rate = (preload_hits / total_requests * 100) if total_requests > 0 else 0
        
        self.logger.info(f"Cost center resolution complete: {len(cost_center_map)} resolved")
        self.logger.info(f"Performance: {preload_hits} preload hits, {api_calls} API calls ({preload_hit_rate:.1f}% preload hit rate)")
        
        if newly_created_ids:
            self.logger.debug(f"Newly created cost centers in this run: {len(newly_created_ids)} cost centers")
        
        return cost_center_map, newly_created_ids
    
    def sync_team_assignments(self, mode: str = "plan", ignore_current_cost_center: bool = False) -> Dict[str, Dict[str, bool]]:
        """
        Sync team-based cost center assignments to GitHub Enterprise.
        
        Args:
            mode: "plan" (dry-run) or "apply" (actually sync)
            
        Returns:
            Dict mapping cost_center_id -> Dict mapping username -> success status
        """
        # Build assignments
        team_assignments = self.build_team_assignments()
        
        if not team_assignments:
            self.logger.warning("No team assignments to sync")
            return {}
        
        # Get unique cost centers
        cost_centers_needed = set(team_assignments.keys())
        
        # Ensure cost centers exist (get ID mapping) - only in apply mode
        if mode == "plan":
            # In plan mode, just use the names as-is (no actual creation)
            cost_center_id_map = {cc: cc for cc in cost_centers_needed}
            newly_created_cost_center_ids = set()  # No creation in plan mode
            self.logger.info(f"Plan mode: Would ensure {len(cost_centers_needed)} cost centers exist")
        else:
            cost_center_id_map, newly_created_cost_center_ids = self.ensure_cost_centers_exist(cost_centers_needed)
        
        # Convert assignments to use actual cost center IDs
        id_based_assignments: Dict[str, List[str]] = {}
        
        for cost_center_name, member_tuples in team_assignments.items():
            cost_center_id = cost_center_id_map.get(cost_center_name, cost_center_name)
            
            # Extract just usernames (deduplicate)
            usernames = list(set(username for username, _, _ in member_tuples))
            
            if cost_center_id not in id_based_assignments:
                id_based_assignments[cost_center_id] = []
            
            id_based_assignments[cost_center_id].extend(usernames)
        
        # Deduplicate usernames per cost center
        for cost_center_id in id_based_assignments:
            id_based_assignments[cost_center_id] = list(set(id_based_assignments[cost_center_id]))
        
        # Show summary
        total_users = sum(len(users) for users in id_based_assignments.values())
        self.logger.info(
            f"Prepared {len(id_based_assignments)} cost centers with {total_users} total user assignments"
        )
        
        if mode == "plan":
            self.logger.info("MODE=plan: Would sync the following assignments:")
            for cost_center_id, usernames in id_based_assignments.items():
                self.logger.info(f"  {cost_center_id}: {len(usernames)} users")
            
            # In plan mode, show that removed user cleanup would be performed if enabled
            if self.config.teams_remove_users_no_longer_in_teams:
                self.logger.info("\nMODE=plan: Full sync mode is ENABLED")
                self.logger.info("  In apply mode, users no longer in teams will be removed from cost centers")
                self.logger.info("  (Cannot show specific removed users in plan mode - cost centers don't exist yet)")
            
            return {}
        
        # Apply mode: actually sync
        self.logger.info("Syncing team-based assignments to GitHub Enterprise...")
        results = self.github_manager.bulk_update_cost_center_assignments(id_based_assignments, ignore_current_cost_center)
        
        # Always check for users no longer in teams (detection), but only remove if configured
        self.logger.info("Checking for users in cost centers who are no longer in teams...")
        removed_user_results = self._remove_users_no_longer_in_teams(
            id_based_assignments, 
            cost_center_id_map, 
            newly_created_cost_center_ids,
            remove=self.config.teams_remove_users_no_longer_in_teams
        )
        
        # Merge removed user results into main results (if removal was enabled)
        if self.config.teams_remove_users_no_longer_in_teams:
            for cost_center_id, user_results in removed_user_results.items():
                if cost_center_id not in results:
                    results[cost_center_id] = {}
                results[cost_center_id].update(user_results)
        
        return results
    
    def _remove_users_no_longer_in_teams(self, expected_assignments: Dict[str, List[str]], 
                              cost_center_id_map: Dict[str, str],
                              newly_created_cost_center_ids: Set[str],
                              remove: bool = True) -> Dict[str, Dict[str, bool]]:
        """
        Detect and optionally remove users who are no longer in teams from cost centers.
        
        These are users who are currently assigned to a cost center but are no longer
        members of the corresponding GitHub team.
        
        Args:
            expected_assignments: Dict mapping cost_center_id -> list of expected usernames
            cost_center_id_map: Dict mapping cost_center_name -> cost_center_id
            newly_created_cost_center_ids: Set of cost center IDs that were created in this run (skip these)
            remove: If True, remove users no longer in teams. If False, only detect and log.
            
        Returns:
            Dict mapping cost_center_id -> Dict mapping username -> removal success status
        """
        removal_results = {}
        total_removed_users = 0
        total_successfully_removed = 0
        
        # Filter out newly created cost centers - they can't have users who left teams yet
        cost_centers_to_check = {cc_id: users for cc_id, users in expected_assignments.items() 
                                if cc_id not in newly_created_cost_center_ids}
        
        skipped_newly_created = len(expected_assignments) - len(cost_centers_to_check)
        if skipped_newly_created > 0:
            self.logger.info(f"⚡ Performance optimization: Skipping {skipped_newly_created} newly created cost centers (no users could have left teams yet)")
        
        self.logger.info(f"Checking {len(cost_centers_to_check)} cost centers for users no longer in teams...")
        
        for cost_center_id, expected_users in cost_centers_to_check.items():
            # Get current members of the cost center
            current_members = self.github_manager.get_cost_center_members(cost_center_id)
            
            # Debug logging
            self.logger.debug(f"Cost center {cost_center_id}: {len(current_members)} current, {len(expected_users)} expected")
            self.logger.debug(f"  Current: {sorted(current_members)}")
            self.logger.debug(f"  Expected: {sorted(expected_users)}")
            
            # Find users no longer in teams (in cost center but not in expected team members)
            expected_users_set = set(expected_users)
            current_members_set = set(current_members)
            users_no_longer_in_team = current_members_set - expected_users_set
            
            if users_no_longer_in_team:
                # Find the cost center name for logging
                cost_center_name = None
                for name, cc_id in cost_center_id_map.items():
                    if cc_id == cost_center_id:
                        cost_center_name = name
                        break
                
                display_name = cost_center_name or cost_center_id
                
                self.logger.warning(
                    f"⚠️  Found {len(users_no_longer_in_team)} users no longer in team for cost center '{display_name}' "
                    f"(in cost center but not in team)"
                )
                
                for username in sorted(users_no_longer_in_team):
                    self.logger.warning(f"   ⚠️  {username} is in cost center but not in team")
                
                total_removed_users += len(users_no_longer_in_team)
                
                # Remove users no longer in teams if configured
                if remove:
                    self.logger.info(f"Removing {len(users_no_longer_in_team)} users from '{display_name}'...")
                    removal_status = self.github_manager.remove_users_from_cost_center(
                        cost_center_id, 
                        list(users_no_longer_in_team)
                    )
                    
                    removal_results[cost_center_id] = removal_status
                    successful_removals = sum(1 for success in removal_status.values() if success)
                    total_successfully_removed += successful_removals
                    
                    if successful_removals < len(users_no_longer_in_team):
                        failed = len(users_no_longer_in_team) - successful_removals
                        self.logger.warning(
                            f"Failed to remove {failed}/{len(users_no_longer_in_team)} users from '{display_name}'"
                        )
                else:
                    self.logger.info(f"⚠️  Full sync is DISABLED - users will remain in cost center")
        
        if total_removed_users > 0:
            if remove:
                self.logger.info(
                    f"📊 Removed users summary: Found {total_removed_users} users no longer in teams, "
                    f"successfully removed {total_successfully_removed}"
                )
            else:
                self.logger.warning(
                    f"📊 Removed users summary: Found {total_removed_users} users no longer in teams (NOT removed - full sync disabled)"
                )
        else:
            self.logger.info("✅ No users found who left teams - all cost centers are in sync with teams")
        
        return removal_results
    
    def generate_summary(self) -> Dict:
        """
        Generate a summary report of team-based assignments.
        
        Returns:
            Dict with summary statistics
        """
        team_assignments = self.build_team_assignments()
        
        # Get unique users across all cost centers (each user in exactly one)
        all_users = set()
        for members in team_assignments.values():
            for username, _, _ in members:
                all_users.add(username)
        
        summary = {
            "mode": self.teams_mode,
            "organizations": self.organizations,
            "total_teams": sum(len(teams) for teams in self.teams_cache.values()),
            "total_cost_centers": len(team_assignments),
            "unique_users": len(all_users),
            "cost_centers": {}
        }
        
        # Add per-cost-center breakdown
        for cost_center, members in team_assignments.items():
            unique_members = set(username for username, _, _ in members)
            summary["cost_centers"][cost_center] = {
                "users": len(unique_members)
            }
        
        return summary

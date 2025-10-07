"""
Teams-based Cost Center Manager for GitHub Teams integration.
"""

import logging
from typing import Dict, List, Set, Tuple, Optional


class TeamsCostCenterManager:
    """Manages cost center assignments based on GitHub team membership."""
    
    def __init__(self, config, github_manager):
        """
        Initialize the teams cost center manager.
        
        Args:
            config: ConfigManager instance with teams configuration
            github_manager: GitHubCopilotManager instance for API calls
        """
        self.config = config
        self.github_manager = github_manager
        self.logger = logging.getLogger(__name__)
        
        # Teams configuration
        self.teams_scope = config.teams_scope  # "organization" or "enterprise"
        self.teams_mode = config.teams_mode  # "auto" or "manual"
        self.organizations = config.teams_organizations
        self.auto_create = config.teams_auto_create
        self.name_template = config.teams_name_template
        self.team_mappings = config.teams_mappings or {}
        
        # Cache for team data
        self.teams_cache: Dict[str, List[Dict]] = {}  # org/enterprise -> list of teams
        self.members_cache: Dict[str, List[str]] = {}  # "org/team_slug" or "team_slug" -> list of usernames
        self.cost_center_cache: Dict[str, str] = {}  # "org/team_slug" or "team_slug" -> cost_center_id
        
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
        if team_key in self.cost_center_cache:
            return self.cost_center_cache[team_key]
        
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
            # Generate cost center name using template
            try:
                cost_center = self.name_template.format(
                    team_name=team_name,
                    team_slug=team_slug,
                    org=org_or_enterprise
                )
            except KeyError as e:
                self.logger.error(
                    f"Invalid template variable in cost_center_name_template: {e}. "
                    f"Available: team_name, team_slug, org"
                )
                # Fallback to simple naming
                cost_center = f"Team: {team_name}"
        
        else:
            self.logger.error(f"Invalid teams mode: {self.teams_mode}. Must be 'auto' or 'manual'")
            return None
        
        # Cache the result
        self.cost_center_cache[team_key] = cost_center
        return cost_center
    
    def build_team_assignments(self) -> Dict[str, List[Tuple[str, str, str]]]:
        """
        Build complete team-to-members mapping with cost centers.
        
        IMPORTANT: Users can only belong to ONE cost center. If a user is in multiple teams,
        they will be assigned to the LAST team's cost center that is processed.
        
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
        
        # Report on multi-team users (conflicts where last assignment wins)
        multi_team_users = {user: teams for user, teams in user_team_map.items() if len(teams) > 1}
        if multi_team_users:
            self.logger.warning(
                f"⚠️  Found {len(multi_team_users)} users who are members of multiple teams. "
                "Each user can only belong to ONE cost center - the LAST team processed will determine their assignment."
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
    
    def ensure_cost_centers_exist(self, cost_centers: Set[str]) -> Dict[str, str]:
        """
        Ensure all required cost centers exist, creating them if needed.
        
        Args:
            cost_centers: Set of cost center names or IDs
            
        Returns:
            Dict mapping original name/ID -> actual cost center ID
        """
        if not self.auto_create:
            self.logger.info("Auto-creation disabled, assuming cost center IDs are valid")
            # Return identity mapping (assume they're already IDs)
            return {cc: cc for cc in cost_centers}
        
        self.logger.info(f"Ensuring {len(cost_centers)} cost centers exist...")
        
        cost_center_map = {}
        
        for cost_center_name in cost_centers:
            # Try to create the cost center (will return existing ID if already exists)
            cost_center_id = self.github_manager.create_cost_center(cost_center_name)
            
            if cost_center_id:
                cost_center_map[cost_center_name] = cost_center_id
                self.logger.debug(f"Cost center '{cost_center_name}' → ID: {cost_center_id}")
            else:
                self.logger.error(f"Failed to create/find cost center: {cost_center_name}")
                # Use the name as fallback (will likely fail assignment but won't crash)
                cost_center_map[cost_center_name] = cost_center_name
        
        self.logger.info(f"Successfully resolved {len(cost_center_map)} cost centers")
        return cost_center_map
    
    def sync_team_assignments(self, mode: str = "plan") -> Dict[str, Dict[str, bool]]:
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
            self.logger.info(f"Plan mode: Would ensure {len(cost_centers_needed)} cost centers exist")
        else:
            cost_center_id_map = self.ensure_cost_centers_exist(cost_centers_needed)
        
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
            
            # In plan mode, show that orphaned users would be checked if the option is enabled
            if self.config.teams_remove_orphaned_users:
                self.logger.info("\nMODE=plan: Orphaned user detection is ENABLED")
                self.logger.info("  In apply mode, users in cost centers but not in teams will be removed")
                self.logger.info("  (Cannot show specific orphaned users in plan mode - cost centers don't exist yet)")
            
            return {}
        
        # Apply mode: actually sync
        self.logger.info("Syncing team-based assignments to GitHub Enterprise...")
        results = self.github_manager.bulk_update_cost_center_assignments(id_based_assignments)
        
        # Handle orphaned users if configured
        if self.config.teams_remove_orphaned_users:
            self.logger.info("Checking for orphaned users (users in cost centers but not in teams)...")
            orphaned_results = self._remove_orphaned_users(id_based_assignments, cost_center_id_map)
            
            # Merge orphaned user removal results into main results
            for cost_center_id, user_results in orphaned_results.items():
                if cost_center_id not in results:
                    results[cost_center_id] = {}
                results[cost_center_id].update(user_results)
        
        return results
    
    def _remove_orphaned_users(self, expected_assignments: Dict[str, List[str]], 
                              cost_center_id_map: Dict[str, str]) -> Dict[str, Dict[str, bool]]:
        """
        Detect and remove orphaned users from cost centers.
        
        Orphaned users are those who are in a cost center but not in the corresponding team.
        
        Args:
            expected_assignments: Dict mapping cost_center_id -> list of expected usernames
            cost_center_id_map: Dict mapping cost_center_name -> cost_center_id
            
        Returns:
            Dict mapping cost_center_id -> Dict mapping username -> removal success status
        """
        removal_results = {}
        total_orphaned = 0
        total_removed = 0
        
        self.logger.info(f"Checking {len(expected_assignments)} cost centers for orphaned users...")
        
        for cost_center_id, expected_users in expected_assignments.items():
            # Get current members of the cost center
            current_members = self.github_manager.get_cost_center_members(cost_center_id)
            
            # Debug logging
            self.logger.debug(f"Cost center {cost_center_id}: {len(current_members)} current, {len(expected_users)} expected")
            self.logger.debug(f"  Current: {sorted(current_members)}")
            self.logger.debug(f"  Expected: {sorted(expected_users)}")
            
            # Find orphaned users (in cost center but not in expected team members)
            expected_users_set = set(expected_users)
            current_members_set = set(current_members)
            orphaned_users = current_members_set - expected_users_set
            
            if orphaned_users:
                # Find the cost center name for logging
                cost_center_name = None
                for name, cc_id in cost_center_id_map.items():
                    if cc_id == cost_center_id:
                        cost_center_name = name
                        break
                
                display_name = cost_center_name or cost_center_id
                
                self.logger.warning(
                    f"⚠️  Found {len(orphaned_users)} orphaned users in cost center '{display_name}' "
                    f"(in cost center but not in team)"
                )
                
                for username in sorted(orphaned_users):
                    self.logger.warning(f"   ⚠️  {username} is in cost center but not in team")
                
                total_orphaned += len(orphaned_users)
                
                # Remove orphaned users
                self.logger.info(f"Removing {len(orphaned_users)} orphaned users from '{display_name}'...")
                removal_status = self.github_manager.remove_users_from_cost_center(
                    cost_center_id, 
                    list(orphaned_users)
                )
                
                removal_results[cost_center_id] = removal_status
                successful_removals = sum(1 for success in removal_status.values() if success)
                total_removed += successful_removals
                
                if successful_removals < len(orphaned_users):
                    failed = len(orphaned_users) - successful_removals
                    self.logger.warning(
                        f"Failed to remove {failed}/{len(orphaned_users)} orphaned users from '{display_name}'"
                    )
        
        if total_orphaned > 0:
            self.logger.info(
                f"📊 Orphaned users summary: Found {total_orphaned} orphaned users, "
                f"successfully removed {total_removed}"
            )
        else:
            self.logger.info("✅ No orphaned users found - all cost centers are in sync with teams")
        
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

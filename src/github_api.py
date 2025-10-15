"""
GitHub API Manager for Copilot license operations.
"""

import logging
import re
import time
from typing import Dict, List, Optional
from datetime import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class BudgetsAPIUnavailableError(Exception):
    """Raised when the GitHub Budgets API is not available for this enterprise."""
    pass


class GitHubCopilotManager:
    """Manages GitHub API operations for Copilot licenses."""
    
    def __init__(self, config):
        """Initialize the GitHub API manager."""
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.session = self._create_session()
        self.base_url = "https://api.github.com"
        
        # Enterprise-only API
        self.use_enterprise = True  
        self.enterprise_name = config.github_enterprise
        if not self.enterprise_name:
            raise ValueError("Enterprise name is required")
        
    def _create_session(self) -> requests.Session:
        """Create a configured requests session with retry logic."""
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set headers
        session.headers.update({
            "Authorization": f"token {self.config.github_token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "cost-center-automation",
            "X-GitHub-Api-Version": "2022-11-28"
        })
        
        return session
    
    def _make_request(self, url: str, params: Optional[Dict] = None, method: str = 'GET', 
                     json: Optional[Dict] = None, custom_headers: Optional[Dict] = None) -> Dict:
        """Make a GitHub API request with error handling."""
        try:
            # Prepare headers
            headers = {}
            if custom_headers:
                headers.update(custom_headers)
            
            # Make the request based on method
            if method.upper() == 'GET':
                response = self.session.get(url, params=params, headers=headers)
            elif method.upper() == 'POST':
                response = self.session.post(url, params=params, json=json, headers=headers)
            elif method.upper() == 'DELETE':
                response = self.session.delete(url, params=params, json=json, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # Handle rate limiting
            if response.status_code == 429:
                reset_time = int(response.headers.get('X-RateLimit-Reset', time.time() + 60))
                wait_time = reset_time - int(time.time()) + 1
                self.logger.warning(f"Rate limit hit. Waiting {wait_time} seconds...")
                time.sleep(wait_time)
                return self._make_request(url, params, method, json, custom_headers)
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.HTTPError as e:
            self.logger.error(f"API request failed: {str(e)}")
            raise  # Re-raise as HTTPError so specific handlers can catch it
        except requests.exceptions.RequestException as e:
            self.logger.error(f"API request failed: {str(e)}")
            raise
    
    def get_copilot_users(self) -> List[Dict]:
        """Get all Copilot license holders in the enterprise."""
        if not (self.use_enterprise and self.enterprise_name):
            raise ValueError("Enterprise name must be configured to fetch Copilot users")
        self.logger.info(f"Fetching Copilot users for enterprise: {self.enterprise_name}")
        url = f"{self.base_url}/enterprises/{self.enterprise_name}/copilot/billing/seats"
        
        all_users = []
        page = 1
        per_page = 100
        
        while True:
            params = {"page": page, "per_page": per_page}
            response_data = self._make_request(url, params)
            
            seats = response_data.get("seats", [])
            if not seats:
                break
            
            for seat in seats:
                user_info = seat.get("assignee", {})
                user_data = {
                    "login": user_info.get("login"),
                    "id": user_info.get("id"),
                    "name": user_info.get("name"),
                    "email": user_info.get("email"),
                    "type": user_info.get("type"),
                    "created_at": seat.get("created_at"),
                    "updated_at": seat.get("updated_at"),
                    "pending_cancellation_date": seat.get("pending_cancellation_date"),
                    "last_activity_at": seat.get("last_activity_at"),
                    "last_activity_editor": seat.get("last_activity_editor"),
                    "plan": seat.get("plan"),
                    # Enterprise-specific fields
                    "assigning_team": seat.get("assigning_team")
                }
                all_users.append(user_data)
            
            self.logger.info(f"Fetched page {page} with {len(seats)} users")
            page += 1
            
            # Check if we have more pages
            if len(seats) < per_page:
                break
        
        self.logger.info(f"Total Copilot users found: {len(all_users)}")
        # Deduplicate users by login (some API anomalies can return duplicates)
        seen_logins = set()
        unique_users = []
        duplicate_counts = {}
        for user in all_users:
            login = user.get("login")
            if not login:
                # Skip entries without a login (unexpected)
                continue
            if login in seen_logins:
                duplicate_counts[login] = duplicate_counts.get(login, 0) + 1
                continue
            seen_logins.add(login)
            unique_users.append(user)

        if duplicate_counts:
            total_dups = sum(duplicate_counts.values())
            sample = ", ".join(f"{k} (+{v})" for k, v in list(duplicate_counts.items())[:10])
            if len(duplicate_counts) > 10:
                sample += ", ..."
            self.logger.warning(
                f"Detected and skipped {total_dups} duplicate seat entries across {len(duplicate_counts)} users: {sample}"
            )
            self.logger.info(f"Unique Copilot users after de-duplication: {len(unique_users)}")
        return unique_users
    

    
    def get_user_details(self, username: str) -> Dict:
        """Get detailed information for a specific user."""
        url = f"{self.base_url}/users/{username}"
        return self._make_request(url)
    
    # Removed organization/team membership methods for enterprise-only focus
    
    # Removed get_copilot_cost_center_assignments as the tool now always assigns deterministically
    
    def add_users_to_cost_center(self, cost_center_id: str, usernames: List[str], ignore_current_cost_center: bool = False) -> Dict[str, bool]:
        """Add multiple users (up to 50) to a specific cost center.
        
        By default, skips users who already belong to any cost center. Use ignore_current_cost_center=True
        to add users regardless of their current cost center membership.
        
        Args:
            cost_center_id: Target cost center ID
            usernames: List of usernames to add
            ignore_current_cost_center: If True, add users even if they belong to another cost center
        
        Returns:
            Dict mapping username -> success status for detailed logging
        """
        if not self.use_enterprise or not self.enterprise_name:
            self.logger.warning("Cost center assignment updates only available for GitHub Enterprise")
            return {username: False for username in usernames}
        
        if len(usernames) > 50:
            self.logger.error(f"Cannot add more than 50 users at once. Got {len(usernames)} users.")
            return {username: False for username in usernames}
        
        users_to_add = []
        users_already_in_target = []
        users_in_other_cost_center = []
        
        # Check if users are already in the target cost center for safety
        # (this may be redundant if bulk check was done at batch level, but ensures correctness)
        current_members_in_target = set(self.get_cost_center_members(cost_center_id))
        self.logger.debug(f"get_cost_center_members returned {len(current_members_in_target)} members for {cost_center_id}")
        users_in_target = [u for u in usernames if u in current_members_in_target]
        users_not_in_target = [u for u in usernames if u not in current_members_in_target]
        
        # Only log bulk check if there are users already in target (avoid noise)
        if users_in_target:
            self.logger.info(f"🔍 Bulk membership check: {len(users_in_target)}/{len(usernames)} already in target cost center {cost_center_id}")
        
        # Mark users already in target as successful (no need to add)
        for username in users_in_target:
            users_already_in_target.append(username)
            self.logger.debug(f"User {username} already in target cost center {cost_center_id}")
        
        if ignore_current_cost_center:
            # Fast path: add all users NOT in target, don't check if they're in other cost centers
            users_to_add = users_not_in_target.copy()
            self.logger.debug(f"ignore_current_cost_center=True: Adding {len(users_to_add)} users without checking other cost centers")
        else:
            # Safe path: check if users NOT in target are in OTHER cost centers
            self.logger.debug(f"ignore_current_cost_center=False: Checking {len(users_not_in_target)} users for membership in other cost centers")
            
            for username in users_not_in_target:
                existing_membership = self.check_user_cost_center_membership(username)
                
                if existing_membership:
                    # User is in a different cost center
                    existing_cost_center_name = existing_membership.get('cost_center_name', existing_membership.get('cost_center_id'))
                    users_in_other_cost_center.append((username, existing_cost_center_name))
                    self.logger.info(f"Skipping {username} - already in cost center '{existing_cost_center_name}' (use --check-current-cost-center to override)")
                else:
                    # User is not in any cost center, safe to add
                    users_to_add.append(username)
        
        # Log summary of what we found
        if users_already_in_target:
            self.logger.debug(f"Skipping {len(users_already_in_target)} users already in target cost center {cost_center_id}")
        
        if users_in_other_cost_center:
            self.logger.info(f"Skipping {len(users_in_other_cost_center)} users already in other cost centers:")
            for username, cost_center_name in users_in_other_cost_center:
                self.logger.info(f"  - {username} → currently in '{cost_center_name}'")
        
        # If no users need to be added, return appropriate status
        if not users_to_add:
            results = {}
            # Users already in target cost center get success status
            for username in users_already_in_target:
                results[username] = True
            # Users in other cost centers get failure status (unless ignoring)
            for username, _ in users_in_other_cost_center:
                results[username] = False
            
            if users_already_in_target and not users_in_other_cost_center:
                self.logger.info(f"All {len(usernames)} users already assigned to cost center {cost_center_id}")
            
            return results
        
        total_skipped = len(users_already_in_target) + len(users_in_other_cost_center)
        self.logger.info(f"Adding {len(users_to_add)} users to cost center {cost_center_id} (skipping {total_skipped} already assigned or in other cost centers)")
            
        url = f"{self.base_url}/enterprises/{self.enterprise_name}/settings/billing/cost-centers/{cost_center_id}/resource"
        
        payload = {
            "users": users_to_add  # Only send users who need to be added
        }
        
        # Set proper headers including API version
        headers = {
            "accept": "application/vnd.github+json",
            "x-github-api-version": "2022-11-28",
            "content-type": "application/json"
        }
        
        try:
            response = self.session.post(url, json=payload, headers=headers)
            
            # Handle rate limiting
            if response.status_code == 429:
                reset_time = int(response.headers.get('X-RateLimit-Reset', time.time() + 60))
                wait_time = reset_time - int(time.time()) + 1
                self.logger.warning(f"Rate limit hit. Waiting {wait_time} seconds...")
                time.sleep(wait_time)
                return self.add_users_to_cost_center(cost_center_id, usernames)
            
            if response.status_code in [200, 201, 204]:
                self.logger.info(f"✅ Successfully added {len(users_to_add)} users to cost center {cost_center_id}")
                
                for username in users_to_add:
                    self.logger.info(f"   ✅ {username} → {cost_center_id}")
                
                # Return success for users who were added and those already in target
                results = {username: True for username in users_to_add + users_already_in_target}
                # Users in other cost centers get failure status (unless they were moved)
                for username, _ in users_in_other_cost_center:
                    if username not in users_to_add:  # Wasn't moved
                        results[username] = False
                return results
            else:
                self.logger.error(f"❌ Failed to add users to cost center {cost_center_id}: {response.status_code} {response.text}")
                for username in users_to_add:
                    self.logger.error(f"   ❌ {username} → {cost_center_id} (API Error)")
                # Failed users get False, users already in target get True
                results = {username: False for username in users_to_add}
                results.update({username: True for username in users_already_in_target})
                # Users in other cost centers get failure status
                for username, _ in users_in_other_cost_center:
                    results[username] = False
                return results
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"❌ Error adding users to cost center {cost_center_id}: {str(e)}")
            for username in users_to_add:
                self.logger.error(f"   ❌ {username} → {cost_center_id} (Network Error)")
            # Failed users get False, users already in target get True
            results = {username: False for username in users_to_add}
            results.update({username: True for username in users_already_in_target})
            # Users in other cost centers get failure status
            for username, _ in users_in_other_cost_center:
                results[username] = False
            return results

    def bulk_update_cost_center_assignments(self, cost_center_assignments: Dict[str, List[str]], ignore_current_cost_center: bool = False) -> Dict[str, Dict[str, bool]]:
        """
        Bulk update cost center assignments for multiple users.
        
        Args:
            cost_center_assignments: Dict mapping cost_center_id -> list of usernames
            ignore_current_cost_center: If True, add users even if they belong to another cost center
            
        Returns:
            Dict mapping cost_center_id -> Dict mapping username -> success status
        """
        results = {}
        total_users = sum(len(usernames) for usernames in cost_center_assignments.values())
        successful_users = 0
        failed_users = 0
        
        for cost_center_id, usernames in cost_center_assignments.items():
            if not usernames:
                continue
                
            # OPTIMIZATION: Check bulk membership BEFORE batching to avoid unnecessary batches
            # This is especially important when most/all users are already in the correct cost center
            current_members_in_target = set(self.get_cost_center_members(cost_center_id))
            users_already_in_target = [u for u in usernames if u in current_members_in_target]
            users_not_in_target = [u for u in usernames if u not in current_members_in_target]
            
            self.logger.info(f"🔍 Bulk membership check: {len(users_already_in_target)}/{len(usernames)} already in target cost center {cost_center_id}")
            
            # If all users are already in target, skip batching entirely
            if not users_not_in_target:
                self.logger.info(f"All {len(usernames)} users already assigned to cost center {cost_center_id}")
                cost_center_results = {username: True for username in usernames}
            else:
                # Only create batches for users who actually need to be processed
                usernames_to_process = users_not_in_target if ignore_current_cost_center else usernames
                batch_size = 50
                batches = [usernames_to_process[i:i + batch_size] for i in range(0, len(usernames_to_process), batch_size)]
                
                self.logger.info(f"Processing {len(usernames_to_process)} users for cost center {cost_center_id} in {len(batches)} batches")
                
                cost_center_results = {}
                # Add users already in target as successful
                for username in users_already_in_target:
                    cost_center_results[username] = True
                
                for i, batch in enumerate(batches, 1):
                    self.logger.info(f"Processing batch {i}/{len(batches)} ({len(batch)} users) for cost center {cost_center_id}")
                    batch_results = self.add_users_to_cost_center(cost_center_id, batch, ignore_current_cost_center)
                    cost_center_results.update(batch_results)
                
                batch_success_count = sum(1 for success in batch_results.values() if success)
                batch_failure_count = len(batch_results) - batch_success_count
                
                if batch_failure_count > 0:
                    self.logger.warning(f"Batch {i} completed: {batch_success_count} successful, {batch_failure_count} failed")
                else:
                    self.logger.info(f"Batch {i} completed: all {batch_success_count} users successful")
            
            results[cost_center_id] = cost_center_results
            
            # Count successes and failures for this cost center
            cc_successful = sum(1 for success in cost_center_results.values() if success)
            cc_failed = len(cost_center_results) - cc_successful
            successful_users += cc_successful
            failed_users += cc_failed
        
        # Log final summary
        self.logger.info(f"📊 ASSIGNMENT RESULTS: {successful_users}/{total_users} users successfully assigned")
        if failed_users > 0:
            self.logger.error(f"⚠️  {failed_users} users failed assignment")
        else:
            self.logger.info("🎉 All users successfully assigned!")
            
        return results
    
    def get_rate_limit_status(self) -> Dict:
        """Get current rate limit status."""
        url = f"{self.base_url}/rate_limit"
        return self._make_request(url)
    
    def list_org_teams(self, org: str) -> List[Dict]:
        """
        List all teams in an organization.
        
        Args:
            org: Organization name
            
        Returns:
            List of team dictionaries with id, name, slug, description, etc.
        """
        self.logger.info(f"Fetching teams for organization: {org}")
        url = f"{self.base_url}/orgs/{org}/teams"
        
        all_teams = []
        page = 1
        per_page = 100
        
        while True:
            params = {"page": page, "per_page": per_page}
            
            try:
                response_data = self._make_request(url, params)
                
                # Response is a list directly for teams endpoint
                if not isinstance(response_data, list):
                    self.logger.error(f"Unexpected response format for teams: {type(response_data)}")
                    break
                
                teams = response_data
                if not teams:
                    break
                
                all_teams.extend(teams)
                self.logger.info(f"Fetched page {page} with {len(teams)} teams")
                
                page += 1
                
                # Check if we have more pages
                if len(teams) < per_page:
                    break
                    
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Failed to fetch teams for org {org}: {str(e)}")
                break
        
        self.logger.info(f"Total teams found in {org}: {len(all_teams)}")
        return all_teams
    
    def get_team_members(self, org: str, team_slug: str) -> List[Dict]:
        """
        Get all members of a specific team.
        
        Args:
            org: Organization name
            team_slug: Team slug (URL-friendly team name)
            
        Returns:
            List of team member dictionaries with login, id, name, etc.
        """
        self.logger.debug(f"Fetching members for team: {org}/{team_slug}")
        url = f"{self.base_url}/orgs/{org}/teams/{team_slug}/members"
        
        all_members = []
        page = 1
        per_page = 100
        
        while True:
            params = {"page": page, "per_page": per_page}
            
            try:
                response_data = self._make_request(url, params)
                
                # Response is a list directly for members endpoint
                if not isinstance(response_data, list):
                    self.logger.error(f"Unexpected response format for team members: {type(response_data)}")
                    break
                
                members = response_data
                if not members:
                    break
                
                all_members.extend(members)
                self.logger.debug(f"Fetched page {page} with {len(members)} members for {org}/{team_slug}")
                
                page += 1
                
                # Check if we have more pages
                if len(members) < per_page:
                    break
                    
            except requests.exceptions.RequestException as e:
                self.logger.warning(f"Failed to fetch members for team {org}/{team_slug}: {str(e)}")
                break
        
        self.logger.info(f"Total members found in {org}/{team_slug}: {len(all_members)}")
        return all_members
    
    def list_enterprise_teams(self) -> List[Dict]:
        """
        List all teams in the enterprise.
        
        Returns:
            List of team dictionaries with id, name, slug, description, etc.
        """
        if not self.use_enterprise or not self.enterprise_name:
            self.logger.error("Enterprise name required for listing enterprise teams")
            return []
        
        self.logger.info(f"Fetching enterprise teams for: {self.enterprise_name}")
        url = f"{self.base_url}/enterprises/{self.enterprise_name}/teams"
        
        all_teams = []
        page = 1
        per_page = 100
        
        while True:
            params = {"page": page, "per_page": per_page}
            
            try:
                response_data = self._make_request(url, params)
                
                # Response is a list directly for teams endpoint
                if not isinstance(response_data, list):
                    self.logger.error(f"Unexpected response format for enterprise teams: {type(response_data)}")
                    break
                
                teams = response_data
                if not teams:
                    break
                
                all_teams.extend(teams)
                self.logger.info(f"Fetched page {page} with {len(teams)} enterprise teams")
                
                page += 1
                
                # Check if we have more pages
                if len(teams) < per_page:
                    break
                    
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Failed to fetch enterprise teams: {str(e)}")
                break
        
        self.logger.info(f"Total enterprise teams found: {len(all_teams)}")
        return all_teams
    
    def get_enterprise_team_members(self, team_slug: str) -> List[Dict]:
        """
        Get all members of a specific enterprise team.
        
        Args:
            team_slug: Team slug (URL-friendly team name)
            
        Returns:
            List of team member dictionaries with login, id, name, etc.
        """
        if not self.use_enterprise or not self.enterprise_name:
            self.logger.error("Enterprise name required for fetching enterprise team members")
            return []
        
        self.logger.debug(f"Fetching members for enterprise team: {team_slug}")
        url = f"{self.base_url}/enterprises/{self.enterprise_name}/teams/{team_slug}/memberships"
        
        all_members = []
        page = 1
        per_page = 100
        
        while True:
            params = {"page": page, "per_page": per_page}
            
            try:
                response_data = self._make_request(url, params)
                
                # Response is a list directly for memberships endpoint
                if not isinstance(response_data, list):
                    self.logger.error(f"Unexpected response format for enterprise team members: {type(response_data)}")
                    self.logger.debug(f"Response data: {response_data}")
                    break
                
                members = response_data
                if not members:
                    break
                
                # Enterprise teams memberships endpoint returns user objects directly (not wrapped)
                # Just add them all to our list
                all_members.extend(members)
                
                self.logger.debug(f"Fetched page {page} with {len(members)} members for enterprise team {team_slug}")
                
                page += 1
                
                # Check if we have more pages
                if len(members) < per_page:
                    break
                    
            except requests.exceptions.RequestException as e:
                self.logger.warning(f"Failed to fetch members for enterprise team {team_slug}: {str(e)}")
                break
        
        self.logger.info(f"Total members found in enterprise team {team_slug}: {len(all_members)}")
        return all_members
    
    def get_all_active_cost_centers(self) -> Dict[str, str]:
        """
        Get all active cost centers from the enterprise for performance optimization.
        
        Returns:
            Dict mapping cost center name -> cost center ID
        """
        if not self.use_enterprise or not self.enterprise_name:
            self.logger.error("Cost center operations only available for GitHub Enterprise")
            return {}
            
        url = f"{self.base_url}/enterprises/{self.enterprise_name}/settings/billing/cost-centers"
        
        try:
            response_data = self._make_request(url)
            cost_centers = response_data.get('costCenters', [])
            
            active_centers_map = {}
            for cc in cost_centers:
                if cc.get('state', '').lower() == 'active':
                    name = cc.get('name', '')
                    uuid = cc.get('id', '')
                    if name and uuid:
                        active_centers_map[name] = uuid
            
            self.logger.debug(f"Found {len(active_centers_map)} active cost centers out of {len(cost_centers)} total")
            return active_centers_map
            
        except Exception as e:
            self.logger.error(f"Error fetching active cost centers: {str(e)}")
            return {}
    
    def create_cost_center(self, name: str) -> Optional[str]:
        """
        Create a new cost center in the enterprise.
        
        Args:
            name: The name for the new cost center
            
        Returns:
            The cost center ID if successful, None if failed
        """
        if not self.use_enterprise or not self.enterprise_name:
            self.logger.error("Cost center creation only available for GitHub Enterprise")
            return None
            
        url = f"{self.base_url}/enterprises/{self.enterprise_name}/settings/billing/cost-centers"
        
        payload = {
            "name": name
        }
        
        # Set proper headers including API version
        headers = {
            "accept": "application/vnd.github+json",
            "x-github-api-version": "2022-11-28",
            "content-type": "application/json"
        }
        
        try:
            response = self.session.post(url, json=payload, headers=headers)
            
            # Handle rate limiting
            if response.status_code == 429:
                reset_time = int(response.headers.get('X-RateLimit-Reset', time.time() + 60))
                wait_time = reset_time - int(time.time()) + 1
                self.logger.warning(f"Rate limit hit. Waiting {wait_time} seconds...")
                time.sleep(wait_time)
                return self.create_cost_center(name)
            
            if response.status_code in [200, 201]:
                response_data = response.json()
                cost_center_id = response_data.get('id')
                self.logger.info(f"Successfully created cost center '{name}' with ID: {cost_center_id}")
                return cost_center_id
            elif response.status_code == 409:
                # Cost center already exists - try to extract UUID from error message first
                self.logger.info(f"Cost center '{name}' already exists, extracting existing ID...")
                
                try:
                    response_data = response.json()
                    error_message = response_data.get('message', '')
                    
                    # Try to extract UUID from message: "...existing cost center UUID: <uuid>..."
                    uuid_pattern = r'existing cost center UUID:\s*([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})'
                    match = re.search(uuid_pattern, error_message, re.IGNORECASE)
                    
                    if match:
                        cost_center_id = match.group(1)
                        self.logger.info(f"Extracted existing cost center ID from API response: {cost_center_id}")
                        return cost_center_id
                    else:
                        self.logger.warning(f"Could not extract UUID from 409 response message: {error_message}")
                        self.logger.info("Falling back to name search to find existing cost center...")
                        return self._find_cost_center_by_name(name)
                        
                except (ValueError, KeyError) as e:
                    self.logger.warning(f"Could not parse 409 response: {str(e)}, falling back to name search...")
                    return self._find_cost_center_by_name(name)
            else:
                self.logger.error(f"Failed to create cost center '{name}': {response.status_code} {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error creating cost center '{name}': {str(e)}")
            return None
    
    def create_cost_center_with_preload_fallback(self, name: str, active_centers_map: Dict[str, str]) -> Optional[str]:
        """
        Create a cost center with preload optimization and fallback to collision handling.
        
        Args:
            name: The name for the new cost center
            active_centers_map: Preloaded map of active cost center names to IDs
            
        Returns:
            The cost center ID if successful, None if failed
        """
        if not self.use_enterprise or not self.enterprise_name:
            self.logger.error("Cost center creation only available for GitHub Enterprise")
            return None
        
        # Check if it already exists in the preloaded map
        if name in active_centers_map:
            cost_center_id = active_centers_map[name]
            self.logger.debug(f"Found existing cost center in preload map: '{name}' → {cost_center_id}")
            return cost_center_id
            
        url = f"{self.base_url}/enterprises/{self.enterprise_name}/settings/billing/cost-centers"
        
        payload = {
            "name": name
        }
        
        # Set proper headers including API version
        headers = {
            "accept": "application/vnd.github+json",
            "x-github-api-version": "2022-11-28",
            "content-type": "application/json"
        }
        
        try:
            response = self.session.post(url, json=payload, headers=headers)
            
            # Handle rate limiting
            if response.status_code == 429:
                reset_time = int(response.headers.get('X-RateLimit-Reset', time.time() + 60))
                wait_time = reset_time - int(time.time()) + 1
                self.logger.warning(f"Rate limit hit. Waiting {wait_time} seconds...")
                time.sleep(wait_time)
                return self.create_cost_center_with_preload_fallback(name, active_centers_map)
            
            if response.status_code in [200, 201]:
                response_data = response.json()
                cost_center_id = response_data.get('id')
                self.logger.info(f"Successfully created cost center '{name}' with ID: {cost_center_id}")
                # Update the preload map for subsequent calls in the same batch
                active_centers_map[name] = cost_center_id
                return cost_center_id
            elif response.status_code == 409:
                # Race condition - someone else created it between preload and now
                self.logger.info(f"Cost center '{name}' was created by another process (race condition)")
                
                try:
                    response_data = response.json()
                    error_message = response_data.get('message', '')
                    
                    # Try to extract UUID from message first
                    uuid_pattern = r'existing cost center UUID:\s*([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})'
                    match = re.search(uuid_pattern, error_message, re.IGNORECASE)
                    
                    if match:
                        cost_center_id = match.group(1)
                        self.logger.info(f"Extracted cost center ID from race condition response: {cost_center_id}")
                        # Update the preload map for subsequent calls
                        active_centers_map[name] = cost_center_id
                        return cost_center_id
                    else:
                        # Fallback to original collision handling
                        self.logger.warning(f"Could not extract UUID from race condition response, falling back to name search")
                        cost_center_id = self._find_cost_center_by_name(name)
                        if cost_center_id:
                            active_centers_map[name] = cost_center_id
                        return cost_center_id
                        
                except (ValueError, KeyError) as e:
                    self.logger.warning(f"Could not parse race condition response: {str(e)}, falling back to name search...")
                    cost_center_id = self._find_cost_center_by_name(name)
                    if cost_center_id:
                        active_centers_map[name] = cost_center_id
                    return cost_center_id
            else:
                self.logger.error(f"Failed to create cost center '{name}': {response.status_code} {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error creating cost center '{name}': {str(e)}")
            return None
    
    def _find_cost_center_by_name(self, name: str) -> Optional[str]:
        """
        Find an ACTIVE cost center by name.
        
        Args:
            name: Name of the cost center to find
            
        Returns:
            Cost center ID if found and active, None otherwise
        """
        if not self.use_enterprise or not self.enterprise_name:
            return None
            
        url = f"{self.base_url}/enterprises/{self.enterprise_name}/settings/billing/cost-centers"
        
        try:
            response_data = self._make_request(url)
            cost_centers = response_data.get('costCenters', [])
            
            active_centers = []
            deleted_centers = []
            
            for center in cost_centers:
                if center.get('name') == name:
                    status = center.get('state', 'unknown').upper()
                    cost_center_id = center.get('id')
                    
                    if status == 'ACTIVE':
                        active_centers.append((cost_center_id, center))
                        self.logger.info(f"Found ACTIVE cost center '{name}' with ID: {cost_center_id}")
                        return cost_center_id
                    else:
                        deleted_centers.append((cost_center_id, status))
                        self.logger.warning(f"Found INACTIVE cost center '{name}' with ID: {cost_center_id}, status: {status}")
            
            # Log what we found for debugging
            if deleted_centers:
                inactive_list = [f"{cc_id} ({status})" for cc_id, status in deleted_centers]
                self.logger.error(f"❌ DELETED COST CENTER: '{name}' exists but is DELETED")
                self.logger.error(f"   Found {len(deleted_centers)} deleted cost center(s): {', '.join(inactive_list)}")
                self.logger.error(f"   ⚠️  Cannot assign users to deleted cost centers!")
                self.logger.error(f"   💡 Solution: Delete and recreate the cost center, or contact GitHub support to reactivate it")
            
            if not active_centers and not deleted_centers:
                self.logger.error(f"No cost center found with name '{name}' (despite 409 conflict)")
            else:
                self.logger.error(f"No ACTIVE cost center found with name '{name}' - only deleted ones exist")
            
            return None
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error finding cost center '{name}': {str(e)}")
            return None
    
    def ensure_cost_centers_exist(self, no_pru_cost_center_name: str = "00 - No PRU overages", 
                                 pru_allowed_cost_center_name: str = "01 - PRU overages allowed") -> Optional[Dict[str, str]]:
        """
        Ensure the required cost centers exist, creating them if necessary.
        
        Args:
            no_pru_cost_center_name: Name for the no-PRU cost center
            pru_allowed_cost_center_name: Name for the PRU-allowed cost center
            
        Returns:
            Dict with 'no_pru_id' and 'pru_allowed_id' if successful, None if failed
        """
        if not self.use_enterprise or not self.enterprise_name:
            self.logger.error("Cost center operations only available for GitHub Enterprise")
            return None
        
        # Try to create the cost centers (will handle 409 conflicts gracefully)
        self.logger.info(f"Ensuring cost center exists: {no_pru_cost_center_name}")
        no_pru_id = self.create_cost_center(no_pru_cost_center_name)
        if not no_pru_id:
            self.logger.error(f"Failed to ensure cost center exists: {no_pru_cost_center_name}")
            return None
        
        self.logger.info(f"Ensuring cost center exists: {pru_allowed_cost_center_name}")
        pru_allowed_id = self.create_cost_center(pru_allowed_cost_center_name)
        if not pru_allowed_id:
            self.logger.error(f"Failed to ensure cost center exists: {pru_allowed_cost_center_name}")
            return None
        
        result = {
            'no_pru_id': no_pru_id,
            'pru_allowed_id': pru_allowed_id
        }
        
        self.logger.info(f"Cost centers ready - No PRU: {no_pru_id}, PRU Allowed: {pru_allowed_id}")
        return result
    
    def get_cost_center_members(self, cost_center_id: str) -> List[str]:
        """
        Get all members (usernames) currently assigned to a cost center.
        
        Args:
            cost_center_id: The ID of the cost center
            
        Returns:
            List of usernames currently in the cost center
        """
        if not self.use_enterprise or not self.enterprise_name:
            self.logger.error("Cost center operations only available for GitHub Enterprise")
            return []
        
        url = f"{self.base_url}/enterprises/{self.enterprise_name}/settings/billing/cost-centers/{cost_center_id}"
        
        try:
            response_data = self._make_request(url)
            
            # The response contains a resources array with type and name fields
            resources = response_data.get('resources', [])
            usernames = []
            
            for resource in resources:
                # Each resource has 'type' (e.g., "User") and 'name' (username)
                if resource.get('type') == 'User':
                    username = resource.get('name')
                    if username:
                        usernames.append(username)
            
            self.logger.debug(f"Cost center {cost_center_id} has {len(usernames)} members")
            return usernames
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to get members for cost center {cost_center_id}: {str(e)}")
            return []
    
    def remove_users_from_cost_center(self, cost_center_id: str, usernames: List[str]) -> Dict[str, bool]:
        """
        Remove multiple users from a specific cost center.
        
        Args:
            cost_center_id: The ID of the cost center
            usernames: List of usernames to remove
            
        Returns:
            Dict mapping username -> success status
        """
        if not self.use_enterprise or not self.enterprise_name:
            self.logger.error("Cost center operations only available for GitHub Enterprise")
            return {user: False for user in usernames}
        
        if not usernames:
            return {}
        
        url = f"{self.base_url}/enterprises/{self.enterprise_name}/settings/billing/cost-centers/{cost_center_id}/resource"
        
        payload = {
            "users": usernames
        }
        
        headers = {
            "accept": "application/vnd.github+json",
            "x-github-api-version": "2022-11-28",
            "content-type": "application/json"
        }
        
        try:
            response = self.session.delete(url, json=payload, headers=headers)
            
            # Handle rate limiting
            if response.status_code == 429:
                reset_time = int(response.headers.get('X-RateLimit-Reset', time.time() + 60))
                wait_time = reset_time - int(time.time()) + 1
                self.logger.warning(f"Rate limit hit. Waiting {wait_time} seconds...")
                time.sleep(wait_time)
                return self.remove_users_from_cost_center(cost_center_id, usernames)
            
            if response.status_code in [200, 204]:
                self.logger.info(f"✅ Successfully removed {len(usernames)} users from cost center {cost_center_id}")
                for username in usernames:
                    self.logger.info(f"   ✅ {username} removed from {cost_center_id}")
                return {user: True for user in usernames}
            else:
                self.logger.error(
                    f"Failed to remove users from cost center {cost_center_id}: "
                    f"{response.status_code} {response.text}"
                )
                return {user: False for user in usernames}
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error removing users from cost center {cost_center_id}: {str(e)}")
            return {user: False for user in usernames}
    
    def check_user_cost_center_membership(self, username: str) -> Optional[Dict]:
        """
        Check if a user belongs to any cost center.
        
        Args:
            username: The username to check
            
        Returns:
            Dict with cost center info if user belongs to one, None if user is not in any cost center
            Format: {"cost_center_id": "abc-123", "cost_center_name": "Team Engineering"}
        """
        if not self.use_enterprise or not self.enterprise_name:
            self.logger.error("Cost center operations only available for GitHub Enterprise")
            return None
        
        url = f"{self.base_url}/enterprises/{self.enterprise_name}/settings/billing/cost-centers/memberships"
        params = {
            "resource_type": "user",
            "name": username
        }
        
        try:
            response_data = self._make_request(url, params=params)
            
            # The API returns {"resource": {...}, "memberships": [...]}
            # Extract the memberships list
            memberships = response_data.get('memberships', []) if response_data else []
            
            if memberships and len(memberships) > 0:
                membership_info = memberships[0]  # User should only belong to one cost center
                cost_center = membership_info.get('cost_center', {})
                
                # Extract the cost center info in the format our code expects
                result = {
                    'cost_center_id': cost_center.get('id'),
                    'cost_center_name': cost_center.get('name')
                }
                
                self.logger.debug(f"User {username} belongs to cost center: {result.get('cost_center_id')}")
                return result
            else:
                self.logger.debug(f"User {username} does not belong to any cost center")
                return None
                
        except requests.exceptions.RequestException as e:
            self.logger.debug(f"Failed to check cost center membership for {username}: {str(e)}")
            return None
    
    def check_cost_center_has_budget(self, cost_center_id: str, cost_center_name: str) -> bool:
        """
        Check if a cost center already has a budget.
        
        Due to a known bug in the Budget API, when we create a budget with the cost center UUID
        as budget_entity_name, the API stores the cost center NAME instead. So we need to 
        check against the name, not the ID.
        
        Args:
            cost_center_id: UUID of the cost center to check
            cost_center_name: Name of the cost center to check
            
        Returns:
            True if a budget already exists for this cost center, False otherwise
            
        Raises:
            BudgetsAPIUnavailableError: If the Budgets API is not available for this enterprise
        """
        if not self.use_enterprise or not self.enterprise_name:
            return False
        
        url = f"{self.base_url}/enterprises/{self.enterprise_name}/settings/billing/budgets"
        
        try:
            response_data = self._make_request(url)
            budgets = response_data.get('budgets', [])
            
            # Check if any budget has this cost center NAME as the entity name
            # (API bug: stores name even when we send ID)
            for budget in budgets:
                if budget.get('budget_scope') == 'cost_center' and budget.get('budget_entity_name') == cost_center_name:
                    self.logger.debug(f"Budget already exists for cost center '{cost_center_name}' (ID: {cost_center_id})")
                    return True
            
            return False
            
        except requests.exceptions.HTTPError as e:
            if hasattr(e, 'response') and e.response is not None and e.response.status_code == 404:
                raise BudgetsAPIUnavailableError(f"Budgets API is not available for enterprise '{self.enterprise_name}'. This feature may not be enabled for your enterprise.")
            self.logger.warning(f"Failed to check budget for cost center '{cost_center_name}' (ID: {cost_center_id}): {str(e)}")
            return False
        except requests.exceptions.RequestException as e:
            self.logger.warning(f"Failed to check budget for cost center '{cost_center_name}' (ID: {cost_center_id}): {str(e)}")
            return False
    
    def create_cost_center_budget(self, cost_center_id: str, cost_center_name: str) -> bool:
        """
        Create a budget for a cost center using the GitHub Enterprise Budgets API.
        
        This method uses unreleased GitHub APIs and should only be used when the 
        --create-budgets flag is explicitly passed.
        
        Args:
            cost_center_id: UUID of the cost center to create a budget for
            cost_center_name: Name of the cost center (used for logging only)
            
        Returns:
            True if budget was created successfully, False otherwise
            
        Raises:
            BudgetsAPIUnavailableError: If the Budgets API is not available for this enterprise
        """
        if not self.use_enterprise or not self.enterprise_name:
            self.logger.error("Budget creation only available for GitHub Enterprise")
            return False
        
        # Check if budget already exists (this may raise BudgetsAPIUnavailableError)
        try:
            if self.check_cost_center_has_budget(cost_center_id, cost_center_name):
                self.logger.info(f"Budget already exists for cost center: {cost_center_name} (ID: {cost_center_id})")
                return True
        except BudgetsAPIUnavailableError:
            # Re-raise the exception to be handled by the caller
            raise
        
        url = f"{self.base_url}/enterprises/{self.enterprise_name}/settings/billing/budgets"
        
        payload = {
            "budget_type": "SkuPricing",
            "budget_product_sku": "copilot_premium_request",
            "budget_scope": "cost_center",
            "budget_amount": 0,
            "prevent_further_usage": True,
            "budget_entity_name": cost_center_id,  # Use UUID instead of name
            "budget_alerting": {
                "will_alert": False,
                "alert_recipients": []
            }
        }
        
        headers = {
            "accept": "application/vnd.github+json",
            "x-github-api-version": "2022-11-28",
            "content-type": "application/json"
        }
        
        try:
            response = self._make_request(url, method='POST', json=payload, custom_headers=headers)
            self.logger.info(f"Successfully created budget for cost center: {cost_center_name} (ID: {cost_center_id})")
            return True
            
        except requests.exceptions.HTTPError as e:
            if hasattr(e, 'response') and e.response is not None and e.response.status_code == 404:
                raise BudgetsAPIUnavailableError(f"Budgets API is not available for enterprise '{self.enterprise_name}'. This feature may not be enabled for your enterprise.")
            self.logger.error(f"Failed to create budget for cost center '{cost_center_name}' (ID: {cost_center_id}): {str(e)}")
            return False
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to create budget for cost center '{cost_center_name}' (ID: {cost_center_id}): {str(e)}")
            return False
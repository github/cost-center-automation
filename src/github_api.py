"""
GitHub API Manager for Copilot license operations.
"""

import logging
import time
from typing import Dict, List, Optional
from datetime import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


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
            "User-Agent": "Copilot-Cost-Center-Manager",
            "X-GitHub-Api-Version": "2022-11-28"
        })
        
        return session
    
    def _make_request(self, url: str, params: Optional[Dict] = None) -> Dict:
        """Make a GitHub API request with error handling."""
        try:
            response = self.session.get(url, params=params)
            
            # Handle rate limiting
            if response.status_code == 429:
                reset_time = int(response.headers.get('X-RateLimit-Reset', time.time() + 60))
                wait_time = reset_time - int(time.time()) + 1
                self.logger.warning(f"Rate limit hit. Waiting {wait_time} seconds...")
                time.sleep(wait_time)
                return self._make_request(url, params)
            
            response.raise_for_status()
            return response.json()
            
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
    
    def filter_users_by_timestamp(self, users: List[Dict], since_timestamp: datetime) -> List[Dict]:
        """Filter users to only include those created after the given timestamp."""
        filtered_users = []
        
        for user in users:
            created_at_str = user.get('created_at')
            if not created_at_str:
                # If no creation timestamp, include the user (safer approach)
                filtered_users.append(user)
                continue
            
            try:
                # Parse the GitHub timestamp (e.g., "2025-04-15T23:45:31-05:00")
                created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                
                if created_at > since_timestamp:
                    filtered_users.append(user)
                    self.logger.debug(f"Including user {user.get('login')} (created: {created_at_str})")
                else:
                    self.logger.debug(f"Skipping user {user.get('login')} (created: {created_at_str} <= {since_timestamp})")
                    
            except Exception as e:
                self.logger.warning(f"Failed to parse timestamp for user {user.get('login')}: {e}")
                # Include user if timestamp parsing fails (safer approach)
                filtered_users.append(user)
        
        self.logger.info(f"Filtered {len(users)} users to {len(filtered_users)} users created after {since_timestamp}")
        return filtered_users
    
    def get_user_details(self, username: str) -> Dict:
        """Get detailed information for a specific user."""
        url = f"{self.base_url}/users/{username}"
        return self._make_request(url)
    
    # Removed organization/team membership methods for enterprise-only focus
    
    # Removed get_copilot_cost_center_assignments as the tool now always assigns deterministically
    
    def add_users_to_cost_center(self, cost_center_id: str, usernames: List[str]) -> Dict[str, bool]:
        """Add multiple users (up to 50) to a specific cost center.
        
        Returns:
            Dict mapping username -> success status for detailed logging
        """
        if not self.use_enterprise or not self.enterprise_name:
            self.logger.warning("Cost center assignment updates only available for GitHub Enterprise")
            return {username: False for username in usernames}
        
        if len(usernames) > 50:
            self.logger.error(f"Cannot add more than 50 users at once. Got {len(usernames)} users.")
            return {username: False for username in usernames}
            
        url = f"{self.base_url}/enterprises/{self.enterprise_name}/settings/billing/cost-centers/{cost_center_id}/resource"
        
        payload = {
            "users": usernames
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
                self.logger.info(f"✅ Successfully assigned {len(usernames)} users to cost center {cost_center_id}")
                for username in usernames:
                    self.logger.info(f"   ✅ {username} → {cost_center_id}")
                return {username: True for username in usernames}
            else:
                self.logger.error(f"❌ Failed to assign users to cost center {cost_center_id}: {response.status_code} {response.text}")
                for username in usernames:
                    self.logger.error(f"   ❌ {username} → {cost_center_id} (API Error)")
                return {username: False for username in usernames}
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"❌ Error assigning users to cost center {cost_center_id}: {str(e)}")
            for username in usernames:
                self.logger.error(f"   ❌ {username} → {cost_center_id} (Network Error)")
            return {username: False for username in usernames}

    def bulk_update_cost_center_assignments(self, cost_center_assignments: Dict[str, List[str]]) -> Dict[str, Dict[str, bool]]:
        """
        Bulk update cost center assignments for multiple users.
        
        Args:
            cost_center_assignments: Dict mapping cost_center_id -> list of usernames
            
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
                
            # Process users in batches of 50
            batch_size = 50
            batches = [usernames[i:i + batch_size] for i in range(0, len(usernames), batch_size)]
            
            self.logger.info(f"Processing {len(usernames)} users for cost center {cost_center_id} in {len(batches)} batches")
            
            cost_center_results = {}
            for i, batch in enumerate(batches, 1):
                self.logger.info(f"Processing batch {i}/{len(batches)} ({len(batch)} users) for cost center {cost_center_id}")
                batch_results = self.add_users_to_cost_center(cost_center_id, batch)
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
                # Cost center already exists, find it by name
                self.logger.info(f"Cost center '{name}' already exists, finding existing ID...")
                return self._find_cost_center_by_name(name)
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
                self.logger.warning(f"Found {len(deleted_centers)} inactive cost centers with name '{name}': {', '.join(inactive_list)}")
            
            if not active_centers and not deleted_centers:
                self.logger.error(f"No cost center found with name '{name}' (despite 409 conflict)")
            else:
                self.logger.error(f"No ACTIVE cost center found with name '{name}' - only inactive ones exist")
            
            return None
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error finding cost center '{name}': {str(e)}")
            return None
    
    def ensure_cost_centers_exist(self, no_pru_name: str = "00 - No PRU overages", 
                                 pru_allowed_name: str = "01 - PRU overages allowed") -> Optional[Dict[str, str]]:
        """
        Ensure the required cost centers exist, creating them if necessary.
        
        Args:
            no_pru_name: Name for the no-PRU cost center
            pru_allowed_name: Name for the PRU-allowed cost center
            
        Returns:
            Dict with 'no_pru_id' and 'pru_allowed_id' if successful, None if failed
        """
        if not self.use_enterprise or not self.enterprise_name:
            self.logger.error("Cost center operations only available for GitHub Enterprise")
            return None
        
        # Try to create the cost centers (will handle 409 conflicts gracefully)
        self.logger.info(f"Ensuring cost center exists: {no_pru_name}")
        no_pru_id = self.create_cost_center(no_pru_name)
        if not no_pru_id:
            self.logger.error(f"Failed to ensure cost center exists: {no_pru_name}")
            return None
        
        self.logger.info(f"Ensuring cost center exists: {pru_allowed_name}")
        pru_allowed_id = self.create_cost_center(pru_allowed_name)
        if not pru_allowed_id:
            self.logger.error(f"Failed to ensure cost center exists: {pru_allowed_name}")
            return None
        
        result = {
            'no_pru_id': no_pru_id,
            'pru_allowed_id': pru_allowed_id
        }
        
        self.logger.info(f"Cost centers ready - No PRU: {no_pru_id}, PRU Allowed: {pru_allowed_id}")
        return result
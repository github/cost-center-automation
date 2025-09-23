"""
GitHub API Manager for Copilot license operations.
"""

import logging
import time
from typing import Dict, List, Optional
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
        
        # Determine if we're using enterprise or organization API
        self.use_enterprise = hasattr(config, 'github_enterprise') and config.github_enterprise
        self.enterprise_name = getattr(config, 'github_enterprise', None)
        self.org_name = getattr(config, 'github_org', None)
        
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
        """Get all Copilot license holders in the organization or enterprise."""
        if self.use_enterprise and self.enterprise_name:
            self.logger.info(f"Fetching Copilot users for enterprise: {self.enterprise_name}")
            url = f"{self.base_url}/enterprises/{self.enterprise_name}/copilot/billing/seats"
        elif self.org_name:
            self.logger.info(f"Fetching Copilot users for organization: {self.org_name}")
            url = f"{self.base_url}/orgs/{self.org_name}/copilot/billing/seats"
        else:
            raise ValueError("Either github_enterprise or github_org must be configured")
        
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
                    "assigning_team": seat.get("assigning_team"),
                    "organization": user_info.get("organization") if self.use_enterprise else None
                }
                all_users.append(user_data)
            
            self.logger.info(f"Fetched page {page} with {len(seats)} users")
            page += 1
            
            # Check if we have more pages
            if len(seats) < per_page:
                break
        
        self.logger.info(f"Total Copilot users found: {len(all_users)}")
        return all_users
    
    def get_user_details(self, username: str) -> Dict:
        """Get detailed information for a specific user."""
        url = f"{self.base_url}/users/{username}"
        return self._make_request(url)
    
    def get_user_org_membership(self, username: str) -> Dict:
        """Get user's organization membership details."""
        if not self.org_name:
            self.logger.warning("No organization configured, skipping org membership check")
            return {"status": "no_org_configured"}
            
        url = f"{self.base_url}/orgs/{self.org_name}/members/{username}"
        try:
            return self._make_request(url)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return {"status": "not_found"}
            raise
    
    def get_user_teams(self, username: str) -> List[Dict]:
        """Get teams that a user belongs to."""
        if not self.org_name:
            self.logger.warning("No organization configured, skipping team membership check")
            return []
            
        url = f"{self.base_url}/orgs/{self.org_name}/teams"
        all_teams = self._make_request(url)
        
        user_teams = []
        for team in all_teams:
            # Check if user is member of this team
            team_url = f"{self.base_url}/orgs/{self.org_name}/teams/{team['slug']}/members/{username}"
            try:
                self._make_request(team_url)
                user_teams.append(team)
            except requests.exceptions.HTTPError:
                # User is not a member of this team
                pass
        
        return user_teams
    
    # Removed get_copilot_cost_center_assignments as the tool now always assigns deterministically
    
    def add_users_to_cost_center(self, cost_center_id: str, usernames: List[str]) -> bool:
        """Add multiple users (up to 50) to a specific cost center."""
        if not self.use_enterprise or not self.enterprise_name:
            self.logger.warning("Cost center assignment updates only available for GitHub Enterprise")
            return False
        
        if len(usernames) > 50:
            self.logger.error(f"Cannot add more than 50 users at once. Got {len(usernames)} users.")
            return False
            
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
                self.logger.info(f"Successfully added {len(usernames)} users to cost center {cost_center_id}")
                return True
            else:
                self.logger.error(f"Failed to add users to cost center {cost_center_id}: {response.status_code} {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error adding users to cost center {cost_center_id}: {str(e)}")
            return False

    def bulk_update_cost_center_assignments(self, cost_center_assignments: Dict[str, List[str]]) -> Dict[str, bool]:
        """
        Bulk update cost center assignments for multiple users.
        
        Args:
            cost_center_assignments: Dict mapping cost_center_id -> list of usernames
            
        Returns:
            Dict mapping cost_center_id -> success status
        """
        results = {}
        
        for cost_center_id, usernames in cost_center_assignments.items():
            if not usernames:
                continue
                
            # Process users in batches of 50
            batch_size = 50
            batches = [usernames[i:i + batch_size] for i in range(0, len(usernames), batch_size)]
            
            self.logger.info(f"Processing {len(usernames)} users for cost center {cost_center_id} in {len(batches)} batches")
            
            batch_success = True
            for i, batch in enumerate(batches, 1):
                self.logger.info(f"Processing batch {i}/{len(batches)} ({len(batch)} users) for cost center {cost_center_id}")
                if not self.add_users_to_cost_center(cost_center_id, batch):
                    batch_success = False
                    self.logger.error(f"Failed to process batch {i} for cost center {cost_center_id}")
                else:
                    self.logger.info(f"Successfully processed batch {i} for cost center {cost_center_id}")
            
            results[cost_center_id] = batch_success
            
        return results
    
    def get_rate_limit_status(self) -> Dict:
        """Get current rate limit status."""
        url = f"{self.base_url}/rate_limit"
        return self._make_request(url)
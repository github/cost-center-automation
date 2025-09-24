"""
Simplified Cost Center Manager for PRUs-based assignment.
"""

import logging
from typing import Dict, List


class CostCenterManager:
    """Manages simplified cost center assignments for users."""
    
    def __init__(self, config, auto_create_enabled=False):
        """Initialize the cost center manager."""
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.cost_center_no_prus = config.no_prus_cost_center
        self.cost_center_prus_allowed = config.prus_allowed_cost_center
        self.prus_exception_users = set(config.prus_exception_users)
        self.current_assignments = {}
        
        self.logger.info(f"Initialized CostCenterManager with {len(self.prus_exception_users)} PRUs exception users")
        
        # Show better messages when auto-creation is enabled
        if auto_create_enabled or config.auto_create_cost_centers:
            self.logger.info(f"No PRUs cost center: Will create '{config.no_pru_cost_center_name}'")
            self.logger.info(f"PRUs allowed cost center: Will create '{config.pru_allowed_cost_center_name}'")
        else:
            self.logger.info(f"No PRUs cost center: {self.cost_center_no_prus}")
            self.logger.info(f"PRUs allowed cost center: {self.cost_center_prus_allowed}")

    def set_current_assignments(self, assignments: Dict[str, str]):
        """Set the current cost center assignments from GitHub Enterprise."""
        self.current_assignments = assignments
        self.logger.info(f"Loaded {len(assignments)} current cost center assignments")
    
    def assign_cost_center(self, user: Dict) -> str:
        """
        Assign a cost center to a user based on simplified PRUs logic.
        
        Rules:
        - If username is in PRUs exception list → prus_allowed_cost_center
        - Otherwise → no_prus_cost_center
        """
        username = user.get("login", "")
        
        if username in self.prus_exception_users:
            self.logger.debug(f"User {username} is in PRUs exception list → {self.cost_center_prus_allowed}")
            user["assignment_method"] = "prus_exception"
            return self.cost_center_prus_allowed
        else:
            self.logger.debug(f"User {username} is not in exception list → {self.cost_center_no_prus}")
            user["assignment_method"] = "default_no_prus"
            return self.cost_center_no_prus
    
    def bulk_assign_cost_centers(self, users: List[Dict]) -> List[Dict]:
        """Assign cost centers to a list of users."""
        self.logger.info(f"Bulk assigning cost centers for {len(users)} users")
        
        prus_count = 0
        no_prus_count = 0
        
        for user in users:
            cost_center = self.assign_cost_center(user)
            user["cost_center"] = cost_center
            
            if cost_center == self.cost_center_prus_allowed:
                prus_count += 1
            else:
                no_prus_count += 1
        
        self.logger.info(f"Assignment complete: {prus_count} PRUs allowed, {no_prus_count} no PRUs")
        return users
    
    def generate_summary(self, users: List[Dict]) -> Dict[str, int]:
        """Generate a summary of cost center assignments."""
        summary = {}
        
        for user in users:
            cost_center = user.get("cost_center", "Unassigned")
            summary[cost_center] = summary.get(cost_center, 0) + 1
        
        self.logger.info(f"Cost center summary: {len(summary)} unique cost centers")
        return summary
    
    def validate_configuration(self) -> List[str]:
        """Validate the simplified cost center configuration."""
        issues = []
        
        # Check if cost center IDs are defined
        if not self.cost_center_no_prus:
            issues.append("no_prus_cost_center is not defined")
        
        if not self.cost_center_prus_allowed:
            issues.append("prus_allowed_cost_center is not defined")
        
        # Check if cost center IDs are the same (would be confusing)
        if self.cost_center_no_prus == self.cost_center_prus_allowed:
            issues.append("no_prus_cost_center and prus_allowed_cost_center cannot be the same")
        
        # Validate exception users list
        if not isinstance(self.prus_exception_users, (list, set)):
            issues.append("prus_exception_users must be a list")
        
        return issues
    
    def get_cost_center_statistics(self, users: List[Dict]) -> Dict:
        """Get detailed statistics about cost center assignments."""
        prus_users = []
        no_prus_users = []
        
        for user in users:
            cost_center = user.get("cost_center")
            username = user.get("login")
            
            if cost_center == self.cost_center_prus_allowed:
                prus_users.append(username)
            elif cost_center == self.cost_center_no_prus:
                no_prus_users.append(username)
        
        stats = {
            "total_users": len(users),
            "prus_allowed": {
                "cost_center": self.cost_center_prus_allowed,
                "count": len(prus_users),
                "users": prus_users
            },
            "no_prus": {
                "cost_center": self.cost_center_no_prus,
                "count": len(no_prus_users),
                "users": no_prus_users
            },
            "configured_exceptions": len(self.prus_exception_users),
            "actual_exceptions": len(prus_users)
        }
        
        return stats
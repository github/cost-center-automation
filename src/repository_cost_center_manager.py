"""
Repository Cost Center Manager for assigning repositories to cost centers based on custom properties.
"""

import logging
from typing import Dict, List, Optional, Set


class RepositoryCostCenterManager:
    """Manages cost center assignments based on repository custom properties."""
    
    def __init__(self, config, github_api, create_budgets: bool = False):
        """Initialize the repository cost center manager.
        
        Args:
            config: Configuration object
            github_api: GitHubCopilotManager instance for API calls
            create_budgets: Whether to create budgets for cost centers
        """
        self.config = config
        self.github_api = github_api
        self.create_budgets = create_budgets
        self.logger = logging.getLogger(__name__)
        
        # Validate configuration
        if not hasattr(config, 'github_cost_centers_repository_config'):
            raise ValueError("Repository mode requires 'repository_config' in configuration")
        
        self.repo_config = config.github_cost_centers_repository_config
    
    def run(self, org_name: str) -> Dict[str, any]:
        """Main entry point for repository-based cost center assignment.
        
        Args:
            org_name: Organization name to process
            
        Returns:
            Summary dictionary with assignment results
        """
        self.logger.info("=" * 80)
        self.logger.info("Starting repository-based cost center assignment")
        self.logger.info("=" * 80)
        
        # Check which mode is configured
        if hasattr(self.repo_config, 'explicit_mappings'):
            return self.explicit_mapping_mode(org_name)
        else:
            raise ValueError(
                "Repository mode requires 'explicit_mappings' in repository_config. "
                "Please configure explicit mappings in your config file."
            )
    
    def explicit_mapping_mode(self, org_name: str) -> Dict[str, any]:
        """Map repositories to cost centers using explicit property value mappings.
        
        This mode allows users to define which custom property values map to which cost centers.
        For example, mapping property values ["platform", "infrastructure"] to "Platform Engineering" cost center.
        
        Args:
            org_name: Organization name to process
            
        Returns:
            Summary dictionary with assignment results
        """
        self.logger.info("Running in EXPLICIT MAPPING mode")
        self.logger.info(f"Organization: {org_name}")
        
        explicit_mappings = self.repo_config.explicit_mappings
        if not explicit_mappings:
            self.logger.error("No explicit mappings configured")
            return {"error": "No explicit mappings configured"}
        
        self.logger.info(f"Found {len(explicit_mappings)} cost center mapping(s) to process")
        
        # Fetch all repositories with their custom properties
        self.logger.info("Fetching all repositories with custom properties...")
        all_repos = self.github_api.get_all_org_repositories_with_properties(org_name)
        
        if not all_repos:
            self.logger.warning(f"No repositories found in organization '{org_name}'")
            return {"repositories_found": 0, "assignments": []}
        
        self.logger.info(f"Found {len(all_repos)} repositories in organization")
        
        # Get all existing cost centers for the enterprise
        self.logger.info("Fetching existing cost centers...")
        existing_cost_centers = self.github_api.get_cost_centers()
        cost_center_map = {cc['name']: cc for cc in existing_cost_centers}
        self.logger.info(f"Found {len(existing_cost_centers)} existing cost centers")
        
        summary = {
            "repositories_found": len(all_repos),
            "mappings_processed": 0,
            "assignments": []
        }
        
        # Process each explicit mapping
        for mapping_idx, mapping in enumerate(explicit_mappings, 1):
            self.logger.info("=" * 80)
            self.logger.info(f"Processing mapping {mapping_idx}/{len(explicit_mappings)}")
            
            cost_center_name = mapping.get('cost_center')
            property_name = mapping.get('property_name')
            property_values = mapping.get('property_values', [])
            
            if not cost_center_name or not property_name or not property_values:
                self.logger.error(
                    f"Invalid mapping configuration: cost_center='{cost_center_name}', "
                    f"property_name='{property_name}', property_values={property_values}"
                )
                continue
            
            self.logger.info(f"Cost Center: {cost_center_name}")
            self.logger.info(f"Property Name: {property_name}")
            self.logger.info(f"Property Values: {property_values}")
            
            # Find repositories matching this mapping
            matching_repos = self._find_matching_repositories(
                all_repos, 
                property_name, 
                property_values
            )
            
            if not matching_repos:
                self.logger.warning(
                    f"No repositories found with property '{property_name}' "
                    f"matching values: {property_values}"
                )
                summary['assignments'].append({
                    'cost_center': cost_center_name,
                    'property_name': property_name,
                    'property_values': property_values,
                    'repositories_matched': 0,
                    'repositories_assigned': 0,
                    'success': False,
                    'message': 'No matching repositories found'
                })
                continue
            
            self.logger.info(f"Found {len(matching_repos)} matching repositories")
            
            # Get or create cost center
            cost_center = cost_center_map.get(cost_center_name)
            
            if not cost_center:
                self.logger.info(f"Cost center '{cost_center_name}' does not exist, creating it...")
                try:
                    cost_center = self.github_api.create_cost_center(cost_center_name)
                    cost_center_map[cost_center_name] = cost_center
                    self.logger.info(
                        f"Successfully created cost center: {cost_center_name} "
                        f"(ID: {cost_center['id']})"
                    )
                    
                    # Create budgets if enabled
                    if self.create_budgets and hasattr(self.config, 'budgets_enabled') and self.config.budgets_enabled:
                        self._create_budgets_for_cost_center(cost_center['id'], cost_center_name)
                except Exception as e:
                    self.logger.error(f"Failed to create cost center '{cost_center_name}': {str(e)}")
                    summary['assignments'].append({
                        'cost_center': cost_center_name,
                        'property_name': property_name,
                        'property_values': property_values,
                        'repositories_matched': len(matching_repos),
                        'repositories_assigned': 0,
                        'success': False,
                        'message': f'Failed to create cost center: {str(e)}'
                    })
                    continue
            else:
                self.logger.info(
                    f"Cost center '{cost_center_name}' already exists "
                    f"(ID: {cost_center['id']})"
                )
            
            # Assign repositories to cost center
            cost_center_id = cost_center['id']
            assigned_count = self._assign_repositories_to_cost_center(
                cost_center_id,
                cost_center_name,
                matching_repos
            )
            
            summary['mappings_processed'] += 1
            summary['assignments'].append({
                'cost_center': cost_center_name,
                'cost_center_id': cost_center_id,
                'property_name': property_name,
                'property_values': property_values,
                'repositories_matched': len(matching_repos),
                'repositories_assigned': assigned_count,
                'success': assigned_count > 0,
                'message': f'Successfully assigned {assigned_count}/{len(matching_repos)} repositories'
            })
        
        # Print summary
        self.logger.info("=" * 80)
        self.logger.info("REPOSITORY ASSIGNMENT SUMMARY")
        self.logger.info("=" * 80)
        self.logger.info(f"Total repositories in organization: {summary['repositories_found']}")
        self.logger.info(f"Mappings processed: {summary['mappings_processed']}")
        
        for assignment in summary['assignments']:
            self.logger.info("")
            self.logger.info(f"Cost Center: {assignment['cost_center']}")
            self.logger.info(f"  Property: {assignment['property_name']}")
            self.logger.info(f"  Values: {assignment['property_values']}")
            self.logger.info(f"  Matched: {assignment['repositories_matched']} repositories")
            self.logger.info(f"  Assigned: {assignment['repositories_assigned']} repositories")
            self.logger.info(f"  Status: {'✓ Success' if assignment['success'] else '✗ Failed'}")
        
        self.logger.info("=" * 80)
        
        return summary
    
    def _find_matching_repositories(
        self, 
        repositories: List[Dict], 
        property_name: str, 
        property_values: List[str]
    ) -> List[Dict]:
        """Find repositories that have a specific custom property with matching values.
        
        Args:
            repositories: List of repository dictionaries with properties
            property_name: Name of the custom property to match
            property_values: List of acceptable values for the property
            
        Returns:
            List of repositories that match the criteria
        """
        matching_repos = []
        property_values_set = set(property_values)  # Use set for O(1) lookup
        
        for repo in repositories:
            properties = repo.get('properties', [])
            
            # Check if this repository has the property with a matching value
            for prop in properties:
                if prop.get('property_name') == property_name:
                    value = prop.get('value')
                    if value in property_values_set:
                        matching_repos.append(repo)
                        self.logger.debug(
                            f"Repository '{repo['repository_full_name']}' matched: "
                            f"{property_name}={value}"
                        )
                        break  # Found a match, move to next repository
        
        return matching_repos
    
    def _assign_repositories_to_cost_center(
        self,
        cost_center_id: str,
        cost_center_name: str,
        repositories: List[Dict]
    ) -> int:
        """Assign multiple repositories to a cost center.
        
        The GitHub API requires repository names in "org/repo" format for assignment.
        
        Args:
            cost_center_id: UUID of the cost center
            cost_center_name: Name of the cost center (for logging)
            repositories: List of repository dictionaries
            
        Returns:
            Number of repositories successfully assigned
        """
        if not repositories:
            return 0
        
        # Extract repository names
        repo_names = []
        
        for repo in repositories:
            repo_full_name = repo.get('repository_full_name')
            
            if repo_full_name:
                repo_names.append(repo_full_name)
            else:
                repo_name = repo.get('repository_name', 'unknown')
                self.logger.warning(f"Repository '{repo_name}' is missing repository_full_name, skipping")
        
        if not repo_names:
            self.logger.error("No valid repository names found to assign")
            return 0
        
        self.logger.info(
            f"Assigning {len(repo_names)} repositories to cost center '{cost_center_name}' "
            f"(ID: {cost_center_id})"
        )
        
        # Log repository names for visibility
        for repo_name in repo_names[:10]:  # Show first 10
            self.logger.info(f"  - {repo_name}")
        if len(repo_names) > 10:
            self.logger.info(f"  ... and {len(repo_names) - 10} more")
        
        # Call the API to assign repositories
        try:
            success = self.github_api.add_repositories_to_cost_center(cost_center_id, repo_names)
            
            if success:
                self.logger.info(
                    f"Successfully assigned {len(repo_names)} repositories to "
                    f"cost center '{cost_center_name}'"
                )
                return len(repo_names)
            else:
                self.logger.error(
                    f"Failed to assign repositories to cost center '{cost_center_name}'"
                )
                return 0
                
        except Exception as e:
            self.logger.error(
                f"Error assigning repositories to cost center '{cost_center_name}': {str(e)}"
            )
            return 0

    def _create_budgets_for_cost_center(self, cost_center_id: str, cost_center_name: str):
        """Create budgets for a cost center based on configuration.
        
        Args:
            cost_center_id: UUID of the cost center
            cost_center_name: Name of the cost center
        """
        if not hasattr(self.config, 'budget_products'):
            self.logger.warning("No budget products configured")
            return
        
        self.logger.info(f"Creating budgets for cost center: {cost_center_name}")
        
        for product_name, product_config in self.config.budget_products.items():
            if not product_config.get('enabled', False):
                self.logger.debug(f"Skipping {product_name} budget (disabled)")
                continue
            
            amount = product_config.get('amount', 100)
            
            try:
                if product_name == 'copilot':
                    # Use the original method for Copilot
                    success = self.github_api.create_cost_center_budget(
                        cost_center_id, cost_center_name, budget_amount=amount
                    )
                else:
                    # Use the new product budget method for other products
                    success = self.github_api.create_product_budget(
                        cost_center_id, cost_center_name, product_name, amount
                    )
                
                if success:
                    self.logger.info(f"✅ Created ${amount} {product_name} budget for {cost_center_name}")
                else:
                    self.logger.warning(f"❌ Failed to create {product_name} budget for {cost_center_name}")
                    
            except Exception as e:
                self.logger.error(f"Error creating {product_name} budget for {cost_center_name}: {str(e)}")

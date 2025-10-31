"""
Configuration model classes for cost center automation.

These classes provide structured access to different configuration sections.
"""


class RepositoryConfig:
    """Configuration for repository-based cost center assignment mode."""
    
    def __init__(self, data: dict):
        """
        Initialize repository configuration.
        
        Args:
            data: Dictionary containing repository configuration data
            
        Raises:
            ValueError: If configuration validation fails
        """
        # Explicit mappings list
        self.explicit_mappings = data.get("explicit_mappings", [])
        
        # Validate explicit mappings structure
        for idx, mapping in enumerate(self.explicit_mappings):
            if not isinstance(mapping, dict):
                raise ValueError(f"Explicit mapping {idx} must be a dictionary")
            
            if not mapping.get("cost_center"):
                raise ValueError(f"Explicit mapping {idx} missing 'cost_center' field")
            
            if not mapping.get("property_name"):
                raise ValueError(f"Explicit mapping {idx} missing 'property_name' field")
            
            if not mapping.get("property_values"):
                raise ValueError(f"Explicit mapping {idx} missing 'property_values' field")
            
            if not isinstance(mapping.get("property_values"), list):
                raise ValueError(f"Explicit mapping {idx} 'property_values' must be a list")

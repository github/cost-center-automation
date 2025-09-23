"""
Configuration Manager for loading and managing application settings.
"""

import logging
import os
from pathlib import Path
from typing import Dict, Any, List
import yaml
from dotenv import load_dotenv


class ConfigManager:
    """Manages application configuration from files and environment variables."""
    
    def __init__(self, config_path: str = "config/config.yaml"):
        """Initialize the configuration manager."""
        self.logger = logging.getLogger(__name__)
        self.config_path = Path(config_path)
        
        # Load environment variables
        load_dotenv()
        
        # Load configuration
        self._load_config()
        
    def _load_config(self):
        """Load main configuration from YAML file."""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config_data = yaml.safe_load(f) or {}
            else:
                self.logger.warning(f"Config file {self.config_path} not found, using defaults")
                config_data = {}
            
            # GitHub configuration
            github_config = config_data.get("github", {})
            self.github_token = (
                os.getenv("GITHUB_TOKEN") or 
                github_config.get("token") or 
                self._prompt_for_token()
            )
            
            # Support both enterprise and organization setups
            self.github_enterprise = (
                os.getenv("GITHUB_ENTERPRISE") or 
                github_config.get("enterprise")
            )
            self.github_org = (
                os.getenv("GITHUB_ORG") or 
                github_config.get("organization")
            )
            
            # Validate that at least one is configured
            if not self.github_enterprise and not self.github_org:
                raise ValueError("Either github.enterprise or github.organization must be configured")
            
            # Export configuration
            export_config = config_data.get("export", {})
            self.export_dir = export_config.get("directory", "exports")
            self.export_formats = export_config.get("formats", ["csv", "excel"])
            
            # Logging configuration
            logging_config = config_data.get("logging", {})
            self.log_level = logging_config.get("level", "INFO")
            self.log_file = logging_config.get("file", "logs/copilot_manager.log")
            
            # Cost center configuration
            cost_center_config = config_data.get("cost_centers", {})
            # Support both legacy and normalized keys
            self.no_prus_cost_center = (
                cost_center_config.get("no_prus_cost_center") or
                cost_center_config.get("no_PRUs_costCenter") or
                "CC-001-NO-PRUS"
            )
            self.prus_allowed_cost_center = (
                cost_center_config.get("prus_allowed_cost_center") or
                cost_center_config.get("PRUs_allowed_costCenter") or
                "CC-002-PRUS-ALLOWED"
            )
            self.prus_exception_users = (
                cost_center_config.get("prus_exception_users") or
                cost_center_config.get("PRUs_exception_users") or
                []
            )
            
            # Store full config for other methods
            self.config = config_data
            
        except Exception as e:
            self.logger.error(f"Error loading configuration: {str(e)}")
            raise
    
    def load_cost_center_config(self) -> Dict[str, Any]:
        """Load cost center configuration from main config file."""
        # Cost center config is now part of the main config
        return self.config.get('cost_centers', {})
    
    def _prompt_for_token(self) -> str:
        """Prompt user for GitHub token if not found in config."""
        self.logger.error("GitHub token not found in config or environment variables")
        token = input("Please enter your GitHub Personal Access Token: ").strip()
        if not token:
            raise ValueError("GitHub token is required")
        return token
    
    def _prompt_for_org(self) -> str:
        """Prompt user for GitHub organization if not found in config."""
        if not self.github_enterprise:
            self.logger.error("GitHub organization not found in config or environment variables")
            org = input("Please enter your GitHub organization name: ").strip()
            if not org:
                raise ValueError("GitHub organization is required when not using enterprise")
            return org
        return None
    
    def validate_config(self) -> bool:
        """Validate the current configuration."""
        issues = []
        
        # Check required GitHub settings
        if not self.github_token:
            issues.append("GitHub token is missing")
        
        if not self.github_enterprise and not self.github_org:
            issues.append("Either GitHub enterprise or organization must be configured")
        
        # Check if export directory is writable
        export_path = Path(self.export_dir)
        try:
            export_path.mkdir(exist_ok=True)
        except Exception:
            issues.append(f"Cannot create export directory: {self.export_dir}")
        
        # Check if log directory is writable
        log_path = Path(self.log_file).parent
        try:
            log_path.mkdir(exist_ok=True)
        except Exception:
            issues.append(f"Cannot create log directory: {log_path}")
        
        if issues:
            for issue in issues:
                self.logger.error(f"Configuration issue: {issue}")
            return False
        
        return True
    
    def create_example_config(self, force: bool = False):
        """Create example configuration files."""
        config_dir = Path("config")
        config_dir.mkdir(exist_ok=True)
        
        # Main config file
        main_config_path = config_dir / "config.example.yaml"
        if not main_config_path.exists() or force:
            example_config = {
                "github": {
                    "token": "your_github_personal_access_token_here",
                    "enterprise": "your_enterprise_name"
                },
                "export": {
                    "directory": "exports",
                    "formats": ["csv", "excel"]
                },
                "logging": {
                    "level": "INFO",
                    "file": "logs/copilot_manager.log"
                },
                "cost_centers": {
                    "no_PRUs_costCenter": "CC-001-NO-PRUS",
                    "PRUs_allowed_costCenter": "CC-002-PRUS-ALLOWED"
                }
            }
            
            with open(main_config_path, 'w', encoding='utf-8') as f:
                yaml.dump(example_config, f, default_flow_style=False)
            
            self.logger.info(f"Created example config: {main_config_path}")
        
        # Cost center rules file
        rules_config_path = config_dir / "cost_centers.example.yaml"
        if not rules_config_path.exists() or force:
            example_rules = {
                "PRUs_exception_users": [
                    "john.doe",
                    "jane.smith",
                    "admin.user"
                ]
            }
            
            with open(rules_config_path, 'w', encoding='utf-8') as f:
                yaml.dump(example_rules, f, default_flow_style=False)
            
            self.logger.info(f"Created example cost center rules: {rules_config_path}")
    
    def get_config_summary(self) -> Dict[str, Any]:
        """Get a summary of current configuration."""
        # Construct cost center URLs if enterprise is configured
        no_prus_url = None
        prus_allowed_url = None
        if self.github_enterprise:
            no_prus_url = f"https://github.com/enterprises/{self.github_enterprise}/billing/cost_centers/{self.no_prus_cost_center}"
            prus_allowed_url = f"https://github.com/enterprises/{self.github_enterprise}/billing/cost_centers/{self.prus_allowed_cost_center}"
        
        return {
            "github_enterprise": self.github_enterprise,
            "github_org": self.github_org,
            "github_token_set": bool(self.github_token),
            "export_dir": self.export_dir,
            "export_formats": self.export_formats,
            "log_level": self.log_level,
            "log_file": self.log_file,
            "no_prus_cost_center": self.no_prus_cost_center,
            "no_prus_cost_center_url": no_prus_url,
            "prus_allowed_cost_center": self.prus_allowed_cost_center,
            "prus_allowed_cost_center_url": prus_allowed_url,
            "prus_exception_users_count": len(self.prus_exception_users)
        }
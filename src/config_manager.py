"""
Configuration Manager for loading and managing application settings.
"""

import logging
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import json
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
            
            # Enterprise-only setup with placeholder awareness
            placeholder_enterprise_values = {"", None, "REPLACE_WITH_ENTERPRISE_SLUG", "your_enterprise_name"}
            self.github_enterprise = (
                os.getenv("GITHUB_ENTERPRISE") or 
                github_config.get("enterprise")
            )
            # If still placeholder, treat as unset
            if self.github_enterprise in placeholder_enterprise_values:
                # Try env again explicitly (in case yaml had placeholder overriding)
                env_val = os.getenv("GITHUB_ENTERPRISE")
                if env_val and env_val not in placeholder_enterprise_values:
                    self.github_enterprise = env_val
                else:
                    self.github_enterprise = None
            
            # Validate that enterprise is configured clearly
            if not self.github_enterprise:
                raise ValueError("GitHub enterprise must be configured (set env GITHUB_ENTERPRISE or update config.github.enterprise)")
            
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
            self.no_prus_cost_center = (
                cost_center_config.get("no_prus_cost_center") or
                "CC-001-NO-PRUS"
            )
            self.prus_allowed_cost_center = (
                cost_center_config.get("prus_allowed_cost_center") or
                "CC-002-PRUS-ALLOWED"
            )
            self.prus_exception_users = (
                cost_center_config.get("prus_exception_users") or
                []
            )
            
            # Auto-creation configuration
            self.auto_create_cost_centers = cost_center_config.get("auto_create", False)
            self.no_pru_cost_center_name = cost_center_config.get("no_pru_name", "00 - No PRU overages")
            self.pru_allowed_cost_center_name = cost_center_config.get("pru_allowed_name", "01 - PRU overages allowed")
            
            # Incremental processing configuration
            self.enable_incremental = cost_center_config.get("enable_incremental", False)
            self.timestamp_file = Path(self.export_dir) / ".last_run_timestamp"
            
            # Store full config for other methods
            self.config = config_data
            
        except Exception as e:
            self.logger.error(f"Error loading configuration: {str(e)}")
            raise

        # Post-load sanity warnings for placeholder values will be checked later

    def _warn_on_placeholders(self):
        """Emit warnings if placeholder values are still present in config."""
        # Skip placeholder warnings if auto-creation is enabled
        if self.auto_create_cost_centers:
            return
            
        placeholder_tokens = {
            "no_prus_cost_center": ["REPLACE_WITH_NO_PRUS_COST_CENTER_ID", "CC-001-NO-PRUS"],
            "prus_allowed_cost_center": ["REPLACE_WITH_PRUS_ALLOWED_COST_CENTER_ID", "CC-002-PRUS-ALLOWED"],
        }
        for attr, placeholders in placeholder_tokens.items():
            value = getattr(self, attr, None)
            if value in placeholders:
                self.logger.warning(
                    f"Configuration for '{attr}' appears to be a placeholder ('{value}'). "
                    "Update 'config/config.yaml' with real cost center IDs before applying assignments."
                )
        # Warn if exception users list is empty (only informational)
        if not self.prus_exception_users:
            self.logger.info(
                "No PRUs exception users configured. All users will be assigned to the default 'no_prus_cost_center'."
            )
    
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
        """Prompt user for GitHub enterprise if not found in config."""
        if not self.github_enterprise:
            self.logger.error("GitHub enterprise not found in config or environment variables")
            enterprise = input("Please enter your GitHub enterprise name: ").strip()
            if not enterprise:
                raise ValueError("GitHub enterprise is required")
            self.github_enterprise = enterprise
    
    def validate_config(self) -> bool:
        """Validate the current configuration."""
        issues = []
        
        # Check required GitHub settings
        if not self.github_token:
            issues.append("GitHub token is missing")
        
        if not self.github_enterprise:
            issues.append("GitHub enterprise must be configured")
        
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
                    "no_prus_cost_center": "CC-001-NO-PRUS",
                    "prus_allowed_cost_center": "CC-002-PRUS-ALLOWED"
                }
            }
            
            with open(main_config_path, 'w', encoding='utf-8') as f:
                yaml.dump(example_config, f, default_flow_style=False)
            
            self.logger.info(f"Created example config: {main_config_path}")
        
        # Cost center rules file
        rules_config_path = config_dir / "cost_centers.example.yaml"
        if not rules_config_path.exists() or force:
            example_rules = {
                "prus_exception_users": [
                    "john.doe",
                    "jane.smith",
                    "admin.user"
                ]
            }
            
            with open(rules_config_path, 'w', encoding='utf-8') as f:
                yaml.dump(example_rules, f, default_flow_style=False)
            
            self.logger.info(f"Created example cost center rules: {rules_config_path}")
    
    def enable_auto_creation(self):
        """Enable auto-creation mode (typically called when --create-cost-centers flag is used)."""
        self.auto_create_cost_centers = True

    def check_config_warnings(self):
        """Check and emit configuration warnings after all initialization is complete."""
        self._warn_on_placeholders()
    
    def save_last_run_timestamp(self, timestamp: Optional[datetime] = None) -> None:
        """Save the last run timestamp to file."""
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        # Ensure export directory exists
        self.timestamp_file.parent.mkdir(exist_ok=True)
        
        timestamp_data = {
            "last_run": timestamp.isoformat() + "Z",
            "saved_at": datetime.utcnow().isoformat() + "Z"
        }
        
        try:
            with open(self.timestamp_file, 'w') as f:
                json.dump(timestamp_data, f, indent=2)
            self.logger.info(f"Saved last run timestamp: {timestamp.isoformat()}Z")
        except Exception as e:
            self.logger.error(f"Failed to save last run timestamp: {e}")
    
    def load_last_run_timestamp(self) -> Optional[datetime]:
        """Load the last run timestamp from file."""
        if not self.timestamp_file.exists():
            self.logger.info("No previous run timestamp found - will process all users")
            return None
        
        try:
            with open(self.timestamp_file, 'r') as f:
                timestamp_data = json.load(f)
            
            timestamp_str = timestamp_data.get('last_run')
            if timestamp_str:
                # Parse ISO format timestamp
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                self.logger.info(f"Loaded last run timestamp: {timestamp_str}")
                return timestamp
            else:
                self.logger.warning("Invalid timestamp file format")
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to load last run timestamp: {e}")
            return None

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
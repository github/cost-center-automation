#!/usr/bin/env python3
"""
Simplified GitHub Copilot Cost Center Management Script

This script manages GitHub Copilot license holders with a simple two-cost-center model:
- no_PRUs_costCenter: Default for all users
- PRUs_allowed_costCenter: Only for exception users listed in config
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional

from src.github_api import GitHubCopilotManager
from src.cost_center_manager import CostCenterManager
from src.exporter import DataExporter
from src.config_manager import ConfigManager
from src.logger_setup import setup_logging


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Simplified GitHub Copilot Cost Center Management"
    )
    
    # Action arguments
    parser.add_argument(
        "--list-users",
        action="store_true",
        help="List all Copilot license holders"
    )
    
    parser.add_argument(
        "--assign-cost-centers",
        action="store_true",
        help="Compute (and optionally apply) cost center assignments using simplified PRUs model"
    )
    
    parser.add_argument(
        "--export-format",
        choices=["csv", "xlsx"],
        default="csv",
        help="Export data format"
    )

    parser.add_argument(
        "--export-users",
        choices=["csv", "excel", "json", "all"],
        help="Export the full computed user list with cost centers (after assignment step)"
    )
    
    parser.add_argument(
        "--show-config",
        action="store_true",
        help="Show current configuration and exit"
    )
    
    # Mode replaces --dry-run and --sync-cost-centers separation
    parser.add_argument(
        "--mode",
        choices=["plan", "apply"],
        default="plan",
        help="Execution mode: plan (no changes) or apply (push assignments to GitHub)"
    )
    
    parser.add_argument(
        "--summary-report",
        action="store_true",
        help="Generate cost center summary report"
    )
    
    # Options
    parser.add_argument(
        "--users",
        help="Comma-separated list of specific users to process"
    )
    
    
    parser.add_argument(
        "--config",
        default="config/config.yaml",
        help="Configuration file path"
    )
    
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    return parser.parse_args()


def main():
    """Main execution function."""
    args = parse_arguments()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    setup_logging(level=log_level)
    logger = logging.getLogger(__name__)
    
    try:
        # Load configuration
        config = ConfigManager(args.config)
        logger.info("Configuration loaded successfully")
        
        # Initialize managers
        github_manager = GitHubCopilotManager(config)
        cost_center_manager = CostCenterManager(config)
        exporter = DataExporter(config)
        
        # Show configuration if requested
        if args.show_config:
            print("\n=== Current Configuration ===")
            print(f"Enterprise: {config.github_enterprise}")
            
            # Display cost centers with URLs
            print(f"No PRUs Cost Center: {config.no_prus_cost_center}")
            if config.github_enterprise:
                no_prus_url = f"https://github.com/enterprises/{config.github_enterprise}/billing/cost_centers/{config.no_prus_cost_center}"
                print(f"  → {no_prus_url}")
            
            print(f"PRUs Allowed Cost Center: {config.prus_allowed_cost_center}")
            if config.github_enterprise:
                prus_allowed_url = f"https://github.com/enterprises/{config.github_enterprise}/billing/cost_centers/{config.prus_allowed_cost_center}"
                print(f"  → {prus_allowed_url}")
            
            print(f"PRUs Exception Users ({len(config.prus_exception_users)}):")
            for user in config.prus_exception_users:
                print(f"  - {user}")
            
                if not any([args.list_users, args.assign_cost_centers, args.summary_report]):
                    return

            # We no longer fetch existing assignments; we always compute desired state from rules

            # Get Copilot users
        logger.info("Fetching Copilot license holders...")
        users = github_manager.get_copilot_users()
        logger.info(f"Found {len(users)} Copilot license holders")
        
        # Filter users if specified
        if args.users:
            specified_users = [u.strip() for u in args.users.split(",")]
            users = [user for user in users if user.get("login") in specified_users]
            logger.info(f"Filtered to {len(users)} specified users")
        
        # List users if requested
        if args.list_users:
            print("\n=== Copilot License Holders ===")
            print(f"Total users: {len(users)}")
            for user in users:
                username = user.get('login')
                name = user.get('name', 'N/A')
                # Show if user is in PRUs exception list
                is_exception = username in cost_center_manager.prus_exception_users
                exception_marker = " [PRUs Exception]" if is_exception else ""
                print(f"- {username} ({name}){exception_marker}")
        
        # Assign cost centers if requested
        if args.assign_cost_centers:
            logger.info("Assigning cost centers using simplified PRUs model...")
            if args.mode == "plan":
                logger.info("MODE=plan (no changes will be made)")
            
            prus_assignments = 0
            no_prus_assignments = 0
            # We now build full desired grouping without diffing existing assignments
            desired_groups = {
                cost_center_manager.cost_center_prus_allowed: [],
                cost_center_manager.cost_center_no_prus: []
            }
            
            for user in users:
                cost_center = cost_center_manager.assign_cost_center(user)
                user["cost_center"] = cost_center
                
                # Count assignments
                if cost_center == cost_center_manager.cost_center_prus_allowed:
                    prus_assignments += 1
                else:
                    no_prus_assignments += 1
                
                username = user.get('login')
                desired_groups[cost_center].append(username)
                if args.mode == "plan":
                    logger.debug(f"Would assign {username} to '{cost_center}'")
            
            # Summary of assignments
            print(f"\n=== Assignment Summary ===")
            print(f"PRUs Allowed ({cost_center_manager.cost_center_prus_allowed}): {prus_assignments} users")
            print(f"No PRUs ({cost_center_manager.cost_center_no_prus}): {no_prus_assignments} users")
            print(f"Total: {len(users)} users")
            
            # Sync assignments (full desired state) if requested
            if args.assign_cost_centers:
                if args.mode == "plan":
                    logger.info("Would sync full assignment state (plan mode)")
                    for cost_center_id, usernames in desired_groups.items():
                        logger.info(f"Would add {len(usernames)} users to cost center {cost_center_id}")
                else:  # apply
                    logger.info("Applying full assignment state to GitHub Enterprise...")
                    cost_center_groups = {cc: users for cc, users in desired_groups.items() if users}
                    if not cost_center_groups:
                        logger.warning("No users to sync")
                    else:
                        results = github_manager.bulk_update_cost_center_assignments(cost_center_groups)
                        successful_cost_centers = sum(1 for success in results.values() if success)
                        total_users_synced = sum(len(u) for cc, u in cost_center_groups.items() if results.get(cc, False))
                        logger.info(f"Successfully synced {successful_cost_centers}/{len(cost_center_groups)} cost centers ({total_users_synced} users)")
                        for cost_center_id, success in results.items():
                            if not success:
                                failed_users = len(cost_center_groups[cost_center_id])
                                logger.error(f"Failed to sync {failed_users} users to cost center {cost_center_id}")

                # Optional export of the full user list
                if args.export_users:
                    export_targets = []
                    if args.export_users == "all":
                        export_targets = ["csv", "excel", "json"]
                    else:
                        export_targets = [args.export_users]
                    logger.info(f"Exporting users in formats: {', '.join(export_targets)}")
                    for fmt in export_targets:
                        try:
                            if fmt == "csv":
                                path = exporter.export_to_csv(users)
                            elif fmt == "excel":
                                path = exporter.export_to_excel(users)
                            elif fmt == "json":
                                path = exporter.export_to_json(users)
                            logger.info(f"Exported users to {path}")
                        except Exception as export_err:
                            logger.error(f"Failed to export users to {fmt}: {export_err}")


        # Generate summary report if requested
        if args.summary_report:
            logger.info("Generating cost center summary...")
            summary = cost_center_manager.generate_summary(users)
            summary_file = exporter.export_summary(summary)
            logger.info(f"Summary report exported to: {summary_file}")
            
            # Print summary to console
            print("\n=== Cost Center Summary ===")
            for cost_center, count in summary.items():
                print(f"{cost_center}: {count} users")
        
        logger.info("Script execution completed successfully")
        
    except Exception as e:
        logger.error(f"Script execution failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Simplified GitHub Copilot Cost Center Management Script

This script manages GitHub Copilot license holders with a simple two-cost-center model:
- no_prus_cost_center: Default for all users
- prus_allowed_cost_center: Only for exception users listed in config
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional

from src.github_api import GitHubCopilotManager
from src.cost_center_manager import CostCenterManager
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
        "--show-config",
        action="store_true",
        help="Show current configuration and exit"
    )
    
    parser.add_argument(
        "--create-cost-centers",
        action="store_true",
        help="Create cost centers if they don't exist (enterprise only)"
    )
    
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Only process users added since last run (ideal for cron jobs)"
    )
    
    # Mode replaces --dry-run and --sync-cost-centers separation
    parser.add_argument(
        "--mode",
        choices=["plan", "apply"],
        default="plan",
        help="Execution mode: plan (no changes) or apply (push assignments to GitHub)"
    )

    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip confirmation prompt in apply mode (non-interactive)"
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


def _show_success_summary(config: ConfigManager, args, users: Optional[List[Dict]] = None, original_user_count: Optional[int] = None, assignment_results: Optional[Dict] = None):
    """Show a comprehensive success summary at the end of execution."""
    print("\n" + "="*60)
    print("🎉 SUCCESS SUMMARY")
    print("="*60)
    
    # Show what operations were completed
    operations = []
    if args.create_cost_centers or config.auto_create_cost_centers:
        operations.append("✅ Cost centers created")
    if args.assign_cost_centers:
        operations.append("✅ Users assigned to cost centers")
    if args.list_users:
        operations.append("✅ Users listed")
    if args.summary_report:
        operations.append("✅ Summary report generated")
    if args.incremental:
        operations.append("🔄 Incremental processing used")
    
    for op in operations:
        print(f"  {op}")
    
    # Show cost center information with links
    if config.github_enterprise and not config.github_enterprise.startswith("REPLACE_WITH_"):
        print(f"\n📊 COST CENTERS ({config.github_enterprise}):")
        
        # No PRUs cost center
        if not config.no_prus_cost_center.startswith("REPLACE_WITH_"):
            no_pru_url = f"https://github.com/enterprises/{config.github_enterprise}/billing/cost_centers/{config.no_prus_cost_center}"
            print(f"  🔵 No PRU Overages: {config.no_prus_cost_center}")
            print(f"     → {no_pru_url}")
        
        # PRUs allowed cost center  
        if not config.prus_allowed_cost_center.startswith("REPLACE_WITH_"):
            pru_url = f"https://github.com/enterprises/{config.github_enterprise}/billing/cost_centers/{config.prus_allowed_cost_center}"
            print(f"  🟡 PRU Overages Allowed: {config.prus_allowed_cost_center}")
            print(f"     → {pru_url}")
    
    # Show user statistics if users were processed
    if users:
        print(f"\n👥 USER STATISTICS:")
        print(f"  📈 Total users processed: {len(users)}")
        
        # Show incremental processing info if applicable
        if args.incremental and original_user_count is not None:
            print(f"  🔄 Incremental processing: {len(users)} of {original_user_count} total users")
        
        # Show actual assignment results if available
        if assignment_results and args.mode == "apply" and args.assign_cost_centers:
            total_attempted = 0
            total_successful = 0
            for cost_center_id, user_results in assignment_results.items():
                successful = sum(1 for success in user_results.values() if success)
                total_attempted += len(user_results)
                total_successful += successful
                
            print(f"  ✅ Assignment success rate: {total_successful}/{total_attempted} users")
            if total_successful < total_attempted:
                failed = total_attempted - total_successful
                print(f"  ❌ Failed assignments: {failed} users")
        elif args.assign_cost_centers:
            # Count by cost center if assignments were planned
            no_pru_count = len([u for u in users if u.get('cost_center') == config.no_prus_cost_center])
            pru_count = len([u for u in users if u.get('cost_center') == config.prus_allowed_cost_center])
            print(f"  🔵 No PRU users: {no_pru_count}")
            print(f"  🟡 PRU exception users: {pru_count}")
    
    print("="*60)


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
        
        # Enable auto-creation if requested via command line
        if args.create_cost_centers:
            config.enable_auto_creation()
        
        # Check for configuration warnings after auto-creation is potentially enabled
        config.check_config_warnings()
        
        logger.info("Configuration loaded successfully")
        
        # Initialize managers
        github_manager = GitHubCopilotManager(config)
        cost_center_manager = CostCenterManager(config, auto_create_enabled=args.create_cost_centers)
        
        # Always show configuration at the beginning of every run
        print("\n===== Current Configuration =====")
        print(f"Enterprise: {config.github_enterprise}")
        
        # Check if auto-creation is enabled
        auto_create_enabled = args.create_cost_centers or config.auto_create_cost_centers
        
        # Display cost centers (with auto-creation info if applicable)
        if auto_create_enabled:
            print(f"No PRUs Cost Center: New cost center \"{config.no_pru_cost_center_name}\" to be created")
            print(f"PRUs Allowed Cost Center: New cost center \"{config.pru_allowed_cost_center_name}\" to be created")
        else:
            # Display normal cost center info with URLs (only if not placeholders)
            print(f"No PRUs Cost Center: {config.no_prus_cost_center}")
            if (config.github_enterprise and 
                not config.github_enterprise.startswith("REPLACE_WITH_") and
                not config.no_prus_cost_center.startswith("REPLACE_WITH_")):
                no_prus_url = f"https://github.com/enterprises/{config.github_enterprise}/billing/cost_centers/{config.no_prus_cost_center}"
                print(f"  → {no_prus_url}")
            
            print(f"PRUs Allowed Cost Center: {config.prus_allowed_cost_center}")
            if (config.github_enterprise and 
                not config.github_enterprise.startswith("REPLACE_WITH_") and
                not config.prus_allowed_cost_center.startswith("REPLACE_WITH_")):
                prus_allowed_url = f"https://github.com/enterprises/{config.github_enterprise}/billing/cost_centers/{config.prus_allowed_cost_center}"
                print(f"  → {prus_allowed_url}")
        
        print(f"PRUs Exception Users ({len(config.prus_exception_users)}):")
        for user in config.prus_exception_users:
            print(f"  - {user}")
        print("===== End of Configuration =====\n")
        
        # Exit early if only showing config (--show-config with no other actions)
        if args.show_config and not any([args.list_users, args.assign_cost_centers, args.summary_report]):
            return

            # We no longer fetch existing assignments; we always compute desired state from rules

            # Get Copilot users
        logger.info("Fetching Copilot license holders...")
        users = github_manager.get_copilot_users()
        logger.info(f"Found {len(users)} Copilot license holders")
        
        # Handle incremental processing if requested
        original_user_count = len(users)
        if args.incremental:
            last_run_timestamp = config.load_last_run_timestamp()
            if last_run_timestamp:
                users = github_manager.filter_users_by_timestamp(users, last_run_timestamp)
                logger.info(f"Incremental mode: Processing {len(users)} users (of {original_user_count} total) created after {last_run_timestamp}")
                
                if len(users) == 0:
                    logger.info("No new users found since last run - nothing to process")
                    if args.mode == "apply":
                        # Still save timestamp to indicate successful run
                        config.save_last_run_timestamp()
                    return
            else:
                logger.info("Incremental mode: No previous timestamp found, processing all users")
        
        # Handle cost center auto-creation if requested
        if args.create_cost_centers or config.auto_create_cost_centers:
            logger.info("Auto-creation of cost centers requested...")
            
            if args.mode == "plan":
                logger.info("MODE=plan: Would create cost centers if they don't exist")
                logger.info(f"  - No PRU cost center: '{config.no_pru_cost_center_name}'")
                logger.info(f"  - PRU allowed cost center: '{config.pru_allowed_cost_center_name}'")
            else:  # apply mode
                logger.info("Creating cost centers if they don't exist...")
                cost_center_ids = github_manager.ensure_cost_centers_exist(
                    config.no_pru_cost_center_name,
                    config.pru_allowed_cost_center_name
                )
                
                if cost_center_ids:
                    # Update the cost center IDs in the config and manager
                    config.no_prus_cost_center = cost_center_ids['no_pru_id']
                    config.prus_allowed_cost_center = cost_center_ids['pru_allowed_id']
                    
                    # Update the cost center manager with new IDs
                    cost_center_manager.cost_center_no_prus = cost_center_ids['no_pru_id']
                    cost_center_manager.cost_center_prus_allowed = cost_center_ids['pru_allowed_id']
                    
                    logger.info(f"Updated cost center IDs:")
                    logger.info(f"  - No PRU: {cost_center_ids['no_pru_id']}")
                    logger.info(f"  - PRU allowed: {cost_center_ids['pru_allowed_id']}")
                else:
                    logger.error("Failed to create/find required cost centers")
                    sys.exit(1)
        
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
                # Show if user is in PRUs exception list
                is_exception = username in cost_center_manager.prus_exception_users
                exception_marker = " [PRUs Exception]" if is_exception else ""
                print(f"- {username}{exception_marker}")
        
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
                    # Safety confirmation unless --yes provided
                    if not args.yes:
                        print("\nYou are about to APPLY cost center assignments to GitHub Enterprise.")
                        print("This will push assignments for ALL processed users (no diff).")
                        print("Summary:")
                        for cc_id, usernames in desired_groups.items():
                            print(f"  - {cc_id}: {len(usernames)} users")
                        confirm = input("\nProceed? Type 'apply' to continue: ").strip().lower()
                        if confirm != "apply":
                            logger.warning("Aborted by user before applying assignments")
                            return
                    logger.info("Applying full assignment state to GitHub Enterprise...")
                    cost_center_groups = {cc: users for cc, users in desired_groups.items() if users}
                    if not cost_center_groups:
                        logger.warning("No users to sync")
                    else:
                        results = github_manager.bulk_update_cost_center_assignments(cost_center_groups)
                        
                        # Process detailed results for summary
                        total_users_attempted = 0
                        total_users_successful = 0
                        total_users_failed = 0
                        
                        for cost_center_id, user_results in results.items():
                            cc_successful = sum(1 for success in user_results.values() if success)
                            cc_failed = len(user_results) - cc_successful
                            total_users_attempted += len(user_results)
                            total_users_successful += cc_successful
                            total_users_failed += cc_failed
                            
                            if cc_failed > 0:
                                logger.warning(f"Cost center {cost_center_id}: {cc_successful}/{len(user_results)} users successful")
                                # Log failed users for this cost center
                                failed_users = [username for username, success in user_results.items() if not success]
                                logger.error(f"Failed users for {cost_center_id}: {', '.join(failed_users)}")
                            else:
                                logger.info(f"Cost center {cost_center_id}: all {cc_successful} users successful")
                        
                        # Final summary
                        if total_users_failed > 0:
                            logger.warning(f"FINAL RESULT: {total_users_successful}/{total_users_attempted} users successfully assigned ({total_users_failed} failed)")
                        else:
                            logger.info(f"FINAL RESULT: All {total_users_successful} users successfully assigned! 🎉")
                        
                        # Store results for success summary (make it accessible outside the if block)
                        assignment_results = results


        # Generate summary report if requested
        if args.summary_report:
            logger.info("Generating cost center summary...")
            summary = cost_center_manager.generate_summary(users)
            
            # Print summary to console and log
            print("\n=== Cost Center Summary ===")
            logger.info("Cost Center Assignment Summary:")
            for cost_center, count in summary.items():
                print(f"{cost_center}: {count} users")
                logger.info(f"  {cost_center}: {count} users")
        
        # Save timestamp for incremental processing if in apply mode
        if args.mode == "apply" and args.incremental:
            config.save_last_run_timestamp()
            logger.info("Saved current timestamp for next incremental run")
        
        # Show final success summary
        _show_success_summary(
            config, 
            args, 
            users if 'users' in locals() else None, 
            original_user_count if args.incremental else None,
            assignment_results if 'assignment_results' in locals() else None
        )
        
        logger.info("Script execution completed successfully")
        
    except Exception as e:
        logger.error(f"Script execution failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
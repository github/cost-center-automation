#!/usr/bin/env python3
"""
GitHub Cost Center Management Script

Automates cost center assignments for GitHub Copilot users with two operational modes:

1. PRU-Based Mode: Simple two-tier model based on Premium Request Unit exceptions
   - Default cost center for all users
   - Exception cost center for specified PRU-allowed users

2. Teams-Based Mode: Assigns users based on GitHub team membership
   - Organization scope: Sync teams from specific GitHub organizations
   - Enterprise scope: Sync teams across the entire GitHub Enterprise
   - Automatic cost center creation and naming
   - Team-based assignment (organization & enterprise teams)
   - Full sync mode (removes users who left teams)
   - Cost center auto-creation
"""

import argparse
import logging
import signal
import sys
from pathlib import Path
from typing import Dict, List, Optional

from src.github_api import GitHubCopilotManager
from src.cost_center_manager import CostCenterManager
from src.teams_cost_center_manager import TeamsCostCenterManager
from src.repository_cost_center_manager import RepositoryCostCenterManager
from src.config_manager import ConfigManager
from src.logger_setup import setup_logging


def setup_signal_handlers():
    """Setup signal handlers to gracefully handle broken pipes and interrupts."""
    def handle_broken_pipe(signum, frame):
        """Handle broken pipe gracefully - exit quietly when output pipe is closed."""
        sys.exit(0)
    
    def handle_interrupt(signum, frame):
        """Handle keyboard interrupt gracefully."""
        print("\n\nOperation interrupted by user.", file=sys.stderr)
        sys.exit(1)
    
    # Handle broken pipe (e.g., when piping to head, less, etc.)
    signal.signal(signal.SIGPIPE, handle_broken_pipe)
    # Handle Ctrl+C
    signal.signal(signal.SIGINT, handle_interrupt)


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="GitHub Cost Center Management - PRU-based or Teams-based assignment",
        epilog="""
Examples:
  # PRU-based mode (default)
  %(prog)s --assign-cost-centers --mode plan
  %(prog)s --assign-cost-centers --mode apply --yes
  
  # Teams-based mode (organization scope)
  %(prog)s --teams-mode --assign-cost-centers --mode plan
  %(prog)s --teams-mode --assign-cost-centers --mode apply --yes
  
  # View configuration
  %(prog)s --show-config
  %(prog)s --teams-mode --show-config
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
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
        help="Assign users to cost centers (use with --mode plan/apply)"
    )
    
    parser.add_argument(
        "--show-config",
        action="store_true",
        help="Show current configuration and exit"
    )
    
    parser.add_argument(
        "--create-cost-centers",
        action="store_true",
        help="Create cost centers if they don't exist (PRU mode only)"
    )
    
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Only process users added since last run (PRU mode only, ideal for cron jobs)"
    )
    
    parser.add_argument(
        "--teams-mode",
        action="store_true",
        help="Enable teams-based assignment (alternative to PRU-based mode)"
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
        "--check-current-cost-center",
        action="store_true",
        help="Check current cost center membership before assigning users (default: assign users without checking current membership for better performance)"
    )
    
    parser.add_argument(
        "--create-budgets",
        action="store_true",
        help="Create budgets for new cost centers (requires unreleased GitHub Enterprise APIs)"
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
    
    # Cache management options
    parser.add_argument(
        "--cache-stats",
        action="store_true",
        help="Show cost center cache statistics"
    )
    
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear the cost center cache"
    )
    
    parser.add_argument(
        "--cache-cleanup",
        action="store_true",
        help="Remove expired entries from the cost center cache"
    )
    
    return parser.parse_args()


def _handle_teams_mode(args, config: ConfigManager, teams_manager, logger) -> None:
    """Handle teams-based cost center assignment mode."""
    
    logger.info("="*60)
    logger.info("TEAMS MODE - GitHub Teams Integration")
    logger.info("="*60)
    
    # Show teams configuration
    print("\n===== Teams Mode Configuration =====")
    teams_scope = config.teams_scope  # Already validated in main()
    print(f"Scope: {teams_scope}")
    print(f"Mode: {config.teams_mode}")
    
    if teams_scope == "enterprise":
        print(f"Enterprise: {config.github_enterprise}")
    else:
        print(f"Organizations: {', '.join(config.teams_organizations)}")
    
    print(f"Auto-create cost centers: {config.teams_auto_create}")
    print(f"Full sync (remove users who left teams): {config.teams_remove_users_no_longer_in_teams}")
    print(f"Check current cost center: {args.check_current_cost_center}")
    print(f"Create budgets: {args.create_budgets}")
    
    if config.teams_mode == "auto":
        if teams_scope == "enterprise":
            print(f"Cost center naming: [enterprise team] {{team-name}}")
        else:
            print(f"Cost center naming: [org team] {{org-name}}/{{team-name}}")
    elif config.teams_mode == "manual":
        print(f"Manual mappings configured: {len(config.teams_mappings)}")
        for team_key, cost_center in config.teams_mappings.items():
            print(f"  - {team_key} → {cost_center}")
    
    print("===== End of Configuration =====\n")
    
    # Exit early if only showing config
    if args.show_config and not any([args.assign_cost_centers, args.summary_report]):
        logger.info("Configuration displayed. Use --mode plan or --mode apply to process teams.")
        return
    
    # If no action flags specified, default behavior depends on mode
    if not any([args.assign_cost_centers, args.summary_report]):
        if args.mode == "apply":
            # In apply mode, user likely wants to assign cost centers
            print("\n" + "="*60)
            print("ℹ️  APPLY MODE - Processing cost center assignments")
            print("="*60)
            print("💡 Tip: Use --mode plan to preview changes without applying them.\n")
            args.assign_cost_centers = True
        else:
            # In plan mode, show plan
            print("\n" + "="*60)
            print("ℹ️  PLAN MODE - Showing what would be done (no changes)")
            print("="*60)
            print("💡 Tip: Use --mode apply --yes to actually sync the assignments.\n")
            args.assign_cost_centers = True  # Enable preview in plan mode too!
    
    # Generate summary report if requested
    if args.summary_report:
        logger.info("Generating teams-based cost center summary...")
        summary = teams_manager.generate_summary()
        
        teams_scope = config.teams_scope  # Already validated in main()
        
        print("\n=== Teams Cost Center Summary ===")
        print(f"Scope: {teams_scope}")
        print(f"Mode: {summary['mode']}")
        
        if teams_scope == "enterprise":
            print(f"Enterprise: {config.github_enterprise}")
        else:
            print(f"Organizations: {', '.join(summary['organizations'])}")
        
        print(f"Total teams: {summary['total_teams']}")
        print(f"Cost centers: {summary['total_cost_centers']}")
        print(f"Unique users: {summary['unique_users']}")
        print(f"Note: Each user is assigned to exactly ONE cost center")
        
        if summary['cost_centers']:
            print("\nPer-Cost-Center Breakdown:")
            for cost_center, stats in summary['cost_centers'].items():
                print(f"  {cost_center}: {stats['users']} users")
    
    # Assign cost centers if requested
    if args.assign_cost_centers:
        print("\n" + "="*60)
        if args.mode == "plan":
            print("📋 PLAN MODE - Preview Only (No Changes)")
            print("="*60)
            logger.info("MODE=plan (no changes will be made)")
        else:
            print("⚡ APPLY MODE - Will Make Changes")
            print("="*60)
        
        logger.info("Processing team-based cost center assignments...")
        
        # Build and optionally sync assignments
        if args.mode == "plan":
            results = teams_manager.sync_team_assignments(mode="plan", ignore_current_cost_center=not args.check_current_cost_center)
        else:  # apply mode
            # Safety confirmation unless --yes provided
            if not args.yes:
                print("\n⚠️  WARNING: You are about to APPLY team-based cost center assignments!")
                print("This will assign users to cost centers based on their team membership.")
                print("NOTE: Each user can only belong to ONE cost center.")
                print("Users in multiple teams: assignment depends on current cost center status.")
                if args.check_current_cost_center:
                    print("� Current cost center membership will be checked - users in other cost centers will be SKIPPED.")
                else:
                    print("⚡ Fast mode: Users will be assigned WITHOUT checking current cost center membership.")
                confirm = input("\nProceed? Type 'apply' to continue: ").strip().lower()
                if confirm != "apply":
                    logger.warning("Aborted by user before applying assignments")
                    return
            
            logger.info("Applying team-based assignments to GitHub Enterprise...")
            results = teams_manager.sync_team_assignments(mode="apply", ignore_current_cost_center=not args.check_current_cost_center)
            
            if results:
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
                    else:
                        logger.info(f"Cost center {cost_center_id}: all {cc_successful} users successful")
                
                # Final summary
                if total_users_failed > 0:
                    logger.warning(f"FINAL RESULT: {total_users_successful}/{total_users_attempted} users successfully assigned ({total_users_failed} failed)")
                else:
                    logger.info(f"FINAL RESULT: All {total_users_successful} users successfully assigned! 🎉")
                
                # Show success summary
                print("\n" + "="*60)
                print("🎉 TEAMS MODE SUCCESS SUMMARY")
                print("="*60)
                print(f"  ✅ Team-based assignments completed")
                print(f"  📊 Total users: {total_users_successful}/{total_users_attempted}")
                if total_users_failed > 0:
                    print(f"  ❌ Failed: {total_users_failed}")
                print("="*60)
    
    logger.info("Teams mode execution completed successfully")


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
        if not config.no_prus_cost_center_id.startswith("REPLACE_WITH_"):
            no_pru_url = f"https://github.com/enterprises/{config.github_enterprise}/billing/cost_centers/{config.no_prus_cost_center_id}"
            print(f"  🔵 No PRU Overages: {config.no_prus_cost_center_id}")
            print(f"     → {no_pru_url}")
        
        # PRUs allowed cost center  
        if not config.prus_allowed_cost_center_id.startswith("REPLACE_WITH_"):
            pru_url = f"https://github.com/enterprises/{config.github_enterprise}/billing/cost_centers/{config.prus_allowed_cost_center_id}"
            print(f"  🟡 PRU Overages Allowed: {config.prus_allowed_cost_center_id}")
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
            no_pru_count = len([u for u in users if u.get('cost_center') == config.no_prus_cost_center_id])
            pru_count = len([u for u in users if u.get('cost_center') == config.prus_allowed_cost_center_id])
            print(f"  🔵 No PRU users: {no_pru_count}")
            print(f"  🟡 PRU exception users: {pru_count}")
    
    print("="*60)


def main():
    """Main execution function."""
    # Setup signal handlers first
    setup_signal_handlers()
    
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
        
        # Handle cache management commands (can be run without GitHub API)
        if args.cache_stats or args.clear_cache or args.cache_cleanup:
            from src.cost_center_cache import CostCenterCache
            cache = CostCenterCache()
            
            if args.cache_stats:
                stats = cache.get_cache_stats()
                print("\n===== Cost Center Cache Statistics =====")
                print(f"Cache file: {stats['cache_file']}")
                print(f"Total entries: {stats['total_entries']}")
                print(f"Valid entries: {stats['valid_entries']}")
                print(f"Expired entries: {stats['expired_entries']}")
                print(f"Cache TTL: {stats['ttl_hours']} hours")
                print(f"Last updated: {stats['last_updated'] or 'Never'}")
                
                if stats['total_entries'] > 0:
                    hit_rate = (stats['valid_entries'] / stats['total_entries']) * 100
                    print(f"Effective hit rate: {hit_rate:.1f}%")
                print("==========================================\n")
            
            if args.clear_cache:
                cache.clear_cache()
                print("Cost center cache cleared successfully.\n")
            
            if args.cache_cleanup:
                removed_count = cache.cleanup_expired_entries()
                print(f"Cleaned up {removed_count} expired cache entries.\n")
            
            # Exit if only cache management was requested
            if args.cache_stats or args.clear_cache or args.cache_cleanup:
                if not any([args.list_users, args.assign_cost_centers, args.summary_report, 
                           args.show_config, args.teams_mode]):
                    return
        
        # Initialize GitHub manager
        github_manager = GitHubCopilotManager(config)
        
        # Check operation mode: repository, teams, or PRU-based (default)
        cost_center_mode = getattr(config, 'github_cost_centers_mode', 'users')
        
        # Repository mode: Assign repositories to cost centers based on custom properties
        if cost_center_mode == "repository":
            logger.info("=" * 80)
            logger.info("REPOSITORY MODE ENABLED")
            logger.info("=" * 80)
            
            if not hasattr(config, 'github_cost_centers_repository_config'):
                logger.error("Repository mode requires 'repository_config' in config.github.cost_centers")
                sys.exit(1)
            
            # Validate that an organization name is available
            # For repository mode, we need an org context - use first teams org or enterprise
            org_name = None
            if hasattr(config, 'teams_organizations') and config.teams_organizations:
                org_name = config.teams_organizations[0]
                logger.info(f"Using organization: {org_name}")
            elif config.github_enterprise:
                # For enterprise, we'd need to list orgs - for now require explicit config
                logger.error(
                    "Repository mode requires an organization name. "
                    "Please add 'organizations: [\"your-org-name\"]' to config.teams.organizations"
                )
                sys.exit(1)
            
            # Initialize repository manager
            repo_manager = RepositoryCostCenterManager(config, github_manager, create_budgets=args.create_budgets)
            
            # Handle show-config
            if args.show_config:
                logger.info("=" * 60)
                logger.info("Repository Mode Configuration")
                logger.info("=" * 60)
                logger.info(f"Organization: {org_name}")
                logger.info(f"Explicit Mappings: {len(config.github_cost_centers_repository_config.explicit_mappings)}")
                logger.info("\nMappings:")
                for idx, mapping in enumerate(config.github_cost_centers_repository_config.explicit_mappings, 1):
                    logger.info(f"\n  {idx}. Cost Center: {mapping.get('cost_center')}")
                    logger.info(f"     Property: {mapping.get('property_name')}")
                    logger.info(f"     Values: {mapping.get('property_values')}")
                logger.info("=" * 60)
                
                if not any([args.list_users, args.assign_cost_centers]):
                    return
            
            # Handle assignment
            if args.assign_cost_centers:
                if args.mode == "plan":
                    logger.info("MODE=plan: Would assign repositories to cost centers (dry-run)")
                    logger.info("Run with --mode apply to make actual changes")
                    # TODO: Implement dry-run mode in repository manager
                    return
                elif args.mode == "apply":
                    if not args.yes:
                        response = input("\nThis will assign repositories to cost centers. Continue? (yes/no): ")
                        if response.lower() != "yes":
                            logger.info("Operation cancelled by user")
                            return
                    
                    logger.info("MODE=apply: Assigning repositories to cost centers...")
                    summary = repo_manager.run(org_name)
                    
                    logger.info("Repository assignment completed!")
                    return
                else:
                    logger.error(f"Invalid mode: {args.mode}. Use 'plan' or 'apply'")
                    sys.exit(1)
            else:
                logger.info("No action specified. Use --assign-cost-centers to assign repositories")
                return
        
        # Teams mode: Check if teams mode is enabled (via flag or config)
        teams_mode_enabled = args.teams_mode or config.teams_enabled
        
        if teams_mode_enabled:
            # Validate teams configuration - scope is required
            if not hasattr(config, 'teams_scope') or config.teams_scope is None:
                logger.error("Teams mode requires 'scope' to be configured in config.teams.scope (must be 'organization' or 'enterprise')")
                sys.exit(1)
            
            teams_scope = config.teams_scope
            
            # Validate scope value
            if teams_scope not in ["organization", "enterprise"]:
                logger.error(f"Invalid teams scope '{teams_scope}'. Must be 'organization' or 'enterprise'")
                sys.exit(1)
            
            # Validate scope-specific requirements
            if teams_scope == "organization":
                if not config.teams_organizations:
                    logger.error("Teams mode with scope='organization' requires organizations to be configured in config.teams.organizations")
                    sys.exit(1)
            elif teams_scope == "enterprise":
                if not config.github_enterprise:
                    logger.error("Teams mode with scope='enterprise' requires enterprise to be configured in config.github_enterprise")
                    sys.exit(1)
            
            # Initialize teams manager
            teams_manager = TeamsCostCenterManager(config, github_manager, create_budgets=args.create_budgets)
            
            scope_label = "enterprise" if teams_scope == "enterprise" else f"{len(config.teams_organizations)} organizations"
            logger.info(f"Teams mode enabled: {config.teams_mode} mode with {teams_scope} scope ({scope_label})")
            
            # Handle teams mode flow
            return _handle_teams_mode(args, config, teams_manager, logger)
        
        # ===== Standard PRU-based mode continues below =====
        
        # Initialize cost center manager for PRU-based mode
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
            print(f"No PRUs Cost Center: {config.no_prus_cost_center_id}")
            
            if (config.github_enterprise and 
                not config.github_enterprise.startswith("REPLACE_WITH_") and
                not config.no_prus_cost_center_id.startswith("REPLACE_WITH_")):
                no_prus_url = f"https://github.com/enterprises/{config.github_enterprise}/billing/cost_centers/{config.no_prus_cost_center_id}"
                print(f"  → {no_prus_url}")
            
            print(f"PRUs Allowed Cost Center: {config.prus_allowed_cost_center_id}")
            
            if (config.github_enterprise and 
                not config.github_enterprise.startswith("REPLACE_WITH_") and
                not config.prus_allowed_cost_center_id.startswith("REPLACE_WITH_")):
                prus_allowed_url = f"https://github.com/enterprises/{config.github_enterprise}/billing/cost_centers/{config.prus_allowed_cost_center_id}"
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
                    config.no_prus_cost_center_id = cost_center_ids['no_pru_id']
                    config.prus_allowed_cost_center_id = cost_center_ids['pru_allowed_id']
                    
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
                        if args.check_current_cost_center:
                            print("� Current cost center membership will be checked - users in other cost centers will be SKIPPED.")
                        else:
                            print("⚡ Fast mode: Users will be assigned WITHOUT checking current cost center membership.")
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
                        results = github_manager.bulk_update_cost_center_assignments(cost_center_groups, not args.check_current_cost_center)
                        
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
        
    except BrokenPipeError:
        # Handle broken pipe gracefully (e.g., when output is piped to head, less, etc.)
        sys.exit(0)
    except KeyboardInterrupt:
        logger.info("\nOperation interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Script execution failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
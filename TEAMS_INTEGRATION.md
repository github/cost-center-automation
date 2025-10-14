# Teams Integration - Quick Reference

This document provides a quick reference for using the new Teams Integration feature in the cost center automation utility.

## Overview

The Teams Integration mode allows you to automatically assign GitHub Copilot users to cost centers based on their GitHub team membership. This is an **alternative mode** to the PRU-based assignment logic.

## Key Concepts

### Two Modes of Operation

1. **Auto Mode**: Automatically creates one cost center per team
   - Best for: Organizations wanting 1:1 mapping of teams to cost centers
   - Naming: Uses customizable template (default: "Team: {team_name}")

2. **Manual Mode**: Explicitly map teams to cost centers
   - Best for: Organizations wanting to group multiple teams or use existing cost centers
   - Requires: Team mappings defined in configuration

### Multi-Team Membership

**Important:** Each user can only belong to ONE cost center.

If a user belongs to multiple teams:
- They will be assigned to the cost center of the **last team processed**
- Previous cost center assignments are overwritten
- The system logs warnings for users with multiple team memberships
- You can review these warnings before applying to understand conflicts

## Configuration Examples

### Auto Mode Configuration

```yaml
# config.yaml
teams:
  enabled: true
  mode: "auto"
  
  organizations:
    - "my-org"
    - "another-org"
  
  auto_create_cost_centers: true
  cost_center_name_template: "Team: {team_name}"
```

### Manual Mode Configuration

```yaml
# config.yaml
teams:
  enabled: true
  mode: "manual"
  
  organizations:
    - "my-org"
  
  auto_create_cost_centers: true
  
  team_mappings:
    "my-org/frontend": "Engineering: Frontend"
    "my-org/backend": "Engineering: Backend"
    "my-org/mobile": "Engineering: Mobile"
    "my-org/devops": "CC-DEVOPS-001"  # Use existing cost center ID
```

## Command Examples

### View Configuration
```bash
# Show what teams mode would do
python main.py --teams-mode --show-config
```

### Plan Mode (Dry Run)
```bash
# See what assignments would be made (no changes)
python main.py --teams-mode --assign-cost-centers --mode plan
```

### Apply Mode (With Confirmation)
```bash
# Apply assignments (will prompt for confirmation)
python main.py --teams-mode --assign-cost-centers --mode apply
```

### Apply Mode (Non-Interactive)
```bash
# Apply without confirmation (for automation)
python main.py --teams-mode --assign-cost-centers --mode apply --yes
```

### Generate Summary Report
```bash
# Show summary of teams and cost centers
python main.py --teams-mode --summary-report
```

### Combined Operations
```bash
# Plan with summary report
python main.py --teams-mode --assign-cost-centers --summary-report --mode plan

# Apply with verbose logging
python main.py --teams-mode --assign-cost-centers --mode apply --yes --verbose
```

## API Endpoints Used

The Teams Integration mode uses these GitHub REST API endpoints:

1. **List Organization Teams**
   - Endpoint: `GET /orgs/{org}/teams`
   - Scope: `read:org`
   - Returns: List of all teams in the organization

2. **List Team Members**
   - Endpoint: `GET /orgs/{org}/teams/{team_slug}/members`
   - Scope: `read:org`
   - Returns: List of all members in the team

3. **Create Cost Center** (if auto-create enabled)
   - Endpoint: `POST /enterprises/{enterprise}/settings/billing/cost-centers`
   - Scope: `manage_billing:enterprise`
   - Creates new cost centers

4. **Add Users to Cost Center**
   - Endpoint: `POST /enterprises/{enterprise}/settings/billing/cost-centers/{id}/resource`
   - Scope: `manage_billing:enterprise`
   - Adds users to cost center (batch: up to 50 users)

## Token Permissions

Your GitHub Personal Access Token must have:
- `manage_billing:enterprise` - To manage cost centers
- `read:org` - To read team information

## Behavior Notes

### What Gets Processed
- **Auto Mode**: All teams in configured organizations
- **Manual Mode**: Only teams with explicit mappings

### What Gets Skipped
- Teams with no members (logged as info)
- Teams without mappings in manual mode (logged as warning)
- Users not in any configured team (not encountered since input is teams)

### Multi-Team User Behavior
- Users in multiple teams are logged with a WARNING
- The last team processed determines the final cost center assignment
- Previous assignments are overwritten (users can only be in ONE cost center)

### Multi-Organization Support
- Process teams from multiple organizations in a single run
- Cost center names can include organization name using `{org}` variable
- Example template: `"{org} - {team_name}"` → "acme-corp - Frontend"

## Comparison: Teams Mode vs PRU Mode

| Aspect | Teams Mode | PRU Mode |
|--------|-----------|----------|
| **Trigger** | `--teams-mode` flag or `teams.enabled: true` | Default mode |
| **Input** | GitHub teams | Copilot license holders |
| **Logic** | Team membership | Exception list |
| **Cost Centers** | One per team (auto) or mapped | Two (with/without PRU) |
| **Multi-assignment** | Yes (multi-team users) | No |
| **Config Complexity** | Medium-High | Low |
| **Use Case** | Team-based allocation | Simple usage tiers |

## Automation Example

### Cron Job - Daily Team Sync
```bash
# /etc/cron.d/copilot-team-sync
# Run daily at 2 AM to sync teams with cost centers
0 2 * * * cd /path/to/cost-center-automation && python main.py --teams-mode --assign-cost-centers --mode apply --yes >> /var/log/copilot-team-sync.log 2>&1
```

### GitHub Actions - Weekly Team Sync
```yaml
# .github/workflows/team-sync.yml
name: Weekly Team Cost Center Sync

on:
  schedule:
    - cron: '0 2 * * 1'  # Every Monday at 2 AM
  workflow_dispatch:

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install -r requirements.txt
      
      - name: Sync teams to cost centers
        env:
          GITHUB_TOKEN: ${{ secrets.COST_CENTER_TOKEN }}
        run: |
          python main.py --teams-mode --assign-cost-centers --mode apply --yes --summary-report
```

## Troubleshooting

### "Teams mode requires organizations to be configured"
**Solution**: Add organizations to `config.yaml`:
```yaml
teams:
  organizations:
    - "your-org-name"
```

### "No mapping found for team org/team-slug in manual mode"
**Solution**: Add team mapping in manual mode:
```yaml
teams:
  mode: "manual"
  team_mappings:
    "org/team-slug": "Cost Center Name"
```

### "Failed to fetch teams for org X"
**Possible causes**:
- Token lacks `read:org` scope
- Organization name is incorrect
- Token doesn't have access to the organization

### Warning: "User X is in multiple teams"
**This is expected**: The tool warns you when a user belongs to multiple teams. By default, users already in cost centers will be skipped to avoid conflicts. Use `--ignore-current-cost-center` if you need to move users between cost centers. Review these warnings in plan mode to understand assignment behavior.

## Best Practices

1. **Start with Plan Mode**: Always run with `--mode plan` first to preview changes
2. **Review Multi-Team Warnings**: Check warning logs for users in multiple teams before applying
3. **Use Verbose Logging**: Add `--verbose` flag for detailed operation logs
4. **Test with Small Orgs First**: Test the configuration with a small organization before scaling
5. **Consider Team Structure**: Users should ideally belong to one primary team for cost allocation
6. **Use Manual Mode for Control**: If you have many multi-team users, use manual mode to control which teams are processed
7. **Automate Safely**: Use `--yes` flag only in fully automated environments
8. **Regular Sync**: Run team sync regularly (daily/weekly) to keep cost centers up-to-date

**Note:** Incremental sync (processing only new/changed users) is NOT currently supported for teams mode. All team members are processed every run.

## Future Enhancements

When the cost center membership API becomes available:
- Option to check existing cost center membership before assignment
- Ability to remove users from cost centers (not currently supported)
- Diff mode to only add new team members (incremental sync)

**Incremental sync for teams mode is not available yet.**

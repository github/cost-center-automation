# Teams Integration - Quick Start Guide

Get started with GitHub Teams Integration for cost center automation in 5 minutes!

## Step 1: Verify Prerequisites

Ensure you have:
- ✅ GitHub Enterprise Cloud admin access
- ✅ Personal Access Token with:
  - `manage_billing:enterprise` scope
  - `read:org` scope (NEW for teams mode)
- ✅ Python 3.8+ installed
- ✅ Repository cloned and dependencies installed

```bash
cd cost-center-automation
pip install -r requirements.txt
```

## Step 2: Configure Organizations

Edit `config/config.yaml` and add your organizations:

```yaml
teams:
  enabled: true
  mode: "auto"  # Start with auto mode
  
  # Add your organizations here
  organizations:
    - "your-github-org"
  
  auto_create_cost_centers: true
  cost_center_name_template: "Team: {team_name}"
```

## Step 3: Set Environment Variables

```bash
# Set your GitHub token and enterprise
export GITHUB_TOKEN="ghp_your_token_here"
export GITHUB_ENTERPRISE="your-enterprise-name"
```

Or create a `.env` file:
```
GITHUB_TOKEN=ghp_your_token_here
GITHUB_ENTERPRISE=your-enterprise-name
```

## Step 4: Test with Plan Mode

Run in plan mode to see what would happen (no changes made):

```bash
python main.py --teams-mode --assign-cost-centers --mode plan
```

You should see:
- List of teams found in your organization
- Cost centers that would be created
- Users that would be assigned
- Summary of assignments

## Step 5: Review the Plan

Check the output for:
- ✅ All expected teams are listed
- ✅ Cost center names look correct
- ✅ Team member counts are accurate
- ⚠️  Review any warnings about users in multiple teams
- ✅ No unexpected errors

Example output:
```
2025-10-06 10:00:00 [INFO] Found 5 teams in your-github-org
2025-10-06 10:00:01 [INFO] Team Frontend (your-github-org/frontend) → Cost Center 'Team: Frontend': 12 members
2025-10-06 10:00:02 [INFO] Team Backend (your-github-org/backend) → Cost Center 'Team: Backend': 8 members
...
2025-10-06 10:00:04 [WARNING] ⚠️  Found 3 users who are members of multiple teams.
2025-10-06 10:00:04 [WARNING]   ⚠️  alice is in multiple teams [org/frontend, org/mobile] → will be assigned to 'Team: Mobile'
2025-10-06 10:00:05 [INFO] Team assignment summary: 5 cost centers, 42 unique users (each assigned to exactly ONE cost center)
```

## Step 6: Apply Changes

When you're ready to apply:

```bash
# With confirmation prompt
python main.py --teams-mode --assign-cost-centers --mode apply

# Or skip confirmation (for automation)
python main.py --teams-mode --assign-cost-centers --mode apply --yes
```

## Step 7: Verify Results

Check your GitHub Enterprise cost centers:
1. Go to `https://github.com/enterprises/YOUR-ENTERPRISE/billing/cost_centers`
2. Verify new cost centers were created
3. Click into each cost center to see assigned users

## Next Steps

### Option A: Keep Auto Mode
If you're happy with one cost center per team, you're done! Just run regularly:

```bash
# Daily sync (cron example)
0 2 * * * cd /path/to/repo && python main.py --teams-mode --assign-cost-centers --mode apply --yes
```

### Option B: Switch to Manual Mode
For more control over team-to-cost-center mappings:

```yaml
teams:
  enabled: true
  mode: "manual"
  
  organizations:
    - "your-github-org"
  
  team_mappings:
    "your-github-org/frontend": "Engineering: Frontend"
    "your-github-org/backend": "Engineering: Backend"
    "your-github-org/mobile-ios": "Engineering: Mobile"
    "your-github-org/mobile-android": "Engineering: Mobile"  # Same cost center
```

### Option C: Use Custom Naming Template
Customize how cost centers are named in auto mode:

```yaml
teams:
  mode: "auto"
  # Include org name in cost center
  cost_center_name_template: "{org} - {team_name}"
  # Or use team slug
  cost_center_name_template: "Team: {team_slug}"
  # Or get creative
  cost_center_name_template: "[{org}] {team_name}"
```

## Common Scenarios

### Scenario 1: Multiple Organizations
```yaml
teams:
  organizations:
    - "org1"
    - "org2"
    - "org3"
  cost_center_name_template: "{org}: {team_name}"
```

### Scenario 2: Existing Cost Centers (Manual Mode)
```yaml
teams:
  mode: "manual"
  auto_create_cost_centers: false  # Use existing IDs
  team_mappings:
    "my-org/team-a": "CC-001-EXISTING"
    "my-org/team-b": "CC-002-EXISTING"
```

### Scenario 3: Mixed Approach
```yaml
teams:
  mode: "manual"
  auto_create_cost_centers: true  # Create if needed
  team_mappings:
    "my-org/frontend": "CC-FRONTEND-001"  # Existing
    "my-org/backend": "Engineering: Backend"  # Will be created
```

## Troubleshooting

### Error: "Teams mode requires organizations to be configured"
**Fix**: Add organizations to config:
```yaml
teams:
  organizations:
    - "your-org"
```

### Error: "Failed to fetch teams for org X"
**Possible causes**:
- Token missing `read:org` scope → Regenerate token with correct scope
- Wrong org name → Check spelling
- No access to org → Verify token has access

### Warning: "No mapping found for team org/team-slug in manual mode"
**Fix**: Add mapping for the team:
```yaml
teams:
  team_mappings:
    "org/team-slug": "Cost Center Name"
```

### Warning: User in multiple teams
**This is a conflict notification.** Users can only belong to ONE cost center. If a user is in multiple teams, they'll be assigned to the LAST team's cost center processed. Review the warning logs to see which cost center each multi-team user will get.

**Solution:** If this is not desired:
1. Use manual mode to control which teams are processed
2. Ensure users have one primary team for cost allocation
3. Review team membership structure

## Getting Help

- 📖 Full documentation: `README.md`
- 🔍 Detailed reference: `TEAMS_INTEGRATION.md`
- 💡 Implementation details: `IMPLEMENTATION_SUMMARY.md`
- 🐛 Report issues: GitHub Issues

## Quick Command Reference


```bash
# Show configuration
python main.py --teams-mode --show-config

# Plan (dry run)
python main.py --teams-mode --assign-cost-centers --mode plan

# Apply with confirmation
python main.py --teams-mode --assign-cost-centers --mode apply

# Apply without confirmation
python main.py --teams-mode --assign-cost-centers --mode apply --yes

# Generate summary report
python main.py --teams-mode --summary-report

# Verbose mode (for debugging)
python main.py --teams-mode --assign-cost-centers --mode plan --verbose

# Note: Incremental mode is NOT supported for teams mode. All team members are processed every run.
```

---

**🎉 That's it! You're now using GitHub Teams Integration for cost center automation.**

For advanced usage, automation setup, and best practices, see the full documentation in `TEAMS_INTEGRATION.md`.

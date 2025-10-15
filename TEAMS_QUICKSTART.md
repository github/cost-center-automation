# Teams Integration - Quick Start Guide

Get started with GitHub Teams Integration for cost center automation in 5 minutes using GitHub Actions!

## Overview

This guide helps you set up **automated cost center sync** that:
- ✅ Syncs with your **enterprise teams** (default)
- ✅ Creates one cost center per team automatically
- ✅ Removes users from cost centers when they leave teams (full sync)
- ✅ Runs on a schedule via GitHub Actions

## Step 1: Create Your GitHub Token

1. Go to [GitHub Settings → Tokens (classic)](https://github.com/settings/tokens/new)
2. Create a token with these scopes:
   - ✅ `manage_billing:enterprise` (required)
   - ✅ `read:org` (required for teams)
3. Copy the token - you'll need it in the next step

## Step 2: Set Up GitHub Actions

### Add Repository Secret

1. Go to your repository **Settings → Secrets and variables → Actions**
2. Click **New repository secret**
3. Name: `COST_CENTER_TOKEN`
4. Value: Paste your token from Step 1
5. Click **Add secret**

### Create Workflow File

Create `.github/workflows/cost-center-sync.yml`:

```yaml
name: Cost Center Sync

on:
  schedule:
    # Run daily at 2 AM UTC
    - cron: '0 2 * * *'
  workflow_dispatch:  # Allow manual runs

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Sync cost centers with enterprise teams
        env:
          GITHUB_TOKEN: ${{ secrets.COST_CENTER_TOKEN }}
          GITHUB_ENTERPRISE: ${{ github.repository_owner }}
        run: |
          python main.py --teams-mode --assign-cost-centers --mode apply --yes
```

**Note:** This uses `github.repository_owner` as the enterprise name. If your enterprise name is different, replace it with your actual enterprise name.

## Step 3: Configure Teams Integration

Edit `config/config.yaml`:

```yaml
teams:
  enabled: true
  scope: "enterprise"  # Sync with enterprise teams (default)
  mode: "auto"  # Create one cost center per team
  auto_create_cost_centers: true
  remove_users_no_longer_in_teams: true  # Full sync: remove users who left teams
```

**That's it!** With these defaults, you get:
- ✅ Enterprise team sync (no need to list organizations)
- ✅ Automatic cost center creation per team
- ✅ Full sync mode (users removed when they leave teams)
- ✅ Smart handling (skips users already in other cost centers)

## Step 4: Test Your Setup

### Manual Test Run

Trigger the workflow manually to test:

1. Go to **Actions** tab in your repository
2. Click **Cost Center Sync** workflow
3. Click **Run workflow** dropdown
4. Click **Run workflow** button

### Check the Output

Watch the workflow run and verify:
- ✅ All enterprise teams are discovered
- ✅ Cost centers are created with format `[enterprise team] {team-name}`
- ✅ Users are assigned correctly
- ✅ No errors in the logs

### Verify in GitHub

1. Go to `https://github.com/enterprises/YOUR-ENTERPRISE/billing/cost_centers`
2. Verify cost centers were created for each team
3. Click into each cost center to verify user assignments

## Step 5: Review Full Sync Behavior

**Full sync mode is enabled by default** (`remove_users_no_longer_in_teams: true`):

- ✅ Users **added** to a team → automatically assigned to that team's cost center
- ✅ Users **removed** from a team → automatically removed from that team's cost center
- ✅ Users **moved** between teams → reassigned to the new team's cost center

### Check the Logs

After the first run, review the logs for users who left teams:

```
[INFO] Checking for users in cost centers who are no longer in teams...
[INFO] Found 3 users no longer in teams across 2 cost centers
[INFO] Removing users from cost centers...
[INFO] Removed alice from cost center '[enterprise team] Frontend'
```

## Advanced Configuration

### Option 1: Use Organization Teams Instead

If you prefer organization-level teams:

```yaml
teams:
  scope: "organization"
  organizations:
    - "your-org-1"
    - "your-org-2"
```

Cost centers will be named: `[org team] {org-name}/{team-name}`

### Option 2: Disable Full Sync

If you want to keep users in cost centers even after they leave teams:

```yaml
teams:
  remove_users_no_longer_in_teams: false
```

⚠️ **Warning:** This can cause cost centers to grow indefinitely.

### Option 3: Manual Mode

For complete control over team-to-cost-center mappings:

```yaml
teams:
  mode: "manual"
  team_mappings:
    "frontend": "Engineering: Frontend"  # Enterprise teams use just slug
    "backend": "Engineering: Backend"
    "mobile-ios": "Engineering: Mobile"
    "mobile-android": "Engineering: Mobile"  # Multiple teams → same cost center
```

### Option 4: Force Move Users Between Cost Centers

If you need to move users from other cost centers:

```yaml
# In your workflow, change the run command to:
run: |
  python main.py --teams-mode --assign-cost-centers --mode apply --yes --ignore-current-cost-center
```

⚠️ **Use carefully:** This will move users from any existing cost center to match team membership.

### Option 5: Custom Schedule

Adjust the cron schedule in your workflow:

```yaml
on:
  schedule:
    - cron: '0 2 * * *'    # Daily at 2 AM UTC
    # - cron: '0 */6 * * *'  # Every 6 hours
    # - cron: '0 2 * * 1'    # Weekly on Monday at 2 AM
```

## Troubleshooting

### Workflow Fails: "Authentication failed"

**Causes:**
- ❌ Token not set or expired
- ❌ Token missing required scopes

**Fix:**
1. Verify secret name matches: `COST_CENTER_TOKEN`
2. Check token has `manage_billing:enterprise` and `read:org` scopes
3. Regenerate token if expired

### Error: "Failed to fetch enterprise teams"

**Causes:**
- ❌ Wrong enterprise name in workflow
- ❌ Token doesn't have access to enterprise

**Fix:**
1. Check the enterprise name in your workflow matches your actual enterprise
2. Verify token owner has enterprise admin access

### Warning: "User in multiple teams"

**This is normal.** Users can only belong to ONE cost center. If someone is in multiple teams, they'll be assigned to the LAST team processed.

**Review the logs** to see assignments:
```
[WARNING] alice is in multiple teams [frontend, mobile] → will be assigned to '[enterprise team] mobile'
```

**Solutions:**
- Accept this behavior (user's primary team wins)
- Use manual mode to control which teams are included
- Restructure team membership to have clear primary teams

### Want to See What Would Change?

Add a plan-only workflow for testing:

```yaml
name: Cost Center Sync (Plan Only)

on:
  workflow_dispatch:

jobs:
  plan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - env:
          GITHUB_TOKEN: ${{ secrets.COST_CENTER_TOKEN }}
          GITHUB_ENTERPRISE: ${{ github.repository_owner }}
        run: |
          python main.py --teams-mode --assign-cost-centers --mode plan
```

## Local Testing (Optional)

If you want to test locally before using Actions:

```bash
# Clone and setup
git clone <your-repo-url>
cd cost-center-automation
pip install -r requirements.txt

# Set environment variables
export GITHUB_TOKEN="your_token_here"
export GITHUB_ENTERPRISE="your-enterprise"

# Run in plan mode (dry run)
python main.py --teams-mode --assign-cost-centers --mode plan

# Apply changes
python main.py --teams-mode --assign-cost-centers --mode apply --yes
```

## Getting Help

- 📖 Full documentation: [README.md](README.md)
- 🔍 Detailed reference: [TEAMS_INTEGRATION.md](TEAMS_INTEGRATION.md)
- 🐛 Report issues: GitHub Issues

## Quick Command Reference

```bash
# Show current configuration
python main.py --teams-mode --show-config

# Plan (dry run) - see what would change
python main.py --teams-mode --assign-cost-centers --mode plan

# Apply changes with confirmation prompt
python main.py --teams-mode --assign-cost-centers --mode apply

# Apply changes without confirmation (for automation)
python main.py --teams-mode --assign-cost-centers --mode apply --yes

# Verbose mode (for debugging)
python main.py --teams-mode --assign-cost-centers --mode plan --verbose
```

---

**🎉 That's it! Your cost centers now sync automatically with your enterprise teams via GitHub Actions.**

Every day (or on your chosen schedule), the workflow will:
1. Discover all enterprise teams
2. Create/update cost centers for each team
3. Assign users based on team membership
4. Remove users who left teams (full sync)

For advanced usage and customization, see [TEAMS_INTEGRATION.md](TEAMS_INTEGRATION.md).

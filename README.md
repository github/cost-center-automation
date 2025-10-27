# GitHub Cost Center Automation

**tl;dr:**
- Automate cost center creation and syncing with enterprise teams, org-based teams, or for every Copilot user in your enterprise
- Configure Actions workflow to keep cost centers in sync
- Coming soon: automatically create budgets for each cost center

Automate GitHub Copilot license cost center assignments for your enterprise with two powerful modes:

- **PRU-Based Mode**: Simple two-tier model (PRU overages allowed/not allowed)
- **Teams-Based Mode**: Automatic assignment based on GitHub team membership

## 🚀 Quick Start (5 minutes)

### 1. Create Your Token

Create a GitHub Personal Access Token with these scopes:
- `manage_billing:enterprise` (required)
- `read:org` (required for Teams Mode)

[→ Create token here](https://github.com/settings/tokens/new)

### 2. Choose Your Mode

<details>
<summary><b>PRU-Based Mode</b> (Simple two-tier model)</summary>

```bash
# Clone and setup
git clone <your-repo-url>
cd cost-center-automation
pip install -r requirements.txt

# Configure
export GITHUB_TOKEN="your_token_here"
export GITHUB_ENTERPRISE="your-enterprise"

# Run (creates cost centers automatically)
python main.py --create-cost-centers --assign-cost-centers --mode apply --yes
```

**Done!** All users are now in "00 - No PRU overages" cost center.

To allow specific users PRU overages, edit `config/config.yaml`:
```yaml
cost_centers:
  prus_exception_users:
    - "alice"
    - "bob"
```

</details>

<details>
<summary><b>Teams-Based Mode</b> (Sync with GitHub teams)</summary>

```bash
# Clone and setup
git clone <your-repo-url>
cd cost-center-automation
pip install -r requirements.txt

# Configure
cp config/config.example.yaml config/config.yaml
export GITHUB_TOKEN="your_token_here"
export GITHUB_ENTERPRISE="your-enterprise"

# Edit config/config.yaml
teams:
  enabled: true
  scope: "organization"  # or "enterprise"
  organizations:
    - "your-org-name"

# Run
python main.py --teams-mode --assign-cost-centers --mode apply --yes
```

**Done!** Cost centers created for each team, users automatically assigned.

See [TEAMS_QUICKSTART.md](TEAMS_QUICKSTART.md) for more details.

</details>

### 3. Automate (Optional)

Set up GitHub Actions for automatic syncing every 6 hours - see [Automation](#automation) below.

## Features

### Three Operational Modes

**PRU-Based Mode** (Default)
- Simple two-tier model: PRU overages allowed/not allowed
- Automatic cost center creation with default names
- Exception list for users who need PRU access
- Incremental processing support (only new users)

**Teams-Based Mode**
- Organization scope: Sync teams from specific GitHub orgs
- Enterprise scope: Sync all teams across the enterprise
- Automatic cost center creation with bracket notation naming
- Full sync mode (removes users who left teams)
- Single assignment (existing cost center assignments are preserved by default)

**Repository-Based Mode** (New!)
- Assign repositories to cost centers based on custom properties
- Flexible explicit mapping: map property values to cost centers
- Works with any custom property (team, service, environment, etc.)
- Automatic cost center creation for new mappings
- Perfect for aligning repository ownership with cost tracking

### Additional Features
- 🔄 **Plan/Apply execution**: Preview changes before applying
- 📊 **Enhanced logging**: Real-time success/failure tracking
- � **Smart user handling**: Skips users already in cost centers by default
- ⚡ **Override option**: `--ignore-current-cost-center` to move users between cost centers
- �🐳 **Container ready**: Dockerfile and docker-compose included
- ⚙️ **Automation examples**: GitHub Actions, cron, and shell scripts
- 🔧 **Auto-creation**: Automatic cost center creation (no manual UI setup)

## Prerequisites

- GitHub Enterprise Cloud with admin access
- GitHub Personal Access Token with scopes:
  - `manage_billing:enterprise` (required for all modes)
  - `read:org` (required for Teams Mode)
- Python 3.8+ (for local execution)

## Configuration

Configuration lives in `config/config.yaml` (copy from `config/config.example.yaml`).

### PRU-Based Mode Configuration

```yaml
github:
  enterprise: ""  # Or set via GITHUB_ENTERPRISE env var

cost_centers:
  auto_create: true  # Automatically create cost centers
  no_prus_cost_center_name: "00 - No PRU overages"
  prus_allowed_cost_center_name: "01 - PRU overages allowed"
  
  # Users who need PRU access
  prus_exception_users:
    - "alice"
    - "bob"
```

### Teams-Based Mode Configuration

```yaml
teams:
  enabled: true
  scope: "organization"  # or "enterprise"
  mode: "auto"  # One cost center per team
  
  organizations:  # Only for organization scope
    - "your-org"
  
  auto_create_cost_centers: true
  remove_users_no_longer_in_teams: true
```

**Cost Center Naming:**
- Organization scope: `[org team] {org-name}/{team-name}`
- Enterprise scope: `[enterprise team] {team-name}`

### Repository-Based Mode Configuration

Assign repositories to cost centers based on custom properties. This mode is ideal for tracking costs by project, service, or team ownership.

**Prerequisites:**
1. Configure custom properties in your organization settings
2. Assign property values to your repositories
3. Map property values to cost centers in config

**Example Configuration:**

```yaml
github:
  cost_centers:
    mode: "repository"  # Enable repository mode
    
    repository_config:
      explicit_mappings:
        # Map repositories by team property
        - cost_center: "Platform Engineering"
          property_name: "team"
          property_values:
            - "platform"
            - "infrastructure"
            - "devops"
        
        # Map by environment
        - cost_center: "Production Services"
          property_name: "environment"
          property_values:
            - "production"
        
        # Map by service type
        - cost_center: "Data & Analytics"
          property_name: "team"
          property_values:
            - "data"
            - "analytics"
            - "ml"

teams:
  organizations:
    - "your-org-name"  # Required for repository mode
```

**Usage:**

```bash
# Plan mode: See what would be assigned
python main.py --assign-cost-centers --mode plan

# Apply mode: Make the assignments
python main.py --assign-cost-centers --mode apply --yes
```

**How It Works:**
1. Fetches all repositories in your organization with their custom properties
2. For each mapping, finds repositories with matching property values
3. Creates cost centers if they don't exist (automatically)
4. Assigns matching repositories to their designated cost centers

**Common Use Cases:**
- **By Team**: Map `team` property values to team-specific cost centers
- **By Environment**: Separate production vs. development repository costs
- **By Service**: Group microservices, frontend, backend, data services
- **By Department**: Map organizational units to cost centers

### Environment Variables

Set these instead of config file values:
- `GITHUB_TOKEN` (required)
- `GITHUB_ENTERPRISE` (required)
- `GITHUB_API_BASE_URL` (optional, see below)

## GitHub Enterprise Data Resident Support

This tool supports enterprises running on **GitHub Enterprise Data Resident** (GHE.com), which uses dedicated API endpoints.

### Standard GitHub.com (Default)

No configuration needed. The tool uses `https://api.github.com` by default.

### GitHub Enterprise Data Resident

For Data Resident enterprises, set your custom API URL:

**Option 1: Environment Variable**
```bash
export GITHUB_API_BASE_URL="https://api.octocorp.ghe.com"
```

**Option 2: Config File**
```yaml
github:
  enterprise: "octocorp"
  api_base_url: "https://api.octocorp.ghe.com"
```

Replace `octocorp` with your enterprise's subdomain.

### GitHub Enterprise Server (Self-Hosted)

For self-hosted GitHub Enterprise Server installations:

```bash
export GITHUB_API_BASE_URL="https://github.company.com/api/v3"
```

Or in config:
```yaml
github:
  enterprise: "your-enterprise"
  api_base_url: "https://github.company.com/api/v3"
```

**Note:** The tool will validate your API URL at startup and log which endpoint it's using.

## Teams Mode Details

For complete Teams Mode documentation, see:
- [TEAMS_QUICKSTART.md](TEAMS_QUICKSTART.md) - Step-by-step setup guide
- [TEAMS_INTEGRATION.md](TEAMS_INTEGRATION.md) - Full reference documentation

### Key Concepts

**Organization vs Enterprise Scope**
- **Organization**: Syncs teams from specific GitHub organizations you specify
- **Enterprise**: Syncs all teams across your entire GitHub Enterprise

**Cost Center Naming**
- Organization scope: `[org team] {org-name}/{team-name}`
- Enterprise scope: `[enterprise team] {team-name}`

**Multi-Team Users**
- Each user can only belong to ONE cost center
- Multi-team users are assigned to their last team's cost center
- Warnings logged for review before applying

### Manual Mode

For advanced use cases, map specific teams to specific cost centers:

```yaml
teams:
  mode: "manual"
  team_mappings:
    "my-org/frontend": "Engineering: Frontend"
    "my-org/backend": "Engineering: Backend"
```

## Usage

### Common Commands

```bash
# View configuration
python main.py --show-config
python main.py --teams-mode --show-config

# List all Copilot users
python main.py --list-users
```

### PRU-Based Mode

```bash
# Plan assignments (preview, no changes)
python main.py --assign-cost-centers --mode plan

# Apply assignments (with confirmation)
python main.py --assign-cost-centers --mode apply

# Apply without confirmation (automation)
python main.py --create-cost-centers --assign-cost-centers --mode apply --yes

# Move users between cost centers if needed
python main.py --assign-cost-centers --ignore-current-cost-center --mode apply

# Incremental mode (only new users, for cron jobs)
python main.py --assign-cost-centers --incremental --mode apply --yes
```

### Teams-Based Mode

```bash
# Plan assignments (preview, no changes)
python main.py --teams-mode --assign-cost-centers --mode plan

# Apply assignments (with confirmation)
python main.py --teams-mode --assign-cost-centers --mode apply

# Apply without confirmation (automation)
python main.py --teams-mode --assign-cost-centers --mode apply --yes

# Move users between cost centers if needed
python main.py --teams-mode --assign-cost-centers --ignore-current-cost-center --mode apply

# Generate summary report
python main.py --teams-mode --summary-report
```

**Smart User Handling:**
- By default, users already in cost centers are skipped to avoid conflicts
- Use `--ignore-current-cost-center` to move users between cost centers

### Cache Management (Performance Optimization)

The tool automatically caches cost center mappings to improve performance by avoiding redundant API calls:

```bash
# View cache statistics
python main.py --cache-stats

# Clear the entire cache
python main.py --clear-cache

# Remove expired cache entries
python main.py --cache-cleanup

# Cache is automatically used during normal operations
python main.py --teams-mode --assign-cost-centers --mode plan  # Uses cache
```

**Cache Benefits:**
- 📈 **Significant performance improvement** for teams with many cost centers
- 🔄 **Automatic expiration** (24 hours by default) ensures data freshness
- 💾 **GitHub Actions cache integration** for CI/CD workflows
- 🎯 **Smart invalidation** when configuration changes

**Cache Statistics Example:**
```
===== Cost Center Cache Statistics =====
Cache file: .cache/cost_centers.json
Total entries: 25
Valid entries: 23
Expired entries: 2
Cache TTL: 24.0 hours
Last updated: 2024-01-15T10:30:45.123456
Effective hit rate: 92.0%
==========================================
```

**Note:** Incremental mode is NOT supported in Teams Mode. All team members are processed every run.

## Incremental Processing (PRU Mode Only)

Process only users added since the last run - perfect for cron jobs:

```bash
# First run: processes all users, saves timestamp
python main.py --assign-cost-centers --incremental --mode apply --yes

# Subsequent runs: only new users
python main.py --assign-cost-centers --incremental --mode apply --yes
```

**Note:** Teams Mode does not support incremental processing.

## Logging

Logs are written to `logs/populate_cost_centers.log` with detailed tracking:

```log
2025-10-08 10:39:06 [INFO] ✅ Successfully added 3 users to cost center abc123
2025-10-08 10:39:06 [INFO]    ✅ user1 → abc123
2025-10-08 10:39:06 [INFO]    ✅ user2 → abc123  
2025-10-08 10:39:06 [INFO] 📊 ASSIGNMENT RESULTS: 3/3 users successfully assigned
```

## Automation

### GitHub Actions (Recommended)

The included workflow automatically syncs cost centers every 6 hours:

1. Add token as secret: `COST_CENTER_AUTOMATION_TOKEN`
2. Go to **Actions** tab → "Cost center automation"
3. Click "Run workflow" → Select mode → Run

See `.github/workflows/` for configuration.

### Docker

```bash
# Build and run
docker build -t copilot-cc .
docker run --rm -e GITHUB_TOKEN=$GITHUB_TOKEN copilot-cc \
  python main.py --assign-cost-centers --mode apply --yes

# Background service
docker compose up -d --build
```

### Cron Jobs

```bash
# PRU mode with incremental processing (hourly)
0 * * * * cd /path/to/repo && ./automation/update_cost_centers.sh

# Teams mode (weekly)
0 2 * * 1 cd /path/to/repo && python main.py --teams-mode --assign-cost-centers --mode apply --yes
```

See `automation/update_cost_centers.sh` for the included automation script.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| 401/403 errors | Regenerate token with correct scopes |
| No teams found | Verify `read:org` scope for Teams Mode |
| Cost center creation fails | Ensure `manage_billing:enterprise` scope |
| Multi-team user warnings | Review plan output, adjust team structure if needed |

Check `logs/populate_cost_centers.log` for detailed traces. Use `--verbose` for DEBUG logging.

## Contributing

1. Fork this repository and create a branch (`feat/<name>`)
2. Make focused changes with clear commit messages
3. Submit PR with description and link related issues

## Additional Documentation

- [TEAMS_QUICKSTART.md](TEAMS_QUICKSTART.md) - Teams Mode setup guide
- [TEAMS_INTEGRATION.md](TEAMS_INTEGRATION.md) - Teams Mode reference
- [REMOVED_USERS_FEATURE.md](REMOVED_USERS_FEATURE.md) - Full sync mode documentation

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) file for details.

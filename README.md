# GitHub cost center manager

This utility allows for auto-assignment of all Copilot-licensed users in a given enterprise to a cost center.

## 🚀 Quick start guide

### Option A: GitHub Actions (Recommended)

1. **Create a new repository from this template** in your GitHub Enterprise organization:
   - Click the green "Use this template" button at the top of this repository.
   - Fill in the repository details and create your own copy.

2. **Add your GitHub token as a repository secret**:
   - Go to your new repository’s **Settings** → **Secrets and variables** → **Actions**
   - Add secret: `COPILOT_GITHUB_TOKEN` (your GitHub Personal Access Token with `manage_billing:enterprise` scope)

3. **Run the workflow**:
   - Go to the **Actions** tab → "GitHub Copilot Cost Center Automation"
   - Click "Run workflow" → Select "incremental" mode → Run

4. **Done!** The workflow automatically:
   - Detects your enterprise
   - Creates cost centers if needed ("00 - No PRU overages", "01 - PRU overages allowed")
   - Assigns all Copilot users to appropriate cost centers
   - Runs every 6 hours automatically

### Option B: Local Execution

1. **Clone and setup**:
   ```bash
   git clone <your-repo-url>
   cd populate_cost_centers
   pip install -r requirements.txt
   ```

2. **Configure**:
   ```bash
   cp config/config.example.yaml config/config.yaml
   echo "GITHUB_TOKEN=your_github_token_here" > .env
   # Edit config/config.yaml - set your enterprise name (or leave auto-detection)
   ```

3. **Run**:
   ```bash
   # Create cost centers and assign users (with confirmation)
   python main.py --create-cost-centers --assign-cost-centers --mode apply
   ```

**That's it!** Your Copilot users are now organized in cost centers for better billing tracking.

## Overview

Automates GitHub Copilot license cost center assignments for enterprises using a simple two-tier model:
- **Default**: All Copilot users are added to `00 - No PRU overages` cost center
- **Exceptions**: Specified users are added to `01 - PRU overages allowed` cost center

Supports both interactive execution and automated scheduling with incremental processing.

## Features

- **Automatic cost center creation**: Creates cost centers automatically (or use existing cost centers, if preferred)
- **Incremental processing**: Only process users added since last run (perfect for cron jobs)
- **Enhanced result logging**: Real-time success/failure tracking with user-level detail
- Plan vs apply execution (`--mode plan|apply`) + interactive safety prompt (bypass with `--yes`)
- Container friendly (Dockerfile + docker-compose)
- GitHub Actions & cron automation examples

## Prerequisites

- Python 3.8 or higher
- GitHub Enterprise Cloud admin access
- GitHub Personal Access Token with appropriate permissions:
  - For **Enterprise**: Enterprise admin permissions or `manage_billing:enterprise` scope

## Installation

1. Clone or download your repository created from this template
2. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Copy the example configuration:
   ```bash
   cp config/config.example.yaml config/config.yaml
   ```

4. Set up your GitHub token:
   ```bash
   echo "GITHUB_TOKEN=your_actual_token_here" > .env
   ```

5. Edit `config/config.yaml` with your:
   - GitHub Enterprise name
   - Cost center IDs (if they exist) OR enable auto-creation
   - Any users which should get access to additional PRUs

## Configuration

All configuration lives in: `config/config.yaml` (example below) 

### Core Keys
```yaml
github:
  # Provide either slug 
  enterprise: "your_enterprise_name"    
  # token: "YOUR_TOKEN_HERE"   # Prefer setting GITHUB_TOKEN env var instead

cost_centers:
  no_prus_cost_center: "REPLACE_WITH_NO_PRUS_COST_CENTER_ID"
  prus_allowed_cost_center: "REPLACE_WITH_PRUS_ALLOWED_COST_CENTER_ID"
  prus_exception_users:
    # - "alice"
    # - "bob"
  
  # Auto-creation settings (creates cost centers if they don't exist)
  auto_create: false  # Set to true to enable auto-creation
  no_pru_name: "00 - No PRU overages"  # Name for no-PRU cost center
  pru_allowed_name: "01 - PRU overages allowed"  # Name for PRU-allowed cost center

logging:
  level: "INFO"
  file: "logs/populate_cost_centers.log"
```

### Placeholder Warnings
If either cost center ID still equals `REPLACE_WITH_*` (or the sample defaults) a WARNING is logged. In plan mode this is informational; in apply mode you should fix values before proceeding.

### User Assignment Logic
- Default: everyone → `no_prus_cost_center`
- If username in `prus_exception_users` → `prus_allowed_cost_center`

### Environment Variables (override config)
- `GITHUB_TOKEN`
- `GITHUB_ENTERPRISE`

### Duplicate Seat Handling
If the Copilot seat API returns the same user more than once, duplicates are skipped and summarized in a warning.

## Cost Center Auto-Creation

This tool can automatically create cost centers if they don't exist, eliminating manual GitHub UI setup:

### Quick Start with Auto-Creation

```bash
# Plan what cost centers would be created
python main.py --create-cost-centers --show-config

# Create cost centers and assign users (with confirmation prompt)
python main.py --create-cost-centers --assign-cost-centers --mode apply

# Non-interactive creation for automation
python main.py --create-cost-centers --assign-cost-centers --mode apply --yes
```

### Default Cost Center Names
- **`"00 - No PRU overages"`** - For users without PRU access (majority)
- **`"01 - PRU overages allowed"`** - For exception users with PRU access

### Configuration Options

**Enable via config file:**
```yaml
cost_centers:
  auto_create: true  # Enable automatic creation
  no_pru_name: "Custom No PRU Name"  # Optional: customize names
  pru_allowed_name: "Custom PRU Name"
```

**Or use command line flag:** `--create-cost-centers`

### How It Works
1. **Detection**: Checks if cost centers with specified names already exist
2. **Creation**: Creates missing cost centers via GitHub Enterprise API
3. **Assignment**: Uses the created cost center IDs for user assignments
4. **Idempotent**: Safe to run multiple times - won't create duplicates

## Usage

### Basic Usage

```bash
# Show current configuration and PRUs exception users
python main.py --show-config

# List all Copilot license holders (shows PRUs exceptions)
python main.py --list-users

# Plan cost center assignments (no changes made)
python main.py --assign-cost-centers --mode plan

# Apply cost center assignments (will prompt for confirmation)
python main.py --assign-cost-centers --mode apply
```

### Additional Examples

```bash
# Apply without interactive confirmation (for automation)
python main.py --assign-cost-centers --mode apply --yes

# Generate summary report (plan mode by default)
python main.py --assign-cost-centers --summary-report

# Process only specific users (plan)
python main.py --users user1,user2,user3 --assign-cost-centers --mode plan

# Auto-create cost centers and assign users (with confirmation)
python main.py --create-cost-centers --assign-cost-centers --mode apply

# Auto-create and assign (non-interactive)
python main.py --create-cost-centers --assign-cost-centers --mode apply --yes

# Incremental processing - only process users added since last run (ideal for cron jobs)
python main.py --assign-cost-centers --incremental --mode apply --yes

# Plan mode with incremental processing (see what new users would be processed)
python main.py --assign-cost-centers --incremental --mode plan

# Full cron job setup: incremental processing with detailed logging and reports
python main.py --assign-cost-centers --incremental --mode apply --yes --summary-report
```

## Incremental Processing

For efficient cron job automation, the `--incremental` flag processes only users added since the last successful run:

### How it Works

1. **First Run**: Processes all users and saves timestamp to `exports/.last_run_timestamp`
2. **Subsequent Runs**: Only processes users with `created_at` timestamp after the last run
3. **No New Users**: Exits quickly with "No new users found since last run"
4. **Timestamp Updates**: Only saved on successful `--mode apply` executions

### Automation Script

The included automation script defaults to incremental mode:

```bash
# Incremental mode (default - recommended for cron jobs)
./automation/update_cost_centers.sh

# Full mode (processes all users)
./automation/update_cost_centers.sh full
```

## Enhanced Result Logging

The tool provides **real-time detailed logging** showing actual assignment results:

### What You Get

- **✅ Individual User Success**: `✅ username → cost_center_id`
- **❌ Individual User Failures**: `❌ username → cost_center_id (API Error)`
- **📊 Batch Progress**: `Batch 1 completed: 5 successful, 0 failed`
- **📈 Final Results**: `📊 ASSIGNMENT RESULTS: 95/100 users successfully assigned`
- **🎯 Success Summary**: `✅ Assignment success rate: 95/100 users`

### Example Output

```log
2025-09-24 10:39:06 [INFO] src.github_api: ✅ Successfully assigned 3 users to cost center abc123
2025-09-24 10:39:06 [INFO] src.github_api:    ✅ user1 → abc123
2025-09-24 10:39:06 [INFO] src.github_api:    ✅ user2 → abc123  
2025-09-24 10:39:06 [INFO] src.github_api:    ✅ user3 → abc123
2025-09-24 10:39:06 [INFO] src.github_api: 📊 ASSIGNMENT RESULTS: 3/3 users successfully assigned
2025-09-24 10:39:06 [INFO] src.github_api: 🎉 All users successfully assigned!
```

## Output Files

Generated files include timestamp for traceability:

- `logs/populate_cost_centers.log` – Detailed execution log with enhanced result tracking
- `exports/.last_run_timestamp` – Timestamp for incremental processing (JSON format)

### Log File Features

- **Rotating logs** to prevent disk space issues
- **Structured format** with timestamps and log levels
- **Enhanced result tracking** with individual user success/failure details
- **API response logging** for troubleshooting
- **Performance metrics** and execution summaries

## Configuration Files

- `config/config.yaml` - Single configuration file containing all settings (GitHub API, cost centers, logging)
- `config/config.example.yaml` - Example template to copy from
- `.env` - Environment variables (GitHub token, optional overrides)

## Automation

### Docker
```bash
# Build image
docker build -t copilot-cc .

# Plan mode
docker run --rm -e GITHUB_TOKEN=$GITHUB_TOKEN copilot-cc \
  python main.py --assign-cost-centers --mode plan --summary-report

# Apply with auto-creation
docker run --rm -e GITHUB_TOKEN=$GITHUB_TOKEN copilot-cc \
  python main.py --create-cost-centers --assign-cost-centers --mode apply --yes --verbose

# Background service
docker compose up -d --build
```

### GitHub Actions
```yaml
# Incremental processing (recommended for scheduled workflows)
- name: Apply cost centers (incremental)
  run: |
    python main.py --assign-cost-centers --incremental --mode apply --yes --summary-report

# Full processing (weekly/monthly)
- name: Apply cost centers (full)
  run: |
    python main.py --assign-cost-centers --mode apply --yes --summary-report

# Plan mode for validation
- name: Plan cost center assignments
  run: |
    python main.py --assign-cost-centers --incremental --mode plan --summary-report
```

### Cron / Shell Script
See `automation/update_cost_centers.sh` - uses incremental processing by default for efficient cron execution:

```bash
# Incremental mode (default - processes only new users)
./automation/update_cost_centers.sh

# Full mode (processes all users)  
./automation/update_cost_centers.sh full
```

The script includes detailed logging and `--summary-report` for comprehensive automation monitoring.

**Monitor execution:**
```bash
# View live logs
tail -f logs/populate_cost_centers.log

# Cron job examples
0 * * * * cd /path/to/populate_cost_centers && ./automation/update_cost_centers.sh >/dev/null 2>&1  # Hourly incremental
0 2 * * 0 cd /path/to/populate_cost_centers && ./automation/update_cost_centers.sh full >/dev/null 2>&1  # Weekly full
```

## Troubleshooting

| Issue | Explanation | Action |
|-------|-------------|--------|
| Placeholder warning | Cost center ID not replaced | Edit `config/config.yaml` |
| 401 / 403 errors | Token missing scope / expired | Regenerate PAT with required scopes |
| No users returned | No active Copilot seats | Verify seat assignments in Enterprise settings |
| Apply aborted | Confirmation not granted | Re-run with `--yes` or type `apply` at prompt |
| Cost center creation failed | Missing enterprise permissions | Ensure token has `manage_billing:enterprise` scope |

Logs: inspect `logs/populate_cost_centers.log` for detailed traces (DEBUG if `--verbose`).

## Contributing

1. Create your own repository from the template & branch (`feat/<name>`)
2. Add/adjust tests (future enhancement: test harness TBD)
3. Keep changeset focused & documented in commit message
4. Submit PR with before/after summary
5. Tag reviewers & link related issues

## License

MIT License — see LICENSE for details.

---
Maintained state: Tags `v0.1.0` (baseline refactor), `v0.1.1` (apply confirmation & flags). Latest: Enhanced result logging, incremental processing, automatic cost center creation.

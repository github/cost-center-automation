# Simplified GitHub Copilot Cost Center Management

A simplified Python script to manage GitHub Copilot license holders with a two-cost-center model for PRUs management.

## Features

- **Simple Two-Cost-Center Model:**
  - `no_PRUs_costCenter`: Default cost center for all users (no Private Repository Usage)
  - `PRUs_allowed_costCenter`: Exception cost center for users allowed PRUs
- List all GitHub Copilot license holders in your enterprise
- **Exception-based assignment**: Only users in the exception list get PRUs access
- **Sync cost center assignments back to GitHub Enterprise**
- Export data to CSV and Excel formats
- Comprehensive logging and error handling
- Support for dry-run testing and automation

## Prerequisites

- Python 3.8 or higher
- GitHub Enterprise Cloud or GitHub organization admin access
- GitHub Personal Access Token with appropriate permissions:
  - For **Enterprise**: Enterprise admin permissions or `manage_billing:enterprise` scope
  - For **Organization**: `admin:org` and `user:read` scopes

## Installation

1. Clone or download this repository
2. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Copy the example configuration:
   ```bash
   cp config/config.example.yaml config/config.yaml
   ```

4. Edit `config/config.yaml` with your:
   - GitHub Enterprise name
   - GitHub Personal Access Token with enterprise billing permissions
   - Cost center IDs for your two cost centers

5. Edit `config/cost_centers.yaml` to specify which users should get PRUs access

## Configuration

### Cost Center Setup

The script uses a simple two-cost-center model:

1. **`no_PRUs_costCenter`**: Default cost center ID for all users (no Private Repository Usage allowed)
2. **`PRUs_allowed_costCenter`**: Cost center ID for users who are allowed Private Repository Usage

### User Assignment Logic

- **Default**: All users are assigned to `no_PRUs_costCenter`
- **Exception**: Only users listed in `config/cost_centers.yaml` under `PRUs_exception_users` are assigned to `PRUs_allowed_costCenter`

### Example Configuration

**config/config.yaml:**
```yaml
github:
  enterprise: "your_enterprise_name"
  token: "your_github_token"

cost_centers:
  no_PRUs_costCenter: "CC-001-NO-PRUS"
  PRUs_allowed_costCenter: "CC-002-PRUS-ALLOWED"
```

**config/cost_centers.yaml:**
```yaml
PRUs_exception_users:
  - "admin.user"
  - "senior.developer"
  - "team.lead"
```

## Usage

### Basic Usage

```bash
# Show current configuration and PRUs exception users
python main.py --show-config

# List all Copilot license holders (shows PRUs exceptions)
python main.py --list-users

# Assign cost centers using simplified PRUs model
python main.py --assign-cost-centers --export csv

# Dry run to preview cost center assignments
python main.py --assign-cost-centers --dry-run
```

### Advanced Usage

```bash
# Assign and sync cost centers back to GitHub Enterprise
python main.py --assign-cost-centers --sync-cost-centers

# Generate summary report
python main.py --assign-cost-centers --summary-report

# Process only specific users
python main.py --users user1,user2,user3 --assign-cost-centers --dry-run

# Export to Excel with cost center assignments
python main.py --assign-cost-centers --export excel
```

## Output Files

- `exports/copilot_users.csv` - User list with cost center assignments
- `exports/copilot_users.xlsx` - Detailed Excel report
- `exports/cost_center_summary.csv` - Cost center breakdown
- `logs/` - Application logs

## Configuration Files

- `config/config.yaml` - Main configuration (GitHub API, organization settings)
- `config/cost_centers.yaml` - Cost center assignment rules
- `config/logging.yaml` - Logging configuration

## Automation

The script can be automated using:
- Cron jobs for scheduled updates
- GitHub Actions for CI/CD integration
- Docker containers for consistent execution

See the `automation/` directory for examples.

## Troubleshooting

### Common Issues

1. **API Rate Limits**: The script respects GitHub API rate limits and will automatically retry
2. **Permission Issues**: Ensure your token has `admin:org` permissions
3. **Missing Users**: Check if users have Copilot licenses activated

### Logs

Check the `logs/` directory for detailed execution logs and error messages.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

MIT License - see LICENSE file for details.
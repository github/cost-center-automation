# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Repository-Based Cost Center Assignment**: New mode for assigning repositories to cost centers based on custom properties
  - Explicit mapping mode: Map custom property values to specific cost centers
  - Works with any repository custom property (team, service, environment, etc.)
  - Automatic cost center creation for new mappings
  - Full pagination support for organizations with many repositories
  - Comprehensive logging showing repository discovery, matching, and assignment
- New module `repository_cost_center_manager.py` for repository-based assignment logic
- New GitHub API methods for custom properties:
  - `get_org_custom_properties()`: Fetch organization custom property schema
  - `get_org_repositories_with_properties()`: List repositories with their property values (paginated)
  - `get_all_org_repositories_with_properties()`: Automatic pagination wrapper
  - `get_repository_custom_properties()`: Get properties for a specific repository
  - `add_repositories_to_cost_center()`: Batch assign repositories to cost centers
- Configuration support for repository mode in `config_manager.py`
  - New `github.cost_centers.mode` setting (supports "users", "teams", or "repository")
  - New `github.cost_centers.repository_config` section with validation
  - Explicit mappings configuration with property name and value matching
- Documentation for repository mode in README.md with examples
- Detailed design document in `REPOSITORY_COST_CENTER_DESIGN.md`
- **GitHub Enterprise Data Resident Support**: Full support for enterprises running on GitHub Enterprise Data Resident (GHE.com) with custom API endpoints
- New configuration option `github.api_base_url` in config files for custom API endpoints
- New environment variable `GITHUB_API_BASE_URL` for custom API endpoint configuration
- Automatic API URL validation with support for:
  - Standard GitHub.com (`https://api.github.com`)
  - GitHub Enterprise Data Resident (`https://api.{subdomain}.ghe.com`)
  - GitHub Enterprise Server (`https://{hostname}/api/v3`)
- Comprehensive logging to show which API endpoint is being used at startup
- Updated documentation in README.md, config.example.yaml, and .env.example

### Changed
- Updated `main.py` to support three operational modes (PRU-based, Teams-based, Repository-based)
- Renamed "Two Operational Modes" to "Three Operational Modes" in documentation
- `GitHubCopilotManager` now uses configurable API base URL instead of hardcoded value
- URL validation and normalization in `ConfigManager` to ensure proper API endpoint formatting

## [1.0.0] - 2024-09-25

### Added
- Initial release of the cost center automation tool
- GitHub Actions workflow for automated cost center management
- Support for incremental and full processing modes
- Automatic enterprise detection and cost center assignment
- Comprehensive documentation and setup instructions

### Features
- **Automated Cost Center Management**: Creates and assigns cost centers automatically
- **Incremental Processing**: Only processes changes since last run for efficiency
- **Enterprise Detection**: Automatically detects GitHub Enterprise context
- **Flexible Configuration**: Supports both GitHub Actions and local execution modes
- **Comprehensive Logging**: Detailed logging and artifact collection

### Workflows
- `cost-center-automation.yml`: Main automation workflow

### Configuration
- Support for `COST_CENTER_AUTOMATION_TOKEN` secret
- Configurable cron schedules (every 6 hours by default)
- Manual workflow dispatch with mode selection

### Documentation
- Complete setup instructions for GitHub Actions and local execution
- Troubleshooting guide with common issues and solutions
- API reference and configuration options
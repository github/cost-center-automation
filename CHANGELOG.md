# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
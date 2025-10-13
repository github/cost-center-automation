#!/bin/bash

# GitHub Copilot Cost Center Update Script
# This script runs the cost center assignment and exports data
# Usage: ./update_cost_centers.sh [full]
#   - Default: Incremental processing (only new users since last run)
#   - full: Process all users (full sync)

# Set script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Check if full mode is requested
FULL_MODE=false
if [ "$1" = "full" ]; then
    FULL_MODE=true
    echo "Running in FULL mode - processing all users"
else
    echo "Running in INCREMENTAL mode - processing only new users since last run"
fi

# Change to project directory
cd "$PROJECT_DIR"

# Set Python executable (use venv if it exists, otherwise try .venv)
PYTHON_CMD="python"
if [ -d ".venv" ]; then
    PYTHON_CMD=".venv/bin/python"
    echo "Using Python from .venv: $PYTHON_CMD"
elif [ -d "venv" ]; then
    source venv/bin/activate
    echo "Activated venv"
else
    echo "Using system Python: $PYTHON_CMD"
fi

# Set log file with timestamp
LOG_FILE="logs/automation_$(date +%Y%m%d_%H%M%S).log"

echo "Starting Copilot cost center update at $(date)" | tee -a "$LOG_FILE"

# Build command arguments based on mode
CMD_ARGS="--assign-cost-centers The script includes detailed logging and `--summary-report` for comprehensive automation monitoring. --mode apply --yes --verbose"

# Add incremental flag unless full mode is requested
if [ "$FULL_MODE" = false ]; then
    CMD_ARGS="$CMD_ARGS --incremental"
fi

echo "Running command: $PYTHON_CMD main.py $CMD_ARGS" | tee -a "$LOG_FILE"

# Run the main script with cost center assignment and export
$PYTHON_CMD main.py $CMD_ARGS 2>&1 | tee -a "$LOG_FILE"

# Check exit status
if [ $? -eq 0 ]; then
    echo "Script completed successfully at $(date)" | tee -a "$LOG_FILE"
    
    # Optional: Send notification (uncomment and configure)
    # echo "Copilot cost center update completed successfully" | mail -s "Copilot Update Success" admin@company.com
else
    echo "Script failed at $(date)" | tee -a "$LOG_FILE"
    
    # Optional: Send error notification (uncomment and configure)
    # echo "Copilot cost center update failed. Check logs: $LOG_FILE" | mail -s "Copilot Update Failed" admin@company.com
fi
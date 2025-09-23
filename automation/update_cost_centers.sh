#!/bin/bash

# GitHub Copilot Cost Center Update Script
# This script runs the cost center assignment and exports data

# Set script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Change to project directory
cd "$PROJECT_DIR"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Set log file with timestamp
LOG_FILE="logs/automation_$(date +%Y%m%d_%H%M%S).log"

echo "Starting Copilot cost center update at $(date)" | tee -a "$LOG_FILE"

# Run the main script with cost center assignment and export
python main.py \
    --assign-cost-centers \
    --export both \
    --summary-report \
    --verbose \
    2>&1 | tee -a "$LOG_FILE"

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
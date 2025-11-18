#!/bin/bash
# One-command script to retrieve Amazon data and display in dashboard
# ====================================================================
#
# This script:
# 1. Fetches credentials from Google Secret Manager
# 2. Retrieves data from Amazon Ads API
# 3. Exports to BigQuery
# 4. Launches dashboard to display the data
#
# Prerequisites:
# - ppc_config.yaml configured with project_id and secret_id
# - Google Cloud authenticated (gcloud auth application-default login)
# - Dependencies installed (pip install -r requirements.txt)
#
# Usage:
#   ./retrieve_and_display.sh
#
# Or with custom config:
#   ./retrieve_and_display.sh my_config.yaml

set -e  # Exit on error

CONFIG_FILE="${1:-ppc_config.yaml}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "================================================================================"
echo "AMAZON PPC: RETRIEVE DATA AND DISPLAY IN DASHBOARD"
echo "================================================================================"
echo ""

# Check if config exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ Configuration file not found: $CONFIG_FILE"
    echo ""
    echo "Create one from the example:"
    echo "  cp ppc_config.example.yaml $CONFIG_FILE"
    echo ""
    echo "Then edit it with your settings:"
    echo "  google_cloud:"
    echo "    project_id: 'your-gcp-project-id'"
    echo "    secret_id: 'amazon-ads-credentials'"
    exit 1
fi

echo "✅ Using configuration: $CONFIG_FILE"
echo ""

# Extract profile ID from config if available
PROFILE_ID=$(python3 -c "
import yaml
try:
    with open('$CONFIG_FILE') as f:
        config = yaml.safe_load(f)
        print(config.get('google_cloud', {}).get('project_id', ''))
except:
    print('')
" 2>/dev/null || echo "")

# Step 1: Run the complete pipeline
echo "================================================================================"
echo "STEP 1: RETRIEVE DATA FROM AMAZON"
echo "================================================================================"
echo ""
echo "This will:"
echo "  1. Fetch credentials from Google Secret Manager"
echo "  2. Connect to Amazon Ads API"
echo "  3. Retrieve campaign and performance data"
echo "  4. Export to BigQuery"
echo ""
echo "Starting pipeline..."
echo ""

python3 run_complete_pipeline.py --config "$CONFIG_FILE"

PIPELINE_STATUS=$?

if [ $PIPELINE_STATUS -ne 0 ]; then
    echo ""
    echo "❌ Pipeline failed. Please check the errors above."
    exit 1
fi

echo ""
echo "✅ Data successfully retrieved and exported to BigQuery!"
echo ""

# Step 2: Launch dashboard
echo "================================================================================"
echo "STEP 2: LAUNCH DASHBOARD"
echo "================================================================================"
echo ""
echo "Starting Streamlit dashboard..."
echo ""
echo "The dashboard will open in your browser at http://localhost:8501"
echo ""
echo "In the dashboard:"
echo "  1. Select 'BigQuery' as data source in the sidebar"
echo "  2. Enter your GCP Project ID"
echo "  3. Your real Amazon PPC data will be displayed!"
echo ""
echo "Press Ctrl+C to stop the dashboard when done."
echo ""

# Launch dashboard
streamlit run dashboard.py

echo ""
echo "================================================================================"
echo "Dashboard stopped"
echo "================================================================================"

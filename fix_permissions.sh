#!/bin/bash
# Fix permissions for existing service account
# Usage: ./fix_permissions.sh [PROJECT_ID]

set -e

PROJECT_ID="${1:-${GCP_PROJECT_ID}}"
SERVICE_ACCOUNT="dashboard-sa"

if [ -z "$PROJECT_ID" ]; then
    echo "❌ Error: PROJECT_ID not provided"
    echo ""
    echo "Usage:"
    echo "  ./fix_permissions.sh PROJECT_ID"
    echo ""
    echo "Or set environment variable:"
    echo "  export GCP_PROJECT_ID=your-project-id"
    echo "  ./fix_permissions.sh"
    exit 1
fi

echo "================================================================================"
echo "FIXING PERMISSIONS FOR DASHBOARD SERVICE ACCOUNT"
echo "================================================================================"
echo ""
echo "Project ID: $PROJECT_ID"
echo "Service Account: ${SERVICE_ACCOUNT}@${PROJECT_ID}.iam.gserviceaccount.com"
echo ""

# Set project
gcloud config set project "$PROJECT_ID"

# Check if service account exists
if ! gcloud iam service-accounts describe "${SERVICE_ACCOUNT}@${PROJECT_ID}.iam.gserviceaccount.com" >/dev/null 2>&1; then
    echo "❌ Service account does not exist. Run deploy_cloudrun.sh first."
    exit 1
fi

echo "Granting BigQuery User role (for running queries)..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${SERVICE_ACCOUNT}@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/bigquery.user" \
    --condition=None

echo ""
echo "Granting BigQuery Data Viewer role..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${SERVICE_ACCOUNT}@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/bigquery.dataViewer" \
    --condition=None

echo ""
echo "Granting Secret Manager Secret Accessor role..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${SERVICE_ACCOUNT}@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor" \
    --condition=None

echo ""
echo "================================================================================"
echo "✅ PERMISSIONS UPDATED SUCCESSFULLY"
echo "================================================================================"
echo ""
echo "The service account now has:"
echo "  - BigQuery User (to run queries)"
echo "  - BigQuery Data Viewer (to read data)"
echo "  - Secret Manager Secret Accessor (to read secrets)"
echo ""
echo "You can now redeploy the dashboard:"
echo "  ./deploy_cloudrun.sh $PROJECT_ID"
echo ""
echo "Or just update the running service to use the new code:"
echo "  cd /path/to/optimizer"
echo "  git pull"
echo "  gcloud run deploy amazon-ppc-dashboard --source . --region us-central1"
echo ""
echo "================================================================================"

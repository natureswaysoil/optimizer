#!/bin/bash
# Deploy Amazon PPC Dashboard to Google Cloud Run
# Usage: ./deploy_cloudrun.sh [PROJECT_ID] [REGION]

set -e  # Exit on error

# Configuration
PROJECT_ID="${1:-${GCP_PROJECT_ID}}"
REGION="${2:-us-central1}"
SERVICE_NAME="amazon-ppc-dashboard"
SERVICE_ACCOUNT="dashboard-sa"

echo "================================================================================"
echo "DEPLOYING AMAZON PPC DASHBOARD TO GOOGLE CLOUD RUN"
echo "================================================================================"
echo ""

# Validate inputs
if [ -z "$PROJECT_ID" ]; then
    echo "❌ Error: PROJECT_ID not provided"
    echo ""
    echo "Usage:"
    echo "  ./deploy_cloudrun.sh PROJECT_ID [REGION]"
    echo ""
    echo "Or set environment variable:"
    echo "  export GCP_PROJECT_ID=your-project-id"
    echo "  ./deploy_cloudrun.sh"
    exit 1
fi

echo "Configuration:"
echo "  Project ID: $PROJECT_ID"
echo "  Region: $REGION"
echo "  Service: $SERVICE_NAME"
echo ""

# Set project
echo "Setting GCP project..."
gcloud config set project "$PROJECT_ID"

# Enable required APIs
echo ""
echo "Enabling required APIs..."
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable bigquery.googleapis.com

# Create service account if it doesn't exist
echo ""
echo "Checking service account..."
if ! gcloud iam service-accounts describe "${SERVICE_ACCOUNT}@${PROJECT_ID}.iam.gserviceaccount.com" >/dev/null 2>&1; then
    echo "Creating service account..."
    gcloud iam service-accounts create "$SERVICE_ACCOUNT" \
        --display-name="Dashboard Service Account" \
        --description="Service account for Amazon PPC Dashboard"
    
    # Grant permissions
    echo "Granting permissions..."
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:${SERVICE_ACCOUNT}@${PROJECT_ID}.iam.gserviceaccount.com" \
        --role="roles/bigquery.user"
    
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:${SERVICE_ACCOUNT}@${PROJECT_ID}.iam.gserviceaccount.com" \
        --role="roles/bigquery.dataViewer"
    
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:${SERVICE_ACCOUNT}@${PROJECT_ID}.iam.gserviceaccount.com" \
        --role="roles/secretmanager.secretAccessor"
    
    echo "✅ Service account created and configured"
else
    echo "✅ Service account already exists"
fi

# Build and deploy
echo ""
echo "================================================================================"
echo "BUILDING AND DEPLOYING TO CLOUD RUN"
echo "================================================================================"
echo ""
echo "This will take 3-5 minutes..."
echo ""

gcloud run deploy "$SERVICE_NAME" \
    --source . \
    --platform managed \
    --region "$REGION" \
    --allow-unauthenticated \
    --service-account="${SERVICE_ACCOUNT}@${PROJECT_ID}.iam.gserviceaccount.com" \
    --set-env-vars="GCP_PROJECT_ID=$PROJECT_ID" \
    --memory=2Gi \
    --cpu=1 \
    --timeout=3600 \
    --max-instances=10 \
    --min-instances=1

# Get service URL
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
    --platform managed \
    --region "$REGION" \
    --format="value(status.url)")

echo ""
echo "================================================================================"
echo "✅ DEPLOYMENT SUCCESSFUL!"
echo "================================================================================"
echo ""
echo "Dashboard URL: $SERVICE_URL"
echo ""
echo "Next steps:"
echo "1. Visit the dashboard URL above"
echo "2. Select 'BigQuery' as data source in the sidebar"
echo "3. Enter Project ID: $PROJECT_ID"
echo "4. Your live Amazon PPC data will load automatically!"
echo ""
echo "To view logs:"
echo "  gcloud run logs read $SERVICE_NAME --region $REGION --limit 50"
echo ""
echo "To update deployment:"
echo "  ./deploy_cloudrun.sh $PROJECT_ID $REGION"
echo ""
echo "================================================================================"

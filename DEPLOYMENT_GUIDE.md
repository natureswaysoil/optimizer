# Dashboard Deployment Guide

This guide shows you how to deploy the Amazon PPC dashboard to various cloud platforms so it's accessible via a public URL with your live BigQuery data.

## 🚀 Deployment Options

### Option 1: Google Cloud Run (Recommended)
- **Cost**: ~$5-20/month with always-on instance
- **Setup Time**: 10-15 minutes
- **Best For**: Production deployments with automatic scaling

### Option 2: Streamlit Community Cloud
- **Cost**: Free tier available
- **Setup Time**: 5-10 minutes
- **Best For**: Quick prototypes and demos

### Option 3: Google App Engine
- **Cost**: ~$10-30/month
- **Setup Time**: 15-20 minutes
- **Best For**: Enterprise deployments with SLA requirements

## 📋 Prerequisites

Before deploying, ensure you have:

1. **Google Cloud Project** with billing enabled
2. **BigQuery dataset** with your Amazon PPC data
3. **Secret Manager** with Amazon Ads credentials
4. **gcloud CLI** installed and authenticated

```bash
# Install gcloud if not already installed
curl https://sdk.cloud.google.com | bash

# Authenticate
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

---

## 🐳 Option 1: Google Cloud Run (Recommended)

### Step 1: Create Deployment Files

The repository already includes:
- `Dockerfile` - Container configuration
- `app.yaml` - App Engine config (if needed)
- `.dockerignore` - Files to exclude from container

### Step 2: Configure for Cloud Run

Edit `ppc_config.yaml` for production:

```yaml
google_cloud:
  project_id: "your-gcp-project-id"
  secret_id: "amazon-ads-credentials"
  bigquery:
    dataset_id: "amazon_ads_data"
```

### Step 3: Deploy to Cloud Run

Use the provided deployment script:

```bash
# Make script executable
chmod +x deploy_cloudrun.sh

# Deploy
./deploy_cloudrun.sh
```

Or manually:

```bash
# Set variables
PROJECT_ID="your-project-id"
REGION="us-central1"
SERVICE_NAME="amazon-ppc-dashboard"

# Enable required APIs
gcloud services enable run.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable bigquery.googleapis.com

# Build and deploy
gcloud run deploy $SERVICE_NAME \
  --source . \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --set-env-vars="GCP_PROJECT_ID=$PROJECT_ID" \
  --service-account=dashboard-sa@$PROJECT_ID.iam.gserviceaccount.com
```

### Step 4: Access Your Dashboard

After deployment, you'll get a URL like:
```
https://amazon-ppc-dashboard-xxxxx-uc.a.run.app
```

The dashboard will automatically:
- Load configuration from Cloud environment
- Fetch credentials from Secret Manager
- Connect to your BigQuery data
- Display your live Amazon PPC metrics

---

## ☁️ Option 2: Streamlit Community Cloud

### Step 1: Prepare Repository

1. Push your code to GitHub (already done for this PR)
2. Ensure `requirements.txt` is up to date
3. Create `secrets.toml` template

### Step 2: Deploy to Streamlit Cloud

1. Go to https://share.streamlit.io/
2. Sign in with GitHub
3. Click "New app"
4. Select repository: `natureswaysoil/optimizer`
5. Main file path: `dashboard.py`
6. Click "Deploy"

### Step 3: Configure Secrets

In Streamlit Cloud dashboard:

1. Go to App Settings > Secrets
2. Add your configuration:

```toml
# .streamlit/secrets.toml format
[gcp]
project_id = "your-gcp-project-id"
dataset_id = "amazon_ads_data"

# Service account key (for BigQuery access)
[gcp.service_account]
type = "service_account"
project_id = "your-project-id"
private_key_id = "key-id"
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "dashboard@your-project.iam.gserviceaccount.com"
client_id = "12345"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
```

### Step 4: Update Dashboard for Streamlit Cloud

Modify `dashboard.py` to read from Streamlit secrets:

```python
import streamlit as st

# Load config from Streamlit secrets if available
if hasattr(st, 'secrets') and 'gcp' in st.secrets:
    project_id = st.secrets.gcp.project_id
    dataset_id = st.secrets.gcp.dataset_id
```

---

## 🏢 Option 3: Google App Engine

### Step 1: Create app.yaml

The repository includes `app.yaml`. Verify configuration:

```yaml
runtime: python39
entrypoint: streamlit run dashboard.py --server.port=$PORT

env_variables:
  GCP_PROJECT_ID: "your-project-id"
  DATASET_ID: "amazon_ads_data"

automatic_scaling:
  min_instances: 1
  max_instances: 10
```

### Step 2: Deploy

```bash
gcloud app deploy app.yaml
```

### Step 3: Access Dashboard

```bash
gcloud app browse
```

---

## 🔒 Security Configuration

### Service Account Setup

Create a service account for the dashboard:

```bash
# Create service account
gcloud iam service-accounts create dashboard-sa \
  --display-name="Dashboard Service Account"

# Grant permissions
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:dashboard-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/bigquery.dataViewer"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:dashboard-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

### Configure Authentication

For production deployments, enable authentication:

**Cloud Run:**
```bash
# Deploy with authentication
gcloud run deploy amazon-ppc-dashboard \
  --source . \
  --no-allow-unauthenticated

# Grant access to specific users
gcloud run services add-iam-policy-binding amazon-ppc-dashboard \
  --member="user:user@example.com" \
  --role="roles/run.invoker"
```

---

## 🔧 Environment Configuration

### Option A: Using Environment Variables

Set in deployment:

```bash
GCP_PROJECT_ID=your-project-id
DATASET_ID=amazon_ads_data
SECRET_ID=amazon-ads-credentials
```

### Option B: Using Config File

Deploy `ppc_config.yaml` with your settings:

```yaml
google_cloud:
  project_id: "your-project-id"
  secret_id: "amazon-ads-credentials"
  bigquery:
    dataset_id: "amazon_ads_data"
```

---

## 📊 Post-Deployment

### Verify Deployment

1. **Check Dashboard Loads**
   - Visit your deployment URL
   - Verify the dashboard interface appears

2. **Test BigQuery Connection**
   - Select "BigQuery" as data source
   - Enter your project ID
   - Verify data loads

3. **Check Logs**
   ```bash
   # Cloud Run
   gcloud run logs read amazon-ppc-dashboard --limit 50
   
   # App Engine
   gcloud app logs tail
   ```

### Monitor Usage

```bash
# Cloud Run metrics
gcloud run services describe amazon-ppc-dashboard --region us-central1

# Check costs
gcloud billing accounts list
```

---

## 🐛 Troubleshooting

### "Permission Denied" Errors

**Solution:**
```bash
# Verify service account has correct roles
gcloud projects get-iam-policy YOUR_PROJECT_ID \
  --flatten="bindings[].members" \
  --filter="bindings.members:dashboard-sa@*"
```

### "BigQuery Dataset Not Found"

**Solution:**
1. Verify dataset exists: `bq ls`
2. Check project ID is correct
3. Ensure service account has `bigquery.dataViewer` role

### Dashboard Shows "Sample Data"

**Solution:**
- Verify BigQuery connection in sidebar
- Check project ID and dataset ID are correct
- Ensure data was exported: run `python run_complete_pipeline.py`

### "Secret Not Found"

**Solution:**
```bash
# Verify secret exists
gcloud secrets describe amazon-ads-credentials

# Grant access to service account
gcloud secrets add-iam-policy-binding amazon-ads-credentials \
  --member="serviceAccount:dashboard-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

---

## 💰 Cost Estimation

### Cloud Run
- **Always-on (1 instance)**: ~$5-10/month
- **Auto-scaling**: $0.00002400 per request + $0.00001650 per GB-second
- **Free tier**: 2 million requests/month

### Streamlit Community Cloud
- **Free tier**: 1 app, public repos
- **Team plan**: $20/month/app, private repos

### App Engine
- **Standard**: ~$10-30/month for low traffic
- **Flexible**: ~$50-100/month for moderate traffic

---

## 📝 Deployment Checklist

- [ ] Google Cloud project created and billing enabled
- [ ] BigQuery dataset populated with data (`run_complete_pipeline.py`)
- [ ] Secret Manager configured with Amazon credentials
- [ ] Service account created with appropriate permissions
- [ ] `ppc_config.yaml` configured for production
- [ ] Deployment scripts tested locally
- [ ] Dashboard deployed to chosen platform
- [ ] Authentication configured (if required)
- [ ] DNS/custom domain configured (optional)
- [ ] Monitoring and alerts set up
- [ ] Cost budgets configured

---

## 🔄 CI/CD Setup

### Automatic Deployment with GitHub Actions

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Cloud Run

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - uses: google-github-actions/setup-gcloud@v0
        with:
          service_account_key: ${{ secrets.GCP_SA_KEY }}
          project_id: ${{ secrets.GCP_PROJECT_ID }}
      
      - name: Deploy to Cloud Run
        run: |
          gcloud run deploy amazon-ppc-dashboard \
            --source . \
            --platform managed \
            --region us-central1 \
            --allow-unauthenticated
```

---

## 🌐 Custom Domain

### Set up custom domain:

```bash
# Map domain to Cloud Run service
gcloud run domain-mappings create \
  --service amazon-ppc-dashboard \
  --domain dashboard.yourdomain.com \
  --region us-central1
```

Then add DNS records as instructed by gcloud.

---

## 📚 Additional Resources

- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Streamlit Deployment Guide](https://docs.streamlit.io/streamlit-community-cloud/get-started/deploy-an-app)
- [App Engine Documentation](https://cloud.google.com/appengine/docs)
- [BigQuery Authentication](https://cloud.google.com/bigquery/docs/authentication)

---

## ✅ Success Criteria

Your deployment is successful when:

1. ✅ Dashboard accessible via public URL
2. ✅ BigQuery data loads automatically
3. ✅ All visualizations render correctly
4. ✅ Metrics update when date range changed
5. ✅ Authentication working (if configured)
6. ✅ Logs show no errors
7. ✅ Costs within expected range

---

**Ready to deploy?** Choose your platform and follow the steps above. The dashboard code is production-ready and will automatically connect to your BigQuery data!

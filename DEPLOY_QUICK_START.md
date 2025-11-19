# Quick Deployment Guide

Deploy the Amazon PPC Dashboard to Google Cloud Run in **3 simple steps**.

## Prerequisites

- Google Cloud account with billing enabled
- `gcloud` CLI installed
- Data in BigQuery (run `./retrieve_and_display.sh` first)

## Step 1: Set Your Project ID

```bash
export GCP_PROJECT_ID="your-gcp-project-id"
```

## Step 2: Run Deployment Script

```bash
./deploy_cloudrun.sh $GCP_PROJECT_ID
```

This will:
- Enable required APIs
- Create service account with permissions
- Build Docker container
- Deploy to Cloud Run
- Return your dashboard URL

## Step 3: Access Your Dashboard

After deployment completes (3-5 minutes), you'll get a URL like:

```
https://amazon-ppc-dashboard-xxxxx-uc.a.run.app
```

Open this URL and:
1. Select "BigQuery" as data source
2. Enter your Project ID
3. Your live Amazon PPC data loads automatically!

## That's It! 🎉

Your dashboard is now:
- ✅ Publicly accessible (or configure auth if needed)
- ✅ Automatically connected to BigQuery
- ✅ Loading your real Amazon data
- ✅ Auto-scaling based on traffic
- ✅ Costing ~$5-10/month with always-on instance

## Update Deployment

To update with new changes:

```bash
./deploy_cloudrun.sh $GCP_PROJECT_ID
```

## View Logs

```bash
gcloud run logs read amazon-ppc-dashboard --region us-central1 --limit 50
```

## Configure Authentication (Optional)

To restrict access:

```bash
# Remove public access
gcloud run services remove-iam-policy-binding amazon-ppc-dashboard \
  --region=us-central1 \
  --member="allUsers" \
  --role="roles/run.invoker"

# Grant access to specific users
gcloud run services add-iam-policy-binding amazon-ppc-dashboard \
  --region=us-central1 \
  --member="user:your-email@example.com" \
  --role="roles/run.invoker"
```

## Troubleshooting

### Deployment fails
- Check billing is enabled: `gcloud billing accounts list`
- Verify project ID: `gcloud config get-value project`

### Dashboard shows no data
- Verify BigQuery has data: `bq query "SELECT COUNT(*) FROM \`PROJECT.amazon_ads_data.campaign_performance\`"`
- Run pipeline first: `python run_complete_pipeline.py`

### Permission errors
- Service account may need additional roles
- Check logs: `gcloud run logs read amazon-ppc-dashboard --limit 50`

---

For detailed deployment options, see [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)

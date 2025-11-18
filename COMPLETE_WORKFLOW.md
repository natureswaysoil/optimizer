# Complete Workflow: Google Secrets → Amazon Data → Dashboard

This guide shows you how to go from credentials in Google Secret Manager to viewing your real Amazon PPC data in the dashboard.

## 🚀 One-Command Solution

### Option 1: Shell Script (Easiest)

```bash
# Run everything with one command
./retrieve_and_display.sh
```

This single command:
1. ✅ Fetches credentials from Google Secret Manager
2. ✅ Connects to Amazon Ads API
3. ✅ Retrieves all your campaign data
4. ✅ Exports to BigQuery
5. ✅ Launches dashboard to display the data

### Option 2: Python Script

```bash
# Run the pipeline
python run_complete_pipeline.py

# Then launch dashboard separately
streamlit run dashboard.py
```

## 📋 Prerequisites

Before running, ensure you have:

1. **Credentials in Google Secret Manager**
   ```bash
   gcloud secrets describe amazon-ads-credentials
   ```

2. **Configuration file** with your settings
   ```bash
   # Copy example
   cp ppc_config.example.yaml ppc_config.yaml
   
   # Edit with your project_id and secret_id
   nano ppc_config.yaml
   ```

3. **Google Cloud authentication**
   ```bash
   gcloud auth application-default login
   ```

4. **Dependencies installed**
   ```bash
   pip install -r requirements.txt
   ```

## 🔧 Configuration

Edit `ppc_config.yaml`:

```yaml
# Minimal configuration needed
google_cloud:
  project_id: "your-gcp-project-id"        # Required
  secret_id: "amazon-ads-credentials"       # Required
  bigquery:
    dataset_id: "amazon_ads_data"           # Optional

# Features to run
features:
  enabled:
    - data_export  # This exports to BigQuery for dashboard
```

## 🎯 Step-by-Step Walkthrough

### Step 1: Verify Setup

Check that everything is configured:

```bash
# Verify config exists
cat ppc_config.yaml | grep project_id

# Verify secret exists
gcloud secrets describe amazon-ads-credentials

# Verify authentication
gcloud auth application-default print-access-token
```

### Step 2: Run the Pipeline

```bash
# Run with default config
python run_complete_pipeline.py

# Or with custom config
python run_complete_pipeline.py --config my_config.yaml

# Dry run first (recommended)
python run_complete_pipeline.py --dry-run
```

**What happens:**
```
================================================================================
COMPLETE AMAZON PPC PIPELINE
================================================================================
Started at: 2024-01-15T10:30:00

STEP 1: Validate Configuration
✅ Configuration valid
   Project ID: my-gcp-project
   Secret ID: amazon-ads-credentials

STEP 2: Initialize Automation
INFO - Google Secret Manager configured - fetching credentials...
INFO - ✅ Successfully fetched credentials from Secret Manager
INFO - ✅ Credentials loaded from Google Secret Manager
✅ Automation initialized successfully

STEP 3: Run Features
Running features: data_export
INFO - Starting data export to BigQuery...
INFO - ✅ Exported 150 campaigns
INFO - ✅ Exported 4,500 campaign performance records
INFO - ✅ Exported 12,000 keyword performance records
✅ SUCCESS: data_export

STEP 4: Results Summary
✅ SUCCESS: data_export
   campaigns_exported: 150
   campaign_performance_rows: 4500
   keyword_performance_rows: 12000

STEP 5: View Data in Dashboard
Your data is now in BigQuery!

To view in the dashboard:
1. Launch dashboard:
   streamlit run dashboard.py

2. In the dashboard sidebar:
   - Select 'BigQuery' as data source
   - Enter Project ID: my-gcp-project
   - Enter Dataset ID: amazon_ads_data

3. Your real Amazon PPC data will be displayed!

✅ PIPELINE COMPLETED SUCCESSFULLY
================================================================================
```

### Step 3: Launch Dashboard

```bash
streamlit run dashboard.py
```

The dashboard will open at `http://localhost:8501`

### Step 4: View Your Data

In the dashboard:

1. **Sidebar Configuration:**
   - Select "BigQuery" from the data source dropdown
   - Enter your GCP Project ID (e.g., `my-gcp-project`)
   - Enter Dataset ID (default: `amazon_ads_data`)

2. **Your Data Loads Automatically:**
   - Real campaign performance metrics
   - Actual spend and sales data
   - Live keyword performance
   - Budget utilization

3. **Explore the Dashboards:**
   - **KPIs**: Total spend, sales, ACOS, ROAS
   - **Trends**: Performance over time
   - **Campaigns**: Compare campaign performance
   - **Budget**: Monitor budget utilization
   - **Keywords**: Analyze keyword performance

## 🔄 Automated Workflow

For daily updates, set up a cron job:

```bash
# Edit crontab
crontab -e

# Add this line to run daily at 2 AM
0 2 * * * cd /path/to/optimizer && python run_complete_pipeline.py >> /var/log/amazon-ppc.log 2>&1
```

This will:
- Fetch fresh credentials daily
- Pull latest data from Amazon
- Update BigQuery tables
- Dashboard always shows current data

## 📊 What Data is Retrieved

The pipeline fetches:

### Campaign Budgets
- Campaign names and IDs
- Daily budget amounts
- Campaign states (enabled/paused)
- Targeting types

### Campaign Performance (Last 30 Days)
- Daily impressions and clicks
- Spend and sales
- Conversions
- Calculated: CTR, CPC, ACOS, ROAS

### Keyword Performance (Last 7 Days)
- Keyword text and match types
- Impressions, clicks, spend
- Sales and conversions
- Performance by keyword

## 🎨 Dashboard Features

Once data is loaded, you can:

### View KPIs
- Total spend and sales
- Overall ACOS and ROAS
- Click-through rates
- Conversion metrics

### Analyze Trends
- Spend vs. sales over time
- ACOS trends with targets
- Click and impression volumes
- ROAS performance

### Compare Campaigns
- Side-by-side campaign metrics
- Budget utilization
- Performance rankings
- Efficiency comparisons

### Optimize Keywords
- Top performing keywords
- ACOS by keyword
- Match type analysis
- Bid optimization insights

### Monitor Budgets
- Budget vs. actual spend
- Utilization percentages
- Over/under budget alerts
- Recommendations

## 🛠️ Advanced Usage

### Run Specific Features

```bash
# Only export data
python run_complete_pipeline.py --features data_export

# Export and optimize bids
python run_complete_pipeline.py --features data_export bid_optimization

# Run all features
python run_complete_pipeline.py --features data_export bid_optimization dayparting campaign_management
```

### Use Different Profiles

```bash
# Specify profile ID explicitly
python run_complete_pipeline.py --profile-id 1780498399290938
```

### Custom Configuration

```bash
# Use different config file
python run_complete_pipeline.py --config production_config.yaml
```

## 🐛 Troubleshooting

### "Configuration file not found"

**Solution:**
```bash
cp ppc_config.example.yaml ppc_config.yaml
# Edit ppc_config.yaml with your settings
```

### "Failed to fetch credentials from Secret Manager"

**Solution:**
```bash
# Check authentication
gcloud auth application-default login

# Verify secret exists
gcloud secrets describe amazon-ads-credentials

# Check IAM permissions
gcloud secrets add-iam-policy-binding amazon-ads-credentials \
  --member="user:$(gcloud config get-value account)" \
  --role="roles/secretmanager.secretAccessor"
```

### "Authentication failed"

**Solution:**
```bash
# View the secret to verify credentials are correct
gcloud secrets versions access latest --secret=amazon-ads-credentials

# Ensure it has all required keys:
# - AMAZON_CLIENT_ID
# - AMAZON_CLIENT_SECRET
# - AMAZON_REFRESH_TOKEN
# - AMAZON_PROFILE_ID
```

### "No data in dashboard"

**Solution:**
```bash
# Verify data was exported
bq query --use_legacy_sql=false \
  'SELECT COUNT(*) FROM `your-project.amazon_ads_data.campaign_performance`'

# Re-run the pipeline
python run_complete_pipeline.py

# Clear dashboard cache
streamlit cache clear
```

### "Dashboard shows sample data"

**Solution:**
Make sure you:
1. Selected "BigQuery" (not "Sample Data") in sidebar
2. Entered correct Project ID
3. Data export completed successfully

## 📈 Data Refresh Schedule

### Manual Refresh
```bash
# Run anytime to update data
python run_complete_pipeline.py
```

### Hourly Refresh
```bash
# Add to crontab
0 * * * * cd /path/to/optimizer && python run_complete_pipeline.py
```

### Daily Refresh (Recommended)
```bash
# Add to crontab - runs at 2 AM daily
0 2 * * * cd /path/to/optimizer && python run_complete_pipeline.py
```

## 🎯 Quick Reference

| Command | Purpose |
|---------|---------|
| `./retrieve_and_display.sh` | One command to do everything |
| `python run_complete_pipeline.py` | Fetch data and export to BigQuery |
| `streamlit run dashboard.py` | Launch dashboard |
| `python run_complete_pipeline.py --dry-run` | Test without changes |
| `python run_complete_pipeline.py --features data_export` | Only export data |

## 📝 Summary

**Before:** Manual credential management, separate scripts, complex setup

**After:** One command retrieves data from Amazon and displays in dashboard!

```bash
# That's literally it
./retrieve_and_display.sh
```

Your Amazon PPC data flows from:
1. **Google Secret Manager** (secure credentials) →
2. **Amazon Ads API** (fetch data) →
3. **BigQuery** (store data) →
4. **Streamlit Dashboard** (visualize data)

All automated, all secure, all in one command! 🎉

---

**Need help?** Check the other guides:
- [AUTOMATIC_CREDENTIALS.md](AUTOMATIC_CREDENTIALS.md) - Credential setup
- [GOOGLE_SECRETS_SETUP.md](GOOGLE_SECRETS_SETUP.md) - Secret Manager details
- [QUICK_START_SECRETS.md](QUICK_START_SECRETS.md) - 5-minute setup
- [README.md](README.md) - Full documentation

# Amazon PPC Optimizer - Usage Guide

## Quick Start Guide

### Step 1: Install Dependencies

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install required packages
pip install -r requirements.txt
```

### Step 2: Configure Credentials

Create a `.env` file or export environment variables:

```bash
# Amazon Advertising API Credentials
export AMAZON_CLIENT_ID="amzn1.application-oa2-client.xxxxx"
export AMAZON_CLIENT_SECRET="your_client_secret"
export AMAZON_REFRESH_TOKEN="Atzr|IwEBxxxxxxxx"
export AMAZON_PROFILE_ID="1780498399290938"
```

### Step 3: Test Connection

```bash
python optimizer_core.py --config ppc_config.yaml \
  --profile-id YOUR_PROFILE_ID \
  --verify-connection
```

### Step 4: Launch Dashboard

```bash
# Option 1: Use the startup script
./run_dashboard.sh

# Option 2: Run directly
streamlit run dashboard.py
```

## Complete Workflow

### Workflow 1: View Sample Data Dashboard

**Goal**: Explore the dashboard interface with demo data

```bash
# 1. Launch dashboard
streamlit run dashboard.py

# 2. In the sidebar, select "Sample Data (Demo)"
# 3. Explore the different sections
```

**What you'll see**:
- 5 sample campaigns with 30 days of data
- Performance trends and visualizations
- Budget utilization analysis
- Keyword performance metrics

### Workflow 2: Export Data to BigQuery

**Goal**: Extract your Amazon PPC data and load it into BigQuery for analysis

**Prerequisites**:
- Google Cloud Platform account
- BigQuery API enabled
- Service account with BigQuery permissions

**Steps**:

```bash
# 1. Set up Google Cloud authentication
gcloud auth application-default login

# 2. Create BigQuery dataset
bq mk --dataset --location=US your-project-id:amazon_ads_data

# 3. Configure ppc_config.yaml
# Edit the file and add:
#   google_cloud:
#     project_id: "your-project-id"
#     bigquery:
#       dataset_id: "amazon_ads_data"
#   features:
#     enabled:
#       - data_export

# 4. Run data export
python optimizer_core.py \
  --config ppc_config.yaml \
  --profile-id YOUR_PROFILE_ID \
  --features data_export

# 5. Verify data in BigQuery
bq query --use_legacy_sql=false \
  'SELECT COUNT(*) as row_count FROM `your-project-id.amazon_ads_data.campaign_performance`'
```

**Expected Output**:
```
✓ Fetch Campaign Budgets completed in 2.34s
✓ Parallel Report Processing completed in 45.67s
Loaded 150 rows into amazon_ads_data.campaign_budgets.
Loaded 450 rows into amazon_ads_data.campaign_performance.
Loaded 1200 rows into amazon_ads_data.keyword_performance.
✓ Data Export to BigQuery completed in 48.12s
```

### Workflow 3: View Live Data in Dashboard

**Goal**: Visualize your BigQuery data in the dashboard

```bash
# 1. Launch dashboard
streamlit run dashboard.py

# 2. In the sidebar:
#    - Select "BigQuery" as data source
#    - Enter Project ID: your-project-id
#    - Enter Dataset ID: amazon_ads_data

# 3. Select date range (default: last 7 days)

# 4. Explore your live data!
```

### Workflow 4: Run Bid Optimization

**Goal**: Automatically adjust keyword bids based on performance

**Steps**:

```bash
# 1. Configure bid optimization settings in ppc_config.yaml
#    bid_optimization:
#      enabled: true
#      target_acos: 0.30  # 30% target ACOS
#      min_impressions: 100
#      max_bid_increase_percent: 20
#      max_bid_decrease_percent: 50

# 2. Run bid optimization (dry-run first!)
python optimizer_core.py \
  --config ppc_config.yaml \
  --profile-id YOUR_PROFILE_ID \
  --features bid_optimization \
  --dry-run

# 3. Review the audit log
cat logs/ppc_audit_*.csv

# 4. If satisfied, run without dry-run
python optimizer_core.py \
  --config ppc_config.yaml \
  --profile-id YOUR_PROFILE_ID \
  --features bid_optimization
```

**Expected Output**:
```
✓ Bid Optimization completed in 12.45s
Keywords optimized: 45
Keywords updated: 45
Average ACOS: 28.5%
```

### Workflow 5: Dayparting (Time-Based Bid Adjustments)

**Goal**: Adjust bids based on time of day and day of week

```bash
# 1. Configure dayparting in ppc_config.yaml
#    dayparting:
#      enabled: true
#      timezone: "America/Los_Angeles"
#      schedule:
#        monday:
#          - {start: 6, end: 22, multiplier: 1.0}

# 2. Run dayparting
python optimizer_core.py \
  --config ppc_config.yaml \
  --profile-id YOUR_PROFILE_ID \
  --features dayparting \
  --dry-run

# 3. Check audit log for bid changes
grep "DAYPARTING" logs/ppc_audit_*.csv
```

### Workflow 6: Campaign Management

**Goal**: Automatically pause/activate campaigns based on ACOS

```bash
# 1. Configure campaign management
#    campaign_management:
#      enabled: true
#      acos_threshold: 0.45  # 45% ACOS threshold
#      min_spend: 20.0       # Minimum $20 spend

# 2. Run campaign management
python optimizer_core.py \
  --config ppc_config.yaml \
  --profile-id YOUR_PROFILE_ID \
  --features campaign_management \
  --dry-run

# 3. Review changes
grep "CAMPAIGN_STATE" logs/ppc_audit_*.csv
```

### Workflow 7: Keyword Discovery

**Goal**: Discover and add new high-performing keywords

```bash
# 1. Configure keyword discovery
#    keyword_discovery:
#      enabled: true
#      min_search_volume: 100
#      max_keywords_per_ad_group: 50

# 2. Run keyword discovery
python optimizer_core.py \
  --config ppc_config.yaml \
  --profile-id YOUR_PROFILE_ID \
  --features keyword_discovery \
  --dry-run

# 3. Review suggested keywords
grep "KEYWORD_ADDED" logs/ppc_audit_*.csv
```

### Workflow 8: Negative Keyword Management

**Goal**: Identify and add negative keywords to prevent wasted spend

```bash
# 1. Configure negative keywords
#    negative_keywords:
#      enabled: true
#      min_spend_threshold: 10.0
#      max_acos_threshold: 0.60

# 2. Run negative keyword analysis
python optimizer_core.py \
  --config ppc_config.yaml \
  --profile-id YOUR_PROFILE_ID \
  --features negative_keywords \
  --dry-run

# 3. Review negative keywords
grep "NEGATIVE_KEYWORD" logs/ppc_audit_*.csv
```

### Workflow 9: Full Automation Suite

**Goal**: Run all enabled features in one command

```bash
# 1. Configure all desired features in ppc_config.yaml
#    features:
#      enabled:
#        - bid_optimization
#        - dayparting
#        - campaign_management
#        - keyword_discovery
#        - negative_keywords
#        - data_export

# 2. Run full automation
python optimizer_core.py \
  --config ppc_config.yaml \
  --profile-id YOUR_PROFILE_ID

# 3. Check summary in logs
tail -50 ppc_automation_*.log
```

### Workflow 10: Scheduled Automation with Cron

**Goal**: Run automation daily at specific times

```bash
# 1. Create a shell script: run_automation.sh
cat > run_automation.sh << 'EOF'
#!/bin/bash
cd /path/to/optimizer
source venv/bin/activate
export AMAZON_CLIENT_ID="..."
export AMAZON_CLIENT_SECRET="..."
export AMAZON_REFRESH_TOKEN="..."
export AMAZON_PROFILE_ID="..."

python optimizer_core.py \
  --config ppc_config.yaml \
  --profile-id $AMAZON_PROFILE_ID \
  --features data_export bid_optimization
EOF

chmod +x run_automation.sh

# 2. Add to crontab
crontab -e

# 3. Add this line (runs daily at 2 AM):
0 2 * * * /path/to/run_automation.sh >> /path/to/logs/cron.log 2>&1

# 4. Verify cron job
crontab -l
```

## Troubleshooting

### Issue: "Authentication Failed"

**Solution**:
```bash
# Verify credentials
echo $AMAZON_CLIENT_ID
echo $AMAZON_PROFILE_ID

# Test connection
python optimizer_core.py \
  --config ppc_config.yaml \
  --profile-id YOUR_PROFILE_ID \
  --verify-connection
```

### Issue: "BigQuery Permission Denied"

**Solution**:
```bash
# Check authentication
gcloud auth application-default login

# Verify service account has permissions
gcloud projects get-iam-policy YOUR_PROJECT_ID
```

### Issue: "Dashboard Shows No Data"

**Solution**:
```bash
# 1. Check if data export ran successfully
bq query --use_legacy_sql=false \
  'SELECT * FROM `your-project-id.amazon_ads_data.campaign_performance` LIMIT 10'

# 2. Re-run data export
python optimizer_core.py \
  --config ppc_config.yaml \
  --profile-id YOUR_PROFILE_ID \
  --features data_export

# 3. Clear Streamlit cache
streamlit cache clear
```

### Issue: "Rate Limit Exceeded"

**Solution**:
```bash
# Reduce API request rate in ppc_config.yaml
api:
  max_requests_per_second: 5  # Reduce from 10 to 5

# Or add delay between operations
time.sleep(2)  # Add 2-second delay
```

## Best Practices

### 1. Always Test with Dry-Run First
```bash
python optimizer_core.py \
  --config ppc_config.yaml \
  --profile-id YOUR_PROFILE_ID \
  --dry-run
```

### 2. Monitor Audit Logs
```bash
# Review all bid changes
grep "BID_UPDATE" logs/ppc_audit_*.csv | less
```

### 3. Start with Conservative Settings
```yaml
bid_optimization:
  max_bid_increase_percent: 10  # Start small
  max_bid_decrease_percent: 20
```

### 4. Run Data Export Daily
```bash
# Schedule daily at 1 AM
0 1 * * * /path/to/run_data_export.sh
```

### 5. Review Dashboard Weekly
- Check campaign performance trends
- Identify budget opportunities
- Analyze keyword performance
- Adjust targeting strategies

## Advanced Tips

### Custom Date Ranges
```python
# In dashboard.py, modify generate_sample_data():
dates = pd.date_range(end=datetime.now().date(), periods=90)  # 90 days
```

### Export Dashboard Data
```python
# Add to dashboard.py:
if st.button("Download CSV"):
    campaign_performance.to_csv("campaign_data.csv")
```

### Multiple Profiles
```bash
# Run for multiple profiles in sequence
for profile in 123 456 789; do
  python optimizer_core.py \
    --config ppc_config.yaml \
    --profile-id $profile \
    --features data_export
done
```

---

## Support

For additional help:
1. Check the README.md for detailed documentation
2. Review logs in the `logs/` directory
3. Consult Amazon Advertising API documentation
4. Open an issue on GitHub

**Happy Optimizing! 🚀**

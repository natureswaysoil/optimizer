# Quick Start: Google Secret Manager → Amazon Data → Dashboard

This is a fast-track guide to get from Google Secret Manager to viewing your Amazon PPC data in the dashboard.

## 5-Minute Setup

### Step 1: Store Credentials in Secret Manager (1 min)

```bash
# Create credentials file
cat > /tmp/creds.json << 'EOF'
{
  "AMAZON_CLIENT_ID": "amzn1.application-oa2-client.YOUR_ID",
  "AMAZON_CLIENT_SECRET": "YOUR_SECRET",
  "AMAZON_REFRESH_TOKEN": "Atzr|IwEBYOUR_TOKEN",
  "AMAZON_PROFILE_ID": "YOUR_PROFILE_ID"
}
EOF

# Store in Secret Manager
gcloud secrets create amazon-ads-credentials \
  --data-file=/tmp/creds.json \
  --replication-policy="automatic"

# Clean up
rm /tmp/creds.json
```

### Step 2: Test Connection (30 sec)

```bash
export GCP_PROJECT_ID="your-gcp-project-id"
python fetch_and_connect.py
```

**Expected output:**
```
✅ Credentials fetched successfully
✅ Authentication successful!
✅ Successfully retrieved X campaigns

Your campaigns:
1. Campaign Name Here
   ID: 123456789
   State: enabled
   Daily Budget: $50.00
   ...
```

### Step 3: Export Data to BigQuery (2 min)

Edit `ppc_config.yaml`:
```yaml
google_cloud:
  project_id: "your-gcp-project-id"
  secret_id: "amazon-ads-credentials"
  bigquery:
    dataset_id: "amazon_ads_data"
```

Run export:
```bash
python optimizer_core.py --config ppc_config.yaml \
  --profile-id YOUR_PROFILE_ID --features data_export
```

### Step 4: View in Dashboard (30 sec)

```bash
streamlit run dashboard.py
```

In the browser:
1. Select "BigQuery" from sidebar
2. Enter Project ID: `your-gcp-project-id`
3. Enter Dataset ID: `amazon_ads_data`
4. View your real data! 📊

## Troubleshooting

### "Permission denied"
```bash
gcloud secrets add-iam-policy-binding amazon-ads-credentials \
  --member="user:$(gcloud config get-value account)" \
  --role="roles/secretmanager.secretAccessor"
```

### "Secret not found"
```bash
gcloud secrets list
# Verify the secret exists
```

### "Authentication failed"
```bash
gcloud auth application-default login
# Re-authenticate
```

### "Invalid JSON"
Check your secret format:
```bash
gcloud secrets versions access latest --secret="amazon-ads-credentials"
# Must be valid JSON with all 4 required keys
```

## What Each Command Does

| Command | What It Does |
|---------|-------------|
| `gcloud secrets create` | Stores your credentials securely in Google Cloud |
| `fetch_and_connect.py` | Fetches credentials and connects to Amazon to verify |
| `optimizer_core.py --features data_export` | Exports your Amazon data to BigQuery tables |
| `streamlit run dashboard.py` | Launches the interactive web dashboard |

## Next Steps

Once you have data flowing:

1. **Automate daily exports** (cron job):
   ```bash
   # Add to crontab
   0 2 * * * cd /path/to/optimizer && python optimizer_core.py \
     --config ppc_config.yaml --profile-id YOUR_PROFILE_ID \
     --features data_export >> /var/log/amazon-export.log 2>&1
   ```

2. **Run optimizations**:
   ```bash
   python optimizer_core.py --config ppc_config.yaml \
     --profile-id YOUR_PROFILE_ID --features bid_optimization
   ```

3. **Share dashboard** (deploy to Cloud Run, App Engine, etc.)

## Files Reference

- `fetch_and_connect.py` - Fetch credentials & test connection
- `optimizer_core.py` - Main automation & data export
- `dashboard.py` - Interactive Streamlit dashboard
- `ppc_config.yaml` - Configuration file
- `GOOGLE_SECRETS_SETUP.md` - Detailed setup guide (read this for full details)

## Security Note

✅ **Secure**: Credentials never stored in code or files  
✅ **Auditable**: All access logged by Google Cloud  
✅ **Encrypted**: Data encrypted at rest and in transit  

Never commit credentials to Git! Secret Manager keeps them safe.

---

**Need more help?** See [GOOGLE_SECRETS_SETUP.md](GOOGLE_SECRETS_SETUP.md) for the complete guide.

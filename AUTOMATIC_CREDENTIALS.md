# Automatic Credential Fetching from Google Secret Manager

The optimizer now **automatically fetches** your Amazon Ads credentials from Google Secret Manager when you configure `ppc_config.yaml`. No need to set environment variables or run separate scripts!

## How It Works

1. You configure your GCP project and secret name in `ppc_config.yaml`
2. The optimizer automatically fetches credentials when it starts
3. Credentials are used to authenticate with Amazon Ads API
4. Everything happens seamlessly - no manual steps needed!

## Quick Setup (3 Steps)

### Step 1: Store Credentials in Secret Manager

```bash
# Create the credentials JSON
cat > /tmp/amazon-creds.json << 'EOF'
{
  "AMAZON_CLIENT_ID": "amzn1.application-oa2-client.xxxxx",
  "AMAZON_CLIENT_SECRET": "your_secret",
  "AMAZON_REFRESH_TOKEN": "Atzr|IwEBxxxxxxxx",
  "AMAZON_PROFILE_ID": "1780498399290938"
}
EOF

# Store in Secret Manager
gcloud secrets create amazon-ads-credentials \
  --data-file=/tmp/amazon-creds.json \
  --replication-policy="automatic"

# Clean up
rm /tmp/amazon-creds.json
```

### Step 2: Configure ppc_config.yaml

Edit `ppc_config.yaml` and update these two lines:

```yaml
google_cloud:
  project_id: "your-actual-gcp-project-id"  # ← Update this
  secret_id: "amazon-ads-credentials"        # ← Update if you used a different name
```

That's it! The optimizer will automatically fetch credentials.

### Step 3: Run the Optimizer

```bash
# No environment variables needed!
python optimizer_core.py --config ppc_config.yaml \
  --profile-id YOUR_PROFILE_ID --features data_export
```

**What happens:**
1. ✅ Optimizer loads `ppc_config.yaml`
2. ✅ Sees Google Cloud configuration
3. ✅ Automatically fetches credentials from Secret Manager
4. ✅ Authenticates with Amazon Ads API
5. ✅ Runs your requested features

## Complete Example

### Before (Manual Method) ❌
```bash
# You had to manually set these every time
export AMAZON_CLIENT_ID="amzn1.application-oa2-client.xxxxx"
export AMAZON_CLIENT_SECRET="your_secret"
export AMAZON_REFRESH_TOKEN="Atzr|IwEBxxxxxxxx"
export AMAZON_PROFILE_ID="1780498399290938"

# Then run
python optimizer_core.py --config ppc_config.yaml --profile-id $AMAZON_PROFILE_ID
```

### After (Automatic Method) ✅
```bash
# Just run - credentials fetched automatically!
python optimizer_core.py --config ppc_config.yaml --profile-id YOUR_PROFILE_ID
```

## Configuration File Example

Here's a complete `ppc_config.yaml` with Secret Manager configured:

```yaml
# API Settings
api:
  region: "NA"
  max_requests_per_second: 10

# Google Cloud Integration - Credentials fetched automatically!
google_cloud:
  project_id: "my-gcp-project-123"         # Your GCP project
  secret_id: "amazon-ads-credentials"       # Your secret name
  bigquery:
    dataset_id: "amazon_ads_data"

# Features to run
features:
  enabled:
    - data_export
    - bid_optimization
```

## What You'll See in the Logs

When the optimizer starts with Secret Manager configured:

```
INFO - Configuration loaded from ppc_config.yaml
INFO - Google Secret Manager configured - fetching credentials...
INFO - Fetching credentials from Google Secret Manager...
INFO -   Project: my-gcp-project-123
INFO -   Secret: amazon-ads-credentials
INFO - ✅ Successfully fetched credentials from Secret Manager
INFO - ✅ Credentials loaded from Google Secret Manager
INFO - Successfully authenticated with Amazon Ads API
```

## Fallback Behavior

If Secret Manager fails, the optimizer automatically falls back to environment variables:

```
INFO - Google Secret Manager configured - fetching credentials...
ERROR - Failed to load credentials from Secret Manager: [error details]
INFO - Falling back to environment variables...
```

This ensures the optimizer always works, even if:
- Secret Manager is temporarily unavailable
- Credentials are not in Secret Manager yet
- You prefer to use environment variables

## Testing the Configuration

Use the provided test script to verify everything is set up correctly:

```bash
python test_secret_manager_integration.py
```

Expected output:
```
✅ INTEGRATION COMPLETE
✅ PASS: Configuration Parsing
✅ PASS: Secret Manager Function  
✅ PASS: PPCAutomation Integration
✅ PASS: Secret Manager Library
```

## Troubleshooting

### "Failed to fetch credentials from Secret Manager"

**Check authentication:**
```bash
gcloud auth application-default login
```

**Verify secret exists:**
```bash
gcloud secrets describe amazon-ads-credentials
```

**Check IAM permissions:**
```bash
gcloud secrets add-iam-policy-binding amazon-ads-credentials \
  --member="user:$(gcloud config get-value account)" \
  --role="roles/secretmanager.secretAccessor"
```

### "Secret is not valid JSON"

Check the secret format:
```bash
gcloud secrets versions access latest --secret="amazon-ads-credentials"
```

Must be valid JSON with these exact keys:
- `AMAZON_CLIENT_ID`
- `AMAZON_CLIENT_SECRET`
- `AMAZON_REFRESH_TOKEN`
- `AMAZON_PROFILE_ID`

### "google-cloud-secret-manager not installed"

Install the library:
```bash
pip install google-cloud-secret-manager
```

Or install all requirements:
```bash
pip install -r requirements.txt
```

## Updating Credentials

To update credentials in Secret Manager:

```bash
# Create new credentials JSON
cat > /tmp/new-creds.json << 'EOF'
{
  "AMAZON_CLIENT_ID": "amzn1.application-oa2-client.xxxxx",
  "AMAZON_CLIENT_SECRET": "your_new_secret",
  "AMAZON_REFRESH_TOKEN": "Atzr|IwEBnew_token",
  "AMAZON_PROFILE_ID": "1780498399290938"
}
EOF

# Add new version (keeps history)
gcloud secrets versions add amazon-ads-credentials \
  --data-file=/tmp/new-creds.json

# Clean up
rm /tmp/new-creds.json
```

The optimizer automatically uses the latest version!

## Advanced: Multiple Profiles

You can store credentials for multiple profiles in Secret Manager:

```bash
# Store different profiles with different secret names
gcloud secrets create amazon-ads-profile-1 --data-file=profile1.json
gcloud secrets create amazon-ads-profile-2 --data-file=profile2.json
```

Then use different config files:

```bash
# ppc_config_profile1.yaml
google_cloud:
  project_id: "my-project"
  secret_id: "amazon-ads-profile-1"

# ppc_config_profile2.yaml  
google_cloud:
  project_id: "my-project"
  secret_id: "amazon-ads-profile-2"
```

Run with different configs:
```bash
python optimizer_core.py --config ppc_config_profile1.yaml --profile-id PROFILE_1
python optimizer_core.py --config ppc_config_profile2.yaml --profile-id PROFILE_2
```

## Security Benefits

✅ **No credentials in code or files**  
✅ **No environment variables to manage**  
✅ **Credentials encrypted at rest**  
✅ **All access logged in Cloud Audit Logs**  
✅ **IAM-based access control**  
✅ **Automatic credential rotation support**  

## Cost

Google Secret Manager pricing:
- **$0.06 per 10,000 access operations**
- **$0.03 per active secret version per month**

For typical usage (1 secret, running optimizer a few times per day):
- **~$0.05/month** - essentially free!

## Summary

**Before this feature:**
- Manual credential management
- Set environment variables every time
- Risk of credentials in files/history

**After this feature:**
- Automatic credential fetching
- Just configure once in ppc_config.yaml
- Secure, auditable, encrypted

**Just configure `ppc_config.yaml` and run - everything else is automatic!** 🎉

---

For detailed Secret Manager setup, see [GOOGLE_SECRETS_SETUP.md](GOOGLE_SECRETS_SETUP.md)

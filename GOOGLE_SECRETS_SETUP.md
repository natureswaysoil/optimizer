# Using Google Secret Manager for Amazon Ads Credentials

This guide shows you how to securely store your Amazon Advertising API credentials in Google Secret Manager and use them with the optimizer.

## Why Use Google Secret Manager?

- **Security**: Credentials are encrypted and access-controlled
- **Audit Trail**: All access to secrets is logged
- **Centralized**: Manage all credentials in one place
- **Version Control**: Track changes to credentials over time
- **No Local Files**: No need to store sensitive data in `.env` files

## Prerequisites

1. Google Cloud Platform account
2. `gcloud` CLI installed and configured
3. Secret Manager API enabled in your GCP project
4. Appropriate IAM permissions

## Setup Instructions

### Step 1: Install Google Cloud SDK

If you haven't already:

```bash
# Install gcloud CLI
# Visit: https://cloud.google.com/sdk/docs/install

# Authenticate
gcloud auth login
gcloud auth application-default login

# Set your project
gcloud config set project YOUR_PROJECT_ID
```

### Step 2: Enable Secret Manager API

```bash
# Enable the API
gcloud services enable secretmanager.googleapis.com

# Verify it's enabled
gcloud services list --enabled | grep secretmanager
```

### Step 3: Create the Secret

Create a JSON file with your Amazon Ads credentials:

```bash
# Create credentials JSON
cat > amazon-creds.json << 'EOF'
{
  "AMAZON_CLIENT_ID": "amzn1.application-oa2-client.xxxxx",
  "AMAZON_CLIENT_SECRET": "your_client_secret_here",
  "AMAZON_REFRESH_TOKEN": "Atzr|IwEBxxxxxxxx",
  "AMAZON_PROFILE_ID": "1780498399290938"
}
EOF
```

**Important**: Replace the values above with your actual credentials!

### Step 4: Store in Secret Manager

```bash
# Create the secret
gcloud secrets create amazon-ads-credentials \
  --data-file=amazon-creds.json \
  --replication-policy="automatic"

# Verify it was created
gcloud secrets list

# Delete the local file (for security)
rm amazon-creds.json
```

### Step 5: Grant Access (if needed)

If you're using a service account:

```bash
# Grant access to your service account
gcloud secrets add-iam-policy-binding amazon-ads-credentials \
  --member="serviceAccount:YOUR_SERVICE_ACCOUNT@YOUR_PROJECT.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

For your user account:

```bash
# Grant access to yourself
gcloud secrets add-iam-policy-binding amazon-ads-credentials \
  --member="user:your-email@example.com" \
  --role="roles/secretmanager.secretAccessor"
```

## Using the Credentials

### Method 1: Standalone Script (Recommended for Testing)

Use the provided `fetch_and_connect.py` script:

```bash
# Install dependencies
pip install google-cloud-secret-manager

# Set your project ID
export GCP_PROJECT_ID="your-project-id"

# Run the script
python fetch_and_connect.py

# Or with custom secret name
python fetch_and_connect.py --secret-name my-amazon-creds

# Export campaign data to JSON
python fetch_and_connect.py --export campaigns.json
```

The script will:
1. Fetch credentials from Secret Manager
2. Authenticate with Amazon Ads API
3. Retrieve your campaigns
4. Display them on screen
5. Optionally export to JSON file

### Method 2: Integrated with optimizer_core.py

The optimizer already supports Google Secret Manager! Just configure it:

1. **Edit `ppc_config.yaml`**:

```yaml
google_cloud:
  project_id: "your-project-id"
  secret_id: "amazon-ads-credentials"
  bigquery:
    dataset_id: "amazon_ads_data"
```

2. **Run the optimizer**:

```bash
# The optimizer will automatically fetch credentials from Secret Manager
python optimizer_core.py \
  --config ppc_config.yaml \
  --profile-id YOUR_PROFILE_ID \
  --features data_export
```

The optimizer checks for credentials in this order:
1. Environment variables (`AMAZON_CLIENT_ID`, etc.)
2. Google Secret Manager (if configured)
3. Fails if neither is available

### Method 3: Manual Fetch and Export

Fetch credentials and set them as environment variables:

```bash
# Fetch the secret
SECRET_JSON=$(gcloud secrets versions access latest \
  --secret="amazon-ads-credentials" \
  --format='get(payload.data)' | base64 -d)

# Export as environment variables
export AMAZON_CLIENT_ID=$(echo $SECRET_JSON | jq -r '.AMAZON_CLIENT_ID')
export AMAZON_CLIENT_SECRET=$(echo $SECRET_JSON | jq -r '.AMAZON_CLIENT_SECRET')
export AMAZON_REFRESH_TOKEN=$(echo $SECRET_JSON | jq -r '.AMAZON_REFRESH_TOKEN')
export AMAZON_PROFILE_ID=$(echo $SECRET_JSON | jq -r '.AMAZON_PROFILE_ID')

# Now run any script
python optimizer_core.py --config ppc_config.yaml \
  --profile-id $AMAZON_PROFILE_ID --features data_export
```

## Complete Workflow: From Secret Manager to Dashboard

Here's the full workflow to go from credentials in Secret Manager to viewing data in the dashboard:

```bash
# 1. Set your project
export GCP_PROJECT_ID="your-project-id"

# 2. Test the connection (optional but recommended)
python fetch_and_connect.py

# 3. Configure ppc_config.yaml with your project_id and secret_id

# 4. Export data to BigQuery
python optimizer_core.py \
  --config ppc_config.yaml \
  --profile-id YOUR_PROFILE_ID \
  --features data_export

# 5. Launch the dashboard
streamlit run dashboard.py

# 6. In the dashboard:
#    - Select "BigQuery" as data source
#    - Enter your GCP Project ID
#    - View your real Amazon PPC data!
```

## Updating Credentials

If your Amazon credentials change (e.g., token refresh):

```bash
# Create new credentials JSON
cat > new-creds.json << 'EOF'
{
  "AMAZON_CLIENT_ID": "amzn1.application-oa2-client.xxxxx",
  "AMAZON_CLIENT_SECRET": "your_new_secret",
  "AMAZON_REFRESH_TOKEN": "Atzr|IwEBnew_token",
  "AMAZON_PROFILE_ID": "1780498399290938"
}
EOF

# Add a new version to the secret
gcloud secrets versions add amazon-ads-credentials \
  --data-file=new-creds.json

# The latest version is automatically used
# Clean up
rm new-creds.json
```

## Troubleshooting

### Error: "Permission denied"

**Solution**: Grant yourself access:
```bash
gcloud secrets add-iam-policy-binding amazon-ads-credentials \
  --member="user:$(gcloud config get-value account)" \
  --role="roles/secretmanager.secretAccessor"
```

### Error: "Secret not found"

**Solution**: Verify the secret exists and you're using the correct name:
```bash
gcloud secrets list
gcloud secrets describe amazon-ads-credentials
```

### Error: "Authentication failed"

**Solution**: Ensure you're authenticated with gcloud:
```bash
gcloud auth application-default login
gcloud auth list
```

### Error: "Invalid JSON in secret"

**Solution**: Check the secret format:
```bash
gcloud secrets versions access latest --secret="amazon-ads-credentials"
```

The JSON must have exactly these keys:
- `AMAZON_CLIENT_ID`
- `AMAZON_CLIENT_SECRET`
- `AMAZON_REFRESH_TOKEN`
- `AMAZON_PROFILE_ID`

### Error: "Module 'google.cloud.secretmanager' not found"

**Solution**: Install the library:
```bash
pip install google-cloud-secret-manager
```

## Security Best Practices

1. **Never commit credentials to Git**
   - The `.gitignore` already excludes credential files
   - Always use Secret Manager for production

2. **Use service accounts in production**
   - Create a dedicated service account
   - Grant only necessary permissions
   - Use workload identity for GKE/Cloud Run

3. **Rotate credentials regularly**
   - Add new versions to Secret Manager
   - Update periodically (e.g., every 90 days)

4. **Monitor access**
   - Check audit logs regularly
   - Set up alerts for unusual access patterns

5. **Limit IAM permissions**
   - Only grant `secretAccessor` role
   - Use least privilege principle

## Cost

Google Secret Manager pricing (as of 2024):
- $0.06 per 10,000 access operations
- $0.03 per active secret version per month

For this use case (1 secret, occasional access), cost is typically **under $1/month**.

## Alternative: Using .env File (Not Recommended for Production)

If you prefer not to use Secret Manager for development:

```bash
# Create .env file (not recommended for production!)
cat > .env << 'EOF'
AMAZON_CLIENT_ID=amzn1.application-oa2-client.xxxxx
AMAZON_CLIENT_SECRET=your_secret
AMAZON_REFRESH_TOKEN=Atzr|IwEBxxxxxxxx
AMAZON_PROFILE_ID=1780498399290938
EOF

# Load it
source .env

# Run scripts
python optimizer_core.py --config ppc_config.yaml \
  --profile-id $AMAZON_PROFILE_ID --features data_export
```

**Warning**: Never commit `.env` files to Git! They're excluded in `.gitignore` but be careful.

## Summary

✅ **Secure**: Credentials encrypted at rest and in transit  
✅ **Convenient**: No local credential files needed  
✅ **Auditable**: All access logged in Cloud Audit Logs  
✅ **Integrated**: Works seamlessly with existing code  
✅ **Cost-effective**: Under $1/month for typical usage

Now you can safely store and use your Amazon Ads credentials with Google Secret Manager!

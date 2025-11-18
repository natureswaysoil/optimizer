#!/usr/bin/env python3
"""
Fetch Amazon Ads Credentials from Google Secret Manager and Connect
===================================================================

This script:
1. Fetches Amazon Advertising API credentials from Google Secret Manager
2. Uses those credentials to authenticate with Amazon Ads API
3. Retrieves your real campaign data
4. Demonstrates the connection is working

Prerequisites:
- Google Cloud authentication configured (gcloud auth application-default login)
- Secret Manager secret containing Amazon credentials as JSON
- Required environment variables:
  * GCP_PROJECT_ID - Your Google Cloud Project ID
  * SECRET_NAME - Name of the secret in Secret Manager (default: amazon-ads-credentials)

Secret Format (JSON):
{
  "AMAZON_CLIENT_ID": "amzn1.application-oa2-client.xxxxx",
  "AMAZON_CLIENT_SECRET": "your_secret",
  "AMAZON_REFRESH_TOKEN": "Atzr|IwEBxxxxxxxx",
  "AMAZON_PROFILE_ID": "1780498399290938"
}

Usage:
  # Basic usage
  export GCP_PROJECT_ID="your-project-id"
  python fetch_and_connect.py

  # With custom secret name
  export GCP_PROJECT_ID="your-project-id"
  export SECRET_NAME="my-amazon-credentials"
  python fetch_and_connect.py
  
  # Fetch and export to data file
  python fetch_and_connect.py --export campaigns.json
"""

import os
import sys
import json
import argparse
from datetime import datetime

# Check for Google Cloud libraries
try:
    from google.cloud import secretmanager
    from google.cloud.exceptions import GoogleCloudError
except ImportError:
    print("ERROR: Google Cloud Secret Manager library not installed")
    print("Install with: pip install google-cloud-secret-manager")
    sys.exit(1)

# Import optimizer core
try:
    import optimizer_core
except ImportError:
    print("ERROR: optimizer_core.py not found")
    print("Make sure you're running this script from the optimizer directory")
    sys.exit(1)


class SecretsFetcher:
    """Fetches credentials from Google Secret Manager"""
    
    def __init__(self, project_id: str, secret_name: str = "amazon-ads-credentials"):
        """
        Initialize the secrets fetcher
        
        Args:
            project_id: GCP project ID
            secret_name: Name of the secret in Secret Manager
        """
        self.project_id = project_id
        self.secret_name = secret_name
        self.client = secretmanager.SecretManagerServiceClient()
        
    def fetch_credentials(self) -> dict:
        """
        Fetch Amazon Ads credentials from Secret Manager
        
        Returns:
            Dictionary with credential keys
        """
        print(f"🔐 Fetching credentials from Google Secret Manager...")
        print(f"   Project: {self.project_id}")
        print(f"   Secret: {self.secret_name}")
        print()
        
        try:
            # Build the secret version name
            name = f"projects/{self.project_id}/secrets/{self.secret_name}/versions/latest"
            
            # Access the secret
            response = self.client.access_secret_version(request={"name": name})
            
            # Decode the secret payload
            secret_string = response.payload.data.decode('UTF-8')
            credentials = json.loads(secret_string)
            
            # Validate required keys
            required_keys = [
                'AMAZON_CLIENT_ID',
                'AMAZON_CLIENT_SECRET',
                'AMAZON_REFRESH_TOKEN',
                'AMAZON_PROFILE_ID'
            ]
            
            missing_keys = [key for key in required_keys if key not in credentials]
            if missing_keys:
                raise ValueError(f"Secret missing required keys: {', '.join(missing_keys)}")
            
            print("✅ Credentials fetched successfully")
            
            # Display (masked) credential info
            for key in required_keys:
                value = credentials[key]
                if 'SECRET' in key or 'TOKEN' in key:
                    display_value = value[:8] + '...' if len(value) > 8 else '***'
                else:
                    display_value = value[:20] + '...' if len(value) > 20 else value
                print(f"   {key}: {display_value}")
            print()
            
            return credentials
            
        except GoogleCloudError as e:
            print(f"❌ Failed to fetch credentials from Secret Manager: {e}")
            print()
            print("Troubleshooting:")
            print("1. Ensure you're authenticated: gcloud auth application-default login")
            print("2. Verify the secret exists: gcloud secrets list")
            print(f"3. Check secret name: {self.secret_name}")
            print("4. Verify IAM permissions: roles/secretmanager.secretAccessor")
            raise
            
        except json.JSONDecodeError as e:
            print(f"❌ Secret is not valid JSON: {e}")
            print()
            print("The secret must be a JSON object with the following structure:")
            print(json.dumps({
                "AMAZON_CLIENT_ID": "amzn1.application-oa2-client.xxxxx",
                "AMAZON_CLIENT_SECRET": "your_secret",
                "AMAZON_REFRESH_TOKEN": "Atzr|IwEBxxxxxxxx",
                "AMAZON_PROFILE_ID": "1780498399290938"
            }, indent=2))
            raise


def test_amazon_connection(credentials: dict, export_file: str = None) -> bool:
    """
    Test Amazon Advertising API connection with fetched credentials
    
    Args:
        credentials: Dictionary with Amazon Ads credentials
        export_file: Optional file to export campaign data to
        
    Returns:
        True if connection successful
    """
    print("=" * 70)
    print("CONNECTING TO AMAZON ADVERTISING API")
    print("=" * 70)
    print()
    
    # Set credentials as environment variables for the API client
    os.environ['AMAZON_CLIENT_ID'] = credentials['AMAZON_CLIENT_ID']
    os.environ['AMAZON_CLIENT_SECRET'] = credentials['AMAZON_CLIENT_SECRET']
    os.environ['AMAZON_REFRESH_TOKEN'] = credentials['AMAZON_REFRESH_TOKEN']
    profile_id = credentials['AMAZON_PROFILE_ID']
    
    try:
        # Load config
        config = optimizer_core.Config('ppc_config.yaml')
        
        # Create API client
        print("🔄 Initializing Amazon Ads API client...")
        api = optimizer_core.AmazonAdsAPI(
            profile_id=profile_id,
            region=config.get('api.region', 'NA')
        )
        
        print("✅ Authentication successful!")
        print()
        
        # Retrieve campaigns
        print("-" * 70)
        print("RETRIEVING YOUR CAMPAIGNS FROM AMAZON")
        print("-" * 70)
        print()
        
        campaigns = api.get_campaigns()
        
        print(f"✅ Successfully retrieved {len(campaigns)} campaigns")
        print()
        
        if campaigns:
            print("Your campaigns:")
            print()
            
            campaign_data = []
            for i, campaign in enumerate(campaigns[:10], 1):  # Show first 10
                print(f"{i}. {campaign.name}")
                print(f"   ID: {campaign.campaign_id}")
                print(f"   State: {campaign.state}")
                print(f"   Daily Budget: ${campaign.daily_budget:.2f}")
                print(f"   Targeting: {campaign.targeting_type}")
                print()
                
                # Collect for export
                campaign_data.append({
                    'campaign_id': campaign.campaign_id,
                    'name': campaign.name,
                    'state': campaign.state,
                    'daily_budget': float(campaign.daily_budget),
                    'targeting_type': campaign.targeting_type,
                    'campaign_type': campaign.campaign_type
                })
            
            if len(campaigns) > 10:
                print(f"   ... and {len(campaigns) - 10} more campaigns")
                print()
                
                # Add remaining campaigns to export
                for campaign in campaigns[10:]:
                    campaign_data.append({
                        'campaign_id': campaign.campaign_id,
                        'name': campaign.name,
                        'state': campaign.state,
                        'daily_budget': float(campaign.daily_budget),
                        'targeting_type': campaign.targeting_type,
                        'campaign_type': campaign.campaign_type
                    })
            
            # Export if requested
            if export_file:
                print("-" * 70)
                print(f"EXPORTING DATA TO {export_file}")
                print("-" * 70)
                print()
                
                export_data = {
                    'export_timestamp': datetime.utcnow().isoformat(),
                    'profile_id': profile_id,
                    'total_campaigns': len(campaigns),
                    'campaigns': campaign_data
                }
                
                with open(export_file, 'w') as f:
                    json.dump(export_data, f, indent=2)
                
                print(f"✅ Exported {len(campaign_data)} campaigns to {export_file}")
                print()
        
        print("-" * 70)
        print("✅ CONNECTION SUCCESSFUL - DATA RETRIEVED!")
        print("-" * 70)
        print()
        print("Next steps:")
        print()
        print("1. Export your data to BigQuery:")
        print(f"   python optimizer_core.py --config ppc_config.yaml \\")
        print(f"     --profile-id {profile_id} --features data_export")
        print()
        print("2. Launch the dashboard:")
        print("   streamlit run dashboard.py")
        print()
        print("3. View your real data in the dashboard!")
        print("   - Select 'BigQuery' mode")
        print("   - Enter your GCP project ID")
        print()
        
        return True
        
    except optimizer_core.AuthenticationError as e:
        print(f"❌ Authentication failed: {e}")
        print()
        print("The credentials from Secret Manager may be invalid or expired.")
        print("Please verify the credentials in your secret.")
        return False
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print()
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description='Fetch Amazon Ads credentials from Google Secret Manager and connect'
    )
    parser.add_argument(
        '--project-id',
        help='GCP Project ID (or set GCP_PROJECT_ID env var)',
        default=os.getenv('GCP_PROJECT_ID')
    )
    parser.add_argument(
        '--secret-name',
        help='Secret name in Secret Manager (default: amazon-ads-credentials)',
        default=os.getenv('SECRET_NAME', 'amazon-ads-credentials')
    )
    parser.add_argument(
        '--export',
        help='Export campaign data to JSON file',
        metavar='FILE'
    )
    
    args = parser.parse_args()
    
    # Validate required arguments
    if not args.project_id:
        print("ERROR: GCP Project ID is required")
        print()
        print("Provide via:")
        print("  --project-id YOUR_PROJECT_ID")
        print("or:")
        print("  export GCP_PROJECT_ID=YOUR_PROJECT_ID")
        sys.exit(1)
    
    print("=" * 70)
    print("AMAZON ADS API CONNECTION VIA GOOGLE SECRET MANAGER")
    print("=" * 70)
    print()
    
    try:
        # Fetch credentials from Secret Manager
        fetcher = SecretsFetcher(args.project_id, args.secret_name)
        credentials = fetcher.fetch_credentials()
        
        # Test Amazon connection
        success = test_amazon_connection(credentials, args.export)
        
        if success:
            print()
            print("=" * 70)
            print("SUCCESS! Your Amazon Ads API is connected and working!")
            print("=" * 70)
            sys.exit(0)
        else:
            sys.exit(1)
            
    except Exception as e:
        print()
        print("=" * 70)
        print("FAILED - See errors above")
        print("=" * 70)
        sys.exit(1)


if __name__ == '__main__':
    main()

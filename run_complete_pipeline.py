#!/usr/bin/env python3
"""
Complete Amazon PPC Pipeline: Secrets → Amazon → BigQuery → Dashboard
=====================================================================

This script automates the entire pipeline:
1. Fetches credentials from Google Secret Manager
2. Connects to Amazon Ads API
3. Retrieves campaign and performance data
4. Exports data to BigQuery
5. Ready for dashboard visualization

Usage:
  # Basic usage (uses config from ppc_config.yaml)
  python run_complete_pipeline.py
  
  # With custom config
  python run_complete_pipeline.py --config my_config.yaml
  
  # Specify features to run
  python run_complete_pipeline.py --features data_export bid_optimization
  
  # Dry run (no actual changes)
  python run_complete_pipeline.py --dry-run
"""

import os
import sys
import argparse
import logging
from datetime import datetime

# Import optimizer_core
try:
    import optimizer_core
except ImportError:
    print("ERROR: optimizer_core.py not found")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def validate_config(config_path: str) -> bool:
    """Validate that config has required Google Cloud settings"""
    logger.info(f"Validating configuration: {config_path}")
    
    try:
        config = optimizer_core.Config(config_path)
        
        project_id = config.get('google_cloud.project_id')
        secret_id = config.get('google_cloud.secret_id')
        dataset_id = config.get('google_cloud.bigquery.dataset_id')
        
        if not project_id or not secret_id:
            logger.error("Configuration missing Google Cloud settings")
            logger.error("Required in ppc_config.yaml:")
            logger.error("  google_cloud:")
            logger.error("    project_id: 'your-project-id'")
            logger.error("    secret_id: 'amazon-ads-credentials'")
            return False
        
        logger.info(f"✅ Configuration valid")
        logger.info(f"   Project ID: {project_id}")
        logger.info(f"   Secret ID: {secret_id}")
        logger.info(f"   BigQuery Dataset: {dataset_id}")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        return False


def run_pipeline(config_path: str, profile_id: str = None, features: list = None, 
                 dry_run: bool = False) -> bool:
    """
    Run the complete pipeline
    
    Args:
        config_path: Path to ppc_config.yaml
        profile_id: Amazon Ads profile ID (optional, can be in secret)
        features: List of features to run (default: data_export)
        dry_run: If True, no actual changes made
        
    Returns:
        True if successful
    """
    logger.info("=" * 80)
    logger.info("COMPLETE AMAZON PPC PIPELINE")
    logger.info("=" * 80)
    logger.info(f"Started at: {datetime.now().isoformat()}")
    logger.info(f"Config: {config_path}")
    logger.info(f"Profile ID: {profile_id or 'From Secret Manager'}")
    logger.info(f"Features: {features or 'Default from config'}")
    logger.info(f"Dry Run: {dry_run}")
    logger.info("=" * 80)
    
    try:
        # Step 1: Validate configuration
        logger.info("\n" + "=" * 80)
        logger.info("STEP 1: Validate Configuration")
        logger.info("=" * 80)
        
        if not validate_config(config_path):
            logger.error("Configuration validation failed")
            return False
        
        # Step 2: Initialize automation (will fetch credentials automatically)
        logger.info("\n" + "=" * 80)
        logger.info("STEP 2: Initialize Automation")
        logger.info("=" * 80)
        logger.info("Initializing Amazon PPC Automation...")
        logger.info("This will automatically:")
        logger.info("  1. Fetch credentials from Google Secret Manager")
        logger.info("  2. Authenticate with Amazon Ads API")
        logger.info("  3. Prepare for data retrieval")
        
        automation = optimizer_core.PPCAutomation(
            config_path=config_path,
            profile_id=profile_id,
            dry_run=dry_run
        )
        
        logger.info("✅ Automation initialized successfully")
        
        # Step 3: Run features
        logger.info("\n" + "=" * 80)
        logger.info("STEP 3: Run Features")
        logger.info("=" * 80)
        
        if not features:
            features = ['data_export']
            logger.info("No features specified, running default: data_export")
        
        logger.info(f"Running features: {', '.join(features)}")
        
        results = automation.run(features)
        
        # Step 4: Display results
        logger.info("\n" + "=" * 80)
        logger.info("STEP 4: Results Summary")
        logger.info("=" * 80)
        
        for feature, result in results.items():
            if isinstance(result, dict):
                status = "✅ SUCCESS" if result.get('success') else "❌ FAILED"
                logger.info(f"{status}: {feature}")
                
                if result.get('success'):
                    # Display success metrics
                    for key, value in result.items():
                        if key != 'success' and key != 'error':
                            logger.info(f"   {key}: {value}")
                else:
                    # Display error
                    error = result.get('error', 'Unknown error')
                    logger.info(f"   Error: {error}")
            else:
                logger.info(f"Feature: {feature}")
                logger.info(f"   Result: {result}")
        
        # Step 5: Next steps
        logger.info("\n" + "=" * 80)
        logger.info("STEP 5: View Data in Dashboard")
        logger.info("=" * 80)
        
        config = optimizer_core.Config(config_path)
        project_id = config.get('google_cloud.project_id')
        dataset_id = config.get('google_cloud.bigquery.dataset_id', 'amazon_ads_data')
        
        logger.info("Your data is now in BigQuery!")
        logger.info("")
        logger.info("To view in the dashboard:")
        logger.info("1. Launch dashboard:")
        logger.info("   streamlit run dashboard.py")
        logger.info("")
        logger.info("2. In the dashboard sidebar:")
        logger.info(f"   - Select 'BigQuery' as data source")
        logger.info(f"   - Enter Project ID: {project_id}")
        logger.info(f"   - Enter Dataset ID: {dataset_id}")
        logger.info("")
        logger.info("3. Your real Amazon PPC data will be displayed!")
        
        logger.info("\n" + "=" * 80)
        logger.info("✅ PIPELINE COMPLETED SUCCESSFULLY")
        logger.info("=" * 80)
        logger.info(f"Completed at: {datetime.now().isoformat()}")
        
        return True
        
    except optimizer_core.AuthenticationError as e:
        logger.error("\n" + "=" * 80)
        logger.error("❌ AUTHENTICATION FAILED")
        logger.error("=" * 80)
        logger.error(f"Error: {e}")
        logger.error("")
        logger.error("Troubleshooting:")
        logger.error("1. Verify credentials in Google Secret Manager:")
        logger.error("   gcloud secrets versions access latest --secret=amazon-ads-credentials")
        logger.error("")
        logger.error("2. Check IAM permissions:")
        logger.error("   gcloud secrets add-iam-policy-binding amazon-ads-credentials \\")
        logger.error("     --member='user:your-email@example.com' \\")
        logger.error("     --role='roles/secretmanager.secretAccessor'")
        logger.error("")
        logger.error("3. Verify Amazon Ads credentials are valid")
        return False
        
    except Exception as e:
        logger.error("\n" + "=" * 80)
        logger.error("❌ PIPELINE FAILED")
        logger.error("=" * 80)
        logger.error(f"Error: {e}")
        logger.error("")
        logger.error("Full error details:")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Complete Amazon PPC Pipeline: Secrets → Amazon → BigQuery → Dashboard',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with default config
  python run_complete_pipeline.py
  
  # Run with custom config
  python run_complete_pipeline.py --config my_config.yaml
  
  # Run specific features
  python run_complete_pipeline.py --features data_export bid_optimization
  
  # Dry run (no changes)
  python run_complete_pipeline.py --dry-run
  
  # With specific profile ID
  python run_complete_pipeline.py --profile-id 1780498399290938
        """
    )
    
    parser.add_argument(
        '--config',
        default='ppc_config.yaml',
        help='Path to configuration file (default: ppc_config.yaml)'
    )
    
    parser.add_argument(
        '--profile-id',
        help='Amazon Ads Profile ID (optional if in Secret Manager)'
    )
    
    parser.add_argument(
        '--features',
        nargs='+',
        help='Features to run (default: data_export)',
        choices=['data_export', 'bid_optimization', 'dayparting', 
                'campaign_management', 'keyword_discovery', 'negative_keywords']
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run without making actual changes'
    )
    
    args = parser.parse_args()
    
    # Check if config file exists
    if not os.path.exists(args.config):
        logger.error(f"Configuration file not found: {args.config}")
        logger.error("")
        logger.error("Create one from the example:")
        logger.error(f"  cp ppc_config.example.yaml {args.config}")
        logger.error("")
        logger.error("Then edit it with your settings:")
        logger.error("  google_cloud:")
        logger.error("    project_id: 'your-gcp-project-id'")
        logger.error("    secret_id: 'amazon-ads-credentials'")
        sys.exit(1)
    
    # Run the pipeline
    success = run_pipeline(
        config_path=args.config,
        profile_id=args.profile_id,
        features=args.features,
        dry_run=args.dry_run
    )
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

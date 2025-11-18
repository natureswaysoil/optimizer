#!/usr/bin/env python3
"""
Amazon PPC Automation Suite
===========================

Comprehensive Amazon Advertising API automation script that includes:
- Bid optimization based on performance metrics
- Dayparting (time-based bid adjustments) with timezone awareness and BigQuery integration
- Campaign management (activate/deactivate based on ACOS)
- Keyword discovery and automatic addition
- Negative keyword management
- Batch processing and parallel API calls for performance optimization

Author: Nature's Way Soil
Version: 2.0.0 (Optimized)
License: MIT

Setup:
  export AMAZON_CLIENT_ID="amzn1.application-oa2-client.xxxxx"
  export AMAZON_CLIENT_SECRET="xxxxxxxx"
  export AMAZON_REFRESH_TOKEN="Atzr|IwEBxxxxxxxx"
  
Usage:
  python optimizer_core.py --config ppc_config.yaml --profile-id 1780498399290938
  python optimizer_core.py --config ppc_config.yaml --profile-id 1780498399290938 --dry-run
  python optimizer_core.py --config ppc_config.yaml --profile-id 1780498399290938 \
    --features bid_optimization dayparting
  python optimizer_core.py --config ppc_config.yaml --verify-connection --verify-sample-size 10
"""

import argparse
import csv
import io
import json
import logging
import os
import sys
import time
import zipfile
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
import gzip
import traceback

import requests

try:
  import yaml
except ImportError as e:
  # FATAL: pyyaml is required for config loading
  print(f"FATAL ERROR during import: pyyaml is required. Install with: pip install pyyaml. Error: {e}", file=sys.stderr)
  raise ImportError(f"Required dependency \'pyyaml\' not found: {e}") from e

try:
  import pytz
except ImportError:
  print("WARNING: pytz is not installed. Dayparting will use server timezone (UTC).")
  print("Install with: pip install pytz")
  pytz = None

# Google Cloud Secret Manager (optional)
try:
  from google.cloud import secretmanager
  from google.cloud.exceptions import GoogleCloudError
  SECRETMANAGER_AVAILABLE = True
except ImportError:
  secretmanager = None
  GoogleCloudError = Exception
  SECRETMANAGER_AVAILABLE = False

# ============================================================================
# CONSTANTS
# ============================================================================

ENDPOINTS = {
  "NA": "https://advertising-api.amazon.com",
  "EU": "https://advertising-api-eu.amazon.com",
  "FE": "https://advertising-api-fe.amazon.com",
}

TOKEN_URL = "https://api.amazon.com/auth/o2/token"
USER_AGENT = "NWS-PPC-Automation/2.0"

# Amazon Ads API versions for Amazon-Advertising-API-Version header
# For Sponsored Products endpoints (campaigns, ad groups, keywords): use v2
# For Reporting API: use v3
SP_API_VERSION = "v2"
REPORTS_API_VERSION = "v3"

# Rate limiting - Amazon Advertising API supports 10 requests/second (Optimized: Guide 1)
MAX_REQUESTS_PER_SECOND = 10 
REQUEST_INTERVAL = 1.0 / MAX_REQUESTS_PER_SECOND

# ============================================================================
# LOGGING SETUP
# ============================================================================

# Detect if running in Cloud Functions environment
IS_CLOUD_FUNCTION = os.getenv('K_SERVICE') is not None or os.getenv('FUNCTION_TARGET') is not None

if IS_CLOUD_FUNCTION:
  # Use only StreamHandler for Cloud Functions (logs go to Cloud Logging)
  logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
  )
  logger = logging.getLogger(__name__)
  logger.info("Running in Cloud Functions environment - using Cloud Logging")
else:
  # For local development, use both console and file logging with log rotation
  logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
      logging.FileHandler(f'ppc_automation_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
      logging.StreamHandler(sys.stdout)
    ]
  )
  logger = logging.getLogger(__name__)
  logger.info("Running in local environment - using file and console logging")

# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class Auth:
  """Authentication credentials"""
  access_token: str
  token_type: str
  expires_at: float

  def is_expired(self) -> bool:
    # Refresh token 60 seconds before actual expiry
    return time.time() > self.expires_at - 60


@dataclass
class Campaign:
  """Campaign data structure"""
  campaign_id: str
  name: str
  state: str
  daily_budget: float
  targeting_type: str
  campaign_type: str = "sponsoredProducts"
  
  
@dataclass
class AdGroup:
  """Ad Group data structure"""
  ad_group_id: str
  campaign_id: str
  name: str
  state: str
  default_bid: float


@dataclass
class Keyword:
  """Keyword data structure"""
  keyword_id: str
  ad_group_id: str
  campaign_id: str
  keyword_text: str
  match_type: str
  state: str
  bid: float


@dataclass
class PerformanceMetrics:
  """Performance metrics for keywords/campaigns"""
  impressions: int = 0
  clicks: int = 0
  cost: float = 0.0
  sales: float = 0.0
  orders: int = 0
  
  @property
  def ctr(self) -> float:
    return (self.clicks / self.impressions) if self.impressions > 0 else 0.0
  
  @property
  def acos(self) -> float:
    return (self.cost / self.sales) if self.sales > 0 else float('inf')
  
  @property
  def roas(self) -> float:
    return (self.sales / self.cost) if self.cost > 0 else 0.0
  
  @property
  def cpc(self) -> float:
    return (self.cost / self.clicks) if self.clicks > 0 else 0.0


@dataclass
class AuditEntry:
  """Audit trail entry"""
  timestamp: str
  action_type: str
  entity_type: str
  entity_id: str
  old_value: str
  new_value: str
  reason: str
  dry_run: bool


# ============================================================================
# RATE LIMITER (Optimized: Guide 1)
# ============================================================================

class RateLimiter:
  """Rate limiter for API calls with burst support (Token Bucket Algorithm)"""
  
  def __init__(self, max_per_second: int = MAX_REQUESTS_PER_SECOND, burst_size: int = 3):
    self.max_per_second = max_per_second
    self.interval = 1.0 / max_per_second
    self.burst_size = burst_size # Optimized: Guide 1 (burst support)
    self.tokens = burst_size
    self.last_update_time = time.time()
  
  def wait_if_needed(self):
    """Wait if necessary to respect rate limits with token bucket algorithm"""
    current_time = time.time()
    time_elapsed = current_time - self.last_update_time
    
    # Refill tokens based on time elapsed
    self.tokens = min(self.burst_size, self.tokens + time_elapsed * self.max_per_second)
    self.last_update_time = current_time
    
    # If no tokens available, wait
    if self.tokens < 1:
      # Calculate wait time for the next token to be available
      sleep_time = (1 - self.tokens) / self.max_per_second
      time.sleep(sleep_time)
      # Reset tokens after waiting (or set to 1 if we waited for a full token)
      self.tokens = 1
    
    # Consume one token
    self.tokens -= 1


# ============================================================================
# PERFORMANCE TIMING DECORATOR (Optimization: General Timing)
# ============================================================================

def timing_logger(operation_name: str = None):
  """Decorator to log execution time of operations"""
  def decorator(func):
    def wrapper(*args, **kwargs):
      op_name = operation_name or func.__name__
      start_time = time.time()
      logger.info(f"Starting {op_name}...")
      try:
        result = func(*args, **kwargs)
        elapsed = time.time() - start_time
        logger.info(f"✓ {op_name} completed in {elapsed:.2f}s")
        return result
      except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"✗ {op_name} failed after {elapsed:.2f}s: {e}")
        raise
    return wrapper
  return decorator


# ============================================================================
# CONFIGURATION LOADER
# ============================================================================

class ConfigurationError(Exception):
  """Custom exception for configuration errors"""
  pass


class AuthenticationError(Exception):
  """Amazon Ads API authentication error"""
  pass


class Config:
  """Configuration manager with enhanced error handling"""
  
  def __init__(self, config_path: str):
    self.config_path = config_path
    self.data = self._load_config()
  
  def _load_config(self) -> Dict:
    """
    Load configuration from YAML file
    """
    if not os.path.exists(self.config_path):
      error_msg = f"Configuration file not found: {self.config_path}"
      logger.error(error_msg)
      raise ConfigurationError(error_msg)
    
    try:
      with open(self.config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
      
      if not isinstance(config, dict):
        error_msg = f"Invalid configuration format: expected dictionary, got {type(config).__name__}"
        logger.error(error_msg)
        raise ConfigurationError(error_msg)
      
      logger.info(f"Configuration loaded from {self.config_path}")
      return config
      
    except yaml.YAMLError as e:
      error_msg = f"Failed to parse YAML configuration: {e}"
      logger.error(error_msg)
      raise ConfigurationError(error_msg)
      
    except IOError as e:
      error_msg = f"Failed to read configuration file: {e}"
      logger.error(error_msg)
      raise ConfigurationError(error_msg)
      
    except Exception as e:
      error_msg = f"Unexpected error loading configuration: {e}"
      logger.error(error_msg)
      raise ConfigurationError(error_msg)
  
  def get(self, key: str, default=None):
    """
    Get configuration value with dot notation support
    """
    if not key:
      return default
    
    keys = key.split('.')
    value = self.data
    
    for k in keys:
      if isinstance(value, dict):
        value = value.get(k, None)
        if value is None:
          return default
      else:
        return default
    
    return value if value is not None else default


# ============================================================================
# GOOGLE SECRET MANAGER HELPER
# ============================================================================

def fetch_credentials_from_secret_manager(project_id: str, secret_id: str) -> Dict[str, str]:
  """
  Fetch Amazon Ads credentials from Google Secret Manager
  
  Args:
    project_id: GCP project ID
    secret_id: Secret name in Secret Manager
    
  Returns:
    Dictionary with credential keys (AMAZON_CLIENT_ID, etc.)
    
  Raises:
    ImportError: If Google Secret Manager library not available
    GoogleCloudError: If unable to fetch secret
    ValueError: If secret format is invalid
  """
  if not SECRETMANAGER_AVAILABLE:
    raise ImportError(
      "Google Cloud Secret Manager library not installed. "
      "Install with: pip install google-cloud-secret-manager"
    )
  
  logger.info(f"Fetching credentials from Google Secret Manager...")
  logger.info(f"  Project: {project_id}")
  logger.info(f"  Secret: {secret_id}")
  
  try:
    # Create Secret Manager client
    client = secretmanager.SecretManagerServiceClient()
    
    # Build the secret version name (use latest)
    name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
    
    # Access the secret
    response = client.access_secret_version(request={"name": name})
    
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
      raise ValueError(
        f"Secret '{secret_id}' is missing required keys: {', '.join(missing_keys)}. "
        f"Required keys: {', '.join(required_keys)}"
      )
    
    logger.info("✅ Successfully fetched credentials from Secret Manager")
    
    # Log credential status (masked)
    for key in required_keys:
      value = credentials[key]
      if 'SECRET' in key or 'TOKEN' in key:
        display_value = value[:8] + '...' if len(value) > 8 else '***'
      else:
        display_value = value[:20] + '...' if len(value) > 20 else value
      logger.debug(f"  {key}: {display_value}")
    
    return credentials
    
  except GoogleCloudError as e:
    logger.error(f"Failed to fetch credentials from Secret Manager: {e}")
    logger.error(
      "Troubleshooting:\n"
      "1. Ensure you're authenticated: gcloud auth application-default login\n"
      f"2. Verify the secret exists: gcloud secrets describe {secret_id}\n"
      "3. Check IAM permissions: roles/secretmanager.secretAccessor required"
    )
    raise
    
  except json.JSONDecodeError as e:
    logger.error(f"Secret '{secret_id}' is not valid JSON: {e}")
    logger.error(
      "The secret must be a JSON object with these keys:\n"
      "{\n"
      '  "AMAZON_CLIENT_ID": "amzn1.application-oa2-client.xxxxx",\n'
      '  "AMAZON_CLIENT_SECRET": "your_secret",\n'
      '  "AMAZON_REFRESH_TOKEN": "Atzr|IwEBxxxxxxxx",\n'
      '  "AMAZON_PROFILE_ID": "1780498399290938"\n'
      "}"
    )
    raise ValueError(f"Invalid JSON in secret '{secret_id}'") from e


# ============================================================================
# AUDIT LOGGER
# ============================================================================

class AuditLogger:
  """CSV-based audit trail logger"""

  def __init__(self, output_dir: str = "."):
    self.output_dir = output_dir
    os.makedirs(self.output_dir, exist_ok=True)
    self.filename = os.path.join(
      output_dir,
      f"ppc_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    )
    self.entries: List[AuditEntry] = []
  
  def log(self, action_type: str, entity_type: str, entity_id: str,
      old_value: str, new_value: str, reason: str, dry_run: bool = False):
    """Log an audit entry"""
    entry = AuditEntry(
      timestamp=datetime.utcnow().isoformat(),
      action_type=action_type,
      entity_type=entity_type,
      entity_id=entity_id,
      old_value=old_value,
      new_value=new_value,
      reason=reason,
      dry_run=dry_run
    )
    self.entries.append(entry)
    logger.debug(f"Audit log: {action_type} {entity_type} {entity_id}: {old_value} -> {new_value} ({reason})")
  
  def save(self):
    """Save audit trail to CSV"""
    if not self.entries:
      logger.info("No audit entries to save")
      return
    
    try:
      with open(self.filename, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['timestamp', 'action_type', 'entity_type', 'entity_id',
                 'old_value', 'new_value', 'reason', 'dry_run']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for entry in self.entries:
          writer.writerow({
            'timestamp': entry.timestamp,
            'action_type': entry.action_type,
            'entity_type': entry.entity_type,
            'entity_id': entry.entity_id,
            'old_value': entry.old_value,
            'new_value': entry.new_value,
            'reason': entry.reason,
            'dry_run': entry.dry_run
          })
        
      logger.info(f"Audit trail saved to {self.filename} ({len(self.entries)} entries)")
    except Exception as e:
      logger.error(f"Failed to save audit trail: {e}")


# ============================================================================
# AMAZON ADS API CLIENT
# ============================================================================

class AmazonAdsAPI:
  """Amazon Advertising API client with retry logic and rate limiting"""
  
  def __init__(self, profile_id: str, region: str = "NA", max_requests_per_second: int = None,
         session: requests.Session = None):
    self.profile_id = profile_id
    self.region = region.upper()
    self.base_url = ENDPOINTS.get(self.region, ENDPOINTS["NA"])
    # Initialize client_id from environment; will be refreshed in _authenticate
    self.client_id: Optional[str] = os.getenv("AMAZON_CLIENT_ID", "") or None
    self.auth = self._authenticate()
    # Rate limiter respects the configurable max_requests_per_second (Optimized: Guide 1)
    self.rate_limiter = RateLimiter(max_requests_per_second or MAX_REQUESTS_PER_SECOND)
    # Use requests.Session for connection pooling (Optimized: Guide 9)
    self.session = session or requests.Session() 
    # Cache for campaigns and ad groups (Optimized: Guide 5)
    self._campaigns_cache: Optional[List[Campaign]] = None
    self._ad_groups_cache: Optional[List[AdGroup]] = None
    # Track last fetch error for campaigns to distinguish true empty set from failure
    self._last_campaigns_error: Optional[Exception] = None
  
  def _authenticate(self) -> Auth:
    """Authenticate and get access token"""
    client_id = os.getenv("AMAZON_CLIENT_ID", "").strip()
    client_secret = os.getenv("AMAZON_CLIENT_SECRET", "").strip()
    refresh_token = os.getenv("AMAZON_REFRESH_TOKEN", "").strip()
    
    if not all([client_id, client_secret, refresh_token]):
      logger.error("Missing required environment variables for authentication")
      raise AuthenticationError(
        "Missing required environment variables: AMAZON_CLIENT_ID, "
        "AMAZON_CLIENT_SECRET, or AMAZON_REFRESH_TOKEN"
      )

    # Log credential status (masked)
    logger.debug(f"Auth attempt - client_id: {client_id[:8] if client_id else 'MISSING'}..., "
          f"client_secret: {'SET' if client_secret else 'MISSING'}, "
          f"refresh_token: {refresh_token[:12] if refresh_token else 'MISSING'}...")

    # Cache client ID for use in request headers (stripped of whitespace)
    self.client_id = client_id
    
    payload = {
      "grant_type": "refresh_token",
      "refresh_token": refresh_token,
      "client_id": client_id,
      "client_secret": client_secret,
    }
    
    try:
      logger.debug(f"POST {TOKEN_URL}")
      response = requests.post(TOKEN_URL, data=payload, timeout=30)
      logger.debug(f"Response status: {response.status_code}")
      
      try:
        response_data = response.json()
        if response.status_code != 200:
          logger.error(f"Amazon auth error response: {response_data}")
      except:
        logger.debug(f"Response body (first 200 chars): {response.text[:200]}")
      
      response.raise_for_status()
      data = response.json()
      
      # Strip any whitespace from the access token (common issue with Secret Manager)
      access_token = data["access_token"].strip() if isinstance(data["access_token"], str) else data["access_token"]
      
      auth = Auth(
        access_token=access_token,
        token_type=data.get("token_type", "Bearer"),
        expires_at=time.time() + int(data.get("expires_in", 3600))
      )
      logger.info("Successfully authenticated with Amazon Ads API")
      logger.debug(f"Access token length: {len(access_token)}")
      return auth
    except requests.exceptions.RequestException as e:
      logger.error(f"Authentication request failed: {e}")
      raise AuthenticationError(f"Failed to authenticate with Amazon Ads API: {e}")
    except (KeyError, ValueError) as e:
      logger.error(f"Invalid authentication response: {e}")
      raise AuthenticationError(f"Invalid response from Amazon Ads API: {e}")
  
  def _refresh_auth_if_needed(self):
    """Refresh authentication if token expired"""
    if self.auth.is_expired():
      logger.info("Access token expired, refreshing...")
      self.auth = self._authenticate()

  def _headers(self, api_version: str = None) -> Dict[str, str]:
    """Get API request headers with optional API version"""
    self._refresh_auth_if_needed()

    client_id = self.client_id or os.getenv("AMAZON_CLIENT_ID", "")
    if not client_id:
      logger.warning("Amazon client ID missing when preparing headers")

    headers = {
      "Authorization": f"Bearer {self.auth.access_token}",
      "Content-Type": "application/json",
      "Amazon-Advertising-API-ClientId": client_id,
      "Amazon-Advertising-API-Scope": self.profile_id,
      "User-Agent": USER_AGENT,
      "Accept": "application/json",
    }
    
    # Add API version header if specified (for new versioned endpoints)
    if api_version:
      headers["Amazon-Advertising-API-Version"] = api_version
      
    return headers

  def _upgrade_endpoint(self, endpoint: str) -> tuple[str, str]:
    """
    Translate deprecated v2 endpoints to new format.
    Returns: (endpoint_path, api_version)
    """

    if not endpoint.startswith("/v2/"):
      # Already a new-style endpoint or doesn't need upgrading
      return endpoint, None

    # Map of v2 endpoints to their new paths (without version in path)
    replacements = {
      "/v2/sp/campaigns": ("/sp/campaigns", SP_API_VERSION),
      "/v2/sp/adGroups": ("/sp/adGroups", SP_API_VERSION),
      "/v2/sp/keywords/extended": ("/sp/keywords/extended", SP_API_VERSION),
      "/v2/sp/keywords": ("/sp/keywords", SP_API_VERSION),
      "/v2/sp/negativeKeywords": ("/sp/negativeKeywords", SP_API_VERSION),
      "/v2/sp/targets/keywords/recommendations": (
        "/sp/targets/keywords/recommendations", SP_API_VERSION
      ),
      "/v2/reports": ("/reports", REPORTS_API_VERSION),
    }

    for old_prefix, (new_prefix, api_version) in replacements.items():
      if endpoint.startswith(old_prefix):
        suffix = endpoint[len(old_prefix):]
        # Example: /v2/sp/campaigns/status -> /sp/campaigns/status
        return f"{new_prefix}{suffix}", api_version

    # Unknown v2 endpoint, return as-is with warning
    logger.warning(f"Unknown v2 endpoint format: {endpoint}")
    # Return endpoint stripped of /v2/ but with v2 API version header for compatibility
    return endpoint[3:], SP_API_VERSION if endpoint.startswith("/v2/sp/") else None

  def _request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
    """Make API request with retry logic and rate limiting (Optimized: Guide 3)"""
    self.rate_limiter.wait_if_needed()

    upgraded_endpoint, api_version = self._upgrade_endpoint(endpoint)
    # Construct full URL using the upgraded endpoint path
    url = f"{self.base_url}{upgraded_endpoint}"
    
    # Standard retries for transient errors (Optimized: Guide 3)
    max_retries = 3
    retry_delay = 1
    
    reauth_attempted = False

    for attempt in range(max_retries):
      try:
        # Log request details (mask sensitive headers)
        headers = self._headers(api_version=api_version)
        safe_headers = {k: ('REDACTED' if 'auth' in k.lower() else v) for k, v in headers.items()}
        logger.debug(f"Amazon API {method} {url} (attempt {attempt + 1}/{max_retries})")
        logger.debug(f"Request headers: {safe_headers}")
        logger.debug(f"API version for this request: {api_version}")
        if 'json' in kwargs:
          logger.debug(f"Request body preview: {str(kwargs['json'])[:500]}")
        
        # Use the session for connection pooling (Optimized: Guide 9)
        response = self.session.request(
          method=method,
          url=url,
          headers=headers,
          timeout=30,
          **kwargs
        )
        
        # Log response details
        logger.debug(f"Response status: {response.status_code}")
        logger.debug(f"Response headers: {dict(response.headers)}")
        
        if response.status_code == 429: # Rate limit
          retry_after = int(response.headers.get('Retry-After', retry_delay * (attempt + 1) * 2)) # Double delay on 429
          logger.warning(f"Rate limit hit, waiting {e}s...")
          time.sleep(retry_after)
          continue

        # Log response body preview for errors
        if response.status_code >= 400:
          body_preview = response.text[:1000] if response.text else 'Empty response'
          logger.error(f"Amazon API error {response.status_code} on {method} {url}: {body_preview}")

          # Extra diagnostics for auth-related 401/403
          if response.status_code in (401, 403) and not reauth_attempted:
            logger.info(
              f"Received {response.status_code} from Amazon Ads API; refreshing credentials and retrying",
            )
            self.auth = self._authenticate()
            reauth_attempted = True
            time.sleep(retry_delay * (attempt + 1))
            continue

        response.raise_for_status()
        return response

      except requests.exceptions.HTTPError as e:
        if attempt == max_retries - 1:
          logger.error(f"Request failed after {max_retries} attempts: {e}")
          if hasattr(e, 'response') and e.response is not None:
            logger.error(f"Final error response body: {e.response.text[:1000]}")
          raise
        logger.warning(f"Request failed (attempt {attempt + 1}/{max_retries}): {e}")
        if hasattr(e, 'response') and e.response is not None:
          logger.debug(f"Error response body: {e.response.text[:500]}")
        # Exponential backoff (Optimized: Guide 3)
        time.sleep(retry_delay * (attempt + 1)) 
      except requests.exceptions.RequestException as e:
        if attempt == max_retries - 1:
          logger.error(f"Request exception after {max_retries} attempts: {e}")
          raise
        logger.warning(f"Request exception (attempt {attempt + 1}/{max_retries}): {e}")
        time.sleep(retry_delay * (attempt + 1))
    
    raise Exception("Max retries exceeded")

  def verify_connection(self, sample_size: int = 5) -> Dict[str, Any]:
    """Verify API connectivity by retrieving a small campaign sample"""

    try:
      response = self._request(
        "GET",
        "/v2/sp/campaigns",
        params={"startIndex": 0, "count": max(sample_size, 1)}
      )
      campaigns = response.json() or []

      sample = []
      for entry in campaigns[:sample_size]:
        sample.append(
          {
            "campaignId": entry.get("campaignId"),
            "name": entry.get("name"),
            "state": entry.get("state"),
            "dailyBudget": entry.get("dailyBudget"),
          }
        )

      result = {
        "success": True,
        "campaign_count": len(campaigns),
        "sample": sample,
      }
      logger.info(
        "Amazon Ads API connectivity verified. Retrieved %d campaigns.",
        result["campaign_count"],
      )
      return result
    except Exception as exc:
      logger.error(f"Amazon Ads API verification failed: {e}")
      return {
        "success": False,
        "error": str(exc),
      }
  
  # ========================================================================
  # CAMPAIGNS (Optimized: Guide 5 - Caching)
  # ========================================================================
  
  def get_campaigns(self, state_filter: str = None, use_cache: bool = True) -> List[Campaign]:
    """Get all campaigns with caching support"""
    # Use cache if available and no state filter
    if use_cache and self._campaigns_cache is not None and state_filter is None:
      logger.debug(f"Using cached campaigns ({len(self._campaigns_cache)} items)")
      return self._campaigns_cache
    
    try:
      # Clear previous error before new attempt
      self._last_campaigns_error = None
      params = {}
      if state_filter:
        params['stateFilter'] = state_filter
      
      response = self._request('GET', '/v2/sp/campaigns', params=params)
      campaigns_data = response.json()
      
      if not isinstance(campaigns_data, list):
        logger.warning(f"Unexpected campaigns response format: {type(campaigns_data).__name__}")
        return []
      
      campaigns = []
      for c in campaigns_data:
        if not isinstance(c, dict):
          continue
          
        campaign = Campaign(
          campaign_id=str(c.get('campaignId', '')),
          name=c.get('name', ''),
          state=c.get('state', ''),
          daily_budget=float(c.get('dailyBudget', 0.0)),
          targeting_type=c.get('targetingType', ''),
          campaign_type='sponsoredProducts'
        )
        campaigns.append(campaign)
      
      logger.info(f"Retrieved {len(campaigns)} campaigns")
      
      # Cache if no state filter
      if state_filter is None:
        self._campaigns_cache = campaigns
      
      return campaigns
    except Exception as e:
      logger.error(f"Failed to get campaigns: {e}")
      self._last_campaigns_error = e
      return []
  
  def invalidate_campaigns_cache(self):
    """Invalidate campaigns cache after updates (Optimized: Guide 5)"""
    self._campaigns_cache = None
  
  def fetch_campaign_budgets(self) -> List[Dict[str, Any]]:
    """Fetch campaign budget information"""
    try:
      campaigns = self.get_campaigns()
      budget_data = []
      
      for campaign in campaigns:
        if not campaign.campaign_id:
          continue
          
        budget_data.append({
          'campaign_id': campaign.campaign_id,
          'campaign_name': campaign.name,
          'daily_budget': float(campaign.daily_budget or 0.0),
          'budget_type': 'DAILY',
          'state': campaign.state,
          'targeting_type': campaign.targeting_type,
        })
      
      logger.info(f"Fetched budget data for {len(budget_data)} campaigns")
      return budget_data
      
    except Exception as e:
      logger.error(f"Failed to fetch campaign budgets: {e}")
      return []
  
  def update_campaign(self, campaign_id: str, updates: Dict) -> bool:
    """Update campaign settings"""
    try:
      # Amazon's v2 API uses a list of updates, even for one item
      updates_list = [{**updates, 'campaignId': int(campaign_id)}]
      response = self._request(
        'PUT',
        '/v2/sp/campaigns',
        json=updates_list
      )
      # Check response for success/failure
      results = response.json()
      if results and results[0].get('code') == 'SUCCESS':
        logger.info(f"Updated campaign {e}: {updates}")
        self.invalidate_campaigns_cache() # Invalidate cache after update
        return True
      else:
        logger.error(f"Failed to update campaign {e}: {results[0].get('details', 'Unknown error')}")
        return False
    except Exception as e:
      logger.error(f"Failed to update campaign {campaign_id}: {e}")
      return False
  
  def create_campaign(self, campaign_data: Dict) -> Optional[str]:
    """Create new campaign"""
    try:
      response = self._request('POST', '/v2/sp/campaigns', json=[campaign_data])
      result = response.json()
      
      if result and len(result) > 0 and result[0].get('code') == 'SUCCESS':
        campaign_id = result[0].get('campaignId')
        logger.info(f"Created campaign: {e}")
        self.invalidate_campaigns_cache()
        return str(campaign_id)
      else:
        logger.error(f"Failed to create campaign: {result[0].get('details', 'Unknown error')}")
        return None
    except Exception as e:
      logger.error(f"Failed to create campaign: {e}")
      return None
  
  # ========================================================================
  # AD GROUPS (Optimized: Guide 5 - Caching)
  # ========================================================================
  
  def get_ad_groups(self, campaign_id: str = None, use_cache: bool = True) -> List[AdGroup]:
    """Get ad groups with caching support"""
    # Use cache if available and no campaign_id filter
    if use_cache and self._ad_groups_cache is not None and campaign_id is None:
      logger.debug(f"Using cached ad groups ({len(self._ad_groups_cache)} items)")
      return self._ad_groups_cache
    
    try:
      params = {}
      if campaign_id:
        params['campaignIdFilter'] = campaign_id
      
      response = self._request('GET', '/v2/sp/adGroups', params=params)
      ad_groups_data = response.json()
      
      ad_groups = []
      for ag in ad_groups_data:
        ad_group = AdGroup(
          ad_group_id=str(ag.get('adGroupId')),
          campaign_id=str(ag.get('campaignId')),
          name=ag.get('name', ''),
          state=ag.get('state', ''),
          default_bid=float(ag.get('defaultBid', 0))
        )
        ad_groups.append(ad_group)
      
      logger.info(f"Retrieved {len(ad_groups)} ad groups")
      
      # Cache if no campaign_id filter
      if campaign_id is None:
        self._ad_groups_cache = ad_groups
      
      return ad_groups
    except Exception as e:
      logger.error(f"Failed to get ad groups: {e}")
      return []
  
  def invalidate_ad_groups_cache(self):
    """Invalidate ad groups cache after updates (Optimized: Guide 5)"""
    self._ad_groups_cache = None
  
  def create_ad_group(self, ad_group_data: Dict) -> Optional[str]:
    """Create new ad group"""
    try:
      response = self._request('POST', '/v2/sp/adGroups', json=[ad_group_data])
      result = response.json()
      
      if result and len(result) > 0 and result[0].get('code') == 'SUCCESS':
        ad_group_id = result[0].get('adGroupId')
        logger.info(f"Created ad group: {e}")
        self.invalidate_ad_groups_cache()
        return str(ad_group_id)
      else:
        logger.error(f"Failed to create ad group: {result[0].get('details', 'Unknown error')}")
        return None
    except Exception as e:
      logger.error(f"Failed to create ad group: {e}")
      return None
  
  # ========================================================================
  # KEYWORDS
  # ========================================================================
  
  def get_keywords(self, campaign_id: str = None, ad_group_id: str = None) -> List[Keyword]:
    """
    Get keywords using v2 endpoint.
    If no filter is provided, it iterates over all campaigns to fetch keywords.
    """
    try:
      # If no filters, iterate over campaigns (required by Amazon API v2)
      if not campaign_id and not ad_group_id:
        logger.info("Keywords endpoint requires campaignIdFilter or adGroupIdFilter. Fetching by iterating all campaigns...")
        # Get all campaigns first (using cache)
        campaigns = self.get_campaigns()
        all_keywords = []
        total_campaigns = len(campaigns)
        
        logger.info(f"Fetching keywords from {e} campaigns...")
        
        # NOTE: This sequential loop respects the RateLimiter built into _request.
        for i, camp in enumerate(campaigns, 1):
          try:
            # Recursive call with filter
            camp_keywords = self.get_keywords(campaign_id=camp.campaign_id, use_cache=False) 
            all_keywords.extend(camp_keywords)
            
            if i % 10 == 0:
              logger.info(f"Progress: {i}/{total_campaigns} campaigns processed, {len(all_keywords)} keywords found")
          except Exception as e:
            logger.error(f"Failed to get keywords for campaign {camp.campaign_id}: {e}")
        
        logger.info(f"Completed: Retrieved {len(all_keywords)} keywords from {e} campaigns")
        return all_keywords
      
      # Case 2: Filter is provided, make a direct API call
      params = {}
      if campaign_id:
        params['campaignIdFilter'] = campaign_id
      if ad_group_id:
        params['adGroupIdFilter'] = ad_group_id
      
      response = self._request('GET', '/v2/sp/keywords', params=params)
      keywords_data = response.json()
      
      keywords = []
      for kw in keywords_data:
        keyword = Keyword(
          keyword_id=str(kw.get('keywordId')),
          ad_group_id=str(kw.get('adGroupId')),
          campaign_id=str(kw.get('campaignId')),
          keyword_text=kw.get('keywordText', ''),
          match_type=kw.get('matchType', ''),
          state=kw.get('state', ''),
          bid=float(kw.get('bid', 0))
        )
        keywords.append(keyword)
      
      logger.debug(f"Retrieved {len(keywords)} keywords for campaign {campaign_id or ad_group_id}")
      return keywords
      
    except Exception as e:
      logger.error(f"Failed to get keywords: {e}")
      return []
  
  def update_keyword_bid(self, keyword_id: str, bid: float, state: str = None) -> bool:
    """Update keyword bid (single keyword - discouraged in favor of batch_update_keywords)"""
    updates = [{'keywordId': int(keyword_id), 'bid': round(bid, 2)}]
    if state:
        updates[0]['state'] = state
        
    try:
      # Use the batch update function for consistency, even for a single item
      results = self.batch_update_keywords(updates)
      return results['success'] == 1
    except Exception as e:
      logger.error(f"Failed to update keyword {keyword_id}: {e}")
      return False
  
  def batch_update_keywords(self, updates: List[Dict]) -> Dict:
    """Batch update keywords (up to 100 at a time) (Optimized: Guide 8)"""
    results = {
      'total': len(updates),
      'success': 0,
      'failed': 0
    }
    
    batch_size = 100
    for i in range(0, len(updates), batch_size):
      batch = updates[i:i+batch_size]
      try:
        response = self._request('PUT', '/v2/sp/keywords', json=batch)
        result = response.json()
        
        for r in result:
          if r.get('code') == 'SUCCESS':
            results['success'] += 1
          else:
            results['failed'] += 1
            # Log specific keyword failure
            logger.warning(f"Failed to update keyword {r.get('keywordId')}: {r.get('details')}")
        
        logger.info(f"Batch updated {len(batch)} keywords (batch {i//batch_size + 1}/{len(updates)//batch_size + 1})")
      except Exception as e:
        logger.error(f"Failed to batch update keywords: {e}")
        results['failed'] += len(batch)
    
    logger.info(f"Batch update complete: {results['success']}/{results['total']} successful")
    return results
  
  def create_keywords(self, keywords_data: List[Dict]) -> List[str]:
    """Create new keywords"""
    # NOTE: Keywords are created in batches implicitly by the caller (KeywordDiscovery)
    try:
      response = self._request('POST', '/v2/sp/keywords', json=keywords_data)
      result = response.json()
      
      created_ids = []
      for r in result:
        if r.get('code') == 'SUCCESS':
          created_ids.append(str(r.get('keywordId')))
        else:
          logger.warning(f"Failed to create keyword: {r.get('details')}")
      
      logger.info(f"Created {len(created_ids)} keywords")
      return created_ids
    except Exception as e:
      logger.error(f"Failed to create keywords: {e}")
      return []
  
  # ========================================================================
  # NEGATIVE KEYWORDS
  # ========================================================================
  
  def get_negative_keywords(self, campaign_id: str = None) -> List[Dict]:
    """Get negative keywords"""
    try:
      params = {}
      if campaign_id:
        params['campaignIdFilter'] = campaign_id
      
      response = self._request('GET', '/v2/sp/negativeKeywords', params=params)
      return response.json()
    except Exception as e:
      logger.error(f"Failed to get negative keywords: {e}")
      return []
  
  def create_negative_keywords(self, negative_keywords_data: List[Dict]) -> List[str]:
    """Create negative keywords"""
    try:
      response = self._request('POST', '/v2/sp/negativeKeywords', json=negative_keywords_data)
      result = response.json()
      
      created_ids = []
      for r in result:
        if r.get('code') == 'SUCCESS':
          created_ids.append(str(r.get('keywordId')))
        else:
          logger.warning(f"Failed to create negative keyword: {r.get('details')}")
      
      logger.info(f"Created {len(created_ids)} negative keywords")
      return created_ids
    except Exception as e:
      logger.error(f"Failed to create negative keywords: {e}")
      return []
  
  # ========================================================================
  # REPORTS
  # ========================================================================
  
  def create_report(self, report_type: str, metrics: List[str],
          report_date: str = None, segment: str = None) -> Optional[str]:
    """Create performance report using the Amazon Ads Reporting v3 API."""

    report_type = (report_type or '').lower()
    segment = (segment or '').lower() or None

    report_definitions = {
      'campaigns': {
        'reportTypeId': 'spCampaigns',
        'groupBy': ['campaign'],
      },
      'keywords': {
        'reportTypeId': 'spKeywords',
        'groupBy': ['campaign', 'adGroup', 'keyword'],
      },
      'targets': {
        'reportTypeId': 'spTargets',
        'groupBy': ['campaign', 'adGroup', 'targeting'],
      },
      'targets:query': { # For Search Term Reports
        'reportTypeId': 'spSearchTerm',
        'groupBy': ['campaign', 'adGroup', 'searchTerm'],
      },
    }

    definition_key = report_type if segment is None or segment == 'query' else f"{report_type}:{segment}"
    definition = report_definitions.get(definition_key)

    if not definition:
      logger.error(f"Unsupported report configuration: type={report_type}, segment={segment}")
      return None

    try:
      # Determine date range (default to yesterday)
      if report_date:
        if len(report_date) == 8:
          start_date = datetime.strptime(report_date, '%Y%m%d').date()
        else:
          start_date = datetime.strptime(report_date, '%Y-%m-%d').date()
      else:
        start_date = (datetime.utcnow() - timedelta(days=1)).date()
      end_date = start_date
    except ValueError as exc:
      logger.error(f"Invalid report date \'{report_date}\': {exc}")
      return None

    columns = metrics or []

    payload = {
      'name': f"{definition['reportTypeId']}-report-{start_date.isoformat()}",
      'startDate': start_date.isoformat(),
      'endDate': end_date.isoformat(),
      'format': 'GZIP_JSON',
      'timeUnit': 'SUMMARY',
      'configuration': {
        'adProduct': 'SPONSORED_PRODUCTS',
        'reportTypeId': definition['reportTypeId'],
        'columns': columns,
        'metrics': columns,
      }
    }

    if definition.get('groupBy'):
      payload['configuration']['groupBy'] = definition['groupBy']

    try:
      # Use v2 endpoint path (will be upgraded to v3 by _upgrade_endpoint)
      response = self._request('POST', '/v2/reports', json=payload)
      data = response.json() if response.content else {}
      report_id = data.get('reportId') or data.get('report_id')

      if not report_id:
        logger.error(f"Unexpected create_report response: {e}")
        return None

      logger.info(f"Created report {e} ({definition['reportTypeId']})")
      return report_id
    except Exception as exc:
      logger.error(f"Failed to create report: {e}")
      return None

  def get_report_status(self, report_id: str) -> Dict:
    """Get report status"""
    try:
      # Use v2 endpoint path (will be upgraded to v3 by _upgrade_endpoint)
      endpoint = f"/v2/reports/{report_id}"
      response = self._request('GET', endpoint)
      data = response.json() if response.content else {}

      # Normalise status fields
      if 'status' not in data:
        if 'processingStatus' in data:
          data['status'] = data['processingStatus']
        elif 'state' in data:
          data['status'] = data['state']

      # Normalise download location keys
      if 'location' not in data:
        location = None
        if isinstance(data.get('url'), str):
          location = data['url']
        elif isinstance(data.get('report'), dict):
          location = data['report'].get('url') or data['report'].get('downloadUrl')
        elif isinstance(data.get('file'), dict):
          location = data['file'].get('url')
        if location:
          data['location'] = location

      return data
    except Exception as e:
      logger.error(f"Failed to get report status: {e}")
      return {}
  
  def download_report(self, report_url: str) -> List[Dict]:
    """Download and parse report with retry logic"""
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
      try:
        logger.debug(f"Downloading report from {report_url} (attempt {attempt + 1}/{max_retries})")
        # Use simple requests.get for file download outside the session/rate limiter
        response = requests.get(report_url, timeout=60)
        
        logger.debug(f"Report download status: {response.status_code}, Content-Type: {response.headers.get('Content-Type')}, Size: {len(response.content)} bytes")
        
        if response.status_code >= 400:
          logger.error(f"Report download failed with status {response.status_code}: {response.text[:500]}")
        
        response.raise_for_status()
        
        # Try to decompress as gzip (Standard Amazon format)
        content = response.content
        
        try:
          with gzip.GzipFile(fileobj=io.BytesIO(content)) as gz:
            text = io.TextIOWrapper(gz, encoding='utf-8', newline='')
            data = list(csv.DictReader(text))
            logger.info(f"Successfully parsed GZIP report with {len(data)} rows")
            return data
        except gzip.BadGzipFile:
          # Fallback 1: Try ZIP format (for older or other API versions)
          try:
            with zipfile.ZipFile(io.BytesIO(content)) as z:
              names = z.namelist()
              if names:
                with z.open(names[0]) as f:
                  text = io.TextIOWrapper(f, encoding='utf-8', newline='')
                  data = list(csv.DictReader(text))
                  logger.info(f"Successfully parsed ZIP report with {len(data)} rows")
                  return data
              else:
                raise Exception("ZIP file is empty")
          except (zipfile.BadZipFile, Exception) as zip_exc:
            # Fallback 2: Try as plain text (rare)
            logger.warning(f"Failed to parse as ZIP/GZIP ({zip_exc}). Trying as plain text...")
            try:
                text = io.StringIO(content.decode('utf-8'))
                data = list(csv.DictReader(text))
                logger.info(f"Successfully parsed plain text report with {len(data)} rows")
                return data
            except Exception as plain_exc:
                logger.error(f"Failed to parse report as plain text: {plain_exc}")
                raise Exception("Failed to parse report content") from plain_exc
            
      except requests.exceptions.RequestException as e:
        if attempt == max_retries - 1:
          logger.error(f"Failed to download report after {max_retries} attempts: {e}")
          return []
        logger.warning(f"Report download failed (attempt {attempt + 1}/{max_retries}): {e}")
        time.sleep(retry_delay * (attempt + 1))
      except Exception as e:
        if attempt == max_retries - 1:
          logger.error(f"Failed to parse report after {max_retries} attempts: {e}")
          return []
        logger.warning(f"Report parsing failed (attempt {attempt + 1}/{max_retries}): {e}")
        time.sleep(retry_delay * (attempt + 1))
    
    return []
  
  def wait_for_report(self, report_id: str, timeout: int = 300) -> Optional[str]:
    """Wait for report to be ready with adaptive polling (exponential backoff) (Optimized: Guide 7)"""
    start_time = time.time()
    poll_interval = 2 # Start with 2 seconds
    max_poll_interval = 10 # Cap at 10 seconds
    
    while time.time() - start_time < timeout:
      status_data = self.get_report_status(report_id)
      status = (status_data.get('status') or '').upper()

      if status in {'SUCCESS', 'COMPLETED', 'DONE'}:
        elapsed = time.time() - start_time
        logger.info(f"Report {e} ready in {elapsed:.1f}s")
        return status_data.get('location')
      elif status in {'FAILURE', 'FAILED', 'CANCELLED'}:
        logger.error(f"Report {e} failed: {status_data}")
        return None
      
      # Adaptive polling: gradually increase wait time
      time.sleep(poll_interval)
      poll_interval = min(poll_interval * 1.5, max_poll_interval)
    
    logger.error(f"Report {report_id} timeout after {timeout}s")
    return None
  
  def create_and_download_reports_parallel(self, report_configs: List[Dict], 
                                     max_workers: int = 3) -> Dict[str, List[Dict]]:
    """
    Create multiple reports and download them in parallel for faster processing. (Optimized: Guide 6)
    """
    start_time = time.time()
    logger.info(f"Creating {len(report_configs)} reports in parallel...")
    
    # Step 1: Create all reports (must be sequential due to rate limiting in self._request)
    report_ids = {}
    for config in report_configs:
      name = config.get('name', 'unnamed')
      report_id = self.create_report(
        report_type=config['report_type'],
        metrics=config['metrics'],
        report_date=config.get('report_date'),
        segment=config.get('segment')
      )
      if report_id:
        report_ids[name] = report_id
        logger.info(f"Created report \'{name}\': {report_id}")
    
    if not report_ids:
      logger.error("No reports were created successfully")
      return {}
    
    # Step 2: Wait for all reports in parallel using ThreadPoolExecutor
    logger.info(f"Waiting for {len(report_ids)} reports in parallel...")
    report_urls = {}
    
    def wait_for_single_report(name_and_id):
      """Helper function to wait for a single report status"""
      name, report_id = name_and_id
      # Use a higher timeout for parallel waiting
      url = self.wait_for_report(report_id, timeout=400) 
      return name, url
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
      future_to_name = {
        executor.submit(wait_for_single_report, (name, rid)): name 
        for name, rid in report_ids.items()
      }
      
      for future in as_completed(future_to_name):
        name = future_to_name[future]
        try:
          result_name, url = future.result()
          if url:
            report_urls[result_name] = url
            logger.info(f"Report \'{name}\' ready for download")
        except Exception as e:
          logger.error(f"Error waiting for report \'{name}\': {e}")
    
    # Step 3: Download all reports in parallel
    logger.info(f"Downloading {len(report_urls)} reports in parallel...")
    results = {}
    
    def download_single_report(name_and_url):
      """Helper function to download a single report"""
      name, url = name_and_url
      # Note: self.download_report handles its own internal retries
      data = self.download_report(url) 
      return name, data
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
      future_to_name = {
        executor.submit(download_single_report, (name, url)): name 
        for name, url in report_urls.items()
      }
      
      for future in as_completed(future_to_name):
        name = future_to_name[future]
        try:
          result_name, data = future.result()
          results[result_name] = data
          logger.info(f"Downloaded report '{result_name}': {len(data)} records")
        except Exception as e:
          logger.error(f"Error downloading report \'{name}\': {e}")
    
    elapsed = time.time() - start_time
    # Logging the potential time saved (heuristic)
    logger.info(f"Parallel report processing complete in {elapsed:.1f}s")
    
    return results
  
  # ========================================================================
  # KEYWORD SUGGESTIONS
  # ========================================================================
  
  def get_keyword_suggestions(self, asin: str, max_suggestions: int = 100) -> List[Dict]:
    """Get keyword suggestions for ASIN"""
    try:
      # Use keyword recommendations endpoint
      payload = {
        'asins': [asin],
        'maxRecommendations': max_suggestions
      }
      
      response = self._request('POST', '/v2/sp/targets/keywords/recommendations', json=payload)
      recommendations = response.json()
      
      suggested_keywords = []
      if 'recommendations' in recommendations:
        for rec in recommendations['recommendations']:
          suggested_keywords.append({
            'keyword': rec.get('keyword', ''),
            'match_type': rec.get('matchType', 'broad'),
            'suggested_bid': rec.get('bid', 0.5)
          })
      
      logger.info(f"Retrieved {len(suggested_keywords)} keyword suggestions for ASIN {e}")
      return suggested_keywords
    except Exception as e:
      logger.error(f"Failed to get keyword suggestions for ASIN {asin}: {e}")
      return []


# ============================================================================
# AUTOMATION FEATURES
# ============================================================================

class BidOptimizer:
  """Bid optimization based on performance metrics"""
  
  def __init__(self, config: Config, api: AmazonAdsAPI, audit_logger: AuditLogger):
    self.config = config
    self.api = api
    self.audit = audit_logger
  
  def optimize(self, dry_run: bool = False) -> Dict:
    """Run bid optimization with performance timing and batch processing (Optimized: Guide 2)"""
    start_time = time.time()
    logger.info("=== Starting Bid Optimization ===")
    
    results = {
      'keywords_analyzed': 0,
      'bids_increased': 0,
      'bids_decreased': 0,
      'no_change': 0,
      'keywords_optimized': 0,
      'top_performers': []
    }
    
    # Get performance data config
    lookback_days = self.config.get('bid_optimization.lookback_days', 14)
    report_date = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
    
    # Use parallel report config if desired, but for single report, sequential is fine
    report_id = self.api.create_report(
      'keywords',
      ['campaignId', 'adGroupId', 'keywordId', 'impressions', 'clicks', 
       'cost', 'attributedSales14d', 'attributedConversions14d'],
      report_date=report_date
    )
    
    if not report_id:
      logger.error("Failed to create performance report")
      return results
    
    report_url = self.api.wait_for_report(report_id)
    if not report_url:
      logger.error("Failed to get report data URL")
      return results
    
    report_data = self.api.download_report(report_url)
    
    # Process keywords in batches to optimize memory usage (Optimized: Guide 2)
    batch_size = 100
    keyword_updates = [] # Collect all updates for batch processing (Optimized: Guide 8)
    
    # Get current keywords (may trigger an expensive API call if cache is empty)
    keywords = self.api.get_keywords()
    keyword_map = {kw.keyword_id: kw for kw in keywords}
    
    logger.info(f"Processing {len(report_data)} performance records...")
    
    keyword_performance = []
    
    # Analyze each keyword
    for idx, row in enumerate(report_data):
      keyword_id = str(row.get('keywordId', ''))
      if not keyword_id or keyword_id not in keyword_map:
        continue
      
      results['keywords_analyzed'] += 1
      keyword = keyword_map[keyword_id]
      
      # Calculate metrics
      metrics = PerformanceMetrics(
        impressions=int(row.get('impressions', 0) or 0),
        clicks=int(row.get('clicks', 0) or 0),
        cost=float(row.get('cost', 0) or 0),
        sales=float(row.get('attributedSales14d', 0) or 0),
        orders=int(row.get('attributedConversions14d', 0) or 0)
      )
      
      new_bid = self._calculate_new_bid(keyword, metrics)
      bid_change = 0.0
      
      if new_bid is not None and abs(new_bid - keyword.bid) > 0.01:
        reason = self._get_bid_change_reason(keyword, metrics, new_bid)
        bid_change = new_bid - keyword.bid
        
        if new_bid > keyword.bid:
          results['bids_increased'] += 1
        else:
          results['bids_decreased'] += 1
        
        self.audit.log(
          'BID_UPDATE',
          'KEYWORD',
          keyword_id,
          f"${keyword.bid:.2f}",
          f"${new_bid:.2f}",
          reason,
          dry_run
        )
        
        # Collect updates for batch processing (Optimized: Guide 8)
        keyword_updates.append({
          'keywordId': int(keyword_id),
          'bid': round(new_bid, 2)
        })
      else:
        results['no_change'] += 1
      
      # Collect keyword performance data for top performers
      if metrics.sales > 0: # Only include keywords with sales
        keyword_performance.append({
          'keyword_text': keyword.keyword_text,
          'keyword_id': keyword_id,
          'clicks': metrics.clicks,
          'sales': metrics.sales,
          'cost': metrics.cost,
          'acos': metrics.acos,
          'bid_old': keyword.bid,
          'bid_new': new_bid if new_bid is not None else keyword.bid,
          'bid_change': bid_change
        })

      # Log progress every batch_size records (Optimized: Guide 2)
      if (idx + 1) % batch_size == 0:
        logger.info(f"Processed {idx + 1}/{len(report_data)} records...")

    # Total keywords optimized equals all bid increases and decreases
    results['keywords_optimized'] = (
      results['bids_increased'] + results['bids_decreased']
    )
    
    # Apply batch updates (Optimized: Guide 8)
    if keyword_updates and not dry_run:
      logger.info(f"Applying {len(keyword_updates)} bid updates in batches...")
      batch_results = self.api.batch_update_keywords(keyword_updates)
      # Override the simple success count with the true batch result count
      results['keywords_optimized'] = batch_results['success']
      results['batch_update_failures'] = batch_results['failed']
    
    # Sort by sales and get top 20 performers for dashboard
    keyword_performance.sort(key=lambda x: x['sales'], reverse=True)
    results['top_performers'] = keyword_performance[:20]
    
    # Calculate totals for summary
    results['total_spend'] = sum(kw['cost'] for kw in keyword_performance)
    results['total_sales'] = sum(kw['sales'] for kw in keyword_performance)
    
    logger.info(f"Collected {len(results['top_performers'])} top performing keywords for dashboard")
    
    elapsed = time.time() - start_time
    logger.info(f"Bid optimization complete in {elapsed:.2f}s.")
    results['execution_time_seconds'] = round(elapsed, 2)
    return results
  
  def _calculate_new_bid(self, keyword: Keyword, metrics: PerformanceMetrics) -> Optional[float]:
    """Calculate new bid based on performance"""
    # Get thresholds from config
    min_clicks = self.config.get('bid_optimization.min_clicks', 25)
    min_spend = self.config.get('bid_optimization.min_spend', 5.0)
    high_acos = self.config.get('bid_optimization.high_acos', 0.60)
    low_acos = self.config.get('bid_optimization.low_acos', 0.25)
    up_pct = self.config.get('bid_optimization.up_pct', 0.15)
    down_pct = self.config.get('bid_optimization.down_pct', 0.20)
    min_bid = self.config.get('bid_optimization.min_bid', 0.25)
    max_bid = self.config.get('bid_optimization.max_bid', 5.0)
    
    # Check if we have enough data
    if metrics.clicks < min_clicks and metrics.cost < min_spend:
      return None
    
    current_bid = keyword.bid
    new_bid = None
    
    # No sales - reduce bid
    if metrics.sales <= 0 and metrics.clicks >= min_clicks:
      new_bid = current_bid * (1 - down_pct)
    # High ACOS - reduce bid
    elif metrics.acos > high_acos:
      new_bid = current_bid * (1 - down_pct)
    # Low ACOS - increase bid
    elif metrics.acos < low_acos and metrics.sales > 0:
      new_bid = current_bid * (1 + up_pct)
    # Medium ACOS - no change
    else:
      return None
    
    if new_bid is None:
      return None
      
    # Clamp to min/max
    new_bid = max(min_bid, min(max_bid, new_bid))
    
    # Only return if there is a meaningful change
    if abs(new_bid - current_bid) < 0.01:
        return None
        
    return round(new_bid, 2)
  
  def _get_bid_change_reason(self, keyword: Keyword, metrics: PerformanceMetrics, 
                  new_bid: float) -> str:
    """Get reason for bid change"""
    
    high_acos = self.config.get('bid_optimization.high_acos', 0.60)
    low_acos = self.config.get('bid_optimization.low_acos', 0.25)
    
    if new_bid > keyword.bid:
      return f"Low ACOS ({metrics.acos:.1%}) < {low_acos:.1%} - increasing bid"
    elif new_bid < keyword.bid:
      if metrics.sales <= 0:
        return f"No sales after {metrics.clicks} clicks - reducing bid"
      else:
        return f"High ACOS ({metrics.acos:.1%}) > {high_acos:.1%} - reducing bid"
    return f"ACOS: {metrics.acos:.1%}, CTR: {metrics.ctr:.2%}"


class DaypartingManager:
  """Time-based bid adjustments with ML-driven optimization (Optimized: Guide 4)"""
  
  def __init__(self, config: Config, api: AmazonAdsAPI, audit_logger: AuditLogger, bigquery_client=None):
    self.config = config
    self.api = api
    self.audit = audit_logger
    self.bigquery_client = bigquery_client
    self.base_bids: Dict[str, float] = {} # Store original bids
  
  def apply_intelligent_dayparting(self, dry_run: bool = False) -> Dict:
    """Apply ML-driven dayparting based on BigQuery performance data"""
    start_time = time.time()
    logger.info("=== Applying Intelligent Dayparting (Data-Driven) ===")
    
    # Check if dayparting is enabled
    if not self.config.get('dayparting.enabled', False):
      logger.info("Dayparting is disabled in config")
      return {}
    
    if not self.bigquery_client:
      logger.warning("BigQuery client not available, falling back to config-based dayparting")
      return self.apply_dayparting(dry_run)
    
    # Get timezone from config (Optimized: Guide 4)
    timezone_str = self.config.get('dayparting.timezone', 'US/Pacific')
    
    if pytz:
      try:
        tz = pytz.timezone(timezone_str)
        current_time = datetime.now(tz)
      except Exception as e:
        logger.warning(f"Invalid timezone \'{timezone_str}\', using UTC: {e}")
        current_time = datetime.now(pytz.utc)
        timezone_str = 'UTC'
    else:
      current_time = datetime.now()
      logger.warning("pytz not available, using server timezone (UTC)")
      timezone_str = 'UTC'
    
    current_hour = current_time.hour
    current_day = current_time.strftime('%A').upper()
    current_day_num = current_time.weekday() # 0=Monday, 6=Sunday
    # Convert to SQL day_of_week (0=Sunday, 6=Saturday)
    sql_day_of_week = (current_day_num + 1) % 7
    
    logger.info(f"Current time ({timezone_str}): {current_time} (day {day_of_week}) {current_hour:02d}:00")
    
    # Fetch optimal multiplier from BigQuery
    multiplier = self._fetch_optimal_multiplier(sql_day_of_week, current_hour)
    
    if multiplier is None:
      logger.warning("No BigQuery data available, falling back to config-based multiplier")
      multiplier = self._get_multiplier(current_hour, current_day)
      data_source = 'config'
    else:
      data_source = 'bigquery'
    
    logger.info(f"Using multiplier ({data_source}): {multiplier:.2f} for {e} {current_hour:02d}:00")
    
    results = {
      'keywords_updated': 0,
      'current_hour': current_hour,
      'current_day': current_day,
      'multiplier': multiplier,
      'data_source': data_source
    }
    
    # Get all campaigns (using cache if available)
    campaigns = self.api.get_campaigns()
    
    # Collect all keyword updates for batch processing (Optimization: Guide 8)
    keyword_updates = []
    
    for campaign in campaigns:
      # Get keywords for this campaign (no cache for iterative fetching)
      keywords = self.api.get_keywords(campaign_id=campaign.campaign_id, use_cache=False)
      
      for keyword in keywords:
        # Store base bid if not stored yet
        keyword_id = keyword.keyword_id
        if keyword_id not in self.base_bids:
          self.base_bids[keyword_id] = keyword.bid
        
        base_bid = self.base_bids[keyword_id]
        new_bid = base_bid * multiplier
        
        # Apply bid caps
        min_bid = self.config.get('bid_optimization.min_bid', 0.25)
        max_bid = self.config.get('bid_optimization.max_bid', 5.0)
        new_bid = max(min_bid, min(max_bid, new_bid))
        new_bid = round(new_bid, 2)
        
        # Only update if there's a meaningful change
        if abs(new_bid - keyword.bid) > 0.01:
          reason = f"Data-driven dayparting: {current_hour:02d}:00 ({multiplier:.2f}x) for campaign {campaign.name}"
          self.audit.log(
            'INTELLIGENT_DAYPARTING',
            'KEYWORD',
            keyword_id,
            f"${keyword.bid:.2f}",
            f"${new_bid:.2f}",
            reason,
            dry_run
          )
          
          keyword_updates.append({
            'keywordId': int(keyword_id),
            'bid': new_bid
          })
    
    # Apply batch updates (Optimized: Guide 8)
    if keyword_updates and not dry_run:
        batch_results = self.api.batch_update_keywords(keyword_updates)
        results['keywords_updated'] = batch_results['success']
    elif dry_run:
        results['keywords_updated'] = len(keyword_updates)
    
    elapsed = time.time() - start_time
    logger.info(f"Intelligent dayparting applied: {results['keywords_updated']} keywords updated in {elapsed:.2f}s.")
    results['execution_time_seconds'] = round(elapsed, 2)
    return results
  
  def _fetch_optimal_multiplier(self, day_of_week: int, hour: int) -> Optional[float]:
    """Fetch optimal bid multiplier from BigQuery based on historical performance"""
    try:
      # Assuming self.bigquery_client is a wrapper around the actual BigQuery client
      query = f"""
      SELECT 
        modifier
      FROM `{self.bigquery_client.dataset_ref}.hourly_bid_modifiers`
      WHERE day_of_week = {day_of_week}
        AND hour = {hour}
        AND recommended = TRUE
      ORDER BY total_conversions DESC, avg_acos ASC
      LIMIT 1
      """
      
      logger.debug(f"Fetching multiplier from BigQuery for day={day_of_week}, hour={hour}")
      
      query_job = self.bigquery_client.client.query(query)
      results = list(query_job.result())
      
      if results:
        modifier = float(results[0]['modifier'])
        return modifier
      else:
        logger.debug(f"No BigQuery data for day={value}, hour={e}")
        return None
        
    except Exception as e:
      logger.error(f"Error fetching multiplier from BigQuery: {e}")
      logger.debug(traceback.format_exc())
      return None
  
  def apply_dayparting(self, dry_run: bool = False) -> Dict:
    """Apply simple config-based dayparting bid adjustments"""
    start_time = time.time()
    logger.info("=== Applying Config-Based Dayparting ===")
    
    if not self.config.get('dayparting.enabled', False):
      logger.info("Dayparting is disabled in config")
      return {}
    
    # Get timezone from config (Optimized: Guide 4)
    timezone_str = self.config.get('dayparting.timezone', 'US/Pacific')
    
    if pytz:
      try:
        tz = pytz.timezone(timezone_str)
        current_time = datetime.now(tz)
        logger.info(f"Using timezone: {e}")
      except Exception as e:
        logger.warning(f"Invalid timezone \'{timezone_str}\', using UTC: {e}")
        current_time = datetime.now(pytz.utc)
        timezone_str = 'UTC'
    else:
      current_time = datetime.now()
      logger.warning("pytz not available, using server timezone (UTC)")
      timezone_str = 'UTC'
    
    current_hour = current_time.hour
    current_day = current_time.strftime('%A').upper()
    
    # Get multiplier for current hour
    multiplier = self._get_multiplier(current_hour, current_day)
    
    logger.info(f"Current time ({value}): {e} {current_hour:02d}:00, Multiplier: {multiplier:.2f}")
    
    results = {
      'keywords_updated': 0,
      'current_hour': current_hour,
      'current_day': current_day,
      'multiplier': multiplier,
      'data_source': 'config'
    }
    
    # Get all keywords (using an expensive call, but necessary here)
    keywords = self.api.get_keywords()
    keyword_updates = []
    
    for keyword in keywords:
      # Store base bid if not stored
      if keyword.keyword_id not in self.base_bids:
        self.base_bids[keyword.keyword_id] = keyword.bid
      
      base_bid = self.base_bids[keyword.keyword_id]
      new_bid = base_bid * multiplier
      
      # Apply bid caps
      min_bid = self.config.get('bid_optimization.min_bid', 0.25)
      max_bid = self.config.get('bid_optimization.max_bid', 5.0)
      new_bid = max(min_bid, min(max_bid, new_bid))
      new_bid = round(new_bid, 2)
      
      if abs(new_bid - keyword.bid) > 0.01:
        reason = f"Config dayparting: {day_name} {current_hour:02d}:00 ({multiplier:.2f}x)"
        self.audit.log(
          'DAYPARTING_ADJUSTMENT',
          'KEYWORD',
          keyword.keyword_id,
          f"${keyword.bid:.2f}",
          f"${new_bid:.2f}",
          reason,
          dry_run
        )
        
        keyword_updates.append({
            'keywordId': int(keyword.keyword_id),
            'bid': new_bid
        })
    
    # Apply batch updates (Optimized: Guide 8)
    if keyword_updates and not dry_run:
        batch_results = self.api.batch_update_keywords(keyword_updates)
        results['keywords_updated'] = batch_results['success']
    elif dry_run:
        results['keywords_updated'] = len(keyword_updates)
    
    elapsed = time.time() - start_time
    logger.info(f"Config-based dayparting applied: {results['keywords_updated']} keywords updated in {elapsed:.2f}s.")
    results['execution_time_seconds'] = round(elapsed, 2)
    return results
  
  def _get_multiplier(self, hour: int, day: str) -> float:
    """Get bid multiplier for specific hour and day"""
    # Get day-specific multipliers
    day_multipliers = self.config.get('dayparting.day_multipliers', {})
    day_multiplier = day_multipliers.get(day, 1.0)
    
    # Get hour-specific multipliers
    hour_multipliers = self.config.get('dayparting.hour_multipliers', {})
    # Use hour as string key from config, convert to int for safer lookup
    hour_multiplier = hour_multipliers.get(str(hour), 1.0)
    
    # Combined multiplier
    combined = day_multiplier * hour_multiplier
    
    # Clamp to reasonable range
    min_mult = self.config.get('dayparting.min_multiplier', 0.4)
    max_mult = self.config.get('dayparting.max_multiplier', 1.8)
    
    return max(min_mult, min(max_mult, combined))


class CampaignManager:
  """Campaign activation/deactivation based on performance"""
  
  def __init__(self, config: Config, api: AmazonAdsAPI, audit_logger: AuditLogger):
    self.config = config
    self.api = api
    self.audit = audit_logger
  
  def manage_campaigns(self, dry_run: bool = False) -> Dict:
    """Activate/deactivate campaigns based on ACOS with performance timing"""
    start_time = time.time()
    logger.info("=== Managing Campaigns ===")
    
    results = {
      'campaigns_activated': 0,
      'campaigns_paused': 0,
      'no_change': 0,
      'campaigns_analyzed': 0,
      'campaigns_with_metrics': 0,
      'total_spend': 0.0,
      'total_sales': 0.0,
      'average_acos': 0.0,
      'budget_changes': 0,
      'campaigns': []
    }
    
    # Use parallel report processing if needed, but here a single campaign report is fine
    report_id = self.api.create_report(
      'campaigns',
      ['campaignId', 'impressions', 'clicks', 'cost', 
       'attributedSales14d', 'attributedConversions14d']
    )
    
    if not report_id:
      logger.error("Failed to create campaign report")
      return results
    
    report_url = self.api.wait_for_report(report_id)
    if not report_url:
      logger.error("Failed to get report data URL")
      return results
    
    report_data = self.api.download_report(report_url)
    
    # Get current campaigns (using cache)
    campaigns = self.api.get_campaigns()
    campaign_map = {
      c.campaign_id: c
      for c in campaigns
      if c.campaign_id and (c.state or '').lower() != 'archived'
    }
    
    results['campaigns_analyzed'] = len(campaign_map)

    analyzed_campaign_ids: Set[str] = set()
    campaign_details = []
    
    acos_threshold = self.config.get('campaign_management.acos_threshold', 0.45)
    min_spend = self.config.get('campaign_management.min_spend', 20.0)
    
    campaign_updates = []
    
    for row in report_data:
      campaign_id_raw = row.get('campaignId')
      if campaign_id_raw is None:
        continue

      campaign_id = str(campaign_id_raw)
      if campaign_id not in campaign_map:
        continue

      campaign = campaign_map[campaign_id]

      analyzed_campaign_ids.add(campaign_id)
      
      cost = float(row.get('cost', 0) or 0)
      sales = float(row.get('attributedSales14d', 0) or 0)
      
      # Track aggregated metrics for dashboard reporting
      results['total_spend'] += cost
      results['total_sales'] += sales
      
      # Skip if not enough data
      if cost < min_spend:
        results['no_change'] += 1
        continue

      acos = (cost / sales) if sales > 0 else float('inf')
      
      impressions = int(row.get('impressions', 0) or 0)
      clicks = int(row.get('clicks', 0) or 0)
      conversions = int(row.get('attributedConversions14d', 0) or 0)
      
      # Collect campaign details for dashboard
      current_campaign_detail = {
        'campaign_id': campaign_id,
        'campaign_name': campaign.name,
        'status': campaign.state,
        'spend': cost,
        'sales': sales,
        'acos': acos,
        'impressions': impressions,
        'clicks': clicks,
        'conversions': conversions,
        'daily_budget': campaign.daily_budget,
        'changes_made': 0
      }
      campaign_details.append(current_campaign_detail)

      new_state = None
      reason = None

      # Determine action
      if acos < acos_threshold and campaign.state != 'enabled':
        # Activate campaign
        new_state = 'enabled'
        reason = f"ACOS {acos:.1%} below threshold {acos_threshold:.1%}"
        results['campaigns_activated'] += 1
      
      elif acos > acos_threshold and campaign.state == 'enabled':
        # Pause campaign
        new_state = 'paused'
        reason = f"ACOS {acos:.1%} above threshold {acos_threshold:.1%}"
        results['campaigns_paused'] += 1
      
      else:
        results['no_change'] += 1
        continue
      
      # Log and collect update
      self.audit.log(
        'CAMPAIGN_STATE_UPDATE',
        'CAMPAIGN',
        campaign_id,
        campaign.state,
        new_state,
        reason,
        dry_run
      )
      
      campaign_updates.append({
          'campaignId': int(campaign_id),
          'state': new_state
      })
      
      current_campaign_detail['changes_made'] = 1
      current_campaign_detail['status'] = new_state
      
    # Apply campaign state updates
    if campaign_updates and not dry_run:
      logger.info(f"Applying {len(campaign_updates)} campaign state updates...")
      for update in campaign_updates:
          # Note: Campaign updates are not batched by Amazon API in the same way as keywords
          # The loop above collects the audit, the call below applies the change one-by-one (using the update_campaign method)
          self.api.update_campaign(str(update['campaignId']), {'state': update['state']})
      
    results['campaigns_with_metrics'] = len(analyzed_campaign_ids)
    results['budget_changes'] = results['campaigns_activated'] + results['campaigns_paused'] # Reflect state change
    
    if results['total_sales'] > 0:
      results['average_acos'] = results['total_spend'] / results['total_sales']
    else:
      results['average_acos'] = 0.0
    
    # Sort campaigns by spend and add to results for dashboard
    campaign_details.sort(key=lambda x: x['spend'], reverse=True)
    results['campaigns'] = campaign_details
    
    logger.info(f"Collected {len(campaign_details)} campaign details for dashboard")

    elapsed = time.time() - start_time
    logger.info(f"Campaign management complete in {elapsed:.2f}s.")
    results['execution_time_seconds'] = round(elapsed, 2)
    return results


class KeywordDiscovery:
  """Discover and add new keywords"""
  
  def __init__(self, config: Config, api: AmazonAdsAPI, audit_logger: AuditLogger):
    self.config = config
    self.api = api
    self.audit = audit_logger
  
  def discover_keywords(self, dry_run: bool = False) -> Dict:
    """Discover and add new keywords with performance timing (Optimized: Guide 10)"""
    start_time = time.time()
    logger.info("=== Discovering Keywords ===")
    
    results = {
      'keywords_discovered': 0,
      'keywords_added': 0,
      'search_terms_analyzed': 0
    }
    
    # Create and download Search Term Report (using parallel reporting if configured)
    report_configs = [{
        'name': 'search_terms',
        'report_type': 'targets',
        'metrics': ['campaignId', 'adGroupId', 'query', 'impressions', 'clicks', 
                    'cost', 'attributedSales14d', 'attributedConversions14d'],
        'segment': 'query'
    }]
    
    report_results = self.api.create_and_download_reports_parallel(report_configs, max_workers=1)
    report_data = report_results.get('search_terms', [])
    
    if not report_data:
      logger.error("Failed to get search term report data")
      return results
    
    # Get existing keywords to avoid duplicates (using cache)
    existing_keywords = self.api.get_keywords()
    
    # Optimized lookup structures (Optimized: Guide 10)
    existing_keyword_texts = frozenset(
      (kw.ad_group_id, kw.keyword_text.lower(), kw.match_type) 
      for kw in existing_keywords
    )
    logger.debug(f"Indexed {len(existing_keyword_texts)} existing keyword combinations for fast lookup.")
    
    # Analyze search terms
    min_clicks = self.config.get('keyword_discovery.min_clicks', 5)
    max_acos = self.config.get('keyword_discovery.max_acos', 0.40)
    
    new_keywords_to_add = []
    
    for row in report_data:
      results['search_terms_analyzed'] += 1
      query = str(row.get('query', '')).strip().lower()
      ad_group_id = str(row.get('adGroupId', ''))
      campaign_id = str(row.get('campaignId', ''))
      
      if not query or not ad_group_id or not campaign_id:
        continue
      
      # Calculate metrics
      clicks = int(row.get('clicks', 0) or 0)
      cost = float(row.get('cost', 0) or 0)
      sales = float(row.get('attributedSales14d', 0) or 0)
      
      if clicks < min_clicks:
        continue
      
      acos = (cost / sales) if sales > 0 else float('inf')
      
      if acos > max_acos:
        continue
      
      # Check if already exists (Optimized: Guide 10)
      if (ad_group_id, query, 'exact') in existing_keyword_texts:
        continue
      
      results['keywords_discovered'] += 1
      
      # Prepare keyword for addition
      suggested_bid = self.config.get('keyword_discovery.initial_bid', 0.75)
      
      new_keywords_to_add.append({
        'campaignId': int(campaign_id),
        'adGroupId': int(ad_group_id),
        'keywordText': query,
        'matchType': 'exact',
        'state': 'enabled',
        'bid': suggested_bid
      })
      
      self.audit.log(
        'KEYWORD_DISCOVERY',
        'KEYWORD',
        'NEW',
        '',
        query,
        f"Added from search term: {clicks} clicks, ACOS {acos:.1%}",
        dry_run
      )
    
    # Add keywords in batches (Optimized: Guide 8)
    if new_keywords_to_add and not dry_run:
      batch_size = 100
      for i in range(0, len(new_keywords_to_add), batch_size):
        batch = new_keywords_to_add[i:i+batch_size]
        created_ids = self.api.create_keywords(batch)
        results['keywords_added'] += len(created_ids)
    elif dry_run:
      results['keywords_added'] = len(new_keywords_to_add)
    
    elapsed = time.time() - start_time
    logger.info(f"Keyword discovery complete in {elapsed:.2f}s.")
    results['execution_time_seconds'] = round(elapsed, 2)
    return results


class NegativeKeywordManager:
  """Manage negative keywords"""
  
  def __init__(self, config: Config, api: AmazonAdsAPI, audit_logger: AuditLogger):
    self.config = config
    self.api = api
    self.audit = audit_logger
  
  def add_negative_keywords(self, dry_run: bool = False) -> Dict:
    """Add poor-performing keywords as negatives"""
    start_time = time.time()
    logger.info("=== Managing Negative Keywords ===")
    
    results = {
      'search_terms_analyzed': 0,
      'negative_keywords_added': 0
    }
    
    # Create and download Search Term Report
    report_configs = [{
        'name': 'search_terms',
        'report_type': 'targets',
        'metrics': ['campaignId', 'adGroupId', 'query', 'impressions', 'clicks', 
                    'cost', 'attributedSales14d', 'attributedConversions14d'],
        'segment': 'query'
    }]
    
    report_results = self.api.create_and_download_reports_parallel(report_configs, max_workers=1)
    report_data = report_results.get('search_terms', [])
    
    if not report_data:
      logger.error("Failed to get search term report data")
      return results
    
    # Get existing negative keywords (API call to list all existing negatives)
    existing_negatives = self.api.get_negative_keywords()
    existing_negative_texts = {
      (str(nk.get('campaignId')), str(nk.get('keywordText', '')).lower())
      for nk in existing_negatives
    }
    logger.debug(f"Indexed {len(existing_negative_texts)} existing negative keyword combinations.")
    
    # Analyze search terms
    min_spend = self.config.get('negative_keywords.min_spend', 10.0)
    max_acos = self.config.get('negative_keywords.max_acos', 1.0)
    
    negatives_to_add = []
    
    for row in report_data:
      results['search_terms_analyzed'] += 1
      query = str(row.get('query', '')).strip().lower()
      campaign_id = str(row.get('campaignId', ''))
      
      if not query or not campaign_id:
        continue
      
      cost = float(row.get('cost', 0) or 0)
      sales = float(row.get('attributedSales14d', 0) or 0)
      
      if cost < min_spend:
        continue
      
      acos = (cost / sales) if sales > 0 else float('inf')
      
      # Check if ACOS is too high or if there are no sales and high spend
      if not (acos > max_acos or (sales <= 0 and cost >= min_spend)):
        continue
      
      # Check if already negative
      if (campaign_id, query) in existing_negative_texts:
        continue
      
      negatives_to_add.append({
        'campaignId': int(campaign_id),
        'keywordText': query,
        'matchType': 'negativePhrase', # Default to negativePhrase
        'state': 'enabled'
      })
      
      self.audit.log(
        'NEGATIVE_KEYWORD_ADD',
        'NEGATIVE_KEYWORD',
        campaign_id,
        '',
        query,
        f"Poor performer: ${cost:.2f} spend, ACOS {acos:.1%}",
        dry_run
      )
    
    # Add negative keywords in batches (Optimized: Guide 8)
    if negatives_to_add and not dry_run:
      batch_size = 100
      for i in range(0, len(negatives_to_add), batch_size):
        batch = negatives_to_add[i:i+batch_size]
        created_ids = self.api.create_negative_keywords(batch)
        results['negative_keywords_added'] += len(created_ids)
    elif dry_run:
      results['negative_keywords_added'] = len(negatives_to_add)
    
    elapsed = time.time() - start_time
    logger.info(f"Negative keyword management complete in {elapsed:.2f}s.")
    results['execution_time_seconds'] = round(elapsed, 2)
    return results


# ============================================================================
# MAIN AUTOMATION ORCHESTRATOR
# ============================================================================

class PPCAutomation:
  """Main automation orchestrator with comprehensive error handling"""
  
  def __init__(self, config_path: str, profile_id: str, dry_run: bool = False, bigquery_client=None):
    self.config = Config(config_path)
    self.profile_id = profile_id
    self.dry_run = dry_run
    self.bigquery_client = bigquery_client
    
    # Check if Google Secret Manager is configured
    gcp_project_id = self.config.get('google_cloud.project_id')
    secret_id = self.config.get('google_cloud.secret_id')
    
    if gcp_project_id and secret_id:
      logger.info("Google Secret Manager configured - fetching credentials...")
      try:
        credentials = fetch_credentials_from_secret_manager(gcp_project_id, secret_id)
        
        # Set credentials as environment variables for AmazonAdsAPI to use
        os.environ['AMAZON_CLIENT_ID'] = credentials['AMAZON_CLIENT_ID']
        os.environ['AMAZON_CLIENT_SECRET'] = credentials['AMAZON_CLIENT_SECRET']
        os.environ['AMAZON_REFRESH_TOKEN'] = credentials['AMAZON_REFRESH_TOKEN']
        
        # If profile_id not provided as argument, use from secret
        if not profile_id:
          self.profile_id = credentials['AMAZON_PROFILE_ID']
          logger.info(f"Using profile ID from Secret Manager: {self.profile_id}")
        
        logger.info("✅ Credentials loaded from Google Secret Manager")
        
      except Exception as e:
        logger.error(f"Failed to load credentials from Secret Manager: {e}")
        logger.info("Falling back to environment variables...")
    else:
      logger.debug("Google Secret Manager not configured, using environment variables")
    
    # Initialize API client with configurable rate limit (Optimized: Guide 1)
    region = self.config.get('api.region', 'NA')
    max_requests_per_second = self.config.get('api.max_requests_per_second', MAX_REQUESTS_PER_SECOND)
    self.api = AmazonAdsAPI(profile_id, region, max_requests_per_second=max_requests_per_second)
    
    # Initialize audit logger
    audit_output_dir = self.config.get('logging.output_dir', './logs')
    self.audit = AuditLogger(audit_output_dir)
    
    # Initialize feature modules
    self.bid_optimizer = BidOptimizer(self.config, self.api, self.audit)
    self.dayparting = DaypartingManager(self.config, self.api, self.audit, bigquery_client)
    self.campaign_manager = CampaignManager(self.config, self.api, self.audit)
    self.keyword_discovery = KeywordDiscovery(self.config, self.api, self.audit)
    self.negative_keywords = NegativeKeywordManager(self.config, self.api, self.audit)
  
  def run(self, features: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Run automation with specified features
    """
    logger.info("=" * 80)
    logger.info("AMAZON PPC AUTOMATION SUITE")
    logger.info("=" * 80)
    logger.info(f"Profile ID: {self.profile_id}")
    logger.info(f"Dry Run: {self.dry_run}")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    logger.info("=" * 80)
    
    if features is None:
      features = self.config.get('features.enabled', [])
    
    # Ensure features is a list
    if not isinstance(features, list):
      logger.warning(f"Invalid features type: {type(features).__name__}, using default features")
      features = []
    
    logger.info(f"Enabled features: {', '.join(features) if features else 'None'}")
    
    results = {}
    
    try:
      # Run each feature with error handling
      if 'bid_optimization' in features:
        try:
          results['bid_optimization'] = self.bid_optimizer.optimize(self.dry_run)
        except Exception as e:
          logger.error(f"Bid optimization failed: {e}")
          results['bid_optimization'] = {'error': str(e)}
      
      if 'dayparting' in features:
        try:
          # Use intelligent dayparting if BigQuery is available, otherwise fallback to config-based
          if self.bigquery_client and self.config.get('dayparting.use_bigquery_data', True):
            results['dayparting'] = self.dayparting.apply_intelligent_dayparting(self.dry_run)
          else:
            results['dayparting'] = self.dayparting.apply_dayparting(self.dry_run)
        except Exception as e:
          logger.error(f"Dayparting failed: {e}")
          logger.debug(traceback.format_exc())
          results['dayparting'] = {'error': str(e)}
      
      if 'campaign_management' in features:
        try:
          results['campaign_management'] = self.campaign_manager.manage_campaigns(self.dry_run)
        except Exception as e:
          logger.error(f"Campaign management failed: {e}")
          results['campaign_management'] = {'error': str(e)}
      
      if 'keyword_discovery' in features:
        try:
          results['keyword_discovery'] = self.keyword_discovery.discover_keywords(self.dry_run)
        except Exception as e:
          logger.error(f"Keyword discovery failed: {e}")
          results['keyword_discovery'] = {'error': str(e)}
      
      if 'negative_keywords' in features:
        try:
          results['negative_keywords'] = self.negative_keywords.add_negative_keywords(self.dry_run)
        except Exception as e:
          logger.error(f"Negative keywords management failed: {e}")
          results['negative_keywords'] = {'error': str(e)}
      
    except Exception as e:
      logger.error(f"Automation failed with unexpected error: {e}")
      logger.error(traceback.format_exc())
      results['error'] = str(e)
    finally:
      # Save audit trail
      try:
        self.audit.save()
      except Exception as e:
        logger.error(f"Failed to save audit trail: {e}")
    
    # Print summary
    logger.info("=" * 80)
    logger.info("AUTOMATION SUMMARY")
    logger.info("=" * 80)
    for feature, result in results.items():
      if isinstance(result, dict) and 'error' not in result:
        logger.info(f"\n{feature.upper().replace('_', ' ')}:")
        # Display key summary metrics
        metrics_to_display = [
            'execution_time_seconds', 'keywords_optimized', 'keywords_updated',
            'campaigns_activated', 'campaigns_paused', 'keywords_added', 'negative_keywords_added'
        ]
        
        for key in metrics_to_display:
            if key in result:
                value = result[key]
                logger.info(f"  {key.replace('_', ' ')}: {value}")
      elif isinstance(result, dict) and 'error' in result:
        logger.info(f"\n{feature.upper().replace('_', ' ')}: FAILED ({result['error']})")
      else:
        logger.info(f"\n{feature.upper().replace('_', ' ')}: {result}")
        
    logger.info("=" * 80)
    
    return results


# ============================================================================
# CLI
# ============================================================================

def main():
  parser = argparse.ArgumentParser(description='Amazon PPC Automation Suite')
  parser.add_argument('--config', required=True, help='Path to configuration YAML file')
  parser.add_argument('--profile-id', help='Amazon Ads Profile ID (overrides config)')
  parser.add_argument('--dry-run', action='store_true', help='Run without making actual changes')
  parser.add_argument('--features', nargs='+',
            choices=['bid_optimization', 'dayparting', 'campaign_management',
                'keyword_discovery', 'negative_keywords'],
            help='Specific features to run (default: all enabled in config)')
  parser.add_argument('--verify-connection', action='store_true',
            help='Check Amazon Ads API connectivity and exit')
  parser.add_argument('--verify-sample-size', type=int, default=5,
            help='Number of campaigns to include in verification sample (default: 5)')

  args = parser.parse_args()

  # Profile ID must be explicitly provided or available via config lookup. 
  # For simplicity here, we enforce the CLI argument if not set in environment.
  if not args.profile_id and not os.getenv("AMAZON_PROFILE_ID"):
      parser.error("The following arguments are required: --profile-id (or set AMAZON_PROFILE_ID environment variable)")

  profile_id = args.profile_id or os.getenv("AMAZON_PROFILE_ID")

  # Run automation
  automation = PPCAutomation(args.config, profile_id, args.dry_run)

  if args.verify_connection:
    verification = automation.api.verify_connection(args.verify_sample_size)
    print(json.dumps(verification, indent=2))
    if verification.get('success'):
      sys.exit(0)
    sys.exit(1)

  automation.run(args.features)



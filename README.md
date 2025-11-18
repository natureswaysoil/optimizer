# Amazon PPC Optimizer & Dashboard

A comprehensive Amazon Pay-Per-Click (PPC) automation suite with an interactive dashboard for visualizing campaign performance data.

## 🌟 Features

### Automation Features
- **Bid Optimization**: Automatically adjust bids based on performance metrics
- **Dayparting**: Time-based bid adjustments with timezone awareness
- **Campaign Management**: Activate/deactivate campaigns based on ACOS thresholds
- **Keyword Discovery**: Automatic keyword suggestions and additions
- **Negative Keyword Management**: Identify and add negative keywords
- **Data Export**: ETL pipeline to export data to Google BigQuery

### Dashboard Features
- **Real-time KPI Metrics**: Track spend, sales, ACOS, ROAS, CTR, and more
- **Performance Trends**: Visualize performance over time with interactive charts
- **Campaign Comparison**: Compare performance across campaigns
- **Keyword Analysis**: Deep dive into keyword-level performance
- **Budget Monitoring**: Track budget utilization and get recommendations
- **Interactive Filters**: Filter by date range and campaign

## 📋 Prerequisites

- Python 3.8 or higher
- Amazon Advertising API credentials (Client ID, Client Secret, Refresh Token)
- Amazon Advertising Profile ID
- (Optional) Google Cloud Project with BigQuery enabled for data storage

## 🚀 Quick Start

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/natureswaysoil/optimizer.git
cd optimizer

# Create a virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

#### Set up Amazon Ads API credentials

Export your credentials as environment variables:

```bash
export AMAZON_CLIENT_ID="amzn1.application-oa2-client.xxxxx"
export AMAZON_CLIENT_SECRET="xxxxxxxx"
export AMAZON_REFRESH_TOKEN="Atzr|IwEBxxxxxxxx"
export AMAZON_PROFILE_ID="1780498399290938"
```

Or create a `.env` file:

```bash
AMAZON_CLIENT_ID=amzn1.application-oa2-client.xxxxx
AMAZON_CLIENT_SECRET=xxxxxxxx
AMAZON_REFRESH_TOKEN=Atzr|IwEBxxxxxxxx
AMAZON_PROFILE_ID=1780498399290938
```

#### Configure the automation settings

Edit `ppc_config.yaml` to customize:
- API region (NA, EU, FE)
- Features to enable/disable
- Bid optimization parameters
- Dayparting schedules
- Budget thresholds

### 3. Verify Connection

Test your Amazon Ads API connection:

```bash
python optimizer_core.py --config ppc_config.yaml --profile-id YOUR_PROFILE_ID --verify-connection
```

### 4. Run the Dashboard

Launch the interactive dashboard:

```bash
streamlit run dashboard.py
```

The dashboard will open in your web browser at `http://localhost:8501`

## 📊 Dashboard Usage

### Data Sources

The dashboard supports two data sources:

1. **Sample Data (Demo)**: Pre-generated sample data for demonstration
2. **BigQuery**: Live data from your Google BigQuery datasets

### Using BigQuery Data

1. Run the data export feature to populate BigQuery:

```bash
python optimizer_core.py --config ppc_config.yaml --profile-id YOUR_PROFILE_ID --features data_export
```

2. In the dashboard sidebar, select "BigQuery" as the data source
3. Enter your GCP Project ID and Dataset ID
4. The dashboard will automatically load your campaign data

### Dashboard Sections

- **Key Performance Indicators**: Overview of total spend, sales, ACOS, ROAS, clicks, and conversions
- **Performance Trends**: Time-series charts showing daily trends
- **Campaign Performance**: Compare campaigns and view detailed metrics
- **Budget Management**: Monitor budget utilization and get recommendations
- **Keyword Performance**: Analyze top-performing keywords

## 🤖 Running Automation Features

### Run all enabled features

```bash
python optimizer_core.py --config ppc_config.yaml --profile-id YOUR_PROFILE_ID
```

### Run specific features

```bash
python optimizer_core.py --config ppc_config.yaml --profile-id YOUR_PROFILE_ID \
  --features bid_optimization dayparting
```

### Dry run (no actual changes)

```bash
python optimizer_core.py --config ppc_config.yaml --profile-id YOUR_PROFILE_ID --dry-run
```

### Export data to BigQuery

```bash
python optimizer_core.py --config ppc_config.yaml --profile-id YOUR_PROFILE_ID \
  --features data_export
```

## 🗄️ BigQuery Setup

### 1. Enable BigQuery API

```bash
gcloud services enable bigquery.googleapis.com
```

### 2. Create Dataset

```bash
bq mk --dataset --location=US your-project-id:amazon_ads_data
```

### 3. Configure in ppc_config.yaml

```yaml
google_cloud:
  project_id: "your-project-id"
  bigquery:
    dataset_id: "amazon_ads_data"
```

### 4. Authenticate

```bash
gcloud auth application-default login
```

## 📦 BigQuery Schema

The automation exports data to three tables:

### campaign_budgets
- campaign_id (STRING)
- campaign_name (STRING)
- daily_budget (BIGNUMERIC)
- budget_type (STRING)
- state (STRING)
- targeting_type (STRING)
- fetch_timestamp (TIMESTAMP)

### campaign_performance
- report_date (DATE)
- campaignId (STRING)
- impressions (INT64)
- clicks (INT64)
- cost (BIGNUMERIC)
- attributedSales14d (BIGNUMERIC)
- attributedConversions14d (INT64)
- fetch_timestamp (TIMESTAMP)

### keyword_performance
- report_date (DATE)
- campaignId (STRING)
- adGroupId (STRING)
- keywordId (STRING)
- keywordText (STRING)
- matchType (STRING)
- impressions (INT64)
- clicks (INT64)
- cost (BIGNUMERIC)
- attributedSales14d (BIGNUMERIC)
- attributedConversions14d (INT64)
- fetch_timestamp (TIMESTAMP)

## 🔧 Configuration Options

### API Settings

```yaml
api:
  region: "NA"  # NA (North America), EU (Europe), FE (Far East)
  max_requests_per_second: 10
```

### Bid Optimization

```yaml
bid_optimization:
  enabled: true
  report_days: 7
  min_impressions: 100
  target_acos: 0.30
  max_bid_increase_percent: 20
  max_bid_decrease_percent: 50
  min_bid: 0.25
  max_bid: 5.00
```

### Dayparting

```yaml
dayparting:
  enabled: false
  timezone: "America/Los_Angeles"
  schedule:
    monday:
      - {start: 6, end: 22, multiplier: 1.0}
```

## 🔐 Security Best Practices

1. **Never commit credentials** to version control
2. Use **Google Secret Manager** for production deployments
3. Enable **2FA** on your Amazon Advertising account
4. Regularly **rotate API credentials**
5. Use **service accounts** with minimal permissions for BigQuery
6. Review **audit logs** regularly

## 📈 Monitoring & Logs

The automation creates detailed logs:

- **Application logs**: `ppc_automation_YYYYMMDD_HHMMSS.log`
- **Audit trails**: `logs/ppc_audit_YYYYMMDD_HHMMSS.csv`

Logs include:
- API requests and responses
- Bid changes and reasons
- Campaign state changes
- Errors and warnings

## 🐛 Troubleshooting

### Connection Issues

```bash
# Verify API credentials
python optimizer_core.py --config ppc_config.yaml --profile-id YOUR_PROFILE_ID --verify-connection

# Check credentials in environment
echo $AMAZON_CLIENT_ID
echo $AMAZON_PROFILE_ID
```

### BigQuery Issues

```bash
# Test BigQuery access
bq query --use_legacy_sql=false 'SELECT 1'

# Check dataset exists
bq ls --project_id=your-project-id
```

### Dashboard Issues

```bash
# Clear Streamlit cache
streamlit cache clear

# Run with debug logging
streamlit run dashboard.py --logger.level=debug
```

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Amazon Advertising API documentation
- Streamlit for the amazing dashboard framework
- Google Cloud Platform for BigQuery integration

## 📞 Support

For issues and questions:
- Open an issue on GitHub
- Check the logs for error details
- Review the Amazon Ads API documentation

## 🔄 Version History

- **v1.0.0** - Initial release with dashboard and automation features
- **v2.0.0** - Added BigQuery integration and intelligent dayparting
- **v3.0.0** - Enhanced dashboard with interactive visualizations

---

**Made with ❤️ by Nature's Way Soil**

# Amazon PPC Dashboard Preview

## Overview

The Amazon PPC Dashboard is a comprehensive web application built with Streamlit that provides real-time insights into your Amazon advertising campaigns.

## Key Features

### 📈 Key Performance Indicators (KPIs)
- **Total Spend & Sales**: Monitor your advertising investment and returns
- **Impressions & Clicks**: Track campaign visibility and engagement
- **CTR (Click-Through Rate)**: Measure ad effectiveness
- **CPC (Cost Per Click)**: Track bidding efficiency
- **ACOS (Advertising Cost of Sale)**: Monitor profitability with target indicators
- **ROAS (Return on Ad Spend)**: Track revenue multiplier
- **Conversions**: Count total orders generated

### 📊 Performance Trends
Interactive time-series visualizations showing:
- Spend vs Sales over time
- ACOS trends with target thresholds
- Clicks and Impressions volume
- ROAS trends

### 🎯 Campaign Performance
- Side-by-side campaign comparison
- Detailed metrics table with:
  - Campaign names and states
  - Performance metrics (Impressions, Clicks, Spend, Sales)
  - Calculated KPIs (CTR, CPC, ACOS, ROAS)
- Sortable and filterable data views

### 💰 Budget Management
- Budget utilization tracking (last 7 days)
- Visual comparison of budget vs actual spend
- Automated recommendations:
  - ⚠️ Campaigns near/over budget
  - 💡 Campaigns under-utilizing budget
- Utilization percentage calculations

### 🔑 Keyword Performance
- Top 20 keywords by spend
- Keyword performance scatter plot (ACOS vs Spend)
- Match type categorization (Exact, Phrase, Broad)
- Detailed keyword metrics table
- Bid optimization insights

## Data Sources

### 1. Sample Data Mode (Demo)
- Pre-generated realistic data for 5 campaigns
- 30 days of historical performance
- 10 sample keywords across different match types
- Perfect for testing and demonstrations

### 2. BigQuery Integration
- Live data from Google BigQuery
- Configurable project and dataset
- Automatic data refresh every 5 minutes
- Supports three data tables:
  - `campaign_budgets`: Campaign settings and budgets
  - `campaign_performance`: Daily performance metrics
  - `keyword_performance`: Keyword-level analytics

## Interactive Features

### Date Range Filtering
- Select custom date ranges
- View performance for specific periods
- Compare different time windows

### Responsive Design
- Wide layout optimized for data visualization
- Color-coded metrics:
  - 🟢 Green: Good performance (ACOS < 30%)
  - 🟡 Yellow: Moderate (ACOS 30-50%)
  - 🔴 Red: Needs attention (ACOS > 50%)

### Custom Styling
- Amazon brand colors (#ff9900, #232f3e)
- Professional metric cards
- Clean, modern interface
- Print-friendly reports

## How to Use

1. **Launch the Dashboard**:
   ```bash
   streamlit run dashboard.py
   ```

2. **Configure Data Source** (Sidebar):
   - Choose "Sample Data" for demo
   - Choose "BigQuery" for live data
   - Enter BigQuery credentials if needed

3. **Select Date Range**:
   - Use the date picker in the sidebar
   - Default: Last 7 days

4. **Explore Metrics**:
   - Scroll through different sections
   - Hover over charts for detailed tooltips
   - Click table headers to sort
   - Download data as CSV (future feature)

## Dashboard Sections

### Section 1: Key Performance Indicators
5-column layout showing critical metrics at a glance

### Section 2: Performance Trends
4-panel chart showing:
- Financial performance (spend/sales)
- Efficiency metrics (ACOS)
- Volume metrics (impressions/clicks)
- Profitability (ROAS)

### Section 3: Campaign Performance
- Horizontal bar chart comparing campaigns
- Detailed data table with all metrics
- Formatted currency and percentages

### Section 4: Budget Management
- Budget utilization visualization
- Overlay bar chart (budget vs spend)
- Actionable recommendations

### Section 5: Keyword Performance
- Top keywords bar chart
- ACOS vs Spend scatter plot
- Keyword details table with match types

## Technical Details

### Built With
- **Streamlit**: Web application framework
- **Pandas**: Data manipulation
- **Plotly**: Interactive visualizations
- **Python 3.8+**: Core language

### Performance
- Cached data loading (5-minute TTL)
- Responsive charts
- Fast filtering and sorting
- Optimized for datasets with 1000+ campaigns

### Browser Support
- Chrome (recommended)
- Firefox
- Safari
- Edge

## Data Refresh

- **Sample Data**: Instant, no refresh needed
- **BigQuery**: Auto-refresh every 5 minutes via caching
- Manual refresh: Click "R" in browser or use Streamlit menu

## Future Enhancements

- [ ] Export to CSV/Excel
- [ ] Email alerts for budget overruns
- [ ] Campaign performance predictions
- [ ] A/B testing insights
- [ ] Competitor analysis
- [ ] Mobile-responsive design
- [ ] Custom dashboard widgets
- [ ] Scheduled reports

## Screenshot Locations

The dashboard generates live, interactive visualizations. To see it in action:
1. Run `streamlit run dashboard.py`
2. Open http://localhost:8501 in your browser
3. Explore the interactive features

---

**Note**: This dashboard is designed to work seamlessly with the optimizer_core.py automation script. Run the data_export feature to populate BigQuery with your Amazon PPC data, then visualize it in real-time with this dashboard.

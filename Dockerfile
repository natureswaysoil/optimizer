# Dockerfile for Amazon PPC Dashboard
# Build: docker build -t amazon-ppc-dashboard .
# Run: docker run -p 8501:8501 -e GCP_PROJECT_ID=your-project amazon-ppc-dashboard

FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY dashboard.py .
COPY ppc_config.yaml .
COPY optimizer_core.py .

# Create necessary directories
RUN mkdir -p logs

# Expose port (Cloud Run uses PORT env variable, default to 8080)
EXPOSE 8080

# Health check (uses PORT env variable, default to 8080)
HEALTHCHECK CMD curl --fail http://localhost:${PORT:-8080}/_stcore/health || exit 1

# Set environment variables
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# Run dashboard
# Cloud Run sets PORT environment variable, default to 8080 if not set
CMD streamlit run dashboard.py --server.port=${PORT:-8080} --server.address=0.0.0.0

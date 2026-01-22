# Dockerfile for dbt Magellan Web UI
# Build: docker build -t dbt-magellan -f importer/web/Dockerfile .
# Run:   docker run -p 8080:8080 \
#          -v $(pwd)/.env:/app/.env \
#          -v $(pwd)/output:/app/output \
#          dbt-magellan
#
# License (Migration Workflow):
#   Add MAGELLAN_LICENSE_EMAIL and MAGELLAN_LICENSE_KEY to .env
#   Temporary bypass: MAGELLAN_LICENSE_BYPASS=true

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Terraform (for deployment functionality)
ARG TERRAFORM_VERSION=1.9.8
RUN curl -fsSL https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_amd64.zip -o terraform.zip \
    && unzip terraform.zip \
    && mv terraform /usr/local/bin/ \
    && rm terraform.zip

# Copy requirements first for better caching
COPY importer/requirements.txt /app/importer/requirements.txt
RUN pip install --no-cache-dir -r /app/importer/requirements.txt

# Copy the entire importer package
COPY importer/ /app/importer/

# Copy supporting files
COPY schemas/ /app/schemas/
COPY modules/ /app/modules/
COPY main.tf /app/main.tf
COPY variables.tf /app/variables.tf
COPY outputs.tf /app/outputs.tf
COPY providers.tf /app/providers.tf

# Create directories for output and state
RUN mkdir -p /app/output /app/deployments

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8080

# Default command - run the web UI
# Host 0.0.0.0 allows connections from outside the container
CMD ["python", "-m", "importer.web", "--host", "0.0.0.0", "--port", "8080", "--no-open"]

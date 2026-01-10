# Custom MLflow image with PostgreSQL and S3 support
# Based on official MLflow image
ARG MLFLOW_VERSION=3.8.1
FROM ghcr.io/mlflow/mlflow:v${MLFLOW_VERSION}

# Install PostgreSQL driver and S3 support
# Versions pinned for reproducibility and security
RUN pip install --no-cache-dir \
    psycopg2-binary==2.9.11 \
    boto3==1.42.25

# MLflow server runs on port 5000 by default
EXPOSE 5000

# Default command - can be overridden
CMD ["mlflow", "server", "--host", "0.0.0.0", "--port", "5000"]

FROM python:3.12-slim

WORKDIR /usr/app

# Install git (useful if we need to pull dbt packages)
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# Copy requirements.txt from the repository root context
COPY requirements.txt .

# Install all project dependencies (includes dbt, great_expectations, deltalake, pandas, etc.)
RUN pip install --no-cache-dir -r requirements.txt

# Set profiles directory to the mounted dbt folder
ENV DBT_PROFILES_DIR=/usr/app/dbt_project

ENTRYPOINT ["dbt"]

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (ravenhelm-contracts from Forgejo PyPI via BuildKit netrc secret).
COPY requirements.txt .
RUN --mount=type=secret,id=forgejo_netrc,target=/root/.netrc,required=false \
    pip install --no-cache-dir \
    --trusted-host hrafngud.ravenmask.net \
    --extra-index-url http://hrafngud.ravenmask.net:3300/api/packages/nate/pypi/simple/ \
    -r requirements.txt

# Copy application
COPY . .

# Run migrations and start server
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port 8000"]

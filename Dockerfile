FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

# Copy source code
COPY mcpspider/ ./mcpspider/

# Default: run MCP server
ENTRYPOINT ["python", "-m", "mcpspider"]
CMD ["server"]

# MCPScout - AI-powered intelligence platform

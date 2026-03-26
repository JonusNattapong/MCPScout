FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml README.md ./
COPY mcpspider/ ./mcpspider/
RUN pip install --no-cache-dir .

# Copy source code
COPY __init__.py __main__.py cli.py ./
COPY crawler/ ./crawler/
COPY search/ ./search/
COPY social/ ./social/
COPY mcp_server/ ./mcp_server/
COPY summarizer/ ./summarizer/
COPY utils/ ./utils/
COPY tests/ ./tests/

# Create directory for cache and data
RUN mkdir -p /app/data

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Default: run MCP server
ENTRYPOINT ["python", "-m", "__main__"]
CMD ["server"]

# MCPSearch - AI-powered intelligence platform

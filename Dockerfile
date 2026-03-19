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
COPY __init__.py __main__.py cli.py ./
COPY crawler/ ./crawler/
COPY search/ ./search/
COPY social/ ./social/
COPY mcp_server/ ./mcp_server/
COPY summarizer/ ./summarizer/
COPY utils/ ./utils/

# Default: run MCP server
ENTRYPOINT ["python", "-m", "__main__"]
CMD ["server"]

# MCPScout - AI-powered intelligence platform

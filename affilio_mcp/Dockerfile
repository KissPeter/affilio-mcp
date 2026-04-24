FROM python:3.11-slim

# Create app directory
WORKDIR /app

# Install system dependencies required for Pillow and other packages
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libjpeg-dev zlib1g-dev libpng-dev bash \
    && rm -rf /var/lib/apt/lists/*

# Copy the redirect context (build context expected to be the `redirect/` folder)
# and install only the MCP service requirements (isolated)
COPY . /app

# Install python deps
RUN pip install --no-cache-dir -r affilio_mcp/requirements.txt &&  rm -f  affilio_mcp/requirements.txt

# Create an unprivileged user and set permissions
RUN groupadd -g 1001 affilio && useradd -u 1001 -g affilio -s /sbin/nologin -M affilio \
    && chown -R affilio:affilio /app

# Expose port
EXPOSE 8000

# Healthcheck: ensure the internal HTTP health endpoint responds
HEALTHCHECK --interval=60s --timeout=10s --start-period=10s --retries=3 \
  CMD bash -c 'printf "GET /health HTTP/1.0\nHost:localhost\n\n\n" > /dev/tcp/127.0.0.1/8000; exit $?;'

# Default command: run with Gunicorn using Uvicorn worker for ASGI support.
# Use 2 worker processes and 4 threads per worker as requested.
# Run as non-root user for improved security.
USER affilio
CMD ["gunicorn", "affilio_mcp.server:app", "-k", "uvicorn.workers.UvicornWorker", "--workers", "2", "--threads", "4", "--bind", "0.0.0.0:8000"]

# =============================================================================
# SUME Dashboard — Dockerfile
# Multi-stage build: dependencies → production
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Build dependencies
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

# System deps for weasyprint (pango, cairo, gdk-pixbuf)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    libcairo2-dev \
    libglib2.0-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Install Python deps into a virtual env for clean copy
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ---------------------------------------------------------------------------
# Stage 2: Production image
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS production

# Runtime system deps for weasyprint (smaller set)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libcairo2 \
    libglib2.0-0 \
    fontconfig \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual env from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# App user (non-root)
RUN groupadd -r sume && useradd -r -g sume -d /app -s /sbin/nologin sume

WORKDIR /app

# Copy application code
COPY src/ src/
COPY templates/ templates/
COPY config.yaml .
COPY pyproject.toml .

# Streamlit config
RUN mkdir -p .streamlit && \
    echo '[theme]\nbase = "light"\nprimaryColor = "#00A94F"\nbackgroundColor = "#FFFFFF"\nsecondaryBackgroundColor = "#f0fdf4"\ntextColor = "#212121"\nfont = "sans serif"\n\n[server]\nheadless = true\nport = 8504\nenableCORS = false\nenableXsrfProtection = true' > .streamlit/config.toml

# Create directories for data, reports, logs
RUN mkdir -p data reports logs && \
    chown -R sume:sume /app

USER sume

# Expose Streamlit port
EXPOSE 8504

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8504/_stcore/health')" || exit 1

# Run Streamlit
ENTRYPOINT ["streamlit", "run", "src/dashboard/app.py", \
    "--server.headless", "true", \
    "--server.port", "8504", \
    "--server.address", "0.0.0.0", \
    "--browser.gatherUsageStats", "false"]

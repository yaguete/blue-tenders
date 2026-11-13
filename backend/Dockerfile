FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl tzdata \
 && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.9.5 /uv /bin/uv

ADD https://github.com/aptible/supercronic/releases/download/v0.2.33/supercronic-linux-amd64 /tmp/supercronic
RUN echo "feefa310da569c81b99e1027b86b27b51e6ee9ab647747b49099645120cfc671  /tmp/supercronic" | sha256sum -c - \
 && mv /tmp/supercronic /usr/local/bin/supercronic \
 && chmod +x /usr/local/bin/supercronic

WORKDIR /srv
COPY backend/pyproject.toml backend/uv.lock ./backend/
RUN cd backend && uv sync --frozen --no-dev
COPY backend ./backend
COPY config ./config
WORKDIR /srv/backend
CMD ["/srv/backend/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]

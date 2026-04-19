FROM python:3.11-alpine

LABEL org.opencontainers.image.title="Traefik Manager" \
      org.opencontainers.image.description="Web UI to manage Traefik routes, middlewares, and services" \
      org.opencontainers.image.url="https://github.com/chr0nzz/traefik-manager" \
      org.opencontainers.image.source="https://github.com/chr0nzz/traefik-manager" \
      org.opencontainers.image.licenses="GPL-3.0"

RUN apk add --no-cache curl

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY . .

RUN mkdir -p /app/config /app/backups /app/templates /app/static/icons

ENV CERT_RESOLVER=cloudflare
ENV DOMAINS=example.com
ENV TRAEFIK_API_URL=http://traefik:8080

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:5000/ || exit 1

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--log-level", "info", "app:app"]

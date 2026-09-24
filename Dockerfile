FROM python:3.11-alpine

LABEL org.opencontainers.image.title="Traefik Manager" \
      org.opencontainers.image.description="Web UI to manage Traefik routes, middlewares, and services" \
      org.opencontainers.image.url="https://github.com/chr0nzz/traefik-manager" \
      org.opencontainers.image.source="https://github.com/chr0nzz/traefik-manager" \
      org.opencontainers.image.licenses="GPL-3.0"

RUN apk add --no-cache curl tar git tzdata su-exec

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY . .

RUN pybabel compile -d locale -D messages --statistics

RUN mkdir -p /app/config /app/backups /app/templates /app/static/icons \
             /app/static/vendor/monaco /app/static/vendor/fonts/inter \
             /app/static/vendor/fonts/jetbrains-mono \
             /app/static/vendor/phosphor

# Every download below goes through scripts/fetch-asset.sh, which fails on an HTTP error
# instead of saving the error page, and refuses anything whose SHA-256 is not the one recorded
# in scripts/vendor-assets.sha256. This binary is executed during the build, so it matters most.
RUN /app/scripts/fetch-asset.sh \
    "https://github.com/tailwindlabs/tailwindcss/releases/download/v3.4.17/tailwindcss-linux-x64" \
    /usr/local/bin/tailwindcss \
    && chmod +x /usr/local/bin/tailwindcss

RUN /app/scripts/fetch-asset.sh --tar-xz "https://registry.npmjs.org/@phosphor-icons/web/-/web-2.1.1.tgz" /tmp \
    && for w in regular bold fill thin light duotone; do \
         cat /tmp/package/src/$w/style.css; \
       done \
       | sed 's|url("./|url("./phosphor/|g' \
       > /app/static/vendor/phosphor.css \
    && cp /tmp/package/src/*/Phosphor*.woff2 /app/static/vendor/phosphor/ \
    && cp /tmp/package/src/*/Phosphor*.woff /app/static/vendor/phosphor/ \
    && rm -rf /tmp/package

RUN /app/scripts/fetch-asset.sh "https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js" /app/static/vendor/qrcode.min.js

RUN /app/scripts/fetch-asset.sh "https://cdn.jsdelivr.net/npm/@dagrejs/dagre@3.1.1/dist/dagre.min.js" /app/static/vendor/dagre.min.js

RUN /app/scripts/fetch-asset.sh --tar-xz "https://registry.npmjs.org/monaco-editor/-/monaco-editor-0.52.0.tgz" /tmp \
    && mv /tmp/package/min/vs /app/static/vendor/monaco/vs \
    && rm -rf /tmp/package

RUN mkdir -p /app/static/vendor/monaco-themes \
    && /app/scripts/fetch-asset.sh "https://cdn.jsdelivr.net/npm/monaco-themes@0.4.4/themes/GitHub%20Light.json" "/app/static/vendor/monaco-themes/GitHub Light.json" \
    && /app/scripts/fetch-asset.sh "https://cdn.jsdelivr.net/npm/monaco-themes@0.4.4/themes/GitHub%20Dark.json" "/app/static/vendor/monaco-themes/GitHub Dark.json"

RUN /app/scripts/fetch-asset.sh --tar-xz "https://registry.npmjs.org/@fontsource/inter/-/inter-5.1.1.tgz" /tmp \
    && cp /tmp/package/index.css /app/static/vendor/fonts/inter.css \
    && sed -i \
        -e "s|url('./files/|url('./inter/|g" \
        -e 's|url("./files/|url("./inter/|g' \
        -e "s|url(./files/|url(./inter/|g" \
        /app/static/vendor/fonts/inter.css \
    && cp /tmp/package/files/* /app/static/vendor/fonts/inter/ \
    && rm -rf /tmp/package

RUN /app/scripts/fetch-asset.sh --tar-xz "https://registry.npmjs.org/@fontsource/jetbrains-mono/-/jetbrains-mono-5.1.0.tgz" /tmp \
    && cp /tmp/package/index.css /app/static/vendor/fonts/jetbrains-mono.css \
    && sed -i \
        -e "s|url('./files/|url('./jetbrains-mono/|g" \
        -e 's|url("./files/|url("./jetbrains-mono/|g' \
        -e "s|url(./files/|url(./jetbrains-mono/|g" \
        /app/static/vendor/fonts/jetbrains-mono.css \
    && cp /tmp/package/files/* /app/static/vendor/fonts/jetbrains-mono/ \
    && rm -rf /tmp/package

RUN /app/scripts/fetch-asset.sh --tar-xz "https://registry.npmjs.org/country-flag-emoji-polyfill/-/country-flag-emoji-polyfill-0.1.10.tgz" /tmp \
    && cp /tmp/package/dist/TwemojiCountryFlags.woff2 /app/static/vendor/fonts/ \
    && cp /tmp/package/LICENSE.md /app/static/vendor/fonts/TwemojiCountryFlags-LICENSE.md \
    && rm -rf /tmp/package

RUN tailwindcss -c /app/tailwind.config.js \
    -i /app/static/css/tailwind.input.css \
    -o /app/static/css/tailwind.css --minify

ENV CERT_RESOLVER=cloudflare
ENV DOMAINS=example.com
ENV TRAEFIK_API_URL=http://traefik:8080

EXPOSE 5000

ENV HOME=/tmp

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:5000/ || exit 1

RUN chmod +x /app/scripts/docker-entrypoint.sh
ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]
CMD ["gunicorn", "--config", "/app/gunicorn.conf.py", "app:app"]

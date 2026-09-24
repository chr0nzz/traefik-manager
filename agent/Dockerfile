FROM golang:1.25-alpine AS builder

WORKDIR /build

COPY go.mod ./
COPY *.go ./
RUN go mod tidy && CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o tma .

FROM alpine:3.21

RUN apk add --no-cache git ca-certificates curl tzdata su-exec

RUN mkdir -p /app/config /app/backups

COPY --from=builder /build/tma /usr/local/bin/tma
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 8090

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8090/health || exit 1

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["tma"]

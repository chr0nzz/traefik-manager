# Middlewares Tab

The **Middlewares** tab manages all middleware definitions stored in `dynamic.yml`. Middlewares can be attached to HTTP routes to add auth, rate limiting, redirects, header injection, and more.

## What it shows

- Middleware name and type
- Live status from the Traefik API (enabled / warning / error)
- Protocol badge (HTTP / TCP)
- Edit and delete controls

## Creating a middleware

Click **Add Middleware** in the top bar. Two fields:

| Field | Description |
|---|---|
| Name | Unique identifier - referenced in routes as `name@file` |
| Template | Pick a preset or choose Custom to write raw YAML |
| Configuration | YAML body for the middleware (auto-filled when a template is chosen) |

### Available templates

| Category | Templates |
|---|---|
| Auth | Basic Auth, Digest Auth, Forward Auth, Forward Auth (Authentik), Forward Auth (Authelia) |
| Security | IP Allow List, IP Allow List (Private Ranges), Rate Limit, Secure Headers, CORS Headers |
| Routing | Redirect to HTTPS, Redirect Regex, Strip Prefix, Add Prefix, Replace Path |
| Advanced | Gzip Compress, Retry, Circuit Breaker, Buffering, Middleware Chain, In-Flight Limit |

## Editing a middleware

Click the pencil icon on any middleware card.

## Attaching a middleware to a route

When creating or editing a route, enter middleware names in the **Middlewares** field as a comma-separated list, e.g. `auth@file, redirect-https@file`. The `@file` suffix tells Traefik the middleware is defined in the file provider.

## How it works

Middleware definitions are written to `dynamic.yml` under `http.middlewares`. traefik-manager reads the live status for each from the Traefik API (`/api/http/middlewares`).

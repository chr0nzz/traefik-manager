# API Reference

Traefik Manager exposes a REST API used by the web UI and the official mobile app. The API reference is built into every TM instance and served with live Try It support.

## Accessing the API reference

Open the API reference directly from your own Traefik Manager instance:

```
https://your-tm-url/api
```

Or click the **API** button in the TM navbar (toggle visibility in **Settings → Interface → Navbar**).

This gives you:
- Full endpoint documentation
- Live **Try It** - send real requests to your instance directly from the browser
- Authentication pre-configured to your instance


## Authentication

Two methods are supported:

**API key** *(recommended)* - generate a key in **Settings → Authentication → API Keys** and send it as a header:
```
X-Api-Key: your-api-key
```

**Session cookie** - log in via the web UI. The browser session is used automatically for requests from the same origin.

## CSRF

State-changing endpoints (POST / DELETE) require a CSRF token when using session auth. Send it as `X-CSRF-Token`. API key requests skip CSRF entirely.

## Base URL

All endpoints are relative to your TM base URL:
```
https://your-tm-url/api/...
```

## OpenAPI spec

The raw OpenAPI 3.1 spec is available at:
```
https://your-tm-url/openapi.yaml
```

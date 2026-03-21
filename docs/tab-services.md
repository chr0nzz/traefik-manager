# Services Tab

The **Services** tab shows all services registered in Traefik across every provider - `@file`, `@docker`, `@kubernetes`, and so on. It is a read-only view pulled live from the Traefik API.

## What it shows

- Service name and provider (e.g. `my-app@file`, `nginx@docker`)
- Status badge: Success, Warning, or Error
- HTTP, TCP, and UDP services

## Filtering

- **Search** - filter by service name
- **Status buttons** - show All / Success / Warnings / Errors

## Requirements

No volume mounts required. Data is read directly from the Traefik API (`/api/http/services`, `/api/tcp/services`, `/api/udp/services`). The Traefik API URL must be configured in **Settings → Connection**.

## Notes

- This tab is always visible - it cannot be disabled
- Use the **Routes** tab to create and manage routes stored in `dynamic.yml`

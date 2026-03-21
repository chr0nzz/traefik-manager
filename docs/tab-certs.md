# Certs Tab

The **Certs** tab shows TLS certificates managed by Traefik's ACME resolver, read from `acme.json`.

## What it shows

- Domain (main domain + SANs)
- ACME resolver name
- Expiry date (parsed from the certificate)

Certificates are **read-only** - they are issued and renewed automatically by Traefik. To revoke or force a renewal, do so via your Traefik configuration.

## Enabling the tab

### During setup wizard
Toggle **Certs** on in the "Optional monitoring" step.

### After setup
Go to **Settings → Optional Tabs** and enable Certs.

## Requirements

Mount your Traefik `acme.json` into the traefik-manager container at `/app/acme.json`:

```yaml
volumes:
  - /path/to/traefik/acme.json:/app/acme.json:ro
```

> **Tip:** Mount it read-only (`:ro`) - traefik-manager never writes to `acme.json`.

If the file is not mounted, the Certs tab will display an error message with the exact volume line to add to your compose file.

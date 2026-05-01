# Certs Tab

The **Certs** tab shows TLS certificates managed by Traefik, read from two sources:

- **ACME (`acme.json`)** - certificates issued and renewed automatically by Traefik's ACME resolvers (Let's Encrypt, ZeroSSL, etc.)
- **File-based (`tls.yml`)** - PEM certificates declared under `tls.certificates` in any loaded dynamic config file

## What it shows

- Domain (main domain + SANs)
- ACME resolver name (or `file` for PEM certs)
- Expiry date (parsed from the certificate)
- Source cert file path (for PEM certs)

Certificates are **read-only** - they are issued and renewed automatically by Traefik. To revoke or force a renewal, do so via your Traefik configuration.

## Enabling the tab

### During setup wizard
Toggle **Certs** on in the "Optional monitoring" step.

### After setup
Go to **Settings → System Monitoring** and enable Certs.

## Requirements

### ACME certificates (acme.json)

Point traefik-manager at your `acme.json` via the `ACME_JSON_PATH` environment variable (default: `/app/acme.json`).

:::tabs
== Docker / Podman
```yaml
volumes:
  - /path/to/traefik/acme.json:/app/acme.json:ro
```

== Linux (systemd)
```ini
Environment=ACME_JSON_PATH=/etc/traefik/acme.json
```
:::

> **Tip:** Mount it read-only (`:ro`) - traefik-manager never writes to `acme.json`.

### File-based certificates (tls.yml)

Traefik Manager automatically scans all loaded dynamic config files for `tls.certificates` entries and reads each `certFile` PEM directly.

Example `tls.yml`:
```yaml
tls:
  certificates:
    - certFile: /etc/traefik/certs/chain.pem
      keyFile: /etc/traefik/certs/key.pem
```

::: warning Cert files must be mounted into the TM container
The `certFile` paths in your dynamic config refer to paths **inside the Traefik container**. For Traefik Manager to read those files and display the certificates, the same cert files must also be mounted into the **Traefik Manager container** at the same path.

```yaml
# docker-compose.yml
services:
  traefik-manager:
    volumes:
      - /etc/traefik/certs:/etc/traefik/certs:ro  # same path as in tls.yml
```

If the files are not mounted into TM, the Certs tab will not show file-based certificates even though Traefik itself serves them correctly.
:::

On native Linux installs, make sure Traefik Manager has read access to the cert files:
```bash
chmod o+r /etc/traefik/certs/chain.pem
```

If `acme.json` is not found, the tab shows an error with the path it expected and the env var to set. File-based certs are still shown if available.

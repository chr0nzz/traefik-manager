# Certs Tab

The **Certs** tab shows TLS certificates managed by Traefik, read from two sources:

- **ACME (`acme.json`)** - certificates issued and renewed automatically by Traefik's ACME resolvers (Let's Encrypt, ZeroSSL, etc.)
- **File-based (`tls.yml`)** - PEM certificates declared under `tls.certificates` in any loaded dynamic config file

## What it shows

A summary strip counts your certificates, how many expire within 7 and within 30 days, and when the next one expires. Each card below shows the main domain with the issuing resolver underneath (`file` for PEM certs), the first two additional SANs with a copy button each (the rest behind a `+N more`), and the expiry date with the days remaining coloured green, amber under 30 days, and red under 7.

Certificates are **read-only** - they are issued and renewed automatically by Traefik. To revoke or force a renewal, do so via your Traefik configuration.

## Certificates nothing uses

Traefik renews every certificate in `acme.json` whether or not a router still needs it, and it never removes the section belonging to a resolver you have deleted. Both show up here.

| Flag | Meaning |
|---|---|
| `unused` | No router on this server serves a domain this certificate covers |
| `no resolver` | The certificate resolver that issued it is not in the static config any more |

A wildcard certificate counts as used when a router serves any name it covers, `*.example.com` for `app.example.com`. A certificate pre-issued through `tls.domains` on a route counts as used even though no rule names it, and so does the `defaultGeneratedCert` in `tls.stores`. Routes you have switched off still count, because turning one back on with its certificate deleted means a fresh issue.

`unused` is only ever shown when the picture is complete. If Traefik's API did not answer for every protocol, a config file failed to parse, a router matches hosts by regular expression, or a catch-all router exists that any certificate could serve, the summary strip says so and no certificate is called unused. `no resolver` needs the static config mounted; without it no resolver is judged.

## Enabling the tab

### During setup wizard
Toggle **Certificates** on in the Monitoring step.

### After setup
Go to **Settings - System Monitoring - Tab Visibility** and enable Certs.

## Requirements

### ACME certificates (acme.json)

Point traefik-manager at your `acme.json` with the `ACME_JSON_PATH` environment variable (default: `/app/acme.json`), or with the acme.json Path field under **Settings - System Monitoring - File Paths**, which wins over the env var. Mount it read-only (`:ro`) - traefik-manager never writes to `acme.json`.

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

#### Several storage files

Traefik writes **one storage file per certificate resolver**, so a setup with more than one resolver has more than one file. `ACME_JSON_PATH` accepts a comma-separated list:

:::tabs
== Docker / Podman
```yaml
environment:
  - ACME_JSON_PATH=/letsencrypt/ovh.json,/letsencrypt/lan.json
volumes:
  - /path/to/traefik/letsencrypt:/letsencrypt:ro
```

== Linux (systemd)
```ini
Environment=ACME_JSON_PATH=/etc/traefik/ovh.json,/etc/traefik/lan.json
```
:::

Or point it at a **directory**, and every `.json` file inside is read:

```yaml
environment:
  - ACME_JSON_PATH=/letsencrypt
```

Certificates from every file are listed together, each showing the resolver that issued it. A file that is missing or unreadable is reported without hiding the certificates from the others.

This works the same on the Host and on a [remote agent](agent.md).

### File-based certificates (tls.yml)

Traefik Manager scans all loaded dynamic config files for `tls.certificates` entries and reads each `certFile` PEM directly. This is done on the Host only - a [remote agent](agent.md) reports its ACME certificates.

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

If no certificates can be read at all, the tab shows an "acme.json not mounted" panel with the volume line to add to your compose file. File-based certs, when readable, are shown instead.

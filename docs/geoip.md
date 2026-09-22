# IP Geolocation

Traefik Manager can resolve client IP addresses to countries and show them in the [Logs](tab-logs.md) and [CrowdSec](tab-crowdsec.md) tabs - a country flag on every IP, plus a **Geography** panel with a shaded **world map** and a ranked country list, either of which you can click to filter.

::: tip Privacy
All lookups happen **on the server against a local database**. IP addresses are never sent to any third-party geolocation API, there are no per-request network calls, and it keeps working offline. Only the database file itself is downloaded, from DB-IP.
:::

## Enabling it

The setup wizard offers it as **GeoIP lookup** on the **Monitoring** step. Afterwards:

1. Open **Settings → Interface → General → Geolocation** and turn on **IP geolocation**.
2. TM downloads the country database automatically. Use **Download** / **Update** to refresh it at any time.

Open the Logs or CrowdSec tab and IPs will show their country.

## What you get

- **Logs tab** - a flag next to each client IP, the country in the log detail panel, and a Geography panel pairing the world map with a ranked country list. Click a country on either to filter the log entries.
- **CrowdSec tab** - a country flag on every alert row, and the same Geography panel showing where the attacking sources are. Click a country to filter the whole tab. CrowdSec usually resolves the country itself, so the host database is consulted only when no alert carries one, and never for the decisions list.

Remote agents are covered automatically - the Host resolves the addresses in the data it fetches from each agent, so no agent-side configuration is needed.

## The database

By default TM uses the free **[DB-IP Lite](https://db-ip.com) IP-to-Country** database:

- **License:** CC-BY 4.0 - the only requirement is the visible "IP Geolocation by DB-IP" credit shown in the app.
- **Size:** ~4 MB, country-level.
- **Updates:** published monthly. TM checks at startup and once a day after that, and re-downloads if the database is missing or more than 35 days old. **Download / Update** in Settings does it on demand.
- **Download:** keyless, no account needed.

The database lives in a `geoip/` folder next to `manager.yml` - `/app/config/geoip/dbip-country-lite.mmdb` by default. The location follows `SETTINGS_PATH`, not the `CONFIG_DIR` environment variable.

### Using your own database

Point the `GEOIP_DB_PATH` environment variable at any MaxMind DB format (`.mmdb`) file - a MaxMind GeoLite2 or a paid DB-IP database, for example - and TM reads that instead:

```yaml
environment:
  - GEOIP_DB_PATH=/data/GeoLite2-Country.mmdb
volumes:
  - /path/to/GeoLite2-Country.mmdb:/data/GeoLite2-Country.mmdb:ro
```

`GEOIP_DB_PATH` only changes which file TM reads. The DB-IP auto-download still targets that same path, so once the file is more than 35 days old - or you click Download / Update - your custom database is overwritten with DB-IP Lite. Mount it read-only to prevent that.

## Settings reference

| Setting | Where | Description |
|---|---|---|
| IP geolocation | Settings → Interface → General → Geolocation, or `geoip_enabled` in `manager.yml` | Master on/off toggle (off by default) |
| `GEOIP_DB_PATH` | Environment variable, or `geoip_db_path` in `manager.yml` | Path to a custom `.mmdb`; overrides the built-in DB-IP download |

## Notes

- Private and internal IP ranges are not in the country database, so they show no flag.
- Geolocation is country-level. City-level accuracy is not needed for the map and keeps the database small.
- Turning the feature off removes the flags, the map and the Geography panel on the next refresh.

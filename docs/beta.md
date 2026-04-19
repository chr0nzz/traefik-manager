# Beta Program

Traefik Manager v1 is currently in beta. This page explains how to join, test, and report issues.

---

## What's in beta

- Static Config editor - view and edit `traefik.yml` directly from **Settings**
- Restart method support - socket proxy, poison pill, and direct socket
- UI and stability improvements across all tabs

---

## Fresh install (beta)

Run the beta installer:

```bash
curl -fsSL https://get-traefik.xyzlab.dev/beta | bash
```

This uses the `:beta` image tag automatically.

---

## Upgrade an existing install

Use the tool below to upgrade your current `docker-compose.yml` to the beta version. Paste your compose file, choose a restart method, and click **Upgrade**.

<ComposeUpgrader />

After copying the upgraded compose, apply it:

```bash
docker compose pull
docker compose up -d
```

---

## Enable the Static Config editor

The Static Config editor requires a read-write `traefik.yml` mount and a restart method. The Compose Upgrader above handles this automatically. For manual setup see [Enabling Static Config](./static-enable.md).

---

## Roll back

To go back to the stable release, change the image tag in your compose file:

```yaml
image: ghcr.io/chr0nzz/traefik-manager:latest
```

Then pull and restart:

```bash
docker compose pull
docker compose up -d
```

---

## Report issues

Found a bug or have feedback? Open an issue on [GitHub](https://github.com/chr0nzz/traefik-manager/issues).

# Beta

Beta tracks the `dev` branch, so it carries the next release before it ships. You get fixes early, and bugs get caught before they reach everyone else. Docker installs use the `:beta` image, Linux service installs follow the `dev` branch.

---

## Switch to beta

### With tm

If the stack was installed with [tm](tm-cli.md), one command covers every install type, including the Linux service:

```bash
tm update --channel beta
```

`tm` remembers the channel, so a plain `tm update` keeps you where you are. `tm status` shows which channel an install is on, which is worth including in a bug report.

Agents are separate installs: run the same command on each agent host you want on beta.

### By hand

Docker, editing your `docker-compose.yml`:

```yaml
image: ghcr.io/chr0nzz/traefik-manager:beta
```

```bash
docker compose pull traefik-manager && docker compose up -d traefik-manager
```

Agents have a `:beta` tag too (`ghcr.io/chr0nzz/traefik-manager-agent:beta`). Keep the Host and its agents on the same channel.

Linux service, from the install directory:

```bash
sudo -u traefik-manager git -C /opt/traefik-manager fetch origin dev
sudo -u traefik-manager git -C /opt/traefik-manager checkout dev
sudo -u traefik-manager git -C /opt/traefik-manager pull
sudo systemctl restart traefik-manager
```

Run the git commands as the user that owns the install directory, or git refuses with a dubious ownership error and any file it writes ends up owned by root.

---

## Roll back

| Install | How |
|---|---|
| tm | `tm update --channel stable` |
| Docker by hand | set the image back to `:latest`, then pull and up again |
| Linux service | the same git commands with `main` in place of `dev` |

Your `manager.yml` and backups are untouched by the switch, in either direction.

---

## Before you switch

`dev` is where fixes land the day they are written, so a beta image can be newer than any testing it has had:

- Take a backup first, from **Settings - Backups**, or copy your config directory
- Expect the occasional rough edge. Anything that reaches `:latest` has been through a release
- A new setting written by a beta may not be understood by the older `:latest` build if you roll back
- There is no beta build of the standalone agent binary, which ships only in releases. Run the agent with Docker to put it on beta

---

## Reporting

The useful bug report says what you did, what happened, and what you expected. Beyond that:

- **Logs from the moment it broke** - `docker compose logs traefik-manager` - are worth more than a description of the error
- **Your version**, from **Settings - About**, and your channel, from `tm status`
- **Your setup** where it is relevant: reverse proxy in front, agents, OIDC provider, CrowdSec

[Open an issue](https://github.com/chr0nzz/traefik-manager/issues/new/choose), or [start a discussion](https://github.com/chr0nzz/traefik-manager/discussions) if you are unsure whether something is a bug.

---

## Testing a specific fix

A fix often lands on `dev` and needs confirming before release: pull `:beta` and try the exact thing that failed. That confirmation is the difference between a fix that is believed to work and one that is known to.

Switching over for one test and rolling back afterwards is a perfectly good way to help.

---

## Mobile app

| Platform | Beta |
|---|---|
| iPhone, iPad and Apple silicon Mac | [Join the TestFlight beta](https://testflight.apple.com/join/zjT2P6JN) |

Install the [TestFlight](https://apps.apple.com/app/testflight/id899247664) app, open the link and tap **Accept**. TestFlight updates the app when a new beta build is out. Send feedback from TestFlight or [open an issue](https://github.com/chr0nzz/traefik-manager-mobile/issues).

To leave the beta, install [Traefik Manager from the App Store](https://apps.apple.com/us/app/traefik-manager/id6826725061).

---

## What is in it

The [release notes](https://github.com/chr0nzz/traefik-manager/releases) cover each release. For what is on `dev` right now, the [commit history](https://github.com/chr0nzz/traefik-manager/commits/dev) is the source of truth.

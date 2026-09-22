# Contributing to Traefik Manager

Thanks for your interest in contributing. This guide covers everything you need to get started.

---

## Table of Contents

- [Reporting bugs](#reporting-bugs)
- [Suggesting features](#suggesting-features)
- [Submitting a pull request](#submitting-a-pull-request)
- [Running locally](#running-locally)
- [Tests](#tests)
- [Project structure](#project-structure)
- [Code style](#code-style)
- [Branch guide](#branch-guide)

---

## Reporting bugs

Please use the [Bug Report](.github/ISSUE_TEMPLATE/bug_report.yml) issue template. Include:

- Traefik Manager version
- How you're running it (Docker, Podman, native Linux)
- Traefik version
- Steps to reproduce
- What you expected vs what happened

For **security vulnerabilities**, do not open a public issue - see [SECURITY.md](.github/SECURITY.md).

---

## Suggesting features

Start an [Idea discussion](https://github.com/chr0nzz/traefik-manager/discussions/new?category=ideas) before writing any code. This lets us discuss it first and avoids wasted effort if it doesn't fit the project's direction. Ideas become an issue once they are planned.

---

## Submitting a pull request

> [!IMPORTANT]
> **All pull requests target `dev`.** Never open a PR against `main` - it only moves when a release is cut. PRs against `main` will be asked to retarget.

1. Fork the repo and create your branch from `dev`.
2. Keep PRs focused - one fix or feature per PR.
3. For anything beyond a small bug fix, open an issue first so we can align on approach.
4. Test your changes with a real Traefik instance if possible.
5. Update the relevant docs page in `docs/` if your change affects user-facing behaviour.
6. Open the PR against `dev` (see [Branch guide](#branch-guide)). GitHub preselects `main` - change the base branch dropdown when creating the PR.

---

## Running locally

### Requirements

- Python 3.11+
- A running Traefik instance (or the Traefik API accessible at some URL)
- Docker (optional, for building the image)

### Setup

```bash
git clone https://github.com/chr0nzz/traefik-manager.git
cd traefik-manager
git checkout dev

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Configuration

Create a config directory and a minimal dynamic config file:

```bash
mkdir -p config backups
touch config/dynamic.yml
```

### Environment variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TRAEFIK_API_URL` | URL of the Traefik API | `http://traefik:8080` |
| `CONFIG_PATH` | Path to your Traefik dynamic config | `config/dynamic.yml` |
| `COOKIE_SECURE` | Set `true` when running behind HTTPS | `false` |
| `RESTART_METHOD` | How TM restarts Traefik (`proxy`, `poison-pill`, `socket`) | `proxy` |
| `STATIC_CONFIG_PATH` | Path to `traefik.yml` to enable the Static Config Editor | - |

These are the ones you need to run it locally. The full list is in the [Environment Variables](https://traefik-manager.xyzlab.dev/env-vars.html) reference.

### Run

```bash
TRAEFIK_API_URL=http://your-traefik:8080 \
CONFIG_PATH=config/dynamic.yml \
python3 app.py
```

The UI is available at `http://localhost:5000`. There is no username - login is password-only. On first run a random password is generated and printed to the console with an `AUTO-GENERATED PASSWORD` banner; use that, then the setup wizard prompts you to set a permanent one. Set `ADMIN_PASSWORD` to choose it yourself instead.

### Docker build

```bash
docker build -t traefik-manager:local .
docker run -p 5000:5000 \
  -e TRAEFIK_API_URL=http://your-traefik:8080 \
  -v $(pwd)/config:/app/config \
  traefik-manager:local
```

### Tests

```bash
pip install -r requirements-dev.txt

pytest                                # Python suite
make lint                             # ruff - undefined names are a hard failure
cd agent && go test ./...             # agent suite
```

The suite runs against a temporary config directory - it never touches a real Traefik or your own config. Please run it before opening a pull request, and add a test when you change the config write path (`/save`, middleware saves, backups). Tests assert the YAML that actually lands on disk, not just the HTTP status, because that is where config-corrupting bugs show up.

---

## Project structure

```
app.py                        # Flask app, routes, CLI
core/                         # Shared logic - settings, config I/O, auth, git, Traefik, agents
tests/                        # pytest suite - run before opening a PR
requirements.txt              # Python dependencies
Dockerfile
docker-compose.yml
agent/                        # TMA - the Go agent for remote servers
templates/
    index.html                # Main SPA shell
    sections/                 # Navbar and stats bar
    tabs/                     # One file per tab (routes, middlewares, dashboard, etc.)
    modals/                   # Route, middleware, settings and other modals
static/
    css/app.css               # All custom styles
    js/                       # Application JS, one file per area
    vendor/                   # Third-party JS/CSS (Monaco, dagre, fonts)
docs/                         # VitePress documentation site
    .vitepress/
        config.ts             # Nav, sidebar, theme config
        theme/                # Custom theme components and styles
    *.md                      # One page per doc
.github/
    workflows/
        docker.yml            # Builds and pushes Docker images on tag/branch push
        tests.yml             # pytest + coverage + ruff, and the Go agent build/vet/test
        pr-base-check.yml     # Fails a PR opened against main instead of dev
        release-binaries.yml  # Builds agent binaries on a published release
wrangler.toml                 # Cloudflare Pages builds and deploys the docs site
```

> [!NOTE]
> **`app.py` still holds the route handlers.** Shared logic lives in `core/`, and the JavaScript is fully split into `static/js/`, but the Flask routes are still in `app.py`. Moving them into blueprints needs an app-factory restructure and has not been done. See the [Development guide](https://traefik-manager.xyzlab.dev/development.html) for the `core/` module graph and its conventions.

---

## Code style

- **Python:** no strict formatter enforced, but follow the existing style - 4-space indent, single quotes, type hints on new functions.
- **HTML/JS:** keep changes within the existing Tailwind + vanilla JS patterns. No new frameworks.
- **CSS:** add rules to `static/css/app.css`. No inline styles in HTML unless they're dynamic values.
- **No comments:** don't add explanatory comments to code - use clear names instead. The existing codebase follows this convention.
- **No dead code:** don't leave commented-out blocks or unused variables.
- **Commit messages:** one imperative subject line with a conventional prefix (`fix:`, `feat:`, `docs:`, `build:`, `ci:`, `chore:`, `test:`), with the issue or discussion in brackets when there is one. No body - the reasoning belongs in the release notes.

---

## Branch guide

| Branch | Purpose | Accepts PRs? |
|--------|---------|--------------|
| `dev` | Active development - all features, bug fixes, and docs changes for the next release | **Yes - every PR targets `dev`** |
| `main` | Release branch - only moves when a version is tagged | **No - never open PRs here** |

Everything lands on `dev` first - features, bug fixes, and docs alike. When `dev` is ready for release it is merged to `main` and tagged, which publishes the Docker images. Nothing else touches `main`: a PR merged there would sit unreleased, drift out of sync with `dev`, and risk being clobbered by the next release merge.

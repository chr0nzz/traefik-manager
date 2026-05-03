# Contributing to Traefik Manager

Thanks for your interest in contributing. This guide covers everything you need to get started.

---

## Table of Contents

- [Reporting bugs](#reporting-bugs)
- [Suggesting features](#suggesting-features)
- [Submitting a pull request](#submitting-a-pull-request)
- [Running locally](#running-locally)
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

Open a [Feature Request](.github/ISSUE_TEMPLATE/feature_request.yml) issue before writing any code. This lets us discuss the idea first and avoids wasted effort if it doesn't fit the project's direction.

---

## Submitting a pull request

1. Fork the repo and create your branch from `v1` (for beta/active development) or `main` (for docs or stable fixes).
2. Keep PRs focused - one fix or feature per PR.
3. For anything beyond a small bug fix, open an issue first so we can align on approach.
4. Test your changes with a real Traefik instance if possible.
5. Update the relevant docs page in `docs/` if your change affects user-facing behaviour.
6. Open the PR against the correct branch (see [Branch guide](#branch-guide)).

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
git checkout v1

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

### Run

```bash
TRAEFIK_API_URL=http://your-traefik:8080 \
CONFIG_PATH=config/dynamic.yml \
python3 app.py
```

The UI is available at `http://localhost:5000`. Default credentials on first run: `admin` / `admin`.

### Docker build

```bash
docker build -t traefik-manager:local .
docker run -p 5000:5000 \
  -e TRAEFIK_API_URL=http://your-traefik:8080 \
  -v $(pwd)/config:/app/config \
  traefik-manager:local
```

---

## Project structure

```
app.py                        # Main Flask application - all routes and business logic
requirements.txt              # Python dependencies
Dockerfile
docker-compose.yml
templates/
    index.html                # Main SPA shell
    sections/                 # Navbar, stats bar, modals
    tabs/                     # One file per tab (routes, middlewares, dashboard, etc.)
    modals/                   # Route and middleware editor modals
static/
    css/app.css               # All custom styles
    js/                       # Third-party JS (Monaco, dagre, etc.)
docs/                         # VitePress documentation site
    .vitepress/
        config.ts             # Nav, sidebar, theme config
        theme/                # Custom theme components and styles
    *.md                      # One page per doc
.github/
    workflows/
        docker.yml            # Builds and pushes Docker image on tag/branch push
        docs.yml              # Deploys VitePress docs
```

---

## Code style

- **Python:** no strict formatter enforced, but follow the existing style - 4-space indent, single quotes, type hints on new functions.
- **HTML/JS:** keep changes within the existing Tailwind + vanilla JS patterns. No new frameworks.
- **CSS:** add rules to `static/css/app.css`. No inline styles in HTML unless they're dynamic values.
- **No comments:** don't add explanatory comments to code - use clear names instead. The existing codebase follows this convention.
- **No dead code:** don't leave commented-out blocks or unused variables.

---

## Branch guide

| Branch | Purpose | PR target |
|--------|---------|-----------|
| `v1` | Active beta development - new features and bug fixes for the next release | `v1` |
| `main` | Stable - docs fixes, security patches only | `main` |

When v1 is ready for production release it will be merged to `main`. New features during that window go to `v1`.

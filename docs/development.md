# Development

How the project is laid out, how to run it locally, and what is expected of a pull request.

For bug reports and feature requests see [CONTRIBUTING.md](https://github.com/chr0nzz/traefik-manager/blob/main/CONTRIBUTING.md).

## Project layout

```
app.py                  Flask app, routes, CLI
core/                   Shared logic, one module per concern
agent/                  TMA - the Go agent for remote servers
tests/                  pytest suite
templates/
    index.html          SPA shell and side nav, plus the theme/pref bootstrap and the agent-switcher JS
    sections/           Top bar, stats bar
    tabs/               One file per tab
    modals/             Route, middleware, settings and other modals
static/
    css/app.css         Custom styles for the app shell (login.html and index.html each carry their own inline <style> block)
    css/tailwind.css    Generated from tailwind.input.css at image build - never edit it
    js/                 Application JS, one file per area
    vendor/             Third-party JS/CSS, bundled at image build
    sw.js               Service worker; openapi.yaml sits alongside it
docs/                   This VitePress site
```

### `core/`

Shared logic lives here so it can be tested directly and imported without pulling in the Flask app. The modules form an acyclic graph, and it is worth keeping it that way:

```
env -> crypto, config -> agents_store -> settings -> auth, backups, notifications,
                                                     traefik, agents_http, geoip,
                                                     crowdsec, routes_build, git
```

`certs` and `self_route` stop at `config` and never reach `settings`. `git` also pulls `agents_http` and `notifications`; `routes_build` also pulls `traefik` and, lazily, `service_ownership`. `notifications` pulls `notify_providers`, `composite_services` pulls `service_ownership`, and `monitor` and `updates` sit on top of the rest.

| Module | Owns |
|---|---|
| `env` | Environment-derived paths and constants, logger |
| `crypto` | Fernet encryption for secrets at rest |
| `config` | YAML read/write, Go-template preservation, path safety |
| `agents_store` | `agents.yml` persistence, secrets encrypted |
| `settings` | `manager.yml` load/save, settings-derived paths |
| `auth` | `login_required`, `csrf_protect`, session and API-key checks |
| `routes_build` | Turning config into route objects, and merging them back |
| `backups` | Timestamped local backups and retention |
| `git` | Git backup: repo management, commits, pushes |
| `traefik` | Read-only Traefik API client |
| `agents_http` | HTTP client for remote agents |
| `notifications` | In-app log, queueing and delivery scheduling |
| `notify_providers` | The per-destination senders behind those channels |
| `monitor` | The background check loop and its schedule |
| `updates` | Release checks for Traefik Manager and Traefik |
| `service_ownership` | The `svc::` ledger: what Traefik Manager wrote and may rewrite |
| `composite_services` | Building and merging weighted, mirroring and failover services |
| `geoip`, `crowdsec`, `certs`, `self_route` | Feature-specific helpers |

Two conventions exist because breaking them caused real bugs:

- **Import mutable module state as a module, not a name.** `CONFIG_PATHS` is rebound at runtime when a config file is created from the UI, so `from core.env import CONFIG_PATHS` captures a snapshot that never updates. Use `env.CONFIG_PATHS`.
- **Import `config` and `settings` under an alias** (`cfg_mod`, `settings_mod`). `config` and `settings` are extremely common local variable names, and a local silently shadows the module.

### `static/js/`

Classic scripts, loaded in order, no bundler and no ES modules. Over 200 functions are called from inline `onclick=` handlers in the templates, so **every top-level function must stay a global**. `init.js` holds the code that runs at load time; everything else is function declarations and self-contained state. It is loaded near the end, though not strictly last - check `templates/index.html` for the real order before assuming.

::: warning Tailwind purges what it cannot see
`tailwind.config.js` scans `templates/**/*.html` and `static/js/**/*.js`. Utility classes used only in JS-generated markup are purged if the file is not covered by those globs. Moving class-bearing markup to a new location means updating the glob - `tests/test_assets.py` fails if you forget.
:::

## Running locally

```bash
pip install -r requirements.txt
./scripts/setup-assets.sh
TRAEFIK_API_URL=http://your-traefik:8080 CONFIG_PATH=config/dynamic.yml python3 app.py
```

`static/vendor/` and `static/css/tailwind.css` are git-ignored and built at image build, so run `setup-assets.sh` once or the UI comes up unstyled. Re-run it after adding utility classes in a file Tailwind had not seen.

The UI is at `http://localhost:5000`. See [Environment Variables](env-vars.md) for the full list, and [CONTRIBUTING.md](https://github.com/chr0nzz/traefik-manager/blob/main/CONTRIBUTING.md) for the Docker build.

## Tests

```bash
pip install -r requirements-dev.txt
pytest              # Python suite
make lint           # ruff, undefined names are a hard failure
make coverage       # pytest with a coverage report
make agent-test     # go build, vet and test
make docs-dev       # this site, live
```

The suite runs against a temporary config directory and never touches a real Traefik or your own config. It runs on every pull request, along with ruff and the Go agent's build, vet and test; the coverage table lands in the workflow's job summary.

### What is covered

| Area | What it asserts |
|---|---|
| `test_routes.py` | Route saves for HTTP, TCP and UDP; backend validation; the multi-backend safeguard; the mobile client contract, including that a backend edit preserves sticky, health checks and priority; comment preservation |
| `test_presets.py` | Security-headers and streaming presets, the ownership ledger, refuse-to-overwrite |
| `test_middlewares.py` | Middleware save and delete, unrelated middlewares preserved |
| `test_backups.py` | Backups created before a write and containing the previous content |
| `test_auth.py` | Login, logout, CSRF rejection, unauthenticated access |
| `test_core_*.py` | Each `core/` module directly, including git hardening and agent secret encryption |
| `test_acme_paths.py` | Single and multiple acme storage files |
| `test_endpoints.py` | Every `url_for()` target resolves; no duplicate routes |
| `test_assets.py` | Tailwind scans every file that emits utility classes |
| `test_css.py` | No unshrinkable `min-width`/`min-height` floors in `app.css`; `resize` always paired with a scroll context |
| `test_lint.py` | No undefined names; every `core` alias in `app.py` resolves |
| `test_ui_prefs.py` | Interface preferences round-trip through settings; unknown keys are dropped |
| `test_version_sync.py` | Every version string matches `core/env.py` |
| `test_api_docs_coverage.py` | Every `/api/` route appears in `docs/api.md` and both OpenAPI copies, and the two specs are identical |
| `test_api_auth_401.py` | API paths answer an expired session with `401`, not a redirect; page routes still redirect |
| `test_api_key_csrf.py` | API keys skip CSRF, as documented |
| `test_crowdsec_mtls.py`, `test_crowdsec_scale.py` | Client-certificate auth to the LAPI; the streaming read and its fallback |
| `test_restore_static_target.py` | A static backup restores to `traefik.yml`, never over the dynamic config |
| `test_static_provider_keys.py` | Saving a provider section preserves keys the form does not manage |
| `test_no_dashes.py` | No em dashes anywhere |
| `test_i18n.py` | Language prefixes, the language setting and picker, the browser catalogue and plural mapping |
| `test_i18n_security.py` | A hostile catalogue renders as text in every template form and cannot break out of the inline catalogue |
| `test_i18n_checks.py` | The translation checks reject hostile or broken catalogues, the JS extractor reads every call, and the repository passes |
| `test_i18n_templates.py` | Every template string renders translated under a pseudo-locale, no English is left unmarked, and every `tag()` call is allowed |

The table is not exhaustive - `tests/` holds more than this. Run `pytest --collect-only -q` for the full list.

### Translations

Strings are marked with `_()`, `ngettext()` and `pgettext()` in Python and templates, and with `t()`, `tn()` and `tc()` in JavaScript. Pass plain string literals with named placeholders (`%(name)s` in Python, `{name}` in JavaScript) and keep HTML outside the translated text.

```bash
make i18n-tools     # once: installs the pinned JS parser under scripts/i18n
make i18n-extract   # rebuild locale/messages.pot and update every catalogue
make i18n-check     # every translation check CI runs
make i18n-pseudo    # pseudo-translated catalogue in /tmp/tm-pseudo-locale (OUT=dir to change)
```

In templates, a sentence stays one message even when it holds markup. Inline code, emphasis and links go in as named placeholders built with `tag()`, which only produces a short list of inline tags and refuses `on*` attributes and non-http links:

```jinja
{{ _('Leave blank to use the %(acme_json_path)s env var.', acme_json_path=tag('code', 'ACME_JSON_PATH', class_='font-mono')) }}
```

Markup `tag()` cannot build, such as a button with an `onclick`, is captured with `{% set name %}...{% endset %}` and passed the same way. Single words get a context with `pgettext('button', 'Save')`, so translators know where they appear. Text that must stay English sits in `<code>`, a `font-mono` element or an element with `translate="no"`.

In JavaScript, `t()`, `tn()` and `tc()` return plain text for `textContent`, `showToast` and attributes set through the DOM. Text that goes into HTML uses `th()`, `thn()` and `thc()`, which escape the translation and every value; a value that is markup on purpose is wrapped in `tmHtml()`. CI rejects a plain `t()` placed into HTML, a translation used as a class, id, style or input value, a helper hidden by a local variable named `t`, and a call whose values do not match its placeholders. Numbers, dates and relative times go through `tmNumber()`, `tmDate()` and `tmAgo()`, and code never compares displayed text: state lives in a data attribute. Only strings JavaScript uses are sent to the browser; the extractor marks them `Used in the browser` in `messages.pot`.

CI fails when a template shows English text that is not marked for translation, and when `messages.pot` is stale, so run `make i18n-extract` and commit the result with the change that added or reworded a string. `make i18n-check` also rejects translations that add markup, quotes, links, placeholders or invisible control characters, and a pull request from Weblate may only change `locale/<lang>/LC_MESSAGES/messages.po`. Every translation is escaped when a template renders it, so none can inject HTML. The translator side lives in [tm-locale](https://github.com/chr0nzz/tm-locale).

To find English that never reaches a catalogue, build the pseudo catalogue, copy its `eo` folder into `locale/` of a test install, add `eo` to `locale/LINGUAS` there, and pick Esperanto in Settings. Every translated string shows as accented text between `⟦` and `⟧`, so plain English on screen is a string that is not marked. Do not commit the `eo` catalogue.

### Screenshots

`scripts/screenshots/run.sh` recaptures every desktop screenshot for the docs and README from a seeded demo environment - both themes, all tabs and modals - straight into `docs/public/images/`. Run it against the beta image after visual changes and review the git diff. Details in [scripts/screenshots/README.md](https://github.com/chr0nzz/traefik-manager/tree/main/scripts/screenshots).

### Conventions

- **Assert the YAML, not the status code.** A `200` from `/save` proves nothing about what landed on disk. Load the written file and assert its structure - that is where config-corrupting bugs show up.
- **Add a test when you change the write path.** `/save`, middleware saves and backups are the code that touches someone's live proxy config.
- **A test that guards a bug should fail without the fix.** Check that it does before opening the PR.

## Pull requests

- **Target `dev`.** `main` is the released branch; a PR against it will be asked to retarget. A check enforces this.
- **One concern per PR.** Small, focused PRs get reviewed and merged quickly. A large refactor mixed with a fix is hard to review and hard to revert.
- **Say what you tested.** Especially for anything touching route or middleware saves. If you tested against a real Traefik, say which version.
- **Host and agent parity.** If a feature works on the Host it should work when a remote agent is selected. The write path is shared, but the read path often is not - check both.

### Code style

- **Python** - 4-space indent, single quotes, type hints on new functions. No formatter is enforced.
- **HTML/JS** - stay within the existing Tailwind and vanilla-JS patterns. No new frameworks.
- **CSS** - add rules to `static/css/app.css`. No inline styles unless the value is dynamic.
- **No comments.** Use clear names instead; the codebase follows this throughout.
- **No dead code.** ruff runs in CI (`ruff.toml`, pyflakes rule set) and fails on unused imports.
- **One-line commits.** An imperative subject line with a conventional prefix, referencing the issue or discussion in brackets. No body; the reasoning goes in the release notes.

## Releasing

`core/env.py` holds `APP_VERSION`, and five other files must match it:

| File | What |
|---|---|
| `core/env.py` | `APP_VERSION` - the source of truth |
| `static/sw.js` | `CACHE_NAME` - bump it or browsers serve stale assets |
| `agent/main.go` | `Version` - baked in at build time, so a stale value makes every agent report as outdated |
| `static/openapi.yaml` | `info.version` |
| `docs/public/openapi.yaml` | `info.version`, and byte-identical to the file above |
| `docs/.vitepress/config.ts` | the nav version label and its `releases/tag/` link |

`tests/test_version_sync.py` fails the build when any of them drifts, so you do not have to remember the list.

Releases are cut by merging `dev` into `main`, tagging `vX.Y.Z`, and publishing a GitHub Release. The tag push builds and pushes the Docker images; **publishing** the release builds the agent binaries, so a draft release does not produce them.

import os
import re
import time
import shutil
import secrets
import logging
import requests
from datetime import datetime, timezone, timedelta
from functools import wraps
from flask import (Flask, render_template, request, redirect,
                   url_for, flash, jsonify, abort, session)
from ruamel.yaml import YAML
from ruamel.yaml import YAML as SafeYAML
from io import StringIO

GITHUB_REPO = "chr0nzz/traefik-manager"


LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)
logger = logging.getLogger("traefik-manager")


app = Flask(__name__)

_SECRET_KEY_PATH = '/app/config/.secret_key'

def _load_or_create_secret_key() -> bytes:
    env_key = os.environ.get('SECRET_KEY', '').strip()
    if env_key:
        return env_key.encode()
    if os.path.exists(_SECRET_KEY_PATH):
        key = open(_SECRET_KEY_PATH, 'rb').read().strip()
        if len(key) >= 32:
            return key
    key = secrets.token_hex(32).encode()
    os.makedirs(os.path.dirname(_SECRET_KEY_PATH), exist_ok=True)
    with open(_SECRET_KEY_PATH, 'wb') as f:
        f.write(key)
    return key

app.secret_key = _load_or_create_secret_key()


app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
app.config['SESSION_COOKIE_HTTPONLY']    = True
app.config['SESSION_COOKIE_SAMESITE']    = 'Lax'


app.config['SESSION_COOKIE_SECURE']      = os.environ.get('COOKIE_SECURE', 'false').lower() == 'true'


INACTIVITY_TIMEOUT = int(os.environ.get('INACTIVITY_TIMEOUT_MINUTES', '120'))


yaml = YAML()
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)
yaml.width = 4096

safe_yaml = SafeYAML(typ='safe')


CONFIG_PATH   = os.environ.get('CONFIG_PATH',   '/app/config/dynamic.yml')
BACKUP_DIR    = os.environ.get('BACKUP_DIR',    '/app/backups')
SETTINGS_PATH = os.environ.get('SETTINGS_PATH', '/app/config/manager.yml')


_ALLOWED_FILE_PREFIXES = tuple(sorted(set([
    '/app/',
    os.path.dirname(os.path.abspath(CONFIG_PATH))   + '/',
    os.path.abspath(BACKUP_DIR)                     + '/',
    os.path.dirname(os.path.abspath(SETTINGS_PATH)) + '/',
])))
_ALLOWED_API_SCHEMES   = ('http://', 'https://')

def _safe_file_path(path: str) -> str:
    if not path:
        return ''
    resolved = os.path.realpath(path)
    if any(resolved.startswith(p) for p in _ALLOWED_FILE_PREFIXES):
        return resolved
    logger.warning(f"Blocked unsafe file path: {path!r}")
    return ''

def _safe_api_url(url: str) -> str:
    url = url.strip()
    if any(url.startswith(s) for s in _ALLOWED_API_SCHEMES):
        return url
    logger.warning(f"Blocked unsafe API URL: {url!r}")
    return ''


ACCESS_LOG_PATH    = '/app/logs/access.log'
ACME_JSON_PATH     = '/app/acme.json'
STATIC_CONFIG_PATH = '/app/traefik.yml'


OPTIONAL_TABS = ['docker', 'kubernetes', 'swarm', 'nomad', 'ecs', 'consulcatalog', 'redis', 'etcd', 'consul', 'zookeeper', 'http_provider', 'file_external', 'certs', 'plugins', 'logs']

def load_settings() -> dict:
    defaults = {
        'domains':              [d.strip() for d in os.environ.get('DOMAINS', 'example.com').split(',') if d.strip()] or ['example.com'],
        'cert_resolver':        os.environ.get('CERT_RESOLVER', 'cloudflare'),
        'traefik_api_url':      os.environ.get('TRAEFIK_API_URL', 'http://traefik:8080'),
        'auth_enabled':         True,
        'password_hash':        '',
        'visible_tabs':         {t: False for t in OPTIONAL_TABS},
        'must_change_password': False,
        'setup_complete':       False,
    }
    if not os.path.exists(SETTINGS_PATH):
        return defaults
    try:
        with open(SETTINGS_PATH, 'r') as f:
            data = yaml.load(f) or {}
        merged = defaults.copy()
        if 'domains' in data and isinstance(data['domains'], list):
            merged['domains'] = [str(d).strip() for d in data['domains'] if str(d).strip()]
        if 'cert_resolver' in data:
            merged['cert_resolver'] = str(data['cert_resolver']).strip()
        if 'traefik_api_url' in data:
            merged['traefik_api_url'] = _safe_api_url(str(data['traefik_api_url'])) or defaults['traefik_api_url']
        if 'auth_enabled' in data:
            merged['auth_enabled'] = bool(data['auth_enabled'])
        if 'password_hash' in data:
            merged['password_hash'] = str(data['password_hash']).strip()
        if 'visible_tabs' in data and isinstance(data['visible_tabs'], dict):
            vt = {t: False for t in OPTIONAL_TABS}
            for t in OPTIONAL_TABS:
                if t in data['visible_tabs']:
                    vt[t] = bool(data['visible_tabs'][t])
            merged['visible_tabs'] = vt
        if 'must_change_password' in data:
            merged['must_change_password'] = bool(data['must_change_password'])
        if 'setup_complete' in data:
            merged['setup_complete'] = bool(data['setup_complete'])
        else:
            # Backward-compat: existing installs with a password_hash already set
            # are treated as having completed setup so the wizard doesn't re-appear.
            if merged['password_hash']:
                merged['setup_complete'] = True
        return merged
    except Exception as e:
        logger.warning(f"Could not load manager.yml, using defaults: {e}")
        return defaults


def save_settings(domains, cert_resolver, traefik_api_url,
                  auth_enabled=True, password_hash='', visible_tabs=None,
                  must_change_password=None, setup_complete=None):
    if visible_tabs is None:
        visible_tabs = {t: False for t in OPTIONAL_TABS}
    # Preserve existing values for the new flags if callers don't supply them
    if must_change_password is None or setup_complete is None:
        _cur = load_settings()
        if must_change_password is None:
            must_change_password = _cur.get('must_change_password', False)
        if setup_complete is None:
            setup_complete = _cur.get('setup_complete', False)
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    with open(SETTINGS_PATH, 'w') as f:
        yaml.dump({
            'domains':              domains,
            'cert_resolver':        cert_resolver,
            'traefik_api_url':      traefik_api_url,
            'auth_enabled':         auth_enabled,
            'password_hash':        password_hash,
            'visible_tabs':         visible_tabs,
            'must_change_password': must_change_password,
            'setup_complete':       setup_complete,
        }, f)
    logger.info("Manager settings saved")


def _auth_enabled() -> bool:
    """
    Auth is disabled only when explicitly opted out.
    Priority: AUTH_ENABLED env var → manager.yml auth_enabled field → default True.
    Set AUTH_ENABLED=false in docker-compose if using Authentik / Traefik basicAuth.
    """
    env = os.environ.get('AUTH_ENABLED', '').strip().lower()
    if env in ('false', '0', 'no'):
        return False
    if env in ('true', '1', 'yes'):
        return True
    return load_settings().get('auth_enabled', True)


def _ensure_password():
    """Auto-generate an admin password on first run if none is configured."""
    if os.environ.get('ADMIN_PASSWORD', '').strip():
        return  # env-var password takes priority — nothing to do
    settings = load_settings()
    if settings.get('password_hash', ''):
        return  # password already stored in config
    password = secrets.token_urlsafe(16)  # 22-char URL-safe string
    logger.warning("=" * 60)
    logger.warning("  TRAEFIK MANAGER — AUTO-GENERATED PASSWORD")
    logger.warning(f"  Password: {password}")
    logger.warning("  Log in with this password, complete setup, then")
    logger.warning("  you will be prompted to set a permanent password.")
    logger.warning("=" * 60)
    save_settings(
        domains=settings['domains'],
        cert_resolver=settings['cert_resolver'],
        traefik_api_url=settings['traefik_api_url'],
        auth_enabled=settings['auth_enabled'],
        password_hash=_hash_password(password),
        visible_tabs=settings['visible_tabs'],
        must_change_password=True,
        setup_complete=False,
    )


_s = load_settings()
logger.info("===========================================")
logger.info("Starting Traefik Manager")
logger.info(f"Config Path:    {CONFIG_PATH}")
logger.info(f"Settings Path:  {SETTINGS_PATH}")
logger.info(f"Backup Dir:     {BACKUP_DIR}")
logger.info(f"Domains:        {_s['domains']}")
logger.info(f"Cert Resolver:  {_s['cert_resolver']}")
logger.info(f"Traefik API:    {_s['traefik_api_url']}")
logger.info(f"Auth Enabled:   {_auth_enabled()}")
logger.info("===========================================")

_ensure_password()


def _get_csrf_token() -> str:
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']

def _check_csrf():
    token = request.form.get('csrf_token', '') or request.headers.get('X-CSRF-Token', '')
    if request.is_json:
        token = (request.get_json(silent=True) or {}).get('csrf_token', '') or token
    expected = session.get('csrf_token', '')
    if not expected or not secrets.compare_digest(str(token), str(expected)):
        logger.warning(f"CSRF check failed from {request.remote_addr}")
        abort(403)

def csrf_protect(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method in ('POST', 'PUT', 'DELETE', 'PATCH'):
            _check_csrf()
        return f(*args, **kwargs)
    return decorated

@app.context_processor
def inject_csrf():
    return {'csrf_token': _get_csrf_token()}


def _hash_password(plaintext: str) -> str:
    import bcrypt
    return bcrypt.hashpw(plaintext.encode(), bcrypt.gensalt(rounds=12)).decode()

def _check_password(plaintext: str, hashed: str) -> bool:
    import bcrypt
    try:
        return bcrypt.checkpw(plaintext.encode(), hashed.encode())
    except Exception:
        return False

def _is_authenticated() -> bool:
    """True if auth is disabled OR if the session carries a valid auth marker."""
    if not _auth_enabled():
        return True
    return session.get('authenticated') is True

def _check_inactivity():
    """Log out the session if the user has been inactive for INACTIVITY_TIMEOUT minutes."""
    if not session.get('authenticated'):
        return
    last = session.get('last_active')
    now  = time.time()
    if last and (now - last) > INACTIVITY_TIMEOUT * 60:
        logger.info(f"Session expired due to inactivity ({INACTIVITY_TIMEOUT}m) for {request.remote_addr}")
        session.clear()
        return
    session['last_active'] = now

def login_required(f):
    """Route decorator: redirect to /login if not authenticated."""
    @wraps(f)
    def decorated(*args, **kwargs):
        _check_inactivity()
        if not _is_authenticated():
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return decorated

def _has_password_set() -> bool:

    if os.environ.get('ADMIN_PASSWORD', '').strip():
        return True
    return bool(load_settings().get('password_hash', ''))

def _get_effective_hash() -> str:
    """Return the bcrypt hash to check against. ADMIN_PASSWORD env var takes priority."""
    admin_pw = os.environ.get('ADMIN_PASSWORD', '').strip()
    if admin_pw:

        return _hash_password(admin_pw)
    return load_settings().get('password_hash', '')


@app.before_request
def log_request_info():
    logger.info(f"{request.remote_addr} → {request.method} {request.path}")


@app.after_request
def set_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options']         = 'DENY'
    response.headers['Referrer-Policy']          = 'strict-origin-when-cross-origin'
    response.headers['X-XSS-Protection']         = '1; mode=block'
    return response


@app.route('/login', methods=['GET', 'POST'])
def login():

    if not _auth_enabled():
        return redirect(url_for('index'))

    if session.get('authenticated'):
        return redirect(url_for('index'))

    settings = load_settings()
    temp_password_hint = (
        settings.get('must_change_password', False)
        and not os.environ.get('ADMIN_PASSWORD', '').strip()
    )

    error = None
    if request.method == 'POST':
        _check_csrf()
        password = request.form.get('password', '')
        pw_hash  = settings.get('password_hash', '')
        admin_pw = os.environ.get('ADMIN_PASSWORD', '').strip()

        if admin_pw:
            ok = secrets.compare_digest(password, admin_pw)
        else:
            ok = bool(pw_hash) and _check_password(password, pw_hash)

        if ok:
            session.clear()
            session.permanent = True
            session['authenticated'] = True
            session['last_active']   = time.time()
            session['login_time']    = datetime.now(timezone.utc).isoformat()
            logger.info(f"Successful login from {request.remote_addr}")

            # Redirect to the appropriate next step
            if settings.get('must_change_password', False) and not admin_pw:
                if not settings.get('setup_complete', False):
                    return redirect(url_for('setup'))
                else:
                    return redirect(url_for('force_change_password'))

            next_url = request.form.get('next') or url_for('index')
            if not next_url.startswith('/'):
                next_url = url_for('index')
            return redirect(next_url)
        else:
            import hmac as _hmac
            _hmac.compare_digest('a', 'b')
            time.sleep(0.3)
            error = 'Incorrect password.'
            logger.warning(f"Failed login attempt from {request.remote_addr}")

    next_url = request.args.get('next', '')
    return render_template('login.html', error=error, next=next_url,
                           csrf_token=_get_csrf_token(),
                           temp_password_hint=temp_password_hint)


@app.route('/setup', methods=['GET', 'POST'])
def setup():
    """Setup wizard. Accessible on first run (setup_complete=False). Requires auth when a password exists."""
    if not _auth_enabled():
        return redirect(url_for('index'))

    current = load_settings()

    # If setup is already done, go to the appropriate page
    if current.get('setup_complete', False):
        if current.get('must_change_password', False):
            return redirect(url_for('force_change_password'))
        return redirect(url_for('index'))

    # When a password exists (auto-generated or pre-configured) require login first
    if _has_password_set() and not session.get('authenticated'):
        return redirect(url_for('login'))

    # In temp-password mode the wizard skips step 4 (password is already set)
    temp_password_mode = current.get('must_change_password', False) and bool(current.get('password_hash', ''))

    defaults = {
        'domains':         current['domains'],
        'cert_resolver':   current['cert_resolver'],
        'traefik_api_url': current['traefik_api_url'],
    }

    error = None
    if request.method == 'POST':
        _check_csrf()

        domains_raw      = request.form.get('domains', '').strip()
        cert_resolver    = request.form.get('cert_resolver', '').strip()
        traefik_api_url  = request.form.get('traefik_api_url', '').strip()
        visible_tabs_raw = request.form.get('visible_tabs', '{}')
        pw               = request.form.get('password', '')
        confirm          = request.form.get('confirm', '')

        domains = [d.strip() for d in domains_raw.split(',') if d.strip()]

        if not domains:
            error = 'Enter at least one domain.'
        elif not traefik_api_url:
            error = 'Enter the Traefik API URL.'
        elif not _safe_api_url(traefik_api_url):
            error = 'Traefik API URL must start with http:// or https://'
        elif not temp_password_mode and len(pw) < 8:
            error = 'Password must be at least 8 characters.'
        elif not temp_password_mode and pw != confirm:
            error = 'Passwords do not match.'
        else:
            import json as _json
            try:
                vt_raw = _json.loads(visible_tabs_raw)
                visible_tabs = {t: bool(vt_raw.get(t, False)) for t in OPTIONAL_TABS}
            except Exception:
                visible_tabs = {t: False for t in OPTIONAL_TABS}

            pw_hash = current['password_hash'] if temp_password_mode else _hash_password(pw)
            save_settings(
                domains=domains,
                cert_resolver=cert_resolver or 'cloudflare',
                traefik_api_url=traefik_api_url,
                auth_enabled=True,
                password_hash=pw_hash,
                visible_tabs=visible_tabs,
                must_change_password=current.get('must_change_password', False),
                setup_complete=True,
            )
            logger.info(f"Setup wizard completed from {request.remote_addr}")

            if temp_password_mode:
                # Session already valid; redirect to forced password change
                return redirect(url_for('force_change_password'))

            session.clear()
            session.permanent        = True
            session['authenticated'] = True
            session['last_active']   = time.time()
            session['login_time']    = datetime.now(timezone.utc).isoformat()
            return redirect(url_for('index'))

    return render_template('login.html', setup_mode=True, error=error,
                           defaults=defaults, csrf_token=_get_csrf_token(),
                           temp_password_mode=temp_password_mode)


@app.route('/logout', methods=['POST'])
@csrf_protect
def logout():
    session.clear()
    logger.info(f"User logged out from {request.remote_addr}")
    return redirect(url_for('login'))


@app.route('/force-change-password', methods=['GET', 'POST'])
@login_required
def force_change_password():
    """Forced password change for auto-generated or CLI-reset passwords."""
    settings = load_settings()
    if not settings.get('must_change_password', False):
        return redirect(url_for('index'))

    error = None
    if request.method == 'POST':
        _check_csrf()
        new_pw  = request.form.get('new_password', '')
        confirm = request.form.get('confirm_password', '')
        if len(new_pw) < 8:
            error = 'Password must be at least 8 characters.'
        elif new_pw != confirm:
            error = 'Passwords do not match.'
        else:
            save_settings(
                domains=settings['domains'],
                cert_resolver=settings['cert_resolver'],
                traefik_api_url=settings['traefik_api_url'],
                auth_enabled=settings['auth_enabled'],
                password_hash=_hash_password(new_pw),
                visible_tabs=settings['visible_tabs'],
                must_change_password=False,
                setup_complete=True,
            )
            logger.info(f"Forced password change completed from {request.remote_addr}")
            return redirect(url_for('index'))

    return render_template('login.html', force_change_mode=True, error=error,
                           csrf_token=_get_csrf_token())


@app.cli.command('reset-password')
def reset_password_cli():
    """Generate a new temporary password, save it, and print it to stdout.

    Usage: docker exec <container> flask reset-password
    """
    password = secrets.token_urlsafe(16)
    settings = load_settings()
    save_settings(
        domains=settings['domains'],
        cert_resolver=settings['cert_resolver'],
        traefik_api_url=settings['traefik_api_url'],
        auth_enabled=settings.get('auth_enabled', True),
        password_hash=_hash_password(password),
        visible_tabs=settings['visible_tabs'],
        must_change_password=True,
        setup_complete=settings.get('setup_complete', True),
    )
    print("=" * 60)
    print("TRAEFIK MANAGER — PASSWORD RESET")
    print(f"New temporary password: {password}")
    print("You will be required to change it on next login.")
    print("=" * 60)


@app.route('/api/auth/change-password', methods=['POST'])
@csrf_protect
@login_required
def api_change_password():
    """Change password from the Settings modal. Requires current password."""
    data        = request.get_json()
    current_pw  = (data or {}).get('current_password', '')
    new_pw      = (data or {}).get('new_password', '')
    confirm_pw  = (data or {}).get('confirm_password', '')

    if len(new_pw) < 8:
        return jsonify({'error': 'New password must be at least 8 characters.'}), 400
    if new_pw != confirm_pw:
        return jsonify({'error': 'Passwords do not match.'}), 400

    settings   = load_settings()
    pw_hash    = settings.get('password_hash', '')
    admin_pw   = os.environ.get('ADMIN_PASSWORD', '').strip()

    if admin_pw:
        ok = secrets.compare_digest(current_pw, admin_pw)
    else:
        ok = bool(pw_hash) and _check_password(current_pw, pw_hash)

    if not ok:
        time.sleep(0.3)
        logger.warning(f"Failed password change attempt from {request.remote_addr}")
        return jsonify({'error': 'Current password is incorrect.'}), 403

    save_settings(
        domains=settings['domains'],
        cert_resolver=settings['cert_resolver'],
        traefik_api_url=settings['traefik_api_url'],
        auth_enabled=settings['auth_enabled'],
        password_hash=_hash_password(new_pw),
        visible_tabs=settings['visible_tabs'],
    )
    logger.info(f"Password changed successfully from {request.remote_addr}")
    return jsonify({'success': True})


@app.route('/api/auth/toggle', methods=['POST'])
@csrf_protect
@login_required
def api_auth_toggle():
    """Enable or disable built-in auth from the Settings modal."""
    data    = request.get_json()
    enabled = bool((data or {}).get('auth_enabled', True))
    settings = load_settings()
    save_settings(
        domains=settings['domains'],
        cert_resolver=settings['cert_resolver'],
        traefik_api_url=settings['traefik_api_url'],
        auth_enabled=enabled,
        password_hash=settings['password_hash'],
        visible_tabs=settings['visible_tabs'],
    )
    logger.info(f"auth_enabled set to {enabled} by {request.remote_addr}")
    return jsonify({'success': True, 'auth_enabled': enabled})


def traefik_api_get(path):
    settings = load_settings()
    base_url = settings['traefik_api_url']
    if not _safe_api_url(base_url):
        logger.error("traefik_api_url failed safety check")
        return None
    try:
        resp = requests.get(f"{base_url}{path}", timeout=3)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.debug(f"Traefik API unavailable: {e}")
    return None

@app.route('/api/traefik/overview')
@login_required
def api_overview():
    return jsonify(traefik_api_get('/api/overview') or {})

@app.route('/api/traefik/routers')
@login_required
def api_routers():
    return jsonify({
        'http': traefik_api_get('/api/http/routers') or [],
        'tcp':  traefik_api_get('/api/tcp/routers')  or [],
        'udp':  traefik_api_get('/api/udp/routers')  or [],
    })

@app.route('/api/traefik/services')
@login_required
def api_services():
    return jsonify({
        'http': traefik_api_get('/api/http/services') or [],
        'tcp':  traefik_api_get('/api/tcp/services')  or [],
        'udp':  traefik_api_get('/api/udp/services')  or [],
    })

@app.route('/api/traefik/middlewares')
@login_required
def api_middlewares():
    return jsonify({
        'http': traefik_api_get('/api/http/middlewares') or [],
        'tcp':  traefik_api_get('/api/tcp/middlewares')  or [],
    })

@app.route('/api/manager/router-names')
@login_required
def api_manager_router_names():
    """Return the set of router names managed by traefik-manager (from dynamic.yml)."""
    config = load_config()
    names = set()
    for proto in ('http', 'tcp', 'udp'):
        names.update(config.get(proto, {}).get('routers', {}).keys())
    return jsonify(list(names))


@app.route('/api/traefik/entrypoints')
@login_required
def api_entrypoints():
    return jsonify(traefik_api_get('/api/entrypoints') or [])

@app.route('/api/traefik/version')
@login_required
def api_version():
    return jsonify(traefik_api_get('/api/version') or {})

@app.route('/api/traefik/ping')
@login_required
def api_ping():
    import time as _t
    settings = load_settings()
    try:
        t0   = _t.monotonic()
        resp = requests.get(f"{settings['traefik_api_url']}/ping", timeout=3)
        ms   = round((_t.monotonic() - t0) * 1000)
        if resp.status_code == 200:
            return jsonify({'ok': True, 'latency_ms': ms})
    except Exception as e:
        logger.debug(f"Ping failed: {e}")
    return jsonify({'ok': False, 'latency_ms': None})

_cached_manager_version = None

@app.route('/api/manager/version')
@login_required
def api_manager_version():
    global _cached_manager_version
    if _cached_manager_version is None:
        try:
            resp = requests.get(
                f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
                headers={"Accept": "application/vnd.github.v3+json"},
                timeout=5
            )
            if resp.status_code == 200:
                tag = resp.json().get("tag_name", "").lstrip("v")
                if tag:
                    _cached_manager_version = tag
        except Exception:
            pass
    return jsonify({"version": _cached_manager_version or "", "repo": GITHUB_REPO})


@app.route('/api/setup/test-connection', methods=['POST'])
@login_required
def api_setup_test_connection():
    """Test a Traefik API URL during setup wizard (requires auth)."""
    settings = load_settings()
    if settings.get('setup_complete', False):
        return jsonify({'ok': False, 'error': 'Setup already complete'}), 403
    data    = request.get_json(silent=True) or {}
    raw_url = str(data.get('url', '')).strip()
    url     = _safe_api_url(raw_url)
    if not url:
        return jsonify({'ok': False, 'error': 'Invalid URL'}), 400
    try:
        resp = requests.get(f"{url}/api/version", timeout=4)
        if resp.status_code == 200:
            info = resp.json()
            return jsonify({'ok': True, 'version': info.get('Version', '?')})
        return jsonify({'ok': False, 'error': f'HTTP {resp.status_code}'})
    except Exception as e:
        return jsonify({'ok': False, 'error': 'Connection failed'})


@app.route('/api/traefik/router/<protocol>/<path:name>')
@login_required
def api_router_detail(protocol, name):
    proto = {'http': 'http', 'tcp': 'tcp', 'udp': 'udp'}.get(protocol.lower(), 'http')
    return jsonify(traefik_api_get(f'/api/{proto}/routers/{name}') or {})

@app.route('/api/traefik/plugins')
@login_required
def api_plugins():
    if not os.path.exists(STATIC_CONFIG_PATH):
        return jsonify({'plugins': [], 'error': 'traefik.yml not mounted'})
    try:
        with open(STATIC_CONFIG_PATH, 'r') as f:
            static = yaml.load(f) or {}
        raw = (static.get('experimental') or {}).get('plugins') or {}
        plugins = [
            {'name': n, 'moduleName': i.get('moduleName',''), 'version': i.get('version',''), 'settings': i.get('settings')}
            for n, i in raw.items() if isinstance(i, dict)
        ]
        return jsonify({'plugins': plugins})
    except Exception as e:
        logger.exception("Error reading static config")
        return jsonify({'plugins': [], 'error': str(e)})

@app.route('/api/traefik/certs')
@login_required
def api_certs():
    import json as _json
    if not os.path.exists(ACME_JSON_PATH):
        return jsonify({'certs': [], 'error': 'acme.json not mounted'})
    try:
        with open(ACME_JSON_PATH, 'r') as f:
            acme_data = _json.load(f)
        certs = []
        for resolver_name, resolver_data in acme_data.items():
            if not isinstance(resolver_data, dict):
                continue
            for c in (resolver_data.get('Certificates') or resolver_data.get('certificates') or []):
                domain    = c.get('domain', {})
                not_after = None
                try:
                    import base64
                    from cryptography import x509
                    from cryptography.hazmat.backends import default_backend
                    cert_obj  = x509.load_pem_x509_certificate(base64.b64decode(c.get('certificate','')), default_backend())
                    not_after = cert_obj.not_valid_after_utc.strftime('%b %d %H:%M:%S %Y GMT')
                except Exception as ex:
                    logger.debug(f"Cert parse error: {ex}")
                certs.append({'resolver': resolver_name, 'main': domain.get('main',''), 'sans': domain.get('sans',[]) or [], 'not_after': not_after})
        return jsonify({'certs': certs})
    except Exception as e:
        logger.exception("Error reading acme.json")
        return jsonify({'certs': [], 'error': str(e)})

@app.route('/api/traefik/logs')
@login_required
def api_logs():
    lines_req = min(int(request.args.get('lines', 200)), 1000)
    if not os.path.exists(ACCESS_LOG_PATH):
        return jsonify({'error': 'Access log not mounted', 'lines': []})
    try:
        with open(ACCESS_LOG_PATH, 'r', errors='replace') as f:
            all_lines = f.readlines()
        return jsonify({'lines': [l.rstrip() for l in all_lines[-lines_req:]]})
    except Exception as e:
        return jsonify({'error': str(e), 'lines': []})


def ensure_backup_dir():
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)

def create_backup():
    ensure_backup_dir()
    if os.path.exists(CONFIG_PATH):
        ts   = time.strftime("%Y%m%d_%H%M%S")
        dest = os.path.join(BACKUP_DIR, f"dynamic.yml.{ts}.bak")
        shutil.copy2(CONFIG_PATH, dest)
        logger.info(f"Backup created: {dest}")
        return dest
    return None

def list_backups():
    ensure_backup_dir()
    backups = []
    for f in sorted(os.listdir(BACKUP_DIR), reverse=True):
        if f.endswith('.bak'):
            path = os.path.join(BACKUP_DIR, f)
            st   = os.stat(path)
            backups.append({
                'name':     f,
                'size':     st.st_size,
                'modified': time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime))
            })
    return backups

_BACKUP_RE = re.compile(r'^dynamic\.yml\.\d{8}_\d{6}\.bak$')

def _validated_backup_path(filename: str) -> str:
    if not _BACKUP_RE.match(filename):
        logger.warning(f"Invalid backup filename rejected: {filename!r}")
        abort(400)
    path = os.path.realpath(os.path.join(BACKUP_DIR, filename))
    if not path.startswith(os.path.realpath(BACKUP_DIR)):
        logger.warning(f"Path traversal attempt blocked: {filename!r}")
        abort(400)
    return path

@app.route('/api/backups')
@login_required
def api_backups():
    return jsonify(list_backups())

@app.route('/api/restore/<filename>', methods=['POST'])
@csrf_protect
@login_required
def api_restore(filename):
    try:
        path = _validated_backup_path(filename)
        if not os.path.exists(path):
            return jsonify({'error': 'Backup not found'}), 404
        create_backup()
        shutil.copy2(path, CONFIG_PATH)
        logger.info(f"Restored: {filename}")
        return jsonify({'success': True})
    except Exception as e:
        logger.exception("Restore error")
        return jsonify({'error': str(e)}), 500

@app.route('/api/backup/create', methods=['POST'])
@csrf_protect
@login_required
def api_backup_create():
    try:
        dest = create_backup()
        if dest:
            return jsonify({'success': True, 'name': os.path.basename(dest)})
        return jsonify({'error': 'No config file to backup'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/backup/delete/<filename>', methods=['POST'])
@csrf_protect
@login_required
def api_backup_delete(filename):
    try:
        path = _validated_backup_path(filename)
        if os.path.exists(path):
            os.remove(path)
        return jsonify({'success': True})
    except Exception as e:
        logger.exception("Backup delete error")
        return jsonify({'error': str(e)}), 500


@app.route('/api/settings', methods=['GET'])
@login_required
def api_get_settings():
    s = load_settings()

    s.pop('password_hash', None)
    s['auth_enabled']    = _auth_enabled()
    s['has_password']    = _has_password_set()
    s['auth_env_forced'] = os.environ.get('AUTH_ENABLED', '').strip().lower() in ('false', '0', 'no')
    return jsonify(s)

@app.route('/api/settings', methods=['POST'])
@csrf_protect
@login_required
def api_save_settings():
    try:
        data        = request.get_json()
        domains_raw = data.get('domains', '')
        domains     = [d.strip() for d in (domains_raw if isinstance(domains_raw, list) else str(domains_raw).split(',')) if str(d).strip()]
        if not domains:
            return jsonify({'error': 'At least one domain is required'}), 400
        cert_resolver   = str(data.get('cert_resolver', 'cloudflare')).strip()
        traefik_api_url = _safe_api_url(str(data.get('traefik_api_url', 'http://traefik:8080')))
        if not traefik_api_url:
            return jsonify({'error': 'Invalid traefik_api_url — must start with http:// or https://'}), 400
        existing = load_settings()
        save_settings(domains, cert_resolver, traefik_api_url,
                      auth_enabled=existing['auth_enabled'],
                      password_hash=existing['password_hash'],
                      visible_tabs=existing['visible_tabs'])
        result = load_settings()
        result.pop('password_hash', None)
        return jsonify({'success': True, 'settings': result})
    except Exception as e:
        logger.exception("Settings save error")
        return jsonify({'error': str(e)}), 500


@app.route('/api/settings/tabs', methods=['POST'])
@csrf_protect
@login_required
def api_save_tabs():
    try:
        data     = request.get_json() or {}
        existing = load_settings()
        vt       = existing['visible_tabs'].copy()
        for t in OPTIONAL_TABS:
            if t in data:
                vt[t] = bool(data[t])
        save_settings(
            domains=existing['domains'],
            cert_resolver=existing['cert_resolver'],
            traefik_api_url=existing['traefik_api_url'],
            auth_enabled=existing['auth_enabled'],
            password_hash=existing['password_hash'],
            visible_tabs=vt,
        )
        logger.info(f"Tab visibility updated by {request.remote_addr}: {vt}")
        return jsonify({'success': True, 'visible_tabs': vt})
    except Exception as e:
        logger.exception("Tab settings save error")
        return jsonify({'error': str(e)}), 500


def load_config():
    if not os.path.exists(CONFIG_PATH):
        return {"http": {"routers": {}, "services": {}, "middlewares": {}}}
    with open(CONFIG_PATH, 'r') as f:
        data = yaml.load(f)
    return data if data and isinstance(data, dict) else {"http": {"routers": {}, "services": {}, "middlewares": {}}}

def save_config(data):
    with open(CONFIG_PATH, 'w') as f:
        yaml.dump(data, f)
    logger.info("Configuration saved")


@app.route('/')
@login_required
def index():
    settings    = load_settings()
    config      = load_config()
    apps        = []
    http_config = config.get('http', {})

    for rname, rdata in http_config.get('routers', {}).items():
        svc_name   = rdata.get('service', '')
        target_url = 'N/A'
        svcs       = http_config.get('services', {})
        if svc_name in svcs:
            servers = svcs[svc_name].get('loadBalancer', {}).get('servers', [])
            if servers:
                target_url = servers[0].get('url', 'Unknown')
        apps.append({'id': rname, 'name': rname, 'rule': rdata.get('rule',''),
                     'service_name': svc_name, 'target': target_url,
                     'middlewares': rdata.get('middlewares',[]),
                     'entryPoints': rdata.get('entryPoints',[]), 'protocol': 'http'})

    for rname, rdata in config.get('tcp', {}).get('routers', {}).items():
        svc_name = rdata.get('service', '')
        target   = 'N/A'
        tcp_svcs = config.get('tcp', {}).get('services', {})
        if svc_name in tcp_svcs:
            servers = tcp_svcs[svc_name].get('loadBalancer', {}).get('servers', [])
            if servers:
                target = servers[0].get('address', 'N/A')
        apps.append({'id': rname, 'name': rname, 'rule': rdata.get('rule',''),
                     'service_name': svc_name, 'target': target,
                     'middlewares': [], 'entryPoints': rdata.get('entryPoints',[]), 'protocol': 'tcp'})

    for rname, rdata in config.get('udp', {}).get('routers', {}).items():
        svc_name = rdata.get('service', '')
        target   = 'N/A'
        udp_svcs = config.get('udp', {}).get('services', {})
        if svc_name in udp_svcs:
            servers = udp_svcs[svc_name].get('loadBalancer', {}).get('servers', [])
            if servers:
                target = servers[0].get('address', 'N/A')
        apps.append({'id': rname, 'name': rname, 'rule': '',
                     'service_name': svc_name, 'target': target,
                     'middlewares': [], 'entryPoints': rdata.get('entryPoints',[]), 'protocol': 'udp'})

    middlewares = []
    for mname, mdata in http_config.get('middlewares', {}).items():
        buf = StringIO()
        yaml.dump(mdata, buf)
        middlewares.append({'name': mname, 'yaml': buf.getvalue(), 'type': 'http'})


    auth_on = _auth_enabled()
    login_time = session.get('login_time', '')

    return render_template('index.html', apps=apps, domains=settings['domains'],
                           middlewares=middlewares, settings=settings,
                           auth_enabled=auth_on, login_time=login_time)


@app.route('/save', methods=['POST'])
@csrf_protect
@login_required
def save_entry():
    try:
        settings       = load_settings()
        svc_name       = request.form.get('serviceName', '').strip()
        subdomain      = request.form.get('subdomain', '').strip()
        domain         = request.form.get('domain', settings['domains'][0]).strip()
        target_ip      = request.form.get('targetIp', '').strip()
        target_port    = request.form.get('targetPort', '').strip()
        middlewares_in = request.form.get('middlewares', '').strip()
        protocol       = request.form.get('protocol', 'http').strip().lower()
        is_edit        = request.form.get('isEdit') == 'true'
        original_id    = request.form.get('originalId', '')
        tcp_rule       = request.form.get('tcpRule', '').strip()

        if not svc_name:
            flash("Service name is required", "error")
            return redirect(url_for('index'))
        if protocol not in ('http', 'tcp', 'udp'):
            flash("Invalid protocol", "error")
            return redirect(url_for('index'))

        router_name  = svc_name
        service_name = f"{svc_name}-service"
        create_backup()
        config = load_config()

        if is_edit and original_id and original_id != router_name:
            for sec in ('http', 'tcp', 'udp'):
                s = config.get(sec, {})
                old_routers = s.get('routers', {})
                old_svc = (old_routers.get(original_id, {}).get('service') or '').strip()
                if original_id in old_routers:
                    del old_routers[original_id]
                if old_svc and 'services' in s and old_svc in s['services']:
                    del s['services'][old_svc]

        if protocol == 'http':
            rule       = f"Host(`{subdomain}`)" if '.' in subdomain else (f"Host(`{subdomain}.{domain}`)" if subdomain else f"Host(`{domain}`)")
            target_url = target_ip if target_ip.startswith('http') else f"http://{target_ip}:{target_port}"
            mws        = [m.strip() for m in middlewares_in.split(',')] if middlewares_in else []
            config.setdefault('http', {}).setdefault('routers', {})
            config['http'].setdefault('services', {})
            r = {'rule': rule, 'entryPoints': ['https'], 'tls': {'certResolver': settings['cert_resolver']}, 'service': service_name}
            if mws:
                r['middlewares'] = mws
            config['http']['routers'][router_name]   = r
            config['http']['services'][service_name] = {'loadBalancer': {'servers': [{'url': target_url}]}}

        elif protocol == 'tcp':
            rule = tcp_rule or (f"HostSNI(`{subdomain}.{domain}`)" if subdomain else "HostSNI(`*`)")
            config.setdefault('tcp', {}).setdefault('routers', {})
            config['tcp'].setdefault('services', {})
            config['tcp']['routers'][router_name]   = {'rule': rule, 'entryPoints': ['https'], 'tls': {'certResolver': settings['cert_resolver']}, 'service': service_name}
            config['tcp']['services'][service_name] = {'loadBalancer': {'servers': [{'address': f"{target_ip}:{target_port}"}]}}

        elif protocol == 'udp':
            udp_ep = request.form.get('udpEntryPoint', '').strip()
            config.setdefault('udp', {}).setdefault('routers', {})
            config['udp'].setdefault('services', {})
            config['udp']['routers'][router_name]   = {'entryPoints': [udp_ep] if udp_ep else [], 'service': service_name}
            config['udp']['services'][service_name] = {'loadBalancer': {'servers': [{'address': f"{target_ip}:{target_port}"}]}}

        save_config(config)
        flash(f"Successfully saved {svc_name}", "success")
    except Exception:
        logger.exception("Error saving configuration")
        flash("Error saving configuration", "error")
    return redirect(url_for('index'))


@app.route('/delete/<router_id>', methods=['POST'])
@csrf_protect
@login_required
def delete_entry(router_id):
    try:
        create_backup()
        config = load_config()
        for sec in ('http', 'tcp', 'udp'):
            s = config.get(sec, {})
            if router_id in s.get('routers', {}):
                svc = (s['routers'][router_id].get('service') or '').strip()
                del s['routers'][router_id]
                if svc and 'services' in s and svc in s['services']:
                    del s['services'][svc]
        save_config(config)
        flash(f"Deleted {router_id}", "success")
    except Exception:
        logger.exception("Delete error")
        flash("Error deleting", "error")
    return redirect(url_for('index'))


@app.route('/save-middleware', methods=['POST'])
@csrf_protect
@login_required
def save_middleware():
    try:
        mw_name     = request.form.get('middlewareName', '').strip()
        mw_content  = request.form.get('middlewareContent', '').strip()
        is_edit     = request.form.get('isMwEdit') == 'true'
        original_id = request.form.get('originalMwId', '')
        if not mw_name:
            flash("Middleware name is required", "error")
            return redirect(url_for('index'))
        create_backup()
        config = load_config()
        config.setdefault('http', {}).setdefault('middlewares', {})
        if is_edit and original_id and original_id != mw_name:
            config['http']['middlewares'].pop(original_id, None)
        config['http']['middlewares'][mw_name] = safe_yaml.load(mw_content)
        save_config(config)
        flash(f"Successfully saved middleware {mw_name}", "success")
    except Exception:
        logger.exception("Middleware save error")
        flash("Error saving middleware", "error")
    return redirect(url_for('index'))


@app.route('/delete-middleware/<mw_name>', methods=['POST'])
@csrf_protect
@login_required
def delete_middleware(mw_name):
    try:
        create_backup()
        config = load_config()
        config.get('http', {}).get('middlewares', {}).pop(mw_name, None)
        save_config(config)
        flash(f"Deleted middleware {mw_name}", "success")
    except Exception:
        logger.exception("Middleware delete error")
        flash("Error deleting middleware", "error")
    return redirect(url_for('index'))


if __name__ == '__main__':
    logger.info("Development server starting...")
    app.run(host='0.0.0.0', port=5000, debug=False)
else:
    logger.info("✅ Traefik Manager: Server is UP and Ready")

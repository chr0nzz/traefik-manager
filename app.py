import os
import re
import time
import shutil
import secrets
import logging
import requests
from datetime import datetime, timezone, timedelta
from functools import wraps
import click
from flask import (Flask, render_template, request, redirect,
                   url_for, flash, jsonify, abort, session, send_file)
from ruamel.yaml import YAML
from ruamel.yaml import YAML as SafeYAML
from io import StringIO
from cryptography.fernet import Fernet, InvalidToken

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

_OTP_KEY_PATH = os.path.join(os.path.dirname(os.environ.get('SETTINGS_PATH', '/app/config/manager.yml')), '.otp_key')

def _get_otp_fernet() -> Fernet:
    key = os.environ.get('OTP_ENCRYPTION_KEY', '').strip()
    if not key:
        if os.path.exists(_OTP_KEY_PATH):
            with open(_OTP_KEY_PATH) as f:
                key = f.read().strip()
        else:
            key = Fernet.generate_key().decode()
            os.makedirs(os.path.dirname(_OTP_KEY_PATH), exist_ok=True)
            with open(_OTP_KEY_PATH, 'w') as f:
                f.write(key)
    return Fernet(key.encode() if isinstance(key, str) else key)

def _encrypt_otp_secret(secret: str) -> str:
    if not secret:
        return ''
    return _get_otp_fernet().encrypt(secret.encode()).decode()

def _decrypt_otp_secret(token: str) -> str:
    if not token:
        return ''
    try:
        return _get_otp_fernet().decrypt(token.encode()).decode()
    except (InvalidToken, Exception):
        return token


app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
app.config['SESSION_COOKIE_HTTPONLY']    = True
app.config['SESSION_COOKIE_SAMESITE']    = 'Lax'


app.config['SESSION_COOKIE_SECURE']      = os.environ.get('COOKIE_SECURE', 'false').lower() == 'true'


INACTIVITY_TIMEOUT = int(os.environ.get('INACTIVITY_TIMEOUT_MINUTES', '120'))

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
limiter = Limiter(get_remote_address, app=app, default_limits=[], storage_uri="memory://")


yaml = YAML()
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)
yaml.width = 4096

safe_yaml = SafeYAML(typ='safe')


BACKUP_DIR    = os.environ.get('BACKUP_DIR',    '/app/backups')
SETTINGS_PATH      = os.environ.get('SETTINGS_PATH', '/app/config/manager.yml')
_CONFIG_DIR        = os.path.dirname(os.path.abspath(SETTINGS_PATH))
GROUPS_CACHE_DIR   = os.path.join(_CONFIG_DIR, 'cache')
GROUPS_CONFIG_FILE = os.path.join(_CONFIG_DIR, 'dashboard.yml')
os.makedirs(GROUPS_CACHE_DIR, exist_ok=True)

_config_dir = os.environ.get('CONFIG_DIR', '').strip()
ACTIVE_CONFIG_DIR = _config_dir
if _config_dir:
    import glob as _glob
    _ymls  = _glob.glob(os.path.join(_config_dir, '**', '*.yml'),  recursive=True)
    _yamls = _glob.glob(os.path.join(_config_dir, '**', '*.yaml'), recursive=True)
    CONFIG_PATHS = sorted(_ymls + _yamls) or [os.path.join(_config_dir, 'dynamic.yml')]
else:
    _raw_paths = os.environ.get('CONFIG_PATHS', '').strip()
    if _raw_paths:
        CONFIG_PATHS = [p.strip() for p in _raw_paths.split(',') if p.strip()]
    else:
        CONFIG_PATHS = [os.environ.get('CONFIG_PATH', '/app/config/dynamic.yml')]

CONFIG_PATH  = CONFIG_PATHS[0]
MULTI_CONFIG = len(CONFIG_PATHS) > 1

_ALLOWED_FILE_PREFIXES = tuple(sorted(set(
    ['/app/', os.path.abspath(BACKUP_DIR) + '/', os.path.dirname(os.path.abspath(SETTINGS_PATH)) + '/'] +
    [os.path.dirname(os.path.abspath(p)) + '/' for p in CONFIG_PATHS]
)))
_ALLOWED_API_SCHEMES   = ('http://', 'https://')

def _safe_file_path(path: str) -> str:
    if not path:
        return ''
    resolved = os.path.realpath(path)
    if any(resolved.startswith(p) for p in _ALLOWED_FILE_PREFIXES):
        return resolved
    logger.warning(f"Blocked unsafe file path: {path!r}")
    return ''

def _resolve_config_path(s: str) -> str:
    """Validate a config file given a basename or full path against CONFIG_PATHS.
    Returns the canonical path if valid, '' otherwise.
    If ACTIVE_CONFIG_DIR is set and s is a plain filename, allows new files in CONFIG_DIR."""
    if not s:
        return CONFIG_PATH
    s = s.strip()
    for p in CONFIG_PATHS:
        if s == p or s == os.path.basename(p):
            return p
    if ACTIVE_CONFIG_DIR and '/' not in s and '\\' not in s and s.endswith(('.yml', '.yaml')):
        candidate = os.path.join(ACTIVE_CONFIG_DIR, s)
        if _is_safe_path(candidate):
            return candidate
    logger.warning(f"Config file not in CONFIG_PATHS: {s!r}")
    return ''

def _register_config_path(path: str):
    """Add a newly created config file to CONFIG_PATHS if not already present."""
    global CONFIG_PATHS, CONFIG_PATH, MULTI_CONFIG
    if path and path not in CONFIG_PATHS:
        CONFIG_PATHS = sorted(CONFIG_PATHS + [path])
        CONFIG_PATH  = CONFIG_PATHS[0]
        MULTI_CONFIG = len(CONFIG_PATHS) > 1

def _safe_api_url(url: str) -> str:
    url = url.strip()
    if any(url.startswith(s) for s in _ALLOWED_API_SCHEMES):
        return url
    logger.warning(f"Blocked unsafe API URL: {url!r}")
    return ''


ACCESS_LOG_PATH    = '/app/logs/access.log'
ACME_JSON_PATH     = '/app/acme.json'
STATIC_CONFIG_PATH = '/app/traefik.yml'


OPTIONAL_TABS = ['dashboard', 'routemap', 'docker', 'kubernetes', 'swarm', 'nomad', 'ecs', 'consulcatalog', 'redis', 'etcd', 'consul', 'zookeeper', 'http_provider', 'file_external', 'certs', 'plugins', 'logs']

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
        'otp_secret':           '',
        'otp_enabled':          False,
        'disabled_routes':      {},
        'api_key_hash':         '',
        'api_key_enabled':      False,
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
        if 'otp_secret' in data:
            merged['otp_secret'] = _decrypt_otp_secret(str(data['otp_secret']).strip())
        if 'otp_enabled' in data:
            merged['otp_enabled'] = bool(data['otp_enabled'])
        else:
            if merged['password_hash']:
                merged['setup_complete'] = True
        if 'disabled_routes' in data and isinstance(data['disabled_routes'], dict):
            merged['disabled_routes'] = dict(data['disabled_routes'])
        if 'api_key_hash' in data:
            merged['api_key_hash'] = str(data['api_key_hash']).strip()
        if 'api_key_enabled' in data:
            merged['api_key_enabled'] = bool(data['api_key_enabled'])
        return merged
    except Exception as e:
        logger.warning(f"Could not load manager.yml, using defaults: {e}")
        return defaults


def save_settings(domains, cert_resolver, traefik_api_url,
                  auth_enabled=True, password_hash='', visible_tabs=None,
                  must_change_password=None, setup_complete=None,
                  otp_secret=None, otp_enabled=None,
                  api_key_hash=None, api_key_enabled=None,
                  api_key_preview=None,
                  disabled_routes=None):
    if visible_tabs is None:
        visible_tabs = {t: False for t in OPTIONAL_TABS}
    _cur = load_settings()
    if must_change_password is None:
        must_change_password = _cur.get('must_change_password', False)
    if setup_complete is None:
        setup_complete = _cur.get('setup_complete', False)
    if otp_secret is None:
        otp_secret = _cur.get('otp_secret', '')
    if otp_enabled is None:
        otp_enabled = _cur.get('otp_enabled', False)
    if api_key_hash is None:
        api_key_hash = _cur.get('api_key_hash', '')
    if api_key_enabled is None:
        api_key_enabled = _cur.get('api_key_enabled', False)
    if api_key_preview is None:
        api_key_preview = _cur.get('api_key_preview', '')
    if disabled_routes is None:
        disabled_routes = _cur.get('disabled_routes', {})
    otp_secret = _encrypt_otp_secret(otp_secret)
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    tmp = SETTINGS_PATH + '.tmp'
    with open(tmp, 'w') as f:
        yaml.dump({
            'domains':              domains,
            'cert_resolver':        cert_resolver,
            'traefik_api_url':      traefik_api_url,
            'auth_enabled':         auth_enabled,
            'password_hash':        password_hash,
            'visible_tabs':         visible_tabs,
            'must_change_password': must_change_password,
            'setup_complete':       setup_complete,
            'otp_secret':           otp_secret,
            'otp_enabled':          otp_enabled,
            'disabled_routes':      disabled_routes,
            'api_key_hash':         api_key_hash,
            'api_key_enabled':      api_key_enabled,
            'api_key_preview':      api_key_preview,
        }, f)
    os.replace(tmp, SETTINGS_PATH)
    logger.info("Manager settings saved")


def _auth_enabled() -> bool:
    env = os.environ.get('AUTH_ENABLED', '').strip().lower()
    if env in ('false', '0', 'no'):
        return False
    if env in ('true', '1', 'yes'):
        return True
    return load_settings().get('auth_enabled', True)


def _hash_password(plaintext: str) -> str:
    import bcrypt
    return bcrypt.hashpw(plaintext.encode(), bcrypt.gensalt(rounds=12)).decode()


def _ensure_password():
    if os.environ.get('ADMIN_PASSWORD', '').strip():
        return
    settings = load_settings()
    if settings.get('password_hash', ''):
        return
    password = secrets.token_urlsafe(16)
    logger.warning("=" * 60)
    logger.warning("  TRAEFIK MANAGER - AUTO-GENERATED PASSWORD")
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
if MULTI_CONFIG:
    for _cp in CONFIG_PATHS:
        logger.info(f"Config File:    {_cp}")
else:
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
            if not request.headers.get('X-Api-Key'):
                _check_csrf()
        return f(*args, **kwargs)
    return decorated

@app.context_processor
def inject_csrf():
    return {'csrf_token': _get_csrf_token()}


def _check_password(plaintext: str, hashed: str) -> bool:
    import bcrypt
    try:
        return bcrypt.checkpw(plaintext.encode(), hashed.encode())
    except Exception:
        return False

def _is_authenticated() -> bool:

    if not _auth_enabled():
        return True
    return session.get('authenticated') is True

def _check_inactivity():
    if not session.get('authenticated'):
        return
    if session.permanent:
        return
    last = session.get('last_active')
    now  = time.time()
    if last and (now - last) > INACTIVITY_TIMEOUT * 60:
        logger.info(f"Session expired due to inactivity ({INACTIVITY_TIMEOUT}m) for {request.remote_addr}")
        session.clear()
        return
    session['last_active'] = now

def _check_api_key() -> bool:
    key = request.headers.get('X-Api-Key', '')
    if not key:
        return False
    settings = load_settings()
    if not settings.get('api_key_enabled') or not settings.get('api_key_hash'):
        return False
    return _check_password(key, settings['api_key_hash'])

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if _check_api_key():
            return f(*args, **kwargs)
        _check_inactivity()
        if not _is_authenticated():
            if request.headers.get('X-Api-Key'):
                abort(401)
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return decorated

def _has_password_set() -> bool:

    if os.environ.get('ADMIN_PASSWORD', '').strip():
        return True
    return bool(load_settings().get('password_hash', ''))

def _get_effective_hash() -> str:
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
    response.headers['Permissions-Policy']       = 'camera=(), microphone=(), geolocation=()'
    if app.config.get('SESSION_COOKIE_SECURE'):
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response


@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute", methods=["POST"])
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
            remember = request.form.get('remember') == 'on'

            if settings.get('otp_enabled') and settings.get('otp_secret') and not admin_pw:
                session.clear()
                session['otp_pending']  = True
                session['otp_remember'] = remember
                session['otp_next']     = request.form.get('next') or ''
                session['otp_must_change'] = settings.get('must_change_password', False)
                session['otp_setup_complete'] = settings.get('setup_complete', False)
                logger.info(f"OTP step required for login from {request.remote_addr}")
                return redirect(url_for('login_otp'))

            _vals = {'permanent': remember, 'authenticated': True,
                     'last_active': time.time(),
                     'login_time': datetime.now(timezone.utc).isoformat()}
            session.clear()
            session.update(_vals)
            logger.info(f"Successful login from {request.remote_addr}")

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
            error = 'Incorrect password.'
            logger.warning(f"Failed login attempt from {request.remote_addr}")

    next_url = request.args.get('next', '')
    return render_template('login.html', error=error, next=next_url,
                           csrf_token=_get_csrf_token(),
                           temp_password_hint=temp_password_hint)


@app.route('/setup', methods=['GET', 'POST'])
def setup():
    if not _auth_enabled():
        return redirect(url_for('index'))

    current = load_settings()

    if current.get('setup_complete', False):
        if current.get('must_change_password', False):
            return redirect(url_for('force_change_password'))
        return redirect(url_for('index'))

    if _has_password_set() and not session.get('authenticated'):
        return redirect(url_for('login'))

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
@click.option('--disable-otp', is_flag=True, default=False,
              help='Also disable two-factor authentication (use if TOTP app is lost).')
def reset_password_cli(disable_otp):

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
        otp_secret='' if disable_otp else None,
        otp_enabled=False if disable_otp else None,
    )
    print("=" * 60)
    print("TRAEFIK MANAGER - PASSWORD RESET")
    print(f"New temporary password: {password}")
    if disable_otp:
        print("Two-factor authentication has been DISABLED.")
    print("You will be required to change it on next login.")
    print("=" * 60)


@app.route('/api/auth/change-password', methods=['POST'])
@limiter.limit("10 per minute")
@csrf_protect
@login_required
def api_change_password():

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


@app.route('/login/otp', methods=['GET', 'POST'])
@limiter.limit("5 per minute", methods=["POST"])
def login_otp():
    if not session.get('otp_pending'):
        return redirect(url_for('login'))

    error = None
    if request.method == 'POST':
        _check_csrf()
        import pyotp
        code     = request.form.get('code', '').strip()
        settings = load_settings()
        secret   = settings.get('otp_secret', '')
        if secret and pyotp.TOTP(secret).verify(code, valid_window=1):
            remember       = session.get('otp_remember', False)
            must_change    = session.get('otp_must_change', False)
            setup_complete = session.get('otp_setup_complete', False)
            next_url       = session.get('otp_next', '') or url_for('index')
            _vals = {'permanent': remember, 'authenticated': True,
                     'last_active': time.time(),
                     'login_time': datetime.now(timezone.utc).isoformat()}
            session.clear()
            session.update(_vals)
            logger.info(f"Successful OTP login from {request.remote_addr}")
            if must_change:
                if not setup_complete:
                    return redirect(url_for('setup'))
                return redirect(url_for('force_change_password'))
            if not next_url.startswith('/'):
                next_url = url_for('index')
            return redirect(next_url)
        else:
            error = 'Invalid code. Please try again.'
            logger.warning(f"Failed OTP attempt from {request.remote_addr}")

    return render_template('login.html', otp_mode=True, error=error,
                           csrf_token=_get_csrf_token())


@app.route('/api/auth/otp/setup', methods=['POST'])
@csrf_protect
@login_required
def api_otp_setup():
    import pyotp
    secret = pyotp.random_base32()
    uri    = pyotp.TOTP(secret).provisioning_uri(
        name='Traefik Manager',
        issuer_name='traefik-manager'
    )
    session['otp_pending_secret'] = secret
    return jsonify({'secret': secret, 'uri': uri})


@app.route('/api/auth/otp/enable', methods=['POST'])
@csrf_protect
@login_required
def api_otp_enable():
    import pyotp
    code   = (request.get_json() or {}).get('code', '').strip()
    secret = session.pop('otp_pending_secret', '')
    if not secret or not pyotp.TOTP(secret).verify(code, valid_window=1):
        return jsonify({'error': 'Invalid code - please try again.'}), 400
    settings = load_settings()
    save_settings(
        domains=settings['domains'],
        cert_resolver=settings['cert_resolver'],
        traefik_api_url=settings['traefik_api_url'],
        auth_enabled=settings['auth_enabled'],
        password_hash=settings['password_hash'],
        visible_tabs=settings['visible_tabs'],
        otp_secret=secret,
        otp_enabled=True,
    )
    logger.info(f"OTP enabled by {request.remote_addr}")
    return jsonify({'success': True})


@app.route('/api/auth/otp/disable', methods=['POST'])
@csrf_protect
@login_required
def api_otp_disable():
    settings = load_settings()
    save_settings(
        domains=settings['domains'],
        cert_resolver=settings['cert_resolver'],
        traefik_api_url=settings['traefik_api_url'],
        auth_enabled=settings['auth_enabled'],
        password_hash=settings['password_hash'],
        visible_tabs=settings['visible_tabs'],
        otp_secret='',
        otp_enabled=False,
    )
    logger.info(f"OTP disabled by {request.remote_addr}")
    return jsonify({'success': True})


@app.route('/api/auth/otp/status')
@login_required
def api_otp_status():
    settings = load_settings()
    return jsonify({'otp_enabled': settings.get('otp_enabled', False)})


@app.route('/api/auth/apikey/generate', methods=['POST'])
@limiter.limit("5 per hour")
@csrf_protect
@login_required
def api_apikey_generate():
    key = secrets.token_urlsafe(32)
    preview = key[:8] + '...' + key[-4:]
    settings = load_settings()
    save_settings(
        domains=settings['domains'],
        cert_resolver=settings['cert_resolver'],
        traefik_api_url=settings['traefik_api_url'],
        auth_enabled=settings['auth_enabled'],
        password_hash=settings['password_hash'],
        visible_tabs=settings['visible_tabs'],
        otp_secret=settings['otp_secret'],
        otp_enabled=settings['otp_enabled'],
        api_key_hash=_hash_password(key),
        api_key_enabled=True,
        api_key_preview=preview,
    )
    logger.info(f"API key generated by {request.remote_addr}")
    return jsonify({'ok': True, 'key': key})


@app.route('/api/auth/apikey/revoke', methods=['POST'])
@csrf_protect
@login_required
def api_apikey_revoke():
    settings = load_settings()
    save_settings(
        domains=settings['domains'],
        cert_resolver=settings['cert_resolver'],
        traefik_api_url=settings['traefik_api_url'],
        auth_enabled=settings['auth_enabled'],
        password_hash=settings['password_hash'],
        visible_tabs=settings['visible_tabs'],
        otp_secret=settings['otp_secret'],
        otp_enabled=settings['otp_enabled'],
        api_key_hash='',
        api_key_enabled=False,
        api_key_preview='',
    )
    logger.info(f"API key revoked by {request.remote_addr}")
    return jsonify({'ok': True})


@app.route('/api/auth/apikey/status')
@login_required
def api_apikey_status():
    settings = load_settings()
    return jsonify({
        'enabled': bool(settings.get('api_key_enabled', False)),
        'has_key': bool(settings.get('api_key_hash', '')),
        'key_preview': settings.get('api_key_preview', '') or None,
    })


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
    lines_req = min(int(request.args.get('lines', 100)), 1000)
    if not os.path.exists(ACCESS_LOG_PATH):
        return jsonify({'error': 'Access log not mounted', 'lines': []})
    try:
        lines = []
        buf_size = 8192
        with open(ACCESS_LOG_PATH, 'rb') as f:
            f.seek(0, 2)
            remaining = f.tell()
            partial = b''
            while remaining > 0 and len(lines) < lines_req:
                chunk = min(buf_size, remaining)
                remaining -= chunk
                f.seek(remaining)
                data = f.read(chunk) + partial
                split = data.split(b'\n')
                partial = split[0]
                lines = split[1:] + lines
            if partial:
                lines = [partial] + lines
        result = [l.decode('utf-8', errors='replace').rstrip() for l in lines[-lines_req:] if l]
        return jsonify({'lines': result})
    except Exception as e:
        return jsonify({'error': str(e), 'lines': []})


def ensure_backup_dir():
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)

def create_backup(path=None):
    if path is None:
        path = CONFIG_PATH
    ensure_backup_dir()
    if os.path.exists(path):
        ts   = time.strftime("%Y%m%d_%H%M%S")
        base = os.path.basename(path)
        dest = os.path.join(BACKUP_DIR, f"{base}.{ts}.bak")
        shutil.copy2(path, dest)
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

_BACKUP_RE = re.compile(r'^[a-zA-Z0-9._-]+\.yml\.\d{8}_\d{6}\.bak$')

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
@limiter.limit("10 per minute")
@csrf_protect
@login_required
def api_restore(filename):
    try:
        path = _validated_backup_path(filename)
        if not os.path.exists(path):
            return jsonify({'error': 'Backup not found'}), 404
        # Infer the target config file from the backup filename (basename.yml.ts.bak)
        # Strip the timestamp suffix to get the original basename
        bname = filename  # e.g. dynamic.yml.20260325_120000.bak
        # Find matching config path by basename prefix
        target_path = CONFIG_PATH
        for p in CONFIG_PATHS:
            if bname.startswith(os.path.basename(p) + '.'):
                target_path = p
                break
        create_backup(target_path)
        shutil.copy2(path, target_path)
        logger.info(f"Restored: {filename} → {target_path}")
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
            return jsonify({'error': 'Invalid traefik_api_url - must start with http:// or https://'}), 400
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


def load_config(path=None):
    if path is None:
        path = CONFIG_PATH
    if not os.path.exists(path):
        return {"http": {"routers": {}, "services": {}, "middlewares": {}}}
    with open(path, 'r') as f:
        data = yaml.load(f)
    return data if data and isinstance(data, dict) else {"http": {"routers": {}, "services": {}, "middlewares": {}}}

def save_config(data, path=None):
    if path is None:
        path = CONFIG_PATH
    tmp = path + '.tmp'
    try:
        with open(tmp, 'w') as f:
            yaml.dump(data, f)
        shutil.copyfile(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
    logger.info(f"Configuration saved: {path}")


def _build_apps(config, config_file=''):
    apps = []
    http_config = config.get('http', {})
    for rname, rdata in http_config.get('routers', {}).items():
        svc_name = rdata.get('service', '')
        target_url = 'N/A'
        svcs = http_config.get('services', {})
        lb = {}
        if svc_name in svcs:
            lb = svcs[svc_name].get('loadBalancer', {})
            servers = lb.get('servers', [])
            if servers:
                target_url = servers[0].get('url', 'Unknown')
        app_id = f"{config_file}::{rname}" if (MULTI_CONFIG and config_file) else rname
        tls_http = rdata.get('tls', {})
        apps.append({'id': app_id, 'name': rname, 'rule': rdata.get('rule', ''),
                     'service_name': svc_name, 'target': target_url,
                     'middlewares': rdata.get('middlewares', []),
                     'entryPoints': rdata.get('entryPoints', []), 'protocol': 'http',
                     'tls': bool(tls_http), 'enabled': True,
                     'passHostHeader': lb.get('passHostHeader', True),
                     'certResolver': tls_http.get('certResolver', '') if isinstance(tls_http, dict) else '',
                     'configFile': config_file, 'provider': 'file'})
    for rname, rdata in config.get('tcp', {}).get('routers', {}).items():
        svc_name = rdata.get('service', '')
        target = 'N/A'
        tcp_svcs = config.get('tcp', {}).get('services', {})
        if svc_name in tcp_svcs:
            servers = tcp_svcs[svc_name].get('loadBalancer', {}).get('servers', [])
            if servers:
                target = servers[0].get('address', 'N/A')
        app_id = f"{config_file}::{rname}" if (MULTI_CONFIG and config_file) else rname
        tls_tcp = rdata.get('tls', {})
        apps.append({'id': app_id, 'name': rname, 'rule': rdata.get('rule', ''),
                     'service_name': svc_name, 'target': target,
                     'middlewares': [], 'entryPoints': rdata.get('entryPoints', []),
                     'protocol': 'tcp', 'tls': bool(tls_tcp), 'enabled': True,
                     'certResolver': tls_tcp.get('certResolver', '') if isinstance(tls_tcp, dict) else '',
                     'configFile': config_file, 'provider': 'file'})
    for rname, rdata in config.get('udp', {}).get('routers', {}).items():
        svc_name = rdata.get('service', '')
        target = 'N/A'
        udp_svcs = config.get('udp', {}).get('services', {})
        if svc_name in udp_svcs:
            servers = udp_svcs[svc_name].get('loadBalancer', {}).get('servers', [])
            if servers:
                target = servers[0].get('address', 'N/A')
        app_id = f"{config_file}::{rname}" if (MULTI_CONFIG and config_file) else rname
        apps.append({'id': app_id, 'name': rname, 'rule': '',
                     'service_name': svc_name, 'target': target,
                     'middlewares': [], 'entryPoints': rdata.get('entryPoints', []),
                     'protocol': 'udp', 'tls': False, 'enabled': True,
                     'configFile': config_file, 'provider': 'file'})
    return apps


def _build_middlewares(config, config_file=''):
    middlewares = []
    for mname, mdata in config.get('http', {}).get('middlewares', {}).items():
        buf = StringIO()
        yaml.dump(mdata, buf)
        middlewares.append({'name': mname, 'yaml': buf.getvalue(), 'type': 'http', 'configFile': config_file})
    return middlewares


def _build_external_routes(include_internal=False):
    routes = []
    for proto in ('http', 'tcp', 'udp'):
        data = traefik_api_get(f'/api/{proto}/routers') or []
        for r in data:
            provider = r.get('provider', '')
            if not provider or provider == 'file':
                continue
            if not include_internal and provider == 'internal':
                continue
            name = r.get('name', '')
            display_name = name.split('@')[0] if '@' in name else name
            tls = r.get('tls', {})
            routes.append({
                'id':           name,
                'name':         display_name,
                'rule':         r.get('rule', ''),
                'service_name': r.get('service', ''),
                'target':       r.get('service', 'N/A'),
                'middlewares':  r.get('middlewares') or [],
                'entryPoints':  r.get('entryPoints') or [],
                'protocol':     proto,
                'tls':          bool(tls),
                'enabled':      r.get('status', 'enabled') == 'enabled',
                'provider':     provider,
                'configFile':   '',
            })
    return routes


def _build_all_apps(include_external=True, include_internal=False):
    """Build combined apps and middlewares from all config files, plus disabled routes."""
    all_apps = []
    all_middlewares = []
    for p in CONFIG_PATHS:
        cf = os.path.basename(p) if MULTI_CONFIG else ''
        config = load_config(p)
        all_apps.extend(_build_apps(config, cf))
        all_middlewares.extend(_build_middlewares(config, cf))
    if include_external:
        all_apps.extend(_build_external_routes(include_internal=include_internal))
    settings = load_settings()
    for rname, rdata in settings.get('disabled_routes', {}).items():
        proto    = rdata.get('protocol', 'http')
        router   = rdata.get('router', {})
        svc_name = router.get('service', '')
        svc      = rdata.get('service', {})
        cf       = rdata.get('configFile', '')
        if proto == 'http':
            servers    = svc.get('loadBalancer', {}).get('servers', [])
            target_url = servers[0].get('url', 'N/A') if servers else 'N/A'
            all_apps.append({'id': rname, 'name': rname, 'rule': router.get('rule', ''),
                             'service_name': svc_name, 'target': target_url,
                             'middlewares': router.get('middlewares', []),
                             'entryPoints': router.get('entryPoints', []),
                             'protocol': 'http', 'tls': bool(router.get('tls')), 'enabled': False,
                             'passHostHeader': svc.get('loadBalancer', {}).get('passHostHeader', True),
                             'configFile': cf, 'provider': 'file'})
        elif proto == 'tcp':
            servers = svc.get('loadBalancer', {}).get('servers', [])
            target  = servers[0].get('address', 'N/A') if servers else 'N/A'
            all_apps.append({'id': rname, 'name': rname, 'rule': router.get('rule', ''),
                             'service_name': svc_name, 'target': target,
                             'middlewares': [], 'entryPoints': router.get('entryPoints', []),
                             'protocol': 'tcp', 'tls': bool(router.get('tls')), 'enabled': False,
                             'configFile': cf, 'provider': 'file'})
        else:
            servers = svc.get('loadBalancer', {}).get('servers', [])
            target  = servers[0].get('address', 'N/A') if servers else 'N/A'
            all_apps.append({'id': rname, 'name': rname, 'rule': '',
                             'service_name': svc_name, 'target': target,
                             'middlewares': [], 'entryPoints': router.get('entryPoints', []),
                             'protocol': 'udp', 'tls': False, 'enabled': False,
                             'configFile': cf, 'provider': 'file'})
    return all_apps, all_middlewares


def _toggle_route(route_id: str, enable: bool):
    settings = load_settings()
    disabled = settings.get('disabled_routes', {})

    if enable:
        if route_id not in disabled:
            return
        saved       = disabled.pop(route_id)
        proto       = saved.get('protocol', 'http')
        router      = saved.get('router', {})
        svc_name    = router.get('service', route_id)
        svc         = saved.get('service', {})
        cf          = saved.get('configFile', '')
        target_path = _resolve_config_path(cf) or CONFIG_PATH
        config      = load_config(target_path)
        section     = config.setdefault(proto, {})
        section.setdefault('routers', {})[route_id]  = router
        section.setdefault('services', {})[svc_name] = svc
        create_backup(target_path)
        save_config(config, target_path)
    else:
        proto       = None
        router      = None
        svc_name    = None
        svc         = None
        target_path = None
        for p in CONFIG_PATHS:
            config = load_config(p)
            for prot in ('http', 'tcp', 'udp'):
                routers = config.get(prot, {}).get('routers', {})
                if route_id in routers:
                    proto       = prot
                    router      = dict(routers.pop(route_id))
                    svc_name    = router.get('service', route_id)
                    svc         = dict(config.get(prot, {}).get('services', {}).pop(svc_name, {}))
                    target_path = p
                    break
            if proto:
                break
        if proto is None:
            return
        cf = os.path.basename(target_path) if MULTI_CONFIG else ''
        disabled[route_id] = {'protocol': proto, 'router': router, 'service': svc, 'configFile': cf}
        create_backup(target_path)
        save_config(config, target_path)

    save_settings(
        domains=settings['domains'],
        cert_resolver=settings['cert_resolver'],
        traefik_api_url=settings['traefik_api_url'],
        auth_enabled=settings['auth_enabled'],
        password_hash=settings['password_hash'],
        visible_tabs=settings['visible_tabs'],
        disabled_routes=disabled,
    )


@app.route('/api/routes')
@login_required
def api_routes():
    apps, middlewares = _build_all_apps(include_external=False)
    apps = [a for a in apps if not (a.get('service_name') or '').endswith('@internal')]
    return jsonify({'apps': apps, 'middlewares': middlewares})


@app.route('/api/routes/all')
@login_required
def api_routes_all():
    apps, middlewares = _build_all_apps(include_external=True, include_internal=True)
    return jsonify({'apps': apps, 'middlewares': middlewares})


@app.route('/api/configs')
@login_required
def api_configs():
    return jsonify([{'label': os.path.basename(p), 'path': p} for p in CONFIG_PATHS])


def _read_groups_config():
    if not os.path.exists(GROUPS_CONFIG_FILE):
        return {'custom_groups': [], 'route_overrides': {}}
    with open(GROUPS_CONFIG_FILE, 'r') as f:
        data = safe_yaml.load(f)
    if not data:
        return {'custom_groups': [], 'route_overrides': {}}
    return {
        'custom_groups':   list(data.get('custom_groups', []) or []),
        'route_overrides': dict(data.get('route_overrides', {}) or {}),
    }

def _write_groups_config(data):
    with open(GROUPS_CONFIG_FILE, 'w') as f:
        safe_yaml.dump({
            'custom_groups':   list(data.get('custom_groups', []) or []),
            'route_overrides': dict(data.get('route_overrides', {}) or {}),
        }, f)

@app.route('/api/dashboard/config', methods=['GET'])
@login_required
def dashboard_config_get():
    return jsonify(_read_groups_config())

@app.route('/api/dashboard/config', methods=['POST'])
@login_required
@csrf_protect
def dashboard_config_post():
    data = request.get_json() or {}
    _write_groups_config(data)
    return jsonify({'ok': True})

@app.route('/api/dashboard/icon/<slug>')
@login_required
def dashboard_icon(slug):
    slug = re.sub(r'[^a-z0-9-]', '', slug.lower())
    if not slug:
        return ('', 404)
    cache_path = os.path.join(GROUPS_CACHE_DIR, slug + '.png')
    miss_path  = os.path.join(GROUPS_CACHE_DIR, slug + '.404')
    if os.path.exists(cache_path):
        return send_file(cache_path, mimetype='image/png', max_age=86400, conditional=True)
    if os.path.exists(miss_path):
        return ('', 404)
    try:
        r = requests.get(f'https://cdn.jsdelivr.net/gh/selfhst/icons/png/{slug}.png', timeout=2)
        if r.status_code == 200 and 'image' in r.headers.get('content-type', ''):
            with open(cache_path, 'wb') as wf:
                wf.write(r.content)
            return send_file(cache_path, mimetype='image/png', max_age=86400, conditional=True)
        open(miss_path, 'w').close()
    except Exception:
        pass
    return ('', 404)


@app.route('/api/routes/<path:route_id>/toggle', methods=['POST'])
@csrf_protect
@login_required
def api_toggle_route(route_id):
    enable = (request.get_json(force=True, silent=True) or {}).get('enable', True)
    try:
        _toggle_route(route_id, bool(enable))
        return jsonify({'ok': True})
    except Exception as e:
        logger.error(f"Toggle route error: {e}")
        return jsonify({'ok': False, 'message': 'Failed to toggle route.'}), 500


@app.route('/')
@login_required
def index():
    settings    = load_settings()
    apps, middlewares = _build_all_apps(include_external=False)
    apps = [a for a in apps if not (a.get('service_name') or '').endswith('@internal')]
    auth_on    = _auth_enabled()
    login_time = session.get('login_time', '')
    config_paths_list = [{'label': os.path.basename(p), 'path': p} for p in CONFIG_PATHS]
    cert_resolvers    = [r.strip() for r in settings['cert_resolver'].split(',') if r.strip()]

    return render_template('index.html', apps=apps, domains=settings['domains'],
                           middlewares=middlewares, settings=settings,
                           auth_enabled=auth_on, login_time=login_time,
                           multi_config=MULTI_CONFIG,
                           config_paths_list=config_paths_list,
                           config_dir_set=bool(ACTIVE_CONFIG_DIR),
                           cert_resolvers=cert_resolvers)


def _is_fetch():
    return request.headers.get('X-Requested-With') == 'fetch'


@app.route('/save', methods=['POST'])
@csrf_protect
@login_required
def save_entry():
    fetch = _is_fetch()
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
        scheme         = request.form.get('scheme', 'http').strip().lower()
        pass_host      = request.form.get('passHostHeader') == 'true'
        _all_eps       = request.form.getlist('entryPoints')
        http_eps       = [ep.strip() for ep in (_all_eps[0] if _all_eps else 'https').split(',') if ep.strip()] or ['https']
        tcp_eps        = [ep.strip() for ep in (_all_eps[1] if len(_all_eps) > 1 else '').split(',') if ep.strip()] or ['https']
        resolvers      = [r.strip() for r in settings['cert_resolver'].split(',') if r.strip()]
        cert_resolver  = request.form.get('certResolver', '').strip() or (resolvers[0] if resolvers else 'cloudflare')
        config_file_raw = request.form.get('configFile', '').strip()
        target_path    = _resolve_config_path(config_file_raw) or CONFIG_PATH

        if not svc_name:
            if fetch:
                return jsonify({'ok': False, 'message': 'Service name is required'}), 400
            flash("Service name is required", "error")
            return redirect(url_for('index'))
        if protocol not in ('http', 'tcp', 'udp'):
            if fetch:
                return jsonify({'ok': False, 'message': 'Invalid protocol'}), 400
            flash("Invalid protocol", "error")
            return redirect(url_for('index'))

        router_name  = svc_name
        service_name = f"{svc_name}-service"
        create_backup(target_path)
        config = load_config(target_path)

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
            target_url = target_ip if target_ip.startswith('http') else f"{scheme}://{target_ip}:{target_port}"
            mws        = [m.strip() for m in middlewares_in.split(',')] if middlewares_in else []
            config.setdefault('http', {}).setdefault('routers', {})
            config['http'].setdefault('services', {})
            r = {'rule': rule, 'entryPoints': http_eps, 'tls': {'certResolver': cert_resolver}, 'service': service_name}
            if mws:
                r['middlewares'] = mws
            lb = {'servers': [{'url': target_url}]}
            if not pass_host:
                lb['passHostHeader'] = False
            config['http']['routers'][router_name]   = r
            config['http']['services'][service_name] = {'loadBalancer': lb}

        elif protocol == 'tcp':
            rule = tcp_rule or (f"HostSNI(`{subdomain}.{domain}`)" if subdomain else "HostSNI(`*`)")
            config.setdefault('tcp', {}).setdefault('routers', {})
            config['tcp'].setdefault('services', {})
            config['tcp']['routers'][router_name]   = {'rule': rule, 'entryPoints': tcp_eps, 'tls': {'certResolver': cert_resolver}, 'service': service_name}
            config['tcp']['services'][service_name] = {'loadBalancer': {'servers': [{'address': f"{target_ip}:{target_port}"}]}}

        elif protocol == 'udp':
            udp_ep = request.form.get('udpEntryPoint', '').strip()
            config.setdefault('udp', {}).setdefault('routers', {})
            config['udp'].setdefault('services', {})
            config['udp']['routers'][router_name]   = {'entryPoints': [udp_ep] if udp_ep else [], 'service': service_name}
            config['udp']['services'][service_name] = {'loadBalancer': {'servers': [{'address': f"{target_ip}:{target_port}"}]}}

        save_config(config, target_path)
        _register_config_path(target_path)
        msg = f"Successfully saved {svc_name}"
        if fetch:
            return jsonify({'ok': True, 'message': msg})
        flash(msg, "success")
    except Exception:
        logger.exception("Error saving configuration")
        if fetch:
            return jsonify({'ok': False, 'message': 'Error saving configuration'}), 500
        flash("Error saving configuration", "error")
    return redirect(url_for('index'))


@app.route('/delete/<router_id>', methods=['POST'])
@csrf_protect
@login_required
def delete_entry(router_id):
    fetch = _is_fetch()
    try:
        config_file_raw = request.form.get('configFile', '').strip()
        # Find which config file contains this route
        if config_file_raw:
            search_paths = [_resolve_config_path(config_file_raw) or CONFIG_PATH]
        else:
            search_paths = CONFIG_PATHS
        deleted = False
        for target_path in search_paths:
            config = load_config(target_path)
            for sec in ('http', 'tcp', 'udp'):
                s = config.get(sec, {})
                if router_id in s.get('routers', {}):
                    svc = (s['routers'][router_id].get('service') or '').strip()
                    del s['routers'][router_id]
                    if svc and 'services' in s and svc in s['services']:
                        del s['services'][svc]
                    create_backup(target_path)
                    save_config(config, target_path)
                    deleted = True
                    break
            if deleted:
                break
        msg = f"Deleted {router_id}"
        if fetch:
            return jsonify({'ok': True, 'message': msg})
        flash(msg, "success")
    except Exception:
        logger.exception("Delete error")
        if fetch:
            return jsonify({'ok': False, 'message': 'Error deleting'}), 500
        flash("Error deleting", "error")
    return redirect(url_for('index'))


@app.route('/save-middleware', methods=['POST'])
@csrf_protect
@login_required
def save_middleware():
    fetch = _is_fetch()
    try:
        mw_name         = request.form.get('middlewareName', '').strip()
        mw_content      = request.form.get('middlewareContent', '').strip()
        is_edit         = request.form.get('isMwEdit') == 'true'
        original_id     = request.form.get('originalMwId', '')
        config_file_raw = request.form.get('configFile', '').strip()
        target_path     = _resolve_config_path(config_file_raw) or CONFIG_PATH
        if not mw_name:
            if fetch:
                return jsonify({'ok': False, 'message': 'Middleware name is required'}), 400
            flash("Middleware name is required", "error")
            return redirect(url_for('index'))
        create_backup(target_path)
        config = load_config(target_path)
        config.setdefault('http', {}).setdefault('middlewares', {})
        if is_edit and original_id and original_id != mw_name:
            config['http']['middlewares'].pop(original_id, None)
        config['http']['middlewares'][mw_name] = safe_yaml.load(mw_content)
        save_config(config, target_path)
        _register_config_path(target_path)
        msg = f"Successfully saved middleware {mw_name}"
        if fetch:
            return jsonify({'ok': True, 'message': msg})
        flash(msg, "success")
    except Exception:
        logger.exception("Middleware save error")
        if fetch:
            return jsonify({'ok': False, 'message': 'Error saving middleware'}), 500
        flash("Error saving middleware", "error")
    return redirect(url_for('index'))


@app.route('/delete-middleware/<mw_name>', methods=['POST'])
@csrf_protect
@login_required
def delete_middleware(mw_name):
    fetch = _is_fetch()
    try:
        config_file_raw = request.form.get('configFile', '').strip()
        if config_file_raw:
            search_paths = [_resolve_config_path(config_file_raw) or CONFIG_PATH]
        else:
            search_paths = CONFIG_PATHS
        for target_path in search_paths:
            config = load_config(target_path)
            mws = config.get('http', {}).get('middlewares', {})
            if mw_name in mws:
                mws.pop(mw_name, None)
                create_backup(target_path)
                save_config(config, target_path)
                break
        msg = f"Deleted middleware {mw_name}"
        if fetch:
            return jsonify({'ok': True, 'message': msg})
        flash(msg, "success")
    except Exception:
        logger.exception("Middleware delete error")
        if fetch:
            return jsonify({'ok': False, 'message': 'Error deleting middleware'}), 500
        flash("Error deleting middleware", "error")
    return redirect(url_for('index'))


if __name__ == '__main__':
    logger.info("Development server starting...")
    app.run(host='0.0.0.0', port=5000, debug=False)
else:
    logger.info("✅ Traefik Manager: Server is UP and Ready")

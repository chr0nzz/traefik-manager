import os
import re
import time
import shutil
import secrets
import logging
import threading
import requests
from collections import deque
from datetime import datetime, timezone, timedelta
from functools import wraps
import click
from flask import (Flask, render_template, request, redirect,
                   url_for, flash, jsonify, abort, session, send_file)
from ruamel.yaml import YAML
from ruamel.yaml import YAML as SafeYAML
from io import StringIO
from cryptography.fernet import Fernet, InvalidToken

GITHUB_REPO  = "chr0nzz/traefik-manager"
APP_VERSION  = "1.0.0-beta4"


LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)
logger = logging.getLogger("traefik-manager")


app = Flask(__name__)

_CONFIG_DIR      = os.path.dirname(os.environ.get('SETTINGS_PATH', '/app/config/manager.yml'))
_SECRET_KEY_PATH = os.path.join(_CONFIG_DIR, '.secret_key')

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

_OTP_KEY_PATH = os.path.join(_CONFIG_DIR, '.otp_key')

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


BACKUP_DIR    = os.environ.get('BACKUP_DIR',    '/app/backups')
SETTINGS_PATH      = os.environ.get('SETTINGS_PATH', '/app/config/manager.yml')
_CONFIG_DIR        = os.path.dirname(os.path.abspath(SETTINGS_PATH))
GROUPS_CACHE_DIR   = os.path.join(_CONFIG_DIR, 'cache')
GROUPS_CONFIG_FILE  = os.path.join(_CONFIG_DIR, 'dashboard.yml')
NOTIFICATIONS_PATH  = os.path.join(_CONFIG_DIR, 'notifications.yml')
os.makedirs(GROUPS_CACHE_DIR, exist_ok=True)

_notifications     = deque(maxlen=100)
_notif_lock        = threading.Lock()

def _load_notifications():
    if os.path.exists(NOTIFICATIONS_PATH):
        try:
            _y = SafeYAML(typ='safe')
            with open(NOTIFICATIONS_PATH, 'r') as f:
                data = _y.load(f) or []
            with _notif_lock:
                _notifications.clear()
                for entry in data[-100:]:
                    _notifications.append(entry)
        except Exception:
            pass

def _save_notifications_bg():
    try:
        _y = SafeYAML(typ='safe')
        with _notif_lock:
            data = list(_notifications)
        with open(NOTIFICATIONS_PATH, 'w') as f:
            _y.dump(data, f)
    except Exception:
        logger.exception("Failed to save notifications")

def add_notification(type_, msg):
    entry = {'ts': time.strftime("%Y-%m-%d %H:%M:%S"), 'type': type_, 'msg': msg}
    with _notif_lock:
        _notifications.append(entry)
    threading.Thread(target=_save_notifications_bg, daemon=True).start()

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

def _is_safe_path(path: str) -> bool:
    """Return True if path is inside ACTIVE_CONFIG_DIR (prevents path traversal)."""
    if not ACTIVE_CONFIG_DIR:
        return False
    try:
        return os.path.realpath(path).startswith(os.path.realpath(ACTIVE_CONFIG_DIR) + os.sep)
    except Exception:
        return False

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
    if ACTIVE_CONFIG_DIR and '/' not in s and '\\' not in s:
        if not s.endswith(('.yml', '.yaml')):
            s = s + '.yml'
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


def _get_acme_json_path() -> str:
    s = load_settings()
    return s.get('acme_json_path', '').strip() or os.environ.get('ACME_JSON_PATH', '/app/acme.json')

def _get_access_log_path() -> str:
    s = load_settings()
    return s.get('access_log_path', '').strip() or os.environ.get('ACCESS_LOG_PATH', '/app/logs/access.log')

def _get_static_config_path() -> str:
    s = load_settings()
    return s.get('static_config_path', '').strip() or os.environ.get('STATIC_CONFIG_PATH', '')

def _get_restart_method() -> str:
    return os.environ.get('RESTART_METHOD', 'proxy').lower()

def _get_traefik_container() -> str:
    return os.environ.get('TRAEFIK_CONTAINER', 'traefik')

def _get_signal_file_path() -> str:
    return os.environ.get('SIGNAL_FILE_PATH', '/signals/restart.sig')


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
        'api_keys':             [],
        'api_key_enabled':      False,
        'self_route':           {'domain': '', 'service_url': ''},
        'acme_json_path':       '',
        'access_log_path':      '',
        'static_config_path':   '',
        'oidc_enabled':         False,
        'oidc_provider_url':    '',
        'oidc_client_id':       '',
        'oidc_client_secret':   '',
        'oidc_display_name':    'OIDC',
        'oidc_allowed_emails':  '',
        'oidc_allowed_groups':  '',
        'oidc_groups_claim':    'groups',
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
        if 'api_keys' in data and isinstance(data['api_keys'], list):
            keys = []
            for k in data['api_keys']:
                if isinstance(k, dict) and k.get('name') and k.get('hash') and k.get('preview'):
                    keys.append({
                        'name':       str(k['name'])[:50],
                        'hash':       str(k['hash']),
                        'preview':    str(k['preview']),
                        'created_at': str(k.get('created_at', '')),
                    })
            merged['api_keys'] = keys
        elif 'api_key_hash' in data and str(data['api_key_hash']).strip():
            merged['api_keys'] = [{
                'name':       'Default',
                'hash':       str(data['api_key_hash']).strip(),
                'preview':    str(data.get('api_key_preview', '')).strip(),
                'created_at': '',
            }]
        merged['api_key_enabled'] = len(merged['api_keys']) > 0
        if 'self_route' in data and isinstance(data['self_route'], dict):
            sr = data['self_route']
            merged['self_route'] = {
                'domain':      str(sr.get('domain', '')).strip(),
                'service_url': str(sr.get('service_url', '')).strip(),
                'router_name': str(sr.get('router_name', 'traefik-manager')).strip() or 'traefik-manager',
                'entry_point': str(sr.get('entry_point', '')).strip(),
            }
        if 'acme_json_path' in data:
            merged['acme_json_path'] = str(data['acme_json_path']).strip()
        if 'access_log_path' in data:
            merged['access_log_path'] = str(data['access_log_path']).strip()
        if 'static_config_path' in data:
            merged['static_config_path'] = str(data['static_config_path']).strip()
        if 'oidc_enabled' in data:
            merged['oidc_enabled'] = bool(data['oidc_enabled'])
        if 'oidc_provider_url' in data:
            merged['oidc_provider_url'] = str(data['oidc_provider_url']).strip()
        if 'oidc_client_id' in data:
            merged['oidc_client_id'] = str(data['oidc_client_id']).strip()
        if 'oidc_client_secret' in data:
            merged['oidc_client_secret'] = _decrypt_otp_secret(str(data['oidc_client_secret']).strip())
        if 'oidc_display_name' in data:
            merged['oidc_display_name'] = str(data['oidc_display_name']).strip()
        if 'oidc_allowed_emails' in data:
            merged['oidc_allowed_emails'] = str(data['oidc_allowed_emails']).strip()
        if 'oidc_allowed_groups' in data:
            merged['oidc_allowed_groups'] = str(data['oidc_allowed_groups']).strip()
        if 'oidc_groups_claim' in data:
            merged['oidc_groups_claim'] = str(data['oidc_groups_claim']).strip()
        return merged
    except Exception as e:
        logger.warning(f"Could not load manager.yml, using defaults: {e}")
        return defaults


def save_settings(domains, cert_resolver, traefik_api_url,
                  auth_enabled=True, password_hash='', visible_tabs=None,
                  must_change_password=None, setup_complete=None,
                  otp_secret=None, otp_enabled=None,
                  api_keys=None,
                  disabled_routes=None,
                  self_route=None,
                  acme_json_path=None,
                  access_log_path=None,
                  static_config_path=None,
                  oidc_enabled=None, oidc_provider_url=None, oidc_client_id=None,
                  oidc_client_secret=None, oidc_display_name=None,
                  oidc_allowed_emails=None, oidc_allowed_groups=None,
                  oidc_groups_claim=None):
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
    if api_keys is None:
        api_keys = _cur.get('api_keys', [])
    if self_route is None:
        self_route = _cur.get('self_route', {'domain': '', 'service_url': ''})
    if disabled_routes is None:
        disabled_routes = _cur.get('disabled_routes', {})
    if acme_json_path is None:
        acme_json_path = _cur.get('acme_json_path', '')
    if access_log_path is None:
        access_log_path = _cur.get('access_log_path', '')
    if static_config_path is None:
        static_config_path = _cur.get('static_config_path', '')
    if oidc_enabled is None:
        oidc_enabled = _cur.get('oidc_enabled', False)
    if oidc_provider_url is None:
        oidc_provider_url = _cur.get('oidc_provider_url', '')
    if oidc_client_id is None:
        oidc_client_id = _cur.get('oidc_client_id', '')
    if oidc_client_secret is None:
        oidc_client_secret = _cur.get('oidc_client_secret', '')
    if oidc_display_name is None:
        oidc_display_name = _cur.get('oidc_display_name', 'OIDC')
    if oidc_allowed_emails is None:
        oidc_allowed_emails = _cur.get('oidc_allowed_emails', '')
    if oidc_allowed_groups is None:
        oidc_allowed_groups = _cur.get('oidc_allowed_groups', '')
    if oidc_groups_claim is None:
        oidc_groups_claim = _cur.get('oidc_groups_claim', 'groups')
    otp_secret = _encrypt_otp_secret(otp_secret)
    oidc_client_secret_enc = _encrypt_otp_secret(oidc_client_secret) if oidc_client_secret else ''
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
            'api_keys':             api_keys,
            'api_key_enabled':      len(api_keys) > 0,
            'self_route':           self_route,
            'acme_json_path':       acme_json_path,
            'access_log_path':      access_log_path,
            'static_config_path':   static_config_path,
            'oidc_enabled':         oidc_enabled,
            'oidc_provider_url':    oidc_provider_url,
            'oidc_client_id':       oidc_client_id,
            'oidc_client_secret':   oidc_client_secret_enc,
            'oidc_display_name':    oidc_display_name,
            'oidc_allowed_emails':  oidc_allowed_emails,
            'oidc_allowed_groups':  oidc_allowed_groups,
            'oidc_groups_claim':    oidc_groups_claim,
        }, f)
    os.replace(tmp, SETTINGS_PATH)
    logger.info("Manager settings saved")


SELF_ROUTE_FILENAME = 'traefik-manager-self.yml'

def _best_entrypoint() -> str:
    eps = traefik_api_get('/api/entrypoints') or []
    for ep in eps:
        addr = ep.get('address', '')
        if ':443' in addr or '/443' in addr:
            return ep.get('name', 'websecure')
    if eps:
        return eps[0].get('name', 'websecure')
    return 'websecure'

def _self_route_path() -> str:
    if ACTIVE_CONFIG_DIR:
        return os.path.join(ACTIVE_CONFIG_DIR, SELF_ROUTE_FILENAME)
    return os.path.join(os.path.dirname(os.path.abspath(CONFIG_PATH)), SELF_ROUTE_FILENAME)

def _write_self_route(domain: str, service_url: str, cert_resolver: str, router_name: str = 'traefik-manager', entry_point: str = 'websecure') -> None:
    router_entry = {
        'rule': f'Host(`{domain}`)',
        'entryPoints': [entry_point or 'websecure'],
        'service': router_name,
        'tls': {'certResolver': cert_resolver} if cert_resolver and cert_resolver.lower() != 'none' else {},
    }
    service_entry = {
        'loadBalancer': {
            'servers': [{'url': service_url}]
        }
    }
    if ACTIVE_CONFIG_DIR:
        path = _self_route_path()
        content = {
            'http': {
                'routers': {router_name: router_entry},
                'services': {router_name: service_entry},
            }
        }
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        tmp = path + '.tmp'
        with open(tmp, 'w') as f:
            yaml.dump(content, f)
        os.replace(tmp, path)
        logger.info(f"Self-route written to new file: {path}")
    else:
        cfg = load_config(CONFIG_PATH)
        cfg.setdefault('http', {}).setdefault('routers', {})[router_name] = router_entry
        cfg['http'].setdefault('services', {})[router_name] = service_entry
        save_config(cfg, CONFIG_PATH)
        logger.info(f"Self-route updated in existing config: {CONFIG_PATH} (router: {router_name})")

def _delete_self_route(router_name: str = 'traefik-manager') -> None:
    if ACTIVE_CONFIG_DIR:
        path = _self_route_path()
        if os.path.exists(path):
            os.remove(path)
            logger.info(f"Self-route file deleted: {path}")
    else:
        cfg = load_config(CONFIG_PATH)
        http = cfg.get('http', {})
        http.get('routers', {}).pop(router_name, None)
        http.get('services', {}).pop(router_name, None)
        save_config(_strip_empty_sections(cfg), CONFIG_PATH)
        logger.info(f"Self-route '{router_name}' removed from config: {CONFIG_PATH}")

def _detect_self_route_domain() -> str:
    import re
    for cfg_path in CONFIG_PATHS:
        if not os.path.exists(cfg_path):
            continue
        try:
            with open(cfg_path, 'r') as f:
                data = yaml.load(f) or {}
            routers = (data.get('http') or {}).get('routers') or {}
            services = (data.get('http') or {}).get('services') or {}
            for rname, rdata in routers.items():
                svc_name = (rdata.get('service') or '').split('@')[0]
                svc = services.get(svc_name) or {}
                servers = ((svc.get('loadBalancer') or {}).get('servers') or [])
                urls = [str(s.get('url', '')) for s in servers if s.get('url')]
                if any('traefik-manager' in u or ':5000' in u for u in urls):
                    rule = rdata.get('rule', '')
                    m = re.search(r'Host\(`([^`]+)`\)', rule)
                    if m:
                        return m.group(1)
        except Exception:
            continue
    return ''


def _detect_self_route_from_own_labels() -> tuple[str, str]:
    import re
    try:
        import docker as _docker
        client = _docker.from_env()
        own_id = os.environ.get('HOSTNAME', '')
        for c in client.containers.list():
            if not (c.id.startswith(own_id) or 'traefik-manager' in c.name):
                continue
            labels = c.labels or {}
            domain = ''
            svc_url = ''
            for k, v in labels.items():
                if k.startswith('traefik.http.routers.') and k.endswith('.rule'):
                    m = re.search(r'Host\(`([^`]+)`\)', v)
                    if m:
                        domain = m.group(1)
                if k.startswith('traefik.http.services.') and k.endswith('.loadbalancer.server.url'):
                    svc_url = v
            if domain:
                return domain, svc_url or 'http://traefik-manager:5000'
    except Exception:
        pass
    return '', ''


def _detect_setup_self_route() -> tuple[str, str]:
    settings = load_settings()
    saved = settings.get('self_route', {})
    if saved.get('domain'):
        return saved['domain'], saved.get('service_url', 'http://traefik-manager:5000')
    domain = _detect_self_route_domain()
    if domain:
        return domain, 'http://traefik-manager:5000'
    return _detect_self_route_from_own_labels()

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


def _read_traefik_labels():
    try:
        import docker as _docker
        client = _docker.from_env()
        container_name = os.environ.get('TRAEFIK_CONTAINER', 'traefik')
        for c in client.containers.list():
            labels = c.labels or {}
            if labels.get('traefik-manager.role') == 'traefik' or c.name == container_name:
                if not os.environ.get('RESTART_METHOD') and labels.get('traefik-manager.restart-method'):
                    os.environ['RESTART_METHOD'] = labels['traefik-manager.restart-method']
                if not os.environ.get('STATIC_CONFIG_PATH') and labels.get('traefik-manager.static-config'):
                    os.environ['STATIC_CONFIG_PATH'] = labels['traefik-manager.static-config']
                if not os.environ.get('TRAEFIK_CONTAINER'):
                    os.environ['TRAEFIK_CONTAINER'] = c.name
                logger.info(f"Static config: read labels from Traefik container {c.name!r}")
                break
    except Exception:
        pass

_read_traefik_labels()

_s = load_settings()
_static_path  = _get_static_config_path()
_restart_meth = _get_restart_method()
_oidc_on      = bool(_s.get('oidc_issuer'))
logger.info("===========================================")
logger.info(f"Traefik Manager v{APP_VERSION}")
if MULTI_CONFIG:
    for _cp in CONFIG_PATHS:
        logger.info(f"Config File:    {_cp}")
elif ACTIVE_CONFIG_DIR:
    logger.info(f"Config Dir:     {ACTIVE_CONFIG_DIR}")
else:
    logger.info(f"Config Path:    {CONFIG_PATH}")
logger.info(f"Settings Path:  {SETTINGS_PATH}")
logger.info(f"Backup Dir:     {BACKUP_DIR}")
logger.info(f"Traefik API:    {_s['traefik_api_url']}")
logger.info(f"Restart Method: {_restart_meth}")
logger.info(f"Static Config:  {_static_path if _static_path else 'not configured'}")
logger.info(f"Domains:        {_s['domains']}")
logger.info(f"Cert Resolver:  {_s['cert_resolver'] or 'not set'}")
logger.info(f"Auth Enabled:   {_auth_enabled()}")
if _oidc_on:
    logger.info(f"OIDC:           enabled ({_s.get('oidc_issuer', '')})")
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
            if not _check_api_key():
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

def _hash_api_key(key: str) -> str:
    import hashlib
    return 'sha256:' + hashlib.sha256(key.encode()).hexdigest()

def _verify_api_key(key: str, stored: str) -> bool:
    import hashlib
    if stored.startswith('sha256:'):
        expected = 'sha256:' + hashlib.sha256(key.encode()).hexdigest()
        return secrets.compare_digest(expected, stored)
    return _check_password(key, stored)


def _is_authenticated() -> bool:

    if not _auth_enabled():
        return True
    return session.get('authenticated') is True

def _check_inactivity():
    if not session.get('authenticated'):
        return
    last = session.get('last_active')
    now  = time.time()
    timeout = INACTIVITY_TIMEOUT * 60 if not session.permanent else INACTIVITY_TIMEOUT * 60 * 24
    if last and (now - last) > timeout:
        logger.info(f"Session expired due to inactivity for {request.remote_addr}")
        session.clear()
        return
    session['last_active'] = now

def _check_api_key() -> bool:
    key = request.headers.get('X-Api-Key', '')
    if not key:
        return False
    settings = load_settings()
    api_keys = settings.get('api_keys', [])
    if not api_keys:
        return False
    return any(_verify_api_key(key, k['hash']) for k in api_keys if k.get('hash'))

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


_load_notifications()

_SILENT_PREFIXES = (
    '/static/',
    '/api/notifications',
    '/api/traefik/',
    '/api/routes',
    '/api/dashboard/',
    '/api/manager/version',
    '/api/configs',
    '/api/settings/tabs',
)

@app.before_request
def log_request_info():
    path = request.path
    method = request.method
    if method == 'GET':
        if request.remote_addr == '127.0.0.1':
            return
        if any(path.startswith(p) for p in _SILENT_PREFIXES):
            logger.debug(f"{request.remote_addr} → {method} {path}")
            return
    logger.info(f"{request.remote_addr} → {method} {path}")


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
                session['otp_remember'] = bool(remember)
                session['otp_next']     = request.form.get('next') or ''
                session['otp_must_change'] = settings.get('must_change_password', False)
                session['otp_setup_complete'] = settings.get('setup_complete', False)
                logger.info(f"OTP step required for login from {request.remote_addr}")
                return redirect(url_for('login_otp'))

            _vals = {'authenticated': True,
                     'last_active': time.time(),
                     'login_time': datetime.now(timezone.utc).isoformat()}
            session.clear()
            session.update(_vals)
            session.permanent = remember
            logger.info(f"Successful login from {request.remote_addr}")
            add_notification('info', f"Login from {request.remote_addr}")

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
                           temp_password_hint=temp_password_hint,
                           oidc_enabled=settings.get('oidc_enabled', False),
                           oidc_display_name=settings.get('oidc_display_name', 'OIDC'))


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

        domains_raw       = request.form.get('domains', '').strip()
        cert_resolver     = request.form.get('cert_resolver', '').strip()
        traefik_api_url   = request.form.get('traefik_api_url', '').strip()
        visible_tabs_raw  = request.form.get('visible_tabs', '{}')
        pw                = request.form.get('password', '')
        confirm           = request.form.get('confirm', '')
        self_route_domain = request.form.get('self_route_domain', '').strip()
        self_route_svc    = request.form.get('self_route_service', '').strip() or 'http://traefik-manager:5000'

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
            resolver = cert_resolver if cert_resolver.lower() not in ('none', '') else ''
            sr = {'domain': '', 'service_url': ''}
            if self_route_domain:
                sr = {'domain': self_route_domain, 'service_url': self_route_svc}
                _write_self_route(self_route_domain, self_route_svc, resolver)
            save_settings(
                domains=domains,
                cert_resolver=resolver,
                traefik_api_url=traefik_api_url,
                auth_enabled=True,
                password_hash=pw_hash,
                visible_tabs=visible_tabs,
                must_change_password=current.get('must_change_password', False),
                setup_complete=True,
                self_route=sr,
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

    detected_domain, detected_svc = _detect_setup_self_route()
    return render_template('login.html', setup_mode=True, error=error,
                           defaults=defaults, csrf_token=_get_csrf_token(),
                           temp_password_mode=temp_password_mode,
                           detected_self_domain=detected_domain,
                           detected_self_svc=detected_svc)


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
            remember       = session.get('otp_remember', True)
            must_change    = session.get('otp_must_change', False)
            setup_complete = session.get('otp_setup_complete', False)
            next_url       = session.get('otp_next', '') or url_for('index')
            _vals = {'authenticated': True,
                     'last_active': time.time(),
                     'login_time': datetime.now(timezone.utc).isoformat()}
            session.clear()
            session.update(_vals)
            session.permanent = remember
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
    data = request.get_json(silent=True) or {}
    device_name = str(data.get('device_name', '')).strip()[:50]
    if not device_name:
        return jsonify({'ok': False, 'error': 'device_name is required'}), 400
    settings = load_settings()
    api_keys = settings.get('api_keys', [])
    if len(api_keys) >= 10:
        return jsonify({'ok': False, 'error': 'Maximum of 10 API keys reached'}), 400
    key = secrets.token_urlsafe(32)
    preview = key[:8] + '...' + key[-4:]
    api_keys.append({
        'name':       device_name,
        'hash':       _hash_api_key(key),
        'preview':    preview,
        'created_at': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M'),
    })
    save_settings(
        domains=settings['domains'],
        cert_resolver=settings['cert_resolver'],
        traefik_api_url=settings['traefik_api_url'],
        auth_enabled=settings['auth_enabled'],
        password_hash=settings['password_hash'],
        visible_tabs=settings['visible_tabs'],
        otp_secret=settings['otp_secret'],
        otp_enabled=settings['otp_enabled'],
        api_keys=api_keys,
    )
    logger.info(f"API key '{device_name}' generated by {request.remote_addr}")
    return jsonify({'ok': True, 'key': key})


@app.route('/api/auth/apikey/revoke', methods=['POST'])
@csrf_protect
@login_required
def api_apikey_revoke():
    data = request.get_json(silent=True) or {}
    preview = str(data.get('preview', '')).strip()
    if not preview:
        return jsonify({'ok': False, 'error': 'preview is required'}), 400
    settings = load_settings()
    api_keys = [k for k in settings.get('api_keys', []) if k.get('preview') != preview]
    save_settings(
        domains=settings['domains'],
        cert_resolver=settings['cert_resolver'],
        traefik_api_url=settings['traefik_api_url'],
        auth_enabled=settings['auth_enabled'],
        password_hash=settings['password_hash'],
        visible_tabs=settings['visible_tabs'],
        otp_secret=settings['otp_secret'],
        otp_enabled=settings['otp_enabled'],
        api_keys=api_keys,
    )
    logger.info(f"API key revoked by {request.remote_addr}")
    return jsonify({'ok': True})


@app.route('/api/auth/apikey/status')
@login_required
def api_apikey_status():
    settings = load_settings()
    api_keys = settings.get('api_keys', [])
    return jsonify({
        'enabled': len(api_keys) > 0,
        'keys': [{'name': k['name'], 'preview': k['preview'], 'created_at': k.get('created_at', '')} for k in api_keys],
        'count': len(api_keys),
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
    return jsonify({'ok': False, 'latency_ms': None}), 503

@app.route('/api/manager/version')
@login_required
def api_manager_version():
    return jsonify({
        "version": APP_VERSION,
        "repo": GITHUB_REPO,
        "static_config_configured": bool(_get_static_config_path()),
    })

@app.route('/api/health')
def api_health():
    return jsonify({"ok": True}), 200


@app.route('/api')
def api_docs():
    from flask import send_from_directory
    return send_from_directory('static', 'api.html')


@app.route('/openapi.yaml')
def openapi_yaml():
    from flask import send_from_directory
    return send_from_directory('static', 'openapi.yaml')


def _restart_via_docker() -> bool:
    try:
        import docker as _docker
        client = _docker.from_env()
        container = client.containers.get(_get_traefik_container())
        container.restart()
        logger.info(f"Restarted Traefik container: {_get_traefik_container()!r}")
        return True
    except Exception as e:
        logger.error(f"Docker restart failed: {e}")
        return False

def _restart_via_signal_file() -> bool:
    try:
        sig_path = _get_signal_file_path()
        os.makedirs(os.path.dirname(sig_path), exist_ok=True)
        with open(sig_path, 'w') as f:
            f.write('')
        logger.info(f"Restart signal written: {sig_path}")
        return True
    except Exception as e:
        logger.error(f"Signal file write failed: {e}")
        return False

def trigger_traefik_restart() -> tuple:
    method = _get_restart_method()
    if method in ('proxy', 'socket'):
        ok = _restart_via_docker()
        return ok, ('' if ok else f'Docker restart failed - check DOCKER_HOST and TRAEFIK_CONTAINER ({_get_traefik_container()!r})')
    if method == 'poison-pill':
        ok = _restart_via_signal_file()
        return ok, ('' if ok else f'Signal file write failed - check SIGNAL_FILE_PATH ({_get_signal_file_path()!r})')
    return False, f'Unknown RESTART_METHOD: {method!r}'


@app.route('/api/static/available')
@login_required
def api_static_available():
    path = _get_static_config_path()
    return jsonify({'available': bool(path and os.path.exists(path))})

@app.route('/api/static/config')
@login_required
def api_static_config_get():
    path = _get_static_config_path()
    if not path or not os.path.exists(path):
        return jsonify({'error': 'Static config not found or STATIC_CONFIG_PATH not set'}), 404
    try:
        with open(path, 'r') as f:
            raw = f.read()
        _y = SafeYAML(typ='safe')
        parsed = _y.load(raw) or {}
        return jsonify({'raw': raw, 'parsed': parsed, 'path': path})
    except Exception as e:
        logger.exception("Failed to read static config")
        return jsonify({'error': str(e)}), 500

@app.route('/api/static/config', methods=['POST'])
@csrf_protect
@login_required
def api_static_config_save():
    path = _get_static_config_path()
    if not path:
        return jsonify({'error': 'STATIC_CONFIG_PATH not configured'}), 400
    safe_path = _safe_file_path(path)
    if not safe_path:
        return jsonify({'error': 'Static config path is outside allowed directories'}), 403
    data = request.get_json(silent=True) or {}
    content = (data.get('content') or data.get('raw') or '').strip()
    if not content:
        return jsonify({'error': 'No content provided'}), 400
    try:
        _y = SafeYAML(typ='safe')
        _y.load(content)
    except Exception as e:
        return jsonify({'error': f'Invalid YAML: {e}'}), 400
    try:
        create_backup(safe_path)
        with open(safe_path, 'w') as f:
            f.write(content)
        logger.info(f"Static config saved by {request.remote_addr}: {safe_path}")
        add_notification('success', 'Static config saved')
        return jsonify({'ok': True})
    except Exception as e:
        logger.exception("Failed to write static config")
        return jsonify({'error': str(e)}), 500

@app.route('/api/static/restart', methods=['POST'])
@csrf_protect
@login_required
def api_static_restart():
    ok, err = trigger_traefik_restart()
    if ok:
        logger.info(f"Traefik restarted via static config by {request.remote_addr}")
        add_notification('warning', 'Traefik restarted')
        return jsonify({'ok': True})
    logger.error(f"Traefik restart failed for {request.remote_addr}: {err}")
    return jsonify({'ok': False, 'error': err}), 500

@app.route('/api/static/status')
@login_required
def api_static_status():
    data = traefik_api_get('/api/overview')
    return jsonify({'up': data is not None})

@app.route('/api/traefik/runtime')
@login_required
def api_traefik_runtime():
    method = _get_restart_method()
    container = _get_traefik_container()
    if method in ('proxy', 'socket'):
        return jsonify({'method': method, 'runtime': 'docker', 'container': container})
    if method == 'poison-pill':
        try:
            import docker as _docker
            client = _docker.from_env()
            client.containers.get(container)
            return jsonify({'method': method, 'runtime': 'docker', 'container': container})
        except Exception:
            return jsonify({'method': method, 'runtime': 'native', 'container': None})
    return jsonify({'method': method, 'runtime': 'unknown', 'container': None})

@app.route('/api/static/section', methods=['POST'])
@csrf_protect
@login_required
def api_static_section_update():
    path = _get_static_config_path()
    if not path or not os.path.exists(path):
        return jsonify({'error': 'Static config not found'}), 404
    req      = request.get_json(silent=True) or {}
    action   = req.get('action', '')
    section  = req.get('section', '')
    name     = str(req.get('name', '')).strip()
    old_name = str(req.get('old_name', name)).strip()
    payload  = req.get('data', {})
    if not action or not section or (action not in ('set', 'remove') and not name):
        return jsonify({'error': 'Missing required fields'}), 400
    current_raw = req.get('current_raw', '')
    try:
        _y = YAML()
        _y.preserve_quotes = True
        if current_raw:
            config = _y.load(StringIO(current_raw)) or {}
        else:
            with open(path, 'r') as f:
                config = _y.load(f) or {}
        if section == 'entrypoints':
            eps = config.setdefault('entryPoints', {})
            if action == 'remove':
                eps.pop(name, None)
            else:
                if action == 'edit' and old_name != name:
                    eps.pop(old_name, None)
                ep = {'address': payload.get('address', '')}
                redirect_to = str(payload.get('redirect_to', '')).strip()
                if redirect_to:
                    ep['http'] = {'redirections': {'entryPoint': {'to': redirect_to, 'scheme': 'https', 'permanent': True}}}
                eps[name] = ep
        elif section == 'resolvers':
            resolvers = config.setdefault('certificatesResolvers', {})
            if action == 'remove':
                resolvers.pop(name, None)
            else:
                if action == 'edit' and old_name != name:
                    resolvers.pop(old_name, None)
                ct   = payload.get('challenge_type', 'dnsChallenge')
                acme = {'email': payload.get('email', ''), 'storage': payload.get('storage', '/acme.json')}
                if ct == 'dnsChallenge':
                    acme['dnsChallenge'] = {'provider': payload.get('provider', '')}
                elif ct == 'httpChallenge':
                    acme['httpChallenge'] = {'entryPoint': payload.get('http_entrypoint', 'web')}
                else:
                    acme['tlsChallenge'] = {}
                resolvers[name] = {'acme': acme}
        elif section == 'plugins':
            plugins = config.setdefault('experimental', {}).setdefault('plugins', {})
            if action == 'remove':
                plugins.pop(name, None)
            else:
                if action == 'edit' and old_name != name:
                    plugins.pop(old_name, None)
                plugins[name] = {'moduleName': payload.get('moduleName', ''), 'version': payload.get('version', '')}
        elif section == 'api' and action == 'set':
            if payload.get('enabled', True):
                api_cfg = {}
                if not payload.get('dashboard', True):
                    api_cfg['dashboard'] = False
                if payload.get('insecure'):
                    api_cfg['insecure'] = True
                if payload.get('debug'):
                    api_cfg['debug'] = True
                config['api'] = api_cfg
            else:
                config.pop('api', None)
        elif section == 'log' and action == 'set':
            level = str(payload.get('level', 'ERROR')).upper()
            if level and level != 'ERROR':
                config['log'] = {'level': level}
            else:
                config.pop('log', None)
            if payload.get('accessLog'):
                al_path = str(payload.get('accessLogPath', '')).strip()
                config['accessLog'] = {'filePath': al_path} if al_path else {}
            else:
                config.pop('accessLog', None)
        elif section == 'providers' and action == 'set':
            providers = config.setdefault('providers', {})
            if payload.get('docker'):
                docker_cfg = {}
                endpoint = str(payload.get('dockerEndpoint', '')).strip()
                if endpoint and endpoint != 'unix:///var/run/docker.sock':
                    docker_cfg['endpoint'] = endpoint
                if payload.get('dockerExposedByDefault'):
                    docker_cfg['exposedByDefault'] = True
                if not payload.get('dockerWatch', True):
                    docker_cfg['watch'] = False
                providers['docker'] = docker_cfg
            else:
                providers.pop('docker', None)
            if payload.get('file'):
                file_cfg = {}
                directory = str(payload.get('fileDirectory', '')).strip()
                if directory:
                    file_cfg['directory'] = directory
                if not payload.get('fileWatch', True):
                    file_cfg['watch'] = False
                providers['file'] = file_cfg
            else:
                providers.pop('file', None)
            if not providers:
                config.pop('providers', None)
        elif section == 'providers' and action in ('add', 'edit', 'remove'):
            providers = config.setdefault('providers', {})
            if action == 'remove':
                providers.pop(name, None)
            else:
                if action == 'edit' and old_name and old_name != name:
                    providers.pop(old_name, None)
                prov_cfg = {}
                yaml_config = str(payload.get('yaml_config', '')).strip()
                if yaml_config:
                    try:
                        _yp = SafeYAML(typ='safe')
                        parsed = _yp.load(yaml_config)
                        if isinstance(parsed, dict):
                            prov_cfg = parsed
                    except Exception:
                        pass
                providers[name] = prov_cfg
            if not providers:
                config.pop('providers', None)
        else:
            return jsonify({'error': f'Unknown section: {section!r}'}), 400
        stream = StringIO()
        _y.dump(config, stream)
        new_raw = stream.getvalue()
        _y2 = SafeYAML(typ='safe')
        parsed = _y2.load(new_raw) or {}
        return jsonify({'ok': True, 'raw': new_raw, 'parsed': parsed})
    except Exception as e:
        logger.exception("Static section update failed")
        return jsonify({'error': str(e)}), 500


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
    static_path = _get_static_config_path()
    if not os.path.exists(static_path):
        return jsonify({'plugins': [], 'error': f'Static config not found at {static_path}. Set STATIC_CONFIG_PATH env var or configure the path in Settings.'})
    try:
        with open(static_path, 'r') as f:
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

@app.route('/api/plugins/install', methods=['POST'])
@csrf_protect
@login_required
def api_plugins_install():
    data = request.get_json(silent=True) or {}
    static_yaml = (data.get('static_yaml') or '').strip()
    middleware_yaml = (data.get('middleware_yaml') or '').strip()
    if not static_yaml:
        return jsonify({'ok': False, 'error': 'Paste the static config snippet'}), 400
    try:
        _ys = SafeYAML(typ='safe')
        parsed_static = _ys.load(static_yaml) or {}
    except Exception as e:
        return jsonify({'ok': False, 'error': f'Invalid static config YAML: {e}'}), 400
    plugins_block = None
    if isinstance(parsed_static.get('experimental'), dict):
        plugins_block = parsed_static['experimental'].get('plugins')
    if not plugins_block and 'plugins' in parsed_static:
        plugins_block = parsed_static['plugins']
    if not plugins_block or not isinstance(plugins_block, dict):
        return jsonify({'ok': False, 'error': 'Could not find plugins block - paste the experimental.plugins YAML from the Traefik plugin page'}), 400
    static_path = _get_static_config_path()
    if not static_path or not os.path.exists(static_path):
        return jsonify({'ok': False, 'error': 'Static config not found'}), 404
    try:
        _ry = YAML()
        _ry.preserve_quotes = True
        with open(static_path, 'r') as f:
            config = _ry.load(f) or {}
        if 'experimental' not in config:
            config['experimental'] = {}
        if 'plugins' not in config['experimental']:
            config['experimental']['plugins'] = {}
        for plugin_name, plugin_data in plugins_block.items():
            config['experimental']['plugins'][plugin_name] = {
                'moduleName': plugin_data.get('moduleName', ''),
                'version': plugin_data.get('version', ''),
            }
        create_backup(static_path)
        stream = StringIO()
        _ry.dump(config, stream)
        with open(static_path, 'w') as f:
            f.write(stream.getvalue())
    except Exception as e:
        logger.exception("Failed to save plugin to static config")
        return jsonify({'ok': False, 'error': str(e)}), 500
    warning = None
    if middleware_yaml and ACTIVE_CONFIG_DIR:
        if '{{' in middleware_yaml:
            return jsonify({'ok': False, 'error': 'The middleware snippet contains template placeholders ({{ ... }}) that must be replaced with real values before saving. Edit the middleware in the editor and replace all {{ }} placeholders.'}), 400
        try:
            _ym = SafeYAML(typ='safe')
            parsed_mw = _ym.load(middleware_yaml) or {}
            if isinstance(parsed_mw.get('http'), dict):
                middlewares = parsed_mw['http'].get('middlewares') or {}
            elif 'middlewares' in parsed_mw:
                middlewares = parsed_mw['middlewares']
            else:
                middlewares = {}
            if middlewares and isinstance(middlewares, dict):
                mw_file = os.path.join(ACTIVE_CONFIG_DIR, 'plugin-middlewares.yml')
                existing = {}
                if os.path.exists(mw_file):
                    with open(mw_file, 'r') as f:
                        existing = yaml.load(f) or {}
                if 'http' not in existing:
                    existing['http'] = {}
                if 'middlewares' not in existing['http']:
                    existing['http']['middlewares'] = {}
                existing['http']['middlewares'].update(middlewares)
                stream = StringIO()
                yaml.dump(existing, stream)
                with open(mw_file, 'w') as f:
                    f.write(stream.getvalue())
        except Exception as e:
            logger.exception("Failed to save middleware")
            warning = f'Plugin saved but middleware could not be written: {e}'
    plugin_names = list(plugins_block.keys())
    add_notification('success', f'Plugin installed: {", ".join(plugin_names)}')
    result = {'ok': True, 'plugins': plugin_names}
    if warning:
        result['warning'] = warning
    return jsonify(result)


def _parse_cert_expiry(pem_bytes):
    try:
        import base64
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend
        if isinstance(pem_bytes, str):
            pem_bytes = base64.b64decode(pem_bytes)
        cert_obj = x509.load_pem_x509_certificate(pem_bytes, default_backend())
        return cert_obj.not_valid_after_utc.strftime('%Y-%m-%dT%H:%M:%SZ')
    except Exception as ex:
        logger.debug(f"Cert parse error: {ex}")
        return None

def _certs_from_tls_configs():
    import base64
    certs = []
    for p in CONFIG_PATHS:
        config = load_config(p)
        for entry in (config.get('tls') or {}).get('certificates') or []:
            cert_file = entry.get('certFile', '')
            if not cert_file or not os.path.exists(cert_file):
                continue
            try:
                pem_bytes = open(cert_file, 'rb').read()
                not_after = _parse_cert_expiry(pem_bytes)
                try:
                    from cryptography import x509
                    from cryptography.hazmat.backends import default_backend
                    cert_obj = x509.load_pem_x509_certificate(pem_bytes, default_backend())
                    sans = [n.value for n in cert_obj.subject_alternative_names(x509.SubjectAlternativeName).get_values_for_type(x509.DNSName)]
                    main = sans[0] if sans else os.path.basename(cert_file)
                except Exception:
                    sans = []
                    main = os.path.basename(cert_file)
                certs.append({'resolver': 'file', 'main': main, 'sans': sans, 'not_after': not_after, 'certFile': cert_file})
            except Exception as ex:
                logger.debug(f"Error reading cert file {cert_file}: {ex}")
    return certs

@app.route('/api/traefik/certs')
@login_required
def api_certs():
    import json as _json
    certs = []
    errors = []

    acme_path = _get_acme_json_path()
    if os.path.exists(acme_path):
        try:
            with open(acme_path, 'r') as f:
                raw = f.read().strip()
            acme_data = _json.loads(raw) if raw else {}
            for resolver_name, resolver_data in acme_data.items():
                if not isinstance(resolver_data, dict):
                    continue
                for c in (resolver_data.get('Certificates') or resolver_data.get('certificates') or []):
                    domain    = c.get('domain', {})
                    not_after = _parse_cert_expiry(c.get('certificate', ''))
                    certs.append({'resolver': resolver_name, 'main': domain.get('main', ''), 'sans': domain.get('sans', []) or [], 'not_after': not_after})
        except Exception as e:
            logger.exception("Error reading acme.json")
            errors.append(str(e))
    else:
        errors.append(f'acme.json not found at {acme_path}. Set ACME_JSON_PATH env var or configure the path in Settings.')

    certs.extend(_certs_from_tls_configs())

    if not certs and errors:
        return jsonify({'certs': [], 'error': ' | '.join(errors)})
    return jsonify({'certs': certs})

@app.route('/api/traefik/logs')
@login_required
def api_logs():
    lines_req = min(int(request.args.get('lines', 100)), 1000)
    log_path = _get_access_log_path()
    if not os.path.exists(log_path):
        return jsonify({'error': f'Access log not found at {log_path}. Set ACCESS_LOG_PATH env var or configure the path in Settings.', 'lines': []})
    try:
        lines = []
        buf_size = 8192
        with open(log_path, 'rb') as f:
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
    static_path = _get_static_config_path()
    static_base = os.path.basename(static_path) if static_path else None
    _name_re    = re.compile(r'^(.+)\.\d{8}_\d{6}\.bak$')
    backups = []
    for f in os.listdir(BACKUP_DIR):
        if f.endswith('.bak'):
            path = os.path.join(BACKUP_DIR, f)
            st   = os.stat(path)
            m    = _name_re.match(f)
            orig = m.group(1) if m else ''
            kind = 'static' if static_base and orig == static_base else 'routes'
            backups.append({
                'name':     f,
                'size':     st.st_size,
                'modified': time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime)),
                'mtime':    st.st_mtime,
                'kind':     kind,
            })
    backups.sort(key=lambda b: b['mtime'], reverse=True)
    for b in backups:
        del b['mtime']
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

@app.route('/api/notifications')
@login_required
def api_notifications():
    with _notif_lock:
        entries = list(reversed(list(_notifications)))
    return jsonify(entries)

@app.route('/api/notifications/delete', methods=['POST'])
@login_required
def api_notifications_delete():
    _check_csrf()
    ts = (request.get_json(silent=True) or {}).get('ts', '')
    if not ts:
        return jsonify({'ok': False, 'message': 'Missing ts'}), 400
    with _notif_lock:
        for i, entry in enumerate(list(_notifications)):
            if entry.get('ts') == ts:
                del _notifications[i]
                break
    threading.Thread(target=_save_notifications_bg, daemon=True).start()
    return jsonify({'ok': True})

@app.route('/api/notifications/clear', methods=['POST'])
@login_required
def api_notifications_clear():
    _check_csrf()
    with _notif_lock:
        _notifications.clear()
    threading.Thread(target=_save_notifications_bg, daemon=True).start()
    return jsonify({'ok': True})

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
        add_notification('warning', f"Backup restored: {filename}")
        return jsonify({'success': True})
    except Exception as e:
        logger.exception("Restore error")
        return jsonify({'error': str(e)}), 500

@app.route('/api/backup/create', methods=['POST'])
@csrf_protect
@login_required
def api_backup_create():
    try:
        created = []
        for p in CONFIG_PATHS:
            dest = create_backup(p)
            if dest:
                created.append(os.path.basename(dest))
        if created:
            add_notification('success', f"Backup created ({len(created)} file{'s' if len(created) > 1 else ''})")
            return jsonify({'success': True, 'names': created, 'count': len(created)})
        return jsonify({'error': 'No config files found to backup'}), 400
    except Exception as e:
        logger.exception("Backup create error")
        return jsonify({'error': str(e)}), 500

@app.route('/api/static/backup/create', methods=['POST'])
@csrf_protect
@login_required
def api_static_backup_create():
    path = _get_static_config_path()
    if not path:
        return jsonify({'error': 'STATIC_CONFIG_PATH not configured'}), 400
    try:
        dest = create_backup(path)
        if dest:
            add_notification('success', f"Static config backup created")
            return jsonify({'success': True, 'name': os.path.basename(dest)})
        return jsonify({'error': 'Static config file not found'}), 400
    except Exception as e:
        logger.exception("Static backup create error")
        return jsonify({'error': str(e)}), 500

@app.route('/api/backup/delete/<filename>', methods=['POST'])
@csrf_protect
@login_required
def api_backup_delete(filename):
    try:
        path = _validated_backup_path(filename)
        if os.path.exists(path):
            os.remove(path)
        add_notification('warning', f"Backup deleted: {filename}")
        return jsonify({'success': True})
    except Exception as e:
        logger.exception("Backup delete error")
        return jsonify({'error': str(e)}), 500


@app.route('/api/settings', methods=['GET'])
@login_required
def api_get_settings():
    s = load_settings()

    s.pop('password_hash', None)
    s.pop('oidc_client_secret', None)
    s['auth_enabled']          = _auth_enabled()
    s['has_password']          = _has_password_set()
    s['auth_env_forced']       = os.environ.get('AUTH_ENABLED', '').strip().lower() in ('false', '0', 'no')
    s['oidc_client_secret_set'] = bool(load_settings().get('oidc_client_secret', ''))
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
        acme_json_path    = str(data.get('acme_json_path', '')).strip()
        access_log_path   = str(data.get('access_log_path', '')).strip()
        static_config_path = str(data.get('static_config_path', '')).strip()
        existing = load_settings()
        save_settings(domains, cert_resolver, traefik_api_url,
                      auth_enabled=existing['auth_enabled'],
                      password_hash=existing['password_hash'],
                      visible_tabs=existing['visible_tabs'],
                      acme_json_path=acme_json_path,
                      access_log_path=access_log_path,
                      static_config_path=static_config_path)
        result = load_settings()
        result.pop('password_hash', None)
        result.pop('oidc_client_secret', None)
        return jsonify({'success': True, 'settings': result})
    except Exception as e:
        logger.exception("Settings save error")
        return jsonify({'error': str(e)}), 500


@app.route('/api/settings/test-connection', methods=['POST'])
@csrf_protect
@login_required
def api_settings_test_connection():
    data    = request.get_json(silent=True) or {}
    raw_url = str(data.get('url', '')).strip()
    url     = _safe_api_url(raw_url)
    if not url:
        return jsonify({'ok': False, 'error': 'Invalid URL'}), 400
    logger.info(f"Connection test to {url!r} by {request.remote_addr}")
    try:
        resp = requests.get(f"{url}/api/version", timeout=4)
        if resp.status_code == 200:
            info = resp.json()
            return jsonify({'ok': True, 'version': info.get('Version', '?')})
        return jsonify({'ok': False, 'error': f'HTTP {resp.status_code}'})
    except Exception:
        return jsonify({'ok': False, 'error': 'Connection failed'})


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


def _find_existing_self_route(hostname: str) -> dict:
    import re
    for cfg_path in CONFIG_PATHS:
        if not os.path.exists(cfg_path):
            continue
        try:
            with open(cfg_path, 'r') as f:
                data = yaml.load(f) or {}
            routers  = (data.get('http') or {}).get('routers') or {}
            services = (data.get('http') or {}).get('services') or {}
            for rname, rdata in routers.items():
                rule = rdata.get('rule', '')
                m = re.search(r'Host\(`([^`]+)`\)', rule)
                if m and m.group(1).lower() == hostname.lower():
                    svc_name = (rdata.get('service') or '').split('@')[0]
                    svc = services.get(svc_name) or {}
                    servers = ((svc.get('loadBalancer') or {}).get('servers') or [])
                    svc_url     = next((str(s['url']) for s in servers if s.get('url')), '')
                    entry_pts   = rdata.get('entryPoints') or ['websecure']
                    entry_point = entry_pts[0] if entry_pts else 'websecure'
                    return {'domain': hostname, 'service_url': svc_url, 'router_name': rname, 'entry_point': entry_point, 'found': True}
        except Exception:
            continue
    return {}

@app.route('/api/settings/self-route', methods=['GET'])
@login_required
def api_get_self_route():
    settings = load_settings()
    sr = settings.get('self_route', {'domain': '', 'service_url': ''})
    default_ep = _best_entrypoint()
    if not sr.get('domain'):
        hostname = request.args.get('hostname', '').strip().lower()
        if hostname:
            found = _find_existing_self_route(hostname)
            if found:
                return jsonify({**found, 'default_entry_point': default_ep})
    return jsonify({**sr, 'default_entry_point': default_ep})

@app.route('/api/settings/self-route', methods=['POST'])
@csrf_protect
@login_required
def api_save_self_route():
    data = request.get_json(silent=True) or {}
    domain      = str(data.get('domain', '')).strip()
    service_url = str(data.get('service_url', '')).strip() or 'http://traefik-manager:5000'
    router_name = str(data.get('router_name', 'traefik-manager')).strip() or 'traefik-manager'
    entry_point = str(data.get('entry_point', '')).strip() or _best_entrypoint()
    settings = load_settings()
    if domain:
        _write_self_route(domain, service_url, settings.get('cert_resolver', 'cloudflare'), router_name, entry_point)
        sr = {'domain': domain, 'service_url': service_url, 'router_name': router_name, 'entry_point': entry_point}
    else:
        _delete_self_route()
        sr = {'domain': '', 'service_url': ''}
    save_settings(
        domains=settings['domains'],
        cert_resolver=settings['cert_resolver'],
        traefik_api_url=settings['traefik_api_url'],
        auth_enabled=settings['auth_enabled'],
        password_hash=settings['password_hash'],
        visible_tabs=settings['visible_tabs'],
        self_route=sr,
    )
    return jsonify({'ok': True})


def load_config(path=None):
    if path is None:
        path = CONFIG_PATH
    if not os.path.exists(path):
        return {}
    with open(path, 'r') as f:
        data = yaml.load(f)
    return data if data and isinstance(data, dict) else {}

def _strip_empty_sections(config: dict) -> dict:
    """Remove empty routers/services/middlewares dicts to avoid Traefik 'standalone element' errors."""
    for proto in ('http', 'tcp', 'udp'):
        if proto in config:
            for section in ('routers', 'services', 'middlewares'):
                if section in config[proto] and not config[proto][section]:
                    del config[proto][section]
            if not config[proto]:
                del config[proto]
    return config

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


def _svc_key(name):
    return name.split('@')[0] if '@' in name else name


def _build_apps(config, config_file='', extra_http_svcs=None, extra_tcp_svcs=None, extra_udp_svcs=None, api_svc_urls=None):
    apps = []
    http_config = config.get('http', {})
    http_svcs = dict(http_config.get('services', {}))
    if extra_http_svcs:
        for k, v in extra_http_svcs.items():
            if k not in http_svcs:
                http_svcs[k] = v
    for rname, rdata in http_config.get('routers', {}).items():
        svc_name = rdata.get('service', '')
        svc_key  = _svc_key(svc_name)
        target_url = 'N/A'
        lb = {}
        if svc_key in http_svcs:
            lb = http_svcs[svc_key].get('loadBalancer', {})
            servers = lb.get('servers', [])
            if servers:
                target_url = servers[0].get('url', 'Unknown')
        if target_url == 'N/A' and api_svc_urls:
            target_url = api_svc_urls.get(f'http:{svc_key}', 'N/A')
        app_id = f"{config_file}::{rname}" if (MULTI_CONFIG and config_file) else rname
        tls_http = rdata.get('tls', {})
        transport_name = lb.get('serversTransport', '')
        transports_cfg = http_config.get('serversTransports', {})
        insecure = bool(transports_cfg.get(transport_name, {}).get('insecureSkipVerify', False)) if transport_name else False
        apps.append({'id': app_id, 'name': rname, 'rule': rdata.get('rule', ''),
                     'service_name': svc_name, 'target': target_url,
                     'middlewares': rdata.get('middlewares', []),
                     'entryPoints': rdata.get('entryPoints', []), 'protocol': 'http',
                     'tls': bool(tls_http), 'enabled': True,
                     'passHostHeader': lb.get('passHostHeader', True),
                     'certResolver': tls_http.get('certResolver', '') if isinstance(tls_http, dict) else '',
                     'insecureSkipVerify': insecure,
                     'configFile': config_file, 'provider': 'file'})
    tcp_svcs = dict(config.get('tcp', {}).get('services', {}))
    if extra_tcp_svcs:
        for k, v in extra_tcp_svcs.items():
            if k not in tcp_svcs:
                tcp_svcs[k] = v
    for rname, rdata in config.get('tcp', {}).get('routers', {}).items():
        svc_name = rdata.get('service', '')
        svc_key  = _svc_key(svc_name)
        target = 'N/A'
        if svc_key in tcp_svcs:
            servers = tcp_svcs[svc_key].get('loadBalancer', {}).get('servers', [])
            if servers:
                target = servers[0].get('address', 'N/A')
        if target == 'N/A' and api_svc_urls:
            target = api_svc_urls.get(f'tcp:{svc_key}', 'N/A')
        app_id = f"{config_file}::{rname}" if (MULTI_CONFIG and config_file) else rname
        tls_tcp = rdata.get('tls', {})
        apps.append({'id': app_id, 'name': rname, 'rule': rdata.get('rule', ''),
                     'service_name': svc_name, 'target': target,
                     'middlewares': [], 'entryPoints': rdata.get('entryPoints', []),
                     'protocol': 'tcp', 'tls': bool(tls_tcp), 'enabled': True,
                     'certResolver': tls_tcp.get('certResolver', '') if isinstance(tls_tcp, dict) else '',
                     'configFile': config_file, 'provider': 'file'})
    udp_svcs = dict(config.get('udp', {}).get('services', {}))
    if extra_udp_svcs:
        for k, v in extra_udp_svcs.items():
            if k not in udp_svcs:
                udp_svcs[k] = v
    for rname, rdata in config.get('udp', {}).get('routers', {}).items():
        svc_name = rdata.get('service', '')
        svc_key  = _svc_key(svc_name)
        target = 'N/A'
        if svc_key in udp_svcs:
            servers = udp_svcs[svc_key].get('loadBalancer', {}).get('servers', [])
            if servers:
                target = servers[0].get('address', 'N/A')
        if target == 'N/A' and api_svc_urls:
            target = api_svc_urls.get(f'udp:{svc_key}', 'N/A')
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


def _traefik_service_url_map():
    url_map = {}
    for proto, addr_key in (('http', 'url'), ('tcp', 'address'), ('udp', 'address')):
        for svc in traefik_api_get(f'/api/{proto}/services') or []:
            key = _svc_key(svc.get('name', ''))
            servers = svc.get('loadBalancer', {}).get('servers', [])
            if servers and addr_key in servers[0]:
                url_map[f'{proto}:{key}'] = servers[0][addr_key]
    return url_map


def _build_external_routes(include_internal=False):
    svc_urls = _traefik_service_url_map()
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
            svc_name = r.get('service', '')
            target = svc_urls.get(f'{proto}:{_svc_key(svc_name)}', svc_name or 'N/A')
            tls = r.get('tls', {})
            routes.append({
                'id':           name,
                'name':         display_name,
                'rule':         r.get('rule', ''),
                'service_name': svc_name,
                'target':       target,
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
    all_apps = []
    all_middlewares = []
    loaded = [(os.path.basename(p) if (MULTI_CONFIG or ACTIVE_CONFIG_DIR) else '', load_config(p)) for p in CONFIG_PATHS]
    combined_http = {}
    combined_tcp  = {}
    combined_udp  = {}
    for _, cfg in loaded:
        for k, v in cfg.get('http', {}).get('services', {}).items():
            combined_http.setdefault(k, v)
        for k, v in cfg.get('tcp', {}).get('services', {}).items():
            combined_tcp.setdefault(k, v)
        for k, v in cfg.get('udp', {}).get('services', {}).items():
            combined_udp.setdefault(k, v)
    api_svc_urls = _traefik_service_url_map()
    for cf, config in loaded:
        all_apps.extend(_build_apps(config, cf, combined_http, combined_tcp, combined_udp, api_svc_urls))
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
    rname = route_id.split('::', 1)[1] if '::' in route_id else route_id

    if enable:
        if route_id not in disabled:
            return
        saved       = disabled.pop(route_id)
        proto       = saved.get('protocol', 'http')
        router      = saved.get('router', {})
        svc_name    = router.get('service', rname)
        svc         = saved.get('service', {})
        cf          = saved.get('configFile', '')
        target_path = _resolve_config_path(cf)
        if not target_path and cf:
            safe_cf     = cf if cf.endswith(('.yml', '.yaml')) else cf + '.yml'
            target_path = os.path.join(os.path.dirname(CONFIG_PATH) or '.', safe_cf)
            if not _is_safe_path(target_path):
                target_path = CONFIG_PATH
        config      = load_config(target_path)
        section     = config.setdefault(proto, {})
        section.setdefault('routers', {})[rname]   = router
        section.setdefault('services', {})[svc_name] = svc
        create_backup(target_path)
        save_config(_strip_empty_sections(config), target_path)
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
                if rname in routers:
                    proto       = prot
                    router      = dict(routers.pop(rname))
                    svc_name    = router.get('service', rname)
                    svc         = dict(config.get(prot, {}).get('services', {}).pop(svc_name, {}))
                    target_path = p
                    break
            if proto:
                break
        if proto is None:
            return
        cf = os.path.basename(target_path) if (MULTI_CONFIG or ACTIVE_CONFIG_DIR) else ''
        disabled[route_id] = {'protocol': proto, 'router': router, 'service': svc, 'configFile': cf}
        create_backup(target_path)
        save_config(_strip_empty_sections(config), target_path)

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
    return jsonify({
        'files': [{'label': os.path.basename(p), 'path': p} for p in CONFIG_PATHS],
        'configDirSet': bool(ACTIVE_CONFIG_DIR),
    })


def _read_groups_config():
    if not os.path.exists(GROUPS_CONFIG_FILE):
        return {'custom_groups': [], 'route_overrides': {}}
    try:
        _y = SafeYAML(typ='safe')
        with open(GROUPS_CONFIG_FILE, 'r') as f:
            data = _y.load(f)
        if not data:
            return {'custom_groups': [], 'route_overrides': {}}
        return {
            'custom_groups':   list(data.get('custom_groups', []) or []),
            'route_overrides': dict(data.get('route_overrides', {}) or {}),
        }
    except Exception:
        logger.exception("Failed to read dashboard config")
        return {'custom_groups': [], 'route_overrides': {}}

def _write_groups_config(data):
    _y = SafeYAML(typ='safe')
    with open(GROUPS_CONFIG_FILE, 'w') as f:
        _y.dump({
            'custom_groups':   list(data.get('custom_groups', []) or []),
            'route_overrides': dict(data.get('route_overrides', {}) or {}),
        }, f)

@app.route('/api/dashboard/config', methods=['GET'])
@login_required
def dashboard_config_get():
    cfg = _read_groups_config()
    sr  = load_settings().get('self_route', {})
    cfg['tm_route_name'] = sr.get('router_name', 'traefik-manager') or 'traefik-manager'
    return jsonify(cfg)

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
        cert_resolver_raw = request.form.get('certResolver', '').strip()
        cert_resolver  = '' if (cert_resolver_raw in ('__none__', 'none')) else (cert_resolver_raw or (resolvers[0] if resolvers else ''))
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

        plain_original_id = original_id.split('::', 1)[1] if '::' in original_id else original_id
        if is_edit and plain_original_id:
            for sec in ('http', 'tcp', 'udp'):
                s = config.get(sec, {})
                old_routers = s.get('routers', {})
                old_svc = (old_routers.get(plain_original_id, {}).get('service') or '').strip()
                if plain_original_id != router_name and plain_original_id in old_routers:
                    del old_routers[plain_original_id]
                if old_svc and old_svc != service_name and 'services' in s and old_svc in s['services']:
                    del s['services'][old_svc]

        if protocol == 'http':
            selected_domains = request.form.getlist('domains') or [domain]
            if subdomain and '.' in subdomain:
                rule = f"Host(`{subdomain}`)"
            elif subdomain:
                hosts = [f"Host(`{subdomain}.{d}`)" for d in selected_domains]
                rule  = " || ".join(hosts)
            else:
                hosts = [f"Host(`{d}`)" for d in selected_domains]
                rule  = " || ".join(hosts)
            target_url = target_ip if target_ip.startswith('http') else f"{scheme}://{target_ip}:{target_port}"
            mws        = [m.strip() for m in middlewares_in.split(',')] if middlewares_in else []
            insecure   = request.form.get('insecureSkipVerify') == 'true'
            config.setdefault('http', {}).setdefault('routers', {})
            config['http'].setdefault('services', {})
            tls_val = {'certResolver': cert_resolver} if cert_resolver else {}
            r = {'rule': rule, 'entryPoints': http_eps, 'tls': tls_val, 'service': service_name}
            if mws:
                r['middlewares'] = mws
            lb = {'servers': [{'url': target_url}]}
            if not pass_host:
                lb['passHostHeader'] = False
            transport_name = f"{svc_name}-transport"
            if insecure:
                lb['serversTransport'] = transport_name
                config['http'].setdefault('serversTransports', {})[transport_name] = {'insecureSkipVerify': True}
            elif not insecure:
                existing_transports = config.get('http', {}).get('serversTransports', {})
                if transport_name in existing_transports:
                    del existing_transports[transport_name]
                    if not existing_transports:
                        del config['http']['serversTransports']
            config['http']['routers'][router_name]   = r
            config['http']['services'][service_name] = {'loadBalancer': lb}

        elif protocol == 'tcp':
            rule = tcp_rule or (f"HostSNI(`{subdomain}.{domain}`)" if subdomain else "HostSNI(`*`)")
            config.setdefault('tcp', {}).setdefault('routers', {})
            config['tcp'].setdefault('services', {})
            tcp_tls = {'certResolver': cert_resolver} if cert_resolver else {}
            config['tcp']['routers'][router_name]   = {'rule': rule, 'entryPoints': tcp_eps, 'tls': tcp_tls, 'service': service_name}
            config['tcp']['services'][service_name] = {'loadBalancer': {'servers': [{'address': f"{target_ip}:{target_port}"}]}}

        elif protocol == 'udp':
            udp_ep = request.form.get('udpEntryPoint', '').strip()
            config.setdefault('udp', {}).setdefault('routers', {})
            config['udp'].setdefault('services', {})
            config['udp']['routers'][router_name]   = {'entryPoints': [udp_ep] if udp_ep else [], 'service': service_name}
            config['udp']['services'][service_name] = {'loadBalancer': {'servers': [{'address': f"{target_ip}:{target_port}"}]}}

        save_config(_strip_empty_sections(config), target_path)
        _register_config_path(target_path)
        msg = f"Successfully saved {svc_name}"
        action = "updated" if is_edit else "created"
        add_notification('success', f"Route {svc_name} {action}")
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
        # Strip configFile:: prefix from router_id (MULTI_CONFIG mode)
        plain_id = router_id.split('::', 1)[1] if '::' in router_id else router_id
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
                if plain_id in s.get('routers', {}):
                    svc = (s['routers'][plain_id].get('service') or '').strip()
                    del s['routers'][plain_id]
                    if svc and 'services' in s and svc in s['services']:
                        del s['services'][svc]
                    create_backup(target_path)
                    save_config(_strip_empty_sections(config), target_path)
                    deleted = True
                    break
            if deleted:
                break
        if not deleted:
            if fetch:
                return jsonify({'ok': False, 'message': f'Route "{plain_id}" not found'}), 404
            flash(f'Route "{plain_id}" not found', "error")
            return redirect(url_for('index'))
        msg = f"Deleted {plain_id}"
        add_notification('warning', f"Route {plain_id} deleted")
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
        config['http']['middlewares'][mw_name] = SafeYAML(typ='safe').load(mw_content)
        save_config(_strip_empty_sections(config), target_path)
        _register_config_path(target_path)
        msg = f"Successfully saved middleware {mw_name}"
        action = "updated" if is_edit else "created"
        add_notification('success', f"Middleware {mw_name} {action}")
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
                save_config(_strip_empty_sections(config), target_path)
                break
        msg = f"Deleted middleware {mw_name}"
        add_notification('warning', f"Middleware {mw_name} deleted")
        if fetch:
            return jsonify({'ok': True, 'message': msg})
        flash(msg, "success")
    except Exception:
        logger.exception("Middleware delete error")
        if fetch:
            return jsonify({'ok': False, 'message': 'Error deleting middleware'}), 500
        flash("Error deleting middleware", "error")
    return redirect(url_for('index'))


@app.route('/auth/oidc/login')
@limiter.limit("10 per minute")
def oidc_login():
    s = load_settings()
    if not s.get('oidc_enabled'):
        return redirect(url_for('login'))
    provider_url = s.get('oidc_provider_url', '').rstrip('/')
    if not provider_url:
        return redirect(url_for('login'))
    try:
        disc = requests.get(f"{provider_url}/.well-known/openid-configuration", timeout=5)
        disc.raise_for_status()
        cfg = disc.json()
    except Exception:
        logger.exception("OIDC discovery failed")
        flash("OIDC provider unavailable. Try again later.", "error")
        return redirect(url_for('login'))
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    session['oidc_state'] = state
    session['oidc_nonce'] = nonce
    redirect_uri = url_for('oidc_callback', _external=True)
    from urllib.parse import urlencode
    params = urlencode({
        'response_type': 'code',
        'client_id':     s.get('oidc_client_id', ''),
        'redirect_uri':  redirect_uri,
        'scope':         'openid email profile',
        'state':         state,
        'nonce':         nonce,
    })
    return redirect(f"{cfg['authorization_endpoint']}?{params}")


@app.route('/auth/oidc/callback')
def oidc_callback():
    s = load_settings()
    if not s.get('oidc_enabled'):
        return redirect(url_for('login'))
    state = request.args.get('state', '')
    if not state or not secrets.compare_digest(state, session.get('oidc_state', '')):
        flash("Invalid OIDC state. Please try again.", "error")
        return redirect(url_for('login'))
    code = request.args.get('code', '')
    if not code:
        flash("OIDC login failed - no code returned.", "error")
        return redirect(url_for('login'))
    provider_url = s.get('oidc_provider_url', '').rstrip('/')
    try:
        disc = requests.get(f"{provider_url}/.well-known/openid-configuration", timeout=5)
        disc.raise_for_status()
        cfg = disc.json()
    except Exception:
        logger.exception("OIDC discovery failed in callback")
        flash("OIDC provider unavailable.", "error")
        return redirect(url_for('login'))
    try:
        token_resp = requests.post(cfg['token_endpoint'], data={
            'grant_type':   'authorization_code',
            'code':         code,
            'redirect_uri': url_for('oidc_callback', _external=True),
            'client_id':    s.get('oidc_client_id', ''),
            'client_secret': s.get('oidc_client_secret', ''),
        }, timeout=10)
        token_resp.raise_for_status()
        tokens = token_resp.json()
    except Exception:
        logger.exception("OIDC token exchange failed")
        flash("OIDC login failed - token exchange error.", "error")
        return redirect(url_for('login'))
    id_token = tokens.get('id_token', '')
    expected_nonce = session.pop('oidc_nonce', '')
    if id_token and expected_nonce:
        try:
            import base64, json as _json
            payload_b64 = id_token.split('.')[1]
            payload_b64 += '=' * (-len(payload_b64) % 4)
            id_claims = _json.loads(base64.urlsafe_b64decode(payload_b64))
            if not secrets.compare_digest(str(id_claims.get('nonce', '')), expected_nonce):
                logger.warning(f"OIDC nonce mismatch from {request.remote_addr}")
                flash("OIDC login failed - nonce mismatch.", "error")
                return redirect(url_for('login'))
        except Exception:
            logger.warning("OIDC id_token nonce verification skipped - could not decode token")
    access_token = tokens.get('access_token', '')
    try:
        userinfo_resp = requests.get(cfg['userinfo_endpoint'],
                                     headers={'Authorization': f'Bearer {access_token}'}, timeout=10)
        userinfo_resp.raise_for_status()
        userinfo = userinfo_resp.json()
    except Exception:
        logger.exception("OIDC userinfo fetch failed")
        flash("OIDC login failed - could not fetch user info.", "error")
        return redirect(url_for('login'))
    email  = str(userinfo.get('email', '')).strip().lower()
    name   = str(userinfo.get('name', userinfo.get('preferred_username', email))).strip()
    groups = userinfo.get(s.get('oidc_groups_claim', 'groups'), [])
    if not isinstance(groups, list):
        groups = [str(groups)]
    allowed_emails = [e.strip().lower() for e in s.get('oidc_allowed_emails', '').split(',') if e.strip()]
    allowed_groups = [g.strip() for g in s.get('oidc_allowed_groups', '').split(',') if g.strip()]
    if allowed_emails and email not in allowed_emails:
        logger.warning(f"OIDC login denied for {email!r} - not in allowed emails")
        flash("Your account is not authorized to access this application.", "error")
        return redirect(url_for('login'))
    if allowed_groups and not any(g in allowed_groups for g in groups):
        logger.warning(f"OIDC login denied for {email!r} - no matching group")
        flash("Your account is not authorized to access this application.", "error")
        return redirect(url_for('login'))
    session.clear()
    session.update({
        'authenticated': True,
        'last_active':   time.time(),
        'login_time':    datetime.now(timezone.utc).isoformat(),
        'oidc_email':    email,
        'oidc_name':     name,
    })
    logger.info(f"OIDC login success for {email!r} from {request.remote_addr}")
    return redirect(url_for('index'))


@app.route('/api/auth/oidc', methods=['GET'])
@login_required
def api_get_oidc():
    s = load_settings()
    return jsonify({
        'oidc_enabled':         s.get('oidc_enabled', False),
        'oidc_provider_url':    s.get('oidc_provider_url', ''),
        'oidc_client_id':       s.get('oidc_client_id', ''),
        'oidc_client_secret_set': bool(s.get('oidc_client_secret', '')),
        'oidc_display_name':    s.get('oidc_display_name', 'OIDC'),
        'oidc_allowed_emails':  s.get('oidc_allowed_emails', ''),
        'oidc_allowed_groups':  s.get('oidc_allowed_groups', ''),
        'oidc_groups_claim':    s.get('oidc_groups_claim', 'groups'),
    })


@app.route('/api/auth/oidc', methods=['POST'])
@csrf_protect
@login_required
def api_save_oidc():
    try:
        data = request.get_json(silent=True) or {}
        s    = load_settings()
        secret_raw = str(data.get('oidc_client_secret', '')).strip()
        if not secret_raw:
            secret_raw = s.get('oidc_client_secret', '')
        save_settings(
            domains=s['domains'],
            cert_resolver=s['cert_resolver'],
            traefik_api_url=s['traefik_api_url'],
            oidc_enabled=bool(data.get('oidc_enabled', False)),
            oidc_provider_url=str(data.get('oidc_provider_url', '')).strip(),
            oidc_client_id=str(data.get('oidc_client_id', '')).strip(),
            oidc_client_secret=secret_raw,
            oidc_display_name=str(data.get('oidc_display_name', 'OIDC')).strip() or 'OIDC',
            oidc_allowed_emails=str(data.get('oidc_allowed_emails', '')).strip(),
            oidc_allowed_groups=str(data.get('oidc_allowed_groups', '')).strip(),
            oidc_groups_claim=str(data.get('oidc_groups_claim', 'groups')).strip() or 'groups',
        )
        return jsonify({'ok': True})
    except Exception:
        logger.exception("OIDC save error")
        return jsonify({'ok': False, 'error': 'Save failed'}), 500


@app.route('/api/auth/oidc/test', methods=['POST'])
@csrf_protect
@login_required
def api_test_oidc():
    data = request.get_json(silent=True) or {}
    url  = str(data.get('provider_url', '')).strip().rstrip('/')
    if not url:
        return jsonify({'ok': False, 'error': 'No provider URL'})
    logger.info(f"OIDC provider test to {url!r} by {request.remote_addr}")
    try:
        resp = requests.get(f"{url}/.well-known/openid-configuration", timeout=5)
        resp.raise_for_status()
        cfg = resp.json()
        return jsonify({'ok': True, 'issuer': cfg.get('issuer', url)})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


if __name__ == '__main__':
    logger.info("Development server starting...")
    app.run(host='0.0.0.0', port=5000, debug=False)
else:
    logger.info("🟢 Traefik Manager: Server is UP and Ready")

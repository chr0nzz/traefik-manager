import fcntl
import os
import re
import time
import base64
import hashlib
from urllib.parse import quote, urlparse
import shutil
import secrets
import threading
import ipaddress
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from datetime import datetime, timezone, timedelta
import click
from flask import (Flask, render_template, request, redirect,
                   url_for, flash, jsonify, abort, session, send_file)
from werkzeug.middleware.proxy_fix import ProxyFix
from ruamel.yaml import YAML
from ruamel.yaml import YAML as SafeYAML
from ruamel.yaml.scalarstring import DoubleQuotedScalarString
from io import StringIO

from core import env
from core.env import GITHUB_REPO, APP_VERSION, logger, PROXY_FIX_HOPS
from core import crypto

from core import config as _cfg
yaml                   = _cfg.yaml
_yaml_safe             = _cfg.yaml_safe
_safe_file_path        = _cfg.safe_file_path
_readable_config_path  = _cfg.readable_config_path
_is_safe_path          = _cfg.is_safe_path
_resolve_config_path   = _cfg.resolve_config_path
_safe_api_url          = _cfg.safe_api_url
_sanitize_go_templates = _cfg.sanitize_go_templates
_restore_go_templates  = _cfg.restore_go_templates
load_config            = _cfg.load_config
_strip_empty_sections  = _cfg.strip_empty_sections
save_config            = _cfg.save_config
_svc_key               = _cfg.svc_key
_as_dict               = _cfg.as_dict
_load_config_display         = _cfg._load_config_display
_get_config_parse_errors     = _cfg._get_config_parse_errors
from core import agents_store as _ag
from core import settings as _settings
OPTIONAL_TABS     = _settings.OPTIONAL_TABS
load_settings     = _settings.load_settings
save_settings     = _settings.save_settings
_get_acme_json_path      = _settings._get_acme_json_path
_get_access_log_path     = _settings._get_access_log_path
_get_static_config_path  = _settings._get_static_config_path
_get_restart_method      = _settings._get_restart_method
load_agents       = _ag.load_agents
save_agents_file  = _ag.save_agents_file
_save_agents      = _ag.encrypt_agents
_parse_agent_dict = _ag.parse_agent_dict
from core import backups as _back
from core import notifications as _noti
from core import notify_providers as _notify_providers
from core import monitor as _monitor
from core import updates as _updates
from core import traefik as _trae
from core import agents_http as _agen
from core import git as _git
from core import auth as _auth
from core import routes_build as _rb
from core import crowdsec as _crowd
from core import certs as _certs
_parse_cert_expiry           = _certs._parse_cert_expiry
_certs_from_tls_configs      = _certs._certs_from_tls_configs
from core import self_route as _self_r
_self_route_path             = _self_r._self_route_path
_detect_self_route_domain    = _self_r._detect_self_route_domain
_detect_self_route_from_own_labels = _self_r._detect_self_route_from_own_labels
_find_existing_self_route    = _self_r._find_existing_self_route
_write_self_route            = _self_r._write_self_route
_delete_self_route           = _self_r._delete_self_route
SELF_ROUTE_FILENAME          = _self_r.SELF_ROUTE_FILENAME
_cs_lapi_url               = _crowd._cs_lapi_url
_cs_api_key                = _crowd._cs_api_key
_cs_machine_id             = _crowd._cs_machine_id
_cs_machine_password       = _crowd._cs_machine_password
_cs_has_machine            = _crowd._cs_has_machine
_cs_has_cert               = _crowd._cs_has_cert
_cs_tls_kwargs             = _crowd._cs_tls_kwargs
cs_timeout                 = _crowd.cs_timeout
cs_alert_limit             = _crowd.cs_alert_limit
_cs_request                = _crowd._cs_request
_cs_request_strict         = _crowd._cs_request_strict
CrowdSecUnavailable        = _crowd.CrowdSecUnavailable
_cs_jwt_cache              = _crowd._cs_jwt_cache
_cs_jwt                    = _crowd._cs_jwt
_cs_machine_request        = _crowd._cs_machine_request
from core import geoip as _geoip
_geoip_enabled             = _geoip._geoip_enabled
_geoip_db_path             = _geoip._geoip_db_path
_geoip_reader              = _geoip._geoip_reader
_geoip_lookup              = _geoip._geoip_lookup
_geoip_status              = _geoip._geoip_status
_geoip_download            = _geoip._geoip_download
_DBIP_URL                  = _geoip._DBIP_URL
_GEOIP_SENTINEL            = _geoip._GEOIP_SENTINEL
_geoip_cache               = _geoip._geoip_cache
_geoip_lock                = _geoip._geoip_lock
_geoip_state               = _geoip._geoip_state
_trusted_ip_key                = _rb._trusted_ip_key
_merge_trusted_ips             = _rb._merge_trusted_ips
_apply_managed_keys            = _rb._apply_managed_keys
_merge_router                  = _rb._merge_router
_merge_service                 = _rb._merge_service
from core import composite_services as _composite
from core import service_ownership as _svc_own


def _router_resolves_to_composite(router_name: str, agent=None) -> bool:
    if not router_name:
        return False
    try:
        configs = list(_agent_load_configs(agent).values()) if agent else [
            load_config(p) for p in env.CONFIG_PATHS]
    except Exception:
        return False
    for cfg in configs:
        for section in ('http', 'tcp', 'udp'):
            routers = (cfg.get(section) or {}).get('routers') or {}
            router = routers.get(router_name)
            if not isinstance(router, dict):
                continue
            svc = str(router.get('service') or '').split('@')[0]
            svc_def = ((cfg.get(section) or {}).get('services') or {}).get(svc)
            if _svc_own.composite_type(svc_def):
                return True
    return False


def _svc_ledger_key(name, agent_id=''):
    return _svc_own.ledger_key(name, agent_id)
_json_plain                    = _rb._json_plain
_headers_preset_defaults       = _rb._headers_preset_defaults
_build_permissions_policy      = _rb._build_permissions_policy
_build_headers_middleware      = _rb._build_headers_middleware
_parse_permissions_policy      = _rb._parse_permissions_policy
_decode_headers_middleware     = _rb._decode_headers_middleware
_to_list                       = _rb._to_list
_service_type                  = _rb._service_type
_build_apps                    = _rb._build_apps
_build_middlewares             = _rb._build_middlewares
_traefik_router_ep_map         = _rb._traefik_router_ep_map
_traefik_service_url_map       = _rb._traefik_service_url_map
_build_external_routes         = _rb._build_external_routes
_entrypoint_mw_map             = _rb._entrypoint_mw_map
_build_all_apps                = _rb._build_all_apps
HEADERS_PRESET_FEATURES        = _rb.HEADERS_PRESET_FEATURES
HEADERS_PRESET_HSTS_SECONDS    = _rb.HEADERS_PRESET_HSTS_SECONDS
HEADERS_PRESET_REFERRER_DEFAULT = _rb.HEADERS_PRESET_REFERRER_DEFAULT
HEADERS_PRESET_REFERRER_VALUES = _rb.HEADERS_PRESET_REFERRER_VALUES
HEADERS_PRESET_SELF_DEFAULT    = _rb.HEADERS_PRESET_SELF_DEFAULT
_HEADERS_PRESET_KEYS           = _rb._HEADERS_PRESET_KEYS
_PERM_TOKEN_TO_VALUE           = _rb._PERM_TOKEN_TO_VALUE
_PERM_VALUE_TO_TOKEN           = _rb._PERM_VALUE_TO_TOKEN
_auth_enabled          = _auth._auth_enabled
_oidc_active           = _auth._oidc_active
_auth_required         = _auth._auth_required
_get_csrf_token        = _auth._get_csrf_token
_check_csrf            = _auth._check_csrf
csrf_protect           = _auth.csrf_protect
_check_password        = _auth._check_password
_verify_api_key        = _auth._verify_api_key
_is_authenticated      = _auth._is_authenticated
_check_inactivity      = _auth._check_inactivity
_check_api_key         = _auth._check_api_key
login_required         = _auth.login_required
_CsrfError = _auth._CsrfError
_git_repo_dir              = _git._git_repo_dir
_valid_git_url             = _git._valid_git_url
_safe_git_branch           = _git._safe_git_branch
_git_askpass_path          = _git._git_askpass_path
_git_run                   = _git._git_run
_git_ensure_repo_at        = _git._git_ensure_repo_at
_git_ensure_repo           = _git._git_ensure_repo
_git_lock                  = _git._git_lock
_git_push_configs          = _git._git_push_configs
_git_push_if_enabled       = _git._git_push_if_enabled
_git_agent_repo_dir        = _git._git_agent_repo_dir
_agent_git_branch          = _git._agent_git_branch
_git_push_agent_configs    = _git._git_push_agent_configs
_git_push_agent_if_enabled = _git._git_push_agent_if_enabled
_git_show_first            = _git._git_show_first
_GIT_ALLOWED_SCHEMES = _git._GIT_ALLOWED_SCHEMES
_GIT_PROTO_HARDENING = _git._GIT_PROTO_HARDENING
ensure_backup_dir            = _back.ensure_backup_dir
_backup_keep_count           = _back._backup_keep_count
_prune_backups               = _back._prune_backups
create_backup                = _back.create_backup
_send_webhook                = _noti._send_webhook
_fire_webhook                = _noti._fire_webhook
_load_notifications          = _noti._load_notifications
get_notifications            = _noti.get_notifications
delete_notification          = _noti.delete_notification
clear_notifications          = _noti.clear_notifications
add_notification             = _noti.add_notification
_traefik_verify              = _trae._traefik_verify
traefik_api_get              = _trae.traefik_api_get
traefik_api_get_all          = _trae.traefik_api_get_all
_fetch_traefik_routers_and_services = _trae._fetch_traefik_routers_and_services
_agent_by_id                 = _agen._agent_by_id
_agent_request               = _agen._agent_request
_agent_load_configs          = _agen._agent_load_configs
_agent_write_config          = _agen._agent_write_config
_notifications = _noti._notifications
_notif_lock    = _noti._notif_lock

class _BasePathMiddleware:
    def __init__(self, wsgi_app, prefix):
        self.wsgi_app = wsgi_app
        self.prefix = prefix

    def __call__(self, environ, start_response):
        path = environ.get('PATH_INFO', '')
        if path == self.prefix or path.startswith(self.prefix + '/'):
            environ['PATH_INFO'] = path[len(self.prefix):] or '/'
        environ['SCRIPT_NAME'] = self.prefix
        return self.wsgi_app(environ, start_response)


app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=PROXY_FIX_HOPS, x_proto=1, x_host=1)
if env.BASE_PATH:
    app.wsgi_app = _BasePathMiddleware(app.wsgi_app, env.BASE_PATH)
    app.config['APPLICATION_ROOT'] = env.BASE_PATH

_CONFIG_DIR      = os.path.dirname(os.environ.get('SETTINGS_PATH', '/app/config/manager.yml'))
_SECRET_KEY_PATH = os.path.join(_CONFIG_DIR, '.secret_key')

def _load_or_create_secret_key() -> bytes:
    env_key = os.environ.get('SECRET_KEY', '').strip()
    if env_key:
        if len(env_key) < 32:
            raise SystemExit("SECRET_KEY must be at least 32 characters. Generate one with: python3 -c \"import secrets; print(secrets.token_hex(32))\"")
        return env_key.encode()
    if os.path.exists(_SECRET_KEY_PATH):
        key = open(_SECRET_KEY_PATH, 'rb').read().strip()
        if len(key) >= 32:
            return key
    key = secrets.token_hex(32).encode()
    key_dir = os.path.dirname(_SECRET_KEY_PATH)
    os.makedirs(key_dir, exist_ok=True)
    tmp = os.path.join(key_dir, '.secret_key.%d.tmp' % os.getpid())
    with open(tmp, 'wb') as f:
        f.write(key)
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    try:
        os.link(tmp, _SECRET_KEY_PATH)
    except FileExistsError:
        existing = open(_SECRET_KEY_PATH, 'rb').read().strip()
        if len(existing) >= 32:
            key = existing
    except OSError:
        with open(_SECRET_KEY_PATH, 'wb') as f:
            f.write(key)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
    return key

app.secret_key = _load_or_create_secret_key()

_OTP_KEY_PATH        = env.OTP_KEY_PATH
_get_otp_fernet      = crypto.get_otp_fernet
_encrypt_otp_secret  = crypto.encrypt_secret
_decrypt_otp_secret  = crypto.decrypt_secret


def load_templates() -> list:
    if not os.path.exists(TEMPLATES_PATH):
        return []
    try:
        with open(TEMPLATES_PATH, 'r') as f:
            raw = _yaml_safe.load(f) or {}
        return [
            {'id': str(t['id']), 'name': str(t.get('name', ''))[:100], 'yaml': str(t.get('yaml', ''))}
            for t in (raw.get('templates', []) or [])
            if isinstance(t, dict) and t.get('id') and t.get('name')
        ]
    except Exception as e:
        logger.warning(f"Could not load templates.yml: {e}")
        return []


def save_templates_file(templates: list):
    import json as _json
    os.makedirs(os.path.dirname(TEMPLATES_PATH), exist_ok=True)
    tmp = f"{TEMPLATES_PATH}.tmp.{os.getpid()}.{threading.get_ident()}"
    safe = [{'id': t['id'], 'name': t['name'], 'yaml': t['yaml']} for t in templates]
    try:
        with open(tmp, 'w') as f:
            yaml.dump({'templates': _json.loads(_json.dumps(safe))}, f)
        os.replace(tmp, TEMPLATES_PATH)
    finally:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass


app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
app.config['SESSION_COOKIE_HTTPONLY']    = True
app.config['SESSION_COOKIE_SAMESITE']    = 'Lax'


app.config['SESSION_COOKIE_SECURE']      = os.environ.get('COOKIE_SECURE', 'false').lower() == 'true'


INACTIVITY_TIMEOUT = _auth.INACTIVITY_TIMEOUT

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
limiter = Limiter(get_remote_address, app=app, default_limits=[], storage_uri="memory://")


BACKUP_DIR         = env.BACKUP_DIR
SETTINGS_PATH      = env.SETTINGS_PATH
_CONFIG_DIR        = env.CONFIG_DIR
GROUPS_CACHE_DIR   = env.GROUPS_CACHE_DIR
GEOIP_DIR          = env.GEOIP_DIR
GROUPS_CONFIG_FILE = env.GROUPS_CONFIG_FILE
NOTIFICATIONS_PATH = env.NOTIFICATIONS_PATH
AGENTS_PATH        = env.AGENTS_PATH
TEMPLATES_PATH     = env.TEMPLATES_PATH


ACTIVE_CONFIG_DIR = env.ACTIVE_CONFIG_DIR
_ALLOWED_API_SCHEMES = env.ALLOWED_API_SCHEMES


def _ssrf_ok(url: str) -> bool:
    try:
        from urllib.parse import urlparse
        import socket, ipaddress
        host = urlparse(url).hostname
        if not host:
            return False
        for res in socket.getaddrinfo(host, None):
            ip = ipaddress.ip_address(res[4][0])
            if ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
                return False
        return True
    except Exception:
        return False


def _register_config_path(path: str):
    env.register_config_path(path)


GEOIP_CHECK_INTERVAL = 86400


def _geoip_autoupdate_loop():
    lock_path = os.path.join(env.CONFIG_DIR, '.geoip.lock')
    while True:
        fh = None
        try:
            fh = open(lock_path, 'a+')
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            _geoip_maybe_autoupdate()
        except (OSError, BlockingIOError):
            pass
        except Exception:
            logger.exception("GeoIP auto-update check failed")
        finally:
            if fh is not None:
                try:
                    fh.close()
                except Exception:
                    pass
        time.sleep(GEOIP_CHECK_INTERVAL)


def _geoip_maybe_autoupdate():
    try:
        if not _geoip_enabled():
            return
        path = _geoip_db_path()
        stale = True
        if os.path.exists(path):
            try:
                stale = (time.time() - os.path.getmtime(path)) > 35 * 86400
            except OSError:
                stale = True
        if stale:
            _geoip_download()
    except Exception:
        logger.exception("GeoIP auto-update failed")

def _get_traefik_container() -> str:
    return os.environ.get('TRAEFIK_CONTAINER', 'traefik')

def _get_signal_file_path() -> str:
    return os.environ.get('SIGNAL_FILE_PATH', '/signals/restart.sig')


def _best_entrypoint() -> str:
    eps = traefik_api_get_all('/api/entrypoints') or []
    for ep in eps:
        addr = ep.get('address', '')
        if ':443' in addr or '/443' in addr:
            return ep.get('name', 'websecure')
    if eps:
        return eps[0].get('name', 'websecure')
    return 'websecure'


def _detect_setup_self_route() -> tuple[str, str]:
    settings = load_settings()
    saved = settings.get('self_route', {})
    if saved.get('domain'):
        return saved['domain'], saved.get('service_url', 'http://traefik-manager:5000')
    domain = _detect_self_route_domain()
    if domain:
        return domain, 'http://traefik-manager:5000'
    return _detect_self_route_from_own_labels()


def _password_error(pw: str, label: str = 'Password') -> str | None:
    if len(pw) < 8:
        return label + ' must be at least 8 characters.'
    if len(pw.encode('utf-8')) > 72:
        return (label + ' must be 72 bytes or fewer, which is the bcrypt limit. '
                'Accented and non-Latin characters take more than one byte each.')
    return None


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
if env.MULTI_CONFIG:
    for _cp in env.CONFIG_PATHS:
        logger.info(f"Config File:    {_cp}")
elif ACTIVE_CONFIG_DIR:
    logger.info(f"Config Dir:     {ACTIVE_CONFIG_DIR}")
else:
    logger.info(f"Config Path:    {env.CONFIG_PATH}")
logger.info(f"Settings Path:  {SETTINGS_PATH}")
logger.info(f"Backup Dir:     {BACKUP_DIR}")
logger.info(f"Traefik API:    {_s['traefik_api_url']}")
logger.info(f"Restart Method: {_restart_meth}")
logger.info(f"Trusted Hops:   {PROXY_FIX_HOPS}")
logger.info(f"Static Config:  {_static_path if _static_path else 'not configured'}")
logger.info(f"Domains:        {_s['domains']}")
logger.info(f"Cert Resolver:  {_s['cert_resolver'] or 'not set'}")
logger.info(f"Auth Enabled:   {_auth_enabled()}")
if _s.get('oidc_enabled'):
    logger.info(f"OIDC:           enabled ({_s.get('oidc_issuer', '')})")
if not _auth_enabled() and not _s.get('oidc_enabled'):
    if _s.get('auth_external_ack'):
        logger.info("Auth:           delegated to an external provider (acknowledged in Settings)")
    else:
        logger.warning("SECURITY: no authentication is active - the web UI is publicly accessible. Enable a password or OIDC.")
if _s.get('oidc_enabled') and not _s.get('oidc_allowed_emails', '').strip() and not _s.get('oidc_allowed_groups', '').strip() and not _s.get('oidc_allow_any_authenticated'):
    logger.warning("SECURITY: OIDC is enabled with no allowed emails/groups - logins are denied until you set an allowlist or enable 'Allow any authenticated account'.")
logger.info("===========================================")

_ensure_password()


@app.context_processor
def _inject_theme():
    try:
        return {'default_theme': load_settings().get('default_theme', 'dark')}
    except Exception:
        return {'default_theme': 'dark'}


@app.errorhandler(_CsrfError)
def _handle_csrf_error(e):
    return jsonify({'ok': False, 'message': 'Session expired - please refresh the page.'}), 403


@app.errorhandler(401)
def _handle_unauthorized(e):
    if request.path.startswith('/api/'):
        return jsonify({'ok': False, 'error': 'Not authenticated', 'auth_required': True}), 401
    return redirect(url_for('login', next=request.path))


@app.context_processor
def inject_csrf():
    return {'csrf_token': _get_csrf_token()}


def _static_build_stamp() -> str:
    newest = 0.0
    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    for sub in ('css', 'js'):
        root = os.path.join(static_dir, sub)
        for dirpath, _dirs, files in os.walk(root):
            for name in files:
                try:
                    newest = max(newest, os.path.getmtime(os.path.join(dirpath, name)))
                except OSError:
                    pass
    return str(int(newest))


ASSET_VERSION = f"{APP_VERSION}-{_static_build_stamp()}"


@app.context_processor
def inject_asset_version():
    return {'asset_version': ASSET_VERSION}

@app.context_processor
def inject_base_path():
    return {'base_path': env.BASE_PATH}


def _hash_api_key(key: str) -> str:
    import hashlib
    return 'sha256:' + hashlib.sha256(key.encode()).hexdigest()

def _safe_next(next_url: str) -> str:
    nu = (next_url or '').strip()
    if nu.startswith('/') and not nu.startswith('//') and not nu.startswith('/\\'):
        return nu
    return url_for('index')


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

threading.Thread(target=_geoip_autoupdate_loop, daemon=True).start()

_monitor.register('crowdsec', _crowd.CS_ALERT_INTERVAL,
                  lambda: _crowd.check_local_alerts(_crowd.CS_ALERT_WINDOW))
_monitor.register('updates', _updates.UPDATE_INTERVAL, _updates.check_updates)
_monitor.register('notify-flush', _noti.FLUSH_INTERVAL, _noti.flush_due)


def _reencrypt_file(name, read, write):
    crypto.clear_plaintext_seen()
    content = read()
    if not crypto.plaintext_secrets_seen():
        return False
    crypto.clear_plaintext_seen()
    try:
        write(content)
    except Exception:
        logger.exception(f"Could not re-encrypt the secrets in {name}")
        return False
    logger.info(f"Secrets written in plain text were re-encrypted in {name}")
    return True


def _reencrypt_plaintext_secrets():
    rewritten = []
    if _reencrypt_file('manager.yml', load_settings, lambda s: save_settings(
            domains=s['domains'], cert_resolver=s['cert_resolver'],
            traefik_api_url=s['traefik_api_url'], auth_enabled=s['auth_enabled'],
            password_hash=s['password_hash'], visible_tabs=s['visible_tabs'])):
        rewritten.append('manager.yml')
    if _reencrypt_file('agents.yml', _ag.load_agents, _ag.save_agents_file):
        rewritten.append('agents.yml')
    crypto.clear_plaintext_seen()
    return rewritten


_reencrypted = _reencrypt_plaintext_secrets()
if _reencrypted:
    add_notification(
        'warning',
        f"A secret was written to {' and '.join(_reencrypted)} in plain text. It has been "
        f"encrypted in place and is no longer stored in the clear",
        category='security')

for _label, _path, _err in env.unwritable_storage():
    logger.error(f"{_label} storage at {_path} is not writable ({_err}). "
                 f"Settings, backups and scheduled checks will not survive a restart. "
                 f"Check the volume or bind mount for this path.")

_monitor.start()

_SILENT_PREFIXES = (
    '/static/',
    '/api/notifications',
    '/api/traefik/',
    '/api/routes',
    '/api/dashboard/',
    '/api/manager/version',
    '/api/configs',
    '/api/settings/tabs',
    '/api/ping',
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
    if not request.path.startswith('/static/') and 'Cache-Control' not in response.headers:
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
        response.headers['Pragma']        = 'no-cache'
        response.headers['Expires']       = '0'
    if app.config.get('SESSION_COOKIE_SECURE'):
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response


def _close_reset_window(settings):
    if not settings.get('setup_password_reset'):
        return
    save_settings(
        domains=settings['domains'], cert_resolver=settings['cert_resolver'],
        traefik_api_url=settings['traefik_api_url'],
        auth_enabled=settings.get('auth_enabled', True),
        password_hash=settings.get('password_hash', ''),
        visible_tabs=settings['visible_tabs'],
        setup_password_reset=False,
    )
    logger.warning("Password reset window closed after a successful login")


@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute", methods=["POST"])
def login():

    if not _auth_required():
        return redirect(url_for('index'))

    if session.get('authenticated'):
        return redirect(url_for('index'))

    settings = load_settings()
    local_auth = _auth_enabled()
    temp_password_hint = (
        settings.get('must_change_password', False)
        and not os.environ.get('ADMIN_PASSWORD', '').strip()
    )

    error = None
    if request.method == 'POST':
        _check_csrf()
        if not local_auth:
            error = 'Local password login is disabled. Sign in with your identity provider.'
            return render_template('login.html', error=error, next=request.args.get('next', ''),
                                   csrf_token=_get_csrf_token(), temp_password_hint=False,
                                   local_auth_enabled=False,
                                   oidc_enabled=settings.get('oidc_enabled', False),
                                   oidc_display_name=settings.get('oidc_display_name', 'OIDC'))
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
            add_notification('info', f"Login from {request.remote_addr}", category='security')
            _close_reset_window(settings)

            if settings.get('must_change_password', False) and not admin_pw:
                if not settings.get('setup_complete', False):
                    return redirect(url_for('setup'))
                else:
                    return redirect(url_for('force_change_password'))

            return redirect(_safe_next(request.form.get('next')))
        else:
            error = 'Incorrect password.'
            logger.warning(f"Failed login attempt from {request.remote_addr}")

    next_url = request.args.get('next', '')
    if (request.method == 'GET'
            and settings.get('oidc_enabled')
            and settings.get('oidc_auto_login')
            and request.args.get('auto') != '0'
            and not session.get('oidc_auto_tried')):
        return redirect(url_for('oidc_login', silent='1'))
    return render_template('login.html', error=error, next=next_url,
                           csrf_token=_get_csrf_token(),
                           temp_password_hint=temp_password_hint,
                           local_auth_enabled=local_auth,
                           oidc_enabled=settings.get('oidc_enabled', False),
                           oidc_display_name=settings.get('oidc_display_name', 'OIDC'))


@app.route('/setup', methods=['GET', 'POST'])
def setup():
    if not _auth_required():
        return redirect(url_for('index'))

    current = load_settings()

    reset_mode = bool(current.get('setup_password_reset', False))

    if not reset_mode:
        if current.get('setup_complete', False):
            if current.get('must_change_password', False):
                return redirect(url_for('force_change_password'))
            return redirect(url_for('index'))

        if _has_password_set() and not session.get('authenticated'):
            return redirect(url_for('login'))

    if reset_mode and request.method == 'POST':
        _check_csrf()
        new_pw  = request.form.get('password', '')
        confirm = request.form.get('confirm', '')
        err = _password_error(new_pw)
        if not err and new_pw != confirm:
            err = 'Passwords do not match.'
        if err:
            return render_template('login.html', setup_mode=True, reset_mode=True,
                                   error=err, csrf_token=_get_csrf_token(),
                                   defaults={'domains': current['domains'],
                                             'cert_resolver': current['cert_resolver'],
                                             'traefik_api_url': current['traefik_api_url']},
                                   temp_password_mode=False,
                                   detected_self_domain='', detected_self_svc='',
                                   detected_self_entry_point='')
        save_settings(
            domains=current['domains'],
            cert_resolver=current['cert_resolver'],
            traefik_api_url=current['traefik_api_url'],
            auth_enabled=current.get('auth_enabled', True),
            password_hash=_hash_password(new_pw),
            visible_tabs=current['visible_tabs'],
            must_change_password=False,
            setup_password_reset=False,
        )
        session.clear()
        session['authenticated'] = True
        session['login_time'] = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')
        logger.warning(f"Password reset completed from {request.remote_addr}")
        return redirect(url_for('index'))

    temp_password_mode = current.get('must_change_password', False) and bool(current.get('password_hash', ''))

    defaults = {
        'domains':         current['domains'],
        'cert_resolver':   current['cert_resolver'],
        'traefik_api_url': current['traefik_api_url'],
    }

    error = None
    if request.method == 'POST':
        _check_csrf()

        domains_raw         = request.form.get('domains', '').strip()
        cert_resolver       = request.form.get('cert_resolver', '').strip()
        traefik_api_url     = request.form.get('traefik_api_url', '').strip()
        traefik_api_user    = request.form.get('traefik_api_user', '').strip()
        traefik_api_password = request.form.get('traefik_api_password', '')
        visible_tabs_raw    = request.form.get('visible_tabs', '{}')
        pw                  = request.form.get('password', '')
        confirm             = request.form.get('confirm', '')
        self_route_domain   = request.form.get('self_route_domain', '').strip()
        self_route_svc      = request.form.get('self_route_service', '').strip() or 'http://traefik-manager:5000'
        self_route_ep       = request.form.get('self_route_entry_point', '').strip() or _best_entrypoint()
        notify_kind         = request.form.get('notify_kind', '').strip().lower()
        notify_fields       = {f: request.form.get('notify_' + f, '').strip()
                               for f in ('url', 'token', 'token2', 'username', 'password')}
        notify_wanted       = any(notify_fields.values())
        notify_missing      = [f for f in _notify_providers.required_fields(notify_kind)
                               if not notify_fields[f]]

        domains = [d.strip() for d in domains_raw.split(',') if d.strip()]
        pw_error = None if temp_password_mode else _password_error(pw)

        if not domains:
            error = 'Enter at least one domain.'
        elif not traefik_api_url:
            error = 'Enter the Traefik API URL.'
        elif not _safe_api_url(traefik_api_url):
            error = 'Traefik API URL must start with http:// or https://'
        elif pw_error:
            error = pw_error
        elif not temp_password_mode and pw != confirm:
            error = 'Passwords do not match.'
        elif notify_wanted and notify_kind not in _settings.CHANNEL_KINDS:
            error = 'Choose a notification destination.'
        elif notify_wanted and notify_missing:
            error = 'Complete every notification field, or clear them to skip notifications.'
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
                sr = {'domain': self_route_domain, 'service_url': self_route_svc, 'entry_point': self_route_ep}
                _write_self_route(self_route_domain, self_route_svc, resolver, entry_point=self_route_ep)
            cs_url  = request.form.get('crowdsec_lapi_url', '').strip()
            git_repo = request.form.get('git_backup_repo', '').strip()
            extra = {}
            if cs_url:
                extra.update(
                    crowdsec_lapi_url=cs_url,
                    crowdsec_api_key=request.form.get('crowdsec_api_key', '').strip(),
                    crowdsec_machine_id=request.form.get('crowdsec_machine_id', '').strip(),
                    crowdsec_machine_password=request.form.get('crowdsec_machine_password', '').strip(),
                )
            if git_repo:
                extra.update(
                    git_backup_enabled=True,
                    git_backup_repo=git_repo,
                    git_backup_branch=request.form.get('git_backup_branch', '').strip() or 'main',
                    git_backup_username=request.form.get('git_backup_username', '').strip(),
                    git_backup_token=request.form.get('git_backup_token', '').strip(),
                    git_backup_auto_push=request.form.get('git_backup_auto_push', '') == 'on',
                )
            if notify_wanted:
                channel = _blank_channel()
                channel.update(kind=notify_kind, name=notify_kind.title(), **notify_fields)
                extra['notification_channels'] = list(current.get('notification_channels') or []) + [channel]
            if request.form.get('geoip_enabled', '') == 'on':
                extra['geoip_enabled'] = True
            theme = request.form.get('default_theme', '').strip().lower()
            if theme in ('dark', 'light', 'system'):
                extra['default_theme'] = theme
            save_settings(
                domains=domains,
                cert_resolver=resolver,
                traefik_api_url=traefik_api_url,
                traefik_api_user=traefik_api_user,
                traefik_api_password=traefik_api_password,
                auth_enabled=True,
                password_hash=pw_hash,
                visible_tabs=visible_tabs,
                must_change_password=current.get('must_change_password', False),
                setup_complete=True,
                self_route=sr,
                **extra,
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
    detected_entry_point = load_settings().get('self_route', {}).get('entry_point', '') or _best_entrypoint()
    return render_template('login.html', setup_mode=True, error=error,
                           reset_mode=reset_mode,
                           defaults=defaults, csrf_token=_get_csrf_token(),
                           temp_password_mode=temp_password_mode,
                           detected_self_domain=detected_domain,
                           detected_self_svc=detected_svc,
                           detected_self_entry_point=detected_entry_point)


def _setup_open() -> bool:
    return not load_settings().get('setup_complete', False)


@app.route('/setup/test-crowdsec', methods=['POST'])
@limiter.limit("10 per minute")
def setup_test_crowdsec():
    if not _setup_open():
        abort(404)
    _check_csrf()
    data = request.get_json(silent=True) or {}
    url  = str(data.get('url', '')).strip()
    key  = str(data.get('key', '')).strip()
    if not url or not url.startswith(('http://', 'https://')):
        return jsonify({'ok': False, 'error': 'Enter an http:// or https:// URL'}), 400
    if not _ssrf_ok(url):
        return jsonify({'ok': False, 'error': 'Target address not allowed'}), 400
    try:
        resp = requests.get(f"{url.rstrip('/')}/v1/decisions",
                            headers={'X-Api-Key': key, 'Accept': 'application/json'},
                            timeout=5)
        if resp.status_code in (401, 403):
            return jsonify({'ok': False, 'error': 'Reached the LAPI, but the key was refused'})
        resp.raise_for_status()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)[:120]})


@app.route('/setup/test-git', methods=['POST'])
@limiter.limit("10 per minute")
def setup_test_git():
    if not _setup_open():
        abort(404)
    _check_csrf()
    data     = request.get_json(silent=True) or {}
    repo_url = str(data.get('repo_url', '')).strip()
    token    = str(data.get('token', '')).strip()
    if not repo_url:
        return jsonify({'ok': False, 'error': 'No repository URL'}), 400
    if not _valid_git_url(repo_url):
        return jsonify({'ok': False, 'error': 'Unsupported URL - use https://, http://, ssh:// or git://'}), 400
    creds = {'username': str(data.get('username', '')).strip(), 'token': token} if token else None
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        _, err, rc = _git_run(['ls-remote', '--quiet', '--', repo_url], cwd=tmpdir, credentials=creds)
    if rc == 0:
        return jsonify({'ok': True})
    safe = err.replace(token, '***') if token else err
    return jsonify({'ok': False, 'error': (safe or 'Could not reach repository')[:160]})


@app.route('/logout', methods=['POST'])
@csrf_protect
def logout():
    session.clear()
    session['oidc_auto_tried'] = True
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
        error = _password_error(new_pw)
        if not error and new_pw != confirm:
            error = 'Passwords do not match.'
        if not error:
            save_settings(
                domains=settings['domains'],
                cert_resolver=settings['cert_resolver'],
                traefik_api_url=settings['traefik_api_url'],
                auth_enabled=settings['auth_enabled'],
                password_hash=_hash_password(new_pw),
                visible_tabs=settings['visible_tabs'],
                must_change_password=False,
                setup_password_reset=False,
                setup_complete=True,
            )
            logger.info(f"Forced password change completed from {request.remote_addr}")
            return redirect(url_for('index'))

    return render_template('login.html', force_change_mode=True, error=error,
                           csrf_token=_get_csrf_token())


@app.cli.command('reset-password')
@click.option('--disable-otp', is_flag=True, default=False,
              help='Also disable two-factor authentication (use if TOTP app is lost).')
@click.option('--prompt', 'prompt_pw', is_flag=True, default=False,
              help='Ask for the new password twice instead of generating a temporary one.')
@click.option('--stdin', 'from_stdin', is_flag=True, default=False,
              help='Read the new password from standard input.')
@click.option('--password', 'password_opt', default=None,
              help='Set the new password directly. Prefer --stdin for scripts.')
def reset_password_cli(disable_otp, prompt_pw, from_stdin, password_opt):

    given = [name for name, used in (('--prompt', prompt_pw),
                                     ('--stdin', from_stdin),
                                     ('--password', password_opt is not None)) if used]
    if len(given) > 1:
        raise click.ClickException('Use only one of %s.' % ', '.join(given))

    explicit = bool(given)
    if prompt_pw:
        password = click.prompt('New password', hide_input=True, confirmation_prompt=True,
                                default='', show_default=False)
    elif from_stdin:
        try:
            raw = click.get_binary_stream('stdin').readline().decode('utf-8-sig')
        except UnicodeDecodeError:
            raise click.ClickException('The password on standard input is not valid UTF-8.')
        password = raw.split('\n', 1)[0].rstrip('\r')
    elif password_opt is not None:
        click.echo('Warning: --password is visible in ps output and shell history. '
                   'Use --stdin instead for scripts.', err=True)
        password = password_opt
    else:
        password = secrets.token_urlsafe(16)

    if explicit:
        if not password:
            raise click.ClickException('Password must not be empty.')
        pw_error = _password_error(password)
        if pw_error:
            raise click.ClickException(pw_error)
        if os.environ.get('ADMIN_PASSWORD', '').strip():
            raise click.ClickException(
                'ADMIN_PASSWORD is set, and it overrides the stored password. '
                'Change or unset that variable instead, or this password will not work.')

    settings = load_settings()
    save_settings(
        domains=settings['domains'],
        cert_resolver=settings['cert_resolver'],
        traefik_api_url=settings['traefik_api_url'],
        auth_enabled=settings.get('auth_enabled', True),
        password_hash=_hash_password(password),
        visible_tabs=settings['visible_tabs'],
        must_change_password=False if explicit else True,
        setup_password_reset=False if explicit else True,
        setup_complete=settings.get('setup_complete', True),
        otp_secret='' if disable_otp else None,
        otp_enabled=False if disable_otp else None,
    )
    print("=" * 60)
    print("TRAEFIK MANAGER - PASSWORD RESET")
    if explicit:
        print("New password set. It is not shown here.")
    else:
        print(f"New temporary password: {password}")
    if disable_otp:
        print("Two-factor authentication has been DISABLED.")
    if not explicit:
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

    pw_error = _password_error(new_pw, 'New password')
    if pw_error:
        return jsonify({'error': pw_error}), 400
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
        must_change_password=False,
        setup_password_reset=False,
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
    reauth = _auth_required() and not session.get('authenticated')
    return jsonify({'success': True, 'auth_enabled': enabled, 'reauth_required': reauth})


@app.route('/api/auth/external-ack', methods=['POST'])
@csrf_protect
@login_required
def api_auth_external_ack():
    data = request.get_json(silent=True) or {}
    ack  = bool(data.get('auth_external_ack'))
    if ack and _auth_required():
        return jsonify({'error': 'Built-in authentication or OIDC is active, so there is nothing to acknowledge'}), 400
    settings = load_settings()
    save_settings(
        domains=settings['domains'],
        cert_resolver=settings['cert_resolver'],
        traefik_api_url=settings['traefik_api_url'],
        auth_enabled=settings['auth_enabled'],
        auth_external_ack=ack,
        password_hash=settings['password_hash'],
        visible_tabs=settings['visible_tabs'],
    )
    logger.warning(f"auth_external_ack set to {ack} by {request.remote_addr} - "
                   f"the operator asserts this instance is protected by an external provider"
                   if ack else f"auth_external_ack cleared by {request.remote_addr}")
    return jsonify({'success': True, 'auth_external_ack': ack})


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
        try:
            otp_valid = secret and pyotp.TOTP(secret).verify(code, valid_window=1)
        except Exception:
            logger.exception("OTP verify error - secret may be corrupt")
            otp_valid = False
        if otp_valid:
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
            add_notification('info', f"Login from {request.remote_addr}", category='security')
            if must_change:
                if not setup_complete:
                    return redirect(url_for('setup'))
                return redirect(url_for('force_change_password'))
            return redirect(_safe_next(next_url))
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


if not os.environ.get('REQUESTS_CA_BUNDLE'):
    _SYSTEM_CA_BUNDLE = '/etc/ssl/certs/ca-certificates.crt'
    if os.path.exists(_SYSTEM_CA_BUNDLE):
        os.environ['REQUESTS_CA_BUNDLE'] = _SYSTEM_CA_BUNDLE


@app.route('/api/traefik/overview')
@login_required
def api_overview():
    return jsonify(traefik_api_get('/api/overview') or {})

def _traefik_proto_payload(kind):
    fetched = {p: traefik_api_get_all(f'/api/{p}/{kind}') for p in ('http', 'tcp', 'udp')}
    out = {p: (v or []) for p, v in fetched.items()}
    out['reachable'] = any(v is not None for v in fetched.values())
    return out


@app.route('/api/traefik/routers')
@login_required
def api_routers():
    return jsonify(_traefik_proto_payload('routers'))

@app.route('/api/services/<path:name>/ownership', methods=['POST'])
@csrf_protect
@login_required
def api_service_ownership(name):
    data   = request.get_json(silent=True) or {}
    adopt  = bool(data.get('adopt'))
    bare   = str(name).split('@')[0]
    agent_id, agent, err = _svc_agent_ctx()
    if err:
        return err
    if agent:
        pairs = [(fname, cfg) for fname, cfg in _agent_load_configs(agent).items()]
    else:
        pairs = [(os.path.basename(p), load_config(p)) for p in env.CONFIG_PATHS]
    svc_def, cfg_file = None, ''
    for fname, cfg in pairs:
        found = ((cfg.get('http') or {}).get('services') or {}).get(bare)
        if isinstance(found, dict):
            svc_def, cfg_file = found, fname
            break
    if svc_def is None:
        return jsonify({'ok': False, 'error': 'Service not found'}), 404
    if adopt and not _svc_own.composite_type(svc_def):
        return jsonify({'ok': False,
                        'error': 'Only weighted, mirroring, failover and '
                                 'highestRandomWeight services can be managed here'}), 400
    settings = load_settings()
    ledger   = dict(settings.get('managed_middlewares') or {})
    key      = _svc_own.ledger_key(bare, agent_id)
    if adopt:
        ledger[key] = _svc_own.ledger_entry(svc_def, cfg_file)
    elif key in ledger:
        del ledger[key]
    else:
        return jsonify({'ok': True, 'owned': False})
    save_settings(
        domains=settings['domains'], cert_resolver=settings['cert_resolver'],
        traefik_api_url=settings['traefik_api_url'], auth_enabled=settings['auth_enabled'],
        password_hash=settings['password_hash'], visible_tabs=settings['visible_tabs'],
        managed_middlewares=ledger,
    )
    logger.info(f"Service {bare!r} {'adopted' if adopt else 'released'} by {request.remote_addr}")
    return jsonify({'ok': True, 'owned': adopt})


_SERVICE_NAME_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$')


def _service_routers_using(configs, name: str) -> list:
    out = []
    for cfg in configs:
        for section in ('http', 'tcp', 'udp'):
            for rname, rdata in ((cfg.get(section) or {}).get('routers') or {}).items():
                if isinstance(rdata, dict) and str(rdata.get('service') or '').split('@')[0] == name:
                    out.append(rname)
    return out


def _stream_service_proto(name: str) -> str:
    bare = str(name or '').split('@')[0]
    if not bare:
        return ''
    for path in env.CONFIG_PATHS:
        config = load_config(path)
        for section, label in (('tcp', 'TCP'), ('udp', 'UDP')):
            if bare in ((config.get(section) or {}).get('services') or {}):
                return label
    return ''


def _service_referenced_by(configs, name: str) -> list:
    out = []
    for cfg in configs:
        for sname, sdef in ((cfg.get('http') or {}).get('services') or {}).items():
            if sname == name:
                continue
            if name in _svc_own.child_names(sdef):
                out.append(sname)
    return out


def _service_home_path(name: str) -> str:
    bare = str(name or '').split('@')[0]
    if not bare:
        return ''
    for path in env.CONFIG_PATHS:
        if bare in ((load_config(path).get('http') or {}).get('services') or {}):
            return path
    return ''


def _children_claimed_by_another(ledger, parent: str, agent_id: str = ''):
    prefix = f'{parent}-backend-'
    for key, value in (ledger or {}).items():
        if not (isinstance(key, str) and isinstance(value, dict)):
            continue
        bare = key.split('svc::', 1)[-1]
        if not bare.startswith(prefix) or not value.get('child'):
            continue
        owner = value.get('parent')
        if owner and owner != parent:
            return (bare, owner)
    return None


def _children_still_in_use(configs, parent: str, keep) -> list:
    prefix = f'{parent}-backend-'
    keep   = set(keep or ())
    blocked = []
    for cfg in configs:
        for child in ((cfg.get('http') or {}).get('services') or {}):
            if not (isinstance(child, str) and child.startswith(prefix)) or child in keep:
                continue
            users = _service_routers_using(configs, child)
            owners = [o for o in _service_referenced_by(configs, child) if o != parent]
            if users or owners:
                blocked.append((child, sorted(set(users + owners))))
    return blocked


def _in_use_error(blocked):
    child, users = blocked[0]
    return jsonify({'ok': False,
                    'error': f"{child} is still used by " + ', '.join(users[:5])}), 409


def _agent_service_home(agent_configs: dict, name: str) -> str:
    bare = str(name or '').split('@')[0]
    if not bare:
        return ''
    for fname, cfg in (agent_configs or {}).items():
        if bare in (((cfg or {}).get('http') or {}).get('services') or {}):
            return fname
    return ''


def _svc_agent_ctx():
    agent_id = (request.args.get('agent_id')
                or (request.get_json(silent=True) or {}).get('agent_id') or '').strip()
    if not agent_id:
        return '', None, None
    agent = _agent_by_id(agent_id)
    if not agent:
        return agent_id, None, (jsonify({'ok': False, 'error': 'Agent not found'}), 404)
    return agent_id, agent, None


@app.route('/api/services', methods=['POST'])
@csrf_protect
@login_required
def api_service_save():
    data      = request.get_json(silent=True) or {}
    name      = str(data.get('name') or '').strip()
    kind      = str(data.get('type') or '').strip()
    original  = str(data.get('originalName') or '').strip()
    cfg_raw   = str(data.get('configFile') or '').strip()
    children  = data.get('children') or []
    if not _SERVICE_NAME_RE.match(name):
        return jsonify({'ok': False, 'error': 'Use letters, numbers, dots, dashes or underscores'}), 400
    if kind not in _composite.TYPES + ('loadBalancer',):
        return jsonify({'ok': False,
                        'error': 'Choose load balancer, weighted, mirroring or failover'}), 400
    if kind == 'failover' and len(_composite.normalise_children(children)) > 2:
        return jsonify({'ok': False,
                        'error': 'Failover takes two backends: the one that serves and the '
                                 'one that takes over'}), 400
    block, owned, _names = _composite.build(name, kind, children)
    if not block:
        return jsonify({'ok': False, 'error': 'Add at least one backend'}), 400
    clash = _stream_service_proto(name) or (_stream_service_proto(original) if original else '')
    if clash:
        return jsonify({'ok': False,
                        'error': f'That name belongs to a {clash} service, '
                                 f'and only HTTP services can be edited here'}), 400

    agent_id, agent, err = _svc_agent_ctx()
    if err:
        return err

    if agent:
        agent_configs = _agent_load_configs(agent)
        cfg_filename = _agent_service_home(agent_configs, original or name) \
            or (cfg_raw if cfg_raw in agent_configs else next(iter(agent_configs), 'dynamic.yml'))
        config = agent_configs.get(cfg_filename) or {}
        target_path = None
    else:
        target_path = _service_home_path(original or name) \
            or (_resolve_config_path(cfg_raw) if cfg_raw else env.CONFIG_PATH)
        if not target_path:
            return jsonify({'ok': False, 'error': f"Cannot write to '{cfg_raw}'"}), 400
        cfg_filename = os.path.basename(target_path)
        config       = load_config(target_path)
    section = config.setdefault('http', {}).setdefault('services', {})

    settings = load_settings()
    ledger   = dict(settings.get('managed_middlewares') or {})
    existing = section.get(name)
    if isinstance(existing, dict) and name != original \
            and not _svc_own.is_owned(name, existing, ledger, agent_id) \
            and not (kind == 'loadBalancer' and 'loadBalancer' in existing):
        return jsonify({'ok': False, 'error': f"A service named '{name}' already exists"}), 409
    if original and original != name:
        _orig_def = section.get(original)
        if not _svc_own.is_owned(original, _orig_def, ledger, agent_id) \
                and not (isinstance(_orig_def, dict) and 'loadBalancer' in _orig_def):
            return jsonify({'ok': False, 'error': 'That service is not managed here'}), 403
        section.pop(original, None)
        _retarget_service(config, original, name)
        for gone in _composite.drop_orphan_children(section, original, set()):
            ledger.pop(_svc_ledger_key(gone, agent_id), None)
        ledger.pop(_svc_ledger_key(original, agent_id), None)

    blocked = _children_still_in_use([config], name, owned)
    if blocked:
        return _in_use_error(blocked)

    claimed = _children_claimed_by_another(ledger, name, agent_id)
    if claimed:
        return jsonify({'ok': False,
                        'error': f"{claimed[0]} already belongs to {claimed[1]}. "
                                 f"Pick a different name"}), 409

    _composite.merge_into(section, name, block, owned)
    for gone in _composite.drop_orphan_children(section, name, set(owned)):
        ledger.pop(_svc_ledger_key(gone, agent_id), None)
    if kind in _composite.TYPES:
        ledger.update(_composite.ledger_entries(name, block, owned, cfg_filename, agent_id))
    else:
        ledger.pop(_svc_ledger_key(name, agent_id), None)

    if agent:
        _agent_write_config(agent, cfg_filename, config)
    else:
        create_backup(target_path)
        save_config(_strip_empty_sections(config), target_path)
    if original and original != name:
        _cascade_across_configs(agent, lambda c: _retarget_service(c, original, name),
                                already=cfg_filename if agent else target_path)
    save_settings(
        domains=settings['domains'], cert_resolver=settings['cert_resolver'],
        traefik_api_url=settings['traefik_api_url'], auth_enabled=settings['auth_enabled'],
        password_hash=settings['password_hash'], visible_tabs=settings['visible_tabs'],
        managed_middlewares=ledger,
    )
    logger.info(f"Service {name!r} saved by {request.remote_addr}")
    add_notification('success', f'Service {name} saved', category='config')
    if agent:
        threading.Thread(target=lambda: _git_push_agent_if_enabled(agent, 'service save'),
                         daemon=True).start()
    else:
        threading.Thread(target=lambda: _git_push_if_enabled('service save'), daemon=True).start()
    return jsonify({'ok': True, 'name': name})


@app.route('/api/services/<path:name>', methods=['DELETE'])
@csrf_protect
@login_required
def api_service_delete(name):
    bare     = str(name).split('@')[0]
    agent_id, agent, err = _svc_agent_ctx()
    if err:
        return err
    agent_configs = _agent_load_configs(agent) if agent else {}
    configs  = list(agent_configs.values()) if agent else [load_config(p) for p in env.CONFIG_PATHS]
    used_by  = _service_routers_using(configs, bare)
    if used_by:
        return jsonify({'ok': False,
                        'error': 'Still used by ' + ', '.join(sorted(set(used_by))[:5])}), 409
    parents = _service_referenced_by(configs, bare)
    if parents:
        return jsonify({'ok': False,
                        'error': 'Still a backend of ' + ', '.join(sorted(set(parents))[:5])}), 409

    settings = load_settings()
    ledger   = dict(settings.get('managed_middlewares') or {})
    removed  = False
    targets = ([(fname, cfg) for fname, cfg in agent_configs.items()] if agent
               else [(path, load_config(path)) for path in env.CONFIG_PATHS])
    for where, config in targets:
        section = (config.get('http') or {}).get('services') or {}
        if bare not in section:
            continue
        _def = section.get(bare)
        if not _svc_own.is_owned(bare, _def, ledger, agent_id) \
                and not (isinstance(_def, dict) and 'loadBalancer' in _def):
            return jsonify({'ok': False, 'error': 'That service is not managed here'}), 403
        child_users = _children_still_in_use(configs, bare, set())
        if child_users:
            return _in_use_error(child_users)
        del section[bare]
        for gone in _composite.drop_orphan_children(section, bare, set()):
            ledger.pop(_svc_ledger_key(gone, agent_id), None)
        ledger.pop(_svc_ledger_key(bare, agent_id), None)
        if agent:
            _agent_write_config(agent, where, config)
        else:
            create_backup(where)
            save_config(_strip_empty_sections(config), where)
        removed = True
        break
    if not removed:
        return jsonify({'ok': False, 'error': 'Service not found'}), 404
    save_settings(
        domains=settings['domains'], cert_resolver=settings['cert_resolver'],
        traefik_api_url=settings['traefik_api_url'], auth_enabled=settings['auth_enabled'],
        password_hash=settings['password_hash'], visible_tabs=settings['visible_tabs'],
        managed_middlewares=ledger,
    )
    logger.info(f"Service {bare!r} deleted by {request.remote_addr}")
    add_notification('warning', f'Service {bare} deleted', category='config')
    if agent:
        threading.Thread(target=lambda: _git_push_agent_if_enabled(agent, 'service delete'),
                         daemon=True).start()
    else:
        threading.Thread(target=lambda: _git_push_if_enabled('service delete'), daemon=True).start()
    return jsonify({'ok': True})


def _owned_child_services(agent_id: str = '') -> list:
    prefix = f'agent_{agent_id}::svc::' if agent_id else 'svc::'
    ledger = load_settings().get('managed_middlewares') or {}
    return sorted(
        key[len(prefix):] for key, value in ledger.items()
        if isinstance(key, str) and key.startswith(prefix)
        and isinstance(value, dict) and value.get('kind') == _svc_own.LEDGER_KIND
        and value.get('child') is True)


def _owned_parent_services(agent_id: str = '') -> list:
    prefix = f'agent_{agent_id}::svc::' if agent_id else 'svc::'
    ledger = load_settings().get('managed_middlewares') or {}
    return sorted(
        key[len(prefix):] for key, value in ledger.items()
        if isinstance(key, str) and key.startswith(prefix)
        and isinstance(value, dict) and value.get('kind') == _svc_own.LEDGER_KIND
        and value.get('child') is not True)


def _prune_service_ledger(agent_id: str = ''):
    settings = load_settings()
    ledger   = settings.get('managed_middlewares') or {}
    if not any(isinstance(k, str) and 'svc::' in k for k in ledger):
        return
    if _get_config_parse_errors():
        return
    configs = [load_config(p) for p in env.CONFIG_PATHS]
    if not any(cfg for cfg in configs):
        return
    kept, dropped = _svc_own.prune(ledger, configs, agent_id)
    if not dropped:
        return
    save_settings(
        domains=settings['domains'], cert_resolver=settings['cert_resolver'],
        traefik_api_url=settings['traefik_api_url'], auth_enabled=settings['auth_enabled'],
        password_hash=settings['password_hash'], visible_tabs=settings['visible_tabs'],
        managed_middlewares=kept,
    )


@app.route('/api/traefik/services')
@login_required
def api_services():
    agent_id, agent, err = _svc_agent_ctx()
    if err:
        return err
    if agent:
        resp = _agent_request(agent, 'GET', '/api/traefik/services')
        payload = resp.json() if resp.ok else {'http': [], 'tcp': [], 'udp': [],
                                               'reachable': False}
    else:
        payload = _traefik_proto_payload('services')
        _prune_service_ledger()
    payload['ownedChildren'] = _owned_child_services(agent_id)
    payload['ownedServices'] = _owned_parent_services(agent_id)
    return jsonify(payload)

@app.route('/api/traefik/middlewares')
@login_required
def api_middlewares():
    http_mws = traefik_api_get_all('/api/http/middlewares')
    tcp_mws  = traefik_api_get_all('/api/tcp/middlewares')
    if http_mws is None and tcp_mws is None:
        return jsonify({'error': 'Traefik API unreachable'}), 502
    return jsonify({
        'http': http_mws or [],
        'tcp':  tcp_mws  or [],
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
    eps = traefik_api_get_all('/api/entrypoints')
    if eps is None:
        return jsonify({'error': 'Traefik API unreachable'}), 502
    return jsonify(eps)

@app.route('/api/traefik/version')
@login_required
def api_version():
    return jsonify(traefik_api_get('/api/version') or {})


CS_PAGE_SIZE = 1000
CS_MAX_PAGES = 200


def _cs_age_text(seconds: int) -> str:
    if seconds >= 86400:
        days = seconds // 86400
        return f"{days} day{'s' if days != 1 else ''}"
    if seconds >= 3600:
        hours = seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''}"
    minutes = max(1, seconds // 60)
    return f"{minutes} minute{'s' if minutes != 1 else ''}"


@app.route('/api/crowdsec/decisions')
@login_required
def api_cs_decisions():
    lapi = _cs_lapi_url()
    key  = _cs_api_key()
    if not lapi:
        return jsonify({'error': 'CrowdSec not configured'}), 503
    if not key and not _cs_has_cert():
        return jsonify({'error': 'No bouncer API key or client certificate. CrowdSec only accepts a bouncer key '
                                 'or a TLS client certificate on /v1/decisions, the machine token is refused there'}), 503
    force_full = request.args.get('full') in ('1', 'true', 'yes')
    try:
        all_decisions = None
        stale_note = ''
        if _crowd._cs_stream_cache.get('streamable', True):
            try:
                all_decisions, _mode = _crowd.cs_decisions_stream(force_full=force_full)
                if str(_mode).startswith('stale:'):
                    _, _age, _why = str(_mode).split(':', 2)
                    stale_note = (f'CrowdSec has not answered for {_cs_age_text(int(_age))}, so these '
                                  f'decisions are the last ones read and may be out of date. {_why}')
            except CrowdSecUnavailable as e:
                if 'HTTP 404' in str(e) or 'HTTP 405' in str(e):
                    logger.info("CrowdSec LAPI has no /v1/decisions/stream, falling back to the paged walk")
                    _crowd._cs_stream_cache['streamable'] = False
                    all_decisions = None
                else:
                    raise
        if all_decisions is None:
            all_decisions = []
            cursor = 0
            for _page in range(CS_MAX_PAGES):
                try:
                    chunk = _cs_request_strict('GET', f'/v1/decisions?limit={CS_PAGE_SIZE}&id_gt={cursor}',
                                               lapi=lapi, key=key)
                except CrowdSecUnavailable:
                    if all_decisions:
                        logger.warning(f"CrowdSec decisions walk failed at page {_page + 1}, "
                                       f"returning the {len(all_decisions)} rows already read")
                        break
                    raise
                if not isinstance(chunk, list) or not chunk:
                    break
                all_decisions.extend(chunk)
                ids = [d.get('id') for d in chunk if isinstance(d.get('id'), int)]
                if not ids:
                    break
                cursor = max(ids)
                if len(chunk) < CS_PAGE_SIZE:
                    break
        now = datetime.now(timezone.utc)
        active = []
        for d in all_decisions:
            until = d.get('until')
            if until:
                try:
                    exp = datetime.fromisoformat(until.replace('Z', '+00:00'))
                    if exp < now:
                        continue
                except Exception:
                    pass
            active.append(d)
        if stale_note:
            logger.warning(f"CrowdSec decisions served from a stale cache: {stale_note}")
            resp = jsonify(active)
            resp.headers['X-CS-Stale'] = stale_note
            return resp
        return jsonify(active)
    except CrowdSecUnavailable as e:
        return jsonify({'error': str(e)}), 502
    except Exception as e:
        logger.exception("CrowdSec decisions error")
        return jsonify({'error': str(e)}), 500

@app.route('/api/crowdsec/alerts')
@login_required
def api_cs_alerts():
    lapi = _cs_lapi_url()
    if not (lapi and (_cs_api_key() or _cs_has_machine())):
        return jsonify({'error': 'CrowdSec not configured'}), 503
    try:
        if _cs_has_machine():
            token = _cs_jwt(lapi)
            if not token:
                return jsonify({'error': 'CrowdSec machine login failed - check CROWDSEC_MACHINE_ID / CROWDSEC_MACHINE_PASSWORD '
                                         'or the client certificate'}), 502
            headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/json'}
        else:
            headers = {'X-Api-Key': _cs_api_key(), 'Accept': 'application/json'}
        _limit = cs_alert_limit()
        _url = f"{lapi.rstrip('/')}/v1/alerts?limit={_limit}&with_decisions=false"
        resp = requests.get(_url, headers=headers, timeout=cs_timeout(), **_cs_tls_kwargs())
        if resp.status_code == 401 and _cs_has_machine():
            logger.info("CrowdSec refused the machine token on /v1/alerts, logging in again")
            _crowd.cs_jwt_reset()
            token = _cs_jwt(lapi)
            if token:
                headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/json'}
                resp = requests.get(_url, headers=headers, timeout=cs_timeout(), **_cs_tls_kwargs())
        if not resp.ok:
            try:
                msg = resp.json().get('message') or resp.json().get('error') or resp.text
            except Exception:
                msg = resp.text
            return jsonify({'error': f'LAPI {resp.status_code}: {msg}'}), resp.status_code
        alerts = resp.json() if resp.content else []
        if not isinstance(alerts, list):
            alerts = []
        out = jsonify(alerts)
        out.headers['X-CS-Alert-Limit'] = str(_limit)
        out.headers['X-CS-Alert-Capped'] = '1' if (_limit and len(alerts) >= _limit) else '0'
        return out
    except Exception as e:
        logger.exception("CrowdSec alerts error")
        return jsonify({'error': str(e)}), 500

@app.route('/api/crowdsec/decisions', methods=['POST'])
@csrf_protect
@login_required
def api_cs_add_decision():
    lapi = _cs_lapi_url()
    key  = _cs_api_key()
    if not (lapi and (key or _cs_has_machine())):
        return jsonify({'error': 'CrowdSec not configured'}), 503
    data     = request.get_json() or {}
    ip       = data.get('value', '').strip()
    dtype    = data.get('type', 'ban').strip()
    duration = data.get('duration', '24h').strip()
    reason   = (data.get('reason', '') or '').strip() or 'manual ban from Traefik Manager'
    if not ip:
        return jsonify({'error': 'IP/Range is required'}), 400
    if dtype not in ('ban', 'captcha', 'bypass'):
        return jsonify({'error': 'Invalid type'}), 400
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    payload = [{
        'capacity': 0,
        'decisions': [{'duration': duration, 'origin': 'manual', 'scenario': reason,
                       'scope': 'Ip', 'type': dtype, 'value': ip, 'simulated': False}],
        'events': [], 'events_count': 1, 'labels': None, 'leakspeed': '0',
        'message': reason, 'scenario': reason, 'scenario_hash': '', 'scenario_version': '',
        'simulated': False,
        'source': {'ip': ip, 'scope': 'Ip', 'value': ip},
        'start_at': now, 'stop_at': now,
    }]
    if _cs_has_machine():
        result = _cs_machine_request('POST', '/v1/alerts', json=payload)
    else:
        result = _cs_request('POST', '/v1/alerts', lapi=lapi, key=key, json=payload)
    if result is None:
        return jsonify({'error': 'Failed to add decision - check LAPI permissions'}), 502
    _crowd.cs_stream_reset()
    return jsonify({'ok': True})

@app.route('/api/crowdsec/decisions/<int:decision_id>', methods=['DELETE'])
@csrf_protect
@login_required
def api_cs_unban(decision_id):
    if not (_cs_lapi_url() and (_cs_api_key() or _cs_has_machine())):
        return jsonify({'error': 'CrowdSec not configured'}), 503
    if _cs_has_machine():
        result = _cs_machine_request('DELETE', f'/v1/decisions/{decision_id}')
    else:
        result = _cs_request('DELETE', f'/v1/decisions/{decision_id}')
    if result is None:
        return jsonify({'error': 'Failed to delete decision'}), 500
    _crowd.cs_stream_reset()
    add_notification('success', f'Decision {decision_id} deleted (IP unbanned)', category='crowdsec')
    return jsonify({'ok': True})


@app.route('/api/ping')
@login_required
def api_route_ping():
    import time as _t
    from urllib.parse import urlparse
    url      = request.args.get('url', '').strip()
    fallback = request.args.get('fallback', '').strip()
    if not url or not url.startswith(('http://', 'https://')):
        return jsonify({'ok': False, 'error': 'Invalid URL'}), 400
    if not _ssrf_ok(url):
        return jsonify({'ok': False, 'error': 'Target address not allowed'}), 400
    host = urlparse(url).hostname or ''
    tm_host = request.host.split(':')[0].lower()
    if host.lower() == tm_host:
        return jsonify({'ok': True, 'latency_ms': 0, 'status_code': 200, 'self': True})
    settings = load_settings()
    self_domain = (settings.get('self_route') or {}).get('domain', '').strip().lower()
    if self_domain and host.lower() == self_domain:
        return jsonify({'ok': True, 'latency_ms': 0, 'status_code': 200, 'self': True})
    def _ping(target):
        t0   = _t.monotonic()
        resp = requests.head(target, timeout=5, allow_redirects=False, verify=False)
        ms   = round((_t.monotonic() - t0) * 1000)
        return ms, resp.status_code
    try:
        ms, code = _ping(url)
        return jsonify({'ok': True, 'latency_ms': ms, 'status_code': code})
    except Exception as primary_err:
        if fallback and fallback.startswith(('http://', 'https://')) and _ssrf_ok(fallback):
            try:
                ms, code = _ping(fallback)
                return jsonify({'ok': True, 'latency_ms': ms, 'status_code': code, 'via_target': True})
            except Exception:
                pass
        err = str(primary_err)[:80]
        return jsonify({'ok': False, 'error': 'Timeout' if 'timeout' in err.lower() else err, 'latency_ms': None})

def _apr1_hash(password: str, salt: str) -> str:
    import hashlib
    pw  = password.encode('latin-1')
    sl  = salt.encode('ascii')
    mgc = b'$apr1$'
    a   = hashlib.md5(pw + mgc + sl)
    b   = hashlib.md5(pw + sl + pw).digest()
    plen = len(pw)
    ndig, nrem = divmod(plen, 16)
    for n in ndig * [16] + [nrem]:
        a.update(b[:n])
    i = plen
    while i:
        a.update(b'\x00' if (i & 1) else pw[:1])
        i >>= 1
    a = a.digest()
    for i in range(1000):
        c = hashlib.md5()
        c.update(pw if (i & 1) else a)
        if i % 3: c.update(sl)
        if i % 7: c.update(pw)
        c.update(a if (i & 1) else pw)
        a = c.digest()
    t64 = './0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
    def to64(v, n):
        r = ''
        for _ in range(n):
            r += t64[v & 0x3f]; v >>= 6
        return r
    enc  = to64((a[0]<<16)|(a[6]<<8)|a[12], 4)
    enc += to64((a[1]<<16)|(a[7]<<8)|a[13], 4)
    enc += to64((a[2]<<16)|(a[8]<<8)|a[14], 4)
    enc += to64((a[3]<<16)|(a[9]<<8)|a[15], 4)
    enc += to64((a[4]<<16)|(a[10]<<8)|a[5], 4)
    enc += to64(a[11], 2)
    return f'$apr1${salt}${enc}'


@app.route('/api/traefik/ping')
@login_required
def api_ping():
    import time as _t
    settings = load_settings()
    u = settings.get('traefik_api_user', '')
    p = settings.get('traefik_api_password', '')
    auth = (u, p) if u and p else None
    try:
        t0   = _t.monotonic()
        resp = requests.get(f"{settings['traefik_api_url']}/ping", timeout=3, auth=auth, verify=_traefik_verify())
        ms   = round((_t.monotonic() - t0) * 1000)
        if resp.status_code == 200:
            return jsonify({'ok': True, 'latency_ms': ms})
    except Exception as e:
        logger.debug(f"Ping failed: {e}")
    return jsonify({'ok': False, 'latency_ms': None}), 503

@app.route('/api/manager/version')
@login_required
def api_manager_version():
    mgr = _updates.release_info(GITHUB_REPO)
    tfk = _updates.release_info(_updates.TRAEFIK_REPO)
    return jsonify({
        "version": APP_VERSION,
        "repo": GITHUB_REPO,
        "static_config_configured": bool(_get_static_config_path()),
        "latest": mgr.get('tag', ''),
        "release_url": mgr.get('url', ''),
        "release_notes": mgr.get('notes', ''),
        "release_error": mgr.get('error', ''),
        "traefik_latest": tfk.get('tag', ''),
        "traefik_release_url": tfk.get('url', ''),
        "traefik_running": _updates.running_traefik_version(),
    })

@app.route('/static/manifest.json')
def static_manifest():
    body = render_template('manifest.json')
    return app.response_class(body, mimetype='application/manifest+json')

_storage_probe_cache = {'at': 0.0, 'problems': []}
STORAGE_PROBE_TTL = 30


@app.route('/api/storage/status')
@login_required
def api_storage_status():
    now = time.time()
    if now - _storage_probe_cache['at'] >= STORAGE_PROBE_TTL:
        _storage_probe_cache['problems'] = [
            {'label': label, 'path': path, 'error': err}
            for label, path, err in env.unwritable_storage()
        ]
        _storage_probe_cache['at'] = now
    return jsonify({'problems': _storage_probe_cache['problems']})

@app.route('/api/health')
def api_health():
    return jsonify({"ok": True}), 200


@app.route('/api')
def api_docs():
    from flask import send_from_directory
    return send_from_directory('static', 'api.html')


@app.route('/openapi.yaml')
def openapi_yaml():
    import re as _re
    try:
        with open(os.path.join(app.static_folder, 'openapi.yaml'), 'r') as f:
            spec = f.read()
        spec = _re.sub(r'(?m)^(\s*version:\s*).*$', rf'\g<1>{APP_VERSION}', spec, count=1)
        return spec, 200, {'Content-Type': 'application/yaml'}
    except Exception:
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
    server = (request.args.get('server') or '').strip()
    if server:
        agent = _agent_by_id(server)
        if not agent:
            return jsonify({'error': 'Agent not found'}), 404
        try:
            resp = _agent_request(agent, 'GET', '/api/static')
        except requests.exceptions.RequestException as e:
            return jsonify({'error': f'Cannot reach agent: {e}'}), 502
        if resp.status_code != 200:
            try:
                msg = (resp.json() or {}).get('error', '')
            except Exception:
                msg = ''
            return jsonify({'error': msg or 'Static config not available on this agent'}), resp.status_code
        body = resp.json() or {}
        raw = body.get('content', '')
        try:
            _y = SafeYAML(typ='safe')
            parsed = _y.load(raw) or {}
        except Exception as e:
            return jsonify({'error': f'Agent static config is not valid YAML: {e}'}), 500
        return jsonify({'raw': raw, 'parsed': parsed, 'path': body.get('path', '')})
    path = _readable_config_path(_get_static_config_path())
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
        _new_doc = _y.load(content)
    except Exception as e:
        return jsonify({'error': f'Invalid YAML: {e}'}), 400
    _before = {}
    try:
        if os.path.exists(safe_path):
            with open(safe_path) as _fh:
                _before = SafeYAML(typ='safe').load(_fh.read()) or {}
    except Exception:
        _before = {}
    _renames, _gone = _plugin_diff(_static_plugins(_before), _static_plugins(_new_doc))
    _dyn = [load_config(_p) for _p in env.CONFIG_PATHS]
    for _name in _gone:
        _users = _middlewares_using_plugin(_dyn, _name)
        if _users:
            return jsonify({'error': f"{_name} is still used by " + ', '.join(_users[:5])
                                     + (' and others' if len(_users) > 5 else '')
                                     + '. Delete those middlewares first',
                            'inUseBy': _users}), 409
    try:
        create_backup(safe_path)
        with open(safe_path, 'w') as f:
            f.write(content)
        for _old, _new in _renames.items():
            _cascade_across_configs(None, lambda c, o=_old, n=_new: _retarget_plugin(c, o, n))
        logger.info(f"Static config saved by {request.remote_addr}: {safe_path}")
        add_notification('success', 'Static config saved')
        threading.Thread(target=lambda: _git_push_if_enabled('static config save'), daemon=True).start()
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
        add_notification('warning', 'Traefik restarted', category='traefik')
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
    req      = request.get_json(silent=True) or {}
    path     = _get_static_config_path()
    if not req.get('current_raw') and (not path or not os.path.exists(path)):
        return jsonify({'error': 'Static config not found'}), 404
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
                    eps[name] = eps.pop(old_name, None)
                ep = eps.get(name)
                if not isinstance(ep, dict):
                    ep = {}
                addr = str(payload.get('address', '')).strip()
                if addr:
                    ep['address'] = DoubleQuotedScalarString(addr)
                elif 'address' not in ep:
                    ep['address'] = ''
                http_blk = ep.get('http') if isinstance(ep.get('http'), dict) else {}
                redirect_to = str(payload.get('redirect_to', '')).strip()
                if redirect_to:
                    http_blk['redirections'] = {'entryPoint': {'to': redirect_to, 'scheme': 'https', 'permanent': True}}
                else:
                    http_blk.pop('redirections', None)
                uhs = str(payload.get('underscore_headers', '')).strip().lower()
                hdr_key = str(payload.get('headers_strategy_key', '')).strip()
                if hdr_key not in ('aliasHeadersStrategy', 'underscoreHeadersStrategy'):
                    hdr_key = 'underscoreHeadersStrategy'
                http_blk.pop('aliasHeadersStrategy', None)
                http_blk.pop('underscoreHeadersStrategy', None)
                if uhs in ('delete', 'reject'):
                    http_blk[hdr_key] = uhs
                mws = [m for m in re.split(r'[\s,]+', str(payload.get('middlewares', ''))) if m]
                if mws:
                    http_blk['middlewares'] = mws
                else:
                    http_blk.pop('middlewares', None)
                if payload.get('tls_enabled'):
                    tls_blk = http_blk.get('tls') if isinstance(http_blk.get('tls'), dict) else {}
                    cr = str(payload.get('tls_cert_resolver', '')).strip()
                    if cr:
                        tls_blk['certResolver'] = cr
                    else:
                        tls_blk.pop('certResolver', None)
                    topt = str(payload.get('tls_options', '')).strip()
                    if topt:
                        tls_blk['options'] = topt
                    else:
                        tls_blk.pop('options', None)
                    http_blk['tls'] = tls_blk
                else:
                    http_blk.pop('tls', None)
                if http_blk:
                    ep['http'] = http_blk
                else:
                    ep.pop('http', None)
                if payload.get('http3'):
                    ep['http3'] = {}
                else:
                    ep.pop('http3', None)
                if payload.get('as_default'):
                    ep['asDefault'] = True
                else:
                    ep.pop('asDefault', None)
                tr  = ep.get('transport') if isinstance(ep.get('transport'), dict) else {}
                rts = tr.get('respondingTimeouts') if isinstance(tr.get('respondingTimeouts'), dict) else {}
                for yaml_key, pay_key in (('readTimeout', 'read_timeout'), ('writeTimeout', 'write_timeout'), ('idleTimeout', 'idle_timeout')):
                    v = str(payload.get(pay_key, '')).strip()
                    if v:
                        if not _is_valid_duration(v):
                            return jsonify({'error': f'Invalid duration for {yaml_key}: {v!r} - use forms like 30, 30s, 1m30s'}), 400
                        rts[yaml_key] = int(v) if v.isdigit() else v
                    else:
                        rts.pop(yaml_key, None)
                if rts:
                    tr['respondingTimeouts'] = rts
                else:
                    tr.pop('respondingTimeouts', None)
                if tr:
                    ep['transport'] = tr
                else:
                    ep.pop('transport', None)
                fwd_ips = _parse_cidr_input(payload.get('trusted_ips'))
                pp_ips  = _parse_cidr_input(payload.get('proxy_trusted_ips'))
                bad = [c for c in fwd_ips + pp_ips if not _is_valid_cidr(c)]
                if bad:
                    return jsonify({'error': 'Invalid IP/CIDR: ' + ', '.join(bad)}), 400
                fh = ep.get('forwardedHeaders') if isinstance(ep.get('forwardedHeaders'), dict) else {}
                if fwd_ips:
                    fh['trustedIPs'] = fwd_ips
                else:
                    fh.pop('trustedIPs', None)
                if payload.get('forwarded_insecure'):
                    fh['insecure'] = True
                else:
                    fh.pop('insecure', None)
                if fh:
                    ep['forwardedHeaders'] = fh
                else:
                    ep.pop('forwardedHeaders', None)
                pp = ep.get('proxyProtocol') if isinstance(ep.get('proxyProtocol'), dict) else {}
                if pp_ips:
                    pp['trustedIPs'] = pp_ips
                else:
                    pp.pop('trustedIPs', None)
                if payload.get('proxy_insecure'):
                    pp['insecure'] = True
                else:
                    pp.pop('insecure', None)
                if pp:
                    ep['proxyProtocol'] = pp
                else:
                    ep.pop('proxyProtocol', None)
                eps[name] = ep
        elif section == 'resolvers':
            resolvers = config.setdefault('certificatesResolvers', {})
            if action == 'remove':
                resolvers.pop(name, None)
            else:
                if action == 'edit' and old_name != name:
                    existing_res = resolvers.pop(old_name, None)
                else:
                    existing_res = resolvers.get(name)
                if not isinstance(existing_res, dict):
                    existing_res = {}
                acme = existing_res.get('acme') if isinstance(existing_res.get('acme'), dict) else {}
                acme['email']   = payload.get('email', '')
                acme['storage'] = payload.get('storage', '/acme.json')
                ct = payload.get('challenge_type', 'dnsChallenge')
                if ct == 'dnsChallenge':
                    dns = acme.get('dnsChallenge') if isinstance(acme.get('dnsChallenge'), dict) else {}
                    dns['provider'] = payload.get('provider', '')
                    dns_res = [r for r in re.split(r'[\s,]+', str(payload.get('dns_resolvers', ''))) if r]
                    if dns_res:
                        dns['resolvers'] = dns_res
                    else:
                        dns.pop('resolvers', None)
                    prop  = dns.get('propagation') if isinstance(dns.get('propagation'), dict) else {}
                    delay = str(payload.get('dns_delay', '')).strip()
                    if delay:
                        if not _is_valid_duration(delay):
                            return jsonify({'error': f'Invalid propagation delay: {delay!r} - use forms like 30, 30s, 2m'}), 400
                        prop['delayBeforeChecks'] = int(delay) if delay.isdigit() else delay
                    else:
                        prop.pop('delayBeforeChecks', None)
                    if payload.get('dns_disable_checks'):
                        prop['disableChecks'] = True
                    else:
                        prop.pop('disableChecks', None)
                    if prop:
                        dns['propagation'] = prop
                    else:
                        dns.pop('propagation', None)
                    acme['dnsChallenge'] = dns
                    acme.pop('httpChallenge', None)
                    acme.pop('tlsChallenge', None)
                elif ct == 'httpChallenge':
                    http_ch = acme.get('httpChallenge') if isinstance(acme.get('httpChallenge'), dict) else {}
                    http_ch['entryPoint'] = payload.get('http_entrypoint', 'web')
                    acme['httpChallenge'] = http_ch
                    acme.pop('dnsChallenge', None)
                    acme.pop('tlsChallenge', None)
                else:
                    acme.setdefault('tlsChallenge', {})
                    acme.pop('dnsChallenge', None)
                    acme.pop('httpChallenge', None)
                ca = str(payload.get('ca_server', '')).strip()
                if ca:
                    acme['caServer'] = ca
                else:
                    acme.pop('caServer', None)
                kt = str(payload.get('key_type', '')).strip()
                if kt:
                    acme['keyType'] = kt
                else:
                    acme.pop('keyType', None)
                eab_kid  = str(payload.get('eab_kid', '')).strip()
                eab_hmac = str(payload.get('eab_hmac', '')).strip()
                if eab_kid and eab_hmac:
                    acme['eab'] = {'kid': eab_kid, 'hmacEncoded': eab_hmac}
                elif eab_kid or eab_hmac:
                    return jsonify({'error': 'EAB needs both the key ID and the HMAC'}), 400
                else:
                    acme.pop('eab', None)
                existing_res['acme'] = acme
                resolvers[name] = existing_res
        elif section == 'plugins':
            exp = config.setdefault('experimental', {})
            plugins = exp.get('plugins') if isinstance(exp.get('plugins'), dict) else {}
            local   = exp.get('localPlugins') if isinstance(exp.get('localPlugins'), dict) else {}
            if action == 'remove':
                plugins.pop(name, None)
                local.pop(name, None)
            else:
                if action == 'edit' and old_name != name:
                    plugins.pop(old_name, None)
                    local.pop(old_name, None)
                if payload.get('local'):
                    plugins.pop(name, None)
                    local[name] = {'moduleName': payload.get('moduleName', '')}
                else:
                    local.pop(name, None)
                    plugins[name] = {'moduleName': payload.get('moduleName', ''), 'version': payload.get('version', '')}
            if plugins:
                exp['plugins'] = plugins
            else:
                exp.pop('plugins', None)
            if local:
                exp['localPlugins'] = local
            else:
                exp.pop('localPlugins', None)
            if not exp:
                config.pop('experimental', None)
        elif section == 'api' and action == 'set':
            if payload.get('enabled', True):
                api_cfg = config.get('api')
                if not isinstance(api_cfg, dict):
                    api_cfg = {}
                if not payload.get('dashboard', True):
                    api_cfg['dashboard'] = False
                elif 'dashboard' in api_cfg:
                    api_cfg['dashboard'] = True
                if payload.get('insecure'):
                    api_cfg['insecure'] = True
                elif 'insecure' in api_cfg:
                    api_cfg['insecure'] = False
                if payload.get('debug'):
                    api_cfg['debug'] = True
                else:
                    api_cfg.pop('debug', None)
                config['api'] = api_cfg
            else:
                config.pop('api', None)
        elif section == 'log' and action == 'set':
            log_blk = config.get('log') if isinstance(config.get('log'), dict) else {}
            level = str(payload.get('level', 'ERROR')).upper()
            if level and level != 'ERROR':
                log_blk['level'] = level
            else:
                log_blk.pop('level', None)
            if str(payload.get('log_format', '')).strip() == 'json':
                log_blk['format'] = 'json'
            else:
                log_blk.pop('format', None)
            log_file = str(payload.get('log_file', '')).strip()
            if log_file:
                log_blk['filePath'] = log_file
            else:
                log_blk.pop('filePath', None)
            for yaml_key, pay_key in (('maxSize', 'log_max_size'), ('maxBackups', 'log_max_backups'), ('maxAge', 'log_max_age')):
                v = str(payload.get(pay_key, '')).strip()
                if v and log_file:
                    if not v.isdigit():
                        return jsonify({'error': f'Rotation {yaml_key} must be a whole number, got {v!r}'}), 400
                    log_blk[yaml_key] = int(v)
                else:
                    log_blk.pop(yaml_key, None)
            if payload.get('log_compress') and log_file:
                log_blk['compress'] = True
            else:
                log_blk.pop('compress', None)
            if log_blk:
                config['log'] = log_blk
            else:
                config.pop('log', None)
            if payload.get('accessLog'):
                al = config.get('accessLog') if isinstance(config.get('accessLog'), dict) else {}
                al_path = str(payload.get('accessLogPath', '')).strip()
                if al_path:
                    al['filePath'] = al_path
                else:
                    al.pop('filePath', None)
                if str(payload.get('al_format', '')).strip() == 'json':
                    al['format'] = 'json'
                else:
                    al.pop('format', None)
                buf = str(payload.get('al_buffering', '')).strip()
                if buf:
                    if not buf.isdigit():
                        return jsonify({'error': f'Buffering must be a whole number of lines, got {buf!r}'}), 400
                    al['bufferingSize'] = int(buf)
                else:
                    al.pop('bufferingSize', None)
                filters = al.get('filters') if isinstance(al.get('filters'), dict) else {}
                codes = [c for c in re.split(r'[\s,]+', str(payload.get('al_status_codes', ''))) if c]
                if codes:
                    bad_codes = [c for c in codes if not re.match(r'^\d{3}(-\d{3})?$', c)]
                    if bad_codes:
                        return jsonify({'error': 'Invalid status code filter: ' + ', '.join(bad_codes)}), 400
                    filters['statusCodes'] = codes
                else:
                    filters.pop('statusCodes', None)
                if payload.get('al_retry'):
                    filters['retryAttempts'] = True
                else:
                    filters.pop('retryAttempts', None)
                min_dur = str(payload.get('al_min_duration', '')).strip()
                if min_dur:
                    if not _is_valid_duration(min_dur):
                        return jsonify({'error': f'Invalid min duration: {min_dur!r} - use forms like 200ms, 1s'}), 400
                    filters['minDuration'] = int(min_dur) if min_dur.isdigit() else min_dur
                else:
                    filters.pop('minDuration', None)
                if filters:
                    al['filters'] = filters
                else:
                    al.pop('filters', None)
                hdr_mode = str(payload.get('al_headers_mode', '')).strip()
                fields = al.get('fields') if isinstance(al.get('fields'), dict) else {}
                hdrs = fields.get('headers') if isinstance(fields.get('headers'), dict) else {}
                if hdr_mode in ('keep', 'redact'):
                    hdrs['defaultMode'] = hdr_mode
                else:
                    hdrs.pop('defaultMode', None)
                if hdrs:
                    fields['headers'] = hdrs
                else:
                    fields.pop('headers', None)
                if fields:
                    al['fields'] = fields
                else:
                    al.pop('fields', None)
                config['accessLog'] = al
            else:
                config.pop('accessLog', None)
        elif section == 'providers' and action == 'set':
            providers = config.setdefault('providers', {})
            if payload.get('docker'):
                _existing = providers.get('docker')
                docker_cfg = _existing if isinstance(_existing, dict) else {}
                endpoint = str(payload.get('dockerEndpoint', '')).strip()
                if endpoint and endpoint != 'unix:///var/run/docker.sock':
                    docker_cfg['endpoint'] = endpoint
                else:
                    docker_cfg.pop('endpoint', None)
                if not payload.get('dockerExposedByDefault', True):
                    docker_cfg['exposedByDefault'] = False
                else:
                    docker_cfg.pop('exposedByDefault', None)
                if not payload.get('dockerWatch', True):
                    docker_cfg['watch'] = False
                else:
                    docker_cfg.pop('watch', None)
                providers['docker'] = docker_cfg
            else:
                providers.pop('docker', None)
            if payload.get('file'):
                _existing = providers.get('file')
                file_cfg = _existing if isinstance(_existing, dict) else {}
                directory = str(payload.get('fileDirectory', '')).strip()
                if directory:
                    file_cfg['directory'] = directory
                else:
                    file_cfg.pop('directory', None)
                if not payload.get('fileWatch', True):
                    file_cfg['watch'] = False
                else:
                    file_cfg.pop('watch', None)
                providers['file'] = file_cfg
            else:
                providers.pop('file', None)
            throttle = str(payload.get('providers_throttle', '')).strip()
            if throttle:
                if not _is_valid_duration(throttle):
                    return jsonify({'error': f'Invalid providers throttle: {throttle!r} - use forms like 2s, 500ms'}), 400
                providers['providersThrottleDuration'] = int(throttle) if throttle.isdigit() else throttle
            else:
                providers.pop('providersThrottleDuration', None)
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
        elif section == 'observability' and action == 'set':
            if payload.get('ping'):
                if not isinstance(config.get('ping'), dict):
                    config['ping'] = {}
            else:
                config.pop('ping', None)
            metrics = config.get('metrics') if isinstance(config.get('metrics'), dict) else {}
            if payload.get('prometheus'):
                prom = metrics.get('prometheus') if isinstance(metrics.get('prometheus'), dict) else {}
                if payload.get('prom_ep_labels', True):
                    prom.pop('addEntryPointsLabels', None)
                else:
                    prom['addEntryPointsLabels'] = False
                if payload.get('prom_router_labels'):
                    prom['addRoutersLabels'] = True
                else:
                    prom.pop('addRoutersLabels', None)
                if payload.get('prom_svc_labels', True):
                    prom.pop('addServicesLabels', None)
                else:
                    prom['addServicesLabels'] = False
                metrics['prometheus'] = prom
            else:
                metrics.pop('prometheus', None)
            if metrics:
                config['metrics'] = metrics
            else:
                config.pop('metrics', None)
            if payload.get('tracing'):
                tr_blk = config.get('tracing') if isinstance(config.get('tracing'), dict) else {}
                svc = str(payload.get('trace_service', '')).strip()
                if svc:
                    tr_blk['serviceName'] = svc
                else:
                    tr_blk.pop('serviceName', None)
                sr = str(payload.get('trace_sample', '')).strip()
                if sr:
                    try:
                        srf = float(sr)
                        if not 0 <= srf <= 1:
                            raise ValueError
                    except ValueError:
                        return jsonify({'error': f'Sample rate must be a number between 0 and 1, got {sr!r}'}), 400
                    tr_blk['sampleRate'] = srf
                else:
                    tr_blk.pop('sampleRate', None)
                ep_url = str(payload.get('trace_endpoint', '')).strip()
                otlp = tr_blk.get('otlp') if isinstance(tr_blk.get('otlp'), dict) else {}
                if ep_url:
                    oh = otlp.get('http') if isinstance(otlp.get('http'), dict) else {}
                    oh['endpoint'] = ep_url
                    otlp['http'] = oh
                else:
                    oh = otlp.get('http') if isinstance(otlp.get('http'), dict) else None
                    if oh is not None:
                        oh.pop('endpoint', None)
                        if not oh:
                            otlp.pop('http', None)
                if otlp:
                    tr_blk['otlp'] = otlp
                else:
                    tr_blk.pop('otlp', None)
                config['tracing'] = tr_blk
            else:
                config.pop('tracing', None)
        elif section == 'system' and action == 'set':
            g_blk = config.get('global') if isinstance(config.get('global'), dict) else {}
            if payload.get('check_new_version', True):
                g_blk.pop('checkNewVersion', None)
            else:
                g_blk['checkNewVersion'] = False
            if payload.get('send_usage'):
                g_blk['sendAnonymousUsage'] = True
            else:
                g_blk.pop('sendAnonymousUsage', None)
            if g_blk:
                config['global'] = g_blk
            else:
                config.pop('global', None)
            core_blk = config.get('core') if isinstance(config.get('core'), dict) else {}
            if str(payload.get('rule_syntax', '')).strip() == 'v2':
                core_blk['defaultRuleSyntax'] = 'v2'
            else:
                core_blk.pop('defaultRuleSyntax', None)
            if core_blk:
                config['core'] = core_blk
            else:
                config.pop('core', None)
            st = config.get('serversTransport') if isinstance(config.get('serversTransport'), dict) else {}
            if payload.get('st_insecure'):
                st['insecureSkipVerify'] = True
            else:
                st.pop('insecureSkipVerify', None)
            cas = [c for c in re.split(r'[\s,]+', str(payload.get('st_root_cas', ''))) if c]
            if cas:
                st['rootCAs'] = cas
            else:
                st.pop('rootCAs', None)
            max_idle = str(payload.get('st_max_idle', '')).strip()
            if max_idle:
                if not max_idle.isdigit():
                    return jsonify({'error': f'Max idle conns must be a whole number, got {max_idle!r}'}), 400
                st['maxIdleConnsPerHost'] = int(max_idle)
            else:
                st.pop('maxIdleConnsPerHost', None)
            fwd_t = st.get('forwardingTimeouts') if isinstance(st.get('forwardingTimeouts'), dict) else {}
            for yaml_key, pay_key in (('dialTimeout', 'st_dial'), ('responseHeaderTimeout', 'st_resp_header'), ('idleConnTimeout', 'st_idle_conn')):
                v = str(payload.get(pay_key, '')).strip()
                if v:
                    if not _is_valid_duration(v):
                        return jsonify({'error': f'Invalid duration for {yaml_key}: {v!r}'}), 400
                    fwd_t[yaml_key] = int(v) if v.isdigit() else v
                else:
                    fwd_t.pop(yaml_key, None)
            if fwd_t:
                st['forwardingTimeouts'] = fwd_t
            else:
                st.pop('forwardingTimeouts', None)
            if st:
                config['serversTransport'] = st
            else:
                config.pop('serversTransport', None)
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


_CLOUDFLARE_IPS_CAPTURED = '2026-07-23'
_CLOUDFLARE_IPS_V4 = [
    '173.245.48.0/20', '103.21.244.0/22', '103.22.200.0/22', '103.31.4.0/22',
    '141.101.64.0/18', '108.162.192.0/18', '190.93.240.0/20', '188.114.96.0/20',
    '197.234.240.0/22', '198.41.128.0/17', '162.158.0.0/15', '104.16.0.0/13',
    '104.24.0.0/14', '172.64.0.0/13', '131.0.72.0/22',
]
_CLOUDFLARE_IPS_V6 = [
    '2400:cb00::/32', '2606:4700::/32', '2803:f800::/32', '2405:b500::/32',
    '2405:8100::/32', '2a06:98c0::/29', '2c0f:f248::/32',
]
_PRIVATE_IP_RANGES = ['10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16', 'fc00::/7']


_DURATION_RE = re.compile(r'^(\d+(\.\d+)?(ns|us|µs|ms|s|m|h))+$')


def _is_valid_duration(v: str) -> bool:
    v = str(v).strip()
    return bool(v) and (v.isdigit() or bool(_DURATION_RE.match(v)))


def _is_valid_cidr(cidr: str) -> bool:
    try:
        ipaddress.ip_network(str(cidr).strip(), strict=False)
        return True
    except ValueError:
        return False


def _parse_cidr_input(raw) -> list:
    if isinstance(raw, list):
        parts = [str(x) for x in raw]
    else:
        parts = re.split(r'[\s,]+', str(raw or ''))
    return [p.strip() for p in parts if p.strip()]


@app.route('/api/static/trusted-ips/preview', methods=['POST'])
@csrf_protect
@login_required
def api_static_trusted_ips_preview():
    req = request.get_json(silent=True) or {}
    current_raw = req.get('current_raw', '')
    entrypoint  = str(req.get('entrypoint', '')).strip()
    try:
        _y = YAML()
        _y.preserve_quotes = True
        if current_raw:
            config = _y.load(StringIO(current_raw)) or {}
        else:
            path = _get_static_config_path()
            if not path or not os.path.exists(path):
                return jsonify({'error': 'Static config not found'}), 404
            with open(path, 'r') as f:
                config = _y.load(f) or {}
        if not isinstance(config, dict):
            return jsonify({'error': 'Static config is not a mapping'}), 400
        ep_key = 'entryPoints' if 'entryPoints' in config else ('entrypoints' if 'entrypoints' in config else 'entryPoints')
        eps = config.get(ep_key)
        summary = []
        if isinstance(eps, dict):
            for nm, cfg in eps.items():
                cur = []
                addr = ''
                if isinstance(cfg, dict):
                    addr = str(cfg.get('address', ''))
                    fh = cfg.get('forwardedHeaders')
                    if isinstance(fh, dict) and isinstance(fh.get('trustedIPs'), list):
                        cur = [str(x) for x in fh['trustedIPs']]
                summary.append({'name': str(nm), 'address': addr, 'trusted_ips': cur})
        resp = {
            'ok': True,
            'entrypoints': summary,
            'cloudflare_captured': _CLOUDFLARE_IPS_CAPTURED,
            'cloudflare_ranges': _CLOUDFLARE_IPS_V4 + _CLOUDFLARE_IPS_V6,
            'private_ranges': _PRIVATE_IP_RANGES,
        }
        if not entrypoint:
            return jsonify(resp)
        if not isinstance(eps, dict) or entrypoint not in eps:
            return jsonify({'error': f'Entrypoint "{entrypoint}" not found in static config'}), 400
        custom  = _parse_cidr_input(req.get('custom_cidrs', []))
        invalid = [c for c in custom if not _is_valid_cidr(c)]
        additions = []
        if req.get('cloudflare'):
            additions += _CLOUDFLARE_IPS_V4 + _CLOUDFLARE_IPS_V6
        if req.get('private'):
            additions += _PRIVATE_IP_RANGES
        additions += [c for c in custom if _is_valid_cidr(c)]
        ep = eps.get(entrypoint)
        if not isinstance(ep, dict):
            ep = {}
        fh = ep.get('forwardedHeaders') if isinstance(ep.get('forwardedHeaders'), dict) else {}
        cur_seq = fh.get('trustedIPs')
        existing = [str(x) for x in cur_seq] if isinstance(cur_seq, list) else []
        final, added = _merge_trusted_ips(existing, additions)
        if isinstance(cur_seq, list):
            for c in added:
                cur_seq.append(DoubleQuotedScalarString(c))
        else:
            fh['trustedIPs'] = [DoubleQuotedScalarString(c) for c in final]
        ep['forwardedHeaders'] = fh
        eps[entrypoint] = ep
        stream = StringIO()
        _y.dump(config, stream)
        new_raw = stream.getvalue()
        parsed = SafeYAML(typ='safe').load(new_raw) or {}
        resp.update({
            'entrypoint': entrypoint,
            'existing': existing,
            'added': added,
            'final': final,
            'invalid': invalid,
            'raw': new_raw,
            'parsed': parsed,
        })
        return jsonify(resp)
    except Exception as e:
        logger.exception("Trusted IPs preview failed")
        return jsonify({'error': str(e)}), 500


@app.route('/api/tools/digestauth', methods=['POST'])
@login_required
def api_digestauth():
    import hashlib
    data     = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    realm    = data.get('realm', '').strip()
    password = data.get('password', '')
    if not username or not realm or not password:
        return jsonify({'ok': False, 'error': 'username, realm and password required'}), 400
    h = hashlib.md5(f'{username}:{realm}:{password}'.encode()).hexdigest()
    return jsonify({'ok': True, 'hash': f'{username}:{realm}:{h}'})

@app.route('/api/tools/htpasswd', methods=['POST'])
@login_required
def api_htpasswd():
    import random, string
    data     = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')
    if not username or not password:
        return jsonify({'ok': False, 'error': 'username and password required'}), 400
    salt = ''.join(random.choices(string.ascii_letters + string.digits + './', k=8))
    h    = _apr1_hash(password, salt)
    return jsonify({'ok': True, 'hash': f'{username}:{h}'})

@app.route('/api/geoip/status')
@login_required
def api_geoip_status():
    return jsonify(_geoip_status())

@app.route('/api/geoip/lookup', methods=['POST'])
@csrf_protect
@login_required
def api_geoip_lookup():
    if not _geoip_enabled():
        return jsonify({'enabled': False, 'available': False, 'results': {}})
    data = request.get_json(silent=True) or {}
    ips  = data.get('ips') or []
    if not isinstance(ips, list):
        ips = []
    reader = _geoip_reader()
    available = reader is not None
    aggregate = bool(data.get('aggregate'))
    results = {}
    counts = {}
    codes = {}
    if available:
        seen = set()
        for raw in ips:
            ip = str(raw).strip()
            if not ip or ip in seen:
                continue
            seen.add(ip)
            geo = _geoip_lookup(ip, reader)
            if not geo:
                continue
            if aggregate:
                cc = geo.get('country_code')
                if cc:
                    entry = counts.setdefault(cc, {'count': 0, 'country': geo.get('country')})
                    entry['count'] += 1
                    codes[ip] = cc
            else:
                results[ip] = geo
    payload = {'enabled': True, 'available': available}
    if aggregate:
        payload['counts'] = counts
        payload['codes'] = codes
    else:
        payload['results'] = results
    return jsonify(payload)

@app.route('/api/geoip/update', methods=['POST'])
@csrf_protect
@login_required
@limiter.limit("6 per hour")
def api_geoip_update():
    ok, info = _geoip_download()
    if ok:
        add_notification('success', f'GeoIP database updated (DB-IP {info})', category='update')
        return jsonify({'success': True, 'db_month': info, 'status': _geoip_status()})
    return jsonify({'success': False, 'error': f'Download failed: {info}'}), 502

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
    if not _ssrf_ok(url):
        return jsonify({'ok': False, 'error': 'Target address not allowed'}), 400
    u = str(data.get('user', '')).strip()
    p = str(data.get('password', '')).strip()
    auth = (u, p) if u and p else None
    try:
        resp = requests.get(f"{url}/api/version", timeout=4, auth=auth, verify=_traefik_verify())
        if resp.status_code == 200:
            info = resp.json()
            return jsonify({'ok': True, 'version': info.get('Version', '?')})
        if resp.status_code in (401, 403):
            return jsonify({'ok': False, 'error': f'HTTP {resp.status_code} - check the API username and password'})
        return jsonify({'ok': False, 'error': f'HTTP {resp.status_code} from {url}/api/version'})
    except requests.exceptions.SSLError as e:
        return jsonify({'ok': False, 'error': f'TLS verification failed - the API certificate is not trusted. Mount your CA into /etc/ssl/certs/ca-certificates.crt or set TRAEFIK_INSECURE_SKIP_VERIFY=true. ({str(e)[:120]})'})
    except requests.exceptions.Timeout:
        return jsonify({'ok': False, 'error': 'Connection timed out - the API URL may be unreachable from the container'})
    except requests.exceptions.ConnectionError as e:
        return jsonify({'ok': False, 'error': f'Connection error - check the URL and network. ({str(e)[:120]})'})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)[:160]})


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

_PLUGIN_CATALOG = {'ts': 0.0, 'map': {}}


@app.route('/api/plugins/catalog')
@login_required
def api_plugin_catalog():
    now = time.time()
    if now - _PLUGIN_CATALOG['ts'] > 86400:
        try:
            r = requests.get('https://plugins.traefik.io/api/services/plugins', timeout=8)
            r.raise_for_status()
            items = r.json()
            catalog = {}
            for item in items if isinstance(items, list) else []:
                mod = str(item.get('import') or '').strip().lower()
                ver = str(item.get('latestVersion') or '').strip()
                if mod and ver:
                    catalog[mod] = ver
            if catalog:
                _PLUGIN_CATALOG['map'] = catalog
                _PLUGIN_CATALOG['ts'] = now
            else:
                _PLUGIN_CATALOG['ts'] = now - 86400 + 900
        except Exception:
            _PLUGIN_CATALOG['ts'] = now - 86400 + 900
    return jsonify({'plugins': _PLUGIN_CATALOG['map']})


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
    agent = None
    static_path = None
    server = str(data.get('server') or '').strip()
    if server:
        agent = _agent_by_id(server)
        if not agent:
            return jsonify({'ok': False, 'error': 'Agent not found'}), 404
        try:
            resp = _agent_request(agent, 'GET', '/api/static')
        except requests.exceptions.RequestException as e:
            return jsonify({'ok': False, 'error': f'Cannot reach agent: {e}'}), 502
        if resp.status_code != 200:
            return jsonify({'ok': False, 'error': 'Static config not available on this agent'}), 404
        source_raw = (resp.json() or {}).get('content', '')
    else:
        static_path = _get_static_config_path()
        if not static_path or not os.path.exists(static_path):
            return jsonify({'ok': False, 'error': 'Static config not found'}), 404
        with open(static_path, 'r') as f:
            source_raw = f.read()
    try:
        _ry = YAML()
        _ry.preserve_quotes = True
        config = _ry.load(StringIO(source_raw)) or {}
        if 'experimental' not in config:
            config['experimental'] = {}
        if 'plugins' not in config['experimental']:
            config['experimental']['plugins'] = {}
        for plugin_name, plugin_data in plugins_block.items():
            config['experimental']['plugins'][plugin_name] = {
                'moduleName': plugin_data.get('moduleName', ''),
                'version': plugin_data.get('version', ''),
            }
        stream = StringIO()
        _ry.dump(config, stream)
        if agent:
            wresp = _agent_request(agent, 'POST', '/api/static', json={'content': stream.getvalue()})
            if wresp.status_code != 200:
                return jsonify({'ok': False, 'error': 'Agent rejected the static config write'}), 502
        else:
            create_backup(static_path)
            with open(static_path, 'w') as f:
                f.write(stream.getvalue())
    except requests.exceptions.RequestException as e:
        return jsonify({'ok': False, 'error': f'Cannot reach agent: {e}'}), 502
    except Exception as e:
        logger.exception("Failed to save plugin to static config")
        return jsonify({'ok': False, 'error': str(e)}), 500
    warning = None
    mw_written = None
    if middleware_yaml and not agent and not ACTIVE_CONFIG_DIR:
        warning = 'Plugin saved, but the middleware was not written - no config directory is configured, so there is no file to write it to'
    if middleware_yaml and (agent or ACTIVE_CONFIG_DIR):
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
                mw_choice = str(data.get('middleware_file') or '').strip()
                existing = {}
                if agent:
                    mw_name = os.path.basename(mw_choice) or 'plugin-middlewares.yml'
                    if '..' in mw_name:
                        raise ValueError('invalid middleware file name')
                    if not mw_name.endswith(('.yml', '.yaml')):
                        mw_name += '.yml'
                    mw_label = mw_name
                    try:
                        cresp = _agent_request(agent, 'GET', '/api/configs')
                        for fobj in (cresp.json() or {}).get('files', []):
                            if fobj.get('name') == mw_name:
                                existing = yaml.load(StringIO(fobj.get('content', ''))) or {}
                                break
                    except Exception:
                        existing = {}
                else:
                    if mw_choice:
                        mw_file = _resolve_config_path(mw_choice)
                        if not mw_file:
                            raise ValueError(f'middleware file not allowed: {mw_choice!r}')
                    else:
                        mw_file = os.path.join(ACTIVE_CONFIG_DIR, 'plugin-middlewares.yml')
                    mw_label = os.path.basename(mw_file)
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
                if agent:
                    mresp = _agent_request(agent, 'POST', '/api/configs', json={'name': mw_name, 'content': stream.getvalue()})
                    if mresp.status_code != 200:
                        raise RuntimeError('agent rejected the middleware file write')
                else:
                    if os.path.exists(mw_file):
                        create_backup(mw_file)
                    with open(mw_file, 'w') as f:
                        f.write(stream.getvalue())
                mw_written = mw_label
        except Exception as e:
            logger.exception("Failed to save middleware")
            warning = f'Plugin saved but middleware could not be written: {e}'
    plugin_names = list(plugins_block.keys())
    add_notification('success', f'Plugin installed: {", ".join(plugin_names)}')
    result = {'ok': True, 'plugins': plugin_names}
    if mw_written:
        result['middleware_file'] = mw_written
    if warning:
        result['warning'] = warning
    return jsonify(result)


@app.route('/api/traefik/certs')
@login_required
def api_certs():
    import json as _json
    certs = []
    errors = []

    acme_paths = _settings.get_acme_json_paths()
    found_any  = False
    for configured in acme_paths:
        acme_path = _readable_config_path(configured)
        if not (acme_path and os.path.exists(acme_path)):
            errors.append(f'acme.json not found at {configured}.')
            continue
        found_any = True
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
                    certs.append({'resolver': resolver_name, 'main': domain.get('main', ''),
                                  'sans': domain.get('sans', []) or [], 'not_after': not_after,
                                  'source': os.path.basename(acme_path)})
        except PermissionError:
            errors.append(f'Permission denied reading {acme_path}. Run: chmod o+r {acme_path}')
        except Exception as e:
            logger.exception("Error reading acme.json")
            errors.append(f'{os.path.basename(acme_path)}: {e}')
    if not acme_paths or not found_any:
        errors.append('Set ACME_JSON_PATH env var or configure the path in Settings. '
                      'Several files can be given comma-separated, or point it at a directory.')

    certs.extend(_certs_from_tls_configs())

    if not certs and errors:
        return jsonify({'certs': [], 'error': ' | '.join(errors)})
    return jsonify({'certs': certs})

@app.route('/api/traefik/logs')
@login_required
def api_logs():
    try:
        lines_req = min(int(request.args.get('lines', 100)), 1000)
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid lines parameter'}), 400
    log_path = _readable_config_path(_get_access_log_path())
    if not log_path or not os.path.exists(log_path):
        return jsonify({'error': 'Access log not found. Set ACCESS_LOG_PATH env var or configure the path in Settings.', 'lines': []})
    try:
        lines = []
        buf_size = 8192
        with open(log_path, 'rb') as f:
            f.seek(0, 2)
            remaining = f.tell()
            partial = b''
            while remaining > 0 and sum(1 for ln in lines if ln.strip()) < lines_req:
                chunk = min(buf_size, remaining)
                remaining -= chunk
                f.seek(remaining)
                data = f.read(chunk) + partial
                split = data.split(b'\n')
                partial = split[0]
                lines = split[1:] + lines
            if partial:
                lines = [partial] + lines
        kept = [ln for ln in lines if ln.strip()]
        result = [ln.decode('utf-8', errors='replace').rstrip() for ln in kept[-lines_req:]]
        return jsonify({'lines': result})
    except Exception as e:
        return jsonify({'error': str(e), 'lines': []})


def list_backups():
    ensure_backup_dir()
    static_path = _get_static_config_path()
    static_base = os.path.basename(static_path) if static_path else None
    _name_re    = re.compile(r'^(.+)\.(\d{8}_\d{6})\.bak$')
    backups = []
    for f in os.listdir(BACKUP_DIR):
        if f.endswith('.bak'):
            path = os.path.join(BACKUP_DIR, f)
            st   = os.stat(path)
            m    = _name_re.match(f)
            orig   = m.group(1) if m else ''
            ts_str = m.group(2) if m else ''
            kind = 'static' if static_base and orig == static_base else 'routes'
            backups.append({
                'name':     f,
                'size':     st.st_size,
                'modified': time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime)),
                'sort_key': ts_str or str(st.st_mtime),
                'kind':     kind,
            })
    backups.sort(key=lambda b: b['sort_key'], reverse=True)
    for b in backups:
        del b['sort_key']
    return backups

_BACKUP_RE = re.compile(r'^[a-zA-Z0-9._ -]+\.yml\.\d{8}_\d{6}\.bak$')

def _validated_backup_path(filename: str) -> str:
    if not _BACKUP_RE.match(filename):
        logger.warning(f"Invalid backup filename rejected: {filename!r}")
        abort(400)
    path = os.path.realpath(os.path.join(BACKUP_DIR, filename))
    if not path.startswith(os.path.realpath(BACKUP_DIR)):
        logger.warning(f"Path traversal attempt blocked: {filename!r}")
        abort(400)
    return path


def _git_req_agent():
    agent_id = (request.args.get('agent_id') or '').strip()
    if not agent_id:
        return None, False
    return _agent_by_id(agent_id), True

@app.route('/api/backup/git/status')
@login_required
def api_git_backup_status():
    agent, wanted = _git_req_agent()
    if wanted and not agent:
        return jsonify({'error': 'Agent not found'}), 404
    s          = load_settings()
    configured = bool(s.get('git_backup_repo', '').strip())
    repo_dir   = _git_agent_repo_dir(agent['id']) if agent else _git_repo_dir()
    result     = {'enabled': bool(s.get('git_backup_enabled')), 'configured': configured, 'last_sha': None, 'last_push': None}
    if agent:
        result['branch'] = _agent_git_branch(agent)
    if configured and os.path.exists(os.path.join(repo_dir, '.git')):
        out, _, rc = _git_run(['log', '-1', '--format=%H|%ci|%s'], cwd=repo_dir)
        if rc == 0 and '|' in out:
            parts = out.split('|', 2)
            result['last_sha']  = parts[0][:8]
            result['last_push'] = parts[1].strip() if len(parts) > 1 else None
    return jsonify(result)

@app.route('/api/backup/git/push', methods=['POST'])
@csrf_protect
@login_required
def api_git_backup_push():
    agent, wanted = _git_req_agent()
    if wanted and not agent:
        return jsonify({'error': 'Agent not found'}), 404
    data    = request.get_json(silent=True) or {}
    message = str(data.get('message', '')).strip()
    if agent:
        ok, err = _git_push_agent_configs(agent, 'manual', custom_message=message or None)
    else:
        ok, err = _git_push_configs('manual', custom_message=message or None)
    if ok:
        add_notification('success', f"Git backup pushed ({agent['name']})" if agent else 'Git backup pushed',
                         category='backup')
        return jsonify({'ok': True})
    add_notification('error', f'Git push failed: {err}', category='backup')
    return jsonify({'ok': False, 'error': err}), 400

def _same_git_remote(a: str, b: str) -> bool:
    a, b = (a or '').strip().rstrip('/'), (b or '').strip().rstrip('/')
    return bool(a) and bool(b) and a.lower() == b.lower()


@app.route('/api/backup/git/test', methods=['POST'])
@csrf_protect
@login_required
def api_git_backup_test():
    body     = request.get_json(silent=True) or {}
    s        = load_settings()
    repo_url = (body.get('repo_url') or s.get('git_backup_repo', '')).strip()
    username = (body.get('username') or s.get('git_backup_username', '')).strip()
    token    = (body.get('token') or '').strip()
    if not token and _same_git_remote(repo_url, s.get('git_backup_repo', '')):
        token = str(s.get('git_backup_token', '')).strip()
    if not repo_url:
        return jsonify({'ok': False, 'error': 'No repository URL configured'}), 400
    if not _valid_git_url(repo_url):
        return jsonify({'ok': False, 'error': 'Unsupported URL - use https://, http://, ssh:// or git://'}), 400
    creds = {'username': username, 'token': token} if token else None
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        _, err, rc = _git_run(['ls-remote', '--quiet', '--', repo_url], cwd=tmpdir, credentials=creds)
    if rc == 0:
        return jsonify({'ok': True})
    safe_err = err.replace(token, '***') if token else err
    return jsonify({'ok': False, 'error': safe_err or 'Could not reach repository'}), 400

@app.route('/api/backup/git/commits')
@login_required
def api_git_backup_commits():
    agent, wanted = _git_req_agent()
    if wanted and not agent:
        return jsonify([])
    repo_dir = _git_agent_repo_dir(agent['id']) if agent else _git_repo_dir()
    if not os.path.exists(os.path.join(repo_dir, '.git')):
        return jsonify([])
    out, _, rc = _git_run(['log', '--format=%H|%ci|%s', '-50'], cwd=repo_dir)
    if rc != 0:
        return jsonify([])
    commits = []
    for line in out.splitlines():
        parts = line.split('|', 2)
        if len(parts) == 3:
            commits.append({'sha': parts[0], 'sha_short': parts[0][:8], 'timestamp': parts[1].strip(), 'message': parts[2].strip()})
    return jsonify(commits)

@app.route('/api/backup/git/commit/<sha>/diff')
@login_required
def api_git_backup_diff(sha):
    if not re.match(r'^[0-9a-f]{7,40}$', sha):
        abort(400)
    agent, wanted = _git_req_agent()
    if wanted and not agent:
        return jsonify({'stat': '', 'files': []})
    repo_dir = _git_agent_repo_dir(agent['id']) if agent else _git_repo_dir()
    if not os.path.exists(os.path.join(repo_dir, '.git')):
        return jsonify({'stat': '', 'files': []})
    try:
        stat, _, _ = _git_run(['show', '--stat', '--format=', sha], cwd=repo_dir)
        changed, _, rc = _git_run(['diff-tree', '--no-commit-id', '-r', '--name-status', sha], cwd=repo_dir)
        files = []
        for line in changed.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split('\t', 1)
            if len(parts) != 2:
                continue
            status, filename = parts[0].strip(), parts[1].strip()
            new_content, _, new_rc = _git_run(['show', f'{sha}:{filename}'], cwd=repo_dir)
            old_content, _, old_rc = _git_run(['show', f'{sha}^:{filename}'], cwd=repo_dir)
            files.append({
                'filename': filename,
                'status':   status,
                'old':      old_content if old_rc == 0 else '',
                'new':      new_content if new_rc == 0 else '',
            })
        return jsonify({'stat': stat, 'files': files})
    except Exception as e:
        logger.exception("Git diff error")
        return jsonify({'error': str(e)}), 500


@app.route('/api/backup/git/restore/<sha>', methods=['POST'])
@csrf_protect
@login_required
def api_git_backup_restore(sha):
    if not re.match(r'^[0-9a-f]{7,40}$', sha):
        abort(400)
    agent, wanted = _git_req_agent()
    if wanted and not agent:
        return jsonify({'error': 'Agent not found'}), 404
    repo_dir = _git_agent_repo_dir(agent['id']) if agent else _git_repo_dir()
    if not os.path.exists(os.path.join(repo_dir, '.git')):
        return jsonify({'error': 'Git repo not initialized'}), 400
    try:
        if agent:
            out, _, rc = _git_run(['ls-tree', '-r', '--name-only', sha, 'dynamic/'], cwd=repo_dir)
            if rc != 0:
                return jsonify({'error': 'Commit not found'}), 404
            restored = 0
            for fpath in out.splitlines():
                fpath = fpath.strip()
                if not fpath:
                    continue
                content, _, src = _git_run(['show', f'{sha}:{fpath}'], cwd=repo_dir)
                if src == 0:
                    resp = _agent_request(agent, 'POST', '/api/configs', json={'name': os.path.basename(fpath), 'content': content})
                    resp.raise_for_status()
                    restored += 1
            add_notification('warning', f"Restored {agent['name']} from git commit {sha[:8]} ({restored} files)",
                             category='backup')
            return jsonify({'ok': True})
        for p in env.CONFIG_PATHS:
            create_backup(p)
        sp = _get_static_config_path()
        if sp:
            create_backup(sp)
        for p in env.CONFIG_PATHS:
            base    = os.path.basename(p)
            content = _git_show_first(repo_dir, sha, [f'dynamic/{base}', base])
            if content:
                with open(p, 'w') as f:
                    f.write(content)
        if sp:
            base    = os.path.basename(sp)
            content = _git_show_first(repo_dir, sha, [f'static/{base}', base])
            if content:
                with open(sp, 'w') as f:
                    f.write(content)
        add_notification('warning', f'Restored from git commit {sha[:8]}', category='backup')
        return jsonify({'ok': True})
    except Exception as e:
        logger.exception("Git restore error")
        add_notification('error', f'Git restore failed: {e}', category='backup')
        return jsonify({'error': str(e)}), 500


@app.route('/api/backup/git/repo', methods=['DELETE'])
@csrf_protect
@login_required
def api_git_backup_reset():
    agent, wanted = _git_req_agent()
    if wanted and not agent:
        return jsonify({'error': 'Agent not found'}), 404
    repo_dir = _git_agent_repo_dir(agent['id']) if agent else _git_repo_dir()
    try:
        if os.path.exists(repo_dir):
            shutil.rmtree(repo_dir)
        logger.info("Git repo directory reset by user")
        add_notification('warning', 'Git repository reset - re-initialize by pushing again', category='backup')
        return jsonify({'ok': True})
    except Exception as e:
        logger.exception("Git repo reset error")
        return jsonify({'error': str(e)}), 500


@app.route('/api/notifications')
@login_required
def api_notifications():
    return jsonify(get_notifications())

@app.route('/api/notifications/log', methods=['POST'])
@csrf_protect
@login_required
def api_notifications_log():
    data = request.get_json(silent=True) or {}
    msg = str(data.get('message', ''))[:300].strip()
    type_ = str(data.get('type', 'info')).lower()
    if type_ not in ('info', 'success', 'warning', 'error'):
        type_ = 'info'
    if not msg:
        return jsonify({'ok': False}), 400
    category = str(data.get('category', '')).strip().lower()
    if category not in _settings.CHANNEL_CATEGORIES:
        category = 'config'
    stored = add_notification(type_, msg, category=category, webhook=False)
    return jsonify({'ok': True, 'stored': stored})


@app.route('/api/notifications/delete', methods=['POST'])
@csrf_protect
@login_required
def api_notifications_delete():
    data = request.get_json(silent=True) or {}
    if 'id' in data:
        if not _noti.delete_notification_by_id(data.get('id')):
            return jsonify({'ok': False, 'message': 'Notification not found'}), 404
        return jsonify({'ok': True})
    ts = data.get('ts', '')
    if not ts:
        return jsonify({'ok': False, 'message': 'Missing id or ts'}), 400
    delete_notification(ts)
    return jsonify({'ok': True})


@app.route('/api/notifications/read', methods=['POST'])
@csrf_protect
@login_required
def api_notifications_read():
    data = request.get_json(silent=True) or {}
    if data.get('all'):
        marker = _noti.highest_id()
    else:
        try:
            marker = int(data.get('id'))
        except (TypeError, ValueError):
            return jsonify({'ok': False, 'message': 'Missing id or all'}), 400
    s = load_settings()
    save_settings(
        domains=s['domains'], cert_resolver=s['cert_resolver'],
        traefik_api_url=s['traefik_api_url'], auth_enabled=s['auth_enabled'],
        password_hash=s['password_hash'], visible_tabs=s['visible_tabs'],
        notifications_read_until=max(0, marker),
    )
    return jsonify({'ok': True, 'read_until': max(0, marker)})


@app.route('/api/notifications/state')
@login_required
def api_notifications_state():
    entries = _noti.get_notifications()
    marker  = int(load_settings().get('notifications_read_until', 0) or 0)
    unread  = sum(1 for e in entries if int(e.get('id', 0) or 0) > marker)
    return jsonify({'read_until': marker, 'count': len(entries), 'unread': unread})

@app.route('/api/notifications/clear', methods=['POST'])
@csrf_protect
@login_required
def api_notifications_clear():
    clear_notifications()
    return jsonify({'ok': True})

@app.route('/api/notifications/add', methods=['POST'])
@csrf_protect
@login_required
def api_notifications_add():
    data = request.get_json(silent=True) or {}
    type_ = data.get('type', 'info')
    msg   = (data.get('message') or '').strip()
    if not msg:
        return jsonify({'ok': False, 'error': 'message required'}), 400
    category = str(data.get('category', '')).strip().lower()
    if category not in _settings.CHANNEL_CATEGORIES:
        category = 'config'
    add_notification(type_, msg, category=category)
    return jsonify({'ok': True})

@app.route('/api/notifications/update', methods=['POST'])
@csrf_protect
@login_required
def api_notifications_update():
    data    = request.get_json(silent=True) or {}
    version = data.get('version', '')
    product = 'Traefik Manager' if data.get('product') == 'manager' else 'Traefik'
    if version:
        add_notification('info', f"{product} v{version} is available - update now", category='update')
    return jsonify({'ok': True})


_CHANNEL_SECRETS = ('token', 'token2', 'password')

_CHANNEL_SECRET_URL_KINDS = ('discord', 'slack', 'ntfy', 'generic')


def _mask_channel_url(kind: str, url: str) -> str:
    if not url or kind not in _CHANNEL_SECRET_URL_KINDS:
        return url
    try:
        parts = urlparse(url)
        if not parts.scheme or not parts.netloc:
            return '***'
        return f'{parts.scheme}://{parts.netloc}/***'
    except Exception:
        return '***'

_QUIET_HOURS_RE = re.compile(r'^(?:[01]\d|2[0-3]):[0-5]\d-(?:[01]\d|2[0-3]):[0-5]\d$')


def _redact_channel(c: dict) -> dict:
    out = dict(c)
    for field in _CHANNEL_SECRETS:
        out[field] = '***' if out.get(field) else ''
    out['url'] = _mask_channel_url(out.get('kind', ''), out.get('url', ''))
    return out


def _blank_channel() -> dict:
    return {
        'id':            _settings._new_channel_id(),
        'name':          '',
        'kind':          '',
        'enabled':       True,
        'url':           '',
        'token':         '',
        'token2':        '',
        'username':      '',
        'password':      '',
        'categories':    list(_settings.CHANNEL_CATEGORIES),
        'min_severity':  'info',
        'digest':        'immediate',
        'quiet_hours':   '',
        'break_through': False,
    }


def _apply_channel_fields(data, base, require_kind):
    ch = dict(base)
    if require_kind or 'kind' in data:
        kind = str(data.get('kind', '')).strip().lower()
        if kind not in _settings.CHANNEL_KINDS:
            return None, 'kind must be one of: ' + ', '.join(_settings.CHANNEL_KINDS)
        ch['kind'] = kind
    if 'categories' in data:
        raw = data.get('categories')
        if not isinstance(raw, list):
            return None, 'categories must be a list'
        unknown = [str(c) for c in raw if c not in _settings.CHANNEL_CATEGORIES]
        if unknown:
            return None, 'unknown categories: ' + ', '.join(unknown)
        ch['categories'] = list(raw)
    if 'min_severity' in data:
        sev = str(data.get('min_severity', '')).strip().lower()
        if sev not in _settings.CHANNEL_SEVERITIES:
            return None, 'min_severity must be one of: ' + ', '.join(_settings.CHANNEL_SEVERITIES)
        ch['min_severity'] = sev
    if 'digest' in data:
        digest = str(data.get('digest', '')).strip().lower()
        if digest not in _settings.CHANNEL_DIGESTS:
            return None, 'digest must be one of: ' + ', '.join(_settings.CHANNEL_DIGESTS)
        ch['digest'] = digest
    if 'quiet_hours' in data:
        window = str(data.get('quiet_hours', '')).strip()
        if window and not _QUIET_HOURS_RE.match(window):
            return None, 'quiet_hours must be HH:MM-HH:MM, for example 23:00-07:00'
        ch['quiet_hours'] = window
    if 'name' in data:
        ch['name'] = str(data.get('name', '')).strip()[:60]
    if 'url' in data:
        incoming_url = str(data.get('url', '')).strip()[:500]
        if '***' not in incoming_url:
            ch['url'] = incoming_url
    if 'username' in data:
        ch['username'] = str(data.get('username', '')).strip()[:100]
    if 'enabled' in data:
        ch['enabled'] = bool(data.get('enabled'))
    if 'break_through' in data:
        ch['break_through'] = bool(data.get('break_through'))
    for field in _CHANNEL_SECRETS:
        if field in data and str(data[field]) != '***':
            ch[field] = str(data[field])
    return ch, ''


def _save_channels(settings, channels):
    save_settings(
        domains=settings['domains'],
        cert_resolver=settings['cert_resolver'],
        traefik_api_url=settings['traefik_api_url'],
        auth_enabled=settings['auth_enabled'],
        password_hash=settings['password_hash'],
        visible_tabs=settings['visible_tabs'],
        notification_channels=channels,
    )


def _stored_channel(channel_id, fallback):
    channels = load_settings().get('notification_channels', [])
    return next((c for c in channels if c.get('id') == channel_id), fallback)


@app.route('/api/notifications/channels', methods=['GET'])
@login_required
def api_notification_channels_list():
    channels = load_settings().get('notification_channels', [])
    return jsonify({'channels': [_redact_channel(c) for c in channels]})


@app.route('/api/notifications/channels', methods=['POST'])
@csrf_protect
@login_required
def api_notification_channels_create():
    data     = request.get_json(silent=True) or {}
    settings = load_settings()
    channel, err = _apply_channel_fields(data, _blank_channel(), True)
    if err:
        return jsonify({'ok': False, 'error': err}), 400
    channel['name'] = channel['name'] or channel['kind'].title()
    channels = list(settings.get('notification_channels', []))
    channels.append(channel)
    _save_channels(settings, channels)
    logger.info(f"Notification channel '{channel['name']}' ({channel['kind']}) created by {request.remote_addr}")
    return jsonify({'ok': True, 'channel': _redact_channel(_stored_channel(channel['id'], channel))})


@app.route('/api/notifications/channels/<channel_id>', methods=['PUT'])
@csrf_protect
@login_required
def api_notification_channels_update(channel_id):
    data     = request.get_json(silent=True) or {}
    settings = load_settings()
    channels = list(settings.get('notification_channels', []))
    idx = next((i for i, c in enumerate(channels) if c.get('id') == channel_id), None)
    if idx is None:
        return jsonify({'ok': False, 'error': 'Channel not found'}), 404
    channel, err = _apply_channel_fields(data, channels[idx], False)
    if err:
        return jsonify({'ok': False, 'error': err}), 400
    channel['id'] = channel_id
    channels[idx] = channel
    _save_channels(settings, channels)
    return jsonify({'ok': True, 'channel': _redact_channel(_stored_channel(channel_id, channel))})


@app.route('/api/notifications/channels/<channel_id>', methods=['DELETE'])
@csrf_protect
@login_required
def api_notification_channels_delete(channel_id):
    settings = load_settings()
    current  = settings.get('notification_channels', [])
    channels = [c for c in current if c.get('id') != channel_id]
    if len(channels) == len(current):
        return jsonify({'ok': False, 'error': 'Channel not found'}), 404
    _save_channels(settings, channels)
    logger.info(f"Notification channel {channel_id} deleted by {request.remote_addr}")
    return jsonify({'ok': True})


@app.route('/api/notifications/channels/<channel_id>/test', methods=['POST'])
@csrf_protect
@login_required
def api_notification_channels_test(channel_id):
    channels = load_settings().get('notification_channels', [])
    channel  = next((c for c in channels if c.get('id') == channel_id), None)
    if channel is None:
        return jsonify({'ok': False, 'error': 'Channel not found'}), 404
    missing = _notify_providers.missing_fields(channel)
    if missing:
        return jsonify({'ok': False, 'error': 'Channel is missing ' + ', '.join(missing)}), 400
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    ok, detail = _notify_providers.send(channel, 'info', 'Traefik Manager',
                                        'Traefik Manager test notification', ts)
    if not ok:
        return jsonify({'ok': False, 'error': detail[:200]})
    return jsonify({'ok': True, 'detail': detail[:200]})


def _tls_opt_sources(server):
    agent = _agent_by_id(server) if server else None
    if agent:
        cfgs = _agent_load_configs(agent)
        return [(name, cfg, name) for name, cfg in cfgs.items()], True
    out = []
    for p in env.CONFIG_PATHS:
        short = os.path.basename(p) if (env.MULTI_CONFIG or ACTIVE_CONFIG_DIR) else ''
        out.append((short, _load_config_display(p), p))
    return out, False


@app.route('/api/tls-options')
@login_required
def api_tls_options_list():
    opts = []
    sources, _is_agent = _tls_opt_sources(request.args.get('server', ''))
    for short, config, p in sources:
        for name, data in (config.get('tls') or {}).get('options', {}).items():
            data = data or {}
            buf = StringIO()
            yaml.dump({'tls': {'options': {name: data}}}, buf)
            ca = data.get('clientAuth') or {}
            opts.append({
                'name': name,
                'configFile': short,
                'configFilePath': p,
                'minVersion': data.get('minVersion', ''),
                'maxVersion': data.get('maxVersion', ''),
                'sniStrict': bool(data.get('sniStrict', False)),
                'cipherSuites': data.get('cipherSuites', []),
                'curvePreferences': data.get('curvePreferences', []),
                'alpnProtocols': data.get('alpnProtocols', []),
                'clientAuthType': ca.get('clientAuthType', ''),
                'clientAuthCAs': ca.get('caFiles', []),
                'yaml': buf.getvalue(),
            })
    return jsonify(opts)


@app.route('/api/tls-options', methods=['POST'])
@csrf_protect
@login_required
def api_tls_options_save():
    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()
    config_file = data.get('configFile', '').strip()
    if not name:
        return jsonify({'ok': False, 'message': 'Profile name is required'}), 400
    server = str(data.get('server') or request.args.get('server', '')).strip()
    agent = _agent_by_id(server) if server else None
    if agent:
        cfgs = _agent_load_configs(agent)
        cfg_name = config_file or (next(iter(cfgs), 'dynamic.yml'))
        config = cfgs.get(cfg_name, {})
        target_path = None
    else:
        target_path = _resolve_config_path(config_file) or env.CONFIG_PATH
        create_backup(target_path)
        config = load_config(target_path)
    opts = {}
    if data.get('minVersion'):
        opts['minVersion'] = data['minVersion']
    if data.get('maxVersion'):
        opts['maxVersion'] = data['maxVersion']
    if data.get('sniStrict'):
        opts['sniStrict'] = True
    ciphers = [c.strip() for c in (data.get('cipherSuites') or []) if c.strip()]
    if ciphers:
        opts['cipherSuites'] = ciphers
    curves = [c.strip() for c in (data.get('curvePreferences') or []) if c.strip()]
    if curves:
        opts['curvePreferences'] = curves
    alpn = [c.strip() for c in (data.get('alpnProtocols') or []) if c.strip()]
    if alpn:
        opts['alpnProtocols'] = alpn
    ca_type = data.get('clientAuthType', '').strip()
    ca_cas = [c.strip() for c in (data.get('clientAuthCAs') or []) if c.strip()]
    if ca_type and ca_type != 'NoClientCert':
        ca_obj = {'clientAuthType': ca_type}
        if ca_cas:
            ca_obj['caFiles'] = ca_cas
        opts['clientAuth'] = ca_obj
    original = str(data.get('originalName') or '').strip()
    if original and original != name:
        (config.get('tls') or {}).get('options', {}).pop(original, None)
        _retarget_tls_option(config, original, name)
    config.setdefault('tls', {}).setdefault('options', {})[name] = opts
    if agent:
        _agent_write_config(agent, cfg_name, config)
    else:
        save_config(_strip_empty_sections(config), target_path)
    if original and original != name:
        _cascade_across_configs(agent, lambda c: _retarget_tls_option(c, original, name),
                                already=cfg_name if agent else target_path)
    add_notification('success', f"TLS profile '{name}' saved")
    return jsonify({'ok': True})


@app.route('/api/tls-options/<name>', methods=['DELETE'])
@csrf_protect
@login_required
def api_tls_options_delete(name):
    config_file = request.args.get('configFile', '').strip()
    server = request.args.get('server', '').strip()
    agent = _agent_by_id(server) if server else None
    if agent:
        cfgs = _agent_load_configs(agent)
        cfg_name = config_file or (next(iter(cfgs), 'dynamic.yml'))
        config = cfgs.get(cfg_name, {})
        target_path = None
    else:
        target_path = _resolve_config_path(config_file) or env.CONFIG_PATH
        config = load_config(target_path)
    tls_opts = (config.get('tls') or {}).get('options', {})
    if name not in tls_opts:
        return jsonify({'ok': False, 'message': 'Profile not found'}), 404
    _tls_all = (list(cfgs.values()) if agent else [load_config(_p) for _p in env.CONFIG_PATHS])
    _tls_users = _tls_option_routers_using(_tls_all, name)
    if _tls_users:
        return jsonify({'ok': False,
                        'message': f"{name} is still used by " + ', '.join(_tls_users[:5])
                                   + (' and others' if len(_tls_users) > 5 else ''),
                        'inUseBy': _tls_users}), 409
    del tls_opts[name]
    if agent:
        _agent_write_config(agent, cfg_name, _strip_empty_sections(config))
    else:
        create_backup(target_path)
        save_config(_strip_empty_sections(config), target_path)
    add_notification('success', f"TLS profile '{name}' deleted")
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
        bname = filename
        target_path = None
        for p in env.CONFIG_PATHS:
            if bname.startswith(os.path.basename(p) + '.'):
                target_path = p
                break
        if target_path is None:
            static_path = _get_static_config_path()
            if static_path and bname.startswith(os.path.basename(static_path) + '.'):
                target_path = static_path
        if target_path is None:
            return jsonify({'error': f'No config file matches {filename!r}'}), 400
        create_backup(target_path)
        shutil.copy2(path, target_path)
        logger.info(f"Restored: {filename} → {target_path}")
        add_notification('warning', f"Backup restored: {filename}", category='backup')
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
        for p in env.CONFIG_PATHS:
            dest = create_backup(p)
            if dest:
                created.append(os.path.basename(dest))
        if created:
            add_notification('success', f"Backup created ({len(created)} file{'s' if len(created) > 1 else ''})",
                             category='backup')
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
            add_notification('success', "Static config backup created", category='backup')
            return jsonify({'success': True, 'name': os.path.basename(dest)})
        return jsonify({'error': 'Static config file not found'}), 400
    except Exception as e:
        logger.exception("Static backup create error")
        return jsonify({'error': str(e)}), 500

@app.route('/api/backup/static/create', methods=['POST'])
@csrf_protect
@login_required
def api_backup_static_create_alias():
    return api_static_backup_create()


@app.route('/api/backup/delete/<filename>', methods=['POST'])
@csrf_protect
@login_required
def api_backup_delete(filename):
    try:
        path = _validated_backup_path(filename)
        if os.path.exists(path):
            os.remove(path)
        add_notification('warning', f"Backup deleted: {filename}", category='backup')
        return jsonify({'success': True})
    except Exception as e:
        logger.exception("Backup delete error")
        return jsonify({'error': str(e)}), 500


def _redact_channels(channels) -> list:
    return [_redact_channel(c) for c in (channels or []) if isinstance(c, dict)]


def _merge_channel_secrets(incoming, existing) -> list:
    by_id = {str(c.get('id', '')): c for c in (existing or []) if isinstance(c, dict)}
    out   = []
    for item in (incoming or []):
        if not isinstance(item, dict):
            continue
        c   = dict(item)
        old = by_id.get(str(c.get('id', '')), {})
        for field in _CHANNEL_SECRETS:
            if str(c.get(field, '')) in ('', '***'):
                c[field] = old.get(field, '')
        if '***' in str(c.get('url', '')):
            c['url'] = old.get('url', '')
        out.append(c)
    return out


@app.route('/api/settings', methods=['GET'])
@login_required
def api_get_settings():
    s = load_settings()

    s.pop('password_hash', None)
    s.pop('oidc_client_secret', None)
    s.pop('webhook_password', None)
    s.pop('crowdsec_api_key', None)
    s.pop('crowdsec_machine_password', None)
    s.pop('traefik_api_password', None)
    s.pop('otp_secret', None)
    s.pop('agents', None)
    s['traefik_api_password_set'] = bool(load_settings().get('traefik_api_password', ''))
    s['auth_enabled']             = _auth_enabled()
    s['oidc_active']            = _oidc_active()
    s['no_auth']                = not _auth_required()
    s['auth_external_ack']      = bool(s.get('auth_external_ack'))
    s['has_password']           = _has_password_set()
    s['auth_env_forced']        = os.environ.get('AUTH_ENABLED', '').strip().lower() in ('false', '0', 'no')
    s['oidc_client_secret_set'] = bool(load_settings().get('oidc_client_secret', ''))
    s['crowdsec_api_key_set']   = bool(_cs_api_key())
    s['crowdsec_machine_password_set'] = bool(_cs_machine_password())
    s['crowdsec_enabled']       = bool(_cs_lapi_url() and (_cs_api_key() or _cs_has_machine()))
    s['git_backup_token_set']   = bool(s.get('git_backup_token', ''))
    s.pop('git_backup_token', None)
    s['notification_channels'] = _redact_channels(s.get('notification_channels'))
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
        webhook_url          = str(data.get('webhook_url', '')).strip()
        webhook_type         = str(data.get('webhook_type', 'discord')).strip()
        webhook_username     = str(data.get('webhook_username', '')).strip()
        webhook_password     = str(data.get('webhook_password', ''))
        crowdsec_lapi_url    = str(data.get('crowdsec_lapi_url', '')).strip()
        crowdsec_api_key     = str(data.get('crowdsec_api_key', ''))
        crowdsec_alert_limit = str(data.get('crowdsec_alert_limit', '')).strip()
        if crowdsec_alert_limit:
            try:
                _lim = int(crowdsec_alert_limit)
                if _lim < 0 or _lim > 100000:
                    return jsonify({'error': 'Alert limit must be between 0 and 100000'}), 400
                crowdsec_alert_limit = str(_lim)
            except ValueError:
                return jsonify({'error': 'Alert limit must be a whole number'}), 400
        crowdsec_machine_id       = str(data.get('crowdsec_machine_id', '')).strip()
        crowdsec_machine_password = str(data.get('crowdsec_machine_password', ''))
        crowdsec_client_cert      = str(data.get('crowdsec_client_cert', '')).strip()
        crowdsec_client_key       = str(data.get('crowdsec_client_key', '')).strip()
        crowdsec_ca_cert          = str(data.get('crowdsec_ca_cert', '')).strip()
        traefik_api_user          = str(data.get('traefik_api_user', '')).strip()
        traefik_api_password      = str(data.get('traefik_api_password', ''))
        git_backup_enabled        = bool(data['git_backup_enabled'])        if 'git_backup_enabled'        in data else None
        git_backup_repo           = str(data['git_backup_repo']).strip()   if 'git_backup_repo'           in data else None
        if git_backup_repo and not _valid_git_url(git_backup_repo):
            return jsonify({'error': 'Invalid git repository URL - must start with https://, http://, ssh:// or git://'}), 400
        git_backup_branch         = (str(data['git_backup_branch']).strip() or 'main') if 'git_backup_branch' in data else None
        git_backup_username       = str(data['git_backup_username']).strip() if 'git_backup_username'      in data else None
        git_backup_token          = str(data.get('git_backup_token', ''))
        git_backup_commit_message = (str(data['git_backup_commit_message']).strip() or 'traefik-manager: {action} at {timestamp}') if 'git_backup_commit_message' in data else None
        git_backup_auto_push      = bool(data['git_backup_auto_push'])     if 'git_backup_auto_push'      in data else None
        backup_keep_count         = max(0, int(data['backup_keep_count'])) if str(data.get('backup_keep_count', '')).strip() != '' else None
        default_theme             = str(data['default_theme']).strip().lower() if 'default_theme' in data else None
        existing = load_settings()
        notification_channels = None
        if 'notification_channels' in data and isinstance(data['notification_channels'], list):
            notification_channels = _merge_channel_secrets(data['notification_channels'],
                                                           existing.get('notification_channels', []))
        if not webhook_password:
            webhook_password = existing.get('webhook_password', '')
        if not crowdsec_api_key:
            crowdsec_api_key = existing.get('crowdsec_api_key', '')
        if not crowdsec_machine_password:
            crowdsec_machine_password = existing.get('crowdsec_machine_password', '')
        if not traefik_api_password:
            traefik_api_password = existing.get('traefik_api_password', '')
        if not git_backup_token:
            git_backup_token = existing.get('git_backup_token', '')
        save_settings(domains, cert_resolver, traefik_api_url,
                      auth_enabled=existing['auth_enabled'],
                      password_hash=existing['password_hash'],
                      visible_tabs=existing['visible_tabs'],
                      acme_json_path=acme_json_path,
                      access_log_path=access_log_path,
                      static_config_path=static_config_path,
                      webhook_url=webhook_url,
                      webhook_type=webhook_type,
                      webhook_username=webhook_username,
                      webhook_password=webhook_password,
                      crowdsec_lapi_url=crowdsec_lapi_url,
                      crowdsec_api_key=crowdsec_api_key,
                      crowdsec_alert_limit=crowdsec_alert_limit,
                      crowdsec_machine_id=crowdsec_machine_id,
                      crowdsec_machine_password=crowdsec_machine_password,
                      crowdsec_client_cert=crowdsec_client_cert,
                      crowdsec_client_key=crowdsec_client_key,
                      crowdsec_ca_cert=crowdsec_ca_cert,
                      traefik_api_user=traefik_api_user,
                      traefik_api_password=traefik_api_password,
                      git_backup_enabled=git_backup_enabled,
                      git_backup_repo=git_backup_repo,
                      git_backup_branch=git_backup_branch,
                      git_backup_username=git_backup_username,
                      git_backup_token=git_backup_token,
                      git_backup_commit_message=git_backup_commit_message,
                      git_backup_auto_push=git_backup_auto_push,
                      backup_keep_count=backup_keep_count,
                      notification_channels=notification_channels,
                      default_theme=default_theme)
        result = load_settings()
        for _k in ('password_hash', 'oidc_client_secret', 'crowdsec_api_key',
                   'crowdsec_machine_password', 'traefik_api_password', 'git_backup_token',
                   'webhook_password', 'otp_secret', 'agents'):
            result.pop(_k, None)
        result['notification_channels'] = _redact_channels(result.get('notification_channels'))
        return jsonify({'success': True, 'settings': result})
    except Exception as e:
        logger.exception("Settings save error")
        return jsonify({'error': str(e)}), 500


@app.route('/api/settings/webhook-test', methods=['POST'])
@csrf_protect
@login_required
def api_webhook_test():
    data     = request.get_json(silent=True) or {}
    url      = str(data.get('url', '')).strip()
    wtype    = str(data.get('webhook_type', 'discord')).strip()
    username = str(data.get('username', '')).strip()
    password = str(data.get('password', ''))
    if not url or not url.startswith(('http://', 'https://')):
        return jsonify({'ok': False, 'error': 'Invalid URL'}), 400
    if not _ssrf_ok(url):
        return jsonify({'ok': False, 'error': 'Target address not allowed'}), 400
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        _send_webhook(url, wtype, 'info', 'Traefik Manager webhook test', ts, username, password)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)[:120]})

@app.route('/api/settings/test-connection', methods=['POST'])
@csrf_protect
@login_required
def api_settings_test_connection():
    data    = request.get_json(silent=True) or {}
    raw_url = str(data.get('url', '')).strip()
    url     = _safe_api_url(raw_url)
    if not url:
        return jsonify({'ok': False, 'error': 'Invalid URL'}), 400
    if not _ssrf_ok(url):
        return jsonify({'ok': False, 'error': 'Target address not allowed'}), 400
    u = str(data.get('user', '')).strip()
    p = str(data.get('password', '')).strip()
    if not p:
        stored   = load_settings()
        if not u:
            u = stored.get('traefik_api_user', '')
        p = stored.get('traefik_api_password', '')
    auth = (u, p) if u and p else None
    logger.info(f"Connection test to {url!r} by {request.remote_addr}")
    try:
        resp = requests.get(f"{url}/api/version", timeout=4, auth=auth, verify=_traefik_verify())
        if resp.status_code == 200:
            info = resp.json()
            return jsonify({'ok': True, 'version': info.get('Version', '?')})
        if resp.status_code in (401, 403):
            return jsonify({'ok': False, 'error': f'HTTP {resp.status_code} - check the API username and password'})
        return jsonify({'ok': False, 'error': f'HTTP {resp.status_code} from {url}/api/version'})
    except requests.exceptions.SSLError as e:
        return jsonify({'ok': False, 'error': f'TLS verification failed - the API certificate is not trusted. Mount your CA into /etc/ssl/certs/ca-certificates.crt or set TRAEFIK_INSECURE_SKIP_VERIFY=true. ({str(e)[:120]})'})
    except requests.exceptions.Timeout:
        return jsonify({'ok': False, 'error': 'Connection timed out - the API URL may be unreachable from the container'})
    except requests.exceptions.ConnectionError as e:
        return jsonify({'ok': False, 'error': f'Connection error - check the URL and network. ({str(e)[:120]})'})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)[:160]})


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


@app.route('/api/settings/ui', methods=['GET', 'POST'])
@csrf_protect
@login_required
def api_ui_prefs():
    existing = load_settings()
    if request.method == 'GET':
        return jsonify({'ok': True, 'ui_prefs': existing.get('ui_prefs', {})})
    data = request.get_json(silent=True) or {}
    incoming = data.get('ui_prefs', data)
    if not isinstance(incoming, dict):
        return jsonify({'ok': False, 'message': 'ui_prefs must be an object'}), 400
    merged = dict(existing.get('ui_prefs', {}))
    merged.update(_settings.sanitize_ui_prefs(incoming))
    save_settings(
        domains=existing['domains'],
        cert_resolver=existing['cert_resolver'],
        traefik_api_url=existing['traefik_api_url'],
        auth_enabled=existing['auth_enabled'],
        password_hash=existing['password_hash'],
        visible_tabs=existing['visible_tabs'],
        ui_prefs=merged,
    )
    return jsonify({'ok': True, 'ui_prefs': merged})


@app.route('/api/settings/theme', methods=['POST'])
@csrf_protect
@login_required
def api_save_theme():
    try:
        data  = request.get_json(silent=True) or {}
        theme = str(data.get('default_theme', '')).strip().lower()
        if theme not in ('dark', 'light', 'system'):
            return jsonify({'success': False, 'error': 'Invalid theme'}), 400
        existing = load_settings()
        save_settings(
            domains=existing['domains'],
            cert_resolver=existing['cert_resolver'],
            traefik_api_url=existing['traefik_api_url'],
            auth_enabled=existing['auth_enabled'],
            password_hash=existing['password_hash'],
            visible_tabs=existing['visible_tabs'],
            default_theme=theme,
        )
        return jsonify({'success': True, 'default_theme': theme})
    except Exception:
        logger.exception("Theme save error")
        return jsonify({'success': False, 'error': 'Save failed'}), 500


@app.route('/api/settings/geoip', methods=['POST'])
@csrf_protect
@login_required
def api_save_geoip():
    try:
        data     = request.get_json(silent=True) or {}
        existing = load_settings()
        enabled  = bool(data['geoip_enabled']) if 'geoip_enabled' in data else existing.get('geoip_enabled', False)
        db_path  = str(data.get('geoip_db_path', existing.get('geoip_db_path', ''))).strip()
        save_settings(
            domains=existing['domains'],
            cert_resolver=existing['cert_resolver'],
            traefik_api_url=existing['traefik_api_url'],
            auth_enabled=existing['auth_enabled'],
            password_hash=existing['password_hash'],
            visible_tabs=existing['visible_tabs'],
            geoip_enabled=enabled,
            geoip_db_path=db_path,
        )
        return jsonify({'success': True, 'status': _geoip_status()})
    except Exception:
        logger.exception("GeoIP settings save error")
        return jsonify({'success': False, 'error': 'Save failed'}), 500


_CGNAT_NETWORK = ipaddress.ip_network('100.64.0.0/10')

def _classify_ip(ip: str) -> str:
    try:
        addr = ipaddress.ip_address((ip or '').strip())
    except ValueError:
        return 'unknown'
    if addr.is_loopback:
        return 'loopback'
    if addr.is_link_local:
        return 'link-local'
    if addr.version == 4 and addr in _CGNAT_NETWORK:
        return 'cgnat'
    if addr.is_private:
        return 'private'
    return 'public'


@app.route('/api/diagnostics/client-ip')
@login_required
def api_client_ip_diagnostic():
    orig        = request.environ.get('werkzeug.proxy_fix.orig') or {}
    socket_peer = orig.get('REMOTE_ADDR', '') or ''
    headers     = {
        'X-Forwarded-For':   request.headers.get('X-Forwarded-For', ''),
        'X-Real-IP':         request.headers.get('X-Real-IP', ''),
        'CF-Connecting-IP':  request.headers.get('CF-Connecting-IP', ''),
        'X-Forwarded-Proto': request.headers.get('X-Forwarded-Proto', ''),
        'X-Forwarded-Host':  request.headers.get('X-Forwarded-Host', ''),
    }
    xff_chain = [p.strip() for p in headers['X-Forwarded-For'].split(',') if p.strip()]
    effective = request.remote_addr or ''
    seen      = [ip for ip in [effective, socket_peer, *xff_chain] if ip]
    classes   = {ip: _classify_ip(ip) for ip in seen}
    return jsonify({
        'effective_ip':        effective,
        'effective_class':     _classify_ip(effective),
        'socket_peer':         socket_peer,
        'socket_peer_class':   _classify_ip(socket_peer),
        'headers':             headers,
        'forwarded_for_chain': xff_chain,
        'proxy_hops':          PROXY_FIX_HOPS,
        'classes':             classes,
    })


@app.route('/api/settings/backup-retention', methods=['POST'])
@csrf_protect
@login_required
def api_save_backup_retention():
    try:
        data     = request.get_json() or {}
        keep     = max(0, int(data.get('backup_keep_count', 0)))
        existing = load_settings()
        save_settings(
            domains=existing['domains'],
            cert_resolver=existing['cert_resolver'],
            traefik_api_url=existing['traefik_api_url'],
            auth_enabled=existing['auth_enabled'],
            password_hash=existing['password_hash'],
            visible_tabs=existing['visible_tabs'],
            backup_keep_count=keep,
        )
        return jsonify({'success': True, 'backup_keep_count': keep})
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid keep count'}), 400
    except Exception as e:
        logger.exception("Backup retention save error")
        return jsonify({'error': str(e)}), 500


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


def _file_template_map(path):
    if path and os.path.exists(path):
        with open(path, 'r') as f:
            _, mapping = _sanitize_go_templates(f.read())
        return mapping
    return {}


def _parse_backends_json(raw):
    import json as _json
    if not raw:
        return None
    try:
        data = _json.loads(raw)
    except (ValueError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def _clean_priority(value):
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return n if n != 0 else None


def _clean_duration(value):
    v = str(value or '').strip()
    if not v:
        return ''
    if v.isdigit():
        return v + 's'
    return v if re.match(r'^\d+(ms|s|m|h)$', v) else ''


def _backend_servers(rows, key, scheme_default='http'):
    servers = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        host = str(row.get('host') or '').strip()
        if not host:
            continue
        port = str(row.get('port') or '').strip()
        if key == 'url':
            if host.startswith('http://') or host.startswith('https://'):
                servers.append({'url': host})
            else:
                scheme = str(row.get('scheme') or scheme_default).strip() or scheme_default
                servers.append({'url': f"{scheme}://{host}:{port}" if port else f"{scheme}://{host}"})
        else:
            servers.append({key: f"{host}:{port}" if port else host})
    return servers


def _sticky_block(sticky):
    if not isinstance(sticky, dict) or not sticky.get('enabled'):
        return None
    cookie = {}
    name = str(sticky.get('cookieName') or '').strip()
    if name:
        cookie['name'] = name
    if sticky.get('secure'):
        cookie['secure'] = True
    if sticky.get('httpOnly'):
        cookie['httpOnly'] = True
    return {'cookie': cookie}


def _healthcheck_block(hc):
    if not isinstance(hc, dict) or not hc.get('enabled'):
        return None
    path = str(hc.get('path') or '').strip()
    if not path:
        return None
    block = {'path': path}
    for field in ('interval', 'timeout'):
        val = _clean_duration(hc.get(field))
        if val:
            block[field] = val
    return block


def _streaming_forwarding_timeouts() -> dict:
    return {'dialTimeout': '30s', 'responseHeaderTimeout': '0s', 'idleConnTimeout': '90s'}


def _headers_toggles_from_form(form) -> dict:
    perms = {}
    for feat in HEADERS_PRESET_FEATURES:
        val = form.get(f'hp_perm_{feat}', '')
        perms[feat] = val if val in ('self', 'all', 'block') else 'block'
    return {
        'perms': perms,
        'hsts': form.get('hp_hsts') == 'true',
        'nosniff': form.get('hp_nosniff') == 'true',
        'frameDeny': form.get('hp_frameDeny') == 'true',
        'referrer': (form.get('hp_referrer') or '').strip(),
    }


def _composite_children(svc_def) -> list:
    if not isinstance(svc_def, dict):
        return []
    names = []
    for key in ('weighted', 'highestRandomWeight'):
        block = svc_def.get(key)
        if isinstance(block, dict):
            for child in (block.get('services') or []):
                if isinstance(child, dict):
                    names.append(child.get('name', ''))
    mirroring = svc_def.get('mirroring')
    if isinstance(mirroring, dict):
        names.append(mirroring.get('service', ''))
        for mirror in (mirroring.get('mirrors') or []):
            if isinstance(mirror, dict):
                names.append(mirror.get('name', ''))
    failover = svc_def.get('failover')
    if isinstance(failover, dict):
        names.append(failover.get('service', ''))
        names.append(failover.get('fallback', ''))
    return [n for n in names if isinstance(n, str) and n]


def _service_in_disabled_snapshots(target: str, exclude_router: str) -> bool:
    try:
        disabled = load_settings().get('disabled_routes', {}) or {}
    except Exception:
        return False
    for key, snap in disabled.items():
        if not isinstance(snap, dict):
            continue
        if str(key).split('::')[-1] == exclude_router:
            continue
        router = snap.get('router')
        if isinstance(router, dict) and _svc_key(router.get('service', '')) == target:
            return True
        for child in _composite_children(snap.get('service')):
            if _svc_key(child) == target:
                return True
    return False


def _service_shared(config: dict, svc_name: str, exclude_router: str) -> bool:
    target = _svc_key(svc_name)
    for sec in ('http', 'tcp', 'udp'):
        sec_cfg = config.get(sec) or {}
        routers = sec_cfg.get('routers') or {}
        for rn, rd in routers.items():
            if rn == exclude_router or not isinstance(rd, dict):
                continue
            if _svc_key(rd.get('service', '')) == target:
                return True
        for sn, sd in (sec_cfg.get('services') or {}).items():
            if _svc_key(sn) == target:
                continue
            for child in _composite_children(sd):
                if _svc_key(child) == target:
                    return True
    return _service_in_disabled_snapshots(target, exclude_router)


def _disabled_key(disabled, full_id, plain_id, prefix=''):
    for key in (full_id, plain_id, prefix + plain_id):
        if key and key in disabled:
            return key
    for key in disabled:
        if prefix and not key.startswith(prefix):
            continue
        if key.split('::')[-1] == plain_id:
            return key
    return None


def _save_disabled_routes(settings, disabled):
    save_settings(
        domains=settings['domains'],
        cert_resolver=settings['cert_resolver'],
        traefik_api_url=settings['traefik_api_url'],
        auth_enabled=settings['auth_enabled'],
        password_hash=settings['password_hash'],
        visible_tabs=settings['visible_tabs'],
        disabled_routes=disabled,
    )


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
        svc_name    = _svc_key(router.get('service', rname))
        svc         = saved.get('service', {})
        cf          = saved.get('configFile', '')
        svc_cf      = saved.get('serviceConfigFile', cf)
        def _resolve_or_fallback(f):
            p = _resolve_config_path(f)
            if not p and f:
                safe = f if f.endswith(('.yml', '.yaml')) else f + '.yml'
                candidate = os.path.join(os.path.dirname(env.CONFIG_PATH) or '.', safe)
                p = candidate if _is_safe_path(candidate) else env.CONFIG_PATH
            return p or env.CONFIG_PATH
        target_path = _resolve_or_fallback(cf)
        config      = load_config(target_path)
        config.setdefault(proto, {}).setdefault('routers', {})[rname] = router
        if svc_cf == cf or not svc_cf:
            if svc:
                config.setdefault(proto, {}).setdefault('services', {})[svc_name] = svc
            create_backup(target_path)
            save_config(_strip_empty_sections(config), target_path)
        else:
            create_backup(target_path)
            save_config(_strip_empty_sections(config), target_path)
            svc_path   = _resolve_or_fallback(svc_cf)
            svc_config = load_config(svc_path)
            if svc:
                svc_config.setdefault(proto, {}).setdefault('services', {})[svc_name] = svc
            create_backup(svc_path)
            save_config(_strip_empty_sections(svc_config), svc_path)
    else:
        proto        = None
        router       = None
        svc_name     = None
        svc          = None
        target_path  = None
        svc_path     = None
        svc_config   = None
        cf_prefix   = route_id.split('::', 1)[0] if '::' in route_id else ''
        _pref_path  = _resolve_config_path(cf_prefix) if cf_prefix else None
        search_paths = [_pref_path] if _pref_path else env.CONFIG_PATHS
        for p in search_paths:
            config = load_config(p)
            for prot in ('http', 'tcp', 'udp'):
                routers = config.get(prot, {}).get('routers', {})
                if rname in routers:
                    proto       = prot
                    router      = dict(routers.pop(rname))
                    svc_name    = _svc_key(router.get('service', rname))
                    target_path = p
                    svc_config  = config
                    break
            if proto:
                break
        if proto is None:
            return
        if _service_shared(svc_config, svc_name, rname):
            svc = dict(svc_config.get(proto, {}).get('services', {}).get(svc_name, {}))
        else:
            svc = dict(svc_config.get(proto, {}).get('services', {}).pop(svc_name, {}))
        if not svc:
            for p in env.CONFIG_PATHS:
                if p == target_path:
                    continue
                other = load_config(p)
                if svc_name in other.get(proto, {}).get('services', {}):
                    svc      = dict(other[proto]['services'].pop(svc_name))
                    svc_path = p
                    svc      = _restore_go_templates(svc, _file_template_map(p))
                    other_stripped = _strip_empty_sections(other)
                    create_backup(p)
                    save_config(other_stripped, p)
                    break
        _target_map = _file_template_map(target_path)
        router = _restore_go_templates(router, _target_map)
        if svc_path is None:
            svc = _restore_go_templates(svc, _target_map)
        cf = os.path.basename(target_path) if (env.MULTI_CONFIG or ACTIVE_CONFIG_DIR) else ''
        svc_cf = os.path.basename(svc_path) if svc_path and (env.MULTI_CONFIG or ACTIVE_CONFIG_DIR) else cf
        disabled[route_id] = {'protocol': proto, 'router': router, 'service': svc, 'configFile': cf, 'serviceConfigFile': svc_cf}
        create_backup(target_path)
        save_config(_strip_empty_sections(svc_config), target_path)

    save_settings(
        domains=settings['domains'],
        cert_resolver=settings['cert_resolver'],
        traefik_api_url=settings['traefik_api_url'],
        auth_enabled=settings['auth_enabled'],
        password_hash=settings['password_hash'],
        visible_tabs=settings['visible_tabs'],
        disabled_routes=disabled,
    )


def _self_route_service_name() -> str:
    try:
        return str((load_settings().get('self_route') or {}).get('router_name')
                   or 'traefik-manager')
    except Exception:
        return 'traefik-manager'


def _collect_file_services(configs):
    out = {'http': set(), 'tcp': set(), 'udp': set()}
    skip = _self_route_service_name()
    for cfg in configs:
        for sec in out:
            out[sec].update(k for k in ((cfg.get(sec) or {}).get('services') or {})
                            if isinstance(k, str) and k and k != skip)
    return {sec: sorted(names) for sec, names in out.items()}


@app.route('/api/routes')
@login_required
def api_routes():
    apps, middlewares = _build_all_apps(include_external=False)
    apps = [a for a in apps if not (a.get('service_name') or '').endswith('@internal')]
    return jsonify({'apps': apps, 'middlewares': middlewares,
                    'configErrors': _get_config_parse_errors(),
                    'services': _collect_file_services(load_config(_p) for _p in env.CONFIG_PATHS)})


@app.route('/api/routes/all')
@login_required
def api_routes_all():
    apps, middlewares = _build_all_apps(include_external=True, include_internal=True)
    services = _collect_file_services(load_config(_p) for _p in env.CONFIG_PATHS)
    return jsonify({'apps': apps, 'middlewares': middlewares, 'services': services})


@app.route('/api/configs')
@login_required
def api_configs():
    return jsonify({
        'files': [{'label': os.path.basename(p), 'path': p} for p in env.CONFIG_PATHS],
        'configDirSet': bool(ACTIVE_CONFIG_DIR),
    })


def _read_groups_file():
    if not os.path.exists(GROUPS_CONFIG_FILE):
        return {}
    try:
        _y = SafeYAML(typ='safe')
        with open(GROUPS_CONFIG_FILE, 'r') as f:
            return _y.load(f) or {}
    except Exception:
        logger.exception("Failed to read dashboard config")
        return {}


def _groups_scope_key(server):
    s = str(server or '').strip()
    return s if s and s != 'host' else ''


def _read_groups_config(server=''):
    data = _read_groups_file()
    key = _groups_scope_key(server)
    if key:
        data = ((data.get('servers') or {}).get(key)) or {}
    return {
        'custom_groups':   list(data.get('custom_groups', []) or []),
        'route_overrides': _sanitize_route_overrides(data.get('route_overrides', {}) or {}),
    }

def _sanitize_route_overrides(overrides):
    out = {}
    for rid, ov in (overrides or {}).items():
        if not isinstance(ov, dict):
            continue
        ov = dict(ov)
        url = str(ov.get('url') or '').strip()
        if not url or not url.lower().startswith(('http://', 'https://')):
            ov.pop('url', None)
        else:
            ov['url'] = url
        out[rid] = ov
    return out


def _write_groups_config(data, server=''):
    doc = _read_groups_file()
    scope = {
        'custom_groups':   list(data.get('custom_groups', []) or []),
        'route_overrides': _sanitize_route_overrides(data.get('route_overrides', {})),
    }
    key = _groups_scope_key(server)
    if key:
        servers = dict(doc.get('servers') or {})
        servers[key] = scope
        doc['servers'] = servers
    else:
        doc['custom_groups'] = scope['custom_groups']
        doc['route_overrides'] = scope['route_overrides']
    _y = SafeYAML(typ='safe')
    with open(GROUPS_CONFIG_FILE, 'w') as f:
        _y.dump(doc, f)

@app.route('/api/dashboard/config', methods=['GET'])
@login_required
def dashboard_config_get():
    cfg = _read_groups_config(request.args.get('server', ''))
    sr  = load_settings().get('self_route', {})
    cfg['tm_route_name'] = sr.get('router_name', 'traefik-manager') or 'traefik-manager'
    return jsonify(cfg)

@app.route('/api/dashboard/config', methods=['POST'])
@login_required
@csrf_protect
def dashboard_config_post():
    data = request.get_json() or {}
    _write_groups_config(data, data.get('server', '') or request.args.get('server', ''))
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


def _toggle_route_agent(agent: dict, agent_id: str, route_id: str, enable: bool):
    settings = load_settings()
    disabled = dict(settings.get('disabled_routes', {}))
    rname    = route_id.split('::', 1)[1] if '::' in route_id else route_id
    store_key = f"agent_{agent_id}::{route_id}"
    if enable:
        if store_key not in disabled:
            return
        saved    = disabled.pop(store_key)
        proto    = saved.get('protocol', 'http')
        router   = saved.get('router', {})
        svc_name = _svc_key(router.get('service', rname))
        svc      = saved.get('service', {})
        cf       = saved.get('configFile', 'dynamic.yml')
        all_cfgs = _agent_load_configs(agent)
        config   = all_cfgs.get(cf, {})
        config.setdefault(proto, {}).setdefault('routers', {})[rname] = router
        if svc:
            config.setdefault(proto, {}).setdefault('services', {})[svc_name] = svc
        _agent_write_config(agent, cf, config)
    else:
        all_cfgs = _agent_load_configs(agent)
        cf_prefix = route_id.split('::', 1)[0] if '::' in route_id else ''
        cfg_items = [(cf_prefix, all_cfgs[cf_prefix])] if cf_prefix in all_cfgs else list(all_cfgs.items())
        for fname, config in cfg_items:
            for prot in ('http', 'tcp', 'udp'):
                routers = config.get(prot, {}).get('routers', {})
                if rname in routers:
                    router   = dict(routers.pop(rname))
                    svc_name = _svc_key(router.get('service', rname))
                    if _service_shared(config, svc_name, rname):
                        svc = dict(config.get(prot, {}).get('services', {}).get(svc_name, {}))
                    else:
                        svc = dict(config.get(prot, {}).get('services', {}).pop(svc_name, {}))
                    disabled[store_key] = {'protocol': prot, 'router': router, 'service': svc, 'configFile': fname}
                    _agent_write_config(agent, fname, config)
                    break
            else:
                continue
            break
    save_settings(
        domains=settings['domains'], cert_resolver=settings['cert_resolver'],
        traefik_api_url=settings['traefik_api_url'], auth_enabled=settings['auth_enabled'],
        password_hash=settings['password_hash'], visible_tabs=settings['visible_tabs'],
        disabled_routes=disabled,
    )


@app.route('/api/routes/<path:route_id>/toggle', methods=['POST'])
@csrf_protect
@login_required
def api_toggle_route(route_id):
    body     = request.get_json(force=True, silent=True) or {}
    enable   = body.get('enable', True)
    agent_id = body.get('agent_id', '').strip()
    agent    = _agent_by_id(agent_id) if agent_id else None
    try:
        if agent:
            _toggle_route_agent(agent, agent_id, route_id, bool(enable))
            threading.Thread(target=lambda: _git_push_agent_if_enabled(agent, 'route toggle'), daemon=True).start()
        else:
            _toggle_route(route_id, bool(enable))
            threading.Thread(target=lambda: _git_push_if_enabled('route toggle'), daemon=True).start()
        return jsonify({'ok': True})
    except Exception as e:
        logger.error(f"Toggle route error: {e}")
        return jsonify({'ok': False, 'message': str(e)}), 500


@app.route('/api/routes/<path:route_id>/raw', methods=['GET'])
@login_required
def api_route_raw_get(route_id):
    rname = route_id.split('::', 1)[1] if '::' in route_id else route_id
    cf    = route_id.split('::', 1)[0] if '::' in route_id else ''

    target_path   = _resolve_config_path(cf) if cf else None
    paths_to_scan = [target_path] if target_path else env.CONFIG_PATHS

    for p in paths_to_scan:
        config = load_config(p)
        for proto in ('http', 'tcp', 'udp'):
            routers = config.get(proto, {}).get('routers', {})
            if rname in routers:
                router   = routers[rname]
                svc_name = router.get('service', rname)
                svc_key  = _svc_key(svc_name)
                svc      = config.get(proto, {}).get('services', {}).get(svc_key)
                out      = {proto: {'routers': {rname: dict(router)}}}
                if svc is not None:
                    out[proto]['services'] = {svc_name: dict(svc)}
                stream = StringIO()
                yaml.dump(out, stream)
                raw = stream.getvalue()
                with open(p, 'r') as f:
                    _, template_map = _sanitize_go_templates(f.read())
                for placeholder, original in template_map.items():
                    raw = raw.replace(placeholder, original)
                return jsonify({'raw': raw, 'configFile': os.path.basename(p), 'proto': proto})

    return jsonify({'error': 'Route not found'}), 404


@app.route('/api/routes/<path:route_id>/raw', methods=['POST'])
@csrf_protect
@login_required
def api_route_raw_save(route_id):
    body    = request.get_json(force=True, silent=True) or {}
    content = body.get('content', '')
    if not content.strip():
        return jsonify({'ok': False, 'error': 'No content'}), 400

    rname = route_id.split('::', 1)[1] if '::' in route_id else route_id
    cf    = route_id.split('::', 1)[0] if '::' in route_id else ''

    user_map     = {}
    user_counter = [0]
    def _replace_user(m):
        key = f'__TM_USER_{user_counter[0]}__'
        user_map[key] = m.group(0)
        user_counter[0] += 1
        return key
    sanitized_user = re.sub(r'\{\{[^}]*\}\}', _replace_user, content)

    try:
        new_data = yaml.load(sanitized_user)
        if not isinstance(new_data, dict):
            raise ValueError("Expected a YAML mapping")
    except Exception as e:
        return jsonify({'ok': False, 'error': f'Invalid YAML: {e}'}), 400

    target_path = _resolve_config_path(cf) if cf else None
    if not target_path:
        for p in env.CONFIG_PATHS:
            cfg = load_config(p)
            for proto in ('http', 'tcp', 'udp'):
                if rname in cfg.get(proto, {}).get('routers', {}):
                    target_path = p
                    break
            if target_path:
                break
    if not target_path:
        return jsonify({'ok': False, 'error': 'Route not found'}), 404

    config = load_config(target_path)

    for proto in ('http', 'tcp', 'udp'):
        proto_cfg  = config.get(proto, {})
        old_router = proto_cfg.get('routers', {}).pop(rname, None)
        if old_router:
            old_svc = _svc_key(old_router.get('service', rname))
            proto_cfg.get('services', {}).pop(old_svc, None)

    for proto in ('http', 'tcp', 'udp'):
        new_proto = new_data.get(proto, {})
        if not new_proto:
            continue
        section = config.setdefault(proto, {})
        new_routers  = new_proto.get('routers', {})
        new_services = new_proto.get('services', {})
        if new_routers:
            section.setdefault('routers', {}).update(new_routers)
        if new_services:
            section.setdefault('services', {}).update(new_services)

    try:
        create_backup(target_path)
        file_map = {}
        if os.path.exists(target_path):
            with open(target_path, 'r') as f:
                _, file_map = _sanitize_go_templates(f.read())
        combined_map = {**file_map, **user_map}
        stream = StringIO()
        yaml.dump(_strip_empty_sections(config), stream)
        yaml_content = stream.getvalue()
        for placeholder, original in combined_map.items():
            yaml_content = yaml_content.replace(placeholder, original)
        tmp = f"{target_path}.tmp.{os.getpid()}.{threading.get_ident()}"
        try:
            with open(tmp, 'w') as f:
                f.write(yaml_content)
                f.flush()
                os.fsync(f.fileno())
            _cfg._replace_or_copy(tmp, target_path)
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass
        logger.info(f"Route '{rname}' raw config saved: {target_path}")
        add_notification('success', f"Route '{rname}' updated")
        threading.Thread(target=lambda: _git_push_if_enabled('route raw save'), daemon=True).start()
        return jsonify({'ok': True})
    except Exception as e:
        logger.exception("Route raw save error")
        return jsonify({'ok': False, 'error': str(e)}), 500


def _static_cert_resolvers():
    path = _get_static_config_path()
    if not path or not os.path.exists(path):
        return []
    try:
        with open(path, 'r') as f:
            data = _yaml_safe.load(f) or {}
        resolvers = data.get('certificatesResolvers') or {}
        if isinstance(resolvers, dict):
            return [str(k).strip() for k in resolvers if str(k).strip()]
    except Exception:
        logger.debug("Failed to read certificatesResolvers from static config", exc_info=True)
    return []

@app.route('/')
@login_required
def index():
    settings    = load_settings()
    apps, middlewares = _build_all_apps(include_external=False)
    apps = [a for a in apps if not (a.get('service_name') or '').endswith('@internal')]
    auth_on    = _auth_required()
    _ack       = bool(load_settings().get('auth_external_ack'))
    no_auth    = not _auth_required() and not _ack
    login_time = session.get('login_time', '')
    config_paths_list = [{'label': os.path.basename(p), 'path': p} for p in env.CONFIG_PATHS]
    cert_resolvers    = [r.strip() for r in settings['cert_resolver'].split(',') if r.strip()]
    for r in _static_cert_resolvers():
        if r not in cert_resolvers:
            cert_resolvers.append(r)

    return render_template('index.html', apps=apps, domains=settings['domains'],
                           middlewares=middlewares, settings=settings,
                           auth_enabled=auth_on, no_auth=no_auth, login_time=login_time,
                           multi_config=env.MULTI_CONFIG,
                           config_paths_list=config_paths_list,
                           config_dir_set=bool(ACTIVE_CONFIG_DIR),
                           cert_resolvers=cert_resolvers,
                           crowdsec_enabled=bool(_cs_lapi_url() and (_cs_api_key() or _cs_has_machine())),
                           ui_prefs=settings.get('ui_prefs', {}))


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
        middlewares_in = request.form.get('middlewares', '').strip()
        protocol       = request.form.get('protocol', 'http').strip().lower()
        is_edit        = request.form.get('isEdit') == 'true'
        original_id    = request.form.get('originalId', '')
        tcp_rule       = request.form.get('tcpRule', '').strip()
        http_rule      = request.form.get('httpRule', '').strip()
        scheme         = request.form.get('scheme', 'http').strip().lower()
        pass_host      = request.form.get('passHostHeader') == 'true'
        _all_eps       = request.form.getlist('entryPoints')
        http_eps       = [ep.strip() for ep in (_all_eps[0] if _all_eps else 'https').split(',') if ep.strip()] or ['https']
        tcp_eps        = [ep.strip() for ep in (_all_eps[1] if len(_all_eps) > 1 else '').split(',') if ep.strip()]
        _all_ips       = request.form.getlist('targetIp')
        _all_ports     = request.form.getlist('targetPort')
        if protocol == 'tcp':
            target_ip   = (_all_ips[1]   if len(_all_ips)   > 1 else '').strip()
            target_port = (_all_ports[1] if len(_all_ports) > 1 else '').strip()
        elif protocol == 'udp':
            target_ip   = (_all_ips[2]   if len(_all_ips)   > 2 else '').strip()
            target_port = (_all_ports[2] if len(_all_ports) > 2 else '').strip()
        else:
            target_ip   = (_all_ips[0]   if _all_ips   else '').strip()
            target_port = (_all_ports[0] if _all_ports else '').strip()
        resolvers      = [r.strip() for r in settings['cert_resolver'].split(',') if r.strip()]
        _all_resolvers    = request.form.getlist('certResolver')
        cert_resolver_raw = (_all_resolvers[0] if _all_resolvers else '').strip()
        no_tls            = cert_resolver_raw == '__disabled__'
        cert_resolver     = '' if (cert_resolver_raw in ('__none__', 'none', '__disabled__')) else (cert_resolver_raw or (resolvers[0] if resolvers else ''))
        use_tls_tcp       = request.form.get('useTls') == 'true'
        tls_passthrough   = request.form.get('tlsPassthrough') == 'true'
        mws_tcp_raw       = request.form.get('middlewaresTcp')
        tcp_cert_raw      = (_all_resolvers[1] if len(_all_resolvers) > 1 else '').strip()
        tcp_cert_resolver = '' if (tcp_cert_raw in ('__none__', 'none')) else (tcp_cert_raw or (resolvers[0] if resolvers else ''))
        config_file_raw = request.form.get('configFile', '').strip()
        agent_id        = request.form.get('agent_id', '').strip()
        agent           = _agent_by_id(agent_id) if agent_id else None
        target_path     = None if agent else (_resolve_config_path(config_file_raw) or env.CONFIG_PATH)
        cfg_filename    = config_file_raw or 'dynamic.yml'

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

        _backends_field = {'http': 'backendsJsonHttp', 'tcp': 'backendsJsonTcp',
                           'udp': 'backendsJsonUdp'}[protocol]
        _has_backends_json = bool((_parse_backends_json(request.form.get(_backends_field)) or {}).get('servers'))
        service_ref         = request.form.get('serviceRef', '').strip()
        _service_ref_posted = 'serviceRef' in request.form
        if _service_ref_posted and not service_ref:
            _msg = "Select a service to reference, or switch the backend to Manual."
            if fetch:
                return jsonify({'ok': False, 'message': _msg}), 400
            flash(_msg, "error")
            return redirect(url_for('index'))
        _existing_is_composite = _router_resolves_to_composite(
            request.form.get('originalName', '').strip() or svc_name, agent)
        if not target_ip and not _has_backends_json and not service_ref \
                and not _existing_is_composite:
            _msg = (f"A backend host is required for {protocol.upper()} routes. "
                    f"Send targetIp (repeated per protocol, index "
                    f"{ {'http': 0, 'tcp': 1, 'udp': 2}[protocol] }) or {_backends_field}.")
            if fetch:
                return jsonify({'ok': False, 'message': _msg}), 400
            flash(_msg, "error")
            return redirect(url_for('index'))

        if protocol in ('tcp', 'udp') and not _has_backends_json and not target_port and not service_ref:
            _host, _sep, _tail = target_ip.rpartition(':')
            if _sep and _tail.isdigit() and (':' not in _host or _host.endswith(']')):
                target_ip, target_port = _host, _tail
            else:
                _msg = (f"A backend port is required for {protocol.upper()} routes. "
                        f"Send targetPort (repeated per protocol, index "
                        f"{ {'tcp': 1, 'udp': 2}[protocol] }) or {_backends_field}.")
                if fetch:
                    return jsonify({'ok': False, 'message': _msg}), 400
                flash(_msg, "error")
                return redirect(url_for('index'))

        router_name  = svc_name
        service_name = f"{svc_name}-service"
        if agent:
            config = _agent_load_configs(agent).get(cfg_filename, {})
        else:
            create_backup(target_path)
            config = load_config(target_path)

        orig_parts = original_id.split('::', 1)
        plain_original_id = orig_parts[1] if len(orig_parts) > 1 else original_id
        orig_cfg_file = orig_parts[0] if len(orig_parts) > 1 else cfg_filename

        _ledger            = settings.get('managed_middlewares', {})
        _ledger_changed    = False
        hdr_name           = f"{router_name}-headers"
        hdr_ledger_key     = f"agent_{agent_id}::{hdr_name}" if agent else hdr_name
        hdr_preset_present = protocol == 'http' and request.form.get('headersPresetPresent') == 'true'
        hdr_preset_on      = hdr_preset_present and request.form.get('headersPresetEnabled') == 'true'
        hdr_preset_custom  = request.form.get('headersPresetCustom') == 'true'
        stream_preset_present = protocol == 'http' and request.form.get('streamingPresetPresent') == 'true'
        stream_preset_on      = stream_preset_present and request.form.get('streamingPresetEnabled') == 'true'
        if hdr_preset_on:
            _existing_hdr = config.get('http', {}).get('middlewares', {}).get(hdr_name)
            _hdr_foreign  = _existing_hdr is not None and (
                hdr_ledger_key not in _ledger or (is_edit and orig_cfg_file != cfg_filename))
            if _hdr_foreign:
                _msg = f"A middleware named '{hdr_name}' already exists and wasn't created by the route presets. Rename or remove it first, then re-save."
                if fetch:
                    return jsonify({'ok': False, 'message': _msg}), 409
                flash(_msg, "error")
                return redirect(url_for('index'))

        _prev_tcp_mws = None
        if is_edit and plain_original_id:
            _prev_src = config
            if orig_cfg_file != cfg_filename:
                if agent:
                    _prev_src = _agent_load_configs(agent).get(orig_cfg_file, {})
                else:
                    _prev_path = _resolve_config_path(orig_cfg_file)
                    _prev_src = load_config(_prev_path) if _prev_path else {}
            _prev_tcp_mws = _prev_src.get('tcp', {}).get('routers', {}).get(plain_original_id, {}).get('middlewares')
            for sec in ('http', 'tcp', 'udp'):
                prev_router = _prev_src.get(sec, {}).get('routers', {}).get(plain_original_id)
                if not isinstance(prev_router, dict):
                    continue
                prev_svc = (prev_router.get('service') or '').split('@')[0].strip()
                if prev_svc and prev_svc in _prev_src.get(sec, {}).get('services', {}):
                    service_name = prev_svc
                break

        if not service_ref and is_edit and plain_original_id:
            for sec in ('http', 'tcp', 'udp'):
                prev_router = _prev_src.get(sec, {}).get('routers', {}).get(plain_original_id)
                if not isinstance(prev_router, dict):
                    continue
                _prev_ref = (prev_router.get('service') or '').strip()
                if _prev_ref and _prev_ref != f"{plain_original_id}-service":
                    _ref_in_svcs = _svc_key(_prev_ref) in (_prev_src.get(sec, {}).get('services') or {})
                    if not _ref_in_svcs or _service_shared(_prev_src, _prev_ref, plain_original_id):
                        service_ref = _prev_ref
                break

        if service_ref:
            if _service_ref_posted and '@' not in service_ref:
                if agent:
                    _ref_cfgs = list(_agent_load_configs(agent).values())
                else:
                    _ref_cfgs = [load_config(_p) for _p in env.CONFIG_PATHS]
                if not any(service_ref in ((_c.get(protocol) or {}).get('services') or {}) for _c in _ref_cfgs):
                    _msg = f"Service '{service_ref}' does not exist for {protocol.upper()} routes."
                    if fetch:
                        return jsonify({'ok': False, 'message': _msg}), 400
                    flash(_msg, "error")
                    return redirect(url_for('index'))
            service_name = service_ref

        if is_edit and plain_original_id and orig_cfg_file != cfg_filename:
            if agent:
                old_all_cfgs = _agent_load_configs(agent)
                old_config = old_all_cfgs.get(orig_cfg_file, {})
            else:
                orig_target_path = _resolve_config_path(orig_cfg_file)
                old_config = load_config(orig_target_path) if orig_target_path else {}
            for sec in ('http', 'tcp', 'udp'):
                s = old_config.get(sec, {})
                old_routers = s.get('routers', {})
                old_svc = (old_routers.get(plain_original_id, {}).get('service') or '').strip()
                if plain_original_id in old_routers:
                    del old_routers[plain_original_id]
                if (old_svc and 'services' in s and old_svc in s['services']
                        and not service_ref
                        and not _service_shared(old_config, old_svc, plain_original_id)):
                    del s['services'][old_svc]
            old_transport_name = f"{plain_original_id}-transport"
            http_sec = old_config.get('http', {})
            old_transports = http_sec.get('serversTransports', {})
            old_tp_key = f"agent_{agent_id}::tp::{old_transport_name}" if agent else f"tp::{old_transport_name}"
            if old_transport_name in old_transports and old_tp_key in _ledger:
                del old_transports[old_transport_name]
                if not old_transports:
                    del http_sec['serversTransports']
                del _ledger[old_tp_key]
                _ledger_changed = True
            old_hdr_name = f"{plain_original_id}-headers"
            old_hdr_key  = f"agent_{agent_id}::{old_hdr_name}" if agent else old_hdr_name
            if hdr_preset_present and old_hdr_key in _ledger:
                old_hdr_mws = http_sec.get('middlewares', {})
                old_hdr_mws.pop(old_hdr_name, None)
                if not old_hdr_mws and 'middlewares' in http_sec:
                    del http_sec['middlewares']
                del _ledger[old_hdr_key]
                _ledger_changed = True
            if agent:
                _agent_write_config(agent, orig_cfg_file, old_config)
            elif orig_target_path:
                save_config(_strip_empty_sections(old_config), orig_target_path)

        if is_edit and plain_original_id:
            for sec in ('http', 'tcp', 'udp'):
                s = config.get(sec, {})
                old_routers = s.get('routers', {})
                old_svc = (old_routers.get(plain_original_id, {}).get('service') or '').strip()
                if plain_original_id != router_name and plain_original_id in old_routers:
                    del old_routers[plain_original_id]
                if (old_svc and old_svc != service_name and 'services' in s and old_svc in s['services']
                        and not _service_shared(config, old_svc, plain_original_id)):
                    del s['services'][old_svc]
            if hdr_preset_present and plain_original_id != router_name:
                rn_hdr_name = f"{plain_original_id}-headers"
                rn_hdr_key  = f"agent_{agent_id}::{rn_hdr_name}" if agent else rn_hdr_name
                if rn_hdr_key in _ledger:
                    rn_hdr_mws = config.get('http', {}).get('middlewares', {})
                    rn_hdr_mws.pop(rn_hdr_name, None)
                    if not rn_hdr_mws and 'http' in config and 'middlewares' in config['http']:
                        del config['http']['middlewares']
                    del _ledger[rn_hdr_key]
                    _ledger_changed = True

        if protocol == 'http':
            if http_rule:
                rule = http_rule
            else:
                selected_domains = request.form.getlist('domains') or [domain]
                if subdomain and '.' in subdomain:
                    rule = f"Host(`{subdomain}`)"
                elif subdomain:
                    hosts = [f"Host(`{subdomain}.{d}`)" for d in selected_domains]
                    rule  = " || ".join(hosts)
                else:
                    hosts = [f"Host(`{d}`)" for d in selected_domains]
                    rule  = " || ".join(hosts)
            if target_ip.startswith(('http://', 'https://')):
                target_url = target_ip
            else:
                target_url = f"{scheme}://{target_ip}:{target_port}" if target_port else f"{scheme}://{target_ip}"
            mws        = [m.strip() for m in middlewares_in.split(',')] if middlewares_in else []
            insecure   = request.form.get('insecureSkipVerify') == 'true'
            config.setdefault('http', {}).setdefault('routers', {})
            config['http'].setdefault('services', {})
            if hdr_preset_present:
                if hdr_preset_on or hdr_ledger_key in _ledger:
                    mws = [m for m in mws if m != hdr_name]
                if hdr_preset_on and not hdr_preset_custom:
                    config['http'].setdefault('middlewares', {})[hdr_name] = _build_headers_middleware(_headers_toggles_from_form(request.form))
                _hdr_present_now = config.get('http', {}).get('middlewares', {}).get(hdr_name) is not None
                if hdr_preset_on and _hdr_present_now:
                    mws.append(hdr_name)
                    if hdr_ledger_key not in _ledger:
                        _ledger[hdr_ledger_key] = {'kind': 'route-headers', 'route': router_name}
                        _ledger_changed = True
                elif hdr_ledger_key in _ledger:
                    _hdr_sec = config.get('http', {}).get('middlewares', {})
                    _hdr_sec.pop(hdr_name, None)
                    if not _hdr_sec and 'middlewares' in config['http']:
                        del config['http']['middlewares']
                    _ledger.pop(hdr_ledger_key, None)
                    _ledger_changed = True
            r = {'rule': rule, 'entryPoints': http_eps, 'service': service_name}
            if mws:
                r['middlewares'] = mws
            if not no_tls:
                tls_entry = {'certResolver': cert_resolver} if cert_resolver else {}
                tls_main  = request.form.get('tlsWildcardMain', '').strip()
                tls_sans  = [s.strip() for s in request.form.get('tlsWildcardSans', '').splitlines() if s.strip()]
                if tls_main:
                    domain_entry = {'main': tls_main}
                    if tls_sans:
                        domain_entry['sans'] = tls_sans
                    tls_entry['domains'] = [domain_entry]
                tls_opts_profile = request.form.get('tlsOptionsProfile', '').strip()
                if tls_opts_profile:
                    tls_entry['options'] = tls_opts_profile
                r['tls'] = tls_entry
            if service_ref:
                _merge_router(config['http']['routers'], router_name, r,
                              ('rule', 'entryPoints', 'service', 'middlewares', 'tls'))
                _orphan_tp = f"{svc_name}-transport"
                _transports = config.get('http', {}).get('serversTransports', {})
                if _orphan_tp in _transports:
                    del _transports[_orphan_tp]
                    if not _transports:
                        del config['http']['serversTransports']
            else:
                _be = _parse_backends_json(request.form.get('backendsJsonHttp'))
                _managed_backends = False
                _composite_posted = isinstance(_be, dict) and 'children' in _be
                _composite_type = str((_be or {}).get('compositeType') or 'weighted').strip()
                if _composite_posted and _composite_type == 'failover' \
                        and len(_composite.normalise_children(_be.get('children'))) > 2:
                    _fo_msg = ('Failover takes two backends: the one that serves '
                               'and the one that takes over')
                    if fetch:
                        return jsonify({'ok': False, 'message': _fo_msg}), 400
                    flash(_fo_msg, "error")
                    return redirect(url_for('index'))
                if _be is not None:
                    _servers = _backend_servers(_be.get('servers'), 'url', scheme)
                    if _servers:
                        _managed_backends = True
                        lb = {'servers': _servers}
                    else:
                        lb = {'servers': [{'url': target_url}]}
                else:
                    lb = {'servers': [{'url': target_url}]}
                if not pass_host and not stream_preset_on:
                    lb['passHostHeader'] = False
                if _managed_backends:
                    _sticky = _sticky_block(_be.get('sticky'))
                    if _sticky:
                        lb['sticky'] = _sticky
                    _hc = _healthcheck_block(_be.get('healthCheck'))
                    if _hc:
                        lb['healthCheck'] = _hc
                    _prio = _clean_priority(_be.get('priority'))
                    if _prio:
                        r['priority'] = _prio
                transport_name = f"{svc_name}-transport"
                tp_ledger_key = f"agent_{agent_id}::tp::{transport_name}" if agent else f"tp::{transport_name}"
                existing_transports = config.get('http', {}).get('serversTransports', {})
                tp_existing = existing_transports.get(transport_name)
                tp_existing = tp_existing if isinstance(tp_existing, dict) else None
                tp_ours = tp_existing is None or tp_ledger_key in _ledger
                if not tp_ours:
                    lb['serversTransport'] = transport_name
                else:
                    tp = dict(tp_existing) if tp_existing else {}
                    if insecure:
                        tp['insecureSkipVerify'] = True
                    else:
                        tp.pop('insecureSkipVerify', None)
                    if stream_preset_present:
                        if stream_preset_on:
                            tp['forwardingTimeouts'] = _streaming_forwarding_timeouts()
                        else:
                            tp.pop('forwardingTimeouts', None)
                    if tp:
                        config['http'].setdefault('serversTransports', {})[transport_name] = tp
                        lb['serversTransport'] = transport_name
                        if tp_ledger_key not in _ledger:
                            _ledger[tp_ledger_key] = {'kind': 'route-transport', 'route': router_name}
                            _ledger_changed = True
                    elif transport_name in existing_transports:
                        del existing_transports[transport_name]
                        if not existing_transports and 'serversTransports' in config['http']:
                            del config['http']['serversTransports']
                        if tp_ledger_key in _ledger:
                            del _ledger[tp_ledger_key]
                            _ledger_changed = True
                _http_managed = ('rule', 'entryPoints', 'service', 'middlewares', 'tls', 'priority') \
                    if _managed_backends else ('rule', 'entryPoints', 'service', 'middlewares', 'tls')
                _merge_router(config['http']['routers'], router_name, r, _http_managed)
                _svc_section = config['http']['services']
                _cmp_block, _cmp_owned, _cmp_names = (
                    _composite.build(router_name, _composite_type, _be.get('children'),
                                     lb_extra={k: v for k, v in lb.items() if k != 'servers'})
                    if _composite_posted else (None, {}, []))
                if _cmp_block:
                    _composite.merge_into(_svc_section, service_name, _cmp_block, _cmp_owned)
                    _stale_prefixes = [router_name]
                    if is_edit and plain_original_id and plain_original_id != router_name:
                        _stale_prefixes.append(plain_original_id)
                    for _prefix in _stale_prefixes:
                        for _gone in _composite.drop_orphan_children(_svc_section, _prefix,
                                                                     set(_cmp_owned)):
                            _ledger.pop(_svc_ledger_key(_gone, agent_id), None)
                            _ledger_changed = True
                    for _k, _v in _composite.ledger_entries(service_name, _cmp_block, _cmp_owned,
                                                            cfg_filename, agent_id).items():
                        _ledger[_k] = _v
                    _ledger_changed = True
                else:
                    if _composite_posted:
                        for _gone in _composite.drop_orphan_children(_svc_section, router_name, set()):
                            _ledger.pop(_svc_ledger_key(_gone, agent_id), None)
                            _ledger_changed = True
                        if _svc_ledger_key(service_name, agent_id) in _ledger:
                            del _ledger[_svc_ledger_key(service_name, agent_id)]
                            _ledger_changed = True
                            _existing_svc = _svc_section.get(service_name)
                            if isinstance(_existing_svc, dict):
                                for _stale in _composite.TYPES + ('highestRandomWeight',):
                                    _existing_svc.pop(_stale, None)
                    _merge_service(_svc_section, service_name, lb, 'url', transport_name,
                                   managed_backends=_managed_backends)

        elif protocol == 'tcp':
            if tcp_rule:
                rule = tcp_rule
            elif subdomain:
                _sni = subdomain if '.' in subdomain else f"{subdomain}.{domain}"
                rule = f"HostSNI(`{_sni}`)"
            else:
                rule = "HostSNI(`*`)"
            config.setdefault('tcp', {}).setdefault('routers', {})
            config['tcp'].setdefault('services', {})
            router_entry = {'rule': rule, 'service': service_name}
            if tcp_eps:
                router_entry['entryPoints'] = tcp_eps
            if mws_tcp_raw is not None:
                tcp_mws = [m.strip() for m in mws_tcp_raw.split(',') if m.strip()]
                if tcp_mws:
                    router_entry['middlewares'] = tcp_mws
            elif _prev_tcp_mws:
                router_entry['middlewares'] = _prev_tcp_mws
            if tls_passthrough:
                router_entry['tls'] = {'passthrough': True}
            elif use_tls_tcp:
                router_entry['tls'] = {'certResolver': tcp_cert_resolver} if tcp_cert_resolver else {}
            if service_ref:
                _merge_router(config['tcp']['routers'], router_name, router_entry,
                              ('rule', 'entryPoints', 'service', 'middlewares', 'tls'))
            else:
                _be_tcp = _parse_backends_json(request.form.get('backendsJsonTcp'))
                _tcp_managed = False
                _tcp_lb = {'servers': [{'address': f"{target_ip}:{target_port}"}]}
                if _be_tcp is not None:
                    _tcp_servers = _backend_servers(_be_tcp.get('servers'), 'address')
                    if _tcp_servers:
                        _tcp_managed = True
                        _tcp_lb = {'servers': _tcp_servers}
                        _tcp_prio = _clean_priority(_be_tcp.get('priority'))
                        if _tcp_prio:
                            router_entry['priority'] = _tcp_prio
                _tcp_keys = ('rule', 'entryPoints', 'service', 'middlewares', 'tls', 'priority') \
                    if _tcp_managed else ('rule', 'entryPoints', 'service', 'middlewares', 'tls')
                _merge_router(config['tcp']['routers'], router_name, router_entry, _tcp_keys)
                _merge_service(config['tcp']['services'], service_name, _tcp_lb, 'address', '',
                               managed_backends=_tcp_managed)

        elif protocol == 'udp':
            udp_ep = request.form.get('udpEntryPoint', '').strip()
            config.setdefault('udp', {}).setdefault('routers', {})
            config['udp'].setdefault('services', {})
            _merge_router(config['udp']['routers'], router_name,
                          {'entryPoints': [udp_ep] if udp_ep else [], 'service': service_name},
                          ('entryPoints', 'service'))
            if not service_ref:
                _be_udp = _parse_backends_json(request.form.get('backendsJsonUdp'))
                _udp_managed = False
                _udp_lb = {'servers': [{'address': f"{target_ip}:{target_port}"}]}
                if _be_udp is not None:
                    _udp_servers = _backend_servers(_be_udp.get('servers'), 'address')
                    if _udp_servers:
                        _udp_managed = True
                        _udp_lb = {'servers': _udp_servers}
                _merge_service(config['udp']['services'], service_name, _udp_lb, 'address', '',
                               managed_backends=_udp_managed)

        if _ledger_changed:
            save_settings(
                domains=settings['domains'],
                cert_resolver=settings['cert_resolver'],
                traefik_api_url=settings['traefik_api_url'],
                auth_enabled=settings['auth_enabled'],
                password_hash=settings['password_hash'],
                visible_tabs=settings['visible_tabs'],
                managed_middlewares=_ledger,
            )
        _was_disabled = False
        if is_edit and original_id:
            _disabled_now = load_settings().get('disabled_routes', {})
            _old_dkey = f"agent_{agent_id}::{original_id}" if agent else original_id
            _was_disabled = _old_dkey in _disabled_now
        if _was_disabled:
            _sec = config.get(protocol, {})
            _kept_router = dict(_sec.get('routers', {}).pop(router_name, {}))
            _kept_svc = {}
            if not _service_shared(config, service_name, router_name):
                _kept_svc = dict(_sec.get('services', {}).pop(service_name, {}))
            else:
                _kept_svc = dict(_sec.get('services', {}).get(service_name, {}))
            disabled = dict(load_settings().get('disabled_routes', {}))
            disabled.pop(_old_dkey, None)
            _new_rid = f"{cfg_filename}::{router_name}" if agent else router_name
            _new_dkey = f"agent_{agent_id}::{_new_rid}" if agent else _new_rid
            disabled[_new_dkey] = {'protocol': protocol, 'router': _kept_router,
                                   'service': _kept_svc, 'configFile': cfg_filename}
            _save_disabled_routes(load_settings(), disabled)
        if agent:
            _agent_write_config(agent, cfg_filename, config)
            threading.Thread(target=lambda: _git_push_agent_if_enabled(agent, 'route save'), daemon=True).start()
        else:
            save_config(_strip_empty_sections(config), target_path)
            _register_config_path(target_path)
            threading.Thread(target=lambda: _git_push_if_enabled('route save'), daemon=True).start()
        action = "updated" if is_edit else "created"
        msg = f"Route {svc_name} {action}"
        add_notification('success', msg)
        if fetch:
            return jsonify({'ok': True, 'message': msg})
        flash(msg, "success")
    except Exception:
        logger.exception("Error saving configuration")
        if fetch:
            return jsonify({'ok': False, 'message': 'Error saving configuration'}), 500
        flash("Error saving configuration", "error")
    return redirect(url_for('index'))


def _transport_in_use(config, name, exclude_service=''):
    http = config.get('http') or {}
    for sname, sdef in (http.get('services') or {}).items():
        if sname == exclude_service or not isinstance(sdef, dict):
            continue
        lb = sdef.get('loadBalancer')
        if isinstance(lb, dict) and lb.get('serversTransport') == name:
            return True
    try:
        disabled = load_settings().get('disabled_routes', {}) or {}
    except Exception:
        return True
    for snap in disabled.values():
        if not isinstance(snap, dict):
            continue
        svc = snap.get('service')
        if not isinstance(svc, dict):
            continue
        lb = svc.get('loadBalancer')
        if isinstance(lb, dict) and lb.get('serversTransport') == name:
            return True
    return False


def _drop_owned_transport(config, svc_name, ledger, agent_id=''):
    if not svc_name:
        return False
    name = f"{svc_name}-transport"
    key = f"agent_{agent_id}::tp::{name}" if agent_id else f"tp::{name}"
    if key not in ledger:
        return False
    http = config.get('http') or {}
    transports = http.get('serversTransports') or {}
    if name in transports:
        if _transport_in_use(config, name, exclude_service=svc_name):
            return False
        del transports[name]
        if not transports and 'serversTransports' in http:
            del http['serversTransports']
    ledger.pop(key, None)
    return True


@app.route('/delete/<router_id>', methods=['POST'])
@csrf_protect
@login_required
def delete_entry(router_id):
    fetch = _is_fetch()
    try:
        settings        = load_settings()
        config_file_raw = request.form.get('configFile', '').strip()
        agent_id        = request.form.get('agent_id', '').strip()
        agent           = _agent_by_id(agent_id) if agent_id else None
        plain_id = router_id.split('::', 1)[1] if '::' in router_id else router_id
        deleted = False
        _del_ledger = dict(settings.get('managed_middlewares', {}) or {})
        _del_ledger_changed = False
        if agent:
            all_configs = _agent_load_configs(agent)
            for fname, config in all_configs.items():
                if config_file_raw and fname != config_file_raw:
                    continue
                for sec in ('http', 'tcp', 'udp'):
                    s = config.get(sec, {})
                    if plain_id in s.get('routers', {}):
                        svc = (s['routers'][plain_id].get('service') or '').strip()
                        del s['routers'][plain_id]
                        if (svc and 'services' in s and svc in s['services']
                                and not _service_shared(config, svc, plain_id)):
                            del s['services'][svc]
                            if _drop_owned_transport(config, svc, _del_ledger, agent_id):
                                _del_ledger_changed = True
                        _agent_write_config(agent, fname, config)
                        deleted = True
                        break
                if deleted:
                    break
        else:
            if config_file_raw:
                search_paths = [_resolve_config_path(config_file_raw) or env.CONFIG_PATH]
            else:
                search_paths = env.CONFIG_PATHS
            for target_path in search_paths:
                config = load_config(target_path)
                for sec in ('http', 'tcp', 'udp'):
                    s = config.get(sec, {})
                    if plain_id in s.get('routers', {}):
                        svc = (s['routers'][plain_id].get('service') or '').strip()
                        del s['routers'][plain_id]
                        if (svc and 'services' in s and svc in s['services']
                                and not _service_shared(config, svc, plain_id)):
                            del s['services'][svc]
                            if _drop_owned_transport(config, svc, _del_ledger):
                                _del_ledger_changed = True
                            if sec == 'http':
                                for _gone in _composite.drop_orphan_children(
                                        s['services'], plain_id, set()):
                                    _del_ledger.pop(_svc_ledger_key(_gone, agent_id), None)
                                    _del_ledger_changed = True
                                if _del_ledger.pop(_svc_ledger_key(svc, agent_id), None):
                                    _del_ledger_changed = True
                        create_backup(target_path)
                        save_config(_strip_empty_sections(config), target_path)
                        deleted = True
                        break
                if deleted:
                    break
        if not deleted:
            disabled = dict(settings.get('disabled_routes', {}))
            if agent:
                agent_id = request.form.get('agent_id', '').strip()
                prefix = f"agent_{agent_id}::"
                store_key = _disabled_key(disabled, prefix + router_id, plain_id, prefix)
            else:
                store_key = _disabled_key(disabled, router_id, plain_id)
            if store_key:
                disabled.pop(store_key)
                _save_disabled_routes(settings, disabled)
                deleted = True
        if not deleted:
            if fetch:
                return jsonify({'ok': False, 'message': f'Route "{plain_id}" not found'}), 404
            flash(f'Route "{plain_id}" not found', "error")
            return redirect(url_for('index'))
        if agent:
            threading.Thread(target=lambda: _git_push_agent_if_enabled(agent, 'route delete'), daemon=True).start()
        else:
            threading.Thread(target=lambda: _git_push_if_enabled('route delete'), daemon=True).start()
        if _del_ledger_changed:
            _s = load_settings()
            save_settings(
                domains=_s['domains'], cert_resolver=_s['cert_resolver'],
                traefik_api_url=_s['traefik_api_url'], auth_enabled=_s['auth_enabled'],
                password_hash=_s['password_hash'], visible_tabs=_s['visible_tabs'],
                managed_middlewares=_del_ledger,
            )
        msg = f"Route {plain_id} deleted"
        add_notification('warning', msg)
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
        _mw_rename_cascade = None
        mw_name         = request.form.get('middlewareName', '').strip()
        mw_content      = request.form.get('middlewareContent', '').strip()
        is_edit         = request.form.get('isMwEdit') == 'true'
        original_id     = request.form.get('originalMwId', '')
        mw_protocol     = request.form.get('mwProtocol', 'http').strip().lower()
        if mw_protocol not in ('http', 'tcp'):
            mw_protocol = 'http'
        original_proto  = request.form.get('originalMwProtocol', '').strip().lower()
        if original_proto not in ('http', 'tcp'):
            original_proto = mw_protocol
        config_file_raw = request.form.get('configFile', '').strip()
        agent_id        = request.form.get('agent_id', '').strip()
        agent           = _agent_by_id(agent_id) if agent_id else None
        cfg_filename    = config_file_raw or 'dynamic.yml'
        target_path     = None if agent else (_resolve_config_path(config_file_raw) or env.CONFIG_PATH)
        if not mw_name:
            if fetch:
                return jsonify({'ok': False, 'message': 'Middleware name is required'}), 400
            flash("Middleware name is required", "error")
            return redirect(url_for('index'))
        if not mw_content:
            if fetch:
                return jsonify({'ok': False, 'message': 'Middleware content cannot be empty'}), 400
            flash("Middleware content cannot be empty", "error")
            return redirect(url_for('index'))
        try:
            parsed_mw = SafeYAML(typ='safe').load(mw_content)
        except Exception as ye:
            msg = f'Invalid YAML: {ye}'
            if fetch:
                return jsonify({'ok': False, 'message': msg}), 400
            flash(msg, "error")
            return redirect(url_for('index'))
        if parsed_mw is None or not isinstance(parsed_mw, dict) or not parsed_mw:
            if fetch:
                return jsonify({'ok': False, 'message': 'Middleware content is empty or invalid'}), 400
            flash("Middleware content is empty or invalid", "error")
            return redirect(url_for('index'))
        wrapper = next((k for k in ('http', 'tcp', 'udp') if k in parsed_mw), None)
        if wrapper:
            section = parsed_mw.get(wrapper)
            inner = section.get('middlewares') if isinstance(section, dict) else None
            if wrapper == 'udp' or len(parsed_mw) != 1 or not isinstance(inner, dict) or not inner:
                msg = 'Paste the middleware body, or a full http:/tcp: block holding a single middleware'
                if fetch:
                    return jsonify({'ok': False, 'message': msg}), 400
                flash(msg, "error")
                return redirect(url_for('index'))
            if len(inner) > 1:
                msg = 'That block defines several middlewares - paste one at a time'
                if fetch:
                    return jsonify({'ok': False, 'message': msg}), 400
                flash(msg, "error")
                return redirect(url_for('index'))
            body = next(iter(inner.values()))
            if not isinstance(body, dict) or not body:
                msg = 'The middleware in that block has no configuration'
                if fetch:
                    return jsonify({'ok': False, 'message': msg}), 400
                flash(msg, "error")
                return redirect(url_for('index'))
            parsed_mw = body
            mw_protocol = wrapper
        if mw_protocol == 'tcp' and not set(parsed_mw.keys()) <= {'ipAllowList', 'ipWhiteList', 'inFlightConn'}:
            msg = 'TCP middlewares support only ipAllowList and inFlightConn'
            if fetch:
                return jsonify({'ok': False, 'message': msg}), 400
            flash(msg, "error")
            return redirect(url_for('index'))
        if agent:
            config = _agent_load_configs(agent).get(cfg_filename, {})
        else:
            create_backup(target_path)
            config = load_config(target_path)
        config.setdefault(mw_protocol, {}).setdefault('middlewares', {})
        if is_edit and original_id and (original_id != mw_name or original_proto != mw_protocol):
            config.get(original_proto, {}).get('middlewares', {}).pop(original_id, None)
            if original_id != mw_name:
                _retarget_middleware(config, original_id, mw_name)
                _mw_rename_cascade = (original_id, mw_name)
        config[mw_protocol]['middlewares'][mw_name] = parsed_mw
        if agent:
            _agent_write_config(agent, cfg_filename, config)
            if _mw_rename_cascade:
                _o, _n = _mw_rename_cascade
                _cascade_across_configs(agent, lambda c: _retarget_middleware(c, _o, _n),
                                        already=cfg_filename)
            threading.Thread(target=lambda: _git_push_agent_if_enabled(agent, 'middleware save'), daemon=True).start()
        else:
            save_config(_strip_empty_sections(config), target_path)
            if _mw_rename_cascade:
                _o, _n = _mw_rename_cascade
                _cascade_across_configs(None, lambda c: _retarget_middleware(c, _o, _n),
                                        already=target_path)
            _register_config_path(target_path)
            threading.Thread(target=lambda: _git_push_if_enabled('middleware save'), daemon=True).start()
        action = "updated" if is_edit else "created"
        msg = f"Middleware {mw_name} {action}"
        add_notification('success', msg)
        if fetch:
            return jsonify({'ok': True, 'message': msg})
        flash(msg, "success")
    except Exception:
        logger.exception("Middleware save error")
        if fetch:
            return jsonify({'ok': False, 'message': 'Error saving middleware'}), 500
        flash("Error saving middleware", "error")
    return redirect(url_for('index'))


def _retarget_service(config, old: str, new: str) -> bool:
    bare = str(old or '').split('@')[0]
    changed = False
    for section in ('http', 'tcp', 'udp'):
        for rdata in ((config.get(section) or {}).get('routers') or {}).values():
            if isinstance(rdata, dict) and str(rdata.get('service') or '').split('@')[0] == bare:
                rdata['service'] = new
                changed = True
    for sdata in ((config.get('http') or {}).get('services') or {}).values():
        if not isinstance(sdata, dict):
            continue
        for kind in ('weighted', 'mirroring', 'failover', 'highestRandomWeight'):
            block = sdata.get(kind)
            if not isinstance(block, dict):
                continue
            for key in ('service', 'fallback'):
                if str(block.get(key) or '').split('@')[0] == bare:
                    block[key] = new
                    changed = True
            for child in (block.get('services') or []) + (block.get('mirrors') or []):
                if isinstance(child, dict) and str(child.get('name') or '').split('@')[0] == bare:
                    child['name'] = new
                    changed = True
    return changed


def _cascade_across_configs(agent, fn, already=''):
    touched = []
    if agent:
        for fname, cfg in _agent_load_configs(agent).items():
            if fname == already:
                continue
            if fn(cfg):
                _agent_write_config(agent, fname, cfg)
                touched.append(fname)
        return touched
    for path in env.CONFIG_PATHS:
        if path == already or os.path.basename(path) == already:
            continue
        cfg = load_config(path)
        if fn(cfg):
            create_backup(path)
            save_config(_strip_empty_sections(cfg), path)
            touched.append(os.path.basename(path))
    return touched


def _static_plugins(doc) -> dict:
    block = ((doc or {}).get('experimental') or {}).get('plugins') or {}
    return {k: v for k, v in block.items() if isinstance(v, dict)}


def _plugin_diff(before: dict, after: dict) -> tuple:
    gone = [k for k in before if k not in after]
    added = [k for k in after if k not in before]
    renames = {}
    for old in list(gone):
        mod = str(before[old].get('moduleName') or '').strip()
        if not mod:
            continue
        for new in list(added):
            if str(after[new].get('moduleName') or '').strip() == mod:
                renames[old] = new
                gone.remove(old)
                added.remove(new)
                break
    return renames, gone


def _middlewares_using_plugin(configs, name: str) -> list:
    out = []
    for cfg in configs:
        for section in ('http', 'tcp'):
            for mname, mdata in ((cfg.get(section) or {}).get('middlewares') or {}).items():
                if isinstance(mdata, dict) and isinstance(mdata.get('plugin'), dict) \
                        and name in mdata['plugin']:
                    out.append(mname)
    return sorted(set(out))


def _retarget_plugin(config, old: str, new: str) -> bool:
    changed = False
    for section in ('http', 'tcp'):
        for mdata in ((config.get(section) or {}).get('middlewares') or {}).values():
            if not isinstance(mdata, dict):
                continue
            block = mdata.get('plugin')
            if isinstance(block, dict) and old in block:
                block[new] = block.pop(old)
                changed = True
    return changed


def _retarget_tls_option(config, old: str, new: str) -> bool:
    bare = str(old or '').split('@')[0]
    changed = False
    for section in ('http', 'tcp'):
        for rdata in ((config.get(section) or {}).get('routers') or {}).values():
            if not isinstance(rdata, dict):
                continue
            tls = rdata.get('tls')
            if isinstance(tls, dict) and str(tls.get('options') or '').split('@')[0] == bare:
                tls['options'] = new
                changed = True
    return changed


def _tls_option_routers_using(configs, name: str) -> list:
    bare = str(name or '').split('@')[0]
    out = []
    for cfg in configs:
        for section in ('http', 'tcp'):
            for rname, rdata in ((cfg.get(section) or {}).get('routers') or {}).items():
                if not isinstance(rdata, dict):
                    continue
                tls = rdata.get('tls')
                if isinstance(tls, dict) and str(tls.get('options') or '').split('@')[0] == bare:
                    out.append(rname)
    return sorted(set(out))


def _middleware_routers_using(configs, name: str) -> list:
    bare = str(name or '').split('@')[0]
    out = []
    for cfg in configs:
        for section in ('http', 'tcp'):
            for rname, rdata in ((cfg.get(section) or {}).get('routers') or {}).items():
                if not isinstance(rdata, dict):
                    continue
                for ref in (rdata.get('middlewares') or []):
                    if str(ref).split('@')[0] == bare:
                        out.append(rname)
                        break
    return sorted(set(out))


def _retarget_middleware(config, old: str, new: str) -> bool:
    bare = str(old or '').split('@')[0]
    changed = False
    for section in ('http', 'tcp'):
        for rdata in ((config.get(section) or {}).get('routers') or {}).values():
            if not isinstance(rdata, dict) or not rdata.get('middlewares'):
                continue
            rebuilt = []
            hit = False
            for ref in rdata['middlewares']:
                if str(ref).split('@')[0] == bare:
                    hit = True
                    if new:
                        rebuilt.append(new)
                else:
                    rebuilt.append(ref)
            if hit:
                changed = True
                if rebuilt:
                    rdata['middlewares'] = rebuilt
                else:
                    rdata.pop('middlewares', None)
    return changed


@app.route('/delete-middleware/<mw_name>', methods=['POST'])
@csrf_protect
@login_required
def delete_middleware(mw_name):
    fetch = _is_fetch()
    try:
        config_file_raw = request.form.get('configFile', '').strip()
        agent_id        = request.form.get('agent_id', '').strip()
        agent           = _agent_by_id(agent_id) if agent_id else None
        force           = str(request.form.get('force', '')).strip().lower() in ('1', 'true', 'yes')
        _all = (list(_agent_load_configs(agent).values()) if agent
                else [load_config(_p) for _p in env.CONFIG_PATHS])
        _users = _middleware_routers_using(_all, mw_name)
        if _users and not force:
            msg = (f"{mw_name} is still used by " + ', '.join(_users[:5])
                   + (' and others' if len(_users) > 5 else ''))
            if fetch:
                return jsonify({'ok': False, 'message': msg, 'inUseBy': _users}), 409
            flash(msg, "error")
            return redirect(url_for('index'))
        if agent:
            all_configs = _agent_load_configs(agent)
            for fname, config in all_configs.items():
                if config_file_raw and fname != config_file_raw:
                    continue
                found = False
                for section in ('http', 'tcp'):
                    mws = config.get(section, {}).get('middlewares', {})
                    if mw_name in mws:
                        mws.pop(mw_name, None)
                        found = True
                        break
                if _retarget_middleware(config, mw_name, ''):
                    found = True
                if found:
                    _agent_write_config(agent, fname, config)
        else:
            if config_file_raw:
                search_paths = [_resolve_config_path(config_file_raw) or env.CONFIG_PATH]
            else:
                search_paths = env.CONFIG_PATHS
            for target_path in search_paths:
                config = load_config(target_path)
                found = False
                for section in ('http', 'tcp'):
                    mws = config.get(section, {}).get('middlewares', {})
                    if mw_name in mws:
                        mws.pop(mw_name, None)
                        found = True
                        break
                if _retarget_middleware(config, mw_name, ''):
                    found = True
                if found:
                    create_backup(target_path)
                    save_config(_strip_empty_sections(config), target_path)
        if agent:
            threading.Thread(target=lambda: _git_push_agent_if_enabled(agent, 'middleware delete'), daemon=True).start()
        else:
            threading.Thread(target=lambda: _git_push_if_enabled('middleware delete'), daemon=True).start()
        msg = f"Middleware {mw_name} deleted"
        add_notification('warning', msg)
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
    silent = request.args.get('silent') == '1'
    if silent:
        session['oidc_auto_tried'] = True
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
    scopes = ['openid', 'email', 'profile']
    groups_claim = s.get('oidc_groups_claim', '').strip()
    if s.get('oidc_allowed_groups', '').strip() and groups_claim and groups_claim not in scopes:
        scopes.append(groups_claim)
    verifier  = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode('ascii')).digest()).decode('ascii').rstrip('=')
    session['oidc_verifier'] = verifier
    auth_params = {
        'response_type':         'code',
        'client_id':             s.get('oidc_client_id', ''),
        'redirect_uri':          redirect_uri,
        'scope':                 ' '.join(scopes),
        'state':                 state,
        'nonce':                 nonce,
        'code_challenge':        challenge,
        'code_challenge_method': 'S256',
    }
    if silent:
        auth_params['prompt'] = 'none'
    params = urlencode(auth_params)
    return redirect(f"{cfg['authorization_endpoint']}?{params}")


@app.route('/auth/oidc/callback')
def oidc_callback():
    s = load_settings()
    if not s.get('oidc_enabled'):
        return redirect(url_for('login'))
    state = request.args.get('state', '')
    if not state or not secrets.compare_digest(state, session.get('oidc_state', '')):
        logger.warning(f"OIDC callback rejected from {request.remote_addr} - state mismatch "
                       f"(provider sent {'a state' if state else 'no state'}, "
                       f"session {'has one' if session.get('oidc_state') else 'has none'})"
                       + (f", provider error={request.args.get('error')!r}"
                          if request.args.get('error') else ''))
        flash("Invalid OIDC state. Please try again.", "error")
        return redirect(url_for('login'))
    err = request.args.get('error', '')
    if err in ('login_required', 'interaction_required', 'consent_required', 'account_selection_required'):
        logger.info(f"OIDC silent login not possible ({err}) - showing the login page")
        return redirect(url_for('login'))
    code = request.args.get('code', '')
    if not code:
        logger.warning(f"OIDC callback returned no code from {request.remote_addr}"
                       + (f" - provider error={request.args.get('error')!r} "
                          f"{request.args.get('error_description', '')!r}"
                          if request.args.get('error') else ''))
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
        client_id     = s.get('oidc_client_id', '')
        client_secret = s.get('oidc_client_secret', '')
        payload = {
            'grant_type':   'authorization_code',
            'code':         code,
            'redirect_uri': url_for('oidc_callback', _external=True),
            'code_verifier': session.pop('oidc_verifier', ''),
        }
        supported = cfg.get('token_endpoint_auth_methods_supported') or []

        def _post_basic():
            basic = base64.b64encode(
                f"{quote(client_id, safe='')}:{quote(client_secret, safe='')}".encode()
            ).decode()
            return requests.post(cfg['token_endpoint'], data=payload,
                                 headers={'Authorization': f'Basic {basic}'}, timeout=8)

        def _post_body():
            return requests.post(
                cfg['token_endpoint'],
                data=dict(payload, client_id=client_id, client_secret=client_secret), timeout=8)

        if not client_secret:
            token_resp = requests.post(
                cfg['token_endpoint'], data=dict(payload, client_id=client_id), timeout=8)
        else:
            basic_only = ('client_secret_basic' in supported
                          and 'client_secret_post' not in supported)
            order = [_post_basic, _post_body] if basic_only else [_post_body, _post_basic]
            token_resp = order[0]()
            first_err = ''
            if token_resp.status_code >= 400:
                try:
                    first_err = (token_resp.json() or {}).get('error', '')
                except Exception:
                    first_err = ''
            retryable = (400 <= token_resp.status_code < 500
                         and token_resp.status_code != 429
                         and first_err != 'invalid_grant')
            if retryable:
                logger.info(
                    "OIDC token exchange rejected with %s (HTTP %s), retrying with the other method",
                    'client_secret_basic' if basic_only else 'client_secret_post',
                    token_resp.status_code)
                retry = order[1]()
                if retry.status_code < 400:
                    logger.info("OIDC token exchange succeeded on the second method")
                    token_resp = retry
                    if token_resp.status_code >= 400:
                        logger.error(
                            "OIDC rejected both client authentication methods. "
                            "TM sent client_id=%r, a secret of %d characters, to %s. "
                            "Compare that client_id and secret length against the provider.",
                            client_id, len(client_secret), cfg['token_endpoint'])
        if token_resp.status_code >= 400:
            detail = ''
            try:
                body = token_resp.json()
                detail = str(body.get('error_description') or body.get('error') or '')
            except Exception:
                detail = (token_resp.text or '')[:300]
            logger.error(
                "OIDC token exchange rejected by the provider (HTTP %s): %s",
                token_resp.status_code, detail or '(empty response body)')
            flash(f"OIDC login failed - the provider rejected the token request: {detail}"
                  if detail else "OIDC login failed - the provider rejected the token request.",
                  "error")
            return redirect(url_for('login'))
        tokens = token_resp.json()
    except Exception:
        logger.exception("OIDC token exchange failed")
        flash("OIDC login failed - token exchange error.", "error")
        return redirect(url_for('login'))
    id_token = tokens.get('id_token', '')
    expected_nonce = session.pop('oidc_nonce', '')
    id_claims = {}
    if id_token:
        try:
            import json as _json
            payload_b64 = id_token.split('.')[1]
            payload_b64 += '=' * (-len(payload_b64) % 4)
            id_claims = _json.loads(base64.urlsafe_b64decode(payload_b64))
        except Exception:
            logger.warning("OIDC could not decode the id_token payload")
    if id_token and expected_nonce:
        try:
            if not secrets.compare_digest(str(id_claims.get('nonce', '')), expected_nonce):
                logger.warning(f"OIDC nonce mismatch from {request.remote_addr}")
                flash("OIDC login failed - nonce mismatch.", "error")
                return redirect(url_for('login'))
        except Exception:
            logger.warning("OIDC id_token nonce verification skipped - could not decode token")
    access_token = tokens.get('access_token', '')
    groups_claim = str(s.get('oidc_groups_claim', '') or 'groups').strip()
    need_email  = not str(id_claims.get('email', '')).strip()
    need_groups = bool(str(s.get('oidc_allowed_groups', '')).strip()) and not id_claims.get(groups_claim)
    userinfo = {}
    if access_token and cfg.get('userinfo_endpoint') and (need_email or need_groups):
        try:
            userinfo_resp = requests.get(cfg['userinfo_endpoint'],
                                         headers={'Authorization': f'Bearer {access_token}'},
                                         timeout=(3, 5))
            userinfo_resp.raise_for_status()
            userinfo = userinfo_resp.json()
        except Exception as e:
            logger.warning("OIDC userinfo fetch failed (%s) - falling back to the id_token claims", e)
    userinfo = {**id_claims, **userinfo} if (userinfo or id_claims) else {}
    if not userinfo:
        logger.error("OIDC login failed - no claims from userinfo or the id_token")
        flash("OIDC login failed - the provider returned no account details.", "error")
        return redirect(url_for('login'))
    email  = str(userinfo.get('email', '')).strip().lower()
    name   = str(userinfo.get('name', userinfo.get('preferred_username', email))).strip()
    groups = userinfo.get(s.get('oidc_groups_claim', 'groups'), [])
    if not isinstance(groups, list):
        groups = [str(groups)]
    _ev = userinfo.get('email_verified')
    email_unverified = _ev is False or (isinstance(_ev, str) and _ev.strip().lower() in ('false', '0', 'no'))
    allowed_emails = [e.strip().lower() for e in s.get('oidc_allowed_emails', '').split(',') if e.strip()]
    allowed_groups = [g.strip() for g in s.get('oidc_allowed_groups', '').split(',') if g.strip()]
    if not allowed_emails and not allowed_groups and not s.get('oidc_allow_any_authenticated'):
        logger.warning(f"OIDC login denied for {email!r} - no allowed emails/groups configured (set an allowlist or enable 'Allow any authenticated account')")
        flash("OIDC is enabled but no allowed emails or groups are configured. Ask an admin to set an allowlist.", "error")
        return redirect(url_for('login'))
    if allowed_emails and email not in allowed_emails:
        logger.warning(f"OIDC login denied for {email!r} - not in allowed emails")
        flash("Your account is not authorized to access this application.", "error")
        return redirect(url_for('login'))
    if allowed_emails and email in allowed_emails and email_unverified:
        logger.warning(f"OIDC login denied for {email!r} - email not verified by the identity provider")
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
    add_notification('info', f"OIDC login: {email} from {request.remote_addr}", category='security')
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
        'oidc_allow_any_authenticated': bool(s.get('oidc_allow_any_authenticated', False)),
        'oidc_groups_claim':    s.get('oidc_groups_claim', 'groups'),
        'oidc_auto_login':      bool(s.get('oidc_auto_login', False)),
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
            auth_enabled=s.get('auth_enabled', True),
            password_hash=s.get('password_hash', ''),
            visible_tabs=s.get('visible_tabs'),
            oidc_enabled=bool(data.get('oidc_enabled', False)),
            oidc_provider_url=str(data.get('oidc_provider_url', '')).strip(),
            oidc_client_id=str(data.get('oidc_client_id', '')).strip(),
            oidc_client_secret=secret_raw,
            oidc_display_name=str(data.get('oidc_display_name', 'OIDC')).strip() or 'OIDC',
            oidc_allowed_emails=str(data.get('oidc_allowed_emails', '')).strip(),
            oidc_allowed_groups=str(data.get('oidc_allowed_groups', '')).strip(),
            oidc_allow_any_authenticated=bool(data.get('oidc_allow_any_authenticated', False)),
            oidc_groups_claim=str(data.get('oidc_groups_claim', 'groups')).strip() or 'groups',
            oidc_auto_login=bool(data.get('oidc_auto_login', False)),
        )
        reauth = _auth_required() and not session.get('authenticated')
        return jsonify({'ok': True, 'reauth_required': reauth})
    except Exception:
        logger.exception("OIDC save error")
        return jsonify({'ok': False, 'error': 'Save failed'}), 500


@app.route('/api/auth/oidc/test', methods=['POST'])
@csrf_protect
@login_required
def api_test_oidc():
    data = request.get_json(silent=True) or {}
    url  = str(data.get('provider_url', '')).strip().rstrip('/')
    if not url or not url.startswith(('http://', 'https://')):
        return jsonify({'ok': False, 'error': 'No provider URL'})
    if not _ssrf_ok(url):
        return jsonify({'ok': False, 'error': 'Target address not allowed'})
    logger.info(f"OIDC provider test to {url!r} by {request.remote_addr}")
    try:
        resp = requests.get(f"{url}/.well-known/openid-configuration", timeout=5)
        resp.raise_for_status()
        cfg = resp.json()
        return jsonify({
            'ok': True,
            'issuer': cfg.get('issuer', url),
            'checked': 'discovery only',
            'note': 'Provider reachable. Credentials are not verified until you sign in.',
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


def _redact_agent(a: dict) -> dict:
    out = dict(a)
    out['api_key'] = '***' if out.get('api_key') else ''
    out['traefik_api_password'] = '***' if out.get('traefik_api_password') else ''
    out['crowdsec_api_key'] = '***' if out.get('crowdsec_api_key') else ''
    out['crowdsec_machine_password'] = '***' if out.get('crowdsec_machine_password') else ''
    out['git_backup_token'] = '***' if out.get('git_backup_token') else ''
    return out


@app.route('/api/mw/templates', methods=['GET'])
@login_required
def api_mw_templates_list():
    return jsonify({'templates': load_templates()})


@app.route('/api/mw/templates', methods=['POST'])
@csrf_protect
@login_required
def api_mw_templates_create():
    import uuid as _uuid
    data = request.get_json(silent=True) or {}
    name = str(data.get('name', '')).strip()[:100]
    yaml_content = str(data.get('yaml', '')).strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    templates = load_templates()
    template = {'id': str(_uuid.uuid4()), 'name': name, 'yaml': yaml_content}
    templates.append(template)
    save_templates_file(templates)
    return jsonify({'ok': True, 'template': template})


@app.route('/api/mw/templates/<template_id>', methods=['PUT'])
@csrf_protect
@login_required
def api_mw_templates_update(template_id):
    data = request.get_json(silent=True) or {}
    templates = load_templates()
    updated = False
    for i, t in enumerate(templates):
        if t['id'] == template_id:
            if 'name' in data:
                templates[i]['name'] = str(data['name']).strip()[:100]
            if 'yaml' in data:
                templates[i]['yaml'] = str(data['yaml'])
            updated = True
            break
    if not updated:
        return jsonify({'error': 'Template not found'}), 404
    save_templates_file(templates)
    return jsonify({'ok': True})


@app.route('/api/mw/templates/<template_id>', methods=['DELETE'])
@csrf_protect
@login_required
def api_mw_templates_delete(template_id):
    templates = [t for t in load_templates() if t['id'] != template_id]
    save_templates_file(templates)
    return jsonify({'ok': True})


@app.route('/api/agents/<agent_id>/routes')
@login_required
def api_agent_routes(agent_id):
    agent = _agent_by_id(agent_id)
    if not agent:
        return jsonify({'error': 'Agent not found'}), 404
    try:
        all_configs = _agent_load_configs(agent)

        config_errors = []
        try:
            r_resp = _agent_request(agent, 'GET', '/api/traefik/routers')
            s_resp = _agent_request(agent, 'GET', '/api/traefik/services')
            all_routers  = r_resp.json()  if r_resp.ok  else {}
            all_services = s_resp.json()  if s_resp.ok  else {}
            if not r_resp.ok:
                try:
                    err = r_resp.json().get('error') or r_resp.text
                except Exception:
                    err = r_resp.text
                config_errors.append({'file': "Agent Traefik API", 'error': err or f'HTTP {r_resp.status_code}'})
        except Exception as e:
            all_routers  = {}
            all_services = {}
            config_errors.append({'file': "Agent Traefik API", 'error': str(e)})

        svc_urls = _traefik_service_url_map(all_services)

        combined_http, combined_tcp, combined_udp = {}, {}, {}
        for config in all_configs.values():
            for k, v in config.get('http', {}).get('services', {}).items():
                combined_http.setdefault(k, v)
            for k, v in config.get('tcp',  {}).get('services', {}).items():
                combined_tcp.setdefault(k, v)
            for k, v in config.get('udp',  {}).get('services', {}).items():
                combined_udp.setdefault(k, v)

        apps, middlewares = [], []
        for fname, config in all_configs.items():
            apps.extend(_build_apps(config, config_file=fname,
                                    extra_http_svcs=combined_http,
                                    extra_tcp_svcs=combined_tcp,
                                    extra_udp_svcs=combined_udp,
                                    api_svc_urls=svc_urls,
                                    agent_id=agent_id))
            middlewares.extend(_build_middlewares(config, config_file=fname))

        apps.extend(_build_external_routes(all_routers, svc_urls))

        prefix = f"agent_{agent_id}::"
        for store_key, rdata in load_settings().get('disabled_routes', {}).items():
            if not store_key.startswith(prefix):
                continue
            rid      = store_key[len(prefix):]
            rname    = rid.split('::', 1)[1] if '::' in rid else rid
            proto    = rdata.get('protocol', 'http')
            router   = rdata.get('router', {})
            svc_name = router.get('service', '')
            svc      = rdata.get('service', {})
            cf       = rdata.get('configFile', '')
            servers  = svc.get('loadBalancer', {}).get('servers', [])
            if proto == 'http':
                target = servers[0].get('url', 'N/A') if servers else 'N/A'
                apps.append({'id': rid, 'name': rname, 'rule': router.get('rule', ''),
                             'service_name': svc_name, 'target': target,
                             'middlewares': router.get('middlewares', []),
                             'entryPoints': router.get('entryPoints', []),
                             'protocol': 'http', 'tls': bool(router.get('tls')), 'enabled': False,
                             'passHostHeader': svc.get('loadBalancer', {}).get('passHostHeader', True),
                             'serviceType': _service_type(svc),
                             'configFile': cf, 'provider': 'file', 'entrypointMiddlewares': []})
            else:
                target = servers[0].get('address', 'N/A') if servers else 'N/A'
                apps.append({'id': rid, 'name': rname, 'rule': router.get('rule', ''),
                             'service_name': svc_name, 'target': target,
                             'middlewares': router.get('middlewares', []) if proto == 'tcp' else [],
                             'entryPoints': router.get('entryPoints', []),
                             'protocol': proto, 'tls': bool(router.get('tls')) if proto == 'tcp' else False,
                             'serviceType': _service_type(svc),
                             'enabled': False, 'configFile': cf, 'provider': 'file'})

        _mm_ledger       = load_settings().get('managed_middlewares', {})
        _http_mw_by_file = {fn: ((cfg.get('http') or {}).get('middlewares') or {}) for fn, cfg in all_configs.items()}
        for _app in apps:
            if _app.get('protocol') != 'http' or _app.get('provider') != 'file':
                continue
            hdr_mw_name = f"{_app.get('name')}-headers"
            hdr_body    = _http_mw_by_file.get(_app.get('configFile', ''), {}).get(hdr_mw_name)
            owned       = f"agent_{agent_id}::{hdr_mw_name}" in _mm_ledger
            decoded     = _decode_headers_middleware(hdr_body) if (owned and hdr_body is not None) else None
            if not owned or hdr_body is None:
                hdr_state = 'off'
            elif decoded is not None:
                hdr_state = 'toggles'
            else:
                hdr_state = 'custom'
            _app['headersPreset'] = {
                'owned':   owned,
                'exists':  hdr_body is not None,
                'state':   hdr_state,
                'toggles': decoded if decoded is not None else _headers_preset_defaults(),
            }

        return jsonify({'apps': apps, 'middlewares': middlewares, 'configErrors': config_errors,
                        'services': _collect_file_services(all_configs.values())})
    except requests.exceptions.SSLError as e:
        return jsonify({'error': 'TLS verification failed - the agent certificate is not trusted '
                                 'by Traefik Manager (%s)' % str(e)[:100]}), 502
    except requests.exceptions.ConnectionError:
        return jsonify({'error': 'Cannot reach agent'}), 502
    except Exception as e:
        logger.exception("Agent routes error")
        return jsonify({'error': str(e)}), 500


def _agent_api_cert_resolvers(agent) -> list:
    found = []
    try:
        resp = _agent_request(agent, 'GET', '/api/traefik/routers')
        if resp.status_code != 200:
            return found
        data = resp.json() or {}
        for proto in ('http', 'tcp'):
            for r in (data.get(proto) or []):
                if not isinstance(r, dict):
                    continue
                tls = r.get('tls')
                if not isinstance(tls, dict):
                    continue
                name = str(tls.get('certResolver') or '').strip()
                if name and name not in found:
                    found.append(name)
    except Exception:
        logger.debug("Failed to read cert resolvers from agent Traefik API", exc_info=True)
    return found


@app.route('/api/agents/<agent_id>/cert-resolvers')
@login_required
def api_agent_cert_resolvers(agent_id):
    agent = _agent_by_id(agent_id)
    if not agent:
        return jsonify({'resolvers': []})
    configured = [r.strip() for r in (agent.get('cert_resolver') or '').split(',') if r.strip()]
    for name in _agent_api_cert_resolvers(agent):
        if name not in configured:
            configured.append(name)
    try:
        resp = _agent_request(agent, 'GET', '/api/static')
        if resp.status_code != 200:
            return jsonify({'resolvers': configured})
        content   = (resp.json() or {}).get('content', '')
        data      = _yaml_safe.load(content) or {}
        resolvers = data.get('certificatesResolvers') or {}
        if isinstance(resolvers, dict):
            for k in resolvers:
                k = str(k).strip()
                if k and k not in configured:
                    configured.append(k)
    except Exception:
        logger.debug("Failed to read agent cert resolvers", exc_info=True)
    return jsonify({'resolvers': configured})


@app.route('/api/agents', methods=['GET'])
@login_required
def api_agents_list():
    agents = load_settings().get('agents', [])
    return jsonify({'agents': [_redact_agent(a) for a in agents]})


@app.route('/api/agents', methods=['POST'])
@csrf_protect
@login_required
def api_agents_create():
    import uuid as _uuid
    data = request.get_json(silent=True) or {}
    name = str(data.get('name', '')).strip()[:100]
    url  = str(data.get('url', '')).strip().rstrip('/')
    if not name or not url:
        return jsonify({'error': 'name and url are required'}), 400
    url_err = _agent_url_error(url)
    if url_err:
        return jsonify({'error': url_err}), 400
    raw_key = secrets.token_urlsafe(32)
    agent = {
        'id':         str(_uuid.uuid4()),
        'name':       name,
        'url':        url,
        'api_key':    raw_key,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'install_method':        'cli' if str(data.get('install_method', '')).strip() == 'cli' else 'manual',
        'traefik_api_url':       str(data.get('traefik_api_url', 'http://traefik:8080')).strip(),
        'cert_resolver':         str(data.get('cert_resolver', '')).strip(),
        'config_path':           str(data.get('config_path', '/app/config')).strip(),
        'backup_keep_count':     str(data.get('backup_keep_count', '')).strip(),
        'static_config_path':    str(data.get('static_config_path', '')).strip(),
        'acme_json_path':        str(data.get('acme_json_path', '')).strip(),
        'access_log_path':       str(data.get('access_log_path', '')).strip(),
        'plugins_dir':           str(data.get('plugins_dir', '')).strip(),
        'restart_method':        str(data.get('restart_method', '')).strip(),
        'traefik_container':     str(data.get('traefik_container', 'traefik')).strip(),
        'docker_host':           str(data.get('docker_host', '')).strip(),
        'signal_file_path':      str(data.get('signal_file_path', '')).strip(),
        'crowdsec_lapi_url':     str(data.get('crowdsec_lapi_url', '')).strip(),
        'crowdsec_api_key':      str(data.get('crowdsec_api_key', '')).strip(),
        'crowdsec_machine_id':       str(data.get('crowdsec_machine_id', '')).strip(),
        'crowdsec_machine_password': str(data.get('crowdsec_machine_password', '')).strip(),
        'crowdsec_client_cert':      str(data.get('crowdsec_client_cert', '')).strip(),
        'crowdsec_client_key':       str(data.get('crowdsec_client_key', '')).strip(),
        'crowdsec_ca_cert':          str(data.get('crowdsec_ca_cert', '')).strip(),
        'git_backup_enabled':    bool(data.get('git_backup_enabled', False)),
        'git_backup_repo':       str(data.get('git_backup_repo', '')).strip(),
        'git_backup_branch':     str(data.get('git_backup_branch', 'main')).strip() or 'main',
        'git_backup_username':   str(data.get('git_backup_username', '')).strip(),
        'git_backup_token':      str(data.get('git_backup_token', '')).strip(),
        'git_backup_auto_push':  bool(data.get('git_backup_auto_push', True)),
        'git_backup_commit_message': str(data.get('git_backup_commit_message', 'traefik-manager: {action} at {timestamp}')).strip() or 'traefik-manager: {action} at {timestamp}',
    }
    agents = load_agents()
    agents.append(agent)
    save_agents_file(agents)
    result = _redact_agent(agent)
    result['api_key_raw'] = raw_key
    return jsonify({'ok': True, 'agent': result})


def _agent_url_error(url: str) -> str:
    value = str(url or '').strip()
    if not value:
        return 'Agent URL must not be empty.'
    if not value.startswith(('http://', 'https://')):
        return 'Agent URL must start with http:// or https:// - without a scheme the agent cannot be reached.'
    rest = value.split('://', 1)[1]
    if not rest or rest.startswith('/'):
        return 'Agent URL must include a host, for example http://10.0.0.5:8090'
    return ''


@app.route('/api/agents/<agent_id>', methods=['PUT'])
@csrf_protect
@login_required
def api_agents_update(agent_id):
    data    = request.get_json(silent=True) or {}
    agents  = load_agents()
    if 'url' in data:
        url_err = _agent_url_error(str(data.get('url', '')).strip())
        if url_err:
            return jsonify({'ok': False, 'error': url_err}), 400
        data['url'] = str(data.get('url', '')).strip().rstrip('/')
    if 'name' in data:
        data['name'] = str(data.get('name', '')).strip()[:100]
        if not data['name']:
            return jsonify({'ok': False, 'error': 'Name must not be empty.'}), 400
    target  = next((a for a in agents if a.get('id') == agent_id), {})
    renames_derived_branch = ('name' in data
                              and target.get('git_host_backup')
                              and not str(target.get('git_host_branch') or '').strip())
    if 'git_host_branch' in data or data.get('git_host_backup') or renames_derived_branch:
        s = load_settings()
        probe = {**target, 'git_host_branch': ''}
        if 'name' in data:
            probe['name'] = data['name']
        branch = _safe_git_branch(str(data.get('git_host_branch', target.get('git_host_branch') or '')).strip() or _agent_git_branch(probe))
        enabled = bool(data.get('git_host_backup', target.get('git_host_backup')))
        if enabled:
            if branch == _safe_git_branch(s.get('git_backup_branch', 'main')):
                return jsonify({'ok': False, 'error': f'Branch "{branch}" is used by the Host - each server needs its own branch'}), 400
            for other in agents:
                if other.get('id') != agent_id and other.get('git_host_backup') and _agent_git_branch(other) == branch:
                    return jsonify({'ok': False, 'error': f'Branch "{branch}" is already used by agent "{other.get("name")}"'}), 400
        if 'git_host_branch' in data:
            data['git_host_branch'] = branch
    updated = False
    for i, a in enumerate(agents):
        if a.get('id') == agent_id:
            updatable = [
                'name', 'url', 'traefik_api_url', 'traefik_insecure_skip_verify',
                'cert_resolver',
                'config_path', 'static_config_path',
                'acme_json_path', 'access_log_path', 'plugins_dir', 'backup_dir', 'backup_keep_count',
                'restart_method', 'traefik_container', 'docker_host', 'signal_file_path',
                'crowdsec_lapi_url', 'crowdsec_machine_id',
                'crowdsec_client_cert', 'crowdsec_client_key', 'crowdsec_ca_cert',
                'git_backup_enabled', 'git_backup_repo',
                'git_backup_branch', 'git_backup_username', 'git_backup_auto_push',
                'git_backup_commit_message', 'tma_port', 'tma_rate_limit', 'domains',
                'git_host_backup', 'git_host_branch',
                'traefik_api_user', 'git_backup_commit_message',
                'install_method',
            ]
            for field in updatable:
                if field in data:
                    agents[i][field] = data[field]
            if 'visible_tabs' in data:
                agents[i]['visible_tabs'] = _settings.sanitize_visible_tabs(data['visible_tabs'])
            if 'traefik_api_password' in data and data['traefik_api_password'] not in ('', '***'):
                agents[i]['traefik_api_password'] = str(data['traefik_api_password'])
            if 'crowdsec_api_key' in data and data['crowdsec_api_key'] not in ('', '***'):
                agents[i]['crowdsec_api_key'] = str(data['crowdsec_api_key'])
            if 'crowdsec_machine_password' in data and data['crowdsec_machine_password'] not in ('', '***'):
                agents[i]['crowdsec_machine_password'] = str(data['crowdsec_machine_password'])
            if 'git_backup_token' in data and data['git_backup_token'] not in ('', '***'):
                agents[i]['git_backup_token'] = str(data['git_backup_token'])
            updated = True
            break
    if not updated:
        return jsonify({'error': 'Agent not found'}), 404
    save_agents_file(agents)
    return jsonify({'ok': True})


def _remove_agent_git_clone(agent_id: str) -> bool:
    try:
        target = os.path.abspath(_git_agent_repo_dir(agent_id))
        base   = os.path.abspath(env.BACKUP_DIR)
        if not target.startswith(base + os.sep):
            return False
        if not os.path.basename(target).startswith('git-agent-'):
            return False
        if not os.path.isdir(target):
            return False
        shutil.rmtree(target, ignore_errors=True)
        return True
    except Exception:
        logger.exception("Could not remove the git clone for agent %s" % agent_id)
        return False


def _forget_agent_settings(agent_id: str) -> bool:
    prefix = f"agent_{agent_id}::"
    s = load_settings()
    disabled = {k: v for k, v in (s.get('disabled_routes') or {}).items()
                if not str(k).startswith(prefix)}
    ledger   = {k: v for k, v in (s.get('managed_middlewares') or {}).items()
                if not str(k).startswith(prefix)}
    if (len(disabled) == len(s.get('disabled_routes') or {})
            and len(ledger) == len(s.get('managed_middlewares') or {})):
        return False
    save_settings(
        domains=s['domains'], cert_resolver=s['cert_resolver'],
        traefik_api_url=s['traefik_api_url'], auth_enabled=s['auth_enabled'],
        password_hash=s['password_hash'], visible_tabs=s['visible_tabs'],
        disabled_routes=disabled, managed_middlewares=ledger,
    )
    return True


@app.route('/api/agents/<agent_id>', methods=['DELETE'])
@csrf_protect
@login_required
def api_agents_delete(agent_id):
    before = load_agents()
    agents = [a for a in before if a.get('id') != agent_id]
    if len(agents) == len(before):
        return jsonify({'ok': True})
    save_agents_file(agents)
    _remove_agent_git_clone(agent_id)
    _forget_agent_settings(agent_id)
    return jsonify({'ok': True})


@app.route('/api/agents/<agent_id>/rotate-key', methods=['POST'])
@csrf_protect
@login_required
def api_agents_rotate_key(agent_id):
    try:
        agents = load_agents()
        idx    = next((i for i, a in enumerate(agents) if a.get('id') == agent_id), None)
        if idx is None:
            return jsonify({'error': 'Agent not found'}), 404
        raw_key = secrets.token_urlsafe(32)
        agents[idx] = dict(agents[idx])
        agents[idx]['api_key'] = raw_key
        save_agents_file(agents)
        result = _redact_agent(agents[idx])
        result['api_key_raw'] = raw_key
        return jsonify({'ok': True, 'agent': result})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/agents/<agent_id>/health', methods=['GET'])
@login_required
def api_agents_health(agent_id):
    agent = _agent_by_id(agent_id)
    if not agent:
        return jsonify({'error': 'Agent not found'}), 404
    try:
        t0   = time.time()
        resp = requests.get(agent['url'].rstrip('/') + '/health', timeout=5)
        ms   = int((time.time() - t0) * 1000)
        body = resp.json() if resp.headers.get('content-type', '').startswith('application/json') else {}
        return jsonify({'ok': resp.status_code == 200, 'latency_ms': ms, 'version': body.get('version', ''), 'status': resp.status_code})
    except requests.exceptions.SSLError as e:
        return jsonify({'ok': False, 'latency_ms': -1,
                        'error': 'TLS verification failed - the agent certificate is not trusted '
                                 'by Traefik Manager (%s)' % str(e)[:100]})
    except requests.exceptions.ConnectionError:
        return jsonify({'ok': False, 'latency_ms': -1, 'error': 'Connection refused'})
    except Exception as e:
        return jsonify({'ok': False, 'latency_ms': -1, 'error': str(e)})


_PROXY_HEADER_DENY = frozenset({
    'x-api-key', 'x-csrf-token', 'x-frame-options', 'x-powered-by',
})


@app.route('/api/agents/proxy/<agent_id>/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
@csrf_protect
@login_required
def api_agents_proxy(agent_id, path):
    agent = _agent_by_id(agent_id)
    if not agent:
        return jsonify({'error': 'Agent not found'}), 404
    try:
        kwargs = {}
        if request.content_type and 'json' in request.content_type:
            kwargs['json'] = request.get_json(silent=True)
        elif request.data:
            kwargs['data'] = request.data
        agent_path = '/api/' + path.lstrip('/')
        if request.query_string:
            kwargs['params'] = request.query_string
        resp = _agent_request(agent, request.method, agent_path, **kwargs)
        if (request.method in ('POST', 'PUT', 'DELETE') and resp.status_code < 400
                and not agent_path.startswith('/api/backup/git')
                and any(agent_path.startswith(x) for x in ('/api/configs', '/api/routes', '/api/middlewares', '/api/static', '/api/restore/', '/api/backup/'))):
            threading.Thread(target=lambda: _git_push_agent_if_enabled(agent, 'config change'), daemon=True).start()
        content_type = resp.headers.get('content-type', 'application/json')
        out_headers = {'Content-Type': content_type}
        for key, value in resp.headers.items():
            if key.lower().startswith('x-') and key.lower() not in _PROXY_HEADER_DENY:
                out_headers[key] = value
        return resp.content, resp.status_code, out_headers
    except requests.exceptions.SSLError as e:
        return jsonify({'error': 'TLS verification failed - the agent certificate is not trusted '
                                 'by Traefik Manager (%s)' % str(e)[:100]}), 502
    except requests.exceptions.ConnectionError:
        return jsonify({'error': 'Cannot reach agent - check URL and network'}), 502
    except requests.exceptions.Timeout:
        return jsonify({'error': 'Agent timed out'}), 504
    except Exception as e:
        logger.exception("Agent proxy error")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    logger.info("Development server starting...")
    app.run(host='0.0.0.0', port=5000, debug=False)
else:
    logger.info("🟢 Traefik Manager: Server is UP and Ready")

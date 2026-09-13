import functools
import os
import threading

from core import agents_store, config, crypto, env, locks
from core.env import logger


def serialized(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with locks.file_lock(env.SETTINGS_PATH):
            return fn(*args, **kwargs)
    return wrapper

OPTIONAL_TABS = ['dashboard', 'routemap', 'docker', 'kubernetes', 'swarm', 'nomad', 'ecs', 'consulcatalog', 'redis', 'etcd', 'consul', 'zookeeper', 'http_provider', 'file_external', 'internal', 'certs', 'tls', 'crowdsec', 'plugins', 'logs', 'static']


UI_PREF_BOOLS = (
    'showStatCards', 'compactStatCards', 'showEntrypoints',
    'showDocsLink', 'showApiLink', 'showShortcutsBtn', 'showIpDiagBtn',
    'showTraefikBadge', 'showTmBadge', 'showRouteIcons', 'logsAutoRefresh',
)
UI_PREF_VIEWS = ('routeViewMode', 'mwViewMode', 'svcViewMode')
UI_PREF_SCOPES = ('statBarScope',)
UI_PREF_LAYOUTS = ('layoutMode',)
UI_PREF_DENSITY = ('dashPodDensity',)
UI_PREF_PLACEMENTS = ('staticPlacement',)
STATIC_SECTION_KEYS = ('entrypoints', 'resolvers', 'providers', 'api', 'log', 'observability', 'system', 'plugins')
SETTINGS_SECTION_KEYS = ('connection', 'routes', 'system', 'auth', 'backups', 'ui',
                         'notifications', 'agents', 'agent-keys', 'about')
UI_PREF_SECTION_ALLOW = {
    'staticOpenSections': STATIC_SECTION_KEYS,
    'settingsOpenSections': SETTINGS_SECTION_KEYS,
}
UI_PREF_SECTION_LISTS = tuple(UI_PREF_SECTION_ALLOW)
UI_PREF_KEYS = (UI_PREF_BOOLS + UI_PREF_VIEWS + UI_PREF_SCOPES + UI_PREF_DENSITY
                + UI_PREF_LAYOUTS + UI_PREF_PLACEMENTS + UI_PREF_SECTION_LISTS)


def sanitize_visible_tabs(tabs) -> dict:
    if not isinstance(tabs, dict):
        return {}
    return {k: bool(v) for k, v in tabs.items() if k in OPTIONAL_TABS}


def sanitize_ui_prefs(prefs) -> dict:
    if not isinstance(prefs, dict):
        return {}
    out = {}
    for k in UI_PREF_BOOLS:
        if k in prefs:
            out[k] = bool(prefs[k])
    for k in UI_PREF_VIEWS:
        if k in prefs:
            v = str(prefs[k]).strip().lower()
            if v in ('grid', 'list'):
                out[k] = v
    for k in UI_PREF_SCOPES:
        if k in prefs:
            v = str(prefs[k]).strip().lower()
            if v in ('all', 'dashboard'):
                out[k] = v
    for k in UI_PREF_LAYOUTS:
        if k in prefs:
            v = str(prefs[k]).strip().lower()
            v = {'classic': 'fixed', 'modern': 'fluid'}.get(v, v)
            if v in ('fluid', 'fixed'):
                out[k] = v
    for k in UI_PREF_DENSITY:
        if k in prefs:
            v = str(prefs[k]).strip().lower()
            if v in ('list', 'icons'):
                out[k] = v
    for k in UI_PREF_PLACEMENTS:
        if k in prefs:
            v = str(prefs[k]).strip().lower()
            if v in ('off', 'settings', 'tab'):
                out[k] = v
    for k, allowed in UI_PREF_SECTION_ALLOW.items():
        if k in prefs and isinstance(prefs[k], list):
            seen = []
            for item in prefs[k]:
                s = str(item).strip()
                if s in allowed and s not in seen:
                    seen.append(s)
            out[k] = seen
    return out


CHANNEL_KINDS = ('discord', 'slack', 'ntfy', 'generic',
                 'gotify', 'pushover', 'pushbullet', 'telegram',
                 'unifiedpush')

CHANNEL_CATEGORIES = ('config', 'backup', 'security', 'traefik',
                      'certs', 'crowdsec', 'agent', 'update')

CHANNEL_SEVERITIES = ('info', 'success', 'warning', 'error')

CHANNEL_DIGESTS = ('immediate', 'hourly', 'daily')

_SECRET_KEEP = ('***',)


def _parse_channels(raw):
    out = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        try:
            kind = str(item.get('kind', '')).strip().lower()
            if kind not in CHANNEL_KINDS:
                continue
            cats = [c for c in (item.get('categories') or []) if c in CHANNEL_CATEGORIES]
            sev = str(item.get('min_severity', 'info')).strip().lower()
            digest = str(item.get('digest', 'immediate')).strip().lower()
            out.append({
                'id':            str(item.get('id', '')).strip()[:40] or _new_channel_id(),
                'name':          str(item.get('name', '')).strip()[:60] or kind.title(),
                'kind':          kind,
                'enabled':       bool(item.get('enabled', True)),
                'url':           str(item.get('url', '')).strip()[:500],
                'token':         crypto.decrypt_secret(item.get('token', '')),
                'token2':        crypto.decrypt_secret(item.get('token2', '')),
                'username':      str(item.get('username', '')).strip()[:100],
                'password':      crypto.decrypt_secret(item.get('password', '')),
                'categories':    cats or list(CHANNEL_CATEGORIES),
                'min_severity':  sev if sev in CHANNEL_SEVERITIES else 'info',
                'digest':        digest if digest in CHANNEL_DIGESTS else 'immediate',
                'quiet_hours':   str(item.get('quiet_hours', '')).strip()[:11],
                'break_through': bool(item.get('break_through', False)),
            })
        except Exception:
            continue
    return out


def _dump_channels(channels):
    out = []
    for c in channels or []:
        if not isinstance(c, dict):
            continue
        out.append({
            'id':            str(c.get('id', '')),
            'name':          str(c.get('name', '')),
            'kind':          str(c.get('kind', '')),
            'enabled':       bool(c.get('enabled', True)),
            'url':           str(c.get('url', '')),
            'token':         crypto.encrypt_secret(c.get('token', '')) if c.get('token') else '',
            'token2':        crypto.encrypt_secret(c.get('token2', '')) if c.get('token2') else '',
            'username':      str(c.get('username', '')),
            'password':      crypto.encrypt_secret(c.get('password', '')) if c.get('password') else '',
            'categories':    list(c.get('categories') or []),
            'min_severity':  str(c.get('min_severity', 'info')),
            'digest':        str(c.get('digest', 'immediate')),
            'quiet_hours':   str(c.get('quiet_hours', '')),
            'break_through': bool(c.get('break_through', False)),
        })
    return out


def _env_bool(name: str, fallback: bool) -> bool:
    raw = os.environ.get(name, '').strip().lower()
    if raw in ('1', 'true', 'yes', 'on'):
        return True
    if raw in ('0', 'false', 'no', 'off'):
        return False
    return fallback


def _new_channel_id():
    import secrets as _s
    return 'ch_' + _s.token_hex(4)


def load_settings() -> dict:
    defaults = {
        'domains':              [d.strip() for d in os.environ.get('DOMAINS', 'example.com').split(',') if d.strip()] or ['example.com'],
        'cert_resolver':        os.environ.get('CERT_RESOLVER', 'cloudflare'),
        'traefik_api_url':      os.environ.get('TRAEFIK_API_URL', 'http://traefik:8080'),
        'auth_enabled':         True,
        'auth_external_ack':    False,
        'password_hash':        '',
        'visible_tabs':         {t: False for t in OPTIONAL_TABS},
        'must_change_password': False,
        'setup_password_reset': False,
        'setup_complete':       False,
        'otp_secret':           '',
        'otp_enabled':          False,
        'disabled_routes':      {},
        'managed_middlewares':  {},
        'api_keys':             [],
        'api_key_enabled':      False,
        'self_route':           {'domain': '', 'service_url': ''},
        'acme_json_path':       '',
        'access_log_path':      '',
        'static_config_path':   '',
        'oidc_enabled':         _env_bool('OIDC_ENABLED', False),
        'oidc_provider_url':    os.environ.get('OIDC_PROVIDER_URL', ''),
        'oidc_client_id':       os.environ.get('OIDC_CLIENT_ID', ''),
        'oidc_client_secret':   os.environ.get('OIDC_CLIENT_SECRET', ''),
        'oidc_display_name':    os.environ.get('OIDC_DISPLAY_NAME', 'OIDC'),
        'oidc_allowed_emails':  os.environ.get('OIDC_ALLOWED_EMAILS', ''),
        'oidc_allowed_groups':  os.environ.get('OIDC_ALLOWED_GROUPS', ''),
        'oidc_groups_claim':    os.environ.get('OIDC_GROUPS_CLAIM', 'groups'),
        'oidc_allow_any_authenticated': _env_bool('OIDC_ALLOW_ANY_AUTHENTICATED', False),
        'oidc_auto_login':      _env_bool('OIDC_AUTO_LOGIN', False),
        'default_theme':        'dark',
        'ui_prefs':             {},
        'geoip_enabled':        False,
        'geoip_db_path':        '',
        'route_check_enabled':  True,
        'route_check_interval': 300,
        'provider_tabs_seen':   [],
        'cert_delete_enabled':  False,
        'notification_channels': [],
        'notifications_read_until': 0,
        'webhook_url':          '',
        'webhook_type':         'discord',
        'webhook_username':     '',
        'webhook_password':     '',
        'crowdsec_lapi_url':    '',
        'crowdsec_api_key':     '',
        'crowdsec_machine_id':       '',
        'crowdsec_machine_password': '',
        'crowdsec_client_cert':      '',
        'crowdsec_client_key':       '',
        'crowdsec_ca_cert':          '',
        'crowdsec_read_timeout':     '',
        'crowdsec_alert_limit':      '',
        'traefik_api_user':          os.environ.get('TRAEFIK_API_USER', ''),
        'traefik_api_password':      os.environ.get('TRAEFIK_API_PASSWORD', ''),
        'git_backup_enabled':        False,
        'git_backup_repo':           '',
        'git_backup_branch':         'main',
        'git_backup_username':       '',
        'git_backup_token':          '',
        'git_backup_commit_message': 'traefik-manager: {action} at {timestamp}',
        'git_backup_auto_push':      True,
        'agents':                    [],
        'agent_api_rate_limit':      int(os.environ.get('AGENT_API_RATE_LIMIT', 30)),
        'backup_keep_count':         int(os.environ.get('BACKUP_KEEP_COUNT', 0)),
    }
    if not os.path.exists(env.SETTINGS_PATH):
        return defaults
    try:
        with open(env.SETTINGS_PATH, 'r') as f:
            raw = f.read()
        try:
            data = config.yaml_safe.load(raw) or {}
        except Exception:
            import re as _re
            stripped = _re.sub(r'(?m)^[-\.]{3}\s*$\n?', '', raw)
            try:
                data = config.yaml_safe.load(stripped) or {}
            except Exception:
                data = {}
                for part in _re.split(r'(?m)^---\s*$', raw):
                    try:
                        doc = config.yaml_safe.load(part.strip())
                        if isinstance(doc, dict):
                            data.update(doc)
                    except Exception:
                        pass
        merged = defaults.copy()
        if 'domains' in data and isinstance(data['domains'], list):
            merged['domains'] = [str(d).strip() for d in data['domains'] if str(d).strip()]
        if 'cert_resolver' in data:
            merged['cert_resolver'] = str(data['cert_resolver']).strip()
        if 'traefik_api_url' in data:
            merged['traefik_api_url'] = config.safe_api_url(str(data['traefik_api_url'])) or defaults['traefik_api_url']
        if 'auth_enabled' in data:
            merged['auth_enabled'] = bool(data['auth_enabled'])
        if 'auth_external_ack' in data:
            merged['auth_external_ack'] = bool(data['auth_external_ack'])
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
        if 'setup_password_reset' in data:
            merged['setup_password_reset'] = bool(data['setup_password_reset'])
        if 'setup_complete' in data:
            merged['setup_complete'] = bool(data['setup_complete'])
        if 'otp_secret' in data:
            merged['otp_secret'] = crypto.decrypt_secret(str(data['otp_secret']).strip())
        if 'otp_enabled' in data:
            merged['otp_enabled'] = bool(data['otp_enabled'])
        else:
            if merged['password_hash']:
                merged['setup_complete'] = True
        if 'disabled_routes' in data and isinstance(data['disabled_routes'], dict):
            merged['disabled_routes'] = dict(data['disabled_routes'])
        if 'managed_middlewares' in data and isinstance(data['managed_middlewares'], dict):
            merged['managed_middlewares'] = dict(data['managed_middlewares'])
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
            merged['oidc_client_secret'] = crypto.decrypt_secret(str(data['oidc_client_secret']).strip())
        if 'oidc_display_name' in data:
            merged['oidc_display_name'] = str(data['oidc_display_name']).strip()
        if 'oidc_allowed_emails' in data:
            merged['oidc_allowed_emails'] = str(data['oidc_allowed_emails']).strip()
        if 'oidc_allowed_groups' in data:
            merged['oidc_allowed_groups'] = str(data['oidc_allowed_groups']).strip()
        if 'oidc_allow_any_authenticated' in data:
            merged['oidc_allow_any_authenticated'] = bool(data['oidc_allow_any_authenticated'])
        if 'oidc_groups_claim' in data:
            merged['oidc_groups_claim'] = str(data['oidc_groups_claim']).strip()
        if 'oidc_auto_login' in data:
            merged['oidc_auto_login'] = bool(data['oidc_auto_login'])
        if 'default_theme' in data:
            _dt = str(data['default_theme']).strip().lower()
            merged['default_theme'] = _dt if _dt in ('dark', 'light', 'system') else 'dark'
        if isinstance(data.get('ui_prefs'), dict):
            merged['ui_prefs'] = sanitize_ui_prefs(data['ui_prefs'])
        if 'geoip_enabled' in data:
            merged['geoip_enabled'] = bool(data['geoip_enabled'])
        if 'geoip_db_path' in data:
            merged['geoip_db_path'] = str(data['geoip_db_path']).strip()
        if 'route_check_enabled' in data:
            merged['route_check_enabled'] = bool(data['route_check_enabled'])
        if 'cert_delete_enabled' in data:
            merged['cert_delete_enabled'] = bool(data['cert_delete_enabled'])
        if 'provider_tabs_seen' in data and isinstance(data['provider_tabs_seen'], list):
            merged['provider_tabs_seen'] = [str(t) for t in data['provider_tabs_seen'] if str(t) in OPTIONAL_TABS]
        if 'route_check_interval' in data:
            try:
                merged['route_check_interval'] = int(data['route_check_interval'])
            except (TypeError, ValueError):
                pass
        if 'notifications_read_until' in data:
            try:
                merged['notifications_read_until'] = max(0, int(data['notifications_read_until']))
            except (TypeError, ValueError):
                merged['notifications_read_until'] = 0
        if 'notification_channels' in data and isinstance(data['notification_channels'], list):
            merged['notification_channels'] = _parse_channels(data['notification_channels'])
        elif str(data.get('webhook_url', '')).strip():
            merged['notification_channels'] = _parse_channels([{
                'id':       'legacy',
                'name':     'Webhook',
                'kind':     str(data.get('webhook_type', 'discord')).strip() or 'discord',
                'enabled':  True,
                'url':      str(data.get('webhook_url', '')).strip(),
                'username': str(data.get('webhook_username', '')).strip(),
                'password': data.get('webhook_password', ''),
            }])
        if 'webhook_url' in data:
            merged['webhook_url'] = str(data['webhook_url']).strip()
        if 'webhook_type' in data:
            merged['webhook_type'] = str(data['webhook_type']).strip()
        if 'webhook_username' in data:
            merged['webhook_username'] = str(data['webhook_username']).strip()
        if 'webhook_password' in data:
            merged['webhook_password'] = crypto.decrypt_secret(str(data['webhook_password']))
        if 'crowdsec_lapi_url' in data:
            merged['crowdsec_lapi_url'] = str(data['crowdsec_lapi_url']).strip()
        if 'crowdsec_api_key' in data:
            merged['crowdsec_api_key'] = crypto.decrypt_secret(str(data['crowdsec_api_key']))
        if 'crowdsec_machine_id' in data:
            merged['crowdsec_machine_id'] = str(data['crowdsec_machine_id']).strip()
        if 'crowdsec_machine_password' in data:
            merged['crowdsec_machine_password'] = crypto.decrypt_secret(str(data['crowdsec_machine_password']))
        for _ck in ('crowdsec_client_cert', 'crowdsec_client_key', 'crowdsec_ca_cert',
                    'crowdsec_read_timeout', 'crowdsec_alert_limit'):
            if _ck in data:
                merged[_ck] = str(data[_ck]).strip()
        if 'traefik_api_user' in data:
            merged['traefik_api_user'] = str(data['traefik_api_user']).strip()
        if 'traefik_api_password' in data:
            merged['traefik_api_password'] = crypto.decrypt_secret(str(data['traefik_api_password']))
        if 'git_backup_enabled' in data:
            merged['git_backup_enabled'] = bool(data['git_backup_enabled'])
        if 'git_backup_repo' in data:
            merged['git_backup_repo'] = str(data['git_backup_repo']).strip()
        if 'git_backup_branch' in data:
            merged['git_backup_branch'] = str(data['git_backup_branch']).strip() or 'main'
        if 'git_backup_username' in data:
            merged['git_backup_username'] = str(data['git_backup_username']).strip()
        if 'git_backup_token' in data:
            merged['git_backup_token'] = crypto.decrypt_secret(str(data['git_backup_token']))
        if 'git_backup_commit_message' in data:
            merged['git_backup_commit_message'] = str(data['git_backup_commit_message']).strip() or 'traefik-manager: {action} at {timestamp}'
        if 'git_backup_auto_push' in data:
            merged['git_backup_auto_push'] = bool(data['git_backup_auto_push'])
        merged['agents'] = agents_store.load_agents()
        if 'agent_api_rate_limit' in data:
            try:
                merged['agent_api_rate_limit'] = max(1, int(data['agent_api_rate_limit']))
            except Exception:
                pass
        if 'backup_keep_count' in data:
            try:
                merged['backup_keep_count'] = max(0, int(data['backup_keep_count']))
            except Exception:
                pass
        return merged
    except Exception as e:
        logger.warning(f"Could not load manager.yml, using defaults: {e}")
        return defaults

@serialized
def save_settings(domains, cert_resolver, traefik_api_url,
                  auth_enabled=True, auth_external_ack=None, password_hash='', visible_tabs=None,
                  must_change_password=None, setup_password_reset=None, setup_complete=None,
                  otp_secret=None, otp_enabled=None,
                  api_keys=None,
                  disabled_routes=None,
                  managed_middlewares=None,
                  self_route=None,
                  acme_json_path=None,
                  access_log_path=None,
                  static_config_path=None,
                  oidc_enabled=None, oidc_provider_url=None, oidc_client_id=None,
                  oidc_client_secret=None, oidc_display_name=None,
                  oidc_allowed_emails=None, oidc_allowed_groups=None,
                  oidc_allow_any_authenticated=None,
                  oidc_auto_login=None,
                  notification_channels=None, notifications_read_until=None,
                  oidc_groups_claim=None, webhook_url=None, webhook_type=None,
                  webhook_username=None, webhook_password=None,
                  crowdsec_lapi_url=None, crowdsec_api_key=None, crowdsec_alert_limit=None,
                  crowdsec_machine_id=None, crowdsec_machine_password=None,
                  crowdsec_client_cert=None, crowdsec_client_key=None,
                  crowdsec_ca_cert=None,
                  traefik_api_user=None, traefik_api_password=None,
                  git_backup_enabled=None, git_backup_repo=None,
                  git_backup_branch=None, git_backup_username=None,
                  git_backup_token=None, git_backup_commit_message=None,
                  git_backup_auto_push=None,
                  agent_api_rate_limit=None, backup_keep_count=None,
                  default_theme=None, ui_prefs=None,
                  geoip_enabled=None, geoip_db_path=None,
                  route_check_enabled=None, route_check_interval=None,
                  provider_tabs_seen=None, cert_delete_enabled=None):
    if visible_tabs is None:
        visible_tabs = {t: False for t in OPTIONAL_TABS}
    _cur = load_settings()
    if auth_external_ack is None:
        auth_external_ack = _cur.get('auth_external_ack', False)
    if must_change_password is None:
        must_change_password = _cur.get('must_change_password', False)
    if setup_password_reset is None:
        setup_password_reset = _cur.get('setup_password_reset', False)
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
    if managed_middlewares is None:
        managed_middlewares = _cur.get('managed_middlewares', {})
    if acme_json_path is None:
        acme_json_path = _cur.get('acme_json_path', '')
    if ui_prefs is None:
        ui_prefs = _cur.get('ui_prefs', {})
    ui_prefs = sanitize_ui_prefs(ui_prefs)
    if default_theme is None:
        default_theme = _cur.get('default_theme', 'dark')
    default_theme = str(default_theme).strip().lower()
    if default_theme not in ('dark', 'light', 'system'):
        default_theme = 'dark'
    if geoip_enabled is None:
        geoip_enabled = _cur.get('geoip_enabled', False)
    if geoip_db_path is None:
        geoip_db_path = _cur.get('geoip_db_path', '')
    if route_check_enabled is None:
        route_check_enabled = _cur.get('route_check_enabled', True)
    if route_check_interval is None:
        route_check_interval = _cur.get('route_check_interval', 300)
    if provider_tabs_seen is None:
        provider_tabs_seen = _cur.get('provider_tabs_seen', [])
    if cert_delete_enabled is None:
        cert_delete_enabled = _cur.get('cert_delete_enabled', False)
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
    if oidc_allow_any_authenticated is None:
        oidc_allow_any_authenticated = _cur.get('oidc_allow_any_authenticated', False)
    if oidc_groups_claim is None:
        oidc_groups_claim = _cur.get('oidc_groups_claim', 'groups')
    if oidc_auto_login is None:
        oidc_auto_login = _cur.get('oidc_auto_login', False)
    if notification_channels is None:
        notification_channels = _cur.get('notification_channels', [])
    if notifications_read_until is None:
        notifications_read_until = _cur.get('notifications_read_until', 0)
    if webhook_url is None:
        webhook_url = _cur.get('webhook_url', '')
    if webhook_type is None:
        webhook_type = _cur.get('webhook_type', 'discord')
    if webhook_username is None:
        webhook_username = _cur.get('webhook_username', '')
    if webhook_password is None:
        webhook_password = _cur.get('webhook_password', '')
    if crowdsec_lapi_url is None:
        crowdsec_lapi_url = _cur.get('crowdsec_lapi_url', '')
    if crowdsec_api_key is None:
        crowdsec_api_key = _cur.get('crowdsec_api_key', '')
    if crowdsec_alert_limit is None:
        crowdsec_alert_limit = _cur.get('crowdsec_alert_limit', '')
    if crowdsec_machine_id is None:
        crowdsec_machine_id = _cur.get('crowdsec_machine_id', '')
    if crowdsec_machine_password is None:
        crowdsec_machine_password = _cur.get('crowdsec_machine_password', '')
    if crowdsec_client_cert is None:
        crowdsec_client_cert = _cur.get('crowdsec_client_cert', '')
    if crowdsec_client_key is None:
        crowdsec_client_key = _cur.get('crowdsec_client_key', '')
    if crowdsec_ca_cert is None:
        crowdsec_ca_cert = _cur.get('crowdsec_ca_cert', '')
    if traefik_api_user is None:
        traefik_api_user = _cur.get('traefik_api_user', '')
    if traefik_api_password is None:
        traefik_api_password = _cur.get('traefik_api_password', '')
    if git_backup_enabled is None:
        git_backup_enabled = _cur.get('git_backup_enabled', False)
    if git_backup_repo is None:
        git_backup_repo = _cur.get('git_backup_repo', '')
    if git_backup_branch is None:
        git_backup_branch = _cur.get('git_backup_branch', 'main')
    if git_backup_username is None:
        git_backup_username = _cur.get('git_backup_username', '')
    if git_backup_token is None:
        git_backup_token = _cur.get('git_backup_token', '')
    if git_backup_commit_message is None:
        git_backup_commit_message = _cur.get('git_backup_commit_message', 'traefik-manager: {action} at {timestamp}')
    if git_backup_auto_push is None:
        git_backup_auto_push = _cur.get('git_backup_auto_push', True)
    if agent_api_rate_limit is None:
        agent_api_rate_limit = _cur.get('agent_api_rate_limit', int(os.environ.get('AGENT_API_RATE_LIMIT', 30)))
    if backup_keep_count is None:
        backup_keep_count = _cur.get('backup_keep_count', int(os.environ.get('BACKUP_KEEP_COUNT', 0)))
    otp_secret = crypto.encrypt_secret(otp_secret)
    oidc_client_secret_enc = crypto.encrypt_secret(oidc_client_secret) if oidc_client_secret else ''
    os.makedirs(os.path.dirname(env.SETTINGS_PATH), exist_ok=True)
    import json as _json
    def _plain(v):
        try:
            return _json.loads(_json.dumps(v, default=str))
        except Exception:
            return v
    tmp = f"{env.SETTINGS_PATH}.tmp.{os.getpid()}.{threading.get_ident()}"
    _doc = _plain({
        'domains':              domains,
        'cert_resolver':        cert_resolver,
        'traefik_api_url':      traefik_api_url,
        'auth_enabled':         auth_enabled,
        'auth_external_ack':    auth_external_ack,
        'password_hash':        password_hash,
        'visible_tabs':         visible_tabs,
        'must_change_password': must_change_password,
        'setup_password_reset': bool(setup_password_reset),
        'setup_complete':       setup_complete,
        'otp_secret':           otp_secret,
        'otp_enabled':          otp_enabled,
        'disabled_routes':      disabled_routes,
        'managed_middlewares':  managed_middlewares,
        'api_keys':             api_keys,
        'api_key_enabled':      len(list(api_keys)) > 0,
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
        'oidc_allow_any_authenticated': bool(oidc_allow_any_authenticated),
        'oidc_auto_login':      bool(oidc_auto_login),
        'default_theme':        default_theme,
        'ui_prefs':             ui_prefs,
        'geoip_enabled':        bool(geoip_enabled),
        'geoip_db_path':        str(geoip_db_path or '').strip(),
        'route_check_enabled':  bool(route_check_enabled),
        'route_check_interval': int(route_check_interval or 300),
        'provider_tabs_seen':   [str(t) for t in (provider_tabs_seen or []) if str(t) in OPTIONAL_TABS],
        'cert_delete_enabled':  bool(cert_delete_enabled),
        'oidc_groups_claim':    oidc_groups_claim,
        'notification_channels': _dump_channels(notification_channels),
        'notifications_read_until': int(notifications_read_until or 0),
        'webhook_url':          webhook_url,
        'webhook_type':         webhook_type,
        'webhook_username':     webhook_username,
        'webhook_password':     crypto.encrypt_secret(webhook_password) if webhook_password else '',
        'crowdsec_lapi_url':    crowdsec_lapi_url,
        'crowdsec_api_key':     crypto.encrypt_secret(crowdsec_api_key) if crowdsec_api_key else '',
        'crowdsec_alert_limit':  str(crowdsec_alert_limit or '').strip(),
        'crowdsec_machine_id':       crowdsec_machine_id,
        'crowdsec_machine_password': crypto.encrypt_secret(crowdsec_machine_password) if crowdsec_machine_password else '',
        'crowdsec_client_cert':      str(crowdsec_client_cert).strip(),
        'crowdsec_client_key':       str(crowdsec_client_key).strip(),
        'crowdsec_ca_cert':          str(crowdsec_ca_cert).strip(),
        'traefik_api_user':          traefik_api_user,
        'traefik_api_password':      crypto.encrypt_secret(traefik_api_password) if traefik_api_password else '',
        'git_backup_enabled':        git_backup_enabled,
        'git_backup_repo':           git_backup_repo,
        'git_backup_branch':         git_backup_branch,
        'git_backup_username':       git_backup_username,
        'git_backup_token':          crypto.encrypt_secret(git_backup_token) if git_backup_token else '',
        'git_backup_commit_message': git_backup_commit_message,
        'git_backup_auto_push':      git_backup_auto_push,
        'agent_api_rate_limit':      agent_api_rate_limit,
        'backup_keep_count':         backup_keep_count,
    })
    try:
        with open(tmp, 'w') as f:
            config.yaml.dump(_doc, f)
        os.replace(tmp, env.SETTINGS_PATH)
    finally:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass
    logger.info("Manager settings saved")


def _get_acme_json_path() -> str:
    s = load_settings()
    path = s.get('acme_json_path', '').strip() or os.environ.get('ACME_JSON_PATH', '/app/acme.json')
    if path:
        env.register_read_path(path)
    return path


def get_acme_json_paths() -> list:
    raw = _get_acme_json_path()
    out = []
    for part in (p.strip() for p in raw.split(',')):
        if not part:
            continue
        if os.path.isdir(part):
            try:
                for name in sorted(os.listdir(part)):
                    if name.endswith('.json'):
                        full = os.path.join(part, name)
                        if os.path.isfile(full) and full not in out:
                            out.append(full)
            except OSError as e:
                logger.warning(f"Could not list acme directory {part!r}: {e}")
        elif part not in out:
            out.append(part)
    return out

def _get_access_log_path() -> str:
    s = load_settings()
    path = s.get('access_log_path', '').strip() or os.environ.get('ACCESS_LOG_PATH', '/app/logs/access.log')
    if path:
        env.register_read_path(path)
    return path

def _get_static_config_path() -> str:
    s = load_settings()
    path = s.get('static_config_path', '').strip() or os.environ.get('STATIC_CONFIG_PATH', '')
    if path:
        env.register_static_path(path)
        env.register_read_path(path)
    return path

def _get_restart_method() -> str:
    return os.environ.get('RESTART_METHOD', 'proxy').lower()

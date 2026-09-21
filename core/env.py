import ipaddress
import logging
import os
import threading
import time

GITHUB_REPO = "chr0nzz/traefik-manager"
APP_VERSION = "1.14.2"

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)
logger = logging.getLogger("traefik-manager")


def base_path() -> str:
    raw = os.environ.get('BASE_PATH', '').strip().rstrip('/')
    if not raw:
        return ''
    if not raw.startswith('/') or raw.startswith('//') or '://' in raw:
        logger.warning(f"Ignoring BASE_PATH {raw!r}: it must be a path starting with a single /")
        return ''
    return raw


BASE_PATH = base_path()


def proxy_fix_hops() -> int:
    try:
        return max(0, int(os.environ.get('PROXY_FIX_HOPS', '1')))
    except ValueError:
        return 1


PROXY_FIX_HOPS = proxy_fix_hops()

DEFAULT_TRUSTED_PROXIES = '127.0.0.0/8,::1/128,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,fc00::/7,fe80::/10,100.64.0.0/10'

OIDC_REDIRECT_URI = os.environ.get('OIDC_REDIRECT_URI', '').strip()


def trusted_proxies():
    raw = os.environ.get('TRUSTED_PROXIES', '').strip() or DEFAULT_TRUSTED_PROXIES
    if raw == '*':
        return '*'
    networks = []
    for part in raw.split(','):
        part = part.strip()
        if not part:
            continue
        try:
            networks.append(ipaddress.ip_network(part, strict=False))
        except ValueError:
            logger.warning(f"TRUSTED_PROXIES: ignoring {part!r}, it is not an IP address or network")
    return networks


TRUSTED_PROXIES = trusted_proxies()


def trusted_proxies_list():
    return ['*'] if TRUSTED_PROXIES == '*' else [str(n) for n in TRUSTED_PROXIES]


def peer_is_trusted(addr) -> bool:
    if TRUSTED_PROXIES == '*':
        return True
    try:
        ip = ipaddress.ip_address(str(addr or '').split('%')[0])
    except ValueError:
        return False
    mapped = getattr(ip, 'ipv4_mapped', None)
    if mapped:
        ip = mapped
    return any(ip.version == net.version and ip in net for net in TRUSTED_PROXIES)


DEFAULT_LOGIN_FAILURE_LIMIT = '30 per minute;200 per hour'
DEFAULT_OTP_FAILURE_LIMIT = '10 per minute;30 per hour'


def failure_limit(name, default) -> str:
    raw = os.environ.get(name)
    if raw is None:
        return default
    raw = raw.strip()
    if raw.lower() in ('', '0', 'off', 'false', 'none'):
        return ''
    try:
        from limits import parse_many
        if not parse_many(raw):
            raise ValueError(raw)
    except Exception:
        logger.warning(f"{name}: {raw!r} is not a rate limit like '30 per minute;200 per hour', using {default!r}")
        return default
    return raw


LOGIN_FAILURE_LIMIT = failure_limit('LOGIN_FAILURE_LIMIT', DEFAULT_LOGIN_FAILURE_LIMIT)
OTP_FAILURE_LIMIT = failure_limit('OTP_FAILURE_LIMIT', DEFAULT_OTP_FAILURE_LIMIT)

BACKUP_DIR         = os.environ.get('BACKUP_DIR',    '/app/backups')
SETTINGS_PATH      = os.environ.get('SETTINGS_PATH', '/app/config/manager.yml')
CONFIG_DIR         = os.path.dirname(os.path.abspath(SETTINGS_PATH))
GROUPS_CACHE_DIR   = os.path.join(CONFIG_DIR, 'cache')
GEOIP_DIR          = os.path.join(CONFIG_DIR, 'geoip')
GROUPS_CONFIG_FILE = os.path.join(CONFIG_DIR, 'dashboard.yml')
NOTIFICATIONS_PATH = os.path.join(CONFIG_DIR, 'notifications.yml')
AGENTS_PATH        = os.path.join(CONFIG_DIR, 'agents.yml')
TEMPLATES_PATH     = os.path.join(CONFIG_DIR, 'templates.yml')
OTP_KEY_PATH       = os.path.join(CONFIG_DIR, '.otp_key')
SECRET_KEY_PATH    = os.path.join(CONFIG_DIR, '.secret_key')

os.makedirs(GROUPS_CACHE_DIR, exist_ok=True)

OWN_STATE_NAMES = ('manager.yml', 'notifications.yml', 'agents.yml', 'templates.yml', 'dashboard.yml')
OWN_STATE_SUBDIRS = ('cache', 'geoip')


def own_state(settings_path=None, backup_dir=None):
    settings = os.path.abspath(settings_path or SETTINGS_PATH)
    base     = os.path.dirname(settings)
    files    = {settings} | {os.path.join(base, n) for n in OWN_STATE_NAMES}
    dirs     = {backup_dir or BACKUP_DIR} | {os.path.join(base, d) for d in OWN_STATE_SUBDIRS}
    return {os.path.realpath(f) for f in files}, {os.path.realpath(d) for d in dirs if d}


def is_own_state(path, settings_path=None, backup_dir=None) -> bool:
    files, dirs = own_state(settings_path, backup_dir)
    real = os.path.realpath(path)
    return real in files or any(real.startswith(d + os.sep) for d in dirs)


def scan_config_dir(config_dir, settings_path=None, backup_dir=None) -> list:
    import glob as _glob
    found = _glob.glob(os.path.join(config_dir, '**', '*.yml'), recursive=True)
    found += _glob.glob(os.path.join(config_dir, '**', '*.yaml'), recursive=True)
    return sorted(p for p in found if not is_own_state(p, settings_path, backup_dir))


_config_dir = os.environ.get('CONFIG_DIR', '').strip()
ACTIVE_CONFIG_DIR = _config_dir
if _config_dir:
    CONFIG_PATHS = scan_config_dir(_config_dir) or [os.path.join(_config_dir, 'dynamic.yml')]
else:
    _raw_paths = os.environ.get('CONFIG_PATHS', '').strip()
    if _raw_paths:
        CONFIG_PATHS = [p.strip() for p in _raw_paths.split(',') if p.strip()]
    else:
        CONFIG_PATHS = [os.environ.get('CONFIG_PATH', '/app/config/dynamic.yml')]

CONFIG_PATH  = CONFIG_PATHS[0]
MULTI_CONFIG = len(CONFIG_PATHS) > 1

CONFIG_SCAN_TTL    = 2.0
_config_scan_lock  = threading.Lock()
_config_scan_at    = 0.0
_config_scan_mtime = 0


def _probe_writable(path: str) -> str:
    if os.path.isfile(path):
        return '' if os.access(path, os.W_OK) else f'no write permission on {path}'
    if not os.path.isdir(path):
        try:
            os.makedirs(path, exist_ok=True)
        except Exception as e:
            return f'cannot be created: {e}'
    probe = os.path.join(path, f'.tm-write-probe.{os.getpid()}')
    try:
        with open(probe, 'w') as fh:
            fh.write('probe')
        os.remove(probe)
    except Exception as e:
        return str(e)
    return ''


def storage_targets():
    seen = []
    def _add(label, path):
        full = os.path.abspath(path)
        if all(full != p for _l, p in seen):
            seen.append((label, full))
    _add('Configuration', CONFIG_DIR)
    _add('Backups', BACKUP_DIR)
    for _p in CONFIG_PATHS:
        _add('Dynamic config', os.path.dirname(os.path.abspath(_p)))
    for _p in STATIC_CONFIG_DIRS:
        full = os.path.abspath(_p)
        _add('Static config', full if os.path.isfile(full) else os.path.dirname(full))
    return seen


def unwritable_storage():
    return [(label, path, err)
            for label, path in storage_targets()
            if (err := _probe_writable(path))]

ALLOWED_API_SCHEMES = ('http://', 'https://')


STATIC_CONFIG_DIRS = []
if os.environ.get('STATIC_CONFIG_PATH', '').strip():
    STATIC_CONFIG_DIRS.append(os.environ['STATIC_CONFIG_PATH'].strip())


def allowed_file_prefixes() -> tuple:
    return tuple(sorted(set(
        [os.path.abspath(BACKUP_DIR) + '/',
         os.path.dirname(os.path.abspath(SETTINGS_PATH)) + '/'] +
        [os.path.dirname(os.path.abspath(p)) + '/' for p in CONFIG_PATHS] +
        [os.path.dirname(os.path.abspath(p)) + '/' for p in STATIC_CONFIG_DIRS]
    )))


ALLOWED_FILE_PREFIXES = allowed_file_prefixes()


ALLOWED_FILES = []
READ_PATHS = []
_ENV_STATIC_DIRS = list(STATIC_CONFIG_DIRS)
_SETTINGS_PATHS = {}
_settings_paths_lock = threading.Lock()


def set_settings_paths(kind: str, path: str):
    global STATIC_CONFIG_DIRS, ALLOWED_FILE_PREFIXES, ALLOWED_FILES, READ_PATHS
    parts = [p.strip() for p in str(path or '').split(',') if p.strip()]
    with _settings_paths_lock:
        _SETTINGS_PATHS[kind] = parts
        static = _SETTINGS_PATHS.get('static', [])
        read   = sorted({p for group in _SETTINGS_PATHS.values() for p in group})
        files  = sorted({os.path.realpath(p) for p in static if not os.path.isdir(p)})
        dirs   = sorted(set(_ENV_STATIC_DIRS) | {p for p in static if os.path.isdir(p)})
        if read != READ_PATHS:
            READ_PATHS = read
        if files != ALLOWED_FILES:
            ALLOWED_FILES = files
        if dirs != STATIC_CONFIG_DIRS:
            STATIC_CONFIG_DIRS = dirs
            ALLOWED_FILE_PREFIXES = allowed_file_prefixes()


def register_config_path(path: str):
    global CONFIG_PATHS, CONFIG_PATH, MULTI_CONFIG, ALLOWED_FILE_PREFIXES
    if path and path not in CONFIG_PATHS:
        CONFIG_PATHS = sorted(CONFIG_PATHS + [path])
        CONFIG_PATH  = CONFIG_PATHS[0]
        MULTI_CONFIG = len(CONFIG_PATHS) > 1
        ALLOWED_FILE_PREFIXES = allowed_file_prefixes()


def _apply_config_paths(paths):
    global CONFIG_PATHS, CONFIG_PATH, MULTI_CONFIG, ALLOWED_FILE_PREFIXES
    if paths == CONFIG_PATHS:
        return CONFIG_PATHS
    CONFIG_PATHS = paths
    CONFIG_PATH  = CONFIG_PATHS[0]
    MULTI_CONFIG = len(CONFIG_PATHS) > 1
    ALLOWED_FILE_PREFIXES = allowed_file_prefixes()
    return CONFIG_PATHS


def _config_dir_mtime() -> int:
    try:
        return os.stat(ACTIVE_CONFIG_DIR).st_mtime_ns
    except OSError:
        return 0


def _scan_is_current(mtime: int) -> bool:
    return mtime == _config_scan_mtime and time.monotonic() - _config_scan_at < CONFIG_SCAN_TTL


def refresh_config_paths(force: bool = False):
    global _config_scan_at, _config_scan_mtime
    if not ACTIVE_CONFIG_DIR:
        return CONFIG_PATHS
    mtime = _config_dir_mtime()
    if not force and _scan_is_current(mtime):
        return CONFIG_PATHS
    with _config_scan_lock:
        if not force and _scan_is_current(mtime):
            return CONFIG_PATHS
        _config_scan_at    = time.monotonic()
        _config_scan_mtime = mtime
        try:
            found = scan_config_dir(ACTIVE_CONFIG_DIR)
        except OSError as e:
            logger.warning(f"Could not rescan {ACTIVE_CONFIG_DIR}: {e}")
            return CONFIG_PATHS
        inside = os.path.abspath(ACTIVE_CONFIG_DIR) + os.sep
        kept   = [p for p in CONFIG_PATHS if not os.path.abspath(p).startswith(inside)]
        paths  = sorted(set(found) | set(kept))
        return _apply_config_paths(paths or [os.path.join(ACTIVE_CONFIG_DIR, 'dynamic.yml')])

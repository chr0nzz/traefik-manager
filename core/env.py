import logging
import os

GITHUB_REPO = "chr0nzz/traefik-manager"
APP_VERSION = "1.13.3"

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
        ['/app/',
         os.path.abspath(BACKUP_DIR) + '/',
         os.path.dirname(os.path.abspath(SETTINGS_PATH)) + '/'] +
        [os.path.dirname(os.path.abspath(p)) + '/' for p in CONFIG_PATHS] +
        [os.path.dirname(os.path.abspath(p)) + '/' for p in STATIC_CONFIG_DIRS]
    )))


ALLOWED_FILE_PREFIXES = allowed_file_prefixes()


ALLOWED_FILES = []


def register_static_path(path: str):
    global STATIC_CONFIG_DIRS, ALLOWED_FILE_PREFIXES, ALLOWED_FILES
    if not path:
        return
    if os.path.isdir(path):
        if path not in STATIC_CONFIG_DIRS:
            STATIC_CONFIG_DIRS = sorted(STATIC_CONFIG_DIRS + [path])
            ALLOWED_FILE_PREFIXES = allowed_file_prefixes()
        return
    real = os.path.realpath(path)
    if real not in ALLOWED_FILES:
        ALLOWED_FILES = sorted(ALLOWED_FILES + [real])


READ_PATHS = []


def register_read_path(path: str):
    global READ_PATHS
    for part in str(path or '').split(','):
        part = part.strip()
        if part and part not in READ_PATHS:
            READ_PATHS = sorted(READ_PATHS + [part])


def register_config_path(path: str):
    global CONFIG_PATHS, CONFIG_PATH, MULTI_CONFIG, ALLOWED_FILE_PREFIXES
    if path and path not in CONFIG_PATHS:
        CONFIG_PATHS = sorted(CONFIG_PATHS + [path])
        CONFIG_PATH  = CONFIG_PATHS[0]
        MULTI_CONFIG = len(CONFIG_PATHS) > 1
        ALLOWED_FILE_PREFIXES = allowed_file_prefixes()

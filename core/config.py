import errno
import os
import re
import shutil
import threading
from io import StringIO

from ruamel.yaml import YAML

from core import env
from core.env import logger


class ThreadLocalYAML:
    def __init__(self, typ=None):
        self._tl = threading.local()
        self._typ = typ

    def _y(self):
        y = getattr(self._tl, 'y', None)
        if y is None:
            if self._typ:
                y = YAML(typ=self._typ)
            else:
                y = YAML()
                y.preserve_quotes = True
                y.indent(mapping=2, sequence=4, offset=2)
                y.width = 4096
            self._tl.y = y
        return y

    def load(self, stream):
        return self._y().load(stream)

    def dump(self, data, stream):
        return self._y().dump(data, stream)


yaml = ThreadLocalYAML()
yaml_safe = ThreadLocalYAML(typ='safe')


_INPLACE_PATHS = set()


def _replace_or_copy(tmp: str, path: str):
    if os.path.exists(path):
        shutil.copystat(path, tmp)
    try:
        os.replace(tmp, path)
    except OSError as e:
        if e.errno not in (errno.EBUSY, errno.EXDEV):
            raise
        if path not in _INPLACE_PATHS:
            _INPLACE_PATHS.add(path)
            logger.info(f"{path} is a bind-mounted file, writing through it in place")
        shutil.copyfile(tmp, path)


def safe_file_path(path: str) -> str:
    if not path:
        return ''
    resolved = os.path.realpath(path)
    if resolved in getattr(env, 'ALLOWED_FILES', []):
        return resolved
    if any(resolved.startswith(p) for p in env.ALLOWED_FILE_PREFIXES):
        return resolved
    logger.warning(f"Blocked unsafe file path: {path!r}")
    return ''


def readable_config_path(path: str) -> str:
    if not path:
        return ''
    resolved = os.path.realpath(path)
    allowed  = list(env.ALLOWED_FILE_PREFIXES)
    exact    = []
    from_env = []
    for ev in ('STATIC_CONFIG_PATH', 'ACCESS_LOG_PATH', 'ACME_JSON_PATH', 'PLUGINS_DIR'):
        from_env.extend(os.environ.get(ev, '').split(','))
    for part, trusted in ([(p, True) for p in from_env]
                          + [(p, False) for p in getattr(env, 'READ_PATHS', [])]):
        part = part.strip()
        if not part:
            continue
        real = os.path.realpath(part)
        if not trusted and not os.path.isdir(real):
            exact.append(real)
            continue
        base = real if os.path.isdir(real) else os.path.dirname(real)
        if base and base != os.sep:
            allowed.append(base.rstrip(os.sep) + os.sep)
        else:
            exact.append(real)
    if resolved in exact or any(resolved.startswith(p) for p in allowed):
        return resolved
    logger.warning(f"Blocked read of unsafe path: {path!r}")
    return ''


def is_safe_path(path: str) -> bool:
    if not env.ACTIVE_CONFIG_DIR:
        return False
    try:
        return os.path.realpath(path).startswith(os.path.realpath(env.ACTIVE_CONFIG_DIR) + os.sep)
    except Exception:
        return False


def resolve_config_path(s: str) -> str:
    if not s:
        return env.CONFIG_PATH
    s = s.strip()
    for p in env.CONFIG_PATHS:
        if s == p or s == os.path.basename(p):
            return p
    if env.ACTIVE_CONFIG_DIR and '/' not in s and '\\' not in s:
        if not s.endswith(('.yml', '.yaml')):
            s = s + '.yml'
        candidate = os.path.join(env.ACTIVE_CONFIG_DIR, s)
        if is_safe_path(candidate):
            return candidate
    logger.warning(f"Config file not in CONFIG_PATHS: {s!r}")
    return ''


def safe_api_url(url: str) -> str:
    url = url.strip()
    if any(url.startswith(s) for s in env.ALLOWED_API_SCHEMES):
        return url
    logger.warning(f"Blocked unsafe API URL: {url!r}")
    return ''


def sanitize_go_templates(raw):
    mapping = {}
    counter = [0]

    def _replace(m):
        key = f'__TM_TEMPLATE_{counter[0]}__'
        mapping[key] = m.group(0)
        counter[0] += 1
        return key
    return re.sub(r'\{\{[^}]*\}\}', _replace, raw), mapping


def restore_go_templates(obj, mapping):
    if not mapping:
        return obj
    if isinstance(obj, str):
        for ph, orig in mapping.items():
            obj = obj.replace(ph, orig)
        return obj
    if isinstance(obj, dict):
        return {k: restore_go_templates(v, mapping) for k, v in obj.items()}
    if isinstance(obj, list):
        return [restore_go_templates(item, mapping) for item in obj]
    return obj


def load_config(path=None):
    if path is None:
        path = env.CONFIG_PATH
    if not os.path.exists(path):
        return {}
    with open(path, 'r') as f:
        raw = f.read()
    sanitized, _ = sanitize_go_templates(raw)
    data = yaml.load(sanitized)
    return data if data and isinstance(data, dict) else {}


def strip_empty_sections(config: dict) -> dict:
    for proto in ('http', 'tcp', 'udp'):
        if proto in config:
            for section in ('routers', 'services', 'middlewares', 'serversTransports'):
                if section in config[proto] and not config[proto][section]:
                    del config[proto][section]
            if not config[proto]:
                del config[proto]
    if 'tls' in config and isinstance(config['tls'], dict):
        for section in ('options', 'certificates', 'stores'):
            if section in config['tls'] and not config['tls'][section]:
                del config['tls'][section]
        if not config['tls']:
            del config['tls']
    return config


def save_config(data, path=None):
    if path is None:
        path = env.CONFIG_PATH
    template_map = {}
    if os.path.exists(path):
        with open(path, 'r') as f:
            _, template_map = sanitize_go_templates(f.read())
    stream = StringIO()
    yaml.dump(data, stream)
    content = stream.getvalue()
    for placeholder, original in template_map.items():
        content = content.replace(placeholder, original)
    tmp = f"{path}.tmp.{os.getpid()}.{threading.get_ident()}"
    try:
        with open(tmp, 'w') as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        _replace_or_copy(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
    logger.info(f"Configuration saved: {path}")


_RULE_HOST_RE = re.compile(r'(!?)\s*Host\(`([^`]+)`\)')

_RULE_HOST_ANY_RE = re.compile(
    r'(!?)\s*\b(?:Host|HostSNI)\(\s*((?:(?:`[^`]*`|"(?:[^"\\]|\\.)*")\s*,?\s*)+)\)', re.IGNORECASE)
_RULE_VALUE_RE  = re.compile(r'`([^`]*)`|"((?:[^"\\]|\\.)*)"')
_RULE_REGEXP_RE = re.compile(r'\b(?:HostRegexp|HostSNIRegexp)\s*\(', re.IGNORECASE)


def rule_hosts(rule) -> list:
    return [m.group(2) for m in _RULE_HOST_RE.finditer(str(rule or '')) if m.group(1) != '!']


def rule_host_patterns(rule) -> tuple:
    text = str(rule or '')
    hosts = []
    for match in _RULE_HOST_ANY_RE.finditer(text):
        if match.group(1) == '!':
            continue
        for backtick, quoted in _RULE_VALUE_RE.findall(match.group(2)):
            value = (backtick or quoted).replace('\\"', '"').strip()
            if value:
                hosts.append(value)
    return hosts, bool(_RULE_REGEXP_RE.search(text))


def svc_key(name):
    if not isinstance(name, str):
        return ''
    return name.split('@')[0] if '@' in name else name


def as_dict(val):
    return val if isinstance(val, dict) else {}


def _load_config_display(path):
    if not os.path.exists(path):
        return {}
    with open(path, 'r') as f:
        raw = f.read()
    sanitized, mapping = sanitize_go_templates(raw)
    try:
        data = yaml.load(sanitized)
    except Exception:
        _y2 = YAML()
        _y2.allow_duplicate_keys = True
        try:
            data = _y2.load(sanitized)
        except Exception:
            return {}
    if not data or not isinstance(data, dict):
        return {}
    return restore_go_templates(data, mapping) if mapping else data


def _get_config_parse_errors():
    errors = []
    for p in env.CONFIG_PATHS:
        if not os.path.exists(p):
            continue
        try:
            with open(p, 'r') as f:
                raw = f.read()
            sanitized, _ = sanitize_go_templates(raw)
            _y = YAML()
            _y.load(sanitized)
        except Exception as e:
            msg = str(e)
            first_line = next((l.strip() for l in msg.splitlines() if l.strip()), msg)
            errors.append({'file': os.path.basename(p), 'error': first_line})
    return errors

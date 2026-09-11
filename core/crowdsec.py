import hashlib
import json
import os
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import requests

from core import env
from core import settings as settings_mod
from core.env import logger

try:
    import fcntl
except ImportError:
    fcntl = None

_cs_jwt_cache = {'token': '', 'expiry': None}

CS_STREAM_RESYNC_SECONDS = 3600
CS_STREAM_WRITE_SECONDS = 300
CS_STREAM_FRESH_DEFAULT = 5
_cs_stream_lock = threading.Lock()
_cs_stream_cache = {'fp': '', 'items': {}, 'synced': None, 'ready': False, 'streamable': True}

CS_CONNECT_TIMEOUT_DEFAULT = 5
CS_READ_TIMEOUT_DEFAULT = 20


def _cs_int_env(name: str, fallback: int, lo: int, hi: int) -> int:
    try:
        v = int(str(os.environ.get(name, '')).strip() or fallback)
    except ValueError:
        return fallback
    return max(lo, min(hi, v))


def cs_timeout():
    s = settings_mod.load_settings()
    try:
        read = int(str(s.get('crowdsec_read_timeout', '')).strip() or 0)
    except ValueError:
        read = 0
    if read <= 0:
        read = _cs_int_env('CROWDSEC_READ_TIMEOUT', CS_READ_TIMEOUT_DEFAULT, 1, 25)
    return (_cs_int_env('CROWDSEC_CONNECT_TIMEOUT', CS_CONNECT_TIMEOUT_DEFAULT, 1, 30),
            max(1, min(25, read)))


CS_ALERT_LIMIT_DEFAULT = 500


def cs_alert_limit() -> int:
    s = settings_mod.load_settings()
    try:
        v = int(str(s.get('crowdsec_alert_limit', '')).strip() or -1)
    except ValueError:
        v = -1
    if v < 0:
        v = _cs_int_env('CROWDSEC_ALERT_LIMIT', CS_ALERT_LIMIT_DEFAULT, 0, 100000)
    return max(0, min(100000, v))


def _cs_lapi_url() -> str:
    s = settings_mod.load_settings()
    return s.get('crowdsec_lapi_url', '').strip() or os.environ.get('CROWDSEC_LAPI_URL', '').strip()


def _cs_api_key() -> str:
    s = settings_mod.load_settings()
    return s.get('crowdsec_api_key', '').strip() or os.environ.get('CROWDSEC_API_KEY', '').strip()


def _cs_machine_id() -> str:
    s = settings_mod.load_settings()
    return s.get('crowdsec_machine_id', '').strip() or os.environ.get('CROWDSEC_MACHINE_ID', '').strip()


def _cs_machine_password() -> str:
    s = settings_mod.load_settings()
    return s.get('crowdsec_machine_password', '').strip() or os.environ.get('CROWDSEC_MACHINE_PASSWORD', '').strip()


def _cs_client_cert() -> str:
    s = settings_mod.load_settings()
    return s.get('crowdsec_client_cert', '').strip() or os.environ.get('CROWDSEC_CLIENT_CERT', '').strip()


def _cs_client_key() -> str:
    s = settings_mod.load_settings()
    return s.get('crowdsec_client_key', '').strip() or os.environ.get('CROWDSEC_CLIENT_KEY', '').strip()


def _cs_ca_cert() -> str:
    s = settings_mod.load_settings()
    return s.get('crowdsec_ca_cert', '').strip() or os.environ.get('CROWDSEC_CA_CERT', '').strip()


def _cs_has_cert() -> bool:
    return bool(_cs_client_cert() and _cs_client_key())


def _cs_tls_kwargs() -> dict:
    kw = {}
    if _cs_has_cert():
        kw['cert'] = (_cs_client_cert(), _cs_client_key())
    ca = _cs_ca_cert()
    if ca:
        kw['verify'] = ca
    return kw


def _cs_has_machine() -> bool:
    return bool(_cs_machine_id() and _cs_machine_password()) or _cs_has_cert()


class CrowdSecUnavailable(Exception):
    def __init__(self, message, status=0):
        super().__init__(message)
        self.status = status


def _cs_request_strict(method: str, path: str, lapi: str = None, key: str = None, **kwargs):
    if lapi is None:
        lapi = _cs_lapi_url()
    if key is None:
        key = _cs_api_key()
    lapi = (lapi or '').rstrip('/')
    if not lapi or not (key or _cs_has_cert()):
        raise CrowdSecUnavailable('CrowdSec LAPI URL, bouncer API key or client certificate is not set')
    headers = {'Accept': 'application/json'}
    if key:
        headers['X-Api-Key'] = key
    try:
        resp = requests.request(method, f"{lapi}{path}",
                                headers=headers,
                                timeout=cs_timeout(), **_cs_tls_kwargs(), **kwargs)
        resp.raise_for_status()
    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else '?'
        logger.warning(f"CrowdSec LAPI error {method} {path}: {e}")
        raise CrowdSecUnavailable(f'LAPI answered HTTP {status} on {path}') from e
    except Exception as e:
        logger.warning(f"CrowdSec LAPI error {method} {path}: {e}")
        raise CrowdSecUnavailable(f'CrowdSec LAPI unreachable: {e}') from e
    return resp.json() if resp.content else None


def _cs_request(method: str, path: str, lapi: str = None, key: str = None, **kwargs):
    try:
        return _cs_request_strict(method, path, lapi=lapi, key=key, **kwargs)
    except CrowdSecUnavailable:
        return None


def _cs_jwt(lapi: str = None) -> str:
    if lapi is None:
        lapi = _cs_lapi_url()
    lapi = lapi.rstrip('/')
    mid  = _cs_machine_id()
    pw   = _cs_machine_password()
    if not (lapi and ((mid and pw) or _cs_has_cert())):
        return ''
    now = datetime.now(timezone.utc)
    if _cs_jwt_cache['token'] and _cs_jwt_cache['expiry'] and now < _cs_jwt_cache['expiry']:
        return _cs_jwt_cache['token']
    payload = {'scenarios': []}
    if mid and pw:
        payload['machine_id'] = mid
        payload['password'] = pw
    try:
        resp = requests.post(f"{lapi}/v1/watchers/login",
                             json=payload,
                             timeout=cs_timeout(), **_cs_tls_kwargs())
        resp.raise_for_status()
        body  = resp.json() or {}
        token = body.get('token', '')
        if not token:
            return ''
        _cs_jwt_cache['token'] = token
        try:
            exp = datetime.fromisoformat(str(body.get('expire', '')).replace('Z', '+00:00'))
            _cs_jwt_cache['expiry'] = exp - timedelta(minutes=2)
        except Exception:
            _cs_jwt_cache['expiry'] = now + timedelta(minutes=58)
        return token
    except Exception as e:
        logger.warning(f"CrowdSec machine login failed: {e}")
        return ''


def cs_jwt_reset():
    _cs_jwt_cache['token'] = ''
    _cs_jwt_cache['expiry'] = None


def _cs_machine_send(lapi: str, token: str, method: str, path: str, **kwargs):
    return requests.request(method, f"{lapi}{path}",
                            headers={'Authorization': f'Bearer {token}', 'Accept': 'application/json'},
                            timeout=cs_timeout(), **_cs_tls_kwargs(), **kwargs)


def _cs_machine_request(method: str, path: str, **kwargs):
    lapi  = _cs_lapi_url().rstrip('/')
    token = _cs_jwt(lapi)
    if not (lapi and token):
        return None
    try:
        resp = _cs_machine_send(lapi, token, method, path, **kwargs)
        if resp.status_code == 401:
            logger.info("CrowdSec refused the machine token, logging in again")
            cs_jwt_reset()
            token = _cs_jwt(lapi)
            if not token:
                return None
            resp = _cs_machine_send(lapi, token, method, path, **kwargs)
        resp.raise_for_status()
        return resp.json() if resp.content else {}
    except Exception as e:
        logger.warning(f"CrowdSec machine request error {method} {path}: {e}")
        return None


def _cs_fingerprint() -> str:
    raw = '|'.join([_cs_lapi_url(), _cs_api_key(), _cs_client_cert(), _cs_ca_cert()])
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]


def _cs_stream_path() -> str:
    return os.path.join(env.CONFIG_DIR, 'crowdsec-decisions.json')


def _cs_stream_lock_path() -> str:
    return _cs_stream_path() + '.lock'


def cs_stream_fresh_seconds() -> int:
    return _cs_int_env('CROWDSEC_STREAM_FRESH_SECONDS', CS_STREAM_FRESH_DEFAULT, 0, 3600)


@contextmanager
def _cs_file_lock(blocking: bool = True, path: str = None):
    lock_path = (path or _cs_stream_path()) + '.lock'
    fh   = None
    held = True
    if fcntl is not None:
        try:
            fh = open(lock_path, 'a+')
        except OSError:
            fh = None
        if fh is not None:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX if blocking else fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                held = blocking
                try:
                    fh.close()
                except OSError:
                    pass
                fh = None
    try:
        yield held
    finally:
        if fh is not None:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
            try:
                fh.close()
            except OSError:
                pass


def _cs_shared_read(fp: str, known: dict = None, path: str = None, match: dict = None) -> dict:
    match = match or {}
    path  = path or _cs_stream_path()
    empty = {'fp': fp, 'items': {}, 'synced': None, 'ready': False, 'owner': 0, 'stamp': None}
    empty.update(match)
    try:
        st = os.stat(path)
    except OSError:
        return empty
    stamp = (st.st_mtime_ns, st.st_size)
    if known is not None and known.get('stamp') == stamp:
        return known
    try:
        with open(path, 'r') as f:
            doc = json.load(f)
    except (OSError, ValueError):
        return empty
    if not isinstance(doc, dict) or doc.get('fp') != fp or not isinstance(doc.get('items'), dict):
        return empty
    if any(doc.get(k) != v for k, v in match.items()):
        return empty
    try:
        synced = datetime.fromtimestamp(float(doc.get('synced') or 0), timezone.utc)
    except (TypeError, ValueError, OSError, OverflowError):
        return empty
    result = {'fp': fp, 'items': doc['items'], 'synced': synced, 'ready': True,
              'owner': doc.get('owner') or 0, 'stamp': stamp}
    result.update(match)
    return result


def _cs_shared_write(fp: str, items: dict, synced: datetime, path: str = None, extra: dict = None):
    path = path or _cs_stream_path()
    tmp  = f"{path}.tmp.{os.getpid()}.{threading.get_ident()}"
    doc  = {'fp': fp, 'synced': synced.timestamp(), 'owner': os.getpid(), 'items': items}
    doc.update(extra or {})
    try:
        with open(tmp, 'w') as f:
            json.dump(doc, f, separators=(',', ':'))
        os.replace(tmp, path)
    except (OSError, ValueError) as e:
        logger.warning(f"CrowdSec cache write failed: {e}")
    finally:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass


def _cs_mirror(doc: dict):
    _cs_stream_cache.update({'fp': doc['fp'], 'items': doc['items'],
                             'synced': doc['synced'], 'ready': doc['ready']})
    return list(doc['items'].values())


def _cs_fresh(doc: dict, now: datetime) -> bool:
    if not doc['ready'] or doc['owner'] == os.getpid():
        return False
    return (now - doc['synced']).total_seconds() < cs_stream_fresh_seconds()


def cs_stream_reset():
    with _cs_stream_lock:
        _cs_stream_cache.update({'fp': '', 'items': {}, 'synced': None, 'ready': False, 'streamable': True})
        with _cs_file_lock():
            try:
                os.unlink(_cs_stream_path())
            except OSError:
                pass


def _cs_apply_stream(payload, base: dict):
    items = dict(base)
    for d in (payload.get('new') or []):
        did = d.get('id')
        if did is not None:
            items[str(did)] = d
    for d in (payload.get('deleted') or []):
        did = d.get('id')
        if did is not None:
            items.pop(str(did), None)
        else:
            val = d.get('value')
            if val:
                for k, v in list(items.items()):
                    if v.get('value') == val and v.get('type') == d.get('type'):
                        items.pop(k, None)
    return items


CS_STALE_AFTER_SECONDS = 900


def _cs_stale_mode(age, err):
    if age is not None and age >= CS_STALE_AFTER_SECONDS:
        return f'stale:{age}:{err}'
    return 'cache'


def _cs_write_due(doc: dict, now: datetime, changed: bool) -> bool:
    if changed or not doc['ready'] or not doc['synced']:
        return True
    return (now - doc['synced']).total_seconds() >= CS_STREAM_WRITE_SECONDS


def cs_decisions_stream(force_full: bool = False):
    fp  = _cs_fingerprint()
    now = datetime.now(timezone.utc)
    with _cs_stream_lock:
        doc = _cs_shared_read(fp)
        if not force_full and _cs_fresh(doc, now):
            return _cs_mirror(doc), 'cache'
        with _cs_file_lock(blocking=not doc['ready']) as held:
            doc = _cs_shared_read(fp, known=doc)
            if doc['ready'] and (not held or (not force_full and _cs_fresh(doc, now))):
                return _cs_mirror(doc), 'cache'
            if not held:
                raise CrowdSecUnavailable('The CrowdSec decision cache is being refreshed')
            stale = bool(doc['synced'] and (now - doc['synced']).total_seconds() > CS_STREAM_RESYNC_SECONDS)
            full  = force_full or not doc['ready'] or stale
            path  = '/v1/decisions/stream?startup=true' if full else '/v1/decisions/stream'
            try:
                payload = _cs_request_strict('GET', path)
            except CrowdSecUnavailable as e:
                if doc['ready']:
                    age = int((now - doc['synced']).total_seconds()) if doc['synced'] else None
                    return _cs_mirror(doc), _cs_stale_mode(age, e)
                raise
            if not isinstance(payload, dict):
                raise CrowdSecUnavailable('LAPI stream returned an unexpected payload')
            items = _cs_apply_stream(payload, {} if full else doc['items'])
            changed = full or bool(payload.get('new') or payload.get('deleted'))
            if _cs_write_due(doc, now, changed):
                _cs_shared_write(fp, items, now)
                doc = {'fp': fp, 'items': items, 'synced': now, 'ready': True,
                       'owner': os.getpid(), 'stamp': None}
            return _cs_mirror(doc), ('full' if full else 'delta')


_cs_alert_lock = threading.Lock()
_cs_alert_cache = {'fp': '', 'limit': -1, 'items': {}, 'synced': None, 'ready': False}


def _cs_alerts_path() -> str:
    return os.path.join(env.CONFIG_DIR, 'crowdsec-alerts.json')


def _cs_alert_fp() -> str:
    return _cs_fingerprint() + '|' + _cs_machine_id()


def _cs_alert_fetch(path: str) -> list:
    lapi = _cs_lapi_url().rstrip('/')
    if _cs_has_machine():
        token = _cs_jwt(lapi)
        if not token:
            raise CrowdSecUnavailable('CrowdSec machine login failed - check CROWDSEC_MACHINE_ID / '
                                      'CROWDSEC_MACHINE_PASSWORD or the client certificate', 502)
        headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/json'}
    else:
        headers = {'X-Api-Key': _cs_api_key(), 'Accept': 'application/json'}
    try:
        resp = requests.get(f"{lapi}{path}", headers=headers, timeout=cs_timeout(), **_cs_tls_kwargs())
    except Exception as e:
        raise CrowdSecUnavailable(f'CrowdSec LAPI unreachable: {e}', 0) from e
    if resp.status_code == 401 and _cs_has_machine():
        logger.info("CrowdSec refused the machine token on /v1/alerts, logging in again")
        cs_jwt_reset()
        token = _cs_jwt(lapi)
        if token:
            headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/json'}
            try:
                resp = requests.get(f"{lapi}{path}", headers=headers, timeout=cs_timeout(), **_cs_tls_kwargs())
            except Exception as e:
                raise CrowdSecUnavailable(f'CrowdSec LAPI unreachable: {e}', 0) from e
    if not resp.ok:
        try:
            body = resp.json()
            msg  = body.get('message') or body.get('error') or resp.text
        except Exception:
            msg = resp.text
        raise CrowdSecUnavailable(f'LAPI {resp.status_code}: {msg}', resp.status_code)
    alerts = resp.json() if resp.content else []
    return alerts if isinstance(alerts, list) else []


def _cs_alert_mirror(doc: dict):
    _cs_alert_cache.update({'fp': doc['fp'], 'limit': doc.get('limit', -1), 'items': doc['items'],
                            'synced': doc['synced'], 'ready': doc['ready']})
    return sorted(doc['items'].values(), key=lambda a: a.get('id') or 0, reverse=True)


def cs_alerts_reset():
    with _cs_alert_lock:
        _cs_alert_cache.update({'fp': '', 'limit': -1, 'items': {}, 'synced': None, 'ready': False})
        with _cs_file_lock(path=_cs_alerts_path()):
            try:
                os.unlink(_cs_alerts_path())
            except OSError:
                pass


def cs_alerts(limit: int, force_full: bool = False):
    fp   = _cs_alert_fp()
    now  = datetime.now(timezone.utc)
    path = _cs_alerts_path()
    with _cs_alert_lock:
        doc = _cs_shared_read(fp, path=path, match={'limit': limit})
        if not force_full and _cs_fresh(doc, now):
            return _cs_alert_mirror(doc), 'cache'
        with _cs_file_lock(blocking=not doc['ready'], path=path) as held:
            doc = _cs_shared_read(fp, known=doc, path=path, match={'limit': limit})
            if doc['ready'] and (not held or (not force_full and _cs_fresh(doc, now))):
                return _cs_alert_mirror(doc), 'cache'
            if not held:
                raise CrowdSecUnavailable('The CrowdSec alert cache is being refreshed')
            stale = bool(doc['synced'] and (now - doc['synced']).total_seconds() > CS_STREAM_RESYNC_SECONDS)
            full  = force_full or not doc['ready'] or stale
            try:
                if full:
                    rows  = _cs_alert_fetch(f'/v1/alerts?limit={limit}&with_decisions=false')
                    items = {str(a['id']): a for a in rows if isinstance(a, dict) and a.get('id') is not None}
                else:
                    age   = int((now - doc['synced']).total_seconds())
                    rows  = _cs_alert_fetch(f'/v1/alerts?since={age + 60}s&limit={limit}&with_decisions=false')
                    items = dict(doc['items'])
                    for a in rows:
                        if isinstance(a, dict) and a.get('id') is not None:
                            items[str(a['id'])] = a
                    if limit > 0 and len(items) > limit:
                        keep  = sorted(items, key=lambda k: int(k), reverse=True)[:limit]
                        items = {k: items[k] for k in keep}
            except CrowdSecUnavailable as e:
                if doc['ready']:
                    age = int((now - doc['synced']).total_seconds()) if doc['synced'] else None
                    return _cs_alert_mirror(doc), _cs_stale_mode(age, e)
                raise
            changed = full or set(items) != set(doc['items'])
            if _cs_write_due(doc, now, changed):
                _cs_shared_write(fp, items, now, path=path, extra={'limit': limit})
                doc = {'fp': fp, 'items': items, 'synced': now, 'ready': True,
                       'owner': os.getpid(), 'stamp': None, 'limit': limit}
            return _cs_alert_mirror(doc), ('full' if full else 'delta')


CS_ALERT_POLL_LIMIT = 200
CS_FOREIGN_SCOPES = ('capi', 'lists')


def _cs_alert_is_local(alert: dict) -> bool:
    scope = str((alert.get('source') or {}).get('scope') or '').strip().lower()
    if scope in CS_FOREIGN_SCOPES or scope.startswith('lists:'):
        return False
    origins = {str(d.get('origin') or '').strip().lower()
               for d in (alert.get('decisions') or []) if isinstance(d, dict)}
    origins.discard('')
    return not origins or 'crowdsec' in origins


def poll_local_alerts(since: str = '15m') -> list:
    if not _cs_has_machine():
        return []
    window = str(since or '15m').strip() or '15m'
    alerts = _cs_machine_request('GET', f'/v1/alerts?since={quote(window)}&origin=crowdsec'
                                        f'&with_decisions=false&limit={CS_ALERT_POLL_LIMIT}')
    if not isinstance(alerts, list):
        return []
    return [a for a in alerts if isinstance(a, dict) and _cs_alert_is_local(a)]


CS_ALERT_INTERVAL = 300
CS_ALERT_WINDOW = '10m'
CS_WINDOW_UNITS = {'s': 'second', 'm': 'minute', 'h': 'hour', 'd': 'day'}


def _cs_count(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def _cs_window_label(since: str) -> str:
    window = str(since or '').strip().lower()
    unit   = CS_WINDOW_UNITS.get(window[-1:], '')
    number = window[:-1]
    if unit and number.isdigit():
        return _cs_count(int(number), unit)
    return window


def _cs_alert_source(alert: dict) -> str:
    source = alert.get('source') or {}
    return str(source.get('ip') or source.get('value') or '').strip()


def _cs_alert_scenario(alert: dict) -> str:
    scenario = str(alert.get('scenario') or '').strip() or 'unknown'
    prefix   = 'crowdsecurity/'
    return scenario[len(prefix):] if scenario.startswith(prefix) else scenario


def _cs_alert_events(alert: dict) -> int:
    try:
        return max(0, int(alert.get('events_count') or 0))
    except (TypeError, ValueError):
        return 0


CS_SUMMARY_SCENARIOS = 4


def _cs_flag(cc: str) -> str:
    code = str(cc or '').strip().upper()
    if len(code) != 2 or not code.isalpha():
        return ''
    return ''.join(chr(0x1F1E6 + ord(ch) - 65) for ch in code)


def _cs_alert_origin_detail(alert: dict) -> str:
    src = alert.get('source') if isinstance(alert, dict) else None
    if not isinstance(src, dict):
        return ''
    bits = []
    cn = str(src.get('cn') or '').strip()
    if cn:
        bits.append(_cs_flag(cn) or cn)
    as_name = str(src.get('as_name') or '').strip()
    as_num = str(src.get('as_number') or '').strip()
    if as_name and as_num:
        bits.append(f'AS{as_num} {as_name}')
    elif as_name:
        bits.append(as_name)
    elif as_num:
        bits.append(f'AS{as_num}')
    return ', '.join(bits)


def _cs_scenario_list(names) -> str:
    ordered = sorted(names)
    shown = ordered[:CS_SUMMARY_SCENARIOS]
    rest = len(ordered) - len(shown)
    text = ', '.join(shown)
    return f'{text} and {rest} more' if rest > 0 else text


def summarise_alerts(alerts, window_label: str = '') -> str:
    sources = {}
    scenarios = {}
    detail = {}
    for alert in alerts or []:
        scenario = _cs_alert_scenario(alert)
        ip = _cs_alert_source(alert)
        events = _cs_alert_events(alert)
        scenarios[scenario] = scenarios.get(scenario, 0) + events
        if not ip:
            continue
        entry = sources.setdefault(ip, {'events': 0, 'scenarios': {}})
        entry['events'] += events
        entry['scenarios'][scenario] = entry['scenarios'].get(scenario, 0) + events
        if ip not in detail:
            where = _cs_alert_origin_detail(alert)
            if where:
                detail[ip] = where
    if not sources:
        return ''
    when = f' in the last {window_label}' if window_label else ''
    total = sum(v['events'] for v in sources.values())
    worst_ip, worst = sorted(sources.items(), key=lambda kv: (-kv[1]['events'], kv[0]))[0]
    where = detail.get(worst_ip, '')
    where = f' ({where})' if where else ''
    if len(sources) == 1:
        return (f"{worst_ip}{where} tripped {_cs_count(len(scenarios), 'scenario')}"
                f", {_cs_count(total, 'event')}{when}: {_cs_scenario_list(scenarios)}")
    return (f"{_cs_count(len(sources), 'source')} tripped "
            f"{_cs_count(len(scenarios), 'scenario')}, {_cs_count(total, 'event')}{when}. "
            f"Worst: {worst_ip}{where}, "
            f"{sorted(worst['scenarios'].items(), key=lambda kv: (-kv[1], kv[0]))[0][0]}, "
            f"{_cs_count(worst['events'], 'event')}. Scenarios: {_cs_scenario_list(scenarios)}")


def check_local_alerts(since: str = CS_ALERT_WINDOW) -> list:
    msg = summarise_alerts(poll_local_alerts(since), _cs_window_label(since))
    if not msg:
        return []
    return [('warning', msg, 'crowdsec')]

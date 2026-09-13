import os
import threading
import time

import requests

from core import env
from core import settings as settings_mod
from core.env import logger

_DBIP_URL = 'https://download.db-ip.com/free/dbip-country-lite-{ym}.mmdb.gz'
_geoip_lock  = threading.Lock()
_geoip_state = {'reader': None, 'path': None, 'mtime': None}
_geoip_cache = {}
_GEOIP_SENTINEL = object()


def _geoip_enabled() -> bool:
    s = settings_mod.load_settings()
    return bool(s.get('geoip_enabled', False))


def _geoip_db_path() -> str:
    s = settings_mod.load_settings()
    return (s.get('geoip_db_path') or '').strip() or os.environ.get('GEOIP_DB_PATH', '').strip() or os.path.join(env.GEOIP_DIR, 'dbip-country-lite.mmdb')


def _geoip_reader():
    path = _geoip_db_path()
    if not path or not os.path.exists(path):
        return None
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return None
    with _geoip_lock:
        st = _geoip_state
        if st['reader'] is not None and st['path'] == path and st['mtime'] == mtime:
            return st['reader']
        try:
            import maxminddb
            reader = maxminddb.open_database(path)
        except Exception:
            logger.exception("GeoIP database open failed")
            return None
        st.update({'reader': reader, 'path': path, 'mtime': mtime})
        _geoip_cache.clear()
        return reader


def _geoip_lookup(ip: str, reader=_GEOIP_SENTINEL):
    if not ip:
        return None
    cached = _geoip_cache.get(ip)
    if cached is not None:
        return cached or None
    if reader is _GEOIP_SENTINEL:
        reader = _geoip_reader()
    if reader is None:
        return None
    try:
        rec = reader.get(ip) or {}
    except Exception:
        rec = {}
    country = rec.get('country') or {}
    cc = str(country.get('iso_code') or '').upper()
    name = ((country.get('names') or {}).get('en')) or cc
    result = {'country_code': cc, 'country_name': name} if cc else None
    if len(_geoip_cache) > 50000:
        _geoip_cache.clear()
    _geoip_cache[ip] = result or {}
    return result


def _geoip_download():
    import gzip
    now = time.gmtime()
    y, m = now.tm_year, now.tm_mon
    pm = (y, m - 1) if m > 1 else (y - 1, 12)
    months = [time.strftime('%Y-%m', now), '%04d-%02d' % pm]
    last_err = 'unknown error'
    for ym in months:
        url = _DBIP_URL.format(ym=ym)
        try:
            resp = requests.get(url, timeout=90, headers={'User-Agent': f'traefik-manager/{env.APP_VERSION}'})
            if resp.status_code == 200 and resp.content:
                data = gzip.decompress(resp.content)
                path = _geoip_db_path()
                os.makedirs(os.path.dirname(path), exist_ok=True)
                tmp = f"{path}.tmp.{os.getpid()}.{threading.get_ident()}"
                try:
                    with open(tmp, 'wb') as f:
                        f.write(data)
                    os.replace(tmp, path)
                finally:
                    if os.path.exists(tmp):
                        try:
                            os.unlink(tmp)
                        except OSError:
                            pass
                with _geoip_lock:
                    _geoip_state['reader'] = None
                    _geoip_state['mtime'] = None
                    _geoip_cache.clear()
                logger.info(f"GeoIP database updated (DB-IP {ym})")
                return True, ym
            last_err = f'HTTP {resp.status_code}'
        except Exception as e:
            last_err = str(e)
    return False, last_err


def _geoip_status() -> dict:
    path = _geoip_db_path()
    available = bool(path and os.path.exists(path))
    db_date = None
    if available:
        try:
            db_date = time.strftime('%Y-%m-%d', time.gmtime(os.path.getmtime(path)))
        except OSError:
            db_date = None
    return {'enabled': _geoip_enabled(), 'available': available, 'db_path': path, 'db_date': db_date}

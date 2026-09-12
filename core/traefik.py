import os

import requests

from core import config
from core import settings as settings_mod
from core.env import logger


def _traefik_verify():
    if os.environ.get('TRAEFIK_INSECURE_SKIP_VERIFY', '').lower() in ('true', '1', 'yes'):
        return False
    return True

TRAEFIK_PAGE_SIZE = 1000
TRAEFIK_MAX_PAGES = 50

def _traefik_request(path):
    settings = settings_mod.load_settings()
    base_url = settings['traefik_api_url']
    if not config.safe_api_url(base_url):
        logger.error("traefik_api_url failed safety check")
        return None
    u = settings.get('traefik_api_user', '')
    p = settings.get('traefik_api_password', '')
    auth = (u, p) if u and p else None
    try:
        resp = requests.get(f"{base_url}{path}", timeout=3, auth=auth, verify=_traefik_verify())
        if resp.status_code == 200:
            return resp
    except Exception as e:
        logger.debug(f"Traefik API unavailable: {e}")
    return None

def traefik_api_get(path):
    resp = _traefik_request(path)
    if resp is None:
        return None
    try:
        return resp.json()
    except Exception as e:
        logger.debug(f"Traefik API returned an unreadable body: {e}")
        return None

def _traefik_next_page(resp, page):
    header = getattr(resp, 'headers', None) or {}
    raw = str(header.get('X-Next-Page', '') or '')
    if not raw.isdigit():
        return 0
    nxt = int(raw)
    return nxt if nxt > page else 0

def traefik_api_get_all(path, complete=None):
    sep = '&' if '?' in path else '?'
    out = None
    page = 1
    for _ in range(TRAEFIK_MAX_PAGES):
        query = f"{sep}per_page={TRAEFIK_PAGE_SIZE}" + (f"&page={page}" if page > 1 else '')
        resp = _traefik_request(f"{path}{query}")
        if resp is None:
            if complete is not None:
                complete.append(False)
            return out
        try:
            chunk = resp.json()
        except Exception as e:
            logger.debug(f"Traefik API returned an unreadable body: {e}")
            if complete is not None:
                complete.append(False)
            return out
        if not isinstance(chunk, list):
            return chunk
        out = chunk if out is None else out + chunk
        nxt = _traefik_next_page(resp, page)
        if not nxt or not chunk:
            break
        page = nxt
    return out

def _fetch_traefik_routers_and_services(complete=None):
    all_routers  = {}
    all_services = {}
    for proto in ('http', 'tcp', 'udp'):
        fetched = traefik_api_get_all(f'/api/{proto}/routers', complete)
        if fetched is None and complete is not None:
            complete.append(False)
        all_routers[proto]  = fetched or []
        all_services[proto] = traefik_api_get_all(f'/api/{proto}/services') or []
    return all_routers, all_services

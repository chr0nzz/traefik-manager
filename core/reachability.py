import ipaddress
import socket
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse

import requests

POOL_WORKERS = 6
UNREACHABLE = (502, 503, 504)
REDIRECTS   = (301, 302, 303, 307, 308)
TIMEOUT     = 5

_DOWN_MARKERS    = ('connection refused', 'no route to host', 'network is unreachable',
                    'connection reset', 'remote end closed')
_UNKNOWN_MARKERS = ('name or service not known', 'nodename nor servname', 'temporary failure in name resolution',
                    'nameresolutionerror', 'getaddrinfo failed', 'timed out', 'timeout')


def ssrf_ok(url: str) -> bool:
    try:
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


def _is_http(url: str) -> bool:
    return str(url or '').startswith(('http://', 'https://'))


def _head(target, head):
    t0   = time.monotonic()
    resp = head(target, timeout=TIMEOUT, allow_redirects=False, verify=False)
    ms   = round((time.monotonic() - t0) * 1000)
    location = ''
    try:
        location = resp.headers.get('Location', '') or ''
    except Exception:
        pass
    return ms, resp.status_code, location


def _error_text(exc) -> str:
    err = str(exc)[:80]
    return 'Timeout' if 'timeout' in err.lower() else err


def redirect_target_host(url: str, code: int, location: str) -> str:
    if code not in REDIRECTS or not location:
        return ''
    try:
        to   = (urlparse(urljoin(url, location)).hostname or '').lower()
        here = (urlparse(url).hostname or '').lower()
    except Exception:
        return ''
    return to if to and to != here else ''


def _classify_failure(exc) -> str:
    text = str(exc).lower()
    if isinstance(exc, (requests.exceptions.ConnectTimeout, requests.exceptions.ReadTimeout)):
        return 'unknown'
    if any(m in text for m in _DOWN_MARKERS):
        return 'down'
    if any(m in text for m in _UNKNOWN_MARKERS):
        return 'unknown'
    return 'down' if isinstance(exc, requests.exceptions.ConnectionError) else 'unknown'


def _backend(fallback, ssrf, head):
    if not (fallback and _is_http(fallback) and ssrf(fallback)):
        return 'unknown', None, 'has no address to check'
    try:
        ms, code, _loc = _head(fallback, head)
    except Exception as exc:
        verdict = _classify_failure(exc)
        why = 'refused the connection' if verdict == 'down' else 'could not be reached from Traefik Manager (' + _error_text(exc) + ')'
        return verdict, None, why
    if code in UNREACHABLE:
        return 'down', None, f'answered {code}'
    return 'up', {'ok': True, 'latency_ms': ms, 'status_code': code, 'via_target': True}, ''


def backend_state(url: str, ssrf=None, head=None) -> str:
    verdict, _alt, _why = _backend(url, ssrf or ssrf_ok, head or requests.head)
    return verdict


def pool_health(urls, ssrf=None, head=None):
    clean = [str(u) for u in (urls or []) if str(u).startswith(('http://', 'https://'))]
    if len(clean) < 2:
        return None
    probe = backend_state if (ssrf is None and head is None) else (lambda u: backend_state(u, ssrf, head))
    with ThreadPoolExecutor(max_workers=min(POOL_WORKERS, len(clean))) as pool:
        verdicts = list(pool.map(probe, clean))
    if 'unknown' in verdicts:
        return None
    return {'up': verdicts.count('up'), 'total': len(clean),
            'down_servers': [u for u, v in zip(clean, verdicts) if v != 'up']}


def pool_result(pool: dict) -> dict:
    state = 'down' if pool['up'] == 0 else ('degraded' if pool['up'] < pool['total'] else 'up')
    out = {'ok': pool['up'] > 0, 'state': state, 'source': 'servers',
           'servers': {'up': pool['up'], 'total': pool['total']}}
    if pool['down_servers']:
        out['down_servers'] = pool['down_servers']
    return out


def probe(url: str, fallback: str = '', ssrf=None, head=None) -> dict:
    ssrf = ssrf or ssrf_ok
    head = head or requests.head

    try:
        ms, code, location = _head(url, head)
    except Exception as primary_err:
        verdict, alt, _why = _backend(fallback, ssrf, head)
        if alt:
            return alt
        return {'ok': False, 'error': _error_text(primary_err), 'latency_ms': None}

    if code in UNREACHABLE:
        verdict, alt, _why = _backend(fallback, ssrf, head)
        if alt:
            return alt
        return {'ok': False, 'latency_ms': ms, 'status_code': code,
                'error': f'The proxy answered {code}, the backend is not reachable'}

    auth_host = redirect_target_host(url, code, location)
    if auth_host:
        verdict, alt, why = _backend(fallback, ssrf, head)
        if alt:
            return alt
        if verdict == 'down':
            return {'ok': False, 'latency_ms': ms, 'status_code': code,
                    'error': f'The proxy redirected to {auth_host} before reaching the backend, and the backend {why}'}
        return {'ok': True, 'latency_ms': ms, 'status_code': code, 'unverified': True,
                'note': f'The proxy redirected to {auth_host} before reaching the backend, and the backend {why}'}

    return {'ok': True, 'latency_ms': ms, 'status_code': code}

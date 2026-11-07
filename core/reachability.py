import errno
import http.client
import ipaddress
import re
import socket
import ssl
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse

import requests
from urllib3 import exceptions as _u3

from core import i18n as _i18n

POOL_WORKERS = 6
UNREACHABLE = (502, 503, 504)
REDIRECTS   = (301, 302, 303, 307, 308)
TIMEOUT     = 5
DETAIL_MAX  = 100
CAUSE_DEPTH = 10
_SSL_NOISE  = re.compile(r'^\s*\[[^\]]*\]\s*|\s*\(_ssl\.c:\d+\)\s*$')

_DOWN_KINDS    = ('closed', 'refused', 'no_route', 'network', 'reset')
_UNKNOWN_KINDS = ('dns', 'read_timeout', 'timeout')
_KIND_ORDER    = ('dns', 'closed', 'refused', 'no_route', 'network', 'reset', 'tls', 'read_timeout', 'timeout')
_KIND_ERRNOS   = {errno.ECONNREFUSED: 'refused', errno.EHOSTUNREACH: 'no_route', errno.ENETUNREACH: 'network',
                  errno.ECONNRESET: 'reset', errno.ETIMEDOUT: 'timeout'}
_KIND_TYPES    = ((socket.gaierror, 'dns'), (_u3.NameResolutionError, 'dns'),
                  (http.client.RemoteDisconnected, 'closed'),
                  (ConnectionRefusedError, 'refused'), (ConnectionResetError, 'reset'),
                  (ssl.SSLError, 'tls'), (_u3.SSLError, 'tls'), (requests.exceptions.SSLError, 'tls'),
                  (requests.exceptions.ReadTimeout, 'read_timeout'), (_u3.ReadTimeoutError, 'read_timeout'),
                  (_u3.NewConnectionError, ''),
                  (requests.exceptions.ConnectTimeout, 'timeout'), (_u3.ConnectTimeoutError, 'timeout'),
                  (TimeoutError, 'timeout'))
_KIND_MARKERS  = (('dns', ('name or service not known', 'nodename nor servname', 'temporary failure in name resolution',
                           'name does not resolve', 'nameresolutionerror', 'getaddrinfo failed')),
                  ('closed', ('remote end closed',)),
                  ('refused', ('connection refused',)),
                  ('no_route', ('no route to host',)),
                  ('network', ('network is unreachable',)),
                  ('reset', ('connection reset',)),
                  ('read_timeout', ('read timed out',)),
                  ('timeout', ('timed out', 'timeout')))
_KIND_TEXT     = {
    'refused':      _i18n.lazy_pgettext('check failure', 'connection refused'),
    'no_route':     _i18n.lazy_pgettext('check failure', 'no route to host'),
    'network':      _i18n.lazy_pgettext('check failure', 'network unreachable'),
    'reset':        _i18n.lazy_pgettext('check failure', 'connection reset'),
    'closed':       _i18n.lazy_pgettext('check failure', 'connection closed without a response'),
    'timeout':      _i18n.lazy_pgettext('check failure', 'connection timed out'),
    'read_timeout': _i18n.lazy_pgettext('check failure', 'timed out waiting for a response'),
}


MAX_REDIRECT_HOPS = 5


class BlockedTarget(Exception):
    pass


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


def safe_get(url: str, *, ssrf=None, getter=None, **kwargs):
    ssrf = ssrf or ssrf_ok
    getter = getter or requests.get
    kwargs['allow_redirects'] = False
    target = url
    for _ in range(MAX_REDIRECT_HOPS + 1):
        if not _is_http(target):
            raise BlockedTarget(_i18n.lazy_gettext('%(url)s is not an http(s) address', url=target))
        if not ssrf(target):
            raise BlockedTarget(_i18n.lazy_gettext('%(url)s is not an allowed address', url=target))
        resp = getter(target, **kwargs)
        location = ''
        try:
            location = resp.headers.get('Location', '') or ''
        except Exception:
            pass
        if resp.status_code not in REDIRECTS or not location:
            return resp
        target = urljoin(target, location)
    raise BlockedTarget(_i18n.lazy_ngettext('%(url)s redirected more than %(num)d time',
                                            '%(url)s redirected more than %(num)d times',
                                            MAX_REDIRECT_HOPS, url=url))


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


def _causes(exc) -> list:
    chain = []
    while isinstance(exc, BaseException) and len(chain) < CAUSE_DEPTH and not any(exc is seen for seen in chain):
        chain.append(exc)
        nxt = getattr(exc, 'reason', None)
        if not isinstance(nxt, BaseException):
            nxt = next((a for a in exc.args if isinstance(a, BaseException)), None)
        exc = nxt if nxt is not None else exc.__cause__
    return chain


def _kind_of(exc) -> str:
    code = getattr(exc, 'errno', None)
    if isinstance(code, int) and code in _KIND_ERRNOS:
        return _KIND_ERRNOS[code]
    return next((kind for cls, kind in _KIND_TYPES if isinstance(exc, cls)), '')


def _failure_kind(chain) -> str:
    kinds = {_kind_of(e) for e in chain}
    found = next((kind for kind in _KIND_ORDER if kind in kinds), '')
    if found:
        return found
    text = ' '.join(str(e) for e in chain).lower()
    return next((kind for kind, markers in _KIND_MARKERS if any(m in text for m in markers)), '')


def _cause_text(chain) -> str:
    for exc in reversed(chain):
        text = exc.strerror if isinstance(exc, OSError) and isinstance(exc.strerror, str) and exc.strerror else str(exc)
        text = ' '.join(text.split())
        if text:
            return text[:DETAIL_MAX]
    return ''


def _tls_reason(chain) -> str:
    reason = next((e.reason for e in chain if isinstance(e, ssl.SSLError) and isinstance(getattr(e, 'reason', None), str)
                   and e.reason), '')
    if reason:
        return reason.lower().replace('_', ' ')
    text = _cause_text(chain)
    return _SSL_NOISE.sub('', text).strip() or text


def cert_verify_reason(exc) -> str:
    err = next((e for e in _causes(exc) if isinstance(e, ssl.SSLCertVerificationError)), None)
    if err is None:
        return ''
    text = err.verify_message if isinstance(getattr(err, 'verify_message', None), str) else ''
    return ' '.join(text.split())[:DETAIL_MAX] or _tls_reason([err])


def failure_reason(exc, url: str = ''):
    chain = _causes(exc)
    kind  = _failure_kind(chain)
    if kind == 'dns':
        host = urlparse(url).hostname if url else ''
        if host:
            return _i18n.lazy_pgettext('check failure', 'DNS name %(host)s does not resolve', host=host)
        return _i18n.lazy_pgettext('check failure', 'DNS name does not resolve')
    if kind == 'tls':
        reason = _tls_reason(chain)
        if reason:
            return _i18n.lazy_pgettext('check failure', 'TLS handshake failed (%(reason)s)', reason=reason)
        return _i18n.lazy_pgettext('check failure', 'TLS handshake failed')
    if kind in _KIND_TEXT:
        return _KIND_TEXT[kind]
    return _cause_text(chain)


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
    kind = _failure_kind(_causes(exc))
    if kind in _DOWN_KINDS:
        return 'down'
    if kind in _UNKNOWN_KINDS:
        return 'unknown'
    return 'down' if isinstance(exc, requests.exceptions.ConnectionError) else 'unknown'


def _down_why(exc) -> str:
    kind = _failure_kind(_causes(exc))
    return kind if kind in _DOWN_KINDS else 'unreachable'


def redirect_reason(host: str, why) -> str:
    kind, detail = why if isinstance(why, tuple) else (why, '')
    if kind == 'refused':
        return _i18n.lazy_gettext('The proxy redirected to %(host)s before reaching the backend, '
                                  'and the backend refused the connection', host=host)
    if kind == 'no_route':
        return _i18n.lazy_gettext('The proxy redirected to %(host)s before reaching the backend, '
                                  'and the backend is unreachable (no route to host)', host=host)
    if kind == 'network':
        return _i18n.lazy_gettext('The proxy redirected to %(host)s before reaching the backend, '
                                  'and the backend is unreachable (network unreachable)', host=host)
    if kind == 'reset':
        return _i18n.lazy_gettext('The proxy redirected to %(host)s before reaching the backend, '
                                  'and the backend reset the connection', host=host)
    if kind == 'closed':
        return _i18n.lazy_gettext('The proxy redirected to %(host)s before reaching the backend, '
                                  'and the backend closed the connection without answering', host=host)
    if kind == 'no_address':
        return _i18n.lazy_gettext('The proxy redirected to %(host)s before reaching the backend, '
                                  'and the backend has no address to check', host=host)
    if kind == 'error':
        return _i18n.lazy_gettext('The proxy redirected to %(host)s before reaching the backend, '
                                  'and the backend could not be reached from Traefik Manager (%(error)s)',
                                  host=host, error=detail)
    if kind == 'answered':
        return _i18n.lazy_gettext('The proxy redirected to %(host)s before reaching the backend, '
                                  'and the backend answered %(code)s', host=host, code=detail)
    return _i18n.lazy_gettext('The proxy redirected to %(host)s before reaching the backend, '
                              'and the backend is unreachable', host=host)


def _backend(fallback, ssrf, head):
    if not (fallback and _is_http(fallback) and ssrf(fallback)):
        return 'unknown', None, ('no_address', '')
    try:
        ms, code, _loc = _head(fallback, head)
    except Exception as exc:
        verdict = _classify_failure(exc)
        why = (_down_why(exc), '') if verdict == 'down' else ('error', failure_reason(exc, fallback))
        return verdict, None, why
    if code in UNREACHABLE:
        return 'down', None, ('answered', code)
    return 'up', {'ok': True, 'latency_ms': ms, 'status_code': code, 'via_target': True}, ('', '')


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


def probe(url: str, fallback: str = '', ssrf=None, head=None, verify_backend: bool = True) -> dict:
    ssrf = ssrf or ssrf_ok
    head = head or requests.head

    try:
        ms, code, location = _head(url, head)
    except Exception as primary_err:
        verdict, alt, _why = _backend(fallback, ssrf, head)
        if alt:
            return alt
        return {'ok': False, 'error': failure_reason(primary_err, url), 'latency_ms': None}

    if code in UNREACHABLE:
        verdict, alt, _why = _backend(fallback, ssrf, head)
        if alt:
            return alt
        return {'ok': False, 'latency_ms': ms, 'status_code': code,
                'error': _i18n.lazy_gettext('The proxy answered %(code)s, the backend is not reachable', code=code)}

    auth_host = redirect_target_host(url, code, location) if verify_backend else ''
    if auth_host:
        verdict, alt, why = _backend(fallback, ssrf, head)
        if alt:
            return alt
        if verdict == 'down':
            return {'ok': False, 'latency_ms': ms, 'status_code': code,
                    'error': redirect_reason(auth_host, why)}
        return {'ok': True, 'latency_ms': ms, 'status_code': code, 'unverified': True,
                'note': redirect_reason(auth_host, why)}

    return {'ok': True, 'latency_ms': ms, 'status_code': code}

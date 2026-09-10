import time
from concurrent.futures import ThreadPoolExecutor

from core import config as cfg_mod
from core import monitor as monitor_mod
from core import reachability
from core import settings as settings_mod
from core.env import logger

CATEGORY         = 'traefik'
TICK             = 60
DEFAULT_INTERVAL = 300
INTERVALS        = (60, 300, 900, 1800)
FAILS_TO_DOWN    = 2
WORKERS          = 6
SECTION          = 'routes'
META             = 'routes_meta'

def enabled(settings=None) -> bool:
    settings = settings if settings is not None else settings_mod.load_settings()
    return bool(settings.get('route_check_enabled', True))


def interval(settings=None) -> int:
    settings = settings if settings is not None else settings_mod.load_settings()
    try:
        value = int(settings.get('route_check_interval') or DEFAULT_INTERVAL)
    except (TypeError, ValueError):
        return DEFAULT_INTERVAL
    return value if value in INTERVALS else DEFAULT_INTERVAL


def route_url(app: dict) -> str:
    for host in cfg_mod.rule_hosts(app.get('rule')):
        if '*' in host or '{' in host:
            continue
        return ('https' if app.get('tls') else 'http') + '://' + host
    return ''


def override_url(app: dict, overrides) -> str:
    ov = (overrides or {}).get(str(app.get('id') or ''))
    if not isinstance(ov, dict) or ov.get('link_disabled'):
        return ''
    url = str(ov.get('url') or '').strip()
    return url if url.lower().startswith(('http://', 'https://')) else ''


def candidates(apps, self_hosts=(), overrides=None) -> list:
    out  = []
    mine = {str(h).lower() for h in self_hosts if h}
    for app in apps or []:
        if not isinstance(app, dict) or app.get('protocol', 'http') != 'http':
            continue
        if app.get('enabled') is False or not app.get('id'):
            continue
        url = override_url(app, overrides) or route_url(app)
        if not url:
            continue
        host = url.split('://', 1)[1].split('/', 1)[0].lower()
        out.append((app, '' if host in mine else url))
    return out


def has_health_check(svc) -> bool:
    lb = svc.get('loadBalancer') if isinstance(svc, dict) else None
    return isinstance(lb, dict) and bool(lb.get('healthCheck'))


def service_index(services) -> dict:
    rows = services.get('http') if isinstance(services, dict) else services
    index = {}
    for svc in rows or []:
        if not isinstance(svc, dict) or not has_health_check(svc):
            continue
        status = svc.get('serverStatus')
        if not isinstance(status, dict) or not status:
            continue
        total = len(status)
        up    = sum(1 for v in status.values() if str(v).upper() == 'UP')
        health = {'total': total, 'up': up}
        name = str(svc.get('name') or '')
        index[name] = health
        index.setdefault(cfg_mod.svc_key(name), health)
    return index


def service_health(app: dict, index: dict):
    name = str(app.get('service_name') or '')
    if not name:
        return None
    return index.get(name) or index.get(cfg_mod.svc_key(name))


def is_internal(app: dict) -> bool:
    return str(app.get('service_name') or '').endswith('@internal')


def _fallback(app: dict) -> str:
    target = str(app.get('target') or '')
    return target if target.startswith(('http://', 'https://')) else ''


def _state_for(up: int, total: int) -> str:
    return 'down' if up == 0 else ('degraded' if up < total else 'up')


def servers_health(app: dict, server_probe=None):
    urls = [str(u) for u in (app.get('servers') or []) if str(u).startswith(('http://', 'https://'))]
    if len(urls) < 2:
        return None
    if server_probe is None:
        return reachability.pool_health(urls)
    verdicts = [server_probe(u) for u in urls]
    if 'unknown' in verdicts:
        return None
    up = verdicts.count('up')
    return {'up': up, 'total': len(urls), 'down_servers': [u for u, v in zip(urls, verdicts) if v != 'up']}


def observe(app: dict, url: str, index: dict, probe=None, server_probe=None) -> dict:
    if not url:
        return {'state': 'up', 'source': 'self', 'self': True}
    health = service_health(app, index)
    if health and health['total']:
        return {'state': _state_for(health['up'], health['total']), 'source': 'traefik', 'servers': health}
    direct = servers_health(app, server_probe)
    if direct:
        obs = {'state': _state_for(direct['up'], direct['total']), 'source': 'servers',
               'servers': {'up': direct['up'], 'total': direct['total']}}
        if direct['down_servers']:
            obs['down_servers'] = direct['down_servers']
        return obs
    if is_internal(app):
        result = (probe or reachability.probe)(url, '', verify_backend=False)
    else:
        result = (probe or reachability.probe)(url, _fallback(app))
    obs = {'state': 'up' if result.get('ok') else 'down', 'source': 'ping'}
    for field in ('latency_ms', 'status_code', 'error', 'via_target', 'unverified', 'note'):
        if result.get(field) is not None:
            obs[field] = result[field]
    return obs


def _message(name: str, state: str, obs: dict) -> str:
    if state == 'up':
        return f"Route {name} is reachable again"
    servers = obs.get('servers') or {}
    if obs.get('source') in ('traefik', 'servers'):
        down = obs.get('down_servers') or []
        tail = f" ({', '.join(down)})" if down else ''
        if state == 'degraded':
            return f"Route {name} backend is degraded, {servers.get('up', 0)} of {servers.get('total', 0)} servers up{tail}"
        return f"Route {name} backend is down, 0 of {servers.get('total', 0)} servers up{tail}"
    err = str(obs.get('error') or '').strip()
    return f"Route {name} is unreachable" + (f" ({err})" if err else '')


def settle(prev, obs: dict, name: str, now: float):
    prev       = prev if isinstance(prev, dict) else {}
    prev_state = prev.get('state')
    fails      = int(prev.get('fails') or 0)
    if obs['state'] == 'down' and obs.get('source') in ('ping', 'servers'):
        fails += 1
        state = 'down' if fails >= FAILS_TO_DOWN else 'pending'
    else:
        fails = 0
        state = obs['state']
    entry = {'state': state, 'fails': fails, 'name': name, 'last': dict(obs, at=int(now))}
    event = None
    if state == 'down' and prev_state != 'down':
        event = ('error', _message(name, state, obs))
    elif state == 'degraded' and prev_state != 'degraded':
        event = ('warning', _message(name, state, obs))
    elif state == 'up' and prev_state in ('down', 'degraded'):
        event = ('success', _message(name, state, obs))
    return entry, event


def _self_hosts(settings) -> set:
    domain = str((settings.get('self_route') or {}).get('domain') or '').strip().lower()
    return {domain} if domain else set()


def check(sources, now=None, probe=None, settings=None, overrides_for=None) -> list:
    settings = settings if settings is not None else settings_mod.load_settings()
    now      = now if now is not None else time.time()
    meta     = monitor_mod._section(META)
    state    = monitor_mod._section(SECTION)
    meta['enabled'] = enabled(settings)
    if not meta['enabled']:
        return []
    last = meta.get('last_run')
    if isinstance(last, (int, float)) and (now - last) < interval(settings):
        return []
    meta['last_run'] = now
    servers = monitor_mod._agent_servers()
    raised  = []
    seen    = {}
    checked = set()
    for server, name, apps, services in sources():
        checked.add(server)
        skip  = _self_hosts(settings) if server == monitor_mod.HOST_SERVER else set()
        index = service_index(services)
        overrides = {}
        if overrides_for:
            try:
                overrides = overrides_for(server) or {}
            except Exception:
                logger.exception(f"Route check could not read the dashboard links for {name or 'the host'}")
        jobs  = [(app, url) for app, url in candidates(apps, skip, overrides) if not url or reachability.ssrf_ok(url)]
        if not jobs:
            continue
        try:
            with ThreadPoolExecutor(max_workers=min(WORKERS, len(jobs))) as pool:
                results = list(pool.map(lambda job: observe(job[0], job[1], index, probe), jobs))
        except Exception:
            logger.exception(f"Route check failed for {name or 'the host'}")
            continue
        for (app, _url), obs in zip(jobs, results):
            key = monitor_mod._server_key(server, str(app['id']))
            entry, event = settle(state.get(key), obs, str(app.get('name') or app['id']), now)
            seen[key] = entry
            if event:
                raised.append((event[0], monitor_mod._server_msg(name, event[1]), CATEGORY))
    for key, entry in state.items():
        if monitor_mod._key_server(key) not in checked:
            seen.setdefault(key, entry)
    state.clear()
    state.update(seen)
    monitor_mod._prune(state, monitor_mod._known_servers(servers))
    meta['checked_at'] = int(now)
    return raised


def _public(entry: dict) -> dict:
    last = entry.get('last') if isinstance(entry.get('last'), dict) else {}
    out  = {'state': entry.get('state') or 'pending',
            'pending': int(entry.get('fails') or 0) > 0 and entry.get('state') != 'down',
            'source': last.get('source') or ''}
    for field in ('latency_ms', 'status_code', 'error', 'via_target', 'unverified', 'note', 'servers', 'down_servers', 'self', 'at'):
        if last.get(field) is not None:
            out[field] = last[field]
    return out


def snapshot(server: str = '', settings=None) -> dict:
    settings = settings if settings is not None else settings_mod.load_settings()
    server   = server or monitor_mod.HOST_SERVER
    data     = monitor_mod._read_state()
    section  = data.get(SECTION) if isinstance(data.get(SECTION), dict) else {}
    meta     = data.get(META) if isinstance(data.get(META), dict) else {}
    routes   = {}
    for key, entry in section.items():
        if monitor_mod._key_server(key) != server or not isinstance(entry, dict):
            continue
        rid = key.split(monitor_mod.KEY_SEP, 1)[1] if monitor_mod.KEY_SEP in key else key
        routes[rid] = _public(entry)
    return {'enabled': enabled(settings), 'interval': interval(settings),
            'checked_at': meta.get('checked_at'), 'routes': routes}

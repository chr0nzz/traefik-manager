import ipaddress
import os
from io import StringIO

from core import config as cfg_mod
from core import env
from core import settings as settings_mod
from core import traefik as traefik_mod

HEADERS_PRESET_FEATURES = (
    'geolocation', 'camera', 'microphone', 'fullscreen', 'autoplay',
    'payment', 'usb', 'display-capture', 'accelerometer', 'gyroscope', 'magnetometer',
)
HEADERS_PRESET_SELF_DEFAULT = ('geolocation', 'camera', 'microphone', 'fullscreen', 'autoplay')
HEADERS_PRESET_HSTS_SECONDS = 31536000
HEADERS_PRESET_REFERRER_DEFAULT = 'strict-origin-when-cross-origin'
HEADERS_PRESET_REFERRER_VALUES = {
    'no-referrer', 'strict-origin-when-cross-origin', 'same-origin',
    'strict-origin', 'origin-when-cross-origin',
}
_PERM_VALUE_TO_TOKEN = {'self': '(self)', 'all': '*', 'block': '()'}
_PERM_TOKEN_TO_VALUE = {'(self)': 'self', '*': 'all', '()': 'block'}
_HEADERS_PRESET_KEYS = {
    'customResponseHeaders', 'stsSeconds', 'stsIncludeSubdomains',
    'contentTypeNosniff', 'frameDeny', 'referrerPolicy',
}


def _trusted_ip_key(cidr: str) -> str:
    try:
        return str(ipaddress.ip_network(str(cidr).strip(), strict=False))
    except ValueError:
        return str(cidr).strip().lower()

def _merge_trusted_ips(existing: list, additions: list) -> tuple:
    seen = {_trusted_ip_key(x) for x in existing}
    added = []
    for cidr in additions:
        key = _trusted_ip_key(cidr)
        if key in seen:
            continue
        seen.add(key)
        added.append(cidr)
    return list(existing) + added, added

def _apply_managed_keys(target: dict, new: dict, managed: tuple) -> None:
    for key in managed:
        if key in new:
            target[key] = new[key]
        elif key in target:
            del target[key]

def _merge_router(section: dict, name: str, new: dict, managed: tuple) -> None:
    existing = section.get(name)
    if not isinstance(existing, dict):
        section[name] = new
        return
    _apply_managed_keys(existing, new, managed)

def _service_is_owned(name: str, svc_def, agent_id: str = '') -> bool:
    from core import service_ownership as own_mod
    from core import settings as settings_mod
    try:
        ledger = settings_mod.load_settings().get('managed_middlewares') or {}
    except Exception:
        return False
    return own_mod.is_owned(str(name).split('@')[0], svc_def, ledger, agent_id)


def _composite_children_rows(services: dict, svc_def) -> list:
    from core import service_ownership as own_mod
    kind = own_mod.composite_type(svc_def)
    if not kind:
        return []
    block = cfg_mod.as_dict(svc_def).get(kind) or {}
    rows = []
    if kind in ('weighted', 'highestRandomWeight'):
        entries = [(c.get('name'), c.get('weight'), None)
                   for c in (block.get('services') or []) if isinstance(c, dict)]
    elif kind == 'mirroring':
        entries = [(block.get('service'), None, None)]
        entries += [(c.get('name'), None, c.get('percent'))
                    for c in (block.get('mirrors') or []) if isinstance(c, dict)]
    else:
        entries = [(block.get('service'), None, None), (block.get('fallback'), None, None)]
    for name, weight, percent in entries:
        if not name:
            continue
        child_lb = cfg_mod.as_dict(cfg_mod.as_dict(services.get(cfg_mod.svc_key(name))).get('loadBalancer'))
        url = next((str(sv.get('url')) for sv in (child_lb.get('servers') or [])
                    if isinstance(sv, dict) and sv.get('url')), '')
        rows.append({'name': str(name), 'url': url,
                     'weight': weight if weight is not None else 1,
                     'percent': percent if percent is not None else 0})
    return rows


def _composite_child_lb(services: dict, svc_def) -> dict:
    from core import service_ownership as own_mod
    for child in own_mod.child_names(svc_def):
        child_def = services.get(cfg_mod.svc_key(child))
        child_lb = cfg_mod.as_dict(cfg_mod.as_dict(child_def).get('loadBalancer'))
        if child_lb:
            return child_lb
    return {}


ROUTE_HC_FIELDS = ('path', 'interval', 'timeout')


def _merge_healthcheck(current, new_hc: dict) -> dict:
    if not isinstance(current, dict):
        return new_hc
    merged = dict(current)
    for key in ROUTE_HC_FIELDS:
        if key in new_hc:
            merged[key] = new_hc[key]
        else:
            merged.pop(key, None)
    return merged


def _merge_service(section: dict, name: str, new_lb: dict, server_key: str, transport_name: str,
                   managed_backends: bool = False) -> None:
    existing = section.get(name)
    existing_lb = existing.get('loadBalancer') if isinstance(existing, dict) else None
    if not isinstance(existing_lb, dict):
        if isinstance(existing, dict) and existing:
            return
        section[name] = {'loadBalancer': new_lb}
        return
    servers = existing_lb.get('servers')
    new_servers = new_lb.get('servers') or []
    if managed_backends:
        existing_lb['servers'] = new_servers
    elif isinstance(servers, list) and servers and isinstance(servers[0], dict) and new_servers:
        servers[0][server_key] = new_servers[0][server_key]
    else:
        existing_lb['servers'] = new_servers
    if managed_backends:
        if 'sticky' in new_lb:
            existing_lb['sticky'] = new_lb['sticky']
        elif 'sticky' in existing_lb:
            del existing_lb['sticky']
        if 'healthCheck' in new_lb:
            existing_lb['healthCheck'] = _merge_healthcheck(existing_lb.get('healthCheck'), new_lb['healthCheck'])
        elif 'healthCheck' in existing_lb:
            del existing_lb['healthCheck']
    if 'passHostHeader' in new_lb:
        existing_lb['passHostHeader'] = new_lb['passHostHeader']
    elif 'passHostHeader' in existing_lb:
        del existing_lb['passHostHeader']
    if 'serversTransport' in new_lb:
        existing_lb['serversTransport'] = new_lb['serversTransport']
    elif existing_lb.get('serversTransport') == transport_name:
        del existing_lb['serversTransport']

def _json_plain(value: object) -> object:
    import json as _json
    try:
        return _json.loads(_json.dumps(value, default=str))
    except (TypeError, ValueError):
        return value

def _headers_preset_defaults() -> dict:
    return {
        'perms': {f: ('self' if f in HEADERS_PRESET_SELF_DEFAULT else 'block') for f in HEADERS_PRESET_FEATURES},
        'hsts': True,
        'nosniff': True,
        'frameDeny': True,
        'referrer': HEADERS_PRESET_REFERRER_DEFAULT,
    }

def _build_permissions_policy(perms: dict) -> str:
    parts = []
    for feat in HEADERS_PRESET_FEATURES:
        token = _PERM_VALUE_TO_TOKEN.get(perms.get(feat, 'block'), '()')
        parts.append(f"{feat}={token}")
    return ', '.join(parts)

def _build_headers_middleware(toggles: dict) -> dict:
    headers = {}
    pp = _build_permissions_policy(toggles.get('perms') or {})
    if pp:
        headers['customResponseHeaders'] = {'Permissions-Policy': pp}
    if toggles.get('hsts'):
        headers['stsSeconds'] = HEADERS_PRESET_HSTS_SECONDS
        headers['stsIncludeSubdomains'] = True
    if toggles.get('nosniff'):
        headers['contentTypeNosniff'] = True
    if toggles.get('frameDeny'):
        headers['frameDeny'] = True
    ref = (toggles.get('referrer') or '').strip()
    if ref:
        headers['referrerPolicy'] = ref
    return {'headers': headers}

def _parse_permissions_policy(value) -> dict | None:
    if not isinstance(value, str):
        return None
    perms = {f: 'block' for f in HEADERS_PRESET_FEATURES}
    for token in value.split(','):
        token = token.strip()
        if not token or '=' not in token:
            return None
        feat, _, raw = token.partition('=')
        feat = feat.strip()
        val = _PERM_TOKEN_TO_VALUE.get(raw.strip())
        if feat not in HEADERS_PRESET_FEATURES or val is None:
            return None
        perms[feat] = val
    return perms

def _decode_headers_middleware(body) -> dict | None:
    plain = _json_plain(body)
    if not isinstance(plain, dict) or set(plain.keys()) != {'headers'}:
        return None
    h = plain.get('headers')
    if not isinstance(h, dict) or not set(h.keys()).issubset(_HEADERS_PRESET_KEYS):
        return None
    toggles = {
        'perms': {f: 'block' for f in HEADERS_PRESET_FEATURES},
        'hsts': False, 'nosniff': False, 'frameDeny': False, 'referrer': '',
    }
    crh = h.get('customResponseHeaders')
    if crh is not None:
        if not isinstance(crh, dict) or set(crh.keys()) - {'Permissions-Policy'}:
            return None
        parsed = _parse_permissions_policy(crh.get('Permissions-Policy'))
        if parsed is None:
            return None
        toggles['perms'] = parsed
    if 'stsSeconds' in h:
        toggles['hsts'] = True
    if 'contentTypeNosniff' in h:
        toggles['nosniff'] = True
    if 'frameDeny' in h:
        toggles['frameDeny'] = True
    if 'referrerPolicy' in h:
        if h.get('referrerPolicy') not in HEADERS_PRESET_REFERRER_VALUES:
            return None
        toggles['referrer'] = h['referrerPolicy']
    if _build_headers_middleware(toggles) != plain:
        return None
    return toggles

def _server_field(servers, key, default='N/A'):
    if not servers:
        return default
    first = servers[0]
    if isinstance(first, dict):
        return first.get(key, default)
    if isinstance(first, str) and first.strip():
        return first.strip()
    return default


def _to_list(val, default=None):
    if val is None:
        return default if default is not None else []
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        return [val]
    return list(val) if hasattr(val, '__iter__') else []

def _service_type(svc_def) -> str:
    if isinstance(svc_def, dict):
        for t in ('weighted', 'mirroring', 'failover', 'highestRandomWeight'):
            if t in svc_def:
                return t
    return 'loadBalancer'

def _build_apps(config, config_file='', extra_http_svcs=None, extra_tcp_svcs=None, extra_udp_svcs=None, api_svc_urls=None, agent_id=''):
    apps = []
    http_config = config.get('http') or {}
    http_svcs = dict(http_config.get('services') or {})
    if extra_http_svcs:
        for k, v in extra_http_svcs.items():
            if k not in http_svcs:
                http_svcs[k] = v
    for rname, rdata in (http_config.get('routers') or {}).items():
        if not isinstance(rdata, dict):
            continue
        svc_name = rdata.get('service', '')
        svc_key  = cfg_mod.svc_key(svc_name)
        target_url = 'N/A'
        lb = {}
        if svc_key in http_svcs:
            lb = cfg_mod.as_dict(cfg_mod.as_dict(http_svcs[svc_key]).get('loadBalancer'))
            if not lb:
                lb = _composite_child_lb(http_svcs, http_svcs[svc_key])
            servers = lb.get('servers', [])
            if servers:
                target_url = _server_field(servers, 'url', 'Unknown')
        if target_url == 'N/A' and api_svc_urls:
            target_url = api_svc_urls.get(f'http:{svc_key}', 'N/A')
        if target_url == 'N/A' and str(svc_name).endswith('@internal'):
            target_url = str(svc_name)
        app_id = f"{config_file}::{rname}" if (env.MULTI_CONFIG and config_file) else rname
        tls_http = rdata.get('tls', {})
        tls_on   = 'tls' in rdata and rdata.get('tls') is not False
        transport_name = lb.get('serversTransport', '')
        transports_cfg = http_config.get('serversTransports') or {}
        transport_cfg  = cfg_mod.as_dict(transports_cfg.get(transport_name)) if transport_name else {}
        insecure  = bool(transport_cfg.get('insecureSkipVerify', False))
        streaming = 'forwardingTimeouts' in transport_cfg
        apps.append({'id': app_id, 'name': rname, 'rule': rdata.get('rule', ''),
                     'service_name': svc_name, 'target': target_url,
                     'middlewares': _to_list(rdata.get('middlewares')),
                     'entryPoints': _to_list(rdata.get('entryPoints')), 'protocol': 'http',
                     'tls': tls_on, 'enabled': True,
                     'passHostHeader': lb.get('passHostHeader', True),
                     'certResolver': tls_http.get('certResolver', '') if isinstance(tls_http, dict) else '',
                     'tlsDomains': tls_http.get('domains', []) if isinstance(tls_http, dict) else [],
                     'tlsOptionsProfile': tls_http.get('options', '') if isinstance(tls_http, dict) else '',
                     'insecureSkipVerify': insecure,
                     'streaming': streaming,
                     'servers': [str(s.get('url', '')) for s in (lb.get('servers') or []) if isinstance(s, dict) and s.get('url')],
                     'sticky': (lb.get('sticky') or {}).get('cookie', {}) if isinstance(lb.get('sticky'), dict) else {},
                     'stickyEnabled': isinstance(lb.get('sticky'), dict),
                     'healthCheck': lb.get('healthCheck') if isinstance(lb.get('healthCheck'), dict) else {},
                     'priority': rdata.get('priority'),
                     'serviceType': _service_type(http_svcs.get(svc_key)),
                     'compositeChildren': _composite_children_rows(http_svcs, http_svcs.get(svc_key)),
                     'serviceOwned': _service_is_owned(svc_key, http_svcs.get(svc_key), agent_id),
                     'configFile': config_file, 'provider': 'file'})
    tcp_config = config.get('tcp') or {}
    tcp_svcs = dict(tcp_config.get('services') or {})
    if extra_tcp_svcs:
        for k, v in extra_tcp_svcs.items():
            if k not in tcp_svcs:
                tcp_svcs[k] = v
    for rname, rdata in (tcp_config.get('routers') or {}).items():
        if not isinstance(rdata, dict):
            continue
        svc_name = rdata.get('service', '')
        svc_key  = cfg_mod.svc_key(svc_name)
        target = 'N/A'
        if svc_key in tcp_svcs:
            servers = cfg_mod.as_dict(cfg_mod.as_dict(tcp_svcs[svc_key]).get('loadBalancer')).get('servers', [])
            if servers:
                target = _server_field(servers, 'address')
        if target == 'N/A' and api_svc_urls:
            target = api_svc_urls.get(f'tcp:{svc_key}', 'N/A')
        app_id = f"{config_file}::{rname}" if (env.MULTI_CONFIG and config_file) else rname
        tls_tcp = None if ('tls' not in rdata or rdata.get('tls') is False) else cfg_mod.as_dict(rdata.get('tls'))
        apps.append({'id': app_id, 'name': rname, 'rule': rdata.get('rule', ''),
                     'service_name': svc_name, 'target': target,
                     'middlewares': _to_list(rdata.get('middlewares')), 'entryPoints': _to_list(rdata.get('entryPoints')),
                     'protocol': 'tcp', 'tls': tls_tcp, 'enabled': True,
                     'certResolver': tls_tcp.get('certResolver', '') if isinstance(tls_tcp, dict) else '',
                     'serviceType': _service_type(tcp_svcs.get(svc_key)),
                     'servers': [str(s.get('address', '')) for s in (cfg_mod.as_dict(cfg_mod.as_dict(tcp_svcs.get(svc_key)).get('loadBalancer')).get('servers') or []) if isinstance(s, dict) and s.get('address')],
                     'priority': rdata.get('priority'),
                     'configFile': config_file, 'provider': 'file'})
    udp_config = config.get('udp') or {}
    udp_svcs = dict(udp_config.get('services') or {})
    if extra_udp_svcs:
        for k, v in extra_udp_svcs.items():
            if k not in udp_svcs:
                udp_svcs[k] = v
    for rname, rdata in (udp_config.get('routers') or {}).items():
        if not isinstance(rdata, dict):
            continue
        svc_name = rdata.get('service', '')
        svc_key  = cfg_mod.svc_key(svc_name)
        target = 'N/A'
        if svc_key in udp_svcs:
            servers = cfg_mod.as_dict(cfg_mod.as_dict(udp_svcs[svc_key]).get('loadBalancer')).get('servers', [])
            if servers:
                target = _server_field(servers, 'address')
        if target == 'N/A' and api_svc_urls:
            target = api_svc_urls.get(f'udp:{svc_key}', 'N/A')
        app_id = f"{config_file}::{rname}" if (env.MULTI_CONFIG and config_file) else rname
        apps.append({'id': app_id, 'name': rname, 'rule': '',
                     'service_name': svc_name, 'target': target,
                     'middlewares': [], 'entryPoints': _to_list(rdata.get('entryPoints')),
                     'protocol': 'udp', 'tls': False, 'enabled': True,
                     'serviceType': _service_type(udp_svcs.get(svc_key)),
                     'servers': [str(s.get('address', '')) for s in (cfg_mod.as_dict(cfg_mod.as_dict(udp_svcs.get(svc_key)).get('loadBalancer')).get('servers') or []) if isinstance(s, dict) and s.get('address')],
                     'configFile': config_file, 'provider': 'file'})
    return apps

def _build_middlewares(config, config_file=''):
    middlewares = []
    for mname, mdata in config.get('http', {}).get('middlewares', {}).items():
        buf = StringIO()
        cfg_mod.yaml.dump(mdata, buf)
        middlewares.append({'name': mname, 'yaml': buf.getvalue(), 'type': 'http', 'configFile': config_file})
    for mname, mdata in config.get('tcp', {}).get('middlewares', {}).items():
        buf = StringIO()
        cfg_mod.yaml.dump(mdata, buf)
        middlewares.append({'name': mname, 'yaml': buf.getvalue(), 'type': 'tcp', 'configFile': config_file})
    return middlewares

def _traefik_router_ep_map(all_routers: dict) -> dict:
    ep_map = {}
    for proto, routers in all_routers.items():
        for r in routers:
            name = r.get('name', '')
            key  = name.split('@')[0] if '@' in name else name
            eps  = r.get('entryPoints', [])
            if key and eps:
                ep_map[key] = eps
    return ep_map

def _traefik_service_url_map(all_services: dict = None):
    if all_services is None:
        all_services = {}
        for proto in ('http', 'tcp', 'udp'):
            all_services[proto] = traefik_mod.traefik_api_get_all(f'/api/{proto}/services') or []
    url_map = {}
    for proto, addr_key in (('http', 'url'), ('tcp', 'address'), ('udp', 'address')):
        for svc in all_services.get(proto, []):
            key = cfg_mod.svc_key(svc.get('name', ''))
            servers = svc.get('loadBalancer', {}).get('servers', [])
            if servers and isinstance(servers[0], dict) and addr_key in servers[0]:
                url_map[f'{proto}:{key}'] = servers[0][addr_key]
    return url_map

def _build_external_routes(all_routers: dict, svc_urls: dict, include_internal=False):
    routes = []
    for proto in ('http', 'tcp', 'udp'):
        for r in all_routers.get(proto, []):
            provider = r.get('provider', '')
            if not provider or provider == 'file':
                continue
            if not include_internal and provider == 'internal':
                continue
            name = r.get('name', '')
            display_name = name.split('@')[0] if '@' in name else name
            svc_name = r.get('service', '')
            target = svc_urls.get(f'{proto}:{cfg_mod.svc_key(svc_name)}', svc_name or 'N/A')
            tls = r.get('tls', {})
            routes.append({
                'id':           name,
                'name':         display_name,
                'rule':         r.get('rule', ''),
                'service_name': svc_name,
                'target':       target,
                'middlewares':  r.get('middlewares') or [],
                'entryPoints':  r.get('entryPoints') or [],
                'protocol':     proto,
                'tls':          bool(tls),
                'enabled':      r.get('status', 'enabled') == 'enabled',
                'provider':     provider,
                'configFile':   '',
            })
    return routes

def _entrypoint_mw_map() -> dict:
    path = settings_mod._get_static_config_path()
    if not path or not os.path.isfile(path):
        return {}
    try:
        with open(path, 'r') as f:
            cfg = cfg_mod.yaml.load(f) or {}
        result = {}
        for ep_name, ep_val in cfg.get('entryPoints', {}).items():
            mws = (ep_val or {}).get('http', {}).get('middlewares', [])
            if mws:
                result[ep_name] = [str(m) for m in mws]
        return result
    except Exception:
        return {}

def _build_all_apps(include_external=True, include_internal=False):
    all_apps = []
    all_middlewares = []
    loaded = [(os.path.basename(p) if (env.MULTI_CONFIG or env.ACTIVE_CONFIG_DIR) else '', cfg_mod._load_config_display(p)) for p in env.CONFIG_PATHS]
    combined_http = {}
    combined_tcp  = {}
    combined_udp  = {}
    for _, cfg in loaded:
        for k, v in ((cfg.get('http') or {}).get('services') or {}).items():
            combined_http.setdefault(k, v)
        for k, v in ((cfg.get('tcp') or {}).get('services') or {}).items():
            combined_tcp.setdefault(k, v)
        for k, v in ((cfg.get('udp') or {}).get('services') or {}).items():
            combined_udp.setdefault(k, v)
    ep_mw_map = _entrypoint_mw_map()
    if include_external:
        all_routers, all_services = traefik_mod._fetch_traefik_routers_and_services()
        api_svc_urls  = _traefik_service_url_map(all_services)
        router_ep_map = _traefik_router_ep_map(all_routers)
    else:
        all_routers = all_services = {}
        api_svc_urls  = {}
        router_ep_map = {}
    for cf, config in loaded:
        all_apps.extend(_build_apps(config, cf, combined_http, combined_tcp, combined_udp, api_svc_urls))
        all_middlewares.extend(_build_middlewares(config, cf))
    if include_external:
        all_apps.extend(_build_external_routes(all_routers, api_svc_urls, include_internal=include_internal))
    for app in all_apps:
        if not app.get('entryPoints') and app.get('name') in router_ep_map:
            app['entryPoints'] = router_ep_map[app['name']]
        ep_mws = []
        for ep in app.get('entryPoints', []):
            for mw in ep_mw_map.get(ep, []):
                if mw not in ep_mws:
                    ep_mws.append(mw)
        app['entrypointMiddlewares'] = ep_mws
    settings = settings_mod.load_settings()
    _mm_ledger = settings.get('managed_middlewares', {})
    _http_mw_by_file = {cf: ((cfg.get('http') or {}).get('middlewares') or {}) for cf, cfg in loaded}
    for app in all_apps:
        if app.get('protocol') != 'http' or app.get('provider') != 'file':
            continue
        hdr_mw_name = f"{app.get('name')}-headers"
        hdr_body    = _http_mw_by_file.get(app.get('configFile', ''), {}).get(hdr_mw_name)
        owned       = hdr_mw_name in _mm_ledger
        decoded     = _decode_headers_middleware(hdr_body) if (owned and hdr_body is not None) else None
        if not owned or hdr_body is None:
            hdr_state = 'off'
        elif decoded is not None:
            hdr_state = 'toggles'
        else:
            hdr_state = 'custom'
        app['headersPreset'] = {
            'owned':   owned,
            'exists':  hdr_body is not None,
            'state':   hdr_state,
            'toggles': decoded if decoded is not None else _headers_preset_defaults(),
        }
    for route_id, rdata in settings.get('disabled_routes', {}).items():
        if route_id.startswith('agent_'):
            continue
        rname    = route_id.split('::', 1)[1] if '::' in route_id else route_id
        proto    = rdata.get('protocol', 'http')
        router   = rdata.get('router', {})
        svc_name = router.get('service', '')
        svc      = rdata.get('service', {})
        cf       = rdata.get('configFile', '')
        if proto == 'http':
            servers    = svc.get('loadBalancer', {}).get('servers', [])
            target_url = _server_field(servers, 'url')
            all_apps.append({'id': route_id, 'name': rname, 'rule': router.get('rule', ''),
                             'service_name': svc_name, 'target': target_url,
                             'middlewares': router.get('middlewares', []),
                             'entryPoints': router.get('entryPoints', []),
                             'protocol': 'http', 'tls': 'tls' in router and router.get('tls') is not False, 'enabled': False,
                             'passHostHeader': svc.get('loadBalancer', {}).get('passHostHeader', True),
                             'serviceType': _service_type(svc),
                             'configFile': cf, 'provider': 'file', 'entrypointMiddlewares': []})
        elif proto == 'tcp':
            servers = svc.get('loadBalancer', {}).get('servers', [])
            target  = _server_field(servers, 'address')
            all_apps.append({'id': route_id, 'name': rname, 'rule': router.get('rule', ''),
                             'service_name': svc_name, 'target': target,
                             'middlewares': router.get('middlewares', []), 'entryPoints': router.get('entryPoints', []),
                             'protocol': 'tcp', 'tls': None if ('tls' not in router or router.get('tls') is False) else cfg_mod.as_dict(router.get('tls')), 'enabled': False,
                             'serviceType': _service_type(svc),
                             'configFile': cf, 'provider': 'file'})
        else:
            servers = svc.get('loadBalancer', {}).get('servers', [])
            target  = _server_field(servers, 'address')
            all_apps.append({'id': route_id, 'name': rname, 'rule': '',
                             'service_name': svc_name, 'target': target,
                             'middlewares': [], 'entryPoints': router.get('entryPoints', []),
                             'protocol': 'udp', 'tls': False, 'enabled': False,
                             'serviceType': _service_type(svc),
                             'configFile': cf, 'provider': 'file'})
    return all_apps, all_middlewares

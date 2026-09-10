import os
import threading

from core import config, env
from core.env import logger

SELF_ROUTE_FILENAME = 'traefik-manager-self.yml'


def _self_route_path() -> str:
    if env.ACTIVE_CONFIG_DIR:
        return os.path.join(env.ACTIVE_CONFIG_DIR, SELF_ROUTE_FILENAME)
    return os.path.join(os.path.dirname(os.path.abspath(env.CONFIG_PATH)), SELF_ROUTE_FILENAME)


def _write_self_route(domain: str, service_url: str, cert_resolver: str, router_name: str = 'traefik-manager', entry_point: str = 'websecure') -> None:
    router_entry = {
        'rule': f'Host(`{domain}`)',
        'entryPoints': [entry_point or 'websecure'],
        'service': router_name,
        'tls': {'certResolver': cert_resolver} if cert_resolver and cert_resolver.lower() != 'none' else {},
    }
    service_entry = {
        'loadBalancer': {
            'servers': [{'url': service_url}]
        }
    }
    if env.ACTIVE_CONFIG_DIR:
        path = _self_route_path()
        content = {
            'http': {
                'routers': {router_name: router_entry},
                'services': {router_name: service_entry},
            }
        }
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        tmp = f"{path}.tmp.{os.getpid()}.{threading.get_ident()}"
        try:
            with open(tmp, 'w') as f:
                config.yaml.dump(content, f)
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
        logger.info(f"Self-route written to new file: {path}")
    else:
        cfg = config.load_config(env.CONFIG_PATH)
        cfg.setdefault('http', {}).setdefault('routers', {})[router_name] = router_entry
        cfg['http'].setdefault('services', {})[router_name] = service_entry
        config.save_config(cfg, env.CONFIG_PATH)
        logger.info(f"Self-route updated in existing config: {env.CONFIG_PATH} (router: {router_name})")


def _delete_self_route(router_name: str = 'traefik-manager') -> None:
    if env.ACTIVE_CONFIG_DIR:
        path = _self_route_path()
        if os.path.exists(path):
            os.remove(path)
            logger.info(f"Self-route file deleted: {path}")
    else:
        cfg = config.load_config(env.CONFIG_PATH)
        http = cfg.get('http', {})
        http.get('routers', {}).pop(router_name, None)
        http.get('services', {}).pop(router_name, None)
        config.save_config(config.strip_empty_sections(cfg), env.CONFIG_PATH)
        logger.info(f"Self-route '{router_name}' removed from config: {env.CONFIG_PATH}")


def _detect_self_route_domain() -> str:
    for cfg_path in env.CONFIG_PATHS:
        if not os.path.exists(cfg_path):
            continue
        try:
            with open(cfg_path, 'r') as f:
                sanitized, _ = config.sanitize_go_templates(f.read())
            data = config.yaml.load(sanitized) or {}
            routers = (data.get('http') or {}).get('routers') or {}
            services = (data.get('http') or {}).get('services') or {}
            for rname, rdata in routers.items():
                svc_name = (rdata.get('service') or '').split('@')[0]
                svc = services.get(svc_name) or {}
                servers = ((svc.get('loadBalancer') or {}).get('servers') or [])
                urls = [str(s.get('url', '')) for s in servers if s.get('url')]
                if any('traefik-manager' in u or ':5000' in u for u in urls):
                    hosts = config.rule_hosts(rdata.get('rule', ''))
                    if hosts:
                        return hosts[0]
        except Exception:
            continue
    return ''


def _detect_self_route_from_own_labels() -> tuple[str, str]:
    try:
        import docker as _docker
        client = _docker.from_env()
        own_id = os.environ.get('HOSTNAME', '')
        for c in client.containers.list():
            if not (c.id.startswith(own_id) or 'traefik-manager' in c.name):
                continue
            labels = c.labels or {}
            domain = ''
            svc_url = ''
            for k, v in labels.items():
                if k.startswith('traefik.http.routers.') and k.endswith('.rule'):
                    hosts = config.rule_hosts(v)
                    if hosts:
                        domain = hosts[0]
                if k.startswith('traefik.http.services.') and k.endswith('.loadbalancer.server.url'):
                    svc_url = v
            if domain:
                return domain, svc_url or 'http://traefik-manager:5000'
    except Exception:
        pass
    return '', ''


def _find_existing_self_route(hostname: str) -> dict:
    for cfg_path in env.CONFIG_PATHS:
        if not os.path.exists(cfg_path):
            continue
        try:
            with open(cfg_path, 'r') as f:
                sanitized, _ = config.sanitize_go_templates(f.read())
            data = config.yaml.load(sanitized) or {}
            routers  = (data.get('http') or {}).get('routers') or {}
            services = (data.get('http') or {}).get('services') or {}
            for rname, rdata in routers.items():
                hosts = config.rule_hosts(rdata.get('rule', ''))
                if hosts and hosts[0].lower() == hostname.lower():
                    svc_name = (rdata.get('service') or '').split('@')[0]
                    svc = services.get(svc_name) or {}
                    servers = ((svc.get('loadBalancer') or {}).get('servers') or [])
                    svc_url     = next((str(s['url']) for s in servers if s.get('url')), '')
                    entry_pts   = rdata.get('entryPoints') or ['websecure']
                    entry_point = entry_pts[0] if entry_pts else 'websecure'
                    return {'domain': hostname, 'service_url': svc_url, 'router_name': rname, 'entry_point': entry_point, 'found': True}
        except Exception:
            continue
    return {}

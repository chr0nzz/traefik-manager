TAB_FOR_PROVIDER = {
    'docker': 'docker',
    'swarm': 'swarm',
    'kubernetes': 'kubernetes',
    'kubernetescrd': 'kubernetes',
    'kubernetesingress': 'kubernetes',
    'kubernetesgateway': 'kubernetes',
    'nomad': 'nomad',
    'ecs': 'ecs',
    'consulcatalog': 'consulcatalog',
    'consul': 'consul',
    'etcd': 'etcd',
    'redis': 'redis',
    'zookeeper': 'zookeeper',
    'http': 'http_provider',
    'internal': 'internal',
}

SKIP = ('file', 'acme', 'plugin')


def tab_for(provider) -> str:
    key = str(provider or '').strip().lower().lstrip('@')
    if not key or key in SKIP:
        return ''
    return TAB_FOR_PROVIDER.get(key, '')


def tabs_from_overview(overview) -> set:
    if not isinstance(overview, dict):
        return set()
    found = set()
    for name in overview.get('providers') or []:
        tab = tab_for(name)
        if tab:
            found.add(tab)
    return found


def tabs_from_routers(payload) -> set:
    found = set()
    rows = []
    if isinstance(payload, dict):
        for proto in ('http', 'tcp', 'udp'):
            value = payload.get(proto)
            if isinstance(value, list):
                rows.extend(value)
    elif isinstance(payload, list):
        rows = payload
    for row in rows:
        if not isinstance(row, dict):
            continue
        provider = row.get('provider') or str(row.get('name') or '').rpartition('@')[2]
        tab = tab_for(provider)
        if tab:
            found.add(tab)
    return found


def newly_seen(detected, seen) -> list:
    known = {str(t) for t in (seen or [])}
    return sorted(t for t in (detected or set()) if t not in known)

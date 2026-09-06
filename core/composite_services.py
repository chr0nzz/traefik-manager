from core import service_ownership as own

MANUAL = 'manual'
SERVICE = 'service'
TYPES = ('weighted', 'mirroring', 'failover')


def child_service_name(route_name: str, index: int) -> str:
    return f'{route_name}-backend-{index + 1}'


def _int(value, default):
    try:
        out = int(value)
    except (TypeError, ValueError):
        return default
    return out


def normalise_children(raw) -> list:
    out = []
    for item in (raw or []):
        if not isinstance(item, dict):
            continue
        kind = str(item.get('kind') or '').strip().lower()
        if kind == SERVICE:
            name = str(item.get('name') or '').strip()
            if not name:
                continue
            out.append({'kind': SERVICE, 'name': name,
                        'weight': _int(item.get('weight'), 1),
                        'percent': _int(item.get('percent'), 0)})
        else:
            address = str(item.get('address') or '').strip()
            if not address:
                continue
            out.append({'kind': MANUAL, 'address': address,
                        'scheme': str(item.get('scheme') or 'http').strip() or 'http',
                        'weight': _int(item.get('weight'), 1),
                        'percent': _int(item.get('percent'), 0)})
    return out


def _child_url(child) -> str:
    address = child['address']
    if '://' in address:
        return address
    return f"{child['scheme']}://{address}"


def build(route_name: str, composite_type: str, children: list, lb_extra: dict = None) -> tuple:
    children = normalise_children(children)
    if not children:
        return None, {}, []
    if composite_type == 'failover':
        children = children[:2]
    if composite_type == 'loadBalancer':
        servers = [{'url': _child_url(c)} for c in children if c['kind'] == MANUAL]
        if not servers:
            return None, {}, []
        return {'loadBalancer': {'servers': servers}}, {}, []
    if composite_type not in TYPES:
        return None, {}, []

    owned = {}
    names = []
    for index, child in enumerate(children):
        if child['kind'] == SERVICE:
            names.append(child['name'])
            continue
        name = child_service_name(route_name, index)
        child_lb = {'servers': [{'url': _child_url(child)}]}
        for key, value in (lb_extra or {}).items():
            if value is not None:
                child_lb[key] = value
        owned[name] = {'loadBalancer': child_lb}
        names.append(name)

    if composite_type == 'weighted':
        block = {'weighted': {'services': [
            {'name': n, 'weight': c['weight']} for n, c in zip(names, children)]}}
    elif composite_type == 'mirroring':
        block = {'mirroring': {'service': names[0], 'mirrors': [
            {'name': n, 'percent': c['percent']}
            for n, c in zip(names[1:], children[1:])]}}
        if not block['mirroring']['mirrors']:
            del block['mirroring']['mirrors']
    else:
        block = {'failover': {'service': names[0]}}
        if len(names) > 1:
            block['failover']['fallback'] = names[1]

    return block, owned, names


AUTHORED_KEYS = ('services', 'service', 'mirrors', 'fallback', 'servers')


def merge_into(section: dict, parent_name: str, block: dict, owned: dict) -> None:
    existing = section.get(parent_name)
    if isinstance(existing, dict):
        for stale in TYPES + ('loadBalancer', 'highestRandomWeight'):
            if stale in existing and stale not in block:
                del existing[stale]
        for key, value in block.items():
            current = existing.get(key)
            if isinstance(current, dict) and isinstance(value, dict):
                for inner in AUTHORED_KEYS:
                    if inner in value:
                        current[inner] = value[inner]
                    elif inner in current:
                        del current[inner]
            else:
                existing[key] = value
    else:
        section[parent_name] = dict(block)
    for name, child_block in owned.items():
        child = section.get(name)
        if isinstance(child, dict) and isinstance(child.get('loadBalancer'), dict):
            child['loadBalancer']['servers'] = child_block['loadBalancer']['servers']
        else:
            section[name] = child_block


def drop_orphan_children(section: dict, route_name: str, keep: set) -> list:
    prefix = f'{route_name}-backend-'
    dropped = []
    for name in [n for n in section if isinstance(n, str) and n.startswith(prefix)]:
        if name not in keep:
            del section[name]
            dropped.append(name)
    return dropped


def ledger_entries(parent_name: str, block: dict, owned: dict,
                   config_file: str = '', agent_id: str = '') -> dict:
    out = {own.ledger_key(parent_name, agent_id): own.ledger_entry(block, config_file)}
    for name, child_block in owned.items():
        out[own.ledger_key(name, agent_id)] = {
            'kind':   own.LEDGER_KIND,
            'type':   'loadBalancer',
            'child':  True,
            'parent': parent_name,
            'file':   config_file,
        }
    return out


def find_cycle(section, name: str, children) -> str:
    from core.service_ownership import child_names
    bare = str(name or '').split('@')[0]
    for child in normalise_children(children):
        if child['kind'] != SERVICE:
            continue
        start = str(child['name']).split('@')[0]
        if start == bare:
            return start
        seen = set()
        stack = [start]
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            for nxt in child_names((section or {}).get(cur)):
                nxt = str(nxt).split('@')[0]
                if nxt == bare:
                    return start
                stack.append(nxt)
    return ''

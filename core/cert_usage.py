from datetime import datetime, timezone

from core import config as cfg_mod

FILE_RESOLVER = 'file'

UNKNOWN_NO_ROUTERS  = 'the router list is incomplete, so nothing is called unused'
UNKNOWN_CONFIG      = 'a config file could not be read, so nothing is called unused'
UNKNOWN_REGEXP      = 'a router matches hosts by regular expression, so its certificates cannot be worked out'
UNKNOWN_CATCH_ALL   = 'a catch-all router can be served any certificate, so nothing is called unused'
UNKNOWN_NO_STATIC   = 'the static config is not readable, so resolvers cannot be checked'


def normalize(name) -> str:
    text = str(name or '').strip().rstrip('.').lower()
    if not text or text.isascii():
        return text
    out = []
    for label in text.split('.'):
        if label.isascii():
            out.append(label)
            continue
        try:
            out.append(label.encode('idna').decode('ascii'))
        except (UnicodeError, ValueError):
            return text
    return '.'.join(out)


def cert_domains(cert) -> set:
    if not isinstance(cert, dict):
        return set()
    names = [cert.get('main')] + list(cert.get('sans') or [])
    return {n for n in (normalize(v) for v in names) if n}


def cert_covers_host(cert_domain: str, host: str) -> bool:
    if not cert_domain or not host:
        return False
    if cert_domain == host:
        return True
    labels = host.split('.')
    labels[0] = '*'
    return cert_domain == '.'.join(labels)


def router_pattern_covers(pattern: str, cert_domain: str) -> bool:
    served = normalize(pattern)
    covered = normalize(cert_domain)
    if not served or not covered:
        return False
    if served == '*':
        return True
    if served == covered:
        return True
    if served.startswith('**.'):
        suffix = served[3:]
        bare = covered[2:] if covered.startswith('*.') else covered
        return bool(suffix) and (bare == suffix or bare.endswith('.' + suffix))
    if served.startswith('*.'):
        if cert_covers_host(covered, served):
            return True
        suffix = served[2:]
        return bool(suffix) and covered.count('.') == suffix.count('.') + 1 and covered.endswith('.' + suffix)
    return cert_covers_host(covered, served)


def terminates_tls(app) -> bool:
    tls = app.get('tls') if isinstance(app, dict) else None
    if not tls:
        return False
    if isinstance(tls, dict) and tls.get('passthrough'):
        return False
    return True


def served_names(apps) -> tuple:
    names   = set()
    opaque  = False
    catch   = False
    for app in apps or []:
        if not isinstance(app, dict):
            continue
        patterns, is_opaque = cfg_mod.rule_host_patterns(app.get('rule'))
        tls_on = terminates_tls(app)
        if is_opaque and tls_on:
            opaque = True
        for pattern in patterns:
            clean = normalize(pattern)
            if not clean:
                continue
            if clean == '*' and tls_on:
                catch = True
            names.add(clean)
        for entry in app.get('tlsDomains') or []:
            if not isinstance(entry, dict):
                continue
            names.add(normalize(entry.get('main')))
            for san in entry.get('sans') or []:
                names.add(normalize(san))
    names.discard('')
    return names, opaque, catch


def generated_cert_names(configs) -> set:
    names = set()
    for config in configs or []:
        stores = (cfg_mod.as_dict(config).get('tls') or {}).get('stores') or {}
        for store in cfg_mod.as_dict(stores).values():
            generated = cfg_mod.as_dict(store).get('defaultGeneratedCert') or {}
            domain = cfg_mod.as_dict(generated).get('domain') or {}
            names.add(normalize(cfg_mod.as_dict(domain).get('main')))
            for san in cfg_mod.as_dict(domain).get('sans') or []:
                names.add(normalize(san))
    names.discard('')
    return names


def is_expired(cert, now=None) -> bool:
    raw = (cert or {}).get('not_after')
    if not raw:
        return False
    try:
        when = datetime.strptime(str(raw), '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return False
    return when < (now or datetime.now(timezone.utc))


def analyze(certs, apps, configs=(), resolvers=None, routers_ok=True, configs_ok=True, now=None) -> dict:
    names, opaque, catch = served_names(apps)
    names |= generated_cert_names(configs)

    if not routers_ok:
        unused_block = UNKNOWN_NO_ROUTERS
    elif not configs_ok:
        unused_block = UNKNOWN_CONFIG
    elif opaque:
        unused_block = UNKNOWN_REGEXP
    elif catch:
        unused_block = UNKNOWN_CATCH_ALL
    else:
        unused_block = ''

    known = None if resolvers is None else {str(r).strip() for r in resolvers if str(r).strip()}

    rows = []
    for cert in certs or []:
        if not isinstance(cert, dict):
            continue
        domains = cert_domains(cert)
        row = {'main': cert.get('main', ''), 'resolver': cert.get('resolver', ''),
               'source': cert.get('source', ''), 'expired': is_expired(cert, now),
               'unused': False, 'orphaned': False, 'why': ''}
        if unused_block:
            row['why'] = unused_block
        elif not domains:
            row['why'] = 'this certificate names no domain'
        else:
            row['unused'] = not any(router_pattern_covers(served, domain)
                                    for served in names for domain in domains)
        if cert.get('resolver') and cert.get('resolver') != FILE_RESOLVER:
            if known is None:
                row['resolver_why'] = UNKNOWN_NO_STATIC
            else:
                row['orphaned'] = cert['resolver'] not in known
        rows.append(row)
    return {'certs': rows, 'unused_known': not unused_block, 'why': unused_block,
            'resolvers_known': known is not None}

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_no_route_is_bound_to_a_private_helper(app_module):
    bound = {}
    for rule in app_module.app.url_map.iter_rules():
        if rule.endpoint.startswith('_'):
            bound[rule.endpoint] = str(rule)
    assert not bound, (
        'a helper defined between @app.route and its view steals the URL, and the endpoint '
        'silently answers with the helper return value:\n  '
        + '\n  '.join(f'{k} -> {v}' for k, v in sorted(bound.items())))


def test_the_services_endpoint_is_bound_to_its_own_view(app_module):
    endpoints = {str(r): r.endpoint for r in app_module.app.url_map.iter_rules()}
    assert endpoints.get('/api/traefik/services') == 'api_services'


def test_adopting_a_service_never_writes_config(app_module):
    with open(os.path.join(ROOT, 'app.py'), encoding='utf-8') as fh:
        src = fh.read()
    start = src.index('def api_service_ownership(')
    body = src[start:src.index('\ndef ', start + 1)]
    for writer in ('save_config', 'write_config', 'atomic_write', 'create_backup'):
        assert writer not in body, \
            f'adopting must touch the ledger only, but the view calls {writer}'
    assert 'update_settings' in body or 'save_settings' in body, \
        'adopting has to record ownership in the settings ledger'

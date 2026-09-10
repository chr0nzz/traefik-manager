from conftest import post_form, read_config, write_config

HDR = {'X-CSRF-Token': 'testtoken', 'X-Requested-With': 'fetch'}


def _save_noop(client, name='redirect-only', **extra):
    form = dict(serviceName=name, subdomain=f'{name}.example.com', protocol='http',
                scheme='http', targetIp='', targetPort='', serviceRef='noop@internal')
    form.update(extra)
    return post_form(client, '/save', **form)


def test_a_router_can_point_at_noop_with_no_backend(client):
    r = _save_noop(client)
    assert r.status_code < 400, r.get_data(as_text=True)[:200]
    cfg = read_config()
    assert cfg['http']['routers']['redirect-only']['service'] == 'noop@internal'
    assert 'redirect-only-service' not in (cfg['http'].get('services') or {}), \
        'a noop router must not invent a backend service'


def test_a_noop_router_is_listed_instead_of_silently_dropped(client):
    _save_noop(client)
    apps = client.get('/api/routes', headers=HDR).get_json()['apps']
    names = [a['name'] for a in apps]
    assert 'redirect-only' in names, 'the route was written but hidden from its own list: %r' % names
    app = next(a for a in apps if a['name'] == 'redirect-only')
    assert app['service_name'] == 'noop@internal'
    assert app['target'] == 'noop@internal', 'a backendless route should say so, not read N/A'


def test_a_route_you_wrote_is_listed_whatever_service_it_names(client):
    write_config("""
http:
  routers:
    dash:
      rule: Host(`dash.example.com`)
      service: api@internal
  services: {}
""")
    names = [a['name'] for a in client.get('/api/routes', headers=HDR).get_json()['apps']]
    assert 'dash' in names, 'a router in your own config file must not be hidden by the service it names'


def test_traefiks_own_routers_are_not_in_the_routes_list(client):
    names = [a['name'] for a in client.get('/api/routes', headers=HDR).get_json()['apps']]
    assert not [n for n in names if str(n).endswith('@internal')], \
        'Traefik generates those, they belong in the Internal tab: %r' % names


def test_a_noop_router_survives_an_edit(client):
    _save_noop(client)
    r = _save_noop(client, isEdit='true', originalId='redirect-only')
    assert r.status_code < 400, r.get_data(as_text=True)[:200]
    assert read_config()['http']['routers']['redirect-only']['service'] == 'noop@internal'


def test_the_route_form_offers_noop_for_http_only():
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    js = open(os.path.join(root, 'static', 'js', 'routes.js'), encoding='utf-8').read()
    body = js[js.index('async function _populateServiceRefSelect'):js.index('function _updateRefTarget')]
    assert "proto === 'http'" in body and 'noop@internal' in body, \
        'noop is HTTP only in Traefik, so the option must be gated on protocol'


def test_a_backendless_route_is_not_judged_on_a_backend():
    from core import route_health as rh
    app = {'id': 'r', 'name': 'r', 'rule': 'Host(`r.example.com`)', 'tls': True, 'target': 'noop@internal',
           'service_name': 'noop@internal', 'enabled': True, 'protocol': 'http'}
    assert rh.is_internal(app) is True
    seen = {}

    def fake(url, fallback='', verify_backend=True):
        seen['fallback'] = fallback
        seen['verify'] = verify_backend
        return {'ok': True, 'latency_ms': 4, 'status_code': 301}

    obs = rh.observe(app, 'https://r.example.com', {}, probe=fake)
    assert obs['state'] == 'up'
    assert seen['verify'] is False, 'there is no backend behind noop, so do not report one as unverified'
    assert seen['fallback'] == ''


def test_a_redirect_is_plain_up_when_there_is_no_backend_to_verify():
    from core import reachability
    calls = []

    class _R:
        status_code = 301
        headers = {'Location': 'https://elsewhere.example.com/'}

    def head(target, **kw):
        calls.append(target)
        return _R()

    r = reachability.probe('https://r.example.com', '', ssrf=lambda u: True, head=head, verify_backend=False)
    assert r['ok'] is True and 'unverified' not in r, r
    assert len(calls) == 1, 'nothing else should be probed'


def _js(name):
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return open(os.path.join(root, 'static', 'js', name), encoding='utf-8').read()


def test_the_picker_offers_every_providers_services():
    js = _js('routes.js')
    body = js[js.index('async function _populateServiceRefSelect'):js.index('function _updateRefTarget')]
    assert 'This config' in body, 'your own services must stay grouped and first'
    assert '(read only)' in body, 'a service from a provider is not editable here and should say so'
    assert 'noop@internal' in body and "proto === 'http'" in body, \
        'noop is HTTP only and must be offered even when the Traefik API is down'
    ensure = js[js.index('async function _ensureServicesList'):js.index('async function _populateServiceRefSelect')]
    assert "agentFetch('/api/traefik/services')" in ensure, \
        'the live list is what carries services from other providers, same as middlewares'
    assert "sv.provider !== 'file'" in ensure, 'file services already come from the config, do not list them twice'


def test_the_internal_tab_exists_and_is_read_only():
    js = _js('tab-internal.js')
    assert "getProvider(r) === 'internal'" in js
    assert "document.getElementById('detailEditBtn').style.display = 'none'" in js, \
        'Traefik owns these, they must not offer an edit button'
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    core = open(os.path.join(root, 'static', 'js', 'core.js'), encoding='utf-8').read()
    assert "'internal'" in core and "refreshInternalTab()" in core, 'the tab is never reachable'
    from core import settings as settings_mod
    assert 'internal' in settings_mod.OPTIONAL_TABS, 'it must be toggleable like the other provider tabs'
    idx = open(os.path.join(root, 'templates', 'index.html'), encoding='utf-8').read()
    assert 'tabs/tab_internal.html' in idx

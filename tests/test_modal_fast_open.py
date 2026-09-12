import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


def _fn(js, head, stop):
    start = js.index(head)
    return js[start:js.index(stop, start)]


def _opens_before_first_await(body, opener):
    assert opener in body, f'{opener} is missing'
    return body.index(opener) < (body.index('await ') if 'await ' in body else len(body))


def test_the_route_form_opens_before_anything_is_fetched():
    js = _read('static', 'js', 'routes.js')
    for head, stop in (('async function handleEdit(btn) {', '\nlet _routeViewMode'),
                       ('async function openModal() {', '\nfunction _openRoutePanel()'),
                       ('async function cloneRoute(btn) {', '\nlet _routeMenuCard')):
        body = _fn(js, head, stop)
        assert _opens_before_first_await(body, '_openRoutePanel();'), \
            f'{head} must open the panel first and fill the selects afterwards'
        assert '_fillRouteSelects(' in body


def test_the_route_selects_load_side_by_side_and_ignore_a_stale_open():
    js = _read('static', 'js', 'routes.js')
    body = _fn(js, 'async function _fillRouteSelects(app, proto, opts) {', '\nasync function openModal()')
    assert 'Promise.all([' in body, 'each select waited for the previous one'
    assert '++_routeFillToken' in body and 'fresh()' in body, \
        'opening a second route while the first is still loading must not mix the two'
    for loader in ('_ensureServicesList()', '_initMiddlewareChips(', '_initEntrypointChips(',
                   '_populateTlsOptionsSelect()', "_populateConfigFileSelect('route')", '_loadAgentResolversIntoSelects()'):
        assert loader in body, f'{loader} left out of the parallel load'
    assert body.count('await ') <= 6, 'the awaits belong inside the parallel steps, not between them'


def test_the_service_and_middleware_forms_open_first_too():
    svc = _read('static', 'js', 'services.js')
    body = _fn(svc, 'async function openServiceModal(existing) {', '\n}\n')
    assert _opens_before_first_await(body, "classList.add('open')")
    assert "Promise.all([_populateConfigFileSelect('service'), fillRows()])" in body
    mw = _read('static', 'js', 'middlewares.js')
    body = _fn(mw, 'function openMwModal() {', '\n}\n')
    assert "_openMwPanel();\n    _populateConfigFileSelect('mw');" in body, \
        'the add form waited on the config file list before showing'


def test_the_services_list_is_kept_across_a_refresh_and_fetched_side_by_side():
    js = _read('static', 'js', 'routes.js')
    paint = _fn(js, 'function _paintRoutes(data) {', '\n}\n')
    assert 'liveLoaded: !!prev.liveLoaded' in paint and '_tmServices = null' not in paint, \
        'a refresh dropped the services the picker needs, so the next edit fetched them again'
    ensure = _fn(js, 'async function _ensureServicesList() {', 'async function _populateServiceRefSelect')
    assert 'if (have && have.liveLoaded) return have;' in ensure
    assert 'await Promise.all(jobs)' in ensure, 'the live list and the own list were fetched one after the other'
    assert "if (!window._tmServices) {" in ensure, 'the own list is already on the page after a routes refresh'
    assert '_inflightServicesList' in ensure, 'two openers in flight must share one request'


def test_config_files_and_tls_profiles_are_cached_until_something_changes():
    core = _read('static', 'js', 'core.js')
    assert re.search(r'function _agentConfigFileNames\(\)', core)
    assert re.search(r'function _tlsOptionNames\(\)', core)
    pop = _fn(core, 'async function _populateConfigFileSelect(which) {', '\n}\n')
    assert "agentFetch('/api/configs')" not in pop and 'await _agentConfigFileNames()' in pop
    tls = _fn(core, 'async function _populateTlsOptionsSelect() {', '\n}\n')
    assert "fetch('/api/tls-options')" not in tls and 'await _tlsOptionNames()' in tls
    names = _fn(core, 'function _tlsOptionNames() {', '\n}\n')
    assert "'?server=' + encodeURIComponent(server)" in names, \
        'a route on an agent must see that agent\'s TLS profiles, not the Host\'s'
    certs = _read('static', 'js', 'certs.js')
    assert certs.count('_dropTlsOptionsCache();') == 2, 'saving or deleting a profile must refresh the cached list'
    html = _read('templates', 'index.html')
    body = html.split('function switchServer', 1)[1].split('\n}', 1)[0]
    assert '_inflightServicesList = null' in body and '_dropConfigFilesCache()' in body
    routes = _read('static', 'js', 'routes.js')
    assert '_dropConfigFilesCache()' in _fn(routes, 'async function refreshRoutes() {', '\n}\n'), \
        'a save can create a config file, so the list must be re-read after the next refresh'

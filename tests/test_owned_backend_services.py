import json
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(ROOT, 'static', 'js', 'services.js')

FNS = ['_compositeChildren', '_svcBareName', '_svcOwnedBases',
       '_svcOwnsChild', '_svcOwnedChildIndex', '_svcOwnerName']


def _src():
    with open(JS, encoding='utf-8') as fh:
        return fh.read()


def _preamble():
    src = _src()
    out = []
    for name in FNS:
        m = re.search(r'(function ' + name + r'\(.*?\n\})', src, re.S)
        assert m, 'the %s helper moved' % name
        out.append(m.group(1))
    return '\n'.join(out) + '\n'


def _node(tail, services):
    script = _preamble() + 'const list = ' + json.dumps(services) + ';\n' + tail
    out = subprocess.run(['node', '-e', script], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def _hidden(services):
    return _node('console.log(JSON.stringify('
                 '[..._svcOwnedChildIndex(list)].map(i => list[i].name)));\n', services)


def _owner(services, index):
    return _node('console.log(JSON.stringify(_svcOwnerName(list, list[%d])));\n' % index,
                 services)


def _child(name, proto='HTTP', used_by=None):
    return {'name': name, '_proto': proto, 'usedBy': used_by or [],
            'loadBalancer': {'servers': [{'url': 'http://10.0.0.1:8080'}]}}


def _weighted(name, children, proto='HTTP', used_by=None):
    return {'name': name, '_proto': proto, 'usedBy': used_by or [],
            'weighted': {'services': [{'name': c, 'weight': 1} for c in children]}}


def test_owned_backends_are_kept_out_of_the_services_list():
    services = [_weighted('api-service', ['api-backend-1', 'api-backend-2']),
                _child('api-backend-1'), _child('api-backend-2')]
    assert _hidden(services) == ['api-backend-1', 'api-backend-2'], \
        'a route with manual backend rows must not add a card per row'


def test_the_composite_parent_itself_stays_listed():
    services = [_weighted('api-service', ['api-backend-1']), _child('api-backend-1')]
    assert 'api-service' not in _hidden(services)


def test_a_backend_with_its_own_router_stays_visible():
    services = [_weighted('api-service', ['api-backend-1']),
                _child('api-backend-1', used_by=['other@file'])]
    assert _hidden(services) == [], \
        'a service a router points at directly is not just an owned child'


def test_a_lookalike_name_nobody_references_stays_visible():
    services = [_weighted('api-service', ['pool-a']), _child('api-backend-1'), _child('pool-a')]
    assert _hidden(services) == [], \
        'the parent must actually reference the child before it is hidden'


def test_a_backend_with_no_composite_parent_stays_visible():
    assert _hidden([_child('api-backend-1')]) == []


def test_a_parent_named_after_a_reused_service_still_owns_its_backends():
    services = [_weighted('shared-pool', ['api-backend-1'], used_by=['api@file']),
                _child('api-backend-1')]
    assert _hidden(services) == ['api-backend-1'], \
        'an edited route can keep an older service name, the child prefix is the router name'


def test_an_unnumbered_backend_name_stays_visible():
    services = [_weighted('api-service', ['api-backend-blue']), _child('api-backend-blue')]
    assert _hidden(services) == [], \
        'owned children are always numbered, a hand written name is the users own'


def test_a_backend_on_another_protocol_stays_visible():
    services = [_weighted('api-service', ['api-backend-1']),
                _child('api-backend-1', proto='TCP')]
    assert _hidden(services) == []


def test_provider_suffixes_do_not_break_the_match():
    services = [_weighted('api-service@file', ['api-backend-1@file']),
                _child('api-backend-1@file')]
    assert _hidden(services) == ['api-backend-1@file']


def test_a_child_that_is_itself_composite_stays_visible():
    services = [_weighted('api-service', ['api-backend-1']),
                _weighted('api-backend-1', ['deep-a', 'deep-b'])]
    assert _hidden(services) == [], \
        'only a plain load balancer can be an owned backend row'


def test_a_hidden_backend_reports_the_parent_it_belongs_to():
    services = [_weighted('api-service@file', ['api-backend-1@file']),
                _child('api-backend-1@file')]
    assert _owner(services, 1) == 'api-service'
    assert _owner(services, 0) == ''


def test_the_tab_count_drops_the_owned_backends():
    assert "setTabCount('live', _allServices.length - ownedIdx.size)" in _src(), \
        'the nav tab count must not include services the tab refuses to list'


def test_the_render_loop_skips_owned_backends_until_you_search():
    src = _src()
    assert 'if (ownedIdx.has(i) && !search) continue;' in src, \
        'owned backends are hidden by default and revealed by an explicit search'


def test_filter_menus_are_built_from_the_listed_services():
    src = _src()
    assert 'const listed = _allServices.filter((s, i) => !ownedIdx.has(i));' in src
    assert 'listed.map(s => s._proto)' in src
    assert 'listed.map(providerOf)' in src


def test_owned_backends_stay_in_the_loaded_list_so_they_remain_reachable():
    src = _src()
    assert '_allServices = [...http, ...tcp, ...udp]' in src, \
        'hiding happens at render time, the child must still be openable by name'
    assert "[t('Backend of')," in src, \
        'the child detail panel must name the parent that owns it'

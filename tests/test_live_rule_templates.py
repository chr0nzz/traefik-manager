import os

from core import routes_build as rb
from core import route_health as rh

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TEMPLATE_RULE = 'Host(`plex.{{ env `DOMAINNAME0` }}`)'
LIVE_RULE = 'Host(`plex.example.com`)'


def _routers(rule=LIVE_RULE, name='plex-rtr@file'):
    return {'http': [{'name': name, 'rule': rule}], 'tcp': [], 'udp': []}


def _app(rule=TEMPLATE_RULE, name='plex-rtr'):
    return {'id': 'dynamic.yml::' + name, 'name': name, 'rule': rule, 'protocol': 'http', 'enabled': True}


def test_a_templated_rule_takes_the_host_traefik_resolved():
    apps = [_app()]
    rb.apply_live_rules(apps, _routers())
    assert apps[0]['liveRule'] == LIVE_RULE
    assert apps[0]['rule'] == TEMPLATE_RULE, 'the file keeps its template, only the resolved copy is added'
    assert rh.route_url(apps[0]) == 'http://plex.example.com'


def test_a_plain_rule_is_left_alone():
    apps = [_app(rule='Host(`plex.example.com`)')]
    rb.apply_live_rules(apps, _routers(rule='Host(`plex.example.net`)'))
    assert 'liveRule' not in apps[0], 'a rule without a template must keep the host from the config file'
    assert rh.route_url(apps[0]) == 'http://plex.example.com'


def test_an_unresolved_or_missing_router_leaves_the_route_unchecked():
    apps = [_app()]
    rb.apply_live_rules(apps, _routers(name='other-rtr@file'))
    assert 'liveRule' not in apps[0]
    assert rh.route_url(apps[0]) == '', 'a template Traefik has not resolved must not become a host to ping'

    apps = [_app()]
    rb.apply_live_rules(apps, _routers(rule=TEMPLATE_RULE))
    assert 'liveRule' not in apps[0]

    apps = [_app()]
    rb.apply_live_rules(apps, {})
    assert 'liveRule' not in apps[0]


def test_the_browser_prefers_the_resolved_rule_for_the_launch_link():
    with open(os.path.join(ROOT, 'static', 'js', 'dashboard-tab.js')) as f:
        tab = f.read()
    assert "const rule = r.liveRule || r.rule || ''" in tab, 'the launch link must use the rule Traefik resolved'
    assert "while ((m = re.exec(r.liveRule || r.rule || '')) !== null)" in tab, \
        'search must match the host a templated route actually serves'
    assert "host.indexOf('{') >= 0" in tab, 'an unresolved template must not become a launch URL'


AGENT_ROUTERS = {'http': [{'name': 'plex-rtr@file', 'rule': LIVE_RULE}], 'tcp': [], 'udp': [],
                 'complete': False, 'tcp_error': 'router list incomplete'}


def test_an_agent_router_payload_carries_flags_beside_the_lists():
    apps = [_app()]
    rb.apply_live_rules(apps, AGENT_ROUTERS)
    assert apps[0]['liveRule'] == LIVE_RULE, \
        'an agent sends complete and error flags in the same dict as the router lists'
    assert rb._traefik_router_ep_map(AGENT_ROUTERS) == {}, 'the flags must not be walked as routers either'


def test_a_junk_router_entry_does_not_stop_the_rest():
    apps = [_app()]
    rb.apply_live_rules(apps, {'http': ['not-a-router', None, {'name': 'plex-rtr@file', 'rule': LIVE_RULE}]})
    assert apps[0]['liveRule'] == LIVE_RULE


def test_the_routes_tab_uses_the_resolved_rule_everywhere_it_shows_a_host():
    with open(os.path.join(ROOT, 'static', 'js', 'routes.js')) as f:
        routes = f.read()
    assert 'function _rmServedRule(app)' in routes, 'one helper decides which rule the cards read'
    assert routes.count('_rmServedRule(app)') >= 2, 'both card layouts need it, not just the first'
    assert "matchAll(/Host\\(`([^`]+)`\\)/g)].map(m => m[1])" in routes
    assert "(a.liveRule || a.rule)" in routes, 'the domain filter must list the host actually served'


def test_the_route_map_and_certs_read_the_resolved_rule_too():
    for name in ('routemap.js', 'certs.js'):
        with open(os.path.join(ROOT, 'static', 'js', name)) as f:
            src = f.read()
        assert 'liveRule' in src, f'{name} shows hosts from the rule, so it needs the resolved one'


def test_a_templated_route_gets_its_live_rule_without_the_external_fetch():
    from unittest.mock import patch
    routers = {'http': [{'name': 'plex-rtr@file', 'rule': LIVE_RULE}], 'tcp': [], 'udp': []}
    apps = [_app()]
    with patch.object(rb.traefik_mod, '_fetch_traefik_routers_and_services',
                      return_value=(routers, {})) as fetch:
        rb.apply_live_rules(apps, {} if False else routers)
    assert apps[0]['liveRule'] == LIVE_RULE
    assert fetch.call_count == 0, 'routers already in hand must not be fetched twice'


def test_a_plain_route_list_does_not_call_traefik():
    src = open(os.path.join(ROOT, 'core', 'routes_build.py'), encoding='utf-8').read()
    assert "if not all_routers and any('{{' in str(app.get('rule') or '') for app in all_apps):" in src, \
        'the Routes tab must only reach for the Traefik API when a rule actually holds a template'

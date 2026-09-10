import json
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


def _fn(name, src):
    m = re.search(r'(function ' + name + r'\(.*?\n\})', src, re.S)
    assert m, 'the %s helper moved' % name
    return m.group(1)


HARNESS = """
const _uaShort = s => String(s || '').split('/')[0];
let _atkFacet = { scenario: '', ip: '', asn: '', cc: '', uri: '', user: '', agent: '', verb: '', router: '', host: '', origin: '', type: '', outcome: '' };
"""


def _run(body):
    src = _read('static', 'js', 'crowdsec.js')
    stub = (HARNESS + _fn('_atkMetaMap', src) + '\n' + _fn('_atkCc', src) + '\n'
            + _fn('_atkParseAlert', src) + '\n' + _fn('_atkMatchAlert', src) + '\n' + body)
    out = subprocess.run(['node', '-e', stub], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


ALERT = """
const alert = { uuid: 'x', scenario: 'crowdsecurity/http-probing', events_count: 7,
    source: { ip: '1.2.3.4', scope: 'Ip' },
    meta: [ { key: 'traefik_router_name', value: 'app@file -> auth@file' },
            { key: 'traefik_router_name_leaf', value: 'auth@file' },
            { key: 'target_fqdn', value: 'shop.example.com' },
            { key: 'target_uri', value: '/wp-login.php' } ] };
"""


def test_the_router_and_host_are_read_from_alert_meta():
    res = _run(ALERT + """
const a = _atkParseAlert(alert, 0);
console.log(JSON.stringify({ routers: a.routers, hosts: a.hosts, uris: a.uris }));
""")
    assert res['routers'] == ['auth@file'], 'the leaf router is the useful one in a chain: %r' % res
    assert res['hosts'] == ['shop.example.com']
    assert res['uris'] == ['/wp-login.php'], 'the existing meta must keep working'


def test_the_full_chain_is_used_when_there_is_no_leaf():
    res = _run("""
const alert = { source: {}, meta: [ { key: 'traefik_router_name', value: 'app@file' } ] };
const a = _atkParseAlert(alert, 0);
console.log(JSON.stringify({ routers: a.routers }));
""")
    assert res['routers'] == ['app@file']


def test_an_alert_with_no_traefik_context_is_still_parsed():
    res = _run("""
const a = _atkParseAlert({ source: {}, meta: [] }, 0);
console.log(JSON.stringify({ routers: a.routers, hosts: a.hosts }));
""")
    assert res == {'routers': [], 'hosts': []}


def test_filtering_by_router_and_host_works():
    res = _run(ALERT + """
const a = _atkParseAlert(alert, 0);
const out = {};
_atkFacet.router = 'auth@file'; out.sameRouter = _atkMatchAlert(a, '', null);
_atkFacet.router = 'other@file'; out.otherRouter = _atkMatchAlert(a, '', null);
_atkFacet.router = '';
_atkFacet.host = 'shop.example.com'; out.sameHost = _atkMatchAlert(a, '', null);
_atkFacet.host = 'nope.example.com'; out.otherHost = _atkMatchAlert(a, '', null);
_atkFacet.host = '';
out.searchRouter = _atkMatchAlert(a, 'auth@file', null);
out.searchHost = _atkMatchAlert(a, 'shop.example', null);
console.log(JSON.stringify(out));
""")
    assert res == {'sameRouter': True, 'otherRouter': False, 'sameHost': True,
                   'otherHost': False, 'searchRouter': True, 'searchHost': True}, res


def test_the_card_is_rendered_and_wired():
    js = _read('static', 'js', 'crowdsec.js')
    assert '_atkCardRoutes(d)' in js[js.index('const cards = ['):], 'the card is never added to the grid'
    body = _fn('_atkCardRoutes', js)
    assert "_atkSpec({ router: e.key })" in body, 'rows must filter by router'
    assert "_atkSpec({ host: h.key })" in body, 'host flags must filter by host'
    assert 'context file' in body, 'when the meta is absent the card must say how to get it'
    assert 'router: 1, host: 1' in js or ('router: 1' in js and 'host: 1' in js), \
        'the new facets are alert only, like uri and user'


def test_a_known_router_links_to_its_route():
    js = _read('static', 'js', 'crowdsec.js')
    assert '_openRouteByName(' in js, 'the evidence should open the route it names'
    body = _fn('_atkKnownRoute', js)
    assert "split('@')[0]" in body, 'router names arrive provider qualified'

import os
import re
import subprocess

from js_i18n import i18n_prelude

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(ROOT, 'static', 'js', 'services.js')


def _composite_expression():
    with open(JS, encoding='utf-8') as fh:
        src = fh.read()
    m = re.search(r'const composite = (.*?);\n', src, re.S)
    assert m, 'the composite children expression moved'
    return m.group(1)


def _run(service):
    expr = _composite_expression()
    script = (
        i18n_prelude() +
        'const s = ' + service + ';\n'
        'const composite = ' + expr + ';\n'
        'console.log(JSON.stringify(composite));\n'
    )
    out = subprocess.run(['node', '-e', script], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    import json
    return json.loads(out.stdout)


def test_a_mirror_always_shows_its_share():
    out = _run('{"mirroring": {"service": "main", "mirrors": [{"name": "shadow", "percent": 10}]}}')
    assert out == ['main', 'shadow mirror (10%)']


def test_a_mirror_with_no_percent_shows_zero_because_it_gets_no_traffic():
    out = _run('{"mirroring": {"service": "main", "mirrors": [{"name": "shadow"}]}}')
    assert out == ['main', 'shadow mirror (0%)'], \
        'percent defaults to 0 in Traefik, so a mirror without it receives nothing'


def test_highest_random_weight_children_are_listed():
    out = _run('{"highestRandomWeight": {"services": [{"name": "a"}, {"name": "b", "weight": 3}]}}')
    assert out == ['a', 'b (3)'], 'an HRW service used to render with no children at all'


def test_weighted_children_still_show_their_weight():
    out = _run('{"weighted": {"services": [{"name": "blue", "weight": 1}, {"name": "green"}]}}')
    assert out == ['blue (1)', 'green']


def test_failover_shows_both_halves():
    out = _run('{"failover": {"service": "primary", "fallback": "backup"}}')
    assert out == ['primary', 'backup fallback']


def test_a_plain_load_balancer_has_no_composite_children():
    assert _run('{"loadBalancer": {"servers": [{"url": "http://a:80"}]}}') == []


def _children(service):
    with open(JS, encoding='utf-8') as fh:
        src = fh.read()
    m = re.search(r'(function _compositeChildren\(s\) \{.*?\n\})', src, re.S)
    assert m, 'the composite children helper moved'
    script = i18n_prelude() + m.group(1) + '\nconsole.log(JSON.stringify(_compositeChildren(' + service + ')));\n'
    out = subprocess.run(['node', '-e', script], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    import json
    return json.loads(out.stdout)


def test_the_detail_panel_lists_weighted_children():
    out = _children('{"weighted": {"services": [{"name": "blue", "weight": 2}, {"name": "green"}]}}')
    assert out == [
        {'name': 'blue', 'role': 'Weighted', 'share': '2'},
        {'name': 'green', 'role': 'Weighted', 'share': '-'},
    ]


def test_the_detail_panel_names_the_mirror_roles_and_share():
    out = _children('{"mirroring": {"service": "main", "mirrors": [{"name": "shadow"}]}}')
    assert out == [
        {'name': 'main', 'role': 'Main', 'share': '-'},
        {'name': 'shadow', 'role': 'Mirror', 'share': '0%'},
    ]


def test_the_detail_panel_distinguishes_primary_from_fallback():
    out = _children('{"failover": {"service": "primary", "fallback": "backup"}}')
    assert out == [
        {'name': 'primary', 'role': 'Primary', 'share': '-'},
        {'name': 'backup', 'role': 'Fallback', 'share': '-'},
    ]


def test_the_detail_panel_lists_highest_random_weight_children():
    out = _children('{"highestRandomWeight": {"services": [{"name": "a", "weight": 5}]}}')
    assert out == [{'name': 'a', 'role': 'Weighted', 'share': '5'}]


def test_a_plain_load_balancer_has_no_backends_block():
    assert _children('{"loadBalancer": {"servers": [{"url": "http://a:80"}]}}') == []


def test_a_child_with_no_name_is_dropped():
    assert _children('{"weighted": {"services": [{"weight": 1}, {"name": "ok", "weight": 2}]}}') == [
        {'name': 'ok', 'role': 'Weighted', 'share': '2'}]


def test_the_panel_swaps_servers_for_backends_only_when_there_are_children():
    with open(JS, encoding='utf-8') as fh:
        src = fh.read()
    assert "children.length" in src
    assert "renderDetailBlock(tc('label', 'Backends')" in src
    assert "renderDetailBlock(tc('label', 'Servers')" in src, \
        'a plain load balancer must still show its Servers block'


def test_children_are_clickable_through_to_their_own_service():
    with open(JS, encoding='utf-8') as fh:
        src = fh.read()
    assert 'function _openServiceByName(' in src
    assert '_openServiceByName(' in src.split('function _openServiceByName(')[1], \
        'the backends table must link each child'

import json
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _status_map_fn():
    with open(os.path.join(ROOT, 'static', 'js', 'routemap.js'), encoding='utf-8') as fh:
        src = fh.read()
    m = re.search(r'(function _rmStatusMap\(.*?\n\})', src, re.S)
    assert m, 'the status map builder moved'
    return m.group(1)


def _lookup(routers, name='http:grafana@file'):
    rows = [['http', r] for r in routers]
    stub = (_status_map_fn()
            + '\nconst map = _rmStatusMap(%s, rt => ({ up: rt.status === "enabled" && !rt.error, err: !!rt.error }));'
              '\nconsole.log(JSON.stringify(map[%s] || null));' % (json.dumps(rows), json.dumps(name)))
    out = subprocess.run(['node', '-e', stub], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


def _router(name, ep, status='enabled', error=None):
    r = {'name': name, 'status': status, 'using': [ep]}
    if error:
        r['error'] = [error]
    return r


def test_a_router_split_per_entry_point_is_found_by_its_config_name():
    st = _lookup([_router('websecure-grafana@file', 'websecure'),
                  _router('websecure-public-grafana@file', 'websecure-public')])
    assert st == {'up': True, 'err': False}, (
        'Traefik lists "<entryPoint>-<name>@file", the dashboard looks up "<name>@file"')


def test_the_worst_copy_wins():
    st = _lookup([_router('websecure-grafana@file', 'websecure'),
                  _router('websecure-public-grafana@file', 'websecure-public', error='no certificate')])
    assert st['err'] is True
    st = _lookup([_router('websecure-public-grafana@file', 'websecure-public', status='disabled'),
                  _router('websecure-grafana@file', 'websecure')])
    assert st['up'] is False and st['err'] is False


def test_an_exact_name_is_never_replaced_by_a_split_one():
    st = _lookup([_router('grafana@file', 'traefik', error='broken'),
                  _router('websecure-grafana@file', 'websecure')])
    assert st['err'] is True


def test_unsplit_routers_still_match_as_before():
    assert _lookup([_router('grafana@file', 'websecure')]) == {'up': True, 'err': False}

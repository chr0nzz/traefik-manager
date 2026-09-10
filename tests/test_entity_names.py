import pytest

from core import names

from conftest import post_form, read_config

HDR = {"X-CSRF-Token": "testtoken", "X-Requested-With": "fetch"}

REFUSED = ('', 'a@file', 'a/b', 'a,b', 'a:b', 'a{{x}}', 'a}b', '.', '..', 'x' * 101)
ALLOWED = ('xxx (yyy)', 'plain', 'has space', '-leading', 'a.b_c-d', 'x' * 100, 'café', 'a+b', 'a[1]', 'a#b', 'a%b')


def test_the_rule_matches_what_traefik_forbids():
    for bad in REFUSED:
        assert names.name_error(bad), 'should be refused: %r' % (bad,)
    for good in ALLOWED:
        assert names.name_error(good) == '', 'Traefik accepts this, so we should: %r (%s)' % (good, names.name_error(good))


def test_the_message_names_the_characters():
    assert '@' in names.name_error('a@b') and '/' in names.name_error('a@b')
    assert '100' in names.name_error('x' * 101)


def test_surrounding_space_is_trimmed_not_refused():
    assert names.name_error('  api  ') == ''
    assert names.name_error('   ') != ''


def _route(client, name):
    return post_form(client, '/save', serviceName=name, subdomain='sub', protocol='http',
                     scheme='http', targetIp='10.0.0.5', targetPort='80')


def _middleware(client, name):
    return post_form(client, '/save-middleware', middlewareName=name, mwProtocol='http',
                     middlewareContent='headers:\n  customRequestHeaders:\n    X-Test: "1"')


def _service(client, name):
    return client.post('/api/services', headers=HDR, json={
        'name': name, 'type': 'loadBalancer',
        'children': [{'kind': 'manual', 'address': 'a:80', 'scheme': 'http', 'weight': 1}]})


@pytest.mark.parametrize('saver,section', [(_route, 'routers'), (_middleware, 'middlewares'), (_service, 'services')])
def test_every_editor_refuses_the_same_names(client, saver, section):
    for bad in ('a@file', 'a/b', 'a,b', 'a:b', 'a{{x}}'):
        r = saver(client, bad)
        assert r.status_code == 400, '%s accepted %r' % (section, bad)


@pytest.mark.parametrize('saver,section', [(_route, 'routers'), (_middleware, 'middlewares'), (_service, 'services')])
def test_every_editor_accepts_a_name_with_spaces_and_brackets(client, saver, section):
    r = saver(client, 'xxx (yyy)')
    assert r.status_code == 200, '%s refused the name Traefik accepts: %r' % (section, r.get_data(as_text=True)[:200])
    written = (read_config().get('http') or {}).get(section) or {}
    assert 'xxx (yyy)' in written, '%s did not write the name: %r' % (section, list(written))


def test_a_route_id_with_a_separator_in_the_name_still_resolves():
    import app as tm
    assert tm._disabled_router_name('file.yml::my::route') == 'my::route'
    assert tm._disabled_router_name('plain') == 'plain'

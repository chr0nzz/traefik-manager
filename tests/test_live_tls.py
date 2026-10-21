from core.routes_build import apply_live_tls


def _app(name, tls=False, protocol='http', provider='file'):
    return {'name': name, 'protocol': protocol, 'tls': tls, 'provider': provider, 'tlsOptionsProfile': ''}


def test_a_file_route_without_tls_inherits_it_from_the_live_router():
    apps = [_app('authelia-rtr')]
    apply_live_tls(apps, {'http': [{'name': 'authelia-rtr@file', 'tls': {}, 'using': ['websecure']}]})
    assert apps[0]['tlsInherited'] is True
    assert apps[0]['tlsLiveOptions'] == ''
    assert apps[0]['tlsOptionsProfile'] == ''


def test_the_per_entry_point_copy_traefik_makes_is_matched():
    apps = [_app('grafana')]
    apply_live_tls(apps, {'http': [{'name': 'websecure-grafana@file', 'tls': {'options': 'modern@file'}, 'using': ['websecure']}]})
    assert apps[0]['tlsInherited'] is True
    assert apps[0]['tlsLiveOptions'] == 'modern'


def test_a_live_router_without_tls_changes_nothing():
    apps = [_app('plain')]
    apply_live_tls(apps, {'http': [{'name': 'plain@file', 'using': ['web']}]})
    assert 'tlsInherited' not in apps[0]


def test_routes_that_already_have_tls_or_are_not_file_routes_are_left_alone():
    apps = [_app('own', tls=True), _app('dock', provider='docker'), _app('udp', protocol='udp')]
    routers = {'http': [{'name': 'own@file', 'tls': {}}, {'name': 'dock@docker', 'tls': {}}],
               'udp': [{'name': 'udp@file', 'tls': {}}]}
    apply_live_tls(apps, routers)
    assert all('tlsInherited' not in a for a in apps)


def test_tcp_routes_inherit_too():
    apps = [_app('db', protocol='tcp')]
    apply_live_tls(apps, {'tcp': [{'name': 'db@file', 'tls': {}}]})
    assert apps[0]['tlsInherited'] is True

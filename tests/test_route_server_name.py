import core.config as cfg
from conftest import DYNAMIC_PATH, post_form, write_config


BASE = {
    'appName': 'nas', 'subdomain': 'nas', 'targetIp': '10.0.0.9', 'targetPort': '443',
    'scheme': 'https', 'protocol': 'http', 'entryPoints': 'websecure', 'serviceName': 'nas',
}


def _save(client, **extra):
    data = dict(BASE)
    data.update(extra)
    return post_form(client, '/save', **data)


def _http():
    return cfg.load_config(str(DYNAMIC_PATH)).get('http', {}) or {}


def test_server_name_lands_on_the_route_transport(client):
    write_config('http: {}\n')
    res = _save(client, backendServerName='nas.lan.example', insecureSkipVerify='true')
    assert res.status_code == 200, res.get_data(as_text=True)
    http = _http()
    lb = http['services']['nas-service']['loadBalancer']
    tp = http['serversTransports'][lb['serversTransport']]
    assert tp == {'serverName': 'nas.lan.example', 'insecureSkipVerify': True}


def test_server_name_alone_creates_the_transport(client):
    write_config('http: {}\n')
    _save(client, backendServerName='nas.lan.example')
    tps = _http().get('serversTransports') or {}
    assert list(tps.values()) == [{'serverName': 'nas.lan.example'}]


def test_clearing_server_name_drops_the_transport(client):
    write_config('http: {}\n')
    _save(client, backendServerName='nas.lan.example')
    _save(client, isEdit='true', originalId='nas', backendServerName='')
    http = _http()
    assert not http.get('serversTransports')
    assert 'serversTransport' not in http['services']['nas-service']['loadBalancer']


def test_a_save_without_the_field_keeps_server_name(client):
    write_config('http: {}\n')
    _save(client, backendServerName='nas.lan.example')
    _save(client, isEdit='true', originalId='nas')
    tps = _http().get('serversTransports') or {}
    assert list(tps.values()) == [{'serverName': 'nas.lan.example'}]


def test_a_bad_server_name_is_refused(client):
    write_config('http: {}\n')
    res = _save(client, backendServerName='bad name`')
    assert res.status_code == 400
    assert not _http().get('serversTransports')


def test_the_route_list_reports_server_name(client):
    from core.routes_build import _build_apps
    write_config('http: {}\n')
    _save(client, backendServerName='nas.lan.example')
    apps = _build_apps(cfg.load_config(str(DYNAMIC_PATH)))
    assert [a['serverName'] for a in apps if a['name'] == 'nas'] == ['nas.lan.example']


def test_the_route_detail_service_section_shows_the_transport():
    import os
    src = open(os.path.join(os.path.dirname(__file__), '..', 'static', 'js', 'routes.js'), encoding='utf-8').read()
    rows = src.split('const svcRows = [', 1)[1].split('];', 1)[0]
    assert "app.serverName ? [[t('Backend server name (SNI)'), app.serverName, false]]" in rows
    assert "app.insecureSkipVerify ? [[t('Skip TLS Verification'), _dBool(true), true]]" in rows

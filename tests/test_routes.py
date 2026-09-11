import pytest
import json

from conftest import read_config, write_config, post_form

BACKENDS = json.dumps({
    "servers": [
        {"scheme": "http", "host": "10.0.0.1", "port": "8080"},
        {"scheme": "http", "host": "10.0.0.2", "port": "8080"},
        {"scheme": "http", "host": "10.0.0.3", "port": "8080"},
    ],
    "sticky": {"enabled": True, "cookieName": "tm_sticky", "secure": True, "httpOnly": True},
    "healthCheck": {"enabled": True, "path": "/health", "interval": "10s", "timeout": "3s"},
    "priority": 42,
})


def _save_http(client, name="app1", **extra):
    form = dict(serviceName=name, subdomain=f"{name}.example.com", protocol="http",
                scheme="http", targetIp="10.0.0.1", targetPort="8080",
                certResolver="letsencrypt")
    form.update(extra)
    return post_form(client, "/save", **form)


def test_save_http_route_writes_yaml(client):
    r = _save_http(client)
    assert r.status_code < 400

    cfg = read_config()
    assert "app1" in cfg["http"]["routers"]
    assert "app1.example.com" in cfg["http"]["routers"]["app1"]["rule"]
    servers = cfg["http"]["services"]["app1-service"]["loadBalancer"]["servers"]
    assert servers[0]["url"] == "http://10.0.0.1:8080"


def test_save_tcp_route(client):
    r = post_form(client, "/save", serviceName="db", subdomain="db", protocol="tcp",
                  targetIp=["", "10.0.0.9", ""], targetPort=["", "5432", ""])
    assert r.status_code < 400
    cfg = read_config()
    assert cfg["tcp"]["routers"]["db"]["rule"] == "HostSNI(`db.example.com`)"
    assert cfg["tcp"]["services"]["db-service"]["loadBalancer"]["servers"][0]["address"] == "10.0.0.9:5432"


def test_save_udp_route(client):
    r = post_form(client, "/save", serviceName="dns", subdomain="dns", protocol="udp",
                  targetIp=["", "", "10.0.0.53"], targetPort=["", "", "53"])
    assert r.status_code < 400
    cfg = read_config()
    assert cfg["udp"]["services"]["dns-service"]["loadBalancer"]["servers"][0]["address"] == "10.0.0.53:53"


def test_multiple_backends_and_load_balancing(client):
    r = _save_http(client, backendsJsonHttp=BACKENDS)
    assert r.status_code < 400

    lb = read_config()["http"]["services"]["app1-service"]["loadBalancer"]
    assert len(lb["servers"]) == 3
    assert lb["sticky"]["cookie"]["name"] == "tm_sticky"
    assert lb["healthCheck"]["path"] == "/health"
    assert read_config()["http"]["routers"]["app1"]["priority"] == 42


def test_legacy_client_edit_preserves_backends_and_lb(client):
    _save_http(client, backendsJsonHttp=BACKENDS)

    r = _save_http(client, targetIp="10.9.9.9", targetPort="9999",
                   isEdit="true", originalId="app1")
    assert r.status_code < 400

    cfg = read_config()
    lb = cfg["http"]["services"]["app1-service"]["loadBalancer"]
    assert "10.9.9.9:9999" in lb["servers"][0]["url"]
    assert len(lb["servers"]) == 3, "extra backends were wiped by a legacy save"
    assert lb["sticky"]["cookie"]["name"] == "tm_sticky"
    assert lb["healthCheck"]["path"] == "/health"
    assert cfg["http"]["routers"]["app1"]["priority"] == 42


def test_delete_route(client):
    _save_http(client)
    r = post_form(client, "/delete/app1")
    assert r.status_code < 400
    assert "app1" not in (read_config().get("http", {}).get("routers") or {})


def test_toggle_route_preserves_config(client, app_module):
    _save_http(client, backendsJsonHttp=BACKENDS)

    r = client.post("/api/routes/app1/toggle", json={"enable": False, "csrf_token": "testtoken"},
                    headers={"X-CSRF-Token": "testtoken"})
    assert r.status_code < 400
    assert "app1" not in (read_config().get("http", {}).get("routers") or {})

    r = client.post("/api/routes/app1/toggle", json={"enable": True, "csrf_token": "testtoken"},
                    headers={"X-CSRF-Token": "testtoken"})
    assert r.status_code < 400

    lb = read_config()["http"]["services"]["app1-service"]["loadBalancer"]
    assert len(lb["servers"]) == 3, "disable/enable lost backends"
    assert lb["sticky"]["cookie"]["name"] == "tm_sticky"


def test_api_routes_lists_saved_route(client):
    _save_http(client)
    r = client.get("/api/routes")
    assert r.status_code == 200
    names = [a["name"] for a in r.get_json()["apps"]]
    assert "app1" in names


def test_comments_survive_a_save(client):
    write_config(
        "# top level comment\n"
        "http:\n"
        "  routers:\n"
        "    existing:\n"
        "      rule: Host(`old.example.com`)  # inline note\n"
        "      service: existing-service\n"
        "  services:\n"
        "    existing-service:\n"
        "      loadBalancer:\n"
        "        servers:\n"
        "          - url: http://10.0.0.50:80\n"
    )
    r = _save_http(client, name="newroute")
    assert r.status_code < 400

    raw = open(__import__("conftest").DYNAMIC_PATH).read()
    assert "# top level comment" in raw, "ruamel round-trip dropped a comment"
    assert "# inline note" in raw
    assert "existing" in read_config()["http"]["routers"]


def test_tcp_save_without_a_backend_is_rejected(client):
    r = post_form(client, "/save", serviceName="badtcp", subdomain="badtcp",
                  protocol="tcp", targetIp="10.0.0.9", targetPort="5432")
    assert r.status_code == 400, "a TCP save with no reachable backend should be refused"
    cfg = read_config()
    assert "badtcp" not in (cfg.get("tcp", {}).get("routers") or {})


def test_udp_save_without_a_backend_is_rejected(client):
    r = post_form(client, "/save", serviceName="badudp", subdomain="badudp",
                  protocol="udp", targetIp="10.0.0.9", targetPort="53")
    assert r.status_code == 400
    assert "badudp" not in (read_config().get("udp", {}).get("routers") or {})


def test_http_save_without_a_backend_is_rejected(client):
    r = post_form(client, "/save", serviceName="badhttp", subdomain="badhttp.example.com",
                  protocol="http", scheme="http", targetPort="8080")
    assert r.status_code == 400
    assert "badhttp" not in (read_config().get("http", {}).get("routers") or {})


def test_no_route_ever_gets_an_empty_address(client):
    for proto, port in (("tcp", "5432"), ("udp", "53")):
        post_form(client, "/save", serviceName=f"x{proto}", subdomain=f"x{proto}",
                  protocol=proto, targetIp="", targetPort=port)
    raw = open(str(__import__("conftest").DYNAMIC_PATH)).read()
    assert "address: ':'" not in raw and 'address: ":"' not in raw


def test_backends_json_alone_is_enough(client):
    r = post_form(client, "/save", serviceName="jsononly", subdomain="jsononly",
                  protocol="tcp",
                  backendsJsonTcp=json.dumps({"servers": [{"host": "10.0.0.7", "port": "6379"}]}))
    assert r.status_code < 400, r.data[:200]
    lb = read_config()["tcp"]["services"]["jsononly-service"]["loadBalancer"]
    assert lb["servers"][0]["address"] == "10.0.0.7:6379"


def test_tcp_does_not_double_append_the_domain(client):
    r = post_form(client, "/save", serviceName="fqdn", subdomain="db.other.tld",
                  protocol="tcp", targetIp=["", "10.0.0.9", ""],
                  targetPort=["", "5432", ""])
    assert r.status_code < 400
    rule = read_config()["tcp"]["routers"]["fqdn"]["rule"]
    assert rule == "HostSNI(`db.other.tld`)", rule
    assert ".example.com" not in rule, "the base domain was appended to an FQDN"


def test_tcp_still_appends_the_domain_to_a_bare_label(client):
    r = post_form(client, "/save", serviceName="bare", subdomain="db",
                  protocol="tcp", targetIp=["", "10.0.0.9", ""],
                  targetPort=["", "5432", ""])
    assert r.status_code < 400
    assert read_config()["tcp"]["routers"]["bare"]["rule"] == "HostSNI(`db.example.com`)"


def test_http_and_tcp_treat_subdomains_the_same(client):
    post_form(client, "/save", serviceName="hsame", subdomain="svc.other.tld",
              protocol="http", scheme="http", targetIp="10.0.0.1", targetPort="80")
    post_form(client, "/save", serviceName="tsame", subdomain="svc.other.tld",
              protocol="tcp", targetIp=["", "10.0.0.2", ""], targetPort=["", "443", ""])
    cfg = read_config()
    assert "svc.other.tld" in cfg["http"]["routers"]["hsame"]["rule"]
    assert "svc.other.tld" in cfg["tcp"]["routers"]["tsame"]["rule"]
    assert "other.tld.example.com" not in str(cfg)


def _mobile_save(client, proto, ip, port, **extra):
    slot = {'http': 0, 'tcp': 1, 'udp': 2}[proto]
    ips, ports = ['', '', ''], ['', '', '']
    ips[slot], ports[slot] = ip, port
    return post_form(client, "/save", protocol=proto, targetIp=ips, targetPort=ports, **extra)


def test_mobile_shaped_save_works_for_every_protocol(client):
    for proto, ip, port, extra in (
            ('http', '10.0.0.1', '8080', dict(serviceName='mh', subdomain='mh.example.com', scheme='http')),
            ('tcp',  '10.0.0.9', '5432', dict(serviceName='mt', subdomain='mt')),
            ('udp',  '10.0.0.53', '53',  dict(serviceName='mu', subdomain='mu'))):
        r = _mobile_save(client, proto, ip, port, **extra)
        assert r.status_code < 400, '%s save failed: %s' % (proto, r.data[:200])

    cfg = read_config()
    assert cfg['http']['services']['mh-service']['loadBalancer']['servers'][0]['url'] == 'http://10.0.0.1:8080'
    assert cfg['tcp']['services']['mt-service']['loadBalancer']['servers'][0]['address'] == '10.0.0.9:5432'
    assert cfg['udp']['services']['mu-service']['loadBalancer']['servers'][0]['address'] == '10.0.0.53:53'


def test_mobile_edit_preserves_load_balancing(client):
    post_form(client, "/save", serviceName='multi', subdomain='multi.example.com',
              protocol='http', scheme='http', targetIp='10.0.0.1', targetPort='80',
              backendsJsonHttp=json.dumps({
                  'servers': [{'scheme': 'http', 'host': '10.0.0.1', 'port': '80'},
                              {'scheme': 'http', 'host': '10.0.0.2', 'port': '80'}],
                  'sticky': {'enabled': True, 'cookieName': 'keep'},
                  'priority': 42}))

    _mobile_save(client, 'http', '10.9.9.9', '99', serviceName='multi',
                 subdomain='multi.example.com', scheme='http',
                 isEdit='true', originalId='multi')

    cfg = read_config()
    lb = cfg['http']['services']['multi-service']['loadBalancer']
    assert '10.9.9.9:99' in lb['servers'][0]['url']
    assert len(lb['servers']) == 2, 'mobile edit wiped the second backend'
    assert lb['sticky']['cookie']['name'] == 'keep'
    assert cfg['http']['routers']['multi']['priority'] == 42


def test_mobile_backend_edit_round_trips_through_the_api(client):
    post_form(client, "/save", serviceName='lb', subdomain='lb.example.com',
              protocol='http', scheme='http', targetIp='10.0.0.1', targetPort='80',
              backendsJsonHttp=json.dumps({
                  'servers': [{'scheme': 'http', 'host': '10.0.0.1', 'port': '80'},
                              {'scheme': 'http', 'host': '10.0.0.2', 'port': '80'}],
                  'sticky': {'enabled': True, 'cookieName': 'webcookie', 'secure': True},
                  'healthCheck': {'enabled': True, 'path': '/hz', 'interval': '10s'},
                  'priority': 42}))

    route = next(a for a in client.get("/api/routes/all").get_json()['apps']
                 if a['id'] == 'lb')

    servers = [{'scheme': s.split(':')[0], 'host': s.split('//')[1].split(':')[0],
                'port': s.split(':')[-1]} for s in route['servers']]
    payload = {'servers': servers + [{'scheme': 'http', 'host': '10.0.0.3', 'port': '80'}]}
    if route['stickyEnabled']:
        payload['sticky'] = {'enabled': True,
                             'cookieName': route['sticky'].get('name', ''),
                             'secure':     bool(route['sticky'].get('secure')),
                             'httpOnly':   bool(route['sticky'].get('httpOnly'))}
    if route['healthCheck']:
        payload['healthCheck'] = {'enabled': True,
                                  'path':     route['healthCheck'].get('path', ''),
                                  'interval': route['healthCheck'].get('interval', ''),
                                  'timeout':  route['healthCheck'].get('timeout', '')}
    if isinstance(route['priority'], int):
        payload['priority'] = route['priority']

    r = _mobile_save(client, 'http', '10.0.0.1', '80', serviceName='lb',
                     subdomain='lb.example.com', scheme='http', isEdit='true',
                     originalId='lb', backendsJsonHttp=json.dumps(payload))
    assert r.status_code < 400, r.data[:200]

    cfg = read_config()
    lb  = cfg['http']['services']['lb-service']['loadBalancer']
    assert len(lb['servers']) == 3
    assert lb['sticky']['cookie']['name'] == 'webcookie', 'sticky lost on backend edit'
    assert lb['sticky']['cookie']['secure'] is True
    assert lb['healthCheck']['path'] == '/hz', 'health check lost on backend edit'
    assert lb['healthCheck']['interval'] == '10s'
    assert cfg['http']['routers']['lb']['priority'] == 42


@pytest.mark.parametrize("proto,ip,port,expected", [
    ('tcp', '10.0.0.9:5432',  '',     '10.0.0.9:5432'),
    ('tcp', '[::1]:5432',     '',     '[::1]:5432'),
    ('udp', '10.0.0.53:53',   '',     '10.0.0.53:53'),
    ('tcp', '10.0.0.9',       '5432', '10.0.0.9:5432'),
])
def test_tcp_udp_save_recovers_a_combined_host_port(client, proto, ip, port, expected):
    r = _mobile_save(client, proto, ip, port, serviceName='sv', subdomain='sv')
    assert r.status_code < 400, r.data[:200]
    lb = read_config()[proto]['services']['sv-service']['loadBalancer']
    assert lb['servers'][0]['address'] == expected


@pytest.mark.parametrize("proto,ip", [('tcp', '10.0.0.9'), ('udp', '10.0.0.53'), ('tcp', '::1')])
def test_tcp_udp_save_refuses_a_missing_port(client, proto, ip):
    r = _mobile_save(client, proto, ip, '', serviceName='sv', subdomain='sv')
    assert r.status_code == 400
    assert b'port is required' in r.data
    assert 'sv-service' not in read_config().get(proto, {}).get('services', {})


def _make_owner(client, name='app1', ip='10.0.0.50', port='80'):
    post_form(client, "/save", serviceName=name, subdomain=name, protocol='http',
              scheme='http', targetIp=ip, targetPort=port)


def test_service_ref_writes_router_only(client):
    _make_owner(client)
    r = post_form(client, "/save", serviceName='app2', subdomain='app2',
                  protocol='http', scheme='http', targetIp='', targetPort='',
                  middlewares='mid2', serviceRef='app1-service')
    assert r.status_code < 400, r.data[:200]
    cfg = read_config()
    router = cfg['http']['routers']['app2']
    assert router['service'] == 'app1-service'
    assert router['middlewares'] == ['mid2']
    assert 'app2-service' not in cfg['http']['services']
    assert 'app2-transport' not in cfg.get('http', {}).get('serversTransports', {})


def test_service_ref_rejects_missing_service(client):
    r = post_form(client, "/save", serviceName='app2', subdomain='app2',
                  protocol='http', scheme='http', targetIp='', targetPort='',
                  serviceRef='nope-service')
    assert r.status_code == 400
    assert b'does not exist' in r.data
    assert 'app2' not in read_config().get('http', {}).get('routers', {})


def test_service_ref_edit_keeps_reference(client):
    _make_owner(client)
    post_form(client, "/save", serviceName='app2', subdomain='app2', protocol='http',
              scheme='http', targetIp='', targetPort='', serviceRef='app1-service')
    r = post_form(client, "/save", serviceName='app2', subdomain='app2', protocol='http',
                  scheme='http', targetIp='', targetPort='', middlewares='mid1,mid2',
                  serviceRef='app1-service', isEdit='true', originalId='app2')
    assert r.status_code < 400, r.data[:200]
    cfg = read_config()
    assert cfg['http']['routers']['app2']['service'] == 'app1-service'
    assert cfg['http']['routers']['app2']['middlewares'] == ['mid1', 'mid2']
    assert 'app2-service' not in cfg['http']['services']


def test_legacy_edit_of_referenced_route_preserves_reference(client):
    _make_owner(client)
    post_form(client, "/save", serviceName='app2', subdomain='app2', protocol='http',
              scheme='http', targetIp='', targetPort='', serviceRef='app1-service')
    r = post_form(client, "/save", serviceName='app2', subdomain='app2', protocol='http',
                  scheme='http', targetIp='10.9.9.9', targetPort='99',
                  isEdit='true', originalId='app2')
    assert r.status_code < 400, r.data[:200]
    cfg = read_config()
    assert cfg['http']['routers']['app2']['service'] == 'app1-service'
    assert 'app2-service' not in cfg['http']['services']
    servers = cfg['http']['services']['app1-service']['loadBalancer']['servers']
    assert servers == [{'url': 'http://10.0.0.50:80'}], 'legacy edit wrote into the shared service'


def test_deleting_referencing_route_keeps_service(client):
    _make_owner(client)
    post_form(client, "/save", serviceName='app2', subdomain='app2', protocol='http',
              scheme='http', targetIp='', targetPort='', serviceRef='app1-service')
    r = post_form(client, "/delete/app2")
    assert r.status_code < 400
    cfg = read_config()
    assert 'app2' not in cfg['http']['routers']
    assert 'app1' in cfg['http']['routers']
    assert 'app1-service' in cfg['http']['services']


def test_deleting_owner_route_keeps_shared_service(client):
    _make_owner(client)
    post_form(client, "/save", serviceName='app2', subdomain='app2', protocol='http',
              scheme='http', targetIp='', targetPort='', serviceRef='app1-service')
    post_form(client, "/delete/app1")
    cfg = read_config()
    assert 'app1' not in cfg['http']['routers']
    assert cfg['http']['routers']['app2']['service'] == 'app1-service'
    assert 'app1-service' in cfg['http']['services']


@pytest.mark.parametrize("proto,sub", [('tcp', 'db'), ('udp', 'dns')])
def test_service_ref_tcp_udp(client, proto, sub):
    slot = {'tcp': 1, 'udp': 2}[proto]
    ips, ports = ['', '', ''], ['', '', '']
    ips[slot], ports[slot] = '10.0.0.9', '5432'
    post_form(client, "/save", serviceName='owner', subdomain='owner', protocol=proto,
              targetIp=ips, targetPort=ports)
    r = post_form(client, "/save", serviceName=sub, subdomain=sub, protocol=proto,
                  serviceRef='owner-service')
    assert r.status_code < 400, r.data[:200]
    cfg = read_config()
    assert cfg[proto]['routers'][sub]['service'] == 'owner-service'
    assert f'{sub}-service' not in cfg[proto]['services']


def test_service_ref_provider_qualified_is_written_verbatim(client):
    r = post_form(client, "/save", serviceName='dash', subdomain='dash',
                  protocol='http', scheme='http', targetIp='', targetPort='',
                  serviceRef='whoami@docker')
    assert r.status_code < 400, r.data[:200]
    cfg = read_config()
    assert cfg['http']['routers']['dash']['service'] == 'whoami@docker'
    assert 'whoami' not in cfg['http'].get('services', {})
    assert 'dash-service' not in cfg['http'].get('services', {})


def test_switching_own_route_to_ref_cleans_up_orphan(client):
    _make_owner(client)
    _make_owner(client, name='app2', ip='10.0.0.60', port='81')
    post_form(client, "/save", serviceName='app2', subdomain='app2', protocol='http',
              scheme='http', targetIp='', targetPort='', serviceRef='app1-service',
              isEdit='true', originalId='app2')
    cfg = read_config()
    assert cfg['http']['routers']['app2']['service'] == 'app1-service'
    assert 'app2-service' not in cfg['http']['services']
    assert 'app1-service' in cfg['http']['services']


def test_negative_router_priority_is_kept(client):
    r = _save_http(client, name="catchall", backendsJsonHttp=json.dumps({
        "servers": [{"scheme": "http", "host": "10.0.0.1", "port": "8080"}],
        "priority": -100,
    }))
    assert r.status_code < 400
    assert read_config()["http"]["routers"]["catchall"]["priority"] == -100


def test_zero_router_priority_is_dropped(client):
    r = _save_http(client, name="zeroprio", backendsJsonHttp=json.dumps({
        "servers": [{"scheme": "http", "host": "10.0.0.1", "port": "8080"}],
        "priority": 0,
    }))
    assert r.status_code < 400
    assert "priority" not in read_config()["http"]["routers"]["zeroprio"]


def _seed_disabled(app_module, route_id):
    s = app_module.load_settings()
    disabled = dict(s.get("disabled_routes", {}))
    disabled[route_id] = {"protocol": "http", "configFile": "dynamic.yml",
                          "router": {"rule": "Host(`gone.example.com`)", "service": "gone-service"},
                          "service": {"loadBalancer": {"servers": [{"url": "http://10.0.0.1:8080"}]}}}
    app_module.save_settings(
        domains=s["domains"], cert_resolver=s["cert_resolver"],
        traefik_api_url=s["traefik_api_url"], auth_enabled=s["auth_enabled"],
        password_hash=s["password_hash"], visible_tabs=s["visible_tabs"],
        disabled_routes=disabled, managed_middlewares=s["managed_middlewares"])


def test_delete_a_disabled_route_stored_under_a_prefixed_id(client, app_module):
    route_id = "dynamic.yml::gone"
    _seed_disabled(app_module, route_id)

    r = post_form(client, f"/delete/{route_id}")
    assert r.status_code < 400, r.data
    assert route_id not in app_module.load_settings().get("disabled_routes", {})


def test_delete_a_disabled_route_stored_under_a_bare_id(client, app_module):
    _seed_disabled(app_module, "gone")

    r = post_form(client, "/delete/gone")
    assert r.status_code < 400, r.data
    assert "gone" not in app_module.load_settings().get("disabled_routes", {})


def test_editing_a_disabled_route_keeps_it_disabled(client, app_module):
    _save_http(client, backendsJsonHttp=BACKENDS)
    client.post("/api/routes/app1/toggle", json={"enable": False, "csrf_token": "testtoken"},
                headers={"X-CSRF-Token": "testtoken"})
    assert "app1" not in (read_config().get("http", {}).get("routers") or {})

    _save_http(client, isEdit="true", originalId="app1", backendsJsonHttp=BACKENDS)

    routers = read_config().get("http", {}).get("routers") or {}
    assert "app1" not in routers, \
        "editing a disabled route must not write it back into the config file as enabled"

    disabled = app_module.load_settings().get("disabled_routes", {})
    assert "app1" in disabled, "the route must still be recorded as disabled after the edit"
    assert disabled["app1"]["router"], "the stored disabled route must carry the edited router"


def test_load_balancing_checkboxes_are_wired_to_their_panels(client):
    html = client.get('/').get_data(as_text=True)
    for box in ('lbStickyEnabled', 'lbHealthEnabled'):
        tag = next((t for t in html.split('<input') if 'id="%s"' % box in t), None)
        assert tag is not None, '%s is missing from the route modal' % box
        assert '_lbSyncToggles()' in tag.split('>')[0], (
            '%s has no handler, so its panel never opens' % box)


def test_a_route_save_keeps_health_check_fields_the_route_form_cannot_edit(client):
    post_form(client, "/save", serviceName='pool', subdomain='pool.example.com',
              protocol='http', scheme='http', targetIp='10.0.0.1', targetPort='80',
              backendsJsonHttp=json.dumps({
                  'servers': [{'scheme': 'http', 'host': '10.0.0.1', 'port': '80'}],
                  'healthCheck': {'enabled': True, 'path': '/hz', 'interval': '10s'}}))

    import io
    from ruamel.yaml import YAML
    cfg = read_config()
    cfg['http']['services']['pool-service']['loadBalancer']['healthCheck'].update(
        {'method': 'HEAD', 'port': 8080, 'headers': {'X-Probe': 'tm'}})
    buf = io.StringIO()
    YAML().dump(cfg, buf)
    write_config(buf.getvalue())

    r = post_form(client, "/save", serviceName='pool', subdomain='pool.example.com',
                  protocol='http', scheme='http', targetIp='10.0.0.1', targetPort='80',
                  isEdit='true', originalId='pool',
                  backendsJsonHttp=json.dumps({
                      'servers': [{'scheme': 'http', 'host': '10.0.0.1', 'port': '80'},
                                  {'scheme': 'http', 'host': '10.0.0.2', 'port': '80'}],
                      'healthCheck': {'enabled': True, 'path': '/hz', 'interval': '30s'}}))
    assert r.status_code < 400, r.data[:200]

    hc = read_config()['http']['services']['pool-service']['loadBalancer']['healthCheck']
    assert hc['interval'] == '30s', 'the route form owns interval'
    assert hc['method'] == 'HEAD' and hc['port'] == 8080 and hc['headers'] == {'X-Probe': 'tm'}, \
        'the route form truncated fields it has no editor for: %r' % (hc,)


def test_turning_the_health_check_off_in_the_route_form_removes_the_whole_block(client):
    post_form(client, "/save", serviceName='pool', subdomain='pool.example.com',
              protocol='http', scheme='http', targetIp='10.0.0.1', targetPort='80',
              backendsJsonHttp=json.dumps({
                  'servers': [{'scheme': 'http', 'host': '10.0.0.1', 'port': '80'}],
                  'healthCheck': {'enabled': True, 'path': '/hz'}}))
    post_form(client, "/save", serviceName='pool', subdomain='pool.example.com',
              protocol='http', scheme='http', targetIp='10.0.0.1', targetPort='80',
              isEdit='true', originalId='pool',
              backendsJsonHttp=json.dumps({
                  'servers': [{'scheme': 'http', 'host': '10.0.0.1', 'port': '80'}],
                  'healthCheck': {'enabled': False, 'path': '/hz'}}))
    assert 'healthCheck' not in read_config()['http']['services']['pool-service']['loadBalancer']

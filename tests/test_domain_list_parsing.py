import json

import pytest

import core.agents_store as store
import core.settings as settings_mod
from conftest import post_json
from core import config as config_mod

HDR = {'X-CSRF-Token': 'testtoken', 'X-Requested-With': 'fetch'}


@pytest.fixture(autouse=True)
def _keep_domains():
    before = settings_mod.load_settings()['domains']
    yield
    settings_mod.update_settings(domains=before)


@pytest.mark.parametrize('raw, want', [
    ('a.com,b.com', ['a.com', 'b.com']),
    ('a.com b.com', ['a.com', 'b.com']),
    ('a.com\nb.com\r\nc.com', ['a.com', 'b.com', 'c.com']),
    ('a.com,  b.com\tc.com', ['a.com', 'b.com', 'c.com']),
    ('  A.Com , ,B.COM,,  ', ['a.com', 'b.com']),
    ('a.com b.com a.com A.COM', ['a.com', 'b.com']),
    ('', []),
    (' , \n ', []),
    (None, []),
    (['a.com b.com', ' C.com ', '', None, 'a.com'], ['a.com', 'b.com', 'c.com']),
    (('x.org',), ['x.org']),
])
def test_parse_domains_accepts_commas_spaces_and_newlines(raw, want):
    assert config_mod.parse_domains(raw) == want


def _settings_body(domains):
    s = settings_mod.load_settings()
    return {'domains': domains, 'cert_resolver': s['cert_resolver'],
            'traefik_api_url': s['traefik_api_url']}


def test_api_settings_saves_a_space_separated_string(client):
    r = post_json(client, '/api/settings', _settings_body('Mywire.org expander.net.au\nmywire.org'))
    assert r.status_code == 200, r.get_data(as_text=True)
    assert settings_mod.load_settings(fresh=True)['domains'] == ['mywire.org', 'expander.net.au']


def test_api_settings_normalises_a_list(client):
    r = post_json(client, '/api/settings', _settings_body([' A.com ', 'b.com c.com', 'a.com']))
    assert r.status_code == 200, r.get_data(as_text=True)
    assert settings_mod.load_settings(fresh=True)['domains'] == ['a.com', 'b.com', 'c.com']


def test_api_settings_still_requires_one_domain(client):
    before = settings_mod.load_settings()['domains']
    r = post_json(client, '/api/settings', _settings_body(' ,\n '))
    assert r.status_code == 400
    assert settings_mod.load_settings(fresh=True)['domains'] == before


def test_manager_yml_domains_are_normalised_on_load():
    settings_mod.update_settings(domains=['Example.COM other.net', 'example.com', ''])
    assert settings_mod.load_settings(fresh=True)['domains'] == ['example.com', 'other.net']


def test_domains_env_var_accepts_spaces_and_newlines(monkeypatch):
    monkeypatch.setenv('DOMAINS', 'One.com two.com\nthree.com,one.com')
    assert settings_mod._load_settings(b'cert_resolver: x\n')['domains'] == ['one.com', 'two.com', 'three.com']


def test_domains_env_var_falls_back_when_empty(monkeypatch):
    monkeypatch.setenv('DOMAINS', ' , ')
    assert settings_mod._load_settings(b'cert_resolver: x\n')['domains'] == ['example.com']


def test_agent_domains_are_normalised_on_update(client):
    store.save_agents_file([{'id': 'a1', 'name': 'alpha', 'url': 'http://a1:8090', 'api_key': 'k1'}])
    r = client.put('/api/agents/a1', data=json.dumps({'domains': ['A.com b.com', 'a.com']}),
                   content_type='application/json', headers=HDR)
    assert r.status_code < 400, r.get_data(as_text=True)
    assert store.load_agents(fresh=True)[0]['domains'] == ['a.com', 'b.com']


def test_agent_domains_are_normalised_on_load():
    parsed = store.parse_agent_dict({'id': 'x', 'name': 'N', 'url': 'http://a:1',
                                     'domains': ['X.org y.org', 'x.org']})
    assert parsed['domains'] == ['x.org', 'y.org']


def test_setup_wizard_accepts_space_separated_domains(client):
    s = settings_mod.load_settings()
    settings_mod.save_settings(
        domains=s['domains'], cert_resolver=s['cert_resolver'],
        traefik_api_url=s['traefik_api_url'], auth_enabled=True,
        password_hash=s['password_hash'], visible_tabs=s['visible_tabs'],
        setup_complete=False, crowdsec_lapi_url='', crowdsec_api_key='',
        crowdsec_machine_id='', crowdsec_machine_password='',
        git_backup_enabled=False, git_backup_repo='', git_backup_token='',
        git_backup_auto_push=False, webhook_url='', webhook_type='',
        notification_channels=[], geoip_enabled=False, default_theme='dark')
    pw = 'Correct-Horse-Battery-92'
    r = client.post('/setup', data={'csrf_token': 'testtoken', 'domains': 'Home.lab  example.org\nhome.lab',
                                    'cert_resolver': 'letsencrypt', 'traefik_api_url': 'http://traefik:8080',
                                    'visible_tabs': '{}', 'password': pw, 'confirm': pw},
                    headers={'X-Requested-With': 'fetch'})
    assert r.status_code < 400, r.get_data(as_text=True)
    after = settings_mod.load_settings(fresh=True)
    assert after['setup_complete'] is True, r.get_data(as_text=True)[:500]
    assert after['domains'] == ['home.lab', 'example.org']

import os

import pytest

import core.settings as settings_mod
from conftest import post_json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(autouse=True)
def _clear_limit():
    yield
    s = settings_mod.load_settings()
    settings_mod.save_settings(domains=s['domains'], cert_resolver=s['cert_resolver'],
                               traefik_api_url=s['traefik_api_url'],
                               crowdsec_alert_limit='')


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


def _base(**over):
    s = settings_mod.load_settings()
    body = {'domains': ','.join(s['domains']), 'cert_resolver': s['cert_resolver'],
            'traefik_api_url': s['traefik_api_url']}
    body.update(over)
    return body


def test_the_limit_survives_an_unrelated_settings_save(client):
    s = settings_mod.load_settings()
    settings_mod.save_settings(domains=s['domains'], cert_resolver=s['cert_resolver'],
                               traefik_api_url=s['traefik_api_url'],
                               crowdsec_alert_limit='4321')
    settings_mod.save_settings(domains=s['domains'], cert_resolver=s['cert_resolver'],
                               traefik_api_url=s['traefik_api_url'], default_theme='dark')
    assert settings_mod.load_settings()['crowdsec_alert_limit'] == '4321', (
        'the setting used to be read but never written, so any later save dropped it')


@pytest.mark.parametrize('bad', ['-1', '100001', 'lots'])
def test_a_bad_limit_is_rejected(client, bad):
    r = post_json(client, '/api/settings', _base(crowdsec_alert_limit=bad))
    assert r.status_code == 400, r.get_data(as_text=True)


@pytest.mark.parametrize('good', ['0', '500', '100000'])
def test_a_valid_limit_is_accepted(client, good):
    r = post_json(client, '/api/settings', _base(crowdsec_alert_limit=good))
    assert r.status_code < 400, r.get_data(as_text=True)
    assert settings_mod.load_settings()['crowdsec_alert_limit'] == good


def test_the_agent_honours_a_limit_query_and_clamps_it():
    go = _read('agent', 'handlers.go')
    body = go.split('func (a *App) crowdsecAlertsHandler', 1)[1].split('\n}\n', 1)[0]
    assert 'r.URL.Query().Get("limit")' in body
    assert 'n <= 100000' in body and 'n >= 0' in body


def test_capped_is_measured_before_the_lists_filter():
    go = _read('agent', 'handlers.go')
    body = go.split('func (a *App) crowdsecAlertsHandler', 1)[1].split('\n}\n', 1)[0]
    cap = body.index('capped :=')
    filt = body.index('meta.Decisions[0].Origin == "lists"')
    assert cap < filt, (
        'measuring after the filter under-reports: a full page of blocklist alerts would '
        'look like it was not capped')


def test_the_agent_sets_both_headers():
    body = _read('agent', 'handlers.go').split(
        'func (a *App) crowdsecAlertsHandler', 1)[1].split('\n}\n', 1)[0]
    assert 'X-CS-Alert-Limit' in body and 'X-CS-Alert-Capped' in body


def test_the_proxy_forwards_x_headers_but_not_credentials():
    app = _read('app.py')
    body = app.split('def api_agents_proxy', 1)[1].split('\n@app.route', 1)[0]
    assert "startswith('x-')" in body
    assert '_PROXY_HEADER_DENY' in body
    deny = app.split('_PROXY_HEADER_DENY = frozenset({', 1)[1].split('})', 1)[0]
    assert 'x-api-key' in deny, 'the agent key must never be relayed to the browser'


def test_the_frontend_reads_the_cap_headers():
    js = _read('static', 'js', 'crowdsec.js')
    assert '_csAltCapped = alt.capped === true' in js
    assert '_csAltLimit  = parseInt(alt.limit, 10)' in js


def test_the_hub_passes_its_limit_to_agents_only():
    js = _read('static', 'js', 'crowdsec.js')
    body = js.split('function _csLimitParam', 1)[1].split('\n}', 1)[0]
    assert '_activeAgent' in body, 'the Host applies its own limit server-side already'

import os

from core import providers

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


def test_every_provider_tab_has_a_provider_that_opens_it():
    from core import settings as settings_mod
    tabs = set(providers.TAB_FOR_PROVIDER.values())
    missing = tabs - set(settings_mod.OPTIONAL_TABS)
    assert not missing, f'these map to tabs that do not exist: {sorted(missing)}'
    for tab in tabs:
        assert os.path.exists(os.path.join(ROOT, 'static', 'js', f'tab-{tab}.js')), \
            f'{tab} has no tab to show'


def test_traefiks_own_provider_names_are_recognised():
    assert providers.tab_for('Docker') == 'docker'
    assert providers.tab_for('KubernetesCRD') == 'kubernetes'
    assert providers.tab_for('KubernetesIngress') == 'kubernetes'
    assert providers.tab_for('KubernetesGateway') == 'kubernetes'
    assert providers.tab_for('ConsulCatalog') == 'consulcatalog'
    assert providers.tab_for('HTTP') == 'http_provider'
    assert providers.tab_for('@docker') == 'docker'


def test_the_providers_that_have_no_tab_are_left_alone():
    for name in ('File', 'file', 'acme', 'plugin-foo', '', None, 'something-new'):
        assert providers.tab_for(name) == '', f'{name!r} should not open a tab'


def test_the_overview_is_enough_to_know_which_tabs_to_show():
    found = providers.tabs_from_overview({'providers': ['Docker', 'File', 'Internal']})
    assert found == {'docker', 'internal'}, 'file is the Routes tab, not a provider tab'
    assert providers.tabs_from_overview(None) == set()
    assert providers.tabs_from_overview({}) == set()


def test_router_names_work_when_the_overview_does_not_list_providers():
    payload = {'http': [{'name': 'a@docker'}, {'name': 'b@file'}],
               'tcp': [{'name': 'c@nomad', 'provider': 'nomad'}],
               'udp': []}
    assert providers.tabs_from_routers(payload) == {'docker', 'nomad'}
    assert providers.tabs_from_routers([{'name': 'x@ecs'}]) == {'ecs'}
    assert providers.tabs_from_routers(None) == set()


def test_a_tab_is_only_offered_once_so_turning_it_off_sticks():
    assert providers.newly_seen({'docker', 'nomad'}, []) == ['docker', 'nomad']
    assert providers.newly_seen({'docker', 'nomad'}, ['docker']) == ['nomad']
    assert providers.newly_seen({'docker'}, ['docker']) == [], \
        'a tab the user has already been offered must never be switched back on'


def test_detection_costs_no_extra_request():
    from core import monitor
    src = _read('core', 'monitor.py')
    assert '_check_provider_tabs' not in src, \
        'a second check would fetch the overview twice a minute for every server'
    body = src[src.index('def _check_traefik():'):src.index('def _check_agents():')]
    assert '_apply_provider_tabs(' in body, 'the overview is already fetched here, reuse it'
    for tab in set(providers.TAB_FOR_PROVIDER.values()):
        assert tab in monitor.TAB_LABELS, f'{tab} would be announced by its internal name'


def test_an_unchanged_provider_list_touches_no_files(monkeypatch):
    from core import monitor
    monitor._provider_seen.clear()
    calls = []
    monkeypatch.setattr(monitor, '_enable_host_provider_tabs', lambda found: calls.append(found) or [])
    try:
        overview = {'providers': ['Docker', 'File']}
        monitor._apply_provider_tabs(monitor.HOST_SERVER, '', overview)
        monitor._apply_provider_tabs(monitor.HOST_SERVER, '', overview)
        assert len(calls) == 1, 'the settings file would be read every minute forever'
        monitor._apply_provider_tabs(monitor.HOST_SERVER, '', {'providers': ['Docker', 'Nomad']})
        assert len(calls) == 2, 'a provider appearing later has to be picked up'
    finally:
        monitor._provider_seen.clear()


def test_the_host_and_agents_both_get_their_tabs_turned_on():
    src = _read('core', 'monitor.py')
    body = src[src.index('def _apply_provider_tabs('):src.index('def _enable_host_provider_tabs')]
    assert '_enable_host_provider_tabs' in body and '_enable_agent_provider_tabs' in body, \
        'agents must discover their own providers, same as the host'
    start = src.index('def _enable_agent_provider_tabs')
    agent = src[start:src.index('\ndef ', start + 10)]
    assert 'save_agents_file' in agent, 'the agent tab choice has to survive a restart'
    host = src[src.index('def _enable_host_provider_tabs'):src.index('def _enable_agent_provider_tabs')]
    assert 'provider_tabs_seen' in host and 'save_settings' in host


def test_the_setup_wizard_ticks_what_traefik_reports():
    app_src = _read('app.py')
    assert 'def _detect_provider_tabs()' in app_src
    assert 'detected_tabs=_detect_provider_tabs()' in app_src, 'the wizard never receives the detection'
    html = _read('templates', 'login.html')
    assert 'const DETECTED_TABS = {{ detected_tabs | tojson }};' in html
    assert 'DETECTED_TABS.forEach(t => { setupTabs[t] = true; });' in html
    assert '_paintSetupTabs();' in html, 'the toggles would read off while the value says on'


def test_the_seen_list_is_stored_and_survives_a_reload():
    from core import settings as settings_mod
    src = _read('core', 'settings.py')
    assert "'provider_tabs_seen':   []," in src, 'it needs a default or every restart re-offers every tab'
    assert 'provider_tabs_seen=None' in src
    assert 'provider_tabs_seen' in settings_mod.load_settings()
    agents = _read('core', 'agents_store.py')
    assert 'provider_tabs_seen' in agents, 'an agent would re-enable a tab the user turned off'

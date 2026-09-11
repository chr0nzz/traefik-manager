import glob
import os
import re

from core.config import yaml_safe

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

RUNTIME_SUPPLIED = {'HOSTNAME', 'PATH', 'TZ', 'PWD', 'HOME', 'PATH_INFO', 'SCRIPT_NAME'}
READ_BY_A_LIBRARY = {'DOCKER_HOST'}
READ_IN_A_LOOP = {'STATIC_CONFIG_PATH', 'ACCESS_LOG_PATH', 'ACME_JSON_PATH', 'PLUGINS_DIR'}


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


def _documented(path):
    return set(re.findall(r'^#?\s*([A-Z][A-Z0-9_]*)=', _read(path), re.M))


def _host_env_vars():
    found = set()
    for rel in ['app.py'] + [os.path.relpath(p, ROOT) for p in glob.glob(os.path.join(ROOT, 'core', '*.py'))]:
        src = _read(rel)
        found |= set(re.findall(r"environ\.get\(\s*['\"]([A-Z][A-Z0-9_]*)['\"]", src))
        found |= set(re.findall(r"environ\[\s*['\"]([A-Z][A-Z0-9_]*)['\"]", src))
        found |= set(re.findall(r"_env_bool\(\s*['\"]([A-Z][A-Z0-9_]*)['\"]", src))
        found |= set(re.findall(r"_cs_int_env\(\s*['\"]([A-Z][A-Z0-9_]*)['\"]", src))
    return found - RUNTIME_SUPPLIED


def _agent_env_vars():
    found = set()
    for path in glob.glob(os.path.join(ROOT, 'agent', '*.go')):
        src = _read(os.path.relpath(path, ROOT))
        found |= set(re.findall(r'(?:envOr|envInt|envIntRange|envBool|os\.Getenv)\(\s*"([A-Z][A-Z0-9_]*)"', src))
    return found - RUNTIME_SUPPLIED


def test_every_host_variable_is_in_the_env_example():
    missing = sorted(_host_env_vars() - _documented('.env.example') - READ_BY_A_LIBRARY)
    assert not missing, f'.env.example does not mention {missing}'


def test_every_agent_variable_is_in_the_agent_env_example():
    missing = sorted(_agent_env_vars() - _documented(os.path.join('agent', '.env.example')) - READ_BY_A_LIBRARY)
    assert not missing, f'agent/.env.example does not mention {missing}'


def test_the_env_examples_invent_nothing():
    for path, actual in (('.env.example', _host_env_vars() | READ_BY_A_LIBRARY | READ_IN_A_LOOP),
                         (os.path.join('agent', '.env.example'), _agent_env_vars() | READ_BY_A_LIBRARY)):
        extra = sorted(_documented(path) - actual)
        assert not extra, f'{path} documents {extra}, which nothing reads'


def test_the_sample_manager_yml_is_read_back_as_written(tmp_path, monkeypatch):
    import core.env as env_mod
    import core.settings as settings_mod
    sample = yaml_safe.load(_read('manager.yml'))
    cfg = tmp_path / 'cfg'
    cfg.mkdir()
    (cfg / 'manager.yml').write_text(_read('manager.yml'), encoding='utf-8')
    monkeypatch.setattr(env_mod, 'SETTINGS_PATH', str(cfg / 'manager.yml'))
    monkeypatch.setattr(env_mod, 'OTP_KEY_PATH', str(cfg / '.otp_key'))
    loaded = settings_mod.load_settings()
    for key in ('domains', 'cert_resolver', 'oidc_enabled', 'oidc_auto_login',
                'notification_channels', 'notifications_read_until',
                'managed_middlewares', 'disabled_routes', 'geoip_enabled'):
        assert key in loaded, f'{key} is in the sample but the loader drops it'
        assert loaded[key] == sample[key], f'{key} did not survive a load'


def test_the_sample_covers_every_oidc_key():
    sample = yaml_safe.load(_read('manager.yml'))
    oidc = [k for k in sample if k.startswith('oidc_')]
    assert len(oidc) == 10, f'the sample has {len(oidc)} oidc keys, the code has 10: {sorted(oidc)}'


def test_the_sample_does_not_promise_an_empty_allowlist_admits_everyone():
    block = _read('manager.yml')
    block = block[block.index('# -- OIDC'):block.index('oidc_enabled:')]
    block = ' '.join(block.replace('#', ' ').split())
    assert 'denies every login' in block, (
        'leaving both allow-lists empty denies every login (app.py, _oidc_claims_allowed); '
        'the sample must not say the opposite')

import os
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, 'scripts', 'docker-entrypoint.sh')
AGENT_SCRIPT = os.path.join(ROOT, 'agent', 'docker-entrypoint.sh')


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


def _run(env_extra, *cmd):
    env = {k: v for k, v in os.environ.items() if k not in ('PUID', 'PGID')}
    env.update(env_extra)
    return subprocess.run(['sh', SCRIPT, *cmd], capture_output=True, text=True, env=env, timeout=20)


def test_the_agent_ships_the_same_entrypoint_as_the_app():
    assert _read('scripts', 'docker-entrypoint.sh') == _read('agent', 'docker-entrypoint.sh'), \
        'the two entrypoints drifted apart, so the app and the agent now drop privileges differently'


def test_both_images_run_through_the_entrypoint_and_keep_their_command():
    app = _read('Dockerfile')
    agent = _read('agent', 'Dockerfile')
    assert 'ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]' in app
    assert 'CMD ["gunicorn", "--config", "/app/gunicorn.conf.py", "app:app"]' in app
    assert 'ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]' in agent
    assert 'CMD ["tma"]' in agent
    for src in (app, agent):
        assert 'su-exec' in src, 'the entrypoint drops privileges with su-exec, which the image must install'
        assert '\nUSER ' not in src, 'a USER line makes every existing install run as non-root on upgrade'


def test_the_build_context_includes_the_entrypoint():
    lines = [ln.strip() for ln in _read('.dockerignore').splitlines()]
    assert 'scripts/' in lines, 'scripts/ is excluded from the build context'
    assert '!scripts/docker-entrypoint.sh' in lines, \
        'scripts/ is excluded from the build context, so the image would have no entrypoint and fail to start'


@pytest.mark.parametrize('env_extra', [{}, {'PUID': '0'}, {'PUID': '0', 'PGID': '0'}],
                         ids=['unset', 'puid-0', 'puid-and-pgid-0'])
def test_without_a_puid_the_command_runs_unchanged(env_extra):
    res = _run(env_extra, 'printf', 'ran as before')
    assert res.returncode == 0, res.stderr
    assert res.stdout == 'ran as before'


@pytest.mark.parametrize('env_extra', [
    {'PUID': 'abc'}, {'PUID': '1000', 'PGID': 'x'}, {'PUID': '-1'}, {'PGID': '10 0'},
], ids=['word', 'bad-pgid', 'negative', 'space'])
def test_a_puid_that_is_not_a_number_is_refused_before_anything_changes(env_extra):
    res = _run(env_extra, 'printf', 'should not run')
    assert res.returncode == 1
    assert 'must be numbers' in res.stderr
    assert res.stdout == ''

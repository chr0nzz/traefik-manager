import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONF = os.path.join(ROOT, 'gunicorn.conf.py')


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


def _load(**env):
    ns = {}
    old = {k: os.environ.get(k) for k in env}
    os.environ.update({k: str(v) for k, v in env.items()})
    try:
        exec(compile(_read('gunicorn.conf.py'), CONF, 'exec'), ns)
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    return ns


def test_the_image_uses_the_config_file():
    docker = _read('Dockerfile')
    cmd = docker.split('CMD')[-1]
    assert '--config", "/app/gunicorn.conf.py' in docker, \
        'flags on the command line beat every environment variable, so nobody could tune them'
    assert '--workers' not in cmd and '--threads' not in cmd
    assert '--preload' not in docker, (
        'preload starts the monitor in the arbiter before fork, so no worker would run it and '
        'the arbiter would hold its lock forever')


def test_requests_are_served_in_parallel():
    conf = _load()
    assert conf['worker_class'] == 'gthread', \
        'the sync worker serves one request per worker, so one slow agent blocks everybody'
    assert conf['workers'] * conf['threads'] >= 8


def test_every_knob_can_be_tuned_without_rebuilding():
    conf = _load(WEB_CONCURRENCY=3, GUNICORN_THREADS=12, GUNICORN_TIMEOUT=45,
                 GUNICORN_KEEPALIVE=9, GUNICORN_WORKER_CONNECTIONS=500)
    assert (conf['workers'], conf['threads'], conf['timeout']) == (3, 12, 45)
    assert (conf['keepalive'], conf['worker_connections']) == (9, 500)


def test_a_bad_value_cannot_stop_the_container_booting():
    conf = _load(GUNICORN_THREADS='banana', WEB_CONCURRENCY='')
    assert conf['threads'] == 4 and conf['workers'] == 2
    huge = _load(WEB_CONCURRENCY=9999, GUNICORN_THREADS=9999)
    assert huge['workers'] <= 16 and huge['threads'] <= 64, \
        'an unbounded value would exhaust memory on a small board'
    assert _load(GUNICORN_TIMEOUT=1)['timeout'] >= 15, \
        'a tiny timeout would have the arbiter kill workers mid-request'


def test_the_worker_timeout_leaves_room_for_a_slow_agent():
    conf = _load()
    assert conf['timeout'] >= 60, (
        'under gthread a worker timeout kills every in-flight thread, so it needs more margin '
        'than the 15 second upstream timeout')
    assert conf['graceful_timeout'] >= 5


def test_the_config_is_shipped_in_the_image():
    assert os.path.isfile(CONF)
    path = os.path.join(ROOT, '.dockerignore')
    ignore = _read('.dockerignore') if os.path.exists(path) else ''
    assert not re.search(r'^gunicorn\.conf\.py$', ignore, re.M), 'the image would boot without it'

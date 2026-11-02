import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


def test_the_docker_docs_show_the_named_volume_shape():
    docs = _read('docs', 'docker.md')
    assert 'Named volumes' in docs, \
        'people read the bind-mount example and assume the paths are fixed'
    assert 'ACME_JSON_PATH: /traefik-certs/acme.json' in docs
    assert 'ACCESS_LOG_PATH: /traefik-logs/access.log' in docs


def test_both_path_variables_document_the_named_volume_case():
    env = _read('docs', 'env-vars.md')
    for marker in ('traefik_certs:/traefik-certs:ro', 'traefik_logs:/traefik-logs:ro'):
        assert marker in env, f'missing {marker}'


def test_the_defaults_the_docs_promise_are_the_real_ones():
    import core.settings as st
    for key in ('ACME_JSON_PATH', 'ACCESS_LOG_PATH'):
        os.environ.pop(key, None)
    assert st._get_acme_json_path() == '/app/acme.json'
    assert st._get_access_log_path() == '/app/logs/access.log'


def test_a_path_outside_app_is_readable(tmp_path):
    import core.config as cfg
    target = str(tmp_path / 'acme.json')
    with open(target, 'w') as fh:
        fh.write('{}')
    os.environ['ACME_JSON_PATH'] = target
    try:
        assert cfg.readable_config_path(target), \
            'a named volume mounted outside /app must pass the read guard'
    finally:
        os.environ.pop('ACME_JSON_PATH', None)

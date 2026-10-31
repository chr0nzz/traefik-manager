import os
import shutil
import subprocess

import pytest

from conftest import post_json

JS = 'static/js/static-config.js'


def _js(app_module):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, JS), encoding='utf-8') as fh:
        return fh.read()


def test_underscore_gate_no_longer_claims_3_6_support(app_module):
    src = _js(app_module)
    body = src.split('function _traefikSupportsUnderscoreStrategy', 1)[1].split('\n}', 1)[0]
    assert 'min === 6' not in body, \
        'no 3.6.x release has underscoreHeadersStrategy - offering it there bricks Traefik'
    assert 'pat >= 6' in body, 'underscoreHeadersStrategy starts at 3.7.6'


def test_alias_gate_starts_at_3_7_12(app_module):
    src = _js(app_module)
    assert 'function _traefikSupportsAliasStrategy' in src
    body = src.split('function _traefikSupportsAliasStrategy', 1)[1].split('\n}', 1)[0]
    assert 'pat >= 12' in body, 'aliasHeadersStrategy starts at 3.7.12'
    assert 'min === 6' not in body


@pytest.mark.parametrize('key', ['aliasHeadersStrategy', 'underscoreHeadersStrategy'])
def test_the_form_writes_the_requested_key(client, config_path, key):
    r = post_json(client, '/api/static/section', {
        'action': 'set', 'section': 'entrypoints', 'name': 'websecure',
        'current_raw': 'entryPoints: {}\n',
        'data': {'address': ':443', 'underscore_headers': 'delete',
                 'headers_strategy_key': key},
    })
    assert r.status_code < 400, r.get_data(as_text=True)


def test_only_one_of_the_two_keys_is_ever_written(client):
    post_json(client, '/api/static/section', {
        'action': 'set', 'section': 'entrypoints', 'name': 'websecure',
        'current_raw': 'entryPoints: {}\n',
        'data': {'address': ':443', 'underscore_headers': 'delete',
                 'headers_strategy_key': 'underscoreHeadersStrategy'},
    })
    r = post_json(client, '/api/static/section', {
        'action': 'set', 'section': 'entrypoints', 'name': 'websecure',
        'current_raw': 'entryPoints:\n  websecure:\n    address: ":443"\n    http:\n      underscoreHeadersStrategy: delete\n',
        'data': {'address': ':443', 'underscore_headers': 'delete',
                 'headers_strategy_key': 'aliasHeadersStrategy'},
    })
    assert r.status_code < 400, r.get_data(as_text=True)
    body = r.get_json().get('raw', '') or r.get_data(as_text=True)
    assert 'aliasHeadersStrategy' in body
    assert 'underscoreHeadersStrategy' not in body, \
        'switching to the new key must remove the old one'


def test_an_unknown_key_falls_back_to_the_safe_old_name(client):
    r = post_json(client, '/api/static/section', {
        'action': 'set', 'section': 'entrypoints', 'name': 'websecure',
        'current_raw': 'entryPoints: {}\n',
        'data': {'address': ':443', 'underscore_headers': 'delete',
                 'headers_strategy_key': 'somethingElse'},
    })
    assert r.status_code < 400, r.get_data(as_text=True)
    body = r.get_json().get('raw', '') or r.get_data(as_text=True)
    assert 'underscoreHeadersStrategy' in body
    assert 'aliasHeadersStrategy' not in body


ENTRY = 'entryPoints:\n  websecure:\n    address: ":443"\n    http:\n%s'


def _save(client, data, http='      sanitizePath: true\n'):
    r = post_json(client, '/api/static/section', {
        'action': 'set', 'section': 'entrypoints', 'name': 'websecure',
        'current_raw': ENTRY % http,
        'data': {'address': ':443', **data},
    })
    assert r.status_code < 400, r.get_data(as_text=True)
    parsed = r.get_json()['parsed']['entryPoints']['websecure'].get('http') or {}
    assert not ('aliasHeadersStrategy' in parsed and 'underscoreHeadersStrategy' in parsed)
    return parsed


@pytest.mark.parametrize('key', ['aliasHeadersStrategy', 'underscoreHeadersStrategy'])
@pytest.mark.parametrize('value', ['keep', 'delete', 'reject'])
def test_a_valid_key_writes_the_chosen_value(client, key, value):
    http = _save(client, {'underscore_headers': value, 'headers_strategy_key': key})
    assert http[key] == value


@pytest.mark.parametrize('key', ['aliasHeadersStrategy', 'underscoreHeadersStrategy'])
@pytest.mark.parametrize('existing', ['aliasHeadersStrategy', 'underscoreHeadersStrategy'])
def test_a_valid_key_with_an_empty_value_removes_both(client, key, existing):
    http = _save(client, {'underscore_headers': '', 'headers_strategy_key': key},
                 '      %s: delete\n      sanitizePath: true\n' % existing)
    assert 'aliasHeadersStrategy' not in http
    assert 'underscoreHeadersStrategy' not in http
    assert http['sanitizePath'] is True


@pytest.mark.parametrize('key', [None, 'somethingElse'])
@pytest.mark.parametrize('existing', ['delete', 'reject', 'keep'])
def test_a_legacy_save_with_no_value_preserves_alias(client, key, existing):
    data = {'underscore_headers': ''}
    if key:
        data['headers_strategy_key'] = key
    http = _save(client, data, '      aliasHeadersStrategy: %s\n' % existing)
    assert http['aliasHeadersStrategy'] == existing


@pytest.mark.parametrize('key', [None, 'somethingElse'])
def test_a_legacy_save_with_a_value_stays_on_alias(client, key):
    data = {'underscore_headers': 'reject'}
    if key:
        data['headers_strategy_key'] = key
    http = _save(client, data, '      aliasHeadersStrategy: delete\n')
    assert http == {'aliasHeadersStrategy': 'reject'}


def test_a_legacy_save_without_alias_uses_the_old_name(client):
    http = _save(client, {'underscore_headers': 'delete'})
    assert http['underscoreHeadersStrategy'] == 'delete'
    assert 'aliasHeadersStrategy' not in http


def test_a_legacy_save_with_both_keys_leaves_only_alias(client):
    http = _save(client, {'underscore_headers': ''},
                 '      aliasHeadersStrategy: delete\n      underscoreHeadersStrategy: reject\n')
    assert http == {'aliasHeadersStrategy': 'delete'}


def test_saving_keeps_the_new_traefik_options(client):
    r = post_json(client, '/api/static/section', {
        'action': 'set', 'section': 'entrypoints', 'name': 'websecure',
        'current_raw': 'global:\n  aliasHeadersStrategy: delete\n' + ENTRY % '      maxHeaderValueCount: 800\n',
        'data': {'address': ':443', 'underscore_headers': '', 'headers_strategy_key': 'aliasHeadersStrategy'},
    })
    assert r.status_code < 400, r.get_data(as_text=True)
    parsed = r.get_json()['parsed']
    assert parsed['global']['aliasHeadersStrategy'] == 'delete'
    assert parsed['entryPoints']['websecure']['http']['maxHeaderValueCount'] == 800


def test_saving_the_system_section_keeps_the_global_strategy(client):
    r = post_json(client, '/api/static/section', {
        'action': 'set', 'section': 'system', 'name': '',
        'current_raw': 'global:\n  aliasHeadersStrategy: delete\n',
        'data': {'check_new_version': True, 'send_usage': False},
    })
    assert r.status_code < 400, r.get_data(as_text=True)
    assert r.get_json()['parsed']['global']['aliasHeadersStrategy'] == 'delete'


def test_the_form_rules_hold():
    node = shutil.which('node')
    if not node:
        pytest.skip('node is not installed, run scripts/test_entrypoint_header_strategy.mjs where it is')
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    proc = subprocess.run([node, os.path.join(root, 'scripts', 'test_entrypoint_header_strategy.mjs')],
                          cwd=root, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, 'the form driver failed:\n%s\n%s' % (proc.stdout, proc.stderr)

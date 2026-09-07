import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _src(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


def _fn(name, src):
    m = re.search(r'async function ' + name + r'\(.*?\n\}', src, re.S)
    assert m, 'the %s helper moved' % name
    return m.group(0)


def test_a_refused_delete_offers_to_remove_the_references():
    body = _fn('_sendMwDelete', _src('static', 'js', 'middlewares.js'))
    assert 'res.status === 409' in body, 'the refusal is not handled'
    assert 'inUseBy' in body, 'the routes using it are not read from the refusal'
    assert '_sendMwDelete(name, configFile, true)' in body, \
        'confirming must retry with force, or the button does nothing'


def test_the_first_delete_never_forces():
    body = _fn('deleteMw', _src('static', 'js', 'middlewares.js'))
    assert '_sendMwDelete(name, configFile, false)' in body, \
        'the first attempt must not force, or the guard is pointless'


def test_the_confirm_names_the_routes():
    body = _fn('_sendMwDelete', _src('static', 'js', 'middlewares.js'))
    assert 'routes.slice(0, 5)' in body, 'the prompt should name the routes it will edit'


def test_the_tls_form_sends_the_original_name():
    src = _src('static', 'js', 'certs.js')
    assert 'originalName' in src, 'a TLS rename cannot cascade without the original name'
    assert "document.getElementById('tlsOptName').readOnly     = false;" in src, \
        'the name field must be editable, or a rename is impossible'


def test_removing_a_plugin_in_use_is_refused_in_the_ui():
    body = _fn('deletePlugin', _src('static', 'js', 'middlewares.js'))
    assert '_pluginMwsUsing(name)' in body, \
        'the tab already knows which middlewares use a plugin; it must check before removing'
    assert 'Delete those middlewares first' in body, \
        'the refusal should say what to do next'

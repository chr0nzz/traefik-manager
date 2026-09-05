import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


def test_the_login_page_shows_flashed_errors():
    assert 'get_flashed_messages' in _read('templates', 'login.html'), (
        'every OIDC failure calls flash(); without this the page reloads with no reason shown')


def test_every_oidc_callback_failure_is_logged():
    src = _read('app.py')
    body = src[src.index('def oidc_callback'):]
    body = body[:body.index('\n@app.route')]
    blocks = re.split(r'\n    (?=if |elif )', body)
    silent = []
    for block in blocks:
        if "redirect(url_for('login'))" not in block:
            continue
        if 'logger.' in block:
            continue
        if "not s.get('oidc_enabled')" in block:
            continue
        silent.append(block.strip().splitlines()[0])
    assert not silent, (
        'these fail the login with nothing in the log, so an operator cannot diagnose it: %s'
        % silent)

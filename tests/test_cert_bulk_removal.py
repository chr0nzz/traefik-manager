import os
import shutil
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRIVER = os.path.join(ROOT, 'scripts', 'test_cert_bulk_removal.mjs')


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


def test_the_bulk_driver_ships_with_the_repo():
    assert os.path.isfile(DRIVER), (
        'scripts/test_cert_bulk_removal.mjs is the only executable coverage for removing '
        'several certificates at once, including the restart screen it has to show')


def test_bulk_removal_behaves():
    node = shutil.which('node')
    if not node:
        pytest.skip('node is not installed, run scripts/test_cert_bulk_removal.mjs where it is')
    proc = subprocess.run([node, DRIVER], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, (
        'the bulk certificate removal driver failed:\n%s\n%s' % (proc.stdout, proc.stderr))


def test_the_certs_tab_selects_like_the_routes_tab():
    certs  = _read('templates', 'tabs', 'tab_certs.html')
    routes = _read('templates', 'tabs', 'tab_services.html')
    for html in (certs, routes):
        assert 'ph-bold ph-selection' in html, \
            'both tabs use the same selection icon, and neither labels the button'
    assert '> Select<' not in certs and 'ph-check-square' not in certs, \
        'the routes toolbar button carries an icon only, the certs one invented a text label'
    assert 'title="Bulk select"' in certs
    assert 'title="Exit bulk mode"' in certs, 'the routes bar can be dismissed, this one has to be too'
    for html in (certs, routes):
        bar = html[html.index('BulkBar"' if 'certBulkBar"' in html else 'bulkBar"'):][:200]
        assert 'margin-bottom:16px' in bar, \
            'without a gap the sticky bar sits flush against the first row of cards'


def test_the_restart_screen_can_hand_back_instead_of_reloading():
    js = _read('static', 'js', 'static-config.js')
    body = js[js.index('async function _waitForReconnect('):js.index('async function triggerTraefikRestart(')]
    assert 'onBack = null' in body and "typeof onBack === 'function'" in body, \
        'a tab that only needs its own data back should not have the whole page reloaded under it'
    assert 'location.reload()' in body, 'the static config editor still needs the full reload'
    certs = _read('static', 'js', 'certs.js')
    send = certs[certs.index('async function _sendCertRemoval('):certs.index('async function _loadCertUsage(')]
    assert '_waitForReconnect(false, back)' in send
    assert 'refreshCertsTab()' in send, 'the tab still shows the certificate that was just removed otherwise'
    assert 'location.reload' not in send


def test_the_delete_dialog_opens_without_waiting_for_the_certificate_lookup():
    js = _read('static', 'js', 'routes.js')
    for fn, nxt in (('async function deleteRoute(', 'const answer = await _confirmWith({'),
                    ('async function bulkDelete()', 'const answer  = await _confirmWith({')):
        body = js[js.index(fn):]
        body = body[:body.index(nxt)]
        assert 'await _routeCertOption' not in body, (
            '%s blocked on three API calls before the dialog appeared, which on a host with many '
            'certificates is seconds of nothing happening' % fn)
    assert js.count('checkboxAsync:') == 2, 'both delete paths offer the certificate the same way'
    certs = _read('static', 'js', 'certs.js')
    body = certs[certs.index('async function _certsForRoutes('):certs.index('async function removeCerts(')]
    assert body.index('_loadCertManage()') < body.index('_loadCertUsage()'), \
        'a read-only mount should cost one call, not three'


def test_the_confirmation_reads_as_a_dialog_not_a_wall_of_capitals():
    html = _read('templates', 'index.html')
    box  = html[html.index('<div id="customConfirmOverlay"'):html.index('id="customConfirmOk"')]
    assert 'class="confirm-opt"' in box, \
        'the option sat in a bare label, which the global label rule renders in shouting capitals'
    assert 'id="customConfirmIcon"' in box, 'a destructive dialog says so before the text does'
    css = _read('static', 'css', 'app.css')
    opt = css[css.index('.confirm-opt {'):css.index('.confirm-opt:hover')]
    assert 'text-transform: none' in opt and 'letter-spacing: 0' in opt
    assert 'border' in opt and 'border-radius' in opt, \
        'the option needs to read as a control, not as another paragraph of the message'
    js = _read('static', 'js', 'static-config.js')
    body = js[js.index('function _confirmWith('):js.index('function _monacoThemeName(')]
    assert "icon.style.display = danger ? '' : 'none'" in body
    assert 'checkboxAsync' in body and 'showCheck' in body
    assert "checkWrap.style.display !== 'none'" in body, \
        'a checkbox that never appeared must not come back checked from a previous dialog'

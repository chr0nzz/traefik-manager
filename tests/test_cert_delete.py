import json
import os
import re
import stat

import pytest

from core import acme_store

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HDR  = {'X-CSRF-Token': 'testtoken', 'X-Requested-With': 'fetch'}

STORE = {
    'letsencrypt': {
        'Account': {'Email': 'a@b.c', 'PrivateKey': 'KEYDATA', 'KeyType': '4096',
                    'Registration': {'body': {'status': 'valid'}, 'uri': 'https://acme/1'}},
        'Certificates': [
            {'domain': {'main': 'keep.example.com', 'sans': []}, 'certificate': 'C1', 'key': 'K1', 'Store': 'default'},
            {'domain': {'main': 'drop.example.com', 'sans': ['x.example.com']}, 'certificate': 'C2', 'key': 'K2', 'Store': 'default'},
        ],
    },
    'gone': {'Account': {'Email': 'a@b.c'},
             'Certificates': [{'domain': {'main': 'old.example.com'}, 'certificate': 'C3', 'key': 'K3'}]},
}


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


@pytest.fixture
def store(tmp_path, monkeypatch):
    from core import env as env_mod
    path = tmp_path / 'acme.json'
    path.write_text(json.dumps(STORE))
    path.chmod(0o600)
    monkeypatch.setattr(env_mod, 'BACKUP_DIR', str(tmp_path / 'backups'))
    env_mod.register_read_path(str(path))
    return path


def test_only_what_was_asked_for_is_removed(store):
    removed, backup = acme_store.remove(str(store), [('letsencrypt', 'drop.example.com')])
    assert removed == 1 and backup
    after = json.loads(store.read_text())
    assert [c['domain']['main'] for c in after['letsencrypt']['Certificates']] == ['keep.example.com']
    assert [c['domain']['main'] for c in after['gone']['Certificates']] == ['old.example.com']


def test_the_acme_account_is_never_touched(store):
    acme_store.remove(str(store), [('letsencrypt', 'drop.example.com')])
    after = json.loads(store.read_text())
    assert after['letsencrypt']['Account'] == STORE['letsencrypt']['Account'], \
        'losing the account key forces a new ACME registration'


def test_fields_traefik_wrote_are_kept(store):
    acme_store.remove(str(store), [('letsencrypt', 'drop.example.com')])
    kept = json.loads(store.read_text())['letsencrypt']['Certificates'][0]
    assert kept['Store'] == 'default', 'Store is written by Traefik and must round-trip'
    assert kept['certificate'] == 'C1' and kept['key'] == 'K1'


def test_the_file_keeps_its_inode(store):
    before = os.stat(str(store)).st_ino
    acme_store.remove(str(store), [('letsencrypt', 'drop.example.com')])
    assert os.stat(str(store)).st_ino == before, \
        'replacing the file detaches a bind mount and Traefik then writes into a lost inode'


def test_the_store_stays_unreadable_to_others(store):
    acme_store.remove(str(store), [('letsencrypt', 'drop.example.com')])
    mode = stat.S_IMODE(os.stat(str(store)).st_mode)
    assert mode & 0o077 == 0, 'Traefik skips the whole resolver when acme.json is group or world readable'


def test_a_loose_mode_is_tightened_rather_than_preserved(store):
    store.chmod(0o644)
    acme_store.remove(str(store), [('letsencrypt', 'drop.example.com')])
    assert stat.S_IMODE(os.stat(str(store)).st_mode) & 0o077 == 0


def test_the_backup_does_not_leak_private_keys(store):
    _removed, backup = acme_store.remove(str(store), [('letsencrypt', 'drop.example.com')])
    assert stat.S_IMODE(os.stat(backup).st_mode) & 0o077 == 0, \
        'a backup of acme.json is a copy of every private key'
    assert json.loads(open(backup).read()) == STORE, 'the backup must be the file as it was'


def test_nothing_is_written_when_nothing_matches(store):
    before = store.read_text()
    removed, backup = acme_store.remove(str(store), [('letsencrypt', 'not-there.example.com')])
    assert removed == 0 and backup is None
    assert store.read_text() == before


def test_a_broken_store_is_refused_rather_than_rewritten(tmp_path, monkeypatch):
    from core import env as env_mod
    monkeypatch.setattr(env_mod, 'BACKUP_DIR', str(tmp_path / 'backups'))
    path = tmp_path / 'acme.json'
    path.write_text('{not json')
    with pytest.raises(acme_store.AcmeStoreError):
        acme_store.remove(str(path), [('letsencrypt', 'a.com')])
    assert path.read_text() == '{not json', 'a store we cannot parse must be left alone'


def test_an_empty_store_is_not_an_error(tmp_path):
    path = tmp_path / 'acme.json'
    path.write_text('')
    assert acme_store.load(str(path)) == {}


def test_writable_tells_a_read_only_mount_apart(store, monkeypatch):
    assert acme_store.writable(str(store)) is True
    monkeypatch.setattr(os, 'access', lambda *a, **k: False)
    assert acme_store.writable(str(store)) is False
    assert acme_store.writable(str(store.parent / 'missing.json')) is False


def test_deleting_needs_the_setting_switched_on(client, store, monkeypatch):
    from core import settings as settings_mod
    monkeypatch.setattr(settings_mod, 'get_acme_json_paths', lambda: [str(store)])
    res = client.post('/api/certs/delete', json={'certs': [{'resolver': 'gone', 'main': 'old.example.com'}]}, headers=HDR)
    assert res.status_code == 403
    assert 'Settings' in res.get_json()['error']


def test_deleting_needs_something_selected(client):
    res = client.post('/api/certs/delete', json={'certs': []}, headers=HDR)
    assert res.status_code == 400


def test_an_unknown_server_is_refused(client):
    res = client.get('/api/certs/manage?server=nope')
    assert res.status_code == 404


def test_the_gate_explains_what_is_missing(client, store, monkeypatch):
    from core import settings as settings_mod
    monkeypatch.setattr(settings_mod, 'get_acme_json_paths', lambda: [str(store)])
    monkeypatch.setenv('RESTART_METHOD', '')
    body = client.get('/api/certs/manage').get_json()
    assert body['available'] is False
    assert 'restart' in body['reason'], 'without a restart the edit silently reverts'


def test_the_settings_row_hides_itself_until_it_can_be_used():
    html = _read('templates', 'modals', 'settings_modal.html')
    assert 'id="certDeleteRow" style="display:none"' in html, \
        'it must stay hidden like the static config row until the mount allows it'
    js = _read('static', 'js', 'settings-modal.js')
    assert '_refreshCertDeleteRow' in js and "'/api/certs/manage'" in js
    assert "row.style.display = state.available ? '' : 'none'" in js


def test_the_delete_button_waits_for_both_gates():
    js = _read('static', 'js', 'certs.js')
    assert 'function _certCanDelete()' in js
    assert '_certManage.available && _certManage.enabled' in js, \
        'a writable mount alone must not expose a destructive button'
    assert "resolver === 'file'" in js, 'a file certificate is not in acme.json'


def test_the_confirm_panel_reuses_the_existing_styling():
    html = _read('templates', 'modals', 'cert_delete_modal.html')
    assert 'class="detail-backdrop"' in html and 'detail-panel detail-panel-form' in html
    assert 'detail-panel-foot' in html
    assert 'btn-secondary' in html and 'btn-primary' in html
    assert 'class="btn-primary btn-red"' in html, \
        'a solid red fill is louder than anything else in the app, use the tinted variant'
    assert 'style="background:var(--red)' not in html, 'colour belongs in the stylesheet'
    assert 'restarted' in html.lower(), 'the restart is the part people need warning about'
    js = _read('static', 'js', 'certs.js')
    opener = js[js.index('function openCertDeleteModal('):js.index('function closeCertDeleteModal(')]
    assert 'setDetailDockOpen(true)' in opener, \
        'without docking the panel floats over the page in Fluid mode instead of shifting it'
    closer = js[js.index('function closeCertDeleteModal('):js.index('async function confirmCertDelete(')]
    assert 'setDetailDockOpen(false)' in closer and "document.body.style.overflow = ''" in closer
    assert '5 identical certificates per week' in html, 'deleting can burn the rate limit'
    idx = _read('templates', 'index.html')
    assert "modals/cert_delete_modal.html" in idx


def test_a_certificate_backup_can_be_found_and_restored(client, store, monkeypatch):
    import app as app_mod
    from core import env as env_mod
    from core import settings as settings_mod
    monkeypatch.setattr(settings_mod, 'get_acme_json_paths', lambda: [str(store)])
    monkeypatch.setattr(env_mod, 'BACKUP_DIR', app_mod.BACKUP_DIR)
    _removed, backup = acme_store.remove(str(store), [('letsencrypt', 'drop.example.com')])
    name = os.path.basename(backup)

    listed = {b['name']: b['kind'] for b in client.get('/api/backups').get_json()}
    assert listed.get(name) == 'certs', \
        'a certificate backup listed as a route backup sends people to the wrong restore button'

    res = client.post('/api/restore/' + name, headers=HDR)
    assert res.status_code == 200, res.get_json()
    after = json.loads(store.read_text())
    assert [c['domain']['main'] for c in after['letsencrypt']['Certificates']] == \
        ['keep.example.com', 'drop.example.com'], 'restoring must bring the removed certificate back'
    assert stat.S_IMODE(os.stat(str(store)).st_mode) & 0o077 == 0


def test_a_restart_shows_the_waiting_screen_not_a_toast():
    js = _read('static', 'js', 'certs.js')
    body = js[js.index('async function confirmCertDelete('):js.index('async function _loadCertUsage(')]
    assert '_showRestartOverlay()' in body and '_waitForReconnect(' in body, (
        'Traefik Manager sits behind Traefik, so restarting it takes the interface down. '
        'A toast leaves the user looking at a dead page')
    settings = _read('static', 'js', 'settings-modal.js')
    restore = settings[settings.index('async function restoreBackup('):settings.index('async function deleteBackup(')]
    assert '_showRestartOverlay()' in restore, 'restoring a certificate store restarts Traefik too'
    assert 'data.restarted' in restore, 'a config restore does not restart anything, keep its toast'


def test_restoring_a_certificate_store_restarts_traefik():
    src = _read('app.py')
    body = src[src.index('def api_restore(filename):'):src.index('@app.route(\'/api/backup/create\'')]
    assert 'trigger_traefik_restart()' in body, \
        'Traefik reads acme.json once at startup, so a restore without a restart is undone'
    assert '_acme.write_bytes_in_place' in body, \
        'copying over a bind mounted acme.json detaches it from Traefik'
    assert '_host_cert_manage_state()' in body, 'a read only mount must refuse rather than half work'


def test_a_json_backup_is_accepted_by_the_validator():
    src = _read('app.py')
    line = [ln for ln in src.splitlines() if ln.startswith('_BACKUP_RE')][0]
    assert 'json' in line, 'acme.json backups were listed but could never be restored'
    assert 'yml' in line and 'yaml' in line, 'config backups must still restore'


def test_the_backups_pane_has_somewhere_to_show_them():
    html = _read('templates', 'modals', 'settings_modal.html')
    assert 'id="backup-tab-certs"' in html and 'id="sm-cert-backups-list"' in html
    js = _read('static', 'js', 'settings-modal.js')
    assert "b.kind === 'certs'" in js
    assert "certTab.style.display = certs.length ? '' : 'none'" in js, \
        'an empty tab on every install would be noise'


def test_the_docs_say_how_to_turn_it_on():
    doc = _read('docs', 'tab-certs.md')
    section = doc[doc.index('## Removing a certificate'):doc.index('## Enabling the tab')]
    assert 'RESTART_METHOD=proxy' in section and 'RESTART_METHOD=poison-pill' in section, \
        'pointing at another page is not instructions, the steps have to be runnable from here'
    assert ':::tabs' in section, 'every other mount in these docs shows Docker and Linux side by side'
    assert 'tecnativa/docker-socket-proxy' in section, \
        'naming the proxy method without the sidecar leaves people with nothing to run'
    assert 'CONTAINERS: 1' in section and 'internal: true' in section
    assert 'Already using the Static Config editor' in section, \
        'most people already have a restart method and only need the mount change'
    assert re.search(r'- \S*acme\.json:/app/acme\.json:rw', section), \
        'say :rw rather than dropping :ro, so the change reads as deliberate'
    assert ':rw,z' in section, 'Podman needs the SELinux flag kept alongside the mode'
    assert 'Settings - Interface - Tabs' in section
    for step in ('### 1.', '### 2.', '### 3.'):
        assert step in section, f'{step} missing, the three gates need to be three steps'


def test_the_agent_can_be_asked_and_told():
    go = _read('agent', 'handlers.go')
    assert 'func (a *App) certsStatusHandler(' in go and 'func (a *App) certsDeleteHandler(' in go
    assert 'func acmeWriteInPlace(' in go
    write = go[go.index('func acmeWriteInPlace('):]
    assert 'os.Rename' not in write, 'renaming detaches a bind mount and loses certificates'
    assert 'Truncate' in write and 'Sync()' in write and '0o600' in write
    main = _read('agent', 'main.go')
    assert '/api/traefik/certs/status' in main and '/api/traefik/certs/delete' in main


def test_the_agent_refuses_without_a_restart_method():
    go = _read('agent', 'handlers.go')
    body = go[go.index('func (a *App) certsDeleteHandler('):go.index('func acmeRemove(')]
    assert 'RESTART_METHOD' in body and 'StatusForbidden' in body
    assert 'acmeWritable(path)' in body, 'a read only mount must be refused, not attempted'


def test_the_host_writer_never_renames():
    src = _read('core', 'acme_store.py')
    body = src[src.index('def write_in_place('):src.index('def remove(')]
    assert 'os.replace' not in body and 'shutil' not in body, \
        'renaming over a bind mounted acme.json silently detaches it from Traefik'
    assert 'ftruncate' in body and 'fsync' in body

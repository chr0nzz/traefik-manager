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


def test_deleting_needs_a_restart_method(client, store, monkeypatch):
    from core import settings as settings_mod
    monkeypatch.setattr(settings_mod, 'get_acme_json_paths', lambda: [str(store)])
    monkeypatch.setenv('RESTART_METHOD', '')
    res = client.post('/api/certs/delete', json={'certs': [{'resolver': 'gone', 'main': 'old.example.com'}]}, headers=HDR)
    assert res.status_code == 403
    assert 'restart' in res.get_json()['error'], \
        'without a restart Traefik keeps serving the certificate we just deleted'


def test_nothing_asks_the_user_to_switch_removal_on(client):
    assert client.post('/api/settings/cert-delete', json={'enabled': True}, headers=HDR).status_code == 404, \
        'the opt-in was removed, a read-write mount and a restart method are the whole gate'
    for parts in (('core', 'settings.py'), ('app.py',), ('static', 'js', 'certs.js'),
                  ('static', 'js', 'settings-modal.js'), ('templates', 'modals', 'settings_modal.html')):
        assert 'cert_delete_enabled' not in _read(*parts), '/'.join(parts)


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


def test_the_delete_button_follows_the_mount():
    js = _read('static', 'js', 'certs.js')
    assert 'function _certCanDelete()' in js
    assert '_certManage.available' in js, \
        'a read-only mount must not expose a destructive button'
    assert "resolver === 'file'" in js, 'a file certificate is not in acme.json'


def test_removal_uses_the_same_confirm_as_every_other_delete():
    js = _read('static', 'js', 'certs.js')
    body = js[js.index('async function removeCerts('):js.index('async function _loadCertUsage(')]
    assert "_confirmWith(" in body, 'a bespoke panel meant one confirm style for certificates and another everywhere else'
    assert "typeWord: 'DELETE'" in body, (
        'removing a certificate can trigger a reissue and spend a rate limit, so it needs at least '
        'the friction of deleting a route')
    assert 'notes' in body and 'restarted afterwards' in body, 'the warnings have to survive the move'
    assert "Let's Encrypt allows five identical certificates per week" in body
    assert not os.path.exists(os.path.join(ROOT, 'templates', 'modals', 'cert_delete_modal.html')), \
        'the panel was replaced, it should not linger'
    idx = _read('templates', 'index.html')
    assert 'cert_delete_modal' not in idx


def test_the_rate_limit_warning_only_appears_when_it_applies():
    js = _read('static', 'js', 'certs.js')
    body = js[js.index('async function removeCerts('):js.index('async function _loadCertUsage(')]
    assert 'if (inUse)' in body, \
        'warning about reissue when every selected certificate is already dead is noise'


def test_the_shared_confirm_gained_notes_a_checkbox_and_a_red_button():
    js = _read('static', 'js', 'static-config.js')
    body = js[js.index('function _confirmWith(o)'):js.index('let _staticParsedData')]
    assert "ok.classList.toggle('btn-red'" in body, 'a destructive confirm should not look like a save'
    assert 'customConfirmNotes' in body and 'customConfirmCheck' in body
    assert "resolve({ ok:" in body, 'the checkbox answer has to come back to the caller'
    old_api = js[js.index('function _confirm(message'):js.index('function _confirmWith(o)')]
    assert '.then(r => r.ok)' in old_api, \
        'every existing caller expects a boolean, changing that would break them all'
    html = _read('templates', 'index.html')
    for el in ('customConfirmNotes', 'customConfirmCheckWrap', 'customConfirmCheck', 'customConfirmCheckLabel'):
        assert f'id="{el}"' in html, f'{el} missing from the dialog'


def test_a_bulk_route_delete_names_the_routes():
    js = _read('static', 'js', 'routes.js')
    body = js[js.index('async function bulkDelete()'):js.index('async function bulkToggle(')] \
        if 'async function bulkToggle(' in js else js[js.index('async function bulkDelete()'):][:1200]
    assert '_routeNameList(ids)' in body, \
        'telling someone they are deleting "2 routes" does not let them check it is the right two'


def test_a_restart_shows_the_waiting_screen_not_a_toast():
    js = _read('static', 'js', 'certs.js')
    body = js[js.index('async function removeCerts('):js.index('async function _loadCertUsage(')]
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
    for step in ('### 1.', '### 2.'):
        assert step in section, f'{step} missing, the two gates need to be two steps'
    assert '### 3.' not in section, 'there is no third gate, removal works once the mount and restart are set'
    assert 'Settings - Interface - Tabs' not in section, 'nothing has to be switched on'


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

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
    env_mod.set_settings_paths('acme', str(path))
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
    assert "typeWord: _confirmWordFor(names)" in body, (
        'removing a certificate can trigger a reissue and spend a rate limit, so it needs at least '
        'the friction of deleting a route')
    assert "typeWord: _confirmWordFor(shown)" in _read('static', 'js', 'routes.js'), \
        'a route delete and a certificate removal ask for the same typed confirmation'
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


def _renew(store, extra_main):
    data = json.loads(store.read_text())
    data['letsencrypt']['Certificates'].append(
        {'domain': {'main': extra_main}, 'certificate': 'CR', 'key': 'KR', 'Store': 'default'})
    store.write_text(json.dumps(data))


def _bak_files(tmp_path):
    folder = tmp_path / 'backups'
    return sorted(f for f in os.listdir(folder) if f.endswith('.bak')) if folder.exists() else []


def test_a_store_that_changes_before_the_write_is_planned_again(store, monkeypatch):
    real_plan = acme_store.plan
    calls = []

    def renewing(path, wanted, raw):
        result = real_plan(path, wanted, raw)
        if not calls:
            _renew(store, 'renewed.example.com')
        calls.append(1)
        return result

    monkeypatch.setattr(acme_store, 'plan', renewing)
    removed, _backup = acme_store.remove(str(store), [('letsencrypt', 'drop.example.com')])
    assert removed == 1 and len(calls) == 2
    mains = [c['domain']['main'] for c in json.loads(store.read_text())['letsencrypt']['Certificates']]
    assert mains == ['keep.example.com', 'renewed.example.com'], \
        'writing the stale copy would have thrown away the certificate Traefik just renewed'


def test_a_store_that_keeps_changing_is_left_alone(store, tmp_path, monkeypatch):
    real_plan = acme_store.plan
    seen = []

    def always_renewing(path, wanted, raw):
        result = real_plan(path, wanted, raw)
        seen.append(1)
        _renew(store, 'renewed-%d.example.com' % len(seen))
        return result

    monkeypatch.setattr(acme_store, 'plan', always_renewing)
    with pytest.raises(acme_store.AcmeStoreChanged) as err:
        acme_store.remove(str(store), [('letsencrypt', 'drop.example.com')])
    assert err.value.status == 409
    mains = [c['domain']['main'] for c in json.loads(store.read_text())['letsencrypt']['Certificates']]
    assert 'drop.example.com' in mains and 'renewed-%d.example.com' % acme_store.ATTEMPTS in mains
    assert _bak_files(tmp_path) == [], 'nothing was written, so nothing should have been backed up'


def test_two_removals_at_the_same_time_both_land(store):
    import threading
    errors = []

    def run(resolver, domain):
        try:
            acme_store.remove(str(store), [(resolver, domain)])
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=run, args=a)
               for a in (('letsencrypt', 'drop.example.com'), ('gone', 'old.example.com'))]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)
    assert not errors, errors
    after = json.loads(store.read_text())
    assert [c['domain']['main'] for c in after['letsencrypt']['Certificates']] == ['keep.example.com']
    assert after['gone']['Certificates'] == [], 'one removal overwrote the other'


def test_the_backup_holds_the_bytes_that_were_edited(store):
    before = store.read_bytes()
    _removed, backup = acme_store.remove(str(store), [('letsencrypt', 'drop.example.com')])
    with open(backup, 'rb') as fh:
        assert fh.read() == before


def test_backups_taken_in_the_same_second_are_both_kept(store, monkeypatch):
    stamps = iter(['20260914_101010', '20260914_101010', '20260914_101011'])
    monkeypatch.setattr(acme_store, '_stamp', lambda: next(stamps))
    monkeypatch.setattr(acme_store, '_wait_for_next_second', lambda: None)
    first = acme_store.backup(str(store))
    second = acme_store.backup(str(store))
    assert first != second and os.path.exists(first) and os.path.exists(second), \
        'the second backup truncated the first'


def test_a_short_write_is_finished(store, monkeypatch):
    real_write = os.write
    monkeypatch.setattr(acme_store.os, 'write', lambda fd, data: real_write(fd, bytes(data[:7])))
    acme_store.remove(str(store), [('letsencrypt', 'drop.example.com')])
    after = json.loads(store.read_text())
    assert [c['domain']['main'] for c in after['letsencrypt']['Certificates']] == ['keep.example.com']


def test_a_write_cut_off_before_the_truncate_still_parses(store, monkeypatch):
    body = json.dumps({'letsencrypt': {'Certificates': []}}).encode()

    def fail(fd, size):
        raise OSError('disk went away')

    monkeypatch.setattr(acme_store.os, 'ftruncate', fail)
    with pytest.raises(OSError):
        acme_store.write_bytes_in_place(str(store), body)
    assert json.loads(store.read_text()) == json.loads(body), \
        'padding with spaces keeps the file valid JSON if the process stops between write and truncate'


def test_a_failed_write_puts_the_store_back(store, monkeypatch):
    before = store.read_bytes()
    real = os.ftruncate
    calls = []

    def fail_once(fd, size):
        calls.append(size)
        if len(calls) == 1:
            raise OSError('disk went away')
        return real(fd, size)

    monkeypatch.setattr(acme_store.os, 'ftruncate', fail_once)
    with pytest.raises(OSError):
        acme_store.remove(str(store), [('letsencrypt', 'drop.example.com')])
    assert store.read_bytes() == before


def test_the_lock_file_stays_out_of_the_certificate_directory(store):
    acme_store.remove(str(store), [('letsencrypt', 'drop.example.com')])
    assert sorted(os.listdir(store.parent)) == ['acme.json', 'backups'], \
        'the certificate directory may be read only, and Traefik owns it'


def test_a_broken_second_store_leaves_the_first_untouched(store, tmp_path):
    bad = tmp_path / 'broken.json'
    bad.write_text('{not json')
    bad.chmod(0o600)
    before = store.read_bytes()
    with pytest.raises(acme_store.AcmeStoreError):
        acme_store.remove_many([str(store), str(bad)], [('letsencrypt', 'drop.example.com')])
    assert store.read_bytes() == before
    assert _bak_files(tmp_path) == []


def test_a_read_only_second_store_leaves_the_first_untouched(store, tmp_path, monkeypatch):
    other = tmp_path / 'other.json'
    other.write_text(json.dumps(STORE))
    other.chmod(0o600)
    real = acme_store.writable
    monkeypatch.setattr(acme_store, 'writable', lambda p: False if p == str(other) else real(p))
    before = store.read_bytes()
    with pytest.raises(acme_store.AcmeStoreReadOnly) as err:
        acme_store.remove_many([str(store), str(other)], [('letsencrypt', 'drop.example.com')])
    assert err.value.status == 403
    assert store.read_bytes() == before


def test_a_failure_after_the_first_store_is_reported_as_partial(store, tmp_path, monkeypatch):
    other = tmp_path / 'other.json'
    other.write_text(json.dumps(STORE))
    other.chmod(0o600)
    real_commit = acme_store.commit

    def failing(path, raw, body, key=None):
        if path == str(other):
            raise OSError('disk full')
        return real_commit(path, raw, body, key)

    monkeypatch.setattr(acme_store, 'commit', failing)
    with pytest.raises(acme_store.AcmeStorePartial) as err:
        acme_store.remove_many([str(store), str(other)], [('letsencrypt', 'drop.example.com')])
    assert err.value.removed == 1
    assert 'drop.example.com' not in store.read_text()


def _removal_available(monkeypatch, store):
    import app as app_mod
    monkeypatch.setattr(app_mod, '_host_cert_manage_state',
                        lambda: {'available': True, 'reason': '', 'paths': [str(store)]})
    restarts = []
    monkeypatch.setattr(app_mod, 'trigger_traefik_restart', lambda: restarts.append(1) or (True, ''))
    return app_mod, restarts


def test_a_store_traefik_changed_answers_conflict_without_a_restart(client, store, monkeypatch):
    app_mod, restarts = _removal_available(monkeypatch, store)

    def changed(paths, wanted):
        raise acme_store.AcmeStoreChanged('acme.json changed while it was being edited')

    monkeypatch.setattr(app_mod._acme, 'remove_many', changed)
    res = client.post('/api/certs/delete',
                      json={'certs': [{'resolver': 'letsencrypt', 'main': 'drop.example.com'}]}, headers=HDR)
    assert res.status_code == 409 and not restarts


def test_a_partial_removal_still_restarts_traefik(client, store, monkeypatch):
    app_mod, restarts = _removal_available(monkeypatch, store)

    def partial(paths, wanted):
        raise acme_store.AcmeStorePartial('stopped partway', 2, '/b/acme.json.20260914_101010.bak')

    monkeypatch.setattr(app_mod._acme, 'remove_many', partial)
    res = client.post('/api/certs/delete',
                      json={'certs': [{'resolver': 'letsencrypt', 'main': 'drop.example.com'}]}, headers=HDR)
    body = res.get_json()
    assert res.status_code == 500 and body['partial'] is True and body['removed'] == 2
    assert restarts and body['restarted'] is True, \
        'Traefik has to reload what is on disk, or it writes the removed certificates back'


def test_removal_and_restore_hold_the_store_lock():
    src = _read('app.py')
    delete = src[src.index('def api_certs_delete():'):src.index("@app.route('/api/traefik/certs')")]
    assert '_acme.remove_many(' in delete
    restore = src[src.index('def api_restore(filename):'):src.index("@app.route('/api/backup/create'")]
    assert 'with _acme.store_lock():' in restore
    store = _read('core', 'acme_store.py')
    body = store[store.index('def remove_many('):]
    assert 'with store_lock():' in body


def test_a_partial_removal_keeps_the_restart_screen_up():
    js = _read('static', 'js', 'certs.js')
    body = js[js.index('async function _sendCertRemoval('):js.index('async function _loadCertUsage(')]
    assert 'body.partial && body.restarted' in body, \
        'Traefik restarts after a partial removal, so the page is about to go away'


KEY_VECTORS = [
    (['/a/acme.json'], ['acme.json']),
    (['/le/a/acme.json', '/le/b/acme.json'], ['a-acme.json', 'b-acme.json']),
    (['/srv/ovh.json', '/srv/lan.json'], ['ovh.json', 'lan.json']),
    (['/one/le@prod/acme.json', '/two/acme.json'], ['le-prod-acme.json', 'two-acme.json']),
    (['acme.json', '/x/acme.json'], ['store-acme.json', 'x-acme.json']),
]


def test_backup_keys_follow_the_same_rules_as_the_agent():
    import hashlib
    for paths, keys in KEY_VECTORS:
        assert [acme_store.backup_key(p, paths) for p in paths] == keys, paths
    paths = ['/x/certs/acme.json', '/y/certs/acme.json']
    assert [acme_store.backup_key(p, paths) for p in paths] == \
        [hashlib.sha256(p.encode()).hexdigest()[:8] + '-acme.json' for p in paths]
    agent = _read('agent', 'certs_restore_test.go')
    for paths, keys in KEY_VECTORS:
        for key in keys:
            assert '"%s"' % key in agent, 'the agent test table must carry the same vectors: ' + key


def _pair_of_stores(tmp_path):
    first = tmp_path / 'a' / 'acme.json'
    second = tmp_path / 'b' / 'acme.json'
    for p in (first, second):
        p.parent.mkdir()
        p.write_text(json.dumps(STORE))
        p.chmod(0o600)
    return first, second


def test_two_stores_with_the_same_name_back_up_to_different_files(tmp_path, monkeypatch):
    from core import env as env_mod
    monkeypatch.setattr(env_mod, 'BACKUP_DIR', str(tmp_path / 'backups'))
    first, second = _pair_of_stores(tmp_path)
    removed, _ = acme_store.remove_many([str(first), str(second)], [('letsencrypt', 'drop.example.com')])
    assert removed == 2
    names = sorted(f for f in os.listdir(tmp_path / 'backups') if f.endswith('.bak'))
    assert [n.rsplit('.', 2)[0] for n in names] == ['a-acme.json', 'b-acme.json'], \
        'both backups were named acme.json, so there was no way to tell which store each came from'


def _restore_setup(client, tmp_path, monkeypatch):
    import app as app_mod
    first, second = _pair_of_stores(tmp_path)
    stores = [str(first), str(second)]
    monkeypatch.setattr(app_mod, '_host_cert_manage_state', lambda: {
        'available': True, 'writable': True, 'restart_method': 'poison-pill', 'reason': '', 'paths': stores})
    restarts = []
    monkeypatch.setattr(app_mod, 'trigger_traefik_restart', lambda: restarts.append(1) or (True, ''))
    return app_mod, first, second, restarts


def _drop_backups(pattern):
    from core import env as env_mod
    for f in os.listdir(env_mod.BACKUP_DIR):
        if pattern in f:
            os.remove(os.path.join(env_mod.BACKUP_DIR, f))


def test_a_certificate_backup_restores_into_the_store_it_came_from(client, tmp_path, monkeypatch):
    from core import env as env_mod
    app_mod, first, second, restarts = _restore_setup(client, tmp_path, monkeypatch)
    saved = {'letsencrypt': {'Certificates': [{'domain': {'main': 'restored.example.com'}}]}}
    name = 'b-acme.json.20260914_101010.bak'
    os.makedirs(env_mod.BACKUP_DIR, exist_ok=True)
    with open(os.path.join(env_mod.BACKUP_DIR, name), 'w') as fh:
        json.dump(saved, fh)
    try:
        kinds = {b['name']: b['kind'] for b in app_mod.list_backups()}
        assert kinds.get(name) == 'certs', 'a folder-qualified backup must still be listed as a certificate backup'
        before_first = first.read_bytes()
        inode = os.stat(second).st_ino
        res = client.post('/api/restore/' + name, headers=HDR)
        assert res.status_code == 200, res.get_json()
        assert first.read_bytes() == before_first, 'the other store with the same file name was overwritten'
        assert json.loads(second.read_text()) == saved
        assert os.stat(second).st_ino == inode and stat.S_IMODE(os.stat(second).st_mode) == 0o600
        assert restarts
    finally:
        _drop_backups('acme.json.')


def test_an_ambiguous_certificate_backup_is_refused(client, tmp_path, monkeypatch):
    from core import env as env_mod
    _app_mod, first, second, restarts = _restore_setup(client, tmp_path, monkeypatch)
    name = 'acme.json.20260914_101010.bak'
    os.makedirs(env_mod.BACKUP_DIR, exist_ok=True)
    with open(os.path.join(env_mod.BACKUP_DIR, name), 'w') as fh:
        json.dump({'letsencrypt': {}}, fh)
    try:
        before = (first.read_bytes(), second.read_bytes())
        res = client.post('/api/restore/' + name, headers=HDR)
        assert res.status_code == 409, res.get_json()
        assert (first.read_bytes(), second.read_bytes()) == before and not restarts
    finally:
        _drop_backups('acme.json.')


def test_certificate_backups_are_always_reachable_from_settings():
    html = _read('templates', 'modals', 'settings_modal.html')
    tab = html[html.index('id="backup-tab-certs"'):]
    tab = tab[:tab.index('>')]
    assert 'display:none' not in tab, 'the Certificates backups tab stayed hidden until a backup existed'
    assert 'id="msc-backups-certs"' in html, 'the desktop Backups menu has no Certificates entry'
    assert "openSettingsChild('backups', 'certs')" in html.replace('id="msc-backups-certs" ', ''), \
        'the mobile Backups menu has no Certificates entry'
    js = _read('static', 'js', 'settings-modal.js')
    assert "certTab.style.display" not in js

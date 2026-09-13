import concurrent.futures
import os
import threading

from core import locks

HDR = {'X-CSRF-Token': 'testtoken', 'X-Requested-With': 'fetch'}


def _read(*parts):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, *parts), encoding='utf-8') as fh:
        return fh.read()


def test_the_lock_actually_excludes(tmp_path):
    path  = tmp_path / 'thing.yml'
    order = []
    held  = threading.Event()

    def slow():
        with locks.file_lock(str(path)):
            order.append('in')
            held.set()
            threading.Event().wait(0.2)
            order.append('out')

    def quick():
        held.wait(2)
        with locks.file_lock(str(path)):
            order.append('second')

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        list(concurrent.futures.as_completed([ex.submit(slow), ex.submit(quick)]))
    assert order == ['in', 'out', 'second'], f'the second writer got in early: {order}'


def test_two_paths_do_not_block_each_other(tmp_path):
    done = []

    def run(name):
        with locks.file_lock(str(tmp_path / name)):
            done.append(name)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        list(concurrent.futures.as_completed([ex.submit(run, 'a.yml'), ex.submit(run, 'b.yml')]))
    assert sorted(done) == ['a.yml', 'b.yml']


def test_concurrent_settings_writes_all_survive(client):
    from core import settings as settings_mod
    jobs = [('/api/settings/theme', {'default_theme': 'dark'}),
            ('/api/settings/route-health', {'enabled': True, 'interval': 900}),
            ('/api/settings/backup-retention', {'backup_keep_count': 3})]
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(jobs)) as ex:
            codes = [f.result() for f in [
                ex.submit(lambda j: client.post(j[0], json=j[1], headers=HDR).status_code, job)
                for job in jobs]]
        assert codes == [200] * len(jobs)

        got  = settings_mod.load_settings()
        want = {'default_theme': 'dark', 'route_check_enabled': True,
                'route_check_interval': 900, 'backup_keep_count': 3}
        lost = [k for k, v in want.items() if got.get(k) != v]
        assert not lost, (
            'these settings were written but did not survive: %s. save_settings rewrites the whole '
            'file from a fresh read, so overlapping writes drop one another unless serialized' % lost)
    finally:
        client.post('/api/settings/theme', json={'default_theme': 'system'}, headers=HDR)
        client.post('/api/settings/route-health', json={'enabled': True, 'interval': 300}, headers=HDR)
        client.post('/api/settings/backup-retention', json={'backup_keep_count': 0}, headers=HDR)


def test_one_save_does_not_revert_another(client):
    from core import settings as settings_mod
    try:
        for _ in range(8):
            client.post('/api/settings/tabs', json={'docker': False}, headers=HDR)
            jobs = [('/api/settings/tabs', {'docker': True}),
                    ('/api/settings/theme', {'default_theme': 'dark'})]
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
                list(concurrent.futures.as_completed([
                    ex.submit(lambda j: client.post(j[0], json=j[1], headers=HDR), job) for job in jobs]))
            tabs = settings_mod.load_settings().get('visible_tabs') or {}
            assert tabs.get('docker') is True, (
                'a concurrent save carried a stale copy of visible_tabs and reverted the tab change. '
                'Every handler must send only what it is changing and let the merge happen under the lock')
    finally:
        client.post('/api/settings/tabs', json={'docker': False}, headers=HDR)
        client.post('/api/settings/theme', json={'default_theme': 'system'}, headers=HDR)


def test_handlers_send_only_what_they_change():
    src = _read('app.py')
    stale = src.count("password_hash=existing['password_hash']") + src.count("password_hash=s['password_hash']")
    assert stale <= 12, (
        'these call sites rebuild the whole settings file from a snapshot taken before the lock, '
        'so they silently revert whatever another request changed in between (found %d)' % stale)
    assert 'update_settings(' in src, 'the locked read-modify-write helper is not being used'


def test_the_settings_write_is_serialized():
    src = _read('core', 'settings.py')
    assert '@serialized' in src, 'overlapping settings saves silently lose one another'
    body = src[src.index('def serialized(fn)'):src.index('def load_settings')]
    assert 'locks.file_lock(env.SETTINGS_PATH)' in body, \
        'a thread lock alone leaves the two worker processes racing'


def test_the_dashboard_config_is_written_atomically():
    src = _read('app.py')
    body = src[src.index("def _write_groups_config(data, server=''):"):src.index("@app.route('/api/dashboard/config', methods=['GET'])")]
    assert '_locks.file_lock(GROUPS_CONFIG_FILE)' in body, \
        'the monitor reads this file every cycle while a request can be rewriting it'
    assert "open(GROUPS_CONFIG_FILE, 'w')" not in body, \
        'writing in place lets a reader see a truncated file and lose every route override'
    assert '_replace_or_copy' in body


def test_the_bind_mount_fallback_is_serialized():
    src = _read('core', 'config.py')
    body = src[src.index('def _replace_or_copy('):src.index('def safe_file_path(')]
    assert 'locks.file_lock(path)' in body, \
        'copyfile truncates in place, so two writers can interleave into a file that is neither'
    assert body.index('locks.file_lock') < body.index('shutil.copyfile')


def test_a_geoip_reader_in_use_is_not_closed():
    src = _read('core', 'geoip.py')
    body = src[src.index('def _geoip_reader('):src.index('def _geoip_lookup(')]
    assert ".close()" not in body, \
        'another thread can still be looking up against the old reader when the database refreshes'

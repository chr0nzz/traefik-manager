import inspect
import shutil
import subprocess

import pytest

from core import git, settings as settings_mod

pytestmark = pytest.mark.skipif(
    shutil.which('git') is None, reason='git binary not available')


def _run(*args, **kw):
    return subprocess.run(args, capture_output=True, text=True, **kw)


@pytest.fixture
def bare_remote(tmp_path, monkeypatch):
    fake_global = tmp_path / 'gitconfig'
    fake_global.write_text(
        '[user]\n\tname = test\n\temail = test@example.com\n'
        '[init]\n\tdefaultBranch = main\n')
    monkeypatch.setenv('GIT_CONFIG_GLOBAL', str(fake_global))
    monkeypatch.setenv('GIT_CONFIG_SYSTEM', '/dev/null')
    remote = str(tmp_path / 'remote.git')
    _run('git', 'init', '--bare', '-q', '-b', 'main', remote)
    return remote



def test_only_expected_schemes_are_accepted():
    assert git._valid_git_url('https://github.com/o/r.git')
    assert git._valid_git_url('ssh://git@host/o/r.git')
    assert not git._valid_git_url('file:///etc'), 'file:// must not be an accepted remote'
    assert not git._valid_git_url('ext::sh -c whoami'), 'ext:: transport must be rejected'
    assert not git._valid_git_url('')


def test_protocol_hardening_flags_are_applied():
    assert '-c' in git._GIT_PROTO_HARDENING
    joined = ' '.join(git._GIT_PROTO_HARDENING)
    assert 'protocol.ext.allow=never' in joined
    assert 'protocol.file.allow=user' in joined
    assert 'protocol.fd.allow=user' in joined


def test_branch_names_are_sanitised():
    assert git._safe_git_branch('main') == 'main'
    for bad in ('a b', 'a;rm -rf /', '../evil', 'a$(whoami)'):
        cleaned = git._safe_git_branch(bad)
        assert ' ' not in cleaned and ';' not in cleaned and '$' not in cleaned, \
            'unsafe characters survived branch sanitisation: %r -> %r' % (bad, cleaned)


def test_git_lock_is_a_context_manager():
    assert hasattr(git._git_lock(), '__enter__'), '_git_lock is not usable as a context manager'
    with git._git_lock():
        pass



def _enable_backup(repo, branch='main'):
    s = settings_mod.load_settings()
    settings_mod.save_settings(
        domains=s['domains'], cert_resolver=s['cert_resolver'],
        traefik_api_url=s['traefik_api_url'], auth_enabled=s['auth_enabled'],
        password_hash=s['password_hash'], visible_tabs=s['visible_tabs'],
        git_backup_enabled=True, git_backup_repo=repo, git_backup_branch=branch)
    return s


def test_push_creates_a_commit_containing_the_config(bare_remote, config_path, monkeypatch):
    monkeypatch.setattr(git, '_GIT_ALLOWED_SCHEMES',
                        git._GIT_ALLOWED_SCHEMES + ('file://',))
    before = settings_mod.load_settings()
    try:
        _enable_backup('file://' + bare_remote)
        config_path.write_text('http:\n  routers:\n    pushed-route: {}\n')

        ok, err = git._git_push_configs('test commit')
        assert ok, 'push failed: %s' % err

        log = _run('git', '--git-dir', bare_remote, 'log', '--oneline', '-1', 'main').stdout
        assert 'test commit' in log
        files = _run('git', '--git-dir', bare_remote, 'ls-tree', '-r',
                     '--name-only', 'main').stdout.split()
        assert any(f.endswith('.yml') for f in files), 'no config file in the pushed tree'
        blob = _run('git', '--git-dir', bare_remote, 'show', 'main:' + files[0]).stdout
        assert 'pushed-route' in blob, 'the pushed file is not the current config'
    finally:
        settings_mod.save_settings(
            domains=before['domains'], cert_resolver=before['cert_resolver'],
            traefik_api_url=before['traefik_api_url'], auth_enabled=before['auth_enabled'],
            password_hash=before['password_hash'], visible_tabs=before['visible_tabs'],
            git_backup_enabled=False, git_backup_repo='')


def test_push_refuses_a_disallowed_scheme(config_path):
    before = settings_mod.load_settings()
    try:
        _enable_backup('file:///tmp/should-not-be-used.git')
        ok, err = git._git_push_configs('nope')
        assert not ok
        assert 'scheme' in (err or '').lower(), 'expected a scheme rejection, got %r' % err
    finally:
        settings_mod.save_settings(
            domains=before['domains'], cert_resolver=before['cert_resolver'],
            traefik_api_url=before['traefik_api_url'], auth_enabled=before['auth_enabled'],
            password_hash=before['password_hash'], visible_tabs=before['visible_tabs'],
            git_backup_enabled=False, git_backup_repo='')


def test_credentials_are_not_embedded_in_the_remote_url():
    src = inspect.getsource(git)
    assert 'askpass' in src.lower(), 'the askpass credential path is gone'
    for pattern in ('https://{user}:{token}@', '://%s:%s@'):
        assert pattern not in src, 'credentials appear to be interpolated into a URL'


def test_app_aliases_point_at_core(app_module):
    assert app_module._git_run is git._git_run
    assert app_module._git_push_configs is git._git_push_configs
    assert app_module._GIT_PROTO_HARDENING is git._GIT_PROTO_HARDENING


@pytest.mark.parametrize('has_repo, rcs', [
    (False, {('clone',): 1}),
    (True, {('remote', 'get-url'): 1}),
    (True, {}),
], ids=['clone-failed-then-remote-add', 'repo-without-origin', 'repo-with-origin'])
def test_the_repo_url_always_follows_an_end_of_options_marker(tmp_path, monkeypatch, has_repo, rcs):
    url = 'https://example.com/backups.git'
    repo = tmp_path / 'repo'
    if has_repo:
        (repo / '.git').mkdir(parents=True)
    calls = []

    def fake_run(args, **kw):
        calls.append(args)
        return '', '', rcs.get(tuple(args[:2]), rcs.get(tuple(args[:1]), 0))

    monkeypatch.setattr(git, '_git_run', fake_run)
    git._git_ensure_repo_at(str(repo), url, 'main', None)
    with_url = [c for c in calls if url in c]
    assert with_url, 'no git call received the repo URL on this path'
    for c in with_url:
        assert '--' in c and c.index('--') < c.index(url), (
            f'{c} passes the repo URL where a value starting with - would be read as a git option')


def test_no_test_ever_touches_the_real_global_gitconfig():
    import os
    src = open(os.path.abspath(__file__), encoding='utf-8').read()
    body = src.split('def test_no_test_ever_touches_the_real_global_gitconfig')[0]
    assert "'--global'" not in body and '"--global"' not in body, (
        'a --global git config write lands in the developer\'s real ~/.gitconfig and '
        'silently changes the author of every commit they make afterwards')

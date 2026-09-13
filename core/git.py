import contextlib
import fcntl
import os
import re
import shutil
import subprocess
import time

from core import agents_http, env, notifications
from core import settings as settings_mod
from core.env import logger

_GIT_ALLOWED_SCHEMES = ('https://', 'http://', 'ssh://', 'git://')
_GIT_PROTO_HARDENING = ['-c', 'protocol.ext.allow=never',
                        '-c', 'protocol.file.allow=user',
                        '-c', 'protocol.fd.allow=user']


def _git_repo_dir():
    return os.path.join(env.BACKUP_DIR, 'git-repo')

def _valid_git_url(url: str) -> bool:
    return any((url or '').strip().lower().startswith(s) for s in _GIT_ALLOWED_SCHEMES)

def _safe_git_branch(branch: str) -> str:
    branch = re.sub(r'[^\w./-]', '', (branch or '').strip())
    if not branch or branch.startswith('-'):
        return 'main'
    return branch

def _git_askpass_path() -> str:
    p = os.path.join(env.BACKUP_DIR, '.git-askpass.sh')
    if not os.path.exists(p):
        os.makedirs(env.BACKUP_DIR, exist_ok=True)
        with open(p, 'w') as f:
            f.write('#!/bin/sh\ncase "$1" in\n  Username*) printf "%s" "$GIT_ASKPASS_USER" ;;\n  *) printf "%s" "$GIT_ASKPASS_PASS" ;;\nesac\n')
        os.chmod(p, 0o700)
    return p

def _git_run(args, cwd=None, credentials=None):
    env = os.environ.copy()
    env['GIT_TERMINAL_PROMPT'] = '0'
    env['GIT_AUTHOR_NAME'] = 'Traefik Manager'
    env['GIT_AUTHOR_EMAIL'] = 'traefik-manager@localhost'
    env['GIT_COMMITTER_NAME'] = 'Traefik Manager'
    env['GIT_COMMITTER_EMAIL'] = 'traefik-manager@localhost'
    if credentials and credentials.get('token'):
        env['GIT_ASKPASS'] = _git_askpass_path()
        env['GIT_ASKPASS_USER'] = credentials.get('username') or 'git'
        env['GIT_ASKPASS_PASS'] = credentials.get('token')
    else:
        env['GIT_ASKPASS'] = ''
    result = subprocess.run(
        ['git'] + _GIT_PROTO_HARDENING + args,
        cwd=cwd or _git_repo_dir(),
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        timeout=30,
        env=env
    )
    return result.stdout.strip(), result.stderr.strip(), result.returncode

def _git_ensure_repo_at(repo_dir, repo_url, branch, creds):
    def _fresh_clone():
        if os.path.exists(repo_dir):
            shutil.rmtree(repo_dir, ignore_errors=True)
        os.makedirs(repo_dir, exist_ok=True)
        _, _, rc = _git_run(['clone', '--branch', branch, '--', repo_url, '.'], cwd=repo_dir, credentials=creds)
        if rc != 0:
            _git_run(['init'], cwd=repo_dir)
            _git_run(['remote', 'add', 'origin', repo_url], cwd=repo_dir)
            _git_run(['pull', 'origin', branch], cwd=repo_dir, credentials=creds)
        _git_run(['config', 'user.email', 'traefik-manager@localhost'], cwd=repo_dir)
        _git_run(['config', 'user.name', 'Traefik Manager'], cwd=repo_dir)

    valid = False
    if os.path.exists(os.path.join(repo_dir, '.git')):
        _, _, rc = _git_run(['rev-parse', '--git-dir'], cwd=repo_dir)
        valid = (rc == 0)
    if not valid:
        _fresh_clone()
    else:
        _, _, rc = _git_run(['remote', 'get-url', 'origin'], cwd=repo_dir)
        if rc != 0:
            _, _, arc = _git_run(['remote', 'add', 'origin', repo_url], cwd=repo_dir)
            if arc != 0:
                _fresh_clone()
        else:
            _git_run(['remote', 'set-url', 'origin', repo_url], cwd=repo_dir)
        _git_run(['config', 'user.email', 'traefik-manager@localhost'], cwd=repo_dir)
        _git_run(['config', 'user.name', 'Traefik Manager'], cwd=repo_dir)
    return repo_dir

def _git_ensure_repo():
    s        = settings_mod.load_settings()
    repo_url = s.get('git_backup_repo', '').strip()
    branch   = _safe_git_branch(s.get('git_backup_branch', 'main'))
    username = s.get('git_backup_username', '').strip()
    token    = s.get('git_backup_token', '').strip()
    if not _valid_git_url(repo_url):
        raise ValueError('Unsupported git repository URL scheme')
    creds    = {'username': username, 'token': token} if token else None
    return _git_ensure_repo_at(_git_repo_dir(), repo_url, branch, creds)

@contextlib.contextmanager
def _git_lock():
    os.makedirs(env.BACKUP_DIR, exist_ok=True)
    f = open(os.path.join(env.BACKUP_DIR, '.git-push.lock'), 'w')
    try:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(f, fcntl.LOCK_UN)
        finally:
            f.close()

def _git_push_configs(action='backup', custom_message=None):
    s = settings_mod.load_settings()
    if not s.get('git_backup_repo', '').strip():
        return False, 'No repository configured'
    branch = _safe_git_branch(s.get('git_backup_branch', 'main'))
    token  = s.get('git_backup_token', '').strip()
    creds  = {'username': s.get('git_backup_username', '').strip(), 'token': token} if token else None
    tmpl   = s.get('git_backup_commit_message', 'traefik-manager: {action} at {timestamp}')

    def _redact(text):
        return text.replace(token, '***') if token and text else text

    with _git_lock():
        try:
            repo_dir = _git_ensure_repo()
        except Exception as e:
            return False, f'Repo init failed: {_redact(str(e))}'
        dyn_dir    = os.path.join(repo_dir, 'dynamic')
        static_dir = os.path.join(repo_dir, 'static')
        ts  = time.strftime('%Y-%m-%d %H:%M:%S')
        if custom_message and custom_message.strip():
            msg = custom_message.strip()
        else:
            msg = tmpl.replace('{action}', action).replace('{timestamp}', ts)
        err = ''
        for attempt in (1, 2):
            _, _, frc = _git_run(['fetch', 'origin', branch], credentials=creds)
            if frc == 0:
                _git_run(['reset', '--hard', 'FETCH_HEAD'])
            os.makedirs(dyn_dir,    exist_ok=True)
            os.makedirs(static_dir, exist_ok=True)
            for p in env.CONFIG_PATHS:
                if env.is_own_state(p):
                    logger.warning(f"Not pushing {os.path.basename(p)}: it holds Traefik Manager's own settings, not Traefik config")
                    continue
                if os.path.exists(p):
                    shutil.copy2(p, os.path.join(dyn_dir, os.path.basename(p)))
            sp = settings_mod._get_static_config_path()
            if sp and os.path.exists(sp):
                shutil.copy2(sp, os.path.join(static_dir, os.path.basename(sp)))
            _git_run(['add', '-A'])
            _, _, rc = _git_run(['diff', '--cached', '--quiet'])
            if rc == 0:
                return True, 'No changes'
            _, err, rc = _git_run(['commit', '-m', msg])
            if rc != 0:
                return False, f'Commit failed: {_redact(err)}'
            _, err, rc = _git_run(['push', 'origin', f'HEAD:{branch}'], credentials=creds)
            if rc == 0:
                logger.info(f"Git backup: {msg}")
                return True, ''
        return False, f'Push failed: {_redact(err)}'

def _git_push_if_enabled(action='backup'):
    try:
        s = settings_mod.load_settings()
        enabled   = s.get('git_backup_enabled')
        auto_push = s.get('git_backup_auto_push')
        repo      = s.get('git_backup_repo', '').strip()
        if enabled and auto_push and repo:
            ok, err = _git_push_configs(action)
            if ok and err != 'No changes':
                notifications.add_notification('success', f'Git backup pushed ({action})', category='backup')
            elif not ok:
                logger.warning(f"Git backup failed: {err}")
                notifications.add_notification('error', f'Git backup failed ({action}): {err}', category='backup')
    except Exception:
        logger.exception("Git push error")

def _git_agent_repo_dir(agent_id: str) -> str:
    safe = re.sub(r'[^\w-]', '', str(agent_id))
    return os.path.join(env.BACKUP_DIR, f'git-agent-{safe}')

def _agent_git_branch(agent: dict) -> str:
    branch = (agent.get('git_host_branch') or '').strip()
    if not branch:
        branch = re.sub(r'[^\w.-]+', '-', (agent.get('name') or '').strip().lower()).strip('-')
    if not branch:
        branch = f"agent-{str(agent.get('id', ''))[:8]}"
    return _safe_git_branch(branch)

def _git_push_agent_configs(agent, action='backup', custom_message=None):
    s        = settings_mod.load_settings()
    repo_url = s.get('git_backup_repo', '').strip()
    if not repo_url:
        return False, 'No repository configured on the Host'
    if not _valid_git_url(repo_url):
        return False, 'Unsupported git repository URL scheme'
    branch      = _agent_git_branch(agent)
    host_branch = _safe_git_branch(s.get('git_backup_branch', 'main'))
    if branch == host_branch:
        return False, f'Agent branch "{branch}" must differ from the Host branch'
    token = s.get('git_backup_token', '').strip()
    creds = {'username': s.get('git_backup_username', '').strip(), 'token': token} if token else None
    tmpl  = s.get('git_backup_commit_message', 'traefik-manager: {action} at {timestamp}')

    def _redact(text):
        return text.replace(token, '***') if token and text else text

    try:
        resp = agents_http._agent_request(agent, 'GET', '/api/configs')
        resp.raise_for_status()
        files = (resp.json() or {}).get('files') or []
    except Exception as e:
        return False, f'Could not read agent configs: {e}'
    static_content = ''
    static_name    = ''
    try:
        sresp = agents_http._agent_request(agent, 'GET', '/api/static')
        if sresp.status_code == 200:
            static_content = (sresp.json() or {}).get('content', '') or ''
            static_name    = os.path.basename((agent.get('static_config_path') or '').strip()) or 'traefik.yml'
    except Exception:
        pass

    repo_dir = _git_agent_repo_dir(agent['id'])
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    if custom_message and custom_message.strip():
        msg = custom_message.strip()
    else:
        msg = tmpl.replace('{action}', action).replace('{timestamp}', ts)
    with _git_lock():
        try:
            _git_ensure_repo_at(repo_dir, repo_url, branch, creds)
        except Exception as e:
            return False, f'Repo init failed: {_redact(str(e))}'
        dyn_dir    = os.path.join(repo_dir, 'dynamic')
        static_dir = os.path.join(repo_dir, 'static')
        err = ''
        for attempt in (1, 2):
            _, _, frc = _git_run(['fetch', 'origin', branch], cwd=repo_dir, credentials=creds)
            if frc == 0:
                _git_run(['reset', '--hard', 'FETCH_HEAD'], cwd=repo_dir)
            os.makedirs(dyn_dir,    exist_ok=True)
            os.makedirs(static_dir, exist_ok=True)
            for f in files:
                name = os.path.basename(str(f.get('name') or '').strip())
                if not name:
                    continue
                with open(os.path.join(dyn_dir, name), 'w') as fh:
                    fh.write(str(f.get('content') or ''))
            if static_content and static_name:
                with open(os.path.join(static_dir, static_name), 'w') as fh:
                    fh.write(static_content)
            _git_run(['add', '-A'], cwd=repo_dir)
            _, _, rc = _git_run(['diff', '--cached', '--quiet'], cwd=repo_dir)
            if rc == 0:
                return True, 'No changes'
            _, err, rc = _git_run(['commit', '-m', msg], cwd=repo_dir)
            if rc != 0:
                return False, f'Commit failed: {_redact(err)}'
            _, err, rc = _git_run(['push', 'origin', f'HEAD:{branch}'], cwd=repo_dir, credentials=creds)
            if rc == 0:
                logger.info(f"Git backup ({agent.get('name')}): {msg}")
                return True, ''
        return False, f'Push failed: {_redact(err)}'

def _git_push_agent_if_enabled(agent, action='backup'):
    try:
        if not agent or not agent.get('git_host_backup'):
            return
        s = settings_mod.load_settings()
        if not (s.get('git_backup_enabled') and s.get('git_backup_auto_push') and s.get('git_backup_repo', '').strip()):
            return
        ok, err = _git_push_agent_configs(agent, action)
        if ok and err != 'No changes':
            notifications.add_notification('success', f"Git backup pushed ({agent.get('name')}: {action})",
                                           category='backup')
        elif not ok:
            logger.warning(f"Agent git backup failed: {err}")
            notifications.add_notification('error', f"Git backup failed ({agent.get('name')}): {err}",
                                           category='backup')
    except Exception:
        logger.exception("Agent git push error")


def _git_show_first(repo_dir, sha, candidates):
    for c in candidates:
        content, _, rc = _git_run(['show', f'{sha}:{c}'], cwd=repo_dir)
        if rc == 0 and content:
            return content
    return None

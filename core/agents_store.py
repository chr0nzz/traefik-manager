import os
import threading

from core import config, crypto, env
from core.env import logger


def encrypt_agents(agents: list) -> list:
    out = []
    for a in agents:
        enc = dict(a)
        if enc.get('api_key'):
            enc['api_key'] = crypto.encrypt_secret(enc['api_key'])
        if enc.get('crowdsec_api_key'):
            enc['crowdsec_api_key'] = crypto.encrypt_secret(enc['crowdsec_api_key'])
        if enc.get('crowdsec_machine_password'):
            enc['crowdsec_machine_password'] = crypto.encrypt_secret(enc['crowdsec_machine_password'])
        if enc.get('git_backup_token'):
            enc['git_backup_token'] = crypto.encrypt_secret(enc['git_backup_token'])
        out.append(enc)
    return out

def parse_agent_dict(a: dict) -> dict:
    return {
        'id':         str(a['id']),
        'name':       str(a['name'])[:100],
        'url':        str(a['url']).strip().rstrip('/'),
        'api_key':    crypto.decrypt_secret(str(a.get('api_key', ''))),
        'created_at': str(a.get('created_at', '')),
        'traefik_api_url':              str(a.get('traefik_api_url', 'http://traefik:8080')).strip(),
        'traefik_insecure_skip_verify': bool(a.get('traefik_insecure_skip_verify', False)),
        'cert_resolver':                str(a.get('cert_resolver', '')).strip(),
        'config_path':                  str(a.get('config_path', '/app/config')).strip(),
        'backup_dir':                   str(a.get('backup_dir', '')).strip(),
        'backup_keep_count':            str(a.get('backup_keep_count', '')).strip(),
        'static_config_path':           str(a.get('static_config_path', '')).strip(),
        'acme_json_path':               str(a.get('acme_json_path', '')).strip(),
        'access_log_path':              str(a.get('access_log_path', '')).strip(),
        'plugins_dir':                  str(a.get('plugins_dir', '')).strip(),
        'restart_method':               str(a.get('restart_method', '')).strip(),
        'traefik_container':            str(a.get('traefik_container', 'traefik')).strip(),
        'docker_host':                  str(a.get('docker_host', '')).strip(),
        'signal_file_path':             str(a.get('signal_file_path', '')).strip(),
        'install_method':               'cli' if str(a.get('install_method', '')).strip() == 'cli' else 'manual',
        'traefik_api_user':             str(a.get('traefik_api_user', '')).strip(),
        'traefik_api_password':         str(a.get('traefik_api_password', '')),
        'crowdsec_lapi_url':            str(a.get('crowdsec_lapi_url', '')).strip(),
        'crowdsec_api_key':             crypto.decrypt_secret(str(a.get('crowdsec_api_key', ''))),
        'crowdsec_machine_id':          str(a.get('crowdsec_machine_id', '')).strip(),
        'crowdsec_machine_password':    crypto.decrypt_secret(str(a.get('crowdsec_machine_password', ''))),
        'crowdsec_client_cert':         str(a.get('crowdsec_client_cert', '')).strip(),
        'crowdsec_client_key':          str(a.get('crowdsec_client_key', '')).strip(),
        'crowdsec_ca_cert':             str(a.get('crowdsec_ca_cert', '')).strip(),
        'git_backup_enabled':           bool(a.get('git_backup_enabled', False)),
        'git_backup_repo':              str(a.get('git_backup_repo', '')).strip(),
        'git_backup_branch':            str(a.get('git_backup_branch', 'main')).strip() or 'main',
        'git_backup_username':          str(a.get('git_backup_username', '')).strip(),
        'git_backup_token':             crypto.decrypt_secret(str(a.get('git_backup_token', ''))),
        'git_backup_auto_push':         bool(a.get('git_backup_auto_push', True)),
        'git_backup_commit_message':    str(a.get('git_backup_commit_message', 'traefik-manager: {action} at {timestamp}')).strip() or 'traefik-manager: {action} at {timestamp}',
        'git_host_backup':              bool(a.get('git_host_backup', False)),
        'git_host_branch':              str(a.get('git_host_branch', '')).strip(),
        'tma_port':                     str(a.get('tma_port', '')).strip(),
        'tma_rate_limit':               str(a.get('tma_rate_limit', '')).strip(),
        'domains':                      [str(d).strip() for d in (a.get('domains') or []) if str(d).strip()],
        'visible_tabs':                 {str(k): bool(v) for k, v in a['visible_tabs'].items()} if isinstance(a.get('visible_tabs'), dict) else {},
        'provider_tabs_seen':           [str(t) for t in (a.get('provider_tabs_seen') or []) if str(t)],
    }

def load_agents() -> list:
    if os.path.exists(env.AGENTS_PATH):
        try:
            with open(env.AGENTS_PATH, 'r') as f:
                raw = config.yaml_safe.load(f) or {}
            return [
                parse_agent_dict(a)
                for a in (raw.get('agents', []) or [])
                if isinstance(a, dict) and a.get('id') and a.get('name') and a.get('url')
            ]
        except Exception as e:
            logger.warning(f"Could not load agents.yml: {e}")
            return []

    if os.path.exists(env.SETTINGS_PATH):
        try:
            with open(env.SETTINGS_PATH, 'r') as f:
                data = config.yaml_safe.load(f) or {}
            raw_agents = data.get('agents', [])
            if raw_agents and isinstance(raw_agents, list):
                agents = [
                    parse_agent_dict(a)
                    for a in raw_agents
                    if isinstance(a, dict) and a.get('id') and a.get('name') and a.get('url')
                ]
                if agents:
                    save_agents_file(agents)
                    logger.info(f"Migrated {len(agents)} agent(s) from manager.yml to agents.yml")
                return agents
        except Exception as e:
            logger.warning(f"Agent migration from manager.yml failed: {e}")

    return []

def save_agents_file(agents: list):
    os.makedirs(os.path.dirname(env.AGENTS_PATH), exist_ok=True)
    tmp = f"{env.AGENTS_PATH}.tmp.{os.getpid()}.{threading.get_ident()}"
    try:
        with open(tmp, 'w') as f:
            config.yaml.dump({'agents': encrypt_agents(agents)}, f)
        os.replace(tmp, env.AGENTS_PATH)
    finally:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass

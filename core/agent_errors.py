import json

from flask_babel import gettext, ngettext

from core import i18n

MESSAGES = {
    'unauthorized': lambda p: gettext('The agent refused the API key'),
    'rate_limited': lambda p: gettext('Too many requests to the agent, try again in a moment'),
    'invalid_since': lambda p: gettext('since must be a non-negative integer'),
    'name_required': lambda p: gettext('Name is required'),
    'key_create_failed': lambda p: gettext('Failed to create key: %(detail)s', detail=p['detail']),
    'key_not_found': lambda p: gettext('Key not found'),
    'not_found': lambda p: gettext('Not found'),
    'router_name_required': lambda p: gettext('Router name is required'),
    'proxy_error': lambda p: gettext('Proxy error: %(detail)s', detail=p['detail']),
    'traefik_unavailable': lambda p: gettext('Traefik unavailable: %(detail)s', detail=p['detail']),
    'traefik_unavailable_at': lambda p: gettext('Traefik unavailable at %(url)s: %(detail)s', url=p['url'], detail=p['detail']),
    'config_path_not_found': lambda p: gettext('Config path not found'),
    'config_dir_unreadable': lambda p: gettext('Cannot read the config directory'),
    'config_file_unreadable': lambda p: gettext('Cannot read the config file'),
    'invalid_body': lambda p: gettext('Invalid request body'),
    'invalid_file_name': lambda p: gettext('Invalid file name'),
    'backup_failed_nothing_written': lambda p: gettext('Backup failed, nothing was written: %(detail)s', detail=p['detail']),
    'write_failed': lambda p: gettext('Write failed: %(detail)s', detail=p['detail']),
    'static_config_missing': lambda p: gettext('STATIC_CONFIG_PATH not configured'),
    'static_config_unreadable': lambda p: gettext('Cannot read static config: %(detail)s', detail=p['detail']),
    'invalid_yaml': lambda p: gettext('Invalid YAML: %(error)s', error=p['detail']),
    'signal_file_missing': lambda p: gettext('SIGNAL_FILE_PATH not configured'),
    'signal_file_write_failed': lambda p: gettext('Failed to write the signal file: %(detail)s', detail=p['detail']),
    'docker_restart_failed': lambda p: gettext('Docker restart failed: %(detail)s', detail=p['detail']),
    'restart_method_missing': lambda p: gettext('RESTART_METHOD not configured or unsupported'),
    'crowdsec_missing': lambda p: gettext('CROWDSEC_LAPI_URL not configured'),
    'crowdsec_unavailable': lambda p: gettext('CrowdSec unavailable: %(detail)s', detail=p['detail']),
    'ip_required': lambda p: gettext('IP/Range is required'),
    'invalid_type': lambda p: gettext('Invalid type'),
    'decision_add_failed': lambda p: gettext('Failed to add decision: %(detail)s', detail=p['detail']),
    'backup_failed': lambda p: gettext('Backup failed: %(detail)s', detail=p['detail']),
    'backup_unreadable': lambda p: gettext('Cannot read backup: %(detail)s', detail=p['detail']),
    'acme_store_ambiguous': lambda p: gettext('%(original)s matches more than one certificate store, so this backup cannot be restored safely', original=p['file']),
    'no_config_match': lambda p: gettext('No config file matches %(filename)s', filename=p['file']),
    'backup_failed_nothing_restored': lambda p: gettext('Backup failed, nothing was restored: %(detail)s', detail=p['detail']),
    'restore_failed': lambda p: gettext('Restore failed: %(detail)s', detail=p['detail']),
    'acme_needs_restart': lambda p: gettext('No RESTART_METHOD is configured on this agent, and Traefik only reads acme.json at startup'),
    'backup_not_json': lambda p: gettext('This backup is not valid JSON, nothing was restored'),
    'read_only_not_restored': lambda p: gettext('%(file)s is mounted read only on this agent, nothing was restored', file=p['file']),
    'file_unreadable': lambda p: gettext('Could not read %(file)s: %(detail)s', file=p['file'], detail=p['detail']),
    'delete_failed': lambda p: gettext('Delete failed: %(detail)s', detail=p['detail']),
    'git_no_repo': lambda p: gettext('No repository URL configured'),
    'git_bad_scheme': lambda p: gettext('Invalid repository URL scheme'),
    'target_not_allowed': lambda p: gettext('Target address not allowed'),
    'internal_error': lambda p: gettext('Internal error'),
    'invalid_sha': lambda p: gettext('Invalid commit SHA'),
    'diff_failed': lambda p: gettext('Diff failed'),
    'git_not_initialized': lambda p: gettext('Git repo not initialized'),
    'commit_not_found': lambda p: gettext('Commit not found'),
    'commit_no_configs': lambda p: gettext('The commit holds no config files for this agent'),
    'restore_stopped': lambda p: gettext('Restore stopped at %(file)s: %(detail)s. A backup was taken before the restore', file=p['file'], detail=p['detail']),
    'invalid_config_file': lambda p: gettext('Invalid config file'),
    'yaml_marshal_failed': lambda p: gettext('Failed to build the YAML'),
    'route_not_found': lambda p: gettext('Route not found'),
    'shared_definition_read_only': lambda p: gettext(
        '%(name)s is defined in %(file)s, which is read-only here.', name=p['name'], file=p['file']),
    'shared_file_changed': lambda p: gettext(
        '%(file)s changed on disk since this editor opened. Reopen it and make the change again.',
        file=p['file']),
    'shared_definition_renamed': lambda p: gettext(
        'Renaming %(name)s here would leave it behind in %(file)s. Rename it on the Middlewares tab.',
        name=p['name'], file=p['file']),
    'middleware_not_defined': lambda p: gettext(
        'The middleware %(name)s is not defined anywhere. Create it first, or correct the name.',
        name=p['name']),
    'service_not_defined': lambda p: gettext(
        'The service %(name)s is not defined anywhere. Create it first, or correct the name.',
        name=p['name']),
    'transport_not_defined': lambda p: gettext(
        'The serversTransport %(name)s is not defined anywhere. Create it first, or correct the name.',
        name=p['name']),
    'tls_options_not_defined': lambda p: gettext(
        'The TLS options %(name)s are not defined anywhere. Create them first, or correct the name.',
        name=p['name']),
    'invalid_lines': lambda p: gettext('Invalid lines parameter'),
    'reset_failed': lambda p: gettext('Reset failed: %(detail)s', detail=p['detail']),
    'nothing_selected': lambda p: gettext('Nothing was selected'),
    'acme_path_missing': lambda p: gettext('ACME_JSON_PATH is not set on this agent'),
    'acme_read_only': lambda p: gettext('acme.json is mounted read only on this agent'),
    'read_only_not_changed': lambda p: gettext('%(file)s is mounted read only on this agent, nothing was changed', file=p['file']),
    'no_matching_cert': lambda p: gettext('No matching certificate was found'),
    'certs_partial': lambda p: ngettext('Removed %(num)d certificate, then stopped at %(file)s: %(detail)s',
                                        'Removed %(num)d certificates, then stopped at %(file)s: %(detail)s',
                                        int(p['removed']), file=p['file'], detail=p['detail']),
    'access_log_missing': lambda p: gettext('ACCESS_LOG_PATH not configured'),
    'access_log_not_found': lambda p: gettext('Access log not found at %(path)s', path=p['path']),
}


def text(code, params, fallback: str) -> str:
    fn = MESSAGES.get(code) if isinstance(code, str) else None
    if fn is None or i18n.current_tag() == i18n.DEFAULT_TAG:
        return fallback
    safe = {k: v if isinstance(v, int) and not isinstance(v, bool) else str(v)
            for k, v in (params or {}).items()} if isinstance(params, dict) else {}
    try:
        return fn(safe)
    except (KeyError, TypeError, ValueError):
        return fallback


def localize(body):
    if not isinstance(body, dict):
        return body
    if isinstance(body.get('error'), str) and 'code' in body:
        body['error'] = text(body.get('code'), body.get('params'), body['error'])
    if isinstance(body.get('reason'), str) and body.get('reason_code'):
        body['reason'] = text(body.get('reason_code'), None, body['reason'])
    return body


def localize_bytes(content: bytes, content_type: str) -> bytes:
    if 'json' not in (content_type or '') or i18n.current_tag() == i18n.DEFAULT_TAG:
        return content
    if b'"code"' not in content and b'"reason_code"' not in content:
        return content
    try:
        body = json.loads(content)
    except ValueError:
        return content
    if not isinstance(body, dict):
        return content
    before = (body.get('error'), body.get('reason'))
    localize(body)
    if (body.get('error'), body.get('reason')) == before:
        return content
    return json.dumps(body).encode()

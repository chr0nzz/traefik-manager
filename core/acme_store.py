import json
import os
import stat
import time

from core import env
from core.env import logger

SAFE_MODE = 0o600
CERT_KEYS = ('Certificates', 'certificates')


class AcmeStoreError(Exception):
    pass


def _cert_key(resolver_data):
    for key in CERT_KEYS:
        if isinstance(resolver_data.get(key), list):
            return key
    return ''


def load(path):
    try:
        with open(path, 'r') as fh:
            raw = fh.read().strip()
    except OSError as e:
        raise AcmeStoreError(f'Could not read {os.path.basename(path)}: {e}') from e
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except ValueError as e:
        raise AcmeStoreError(f'{os.path.basename(path)} is not valid JSON, nothing was changed: {e}') from e
    if not isinstance(data, dict):
        raise AcmeStoreError(f'{os.path.basename(path)} does not hold a resolver map, nothing was changed')
    return data


def writable(path) -> bool:
    if not path or not os.path.isfile(path):
        return False
    return os.access(path, os.W_OK)


def entry_matches(entry, wanted) -> bool:
    domain = entry.get('domain') if isinstance(entry, dict) else None
    if not isinstance(domain, dict):
        return False
    return str(domain.get('main') or '') == str(wanted or '')


def backup(path):
    os.makedirs(env.BACKUP_DIR, exist_ok=True)
    dest = os.path.join(env.BACKUP_DIR, f"{os.path.basename(path)}.{time.strftime('%Y%m%d_%H%M%S')}.bak")
    fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, SAFE_MODE)
    try:
        with open(path, 'rb') as src:
            os.write(fd, src.read())
        os.fsync(fd)
    finally:
        os.close(fd)
    os.chmod(dest, SAFE_MODE)
    return dest


def write_in_place(path, data):
    return write_bytes_in_place(path, json.dumps(data, indent=2).encode('utf-8'))


def write_bytes_in_place(path, body):
    try:
        before = os.stat(path)
    except OSError:
        before = None
    fd = os.open(path, os.O_WRONLY | os.O_CREAT, SAFE_MODE)
    try:
        os.write(fd, body)
        os.ftruncate(fd, len(body))
        os.fsync(fd)
    finally:
        os.close(fd)
    mode = stat.S_IMODE(before.st_mode) if before else SAFE_MODE
    if mode & 0o077:
        logger.warning(f"{os.path.basename(path)} had mode {mode:o}, tightening it to 600 so Traefik still reads it")
        mode = SAFE_MODE
    os.chmod(path, mode)
    return len(body)


def remove(path, wanted):
    targets = {(str(r or ''), str(m or '')) for r, m in wanted}
    if not targets:
        return 0, None
    data = load(path)
    removed = 0
    for resolver_name, resolver_data in data.items():
        if not isinstance(resolver_data, dict):
            continue
        key = _cert_key(resolver_data)
        if not key:
            continue
        kept = []
        for entry in resolver_data[key]:
            main = (entry.get('domain') or {}).get('main') if isinstance(entry, dict) else None
            if (str(resolver_name), str(main or '')) in targets:
                removed += 1
                continue
            kept.append(entry)
        resolver_data[key] = kept
    if not removed:
        return 0, None
    try:
        json.loads(json.dumps(data))
    except ValueError as e:
        raise AcmeStoreError(f'The edited store would not be valid JSON, nothing was written: {e}') from e
    saved = backup(path)
    write_in_place(path, data)
    return removed, saved

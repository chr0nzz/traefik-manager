import re

FORBIDDEN = re.compile(r'[@/,:{}]|[\x00-\x1f\x7f]')
MAX_LEN   = 100
RESERVED  = ('.', '..')
MESSAGE   = 'A name cannot contain @ / , : { or }'


def name_error(name) -> str:
    if not isinstance(name, str) or not name.strip():
        return 'Give it a name'
    name = name.strip()
    if name in RESERVED:
        return 'That name is reserved'
    if len(name) > MAX_LEN:
        return f'Keep the name to {MAX_LEN} characters or fewer'
    if FORBIDDEN.search(name):
        return MESSAGE
    return ''


def valid(name) -> bool:
    return not name_error(name)

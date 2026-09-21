from urllib.parse import urljoin, urlparse

import requests

TIMEOUT = 5

DISCORD_COLORS = {'warning': 0xf0a500, 'error': 0xf85149, 'info': 0x58a6ff, 'success': 0x3fb950}

SLACK_ICONS = {'warning': ':warning:', 'error': ':x:', 'success': ':white_check_mark:', 'info': ':information_source:'}

NTFY_TAGS = {'warning': 'warning', 'error': 'rotating_light', 'success': 'white_check_mark', 'info': 'information_source'}

GOTIFY_PRIORITIES = {'error': 8, 'warning': 5}

PUSHOVER_URL = 'https://api.pushover.net/1/messages.json'
PUSHOVER_TITLE_MAX = 250
PUSHOVER_MESSAGE_MAX = 1024
PUSHOVER_EMERGENCY_RETRY = 60
PUSHOVER_EMERGENCY_EXPIRE = 1800

PUSHBULLET_URL = 'https://api.pushbullet.com/v2/pushes'

TELEGRAM_MAX = 4096

DEFAULT_TITLE = 'Traefik Manager'

REQUIRED_FIELDS = {
    'discord':    ['url'],
    'slack':      ['url'],
    'ntfy':       ['url'],
    'generic':    ['url'],
    'gotify':     ['url', 'token'],
    'pushover':   ['token', 'token2'],
    'pushbullet': ['token'],
    'telegram':   ['token', 'token2'],
    'unifiedpush': ['url'],
}


def required_fields(kind) -> list[str]:
    return list(REQUIRED_FIELDS.get(str(kind or '').strip().lower(), []))


def _field(channel, key):
    return str(channel.get(key) or '').strip()


def _title_of(title):
    return str(title or '').strip() or DEFAULT_TITLE


def _clip(text, limit):
    text = str(text or '')
    return text if len(text) <= limit else text[:limit]


def _legacy_auth(channel):
    username = _field(channel, 'username')
    return (username, str(channel.get('password') or '')) if username else None


def _snippet(resp):
    try:
        body = (resp.text or '').strip().replace('\n', ' ')
    except Exception:
        body = ''
    return _clip(body, 200)


BRANDED_KINDS = ('gotify', 'pushover', 'telegram', 'unifiedpush')


def titled(kind: str, title: str) -> str:
    label = str(title or '').strip() or DEFAULT_TITLE
    if label == DEFAULT_TITLE or kind in BRANDED_KINDS:
        return label
    return f'{DEFAULT_TITLE} - {label}'


def _http_error(resp):
    detail = _snippet(resp)
    return 'HTTP %s%s' % (resp.status_code, ': ' + detail if detail else '')


def _result(resp):
    if resp.status_code >= 400:
        return False, _http_error(resp)
    return True, ''


def _send_discord(channel, type_, title, msg, ts):
    payload = {'embeds': [{
        'title': msg,
        'author': {'name': titled('discord', title)},
        'color': DISCORD_COLORS.get(type_, DISCORD_COLORS['info']),
        'footer': {'text': f'{DEFAULT_TITLE} - {ts}'},
    }]}
    return _result(requests.post(_field(channel, 'url'), json=payload,
                                 timeout=TIMEOUT, auth=_legacy_auth(channel)))


def _send_slack(channel, type_, title, msg, ts):
    icon = SLACK_ICONS.get(type_, ':bell:')
    payload = {'text': f'{icon} *{DEFAULT_TITLE}* - {msg}'}
    return _result(requests.post(_field(channel, 'url'), json=payload,
                                 timeout=TIMEOUT, auth=_legacy_auth(channel)))


def _send_ntfy(channel, type_, title, msg, ts):
    headers = {
        'X-Title': titled('ntfy', title),
        'X-Priority': '4' if type_ in ('warning', 'error') else '3',
        'X-Tags': NTFY_TAGS.get(type_, 'bell'),
    }
    return _result(requests.post(_field(channel, 'url'), data=msg.encode('utf-8'),
                                 headers=headers, timeout=TIMEOUT, auth=_legacy_auth(channel)))


def _send_unifiedpush(channel, type_, title, msg, ts):
    payload = {'event': type_, 'source': titled('unifiedpush', title),
               'message': msg, 'timestamp': ts}
    return _result(requests.post(_field(channel, 'url'), json=payload, timeout=TIMEOUT))


def _send_generic(channel, type_, title, msg, ts):
    payload = {'event': type_, 'message': msg, 'timestamp': ts}
    return _result(requests.post(_field(channel, 'url'), json=payload,
                                 timeout=TIMEOUT, auth=_legacy_auth(channel)))


def gotify_url(base: str) -> str:
    return urljoin(str(base or '').strip().rstrip('/') + '/', 'message')


def _send_gotify(channel, type_, title, msg, ts):
    payload = {
        'title': _title_of(title),
        'message': msg,
        'priority': GOTIFY_PRIORITIES.get(type_, 3),
    }
    resp = requests.post(gotify_url(_field(channel, 'url')), json=payload,
                         headers={'X-Gotify-Key': _field(channel, 'token')}, timeout=TIMEOUT)
    return _result(resp)


def pushover_priority(channel, type_) -> int:
    raw = channel.get('priority')
    if raw in (None, ''):
        return 1 if type_ == 'error' else 0
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 1 if type_ == 'error' else 0
    return max(-2, min(2, value))


def _pushover_body(channel, type_, title, msg):
    priority = pushover_priority(channel, type_)
    body = {
        'token': _field(channel, 'token'),
        'user': _field(channel, 'token2'),
        'title': _clip(_title_of(title), PUSHOVER_TITLE_MAX),
        'message': _clip(msg, PUSHOVER_MESSAGE_MAX),
        'priority': priority,
    }
    if priority == 2:
        body['retry'] = PUSHOVER_EMERGENCY_RETRY
        body['expire'] = PUSHOVER_EMERGENCY_EXPIRE
    if channel.get('html'):
        body['html'] = 1
    elif channel.get('monospace'):
        body['monospace'] = 1
    return body


def _pushover_errors(resp):
    try:
        data = resp.json()
    except Exception:
        return ''
    if not isinstance(data, dict):
        return ''
    errors = [str(e) for e in (data.get('errors') or []) if str(e).strip()]
    return '; '.join(errors)


def _send_pushover(channel, type_, title, msg, ts):
    resp = requests.post(PUSHOVER_URL, data=_pushover_body(channel, type_, title, msg), timeout=TIMEOUT)
    if resp.status_code >= 400:
        detail = _pushover_errors(resp)
        return False, detail or _http_error(resp)
    remaining = ''
    try:
        remaining = str(resp.headers.get('X-Limit-App-Remaining') or '').strip()
    except Exception:
        remaining = ''
    return True, f'{remaining} messages remaining this month' if remaining else ''


def _send_pushbullet(channel, type_, title, msg, ts):
    payload = {'type': 'note', 'title': _title_of(title), 'body': msg}
    resp = requests.post(PUSHBULLET_URL, json=payload,
                         headers={'Access-Token': _field(channel, 'token')}, timeout=TIMEOUT)
    return _result(resp)


def telegram_escape(text: str) -> str:
    return (str(text or '').replace('&', '&amp;')
                           .replace('<', '&lt;')
                           .replace('>', '&gt;'))


def _telegram_text(type_, title, msg, ts):
    parts = [f'<b>{telegram_escape(_title_of(title))}</b>']
    if str(msg or '').strip():
        parts.append(telegram_escape(msg))
    if str(ts or '').strip():
        parts.append(telegram_escape(ts))
    return _clip('\n'.join(parts), TELEGRAM_MAX)


def _send_telegram(channel, type_, title, msg, ts):
    token = _field(channel, 'token')
    payload = {
        'chat_id': _field(channel, 'token2'),
        'text': _telegram_text(type_, title, msg, ts),
        'parse_mode': 'HTML',
    }
    if type_ in ('info', 'success'):
        payload['disable_notification'] = True
    resp = requests.post(f'https://api.telegram.org/bot{token}/sendMessage',
                         json=payload, timeout=TIMEOUT)
    return _result(resp)


SENDERS = {
    'discord':    _send_discord,
    'slack':      _send_slack,
    'ntfy':       _send_ntfy,
    'generic':    _send_generic,
    'gotify':     _send_gotify,
    'pushover':   _send_pushover,
    'pushbullet': _send_pushbullet,
    'telegram':   _send_telegram,
    'unifiedpush': _send_unifiedpush,
}


def missing_fields(channel: dict) -> list[str]:
    if not isinstance(channel, dict):
        return []
    return [f for f in required_fields(channel.get('kind')) if not _field(channel, f)]


SECRET_FIELDS = ('token', 'token2', 'password')

# Kinds whose URL is itself the credential: the webhook path is the bearer token.
SECRET_URL_KINDS = ('discord', 'slack', 'ntfy', 'generic')


def scrub(channel: dict, text: str) -> str:
    """Replace a channel's own secrets in text with ***.

    A provider's error often quotes the request it failed to make, so the token or the webhook
    URL ends up inside the message. That message is logged on every failed delivery and shown
    in the interface, which puts a third-party credential somewhere it does not belong.
    """
    if not text or not isinstance(channel, dict):
        return text
    secrets_seen = [str(channel.get(f, '') or '') for f in SECRET_FIELDS]
    url = str(channel.get('url', '') or '')
    if url and str(channel.get('kind', '')).strip().lower() in SECRET_URL_KINDS:
        secrets_seen.append(url)
        try:
            path = urlparse(url).path.strip('/')
        except Exception:
            path = ''
        # The host alone is not a secret, but the path that authenticates the webhook is, and
        # a provider may echo only that part back.
        secrets_seen.extend(seg for seg in path.split('/') if len(seg) >= 8)
    # Longest first, so a secret that contains another is not half-replaced.
    for secret in sorted({s for s in secrets_seen if len(s) >= 8}, key=len, reverse=True):
        text = text.replace(secret, '***')
    return text


def send(channel: dict, type_: str, title: str, msg: str, ts: str) -> tuple[bool, str]:
    ok, err = _send(channel, type_, title, msg, ts)
    return ok, scrub(channel, err)


def _send(channel: dict, type_: str, title: str, msg: str, ts: str) -> tuple[bool, str]:
    if not isinstance(channel, dict):
        return False, 'invalid channel'
    kind = str(channel.get('kind') or '').strip().lower()
    sender = SENDERS.get(kind)
    if sender is None:
        return False, f'unknown channel kind: {kind}' if kind else 'channel has no kind'
    missing = missing_fields(channel)
    if missing:
        return False, 'channel is missing ' + ', '.join(missing)
    try:
        return sender(channel, str(type_ or 'info'), str(title or ''), str(msg or ''), str(ts or ''))
    except requests.exceptions.Timeout:
        return False, f'timed out after {TIMEOUT}s'
    except Exception as e:
        return False, str(e) or e.__class__.__name__

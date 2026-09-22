import os
import re
from functools import lru_cache

from babel import Locale, UnknownLocaleError
from babel.messages.pofile import read_po
from babel.support import Translations
from flask import has_request_context, request
from flask_babel import Babel, get_locale, get_translations
from markupsafe import Markup, escape

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCALE_DIR = os.path.join(ROOT_DIR, 'locale')
DOMAIN = 'messages'
DEFAULT_TAG = 'en'
URL_LOCALE_KEY = 'tm.url_locale'
BROWSER_MARK = 'Used in the browser'

_PLURAL_SAMPLES = tuple(range(0, 201)) + (1000, 10000, 100000, 1000000)
INLINE_TAGS = frozenset({'a', 'b', 'br', 'code', 'em', 'i', 'kbd', 'small', 'span', 'strong', 'u'})
_ATTR_NAME = re.compile(r'^[a-z][a-z0-9-]*$')
_SAFE_HREF = re.compile(r'^(?:https?://|/(?!/)|#)')


def to_tag(identifier: str) -> str:
    return identifier.replace('_', '-')


def to_identifier(tag: str) -> str:
    return tag.replace('-', '_')


def enabled_identifiers(locale_dir: str) -> list:
    try:
        with open(os.path.join(locale_dir, 'LINGUAS'), encoding='utf-8') as fh:
            lines = fh.read().splitlines()
    except OSError:
        return []
    names = []
    for line in lines:
        for name in line.split('#', 1)[0].split():
            if name not in names:
                names.append(name)
    return names


def _catalog_tags(locale_dir: str) -> tuple:
    tags = []
    for name in enabled_identifiers(locale_dir):
        mo = os.path.join(locale_dir, name, 'LC_MESSAGES', DOMAIN + '.mo')
        if not os.path.isfile(mo):
            continue
        try:
            Locale.parse(name)
        except (ValueError, UnknownLocaleError):
            continue
        tags.append(to_tag(name))
    return tuple(tags)


@lru_cache(maxsize=None)
def available_tags(locale_dir: str = None) -> tuple:
    tags = [DEFAULT_TAG]
    for tag in _catalog_tags(locale_dir or LOCALE_DIR):
        if tag not in tags:
            tags.append(tag)
    return tuple(tags)


def normalize(value, tags=None):
    if not value:
        return None
    wanted = str(value).strip().replace('_', '-').lower()
    for tag in tags if tags is not None else available_tags():
        if tag.lower() == wanted:
            return tag
    return None


def _accept_language(tags):
    for value, _quality in request.accept_languages:
        exact = normalize(value, tags)
        if exact:
            return exact
        primary = value.replace('_', '-').split('-')[0].lower()
        matches = [t for t in tags if t.split('-')[0].lower() == primary]
        if len(matches) == 1:
            return matches[0]
    return None


def resolve_tag(default_language: str = '') -> str:
    tags = available_tags()
    if not has_request_context():
        return normalize(default_language, tags) or DEFAULT_TAG
    for candidate in (request.environ.get(URL_LOCALE_KEY), request.args.get('lang')):
        tag = normalize(candidate, tags)
        if tag:
            return tag
    if request.headers.get('X-Api-Key'):
        return DEFAULT_TAG
    tag = normalize(default_language, tags)
    if tag:
        return tag
    return _accept_language(tags) or DEFAULT_TAG


def code_for(tag: str, tags=None) -> str:
    tags = available_tags() if tags is None else tags
    primary = tag.split('-')[0]
    if sum(1 for t in tags if t.split('-')[0] == primary) > 1:
        return tag.upper()
    return primary.upper()


REGION_FOR_SCRIPT = {'Hans': 'CN', 'Hant': 'TW', 'Latn': '', 'Cyrl': ''}
REGION_FOR_LANGUAGE = {
    'ar': '', 'bn': 'BD', 'cs': 'CZ', 'da': 'DK', 'de': 'DE', 'el': 'GR', 'es': 'ES',
    'fa': 'IR', 'fi': 'FI', 'fr': 'FR', 'he': 'IL', 'hi': 'IN', 'hu': 'HU', 'id': 'ID',
    'it': 'IT', 'ja': 'JP', 'ko': 'KR', 'nb': 'NO', 'nl': 'NL', 'nn': 'NO', 'no': 'NO',
    'pl': 'PL', 'pt': 'PT', 'ro': 'RO', 'ru': 'RU', 'sk': 'SK', 'sl': 'SI', 'sr': 'RS',
    'sv': 'SE', 'th': 'TH', 'tr': 'TR', 'uk': 'UA', 'vi': 'VN', 'zh': 'CN',
}


def region_for(tag: str) -> str:
    parts = tag.replace('_', '-').split('-')
    language = parts[0].lower()
    if language == DEFAULT_TAG:
        return ''
    for part in parts[1:]:
        if len(part) == 2 and part.isalpha():
            return part.upper()
        if len(part) == 4 and part.isalpha():
            region = REGION_FOR_SCRIPT.get(part.title())
            if region:
                return region
    return REGION_FOR_LANGUAGE.get(language, '')


def flag_emoji(region: str) -> str:
    code = str(region or '').strip().upper()
    if len(code) != 2 or not code.isalpha():
        return ''
    return ''.join(chr(0x1F1E6 + ord(letter) - 65) for letter in code)


def language_options() -> list:
    options = []
    tags = available_tags()
    for tag in tags:
        identifier = to_identifier(tag)
        try:
            name = Locale.parse(identifier).get_display_name(identifier) or tag
        except (ValueError, UnknownLocaleError):
            name = tag
        options.append({'tag': tag, 'name': name[:1].upper() + name[1:],
                        'code': code_for(tag, tags), 'region': region_for(tag)})
    return options


def current_tag() -> str:
    locale = get_locale()
    return to_tag(str(locale)) if locale else DEFAULT_TAG


def text_direction(tag: str) -> str:
    try:
        order = Locale.parse(to_identifier(tag)).character_order
    except (ValueError, UnknownLocaleError):
        return 'ltr'
    return 'rtl' if order == 'right-to-left' else 'ltr'


def _plural_map(identifier: str, translations) -> dict:
    try:
        rule = Locale.parse(identifier).plural_form
    except (ValueError, UnknownLocaleError):
        rule = Locale.parse(DEFAULT_TAG).plural_form
    plural = getattr(translations, 'plural', None)
    if plural is None:
        return {'one': 0, 'other': 1}
    mapping = {}
    for n in _PLURAL_SAMPLES:
        mapping.setdefault(rule(n), plural(n))
    return mapping


@lru_cache(maxsize=None)
def browser_keys(locale_dir: str = None):
    path = os.path.join(locale_dir or LOCALE_DIR, DOMAIN + '.pot')
    try:
        with open(path, 'rb') as fh:
            template = read_po(fh)
    except (OSError, ValueError):
        return None
    keys = set()
    for message in template:
        if not message.id or BROWSER_MARK not in (message.auto_comments or []):
            continue
        msgid = message.id[0] if isinstance(message.id, (list, tuple)) else message.id
        keys.add(message.context + '\x04' + msgid if message.context else msgid)
    return frozenset(keys)


@lru_cache(maxsize=None)
def client_catalog(tag: str, locale_dir: str = None) -> dict:
    identifier = to_identifier(tag)
    translations = Translations.load(locale_dir or LOCALE_DIR, [identifier], DOMAIN)
    wanted = browser_keys(locale_dir)
    messages = {}
    for key, value in getattr(translations, '_catalog', {}).items():
        msgid = key[0] if isinstance(key, tuple) else key
        if wanted is not None and msgid not in wanted:
            continue
        if isinstance(key, tuple):
            msgid, index = key
            forms = messages.setdefault(msgid, [])
            if not isinstance(forms, list):
                continue
            forms.extend([''] * (index + 1 - len(forms)))
            forms[index] = value
        elif key and value:
            messages[key] = value
    return {
        'locale': tag,
        'plural': _plural_map(identifier, translations),
        'messages': messages,
    }


class LocalePrefixMiddleware:
    def __init__(self, wsgi_app, tags=None):
        self.wsgi_app = wsgi_app
        self.tags = tags

    def __call__(self, environ, start_response):
        path = environ.get('PATH_INFO', '')
        if path.startswith('/'):
            segment, slash, rest = path[1:].partition('/')
            tags = self.tags() if self.tags else available_tags()
            if segment and segment in tags:
                environ['PATH_INFO'] = '/' + rest if slash else '/'
                environ['SCRIPT_NAME'] = environ.get('SCRIPT_NAME', '') + '/' + segment
                environ[URL_LOCALE_KEY] = segment
        return self.wsgi_app(environ, start_response)


def inline_tag(name, text='', **attrs):
    if name not in INLINE_TAGS:
        raise ValueError(f'tag() does not build <{name}>')
    parts = [name]
    for key, value in attrs.items():
        attr = key.rstrip('_').replace('_', '-')
        if not _ATTR_NAME.match(attr) or attr.startswith('on') or attr in ('style-src', 'srcdoc'):
            raise ValueError(f'tag() does not set the attribute {attr}')
        value = '' if value is None else str(value)
        if attr == 'href' and not _SAFE_HREF.match(value.strip()):
            raise ValueError('tag() only links to http(s), relative or fragment addresses')
        parts.append(f'{attr}="{escape(value)}"')
    opening = Markup('<' + ' '.join(parts) + '>')
    if name == 'br':
        return opening
    return opening + escape(text) + Markup(f'</{name}>')


def install_escaped_gettext(jinja_env):
    jinja_env.install_gettext_callables(
        gettext=lambda s: escape(get_translations().ugettext(s)),
        ngettext=lambda s, p, n: escape(get_translations().ungettext(s, p, n)),
        newstyle=True,
        pgettext=lambda c, s: escape(get_translations().upgettext(c, s)),
        npgettext=lambda c, s, p, n: escape(get_translations().unpgettext(c, s, p, n)),
    )


def init_app(app, default_language):
    app.config['BABEL_DEFAULT_LOCALE'] = DEFAULT_TAG
    app.config['BABEL_TRANSLATION_DIRECTORIES'] = LOCALE_DIR
    app.config['BABEL_DOMAIN'] = DOMAIN

    def _saved():
        try:
            return normalize(default_language()) or ''
        except Exception:
            return ''

    def _select():
        return to_identifier(resolve_tag(_saved()))

    babel = Babel(app, locale_selector=_select)
    install_escaped_gettext(app.jinja_env)
    app.jinja_env.globals['tag'] = inline_tag
    app.jinja_env.filters['flag'] = flag_emoji

    @app.context_processor
    def _inject_locale():
        tag = current_tag()
        return {
            'html_lang': tag,
            'html_dir': text_direction(tag),
            'html_lang_code': code_for(tag),
            'html_lang_region': region_for(tag),
            'i18n_catalog': client_catalog(tag),
            'language_options': language_options(),
            'language_setting': _saved(),
        }

    return babel

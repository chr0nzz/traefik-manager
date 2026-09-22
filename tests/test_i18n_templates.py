import os
import sys
from html.parser import HTMLParser

import pytest
from babel.messages.catalog import Catalog
from babel.messages.mofile import write_mo
from flask import render_template
from flask_babel import force_locale, get_domain
from jinja2 import Environment, nodes
from markupsafe import Markup

from core import i18n

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'i18n'))

import tmi18n  # noqa: E402

OPEN, CLOSE = '⟦', '⟧'


def test_tag_builds_only_safe_inline_markup():
    assert i18n.inline_tag('code', 'A<B', class_='font-mono') == Markup('<code class="font-mono">A&lt;B</code>')
    assert i18n.inline_tag('a', 'docs', href='https://example.com', target='_blank') == \
        Markup('<a href="https://example.com" target="_blank">docs</a>')
    assert i18n.inline_tag('br') == Markup('<br>')
    assert i18n.inline_tag('strong', Markup('<i>kept</i>')) == Markup('<strong><i>kept</i></strong>')
    assert i18n.inline_tag('span', '', id='x', style='a"b') == Markup('<span id="x" style="a&#34;b"></span>')


@pytest.mark.parametrize('name, attrs', [
    ('script', {}),
    ('img', {'src': 'x'}),
    ('a', {'href': 'javascript:alert(1)'}),
    ('a', {'href': ' JavaScript:alert(1)'}),
    ('a', {'href': '//evil.example'}),
    ('a', {'href': 'data:text/html,x'}),
    ('b', {'onclick': 'x'}),
    ('b', {'onmouseover_': 'x'}),
    ('b', {'bad name': 'x'}),
])
def test_tag_refuses_anything_else(name, attrs):
    with pytest.raises(ValueError):
        i18n.inline_tag(name, 'x', **attrs)


def _template_calls():
    env = Environment(extensions=['jinja2.ext.i18n'])
    for dirpath, _dirs, files in os.walk(os.path.join(ROOT, 'templates')):
        for name in files:
            if name.endswith('.html'):
                path = os.path.join(dirpath, name)
                with open(path, encoding='utf-8') as fh:
                    tree = env.parse(fh.read())
                for call in tree.find_all(nodes.Call):
                    yield os.path.relpath(path, ROOT), call


def test_every_tag_call_in_the_templates_is_allowed():
    count = 0
    for where, call in _template_calls():
        if not (isinstance(call.node, nodes.Name) and call.node.name == 'tag'):
            continue
        count += 1
        value = lambda n: n.value if isinstance(n, nodes.Const) else 'x'
        i18n.inline_tag(*[value(a) for a in call.args], **{k.key: value(k.value) for k in call.kwargs})
    assert count > 100


def test_every_message_in_the_templates_is_a_literal():
    for where, call in _template_calls():
        if not (isinstance(call.node, nodes.Name) and call.node.name in ('_', 'gettext', 'pgettext', 'ngettext', 'npgettext')):
            continue
        texts = call.args[:2] if call.node.name in ('pgettext', 'ngettext') else call.args[:1]
        if call.node.name == 'npgettext':
            texts = call.args[:3]
        for arg in texts:
            assert isinstance(arg, nodes.Const) and isinstance(arg.value, str), f'{where}:{call.lineno} passes a non-literal message'


@pytest.mark.parametrize('src, expected', [
    ('<p>Save the route</p>', ['"Save the route" is not marked']),
    ('<p title="Delete this route">1</p>', ['title="Delete this route" is not marked']),
    ('<p>{{ _("Save the route") }}</p>', []),
    ('<p translate="no">Save the route</p>', []),
    ('<code>Save the route</code>', []),
    ('<span class="font-mono">Save the route</span>', []),
    ('<p>Traefik Manager</p><p>ACME_JSON_PATH</p><p>example.com, other.net</p><p>v1.14.0</p>', []),
    ('<input placeholder="websecure"><input placeholder="optional">', ['placeholder="optional" is not marked']),
    ('<script>const x = "Save the route";</script>', []),
    ('<button class="font-mono" title="Traefik Manager version">v1</button>', ['title="Traefik Manager version" is not marked']),
    ('<div data-note="These routes are read-only here."></div>', ['data-note="These routes are read-only here." is not marked']),
    ('<input class="font-mono" placeholder="^/foo/(.*)">', []),
    ('<div class="notranslate" title="Keep this"></div>', []),
])
def test_untranslated_text_is_found(src, expected):
    messages = [p.message for p in tmi18n.untranslated_in(src, 'x.html')]
    assert len(messages) == len(expected)
    for got, want in zip(messages, expected):
        assert want in got


def test_the_templates_have_no_untranslated_text():
    assert tmi18n.check_untranslated() == []


def _pseudo_catalogue(locale_dir):
    template = tmi18n.read_catalog(tmi18n.POT_PATH)
    catalog = Catalog(locale='de')
    for message in template:
        if not message.id:
            continue
        if isinstance(message.id, (list, tuple)):
            forms = tuple(OPEN + f + CLOSE for f in (message.id[0], message.id[1]))
            catalog.add(message.id, forms, context=message.context)
        else:
            catalog.add(message.id, OPEN + message.id + CLOSE, context=message.context)
    target = locale_dir / 'de' / 'LC_MESSAGES'
    target.mkdir(parents=True)
    with open(target / 'messages.mo', 'wb') as fh:
        write_mo(fh, catalog)


class _Text(HTMLParser):
    SKIP = {'script', 'style', 'code', 'pre', 'kbd', 'textarea', 'svg', 'title'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.found = []
        self.depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in tmi18n.VOID_TAGS:
            return
        a = dict(attrs)
        mono = 'font-mono' in (a.get('class') or '') or a.get('translate') == 'no'
        self.stack.append((tag, mono))
        for key in ('title', 'placeholder', 'aria-label', 'alt', 'data-tip'):
            if a.get(key) and not self._skipped() and not a[key].startswith(OPEN):
                self.found.append(a[key])

    def handle_endtag(self, tag):
        for k in range(len(self.stack) - 1, -1, -1):
            if self.stack[k][0] == tag:
                del self.stack[k:]
                break

    def _skipped(self):
        return any(t in self.SKIP or mono for t, mono in self.stack)

    def handle_data(self, data):
        outside = []
        for ch in data:
            if ch == OPEN:
                self.depth += 1
            elif ch == CLOSE:
                self.depth = max(0, self.depth - 1)
            elif self.depth == 0:
                outside.append(ch)
        text = ' '.join(''.join(outside).split())
        if text and not self._skipped():
            self.found.append(text)


@pytest.fixture
def pseudo(tmp_path, app_module, monkeypatch):
    _pseudo_catalogue(tmp_path)
    app = app_module.app
    monkeypatch.setattr(app.extensions['babel'], 'translation_directories', [str(tmp_path)])
    with app.test_request_context('/'):
        monkeypatch.setattr(get_domain(), 'cache', {})
    return app


INDEX = dict(apps=[], domains=['a.com', 'b.com'], middlewares=[{'name': 'auth', 'type': 'http', 'configFile': 'd.yml'}],
             auth_enabled=True, no_auth=True, login_time='', multi_config=True, config_paths_list=[],
             config_dir_set=True, cert_resolvers=['le'], crowdsec_enabled=True, ui_prefs={})
LOGIN = [
    dict(error='x', show_local=True, oidc_enabled=True, oidc_display_name='SSO', temp_password_hint=True),
    dict(setup_mode=True, otp_required=True, defaults={}, temp_password_mode=True, detected_self_domain='tm.example.com',
         detected_tabs=[]),
    dict(setup_mode=True, reset_mode=True, defaults={}, detected_tabs=[]),
    dict(force_change_mode=True, error='x'),
    dict(otp_mode=True, error='x'),
]


@pytest.mark.parametrize('template, ctx', [('index.html', INDEX)] + [('login.html', c) for c in LOGIN])
def test_every_visible_string_is_translated(pseudo, app_module, template, ctx):
    with pseudo.test_request_context('/'), force_locale('de'):
        context = dict(ctx)
        if template == 'index.html':
            context['settings'] = app_module.load_settings()
        html = render_template(template, **context)
    parser = _Text()
    parser.feed(html)
    native_names = {o['name'] for o in i18n.language_options()}
    test_data = {'x', 'SSO', 'auth', 'le', 'tm.example.com'}
    missed = [t for t in parser.found if not tmi18n.is_literal(t) and t not in native_names | test_data]
    assert missed == [], missed[:20]
    assert html.count(OPEN) > (400 if template == 'index.html' else 3)

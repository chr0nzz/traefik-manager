import json
import re

import pytest
from babel.messages.catalog import Catalog
from babel.messages.mofile import write_mo
from flask_babel import force_locale, get_domain

from core import i18n

PAYLOAD = '<img src=x onerror=alert(1)>'


def _hostile_catalogue(locale_dir):
    catalog = Catalog(locale='de')
    catalog.add('Save', PAYLOAD)
    catalog.add('Hi %(name)s', '<b onmouseover=alert(1)>Hallo %(name)s</b>')
    catalog.add(('%(num)d route', '%(num)d routes'), ('<script>alert(1)</script>%(num)d', '<script>alert(2)</script>%(num)d'))
    catalog.add('Delete', '"><svg onload=alert(1)>', context='button')
    catalog.add('Quote', '</script><script>alert(1)</script>')
    target = locale_dir / 'de' / 'LC_MESSAGES'
    target.mkdir(parents=True)
    with open(target / 'messages.mo', 'wb') as fh:
        write_mo(fh, catalog)


@pytest.fixture
def hostile(tmp_path, app_module, monkeypatch):
    _hostile_catalogue(tmp_path)
    app = app_module.app
    monkeypatch.setattr(app.extensions['babel'], 'translation_directories', [str(tmp_path)])
    i18n.client_catalog.cache_clear()
    with app.test_request_context('/'):
        monkeypatch.setattr(get_domain(), 'cache', {})
    yield app, tmp_path
    i18n.client_catalog.cache_clear()


TEMPLATE = (
    "{{ _('Save') }}|"
    "{% trans %}Save{% endtrans %}|"
    "{% trans name=name %}Hi {{ name }}{% endtrans %}|"
    "{{ ngettext('%(num)d route', '%(num)d routes', 2) }}|"
    "{{ pgettext('button', 'Delete') }}|"
    "<a title=\"{{ _('Save') }}\">x</a>"
)


def test_translations_render_as_text_in_templates(hostile):
    app, _ = hostile
    with app.test_request_context('/'), force_locale('de'):
        html = app.jinja_env.from_string(TEMPLATE).render(name='<i>eve</i>')
    assert '<img' not in html and '<script' not in html and '<svg' not in html and '<b ' not in html
    assert '&lt;img src=x onerror=alert(1)&gt;' in html
    assert '&lt;script&gt;alert(2)&lt;/script&gt;2' in html
    assert '&#34;&gt;&lt;svg onload=alert(1)&gt;' in html
    assert 'Hallo &lt;i&gt;eve&lt;/i&gt;' in html
    assert 'title="&lt;img src=x onerror=alert(1)&gt;"' in html


def test_english_still_renders_normally(app_module):
    app = app_module.app
    with app.test_request_context('/'):
        html = app.jinja_env.from_string(TEMPLATE).render(name='<i>eve</i>')
    assert html.startswith('Save|Save|Hi &lt;i&gt;eve&lt;/i&gt;|2 routes|Delete|')


def test_inline_catalogue_cannot_close_its_script_tag(hostile, app_module):
    app, tmp_path = hostile
    data = i18n.client_catalog('de', str(tmp_path))
    assert data['messages']['Quote'] == '</script><script>alert(1)</script>'
    with app.test_request_context('/'):
        html = app.jinja_env.from_string(
            '<script type="application/json" id="i18n-catalog">{{ c | tojson }}</script>').render(c=data)
    body = re.search(r'id="i18n-catalog">(.*)</script>$', html, re.S).group(1)
    assert '</script' not in body.lower()
    assert '<' not in body
    assert json.loads(body)['messages']['Quote'] == '</script><script>alert(1)</script>'


def test_the_shim_never_writes_html(tmp_path):
    import os
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static', 'js', 'i18n.js')).read()
    assert 'innerHTML' not in src and 'insertAdjacentHTML' not in src and 'document.write' not in src
    assert 'eval(' not in src and 'new Function' not in src


def test_escaping_is_installed_after_flask_babel(app_module):
    env = app_module.app.jinja_env
    with app_module.app.test_request_context('/'):
        rendered = env.from_string("{{ _('<b>x</b>') }}").render()
    assert rendered == '&lt;b&gt;x&lt;/b&gt;'


def test_a_hostile_language_tag_is_never_reflected(client):
    for value in ('"><script>', 'de"><script>alert(1)</script>', '../../etc/passwd'):
        html = client.get('/', query_string={'lang': value}).get_data(as_text=True)
        assert '<html lang="en"' in html
        assert 'alert(1)' not in html

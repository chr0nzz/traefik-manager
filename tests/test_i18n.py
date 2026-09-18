import json
import re

import pytest
from babel.messages.catalog import Catalog
from babel.messages.mofile import write_mo

from core import i18n
from core import settings as settings_mod

HDR = {'X-CSRF-Token': 'testtoken', 'X-Requested-With': 'fetch'}
PLANNED = ('en', 'de', 'fr', 'es', 'zh-Hans', 'ru')


def _compile(locale_dir, identifier, messages):
    catalog = Catalog(locale=identifier)
    for msgid, msgstr in messages:
        if isinstance(msgid, tuple) and len(msgid) == 3:
            context, singular, plural = msgid
            catalog.add((singular, plural), msgstr, context=context)
        elif isinstance(msgid, tuple) and len(msgid) == 2 and isinstance(msgstr, tuple):
            catalog.add(msgid, msgstr)
        elif isinstance(msgid, tuple):
            context, text = msgid
            catalog.add(text, msgstr, context=context)
        else:
            catalog.add(msgid, msgstr)
    target = locale_dir / identifier / 'LC_MESSAGES'
    target.mkdir(parents=True, exist_ok=True)
    with open(target / 'messages.mo', 'wb') as fh:
        write_mo(fh, catalog)


@pytest.fixture
def locale_dir(tmp_path):
    i18n.available_tags.cache_clear()
    i18n.client_catalog.cache_clear()
    yield tmp_path
    i18n.available_tags.cache_clear()
    i18n.client_catalog.cache_clear()


@pytest.fixture
def with_languages(monkeypatch):
    monkeypatch.setattr(i18n, 'available_tags', lambda locale_dir=None: ('en', 'de', 'zh-Hans'))


def _catalog_block(html):
    match = re.search(r'<script type="application/json" id="i18n-catalog">(.*?)</script>', html, re.S)
    assert match, 'catalogue block missing'
    return json.loads(match.group(1))


def test_index_renders_english_with_catalogue(client):
    html = client.get('/').get_data(as_text=True)
    assert '<html lang="en" dir="ltr"' in html
    data = _catalog_block(html)
    assert data['locale'] == 'en'
    assert data['messages'] == {}
    assert html.index('/static/js/i18n.js') < html.index('/static/js/core.js')


def test_login_renders_lang_and_catalogue(anon_client):
    html = anon_client.get('/login').get_data(as_text=True)
    assert '<html lang="en" dir="ltr">' in html
    assert _catalog_block(html)['locale'] == 'en'
    assert '/static/js/i18n.js' in html


def test_english_prefix_serves_the_same_page(client):
    plain = client.get('/')
    prefixed = client.get('/en/')
    assert plain.status_code == prefixed.status_code == 200
    assert '<html lang="en"' in prefixed.get_data(as_text=True)


def test_prefix_carries_into_redirects(anon_client):
    resp = anon_client.get('/en/')
    assert resp.status_code == 302
    assert resp.headers['Location'].startswith('/en/login')


def test_unknown_prefix_is_not_a_language(client):
    assert client.get('/xx/').status_code == 404


def test_disabled_language_prefix_is_not_served(client):
    assert client.get('/de/').status_code == 404


def test_lang_query_accepts_only_available(client):
    html = client.get('/?lang=de').get_data(as_text=True)
    assert '<html lang="en"' in html


def test_prefix_selects_language(client, with_languages):
    html = client.get('/de/').get_data(as_text=True)
    assert '<html lang="de" dir="ltr"' in html
    assert _catalog_block(html)['locale'] == 'de'


def test_prefix_appends_to_base_path():
    seen = {}

    def inner(environ, start_response):
        seen.update(environ)
        return []

    mw = i18n.LocalePrefixMiddleware(inner, tags=lambda: ('en', 'de'))
    mw({'PATH_INFO': '/de/login', 'SCRIPT_NAME': '/tm'}, None)
    assert seen['SCRIPT_NAME'] == '/tm/de'
    assert seen['PATH_INFO'] == '/login'
    assert seen[i18n.URL_LOCALE_KEY] == 'de'

    seen.clear()
    mw({'PATH_INFO': '/de', 'SCRIPT_NAME': ''}, None)
    assert seen['PATH_INFO'] == '/'

    seen.clear()
    mw({'PATH_INFO': '/delete', 'SCRIPT_NAME': ''}, None)
    assert seen['PATH_INFO'] == '/delete'
    assert i18n.URL_LOCALE_KEY not in seen


def test_no_route_starts_with_a_language_code(app_module):
    first_segments = {rule.rule.strip('/').split('/')[0] for rule in app_module.app.url_map.iter_rules()}
    assert not first_segments & set(PLANNED)


@pytest.mark.parametrize('kwargs, expected', [
    ({'path': '/de/', 'headers': {'Accept-Language': 'zh-CN'}}, 'de'),
    ({'path': '/?lang=zh-hans', 'headers': {'Cookie': 'tm_lang=de'}}, 'zh-Hans'),
    ({'path': '/', 'headers': {'Cookie': 'tm_lang=de'}, 'default': 'zh-Hans'}, 'zh-Hans'),
    ({'path': '/', 'headers': {'Accept-Language': 'de'}, 'default': 'zh-Hans'}, 'zh-Hans'),
    ({'path': '/', 'headers': {'Accept-Language': 'de-AT,en;q=0.5'}}, 'de'),
    ({'path': '/', 'headers': {'Accept-Language': 'zh-CN'}}, 'zh-Hans'),
    ({'path': '/', 'headers': {'Accept-Language': 'ja'}}, 'en'),
    ({'path': '/', 'headers': {'Cookie': 'tm_lang=de'}}, 'en'),
])
def test_resolve_order(app_module, with_languages, kwargs, expected):
    path = kwargs['path']
    environ = {}
    if path.startswith('/de/'):
        environ[i18n.URL_LOCALE_KEY] = 'de'
        path = path[3:]
    with app_module.app.test_request_context(path, headers=kwargs['headers'], environ_base=environ):
        assert i18n.resolve_tag(kwargs.get('default', '')) == expected


def test_linguas_gates_compiled_catalogues(locale_dir):
    _compile(locale_dir, 'de', [('Save', 'Speichern')])
    _compile(locale_dir, 'fr', [('Save', 'Enregistrer')])
    assert i18n.available_tags(str(locale_dir)) == ('en',)

    (locale_dir / 'LINGUAS').write_text('# enabled\nde zh_Hans\nfr  # after review\n')
    i18n.available_tags.cache_clear()
    assert i18n.available_tags(str(locale_dir)) == ('en', 'de', 'fr')


def test_client_catalog_shapes_messages(locale_dir):
    _compile(locale_dir, 'de', [
        ('Save', 'Speichern'),
        ('Empty', ''),
        (('status', 'Down'), 'Ausgefallen'),
        (('{n} router', '{n} routers'), ('{n} Router', '{n} Router')),
    ])
    data = i18n.client_catalog('de', str(locale_dir))
    assert data['locale'] == 'de'
    assert data['messages']['Save'] == 'Speichern'
    assert 'Empty' not in data['messages']
    assert data['messages']['statusDown'] == 'Ausgefallen'
    assert data['messages']['{n} router'] == ['{n} Router', '{n} Router']
    assert data['plural'] == {'one': 0, 'other': 1}


def test_plural_map_follows_the_catalogue(locale_dir):
    _compile(locale_dir, 'ru', [(('{n} route', '{n} routes'), ('a', 'b', 'c'))])
    _compile(locale_dir, 'zh_Hans', [(('{n} route', '{n} routes'), ('x',))])
    assert i18n.client_catalog('ru', str(locale_dir))['plural'] == {'many': 2, 'one': 0, 'few': 1}
    assert i18n.client_catalog('zh-Hans', str(locale_dir))['plural'] == {'other': 0}


def test_language_options_use_native_names(with_languages):
    assert i18n.language_options() == [
        {'tag': 'en', 'name': 'English', 'flag': '\U0001F1FA\U0001F1F8'},
        {'tag': 'de', 'name': 'Deutsch', 'flag': '\U0001F1E9\U0001F1EA'},
        {'tag': 'zh-Hans', 'name': '中文 (简体)', 'flag': '\U0001F1E8\U0001F1F3'},
    ]


def test_text_direction():
    assert i18n.text_direction('de') == 'ltr'
    assert i18n.text_direction('ar') == 'rtl'
    assert i18n.text_direction('not a locale') == 'ltr'


def test_save_language_rejects_unavailable(client):
    resp = client.post('/api/settings/language', json={'default_language': 'de'}, headers=HDR)
    assert resp.status_code == 400
    assert settings_mod.load_settings()['default_language'] == ''


def test_save_language_round_trip(client, with_languages):
    resp = client.post('/api/settings/language', json={'default_language': 'ZH_hans'}, headers=HDR)
    assert resp.get_json() == {'success': True, 'default_language': 'zh-Hans'}
    assert settings_mod.load_settings()['default_language'] == 'zh-Hans'

    client.post('/api/settings/theme', json={'default_theme': 'light'}, headers=HDR)
    assert settings_mod.load_settings()['default_language'] == 'zh-Hans'

    data = client.get('/api/settings').get_json()
    assert data['default_language'] == 'zh-Hans'
    assert [o['tag'] for o in data['available_languages']] == ['en', 'de', 'zh-Hans']

    resp = client.post('/api/settings/language', json={'default_language': ''}, headers=HDR)
    assert resp.get_json()['default_language'] == ''
    assert settings_mod.load_settings()['default_language'] == ''


def test_saved_language_applies_without_other_hints(client, with_languages):
    client.post('/api/settings/language', json={'default_language': 'de'}, headers=HDR)
    try:
        html = client.get('/').get_data(as_text=True)
        assert '<html lang="de"' in html
    finally:
        client.post('/api/settings/language', json={'default_language': ''}, headers=HDR)



def test_flags_come_from_the_likely_territory():
    assert i18n.flag_for('fr') == '\U0001F1EB\U0001F1F7'
    assert i18n.flag_for('ru') == '\U0001F1F7\U0001F1FA'
    assert i18n.flag_for('es') == '\U0001F1EA\U0001F1F8'
    assert i18n.flag_for('not a locale') == ''


def _between(html, start, end):
    i = html.index(start)
    return html[i:html.index(end, i)]


def test_navbar_picker_is_the_first_icon(client, with_languages):
    html = client.get('/').get_data(as_text=True)
    nav = _between(html, 'id="navActions"', 'id="navMoreWrap"')
    assert nav.index('id="langPickerWrap"') < nav.index('nav-docs-link')
    picker = _between(nav, 'id="langPickerWrap"', 'nav-docs-link')
    assert 'class="tm-flag"' in picker
    assert "setLanguage('')" in picker
    assert picker.count('onclick="setLanguage(this.dataset.lang)"') == 3
    assert 'data-lang="zh-Hans"' in picker


def test_settings_lists_every_language_and_follow_system(client, with_languages):
    client.post('/api/settings/language', json={'default_language': 'de'}, headers=HDR)
    try:
        html = client.get('/').get_data(as_text=True)
    finally:
        client.post('/api/settings/language', json={'default_language': ''}, headers=HDR)
    section = _between(html, 'id="languageSection"', 'id="geoipSection"')
    assert section.count('class="sc-set lang-row') == 4
    assert 'lang-row active" data-lang="de"' in section
    assert 'Follow system' in section
    assert 'window.TM_LANGUAGE = "de"' in html


def test_follow_system_is_marked_when_nothing_is_saved(client):
    html = client.get('/').get_data(as_text=True)
    section = _between(html, 'id="languageSection"', 'id="geoipSection"')
    assert 'lang-row active" onclick="setLanguage(\'\')"' in section
    assert 'window.TM_LANGUAGE = ""' in html


def test_interface_is_split_into_sub_sections(client):
    html = client.get('/').get_data(as_text=True)
    for key in ('general', 'dashboard', 'navbar', 'tabs'):
        assert f'id="ui-sub-{key}"' in html
        assert f'id="msc-ui-{key}"' in html
        assert f"openSettingsChild('ui', '{key}')" in html
    general = _between(html, 'id="ui-sub-general"', 'id="ui-sub-dashboard"')
    assert 'id="languageSection"' in general
    navbar = _between(html, 'id="ui-sub-navbar"', 'id="ui-sub-tabs"')
    assert 'id="toggle-lang-picker"' in navbar


def test_the_picker_can_be_hidden(client):
    assert settings_mod.sanitize_ui_prefs({'showLangPicker': 0}) == {'showLangPicker': False}
    html = client.get('/').get_data(as_text=True)
    assert "if (!pref('showLangPicker', true))   d.add('tm-hide-lang');" in html
    assert 'html.tm-hide-lang .nav-lang-picker { display: none !important; }' in html

import glob
import os
import re
import shutil
import sys
import textwrap

import pytest
from babel.messages.catalog import Catalog
from babel.messages.mofile import write_mo
from babel.messages.pofile import write_po

from core import i18n

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'i18n'))

import tmi18n  # noqa: E402

JS_FILES = sorted(glob.glob(os.path.join(ROOT, 'static', 'js', '*.js')))
needs_node = pytest.mark.skipif(
    not (shutil.which('node') and os.path.isdir(os.path.join(ROOT, 'scripts', 'i18n', 'node_modules', 'acorn'))),
    reason='node and acorn are needed for JS extraction (make i18n-tools)')


def _extract(tmp_path, code):
    (tmp_path / 'static' / 'js').mkdir(parents=True)
    (tmp_path / 'templates').mkdir()
    (tmp_path / 'static' / 'js' / 'a.js').write_text(textwrap.dedent(code), encoding='utf-8')
    return tmi18n.run_js_extractor(str(tmp_path))


@needs_node
@pytest.mark.parametrize('code', [
    "el.innerHTML = t('Saved');",
    "el.outerHTML = tn('{n} route', '{n} routes', n);",
    "html = `<b>${t('Saved')}</b>`;",
    "html = '<span>' + t('Saved') + '</span>';",
    "html = `<p>${ok ? t('Saved') : t('Failed')}</p>`;",
    "el.innerHTML = ok ? t('Saved') : '';",
    "el.insertAdjacentHTML('beforeend', tc('status', 'Down'));",
])
def test_plain_translations_in_html_are_rejected(tmp_path, code):
    result = _extract(tmp_path, code)
    assert any('placed into HTML unescaped' in e for e in result['errors']), result


@needs_node
@pytest.mark.parametrize('code', [
    "showToast(t('Saved'));",
    "el.textContent = t('Saved');",
    "el.title = t('Saved');",
    "el.setAttribute('aria-label', t('Saved'));",
    "html = `<b>${_esc(t('Saved'))}</b>`;",
    "html = `<b>${th('Saved')}</b>`;",
    "el.innerHTML = th('Remove {name}', { name: tmHtml('<code>x</code>') });",
    "el.innerHTML = thn('{n} route', '{n} routes', n);",
    "msg = 'Saved ' + t('now');",
    "msg = `Saved ${t('now')}`;",
    "items.push(t('Saved'));",
])
def test_safe_uses_of_translations_pass(tmp_path, code):
    result = _extract(tmp_path, code)
    assert result['errors'] == [], result


@needs_node
def test_html_helpers_are_extracted(tmp_path):
    result = _extract(tmp_path, """
        a = th('One');
        b = thn('{n} thing', '{n} things', n);
        c = thc('button', 'Two');
    """)
    got = {(m['context'], m['msgid'], m['plural']) for m in result['messages']}
    assert got == {(None, 'One', None), (None, '{n} thing', '{n} things'), ('button', 'Two', None)}


def _catalogues(locale_dir, marked):
    template = Catalog()
    catalog = Catalog(locale='de')
    for msgid, text, browser in (('Save', 'Speichern', True), ('Only on the server', 'Nur Server', False),
                                 ('Down', 'Aus', True)):
        context = 'status' if msgid == 'Down' else None
        template.add(msgid, context=context, auto_comments=[i18n.BROWSER_MARK] if browser and marked else [])
        catalog.add(msgid, text, context=context)
    with open(locale_dir / 'messages.pot', 'wb') as fh:
        write_po(fh, template)
    target = locale_dir / 'de' / 'LC_MESSAGES'
    target.mkdir(parents=True)
    with open(target / 'messages.mo', 'wb') as fh:
        write_mo(fh, catalog)


@pytest.fixture
def fresh_caches():
    i18n.browser_keys.cache_clear()
    i18n.client_catalog.cache_clear()
    yield
    i18n.browser_keys.cache_clear()
    i18n.client_catalog.cache_clear()


def test_the_browser_only_gets_strings_javascript_uses(tmp_path, fresh_caches):
    _catalogues(tmp_path, marked=True)
    messages = i18n.client_catalog('de', str(tmp_path))['messages']
    assert messages == {'Save': 'Speichern', 'status\x04Down': 'Aus'}


def test_without_a_template_the_browser_gets_everything(tmp_path, fresh_caches):
    _catalogues(tmp_path, marked=True)
    (tmp_path / 'messages.pot').unlink()
    messages = i18n.client_catalog('de', str(tmp_path))['messages']
    assert set(messages) == {'Save', 'Only on the server', 'status\x04Down'}


def test_the_real_template_marks_browser_strings(fresh_caches):
    keys = i18n.browser_keys()
    assert keys is not None and 'Could not save the language' in keys
    template = tmi18n.read_catalog(tmi18n.POT_PATH)
    total = sum(1 for m in template if m.id)
    assert len(keys) < total / 10, 'most strings are server rendered and must not be sent to the browser'


def _js_source():
    for path in JS_FILES:
        with open(path, encoding='utf-8') as fh:
            yield os.path.relpath(path, ROOT), fh.read()


def test_there_is_one_escaping_helper():
    defs = [(f, m.start()) for f, src in _js_source() for m in re.finditer(r'function\s+_esc\s*\(', src)]
    assert [f for f, _ in defs] == [os.path.join('static', 'js', 'core.js')], defs


def test_code_never_reads_displayed_text_back():
    pattern = re.compile(r'(textContent|innerText)(\.trim\(\))?\s*[!=]==?\s*[\'"`]')
    hits = [f'{f}:{src[:m.start()].count(chr(10)) + 1}' for f, src in _js_source() for m in pattern.finditer(src)]
    assert hits == [], 'compare a data attribute instead, the text is translated: ' + ', '.join(hits)


def test_no_confirmation_asks_for_a_fixed_word():
    hits = [f for f, src in _js_source() if re.search(r"typeWord:\s*'[A-Z]+'|,\s*'DELETE'\)\)", src)]
    assert hits == [], 'destructive confirmations ask for the name of the thing, or the count for several'


def test_numbers_follow_the_interface_language():
    hits = [f for f, src in _js_source() if re.search(r"toLocale(?:Date|Time)?String\(\s*['\"]", src)]
    assert hits == [], 'use tmNumber / tmDate instead of a hard-coded locale'

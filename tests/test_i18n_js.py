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


@needs_node
@pytest.mark.parametrize('code', [
    "function f(t) { return t('Saved'); }",
    "function f() { const t = el(); return t('Saved'); }",
    "function f() { if (x) { const t = el(); t.textContent = t('Saved'); } }",
    "items.forEach(t => { t.title = t('Saved'); });",
    "for (const t of list) { show(t('Saved')); }",
])
def test_a_local_named_like_a_helper_is_rejected(tmp_path, code):
    result = _extract(tmp_path, code)
    assert any('hidden by a local variable' in e for e in result['errors']), result


@needs_node
@pytest.mark.parametrize('code', [
    "el.style.animation = t('slideOut 0.3s ease forwards');",
    "el.className = t('sig-cell');",
    "el.dataset.state = t('on');",
    "el.classList.add(t('active'));",
    "el.id = ok ? t('a') : t('b');",
    "input.value = t('openid');",
])
def test_translations_never_become_styles_classes_or_ids(tmp_path, code):
    result = _extract(tmp_path, code)
    assert any('must stay untranslated' in e for e in result['errors']), result


@needs_node
@pytest.mark.parametrize('code, fragment', [
    ("t('Every {value} seconds', { seconds: 5 });", 'has no value for {value}'),
    ("t('Removed {n} items');", 'has no value for {n}'),
    ("th('Saved', { name: x });", 'no such placeholder'),
    ("tc('button', 'Open {name}', { other: 1 });", 'has no value for {name}'),
])
def test_placeholders_and_values_must_match(tmp_path, code, fragment):
    result = _extract(tmp_path, code)
    assert any(fragment in e for e in result['errors']), result


@needs_node
@pytest.mark.parametrize('code', [
    "tn('{n} route', '{n} routes', n);",
    "thn('{count} route', '{count} routes', n, { count: fmt(n) });",
    "t('Open {name}', params);",
    "t('Open {name}', { name, ...rest });",
])
def test_placeholder_values_that_line_up_pass(tmp_path, code):
    result = _extract(tmp_path, code)
    assert result['errors'] == [], result


@needs_node
def test_shadowing_elsewhere_does_not_hide_the_helper(tmp_path):
    result = _extract(tmp_path, """
        function a() { const t = 1; return t + 1; }
        function b() { return t('Saved'); }
        el.title = cond ? t('Saved') : t('Failed');
    """)
    assert result['errors'] == [], result


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
    i18n._template_index.cache_clear()
    i18n.client_catalog.cache_clear()
    yield
    i18n._template_index.cache_clear()
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
    assert len(keys) < total, 'strings only the server renders stay out of the browser catalogue'
    assert 'Unknown language' not in keys, 'a message only app.py uses must not be sent to the browser'
    assert not any(k.startswith('setting\x04') for k in keys if k.endswith('Show language selector')), \
        'a template-only label must not be sent to the browser'


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

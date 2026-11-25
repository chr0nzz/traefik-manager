import glob
import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PHYSICAL_RULES = {
    'toggle-knob': 'the knob slides with translateX, which does not flip',
    'toggle-switch': 'the knob slides with translateX, which does not flip',
    '.toast': 'toasts slide in with translateX from the right edge',
    '.detail-panel': 'the detail panel slides in with translateX and its resize handle reads clientX',
    '.rm-popup-panel': 'centred with left: 50% and translate(-50%)',
    '#sideNav': 'the side nav drawer slides in with translateX',
    'side-nav-item': 'part of the side nav, which stays physical with it',
    'main.max-w-7xl': 'offsets the page by the side nav and the detail panel, which stay physical',
    'html.tm-fixed': 'positions the side nav, which stays physical',
    'drawer-srv-list': 'positioned from JS with style.left',
    '.routemap-svg': 'route map coordinates are physical',
    '.rm-': 'route map coordinates are physical',
    'slideIn': 'translateX keyframes',
    'route-ctx-menu': 'positioned from JS at the pointer',
}
PHYSICAL_FILES = {
    'static/js/routemap.js': 'lays out nodes and tooltips with physical pixel coordinates',
}

SIDE_PROP = re.compile(r'(?<![\w-])(margin-left|margin-right|padding-left|padding-right|border-left(?:-width|-color|-style)?|'
                       r'border-right(?:-width|-color|-style)?|border-(?:top|bottom)-(?:left|right)-radius)\s*:')
POS_PROP = re.compile(r'(?<![\w-])(left|right)\s*:')
ALIGN = re.compile(r'(?<![\w-])text-align\s*:\s*(left|right)\b')
TW = re.compile(r'(?<![\w/:.$\'"-])(?:[a-z]+:)*-?(?:ml|mr|pl|pr|left|right|border-l|border-r|rounded-[lr]|rounded-[tb][lr])-'
                r'(?:\d+(?:\.5)?|px|auto|full|\[[^\]\s]+\])(?![\w/-])|(?<![\w-])text-(?:left|right)(?![\w-])')


def _read(rel):
    with open(os.path.join(ROOT, rel), encoding='utf-8') as fh:
        return fh.read()


def _sources():
    files = sorted(glob.glob(os.path.join(ROOT, 'templates', '**', '*.html'), recursive=True))
    files += sorted(f for f in glob.glob(os.path.join(ROOT, 'static', 'js', '*.js')) if not f.endswith('.min.js'))
    return [os.path.relpath(f, ROOT) for f in files if os.path.relpath(f, ROOT) not in PHYSICAL_FILES]


def _css_rules(css):
    for m in re.finditer(r'\{([^{}]*)\}', css):
        start = m.start()
        sel_start = max(css.rfind('}', 0, start), css.rfind('{', 0, start), css.rfind(';', 0, start)) + 1
        yield css[sel_start:start].strip(), m.group(1), css.count('\n', 0, start) + 1


def _physical_decls(body):
    found = [m.group(0) for m in SIDE_PROP.finditer(body)]
    found += [m.group(0) for m in POS_PROP.finditer(body)]
    found += [m.group(0) for m in ALIGN.finditer(body)]
    return found


def _style_bodies(src):
    for pat in (r'style_?\s*=\s*"([^"]*)"', r"style_?\s*=\s*'([^']*)'", r'cssText\s*\+?=\s*`([^`]*)`',
                r"cssText\s*\+?=\s*'([^']*)'"):
        for m in re.finditer(pat, src):
            yield m.group(1), src.count('\n', 0, m.start()) + 1


def _style_block_rules(src):
    for block in re.finditer(r'<style[^>]*>(.*?)</style>', src, flags=re.S):
        yield from _css_rules(block.group(1))


def test_app_css_uses_logical_sides():
    bad = []
    for sel, body, line in _css_rules(_read('static/css/app.css')):
        if sel.startswith(('@', 'from', 'to')) or re.match(r'\d+%', sel):
            continue
        if any(k in sel for k in PHYSICAL_RULES):
            continue
        for d in _physical_decls(body):
            bad.append(f'app.css:{line} {sel[-60:]} {{ {d} }}')
    assert not bad, ('use margin-inline-start, padding-inline-end, inset-inline-start, text-align: start and the like, '
                     'so the layout mirrors for right-to-left languages:\n' + '\n'.join(bad))


@pytest.mark.parametrize('rel', _sources())
def test_inline_styles_and_classes_use_logical_sides(rel):
    src = _read(rel)
    bad = []
    for body, line in _style_bodies(src):
        bad += [f'{rel}:{line} style {d}' for d in _physical_decls(body)]
    for sel, body, line in _style_block_rules(src):
        if any(k in sel for k in PHYSICAL_RULES):
            continue
        bad += [f'{rel} <style> {sel[-40:]} {d}' for d in _physical_decls(body)]
    for m in re.finditer(r'class(?:Name)?\s*=\s*(["\'])(.*?)\1', src):
        for t in TW.finditer(m.group(2)):
            bad.append(f'{rel}:{src.count(chr(10), 0, m.start()) + 1} class {t.group(0)}')
    assert not bad, ('use ms-/me-/ps-/pe-/start-/end-/text-start and logical CSS properties, '
                     'so the layout mirrors for right-to-left languages:\n' + '\n'.join(bad))


@pytest.mark.parametrize('rel', _sources())
def test_table_headers_set_their_own_alignment(rel):
    src = _read(rel)
    bad = []
    for m in re.finditer(r'<th\b[^>]*>', src):
        tag = m.group(0)
        if not re.search(r'text-(start|end|center)\b|text-align\s*:|\$\{', tag):
            bad.append(f'{rel}:{src.count(chr(10), 0, m.start()) + 1} {tag[:80]}')
    assert not bad, ('a <th> only inherits text-start from its table when the table is not start-aligned, otherwise it '
                     'centres, so give each header its own text-start:\n' + '\n'.join(bad))


def test_every_physical_exception_still_exists():
    css = _read('static/css/app.css')
    for key in PHYSICAL_RULES:
        assert key in css, f'{key!r} is no longer in app.css, drop it from PHYSICAL_RULES'
    for rel in PHYSICAL_FILES:
        assert os.path.isfile(os.path.join(ROOT, rel)), f'{rel} is gone, drop it from PHYSICAL_FILES'

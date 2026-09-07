import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


def _ancestors_of(html, target_id):
    from html.parser import HTMLParser

    found = {}

    class P(HTMLParser):
        def __init__(self):
            super().__init__()
            self.stack = []

        def handle_starttag(self, tag, attrs):
            d = dict(attrs)
            if d.get('id') == target_id and target_id not in found:
                found[target_id] = list(self.stack)
            if tag not in ('br', 'img', 'input', 'hr', 'meta', 'link'):
                self.stack.append(d.get('id') or tag)

        def handle_endtag(self, tag):
            if self.stack:
                self.stack.pop()

    P().feed(html)
    assert target_id in found, '%s not found in the template' % target_id
    return found[target_id]


def test_the_entry_points_bar_is_not_inside_the_stats_panel():
    html = _read('templates', 'sections', 'stats.html')
    parents = _ancestors_of(html, 'entrypointsBar')
    assert 'statsPanel' not in parents, (
        'the entry points bar sits inside the stats panel, so hiding stat cards hides it too: %r'
        % parents)
    assert 'overviewSection' in parents, 'it should still live in the overview section: %r' % parents


def test_hiding_stat_cards_does_not_hide_the_entry_points_bar():
    css = _read('templates', 'index.html')
    assert 'html.tm-hide-stats #overviewSection' not in css, (
        'hiding the whole overview section takes the entry points bar with it')
    assert re.search(r'html\.tm-hide-stats #statsPanel\s*\{[^}]*display:\s*none', css), \
        'stat cards should hide their own panel only'


def test_the_section_still_collapses_when_both_are_off():
    css = _read('templates', 'index.html')
    assert re.search(r'html\.tm-hide-stats\.tm-hide-entrypoints #overviewSection\s*\{[^}]*display:\s*none', css), \
        'with both off the empty section would still take up margin'


def test_the_early_class_script_still_covers_both():
    html = _read('templates', 'index.html')
    assert "'tm-hide-stats'" in html and "'tm-hide-entrypoints'" in html, \
        'both classes must be applied before paint to avoid a flash'


def _apply_fn():
    src = _read('static', 'js', 'settings-modal.js')
    m = re.search(r'(function applyUiPrefs\(.*?\n\})', src, re.S)
    assert m, 'applyUiPrefs moved'
    return m.group(1)


def test_the_script_does_not_hide_the_whole_section_for_stat_cards():
    body = _apply_fn()
    assert not re.search(r'overviewSection\.classList\.toggle\(\s*[\'"]hidden[\'"]\s*,\s*!showStats\s*\)', body), (
        'hiding the overview section when stat cards are off takes the entry points bar '
        'with it, whatever the CSS says')


def test_the_script_hides_the_stats_panel_instead():
    body = _apply_fn()
    assert re.search(r'statsPanel[A-Za-z]*\.classList\.toggle\(\s*[\'"]hidden[\'"]\s*,\s*!showStats', body), \
        'stat cards should hide their own panel'


def test_the_section_is_hidden_only_when_both_are_off():
    body = _apply_fn()
    m = re.search(r'overviewSection\.classList\.toggle\(\s*[\'"]hidden[\'"]\s*,([^)]*)\)', body)
    assert m, 'the section should still collapse when there is nothing in it'
    cond = m.group(1)
    assert 'showStats' in cond, 'the stats toggle must still count: %r' % cond
    assert '&&' in cond, 'the section must not collapse on the stats toggle alone: %r' % cond
    other = [t for t in re.findall(r'[A-Za-z_][A-Za-z0-9_]*', cond) if t != 'showStats']
    assert other, 'the entry points state must count too: %r' % cond
    assert re.search(r'%s\s*=.*entrypointsBar' % other[0], body) or 'entrypointsBar' in body, \
        'the second operand should come from the entry points bar'

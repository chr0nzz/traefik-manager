import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT = 'TwemojiCountryFlags.woff2'


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


def test_the_flag_font_is_vendored_in_the_image_and_for_native_installs():
    for name in ('Dockerfile', os.path.join('scripts', 'setup-assets.sh')):
        src = _read(name)
        assert 'country-flag-emoji-polyfill' in src and FONT in src, \
            f'{name} does not vendor the flag font, so Windows Chromium shows letters instead of flags'
        assert 'TwemojiCountryFlags-LICENSE.md' in src, 'the flag art is CC-BY 4.0 and needs its notice shipped'


def test_the_font_only_covers_flag_characters():
    css = _read('static', 'css', 'app.css')
    face = re.search(r"@font-face\s*\{[^}]*Twemoji Country Flags[^}]*\}", css)
    assert face, 'app.css declares no flag font'
    assert f"url('../vendor/fonts/{FONT}')" in face.group(0)
    assert 'unicode-range: U+1F1E6-1F1FF' in face.group(0), \
        'without a unicode-range the font would replace every other glyph'
    assert re.search(r"\.tm-flag\s*\{[^}]*font-family:\s*'Twemoji Country Flags'", css)


def test_every_flag_is_wrapped_in_the_flag_font():
    core = _read('static', 'js', 'core.js')
    body = core.split('function _flagEmoji(cc)', 1)[1].split('\n}', 1)[0]
    assert '<span class="tm-flag">' in body


def test_the_log_detail_country_row_is_not_escaped_twice():
    logs = _read('static', 'js', 'logs.js')
    assert "[tc('label', 'Country'), `${_flagEmoji(_g.country_code)} ${_esc(" in logs, \
        'the country name must be escaped before the row is marked as markup'
    assert '${html ? v : _esc(v)}' in logs, 'an escaped span would print its tag as text'

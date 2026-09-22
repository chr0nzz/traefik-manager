import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'i18n'))

import pseudo  # noqa: E402
import tmi18n  # noqa: E402


@pytest.mark.parametrize('source, expected', [
    ('Save', '⟦Šåṽé⟧'),
    ('Delete {n} routes: {names}', '⟦Đéļéţé {n} ŕöûţéš: {names}⟧'),
    ('Remove %(name)s', '⟦Ŕéɱöṽé %(name)s⟧'),
    ('Use https://example.com', '⟦Ûšé https://example.com ⟧'),
    ('Settings &middot; Interface', '⟦Šéţţîñĝš &middot; Îñţéŕƒåçé⟧'),
    (' padded ', ' ⟦þåđđéđ⟧ '),
])
def test_pseudo_text_keeps_placeholders_and_marks_the_rest(source, expected):
    assert pseudo.pseudo(source) == expected


def test_the_pseudo_catalogue_passes_every_catalogue_check(tmp_path):
    path = pseudo.build(str(tmp_path))
    template = tmi18n.read_catalog(tmi18n.POT_PATH)
    assert tmi18n.check_catalogue(path, pseudo.PSEUDO_LOCALE, template) == []
    assert tmi18n.check_compiles(path, pseudo.PSEUDO_LOCALE) == []
    assert (tmp_path / 'LINGUAS').read_text() == 'eo\n'


def test_the_pseudo_catalogue_is_never_written_into_locale(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['pseudo.py', tmi18n.LOCALE_DIR])
    with pytest.raises(SystemExit):
        pseudo.main()

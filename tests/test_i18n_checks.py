import json
import os
import shutil
import subprocess
import sys
import textwrap

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'i18n'))

import tmi18n  # noqa: E402

DE_HEADER = textwrap.dedent('''\
    msgid ""
    msgstr ""
    "Project-Id-Version: Traefik Manager 1.15\\n"
    "Language: de\\n"
    "Plural-Forms: nplurals=2; plural=(n != 1);\\n"
    "MIME-Version: 1.0\\n"
    "Content-Type: text/plain; charset=utf-8\\n"
    "Content-Transfer-Encoding: 8bit\\n"

    ''')


def _node_ready():
    return bool(shutil.which('node')) and os.path.isdir(os.path.join(ROOT, 'scripts', 'i18n', 'node_modules', 'acorn'))


needs_node = pytest.mark.skipif(not _node_ready(), reason='node and acorn are needed for JS extraction '
                                '(make i18n-tools)')


def _po(tmp_path, body, header=DE_HEADER, identifier='de'):
    path = tmp_path / identifier / 'LC_MESSAGES' / 'messages.po'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + textwrap.dedent(body), encoding='utf-8')
    return str(path)


def _entry(msgid, msgstr, context=None):
    lines = []
    if context is not None:
        lines.append(f'msgctxt {json.dumps(context, ensure_ascii=False)}')
    lines.append(f'msgid {json.dumps(msgid, ensure_ascii=False)}')
    lines.append(f'msgstr {json.dumps(msgstr, ensure_ascii=False)}')
    return '\n'.join(lines) + '\n\n'


def _problems(tmp_path, *entries):
    path = _po(tmp_path, ''.join(entries))
    return [p.message for p in tmi18n.check_catalogue(path, 'de')]


def test_a_clean_translation_passes(tmp_path):
    assert _problems(tmp_path,
                     _entry('Save', 'Speichern'),
                     _entry('Remove %(name)s', '%(name)s entfernen'),
                     _entry('{n} routes selected', '{n} Routen ausgewählt'),
                     _entry("Don't", "Nicht"),
                     _entry('Down', 'Ausgefallen', context='status')) == []


@pytest.mark.parametrize('msgid, msgstr, fragment', [
    ('Save', '<img src=x onerror=alert(1)>', 'HTML'),
    ('Save', 'Speichern<script>', 'HTML'),
    ('Save', 'Speichern onmouseover=alert(1)', 'event handler'),
    ('Save', 'Speichern"', 'adds the character \'"\''),
    ('Save', 'Speichern`', "adds the character '`'"),
    ('Save', 'Speichern \\ x', 'adds the character'),
    ('Save', 'Speichern https://evil.example', 'link'),
    ('Save', 'javascript:alert(1)', 'scheme'),
    ('Save', 'data:text/html,x', 'scheme'),
    ('Save', 'www.evil.example', 'link'),
    ('Save', 'Speich‮ern', 'U+202E'),
    ('Save', 'Speich⁦ern', 'U+2066'),
    ('Save', 'Speichern %(secret)s', 'placeholders'),
    ('Remove %(name)s', '%(name)999999999s entfernen', 'placeholders'),
    ('Remove {name}', '{name.__class__} entfernen', 'unsafe placeholder'),
    ('Remove {name}', '{name} {other} entfernen', 'adds placeholders'),
    ('Remove {name}', 'Entfernen', 'drops placeholders'),
    ('Remove %(name)s', 'Entfernen', 'drops placeholders'),
    ('Copy %s to %s', '%d nach %s kopieren', 'positional'),
    ('Save', 'S' * 200, 'far longer'),
    ('Save', 'Spei\nchern', 'line breaks'),
    ('Save', ' Speichern', 'whitespace'),
    ('Save', 'Speichern\t', 'tab'),
])
def test_hostile_or_broken_translations_are_rejected(tmp_path, msgid, msgstr, fragment):
    problems = _problems(tmp_path, _entry(msgid, msgstr))
    assert any(fragment in p for p in problems), problems


def test_percent_is_plain_text_in_brace_messages(tmp_path):
    assert _problems(tmp_path, _entry('{pct}% of that path', '{pct} % de ce chemin')) == []
    assert _problems(tmp_path, _entry('{pct}% done', '{pct} %(secret)s fertig')) != []


def test_raw_control_characters_are_rejected(tmp_path):
    problems = _problems(tmp_path, 'msgid "Save"\nmsgstr "Spei\x07chern"\n\n')
    assert any('U+0007' in p for p in problems), problems


def test_markup_already_in_the_source_may_be_kept(tmp_path):
    assert _problems(tmp_path, _entry('Use <b>{name}</b>', 'Nutze <b>{name}</b>')) == []
    assert _problems(tmp_path, _entry('Use <b>{name}</b>', 'Nutze <i>{name}</i>')) != []


def test_fuzzy_entries_are_not_checked_because_they_never_ship(tmp_path):
    body = '#, fuzzy\n' + _entry('Save', '<script>alert(1)</script>')
    assert _problems(tmp_path, body) == []


def test_plural_forms_must_be_complete(tmp_path):
    body = ('msgid "{n} route"\nmsgid_plural "{n} routes"\n'
            'msgstr[0] "{n} Route"\nmsgstr[1] ""\n\n')
    assert any('plural forms' in p for p in _problems(tmp_path, body))


def test_plural_forms_may_spell_out_one(tmp_path):
    body = ('msgid "{n} route"\nmsgid_plural "{n} routes"\n'
            'msgstr[0] "eine Route"\nmsgstr[1] "{n} Routen"\n\n')
    assert _problems(tmp_path, body) == []


def test_tampered_plural_rule_is_rejected(tmp_path):
    header = DE_HEADER.replace('nplurals=2; plural=(n != 1);', 'nplurals=2; plural=(n*n*n*n != 1);')
    path = _po(tmp_path, _entry('Save', 'Speichern'), header=header)
    assert any('Plural-Forms' in p.message for p in tmi18n.check_catalogue(path, 'de'))


def test_language_header_must_match_the_folder(tmp_path):
    header = DE_HEADER.replace('Language: de', 'Language: fr')
    path = _po(tmp_path, _entry('Save', 'Speichern'), header=header)
    assert any('Language header' in p.message for p in tmi18n.check_catalogue(path, 'de'))


def test_catalogue_must_match_the_template(tmp_path):
    from babel.messages.catalog import Catalog
    template = Catalog()
    template.add('Save')
    template.add('Cancel')
    path = _po(tmp_path, _entry('Save', 'Speichern') + _entry('Injected', 'x'))
    messages = [p.message for p in tmi18n.check_catalogue(path, 'de', template)]
    assert any('"Injected" is not in messages.pot' in m for m in messages)
    assert any('1 strings from messages.pot are missing' in m for m in messages)


def test_compiled_catalogue_round_trips(tmp_path):
    path = _po(tmp_path, _entry('Save', 'Speichern') + _entry('Down', 'Aus', context='status'))
    assert tmi18n.check_compiles(path, 'de') == []


@pytest.mark.parametrize('msgid, fragment', [
    ('Click <a href="x">here</a>', 'must not contain HTML'),
    ('Remove {name.attr}', 'plain name'),
    ('Copy %s to %s', 'named placeholders'),
    ('sig-ep-headic">', 'must not contain HTML'),
    ('<{tag} style="{st}">{inline}', 'must not contain HTML'),
    ('font-size:11px;color:var(--muted)', 'must not contain CSS'),
    ('rateLimit:\n  average: {val}\n  burst: {val2}', 'must not contain configuration'),
    ('accessLog:\n  filePath: "/logs/access.log"', 'must not contain configuration'),
])
def test_source_strings_are_checked(msgid, fragment):
    from babel.messages.catalog import Catalog
    template = Catalog()
    template.add(msgid)
    assert any(fragment in p.message for p in tmi18n.check_template(template))


def test_percent_after_a_brace_placeholder_is_allowed_in_sources():
    from babel.messages.catalog import Catalog
    template = Catalog()
    template.add('{status} on {path}, {pct}% of that path')
    assert tmi18n.check_template(template) == []


def _tree(tmp_path, files):
    for rel, text in files.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
    return str(tmp_path)


def test_layout_rejects_unexpected_files_and_names(tmp_path):
    root = _tree(tmp_path, {
        'locale/LINGUAS': 'de\nde\nfr\n',
        'locale/messages.pot': '',
        'locale/de/LC_MESSAGES/messages.po': DE_HEADER,
        'locale/de/LC_MESSAGES/evil.js': 'x',
        'locale/zh_hans/LC_MESSAGES/messages.po': DE_HEADER,
        'locale/notes.txt': 'x',
    })
    messages = [str(p) for p in tmi18n.check_layout(root)]
    assert any('evil.js' in m and 'unexpected file' in m for m in messages)
    assert any('notes.txt' in m for m in messages)
    assert any('zh_hans' in m and 'should be named zh_Hans' in m for m in messages)
    assert any('de is listed twice' in m for m in messages)
    assert any('fr has no catalogue' in m for m in messages)


@pytest.mark.parametrize('rel, line, fragment', [
    ('core/x.py', 'msg = _(f"Hello {name}")', 'f-string'),
    ('app.py', "msg = gettext('Hi {name}').format(name=user)", 'str.format'),
    ('core/x.py', "html = Markup(_('Hi'))", 'Markup()'),
    ('templates/x.html', "{{ _('Hi') | safe }}", '|safe'),
    ('templates/x.html', '{% trans name=name|safe %}Hi {{ name }}{% endtrans %}', 'trans block'),
    ('templates/x.html', '{% autoescape false %}x{% endautoescape %}', 'autoescape false'),
])
def test_code_rules(tmp_path, rel, line, fragment):
    root = _tree(tmp_path, {rel: line + '\n'})
    assert any(fragment in p.message for p in tmi18n.check_code(root))


def test_code_rules_leave_normal_code_alone(tmp_path):
    root = _tree(tmp_path, {
        'core/x.py': "msg = _('Hello %(name)s', name=name)\nlabel = 'x'.format()\n",
        'templates/x.html': "{{ _('Hi') }} {{ body | safe }}\n",
    })
    assert tmi18n.check_code(root) == []


def test_builds_must_compile_without_fuzzy(tmp_path):
    good = 'RUN pybabel compile -d locale -D messages\n'
    assets = '"$PYBABEL" compile -d "$REPO_ROOT/locale" -D messages\n'
    root = _tree(tmp_path, {'Dockerfile': 'FROM x\n', 'scripts/setup-assets.sh': assets})
    assert any(p.where == 'Dockerfile' for p in tmi18n.check_dockerfile(root))
    root = _tree(tmp_path, {'Dockerfile': good, 'scripts/setup-assets.sh': 'echo done\n'})
    assert any('setup-assets' in p.where for p in tmi18n.check_dockerfile(root))
    root = _tree(tmp_path, {'Dockerfile': good.replace('messages', 'messages --use-fuzzy'), 'scripts/setup-assets.sh': assets})
    assert any('fuzzy' in p.message for p in tmi18n.check_dockerfile(root))
    root = _tree(tmp_path, {'Dockerfile': good, 'scripts/setup-assets.sh': assets.replace('messages', 'messages -f')})
    assert any('fuzzy' in p.message for p in tmi18n.check_dockerfile(root))
    assert tmi18n.check_dockerfile(ROOT) == []


def test_mo_files_are_never_committed():
    tracked = subprocess.run(['git', 'ls-files', '*.mo'], cwd=ROOT, capture_output=True, text=True).stdout
    assert tracked.strip() == ''
    with open(os.path.join(ROOT, '.gitignore'), encoding='utf-8') as fh:
        assert '*.mo' in fh.read().split()


@pytest.mark.skipif(not (shutil.which('msgfmt') and shutil.which('pofilter')),
                    reason='msgfmt and pofilter are installed in CI')
def test_external_tools_flag_a_bad_catalogue(tmp_path):
    body = '#, python-format\nmsgid "Copy %(count)d files"\nmsgstr "Kopiere %(count)s Dateien"\n\n'
    path = _po(tmp_path, body)
    messages = [p.message for p in tmi18n.run_external({'de': path}, require=True)]
    assert any(m.startswith('msgfmt') for m in messages), messages
    assert any(m.startswith('pofilter') for m in messages), messages


def test_missing_tools_fail_only_when_required(monkeypatch, tmp_path):
    monkeypatch.setattr(tmi18n.shutil, 'which', lambda name: None)
    path = _po(tmp_path, _entry('Save', 'Speichern'))
    assert tmi18n.run_external({'de': path}, require=False) == []
    assert len(tmi18n.run_external({'de': path}, require=True)) == 2


def _extract_js(tmp_path, files):
    root = _tree(tmp_path, files)
    return tmi18n.run_js_extractor(root)


@needs_node
def test_js_extractor_survives_what_broke_babel(tmp_path):
    js = textwrap.dedent('''\
        function _esc(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
        const re = /[/"'`]+/g;
        const x = a / b / c;
        function card(title) {
            return `<div class="x">
                <span>${_esc(title)}</span>
                ${items.map(i => `<b>${i}</b>`).join('')}
            </div>`;
        }
        // t('not a message, a comment')
        const s = "t('not a message, a string')";
        showToast(t('Route saved'));
        el.textContent = tn('{n} router', '{n} routers', count, { n: count });
        label = tc('status', 'Down');
        const tpl = t(`Plain template`);
    ''')
    result = _extract_js(tmp_path, {'static/js/a.js': js, 'templates/x.html': ''})
    assert result['errors'] == []
    got = {(m['context'], m['msgid'], m['plural']) for m in result['messages']}
    assert got == {
        (None, 'Route saved', None),
        (None, '{n} router', '{n} routers'),
        ('status', 'Down', None),
        (None, 'Plain template', None),
    }


@needs_node
@pytest.mark.parametrize('call, fragment', [
    ('t(name)', 'plain string literal'),
    ("t('Hello ' + name)", 'plain string literal'),
    ('t(`Hello ${name}`)', 'plain string literal'),
    ("tn('{n} x', plural, n)", 'argument 2'),
    ("tc(ctx, 'Down')", 'argument 1'),
    ("t('')", 'empty message'),
    ('t()', 'needs 1'),
])
def test_js_extractor_rejects_dynamic_messages(tmp_path, call, fragment):
    result = _extract_js(tmp_path, {'static/js/a.js': call + ';\n', 'templates/x.html': ''})
    assert any(fragment in e for e in result['errors']), result


@needs_node
def test_js_extractor_reads_inline_template_scripts(tmp_path):
    html = textwrap.dedent('''\
        <script type="application/json" id="i18n-catalog">{{ i18n_catalog | tojson }}</script>
        <script src="/static/js/core.js"></script>
        <p>{{ _('Not JS') }}</p>
        <script>
            window.X = {{ prefs | tojson }};
            var theme = '{{ default_theme }}' || 'dark';
            {% if auth_enabled %}var on = true;{% endif %}
            alert(t('Inline message'));
        </script>
    ''')
    result = _extract_js(tmp_path, {'static/js/.keep.js': '', 'templates/page.html': html})
    assert result['errors'] == []
    assert [(m['msgid'], m['location']) for m in result['messages']] == [('Inline message', 'templates/page.html:8')]


@needs_node
def test_js_extractor_reports_unparseable_files(tmp_path):
    result = _extract_js(tmp_path, {'static/js/a.js': 'function (\n', 'templates/x.html': ''})
    assert any('cannot parse' in e for e in result['errors'])


@needs_node
def test_repository_catalogues_pass_every_check():
    problems = tmi18n.check_all(require_tools=bool(os.environ.get('CI')))
    assert problems == [], '\n'.join(str(p) for p in problems)


WEBLATE_HEADER = DE_HEADER.replace('plural=(n != 1);', 'plural=n != 1;')


def test_the_plural_rule_weblate_writes_is_accepted(tmp_path):
    """Weblate writes gettext's "plural=n != 1", Babel writes "plural=(n != 1)"."""
    path = _po(tmp_path, _entry('Save', 'Speichern'), header=WEBLATE_HEADER)
    assert [p.message for p in tmi18n.check_catalogue(path, 'de')] == []


def test_a_plural_rule_that_picks_a_different_form_is_still_refused(tmp_path):
    path = _po(tmp_path, _entry('Save', 'Speichern'),
               header=DE_HEADER.replace('plural=(n != 1);', 'plural=(n > 1);'))
    assert any('Plural-Forms' in p.message for p in tmi18n.check_catalogue(path, 'de'))


def test_a_plural_rule_with_the_wrong_count_is_still_refused(tmp_path):
    path = _po(tmp_path, _entry('Save', 'Speichern'),
               header=DE_HEADER.replace('nplurals=2; plural=(n != 1);', 'nplurals=3; plural=(n != 1);'))
    assert any('Plural-Forms' in p.message for p in tmi18n.check_catalogue(path, 'de'))


GETTEXT_PLURALS = {
    'de': 'nplurals=2; plural=n != 1;',
    'es': 'nplurals=2; plural=n != 1;',
    'fr': 'nplurals=2; plural=n > 1;',
    'zh_Hans': 'nplurals=1; plural=0;',
    'ru': ('nplurals=3; plural=n%10==1 && n%100!=11 ? 0 : '
           'n%10>=2 && n%10<=4 && (n%100<10 || n%100>=20) ? 1 : 2;'),
}


def test_babel_and_gettext_agree_on_every_starter_locale():
    """The spelling differs per language, and on the nested rules it differs by more than
    parentheses. The form each one picks must still match."""
    from babel.messages.catalog import Catalog
    assert set(GETTEXT_PLURALS) == set(tmi18n.STARTER_LOCALES)
    for identifier, written in GETTEXT_PLURALS.items():
        babel = Catalog(locale=identifier).plural_forms
        assert tmi18n.same_plural_rule(written, babel), identifier


def test_ci_runs_the_translation_checks():
    from ruamel.yaml import YAML
    with open(os.path.join(ROOT, '.github', 'workflows', 'tests.yml'), encoding='utf-8') as fh:
        workflow = YAML(typ='safe').load(fh)
    jobs = workflow['jobs']
    steps = ' '.join(str(s.get('run', '')) for s in jobs['pytest']['steps'])
    assert 'acorn@8.18.0' in steps and '--ignore-scripts' in steps
    assert 'scripts/i18n/check.py --require-tools' in steps
    scope = jobs['weblate-scope']
    assert 'weblate' in scope['if']
    scope_run = ' '.join(str(s.get('run', '')) for s in scope['steps'])
    assert 'LC_MESSAGES/messages' in scope_run


LONG_MSGID = ('%(line_break)s⚠ A %(buffering)s/%(compress)s middleware is attached - '
              'remove it for smooth streaming and seeking.')


@pytest.mark.skipif(not shutil.which('msgmerge'), reason='gettext msgmerge is not installed')
def test_catalogues_are_wrapped_the_way_weblate_writes_them(tmp_path):
    pot = textwrap.dedent('''\
        msgid ""
        msgstr ""
        "MIME-Version: 1.0\\n"
        "Content-Type: text/plain; charset=utf-8\\n"
        "Content-Transfer-Encoding: 8bit\\n"

        msgid "%s"
        msgstr ""
        ''') % LONG_MSGID
    root = _tree(tmp_path, {
        'locale/messages.pot': pot,
        'locale/de/LC_MESSAGES/messages.po': DE_HEADER,
    })
    path = os.path.join(root, 'locale', 'de', 'LC_MESSAGES', 'messages.po')
    assert tmi18n.normalize_catalogue(path, os.path.join(root, 'locale', 'messages.pot'))
    lines = open(path, encoding='utf-8').read().splitlines()
    assert max(len(line) for line in lines) <= tmi18n.WRAP_WIDTH, \
        'Weblate rewraps at %d columns, so a wider catalogue comes back as a diff on every sync' % tmi18n.WRAP_WIDTH
    assert any(line.endswith('- remove "') for line in lines), \
        'the break must fall where gettext puts it, not where Babel does'
    assert not any('#:' in line for line in lines), 'locations stay out of the catalogues'


def test_normalising_a_catalogue_is_skipped_without_the_template(tmp_path):
    root = _tree(tmp_path, {'locale/de/LC_MESSAGES/messages.po': DE_HEADER})
    path = os.path.join(root, 'locale', 'de', 'LC_MESSAGES', 'messages.po')
    assert tmi18n.normalize_catalogue(path, os.path.join(root, 'locale', 'missing.pot')) is False
    assert open(path, encoding='utf-8').read() == DE_HEADER


def test_the_language_picker_pairs_a_language_with_a_flag_region():
    from core import i18n as i18n_mod
    assert i18n_mod.region_for('de') == 'DE' and i18n_mod.region_for('fr') == 'FR'
    assert i18n_mod.region_for('zh-Hans') == 'CN' and i18n_mod.region_for('zh-Hant') == 'TW', \
        'a script subtag decides the flag when the tag names no region'
    assert i18n_mod.region_for('pt-BR') == 'BR', 'an explicit region wins over the language default'
    assert i18n_mod.region_for('en') == '', 'English is spoken in many countries, so it takes the globe'
    assert i18n_mod.region_for('ar') == '', 'a language spanning many countries takes the globe too'
    assert i18n_mod.region_for('xx') == '', 'an unknown language must not invent a flag'


def test_the_flag_filter_only_builds_flags_from_real_region_codes():
    from core import i18n as i18n_mod
    assert i18n_mod.flag_emoji('DE') == '\U0001F1E9\U0001F1EA'
    assert i18n_mod.flag_emoji('de') == '\U0001F1E9\U0001F1EA', 'case must not matter'
    for junk in ('', 'D', 'DEU', '12', None, 'D1'):
        assert i18n_mod.flag_emoji(junk) == '', 'junk must render nothing, not a broken glyph: %r' % (junk,)


def test_the_picker_shows_a_flag_or_a_globe_and_keeps_the_code_for_screen_readers():
    with open(os.path.join(ROOT, 'templates', 'sections', 'navbar.html'), encoding='utf-8') as fh:
        navbar = fh.read()
    assert "{{ html_lang_region | flag }}" in navbar and "ph-globe" in navbar
    assert "{{ lang.region | flag }}" in navbar, 'every row in the menu needs its flag'
    assert 'class="sr-only" translate="no">{{ html_lang_code }}' in navbar, \
        'the flag alone is not a label, the code stays for screen readers'

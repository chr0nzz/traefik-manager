import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import unicodedata
from dataclasses import dataclass
from gettext import GNUTranslations

from babel import Locale, UnknownLocaleError
from babel.messages.catalog import Catalog
from babel.messages.extract import extract_from_dir
from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po, write_po

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOCALE_DIR = os.path.join(ROOT, 'locale')
POT_PATH = os.path.join(LOCALE_DIR, 'messages.pot')
JS_EXTRACTOR = os.path.join(ROOT, 'scripts', 'i18n', 'extract_js.mjs')

PROJECT = 'Traefik Manager'
BUGS_ADDRESS = 'https://github.com/chr0nzz/tm-locale/issues'
STARTER_LOCALES = ('de', 'fr', 'es', 'zh_Hans', 'ru')

PY_KEYWORDS = {
    '_': None,
    'gettext': None,
    'ngettext': (1, 2),
    'pgettext': ((1, 'c'), 2),
    'npgettext': ((1, 'c'), 2, 3),
    'lazy_gettext': None,
    'lazy_ngettext': (1, 2),
    'lazy_pgettext': ((1, 'c'), 2),
}
METHOD_MAP = [
    ('app.py', 'python'),
    ('core/**.py', 'python'),
    ('templates/**.html', 'jinja2'),
]

POFILTER_TESTS = ('escapes', 'newlines', 'nplurals', 'printf', 'pythonbraceformat', 'variables', 'xmltags')

PRINTF_RE = re.compile(r'%(?:\((?P<name>[^)]*)\))?[#0\- +]*(?:\*|\d+)?(?:\.(?:\*|\d+))?(?P<conv>[diouxXeEfFgGcrsa%])')
BRACE_RE = re.compile(r'\{([^{}]*)\}')
IDENT_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
TAG_RE = re.compile(r'<\s*/?\s*[A-Za-z!][^<>]*>?')
URL_RE = re.compile(r'(?i)(?:\b[a-z][a-z0-9+.\-]*://[^\s<>"\']*|\bwww\.[^\s<>"\']+|\b(?:javascript|data|vbscript|file)\s*:)')
EVENT_ATTR_RE = re.compile(r'(?i)\bon[a-z]+\s*=')
RISKY_ASCII = ('"', '`', '<', '>', '\\')
FORBIDDEN_CODEPOINTS = set(range(0x202A, 0x202F)) | set(range(0x2066, 0x206A)) | {0x2028, 0x2029, 0xFEFF}
ALLOWED_FILES_RE = re.compile(r'^(?:LINGUAS|messages\.pot|[A-Za-z]{2,3}(?:_[A-Za-z0-9]+)*/LC_MESSAGES/messages\.po)$')


@dataclass(frozen=True)
class Problem:
    where: str
    message: str

    def __str__(self):
        return f'{self.where}: {self.message}'


def app_series(root=ROOT):
    with open(os.path.join(root, 'core', 'env.py'), encoding='utf-8') as fh:
        match = re.search(r'APP_VERSION\s*=\s*["\'](\d+)\.(\d+)', fh.read())
    return f'{match.group(1)}.{match.group(2)}' if match else ''


def header_comment(language=None):
    title = f'{PROJECT} interface strings, {language}.' if language else f'{PROJECT} interface strings.'
    return f'# {title}\n# This file is distributed under the same license as {PROJECT}, GPL-3.0.\n#'


def message_key(message):
    msgid = message.id
    if isinstance(msgid, (list, tuple)):
        return (message.context, msgid[0], msgid[1])
    return (message.context, msgid, None)


def message_set(catalog):
    return {message_key(m) for m in catalog if m.id}


def run_js_extractor(root=ROOT):
    node = shutil.which('node')
    if not node:
        raise RuntimeError('node is not installed; it runs scripts/i18n/extract_js.mjs')
    proc = subprocess.run([node, JS_EXTRACTOR, root],
                          cwd=root, capture_output=True, text=True, timeout=300)
    if proc.returncode != 0:
        raise RuntimeError('JS extraction failed:\n' + proc.stderr.strip())
    return json.loads(proc.stdout)


def build_template(root=ROOT):
    catalog = Catalog(project=PROJECT, version=app_series(root), msgid_bugs_address=BUGS_ADDRESS,
                      copyright_holder=f'{PROJECT} contributors', charset='utf-8', fuzzy=False)
    catalog.header_comment = header_comment()
    problems = []

    for filename, lineno, message, _comments, context in extract_from_dir(
            root, METHOD_MAP, {}, PY_KEYWORDS, (), strip_comment_tags=True):
        if isinstance(message, tuple):
            if not message[0]:
                problems.append(Problem(f'{filename}:{lineno}', 'empty message'))
                continue
            msgid = message[:2]
        else:
            if not message:
                problems.append(Problem(f'{filename}:{lineno}', 'empty message'))
                continue
            msgid = message
        _add(catalog, msgid, context, problems, f'{filename}:{lineno}')

    js = run_js_extractor(root)
    problems.extend(Problem(e.split(': ', 1)[0], e.split(': ', 1)[-1]) for e in js['errors'])
    for entry in js['messages']:
        msgid = (entry['msgid'], entry['plural']) if entry['plural'] is not None else entry['msgid']
        _add(catalog, msgid, entry['context'], problems, entry['location'])
    return catalog, problems


def _add(catalog, msgid, context, problems, where):
    key_id = msgid[0] if isinstance(msgid, tuple) else msgid
    existing = catalog.get(key_id, context=context)
    if existing is not None:
        old_plural = existing.id[1] if isinstance(existing.id, tuple) else None
        new_plural = msgid[1] if isinstance(msgid, tuple) else None
        if old_plural != new_plural:
            problems.append(Problem(where, f'"{key_id}" is used both with and without the plural "{new_plural or old_plural}"'))
        return
    catalog.add(msgid, context=context)


def _write(path, catalog):
    buf = io.BytesIO()
    write_po(buf, catalog, width=76, no_location=True, omit_header=False, sort_output=True,
             ignore_obsolete=True, include_previous=False)
    with open(path, 'wb') as fh:
        fh.write(buf.getvalue())


def read_catalog(path, locale=None):
    with open(path, 'rb') as fh:
        return read_po(fh, locale=locale, abort_invalid=True)


def po_paths(locale_dir=LOCALE_DIR):
    out = {}
    if not os.path.isdir(locale_dir):
        return out
    for name in sorted(os.listdir(locale_dir)):
        path = os.path.join(locale_dir, name, 'LC_MESSAGES', 'messages.po')
        if os.path.isfile(path):
            out[name] = path
    return out


def update_catalogues(root=ROOT, init=()):
    template, problems = build_template(root)
    if problems:
        return problems
    locale_dir = os.path.join(root, 'locale')
    pot_path = os.path.join(locale_dir, 'messages.pot')
    os.makedirs(locale_dir, exist_ok=True)
    current = read_catalog(pot_path) if os.path.isfile(pot_path) else None
    if current is None or message_set(current) != message_set(template) or current.project != PROJECT:
        _write(pot_path, template)

    paths = po_paths(locale_dir)
    for identifier in init:
        if identifier in paths:
            continue
        Locale.parse(identifier)
        path = os.path.join(locale_dir, identifier, 'LC_MESSAGES', 'messages.po')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        catalog = Catalog(locale=identifier, project=PROJECT, version=app_series(root),
                          msgid_bugs_address=BUGS_ADDRESS, copyright_holder=f'{PROJECT} contributors',
                          charset='utf-8', fuzzy=False)
        catalog.update(template, no_fuzzy_matching=True)
        catalog.header_comment = header_comment(Locale.parse(identifier).english_name)
        _write(path, catalog)
        paths[identifier] = path

    for identifier, path in paths.items():
        catalog = read_catalog(path, locale=identifier)
        needs_header = (catalog.project != PROJECT or catalog.msgid_bugs_address != BUGS_ADDRESS
                        or 'PROJECT' in catalog.header_comment or 'FIRST AUTHOR' in catalog.header_comment)
        if message_set(catalog) == message_set(template) and not needs_header:
            continue
        catalog.update(template, no_fuzzy_matching=True, update_header_comment=False)
        catalog.project = PROJECT
        catalog.version = app_series(root)
        catalog.msgid_bugs_address = BUGS_ADDRESS
        catalog.copyright_holder = f'{PROJECT} contributors'
        catalog.header_comment = header_comment(Locale.parse(identifier).english_name)
        _write(path, catalog)
    return []


def placeholders(text):
    named, positional, braces = [], [], []
    for m in PRINTF_RE.finditer(text):
        if m.group('conv') == '%':
            continue
        if m.group('name') is not None:
            named.append(m.group(0))
        else:
            positional.append(m.group(0))
    for m in BRACE_RE.finditer(text):
        braces.append(m.group(1))
    return named, positional, braces


def _msgstr_forms(message):
    if isinstance(message.string, (list, tuple)):
        return list(message.string)
    return [message.string]


def _msgid_texts(message):
    return list(message.id) if isinstance(message.id, (list, tuple)) else [message.id]


def check_message(message, num_plurals, where):
    problems = []
    ids = _msgid_texts(message)
    forms = _msgstr_forms(message)
    source = '\n'.join(ids)
    label = f'{where} "{ids[0][:60]}"'

    if not any(forms):
        return problems
    if isinstance(message.id, (list, tuple)):
        if len(forms) != num_plurals:
            problems.append(Problem(label, f'has {len(forms)} plural forms, the language needs {num_plurals}'))
        if not all(forms):
            problems.append(Problem(label, 'fills some plural forms and leaves others empty'))

    src_named, src_positional, src_braces = set(), [], set()
    for text in ids:
        n, p, b = placeholders(text)
        src_named.update(n)
        src_positional = src_positional or p
        src_braces.update(b)

    for form in forms:
        if not form:
            continue
        named, positional, braces = placeholders(form)
        for brace in braces:
            if not IDENT_RE.match(brace):
                problems.append(Problem(label, f'unsafe placeholder {{{brace}}}, only {{name}} is allowed'))
        extra_named = set(named) - src_named
        if extra_named:
            problems.append(Problem(label, 'adds or changes placeholders ' + ', '.join(sorted(extra_named))))
        extra_braces = set(braces) - src_braces
        if extra_braces:
            problems.append(Problem(label, 'adds placeholders ' + ', '.join(sorted('{' + b + '}' for b in extra_braces))))
        if positional != src_positional:
            problems.append(Problem(label, f'positional placeholders {positional} differ from the source {src_positional}'))
        if not isinstance(message.id, (list, tuple)):
            missing = (src_named - set(named)) | {'{' + b + '}' for b in src_braces - set(braces)}
            if missing:
                problems.append(Problem(label, 'drops placeholders ' + ', '.join(sorted(missing))))

        for ch in RISKY_ASCII:
            if form.count(ch) > max(t.count(ch) for t in ids):
                problems.append(Problem(label, f'adds the character {ch!r}, which could change markup or code around the text'))
        if sorted(t.lower() for t in TAG_RE.findall(form)) != sorted(t.lower() for t in TAG_RE.findall(source)) and TAG_RE.search(form):
            problems.append(Problem(label, 'adds or changes HTML markup'))
        for url in URL_RE.findall(form):
            if url not in source:
                problems.append(Problem(label, f'adds a link or scheme not in the source: {url}'))
        if EVENT_ATTR_RE.search(form) and not EVENT_ATTR_RE.search(source):
            problems.append(Problem(label, 'contains an HTML event handler'))
        for ch in form:
            cp = ord(ch)
            if cp in FORBIDDEN_CODEPOINTS:
                problems.append(Problem(label, f'contains the invisible control character U+{cp:04X}'))
                break
            if unicodedata.category(ch) == 'Cc' and ch not in '\n\t':
                problems.append(Problem(label, f'contains the control character U+{cp:04X}'))
                break
        if form.count('\n') not in {t.count('\n') for t in ids}:
            problems.append(Problem(label, 'has a different number of line breaks than the source'))
        if '\t' in form and '\t' not in source:
            problems.append(Problem(label, 'adds a tab character'))
        if (form[:1].isspace(), form[-1:].isspace()) not in {(t[:1].isspace(), t[-1:].isspace()) for t in ids}:
            problems.append(Problem(label, 'leading or trailing whitespace differs from the source'))
        if len(form) > 4 * max(len(t) for t in ids) + 40:
            problems.append(Problem(label, f'is {len(form)} characters, far longer than the source'))
    return problems


def check_template(template, where='locale/messages.pot'):
    problems = []
    for message in template:
        if not message.id:
            continue
        for text in _msgid_texts(message):
            label = f'{where} "{text[:60]}"'
            if TAG_RE.search(text):
                problems.append(Problem(label, 'source strings must not contain HTML; keep markup outside the translated text'))
            for brace in BRACE_RE.findall(text):
                if not IDENT_RE.match(brace):
                    problems.append(Problem(label, f'placeholder {{{brace}}} must be a plain name'))
            named, positional, braces = placeholders(text)
            if positional and (named or braces or len(positional) > 1):
                problems.append(Problem(label, 'use named placeholders so translators can reorder them'))
        if message.context is not None and not message.context.strip():
            problems.append(Problem(f'{where} "{_msgid_texts(message)[0][:60]}"', 'empty context'))
    return problems


def check_catalogue(path, identifier, template=None):
    rel = os.path.relpath(path, ROOT)
    problems = []
    try:
        catalog = read_catalog(path, locale=identifier)
    except Exception as exc:
        return [Problem(rel, f'cannot be read: {exc}')]

    expected = Catalog(locale=identifier)
    if str(catalog.locale) != identifier:
        problems.append(Problem(rel, f'Language header is {catalog.locale}, expected {identifier}'))
    if catalog.plural_forms != expected.plural_forms:
        problems.append(Problem(rel, f'Plural-Forms is "{catalog.plural_forms}", expected "{expected.plural_forms}"'))
    content_type = dict(catalog.mime_headers).get('Content-Type', '')
    if 'charset=utf-8' not in content_type.lower():
        problems.append(Problem(rel, 'must be UTF-8'))

    for message in catalog:
        if not message.id or message.fuzzy:
            continue
        problems.extend(check_message(message, expected.num_plurals, rel))

    if template is not None:
        have, want = message_set(catalog), message_set(template)
        for context, msgid, _plural in sorted(have - want, key=str):
            problems.append(Problem(rel, f'"{msgid[:60]}" is not in messages.pot'))
        missing = want - have
        if missing:
            problems.append(Problem(rel, f'{len(missing)} strings from messages.pot are missing; run make i18n-extract'))
    return problems


def check_compiles(path, identifier):
    rel = os.path.relpath(path, ROOT)
    catalog = read_catalog(path, locale=identifier)
    buf = io.BytesIO()
    try:
        write_mo(buf, catalog, use_fuzzy=False)
        buf.seek(0)
        translations = GNUTranslations(buf)
    except Exception as exc:
        return [Problem(rel, f'does not compile: {exc}')]
    problems = []
    for message in catalog:
        if not message.id or message.fuzzy or not message.string or isinstance(message.id, (list, tuple)):
            continue
        got = translations.pgettext(message.context, message.id) if message.context else translations.gettext(message.id)
        if got != message.string:
            problems.append(Problem(rel, f'"{message.id[:60]}" does not survive compiling'))
    return problems


def check_layout(root=ROOT):
    problems = []
    locale_dir = os.path.join(root, 'locale')
    for dirpath, _dirs, files in os.walk(locale_dir):
        for name in files:
            if name.endswith('.mo'):
                continue
            rel = os.path.relpath(os.path.join(dirpath, name), locale_dir).replace(os.sep, '/')
            if not ALLOWED_FILES_RE.match(rel):
                problems.append(Problem(f'locale/{rel}', 'unexpected file; only LINGUAS, messages.pot and <locale>/LC_MESSAGES/messages.po belong here'))
    for identifier in po_paths(locale_dir):
        try:
            parsed = Locale.parse(identifier)
        except (ValueError, UnknownLocaleError):
            problems.append(Problem(f'locale/{identifier}', 'is not a known locale'))
            continue
        if str(parsed) != identifier:
            problems.append(Problem(f'locale/{identifier}', f'should be named {parsed}'))
    linguas = os.path.join(locale_dir, 'LINGUAS')
    if os.path.isfile(linguas):
        seen = set()
        with open(linguas, encoding='utf-8') as fh:
            for lineno, line in enumerate(fh, 1):
                for name in line.split('#', 1)[0].split():
                    if name in seen:
                        problems.append(Problem(f'locale/LINGUAS:{lineno}', f'{name} is listed twice'))
                    seen.add(name)
                    if name not in po_paths(locale_dir):
                        problems.append(Problem(f'locale/LINGUAS:{lineno}', f'{name} has no catalogue'))
    return problems


def _files(root, rel_dirs, suffixes):
    for rel in rel_dirs:
        base = os.path.join(root, rel)
        if os.path.isfile(base):
            yield base
            continue
        for dirpath, _dirs, files in os.walk(base):
            for name in sorted(files):
                if name.endswith(suffixes):
                    yield os.path.join(dirpath, name)


GETTEXT_CALL = r'\b(?:_|gettext|ngettext|pgettext|npgettext|lazy_gettext|lazy_ngettext|lazy_pgettext)\('
CODE_RULES = (
    (('app.py', 'core'), ('.py',), re.compile(GETTEXT_CALL + r'\s*[fF][rRbB]?["\']'),
     'f-string inside a gettext call cannot be extracted or translated'),
    (('app.py', 'core'), ('.py',), re.compile(GETTEXT_CALL + r'[^\n]*\)\s*\.format\('),
     'str.format on a translated string lets a translation read object attributes; use named %(x)s placeholders'),
    (('app.py', 'core'), ('.py',), re.compile(r'\bMarkup\(\s*' + GETTEXT_CALL[2:]),
     'Markup() on a translated string trusts the translation as HTML'),
    (('templates',), ('.html',), re.compile(r'\{\{[^}]*' + GETTEXT_CALL + r'[^}]*\|\s*safe\b'),
     'a translated string piped through |safe is rendered as HTML'),
    (('templates',), ('.html',), re.compile(r'\{%-?\s*trans\b[^%]*\|\s*safe\b'),
     'a trans block variable piped through |safe is rendered as HTML'),
    (('templates',), ('.html',), re.compile(r'\{%-?\s*autoescape\s+false'),
     'autoescape false would render translations as HTML'),
)


def check_code(root=ROOT):
    problems = []
    for dirs, suffixes, pattern, message in CODE_RULES:
        for path in _files(root, dirs, suffixes):
            with open(path, encoding='utf-8') as fh:
                for lineno, line in enumerate(fh, 1):
                    if pattern.search(line):
                        problems.append(Problem(f'{os.path.relpath(path, root)}:{lineno}', message))
    return problems


def check_dockerfile(root=ROOT):
    path = os.path.join(root, 'Dockerfile')
    with open(path, encoding='utf-8') as fh:
        lines = [ln.strip() for ln in fh]
    compile_lines = [ln for ln in lines if 'pybabel compile' in ln]
    problems = []
    if not compile_lines:
        problems.append(Problem('Dockerfile', 'must compile the catalogues with pybabel compile'))
    for line in compile_lines:
        if '--use-fuzzy' in line or re.search(r'\s-f\b', line):
            problems.append(Problem('Dockerfile', 'must not compile fuzzy translations, they are unreviewed'))
    return problems


def run_external(paths, require=False):
    problems = []
    msgfmt = shutil.which('msgfmt')
    pofilter = shutil.which('pofilter')
    if require:
        if not msgfmt:
            problems.append(Problem('tools', 'msgfmt is not installed (apt install gettext)'))
        if not pofilter:
            problems.append(Problem('tools', 'pofilter is not installed (pip install translate-toolkit)'))
    for identifier, path in paths.items():
        rel = os.path.relpath(path, ROOT)
        if msgfmt:
            proc = subprocess.run([msgfmt, '--check-format', '--check-header', '-o', os.devnull, path],
                                  capture_output=True, text=True)
            if proc.returncode != 0:
                problems.append(Problem(rel, 'msgfmt: ' + proc.stderr.strip()))
        if pofilter:
            with tempfile.TemporaryDirectory() as tmp:
                out = os.path.join(tmp, 'out.po')
                args = [pofilter, '--progress=none', '--nofuzzy']
                for test in POFILTER_TESTS:
                    args += ['-t', test]
                subprocess.run(args + [path, out], capture_output=True, text=True)
                if os.path.isfile(out):
                    flagged = [m for m in read_catalog(out) if m.id]
                    for m in flagged:
                        note = ' '.join(c for c in m.auto_comments + m.user_comments if 'pofilter' in c.lower() or '(' in c)
                        problems.append(Problem(rel, f'pofilter: "{_msgid_texts(m)[0][:60]}" {note}'.strip()))
    return problems


def check_all(root=ROOT, require_tools=False, extract=True):
    problems = []
    problems.extend(check_layout(root))
    problems.extend(check_code(root))
    problems.extend(check_dockerfile(root))

    locale_dir = os.path.join(root, 'locale')
    pot_path = os.path.join(locale_dir, 'messages.pot')
    template = None
    if not os.path.isfile(pot_path):
        problems.append(Problem('locale/messages.pot', 'missing; run make i18n-extract'))
    else:
        template = read_catalog(pot_path)
        problems.extend(check_template(template))

    if extract:
        fresh, extract_problems = build_template(root)
        problems.extend(extract_problems)
        if template is not None and message_set(fresh) != message_set(template):
            added = len(message_set(fresh) - message_set(template))
            removed = len(message_set(template) - message_set(fresh))
            problems.append(Problem('locale/messages.pot',
                                    f'is stale ({added} new, {removed} removed strings); run make i18n-extract and commit'))

    paths = po_paths(locale_dir)
    for identifier, path in paths.items():
        problems.extend(check_catalogue(path, identifier, template))
        problems.extend(check_compiles(path, identifier))
    problems.extend(run_external(paths, require=require_tools))
    return problems

import glob
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCAN = ('static/js/*.js', 'static/css/*.css', 'templates/*.html', 'templates/**/*.html')


def _files():
    seen = []
    for pat in SCAN:
        for f in glob.glob(os.path.join(ROOT, pat), recursive=True):
            if f not in seen:
                seen.append(f)
    return seen


def _text(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def test_every_css_variable_we_use_is_defined_somewhere():
    defined = set()
    for f in _files():
        body = _text(f)
        defined.update(re.findall(r'(--[A-Za-z0-9_-]+)\s*:', body))
        defined.update(re.findall(r"setProperty\(\s*['\"](--[A-Za-z0-9_-]+)", body))
    missing = {}
    for f in _files():
        for m in re.finditer(r'var\(\s*(--[A-Za-z0-9_-]+)\s*(,)?', _text(f)):
            name, fallback = m.group(1), m.group(2)
            if name in defined or fallback:
                continue
            missing.setdefault(name, set()).add(os.path.relpath(f, ROOT))
    assert not missing, (
        'these render as no colour at all, silently:\n  '
        + '\n  '.join('%s used in %s' % (k, ', '.join(sorted(v))) for k, v in sorted(missing.items())))


def test_the_test_job_fails_the_build_when_tests_fail():
    wf = _text(os.path.join(ROOT, '.github', 'workflows', 'tests.yml'))
    step = wf[wf.index('Run tests with coverage'):]
    nxt = step.find('\n      - name:')
    step = step[:nxt] if nxt > 0 else step
    assert 'pytest' in step and '| tee' in step, 'the step changed shape, recheck the exit code path'
    assert 'set -o pipefail' in step, (
        'piping pytest into tee hands the step tee exit code, so a red suite reports green')

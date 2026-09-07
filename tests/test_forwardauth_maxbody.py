import json
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(ROOT, 'static', 'js', 'middlewares.js')


def _src(path=JS):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def _fn(name, src=None):
    src = src if src is not None else _src()
    m = re.search(r'(?:async )?function ' + name + r'\(.*?\n\}', src, re.S)
    assert m, 'the %s helper moved' % name
    return m.group(0)


def _run(stub):
    out = subprocess.run(['node', '-e', stub], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return out.stdout.strip()


def test_the_forward_auth_presets_fill_the_size_limit():
    body = _fn('_showMwWizard')
    for preset in ('forwardAuthAuthentik', 'forwardAuthAuthelia', 'forwardAuthGatekeeper'):
        seg = body[body.index("tpl === '" + preset + "'"):]
        seg = seg[:seg.index('} else if') if '} else if' in seg else len(seg)]
        assert 'MaxBody' in seg, \
            '%s does not fill the response size limit, so Traefik keeps warning' % preset


def test_a_forward_auth_middleware_without_a_limit_is_detected():
    stub = _fn('_faNeedsLimit') + '''
const cases = [
  ['forwardAuth:\\n  address: http://a\\n', true],
  ['forwardAuth:\\n  address: http://a\\n  maxResponseBodySize: 4096\\n', false],
  ['compress: {}\\n', false],
  ['basicAuth:\\n  users: []\\n', false],
];
console.log(JSON.stringify(cases.map(([y, want]) => _faNeedsLimit(y) === want)));
'''
    assert json.loads(_run(stub)) == [True, True, True, True], \
        'the detector must flag only forward auth without a limit'


def test_adding_the_limit_inserts_it_under_forward_auth():
    stub = 'const FA_DEFAULT_MAX_BODY = 4096;\n' + _fn('_faNeedsLimit') + _fn('_faWithLimit') + '''
const out = _faWithLimit('forwardAuth:\\n  address: http://a\\n  trustForwardHeader: true\\n');
console.log(JSON.stringify(out));
'''
    got = json.loads(_run(stub))
    assert 'maxResponseBodySize: 4096' in got, got
    lines = got.splitlines()
    idx = [i for i, ln in enumerate(lines) if 'maxResponseBodySize' in ln][0]
    assert lines[idx].startswith('  '), 'the line must sit inside the forwardAuth block: %r' % got
    assert lines[0].strip() == 'forwardAuth:', got


def test_adding_the_limit_leaves_an_existing_one_alone():
    stub = 'const FA_DEFAULT_MAX_BODY = 4096;\n' + _fn('_faNeedsLimit') + _fn('_faWithLimit') + '''
const y = 'forwardAuth:\\n  address: http://a\\n  maxResponseBodySize: 128\\n';
console.log(JSON.stringify(_faWithLimit(y) === y));
'''
    assert json.loads(_run(stub)) is True, 'an existing limit must not be overwritten'


def test_a_middleware_without_a_limit_shows_a_flag_on_its_card():
    src = _src()
    assert '_faNeedsLimit(mw.yaml)' in src, \
        'the card must flag a forward auth middleware with no limit'
    assert 'addFaLimit(this)' in src, 'the flag must offer to add one'


def test_adding_the_limit_opens_the_editor_rather_than_saving():
    body = _fn('addFaLimit')
    assert 'handleMwEdit(btn)' in body, \
        'it must open the editor so the change is reviewed, not written silently'
    assert '_mwMonacoEditor.setValue' in body, 'the editor has to show the inserted line'
    assert '/save-middleware' not in body, 'it must not write on its own'

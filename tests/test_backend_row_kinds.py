import json
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(ROOT, 'static', 'js', 'routes.js')
MODAL = os.path.join(ROOT, 'templates', 'modals', 'route_modal.html')

FNS = ['_bkRows', '_bkKindOf', '_bkAnyServiceRow', '_collectBackendChildren']


def _read(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def _preamble():
    src = _read(JS)
    out = []
    for name in FNS:
        m = re.search(r'(function ' + name + r'\(.*?\n\})', src, re.S)
        assert m, 'the %s helper moved' % name
        out.append(m.group(1))
    return '\n'.join(out) + '\n'


def _collect(rows, composite='weighted', scheme='http'):
    stub = '''
const _rows = ''' + json.dumps(rows) + ''';
function _mk(r) {
  return { _r: r, closest: () => null,
    querySelector: (sel) => {
      const key = sel.replace('.bk-', '');
      if (key === 'kind')   return { value: r.kind || 'manual' };
      if (key === 'svc')    return { value: r.name || '' };
      if (key === 'host')   return { value: r.host || '' };
      if (key === 'port')   return { value: r.port || '' };
      if (key === 'weight') return { value: r.weight == null ? '' : String(r.weight) };
      if (key === 'scheme') return { value: r.scheme || 'http' };
      return null;
    } };
}
const _els = _rows.map(_mk);
global.document = {
  getElementById: (id) => {
    if (id === 'httpTargetGrid') return _els[0] || null;
    if (id === 'httpCompositeType') return { value: ''' + json.dumps(composite) + ''' };
    if (id === 'scheme') return { value: ''' + json.dumps(scheme) + ''' };
    return null;
  },
  querySelectorAll: () => _els.slice(1),
};
'''
    script = stub + _preamble() + 'console.log(JSON.stringify(_collectBackendChildren()));\n'
    out = subprocess.run(['node', '-e', script], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_row_zero_is_a_backend_row_like_the_others():
    html = _read(MODAL)
    grid = re.search(r'<div id="httpTargetGrid"([^>]*)>', html)
    assert grid, 'the target grid moved'
    assert 'tm-backend-row' in grid.group(1), \
        'row zero must carry the same class or the kind selector reaches only rows 1..n'


def test_row_zero_has_a_kind_a_weight_and_a_service_picker():
    html = _read(MODAL)
    grid_start = html.index('<div id="httpTargetGrid"')
    grid = html[grid_start:html.index('<div id="httpBackendRows">')]
    for cls in ('bk-kind', 'bk-scheme', 'bk-host', 'bk-port', 'bk-weight', 'bk-svc'):
        assert cls in grid, f'row zero is missing {cls}'


def test_row_zero_scheme_is_the_form_scheme_field():
    html = _read(MODAL)
    grid_start = html.index('<div id="httpTargetGrid"')
    grid = html[grid_start:html.index('<div id="httpBackendRows">')]
    assert 'name="scheme" id="scheme"' in grid, \
        'the scheme select moved into row zero; keeping its id and name is what keeps every reader working'
    assert html.count('id="scheme"') == 1, 'two scheme controls would silently disagree'


def test_the_named_form_fields_are_kept_for_legacy_clients():
    html = _read(MODAL)
    assert 'name="targetIp"' in html and 'name="targetPort"' in html


def test_every_manual_row_carries_its_own_weight():
    out = _collect([{'host': 'a', 'port': '80', 'weight': 9},
                    {'host': 'b', 'port': '80', 'weight': 1}])
    assert out == [
        {'kind': 'manual', 'address': 'a:80', 'scheme': 'http', 'weight': 9, 'percent': 9},
        {'kind': 'manual', 'address': 'b:80', 'scheme': 'http', 'weight': 1, 'percent': 1},
    ]


def test_a_service_row_is_collected_by_name():
    out = _collect([{'host': 'a', 'port': '80'},
                    {'kind': 'service', 'name': 'canary', 'weight': 3}])
    assert out[1] == {'kind': 'service', 'name': 'canary', 'weight': 3, 'percent': 3}


def test_row_zero_takes_its_scheme_from_the_shared_control():
    out = _collect([{'host': 'a', 'port': '443'}], scheme='https')
    assert out[0]['scheme'] == 'https'


def test_a_row_with_no_host_and_no_service_is_skipped():
    out = _collect([{'host': 'a', 'port': '80'}, {'host': ''},
                    {'kind': 'service', 'name': ''}])
    assert len(out) == 1


def test_a_blank_weight_defaults_to_one_for_weighted():
    out = _collect([{'host': 'a', 'port': '80'}])
    assert out[0]['weight'] == 1


def test_a_blank_share_defaults_to_zero_for_mirroring():
    out = _collect([{'host': 'a', 'port': '80'}], composite='mirroring')
    assert out[0]['percent'] == 0, 'a mirror with no share receives no traffic, so do not invent one'


def test_a_port_less_address_is_passed_through():
    out = _collect([{'host': 'unix:///var/run/x.sock'}])
    assert out[0]['address'] == 'unix:///var/run/x.sock'


def test_the_composite_payload_is_sent_for_a_service_row_or_a_composite_route():
    src = _read(JS)
    m = re.search(r'if \(proto === .http. && \((.*?)\)\) \{(.*?)\n    \}', src, re.S)
    assert m, 'the composite payload gate moved'
    assert '_bkAnyServiceRow()' in m.group(1), 'a service row must still send the payload'
    assert '_routeWasComposite' in m.group(1), (
        'a route that loaded as a composite must keep sending children, or removing its '
        'last service row silently discards the edit')
    assert 'payload.children' in m.group(2)
    assert 'compositeType' in m.group(2)


def test_switching_a_row_to_service_fills_its_picker():
    src = _read(JS)
    m = re.search(r'function _bkKindChanged\(select\) \{(.*?)\n\}', src, re.S)
    assert m, 'the kind handler moved'
    body = m.group(1)
    assert '_bkFillServiceSelect' in body, \
        'row zero has no picker contents until something fills it'
    assert '!picker.options.length' in body, 'refilling on every change would lose the selection'


def test_an_empty_service_list_says_so():
    src = _read(JS)
    m = re.search(r'async function _bkFillServiceSelect\(row, selected\) \{(.*?)\n\}', src, re.S)
    assert m, 'the picker filler moved'
    assert 'svcs.length' in m.group(1), 'a blank dropdown with no explanation is what users hit'


def test_switching_mode_hides_the_cells_that_do_not_apply():
    src = _read(JS)
    m = re.search(r'function _bkKindChanged\(select\) \{(.*?)\n\}', src, re.S)
    assert m, 'the kind handler moved'
    body = m.group(1)
    for cls in ('bk-scheme', 'bk-host', 'bk-port', 'bk-svc'):
        assert f"'.{cls}'" in body, f'{cls} is never shown or hidden'
    assert "gridColumn = ''" in body, (
        'a leftover explicit column from an earlier version would fight the template')


def test_combining_is_hidden_until_there_is_more_than_one_backend():
    src = _read(JS)
    m = re.search(r'function _bkSyncWeights\(\) \{(.*?)\n\}', src, re.S)
    assert m, 'the sync helper moved'
    assert 'rows.length > 1' in m.group(1), \
        'combining one backend with nothing is meaningless, so the selector must stay hidden'


def test_a_single_service_row_still_sends_its_payload():
    src = _read(JS)
    m = re.search(r'if \(proto === .http. && \(.*?\)\) \{', src)
    assert m, 'the payload gate moved'
    assert 'rows.length' not in src[m.start():m.start() + 200], (
        'the payload must not be gated on row count, or a lone service row would save '
        'with no backend at all')


def test_the_backend_mode_labels_say_what_they_do():
    html = _read(MODAL)
    assert html.count(">{{ _('Build backends') }}</button>") == 3, 'http, tcp and udp each have the toggle'
    assert html.count(">{{ _('Use a service') }}</button>") == 3
    assert "'Manual')" not in html, \
        'Manual read as the opposite of existing, when it means build the list here'
    assert "'Existing service')" not in html


def test_the_picker_precedes_the_weight_so_it_cannot_wrap():
    html = _read(MODAL)
    grid = html[html.index('<div id="httpTargetGrid"'):html.index('<div id="httpBackendRows">')]
    assert grid.index('bk-svc') < grid.index('bk-weight'), (
        'grid places items in dom order, so a picker after the weight gets pushed onto a '
        'second line when it asks for an earlier column')
    assert 'grid-column:2 / span 3' not in grid, 'spans are what caused the wrap'


def test_the_row_template_follows_the_mode():
    src = _read(JS)
    m = re.search(r'function _bkKindChanged\(select\) \{(.*?)\n\}', src, re.S)
    assert m, 'the kind handler moved'
    body = m.group(1)
    assert 'gridTemplateColumns' in body, 'the row must resize when cells hide, not span over them'
    assert "'104px 1fr 74px'" in body, 'service mode has three visible cells'


def test_opening_the_form_again_forgets_the_last_route():
    src = _read(JS)
    m = re.search(r'function _resetBackendKinds\(\) \{(.*?)\n\}', src, re.S)
    assert m, 'the reset helper is missing'
    body = m.group(1)
    assert "zeroKind.value = 'manual'" in body, \
        'a service row left over from the last route reappears on a new one'
    assert "type.value = 'weighted'" in body
    assert '_bkKindChanged' in body or '_bkSyncWeights' in body, \
        'resetting the value without refreshing leaves the combine selector on screen'


def test_the_reset_runs_when_the_form_resets():
    src = _read(JS)
    m = re.search(r'function _resetLbAdvanced\(\) \{(.*?)\n\}', src, re.S)
    assert m and '_resetBackendKinds()' in m.group(1)

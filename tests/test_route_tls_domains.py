import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


def test_the_certificate_domains_can_be_typed():
    html = _read('templates', 'modals', 'route_modal.html')
    assert 'type="hidden" name="tlsWildcardMain"' not in html, \
        'the domains were fixed to the wildcard preset with no way to change them'
    assert 'id="tlsWildcardMain" class="input-field' in html
    assert '<textarea name="tlsWildcardSans" id="tlsWildcardSans"' in html, \
        'sans is a list, so it needs a box that takes more than one line'
    assert 'id="wildcardFields"' in html


def test_the_fields_stay_out_of_the_way_until_asked_for():
    html = _read('templates', 'modals', 'route_modal.html')
    assert re.search(r'id="wildcardFields" style="display:none"', html)
    js = _read('static', 'js', 'routes.js')
    assert 'function _showWildcardFields(on)' in js
    body = js[js.index('function _onWildcardToggle('):js.index('function _applyHttpRuleToForm(')]
    assert '_showWildcardFields(checked)' in body


def test_the_preset_does_not_overwrite_what_you_typed():
    js = _read('static', 'js', 'routes.js')
    body = js[js.index('function _onWildcardToggle('):js.index('function _applyHttpRuleToForm(')]
    assert 'if (mainEl.value.trim() || sansEl.value.trim()) return;' in body, \
        'reopening the section would throw away hand written domains'


def test_editing_a_route_shows_the_domains_it_already_has():
    js = _read('static', 'js', 'routes.js')
    assert js.count('_showWildcardFields(true)') == 2, 'both edit and clone must reveal them'
    assert js.count('_showWildcardFields(false)') >= 2


def test_turning_tls_off_hides_them_again():
    js = _read('static', 'js', 'routes.js')
    body = js[js.index('function toggleWildcardSection('):js.index('function _showWildcardFields(')]
    assert '_onWildcardToggle(false)' in body


def test_the_backend_still_reads_both_fields():
    src = _read('app.py')
    assert "request.form.get('tlsWildcardMain', '').strip()" in src
    assert "request.form.get('tlsWildcardSans', '').splitlines()" in src, \
        'the textarea sends one domain per line'

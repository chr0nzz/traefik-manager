import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


def test_the_services_tab_offers_a_way_to_create_one():
    html = _read('templates', 'tabs', 'tab_live.html')
    assert 'openServiceModal()' in html
    assert 'title="Add service"' in html


def test_the_modal_is_included_in_the_page():
    assert "modals/service_modal.html" in _read('templates', 'index.html')


def test_the_modal_has_every_control_the_save_needs():
    html = _read('templates', 'modals', 'service_modal.html')
    for el in ('svcName', 'svcType', 'svcRows', 'svcOriginalName', 'svcConfigFileSelect',
               'svcDeleteBtn', 'svcSaveBtn', 'svcError'):
        assert f'id="{el}"' in html, f'missing {el}'


def test_the_modal_offers_every_authorable_type():
    html = _read('templates', 'modals', 'service_modal.html')
    for kind in ('loadBalancer', 'weighted', 'mirroring', 'failover'):
        assert f'value="{kind}"' in html, kind


def test_a_plain_load_balancer_hides_the_kind_and_weight_columns():
    js = _read('static', 'js', 'services.js')
    m = re.search(r'function _svcTypeChanged\(\) \{(.*?)\n\}', js, re.S)
    assert m, 'the type handler moved'
    assert "kind === 'loadBalancer'" in m.group(1)
    assert 'plain' in m.group(1), 'weights make no sense for a plain load balancer'


def test_the_edit_button_matches_the_route_detail_panel():
    html = _read('templates', 'modals', 'detail_panels.html')
    route = re.search(r'<button id="detailEditBtn"([^>]*)>(.*?)</button>', html, re.S)
    svc = re.search(r'<button id="svcDetailEditBtn"([^>]*)>(.*?)</button>', html, re.S)
    assert route and svc, 'one of the edit buttons moved'
    assert 'btn-secondary text-xs' in svc.group(1), 'it must use the same class as the route one'
    assert 'ph-pencil-simple' in svc.group(2) and 'Edit' in svc.group(2)


def test_the_modal_footer_uses_the_shared_class():
    html = _read('templates', 'modals', 'service_modal.html')
    assert 'detail-panel-foot' in html, 'every other modal foot uses this'
    assert 'sticky bottom-0' not in html, 'do not hand roll a footer'


def test_backend_rows_reuse_the_existing_row_class():
    js = _read('static', 'js', 'services.js')
    assert "'svc-row tm-backend-row grid gap-3 mt-2'" in js, \
        'the route form already has a backend row style, use it'


def test_file_services_offer_an_edit_button_on_the_card():
    js = _read('static', 'js', 'services.js')
    m = re.search(r'function _svcEditable\(s\) \{(.*?)\n\}', js, re.S)
    assert m, 'the editable check moved'
    body = m.group(1)
    assert "!== 'file'" in body, 'only services in our own config files are editable'
    assert '_ownedChildNames' in body, 'a generated backend is edited through its parent'
    assert 'ph-pencil-simple' in js, 'the card rail carries an Edit pencil like route cards'


def test_the_detail_panel_wires_its_edit_button():
    js = _read('static', 'js', 'services.js')
    assert "getElementById('svcDetailEditBtn')" in js
    assert 'openServiceModal(s)' in js


def test_delete_is_hidden_when_creating():
    html = _read('templates', 'modals', 'service_modal.html')
    m = re.search(r'id="svcDeleteBtn"[^>]*', html)
    assert m and 'display:none' in m.group(0)


def test_the_collector_reads_both_row_kinds():
    js = _read('static', 'js', 'services.js')
    m = re.search(r'function _collectServiceRows\(\) \{(.*?)\n\}', js, re.S)
    assert m, 'the collector moved'
    body = m.group(1)
    assert "'service'" in body and "'manual'" in body
    assert 'percent' in body and 'weight' in body


def test_a_mirror_share_defaults_to_zero_not_one():
    js = _read('static', 'js', 'services.js')
    m = re.search(r'function _collectServiceRows\(\) \{(.*?)\n\}', js, re.S)
    assert "kind === 'mirroring' ? 0 : 1" in m.group(1), \
        'a mirror with no share receives no traffic, so do not invent one'


def test_a_service_cannot_reference_itself():
    js = _read('static', 'js', 'services.js')
    m = re.search(r'async function _svcFillRefSelect\(row, selected\) \{(.*?)\n\}', js, re.S)
    assert m, 'the picker filler moved'
    assert 'editing' in m.group(1), 'the service being edited must not be offered as its own backend'


def test_saving_clears_the_cached_service_list():
    js = _read('static', 'js', 'services.js')
    m = re.search(r'async function saveServiceModal\(\) \{(.*?)\n\}', js, re.S)
    assert '_tmServices = null' in m.group(1), \
        'a new service must appear in the route form picker without a reload'


def test_deleting_warns_before_it_happens():
    js = _read('static', 'js', 'services.js')
    m = re.search(r'async function deleteServiceFromModal\(\) \{(.*?)\n\}', js, re.S)
    assert 'confirm(' in m.group(1)


def test_the_management_block_only_offers_adoption():
    js = _read('static', 'js', 'services.js')
    m = re.search(r'function _svcOwnershipHtml\(s\) \{(.*?)\n\}', js, re.S)
    assert m, 'the ownership block moved'
    assert '_setServiceOwnership' in m.group(1)
    assert 'owned ?' in m.group(1)
    assert 'openServiceModal' not in m.group(1), \
        'editing belongs on the panel header button, like routes'


def test_the_add_button_matches_the_other_toolbar_buttons():
    html = _read('templates', 'tabs', 'tab_live.html')
    m = re.search(r'<button onclick="openServiceModal\(\)"[^>]*>', html)
    assert m, 'the add button moved'
    assert 'proto-btn' in m.group(0), 'it must use the same class as Refresh and the view toggle'
    assert 'btn-primary' not in m.group(0)


def test_the_add_button_sits_in_a_toolbar_group():
    html = _read('templates', 'tabs', 'tab_live.html')
    i = html.index('openServiceModal()')
    before = html[:i]
    group = before.rindex('<div class="flex gap-1 p-1 rounded-lg')
    assert '</div>' not in before[group:], 'the button must live inside a toolbar group like its siblings'


def test_the_modal_docks_the_page_like_every_other_panel():
    js = _read('static', 'js', 'services.js')
    m = re.search(r'async function openServiceModal\(existing\) \{(.*?)\n\}', js, re.S)
    assert m, 'the opener moved'
    assert 'setDetailDockOpen(true)' in m.group(1), 'without this the panel covers the page'
    assert "closeOtherPanels('serviceModal')" in m.group(1)


def test_closing_the_modal_undocks():
    js = _read('static', 'js', 'services.js')
    m = re.search(r'function closeServiceModal\(\) \{(.*?)\n\}', js, re.S)
    assert 'setDetailDockOpen(false)' in m.group(1)
    assert "document.body.style.overflow = ''" in m.group(1)


def test_the_config_file_picker_uses_the_shared_helper():
    js = _read('static', 'js', 'services.js')
    assert "_populateConfigFileSelect('service')" in js, \
        'rolling our own picker is what produced [object Object]'
    html = _read('templates', 'modals', 'service_modal.html')
    for el in ('svcConfigFileSelectWrap', 'svcConfigFileSelect', 'newSvcFileName'):
        assert f'id="{el}"' in html, f'the shared helper expects {el}'


def test_the_shared_helper_knows_about_services():
    js = _read('static', 'js', 'core.js')
    m = re.search(r'async function _populateConfigFileSelect\(which\)(.*?)\n\}', js, re.S)
    assert m, 'the shared helper moved'
    assert 'svcConfigFileSelect' in m.group(1)
    assert 'onSvcConfigFileChange' in m.group(1)


def test_every_manual_row_has_a_scheme_select():
    js = _read('static', 'js', 'services.js')
    m = re.search(r'async function addServiceRow\(data\) \{(.*?)\n\}', js, re.S)
    assert m, 'the row builder moved'
    body = m.group(1)
    assert 'svc-scheme' in body, 'an https backend was impossible without typing the full url'
    assert '<option value="http">HTTP</option><option value="https">HTTPS</option>' in body, \
        'copy the bk-scheme options from the route form exactly'


def test_the_collector_reads_the_row_scheme():
    js = _read('static', 'js', 'services.js')
    m = re.search(r'function _collectServiceRows\(\) \{(.*?)\n\}', js, re.S)
    assert "querySelector('.svc-scheme')" in m.group(1)
    assert "scheme: 'http'," not in m.group(1), 'the scheme must come from the row, not a constant'


def test_editing_parses_the_scheme_back_out():
    js = _read('static', 'js', 'services.js')
    m = re.search(r'function _svcUrlToRow\(url\) \{(.*?)\n\}', js, re.S)
    assert m, 'the url parser moved'
    assert "startsWith('https://')" in m.group(1)


def test_editing_a_composite_loads_the_real_child_address():
    js = _read('static', 'js', 'services.js')
    m = re.search(r'function _svcChildToRow\(label\) \{(.*?)\n\}', js, re.S)
    assert m, 'the child loader moved'
    assert '_allServices.find' in m.group(1), \
        'owned children came back with an empty address before'
    assert "address: ''" not in m.group(1)


def test_a_new_service_defaults_to_a_plain_load_balancer():
    js = _read('static', 'js', 'services.js')
    m = re.search(r'async function openServiceModal\(existing\) \{(.*?)\n\}', js, re.S)
    assert m, 'the opener moved'
    assert ": 'loadBalancer');" in m.group(1), \
        'the common case is a plain service, weighted is the special one'


HC_FIELDS = ('svcHcEnabled', 'svcHcPath', 'svcHcInterval', 'svcHcTimeout', 'svcHcUnhealthy',
             'svcHcMethod', 'svcHcStatus', 'svcHcScheme', 'svcHcPort', 'svcHcHostname',
             'svcHcMode', 'svcHcFollow', 'svcHcHeaders')


def test_the_modal_can_author_every_health_check_field_traefik_supports():
    html = _read('templates', 'modals', 'service_modal.html')
    for el in HC_FIELDS:
        assert f'id="{el}"' in html, f'missing {el}'


def test_the_health_check_is_collected_and_sent():
    js = _read('static', 'js', 'services.js')
    m = re.search(r'function _collectHealthCheck\(\) \{(.*?)\n\}', js, re.S)
    assert m, 'the collector moved'
    body = m.group(1)
    for field in ('path', 'interval', 'timeout', 'unhealthyInterval', 'method', 'status',
                  'scheme', 'port', 'hostname', 'mode', 'followRedirects', 'headers'):
        assert field in body, f'{field} is never collected'
    assert 'healthCheck,' in js, 'the payload never carries the health check'
    assert "show('A health check needs a path to poll.')" in js


def test_editing_a_service_loads_its_existing_health_check():
    js = _read('static', 'js', 'services.js')
    assert '_svcHcFill(existing && !_compositeTypeOf(existing) ? (existing.loadBalancer || {}).healthCheck : null)' in js, \
        'opening the editor must show the health check already in the file, or saving would drop it'


def test_only_a_plain_pool_shows_the_section():
    js = _read('static', 'js', 'services.js')
    m = re.search(r'function _svcTypeChanged\(\) \{(.*?)\n\}', js, re.S)
    assert "hcSection.style.display = plain ? '' : 'none'" in m.group(1)


def test_a_multi_server_pool_without_one_is_flagged_on_the_card():
    js = _read('static', 'js', 'services.js')
    m = re.search(r'function _svcNeedsHealthCheck\(s\) \{(.*?)\n\}', js, re.S)
    assert m, 'the predicate moved'
    body = m.group(1)
    assert '!lb.healthCheck' in body and "(lb.servers || []).length > 1" in body
    assert '_svcNeedsHealthCheck(s) ?' in js, 'the card never renders the warning'
    assert 'var(--yellow)' in js[js.index('_svcNeedsHealthCheck(s) ?'):][:600]

let currentProtoFilter = 'all';
let _routeWasComposite = false;
let _routeCardEls = [];

let _apiStatusFilter = '';
let _routeEpFilter = '';

function filterApiStatus(v) {
    _apiStatusFilter = _apiStatusFilter === v ? '' : v;
    filterRoutes();
}

function filterRouteEntryPoint(name) {
    _routeEpFilter = _routeEpFilter === name ? '' : name;
    filterRoutes();
}

function clearRouteApiFilters() {
    _apiStatusFilter = '';
    _routeEpFilter = '';
}

function filterProto(proto) {
    clearRouteApiFilters();
    currentProtoFilter = proto;
    ['all','HTTP','TCP','UDP'].forEach(p => {
        const btn = document.getElementById('filter' + (p === 'all' ? 'All' : p));
        if (btn) btn.className = 'proto-btn text-xs px-3 py-1.5';
    });
    const activeClass = proto === 'all' ? 'active-http' : proto === 'http' ? 'active-http' : proto === 'tcp' ? 'active-tcp' : 'active-udp';
    const btnId = proto === 'all' ? 'filterAll' : 'filter' + proto.toUpperCase();
    document.getElementById(btnId).className = `proto-btn ${activeClass} text-xs px-3 py-1.5`;
    filterRoutes();
}

let currentRouteDomainFilter = '';
let currentRouteStatusFilter = 'all';

function filterRouteStatus(status) {
    clearRouteApiFilters();
    currentRouteStatusFilter = status;
    ['all','active','inactive'].forEach(s => {
        const btn = document.getElementById('filterStatus-' + s);
        if (btn) btn.className = 'proto-btn text-xs px-3 py-1.5';
    });
    const cls = status === 'active' ? 'active-http' : status === 'inactive' ? 'active-muted' : 'active-http';
    const btn = document.getElementById('filterStatus-' + status);
    if (btn) btn.className = `proto-btn ${cls} text-xs px-3 py-1.5`;
    filterRoutes();
}

function pickRouteDomain(val, label) {
    clearRouteApiFilters();
    currentRouteDomainFilter = val;
    document.getElementById('dd-route-domain-label').textContent = label;
    const btn = document.getElementById('dd-route-domain-btn');
    if (btn) btn.classList.toggle('active', !!val);
    document.querySelectorAll('#dd-route-domain-menu .live-dd-item').forEach(el => {
        el.classList.toggle('active', el.textContent.trim() === label);
    });
    toggleLiveDd('dd-route-domain');
    filterRoutes();
}

function clearRouteDeepFilters() {
    clearRouteApiFilters();
    filterRoutes();
}

function _renderRouteDeepFilters() {
    const bar = document.getElementById('routeDeepFilters');
    if (!bar) return;
    const chips = [];
    if (_routeEpFilter) {
        chips.push(['ph-door-open', 'entry point', _routeEpFilter, 'filterRouteEntryPoint(' + JSON.stringify(_routeEpFilter) + ')']);
    }
    if (_apiStatusFilter) {
        chips.push(['ph-pulse', 'status', _apiStatusFilter, 'filterApiStatus(' + JSON.stringify(_apiStatusFilter) + ')']);
    }
    if (!chips.length) { bar.style.display = 'none'; bar.innerHTML = ''; return; }
    bar.innerHTML = chips.map(([icon, label, value, clear]) =>
        '<button type="button" class="route-deep-chip" onclick="' + _esc(clear) + ';filterRoutes()">'
        + '<i class="ph-bold ' + icon + '"></i>'
        + '<span class="route-deep-label">' + _esc(label) + '</span>'
        + '<span class="route-deep-value">' + _esc(value) + '</span>'
        + '<i class="ph-bold ph-x"></i></button>').join('');
    bar.style.display = 'flex';
}

function filterRoutes() {
    const q = document.getElementById('searchRoutes').value.toLowerCase();
    _renderRouteDeepFilters();
    let visible = 0;
    for (const card of _routeCardEls) {
        const name    = card.dataset.name || '';
        const proto   = card.dataset.protocol || '';
        const domains = (card.dataset.domains || '').split('|').filter(Boolean);
        const enabled = card.dataset.enabled !== 'false';
        const eps = (card.dataset.eps || '').split('|').filter(Boolean);
        const show =
            (!q || name.includes(q)) &&
            (currentProtoFilter === 'all' || proto === currentProtoFilter) &&
            (!currentRouteDomainFilter || domains.some(d => d === currentRouteDomainFilter || d.endsWith('.' + currentRouteDomainFilter))) &&
            (currentRouteStatusFilter === 'all' || (currentRouteStatusFilter === 'active' && enabled) || (currentRouteStatusFilter === 'inactive' && !enabled)) &&
            (!_apiStatusFilter || card.dataset.apistatus === _apiStatusFilter || card.dataset.apibound === _apiStatusFilter || card.dataset.health === _apiStatusFilter) &&
            (!_routeEpFilter || eps.includes(_routeEpFilter));
        card.style.display = show ? '' : 'none';
        if (show) visible++;
    }
    const emptyEl = document.getElementById('routeEmpty');
    if (emptyEl && _routeCardEls.length > 0) {
        if (visible === 0) {
            const t = document.getElementById('routeEmptyText');
            const sub = document.getElementById('routeEmptySub');
            const cta = document.getElementById('routeEmptyCta');
            if (t) t.textContent = 'No routes match your filters';
            if (sub) {
                if (_routeEpFilter) {
                    sub.textContent = 'No route binds the entry point ' + _routeEpFilter + '.';
                    sub.style.display = '';
                } else if (_apiStatusFilter) {
                    sub.textContent = 'No route currently reports status ' + _apiStatusFilter + '.';
                    sub.style.display = '';
                } else {
                    sub.style.display = 'none';
                }
            }
            if (cta) {
                if (_routeEpFilter || _apiStatusFilter) {
                    cta.style.display = 'inline-flex';
                    cta.setAttribute('onclick', 'clearRouteDeepFilters()');
                    cta.innerHTML = '<i class="ph-bold ph-x"></i> Clear filter';
                } else {
                    cta.style.display = 'none';
                }
            }
            emptyEl.style.display = '';
        } else {
            emptyEl.style.display = 'none';
        }
    }
}

let currentProto = 'http';

const _svcRefMode = { http: false, tcp: false, udp: false };
const _SVC_MANUAL_IDS = {
    http: ['httpBackendsHead', 'httpTargetGrid', 'httpBackendRows', 'httpBackendsHint', 'httpLbAdvanced', 'httpSkipVerifyRow'],
    tcp:  ['tcpTargetGrid', 'tcpBackendRows', 'tcpBackendsFoot', 'tcpPriorityRow'],
    udp:  ['udpTargetGrid', 'udpBackendRows', 'udpBackendsFoot'],
};

function _svcRefSelect(proto) {
    return document.getElementById('serviceRef' + proto.charAt(0).toUpperCase() + proto.slice(1));
}

function setServiceRefMode(proto, on, opts) {
    _svcRefMode[proto] = !!on;
    const activeCls = { http: 'active-http', tcp: 'active-tcp', udp: 'active-udp' }[proto];
    const mBtn = document.getElementById(proto + 'SvcModeManualBtn');
    const rBtn = document.getElementById(proto + 'SvcModeRefBtn');
    if (mBtn) { mBtn.classList.toggle(activeCls, !on); mBtn.disabled = !!(opts && opts.lockManual); mBtn.style.opacity = (opts && opts.lockManual) ? '0.5' : ''; }
    if (rBtn) rBtn.classList.toggle(activeCls, !!on);
    const refEl = document.getElementById(proto + 'RefBackend');
    if (refEl) refEl.style.display = on ? '' : 'none';
    _SVC_MANUAL_IDS[proto].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.display = on ? 'none' : '';
    });
    if (typeof currentProto !== 'undefined' && currentProto === proto) setProtocol(proto);
}

async function _ensureServicesList() {
    if (window._tmServices) return window._tmServices;
    const out = { http: [], tcp: [], udp: [], live: { http: [], tcp: [], udp: [] } };
    try {
        const live = await agentFetch('/api/traefik/services').then(r => r.json());
        ['http', 'tcp', 'udp'].forEach(pr => {
            out.live[pr] = (live[pr] || []).map(sv => ({
                name: String(sv.name || ''),
                provider: sv.provider || String(sv.name || '').split('@')[1] || ''
            })).filter(sv => sv.name && sv.provider && sv.provider !== 'file');
        });
    } catch (e) {}
    try {
        const url = _activeAgent ? '/api/agents/' + _activeAgent.id + '/routes' : '/api/routes';
        const res = await fetch(url, { headers: { 'X-Requested-With': 'fetch' } });
        const data = await res.json();
        const own = data.services || { http: [], tcp: [], udp: [] };
        ['http', 'tcp', 'udp'].forEach(pr => { out[pr] = own[pr] || []; });
        window._tmServices = out;
    } catch (e) {
        window._tmServices = out;
    }
    return window._tmServices;
}

async function _populateServiceRefSelect(proto, selected) {
    const sel = _svcRefSelect(proto);
    if (!sel) return;
    const data = await _ensureServicesList();
    const own  = data[proto] || [];
    const live = ((data.live || {})[proto] || []);
    const groups = {};
    live.forEach(sv => { (groups[sv.provider] = groups[sv.provider] || []).push(sv.name); });
    if (proto === 'http' && !(groups.internal || []).includes('noop@internal')) {
        groups.internal = (groups.internal || []).concat('noop@internal');
    }
    const opt = n => `<option value="${_esc(n)}">${_esc(n)}</option>`;
    let html = own.length ? `<optgroup label="This config">${own.map(opt).join('')}</optgroup>` : '';
    Object.keys(groups).sort().forEach(pr => {
        const names = [...new Set(groups[pr])].sort();
        html += `<optgroup label="${_esc(pr)} (read only)">${names.map(opt).join('')}</optgroup>`;
    });
    sel.innerHTML = html;
    const known = own.concat(live.map(sv => sv.name)).concat(groups.internal || []);
    if (selected && !known.includes(selected)) {
        sel.insertAdjacentHTML('afterbegin', opt(selected));
    }
    if (selected) sel.value = selected;
    _updateRefTarget(proto);
}

function _updateRefTarget(proto) {
    const el = document.getElementById(proto + 'RefTarget');
    const sel = _svcRefSelect(proto);
    if (!el || !sel) return;
    const bare = (sel.value || '').split('@')[0];
    const pool = window._lastRenderedApps || (typeof APP_DATA !== 'undefined' ? APP_DATA : []) || [];
    const owner = pool.find(a => a.protocol === proto && ((a.service_name || '').split('@')[0]) === bare
        && a.target && a.target !== 'N/A');
    if (owner) {
        el.textContent = '\u2192 ' + owner.target + ((owner.servers || []).length > 1 ? ` (+${owner.servers.length - 1} more)` : '');
        el.style.display = '';
    } else {
        el.style.display = 'none';
    }
}

function _detectServiceRef(app, proto, svcList) {
    const raw = app.service_name || '';
    const bare = raw.split('@')[0];
    if (!raw || bare === app.name + '-service') return { refMode: false, raw: '' };
    const pool = window._lastRenderedApps || (typeof APP_DATA !== 'undefined' ? APP_DATA : []) || [];
    const refs = pool.filter(a => a.protocol === proto && ((a.service_name || '').split('@')[0]) === bare).length;
    return { refMode: !svcList.includes(bare) || refs > 1, raw };
}

function setProtocol(proto) {
    currentProto = proto;
    document.getElementById('protocolHidden').value = proto;

    
    ['http','tcp','udp'].forEach(p => {
        document.getElementById('proto' + p.toUpperCase()).className = 'proto-btn';
    });
    const cls = { http: 'active-http', tcp: 'active-tcp', udp: 'active-udp' };
    document.getElementById('proto' + proto.toUpperCase()).className = `proto-btn ${cls[proto]}`;

    
    document.querySelectorAll('.protocol-section').forEach(s => s.classList.remove('active'));
    document.getElementById(proto + 'Section').classList.add('active');

    
    document.getElementById('targetIp').required = proto === 'http' && !_svcRefMode.http;
    document.getElementById('targetPort').required = proto === 'http' && !_svcRefMode.http;
    if (document.getElementById('targetIpTcp')) {
        document.getElementById('targetIpTcp').required = proto === 'tcp' && !_svcRefMode.tcp;
        document.getElementById('targetPortTcp').required = proto === 'tcp' && !_svcRefMode.tcp;
    }
    if (document.getElementById('targetIpUdp')) {
        document.getElementById('targetIpUdp').required = proto === 'udp' && !_svcRefMode.udp;
        document.getElementById('targetPortUdp').required = proto === 'udp' && !_svcRefMode.udp;
    }
}

function setHttpRuleMode(mode) {
    const isAdv = mode === 'advanced';
    const simpleBtn = document.getElementById('httpModeSimpleBtn');
    const advBtn    = document.getElementById('httpModeAdvancedBtn');
    const simpleFields = document.getElementById('httpSimpleFields');
    const advFields    = document.getElementById('httpAdvancedFields');
    if (simpleBtn) { simpleBtn.classList.toggle('active-http', !isAdv); simpleBtn.classList.toggle('active-http', !isAdv); }
    if (advBtn)    { advBtn.classList.toggle('active-http', isAdv); }
    if (simpleFields) simpleFields.style.display = isAdv ? 'none' : '';
    if (advFields)    advFields.style.display    = isAdv ? '' : 'none';
    if (!isAdv) { const el = document.getElementById('httpRule'); if (el) el.value = ''; }
}

function _applyServiceTypeNotice(svcType, owned) {
    const editable = !svcType || svcType === 'loadBalancer' || !!owned;
    const notice = document.getElementById('svcTypeNotice');
    if (notice) notice.style.display = editable ? 'none' : 'flex';
    if (!editable) {
        const text = document.getElementById('svcTypeNoticeText');
        if (text) text.textContent = `This route points at a ${svcType} service, which can't be edited here. The target field is ignored on save - edit the service on the Services tab.`;
    }
    ['targetIp', 'targetPort', 'targetIpTcp', 'targetPortTcp', 'targetIpUdp', 'targetPortUdp'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.disabled = !editable;
    });
}

const HP_FEATURES = ['geolocation','camera','microphone','fullscreen','autoplay','payment','usb','display-capture','accelerometer','gyroscope','magnetometer'];
const HP_SELF_DEFAULT = ['geolocation','camera','microphone','fullscreen','autoplay'];

function _hpDefaults() {
    const perms = {};
    HP_FEATURES.forEach(f => perms[f] = HP_SELF_DEFAULT.includes(f) ? 'self' : 'block');
    return { perms, hsts: true, nosniff: true, frameDeny: true, referrer: 'strict-origin-when-cross-origin' };
}

function _buildHeadersPresetPerms() {
    const host = document.getElementById('hpPerms');
    if (!host || host.dataset.built) return;
    host.dataset.built = '1';
    HP_FEATURES.forEach(f => {
        const wrap = document.createElement('div');
        wrap.className = 'flex items-center justify-between gap-2';
        wrap.innerHTML = `<span class="text-sm" style="color:var(--text)">${f}</span>`
            + `<select id="hp_perm_${f}" name="hp_perm_${f}" onchange="_hpUserEdited()" class="input-field" style="max-width:9rem">`
            + `<option value="self">self</option><option value="all">all</option><option value="block">block</option></select>`;
        host.appendChild(wrap);
    });
}

function _applyHeadersPresetToggles(t) {
    HP_FEATURES.forEach(f => {
        const sel = document.getElementById('hp_perm_' + f);
        if (sel) sel.value = (t.perms && t.perms[f]) || 'block';
    });
    document.getElementById('hp_hsts').checked = !!t.hsts;
    document.getElementById('hp_nosniff').checked = !!t.nosniff;
    document.getElementById('hp_frameDeny').checked = !!t.frameDeny;
    document.getElementById('hp_referrer').value = t.referrer || '';
}

function _renderHeadersPresetState(on, custom) {
    document.getElementById('hpBody').style.display = (on && !custom) ? '' : 'none';
    const notice = document.getElementById('hpCustomNotice');
    notice.style.display = (on && custom) ? '' : 'none';
    if (on && custom) {
        const el = document.getElementById('hpCustomName');
        if (el) el.textContent = document.getElementById('serviceName').value + '-headers';
    }
}

function _hpUserEdited() {
    document.getElementById('headersPresetCustom').value = 'false';
    _renderHeadersPresetState(document.getElementById('hpEnabled').checked, false);
}

function _onHeadersPresetToggle(on) {
    document.getElementById('headersPresetEnabled').value = on ? 'true' : 'false';
    document.getElementById('headersPresetCustom').value = 'false';
    _renderHeadersPresetState(on, false);
}

function _resetHeadersPreset() {
    const section = document.getElementById('headersPresetSection');
    if (!section) return;
    _buildHeadersPresetPerms();
    section.style.display = '';
    document.getElementById('hpEnabled').checked = false;
    _applyHeadersPresetToggles(_hpDefaults());
    document.getElementById('headersPresetPresent').value = 'true';
    document.getElementById('headersPresetEnabled').value = 'false';
    document.getElementById('headersPresetCustom').value = 'false';
    _renderHeadersPresetState(false, false);
}

function _applyHeadersPreset(hp) {
    const section = document.getElementById('headersPresetSection');
    if (!section) return;
    _buildHeadersPresetPerms();
    if (!hp) {
        section.style.display = 'none';
        document.getElementById('hpEnabled').checked = false;
        _applyHeadersPresetToggles(_hpDefaults());
        document.getElementById('headersPresetPresent').value = '';
        document.getElementById('headersPresetEnabled').value = 'false';
        document.getElementById('headersPresetCustom').value = 'false';
        _renderHeadersPresetState(false, false);
        return;
    }
    section.style.display = '';
    let state = hp.state;
    if (state === 'custom' && document.getElementById('isEdit').value === 'false') state = 'off';
    const on = state === 'toggles' || state === 'custom';
    const custom = state === 'custom';
    document.getElementById('hpEnabled').checked = on;
    _applyHeadersPresetToggles(hp.toggles || _hpDefaults());
    document.getElementById('headersPresetPresent').value = 'true';
    document.getElementById('headersPresetEnabled').value = on ? 'true' : 'false';
    document.getElementById('headersPresetCustom').value = custom ? 'true' : 'false';
    _renderHeadersPresetState(on, custom);
}

function _streamingBufWarn() {
    const el = document.getElementById('streamingBufWarn');
    if (!el) return;
    const mws = (document.getElementById('middlewares').value || '').split(',').map(s => s.trim());
    el.style.display = mws.some(m => /(?:^|[-_.])(?:buffering|compress)(?:[-_.]|$)/i.test(m)) ? '' : 'none';
}

function _clearStreamingForce() {
    const ph = document.getElementById('passHostHeader');
    if (ph) { ph.disabled = false; delete ph.dataset.streamPrev; }
}

function _renderStreamingState(on) {
    document.getElementById('streamingNote').style.display = on ? '' : 'none';
    const ph = document.getElementById('passHostHeader');
    if (ph) {
        if (on) {
            if (ph.dataset.streamPrev === undefined) ph.dataset.streamPrev = ph.checked ? 'true' : 'false';
            ph.checked = true;
            ph.disabled = true;
        } else {
            ph.disabled = false;
            if (ph.dataset.streamPrev !== undefined) {
                ph.checked = ph.dataset.streamPrev === 'true';
                delete ph.dataset.streamPrev;
            }
        }
    }
    if (on) {
        const el = document.getElementById('streamingTpName');
        if (el) el.textContent = document.getElementById('serviceName').value + '-transport';
        _streamingBufWarn();
    }
}

function _onStreamingToggle(on) {
    document.getElementById('streamingPresetEnabled').value = on ? 'true' : 'false';
    _renderStreamingState(on);
}

function _resetStreamingPreset() {
    const section = document.getElementById('streamingPresetSection');
    if (!section) return;
    _clearStreamingForce();
    section.style.display = '';
    document.getElementById('streamingEnabled').checked = false;
    document.getElementById('streamingPresetPresent').value = 'true';
    document.getElementById('streamingPresetEnabled').value = 'false';
    _renderStreamingState(false);
}

function _applyStreamingPreset(on) {
    const section = document.getElementById('streamingPresetSection');
    if (!section) return;
    _clearStreamingForce();
    if (on == null) {
        section.style.display = 'none';
        document.getElementById('streamingEnabled').checked = false;
        document.getElementById('streamingPresetPresent').value = '';
        document.getElementById('streamingPresetEnabled').value = 'false';
        _renderStreamingState(false);
        return;
    }
    section.style.display = '';
    document.getElementById('streamingEnabled').checked = !!on;
    document.getElementById('streamingPresetPresent').value = 'true';
    document.getElementById('streamingPresetEnabled').value = on ? 'true' : 'false';
    _renderStreamingState(!!on);
}

async function openModal() {
    _routeWasComposite = false;
    closeOtherPanels('appModal');
    document.getElementById('isEdit').value = 'false';
    document.getElementById('modalTitle').innerText = 'Add Route';
    _applyServiceTypeNotice('loadBalancer');
    _resetLbAdvanced();
    document.getElementById('originalId').value = '';
    ['serviceName','subdomain','targetIp','targetPort','middlewares','tcpRule','httpRule'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });
    setHttpRuleMode('simple');
    await Promise.all([
        _initEntrypointChips('http', []),
        _initEntrypointChips('tcp', []),
        _initEntrypointChips('udp', []),
        _initMiddlewareChips([]),
        _initMiddlewareChips([], 'tcp')
    ]);
    setTcpTlsMode('none', document.getElementById('tcpTlsNone'));
    const crHttp = document.getElementById('certResolver');
    if (crHttp) { crHttp.value = (!_activeAgent && availableCertResolvers.length > 0) ? availableCertResolvers[0] : '__disabled__'; toggleWildcardSection(crHttp.value); }
    const crTcp = document.getElementById('certResolverTcp');
    if (crTcp) crTcp.value = (!_activeAgent && availableCertResolvers.length > 0) ? availableCertResolvers[0] : '__disabled__';
    const wcChk = document.getElementById('wildcardCheckbox'); if (wcChk) wcChk.checked = false;
    const mainEl = document.getElementById('tlsWildcardMain'); if (mainEl) mainEl.value = '';
    const sansEl = document.getElementById('tlsWildcardSans'); if (sansEl) sansEl.value = '';
    ['http', 'tcp', 'udp'].forEach(pr => setServiceRefMode(pr, false));
    await _ensureServicesList();
    ['http', 'tcp', 'udp'].forEach(pr => _populateServiceRefSelect(pr, ''));
    setProtocol('http');
    _resetHeadersPreset();
    _resetStreamingPreset();
    const tlsOptSel = document.getElementById('tlsOptionsProfileSelect');
    if (tlsOptSel) tlsOptSel.value = '';
    _populateTlsOptionsSelect();
    _updateRouteModalForAgent();
    _initDomainChips([]);
    await Promise.all([
        _populateConfigFileSelect('route'),
        _loadAgentResolversIntoSelects()
    ]);
    _openRoutePanel();
}

function _openRoutePanel() {
    document.getElementById('appModal').classList.add('open');
    document.getElementById('appModalBackdrop').classList.add('open');
    if (!setDetailDockOpen(true)) document.body.style.overflow = 'hidden';
}

function closeModal() {
    setDetailDockOpen(false);
    document.getElementById('appModal').classList.remove('open');
    document.getElementById('appModalBackdrop').classList.remove('open');
    document.body.style.overflow = '';
}

function _updateRouteModalForAgent(rebuildBody) {
    const domainCol  = document.getElementById('routeDomainCol');
    const domLabel   = document.getElementById('agentDomainLabel');
    const domBody    = document.getElementById('routeDomainBody');
    const subLabel   = document.getElementById('routeSubdomainLabel');
    const subInput   = document.getElementById('subdomain');
    const list = _domainsForForm();
    if (_activeAgent && list.length === 0) {
        if (domainCol) domainCol.style.display = 'none';
        if (subLabel) subLabel.textContent = 'Hostname';
        if (subInput) subInput.placeholder = 'app.example.com';
    } else {
        if (domainCol) domainCol.style.display = '';
        if (subLabel) subLabel.textContent = 'Subdomain';
        if (subInput) subInput.placeholder = 'app';
        if (domLabel) domLabel.textContent = list.length > 1 ? 'Domains' : 'Domain';
        if (rebuildBody !== false && domBody) {
            if (list.length >= 1) {
                if (!document.getElementById('domainChips')) {
                    domBody.innerHTML = `<div id="domainChips" class="flex flex-wrap gap-1.5 p-2 rounded-lg" style="background:var(--input-bg);border:1px solid var(--border);min-height:38px"></div><div id="domainHiddenInputs"></div>`;
                }
            } else {
                domBody.innerHTML = '';
            }
        }
    }
}

function onRouteConfigFileChange(sel) {
    const newInput = document.getElementById('newRouteFileName');
    const cfHid    = document.getElementById('configFile');
    if (sel.value === '__new__') {
        if (newInput) newInput.style.display = '';
        const svcName = (document.getElementById('serviceName')?.value || '').trim().toLowerCase().replace(/[^a-z0-9-]/g, '-');
        if (newInput && !newInput.value && svcName) newInput.value = `app-${svcName}.yml`;
        if (cfHid) cfHid.value = newInput?.value || '';
    } else {
        if (newInput) { newInput.style.display = 'none'; newInput.value = ''; }
        if (cfHid) cfHid.value = sel.value;
    }
}

async function saveRouteAjax(event) {
    event.preventDefault();
    const form = event.target;
    const fn = document.getElementById('newRouteFileName');
    if (fn && fn.style.display !== 'none' && fn.value && !/\.ya?ml$/.test(fn.value)) {
        fn.value += '.yml';
        document.getElementById('configFile').value = fn.value;
    }
    const cfWrap = document.getElementById('configFileSelectWrap');
    const cfSel  = document.getElementById('configFileSelect');
    if (cfWrap && cfWrap.style.display !== 'none' && cfSel && !cfSel.value
            && !document.getElementById('configFile').value) {
        showToast('Select a config file for this route', 'error');
        return;
    }
    const btn = form.querySelector('button[type=submit]');
    btn.disabled = true;
    try {
        _writeBackendsJson();
        const fd = new FormData(form);
        if (_svcRefMode[currentProto]) {
            const _refSel = _svcRefSelect(currentProto);
            fd.append('serviceRef', _refSel ? _refSel.value : '');
        }
        if (_activeAgent) fd.append('agent_id', _activeAgent.id);
        const res = await fetch(form.action, { method:'POST', headers:{'X-Requested-With':'fetch'}, body: fd });
        if (!res.ok) { showToast(await _errText(res, 'Error saving route'), 'error'); return; }
        const json = await res.json();
        showToast(json.message || json.error || 'Error saving route', json.ok ? 'success' : 'error');
        if (json.ok) { closeModal(); refreshRoutes(); fetchNotifications(); if (typeof window.rmInvalidateData === 'function') window.rmInvalidateData(); setTimeout(fetchNotifications, 8000); }
    } catch(e) {
        showToast(_netErrText(e, 'Error saving route'), 'error');
    } finally {
        btn.disabled = false;
    }
}

async function deleteRoute(id, configFile) {
    const shown = String(id).includes('::') ? String(id).split('::').slice(1).join('::') : String(id);
    const where = configFile ? ' from ' + configFile : '';
    if (!await _confirm('Delete route "' + shown + '"' + where + '? This removes it from the config file and stops serving it.', 'Delete Route', 'Delete', 'DELETE')) return;
    const data = new FormData();
    data.append('csrf_token', document.querySelector('meta[name="csrf-token"]')?.content || '');
    if (configFile) data.append('configFile', configFile);
    if (_activeAgent) data.append('agent_id', _activeAgent.id);
    try {
        const res = await fetch('/delete/' + encodeURIComponent(id), { method:'POST', headers:{'X-Requested-With':'fetch'}, body: data });
        if (!res.ok) { showToast(await _errText(res, 'Error deleting route'), 'error'); return; }
        const json = await res.json();
        showToast(json.message || json.error || 'Error deleting route', json.ok ? 'success' : 'error');
        if (json.ok) { refreshRoutes(); fetchNotifications(); if (typeof window.rmInvalidateData === 'function') window.rmInvalidateData(); }
    } catch(e) { showToast(_netErrText(e, 'Error deleting route'), 'error'); }
}

async function toggleRoute(id, currentlyEnabled, silent = false) {
    const data = new FormData();
    data.append('csrf_token', document.querySelector('meta[name="csrf-token"]')?.content || '');
    try {
        const res = await fetch('/api/routes/' + encodeURIComponent(id) + '/toggle', {
            method: 'POST',
            headers: { 'X-Requested-With': 'fetch', 'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]')?.content || '', 'Content-Type': 'application/json' },
            body: JSON.stringify({ enable: !currentlyEnabled, agent_id: _activeAgent ? _activeAgent.id : '', csrf_token: document.querySelector('meta[name="csrf-token"]')?.content || '' })
        });
        if (!res.ok) {
            if (!silent) showToast(await _errText(res, 'Failed to toggle route'), 'error');
            return;
        }
        const json = await res.json();
        if (json.ok) {
            if (!silent) { showToast(currentlyEnabled ? 'Route disabled.' : 'Route enabled.', 'success'); refreshRoutes(); }
            if (typeof window.rmInvalidateData === 'function') window.rmInvalidateData();
        } else {
            if (!silent) showToast(json.message || json.error || 'Failed to toggle route.', 'error');
        }
    } catch(e) { if (!silent) showToast(_netErrText(e, 'Error toggling route'), 'error'); }
}

function _clearRouteViews(message) {
    window._tmServices = null;
    try { renderRouteGrid([]); } catch (e) {}
    try { renderMwGrid([]); } catch (e) {}
    try { loadOverviewStats(); } catch (e) {}
    const where = (typeof _activeAgent !== 'undefined' && _activeAgent)
        ? _activeAgent.name : 'this server';
    _renderConfigErrorBanner([
        `Showing nothing for ${where}: ${message}. Nothing below is from another server.`,
    ]);
    if (message) showToast(message, 'error');
}

function _paintRoutes(data) {
    if (data.services) {
        const keep = (window._tmServices || {}).live;
        window._tmServices = Object.assign({ live: keep || { http: [], tcp: [], udp: [] } }, data.services);
        if (!keep) window._tmServices = null;
    }
    renderRouteGrid(data.apps || []);
    renderMwGrid(data.middlewares || []);
    loadOverviewStats();
    _renderConfigErrorBanner(data.configErrors || []);
}

async function refreshRoutes() {
    tabCacheHydrate('routes', _paintRoutes);
    try {
        let res;
        if (_activeAgent) {
            res = await fetch('/api/agents/' + _activeAgent.id + '/routes', { headers: {'X-Requested-With': 'fetch'} });
        } else {
            res = await fetch('/api/routes');
        }
        if (!res.ok) {
            _clearRouteViews(await _errText(res, 'Could not load routes'));
            return;
        }
        const data = await res.json();
        _paintRoutes(data);
        tabCachePut('routes', { apps: data.apps || [], middlewares: data.middlewares || [],
                                services: data.services || null, configErrors: data.configErrors || [] });
    } catch(e) {
        console.error('refreshRoutes failed:', e);
        _clearRouteViews(_netErrText(e, 'Could not load routes'));
    }
}

function _renderConfigErrorBanner(errors) {
    const el = document.getElementById('configErrorBanner');
    if (!el) return;
    if (!errors.length) { el.style.display = 'none'; el.innerHTML = ''; return; }
    el.style.display = 'block';
    el.innerHTML = errors.map(e =>
        `<div class="flex items-start gap-2 mb-1 last:mb-0">
            <i class="ph-bold ph-warning-circle flex-shrink-0 mt-0.5" style="color:var(--yellow)"></i>
            <div class="text-xs"><span class="font-semibold" style="color:var(--text)">${_esc(e.file)}</span><span class="ml-2" style="color:var(--muted)">${_esc(e.error)}</span></div>
        </div>`
    ).join('');
}

function _setAgentBanner(_show) {}

async function pingAllRoutes() {
    const cards = Array.from(document.querySelectorAll('.route-card')).filter(c => c.dataset.protocol === 'http');
    const pingable = cards.filter(c => {
        if (c.dataset.enabled === 'false') return false;
        const d = (c.dataset.domains || '').split('|').find(d => d && !d.includes('{') && !d.includes('*'));
        return !!d;
    });
    if (!pingable.length) { showToast('No pingable HTTP routes found', 'info'); return; }
    showToast(`Pinging ${pingable.length} HTTP route${pingable.length > 1 ? 's' : ''}\u2026`, 'success');
    let online = 0, degraded = 0, offline = 0;
    const offlineRoutes = [], degradedRoutes = [];
    for (const card of pingable) {
        const domain   = (card.dataset.domains || '').split('|').find(d => d && !d.includes('{') && !d.includes('*'));
        const target   = card.dataset.target || '';
        const servers  = (card.dataset.servers || '').split('|').filter(Boolean);
        const scheme   = card.dataset.tls === '1' ? 'https' : 'http';
        const rid      = card.dataset.rid || card.dataset.routekey;
        const statusEl = card.querySelector('.status-dot');
        if (statusEl) { statusEl.className = 'status-dot status-checking'; statusEl.title = 'Pinging\u2026'; }
        try {
            const params = `/api/ping?url=${encodeURIComponent(scheme + '://' + domain)}`
                + (target ? '&fallback=' + encodeURIComponent(target) : '')
                + servers.map(sv => '&servers=' + encodeURIComponent(sv)).join('');
            const data = await fetch(params).then(r => r.json());
            if (typeof window._rhRemember === 'function') window._rhRemember(rid, data);
            if (statusEl && typeof window._rhDot === 'function') {
                const dot = window._rhDot(window._rhGet(rid));
                statusEl.className = 'status-dot ' + dot.cls;
                statusEl.title = dot.title;
            }
            if (data.state === 'degraded') { degraded++; degradedRoutes.push(domain); }
            else if (data.ok) { online++; }
            else { offline++; offlineRoutes.push(domain); }
        } catch(e) {
            if (statusEl) { statusEl.className = 'status-dot status-unknown'; statusEl.title = 'Ping failed'; }
            offline++; offlineRoutes.push(domain);
        }
    }
    if (typeof _sdApplyRouteCards === 'function') _sdApplyRouteCards();
    const total = online + degraded + offline;
    const bits  = [];
    if (offlineRoutes.length)  bits.push('unreachable: ' + offlineRoutes.join(', '));
    if (degradedRoutes.length) bits.push('degraded: ' + degradedRoutes.join(', '));
    const type = bits.length ? 'warning' : 'info';
    const msg  = bits.length
        ? `Ping all: ${online}/${total} fully online - ${bits.join(' - ')}`
        : `Ping all: all ${total} route${total !== 1 ? 's' : ''} online`;
    const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
    fetch('/api/notifications/add', { method:'POST', headers:{'Content-Type':'application/json','X-CSRF-Token':csrf}, body: JSON.stringify({type, message: msg, category: 'traefik'}) })
        .then(() => fetchNotifications());
}
const _ROUTE_ICON_CDN = 'https://cdn.jsdelivr.net/gh/selfhst/icons@main/png';

function _routeIconSlug(app) {
    let s = (app.service_name || app.name || '').split('@')[0];
    s = s.replace(/:\d+$/, '').replace(/[-_](?:service|svc|router|app|container|pod)s?$/i, '');
    return s.toLowerCase().replace(/[^a-z0-9-]/g, '');
}

function _routeIconUrl(app) {
    const cfg = (typeof _rmConfig !== 'undefined' && _rmConfig) ? _rmConfig : {};
    const ov  = (cfg.route_overrides || {})[app.id] || {};
    if (ov.icon_type === 'url'  && ov.icon_url)  return ov.icon_url;
    if (ov.icon_type === 'slug' && ov.icon_slug) return `${_ROUTE_ICON_CDN}/${ov.icon_slug}.png`;
    const tmName = (cfg.tm_route_name || 'traefik-manager').toLowerCase();
    if ((app.name || '').toLowerCase() === tmName) return tmUrl('/static/icons/icon.png');
    const s = _routeIconSlug(app);
    return s ? `${_ROUTE_ICON_CDN}/${s}.png` : '';
}

async function _ensureRouteIconConfig() {
    if (window._routeIconCfgLoaded) return;
    window._routeIconCfgLoaded = true;
    if (typeof _rmDataLoaded !== 'undefined' && _rmDataLoaded) return;
    try {
        const r = await fetch('/api/dashboard/config');
        const c = await r.json();
        if (c && typeof c === 'object' && typeof _rmConfig !== 'undefined') _rmConfig = c;
    } catch (_) {}
}

function _routeIconHtml(app) {
    if (!window._showRouteIcons) return '';
    const url = _routeIconUrl(app);
    if (!url) return '';
    const slug = _routeIconSlug(app);
    return `<img src="${url}" data-slug="${slug}" onerror="window.rmIconFallback(this)" alt="" class="route-app-icon" style="width:18px;height:18px;border-radius:4px;object-fit:contain;flex-shrink:0">`;
}

function _tmFolderMode(apps) {
    const d = new Set((apps || []).filter(a => !a.provider || a.provider === 'file')
                                  .map(a => a.configFile).filter(Boolean));
    return d.size > 1;
}

function _tmCopy(val) {
    return `<button type="button" class="tm-copy" title="Copy" onclick="event.stopPropagation();_copyToClipboard(${_jsArg(val)})"><i class="ph-bold ph-copy"></i></button>`;
}

function _tmCf(name) {
    if (!name) return '';
    const short = String(name).replace(/\.(ya?ml)$/i, '');
    return `<span class="tm-cf" title="${_esc(name)}"><i class="ph-bold ph-file-code"></i>${_esc(short)}</span>`;
}

function _tmRouteCard(app, i, opts) {
    const proto      = (app.protocol || 'http').toLowerCase();
    const enabled    = app.enabled !== false;
    const isFile     = !app.provider || app.provider === 'file';
    const appJson    = JSON.stringify(app).replace(/'/g, '&#39;');
    const simpleHost = /^Host\(`[^`]+`\)(\s*\|\|\s*Host\(`[^`]+`\))*$/.test((app.rule || '').trim());
    const allDomains = [...(app.rule || '').matchAll(/Host\(`([^`]+)`\)/g)].map(m => m[1]);
    const domain0    = allDomains[0] || '';
    const openUrl    = (proto === 'http' && simpleHost && domain0 && !domain0.includes('{') && !domain0.includes('*') && !domain0.includes('HostRegexp')) ? 'https://' + domain0 : '';
    const bulkSel    = _bulkMode && _bulkSelected.has(app.id);

    const glyphs = [
        app.provider && app.provider !== 'file'
            ? `<i class="ph-bold ph-cube tm-glyph" style="color:var(--muted)" title="Managed by ${_esc(app.provider)} - read only"></i>` : '',
        !enabled ? '<i class="ph-bold ph-pause tm-glyph" style="color:var(--muted)" title="Disabled"></i>' : '',
        app.insecureSkipVerify
            ? '<i class="ph-bold ph-shield-warning tm-glyph" style="color:var(--orange)" title="insecureSkipVerify - backend certificate not verified"></i>' : '',
        proto === 'udp' ? '' : (app.tls
            ? '<i class="ph-bold ph-lock-simple tm-glyph" style="color:var(--muted)" title="TLS"></i>'
            : '<i class="ph-bold ph-lock-simple-open tm-glyph" style="color:var(--yellow)" title="No TLS"></i>'),
    ].join('');

    const iconUrl = (typeof _routeIconUrl === 'function' && window._showRouteIcons) ? _routeIconUrl(app) : '';
    const head = iconUrl
        ? `<span class="tm-ic tm-ic-tile" data-mono="${_esc(_tmMono(app.name))}"><img src="${iconUrl}" data-slug="${_esc(_routeIconSlug(app))}" onerror="window.rmIconFallback(this)" alt="" class="route-app-icon"><span class="status-dot status-checking" title="Checking..."></span></span>`
        : `<span class="tm-ic-bare"><span class="status-dot status-checking" title="Checking..."></span></span>`;

    let valRows;
    if (proto === 'http' && simpleHost && allDomains.length) {
        valRows = allDomains.slice(0, 2).map((d, n) =>
            `<div class="tm-val tm-val-host"><i class="ph-bold ph-globe-simple" ${n ? 'style="opacity:0"' : ''}></i><span class="tm-v">${_esc(d)}</span>` +
            (allDomains.length > 2 && n === 1 ? `<span class="tm-more" title="${_esc(allDomains.join(', '))}">+${allDomains.length - 2}</span>` : '') +
            _tmCopy(d) + '</div>').join('');
    } else if (app.rule) {
        valRows = `<div class="tm-val tm-val-rule"><i class="ph-bold ph-brackets-curly"></i><span class="tm-v" title="${_esc(app.rule)}">${_esc(app.rule)}</span>${_tmCopy(app.rule)}</div>`;
    } else {
        valRows = '';
    }
    const nBackends = (app.servers || []).length;
    valRows += `<div class="tm-val tm-val-target"><i class="ph-bold ph-arrow-elbow-down-right"></i><span class="tm-v">${_esc(app.target)}</span>` +
        (nBackends > 1 ? `<span class="tm-more" title="${nBackends} backends, load balanced">+${nBackends - 1}</span>` : '') +
        _tmCopy(app.target) + '</div>';

    const eps = (app.entryPoints || []).join(' \u00b7 ');
    const mws = [
        ...(app.middlewares || []).map(m => _esc(m)),
        ...(app.entrypointMiddlewares || []).map(m => `<span title="Applied via entrypoint">${_esc(m)} ep</span>`),
    ].join(' \u00b7 ');
    const meta = [
        eps ? `<span>${_esc(eps)}</span>` : '',
        mws ? `<span class="tm-mw">${mws}</span>` : '',
        app.service_name ? `<span class="tm-svcname">${_esc(app.service_name)}</span>` : '',
    ].filter(Boolean).join('<span class="tm-sep"> \u00b7 </span>');

    const rail = `<span class="tm-rail" onclick="event.stopPropagation()">` +
        (openUrl ? '<i class="ph-bold ph-arrow-up-right tm-hint"></i>' : '') +
        `<button type="button" class="tm-btn" title="More" data-app='${appJson}' data-openurl="${_esc(openUrl)}" onclick="event.stopPropagation();_openRouteMenu(event,this)"><i class="ph-bold ph-dots-three"></i></button>` +
        `<button type="button" class="tm-btn" title="Edit" data-app='${appJson}' onclick="event.stopPropagation();handleEdit(this)"><i class="ph-bold ph-pencil-simple"></i></button>` +
        (isFile ? `<span role="switch" tabindex="0" aria-checked="${enabled}" class="toggle-switch toggle-sm${enabled ? ' on' : ''}" title="${enabled ? 'Disable route' : 'Enable route'}" onclick="event.stopPropagation();toggleRoute(${_jsArg(app.id)},${enabled})" onkeydown="if(event.key===' '||event.key==='Enter'){event.preventDefault();event.stopPropagation();toggleRoute(${_jsArg(app.id)},${enabled});}"><span class="toggle-knob"></span></span>` : '') +
        '</span>';

    const bulkCheckbox = _bulkMode
        ? `<input type="checkbox" class="bulk-check" onclick="event.stopPropagation()" ${bulkSel ? 'checked' : ''} onchange="toggleBulkSelect(${_jsArg(app.id)})" style="width:15px;height:15px;accent-color:var(--blue);cursor:pointer;flex-shrink:0;margin-top:6px">`
        : '';

    const dataAttrs = `data-protocol="${proto}" data-name="${_esc(app.name.toLowerCase())}" data-routekey="${_esc(app.name)}" data-idx="${i}" data-rid="${_esc(app.id)}" data-enabled="${enabled}" data-domains="${allDomains.map(d => _esc(d)).join('|')}" data-target="${_esc(app.target)}" data-configfile="${_esc(app.configFile || '')}" data-eps="${(app.entryPoints || []).map(e => _esc(e)).join('|')}" data-servers="${(app.servers || []).map(sv => _esc(sv)).join('|')}" data-tls="${app.tls ? '1' : ''}"`;

    return `<div class="tm-card route-card${bulkSel ? ' tm-sel' : ''}" ${dataAttrs} style="--tm-accent:var(--blue)" onclick="openRouteDetailFromCard(this)">
        <div class="tm-head">${bulkCheckbox}${head}
            <div class="tm-head-txt">
                <div class="tm-title">${proto !== 'http' ? `<span class="tm-proto tm-proto-${proto}">${proto.toUpperCase()}</span>` : ''}<span class="tm-name">${_esc(app.name)}</span>${glyphs}</div>
            </div>${rail}
        </div>
        <div class="tm-vals">${valRows}</div>
        <div class="tm-foot"><span class="tm-meta">${meta}</span>${opts.showCf ? _tmCf(app.configFile) : ''}</div>
    </div>`;
}

function renderRouteGrid(apps) {
    window._lastRenderedApps = apps;
    if (window._showRouteIcons && !window._routeIconCfgLoaded) {
        _ensureRouteIconConfig().then(() => {
            renderRouteGrid(window._lastRenderedApps || apps);
            if (typeof filterRoutes === 'function') filterRoutes();
        });
    }
    if (_activeAgent) apps = apps.filter(a => !a.provider || a.provider === 'file');
    setTabCount('services', apps.filter(a => (!a.provider || a.provider === 'file') && a.enabled !== false).length);
    const grid = document.getElementById('routeGrid');
    if (!grid) return;
    const emptyEl = document.getElementById('routeEmpty');
    if (apps.length === 0) {
        grid.className = 'grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4';
        grid.innerHTML = '';
        _routeCardEls = [];
        if (emptyEl) {
            const t = document.getElementById('routeEmptyText');
            const sub = document.getElementById('routeEmptySub');
            const cta = document.getElementById('routeEmptyCta');
            if (t) t.textContent = _activeAgent ? 'No routes on this server yet' : 'No routes yet';
            if (sub) {
                sub.textContent = 'Create your first route to start managing your Traefik proxy.';
                sub.style.display = '';
            }
            if (cta) {
                cta.setAttribute('onclick', 'openModal()');
                cta.innerHTML = '<i class="ph-bold ph-plus"></i> Add Route';
                cta.style.display = 'inline-flex';
            }
            emptyEl.style.display = '';
        }
        return;
    }
    if (emptyEl) emptyEl.style.display = 'none';
    const _allAppsForRender = apps;
    const _tmOn = _routeViewMode !== 'list';
    const _tmCfShow = _tmOn ? _tmFolderMode(apps) : false;
    grid.innerHTML = apps.map((app, i) => {
        if (_tmOn) return _tmRouteCard(app, i, { showCf: _tmCfShow });
        const proto = app.protocol || 'http';
        const allDomains = [...(app.rule || '').matchAll(/Host\(`([^`]+)`\)/g)].map(m => m[1]);
        const domain     = allDomains[0] || '';
        const isSimpleHostRule = /^(Host\(`[^`]+`\)(\s*\|\|\s*Host\(`[^`]+`\))*)$/.test((app.rule || '').trim());
        const isComplexRule = !isSimpleHostRule && !!app.rule;
        const ruleLabel  = isComplexRule ? 'Rule' : 'Domain';
        const badgeClass = proto === 'http' ? 'badge-http' : (proto === 'tcp' ? 'badge-tcp' : 'badge-udp');
        const tlsBadge = app.tls ? `<span class="badge badge-green" style="font-size:9px"><i class="ph-bold ph-lock"></i> TLS${app.tlsOptionsProfile ? ' ' + _esc(app.tlsOptionsProfile) : ''}</span>` : '';
        const insecureBadge = app.insecureSkipVerify ? `<span class="badge" style="font-size:9px;background:rgba(240,180,0,0.12);color:#d4a017;border:1px solid rgba(240,180,0,0.3)" title="insecureSkipVerify enabled"><i class="ph-bold ph-warning"></i> TLS skip</span>` : '';
        const tlsProfileBadge = '';
        const openLink = (proto === 'http' && domain && !domain.includes('{') && !domain.includes('*') && !domain.includes('HostRegexp'))
            ? `<a href="https://${domain}" target="_blank" class="pill-btn pill-btn-blue" title="Open site"><i class="ph-bold ph-arrow-square-out text-sm"></i></a>` : '';
        const openUrl  = (proto === 'http' && domain && !domain.includes('{') && !domain.includes('*') && !domain.includes('HostRegexp')) ? 'https://' + domain : '';
        const epBadges = (app.entryPoints || []).map(ep => '<span class="badge badge-muted" style="font-size:9px">' + _esc(ep) + '</span>').join('');
        const mwBadges   = (app.middlewares || []).map(mw => `<span class="badge" style="background:rgba(163,113,247,0.1);color:var(--purple);border:1px solid rgba(163,113,247,0.25)">${_esc(mw)}</span>`).join('');
        const epMwBadges = (app.entrypointMiddlewares || []).map(mw => `<span class="badge badge-muted" title="Applied via entrypoint">${_esc(mw)} <span style="font-size:9px;opacity:0.6">ep</span></span>`).join('');
        const enabled = app.enabled !== false;
        const isFileRoute = !app.provider || app.provider === 'file';
        const appJson = JSON.stringify(app).replace(/'/g, '&#39;');
        const iconHtml = _routeIconHtml(app);
        const toggleIcon = enabled ? 'ph-toggle-right' : 'ph-toggle-left';
        const toggleTitle = enabled ? 'Disable route' : 'Enable route';
        const toggleBtn = isFileRoute ? `<button type="button" onclick="toggleRoute(${_jsArg(app.id)},${enabled})" class="pill-btn ${enabled ? 'pill-btn-green' : 'pill-btn-muted'}" title="${toggleTitle}"><i class="ph-bold ${toggleIcon} text-sm"></i></button>` : '';
        const _copyBtn = (val, col) => `<button onclick="event.stopPropagation();_copyToClipboard(${_jsArg(val)})" title="Copy" style="background:none;border:none;cursor:pointer;padding:2px;color:var(--muted);flex-shrink:0;line-height:1;border-radius:3px" onmouseover="this.style.color='var(--${col})'" onmouseout="this.style.color='var(--muted)'"><svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 256 256" fill="currentColor"><path d="M216,32H88a8,8,0,0,0-8,8V80H40a8,8,0,0,0-8,8V216a8,8,0,0,0,8,8H168a8,8,0,0,0,8-8V176h40a8,8,0,0,0,8-8V40A8,8,0,0,0,216,32Zm-56,176H48V96H160Zm48-48H176V88a8,8,0,0,0-8-8H96V48H208Z"/></svg></button>`;
        const domainDisplay = allDomains.length > 1
            ? `<div style="display:flex;flex-direction:column;gap:2px">${allDomains.map(d => `<div style="display:flex;align-items:center;gap:4px"><div class="text-xs font-mono truncate" style="color:var(--blue)">${_esc(d)}</div>${_copyBtn(d,'blue')}</div>`).join('')}</div>`
            : isComplexRule
                ? `<div style="display:flex;align-items:center;gap:4px"><div class="text-xs font-mono" style="color:var(--blue);word-break:break-all" title="${_esc(app.rule)}">${_esc(app.rule)}</div>${_copyBtn(app.rule,'blue')}</div>`
                : `<div style="display:flex;align-items:center;gap:4px"><div class="text-xs font-mono truncate" style="color:var(--blue)">${_esc(domain || app.rule)}</div>${_copyBtn(domain || app.rule,'blue')}</div>`;
        const httpBody = `<div class="rounded-md p-2.5" style="background:var(--input-bg);border:1px solid var(--border)"><div class="text-xs font-semibold uppercase tracking-wider mb-1" style="color:var(--muted)">${ruleLabel}</div>${domainDisplay}</div><div class="rounded-md p-2.5" style="background:var(--input-bg);border:1px solid var(--border)"><div class="text-xs font-semibold uppercase tracking-wider mb-1" style="color:var(--muted)">Target</div><div style="display:flex;align-items:center;gap:4px"><div class="text-xs font-mono truncate" style="color:var(--green)">${_esc(app.target)}</div>${(app.servers||[]).length>1?`<span class="badge badge-muted" style="font-size:9px" title="${(app.servers||[]).length} backends">+${(app.servers||[]).length-1}</span>`:''}<button onclick="event.stopPropagation();_copyToClipboard(${_jsArg(app.target)})" title="Copy" style="background:none;border:none;cursor:pointer;padding:2px;color:var(--muted);flex-shrink:0;line-height:1;border-radius:3px" onmouseover="this.style.color='var(--green)'" onmouseout="this.style.color='var(--muted)'"><svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 256 256" fill="currentColor"><path d="M216,32H88a8,8,0,0,0-8,8V80H40a8,8,0,0,0-8,8V216a8,8,0,0,0,8,8H168a8,8,0,0,0,8-8V176h40a8,8,0,0,0,8-8V40A8,8,0,0,0,216,32Zm-56,176H48V96H160Zm48-48H176V88a8,8,0,0,0-8-8H96V48H208Z"/></svg></button></div></div>`; const tcpBody = `${app.rule ? `<div class="rounded-md p-2.5" style="background:var(--input-bg);border:1px solid var(--border)"><div class="text-xs font-semibold uppercase tracking-wider mb-1" style="color:var(--muted)">Rule</div><div class="text-xs font-mono truncate" style="color:var(--blue)">${_esc(app.rule)}</div></div>` : ''}<div class="rounded-md p-2.5" style="background:var(--input-bg);border:1px solid var(--border)"><div class="text-xs font-semibold uppercase tracking-wider mb-1" style="color:var(--muted)">Target</div><div style="display:flex;align-items:center;gap:4px"><div class="text-xs font-mono truncate" style="color:var(--green)">${_esc(app.target)}</div>${(app.servers||[]).length>1?`<span class="badge badge-muted" style="font-size:9px" title="${(app.servers||[]).length} backends">+${(app.servers||[]).length-1}</span>`:''}<button onclick="event.stopPropagation();_copyToClipboard(${_jsArg(app.target)})" title="Copy" style="background:none;border:none;cursor:pointer;padding:2px;color:var(--muted);flex-shrink:0;line-height:1;border-radius:3px" onmouseover="this.style.color='var(--green)'" onmouseout="this.style.color='var(--muted)'"><svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 256 256" fill="currentColor"><path d="M216,32H88a8,8,0,0,0-8,8V80H40a8,8,0,0,0-8,8V216a8,8,0,0,0,8,8H168a8,8,0,0,0,8-8V176h40a8,8,0,0,0,8-8V40A8,8,0,0,0,216,32Zm-56,176H48V96H160Zm48-48H176V88a8,8,0,0,0-8-8H96V48H208Z"/></svg></button></div></div>`;
        const cfArg = `,${_jsArg(app.configFile || '')}`;
        const cfBadge = (epBadges || mwBadges || epMwBadges || app.configFile) ? `<div class="flex flex-wrap items-center gap-1 mt-2">${epBadges}${mwBadges}${epMwBadges}${app.configFile ? `<span class="badge badge-muted" style="font-size:9px;margin-left:auto">${_esc(app.configFile)}</span>` : ''}</div>` : '';
        const dataAttrs = `data-protocol="${proto}" data-name="${_esc(app.name.toLowerCase())}" data-routekey="${_esc(app.name)}" data-idx="${i}" data-rid="${_esc(app.id)}" data-enabled="${enabled}" data-domains="${allDomains.map(d => _esc(d)).join('|')}" data-target="${_esc(app.target)}" data-configfile="${_esc(app.configFile||'')}" data-eps="${(app.entryPoints||[]).map(e => _esc(e)).join('|')}" data-servers="${(app.servers || []).map(sv => _esc(sv)).join('|')}" data-tls="${app.tls ? '1' : ''}"`;
        const isBulkSelected = _bulkMode && _bulkSelected.has(app.id);
        const bulkOutline = isBulkSelected ? 'outline:2px solid var(--blue);outline-offset:-2px;' : '';
        const bulkCheckbox = _bulkMode ? `<input type="checkbox" class="bulk-check" onclick="event.stopPropagation()" ${isBulkSelected ? 'checked' : ''} onchange="toggleBulkSelect(${_jsArg(app.id)})" style="width:15px;height:15px;accent-color:var(--blue);cursor:pointer;flex-shrink:0;border-radius:3px;margin-right:2px">` : '';
        const listDomainDisplay = allDomains.length > 1
            ? `<div style="display:flex;flex-direction:column;gap:1px">${allDomains.map(d => `<div style="display:flex;align-items:center;gap:4px"><span class="text-xs font-mono truncate" style="color:var(--blue)">${_esc(d)}</span>${_copyBtn(d,'blue')}</div>`).join('')}</div>`
            : isComplexRule
                ? `<div style="display:flex;align-items:center;gap:4px"><span class="text-xs font-mono" style="color:var(--blue);word-break:break-all" title="${_esc(app.rule)}">${_esc(app.rule)}</span>${_copyBtn(app.rule,'blue')}</div>`
                : `<div style="display:flex;align-items:center;gap:4px"><span class="text-xs font-mono truncate" style="color:var(--blue)">${_esc(domain || app.rule)}</span>${_copyBtn(domain || app.rule,'blue')}</div>`;
        if (_routeViewMode === 'list') {
            const epCompact = _dList((app.entryPoints || []).slice(0, 2));
            const mwCompact = _dList((app.middlewares || []).map(mw => mw.split('@')[0]), 'd-mw');
            const listGlyphs = (proto === 'udp' ? '' : (app.tls
                ? `<i class="ph-bold ph-lock-simple d-glyph" style="color:var(--muted)" title="TLS${app.tlsOptionsProfile ? ' ' + _esc(app.tlsOptionsProfile) : ''}"></i>`
                : '<i class="ph-bold ph-lock-simple-open d-glyph" style="color:var(--yellow)" title="No TLS"></i>'))
                + (app.insecureSkipVerify ? '<i class="ph-bold ph-shield-warning d-glyph" style="color:var(--orange)" title="insecureSkipVerify - backend certificate not verified"></i>' : '');
            return `<div class="svc-list-row route-list-grid route-card${enabled ? '' : ' opacity-50'}" style="${bulkOutline}" ${dataAttrs}><div class="svc-list-col-status" style="display:flex;align-items:center;gap:6px">${bulkCheckbox}<span class="svc-status-dot" style="background:${enabled ? 'var(--green)' : 'var(--muted)'}"></span><span class="d-flat ${enabled ? 'd-on' : 'd-off'} rl-state">${enabled ? 'Active' : 'Paused'}</span></div><div style="display:flex;align-items:center;gap:5px"><span class="d-flat d-proto d-proto-${proto}">${proto.toUpperCase()}</span>${listGlyphs}</div><div class="svc-list-col-name"><div style="display:flex;align-items:center;gap:5px">${iconHtml}<span class="truncate">${_esc(app.name)}</span></div></div><div class="rl-svc"><span class="d-flat d-off truncate" title="${_esc(app.service_name)}">${_esc(app.service_name)}</span></div><div style="display:flex;flex-wrap:wrap;gap:2px;align-items:center">${listDomainDisplay}</div><div style="display:flex;align-items:center;gap:4px"><div class="text-xs font-mono truncate" style="color:var(--green)">${_esc(app.target)}</div>${(app.servers||[]).length>1?`<span class="d-flat d-off" title="${(app.servers||[]).length} backends">+${(app.servers||[]).length-1}</span>`:''}<button onclick="event.stopPropagation();_copyToClipboard(${_jsArg(app.target)})" title="Copy" style="background:none;border:none;cursor:pointer;padding:2px;color:var(--muted);flex-shrink:0;line-height:1;border-radius:3px" onmouseover="this.style.color='var(--green)'" onmouseout="this.style.color='var(--muted)'"><svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 256 256" fill="currentColor"><path d="M216,32H88a8,8,0,0,0-8,8V80H40a8,8,0,0,0-8,8V216a8,8,0,0,0,8,8H168a8,8,0,0,0,8-8V176h40a8,8,0,0,0,8-8V40A8,8,0,0,0,216,32Zm-56,176H48V96H160Zm48-48H176V88a8,8,0,0,0-8-8H96V48H208Z"/></svg></button></div><div style="display:flex;flex-wrap:wrap;align-items:center;gap:3px">${epCompact}</div><div style="display:flex;flex-wrap:wrap;align-items:center;gap:3px">${mwCompact}</div><div class="flex items-center gap-1 flex-shrink-0" onclick="event.stopPropagation()"><button type="button" data-app='${appJson}' data-openurl="${_esc(openUrl)}" onclick="event.stopPropagation();_openRouteMenu(event,this)" class="pill-btn pill-btn-blue" title="More"><i class="ph-bold ph-dots-three text-sm"></i></button><button type="button" data-app='${appJson}' onclick="handleEdit(this)" class="pill-btn pill-btn-blue" title="Edit"><i class="ph-bold ph-pencil-simple text-sm"></i></button>${toggleBtn}</div></div>`;
        }
        return `<div class="card route-card${enabled ? '' : ' opacity-50'}" style="${bulkOutline}" ${dataAttrs}><div class="route-card-inner p-4 pb-2"><div class="flex justify-between items-start mb-3"><div class="flex-1 min-w-0"><div class="flex items-center gap-2 mb-0.5">${bulkCheckbox}<span class="badge ${badgeClass}">${proto.toUpperCase()}</span>${tlsBadge}${insecureBadge}${tlsProfileBadge}<span class="status-dot status-checking" title="Checking..."></span></div><div class="flex items-center gap-1.5 mt-1.5">${iconHtml}<h3 class="font-bold text-sm truncate transition-colors" style="color:var(--text)">${_esc(app.name)}</h3></div><div class="text-xs font-mono truncate" style="color:var(--muted)">${_esc(app.service_name)}</div></div><div class="flex items-center gap-1.5 ml-2 flex-shrink-0" onclick="event.stopPropagation()"><button type="button" data-app='${appJson}' data-openurl="${_esc(openUrl)}" onclick="event.stopPropagation();_openRouteMenu(event,this)" class="pill-btn pill-btn-blue" title="More"><i class="ph-bold ph-dots-three text-sm"></i></button><button type="button" data-app='${appJson}' onclick="handleEdit(this)" class="pill-btn pill-btn-blue" title="Edit"><i class="ph-bold ph-pencil-simple text-sm"></i></button>${toggleBtn}</div></div><div class="space-y-2">${proto === 'http' ? httpBody : tcpBody}</div>${cfBadge}</div></div>`;
    }).join('');

    if (_routeViewMode === 'list') {
        const header = `<div class="svc-list-header route-list-grid"><div>Status</div><div>Protocol</div><div>Name</div><div>Service</div><div>Domain / Rule</div><div>Target</div><div>Entry Points</div><div>Middlewares</div><div class="rl-actions-head">Actions</div></div>`;
        grid.className = '';
        grid.innerHTML = `<div class="svc-list">${header}${grid.innerHTML}</div>`;
    } else if (_tmOn) {
        grid.className = 'tm-card-grid';
    } else {
        grid.className = 'grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4';
    }
    _routeCardEls = Array.from(grid.querySelectorAll('.route-card'));
    if (typeof _sdApplyRouteCards === 'function') _sdApplyRouteCards();
    if (document.getElementById('searchRoutes')) filterRoutes();
}


function _ensureResolverOption(sel, value) {
    if (!sel || !value) return;
    if (![...sel.options].some(o => o.value === value)) {
        const opt = document.createElement('option');
        opt.value = value;
        opt.textContent = value;
        const noneOpt = [...sel.options].find(o => o.value === '__none__');
        sel.insertBefore(opt, noneOpt || null);
    }
    sel.value = value;
}

let _cachedEntrypoints = null;
let _cachedCertResolvers = null;
let _inflightEntrypoints = null;
let _inflightCertResolvers = null;
let _inflightMiddlewares = null;

async function _fetchEntrypointsCached() {
    if (_cachedEntrypoints) return _cachedEntrypoints;
    if (!_inflightEntrypoints) {
        _inflightEntrypoints = (async () => {
            const res = await agentFetch('/api/traefik/entrypoints');
            if (!res.ok) throw new Error('entrypoints ' + res.status);
            const data = await res.json();
            _cachedEntrypoints = Array.isArray(data) ? data : [];
            return _cachedEntrypoints;
        })();
        _inflightEntrypoints.catch(() => {}).then(() => { _inflightEntrypoints = null; });
    }
    return _inflightEntrypoints;
}

async function _fetchMiddlewaresCached() {
    if (_cachedMiddlewares) return _cachedMiddlewares;
    if (!_inflightMiddlewares) {
        _inflightMiddlewares = (async () => {
            const res = await agentFetch('/api/traefik/middlewares');
            if (!res.ok) throw new Error('middlewares ' + res.status);
            const data = await res.json();
            const clean = arr => (arr || []).map(m => m.name || m).filter(m => m && (!m.includes('@') || m.endsWith('@file')));
            _cachedMiddlewares = { http: clean(data.http), tcp: clean(data.tcp) };
            return _cachedMiddlewares;
        })();
        _inflightMiddlewares.catch(() => {}).then(() => { _inflightMiddlewares = null; });
    }
    return _inflightMiddlewares;
}

function _fillResolverSelects(list) {
    ['certResolver', 'certResolverTcp'].forEach(id => {
        const sel = document.getElementById(id);
        if (!sel) return;
        const cur = sel.value;
        sel.innerHTML = '';
        sel.add(new Option('No TLS', '__disabled__'));
        (list || []).forEach(r => sel.add(new Option(r, r)));
        sel.add(new Option('None (external / custom cert)', '__none__'));
        if (cur) _ensureResolverOption(sel, cur);
        else sel.value = '__disabled__';
    });
    const crHttp = document.getElementById('certResolver');
    if (crHttp) toggleWildcardSection(crHttp.value);
}

async function _loadAgentResolversIntoSelects() {
    if (!_activeAgent) { _fillResolverSelects(availableCertResolvers); return; }
    if (_cachedCertResolvers === null && !_inflightCertResolvers) {
        _inflightCertResolvers = (async () => {
            const res = await fetch('/api/agents/' + _activeAgent.id + '/cert-resolvers');
            if (!res.ok) throw new Error('cert-resolvers ' + res.status);
            _cachedCertResolvers = (await res.json()).resolvers || [];
            return _cachedCertResolvers;
        })();
        _inflightCertResolvers.catch(() => {}).then(() => { _inflightCertResolvers = null; });
    }
    let list = _cachedCertResolvers;
    if (list === null) {
        try { list = await _inflightCertResolvers; } catch (e) { list = []; }
    }
    _fillResolverSelects(list);
}

function _copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        const el = document.getElementById('_copyToast');
        if (!el) return;
        el.textContent = 'Copied!';
        el.style.opacity = '1';
        clearTimeout(el._t);
        el._t = setTimeout(() => { el.style.opacity = '0'; }, 1500);
    }).catch(() => {});
}

let _customDomains = [];

function _derivedDomains() {
    const apps = window._lastRenderedApps || (typeof APP_DATA !== 'undefined' ? APP_DATA : []) || [];
    const out = new Set();
    apps.forEach(a => {
        [...(a.rule || '').matchAll(/Host(?:SNI)?\(`([^`]+)`\)/g)].forEach(m => {
            const h = m[1].toLowerCase().trim();
            if (!h || h.includes('*') || h.includes('{')) return;
            const parts = h.split('.').filter(Boolean);
            if (parts.length >= 3) out.add(parts.slice(1).join('.'));
            else if (parts.length === 2) out.add(h);
        });
    });
    return [...out];
}

function _domainsForForm() {
    const base = _activeAgent ? (_activeAgent.domains || []) : availableDomains;
    const merged = [...base];
    [..._derivedDomains(), ..._customDomains].forEach(d => { if (!merged.includes(d)) merged.push(d); });
    return merged;
}

function _initDomainChips(selectedDomains) {
    const container = document.getElementById('domainChips');
    const hiddenContainer = document.getElementById('domainHiddenInputs');
    if (!container || !hiddenContainer) return;
    const conf = _activeAgent ? (_activeAgent.domains || []) : availableDomains;
    const initialList = _domainsForForm();
    let selected = new Set(selectedDomains && selectedDomains.length ? selectedDomains : (conf.length === 1 ? [conf[0]] : (initialList.length === 1 ? [initialList[0]] : [])));
    function render() {
        const list = _domainsForForm();
        hiddenContainer.innerHTML = [...selected].map(d => `<input type="hidden" name="domains" value="${_esc(d)}">`).join('');
        container.innerHTML = list.map(d => {
            const on = selected.has(d);
            return `<button type="button" onclick="_toggleDomainChip(this,${_jsArg(d)})" class="dom-chip${on ? ' on' : ''}" title="${_esc(d)}">${_esc(d)}</button>`;
        }).join('') + `<button type="button" onclick="_customDomainPrompt(this)" class="dom-chip-add" title="Add another domain"><i class="ph-bold ph-plus" style="font-size:10px"></i></button>`;
    }
    render();
    window._domainChipSelected = selected;
    window._domainChipRender = render;
}

function _toggleDomainChip(btn, domain) {
    const selected = window._domainChipSelected;
    if (!selected) return;
    if (selected.has(domain)) { if (selected.size > 1) selected.delete(domain); }
    else selected.add(domain);
    window._domainChipRender();
}

function _customDomainPrompt(btn) {
    const input = document.createElement('input');
    input.type = 'text';
    input.placeholder = 'other.com';
    input.className = 'dom-chip-input';
    btn.replaceWith(input);
    input.focus();
    const commit = () => {
        const v = input.value.trim().toLowerCase();
        if (v && /^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$/.test(v)) {
            if (!_customDomains.includes(v)) _customDomains.push(v);
            if (window._domainChipSelected) window._domainChipSelected.add(v);
        }
        if (window._domainChipRender) window._domainChipRender();
    };
    input.addEventListener('keydown', e => {
        if (e.key === 'Enter') { e.preventDefault(); commit(); }
        else if (e.key === 'Escape' && input.value) { e.stopPropagation(); input.value = ''; if (window._domainChipRender) window._domainChipRender(); }
    });
    input.addEventListener('blur', () => { if (input.isConnected) commit(); });
}

function _initAgentDomainChips(domains, selectedDomains) {
    _initDomainChips(selectedDomains);
}

async function _initEntrypointChips(proto, selectedEntrypoints) {
    const containerId = proto === 'http' ? 'httpEntrypointChips' : proto === 'tcp' ? 'tcpEntrypointChips' : 'udpEntrypointChips';
    const hiddenId    = proto === 'http' ? 'entryPoints' : proto === 'tcp' ? 'entryPointsTcp' : 'entryPointsUdp';
    const container   = document.getElementById(containerId);
    const hidden      = document.getElementById(hiddenId);
    if (!container || !hidden) return;

    let epList = [];
    try { epList = await _fetchEntrypointsCached(); } catch(e) {}
    const eps = (epList || []).map(e => e.name || e).filter(Boolean);
    const isSingle = proto === 'udp';
    if (!eps.length) {
        container.innerHTML = `<input type="text" id="${hiddenId}_fallback" class="input-field" placeholder="${proto === 'http' ? 'https' : proto}" style="flex:1" oninput="document.getElementById('${hiddenId}').value=this.value">`;
        hidden.value = selectedEntrypoints ? (isSingle ? (selectedEntrypoints[0] || '') : selectedEntrypoints.join(', ')) : (proto === 'http' ? 'https' : '');
        return;
    }

    const defaults = proto === 'http' ? ['websecure','https'] : [];
    let selected = new Set(selectedEntrypoints && selectedEntrypoints.length ? selectedEntrypoints : eps.filter(e => defaults.includes(e)));
    if (proto === 'http' && selected.size === 0 && eps.length > 0) selected.add(eps.find(e => defaults.includes(e)) || eps[0]);

    function render() {
        hidden.value = isSingle ? ([...selected][0] || '') : [...selected].join(', ');
        const orphans = [...selected].filter(ep => !eps.includes(ep));
        const allEps = [...eps, ...orphans];
        container.innerHTML = allEps.map(ep => {
            const on = selected.has(ep);
            const isOrphan = !eps.includes(ep);
            const borderColor = on ? (isOrphan ? 'var(--yellow,#eab308)' : 'var(--green)') : 'var(--border)';
            const bgColor = on ? (isOrphan ? 'rgba(234,179,8,0.12)' : 'rgba(34,197,94,0.12)') : 'transparent';
            const textColor = on ? (isOrphan ? 'var(--yellow,#eab308)' : 'var(--green)') : 'var(--muted)';
            const titleAttr = isOrphan ? `${_esc(ep)} (not found in Traefik entrypoints - click to remove)` : _esc(ep);
            return `<button type="button" onclick="_toggleEpChip(this,${_jsArg(ep)},'${proto}')" style="padding:3px 10px;border-radius:6px;border:1px solid ${borderColor};background:${bgColor};color:${textColor};font-size:12px;font-family:monospace;cursor:pointer" title="${titleAttr}">${_esc(ep)}</button>`;
        }).join('');
    }
    render();
    if (!window._epChipState) window._epChipState = {};
    window._epChipState[proto] = { selected, render, hiddenId, isSingle };
}

function _toggleEpChip(btn, ep, proto) {
    const state = window._epChipState?.[proto];
    if (!state) return;
    if (state.isSingle) {
        state.selected.clear();
        state.selected.add(ep);
    } else {
        if (state.selected.has(ep)) state.selected.delete(ep);
        else state.selected.add(ep);
    }
    state.render();
}

let _cachedMiddlewares = null;

async function _initMiddlewareChips(selectedMiddlewares, proto) {
    proto = proto === 'tcp' ? 'tcp' : 'http';
    const containerId = proto === 'tcp' ? 'tcpMiddlewareChips' : 'middlewareChips';
    const hiddenId    = proto === 'tcp' ? 'middlewaresTcp' : 'middlewares';
    const container = document.getElementById(containerId);
    const hidden    = document.getElementById(hiddenId);
    if (!container || !hidden) return;

    let mwData = null;
    try { mwData = await _fetchMiddlewaresCached(); } catch(e) {}
    const liveMws = (mwData || {})[proto] || [];
    const configMws = (typeof _allMiddlewares !== 'undefined' ? _allMiddlewares : [])
        .filter(m => (m.type || 'http').toLowerCase() === proto && m.name)
        .map(m => m.name);
    const byBase = new Map();
    [...liveMws, ...configMws].forEach(full => {
        const base = full.split('@')[0];
        if (!byBase.has(base)) byBase.set(base, full);
    });
    const mws = [...byBase.values()];
    if (!mws.length) {
        container.innerHTML = `<input type="text" class="input-field" style="flex:1" placeholder="${proto === 'tcp' ? 'tcp-lan-only@file' : 'auth@file, redirect-https'}" oninput="document.getElementById('${hiddenId}').value=this.value">`;
        hidden.value = selectedMiddlewares ? selectedMiddlewares.join(', ') : '';
        return;
    }

    const routeBases = new Set((selectedMiddlewares || []).map(m => m.trim().split('@')[0]).filter(Boolean));
    const baseToFull = Object.fromEntries(mws.map(mw => [mw.split('@')[0], mw]));
    let selected = new Set([...routeBases].map(b => baseToFull[b]).filter(Boolean));

    const filterId = containerId + 'Filter';
    function render() {
        hidden.value = [...selected].join(', ');
        const q = (document.getElementById(filterId)?.value || '').trim().toLowerCase();
        const sel   = [...selected];
        const all   = mws.filter(mw => !selected.has(mw));
        const unsel = q ? all.filter(mw => mw.toLowerCase().includes(q)) : all;
        const hiddenCount = all.length - unsel.length;
        const chip = (mw, i, on) => {
            const label = mw.split('@')[0];
            return `<button type="button" onclick="_toggleMwChip(${_jsArg(mw)},'${proto}')" class="mw-chip${on ? ' on' : ''}" title="${_esc(mw)}">${on ? (i + 1) + '. ' : ''}${_esc(label)}</button>`;
        };
        const divider = sel.length > 0 && unsel.length > 0
            ? `<span style="align-self:center;width:1px;height:18px;background:var(--border);margin:0 2px;flex-shrink:0"></span>`
            : '';
        const note = hiddenCount
            ? `<span class="d-n" style="align-self:center">${hiddenCount} hidden</span>`
            : (q && !unsel.length && !sel.length ? '<span class="d-n" style="align-self:center">no matches</span>' : '');
        container.innerHTML = sel.map((mw, i) => chip(mw, i, true)).join('')
            + divider
            + unsel.map(mw => chip(mw, 0, false)).join('')
            + note;
        if (proto !== 'tcp') _streamingBufWarn();
    }

    function paintFilter() {
        const wrap = document.getElementById(filterId + 'Wrap');
        if (!wrap) return;
        wrap.style.display = mws.length >= 12 ? '' : 'none';
    }
    window['_mwChipFilter_' + proto] = render;
    const fwrap = document.getElementById(containerId + 'FilterWrap');
    if (fwrap) {
        fwrap.style.display = mws.length >= 12 ? '' : 'none';
        const fin = document.getElementById(containerId + 'Filter');
        if (fin) fin.value = '';
    }
    render();
    if (!window._mwChipState || typeof window._mwChipState.render === 'function') window._mwChipState = {};
    window._mwChipState[proto] = { selected, render };
}

function _toggleMwChip(mw, proto) {
    const state = window._mwChipState && window._mwChipState[proto === 'tcp' ? 'tcp' : 'http'];
    if (!state) return;
    if (state.selected.has(mw)) state.selected.delete(mw);
    else state.selected.add(mw);
    state.render();
}


function setTcpTlsMode(mode, btn) {
    document.querySelectorAll('#tcpTlsNone,#tcpTlsTls,#tcpTlsPassthrough').forEach(b => b.classList.remove('active-http'));
    if (btn) btn.classList.add('active-http');
    const row = document.getElementById('tcpCertResolverRow');
    const useTlsInput = document.getElementById('useTls');
    const passthroughInput = document.getElementById('tlsPassthrough');
    if (row) row.style.display = mode === 'tls' ? '' : 'none';
    if (useTlsInput) useTlsInput.value = mode === 'tls' ? 'true' : '';
    if (passthroughInput) passthroughInput.value = mode === 'passthrough' ? 'true' : '';
}

function toggleTcpCertResolver(checked) {
    setTcpTlsMode(checked ? 'tls' : 'none', document.getElementById(checked ? 'tcpTlsTls' : 'tcpTlsNone'));
}

function toggleLbAdvanced(proto) {
    const body = document.getElementById(proto + 'LbAdvBody');
    const chev = document.getElementById(proto + 'LbAdvChevron');
    if (!body) return;
    const open = body.style.display !== 'none';
    body.style.display = open ? 'none' : '';
    if (chev) chev.className = 'ph-bold ph-caret-' + (open ? 'right' : 'down') + ' text-xs';
}

function _lbSyncToggles() {
    const st = document.getElementById('lbStickyEnabled');
    const sb = document.getElementById('lbStickyBody');
    if (st && sb) sb.style.display = st.checked ? '' : 'none';
    const hc = document.getElementById('lbHealthEnabled');
    const hb = document.getElementById('lbHealthBody');
    if (hc && hb) hb.style.display = hc.checked ? '' : 'none';
}

function removeBackendRow(btn) {
    const row = btn.closest('.tm-backend-row');
    if (row) row.remove();
}

function _bkRows() {
    const zero = document.getElementById('httpTargetGrid');
    const rest = Array.from(document.querySelectorAll('#httpBackendRows .tm-backend-row'));
    return zero ? [zero, ...rest] : rest;
}

function _bkKindOf(row) {
    return row.querySelector('.bk-kind')?.value === 'service' ? 'service' : 'manual';
}

function _bkAnyServiceRow() {
    return _bkRows().some(r => _bkKindOf(r) === 'service' && (r.querySelector('.bk-svc')?.value || ''));
}

function _bkKindChanged(select) {
    if (!select) return;
    const row = select.closest('.tm-backend-row');
    if (!row) return;
    const isSvc = select.value === 'service';
    if (isSvc) {
        const picker = row.querySelector('.bk-svc');
        if (picker && !picker.options.length) {
            _bkFillServiceSelect(row).then(() => _bkSyncWeights());
        }
    }
    const show = (sel, on) => {
        const el = row.querySelector(sel);
        if (el) { el.style.display = on ? '' : 'none'; el.style.gridColumn = ''; }
    };
    show('.bk-scheme', !isSvc);
    show('.bk-host', !isSvc);
    show('.bk-port', !isSvc);
    show('.bk-svc', isSvc);
    const removable = !!row.querySelector('.btn-secondary[title="Remove backend"]');
    row.style.gridTemplateColumns = (isSvc ? '104px 1fr 74px' : '104px 96px 1fr 1fr 74px')
        + (removable ? ' 32px' : '');
    _bkSyncWeights();
}

function _bkSyncWeights() {
    const rows = _bkRows();
    const on = _bkAnyServiceRow() && rows.length > 1;
    rows.forEach(r => {
        const w = r.querySelector('.bk-weight');
        if (w) w.style.display = on ? '' : 'none';
    });
    const cRow = document.getElementById('httpCompositeRow');
    if (cRow) cRow.style.display = on ? '' : 'none';
    _bkCompositeChanged();
}

function _bkCompositeChanged() {
    const kind = document.getElementById('httpCompositeType')?.value || 'weighted';
    const hint = document.getElementById('httpCompositeHint');
    if (hint) {
        hint.textContent = kind === 'weighted' ? 'Traffic is split by weight.'
            : kind === 'mirroring' ? 'The first backend serves; the rest receive a copy by percentage.'
            : 'The first backend serves; the second takes over if it fails.';
    }
    _bkRows().forEach(r => {
        const w = r.querySelector('.bk-weight');
        if (w) w.title = kind === 'mirroring' ? 'Percent' : 'Weight';
    });
}

async function _bkFillServiceSelect(row, selected) {
    const sel = row.querySelector('.bk-svc');
    if (!sel) return;
    const svcs = (await _ensureServicesList()).http || [];
    sel.innerHTML = svcs.length
        ? svcs.map(n => `<option value="${_esc(n)}">${_esc(n)}</option>`).join('')
        : '<option value="">No other services to reference yet</option>';
    if (selected && !svcs.includes(selected)) {
        sel.insertAdjacentHTML('afterbegin', `<option value="${_esc(selected)}">${_esc(selected)}</option>`);
    }
    if (selected) sel.value = selected;
}

function _collectBackendChildren() {
    const kind = document.getElementById('httpCompositeType')?.value || 'weighted';
    const out = [];
    _bkRows().forEach(r => {
        const weight = parseInt(r.querySelector('.bk-weight')?.value, 10);
        const share = isNaN(weight) ? (kind === 'mirroring' ? 0 : 1) : weight;
        if (_bkKindOf(r) === 'service') {
            const name = (r.querySelector('.bk-svc')?.value || '').trim();
            if (name) out.push({ kind: 'service', name, weight: share, percent: share });
            return;
        }
        const host = (r.querySelector('.bk-host')?.value || '').trim();
        if (!host) return;
        const port = (r.querySelector('.bk-port')?.value || '').trim();
        const scheme = r === document.getElementById('httpTargetGrid')
            ? (document.getElementById('scheme')?.value || 'http')
            : (r.querySelector('.bk-scheme')?.value || 'http');
        out.push({ kind: 'manual', address: port ? host + ':' + port : host,
                   scheme, weight: share, percent: share });
    });
    return out;
}

function addBackendRow(proto, data) {
    const wrap = document.getElementById(proto + 'BackendRows');
    if (!wrap) return;
    const kind = document.getElementById('httpCompositeType')?.value || 'weighted';
    if (proto === 'http' && kind === 'failover' && !data
            && wrap.querySelectorAll('.tm-backend-row').length >= 2) {
        showToast('Failover takes two backends: the one that serves and the one that takes over',
                  'error');
        return;
    }
    const d = data || {};
    const row = document.createElement('div');
    row.className = 'tm-backend-row grid gap-3 mt-2';
    row.style.gridTemplateColumns = proto === 'http' ? '110px 1fr 1fr 32px' : '1fr 1fr 32px';
    const schemeCell = proto === 'http'
        ? `<select class="input-field bk-scheme"><option value="http">HTTP</option><option value="https">HTTPS</option></select>`
        : '';
    const kindCell = proto === 'http'
        ? `<select class="input-field bk-kind text-sm" onchange="_bkKindChanged(this)"><option value="manual">IP : Port</option><option value="service">Service</option></select>`
        : '';
    row.innerHTML = kindCell + schemeCell +
        `<input type="text" class="input-field bk-host" placeholder="10.0.0.11">` +
        `<input type="text" class="input-field bk-port" placeholder="8080">` +
        (proto === 'http' ? `<select class="input-field bk-svc text-sm" style="display:none"></select>` : '') +
        (proto === 'http' ? `<input type="number" class="input-field bk-weight text-sm" value="1" min="0" title="Weight" style="display:none">` : '') +
        `<button type="button" onclick="removeBackendRow(this)" class="btn-secondary" title="Remove backend" style="padding:0;width:32px;display:flex;align-items:center;justify-content:center"><i class="ph-bold ph-trash text-xs" style="color:var(--red)"></i></button>`;
    if (proto === 'http') row.style.gridTemplateColumns = '104px 96px 1fr 1fr 74px 32px';
    wrap.appendChild(row);
    if (proto === 'http' && d.scheme) row.querySelector('.bk-scheme').value = d.scheme;
    if (d.host) row.querySelector('.bk-host').value = d.host;
    if (d.port) row.querySelector('.bk-port').value = d.port;
    if (proto === 'http') {
        if (d.kind === 'service') {
            const sel = row.querySelector('.bk-kind');
            if (sel) sel.value = 'service';
        }
        if (d.weight != null) {
            const w = row.querySelector('.bk-weight');
            if (w) w.value = d.weight;
        }
        _bkFillServiceSelect(row, d.name);
        _bkKindChanged(row.querySelector('.bk-kind'));
    }
}

function _clearBackendRows(proto) {
    const wrap = document.getElementById(proto + 'BackendRows');
    if (wrap) wrap.innerHTML = '';
}

function _splitServer(value, proto) {
    let v = String(value || '').trim();
    if (!v) return null;
    if (proto === 'http') {
        const scheme = v.startsWith('https://') ? 'https' : 'http';
        v = v.replace(/^https?:\/\//, '');
        const i = v.lastIndexOf(':');
        return (i > -1 && !v.slice(i + 1).includes('/'))
            ? { scheme, host: v.slice(0, i), port: v.slice(i + 1) }
            : { scheme, host: v, port: '' };
    }
    const i = v.lastIndexOf(':');
    return i > -1 ? { host: v.slice(0, i), port: v.slice(i + 1) } : { host: v, port: '' };
}

function _populateBackends(proto, servers) {
    _clearBackendRows(proto);
    const list = (servers || []).map(s => _splitServer(s, proto)).filter(Boolean);
    const ids = proto === 'http' ? ['targetIp', 'targetPort'] :
                proto === 'tcp'  ? ['targetIpTcp', 'targetPortTcp'] : ['targetIpUdp', 'targetPortUdp'];
    if (list.length) {
        const first = list[0];
        const hostEl = document.getElementById(ids[0]);
        const portEl = document.getElementById(ids[1]);
        if (hostEl) hostEl.value = first.host || '';
        if (portEl) portEl.value = first.port || '';
        if (proto === 'http') {
            const sc = document.getElementById('scheme');
            if (sc && first.scheme) sc.value = first.scheme;
        }
        list.slice(1).forEach(s => addBackendRow(proto, s));
    }
}

function _loadCompositeRows(app) {
    _routeWasComposite = false;
    const rows = (app && app.compositeChildren) || [];
    const kindSel = document.getElementById('httpCompositeType');
    if (kindSel) {
        kindSel.value = ['weighted', 'mirroring', 'failover'].includes(app.serviceType)
            ? app.serviceType : 'weighted';
    }
    if (!rows.length) return false;
    _routeWasComposite = true;
    _clearBackendRows('http');
    const owned = new Set(app.ownedChildren || []);
    const asRow = (c) => {
        const isOwned = owned.has(c.name) || !!c.url;
        const share = kindSel && kindSel.value === 'mirroring' ? c.percent : c.weight;
        if (!isOwned) return { kind: 'service', name: c.name, weight: share };
        const parts = _splitServer(c.url, 'http') || {};
        return { kind: 'manual', host: parts.host || '', port: parts.port || '',
                 scheme: parts.scheme || 'http', weight: share };
    };
    const first = asRow(rows[0]);
    const zeroKind = document.querySelector('#httpTargetGrid .bk-kind');
    if (zeroKind) zeroKind.value = first.kind;
    const setVal = (id, v) => { const el = document.getElementById(id); if (el) el.value = v || ''; };
    setVal('targetIp', first.host);
    setVal('targetPort', first.port);
    if (first.scheme) setVal('scheme', first.scheme);
    const zeroWeight = document.querySelector('#httpTargetGrid .bk-weight');
    if (zeroWeight) zeroWeight.value = first.weight == null ? 1 : first.weight;
    if (first.kind === 'service') {
        const zeroGrid = document.getElementById('httpTargetGrid');
        if (zeroGrid) _bkFillServiceSelect(zeroGrid, first.name);
    }
    if (zeroKind) _bkKindChanged(zeroKind);
    rows.slice(1).forEach(c => addBackendRow('http', asRow(c)));
    _bkSyncWeights();
    return true;
}

function _serializeBackends(proto) {
    const ids = proto === 'http' ? ['targetIp', 'targetPort'] :
                proto === 'tcp'  ? ['targetIpTcp', 'targetPortTcp'] : ['targetIpUdp', 'targetPortUdp'];
    const servers = [];
    const host0 = (document.getElementById(ids[0])?.value || '').trim();
    if (host0) {
        const row = { host: host0, port: (document.getElementById(ids[1])?.value || '').trim() };
        if (proto === 'http') row.scheme = document.getElementById('scheme')?.value || 'http';
        servers.push(row);
    }
    document.querySelectorAll('#' + proto + 'BackendRows .tm-backend-row').forEach(r => {
        const host = (r.querySelector('.bk-host')?.value || '').trim();
        if (!host) return;
        const row = { host, port: (r.querySelector('.bk-port')?.value || '').trim() };
        if (proto === 'http') row.scheme = r.querySelector('.bk-scheme')?.value || 'http';
        servers.push(row);
    });
    const children = proto === 'http' ? _collectBackendChildren() : [];
    if (!servers.length && !children.length) return null;
    const payload = { servers };
    if (proto === 'http' && (_bkAnyServiceRow() || _routeWasComposite)) {
        payload.children = children;
        payload.compositeType = document.getElementById('httpCompositeType')?.value || 'weighted';
    }
    if (proto === 'http') {
        payload.sticky = {
            enabled: !!document.getElementById('lbStickyEnabled')?.checked,
            cookieName: (document.getElementById('lbStickyCookie')?.value || '').trim(),
            secure: !!document.getElementById('lbStickySecure')?.checked,
            httpOnly: !!document.getElementById('lbStickyHttpOnly')?.checked,
        };
        payload.healthCheck = {
            enabled: !!document.getElementById('lbHealthEnabled')?.checked,
            path: (document.getElementById('lbHealthPath')?.value || '').trim(),
            interval: (document.getElementById('lbHealthInterval')?.value || '').trim(),
            timeout: (document.getElementById('lbHealthTimeout')?.value || '').trim(),
        };
        payload.priority = (document.getElementById('lbPriority')?.value || '').trim();
    } else if (proto === 'tcp') {
        payload.priority = (document.getElementById('lbPriorityTcp')?.value || '').trim();
    }
    return JSON.stringify(payload);
}

function _writeBackendsJson() {
    ['http', 'tcp', 'udp'].forEach(proto => {
        const el = document.getElementById('backendsJson' + proto.charAt(0).toUpperCase() + proto.slice(1));
        if (el) el.value = _serializeBackends(proto) || '';
    });
}

function _resetLbAdvanced() {
    ['http', 'tcp', 'udp'].forEach(_clearBackendRows);
    const set = (id, v) => { const el = document.getElementById(id); if (el) el.value = v; };
    const chk = (id, v) => { const el = document.getElementById(id); if (el) el.checked = v; };
    chk('lbStickyEnabled', false); chk('lbStickySecure', false); chk('lbStickyHttpOnly', false);
    chk('lbHealthEnabled', false);
    set('lbStickyCookie', ''); set('lbHealthPath', ''); set('lbHealthInterval', ''); set('lbHealthTimeout', '');
    set('lbPriority', ''); set('lbPriorityTcp', '');
    set('backendsJsonHttp', ''); set('backendsJsonTcp', ''); set('backendsJsonUdp', '');
    _lbSyncToggles();
    _resetBackendKinds();
    const body = document.getElementById('httpLbAdvBody');
    if (body) body.style.display = 'none';
    const chev = document.getElementById('httpLbAdvChevron');
    if (chev) chev.className = 'ph-bold ph-caret-right text-xs';
}

function _resetBackendKinds() {
    const zeroKind = document.querySelector('#httpTargetGrid .bk-kind');
    if (zeroKind) zeroKind.value = 'manual';
    const zeroWeight = document.querySelector('#httpTargetGrid .bk-weight');
    if (zeroWeight) zeroWeight.value = '1';
    const type = document.getElementById('httpCompositeType');
    if (type) type.value = 'weighted';
    if (zeroKind) _bkKindChanged(zeroKind);
    else _bkSyncWeights();
}

function _applyLbAdvanced(app) {
    const set = (id, v) => { const el = document.getElementById(id); if (el) el.value = v; };
    const chk = (id, v) => { const el = document.getElementById(id); if (el) el.checked = v; };
    const sticky = app.sticky || {};
    const hc     = app.healthCheck || {};
    chk('lbStickyEnabled', !!app.stickyEnabled);
    set('lbStickyCookie', sticky.name || '');
    chk('lbStickySecure', !!sticky.secure);
    chk('lbStickyHttpOnly', !!sticky.httpOnly);
    chk('lbHealthEnabled', !!(hc && hc.path));
    set('lbHealthPath', hc.path || '');
    set('lbHealthInterval', hc.interval || '');
    set('lbHealthTimeout', hc.timeout || '');
    set('lbPriority', app.priority || '');
    set('lbPriorityTcp', app.priority || '');
    _lbSyncToggles();
    if (app.stickyEnabled || (hc && hc.path) || app.priority) {
        const body = document.getElementById('httpLbAdvBody');
        const chev = document.getElementById('httpLbAdvChevron');
        if (body) body.style.display = '';
        if (chev) chev.className = 'ph-bold ph-caret-down text-xs';
    }
}

function toggleWildcardSection(resolverVal) {
    const show = resolverVal && resolverVal !== '__disabled__';
    ['wildcardCheckboxRow', 'wildcardSection'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.display = show ? '' : 'none';
    });
    if (!show) {
        const chk = document.getElementById('wildcardCheckbox');
        if (chk) chk.checked = false;
        _onWildcardToggle(false);
    }
}

function _onWildcardToggle(checked) {
    const mainEl = document.getElementById('tlsWildcardMain');
    const sansEl = document.getElementById('tlsWildcardSans');
    if (!mainEl || !sansEl) return;
    if (!checked) { mainEl.value = ''; sansEl.value = ''; return; }
    const domSel = document.getElementById('domainSelect');
    let base = '';
    if (window._domainChipSelected && window._domainChipSelected.size) {
        base = [...window._domainChipSelected][0];
    } else if (domSel && domSel.value) {
        base = domSel.value;
    }
    if (!base) base = (document.getElementById('singleDomain')?.textContent || '').trim();
    if (base) { mainEl.value = base; sansEl.value = '*.' + base; }
}

function _applyHttpRuleToForm(rule) {
    const isSimpleRule = /^(Host\(`[^`]+`\)(\s*\|\|\s*Host\(`[^`]+`\))*)$/.test(rule.trim());
    if (!isSimpleRule && rule) {
        setHttpRuleMode('advanced');
        document.getElementById('httpRule').value = rule;
    } else {
        setHttpRuleMode('simple');
    }
    _updateRouteModalForAgent();
    const domainsForMatch = _domainsForForm();
    let subdomain = '';
    const hostMatches = [...rule.matchAll(/Host\(`([^`]+)`\)/g)].map(m => m[1]);
    const matchedDomains = [];
    for (let fullHost of hostMatches) {
        let found = false;
        for (let d of domainsForMatch) {
            if (fullHost.endsWith('.' + d)) { if (!subdomain) subdomain = fullHost.slice(0, -(d.length + 1)); matchedDomains.push(d); found = true; break; }
            else if (fullHost === d) { matchedDomains.push(d); found = true; break; }
        }
        if (!found && !subdomain) subdomain = fullHost;
    }
    document.getElementById('subdomain').value = subdomain;
    if (document.getElementById('domainChips')) {
        _initDomainChips(matchedDomains.length ? matchedDomains : []);
    } else {
        const sel = document.getElementById('domainSelect');
        if (sel && matchedDomains.length > 0) sel.value = matchedDomains[0];
    }
}

async function cloneRoute(btn) {
    const app = JSON.parse(btn.getAttribute('data-app'));
    await openModal();
    document.getElementById('modalTitle').innerText = 'Clone Route';
    document.getElementById('serviceName').value = (app.name || '') + '-copy';
    _populateBackends(app.protocol || 'http', app.servers);
    _applyLbAdvanced(app);
    const cfSel = document.getElementById('configFileSelect');
    if (app.configFile) {
        document.getElementById('configFile').value = app.configFile;
        if (cfSel) cfSel.value = app.configFile;
    }
    const proto = app.protocol || 'http';
    setProtocol(proto);
    const _cloneSvcList = (await _ensureServicesList())[proto] || [];
    const _cloneRef = _detectServiceRef(app, proto, _cloneSvcList);
    if (_cloneRef.refMode) {
        await _populateServiceRefSelect(proto, _cloneRef.raw);
        setServiceRefMode(proto, true);
    }
    if (proto === 'http') {
        _applyHttpRuleToForm(app.rule || '');
        const _cloneComposite = !!app.serviceType && app.serviceType !== 'loadBalancer';
        const targetScheme = (app.target || '').startsWith('https://') ? 'https' : 'http';
        let target = _cloneComposite ? '' : (app.target || '').replace('http://','').replace('https://','');
        const parts = target.split(':');
        document.getElementById('targetIp').value = parts[0] || '';
        document.getElementById('targetPort').value = _cloneComposite ? '' : (parts[1] || '80');
        const _ownedHdr = (app.headersPreset && app.headersPreset.owned) ? app.name + '-headers' : null;
        await _initMiddlewareChips((app.middlewares || []).filter(m => m !== _ownedHdr));
        _applyHeadersPreset(app.headersPreset);
        await _initEntrypointChips('http', app.entryPoints || []);
        document.getElementById('scheme').value = targetScheme;
        document.getElementById('passHostHeader').checked = app.passHostHeader !== false;
        _applyStreamingPreset(app.streaming);
        const crHttp = document.getElementById('certResolver');
        if (crHttp) {
            if (!app.tls && app.tls !== false) crHttp.value = '__disabled__';
            else if (app.certResolver) _ensureResolverOption(crHttp, app.certResolver);
            else crHttp.value = '__none__';
            toggleWildcardSection(crHttp.value);
        }
        const insecureChk = document.getElementById('insecureSkipVerify');
        if (insecureChk) insecureChk.checked = !!app.insecureSkipVerify;
        const tlsDomains = app.tlsDomains || [];
        const chk = document.getElementById('wildcardCheckbox');
        if (tlsDomains.length && chk) {
            const first = tlsDomains[0];
            chk.checked = true;
            const mainEl = document.getElementById('tlsWildcardMain');
            const sansEl = document.getElementById('tlsWildcardSans');
            if (mainEl) mainEl.value = first.main || '';
            if (sansEl) sansEl.value = (first.sans || []).join('\n');
        } else if (chk) {
            chk.checked = false;
        }
        const tlsOptSel = document.getElementById('tlsOptionsProfileSelect');
        if (tlsOptSel) {
            await _populateTlsOptionsSelect();
            tlsOptSel.value = app.tlsOptionsProfile || '';
        }
    } else if (proto === 'tcp') {
        document.getElementById('tcpRule').value = app.rule || '';
        const target = (app.target || '').split(':');
        document.getElementById('targetIpTcp').value = target[0] || '';
        document.getElementById('targetPortTcp').value = target[1] || '';
        await _initEntrypointChips('tcp', app.entryPoints || []);
        await _initMiddlewareChips(app.middlewares || [], 'tcp');
        const tlsMode = app.tls ? (app.tls.passthrough ? 'passthrough' : 'tls') : 'none';
        setTcpTlsMode(tlsMode, document.getElementById(tlsMode === 'passthrough' ? 'tcpTlsPassthrough' : tlsMode === 'tls' ? 'tcpTlsTls' : 'tcpTlsNone'));
        const crTcp = document.getElementById('certResolverTcp');
        if (crTcp && app.certResolver) _ensureResolverOption(crTcp, app.certResolver);
    } else if (proto === 'udp') {
        const target = (app.target || '').split(':');
        document.getElementById('targetIpUdp').value = target[0] || '';
        document.getElementById('targetPortUdp').value = target[1] || '';
        await _initEntrypointChips('udp', app.entryPoints || []);
    }
}

let _routeMenuCard = null;

function _openRouteMenu(event, btn) {
    event.stopPropagation();
    _routeMenuCard = btn.closest('.route-card');
    const app      = JSON.parse(btn.getAttribute('data-app'));
    const openUrl  = btn.getAttribute('data-openurl') || '';
    const id       = app.id;
    const cf       = _jsArg(app.configFile || '');
    const appJsonStr = JSON.stringify(app).replace(/'/g,'&#39;');
    const menu = document.getElementById('routeActionsMenu');
    if (!menu) return;

    let items = `<button class="route-ctx-item" onclick="_closeRouteMenu();openRouteDetailFromCard(_routeMenuCard)"><i class="ph-bold ph-info"></i> View Details</button>`;
    if (openUrl) items += `<a class="route-ctx-item" href="${_esc(openUrl)}" target="_blank" rel="noopener" onclick="_closeRouteMenu()"><i class="ph-bold ph-arrow-square-out"></i> Open</a>`;
    items += `<button class="route-ctx-item" data-app='${appJsonStr}' onclick="_closeRouteMenu();cloneRoute(this)"><i class="ph-bold ph-copy"></i> Clone</button>`;
    items += `<button class="route-ctx-item" onclick="_closeRouteMenu();openRouteYamlEditor(${_jsArg(id)})"><i class="ph-bold ph-code"></i> Raw YAML</button>`;
    items += `<div style="height:1px;background:var(--border);margin:3px 6px"></div>`;
    items += `<button class="route-ctx-item route-ctx-danger" onclick="_closeRouteMenu();deleteRoute(${_jsArg(id)},${cf})"><i class="ph-bold ph-trash"></i> Delete</button>`;
    menu.innerHTML = items;
    menu.style.display = 'block';

    const rect = btn.getBoundingClientRect();
    const menuW = 170;
    let left = rect.right - menuW;
    if (left < 8) left = 8;
    let top = rect.bottom + 6;
    if (top + 210 > window.innerHeight) top = rect.top - 210;
    menu.style.left = left + 'px';
    menu.style.top  = top  + 'px';
}

function _closeRouteMenu() {
    const menu = document.getElementById('routeActionsMenu');
    if (menu) menu.style.display = 'none';
}

async function handleEdit(btn) {
    const app = JSON.parse(btn.getAttribute('data-app'));
    document.getElementById('isEdit').value = 'true';
    document.getElementById('originalId').value = app.id;
    document.getElementById('modalTitle').innerText = 'Edit ' + app.name;
    document.getElementById('serviceName').value = app.name;
    document.getElementById('configFile').value = app.configFile || '';
    const newRouteInput = document.getElementById('newRouteFileName');
    if (newRouteInput) { newRouteInput.style.display = 'none'; newRouteInput.value = ''; }

    const proto = app.protocol || 'http';
    setProtocol(proto);
    _applyServiceTypeNotice(app.serviceType, app.serviceOwned);
    _resetLbAdvanced();
    if (!(proto === 'http' && _loadCompositeRows(app))) {
        _populateBackends(proto, app.servers);
    }
    _applyLbAdvanced(app);

    const _svcList = (await _ensureServicesList())[proto] || [];
    const _ref = _detectServiceRef(app, proto, _svcList);
    ['http', 'tcp', 'udp'].forEach(pr => { if (pr !== proto) setServiceRefMode(pr, false); });
    await _populateServiceRefSelect(proto, _ref.refMode ? _ref.raw : '');
    setServiceRefMode(proto, _ref.refMode, { lockManual: _ref.refMode });

    if (proto === 'http') {
        _applyHttpRuleToForm(app.rule || '');

        const targetScheme = (app.target || '').startsWith('https://') ? 'https' : 'http';
        let target = app.target.replace('http://','').replace('https://','');
        const parts = target.split(':');
        document.getElementById('targetIp').value = parts[0];
        document.getElementById('targetPort').value = parts[1] || '80';
        const _ownedHdr = (app.headersPreset && app.headersPreset.owned) ? app.name + '-headers' : null;
        await _initMiddlewareChips((app.middlewares || []).filter(m => m !== _ownedHdr));
        _applyHeadersPreset(app.headersPreset);
        await _initEntrypointChips('http', app.entryPoints || []);
        document.getElementById('scheme').value = targetScheme;
        document.getElementById('passHostHeader').checked = app.passHostHeader !== false;
        _applyStreamingPreset(app.streaming);
        const crHttp = document.getElementById('certResolver');
        if (crHttp) {
            if (!app.tls && app.tls !== false) crHttp.value = '__disabled__';
            else if (app.certResolver) _ensureResolverOption(crHttp, app.certResolver);
            else crHttp.value = '__none__';
            toggleWildcardSection(crHttp.value);
        }
        const insecureChk = document.getElementById('insecureSkipVerify');
        if (insecureChk) insecureChk.checked = !!app.insecureSkipVerify;
        const tlsDomains = app.tlsDomains || [];
        const wChk = document.getElementById('wildcardCheckbox');
        if (tlsDomains.length && wChk) {
            const first = tlsDomains[0];
            wChk.checked = true;
            const mainEl = document.getElementById('tlsWildcardMain');
            const sansEl = document.getElementById('tlsWildcardSans');
            if (mainEl) mainEl.value = first.main || '';
            if (sansEl) sansEl.value = (first.sans || []).join('\n');
        } else if (wChk) {
            wChk.checked = false;
            _onWildcardToggle(false);
        }
        const tlsOptSel2 = document.getElementById('tlsOptionsProfileSelect');
        if (tlsOptSel2) {
            await _populateTlsOptionsSelect();
            tlsOptSel2.value = app.tlsOptionsProfile || '';
        }

    } else if (proto === 'tcp') {
        document.getElementById('tcpRule').value = app.rule || '';
        const target = (app.target || '').split(':');
        document.getElementById('targetIpTcp').value = target[0] || '';
        document.getElementById('targetPortTcp').value = target[1] || '';
        await _initEntrypointChips('tcp', app.entryPoints || []);
        await _initMiddlewareChips(app.middlewares || [], 'tcp');
        const tlsMode2 = app.tls ? (app.tls.passthrough ? 'passthrough' : 'tls') : 'none';
        setTcpTlsMode(tlsMode2, document.getElementById(tlsMode2 === 'passthrough' ? 'tcpTlsPassthrough' : tlsMode2 === 'tls' ? 'tcpTlsTls' : 'tcpTlsNone'));
        const crTcp = document.getElementById('certResolverTcp');
        if (crTcp && app.certResolver) _ensureResolverOption(crTcp, app.certResolver);

    } else if (proto === 'udp') {
        const target = (app.target || '').split(':');
        document.getElementById('targetIpUdp').value = target[0] || '';
        document.getElementById('targetPortUdp').value = target[1] || '';
        await _initEntrypointChips('udp', app.entryPoints || []);
    }

    await _populateConfigFileSelect('route');
    const cfSel = document.getElementById('configFileSelect');
    if (app.configFile) {
        if (cfSel) cfSel.value = app.configFile;
        document.getElementById('configFile').value = app.configFile;
    }
    await _loadAgentResolversIntoSelects();
    _openRoutePanel();
}
let _routeViewMode = tmPref('routeViewMode');
let _bulkMode = false;
let _bulkSelected = new Set();

function toggleBulkMode() {
    _bulkMode = !_bulkMode;
    if (!_bulkMode) _bulkSelected.clear();
    const btn = document.getElementById('bulkModeBtn');
    if (btn) btn.classList.toggle('active-http', _bulkMode);
    updateBulkBar();
    const apps = window._lastRenderedApps || [];
    if (apps.length) { renderRouteGrid(apps); loadOverviewStats(); }
}

function toggleBulkSelect(id) {
    if (_bulkSelected.has(id)) _bulkSelected.delete(id);
    else _bulkSelected.add(id);
    updateBulkBar();
    const card = document.querySelector(`.route-card[data-routekey="${CSS.escape(id)}"]`);
    if (card) {
        const cb = card.querySelector('.bulk-check');
        if (cb) cb.checked = _bulkSelected.has(id);
        card.style.outline = _bulkSelected.has(id) ? '2px solid var(--blue)' : '';
        card.style.outlineOffset = _bulkSelected.has(id) ? '-2px' : '';
        card.classList.toggle('tm-sel', _bulkSelected.has(id));
    }
}

function updateBulkBar() {
    const bar   = document.getElementById('bulkBar');
    const count = document.getElementById('bulkCount');
    if (!bar) return;
    bar.style.display = (_bulkMode && _bulkSelected.size > 0) ? '' : 'none';
    if (count) count.textContent = `${_bulkSelected.size} selected`;
}

async function bulkEnable() {
    const ids = [..._bulkSelected];
    for (const id of ids) {
        const card = document.querySelector(`.route-card[data-routekey="${CSS.escape(id)}"]`);
        const enabled = card?.dataset.enabled === 'true';
        if (!enabled) await toggleRoute(id, false, true);
    }
    _bulkSelected.clear(); updateBulkBar(); refreshRoutes();
}

async function bulkDisable() {
    const ids = [..._bulkSelected];
    for (const id of ids) {
        const card = document.querySelector(`.route-card[data-routekey="${CSS.escape(id)}"]`);
        const enabled = card?.dataset.enabled === 'true';
        if (enabled) await toggleRoute(id, true, true);
    }
    _bulkSelected.clear(); updateBulkBar(); refreshRoutes();
}

async function bulkDelete() {
    const ids = [..._bulkSelected];
    if (!ids.length) return;
    if (!await _confirm(`Delete ${ids.length} route${ids.length > 1 ? 's' : ''}? This removes them from the config files and stops serving them.`, 'Bulk Delete', 'Delete', 'DELETE')) return;
    const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
    let failed = 0, firstErr = '';
    for (const id of ids) {
        const card = document.querySelector(`.route-card[data-routekey="${CSS.escape(id)}"]`);
        const cf   = card?.dataset.configfile || '';
        const data = new FormData();
        data.append('csrf_token', csrf);
        if (cf) data.append('configFile', cf);
        if (_activeAgent) data.append('agent_id', _activeAgent.id);
        try {
            const res  = await fetch('/delete/' + encodeURIComponent(id), { method:'POST', headers:{'X-Requested-With':'fetch'}, body: data });
            if (!res.ok) {
                failed++;
                if (!firstErr) firstErr = await _errText(res, 'Route could not be deleted');
                continue;
            }
            const json = await res.json();
            if (!json.ok) {
                failed++;
                if (!firstErr) firstErr = json.message || json.error || '';
            }
        } catch(e) { failed++; if (!firstErr) firstErr = _netErrText(e, 'Route could not be deleted'); }
    }
    if (failed) showToast(`${failed} of ${ids.length} route${ids.length > 1 ? 's' : ''} could not be deleted.` + (firstErr ? ' ' + firstErr : ''), 'error');
    else showToast(`Deleted ${ids.length} route${ids.length > 1 ? 's' : ''}.`, 'success');
    _bulkSelected.clear(); updateBulkBar(); refreshRoutes(); fetchNotifications();
    if (typeof window.rmInvalidateData === 'function') window.rmInvalidateData();
}

function toggleRouteView() {
    _routeViewMode = _routeViewMode === 'grid' ? 'list' : 'grid';
    tmSetPref('routeViewMode', _routeViewMode);
    const icon = document.getElementById('routeViewIcon');
    if (icon) icon.className = _routeViewMode === 'grid' ? 'ph-bold ph-list' : 'ph-bold ph-squares-four';
    refreshRoutes();
}


function openRouteDetailFromCard(card) {
    const routeKey = card.getAttribute('data-routekey');
    if (!routeKey) return;
    const pool = window._lastRenderedApps || APP_DATA || [];
    const appData = pool.find(a => a.name === routeKey) || pool.find(a => a.id === routeKey);
    if (!appData) return;
    openRouteDetail(appData.name, appData.protocol, appData);
}
function _openRouteByName(name) {
    const bare = String(name).split('@')[0];
    const pool = window._lastRenderedApps || APP_DATA || [];
    const a = pool.find(x => x.name === name)
        || pool.find(x => String(x.name).split('@')[0] === bare);
    if (!a) return;
    openRouteDetail(a.name, (a.protocol || 'http').toLowerCase(), a);
}

let _liveRoutersCache = null;
let _liveServicesCache = null;
let _liveEntrypointsCache = null;
let _currentDetailApp = null;

async function openRouteDetail(name, protocol, appData) {
    closeOtherPanels('detailPanel');
    _currentDetailApp = appData;
    const panel = document.getElementById('detailPanel');
    const backdrop = document.getElementById('detailBackdrop');
    const badge = document.getElementById('detailProtoBadge');
    const title = document.getElementById('detailTitle');
    const content = document.getElementById('detailContent');
    const editBtn = document.getElementById('detailEditBtn');

    
    badge.className = 'd-flat d-proto' + (protocol === 'tcp' ? ' d-on' : protocol === 'udp' ? ' d-warn' : '');
    badge.textContent = protocol.toUpperCase();
    title.textContent = name;

    
    const isFileRoute = !appData.provider || appData.provider === 'file';
    editBtn.style.display = isFileRoute ? '' : 'none';
    if (isFileRoute) {
        editBtn.onclick = () => {
            closeRouteDetail();
            const fakeBtn = document.createElement('button');
            fakeBtn.setAttribute('data-app', JSON.stringify(appData));
            handleEdit(fakeBtn);
        };
    }

    
    panel.classList.add('open');
    backdrop.classList.add('open');
    if (!setDetailDockOpen(true)) document.body.style.overflow = 'hidden';

    content.innerHTML = `<div class="text-center py-12" style="color:var(--muted)">
        <i class="ph-light ph-spinner-gap text-3xl animate-spin block mb-2 opacity-50"></i>
        <p class="text-sm">Fetching live data…</p>
    </div>`;

    try {
        
        const [routersRes, servicesRes, entrypointsRes] = await Promise.allSettled([
            agentFetch('/api/traefik/routers').then(r => r.json()),
            agentFetch('/api/traefik/services').then(r => r.json()),
            agentFetch('/api/traefik/entrypoints').then(r => r.json()),
        ]);

        let liveRouter = null, liveService = null, entrypoints = [];
        const apiState = { reachable: false, fileRouters: 0 };

        if (routersRes.status === 'fulfilled' && routersRes.value
                && !routersRes.value.error && routersRes.value.reachable !== false) {
            apiState.reachable = true;
            const allRouters = [
                ...(routersRes.value.http || []),
                ...(routersRes.value.tcp  || []),
                ...(routersRes.value.udp  || []),
            ];
            apiState.fileRouters = allRouters.filter(r => (r.provider || '') === 'file' || String(r.name || '').endsWith('@file')).length;
            liveRouter = allRouters.find(r => r.name && r.name.split('@')[0] === name);
        }

        if (servicesRes.status === 'fulfilled') {
            const allServices = [
                ...(servicesRes.value.http || []),
                ...(servicesRes.value.tcp  || []),
                ...(servicesRes.value.udp  || []),
            ];
            const svcName = appData.service_name || (name + '-service');
            liveService = allServices.find(s => s.name && s.name.split('@')[0] === svcName);
        }

        if (entrypointsRes.status === 'fulfilled') {
            entrypoints = entrypointsRes.value || [];
        }

        content.innerHTML = renderDetailPanel(appData, protocol, liveRouter, liveService, entrypoints, apiState);

    } catch(e) {
        content.innerHTML = renderDetailPanel(appData, protocol, null, null, [], { reachable: false, fileRouters: 0 });
    }
}

function closeRouteDetail() {
    setDetailDockOpen(false);
    document.getElementById('detailPanel').classList.remove('open');
    document.getElementById('detailBackdrop').classList.remove('open');
    document.getElementById('detailEditBtn').style.display = '';

    document.getElementById('detailTitle').nextElementSibling?.classList.contains('badge') &&
        document.getElementById('detailTitle').nextElementSibling.remove();
    document.body.style.overflow = '';
}

function renderDetailPanel(app, protocol, liveRouter, liveService, entrypoints, apiState) {
    const status = liveRouter ? liveRouter.status : null;
    const _rawErr = liveRouter ? liveRouter.error : null;
    const routerError = !_rawErr ? null
        : (Array.isArray(_rawErr) ? _rawErr : [_rawErr])
            .map(x => (typeof x === 'string' ? x : (x && x.message) || JSON.stringify(x)))
            .map(x => String(x).trim()).filter(Boolean).join(' - ') || null;
    const isDisabled = app.enabled === false;
    const statusBadge = isDisabled
        ? _dState('Disabled')
        : _dState(status === 'enabled' ? 'Enabled' : status);
    const errorBanner = routerError
        ? `<div class="mt-4 p-3 rounded-lg text-xs font-mono leading-relaxed" style="color:var(--red);background:rgba(248,81,73,0.08);border:1px solid rgba(248,81,73,0.25);word-break:break-word"><i class="ph-bold ph-warning-circle" style="margin-right:6px"></i>${_esc(routerError)}</div>`
        : '';

    const isFileRoute = !app.provider || app.provider === 'file';
    const _warnNote = html => `<div class="text-xs mb-5 p-2.5 rounded" style="color:var(--yellow);background:rgba(210,153,34,0.08);border:1px solid rgba(210,153,34,0.2);line-height:1.6"><i class="ph-bold ph-warning text-sm" style="margin-right:5px"></i>${html}</div>`;
    const apiNote = liveRouter
        ? `<div class="flex items-center gap-1.5 text-xs mb-5" style="color:var(--muted)"><div style="width:5px;height:5px;border-radius:50%;background:var(--green);display:inline-block"></div> Live data from Traefik API</div>`
        : isDisabled
        ? `<div class="flex items-center gap-1.5 text-xs mb-5 p-2 rounded" style="color:var(--muted);background:var(--input-bg);border:1px solid var(--border)"><i class="ph-bold ph-pause-circle text-sm"></i> Not served by Traefik while disabled - showing your saved configuration</div>`
        : !(apiState && apiState.reachable)
        ? _warnNote(`<b>Traefik API unreachable</b> - showing your saved configuration. Check the API URL under Settings &gt; Connection, and that Traefik has <span class="font-mono">api: {}</span> enabled.`)
        : isFileRoute && apiState.fileRouters === 0
        ? _warnNote(`<b>Traefik is running but has loaded nothing from the file provider</b>, so this route is not being served. Traefik is most likely not watching the file Traefik Manager writes to - check that both containers mount the same config path and that <span class="font-mono">providers.file</span> points at it with <span class="font-mono">watch: true</span>. Showing your saved configuration.`)
        : isFileRoute
        ? _warnNote(`<b>Traefik has not loaded this route</b>, although other file-provider routes are live. If you saved it seconds ago, close and reopen. Otherwise check the Traefik logs for a config error${app.configFile ? `, and that <span class="font-mono">${_esc(app.configFile)}</span> is inside the watched path` : ''}. Showing your saved configuration.`)
        : _warnNote(`<b>Traefik does not report this route</b> - showing your saved configuration.`);

    
    const routerEPs = (liveRouter ? liveRouter.entryPoints : app.entryPoints) || [];
    const matchedEPs = entrypoints.filter(ep => routerEPs.includes(ep.name));

    const epBoxes = routerEPs.map(epName => {
        const ep = matchedEPs.find(e => e.name === epName);
        const addr = ep ? ep.address : '';
        const port = addr.split(':').pop();
        const isHttps = ['443','8443'].includes(port);
        return `<div class="flow-box text-center">
            <div class="text-xs font-bold uppercase tracking-wider mb-1" style="color:var(--muted)">Entry Point</div>
            <div class="font-bold text-sm" style="color:var(--text)">${_esc(epName).toUpperCase()}</div>
            ${addr ? `<div class="font-mono text-xs mt-1" style="color:var(--muted)">${_esc(addr)}</div>` : ''}
            ${isHttps ? '<div class="mt-1 d-flat d-on">TLS</div>' : ''}
        </div>`;
    }).join('') || `<div class="flow-box text-center"><div class="text-xs font-bold uppercase tracking-wider mb-1" style="color:var(--muted)">Entry Point</div><div class="text-sm" style="color:var(--muted)">-</div></div>`;

    const hasTls = liveRouter ? !!(liveRouter.tls) : !!(app.entryPoints && app.entryPoints.includes('https'));
    const tlsInfo = hasTls ? '<div class="mt-1.5 d-flat d-on"><i class="ph-bold ph-shield-check"></i> TLS</div>' : '';

    const serversList = liveService ? (liveService.loadBalancer?.servers || []) : [];
    const serversHtml = serversList.length > 0
        ? serversList.map(s => `<div class="font-mono text-xs break-all mt-1 px-2 py-1 rounded" style="color:var(--green);background:var(--input-bg);word-break:break-all">${_esc(s.url || s.address || '-')}</div>`).join('')
        : `<div class="font-mono text-xs break-all mt-1 px-2 py-1 rounded" style="color:var(--green);background:var(--input-bg);word-break:break-all">${_esc(app.target)}</div>`;

    const flowHtml = renderDetailBlock('Traffic Flow', 'ph-flow-arrow', `
        <div class="flex items-stretch gap-2 flow-diagram-row">
            <div class="flex flex-col gap-2 flex-1">${epBoxes}</div>
            <div class="flow-arrow">→</div>
            <div class="flow-box active-box text-center flex-1">
                <div class="text-xs font-bold uppercase tracking-wider mb-1" style="color:var(--blue)">Router</div>
                <div class="font-bold text-sm" style="color:var(--text)">${_esc(app.name)}</div>
                ${tlsInfo}
                <div class="mt-1.5">${statusBadge}</div>
            </div>
            <div class="flow-arrow">→</div>
            <div class="flow-box text-center flex-1">
                <div class="text-xs font-bold uppercase tracking-wider mb-1" style="color:var(--muted)">Service</div>
                <div class="font-bold text-sm truncate" style="color:var(--text)">${_esc(app.service_name)}</div>
                <div class="mt-2">${serversHtml}</div>
            </div>
        </div>`);

    
    const rule = liveRouter ? liveRouter.rule : app.rule;
    const provider = liveRouter ? (liveRouter.provider || 'file') : 'file';
    const priority = liveRouter ? (liveRouter.priority ?? '-') : '-';

    const routerRows = [
        ['Status', statusBadge, true],
        ['Provider', _dText(provider, 'd-off'), true],
        ['Rule', rule || '-', false],
        ['Name', (liveRouter ? liveRouter.name : app.name) || '-', false],
        ['Entry Points', _dList(routerEPs), true],
        ['Service', app.service_name || '-', false],
        ['Priority', String(priority), false],
    ];

    
    const tlsData = liveRouter ? liveRouter.tls : (hasTls ? { certResolver: 'cloudflare' } : null);
    let tlsSection = '';
    if (protocol === 'http' || protocol === 'tcp') {
        const tlsRows = [
            ['TLS', _dBool(!!tlsData, 'Enabled', 'Disabled'), true],
            ['Certificate Resolver', tlsData ? (tlsData.certResolver || '-') : '-', false],
            ['Options', tlsData ? (tlsData.options || 'default') : '-', false],
            ['Passthrough', _dBool(protocol === 'tcp' && tlsData && !!tlsData.passthrough), true],
        ];
        tlsSection = renderSection('TLS', 'ph-shield', tlsRows);
    }

    
    const mws = (liveRouter ? liveRouter.middlewares : app.middlewares) || [];
    let mwSection = '';
    if (protocol !== 'udp') {
        const mwBody = mws.length > 0
            ? `<div class="flex flex-wrap gap-1.5">${mws.map(m =>
                `<button type="button" class="route-deep-chip" onclick="_openMwByName(${_jsArg(String(m))})" title="Open middleware"><i class="ph-bold ph-plugs-connected"></i>${_esc(String(m).split('@')[0])}</button>`).join('')}</div>`
            : `<div class="text-center py-3" style="color:var(--muted)">
                    <i class="ph-light ph-stack text-2xl block mb-1 opacity-30"></i>
                    <p class="text-xs">No middlewares configured</p>
                </div>`;
        mwSection = renderDetailBlock('Middlewares', 'ph-plugs-connected', mwBody,
            mws.length > 0 ? _dCount(mws.length) : '');
    }

    
    const svcLoadBalancer = liveService ? liveService.loadBalancer : null;
    const svcServers = svcLoadBalancer ? (svcLoadBalancer.servers || []) : [{ url: app.target }];
    const svcPassHostHeader = svcLoadBalancer ? (svcLoadBalancer.passHostHeader !== false ? 'true' : 'false') : '-';
    const svcStatus = liveService ? (liveService.status || '-') : '-';

    const svcServerRows = svcServers.map((s, i) => [
        `Server ${i + 1}`,
        s.url || s.address || '-',
        false
    ]);

    const svcRows = [
        ['Status', svcStatus !== '-' ? _dState(svcStatus === 'enabled' ? 'Enabled' : svcStatus) : '-', svcStatus !== '-'],
        ['Type', app.serviceType && app.serviceType !== 'loadBalancer' ? app.serviceType : 'Load Balancer', false],
        ['Pass Host Header', svcPassHostHeader, false],
        ...(app.containerAddr ? [['Container', app.containerAddr, false]] : []),
        ...svcServerRows,
    ];

    
    let labelsSection = '';
    if (app.dockerLabels && typeof app.dockerLabels === 'object') {
        const labelEntries = Object.entries(app.dockerLabels)
            .filter(([k]) => k.startsWith('traefik.'))
            .sort(([a], [b]) => a.localeCompare(b));
        if (labelEntries.length > 0) {
            const labelRows = labelEntries.map(([k, v]) =>
                `<div class="font-mono text-xs py-1.5 px-0" style="border-bottom:1px solid var(--border);display:grid;grid-template-columns:1fr auto;gap:8px;align-items:start">
                    <span style="color:var(--muted);word-break:break-all">${k.replace(/</g,'&lt;')}</span>
                    <span style="color:var(--text);text-align:right;word-break:break-all">${String(v).replace(/</g,'&lt;')}</span>
                </div>`
            ).join('');
            labelsSection = renderDetailBlock('Docker Labels', 'ph-tag', labelRows,
                _dCount(labelEntries.length));
        }
    }

    return `
    ${apiNote}
    ${errorBanner}
    ${flowHtml}
    ${renderSection('Router Details', 'ph-info', routerRows)}
    ${tlsSection}
    ${mwSection}
    ${renderSection('Service', 'ph-lightning', svcRows)}
    ${labelsSection}
    `;
}



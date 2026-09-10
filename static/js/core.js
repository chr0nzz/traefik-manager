function showToast(msg, type='success', record=true, category='') {
    const icon = type === 'success' ? 'ph-check-circle' : 'ph-warning-circle';
    const color = type === 'success' ? 'text-green-400' : 'text-red-400';
    const el = document.createElement('div');
    el.className = `toast-item ${type}`;
    el.innerHTML = `<i class="ph-fill ${icon} ${color} text-lg"></i><span>${_esc(msg)}</span>`;
    document.getElementById('toastContainer').appendChild(el);
    setTimeout(() => { el.style.animation='slideOut 0.3s ease forwards'; setTimeout(()=>el.remove(),300); }, 4000);
    if (record) _recordNotification(msg, type, category);
}

const _TOAST_CATEGORY_BY_PANEL = {
    agents: 'agent', backups: 'backup', auth: 'security',
};
const _TOAST_CATEGORY_BY_TAB = {
    certs: 'certs', crowdsec: 'crowdsec', logs: 'traefik',
};

function _toastCategory() {
    try {
        for (const el of document.querySelectorAll('[id^="mpanel-"]')) {
            if (el.offsetParent === null) continue;
            const hit = _TOAST_CATEGORY_BY_PANEL[el.id.slice('mpanel-'.length)];
            if (hit) return hit;
        }
        if (typeof _activeTab === 'string') {
            const hit = _TOAST_CATEGORY_BY_TAB[_activeTab];
            if (hit) return hit;
        }
    } catch (e) {}
    return 'config';
}

async function _recordNotification(msg, type, category) {
    if (!category) category = _toastCategory();
    if (typeof _csrfHeaders !== 'function') return;
    try {
        const res = await fetch('/api/notifications/log', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'fetch', ..._csrfHeaders() },
            body: JSON.stringify({ message: msg, category,
                type: type === 'success' ? 'success' : type === 'info' ? 'info' : 'error' }),
        });
        const json = await res.json();
        if (json && json.stored) fetchNotifications();
    } catch (e) {}
}

const OPTIONAL_TABS = ['dashboard', 'routemap', 'docker', 'kubernetes', 'swarm', 'nomad', 'ecs', 'consulcatalog', 'redis', 'etcd', 'consul', 'zookeeper', 'http_provider', 'file_external', 'internal', 'certs', 'tls', 'crowdsec', 'plugins', 'logs', 'static'];

let _visibleTabsCache = {};
let _localTabsCache   = {};

const TAB_DEFS = [
    { id: 'dashboard',     label: 'Dashboard',       icon: 'ph-house' },
    { id: 'services',      label: 'Routes',          icon: 'ph-arrows-split' },
    { id: 'middlewares',   label: 'Middlewares',     icon: 'ph-stack' },
    { id: 'live',          label: 'Services',        icon: 'ph-hard-drives' },
    { id: 'routemap',      label: 'Route Map',       icon: 'ph-tree-structure' },
    { id: 'logs',          label: 'Logs',            icon: 'ph-receipt' },
    { id: 'crowdsec',      label: 'CrowdSec',        icon: 'ph-shield' },
    { id: 'certs',         label: 'Certs',           icon: 'ph-shield-check' },
    { id: 'tls',           label: 'TLS Options',     icon: 'ph-lock-laminated' },
    { id: 'plugins',       label: 'Plugins',         icon: 'ph-puzzle-piece' },
    { id: 'static',        label: 'Static Config',   icon: 'ph-file-code' },
    { id: 'docker',        label: 'Docker',          icon: 'ph-cube' },
    { id: 'kubernetes',    label: 'Kubernetes',      icon: 'ph-circles-three' },
    { id: 'swarm',         label: 'Swarm',           icon: 'ph-graph' },
    { id: 'nomad',         label: 'Nomad',           icon: 'ph-circles-four' },
    { id: 'ecs',           label: 'ECS',             icon: 'ph-cloud' },
    { id: 'consulcatalog', label: 'Consul Catalog',  icon: 'ph-address-book' },
    { id: 'redis',         label: 'Redis',           icon: 'ph-database' },
    { id: 'etcd',          label: 'etcd',            icon: 'ph-database' },
    { id: 'consul',        label: 'Consul KV',       icon: 'ph-database' },
    { id: 'zookeeper',     label: 'ZooKeeper',       icon: 'ph-database' },
    { id: 'internal',      label: 'Internal',        icon: 'ph-gear-six' },
    { id: 'http_provider', label: 'HTTP Provider',   icon: 'ph-link' },
    { id: 'file_external', label: 'File (external)', icon: 'ph-file-text' },
];
const TAB_BY_ID = Object.fromEntries(TAB_DEFS.map(t => [t.id, t]));

const _tabCounts = {};

function setTabCount(tab, n) {
    const val = (n === null || n === undefined || n === '' || n === '-') ? null : String(n);
    if (_tabCounts[tab] === val) return;
    _tabCounts[tab] = val;
    const el = document.querySelector('#sbtn-' + tab + ' .side-nav-count');
    if (el) { el.textContent = val ?? ''; el.style.display = val === null ? 'none' : ''; }
    else buildSideNav();
}

const SIDE_NAV_GROUPS = [
    { label: 'Traffic',        tabs: ['dashboard', 'services', 'middlewares', 'live', 'routemap'] },
    { label: 'Observability',  tabs: ['logs', 'crowdsec'] },
    { label: 'Infrastructure', tabs: ['certs', 'tls', 'plugins', 'static'] },
    { label: 'Providers',      tabs: ['docker', 'kubernetes', 'swarm', 'nomad', 'ecs', 'consulcatalog', 'redis', 'etcd', 'consul', 'zookeeper', 'http_provider', 'file_external', 'internal'] },
];

function _tabVisible(tab) {
    if (OPTIONAL_TABS.includes(tab)) return !!_visibleTabsCache[tab];
    return true;
}

let _activeTab = 'services';

function buildSideNav() {
    const nav = document.getElementById('sideNavItems');
    if (!nav) return;
    nav.innerHTML = '';
    const collapsed = window.innerWidth >= 768
        && document.documentElement.classList.contains('tm-nav-collapsed');

    const make = (def) => {
        const item = document.createElement('button');
        item.className = 'side-nav-item' + (def.id === _activeTab ? ' active' : '');
        item.id = 'sbtn-' + def.id;
        item.title = collapsed ? def.label : '';
        item.onclick = () => { closeSideNavDrawer(); switchTab(def.id); };
        const count = _tabCounts[def.id];
        item.innerHTML = `<i class="ph-bold ${def.icon}"></i>`
            + `<span class="side-nav-label">${_esc(def.label)}</span>`
            + `<span class="side-nav-count"${count === null || count === undefined ? ' style="display:none"' : ''}>`
            + `${count === null || count === undefined ? '' : _esc(count)}</span>`;
        return item;
    };

    const grouped = new Set(SIDE_NAV_GROUPS.flatMap(g => g.tabs));
    TAB_DEFS.filter(d => !grouped.has(d.id) && _tabVisible(d.id))
            .forEach(d => nav.appendChild(make(d)));

    for (const group of SIDE_NAV_GROUPS) {
        const present = group.tabs.filter(t => TAB_BY_ID[t] && _tabVisible(t));
        if (!present.length) continue;
        const head = document.createElement('div');
        head.className = 'side-nav-section';
        head.textContent = group.label;
        nav.appendChild(head);
        present.forEach(t => nav.appendChild(make(TAB_BY_ID[t])));
    }
}

function _tmMono(name) {
    const m = String(name || '').replace(/[^A-Za-z0-9]/g, '');
    return (m.slice(0, 2) || '?').toUpperCase();
}

function revealBelowFold(el) {
    if (!el) return;
    const r = el.getBoundingClientRect();
    if (r.height === 0 && r.top === 0) return;
    if (r.top >= 0 && r.top < window.innerHeight * 0.6) return;
    el.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

const MODAL_CLOSERS = {
    appModal:        'closeModal',
    mwModal:         'closeMwModal',
    detailPanel:     'closeRouteDetail',
    settingsModal:   'closeSettingsModal',
    tlsOptionsModal: 'closeTlsOptionModal',
    ipDiagModal:     'closeIpDiagModal',
    csBanModal:      'closeCsBanModal',
    trustedIpsModal: 'closeTrustedIpsModal',
    rmEditModal:     'rmCloseEditModal',
    rmGroupsModal:   'rmCloseGroupsModal',
    mwDetailPanel:     'closeMwDetail',
    svcDetailPanel:    'closeSvcDetail',
    pluginDetailPanel: 'closePluginDetail',
    logDetailPanel:    'closeLogDetail',
    tlsOptDetailPanel: 'closeTlsOptDetail',
    mwTplPanel:        'closeTemplatesPanel',
};

function closeOtherPanels(keepId) {
    const open = new Set(
        [...document.querySelectorAll('.detail-panel.open, .modal-overlay.open')].map(el => el.id));
    document.querySelectorAll('.modal-overlay, .detail-panel').forEach(el => {
        if (el.id && el.style.display && el.style.display !== 'none') open.add(el.id);
    });
    open.forEach(id => {
        if (!id || id === keepId) return;
        const fn = window[MODAL_CLOSERS[id]];
        if (typeof fn === 'function') fn();
        else document.getElementById(id)?.classList.remove('open');
    });
}

function _detailDockActive() {
    return !document.documentElement.classList.contains('tm-fixed')
        && !document.documentElement.classList.contains('tm-settings-open')
        && window.matchMedia('(min-width: 1440px)').matches;
}

function _initDetailPanelSizers() {
    document.querySelectorAll('.detail-panel').forEach(panel => {
        if (panel.querySelector('.detail-panel-sizer')) return;
        const grip = document.createElement('div');
        grip.className = 'detail-panel-sizer';
        grip.title = 'Drag to resize - double-click to reset';
        panel.appendChild(grip);
        let dragging = false;
        const reset = () => { panel.style.width = ''; panel.style.maxWidth = ''; };
        grip.addEventListener('pointerdown', e => {
            dragging = true;
            grip.classList.add('dragging');
            grip.setPointerCapture(e.pointerId);
            document.body.style.userSelect = 'none';
            e.preventDefault();
        });
        grip.addEventListener('pointermove', e => {
            if (!dragging) return;
            const w = Math.min(Math.max(Math.round(window.innerWidth - e.clientX), 380), Math.round(window.innerWidth * 0.96));
            panel.style.width = w + 'px';
            panel.style.maxWidth = w + 'px';
        });
        const end = () => {
            if (!dragging) return;
            dragging = false;
            grip.classList.remove('dragging');
            document.body.style.userSelect = '';
        };
        grip.addEventListener('pointerup', end);
        grip.addEventListener('pointercancel', end);
        grip.addEventListener('dblclick', reset);
        new MutationObserver(() => {
            if (!panel.classList.contains('open')) reset();
        }).observe(panel, { attributes: true, attributeFilter: ['class'] });
    });
}

function setDetailDockOpen(on) {
    const active = _detailDockActive();
    document.documentElement.classList.toggle('tm-detail-open', on && active);
    return active;
}

let _sideNavSyncTimer = null;
function watchTabBarForSideNav() {
    const bar = document.getElementById('tabBar');
    if (!bar || bar._sideNavWatched) return;
    bar._sideNavWatched = true;
    new MutationObserver(() => {
        clearTimeout(_sideNavSyncTimer);
        _sideNavSyncTimer = setTimeout(buildSideNav, 80);
    }).observe(bar, { subtree: true, childList: true, characterData: true });
}

function toggleSideNavCollapse() {
    const on = document.documentElement.classList.toggle('tm-nav-collapsed');
    localStorage.setItem('tm-nav-collapsed', on ? '1' : '0');
    buildSideNav();
}

function applyTabVisibility(map) {
    if (map) _visibleTabsCache = map;
    if (!_tabVisible(_activeTab)) switchTab('services');
    buildSideNav();
    applyGeoipRelevance();
}

function applyGeoipRelevance() {
    const sec = document.getElementById('geoipSection');
    if (!sec) return;
    const used = !!(_visibleTabsCache.logs || _visibleTabsCache.crowdsec);
    const on   = document.getElementById('toggle-geoip')?.classList.contains('on');
    sec.style.display = (used || on) ? '' : 'none';
}

let _statsHomeMarker = null;
const STAT_TABS = ['dashboard', 'services', 'middlewares', 'live'];

function _statTabSet() {
    const raw = typeof tmPref === 'function' ? tmPref('statBarScope') : 'all';
    if (raw === 'all' || raw === undefined || raw === null || raw === '') return new Set(STAT_TABS);
    if (raw === 'none') return new Set();
    if (raw === 'dashboard') return new Set(['dashboard']);
    return new Set(String(raw).split(',').map(s => s.trim()).filter(t => STAT_TABS.includes(t)));
}

function placeStatCards() {
    const ov = document.getElementById('overviewSection');
    if (!ov) return;
    if (!_statsHomeMarker) {
        _statsHomeMarker = document.createElement('div');
        _statsHomeMarker.style.display = 'none';
        ov.parentElement.insertBefore(_statsHomeMarker, ov);
    }
    const active = document.querySelector('main .tab-content.active');
    const tab = active ? active.id.replace(/^tab-/, '') : '';
    if (!_statTabSet().has(tab)) { _statsHomeMarker.insertAdjacentElement('afterend', ov); return; }
    const bar = active.querySelector('.filter-bar');
    if (bar) bar.insertAdjacentElement('afterend', ov);
    else active.insertAdjacentElement('afterbegin', ov);
}

function switchTab(tab) {
    document.documentElement.classList.toggle('tm-tab-dashboard', tab === 'dashboard');
    document.documentElement.classList.toggle('tm-stats-here', _statTabSet().has(tab));
    _activeTab = tab;
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.querySelectorAll('.side-nav-item').forEach(i => i.classList.remove('active'));
    document.getElementById('sbtn-' + tab)?.classList.add('active');
    document.getElementById('tab-' + tab)?.classList.add('active');
    if (tab === 'dashboard')     refreshDashboardTab();
    if (tab === 'routemap')      refreshRoutemapTab();
    if (tab === 'services' || tab === 'middlewares') refreshRoutes();
    if (tab === 'live')          refreshLiveView();
    if (tab === 'docker')        refreshDockerTab();
    if (tab === 'kubernetes')    refreshKubernetesTab();
    if (tab === 'swarm')         refreshSwarmTab();
    if (tab === 'nomad')         refreshNomadTab();
    if (tab === 'ecs')           refreshEcsTab();
    if (tab === 'consulcatalog') refreshConsulCatalogTab();
    if (tab === 'redis')         refreshRedisTab();
    if (tab === 'etcd')          refreshEtcdTab();
    if (tab === 'consul')        refreshConsulTab();
    if (tab === 'zookeeper')     refreshZookeeperTab();
    if (tab === 'http_provider') refreshHttpProviderTab();
    if (tab === 'internal')      refreshInternalTab();
    if (tab === 'file_external') refreshFileExternalTab();
    if (tab === 'certs')         refreshCertsTab();
    if (tab === 'tls')           refreshTlsOptionsTab();
    if (tab === 'crowdsec')      refreshCrowdSecTab();
    if (tab === 'plugins')       refreshPluginsTab();
    if (tab === 'static')        openStaticTab();
    if (tab === 'logs')          refreshLogs();
    if (typeof _lgAutoSync === 'function') _lgAutoSync();
    placeStatCards();
    _initMobileFilterBars();
}

function _buildConfigSelectOptions(sel, files, allowNew) {
    sel.innerHTML = '<option value="">Select a file...</option>';
    if (allowNew) {
        const o = document.createElement('option'); o.value = '__new__'; o.textContent = '+ New file...'; sel.appendChild(o);
    }
    files.forEach(f => { const o = document.createElement('option'); o.value = f; o.textContent = f; sel.appendChild(o); });
}

async function _populateConfigFileSelect(which) {
    const isRoute = which === 'route';
    const isPluginMw = which === 'pluginMw';
    const isService = which === 'service';
    const wrapId     = isService ? 'svcConfigFileSelectWrap' : isPluginMw ? 'pluginMwFileSelectWrap' : isRoute ? 'configFileSelectWrap' : 'mwConfigFileSelectWrap';
    const selId      = isService ? 'svcConfigFileSelect' : isPluginMw ? 'pluginMwFileSelect' : isRoute ? 'configFileSelect' : 'mwConfigFileSelect';
    const newInputId = isService ? 'newSvcFileName' : isPluginMw ? 'pluginMwNewFileName' : isRoute ? 'newRouteFileName' : 'newMwFileName';
    const wrap    = document.getElementById(wrapId);
    const sel     = document.getElementById(selId);
    const newInput = document.getElementById(newInputId);
    if (!sel) return;
    if (newInput) { newInput.style.display = 'none'; newInput.value = ''; }
    const onChange = isService ? onSvcConfigFileChange : isPluginMw ? onPluginMwFileChange : isRoute ? onRouteConfigFileChange : onMwConfigFileChange;
    if (_activeAgent) {
        if (wrap) wrap.style.display = '';
        try {
            const r = await agentFetch('/api/configs');
            const data = await r.json();
            const files = (data.files || []).map(f => f.name).sort();
            _buildConfigSelectOptions(sel, files, true);
            sel.value = files.length === 1 ? files[0] : '';
            onChange(sel);
        } catch(e) { console.error('Failed to load agent configs', e); }
    } else {
        const show = MULTI_CONFIG || CONFIG_DIR_SET;
        if (wrap) wrap.style.display = show ? '' : 'none';
        _buildConfigSelectOptions(sel, CONFIG_PATHS_LIST.map(cp => cp.label), CONFIG_DIR_SET);
        const realFiles = [...sel.options].filter(o => o.value && o.value !== '__new__');
        sel.value = realFiles.length === 1 ? realFiles[0].value : '';
        onChange(sel);
    }
}

function _dText(v, cls) {
    return `<span class="d-flat ${cls || ''}">${_esc(String(v))}</span>`;
}

function _dBool(on, yes, no) {
    return `<span class="d-flat ${on ? 'd-on' : 'd-off'}">${on ? (yes || 'Yes') : (no || 'No')}</span>`;
}

function _dList(items, cls) {
    const list = (items || []).filter(x => x !== undefined && x !== null && x !== '');
    if (!list.length) return '-';
    return `<span class="d-flat ${cls || 'd-off'}">${list.map(x => _esc(String(x))).join(' \u00b7 ')}</span>`;
}

function _dState(state) {
    const s = String(state || '').toLowerCase();
    const dot = s === 'enabled' ? 'status-online' : (s === 'disabled' || s === 'error') ? 'status-offline' : 'status-unknown';
    const cls = s === 'enabled' ? 'd-on' : (s === 'disabled' || s === 'error') ? 'd-bad' : 'd-off';
    return `<span class="d-state d-flat ${cls}"><span class="status-dot ${dot}"></span>${_esc(state || 'Unknown')}</span>`;
}

function renderSection(title, icon, rows) {
    const rowsHtml = rows.map(([key, val, isHtml]) => {
        const displayVal = isHtml ? val
            : `<span class="font-mono" style="color:var(--text)">${String(val).replace(/</g, '&lt;')}</span>`;
        return `<div class="detail-key">${key}</div><div class="detail-val">${displayVal}</div>`;
    }).join('');
    return `<div class="detail-section">
        <div class="detail-section-header">
            <i class="ph-bold ${icon} sc-sec-icon" style="color:var(--blue)"></i>
            <span class="sc-sec-label">${_esc(title)}</span>
            <span class="sc-sec-rule"></span>
        </div>
        <div class="detail-kv">${rowsHtml}</div>
    </div>`;
}

function renderDetailBlock(title, icon, bodyHtml, badgeHtml) {
    return `<div class="detail-section">
        <div class="detail-section-header">
            <i class="ph-bold ${icon} sc-sec-icon" style="color:var(--blue)"></i>
            <span class="sc-sec-label">${_esc(title)}</span>
            ${badgeHtml || ''}
            <span class="sc-sec-rule"></span>
        </div>
        <div class="detail-body">${bodyHtml}</div>
    </div>`;
}

function _dCount(n) {
    return `<span class="d-n">${n}</span>`;
}

async function _errText(res, fallback) {
    if (res && res.status === 502) return 'Cannot reach the agent. Check that it is running and reachable.';
    if (res && res.status === 401) return 'Session expired. Sign in again.';
    if (res && res.status === 403) return 'Not allowed. Your session may have expired.';
    if (res && res.status === 404) return fallback + ' (not found)';
    try {
        const data = await res.json();
        const detail = data.error || data.message;
        if (detail) return String(detail).slice(0, 300);
    } catch (e) {}
    return res && res.status ? `${fallback} (HTTP ${res.status})` : fallback;
}


function _passwordError(pw, label) {
    label = label || 'Password';
    if (pw.length < 8) return label + ' must be at least 8 characters.';
    if (new TextEncoder().encode(pw).length > 72) {
        return label + ' must be 72 bytes or fewer, which is the bcrypt limit. '
             + 'Accented and non-Latin characters take more than one byte each.';
    }
    return null;
}


function _netErrText(err, fallback) {
    const msg = String((err && err.message) || err || '');
    if (/Failed to fetch|NetworkError|Load failed/i.test(msg)) {
        return 'No response from Traefik Manager. Check that it is still running.';
    }
    return msg ? `${fallback}: ${msg.slice(0, 200)}` : fallback;
}


function _esc(s) {
    return String(s == null ? '' : s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

function _jsArg(v) {
    return _esc(JSON.stringify(v == null ? '' : String(v)));
}

let _backdropMd = null;
function _onBackdropClick(e, fn) {
    if (e.target === e.currentTarget && _backdropMd === e.currentTarget) fn();
}

let _currentVersion = null;

function toggleLiveDd(id) {
    const menu = document.getElementById(id + '-menu');
    const btn  = document.getElementById(id + '-btn');
    const isOpen = menu.classList.contains('open');
    document.querySelectorAll('.live-dd-menu.open').forEach(m => m.classList.remove('open'));
    document.querySelectorAll('.live-dd-btn-inner.open').forEach(b => b.classList.remove('open'));
    if (!isOpen) { menu.classList.add('open'); btn.classList.add('open'); }
}

async function refreshStorageBanner() {
    const el = document.getElementById('storageBanner');
    if (!el) return;
    let problems = [];
    try {
        const res = await fetch('/api/storage/status', { headers: { 'X-Requested-With': 'fetch' } });
        if (!res.ok) return;
        problems = (await res.json()).problems || [];
    } catch (e) {
        return;
    }
    if (!problems.length) { el.style.display = 'none'; el.innerHTML = ''; return; }
    el.style.display = 'block';
    el.innerHTML = `<div class="flex items-start gap-2">
            <i class="ph-bold ph-warning-octagon flex-shrink-0 mt-0.5" style="color:var(--red)"></i>
            <div class="text-xs">
                <div class="font-semibold" style="color:var(--text)">Storage is not writable</div>
                <div class="mt-1" style="color:var(--muted)">Settings, backups and scheduled checks will not survive a restart. Check the volume or bind mount for:</div>
                ${problems.map(p => `<div class="mt-1 font-mono" style="color:var(--muted)">${_esc(p.label)}: ${_esc(p.path)} <span style="opacity:.75">(${_esc(p.error)})</span></div>`).join('')}
            </div>
        </div>`;
}

let _tmAuthLost = false;

const TM_BASE = (document.querySelector('meta[name="tm-base-path"]')?.content || '').replace(/\/$/, '');

function tmUrl(path) {
    if (!TM_BASE) return path;
    if (typeof path !== 'string' || !path.startsWith('/')) return path;
    if (path === TM_BASE || path.startsWith(TM_BASE + '/')) return path;
    return TM_BASE + path;
}

function _tmAppPath(pathname) {
    if (TM_BASE && pathname.startsWith(TM_BASE)) return pathname.slice(TM_BASE.length) || '/';
    return pathname;
}

function _tmHandleAuthLoss() {
    if (_tmAuthLost) return;
    _tmAuthLost = true;
    const here = _tmAppPath(window.location.pathname) + window.location.search;
    window.location.href = tmUrl('/login') + '?next=' + encodeURIComponent(here);
}

(function () {
    const orig = window.fetch;
    window.fetch = function (input, init) {
        if (typeof input === 'string') input = tmUrl(input);
        return orig.call(this, input, init).then(res => {
            if (res.status !== 401) return res;
            let url = '';
            try { url = new URL(typeof input === 'string' ? input : input.url, window.location.origin).pathname; }
            catch (e) { url = String(input || ''); }
            if (_tmAppPath(url).startsWith('/api/') && !_tmAppPath(window.location.pathname).startsWith('/login')) {
                _tmHandleAuthLoss();
            }
            return res;
        });
    };
})();

let _shortcutsPanelOpen = false;

function toggleShortcutsPanel() {
    const panel = document.getElementById('shortcutsPanel');
    const btn   = document.getElementById('shortcutsBellBtn');
    if (!panel) return;
    _shortcutsPanelOpen = !_shortcutsPanelOpen;
    panel.classList.toggle('open', _shortcutsPanelOpen);
    if (btn) btn.style.color = _shortcutsPanelOpen ? 'var(--blue)' : '';
    if (_shortcutsPanelOpen) {
        const panelW = Math.min(320, window.innerWidth - 16);
        const r = btn && btn.offsetParent ? btn.getBoundingClientRect() : null;
        panel.style.position = 'fixed';
        panel.style.width = panelW + 'px';
        if (r && r.width) {
            let left = r.right - panelW;
            if (left < 8) left = 8;
            panel.style.top  = (r.bottom + 8) + 'px';
            panel.style.left = left + 'px';
        } else {
            panel.style.top  = Math.max(24, Math.round(window.innerHeight * 0.14)) + 'px';
            panel.style.left = Math.round((window.innerWidth - panelW) / 2) + 'px';
        }
    }
}

function _isTyping() {
    const t = document.activeElement?.tagName;
    return t === 'INPUT' || t === 'TEXTAREA' || t === 'SELECT' || document.activeElement?.isContentEditable;
}

function _closeTopModal() {
    const modals = [
        ['tlsOptionsModal', closeTlsOptionModal],
        ['csBanModal', window.closeCsBanModal],
        ['mwTplPanel', window.closeTemplatesPanel],
        ['pluginForm', window.closePluginForm],
        ['trustedIpsModal', window.closeTrustedIpsModal],
        ['appModal', closeModal],
        ['mwModal', closeMwModal],
        ['settingsModal', closeSettingsModal],
        ['ipDiagModal', closeIpDiagModal],
        ['rmEditModal', window.rmCloseEditModal],
        ['rmGroupsModal', window.rmCloseGroupsModal],
    ];
    for (const [id, close] of modals) {
        const el = document.getElementById(id);
        const shown = el && (el.classList.contains('detail-panel')
            ? el.classList.contains('open')
            : getComputedStyle(el).display !== 'none');
        if (shown && typeof close === 'function') {
            close();
            return true;
        }
    }
    return false;
}

const THEMES = ['dark', 'light', 'system'];

function applyTheme(theme) {
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const isDark = theme === 'dark' || (theme === 'system' && prefersDark);
    document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light');
    document.documentElement.setAttribute('data-tm-pref', theme);
    
    ['dark','light','system'].forEach(t => {
        document.getElementById('theme-'+t+'-m')?.classList.toggle('active', t === theme);
    });
}

const TM_PREF_DEFAULTS = {
    showStatCards: true, compactStatCards: false, showEntrypoints: true,
    showDocsLink: true, showApiLink: false, showShortcutsBtn: true,
    showIpDiagBtn: true, showTraefikBadge: true, showTmBadge: true,
    showRouteIcons: false,
    routeViewMode: 'grid', mwViewMode: 'grid', svcViewMode: 'grid',
    statBarScope: 'all',
    dashPodDensity: 'list',
    layoutMode: 'fluid',
    logsAutoRefresh: false,
};

let _prefSaveTimer = null;
let _prefPending = {};

function tmPref(key) {
    const server = window.TM_UI_PREFS || {};
    if (Object.prototype.hasOwnProperty.call(server, key)) return server[key];
    const local = localStorage.getItem(key);
    if (local !== null) {
        const dflt = TM_PREF_DEFAULTS[key];
        return typeof dflt === 'boolean' ? local !== 'false' : local;
    }
    return TM_PREF_DEFAULTS[key];
}

function syncThemeButtons(theme) {
    ['dark', 'light', 'system'].forEach(t => {
        const b = document.getElementById('theme-opt-' + t);
        if (b) b.className = 'proto-btn' + (t === theme ? ' active-http' : '');
    });
}

function tmSetPref(key, value) {
    window.TM_UI_PREFS = window.TM_UI_PREFS || {};
    window.TM_UI_PREFS[key] = value;
    localStorage.setItem(key, String(value));
    _prefPending[key] = value;
    clearTimeout(_prefSaveTimer);
    _prefSaveTimer = setTimeout(_tmFlushPrefs, 400);
}

function _tmFlushPrefs() {
    const payload = _prefPending;
    _prefPending = {};
    if (!Object.keys(payload).length) return;
    fetch('/api/settings/ui', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ..._csrfHeaders() },
        body: JSON.stringify({ ui_prefs: payload })
    }).catch(() => {});
}

function _tmAdoptLocalPrefs() {
    const server = window.TM_UI_PREFS || {};
    if (Object.keys(server).length) return;
    const adopted = {};
    Object.keys(TM_PREF_DEFAULTS).forEach(k => {
        const v = localStorage.getItem(k);
        if (v === null) return;
        const dflt = TM_PREF_DEFAULTS[k];
        adopted[k] = typeof dflt === 'boolean' ? v !== 'false' : v;
    });
    if (!Object.keys(adopted).length) return;
    window.TM_UI_PREFS = adopted;
    fetch('/api/settings/ui', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ..._csrfHeaders() },
        body: JSON.stringify({ ui_prefs: adopted })
    }).catch(() => {});
}

function _tmSyncViewIcons() {
    [['svcViewIcon', 'svcViewMode'], ['mwViewIcon', 'mwViewMode'], ['routeViewIcon', 'routeViewMode']]
        .forEach(([iconId, key]) => {
            const icon = document.getElementById(iconId);
            if (icon) icon.className = tmPref(key) === 'grid' ? 'ph-bold ph-list' : 'ph-bold ph-squares-four';
        });
}

function setTheme(theme) {
    localStorage.setItem('tm-theme', theme);
    applyTheme(theme);
    window.TM_DEFAULT_THEME = theme;
    syncThemeButtons(theme);
    fetch('/api/settings/theme', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ..._csrfHeaders() },
        body: JSON.stringify({ default_theme: theme })
    }).catch(() => {});
}

function cycleTheme() {
    const cur = localStorage.getItem('tm-theme') || window.TM_DEFAULT_THEME || 'dark';
    const next = THEMES[(THEMES.indexOf(cur) + 1) % THEMES.length];
    setTheme(next);
}

const _autofillAllowed = new Set(['pwCurrent', 'pwNew', 'pwConfirm', 'otpVerifyCode']);

function _guardAutofillField(el) {
    el.dataset.afGuarded = '1';
    if (el.type === 'hidden' || _autofillAllowed.has(el.id)) return;
    el.setAttribute('autocomplete', el.type === 'password' ? 'new-password' : 'off');
    el.setAttribute('data-lpignore', 'true');
    el.setAttribute('data-1p-ignore', 'true');
    el.setAttribute('data-form-type', 'other');
}

function _sweepAutofillGuard() {
    document.querySelectorAll('input:not([data-af-guarded]), textarea:not([data-af-guarded]), select:not([data-af-guarded])')
        .forEach(_guardAutofillField);
    document.querySelectorAll('form:not([data-af-guarded])').forEach(f => {
        f.dataset.afGuarded = '1';
        f.setAttribute('autocomplete', 'off');
    });
}

let _afSweepQueued = false;

function _queueAutofillSweep() {
    if (_afSweepQueued) return;
    _afSweepQueued = true;
    requestAnimationFrame(() => {
        _afSweepQueued = false;
        _sweepAutofillGuard();
    });
}

function _initAutofillGuard() {
    _sweepAutofillGuard();
    new MutationObserver(_queueAutofillSweep)
        .observe(document.documentElement, { childList: true, subtree: true });
}

let _pwaInstallPrompt = null;

function installPWA() {
    if (!_pwaInstallPrompt) return;
    _pwaInstallPrompt.prompt();
    _pwaInstallPrompt.userChoice.then(choice => {
        if (choice.outcome === 'accepted') {
            _pwaInstallPrompt = null;
            document.getElementById('pwaInstallBtn')?.classList.add('hidden');
        }
    });
}

function _emptyMountState({ icon, title, description, steps, note }) {
    const stepHtml = steps.map((step, i) => `
        <div class="text-left" style="max-width:480px;margin:0 auto">
            <p class="text-xs mb-2" style="color:var(--muted)">${steps.length > 1 ? `<span class="font-bold" style="color:var(--text)">Step ${i+1}.</span> ` : ''}${step.label}</p>
            <div class="relative rounded-lg overflow-hidden" style="background:var(--input-bg);border:1px solid var(--border)">
                <pre class="text-xs font-mono px-4 py-3 pr-16 leading-relaxed overflow-x-auto" style="color:var(--blue);white-space:pre">${step.code}</pre>
                <button onclick="_copyCode(this, ${JSON.stringify(step.code)})"
                    class="absolute top-2 right-2 flex items-center gap-1 text-xs px-2 py-1 rounded"
                    style="background:var(--btn-secondary-bg);border:1px solid var(--border);color:var(--muted);cursor:pointer;transition:all 0.15s"
                    onmouseover="this.style.borderColor='var(--blue)';this.style.color='var(--blue)'"
                    onmouseout="this.style.borderColor='var(--border)';this.style.color='var(--muted)'">
                    <i class="ph-bold ph-copy text-sm"></i> Copy
                </button>
            </div>
        </div>`).join('<div style="height:12px"></div>');

    const noteHtml = note ? `<p class="text-xs mt-4" style="color:var(--muted);opacity:0.7"><i class="ph-bold ph-info mr-1"></i>${note}</p>` : '';

    return `<div class="text-center py-12 px-4 rounded-xl" style="border:1px solid var(--border)">
        <i class="ph-light ${icon} text-5xl block mb-3 opacity-30" style="color:var(--muted)"></i>
        <p class="font-semibold mb-2" style="color:var(--text)">${title}</p>
        <p class="text-xs mb-6" style="color:var(--muted);max-width:400px;margin:0 auto 24px">${description}</p>
        <div class="space-y-3">${stepHtml}</div>
        ${noteHtml}
    </div>`;
}

function _copyCode(btn, text) {
    navigator.clipboard.writeText(text).then(() => {
        const orig = btn.innerHTML;
        btn.innerHTML = '<i class="ph-bold ph-check text-sm"></i> Copied';
        btn.style.color      = 'var(--green)';
        btn.style.borderColor = 'var(--green)';
        setTimeout(() => {
            btn.innerHTML      = orig;
            btn.style.color      = 'var(--muted)';
            btn.style.borderColor = 'var(--border)';
        }, 2000);
    });
}

async function _populateTlsOptionsSelect() {
    const sel = document.getElementById('tlsOptionsProfileSelect');
    if (!sel) return;
    const current = sel.value;
    try {
        const res = await fetch('/api/tls-options');
        const opts = await res.json();
        const inner = `<option value="">None (default)</option>` + opts.map(o => `<option value="${_esc(o.name)}">${_esc(o.name)}</option>`).join('');
        sel.innerHTML = inner;
        sel.value = current;
    } catch(e) {}
}

let _geoEnabled = false, _geoAvailable = false, _geoStatusLoaded = false;
let _geoCache = {};
let _geoMapSvg = null, _geoMapLoading = null;
let _geoTooltipEl = null;

async function loadGeoStatus(force) {
    if (_geoStatusLoaded && !force) return _geoEnabled && _geoAvailable;
    try {
        const r = await fetch('/api/geoip/status').then(r => r.json());
        _geoEnabled = !!r.enabled; _geoAvailable = !!r.available;
    } catch(_) { _geoEnabled = false; _geoAvailable = false; }
    _geoStatusLoaded = true;
    return _geoEnabled && _geoAvailable;
}

const GEO_LOOKUP_BATCH = 5000;
const _geoNames = {};

async function geoAggregate(ips) {
    if (!_geoEnabled || !_geoAvailable) return {};
    const uniq = [...new Set(ips.filter(Boolean))];
    const need = uniq.filter(ip => !(ip in _geoCache));
    const counts = {};
    for (let i = 0; i < need.length; i += GEO_LOOKUP_BATCH) {
        try {
            const r = await fetch('/api/geoip/lookup', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', ..._csrfHeaders() },
                body: JSON.stringify({ ips: need.slice(i, i + GEO_LOOKUP_BATCH), aggregate: true })
            }).then(r => r.json());
            if (r.available === false) { _geoAvailable = false; break; }
            Object.entries(r.codes || {}).forEach(([ip, cc]) => { _geoCache[ip] = { country_code: cc }; });
            Object.entries(r.counts || {}).forEach(([cc, v]) => {
                const e = counts[cc] || (counts[cc] = { count: 0, country: v.country });
                e.count += v.count;
                if (v.country) _geoNames[cc] = v.country;
            });
        } catch (_) { break; }
    }
    need.forEach(ip => { if (!(ip in _geoCache)) _geoCache[ip] = null; });
    return counts;
}

async function geoLookup(ips) {
    if (!_geoEnabled || !_geoAvailable) return {};
    const uniq = [...new Set(ips.filter(Boolean))];
    const need = uniq.filter(ip => !(ip in _geoCache));
    for (let i = 0; i < need.length; i += GEO_LOOKUP_BATCH) {
        const batch = need.slice(i, i + GEO_LOOKUP_BATCH);
        try {
            const r = await fetch('/api/geoip/lookup', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', ..._csrfHeaders() },
                body: JSON.stringify({ ips: batch })
            }).then(r => r.json());
            const res = r.results || {};
            batch.forEach(ip => { _geoCache[ip] = res[ip] || null; });
            if (r.available === false) { _geoAvailable = false; break; }
        } catch(_) { break; }
    }
    const out = {};
    uniq.forEach(ip => { if (_geoCache[ip]) out[ip] = _geoCache[ip]; });
    return out;
}

function _flagEmoji(cc) {
    if (!cc || cc.length !== 2) return '';
    try { return String.fromCodePoint(...[...cc.toUpperCase()].map(c => 0x1F1E6 + c.charCodeAt(0) - 65)); }
    catch(_) { return ''; }
}

function _geoCountryCounts(ips) {
    const counts = {};
    ips.forEach(ip => {
        const g = _geoCache[ip];
        if (g && g.country_code) {
            const cc = g.country_code;
            if (!counts[cc]) counts[cc] = { count: 0, name: g.country_name || _geoNames[cc] || cc };
            counts[cc].count++;
        }
    });
    return counts;
}

async function _ensureWorldMap() {
    if (_geoMapSvg) return _geoMapSvg;
    if (!_geoMapLoading) {
        _geoMapLoading = fetch('/static/world-map.svg').then(r => r.text()).then(t => { _geoMapSvg = t; return t; }).catch(() => { _geoMapLoading = null; return null; });
    }
    return _geoMapLoading;
}

function _geoTooltip() {
    if (!_geoTooltipEl) {
        _geoTooltipEl = document.createElement('div');
        _geoTooltipEl.className = 'tm-geo-tooltip';
        _geoTooltipEl.style.display = 'none';
        document.body.appendChild(_geoTooltipEl);
    }
    return _geoTooltipEl;
}

async function renderGeoMap(container, countryData, onCountryClick, activeCC) {
    if (!container) return;
    if (_geoTooltipEl) _geoTooltipEl.style.display = 'none';
    const svgText = await _ensureWorldMap();
    if (!svgText) { container.innerHTML = ''; return; }
    container.innerHTML = svgText;
    const svgEl = container.querySelector('svg');
    if (!svgEl) return;
    const counts = Object.values(countryData).map(d => d.count);
    const max = Math.max(1, ...counts);
    svgEl.querySelectorAll('path[data-cc]').forEach(p => {
        const cc = p.getAttribute('data-cc');
        const d  = countryData[cc];
        if (d && d.count > 0) {
            const t = Math.log(d.count + 1) / Math.log(max + 1);
            p.style.fill = 'var(--blue)';
            p.style.fillOpacity = (0.22 + 0.78 * t).toFixed(3);
            p.classList.add('tm-geo-active');
            if (activeCC && cc === activeCC) p.classList.add('tm-geo-selected');
        }
    });
    const tip = _geoTooltip();
    svgEl.addEventListener('mousemove', e => {
        const p = e.target.closest('path.tm-geo-active');
        if (!p) { tip.style.display = 'none'; return; }
        const cc = p.getAttribute('data-cc');
        const d  = countryData[cc] || {};
        tip.innerHTML = `${_flagEmoji(cc)} ${_esc(d.name || p.getAttribute('data-name') || cc)} <span style="color:var(--muted);margin-left:4px">${d.count || 0}</span>`;
        tip.style.display = 'block';
        tip.style.left = (e.clientX + 12) + 'px';
        tip.style.top  = (e.clientY + 12) + 'px';
    });
    svgEl.addEventListener('mouseleave', () => { tip.style.display = 'none'; });
    if (onCountryClick) {
        svgEl.addEventListener('click', e => {
            const p = e.target.closest('path.tm-geo-active');
            if (p) onCountryClick(p.getAttribute('data-cc'));
        });
    }
}

function _geoPanelHtml(panelId, countryData, activeCC, onClearAttr) {
    const entries = Object.entries(countryData).sort((a, b) => b[1].count - a[1].count);
    if (!entries.length) return '';
    const max = entries[0][1].count || 1;
    const total = entries.reduce((n, [, d]) => n + d.count, 0) || 1;
    const top = entries.slice(0, 8).map(([cc, d]) => {
        const sel = activeCC === cc;
        const pct = (d.count / total * 100).toFixed(1);
        return `<div class="lg-row${sel ? ' lg-row-on' : ''}" role="button" tabindex="0" onclick="${panelId}_click('${cc}')" title="${_esc(d.name)} - ${d.count.toLocaleString()} requests, ${pct}%">
            <span class="lg-id"><span class="lg-g">${_flagEmoji(cc)}</span><span class="lg-name">${_esc(d.name)}</span></span>
            <span class="lg-bad"></span>
            <span class="lg-n">${d.count.toLocaleString()}</span>
            <span class="lg-pct">${pct}%</span>
        </div>`;
    }).join('');
    const clear = activeCC
        ? `<button type="button" class="sig-explore" onclick="${onClearAttr}" title="Clear the country filter">${_flagEmoji(activeCC)} ${_esc((countryData[activeCC] || {}).name || activeCC)} <i class="ph-bold ph-x"></i></button>`
        : '';
    const label = entries.length === 1 ? 'country' : 'countries';
    const more = entries.length > 8 ? `<div class="lg-tail">+${(entries.length - 8).toLocaleString()} more ${entries.length - 8 === 1 ? 'country' : 'countries'}</div>` : '';
    return `<div class="sig-root">
        <section class="sig-ep lg-geo">
            <div class="sig-ep-head">
                <i class="ph-fill ph-globe-hemisphere-west sig-ep-headic"></i>
                <span class="sc-sec-label">Geography</span><span class="d-n">${entries.length}</span>
                <span class="sc-sec-rule"></span>
                ${clear || `<span class="sig-ep-tot">${entries.length.toLocaleString()} ${label}</span>`}
            </div>
            <div class="tm-geo-grid">
                <div id="${panelId}Map" class="tm-geo-map"></div>
                <div class="lg-geo-side">
                    <div class="lg-rows">${top}</div>
                    ${more}
                </div>
            </div>
        </section>
    </div>`;
}

function classifyIp(ip) {
    if (!ip) return 'unknown';
    ip = ip.trim();
    const v4 = ip.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/);
    if (v4) {
        const o = v4.slice(1).map(Number);
        if (o.some(n => n > 255)) return 'unknown';
        const [a, b] = o;
        if (a === 127) return 'loopback';
        if (a === 169 && b === 254) return 'link-local';
        if (a === 10) return 'private';
        if (a === 172 && b >= 16 && b <= 31) return 'private';
        if (a === 192 && b === 168) return 'private';
        if (a === 100 && b >= 64 && b <= 127) return 'cgnat';
        return 'public';
    }
    let v6 = ip.replace(/^\[|\]$/g, '').split('%')[0].toLowerCase();
    if (!v6.includes(':')) return 'unknown';
    if (v6 === '::1') return 'loopback';
    if (v6.startsWith('fe80')) return 'link-local';
    if (v6.startsWith('fc') || v6.startsWith('fd')) return 'private';
    if (v6.startsWith('::ffff:') && v6.slice(7).includes('.')) return classifyIp(v6.slice(7));
    return 'public';
}

const _IP_CLASS_META = {
    'public':     ['Public', 'ip-badge-public'],
    'private':    ['Private', 'ip-badge-private'],
    'cgnat':      ['CGNAT', 'ip-badge-cgnat'],
    'loopback':   ['Loopback', 'ip-badge-muted'],
    'link-local': ['Link-local', 'ip-badge-muted'],
    'unknown':    ['?', 'ip-badge-muted'],
};

function ipClassBadge(cls) {
    const [label, klass] = _IP_CLASS_META[cls] || _IP_CLASS_META['unknown'];
    return `<span class="ip-badge ${klass}">${label}</span>`;
}

function openIpDiagModal() {
    closeOtherPanels('ipDiagModal');
    const m = document.getElementById('ipDiagModal');
    if (!m) return;
    m.classList.add('open');
    document.getElementById('ipDiagBackdrop').classList.add('open');
    if (!setDetailDockOpen(true)) document.body.style.overflow = 'hidden';
    loadIpDiagnostic();
}

function closeIpDiagModal() {
    setDetailDockOpen(false);
    document.getElementById('ipDiagModal')?.classList.remove('open');
    document.getElementById('ipDiagBackdrop')?.classList.remove('open');
    document.body.style.overflow = '';
}

async function loadIpDiagnostic() {
    const body = document.getElementById('ipDiagBody');
    if (!body) return;
    body.innerHTML = `<div class="text-xs py-4 text-center" style="color:var(--muted)">Loading...</div>`;
    let d;
    try {
        d = await fetch('/api/diagnostics/client-ip').then(r => r.json());
    } catch (_) {
        body.innerHTML = `<div class="text-xs py-4 text-center" style="color:var(--red)">Failed to load diagnostic.</div>`;
        return;
    }
    const row = (label, ip, cls, hint) => `
        <div style="border-bottom:1px solid var(--border);padding:8px 0">
            <div class="flex items-center gap-2">
                <span class="text-xs" style="color:var(--muted);min-width:120px">${label}</span>
                <span class="text-xs font-mono truncate" style="color:var(--text);flex:1;min-width:0" title="${_esc(ip || '')}">${ip ? _esc(ip) : '<span style="color:var(--muted)">-</span>'}</span>
                ${ip ? ipClassBadge(cls || classifyIp(ip)) : ''}
            </div>
            ${hint ? `<div class="text-xs" style="color:var(--muted);margin-top:5px;padding-left:128px">${hint}</div>` : ''}
        </div>`;

    const hdrRows = Object.entries(d.headers || {}).map(([k, v]) => `
        <div class="flex items-center gap-2 py-1.5" style="border-bottom:1px solid var(--border)">
            <span class="text-xs font-mono" style="color:var(--muted);min-width:120px">${_esc(k)}</span>
            <span class="text-xs font-mono truncate" style="color:${v ? 'var(--text)' : 'var(--muted)'};flex:1;min-width:0" title="${_esc(v || '')}">${v ? _esc(v) : 'not set'}</span>
        </div>`).join('');

    const spoofable = d.effective_class === 'private' || d.effective_class === 'loopback' || d.effective_class === 'cgnat';

    body.innerHTML = `
        <div class="rounded-xl p-3 mb-3" style="background:var(--card);border:1px solid var(--border)">
            ${row('App sees (client)', d.effective_ip, d.effective_class)}
            ${row('Socket peer', d.socket_peer, d.socket_peer_class, 'The direct TCP connection - your reverse proxy, or the real client if none.')}
            <div class="flex items-center gap-2 py-2">
                <span class="text-xs" style="color:var(--muted);min-width:120px">Trusted hops</span>
                <span class="text-xs font-mono" style="color:var(--text)">${d.proxy_hops}</span>
            </div>
        </div>
        <div class="text-xs font-semibold uppercase tracking-wide mb-2" style="color:var(--muted)">Forwarding Headers</div>
        <div class="rounded-xl p-3 mb-3" style="background:var(--card);border:1px solid var(--border)">
            ${hdrRows}
        </div>
        ${spoofable ? `<div class="rounded-xl p-3 text-xs" style="background:rgba(210,153,34,0.1);border:1px solid rgba(210,153,34,0.3);color:var(--text)"><i class="ph-bold ph-warning" style="color:var(--yellow);margin-right:6px"></i>The client IP the app trusts is <strong>${_esc(d.effective_class)}</strong>. If clients should reach you from the public internet, a proxy in front is rewriting it - check that your trusted hops and the upstream <code class="font-mono">trustedIPs</code> are set correctly, or real client IPs will be lost to logs, CrowdSec and ipAllowList.</div>` : ''}`;
}

function _initMobileFilterBars() {
    if (window.innerWidth > 640) return;
    document.querySelectorAll('.filter-bar:not([data-fb-init])').forEach(bar => {
        bar.dataset.fbInit = '1';
        const searchBtn = document.createElement('button');
        searchBtn.className = 'fb-search-icon';
        searchBtn.title = 'Search';
        searchBtn.innerHTML = '<i class="ph-bold ph-magnifying-glass" style="font-size:13px"></i>';
        searchBtn.onclick = () => {
            bar.classList.add('fb-open');
            bar.querySelector('input[type=text],input[type=search]')?.focus();
        };
        const cancelBtn = document.createElement('button');
        cancelBtn.className = 'fb-cancel-icon';
        cancelBtn.title = 'Cancel';
        cancelBtn.innerHTML = '<i class="ph-bold ph-arrow-left" style="font-size:13px"></i>';
        cancelBtn.onclick = () => {
            bar.classList.remove('fb-open');
            const inp = bar.querySelector('input[type=text],input[type=search]');
            if (inp) { inp.value = ''; inp.dispatchEvent(new Event('input')); }
        };
        bar.insertBefore(cancelBtn, bar.firstChild);
        bar.insertBefore(searchBtn, bar.firstChild);
        if (bar.querySelector('.fb-secondary')) {
            const filterBtn = document.createElement('button');
            filterBtn.className = 'fb-filter-icon';
            filterBtn.title = 'More filters';
            filterBtn.innerHTML = '<i class="ph-bold ph-sliders" style="font-size:13px"></i>';
            filterBtn.onclick = () => {
                const open = bar.classList.toggle('fb-filter-open');
                filterBtn.classList.toggle('active', open);
            };
            bar.appendChild(filterBtn);
        }
    });
}

let _notifData       = [];
let _notifReadUntil  = parseInt(localStorage.getItem('notifReadUntil') || '0', 10);
let _notifPanelOpen  = false;

const _NOTIF_ICONS = {
    success: 'ph-check-circle',
    warning: 'ph-warning',
    error:   'ph-x-circle',
    info:    'ph-info',
};

function _notifRelTime(ts) {
    const diff = Math.floor((Date.now() - new Date(ts).getTime()) / 1000);
    if (diff < 60)  return 'just now';
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
}

async function fetchNotifications() {
    try {
        const res  = await fetch('/api/notifications');
        if (!res.ok) return;
        _notifData = await res.json();
        try {
            const st = await (await fetch('/api/notifications/state')).json();
            if (typeof st.read_until === 'number') {
                _notifReadUntil = st.read_until;
                localStorage.setItem('notifReadUntil', _notifReadUntil);
            }
        } catch (e) {}
        _renderNotifPanel();
        _syncBrowserNotifs();
    } catch(e) {}
}

const NOTIF_CATEGORY_LABELS = {
    config: 'Config', backup: 'Backups', security: 'Security', traefik: 'Traefik',
    certs: 'Certificates', crowdsec: 'CrowdSec', agent: 'Agents', update: 'Updates',
};

const _tabIcon = id => (TAB_DEFS.find(t => t.id === id) || {}).icon;

const NOTIF_CATEGORY_ICONS = {
    config:   _tabIcon('static'),
    backup:   'ph-archive-box',
    security: 'ph-lock-simple',
    traefik:  'ph-signpost',
    certs:    _tabIcon('certs'),
    crowdsec: _tabIcon('crowdsec'),
    agent:    'ph-robot',
    update:   'ph-arrow-circle-up',
};

let _notifCatFilter = '';

function setNotifCategory(cat, ev) {
    if (ev) ev.stopPropagation();
    _notifCatFilter = _notifCatFilter === cat ? '' : cat;
    _renderNotifPanel();
}

function _renderNotifFilters() {
    const row = document.getElementById('notifFilters');
    if (!row) return;
    const order = Object.keys(NOTIF_CATEGORY_LABELS);
    const present = [];
    for (const n of _notifData) {
        const c = n.category || 'config';
        if (!present.includes(c)) present.push(c);
    }
    if (present.length < 2) {
        row.style.display = 'none'; row.innerHTML = ''; _notifCatFilter = '';
        return;
    }
    if (_notifCatFilter && !present.includes(_notifCatFilter)) _notifCatFilter = '';
    present.sort((a, b) => order.indexOf(a) - order.indexOf(b));
    row.style.display = '';
    const chip = (cat, label, icon, count) => {
        const on = _notifCatFilter === cat;
        return `<button class="notif-cat-chip${on ? ' active' : ''}" onclick="setNotifCategory(${_jsArg(cat)}, event)"`
             + ` title="${_esc(label)} (${count})" aria-label="${_esc(label)}"><i class="ph-bold ${icon}"></i></button>`;
    };
    row.innerHTML = chip('', 'All', 'ph-stack', _notifData.length)
        + present.map(c => chip(c, NOTIF_CATEGORY_LABELS[c] || c,
                                NOTIF_CATEGORY_ICONS[c] || 'ph-circle',
                                _notifData.filter(x => (x.category || 'config') === c).length)).join('');
}

function _renderNotifPanel() {
    const list  = document.getElementById('notifList');
    const badge = document.getElementById('notifBadge');
    const markReadBtn = document.getElementById('notifMarkRead');
    if (!list || !badge) return;

    const shown = _notifCatFilter
        ? _notifData.filter(n => (n.category || 'config') === _notifCatFilter)
        : _notifData;
    _renderNotifFilters();

    const unreadCount = _notifData.filter(n => (n.id || 0) > _notifReadUntil).length;
    const hasUnread = unreadCount > 0;

    badge.classList.toggle('hidden', !hasUnread);

    if (markReadBtn) markReadBtn.style.display = hasUnread ? '' : 'none';

    const clearAllBtn = document.getElementById('notifClearAll');
    if (clearAllBtn) clearAllBtn.style.display = _notifData.length ? '' : 'none';

    if (!_notifData.length) {
        list.innerHTML = `<div class="notif-empty"><i class="ph-light ph-bell-slash" style="font-size:32px;opacity:0.3;display:block;margin-bottom:8px"></i>No notifications yet</div>`;
        return;
    }

    if (!shown.length) {
        const label = NOTIF_CATEGORY_LABELS[_notifCatFilter] || _notifCatFilter;
        list.innerHTML = `<div class="notif-empty"><i class="ph-light ph-funnel" style="font-size:32px;opacity:0.3;display:block;margin-bottom:8px"></i>Nothing in ${_esc(label)}</div>`;
        return;
    }

    list.innerHTML = shown.map((n, i) => {
        const isUnread = (n.id || 0) > _notifReadUntil;
        const type  = n.type || 'info';
        const icon  = _NOTIF_ICONS[type] || 'ph-info';
        return `<div class="notif-item${isUnread ? ' unread' : ''}">
            <div class="notif-icon ${type}"><i class="ph-bold ${icon}"></i></div>
            <div class="notif-body">
                <div class="notif-msg">${_esc(n.msg)}</div>
                <div class="notif-ts">${_notifRelTime(n.ts)}<span class="notif-cat">${_esc(NOTIF_CATEGORY_LABELS[n.category] || n.category || 'Config')}</span></div>
            </div>
            <button class="notif-delete-btn" onclick="deleteNotification(${_jsArg(n.ts)}, ${Number(n.id) || 0})" title="Dismiss"><i class="ph-bold ph-x"></i></button>
        </div>`;
    }).join('');
}

function toggleNotifPanel() {
    const panel = document.getElementById('notifPanel');
    const btn   = document.getElementById('notifBellBtn');
    if (!panel) return;
    _notifPanelOpen = !_notifPanelOpen;
    panel.classList.toggle('open', _notifPanelOpen);
    const color = _notifPanelOpen ? 'var(--blue)' : '';
    if (btn)  btn.style.color  = color;
    if (_notifPanelOpen) {
        if (btn) {
            const r = btn.getBoundingClientRect();
            const panelW = Math.min(360, window.innerWidth - 16);
            let left = r.right - panelW;
            if (left < 8) left = 8;
            panel.style.position = 'fixed';
            panel.style.top  = (r.bottom + 8) + 'px';
            panel.style.left = left + 'px';
            panel.style.right = 'auto';
            panel.style.width = panelW + 'px';
        }
    } else {
        markNotifsRead();
    }
}

async function markNotifsRead() {
    _notifReadUntil = Math.max(_notifReadUntil, ..._notifData.map(n => n.id || 0), 0);
    localStorage.setItem('notifReadUntil', _notifReadUntil);
    _renderNotifPanel();
    try {
        await fetch('/api/notifications/read', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ..._csrfHeaders() },
            body: JSON.stringify({ all: true }),
        });
    } catch (e) {}
}

async function deleteNotification(ts, id) {
    try {
        await fetch('/api/notifications/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ..._csrfHeaders() },
            body: JSON.stringify(id ? { id } : { ts })
        });
        await fetchNotifications();
        _renderNotifPanel();
    } catch(e) {}
}

async function clearAllNotifications() {
    try {
        await fetch('/api/notifications/clear', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ..._csrfHeaders() },
            body: JSON.stringify({})
        });
        await fetchNotifications();
    } catch(e) {}
}

const BROWSER_NOTIF_KEY     = 'tmBrowserNotifs';
const BROWSER_NOTIF_SEV_KEY = 'tmBrowserNotifsSeverity';
const BROWSER_NOTIF_SEVERITIES = ['all', 'warning'];
const BROWSER_NOTIF_BURST = 3;

const _BROWSER_NOTIF_TITLES = {
    success: 'Traefik Manager',
    info:    'Traefik Manager',
    warning: 'Traefik Manager: warning',
    error:   'Traefik Manager: error',
};

const _BROWSER_NOTIF_RANK = { info: 0, success: 0, warning: 1, error: 2 };

let _notifSeenTs = null;

function browserNotifSupport() {
    if (window.isSecureContext === false) return { ok: false, reason: 'insecure' };
    if (typeof Notification === 'undefined') return { ok: false, reason: 'unsupported' };
    return { ok: true, reason: '' };
}

function browserNotifsEnabled() {
    return localStorage.getItem(BROWSER_NOTIF_KEY) === '1';
}

function browserNotifsActive() {
    return browserNotifsEnabled() && browserNotifSupport().ok && Notification.permission === 'granted';
}

function browserNotifSeverity() {
    const v = localStorage.getItem(BROWSER_NOTIF_SEV_KEY);
    return BROWSER_NOTIF_SEVERITIES.includes(v) ? v : 'all';
}

function setBrowserNotifSeverity(sev) {
    if (!BROWSER_NOTIF_SEVERITIES.includes(sev)) return;
    localStorage.setItem(BROWSER_NOTIF_SEV_KEY, sev);
}

function _requestNotifPermission() {
    return new Promise(resolve => {
        let settled = false;
        const finish = perm => {
            if (settled) return;
            settled = true;
            resolve(perm || Notification.permission);
        };
        try {
            const ret = Notification.requestPermission(finish);
            if (ret && typeof ret.then === 'function') ret.then(finish).catch(() => finish(Notification.permission));
        } catch(e) {
            finish(Notification.permission);
        }
    });
}

async function enableBrowserNotifs() {
    const support = browserNotifSupport();
    if (!support.ok) return support;
    let perm = Notification.permission;
    if (perm === 'default') perm = await _requestNotifPermission();
    if (perm !== 'granted') {
        localStorage.setItem(BROWSER_NOTIF_KEY, '0');
        return { ok: false, reason: 'denied' };
    }
    localStorage.setItem(BROWSER_NOTIF_KEY, '1');
    _notifSeenTs = new Set(_notifData.map(n => n.ts));
    return { ok: true, reason: '' };
}

function disableBrowserNotifs() {
    localStorage.setItem(BROWSER_NOTIF_KEY, '0');
}

function _browserNotifWanted(type) {
    if (browserNotifSeverity() !== 'warning') return true;
    return (_BROWSER_NOTIF_RANK[type] || 0) >= 1;
}

function _showBrowserNotif(type, body, tag) {
    try {
        const notif = new Notification(_BROWSER_NOTIF_TITLES[type] || _BROWSER_NOTIF_TITLES.info, {
            body: body,
            tag:  'tm-' + tag,
            icon: tmUrl('/static/icons/icon-192x192.png'),
        });
        notif.onclick = () => {
            window.focus();
            try { notif.close(); } catch(e) {}
            if (!_notifPanelOpen) toggleNotifPanel();
        };
    } catch(e) {}
}

function _syncBrowserNotifs() {
    const seen = _notifSeenTs;
    _notifSeenTs = new Set(_notifData.map(n => n.ts));
    if (!browserNotifsEnabled()) return;
    if (!browserNotifSupport().ok) return;
    if (Notification.permission !== 'granted') {
        disableBrowserNotifs();
        if (typeof renderBrowserNotifs === 'function') renderBrowserNotifs();
        showToast('Desktop notifications are blocked by this browser, so they have been turned off', 'error', false);
        return;
    }
    if (seen === null) return;
    const fresh = _notifData.filter(n => !seen.has(n.ts) && _browserNotifWanted(n.type || 'info'));
    if (!fresh.length) return;
    if (fresh.length > BROWSER_NOTIF_BURST) {
        _showBrowserNotif('info', fresh.length + ' new notifications', 'burst');
        return;
    }
    fresh.slice().reverse().forEach(n => _showBrowserNotif(n.type || 'info', n.msg || '', n.ts));
}

let _navReflowPending = false;

const NAV_PHONE_BELOW = 768;

function _navItems(bar, menu) {
    return [...bar.children, ...menu.children]
        .filter(el => el.dataset && el.dataset.navprio)
        .map(el => ({ el, prio: parseInt(el.dataset.navprio, 10) }))
        .sort((a, b) => a.prio - b.prio);
}

function _navMovable(el) {
    if (el.id !== 'serverSwitcherWrap') return true;
    return window.innerWidth < NAV_PHONE_BELOW;
}

function _navRestore(bar, menu, wrap) {
    [...bar.children, ...menu.children]
        .filter(el => el.dataset && el.dataset.navorder !== undefined)
        .sort((a, b) => a.dataset.navorder - b.dataset.navorder)
        .forEach(el => bar.insertBefore(el, wrap));
}

function _navVisible(el) {
    if (el.classList.contains('hidden') || el.style.display === 'none') return false;
    return getComputedStyle(el).display !== 'none';
}

const NAV_CAP_BELOW = 1440;

const NAV_PINNED = ['navAddRouteBtn', 'navAddMwBtn', 'themeToggleBtn'];

const NAV_NARROW_MAX = 5;

function reflowNav() {
    const bar = document.getElementById('navActions');
    const wrap = document.getElementById('navMoreWrap');
    const menu = document.getElementById('navMoreMenu');
    if (!bar || !wrap || !menu || getComputedStyle(bar).display === 'none') return;

    const items = _navItems(bar, menu);
    const phone  = window.innerWidth < NAV_PHONE_BELOW;
    const narrow = !phone && window.innerWidth < NAV_CAP_BELOW;

    _navRestore(bar, menu, wrap);

    if (phone) {
        wrap.style.display = '';
        for (const { el } of items) {
            if (_navMovable(el)) menu.appendChild(el);
        }
    } else if (narrow) {
        wrap.style.display = '';
        const pinnedCount = items.filter(({ el }) => NAV_PINNED.includes(el.id) && _navVisible(el)).length;
        let slots = Math.max(0, NAV_NARROW_MAX - 1 - pinnedCount);
        for (const { el } of [...items].reverse()) {
            if (NAV_PINNED.includes(el.id)) continue;
            if (!_navMovable(el)) continue;
            if (_navVisible(el) && slots > 0) { slots--; continue; }
            menu.appendChild(el);
        }
    } else {
        wrap.style.display = 'none';
        const room = () => bar.parentElement.clientWidth - bar.parentElement.firstElementChild.offsetWidth - 24;
        if (bar.offsetWidth > room()) wrap.style.display = '';

        for (const { el } of items) {
            if (bar.offsetWidth <= room()) break;
            if (!_navVisible(el) || !_navMovable(el)) continue;
            menu.appendChild(el);
        }
    }

    const moved = [...menu.children].filter(_navVisible).length;
    wrap.style.display = moved ? '' : 'none';
    if (!moved) closeNavMore();
    _navReflowPending = false;
}

function scheduleNavReflow() {
    if (_navReflowPending) return;
    _navReflowPending = true;
    requestAnimationFrame(reflowNav);
}

function toggleNavMore() {
    document.getElementById('navMoreMenu')?.classList.toggle('open');
}

function closeNavMore() {
    document.getElementById('navMoreMenu')?.classList.remove('open');
}

function initNavOverflow() {
    const bar = document.getElementById('navActions');
    if (!bar) return;
    [...bar.children].forEach((el, i) => { el.dataset.navorder = i; });
    scheduleNavReflow();
    window.addEventListener('resize', scheduleNavReflow);
    document.addEventListener('click', e => {
        if (!e.target.closest('#navMoreWrap')) closeNavMore();
    });
    const menu = document.getElementById('navMoreMenu');
    new MutationObserver(muts => {
        if (muts.every(m => m.target === menu)) return;
        scheduleNavReflow();
    }).observe(document.getElementById('navActions').parentElement, {
        attributes: true, attributeFilter: ['class', 'style'], subtree: true,
    });
}

function toggleSideNavDrawer() {
    const open = document.documentElement.classList.toggle('tm-drawer-open');
    document.body.style.overflow = open ? 'hidden' : '';
}

function closeSideNavDrawer() {
    document.documentElement.classList.remove('tm-drawer-open');
    document.body.style.overflow = '';
}

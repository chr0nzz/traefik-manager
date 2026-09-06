let _allServices = [];
let _ownedChildNames = new Set();
let _ownedServiceNames = new Set();
let _svcFilter = 'all';
let _protoLiveFilter = 'all';
let _providerFilter = 'all';
let _svcViewMode = tmPref('svcViewMode');

function toggleSvcView() {
    _svcViewMode = _svcViewMode === 'grid' ? 'list' : 'grid';
    tmSetPref('svcViewMode', _svcViewMode);
    const icon = document.getElementById('svcViewIcon');
    if (icon) icon.className = _svcViewMode === 'grid' ? 'ph-bold ph-list' : 'ph-bold ph-squares-four';
    renderServicesTable();
}

function _setLiveDdActive(menuId, val) {
    document.querySelectorAll('#' + menuId + ' .live-dd-item').forEach(el => {
        const oc = el.getAttribute('onclick') || '';
        el.classList.toggle('active', oc.includes("'" + val + "'"));
    });
}

function pickLiveStatus(val, label, silent) {
    _svcFilter = val;
    document.getElementById('dd-status-label').textContent = label;
    document.getElementById('dd-status-btn').classList.toggle('active', val !== 'all');
    _setLiveDdActive('dd-status-menu', val);
    if (!silent) toggleLiveDd('dd-status');
    renderServicesTable();
}

function pickLiveProto(val, label) {
    _protoLiveFilter = val;
    document.getElementById('dd-proto-label').textContent = label;
    document.getElementById('dd-proto-btn').classList.toggle('active', val !== 'all');
    _setLiveDdActive('dd-proto-menu', val);
    toggleLiveDd('dd-proto');
    renderServicesTable();
}

function pickLiveProvider(val, label, silent) {
    _providerFilter = val;
    document.getElementById('dd-provider-label').textContent = label;
    document.getElementById('dd-provider-btn').classList.toggle('active', val !== 'all');
    _setLiveDdActive('dd-provider-menu', val);
    if (!silent) toggleLiveDd('dd-provider');
    renderServicesTable();
}

function filterLiveProto(p) { pickLiveProto(p, p === 'all' ? 'All Protocols' : p); }
function filterLiveProvider(v) { pickLiveProvider(v, v === 'all' ? 'All Providers' : v); }

function clearLiveFilters() {
    pickLiveStatus('all', 'All Status');
    pickLiveProto('all', 'All Protocols');
    pickLiveProvider('all', 'All Providers');
    document.querySelectorAll('.live-dd-menu.open').forEach(m => m.classList.remove('open'));
    document.querySelectorAll('.live-dd-btn-inner.open').forEach(b => b.classList.remove('open'));
    const s = document.getElementById('svcSearch');
    if (s) { s.value = ''; }
    renderServicesTable();
}

async function refreshLiveView() {
    const container = document.getElementById('liveContent');
    container.innerHTML = `<div class="text-center py-16" style="color:var(--muted)"><i class="ph-light ph-spinner-gap text-4xl block mb-3 animate-spin opacity-40"></i><p>Loading services...</p></div>`;

    try {
        const r = await fetch(_svcApiPath('/api/traefik/services'), { headers: _csrfHeaders() });
        if (!r.ok) {
            const why = await _errText(r, 'Could not load services');
            container.innerHTML = `<div class="text-center py-16 rounded-xl" style="color:var(--muted);border:1px solid var(--border)"><i class="ph-light ph-cloud-slash text-5xl block mb-3 opacity-30"></i><p class="font-medium">Could not load services</p><p class="text-sm mt-2 px-4" style="color:var(--text-secondary);word-break:break-word">${_esc(why)}</p></div>`;
            return;
        }
        const res = await r.json();
        if (res.error) {
            container.innerHTML = `<div class="text-center py-16 rounded-xl" style="color:var(--muted);border:1px solid var(--border)"><i class="ph-light ph-cloud-slash text-5xl block mb-3 opacity-30"></i><p class="font-medium">Traefik API not reachable</p><p class="text-sm mt-2 font-mono px-4" style="color:var(--text-secondary);word-break:break-all">${_esc(res.error)}</p></div>`;
            return;
        }
        const http = (res.http || []).map(s => ({ ...s, _proto: 'HTTP' }));
        const tcp  = (res.tcp  || []).map(s => ({ ...s, _proto: 'TCP' }));
        const udp  = (res.udp  || []).map(s => ({ ...s, _proto: 'UDP' }));
        _ownedChildNames = new Set(res.ownedChildren || []);
        _ownedServiceNames = new Set(res.ownedServices || []);
        _allServices = [...http, ...tcp, ...udp].sort((a,b) => (a.name||'').localeCompare(b.name||''));

        if (_allServices.length === 0) {
            container.innerHTML = `<div class="text-center py-16 rounded-xl" style="color:var(--muted);border:1px solid var(--border)"><i class="ph-light ph-cloud-slash text-5xl block mb-3 opacity-30"></i><p class="font-medium">Traefik API not reachable</p><p class="text-sm mt-1">Set <code class="font-mono">TRAEFIK_API_URL</code> and enable <code class="font-mono">api: {}</code> in Traefik static config</p></div>`;
            return;
        }

        renderServicesTable();
    } catch(e) {
        container.innerHTML = `<div class="text-center py-16 rounded-xl" style="color:var(--muted);border:1px solid var(--border)"><i class="ph-light ph-cloud-slash text-5xl block mb-3 opacity-30"></i><p class="font-medium">Could not load services</p><p class="text-sm mt-2 px-4" style="color:var(--text-secondary);word-break:break-word">${_esc(_netErrText(e, 'Traefik API not reachable'))}</p></div>`;
    }
}

function filterServices(f) {
    if (f && f !== _svcFilter) {
        const labels = { all: 'All Status', success: 'Success', warning: 'Warnings', error: 'Errors' };
        pickLiveStatus(f, labels[f] || f);
        return;
    }
    renderServicesTable();
}

function renderServicesTable() {
    const search = (document.getElementById('svcSearch')?.value || '').toLowerCase();
    const anyDownOf = s => {
        const m = s.serverStatus;
        if (!m || typeof m !== 'object') return false;
        return Object.keys(m).some(k => String(m[k]).toUpperCase() !== 'UP');
    };
    const statusOf = s => {
        const st = (s.status || '').toLowerCase();
        if (st === 'disabled' || st === 'error') return 'error';
        if (st === 'enabled') return anyDownOf(s) ? 'warning' : 'success';
        return 'warning';
    };
    const providerOf = s => {
        const name = s.name || '';
        const parts = name.split('@');
        return parts.length > 1 ? parts[parts.length-1] : 'file';
    };

    const ownedIdx = _svcOwnedChildIndex(_allServices, _ownedChildNames);
    const listed = _allServices.filter((s, i) => !ownedIdx.has(i));

    const uniqueProtos = [...new Set(listed.map(s => s._proto).filter(Boolean))].sort();
    const uniqueProviders = [...new Set(listed.map(providerOf))].sort();
    const protoMenu = document.getElementById('dd-proto-menu');
    if (protoMenu) {
        protoMenu.innerHTML = ['all', ...uniqueProtos].map(p => {
            const label = p === 'all' ? 'All Protocols' : p;
            return `<button class="live-dd-item${_protoLiveFilter === p ? ' active' : ''}" onclick="pickLiveProto('${p}','${label}')">${label}</button>`;
        }).join('');
    }
    const provMenu = document.getElementById('dd-provider-menu');
    if (provMenu) {
        provMenu.innerHTML = ['all', ...uniqueProviders].map(v => {
            const label = v === 'all' ? 'All Providers' : v;
            return `<button class="live-dd-item${_providerFilter === v ? ' active' : ''}" onclick="pickLiveProvider('${v}','${label}')">${label}</button>`;
        }).join('');
    }

    let items = [];
    for (let i = 0; i < _allServices.length; i++) {
        const s = _allServices[i];
        if (ownedIdx.has(i) && !search) continue;
        if (_svcFilter !== 'all' && statusOf(s) !== _svcFilter) continue;
        if (_protoLiveFilter !== 'all' && s._proto !== _protoLiveFilter) continue;
        if (_providerFilter !== 'all' && providerOf(s) !== _providerFilter) continue;
        if (search && !(s.name||'').toLowerCase().includes(search)) continue;
        items.push({s, globalIdx: i});
    }

    const typeOf = s => {
        if (s.loadBalancer) return 'loadbalancer';
        if (s.mirroring)    return 'mirroring';
        if (s.failover)     return 'failover';
        if (s.weighted)     return 'weighted';
        if (s.highestRandomWeight) return 'highestrandomweight';
        return null;
    };

    const cards = items.map(({s, globalIdx}) => {
        const proto     = s._proto || 'HTTP';
        const name      = (s.name || '').split('@')[0];
        const provider  = providerOf(s);
        const type      = typeOf(s);
        const st        = statusOf(s);
        const ownerName = ownedIdx.has(globalIdx) ? _svcOwnerName(_allServices, s) : '';

        const stColor = st === 'success' ? 'var(--green)' : st === 'error' ? 'var(--red)' : 'var(--yellow)';
        const stLabel = st === 'success' ? 'Success'      : st === 'error' ? 'Error'      : 'Warning';

        const serverStatus  = s.serverStatus || {};
        const serverEntries = Object.entries(serverStatus);
        const activeCount   = serverEntries.filter(([,v]) => (v||'').toLowerCase() === 'up').length;
        const serverSummary = serverEntries.length > 0 ? `${activeCount}/${serverEntries.length} active` : null;
        const srvColor      = serverEntries.length > 0 && activeCount === serverEntries.length ? 'var(--green)' : 'var(--orange)';

        const usedBy = s.usedBy || [];
        const usedByHtml = usedBy.length > 0 ? `
            <div class="svc-card-usedby">
                ${usedBy.slice(0, 3).map(r => {
                    const rName = r.includes('@') ? r.split('@')[0] : r;
                    return `<span class="svc-used-chip"><i class="ph-bold ph-git-branch" style="font-size:9px"></i>${_esc(rName)}</span>`;
                }).join('')}
                ${usedBy.length > 3 ? `<span class="svc-used-chip">+${usedBy.length - 3}</span>` : ''}
            </div>` : '';

        if (_svcViewMode !== 'list') {
            const anyDown = serverEntries.length > 0 && activeCount < serverEntries.length;
            const dotCls = st === 'error' || (anyDown && activeCount === 0) ? 'status-offline'
                         : anyDown || st !== 'success' ? 'status-checking' : 'status-online';
            const dotTitle = anyDown ? `${activeCount} of ${serverEntries.length} servers up` : stLabel;
            const lb = s.loadBalancer || {};
            const composite = (s.weighted?.services || []).map(x => `${x.name}${x.weight != null ? ` (${x.weight})` : ''}`)
                .concat((s.highestRandomWeight?.services || []).map(x => `${x.name}${x.weight != null ? ` (${x.weight})` : ''}`))
                .concat(s.mirroring?.service ? [s.mirroring.service] : [])
                .concat((s.mirroring?.mirrors || []).map(m => `${m.name} mirror (${m.percent || 0}%)`))
                .concat(s.failover?.service ? [s.failover.service] : [])
                .concat(s.failover?.fallback ? [`${s.failover.fallback} fallback`] : []);
            const servers = (lb.servers || []).map(x => x.url || x.address).filter(Boolean)
                .concat(composite);
            const rows = servers.slice(0, 2).map(u =>
                `<div class="tm-val tm-val-target"><i class="ph-bold ph-arrow-elbow-down-right"></i><span class="tm-v">${_esc(u)}</span>${_tmCopy(u)}</div>`).join('')
                + (servers.length > 2 ? `<div class="tm-val"><i class="ph-bold ph-dot" style="opacity:0"></i><span class="tm-more" title="${_esc(servers.join(', '))}">+${servers.length - 2} more</span></div>` : '');
            const meta = [
                composite.length ? '' : (servers.length ? `${servers.length} server${servers.length > 1 ? 's' : ''}` : ''),
                serverSummary ? `<span style="color:${srvColor}">${serverSummary}</span>` : '',
                lb.sticky ? 'sticky' : '',
                (lb.healthCheck ? 'health check' : ''),
            ].filter(Boolean).join(' \u00b7 ');
            const usedTxt = usedBy.length ? `used by ${usedBy.length} route${usedBy.length > 1 ? 's' : ''}` : '';
            return `<div class="tm-card" data-health="${st === 'error' ? 'down' : 'up'}" style="--tm-accent:${stColor}" onclick="openSvcDetail(${globalIdx})">
                <div class="tm-head">
                    <span class="tm-ic tm-ic-tile"><i class="ph-bold ${composite.length ? 'ph-share-network' : 'ph-hard-drives'}"></i><span class="status-dot ${dotCls}" title="${_esc(dotTitle)}"></span></span>
                    <div class="tm-head-txt">
                        <div class="tm-title">${proto !== 'HTTP' ? `<span class="tm-proto tm-proto-${proto.toLowerCase()}">${proto}</span>` : ''}<span class="tm-name">${_esc(name)}</span></div>
                        <div class="tm-sub">${_esc(type || 'service')} \u00b7 ${_esc(provider)}${ownerName ? ' \u00b7 backend of ' + _esc(ownerName) : ''}</div>
                    </div>
                    <span class="tm-rail tm-rail-sm" onclick="event.stopPropagation()"><button type="button" class="tm-btn" title="Details" onclick="event.stopPropagation();openSvcDetail(${globalIdx})"><i class="ph-bold ph-info"></i></button>${_svcEditable(s) ? `<button type="button" class="tm-btn" title="Edit" onclick="event.stopPropagation();openServiceModal(_allServices[${globalIdx}])"><i class="ph-bold ph-pencil-simple"></i></button>` : ''}</span>
                </div>
                ${rows ? `<div class="tm-vals">${rows}</div>` : ''}
                <div class="tm-foot"><span class="tm-meta">${meta}</span>${usedTxt ? `<span class="tm-cf">${_esc(usedTxt)}</span>` : ''}</div>
            </div>`;
        }
        return `
        <div class="card svc-card" onclick="openSvcDetail(${globalIdx})">
            <div class="svc-card-header">
                <div class="flex items-center gap-1.5">
                    <span class="badge badge-${proto.toLowerCase()}" style="font-size:9px">${proto}</span>
                    ${type ? `<span class="svc-type-badge">${type}</span>` : ''}
                </div>
                <span class="svc-status-chip" style="color:${stColor};background:color-mix(in srgb,${stColor} 14%,transparent)">
                    <span class="svc-status-dot" style="background:${stColor}"></span>${stLabel}
                </span>
            </div>
            <div class="svc-card-name">${_esc(name)}${ownerName ? `<span class="svc-type-badge" style="margin-left:6px">backend of ${_esc(ownerName)}</span>` : ''}</div>
            <div class="svc-card-meta">
                <span class="svc-meta-chip"><i class="ph-bold ph-database" style="font-size:10px"></i>${_esc(provider)}</span>
                ${serverSummary ? `<span class="svc-meta-chip" style="color:${srvColor};background:color-mix(in srgb,${srvColor} 10%,transparent);border-color:color-mix(in srgb,${srvColor} 35%,transparent)"><i class="ph-bold ph-hard-drives" style="font-size:10px"></i>${serverSummary}</span>` : ''}
            </div>
            ${usedByHtml}
        </div>`;
    }).join('');

    const empty = items.length === 0
        ? `<div class="text-center py-12" style="color:var(--muted)">No services match filter</div>`
        : '';

    if (_svcViewMode === 'list') {
        const rows = items.map(({s, globalIdx}) => {
            const proto     = s._proto || 'HTTP';
            const name      = (s.name || '').split('@')[0];
            const provider  = providerOf(s);
            const type      = typeOf(s);
            const st        = statusOf(s);
            const stColor   = st === 'success' ? 'var(--green)' : st === 'error' ? 'var(--red)' : 'var(--yellow)';
            const serverStatus  = s.serverStatus || {};
            const serverEntries = Object.entries(serverStatus);
            const activeCount   = serverEntries.filter(([,v]) => (v||'').toLowerCase() === 'up').length;
            const serverSummary = serverEntries.length > 0 ? `${activeCount}/${serverEntries.length}` : null;
            const srvColor      = serverEntries.length > 0 && activeCount === serverEntries.length ? 'var(--green)' : 'var(--orange)';
            const usedBy        = s.usedBy || [];
            const ownerName     = ownedIdx.has(globalIdx) ? _svcOwnerName(_allServices, s) : '';
            const lbServers     = (s.loadBalancer?.servers || []);
            const serverUrls    = lbServers.length > 0
                ? lbServers
                : serverEntries.map(([url]) => ({ url }));
            const serverUrlHtml = serverUrls.length > 0
                ? `<div style="display:flex;flex-direction:column;gap:2px">${serverUrls.map(sv => {
                    const url = sv.url || sv.address || '';
                    const isUp = (serverStatus[url] || '').toLowerCase() === 'up';
                    const isDown = serverStatus[url] && !isUp;
                    const color = isDown ? 'var(--red)' : 'var(--green)';
                    return `<span class="text-xs font-mono truncate" style="color:${color}" title="${_esc(url)}">${_esc(url)}</span>`;
                }).join('')}</div>`
                : '<span style="color:var(--muted);font-size:11px">-</span>';
            return `<div class="svc-list-row svc-list-grid" onclick="openSvcDetail(${globalIdx})">
                <div class="svc-list-col-status"><span class="svc-status-dot" style="background:${stColor}"></span><span class="d-flat rl-state" style="color:${stColor}">${st === 'success' ? 'Success' : st === 'error' ? 'Error' : 'Warning'}</span></div>
                <div class="svc-list-col-proto">
                    <span class="d-flat d-proto d-proto-${proto.toLowerCase()}">${proto}</span>
                    ${type ? `<span class="d-flat d-blue">${type}</span>` : ''}
                </div>
                <div class="svc-list-col-name">${_esc(name)}${ownerName ? ` <span class="d-flat d-off">backend of ${_esc(ownerName)}</span>` : ''}</div>
                <div class="svc-list-col-url overflow-hidden">${serverUrlHtml}</div>
                <div class="svc-list-col-provider"><span class="d-flat d-off"><i class="ph-bold ph-database" style="font-size:10px;margin-right:4px"></i>${_esc(provider)}</span></div>
                <div class="svc-list-col-servers">${serverSummary ? `<span class="d-flat" style="color:${srvColor}"><i class="ph-bold ph-hard-drives" style="font-size:10px;margin-right:4px"></i>${serverSummary}</span>` : '<span class="d-flat d-off">-</span>'}</div>
                <div class="svc-list-col-usedby">${usedBy.length > 0 ? `<span class="d-flat d-mw"><i class="ph-bold ph-git-branch" style="font-size:9px;margin-right:4px"></i>${usedBy.length}</span>` : '<span class="d-flat d-off">-</span>'}</div>
            </div>`;
        }).join('');
        const header = `<div class="svc-list-header svc-list-grid">
            <div class="svc-list-col-status">Status</div>
            <div class="svc-list-col-proto">Protocol</div>
            <div class="svc-list-col-name">Name</div>
            <div class="svc-list-col-url">Backend URL</div>
            <div class="svc-list-col-provider">Provider</div>
            <div class="svc-list-col-servers">Servers</div>
            <div class="svc-list-col-usedby">Used By</div>
        </div>`;
        document.getElementById('liveContent').innerHTML = `<div class="svc-list">${header}${rows}${empty}</div>`;
    } else {
        const cls = 'tm-card-grid';
        document.getElementById('liveContent').innerHTML = `<div class="${cls}">${cards}${empty}</div>`;
    }

    setTabCount('live', _allServices.length - ownedIdx.size);
}

function _svcProvider(s) {
    return (s.name || '').includes('@') ? s.name.split('@').pop() : 'file';
}

function _svcEditable(s) {
    const provider = (s.name || '').includes('@') ? s.name.split('@').pop() : 'file';
    if (provider !== 'file') return false;
    if ((s._proto || 'HTTP') !== 'HTTP') return false;
    if (_ownedChildNames.has(_svcBareName(s.name))) return false;
    const kind = _compositeTypeOf(s);
    return !!kind || !!s.loadBalancer;
}

function _svcOwnershipHtml(s) {
    const bare = _svcBareName(s.name);
    const owned = _ownedServiceNames.has(bare);
    return `<div class="text-xs" style="color:var(--muted)">${owned
            ? 'Traefik Manager manages this service. Routes using it can edit their backends here.'
            : 'This service is not managed by Traefik Manager, so routes using it are read only.'}</div>
        <button type="button" class="btn-secondary text-xs mt-2" onclick="_setServiceOwnership(${_jsArg(bare)}, ${owned ? 'false' : 'true'})">
            <i class="ph-bold ${owned ? 'ph-hand-withdraw' : 'ph-hand-deposit'} text-xs"></i> ${owned ? 'Stop managing' : 'Manage this service'}
        </button>`;
}

function _svcApiPath(path) {
    return _activeAgent ? path + '?agent_id=' + encodeURIComponent(_activeAgent.id) : path;
}

async function _setServiceOwnership(name, adopt) {
    try {
        const res = await fetch(_svcApiPath('/api/services/' + encodeURIComponent(name) + '/ownership'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'fetch',
                       ..._csrfHeaders() },
            body: JSON.stringify({ adopt }),
        });
        const body = await res.json();
        if (!res.ok || !body.ok) {
            showToast(body.error || 'Could not change management', 'error');
            return;
        }
        showToast(adopt ? 'Traefik Manager now manages ' + name : 'Released ' + name, 'success');
        loadServices();
    } catch (e) {
        showToast('Could not change management', 'error');
    }
}

function _compositeChildren(s) {
    const out = [];
    (s.weighted?.services || []).forEach(x =>
        out.push({ name: x.name, role: 'Weighted', share: x.weight != null ? String(x.weight) : '-' }));
    (s.highestRandomWeight?.services || []).forEach(x =>
        out.push({ name: x.name, role: 'Weighted', share: x.weight != null ? String(x.weight) : '-' }));
    if (s.mirroring?.service) out.push({ name: s.mirroring.service, role: 'Main', share: '-' });
    (s.mirroring?.mirrors || []).forEach(m =>
        out.push({ name: m.name, role: 'Mirror', share: (m.percent || 0) + '%' }));
    if (s.failover?.service)  out.push({ name: s.failover.service,  role: 'Primary',  share: '-' });
    if (s.failover?.fallback) out.push({ name: s.failover.fallback, role: 'Fallback', share: '-' });
    return out.filter(c => c.name);
}

function _svcBareName(name) {
    return String(name || '').split('@')[0];
}

function _svcOwnedBases(parent) {
    const bases = [];
    const suffix = '-service';
    const p = _svcBareName(parent && parent.name);
    if (p.endsWith(suffix) && p.length > suffix.length) bases.push(p.slice(0, -suffix.length));
    (((parent && parent.usedBy) || [])).forEach(r => {
        const b = _svcBareName(r);
        if (b) bases.push(b);
    });
    return bases;
}

function _svcOwnsChild(parent, child) {
    if (!parent || !child || parent === child) return false;
    if ((parent._proto || 'HTTP') !== (child._proto || 'HTTP')) return false;
    if (!child.loadBalancer || _compositeChildren(child).length > 0) return false;
    if ((child.usedBy || []).length > 0) return false;
    const cName = _svcBareName(child.name);
    if (!cName) return false;
    const named = _svcOwnedBases(parent).some(base => {
        const prefix = base + '-backend-';
        return cName.startsWith(prefix) && /^[0-9]+$/.test(cName.slice(prefix.length));
    });
    if (!named) return false;
    return _compositeChildren(parent).some(c => _svcBareName(c.name) === cName);
}

function _svcOwnedChildIndex(services, ledgerNames) {
    const list = services || [];
    const known = ledgerNames || new Set();
    const owned = new Set();
    for (let i = 0; i < list.length; i++) {
        if (known.has(_svcBareName(list[i].name))) { owned.add(i); continue; }
        if (list.some(p => _svcOwnsChild(p, list[i]))) owned.add(i);
    }
    return owned;
}

function _svcOwnerName(services, child) {
    const parent = (services || []).find(p => _svcOwnsChild(p, child));
    return parent ? _svcBareName(parent.name) : '';
}

function _openServiceByName(name) {
    const bare = String(name || '').split('@')[0];
    const idx = _allServices.findIndex(x => (x.name || '').split('@')[0] === bare);
    if (idx >= 0) openSvcDetail(idx);
    else showToast('Service ' + bare + ' is not in this list', 'error');
}

function openSvcDetail(idx) {
    closeOtherPanels('svcDetailPanel');
    const s = _allServices[idx];
    if (!s) return;

    const panel   = document.getElementById('svcDetailPanel');
    const backdrop = document.getElementById('svcDetailBackdrop');
    const body    = document.getElementById('svcDetailBody');

    
    const proto = s._proto || 'HTTP';
    document.getElementById('svcDetailProtoBadge').className = 'd-flat d-proto' + (proto === 'TCP' ? ' d-on' : proto === 'UDP' ? ' d-warn' : '');
    document.getElementById('svcDetailProtoBadge').textContent = proto;
    document.getElementById('svcDetailTitle').textContent = (s.name || '').split('@')[0];

    const provider = (s.name || '').includes('@') ? s.name.split('@').pop() : 'file';
    const type = s.loadBalancer ? 'loadbalancer' : s.mirroring ? 'mirroring' : s.weighted ? 'weighted' : s.failover ? 'failover' : s.highestRandomWeight ? 'highestrandomweight' : '-';
    const status = s.status || 'unknown';
    const stKind = status === 'enabled' ? ['status-online', 'd-on', 'Success']
                 : status === 'disabled' || status === 'error' ? ['status-offline', 'd-bad', 'Error']
                 : ['status-checking', 'd-warn', 'Warning'];
    const statusBadge = `<span class="d-state d-flat ${stKind[1]}"><span class="status-dot ${stKind[0]}"></span>${stKind[2]}</span>`;

    const lb = s.loadBalancer || {};
    const servers = lb.servers || [];
    const passHostHeader = !s.loadBalancer ? '-'
                         : lb.passHostHeader !== undefined ? String(lb.passHostHeader) : 'true';

    
    const serversHtml = servers.length > 0 ? `
        <table class="w-full text-left mt-2">
            <thead style="background:var(--card)">
                <tr>
                    <th class="px-3 py-2 text-xs font-semibold uppercase tracking-wider" style="color:var(--muted)">Status</th>
                    <th class="px-3 py-2 text-xs font-semibold uppercase tracking-wider" style="color:var(--muted)">URL</th>
                </tr>
            </thead>
            <tbody>
                ${servers.map(sv => `
                <tr style="border-top:1px solid var(--border)">
                    <td class="px-3 py-2.5">
                        <span class="flex items-center gap-1.5"><span class="inline-block w-2 h-2 rounded-full bg-green-500"></span><span class="text-green-400 text-xs">Active</span></span>
                    </td>
                    <td class="px-3 py-2.5 font-mono text-xs break-all" style="color:var(--text)">${_esc(sv.url || sv.address || '-')}</td>
                </tr>`).join('')}
            </tbody>
        </table>` : `<div class="text-xs mt-2" style="color:var(--muted)">No servers configured</div>`;

    
    const children = _compositeChildren(s);
    const childrenHtml = `
        <table class="w-full text-left mt-2">
            <thead style="background:var(--card)">
                <tr>
                    <th class="px-3 py-2 text-xs font-semibold uppercase tracking-wider" style="color:var(--muted)">Role</th>
                    <th class="px-3 py-2 text-xs font-semibold uppercase tracking-wider" style="color:var(--muted)">Service</th>
                    <th class="px-3 py-2 text-xs font-semibold uppercase tracking-wider" style="color:var(--muted)">Share</th>
                </tr>
            </thead>
            <tbody>
                ${children.map(c => `
                <tr style="border-top:1px solid var(--border)">
                    <td class="px-3 py-2.5 text-xs" style="color:var(--muted)">${_esc(c.role)}</td>
                    <td class="px-3 py-2.5">
                        <button type="button" class="route-deep-chip" onclick="_openServiceByName(${_jsArg(c.name)})" title="Open service"><i class="ph-bold ph-stack"></i>${_esc(String(c.name).split('@')[0])}</button>
                    </td>
                    <td class="px-3 py-2.5 font-mono text-xs" style="color:var(--text)">${_esc(c.share)}</td>
                </tr>`).join('')}
            </tbody>
        </table>`;

    const usedBy = s.usedBy || [];
    const usedByHtml = usedBy.length > 0
        ? `<div class="flex flex-wrap gap-1.5">${usedBy.map(r =>
            `<button type="button" class="route-deep-chip" onclick="_openRouteByName(${_jsArg(String(r))})" title="Open route"><i class="ph-bold ph-arrows-split"></i>${_esc(String(r).split('@')[0])}</button>`).join('')}</div>`
        : `<span class="text-xs" style="color:var(--muted)">-</span>`;

    const ownerName = _svcOwnerName(_allServices, s);
    const detailRows = [
        ['Type', type, false],
        ['Provider', _dText(provider, 'd-off'), true],
        ['Status', statusBadge, true],
        ['Pass Host Header', passHostHeader === '-' ? '-' : _dBool(passHostHeader === 'true'), true],
    ];
    if (ownerName) {
        detailRows.splice(1, 0, ['Backend of',
            `<button type="button" class="route-deep-chip" onclick="_openServiceByName(${_jsArg(ownerName)})" title="Open service"><i class="ph-bold ph-stack"></i>${_esc(ownerName)}</button>`,
            true]);
    }

    body.innerHTML =
        renderSection('Service Details', 'ph-info', detailRows)
        + (children.length
            ? renderDetailBlock('Backends', 'ph-tree-structure', childrenHtml, _dCount(children.length))
            : renderDetailBlock('Servers', 'ph-globe', serversHtml, _dCount(servers.length)))
        + (children.length && _svcProvider(s) === 'file' ? renderDetailBlock('Management', 'ph-user-gear', _svcOwnershipHtml(s)) : '')
        + renderDetailBlock('Used by Routers', 'ph-git-branch', usedByHtml);

    const editBtn = document.getElementById('svcDetailEditBtn');
    if (editBtn) {
        const canEdit = _svcEditable(s);
        editBtn.style.display = canEdit ? '' : 'none';
        if (canEdit) {
            editBtn.onclick = () => { closeSvcDetail(); openServiceModal(s); };
        }
    }

    backdrop.classList.add('open');
    panel.classList.add('open');
    setDetailDockOpen(true);
}

function closeSvcDetail() {
    setDetailDockOpen(false);
    document.getElementById('svcDetailPanel').classList.remove('open');
    document.getElementById('svcDetailBackdrop').classList.remove('open');
}

let _svcRowSeq = 0;

function _svcTypeChanged() {
    const kind = document.getElementById('svcType')?.value || 'weighted';
    const hint = document.getElementById('svcTypeHint');
    if (hint) {
        hint.textContent = kind === 'loadBalancer' ? 'Requests are spread evenly across the servers.'
            : kind === 'weighted' ? 'Traffic is split between the backends by weight.'
            : kind === 'mirroring' ? 'The first backend serves every request; the rest receive a copy by percentage.'
            : 'The first backend serves; the second takes over if it fails.';
    }
    const plain = kind === 'loadBalancer';
    const addBtn = document.querySelector('#svcRows')?.previousElementSibling?.querySelector('button');
    if (addBtn) {
        const over = kind === 'failover' && document.querySelectorAll('#svcRows .svc-row').length >= 2;
        addBtn.disabled = over;
        addBtn.title = over ? 'Failover takes two backends' : '';
    }
    document.querySelectorAll('#svcRows .svc-row').forEach(r => {
        const w = r.querySelector('.svc-weight');
        if (w) { w.style.display = plain ? 'none' : ''; w.title = kind === 'mirroring' ? 'Percent' : 'Weight'; }
        _svcRowKindChanged(r.querySelector('.svc-kind'));
    });
}

async function addServiceRow(data) {
    const wrap = document.getElementById('svcRows');
    if (!wrap) return;
    const kind = document.getElementById('svcType')?.value || 'loadBalancer';
    if (kind === 'failover' && wrap.querySelectorAll('.svc-row').length >= 2) {
        showToast('Failover takes two backends: the one that serves and the one that takes over', 'error');
        return;
    }
    const d = data || {};
    const id = 'svcrow' + (++_svcRowSeq);
    const row = document.createElement('div');
    row.className = 'svc-row tm-backend-row grid gap-3 mt-2';
    row.style.gridTemplateColumns = '104px 96px 1fr 74px 32px';
    row.id = id;
    row.innerHTML =
        `<select class="input-field svc-kind text-sm" onchange="_svcRowKindChanged(this)"><option value="manual">IP : Port</option><option value="service">Service</option></select>`
        + `<select class="input-field svc-scheme text-sm"><option value="http">HTTP</option><option value="https">HTTPS</option></select>`
        + `<input type="text" class="input-field svc-addr text-sm" placeholder="10.0.0.10:80">`
        + `<select class="input-field svc-ref text-sm" style="display:none"></select>`
        + `<input type="number" class="input-field svc-weight text-sm" value="1" min="0" title="Weight">`
        + `<button type="button" onclick="this.closest('.svc-row').remove()" class="btn-secondary" title="Remove" style="padding:0;width:32px;display:flex;align-items:center;justify-content:center"><i class="ph-bold ph-trash text-xs" style="color:var(--red)"></i></button>`;
    wrap.appendChild(row);
    if (d.kind === 'service') row.querySelector('.svc-kind').value = 'service';
    if (d.scheme) row.querySelector('.svc-scheme').value = d.scheme;
    if (d.address) row.querySelector('.svc-addr').value = d.address;
    if (d.weight != null) row.querySelector('.svc-weight').value = d.weight;
    await _svcFillRefSelect(row, d.name);
    _svcRowKindChanged(row.querySelector('.svc-kind'));
    _svcTypeChanged();
}

async function _svcFillRefSelect(row, selected) {
    const sel = row.querySelector('.svc-ref');
    if (!sel) return;
    const svcs = (await _ensureServicesList()).http || [];
    const editing = (document.getElementById('svcOriginalName')?.value || '').trim();
    const usable = svcs.filter(n => n !== editing);
    sel.innerHTML = usable.length
        ? usable.map(n => `<option value="${_esc(n)}">${_esc(n)}</option>`).join('')
        : '<option value="">No other services to reference yet</option>';
    if (selected && !usable.includes(selected)) {
        sel.insertAdjacentHTML('afterbegin', `<option value="${_esc(selected)}">${_esc(selected)}</option>`);
    }
    if (selected) sel.value = selected;
}

function _svcRowKindChanged(select) {
    if (!select) return;
    const row = select.closest('.svc-row');
    if (!row) return;
    const isSvc = select.value === 'service';
    if (isSvc && (document.getElementById('svcType')?.value || '') === 'loadBalancer') {
        const t = document.getElementById('svcType');
        if (t) { t.value = 'weighted'; _svcTypeChanged(); return; }
    }
    const plain = (document.getElementById('svcType')?.value || '') === 'loadBalancer';
    const set = (sel, on) => {
        const el = row.querySelector(sel);
        if (el) { el.style.display = on ? '' : 'none'; el.style.gridColumn = ''; }
    };
    set('.svc-addr', !isSvc);
    set('.svc-scheme', !isSvc);
    set('.svc-ref', isSvc);
    row.style.gridTemplateColumns = plain ? '104px 96px 1fr 32px'
        : isSvc ? '104px 1fr 74px 32px' : '104px 96px 1fr 74px 32px';
}

function _collectServiceRows() {
    const kind = document.getElementById('svcType')?.value || 'weighted';
    const out = [];
    document.querySelectorAll('#svcRows .svc-row').forEach(r => {
        const raw = parseInt(r.querySelector('.svc-weight')?.value, 10);
        const share = isNaN(raw) ? (kind === 'mirroring' ? 0 : 1) : raw;
        if (r.querySelector('.svc-kind')?.value === 'service') {
            const name = (r.querySelector('.svc-ref')?.value || '').trim();
            if (name) out.push({ kind: 'service', name, weight: share, percent: share });
            return;
        }
        const address = (r.querySelector('.svc-addr')?.value || '').trim();
        const scheme = r.querySelector('.svc-scheme')?.value || 'http';
        if (address) out.push({ kind: 'manual', address, scheme, weight: share, percent: share });
    });
    return out;
}

async function openServiceModal(existing) {
    closeOtherPanels('serviceModal');
    const set = (id, v) => { const el = document.getElementById(id); if (el) el.value = v || ''; };
    set('svcOriginalName', existing ? _svcBareName(existing.name) : '');
    set('svcName', existing ? _svcBareName(existing.name) : '');
    set('svcType', existing ? (_compositeTypeOf(existing) || 'loadBalancer') : 'loadBalancer');
    const err = document.getElementById('svcError');
    if (err) err.style.display = 'none';
    const title = document.getElementById('svcModalTitle');
    if (title) title.textContent = existing ? 'Edit Service' : 'Add Service';
    const del = document.getElementById('svcDeleteBtn');
    if (del) del.style.display = existing ? '' : 'none';
    const rows = document.getElementById('svcRows');
    if (rows) rows.innerHTML = '';
    await _populateConfigFileSelect('service');
    if (existing && !_compositeTypeOf(existing)) {
        const urls = ((existing.loadBalancer || {}).servers || [])
            .map(sv => sv.url || sv.address).filter(Boolean);
        if (urls.length) {
            for (const u of urls) await addServiceRow(_svcUrlToRow(u));
        } else {
            await addServiceRow();
        }
    } else if (existing) {
        for (const c of _compositeChildren(existing).map(_svcChildToRow)) await addServiceRow(c);
    } else {
        await addServiceRow();
    }
    _svcTypeChanged();
    document.getElementById('serviceModal')?.classList.add('open');
    document.getElementById('svcBackdrop')?.classList.add('open');
    if (!setDetailDockOpen(true)) document.body.style.overflow = 'hidden';
}

function _compositeTypeOf(s) {
    return s.weighted ? 'weighted' : s.mirroring ? 'mirroring' : s.failover ? 'failover' : '';
}

function _svcUrlToRow(url) {
    const u = String(url || '');
    return { kind: 'manual',
             scheme: u.startsWith('https://') ? 'https' : 'http',
             address: u.replace(/^https?:\/\//, '') };
}

function _svcChildToRow(label) {
    const name = String(label).split(' ')[0];
    const m = String(label).match(/\((\d+)%?\)/);
    const weight = m ? m[1] : 1;
    if (!_ownedChildNames.has(name)) return { kind: 'service', name, weight };
    const child = _allServices.find(x => _svcBareName(x.name) === name);
    const url = (((child || {}).loadBalancer || {}).servers || [])
        .map(sv => sv.url || sv.address).filter(Boolean)[0] || '';
    return { ..._svcUrlToRow(url), weight };
}

function onSvcConfigFileChange(sel) {
    const newInput = document.getElementById('newSvcFileName');
    if (!newInput) return;
    if (sel.value === '__new__') {
        newInput.style.display = '';
        const svcName = (document.getElementById('svcName')?.value || '').trim().toLowerCase().replace(/[^a-z0-9-]/g, '-');
        if (!newInput.value && svcName) newInput.value = `services-${svcName}.yml`;
    } else {
        newInput.style.display = 'none';
        newInput.value = '';
    }
}

function _svcTargetConfigFile() {
    const sel = document.getElementById('svcConfigFileSelect');
    if (sel && sel.value === '__new__') {
        return (document.getElementById('newSvcFileName')?.value || '').trim();
    }
    return sel ? sel.value : '';
}

function closeServiceModal() {
    setDetailDockOpen(false);
    document.getElementById('serviceModal')?.classList.remove('open');
    document.getElementById('svcBackdrop')?.classList.remove('open');
    document.body.style.overflow = '';
}

async function saveServiceModal() {
    const err = document.getElementById('svcError');
    const show = (msg) => { if (err) { err.textContent = msg; err.style.display = ''; } };
    const name = (document.getElementById('svcName')?.value || '').trim();
    const children = _collectServiceRows();
    if (!name) return show('Give the service a name.');
    if (!children.length) return show('Add at least one backend.');
    const btn = document.getElementById('svcSaveBtn');
    if (btn) btn.disabled = true;
    try {
        const res = await fetch('/api/services', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'fetch',
                       ..._csrfHeaders() },
            body: JSON.stringify({
                name,
                type: document.getElementById('svcType')?.value || 'weighted',
                originalName: (document.getElementById('svcOriginalName')?.value || '').trim(),
                configFile: _svcTargetConfigFile(),
                agent_id: _activeAgent ? _activeAgent.id : '',
                children,
            }),
        });
        const body = await res.json();
        if (!res.ok || !body.ok) return show(body.error || 'Could not save the service');
        closeServiceModal();
        showToast('Service ' + name + ' saved', 'success');
        window._tmServices = null;
        loadServices();
    } catch (e) {
        show('Could not save the service');
    } finally {
        if (btn) btn.disabled = false;
    }
}

async function deleteServiceFromModal() {
    const name = (document.getElementById('svcOriginalName')?.value || '').trim();
    if (!name) return;
    if (!await _confirm('Delete the service ' + name + '? Its own backends are removed with it.', 'Delete Service', 'Delete', 'DELETE')) return;
    await _sendServiceDelete(name, false);
}

async function _sendServiceDelete(name, force) {
    const err = document.getElementById('svcError');
    try {
        const res = await fetch(_svcApiPath('/api/services/' + encodeURIComponent(name)) + (force ? (_activeAgent ? '&' : '?') + 'force=1' : ''), {
            method: 'DELETE', headers: { 'X-Requested-With': 'fetch', ..._csrfHeaders() },
        });
        const body = await res.json().catch(() => null);
        if (res.status === 409 && body && ((body.inUseBy || []).length || (body.parents || []).length)) {
            const routes = body.inUseBy || [], parents = body.parents || [];
            const show = a => a.slice(0, 5).join(', ') + (a.length > 5 ? ' and ' + (a.length - 5) + ' more' : '');
            const parts = [];
            if (routes.length) parts.push('Delete ' + (routes.length === 1 ? 'the route ' : routes.length + ' routes: ') + show(routes));
            if (parents.length) parts.push('remove it from ' + show(parents) + (parents.length === 1 ? ' (which is deleted if nothing is left in it)' : ' (any left empty are deleted too)'));
            if (await _confirm('"' + name + '" is still in use. ' + parts.join(', and ') + ', then delete it?',
                               'Service In Use', 'Delete all of it', 'DELETE')) {
                await _sendServiceDelete(name, true);
            }
            return;
        }
        if (!res.ok || !body || !body.ok) {
            if (err) { err.textContent = (body && body.error) || 'Could not delete'; err.style.display = ''; }
            return;
        }
        closeServiceModal();
        const d = body.deleted || {};
        const extra = (d.routers || []).length ? ' and ' + d.routers.length + (d.routers.length === 1 ? ' route' : ' routes') : '';
        showToast('Service ' + name + ' deleted' + extra, 'success');
        window._tmServices = null;
        loadServices();
        if (extra && typeof refreshRoutes === 'function') refreshRoutes();
    } catch (e) {
        if (err) { err.textContent = 'Could not delete'; err.style.display = ''; }
    }
}

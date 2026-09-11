const RM_GROUP_COLORS = ['#f0883e','#a371f7','#24a1de','#3fb950','#e2c041','#58a6ff','#ff7b72'];
const RM_ICON_CDN = 'https://cdn.jsdelivr.net/gh/selfhst/icons@main/png';

let _rmConfig    = { custom_groups: [], route_overrides: {} };
let _rmAllRoutes = [];
let _rmRouterStatus = {};
let _rmSvcStatus = {};
let _rmSvcLoaded = false;
let _rmStatusBlind = true;
let _rmAllEps    = {};
let _rmDataLoaded = false;
let _rmLoadedAt   = 0;
let _rmLoadErr    = '';
const RM_DATA_TTL = 30000;

window.rmGetCustomGroups = function() { return _rmConfig.custom_groups || []; };

window.rmIconFallback = function(img) {
    const slug = img.dataset.slug;
    if (!slug) { img.style.display = 'none'; return; }
    const parts = slug.split('-');
    const shorter = parts.length > 2 ? parts.slice(0, -1).join('-') : parts[0];
    if (shorter && shorter !== slug) {
        img.dataset.slug = shorter;
        img.src = `${RM_ICON_CDN}/${shorter}.png`;
    } else {
        img.style.display = 'none';
    }
};

function _rmServerId() {
    return (typeof _activeAgent !== 'undefined' && _activeAgent) ? _activeAgent.id : '';
}

async function rmSaveConfig() {
    const token = document.querySelector('meta[name="csrf-token"]')?.content || '';
    const srv = _rmServerId();
    await fetch('/api/dashboard/config' + (srv ? '?server=' + encodeURIComponent(srv) : ''), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': token },
        body: JSON.stringify({ ..._rmConfig, server: srv })
    });
}

function _rmProtoRows(data) {
    const rows = [];
    ['http', 'tcp', 'udp'].forEach(p => {
        const arr = data && Array.isArray(data[p]) ? data[p] : [];
        arr.forEach(item => { if (item && item.name) rows.push([p, item]); });
    });
    return rows;
}

function _rmStatusMap(rows, build) {
    const out = {}, seen = {}, bare = {};
    rows.forEach(([proto, item]) => {
        const st = build(item);
        if (!st) return;
        out[proto + ':' + item.name] = st;
        const bk = proto + ':' + item.name.split('@')[0];
        seen[bk] = (seen[bk] || 0) + 1;
        if (seen[bk] === 1) bare[bk] = st;
    });
    Object.keys(bare).forEach(k => {
        if (seen[k] === 1 && out[k] === undefined) out[k] = bare[k];
    });
    return out;
}

window.rmEnsureData = async function(force, opts) {
    const wantSvc = !!(opts && opts.services);
    if (_rmDataLoaded && !force && (Date.now() - _rmLoadedAt) < RM_DATA_TTL && (!wantSvc || _rmSvcLoaded)) return true;
    _rmLoadErr = '';
    try {
        const routeUrl = _activeAgent
            ? '/api/agents/' + _activeAgent.id + '/routes'
            : '/api/routes/all';
        const [routeRes, epRes, cfgRes, rtrRes, svcRes] = await Promise.all([
            fetch(routeUrl, { headers: { 'X-Requested-With': 'fetch' } }),
            agentFetch('/api/traefik/entrypoints'),
            fetch('/api/dashboard/config' + (_rmServerId() ? '?server=' + encodeURIComponent(_rmServerId()) : '')),
            agentFetch('/api/traefik/routers').catch(() => null),
            wantSvc ? agentFetch('/api/traefik/services').catch(() => null) : null
        ]);
        if (!routeRes.ok) {
            _rmLoadErr = await _errText(routeRes, 'Could not load route map data');
            throw new Error(_rmLoadErr);
        }
        const routeData = await routeRes.json();
        _rmAllRoutes = (routeData.apps || []).map(r => ({
            ...r,
            middlewares: [...new Set([...(r.middlewares || []), ...(r.entrypointMiddlewares || [])])]
        }));
        try {
            const epData = epRes.ok ? await epRes.json() : {};
            _rmAllEps = Array.isArray(epData)
                ? Object.fromEntries(epData.map(ep => [ep.name, ep]))
                : (epData || {});
        } catch(_) { _rmAllEps = {}; }
        try { _rmConfig = await cfgRes.json() || { custom_groups: [], route_overrides: {} }; } catch(_) {}
        _rmRouterStatus = {};
        _rmStatusBlind  = true;
        try {
            if (rtrRes && rtrRes.ok) {
                const rd = await rtrRes.json();
                _rmStatusBlind = rd.reachable === false;
                _rmRouterStatus = _rmStatusMap(_rmProtoRows(rd), rt => {
                    const errs = [].concat(rt.error || []).filter(Boolean).map(String);
                    return {
                        up:  rt.status === 'enabled' && !errs.length,
                        err: !!errs.length,
                        msg: errs.join('; '),
                    };
                });
            }
        } catch(_) {}
        _rmSvcStatus = {};
        _rmSvcLoaded = wantSvc;
        try {
            if (wantSvc && svcRes && svcRes.ok) {
                const sd = await svcRes.json();
                _rmSvcStatus = _rmStatusMap(_rmProtoRows(sd), sv => {
                    const map = sv.serverStatus;
                    if (!map || typeof map !== 'object') return null;
                    const keys = Object.keys(map);
                    if (!keys.length) return null;
                    let up = 0;
                    keys.forEach(k => { if (String(map[k]).toUpperCase() === 'UP') up++; });
                    if (up === keys.length && !(sv.loadBalancer && sv.loadBalancer.healthCheck)) return null;
                    return { up: up, total: keys.length };
                });
            }
        } catch(_) {}
    } catch(e) {
        if (!_rmLoadErr) _rmLoadErr = _netErrText(e, 'Could not load route map data');
        _rmAllRoutes    = [];
        _rmAllEps       = {};
        _rmRouterStatus = {};
        _rmSvcStatus    = {};
        _rmSvcLoaded    = false;
        _rmStatusBlind  = true;
        return false;
    }
    _rmDataLoaded = true;
    _rmLoadedAt   = Date.now();
    return true;
};

(function() {

const _rmEps = r => Array.isArray(r.entryPoints) ? r.entryPoints : r.entryPoints ? [r.entryPoints] : [];

let _rmProto          = 'all';
let _rmProvider       = 'all';
let _rmEpFilter       = 'all';
let _rmGroupBy        = 'name';
let _rmSearch         = '';
let _rmDrawn          = false;
let _rmTopoSelected   = null;
let _rmPopupOpen      = false;
const _rmExpandedGroups = new Set();
const RM_COLLAPSE_MIN = 6;
let _rmRouteGroupKey  = new Map();
let _rmDagreGraph     = null;
let _rmDagreRoutes    = null;
let _rmDagreW         = 800;
let _rmDagreH         = 600;

const RM_NODE_DIMS = {
    ep:    { width: 130, height: 30 },
    route: { width: 160, height: 32 },
    group: { width: 160, height: 32 },
    mw:    { width: 144, height: 30 },
    svc:   { width: 160, height: 30 },
};


function _rmBuildDagre(routes) {
    const g = new dagre.graphlib.Graph({ multigraph: true });
    g.setGraph({ rankdir: 'LR', nodesep: 4, ranksep: 30, marginx: 12, marginy: 12, acyclicer: 'greedy' });
    g.setDefaultEdgeLabel(() => ({}));

    const mwUsage = {};
    routes.forEach(r => (r.middlewares||[]).forEach(mw => { mwUsage[mw] = (mwUsage[mw]||0)+1; }));

    const byProv = {};
    routes.forEach(r => {
        const prov = r.provider || 'file';
        if (prov === 'file') return;
        (byProv[prov] = byProv[prov] || []).push(r);
    });
    const collapsed = {};
    Object.entries(byProv).forEach(([prov, rs]) => {
        if (rs.length >= RM_COLLAPSE_MIN) collapsed[prov] = rs;
    });
    const collapsedIds = new Set(Object.values(collapsed).flat().map(r => r.id));
    const shown = routes.filter(r => !collapsedIds.has(r.id));

    const epNames = [...new Set(routes.flatMap(r => _rmEps(r)))];
    const epProto = {};
    routes.forEach(r => {
        const p = (r.protocol || 'http').toLowerCase();
        _rmEps(r).forEach(ep => {
            epProto[ep] = epProto[ep] === undefined || epProto[ep] === p ? p : '';
        });
    });
    const mwNames = [...new Set(routes.flatMap(r => r.middlewares||[]))];
    const svcMap  = new Map();
    const svcOwner = new Map();
    routes.forEach(r => {
        if (!r.service_name) return;
        svcMap.set(r.service_name, r.target || r.service_name);
        if (!svcOwner.has(r.service_name)) svcOwner.set(r.service_name, r);
    });

    const dims = (kind, html) => {
        const m = _rmMeasure(html);
        return m && m.width ? m : { ...RM_NODE_DIMS[kind] };
    };

    epNames.forEach(n => g.setNode(`ep:${n}`,
        { ...dims('ep', _rmNodeHtml('ep', n, { mwUsage, proto: epProto[n] })), type:'ep', id:n }));
    mwNames.forEach(n => g.setNode(`mw:${n}`,
        { ...dims('mw', _rmNodeHtml('mw', n, { mwUsage })), type:'mw', id:n }));
    svcMap.forEach((target, n) => g.setNode(`svc:${n}`,
        { ...dims('svc', _rmNodeHtml('svc', n, { target, route: svcOwner.get(n) })),
          type:'svc', id:n, target, owner: svcOwner.get(n) }));
    shown.forEach(r => g.setNode(`route:${r.id}`,
        { ...dims('route', _rmNodeHtml('route', r.id, { route:r })), type:'route', id:r.id, route:r }));
    Object.entries(collapsed).forEach(([prov, rs]) => {
        const ctx = { label: prov, count: rs.length,
                      title: rs.length + ' ' + prov + ' routes - click to list them' };
        g.setNode(`group:${prov}`,
            { ...dims('group', _rmNodeHtml('group', prov, ctx)), type:'group', id:prov,
              label: prov, count: rs.length, title: ctx.title, members: rs });
    });

    Object.entries(collapsed).forEach(([prov, rs]) => {
        const gv = `group:${prov}`;
        const eps = [...new Set(rs.flatMap(r => _rmEps(r)))];
        eps.forEach(ep => {
            const k = `${ep}->${gv}`;
            if (!g.hasEdge(`ep:${ep}`, gv, k)) g.setEdge(`ep:${ep}`, gv, { type:'ep-route' }, k);
        });
        const svcs = [...new Set(rs.map(r => r.service_name).filter(Boolean))];
        svcs.forEach(sn => {
            const k = `${gv}->svc:${sn}`;
            if (!g.hasEdge(gv, `svc:${sn}`, k)) g.setEdge(gv, `svc:${sn}`, { type:'route-svc' }, k);
        });
    });

    shown.forEach(r => {
        const rv = `route:${r.id}`;
        _rmEps(r).forEach(ep => {
            const k = `${ep}→${rv}`;
            if (!g.hasEdge(`ep:${ep}`, rv, k)) g.setEdge(`ep:${ep}`, rv, { type:'ep-route' }, k);
        });
        if ((r.middlewares||[]).length) {
            r.middlewares.forEach(mw => {
                const k1 = `${rv}→mw:${mw}`;
                if (!g.hasEdge(rv, `mw:${mw}`, k1)) g.setEdge(rv, `mw:${mw}`, { type:'route-mw' }, k1);
                if (r.service_name) {
                    const k2 = `mw:${mw}→svc:${r.service_name}`;
                    if (!g.hasEdge(`mw:${mw}`, `svc:${r.service_name}`, k2))
                        g.setEdge(`mw:${mw}`, `svc:${r.service_name}`, { type:'mw-svc' }, k2);
                }
            });
        } else if (r.service_name) {
            const k = `${rv}→svc:${r.service_name}`;
            if (!g.hasEdge(rv, `svc:${r.service_name}`, k))
                g.setEdge(rv, `svc:${r.service_name}`, { type:'route-svc' }, k);
        }
    });

    dagre.layout(g);
    return { g, mwUsage, svcMap, epNames, mwNames, collapsed };
}

function _esc(s) {
    return String(s||'').replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

const _rmPfx = name => name.split(/[-_\s]/)[0].replace(/\d+$/, '');

const _rmDomain = r => {
    if (!r.rule) return '';
    const m = r.rule.match(/Host\(`([^`]+)`\)/i);
    return m ? m[1] : '';
};

function _rmMakeGroupResult(byKey) {
    const groups = Object.fromEntries(Object.entries(byKey).filter(([,v]) => v.length >= 2));
    const grouped = new Set(Object.values(groups).flat().map(r => r.id));
    const routeGroupKey = new Map();
    Object.entries(groups).forEach(([k, members]) => members.forEach(r => routeGroupKey.set(r.id, k)));
    return { groups, grouped, routeGroupKey };
}

function rmGroupRoutes(routes) {
    const byPfx = {};
    routes.forEach(r => {
        const p = _rmPfx(r.name);
        if (p.length >= 2) (byPfx[p] = byPfx[p] || []).push(r);
    });
    return _rmMakeGroupResult(byPfx);
}

function rmGroupByDomain(routes) {
    const by = {};
    routes.forEach(r => {
        const d = _rmDomain(r);
        if (d) (by[d] = by[d] || []).push(r);
    });
    return _rmMakeGroupResult(by);
}

function rmGroupByMw(routes) {
    const by = {};
    routes.forEach(r => {
        const mws = (r.middlewares||[]).slice().sort();
        if (!mws.length) return;
        const k = mws[0].split('@')[0];
        (by[k] = by[k] || []).push(r);
    });
    return _rmMakeGroupResult(by);
}

function rmGetGroups(routes, mode) {
    if (mode === 'domain')     return rmGroupByDomain(routes);
    if (mode === 'middleware') return rmGroupByMw(routes);
    if (mode === 'none')       return { groups: {}, grouped: new Set(), routeGroupKey: new Map() };
    return rmGroupRoutes(routes);
}

function _rmFilteredRoutes() {
    return _rmAllRoutes.filter(r => {
        if (r.enabled === false) return false;
        if (_rmProto !== 'all' && r.protocol !== _rmProto) return false;
        if (_rmProvider !== 'all' && (r.provider || 'file') !== _rmProvider) return false;
        if (_rmEpFilter !== 'all' && !_rmEps(r).includes(_rmEpFilter)) return false;
        if (_rmSearch && !(r.name||'').toLowerCase().includes(_rmSearch)) return false;
        return true;
    });
}

window.rmPickProvider = function(p, label) {
    _rmProvider = p;
    document.getElementById('rm-provider-label').textContent = label;
    document.getElementById('rm-dd-provider-btn').classList.toggle('active', p !== 'all');
    document.querySelectorAll('#rm-dd-provider-menu .live-dd-item').forEach(b => b.classList.toggle('active', b.textContent.trim() === label));
    toggleLiveDd('rm-dd-provider');
    rmRender();
};

window.rmPickEp = function(ep, label) {
    _rmEpFilter = ep;
    document.getElementById('rm-ep-label').textContent = label;
    document.getElementById('rm-dd-ep-btn').classList.toggle('active', ep !== 'all');
    document.querySelectorAll('#rm-dd-ep-menu .live-dd-item').forEach(b => b.classList.toggle('active', b.textContent.trim() === label));
    toggleLiveDd('rm-dd-ep');
    rmRender();
};

function rmRenderEpFilters() {
    const epNames = Object.keys(_rmAllEps).sort();
    const menu = document.getElementById('rm-dd-ep-menu');
    if (!menu) return;
    menu.innerHTML = `<button class="live-dd-item${_rmEpFilter === 'all' ? ' active' : ''}" onclick="rmPickEp('all','All Entry Points')">All Entry Points</button>`;
    epNames.forEach(ep => {
        const btn = document.createElement('button');
        btn.className = 'live-dd-item' + (ep === _rmEpFilter ? ' active' : '');
        btn.textContent = ep;
        btn.onclick = () => window.rmPickEp(ep, ep);
        menu.appendChild(btn);
    });
}

function rmRenderProviderFilters() {
    const providers = [...new Set(_rmAllRoutes.map(r => r.provider || 'file'))].sort();
    const menu = document.getElementById('rm-dd-provider-menu');
    if (!menu) return;
    menu.innerHTML = `<button class="live-dd-item${_rmProvider === 'all' ? ' active' : ''}" onclick="rmPickProvider('all','All Providers')">All Providers</button>`;
    if (providers.length > 1) {
        providers.forEach(p => {
            const btn = document.createElement('button');
            btn.className = 'live-dd-item' + (p === _rmProvider ? ' active' : '');
            btn.textContent = p;
            btn.onclick = () => window.rmPickProvider(p, p);
            menu.appendChild(btn);
        });
    }
}



window.rmClearFilters = function() {
    _rmProto = 'all'; _rmProvider = 'all'; _rmEpFilter = 'all'; _rmGroupBy = 'name'; _rmSearch = '';
    const s = document.getElementById('rmSearch'); if (s) s.value = '';
    ['all','http','tcp','udp'].forEach(p => {
        const btn = document.getElementById('rmf-' + p);
        if (btn) btn.className = 'proto-btn text-xs px-3 py-1.5' + (p === 'all' ? ' active-http' : '');
    });
    document.getElementById('rm-provider-label').textContent = 'All Providers';
    document.getElementById('rm-ep-label').textContent = 'All Entry Points';
    ['rm-dd-provider-btn','rm-dd-ep-btn'].forEach(id => document.getElementById(id)?.classList.remove('active'));
    document.querySelectorAll('#rm-dd-provider-menu .live-dd-item').forEach(b => b.classList.toggle('active', b.textContent.trim() === 'All Providers'));
    document.querySelectorAll('#rm-dd-ep-menu .live-dd-item').forEach(b => b.classList.toggle('active', b.textContent.trim() === 'All Entry Points'));
    rmRender();
};

window.refreshRoutemapTab = async function(force) {
    if (!_rmDrawn || force) {
        document.getElementById('rmLoading').classList.remove('hidden');
        document.getElementById('rmTopoContainer').classList.add('hidden');
        document.getElementById('rmEmpty').classList.add('hidden');
    }

    const ok = await window.rmEnsureData(force);

    document.getElementById('rmLoading').classList.add('hidden');
    if (!ok) {
        if (!_rmDrawn) {
            showToast((_rmLoadErr || 'Could not load route map data').replace(/\.?$/, '.') + ' Retrying on next open.', 'error');
            return;
        }
        showToast((_rmLoadErr || 'Could not refresh the route map').replace(/\.?$/, '.') + ' Showing the last data.', 'error');
    }
    _rmDrawn = true;
    rmRenderProviderFilters();
    rmRenderEpFilters();
    rmRender();
};

window.rmFilterProto = function(proto, label) {
    _rmProto = proto;
    ['all','http','tcp','udp'].forEach(p => {
        const btn = document.getElementById('rmf-' + p);
        if (btn) btn.className = 'proto-btn text-xs px-3 py-1.5' + (p === proto ? ' active-http' : '');
    });
    rmRender();
};

window.rmApplyFilter = function() {
    _rmSearch = document.getElementById('rmSearch').value.toLowerCase();
    rmRender();
};

function rmRender() {
    const routes = _rmFilteredRoutes();
    const topo   = document.getElementById('rmTopoContainer');
    const empty  = document.getElementById('rmEmpty');

    if (!routes.length) {
        topo.classList.add('hidden');
        empty.classList.remove('hidden');
        return;
    }
    empty.classList.add('hidden');
    topo.classList.remove('hidden');
    rmRenderTopology(routes);
}

window.rmResetHighlight = function() {
    _rmTopoSelected = null;
    document.querySelectorAll('#rmCols .rm-node').forEach(n => n.classList.remove('rm-node-dim','rm-node-active'));
    rmDrawCurves(_rmFilteredRoutes());
};

function rmRenderTopology(routes) {
    _rmExpandedGroups.clear();

    const { g, mwUsage } = _rmBuildDagre(routes);
    _rmDagreGraph  = g;
    _rmDagreRoutes = routes;

    const gl   = g.graph();
    let   W    = Math.ceil(gl.width)  + 1;
    const H    = Math.ceil(gl.height) + 1;
    const cont   = document.getElementById('rmTopoContainer');
    const colsEl = document.getElementById('rmCols');
    const svg    = document.getElementById('rmSvg');

    const contW = cont.clientWidth || cont.offsetWidth || 800;
    if (W < contW * 0.9) {
        const sx = contW / W;
        g.nodes().forEach(v => { const nd = g.node(v); if (nd) nd.x = nd.x * sx; });
        W = Math.ceil(contW);
    }
    _rmDagreW = W;
    _rmDagreH = H;

    colsEl.innerHTML = '';
    colsEl.style.display        = 'block';
    colsEl.style.position       = 'relative';
    colsEl.style.height         = H + 'px';
    colsEl.style.transform      = '';
    cont.style.height   = H + 'px';
    cont.style.overflow = 'visible';

    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
    svg.setAttribute('width',  W);
    svg.setAttribute('height', H);

    g.nodes().forEach(v => {
        const nd = g.node(v);
        if (!nd) return;
        const left = Math.round(nd.x - nd.width / 2);
        const top  = Math.round(nd.y - nd.height / 2);

        const wrap = document.createElement('div');
        wrap.style.cssText = `position:absolute;left:${left}px;top:${top}px;width:${nd.width}px`;

        wrap.innerHTML = _rmNodeHtml(nd.type, nd.type === 'route' ? nd.id : nd.id,
            { mwUsage, target: nd.target, route: nd.route || nd.owner, label: nd.label,
              count: nd.count, title: nd.title });
        colsEl.appendChild(wrap);
    });

    colsEl.querySelectorAll('[data-routeid]').forEach(el => {
        el.addEventListener('mouseenter', function() {
            if (_rmPopupOpen) return;
            _rmTopoSelected = this.dataset.routeid;
            rmHighlightRoute(_rmTopoSelected, routes);
            rmShowTooltip(this, _rmTopoSelected, routes);
        });
        el.addEventListener('mouseleave', function() {
            if (_rmPopupOpen) return;
            _rmTopoSelected = null;
            window.rmResetHighlight();
            rmHideTooltip();
        });
        el.addEventListener('click', function(e) {
            e.stopPropagation();
            rmHideTooltip();
            const rid = this.dataset.routeid;
            const r = routes.find(x => x.id === rid) || _rmAllRoutes.find(x => x.id === rid);
            if (r && typeof openRouteDetail === 'function') {
                openRouteDetail(r.name, r.protocol, r);
            } else {
                rmOpenPopup('route', rid, routes);
            }
        });
    });

    colsEl.querySelectorAll('.rm-node-group').forEach(el => {
        const prov = (el.dataset.rmid || '').split(':')[1] || '';
        el.addEventListener('click', function(e) {
            e.stopPropagation();
            rmHideTooltip();
            const members = (_rmDagreGraph && _rmDagreGraph.node('group:' + prov) || {}).members || [];
            rmOpenPopup('group', prov, members, members);
        });
    });

    colsEl.querySelectorAll('.rm-node-ep, .rm-node-mw, .rm-node-svc').forEach(el => {
        if (el.dataset.routeid) return;
        const rmid = el.dataset.rmid || '';
        const colon = rmid.indexOf(':');
        if (colon === -1) return;
        const type   = rmid.slice(0, colon);
        const nodeId = rmid.slice(colon + 1);
        el.addEventListener('mouseenter', function() {
            if (_rmPopupOpen) return;
            rmHighlightNode(type, nodeId, routes);
            rmShowNodeTooltip(this, type, nodeId, routes);
        });
        el.addEventListener('mouseleave', function() {
            if (_rmPopupOpen) return;
            window.rmResetHighlight();
            rmHideTooltip();
        });
        el.addEventListener('click', function(e) {
            e.stopPropagation();
            rmHideTooltip();
            rmOpenPopup(type, nodeId, routes);
        });
    });

    rmDrawCurves(routes);
    if (_rmTouchLayout()) rmInitMobilePan();
}

const _rmColIcons = { ep: 'ph-arrows-in', route: 'ph-git-branch', mw: 'ph-funnel', svc: 'ph-cube' };



function rmNode(typeClass, id, inner, routeId, title, health) {
    const parts   = typeClass.split(' ');
    const base    = parts[0];
    const classes = ['rm-node', ...parts.map(p => 'rm-node-' + p)].join(' ');
    const rid     = routeId ? ` data-routeid="${_esc(routeId)}"` : '';
    const tip     = title ? ` title="${_esc(title)}"` : ` title="${_esc(String(id))}"`;
    const hl      = health ? ` data-health="${_esc(health)}"` : '';
    return `<div class="${classes}" data-rmid="${_esc(base+':'+id)}"${rid}${tip}${hl}>${inner}</div>`;
}

function _rmQualify(name, prov) {
    return String(name || '').includes('@') ? String(name) : String(name || '') + '@' + prov;
}

function _rmRouteHealth(r) {
    if (_rmStatusBlind) return '';
    const proto = (r.protocol || 'http') + ':';
    const prov  = r.provider || 'file';
    const st = _rmRouterStatus[proto + _rmQualify(r.name, prov)]
            || _rmRouterStatus[proto + _rmQualify(r.id, prov)]
            || _rmRouterStatus[proto + (r.name || '')]
            || null;
    if (!st) return '';
    if (st.err) return 'down';
    return st.up ? 'up' : 'warn';
}

function _rmSvcHealth(name, route) {
    if (!_rmSvcLoaded || !name) return '';
    const proto = ((route && route.protocol) || 'http') + ':';
    const prov  = (route && route.provider) || 'file';
    const st = _rmSvcStatus[proto + _rmQualify(name, prov)]
            || _rmSvcStatus[proto + name]
            || null;
    if (!st || !st.total) return '';
    if (st.up === 0) return 'down';
    return st.up < st.total ? 'warn' : 'up';
}

function _rmNodeHtml(kind, id, ctx) {
    ctx = ctx || {};
    if (kind === 'ep') {
        const epP = (ctx.proto || '').toLowerCase();
        return rmNode(epP ? 'ep ' + epP : 'ep', id,
            `<i class="ph-bold ph-door-open rm-node-ic"></i><span class="rm-node-label">${_esc(id)}</span>`);
    }
    if (kind === 'mw') {
        const n = (ctx.mwUsage || {})[id] || 0;
        const badge = n > 1 ? `<span class="rm-mw-count">${n}\u00d7</span>` : '';
        return rmNode('mw', id,
            `<i class="ph-bold ph-stack rm-node-ic"></i><span class="rm-node-label">${_esc(String(id).split('@')[0])}</span>${badge}`);
    }
    if (kind === 'svc') {
        const h = _rmSvcHealth(id, ctx.route);
        return rmNode('svc', id,
            `<i class="ph-bold ph-hard-drives rm-node-ic"></i><span class="rm-node-label">${_esc(String(id).split('@')[0])}</span>`
            + (h ? `<span class="rm-node-dot rm-dot-${h}"></span>` : ''),
            null, ctx.target, h);
    }
    if (kind === 'group') {
        return rmNode('group', id,
            `<i class="ph-bold ph-squares-four rm-node-ic"></i><span class="rm-node-label">${_esc(ctx.label || id)}</span>`
            + `<span class="rm-mw-count">${ctx.count || 0}</span>`, null, ctx.title || '');
    }
    const r = ctx.route || {};
    const proto = (r.protocol || 'http').toLowerCase();
    const h = _rmRouteHealth(r);
    return rmNode('route ' + proto, r.id,
        `<span class="rm-proto-badge rm-proto-${_esc(proto)}">${proto.toUpperCase()}</span>`
        + `<span class="rm-node-label">${_esc(r.name)}</span>`
        + (h ? `<span class="rm-node-dot rm-dot-${h}"></span>` : ''),
        r.id, null, h);
}

function _rmMeasure(html, cls) {
    let box = document.getElementById('rmMeasure');
    if (!box) {
        box = document.createElement('div');
        box.id = 'rmMeasure';
        box.style.cssText = 'position:absolute;visibility:hidden;pointer-events:none;left:-9999px;top:0;';
        document.body.appendChild(box);
    }
    box.className = cls || '';
    box.innerHTML = html;
    const el = box.firstElementChild;
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { width: Math.ceil(r.width), height: Math.ceil(r.height) };
}

function rmHighlightRoute(routeId, routes) {
    const route = routes.find(r => r.id === routeId);
    if (!route) return;
    document.querySelectorAll('#rmCols .rm-node').forEach(n => {
        const id = n.dataset.rmid || '';
        let active = false;
        if (id === `route:${routeId}`)               active = true;
        else if (id.startsWith('ep:'))               active = _rmEps(route).includes(id.slice(3));
        else if (id.startsWith('mw:'))               active = (route.middlewares||[]).includes(id.slice(3));
        else if (id === `svc:${route.service_name}`) active = true;
        n.classList.toggle('rm-node-active', active);
        n.classList.toggle('rm-node-dim', !active);
    });
    rmDrawCurves([route]);
    setTimeout(() => rmDrawCurves([route]), 210);
}

function rmHighlightNode(type, nodeId, routes) {
    const connected = routes.filter(r => {
        if (type === 'ep')  return _rmEps(r).includes(nodeId);
        if (type === 'mw')  return (r.middlewares  || []).includes(nodeId);
        if (type === 'svc') return r.service_name === nodeId;
        return false;
    });
    if (!connected.length) return;
    const activeRouteIds = new Set(connected.map(r => r.id));
    const activeEps      = new Set(connected.flatMap(r => _rmEps(r)));
    const activeMws      = new Set(connected.flatMap(r => r.middlewares  || []));
    const activeSvcs     = new Set(connected.map(r => r.service_name).filter(Boolean));
    document.querySelectorAll('#rmCols .rm-node').forEach(n => {
        const id = n.dataset.rmid || '';
        const gid = n.dataset.groupid || '';
        let active = false;
        if      (id.startsWith('route:')) active = activeRouteIds.has(id.slice(6));
        else if (id.startsWith('ep:'))    active = activeEps.has(id.slice(3));
        else if (id.startsWith('mw:'))    active = activeMws.has(id.slice(3));
        else if (id.startsWith('svc:'))   active = activeSvcs.has(id.slice(4));
        else if (gid) active = connected.some(r => _rmRouteGroupKey.get(r.id) === gid);
        n.classList.toggle('rm-node-active', active);
        n.classList.toggle('rm-node-dim', !active);
    });
    rmDrawCurves(connected, true);
    setTimeout(() => rmDrawCurves(connected, true), 210);
}

function rmOpenPopup(type, nodeId, allRoutes, preFiltered) {
    _rmPopupOpen = true;
    window.rmResetHighlight();

    const overlay = document.getElementById('rmPopupOverlay');
    const popup   = document.getElementById('rmPopup');
    if (!popup) return;

    const typeLabels = { ep: 'Entry Point', mw: 'Middleware', svc: 'Service', route: 'Route', group: 'Group' };
    const typeIcons  = { ep: 'ph-arrows-in', mw: 'ph-shield-check', svc: 'ph-hard-drives',
                         route: 'ph-arrows-split', group: 'ph-stack' };
    document.getElementById('rmPopupTypeBadge').textContent = typeLabels[type] || type;
    document.getElementById('rmPopupTitle').textContent     = nodeId.split('@')[0];
    const popIcon = document.getElementById('rmPopupIcon');
    if (popIcon) popIcon.className = 'ph-fill ' + (typeIcons[type] || 'ph-graph');

    const chip = (icon, label, val, color) => {
        if (!val) return '';
        const c = color ? `style="color:${color};border-color:${color}44;background:${color}11"` : '';
        return `<span class="rm-detail-chip" ${c}><i class="ph-bold ${icon}"></i><span>${label}</span><b>${_esc(String(val))}</b></span>`;
    };

    let focusedRoutes = [];
    let detailsHtml   = '';

    if (type === 'group') {
        focusedRoutes = preFiltered || [];
        detailsHtml   = chip('ph-git-branch', 'Routes', focusedRoutes.length);
    } else if (type === 'route') {
        const r = allRoutes.find(r => r.id === nodeId);
        if (!r) return;
        focusedRoutes = [r];
        const allDomains = [...(r.rule||'').matchAll(/Host\(`([^`]+)`\)/g)].map(m => m[1]);
        allDomains.forEach(d => { detailsHtml += chip('ph-globe', 'Domain', d); });
        if (r.target && r.target !== 'N/A') detailsHtml += chip('ph-cube', 'Target', r.target);
        detailsHtml += chip('ph-arrows-left-right', 'Protocol', (r.protocol||'http').toUpperCase());
        _rmEps(r).forEach(ep => { detailsHtml += chip('ph-arrows-in', 'Entry Point', ep); });
        if (r.tls)          detailsHtml += chip('ph-lock', 'TLS', 'Enabled');
        if (r.certResolver) detailsHtml += chip('ph-certificate', 'Resolver', r.certResolver);
        if (!r.enabled)     detailsHtml += chip('ph-eye-slash', 'Status', 'Inactive');
        if (r.provider && r.provider !== 'file') detailsHtml += chip('ph-package', 'Provider', r.provider);
    } else if (type === 'ep') {
        focusedRoutes = allRoutes.filter(r => _rmEps(r).includes(nodeId));
        const addr = _rmAllEps[nodeId]?.address || '';
        if (addr) detailsHtml += chip('ph-plugs-connected', 'Address', addr);
        detailsHtml += chip('ph-git-branch', 'Routes', focusedRoutes.length);
    } else if (type === 'mw') {
        focusedRoutes = allRoutes.filter(r => (r.middlewares||[]).includes(nodeId));
        detailsHtml   = chip('ph-git-branch', 'Routes', focusedRoutes.length);
    } else if (type === 'svc') {
        focusedRoutes = allRoutes.filter(r => r.service_name === nodeId);
        const target  = focusedRoutes.find(r => r.target && r.target !== 'N/A')?.target || '';
        if (target) detailsHtml += chip('ph-cube', 'Target', target);
        detailsHtml += chip('ph-git-branch', 'Routes', focusedRoutes.length);
    }

    document.getElementById('rmPopupDetails').innerHTML = detailsHtml;

    window._rmPopupAllRoutes = allRoutes;
    window._rmPopupFocused   = focusedRoutes;

    rmRenderPopupTopology(focusedRoutes, type, nodeId, allRoutes);

    overlay.style.display = 'block';
    popup.style.display   = 'flex';
}

function rmRenderPopupTopology(focusedRoutes, activeType, activeNodeId, allRoutes) {
    const cols = document.getElementById('rmPopupCols');
    const cont = document.getElementById('rmPopupTopoContainer');
    if (!cols || !cont) return;

    const { g, mwUsage } = _rmBuildDagre(focusedRoutes);
    const gl = g.graph();
    const W = Math.ceil(gl.width)  + 1;
    const H = Math.ceil(gl.height) + 1;

    const padding   = 32;
    const maxW      = Math.floor(window.innerWidth * 0.92);
    const popupW    = Math.min(W + padding * 2, maxW);
    const popupEl   = document.getElementById('rmPopup');
    if (popupEl) popupEl.style.width = popupW + 'px';

    cols.innerHTML = '';
    cols.style.display   = 'block';
    cols.style.position  = 'relative';
    cols.style.height    = H + 'px';
    cont.style.height    = H + 'px';
    cont.style.overflow  = 'visible';

    const svg = document.getElementById('rmPopupSvg');
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
    svg.setAttribute('width',  W);
    svg.setAttribute('height', H);

    g.nodes().forEach(v => {
        const nd = g.node(v);
        if (!nd) return;
        const left = Math.round(nd.x - nd.width / 2);
        const top  = Math.round(nd.y - nd.height / 2);
        const wrap = document.createElement('div');
        wrap.style.cssText = `position:absolute;left:${left}px;top:${top}px;width:${nd.width}px`;

        const isActive = activeType === nd.type && activeNodeId === nd.id;
        const poprmid  = `${nd.type}:${nd.id}`;

        wrap.innerHTML = _rmNodeHtml(nd.type, nd.id, {
            mwUsage,
            route:  nd.route || nd.owner,
            target: nd.target,
        });
        const nodeEl = wrap.firstElementChild;
        if (nodeEl) {
            nodeEl.dataset.poprmid = poprmid;
            nodeEl.style.cursor = 'pointer';
            if (isActive) nodeEl.classList.add('rm-node-active');
        }
        cols.appendChild(wrap);
    });

    requestAnimationFrame(() => {
        rmDrawPopupCurves(focusedRoutes);
        setTimeout(() => rmDrawPopupCurves(focusedRoutes), 150);

        cols.querySelectorAll('[data-poprmid]').forEach(el => {
            const rmid   = el.dataset.poprmid || '';
            const colon  = rmid.indexOf(':');
            if (colon === -1) return;
            const ntype  = rmid.slice(0, colon);
            const nid    = rmid.slice(colon + 1);
            el.addEventListener('mouseenter', function() {
                if (ntype === 'route') rmPopupHighlightRoute(nid, focusedRoutes);
                else rmPopupHighlightNode(ntype, nid, focusedRoutes);
            });
            el.addEventListener('mouseleave', function() {
                cols.querySelectorAll('[data-poprmid]').forEach(n => n.classList.remove('rm-node-dim','rm-node-active'));
                rmDrawPopupCurves(focusedRoutes);
            });
            el.addEventListener('click', function(e) {
                e.stopPropagation();
                rmClosePopup();
                setTimeout(() => rmOpenPopup(ntype, nid, allRoutes), 50);
            });
        });
    });
}


function rmPopupHighlightRoute(routeId, routes) {
    const route = routes.find(r => r.id === routeId);
    if (!route) return;
    document.querySelectorAll('#rmPopupCols [data-poprmid]').forEach(n => {
        const id = n.dataset.poprmid || '';
        let active = false;
        if (id === `route:${routeId}`)               active = true;
        else if (id.startsWith('ep:'))               active = _rmEps(route).includes(id.slice(3));
        else if (id.startsWith('mw:'))               active = (route.middlewares||[]).includes(id.slice(3));
        else if (id === `svc:${route.service_name}`) active = true;
        n.classList.toggle('rm-node-active', active);
        n.classList.toggle('rm-node-dim', !active);
    });
    rmDrawPopupCurves([route]);
}

function rmPopupHighlightNode(type, nodeId, routes) {
    const connected = routes.filter(r => {
        if (type === 'ep')  return (r.entryPoints||[]).includes(nodeId);
        if (type === 'mw')  return (r.middlewares||[]).includes(nodeId);
        if (type === 'svc') return r.service_name === nodeId;
        return false;
    });
    const activeRouteIds = new Set(connected.map(r => r.id));
    const activeEps      = new Set(connected.flatMap(r => r.entryPoints||[]));
    const activeMws      = new Set(connected.flatMap(r => r.middlewares||[]));
    const activeSvcs     = new Set(connected.map(r => r.service_name).filter(Boolean));
    document.querySelectorAll('#rmPopupCols [data-poprmid]').forEach(n => {
        const id = n.dataset.poprmid || '';
        let active = false;
        if      (id.startsWith('route:')) active = activeRouteIds.has(id.slice(6));
        else if (id.startsWith('ep:'))    active = activeEps.has(id.slice(3));
        else if (id.startsWith('mw:'))    active = activeMws.has(id.slice(3));
        else if (id.startsWith('svc:'))   active = activeSvcs.has(id.slice(4));
        n.classList.toggle('rm-node-active', active);
        n.classList.toggle('rm-node-dim', !active);
    });
    rmDrawPopupCurves(connected);
}

function rmDrawPopupCurves(routes) {
    const svg  = document.getElementById('rmPopupSvg');
    const cont = document.getElementById('rmPopupTopoContainer');
    if (!svg || !cont) return;

    const cr = cont.getBoundingClientRect();
    svg.setAttribute('viewBox', `0 0 ${cr.width} ${cr.height}`);
    svg.setAttribute('width',  cr.width);
    svg.setAttribute('height', cr.height);
    svg.innerHTML = '';

    const get = id => cont.querySelector(`[data-poprmid="${CSS.escape(id)}"]`);

    const allPopupRoutes = window._rmPopupFocused || [];
    const hl = routes.length < allPopupRoutes.length;

    const curve = (fromEl, toEl, color, opacity) => {
        if (!fromEl || !toEl) return;
        const f  = fromEl.getBoundingClientRect();
        const t  = toEl.getBoundingClientRect();
        const x1 = f.right - cr.left;
        const y1 = f.top + f.height / 2 - cr.top;
        const x2 = t.left  - cr.left;
        const y2 = t.top + t.height / 2 - cr.top;
        const cx = x1 + (x2 - x1) * 0.5;
        const p  = document.createElementNS('http://www.w3.org/2000/svg','path');
        p.setAttribute('d', `M${x1},${y1} C${cx},${y1} ${cx},${y2} ${x2},${y2}`);
        p.setAttribute('fill','none');
        p.setAttribute('stroke', color);
        p.setAttribute('stroke-width', '1.5');
        p.setAttribute('stroke-opacity', opacity);
        svg.appendChild(p);
    };

    const popProtoColor = proto => proto === 'tcp' ? 'var(--green)' : proto === 'udp' ? 'rgba(226,192,65,1)' : 'var(--blue)';

    allPopupRoutes.forEach(r => {
        const active = !hl || routes.some(ar => ar.id === r.id);
        const rEl    = get(`route:${r.id}`);
        const mws    = r.middlewares || [];
        const rc     = active ? popProtoColor(r.protocol) : 'var(--border)';
        (r.entryPoints||[]).forEach(ep => curve(get(`ep:${ep}`), rEl, active ? 'var(--teal)' : 'var(--border)', active ? '0.6' : '0.2'));
        if (mws.length) {
            mws.forEach(mw => curve(rEl, get(`mw:${mw}`), active ? 'var(--purple)' : 'var(--border)', active ? '0.6' : '0.2'));
            if (r.service_name) mws.forEach(mw => curve(get(`mw:${mw}`), get(`svc:${r.service_name}`), rc, active ? '0.5' : '0.2'));
        } else if (r.service_name) {
            curve(rEl, get(`svc:${r.service_name}`), rc, active ? '0.6' : '0.2');
        }
    });
}

window.rmClosePopup = function() {
    _rmPopupOpen = false;
    document.getElementById('rmPopupOverlay').style.display = 'none';
    const p = document.getElementById('rmPopup');
    p.style.display = 'none';
    p.style.width   = '';
    window.rmResetHighlight();
};

function rmDrawCurves(routes, forceHighlight) {
    const svg  = document.getElementById('rmSvg');
    const cont = document.getElementById('rmTopoContainer');
    const g    = _rmDagreGraph;
    if (!svg || !cont || !g) return;

    svg.innerHTML = '';

    const useMobile = !!document.getElementById('rmPanInner');
    let getNodePos;
    if (useMobile) {
        const colsEl = document.getElementById('rmCols');
        svg.setAttribute('width',   _rmDagreW);
        svg.setAttribute('height',  _rmDagreH);
        svg.setAttribute('viewBox', `0 0 ${_rmDagreW} ${_rmDagreH}`);
        getNodePos = el => {
            let x = 0, y = 0, node = el;
            while (node && node !== colsEl && node !== cont) {
                x += node.offsetLeft; y += node.offsetTop;
                node = node.offsetParent;
            }
            return { x1: x + el.offsetWidth, yc: y + el.offsetHeight / 2,
                     x2: x,                   yc2: y + el.offsetHeight / 2 };
        };
    } else {
        const cr = cont.getBoundingClientRect();
        svg.setAttribute('width',   cr.width);
        svg.setAttribute('height',  cr.height);
        svg.setAttribute('viewBox', `0 0 ${cr.width} ${cr.height}`);
        getNodePos = el => {
            const f = el.getBoundingClientRect();
            return { x1: f.right - cr.left, yc:  f.top + f.height / 2 - cr.top,
                     x2: f.left  - cr.left, yc2: f.top + f.height / 2 - cr.top };
        };
    }

    const hl = forceHighlight || _rmTopoSelected !== null;
    const DC = 'var(--border)';
    const DO = '0.2';

    const activeRouteIds = new Set(routes.map(r => r.id));
    const activeEps  = new Set(routes.flatMap(r => r.entryPoints||[]));
    const activeMws  = new Set(routes.flatMap(r => r.middlewares||[]));
    const activeSvcs = new Set(routes.filter(r => r.service_name).map(r => r.service_name));

    const edgeColor = {
        'ep-route':  'var(--teal)',
        'route-mw':  'var(--purple)',
        'mw-svc':    'var(--orange)',
        'route-svc': 'var(--orange)',
    };

    const getEl = rmid => {
        let el = cont.querySelector(`[data-rmid="${CSS.escape(rmid)}"]`);
        if (!el && rmid.startsWith('route:')) {
            const gk = _rmRouteGroupKey?.get(rmid.slice(6));
            if (gk && !_rmExpandedGroups?.has(gk))
                el = cont.querySelector(`.rm-node-group[data-groupid="${CSS.escape(gk)}"]`);
        }
        return el;
    };

    const drawn = new Set();

    g.edges().forEach(e => {
        const edge = g.edge(e);
        if (!edge) return;
        const type = edge.type || 'route-svc';

        let isActive = !hl;
        if (hl) {
            if (type === 'ep-route')  isActive = activeEps.has(e.v.slice(3))  && activeRouteIds.has(e.w.slice(6));
            if (type === 'route-mw')  isActive = activeMws.has(e.w.slice(3));
            if (type === 'mw-svc')    isActive = activeMws.has(e.v.slice(3))  && activeSvcs.has(e.w.slice(4));
            if (type === 'route-svc') isActive = activeSvcs.has(e.w.slice(4));
        }

        const fromEl = getEl(e.v);
        const toEl   = getEl(e.w);
        if (!fromEl || !toEl) return;

        const key = (fromEl.dataset.rmid || fromEl.dataset.groupid || '') + '→' + (toEl.dataset.rmid || toEl.dataset.groupid || '');
        if (drawn.has(key)) return;
        drawn.add(key);

        const activeColor = edgeColor[type];

        const fp = getNodePos(fromEl);
        const tp = getNodePos(toEl);
        const x1 = fp.x1, y1 = fp.yc, x2 = tp.x2, y2 = tp.yc2;
        const cx = x1 + (x2 - x1) * 0.5;

        const p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        p.setAttribute('d', `M${x1},${y1} C${cx},${y1} ${cx},${y2} ${x2},${y2}`);
        p.setAttribute('fill',           'none');
        p.setAttribute('stroke',         isActive ? activeColor : DC);
        p.setAttribute('stroke-width',   '1.5');
        p.setAttribute('stroke-opacity', isActive ? (type === 'mw-svc' ? '0.5' : '0.6') : DO);
        svg.appendChild(p);
    });
}

let _rmTipEl = null;

function rmShowTooltip(anchorEl, routeId, routes) {
    const route = routes.find(r => r.id === routeId);
    if (!route) return;

    if (!_rmTipEl) {
        _rmTipEl = document.createElement('div');
        _rmTipEl.className = 'rm-tooltip';
        document.body.appendChild(_rmTipEl);
    }

    const mws    = route.middlewares || [];
    const eps    = route.entryPoints || [];
    const mwHtml = mws.length
        ? mws.map(m => `<span class="rm-mw-pill">${_esc(m.split('@')[0])}</span>`).join('')
        : `<span style="color:var(--muted);font-size:10px">none</span>`;
    const epHtml = eps.length
        ? eps.map(e => `<span class="rm-shield-pill">${_esc(e)}</span>`).join('')
        : `<span style="color:var(--muted);font-size:10px">none</span>`;

    _rmTipEl.innerHTML = `
        <div class="rm-tooltip-name">${_esc(route.name)}</div>
        ${route.target ? `<div class="rm-tooltip-row"><span class="rm-tooltip-label">Target</span><code>${_esc(route.target)}</code></div>` : ''}
        <div class="rm-tooltip-row"><span class="rm-tooltip-label">Entry points</span><div class="rm-mw-pills">${epHtml}</div></div>
        <div class="rm-tooltip-row"><span class="rm-tooltip-label">Middlewares</span><div class="rm-mw-pills">${mwHtml}</div></div>
        <div style="margin-top:6px;font-size:10px;color:var(--muted);opacity:0.7">Click to inspect</div>
    `;

    const rect = anchorEl.getBoundingClientRect();
    _rmTipEl.style.display = 'block';
    const tipH = _rmTipEl.offsetHeight;
    const top  = rect.top + window.scrollY - tipH - 8;
    _rmTipEl.style.left = rect.left + window.scrollX + 'px';
    _rmTipEl.style.top  = (top < 8 ? rect.bottom + window.scrollY + 8 : top) + 'px';
}

function rmShowNodeTooltip(anchorEl, type, nodeId, routes) {
    const connected = routes.filter(r => {
        if (type === 'ep')  return (r.entryPoints || []).includes(nodeId);
        if (type === 'mw')  return (r.middlewares  || []).includes(nodeId);
        if (type === 'svc') return r.service_name === nodeId;
        return false;
    });
    if (!_rmTipEl) {
        _rmTipEl = document.createElement('div');
        _rmTipEl.className = 'rm-tooltip';
        document.body.appendChild(_rmTipEl);
    }
    const label = type === 'ep' ? 'Entry Point' : type === 'mw' ? 'Middleware' : 'Service';
    const routeList = connected.length
        ? connected.map(r => `<span class="rm-shield-pill">${_esc(r.name)}</span>`).join('')
        : `<span style="color:var(--muted);font-size:10px">none</span>`;
    _rmTipEl.innerHTML = `
        <div class="rm-tooltip-name">${_esc(nodeId.split('@')[0])}</div>
        <div class="rm-tooltip-row"><span class="rm-tooltip-label">${label}</span></div>
        <div class="rm-tooltip-row"><span class="rm-tooltip-label">Used by</span><div class="rm-mw-pills">${routeList}</div></div>
        <div style="margin-top:6px;font-size:10px;color:var(--muted);opacity:0.7">Click to inspect</div>
    `;
    const rect = anchorEl.getBoundingClientRect();
    _rmTipEl.style.display = 'block';
    const tipH = _rmTipEl.offsetHeight;
    const top  = rect.top + window.scrollY - tipH - 8;
    _rmTipEl.style.left = rect.left + window.scrollX + 'px';
    _rmTipEl.style.top  = (top < 8 ? rect.bottom + window.scrollY + 8 : top) + 'px';
}

function rmHideTooltip() {
    if (_rmTipEl) _rmTipEl.style.display = 'none';
}

function _rmTouchLayout() {
    try {
        if (window.matchMedia('(pointer: coarse)').matches) return true;
    } catch (e) {}
    return window.innerWidth <= 640;
}
let _rmZScale = 1, _rmZPanX = 0, _rmZPanY = 0;
let _rmZTouchX = 0, _rmZTouchY = 0, _rmZPinchDist = null;
let _rmZoomInited = false;

function rmApplyPanZoom() {
    const inner = document.getElementById('rmPanInner');
    if (inner) inner.style.transform = `translate(${_rmZPanX}px,${_rmZPanY}px) scale(${_rmZScale})`;
    const pct = document.getElementById('rmZoomPct');
    if (pct) pct.textContent = Math.round(_rmZScale * 100) + '%';
}

function rmZoomBy(factor) {
    const cont = document.getElementById('rmTopoContainer');
    if (!cont) return;
    const cx = cont.clientWidth / 2, cy = cont.clientHeight / 2;
    const ns = Math.max(0.15, Math.min(4, _rmZScale * factor));
    _rmZPanX = cx - (cx - _rmZPanX) * (ns / _rmZScale);
    _rmZPanY = cy - (cy - _rmZPanY) * (ns / _rmZScale);
    _rmZScale = ns;
    rmApplyPanZoom();
}

window.rmZoomBy = rmZoomBy;

window.rmZoomReset = function() {
    const cont = document.getElementById('rmTopoContainer');
    const svg  = document.getElementById('rmSvg');
    if (!cont || !svg) return;
    const mapW = parseFloat(svg.getAttribute('width') || '0');
    const mapH = parseFloat(svg.getAttribute('height') || '0');
    if (!mapW || !mapH) { _rmZScale = 1; _rmZPanX = 0; _rmZPanY = 0; }
    else {
        const fitScale = Math.min(cont.clientWidth / mapW, cont.clientHeight / mapH, 1);
        _rmZScale = fitScale;
        _rmZPanX  = (cont.clientWidth  - mapW * fitScale) / 2;
        _rmZPanY  = 12;
    }
    rmApplyPanZoom();
};

function rmInitMobilePan() {
    if (!_rmTouchLayout()) return;
    const cont = document.getElementById('rmTopoContainer');
    const svg  = document.getElementById('rmSvg');
    if (!cont || !svg) return;

    const viewH = Math.round(window.innerHeight * 0.62);
    cont.style.height   = viewH + 'px';
    cont.style.overflow = 'hidden';
    cont.style.cursor   = 'grab';
    cont.style.minHeight = viewH + 'px';

    if (!document.getElementById('rmPanInner')) {
        const cols  = document.getElementById('rmCols');
        const inner = document.createElement('div');
        inner.id = 'rmPanInner';
        inner.style.cssText = 'position:absolute;top:0;left:0;transform-origin:0 0;will-change:transform';
        cont.insertBefore(inner, svg);
        inner.appendChild(svg);
        inner.appendChild(cols);
    }

    window.rmZoomReset();

    const bar = document.getElementById('rmMobileZoomBar');
    if (bar) bar.classList.remove('hidden');

    if (_rmZoomInited) return;
    _rmZoomInited = true;

    cont.addEventListener('touchstart', e => {
        rmHideTooltip();
        if (e.touches.length === 1) {
            _rmZTouchX = e.touches[0].clientX - _rmZPanX;
            _rmZTouchY = e.touches[0].clientY - _rmZPanY;
            _rmZPinchDist = null;
        } else if (e.touches.length === 2) {
            _rmZPinchDist = Math.hypot(
                e.touches[0].clientX - e.touches[1].clientX,
                e.touches[0].clientY - e.touches[1].clientY
            );
        }
    }, { passive: true });

    cont.addEventListener('touchmove', e => {
        e.preventDefault();
        if (e.touches.length === 1 && _rmZPinchDist === null) {
            _rmZPanX = e.touches[0].clientX - _rmZTouchX;
            _rmZPanY = e.touches[0].clientY - _rmZTouchY;
        } else if (e.touches.length === 2 && _rmZPinchDist !== null) {
            const dist = Math.hypot(
                e.touches[0].clientX - e.touches[1].clientX,
                e.touches[0].clientY - e.touches[1].clientY
            );
            const cx = (e.touches[0].clientX + e.touches[1].clientX) / 2;
            const cy = (e.touches[0].clientY + e.touches[1].clientY) / 2;
            const rect = cont.getBoundingClientRect();
            const ns = Math.max(0.15, Math.min(4, _rmZScale * (dist / _rmZPinchDist)));
            _rmZPanX = (cx - rect.left) - ((cx - rect.left) - _rmZPanX) * (ns / _rmZScale);
            _rmZPanY = (cy - rect.top)  - ((cy - rect.top)  - _rmZPanY) * (ns / _rmZScale);
            _rmZScale = ns;
            _rmZPinchDist = dist;
        }
        rmApplyPanZoom();
    }, { passive: false });

    cont.addEventListener('touchend', () => { _rmZPinchDist = null; });
}

let _rmLastW = 0, _rmReflowTimer = null;

function _rmReflow() {
    if (!document.getElementById('tab-routemap')?.classList.contains('active')) return;
    const cont = document.getElementById('rmTopoContainer');
    if (!cont) return;
    const w = Math.round(cont.clientWidth);
    if (!w || Math.abs(w - _rmLastW) < 8) return;
    _rmLastW = w;
    clearTimeout(_rmReflowTimer);
    _rmReflowTimer = setTimeout(() => {
        if (_rmDrawn && _rmFilteredRoutes().length) rmRender();
    }, 90);
}

let _rmLastWidth = window.innerWidth;

window.addEventListener('resize', () => {
    if (!document.getElementById('tab-routemap')?.classList.contains('active')) return;
    const cont   = document.getElementById('rmTopoContainer');
    const colsEl = document.getElementById('rmCols');
    const rotated = window.innerWidth !== _rmLastWidth;
    _rmLastWidth = window.innerWidth;
    if (cont && colsEl) cont.style.height = colsEl.offsetHeight + 'px';
    rmDrawCurves(_rmFilteredRoutes());
    if (_rmTouchLayout() && cont) {
        cont.style.height = Math.round(window.innerHeight * 0.62) + 'px';
        if (!document.getElementById('rmPanInner')) rmInitMobilePan();
        else if (rotated) window.rmZoomReset();
    }
    _rmReflow();
});

if (typeof ResizeObserver !== 'undefined') {
    const startRmObserver = () => {
        const cont = document.getElementById('rmTopoContainer');
        if (!cont) { setTimeout(startRmObserver, 400); return; }
        _rmLastW = Math.round(cont.clientWidth);
        new ResizeObserver(_rmReflow).observe(cont);
    };
    startRmObserver();
}

document.addEventListener('click', e => {
    const wrap = document.getElementById('rmFilterWrap');
    if (wrap && !wrap.contains(e.target)) {}
});

document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && _rmPopupOpen) window.rmClosePopup();
});

window.rmInvalidateData = function() {
    _rmDataLoaded = false;
    _rmDrawn = false;
    if (typeof window.rmInvalidateDashboard === 'function') window.rmInvalidateDashboard();
};

})();

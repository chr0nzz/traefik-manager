const ATK_CELL_CAP     = 240;
const ATK_ROW_CELL_CAP = 20;
const ATK_ROW_CAP      = 6;
const ATK_FEED_PAGE    = 20;
const ATK_EV_CAP       = 400;
const ATK_SUBSCRIBED   = { capi: 1, lists: 1 };
const ATK_BY_HAND      = { cscli: 1, manual: 1 };
let _csDecStale = '';
const ATK_ALERT_ONLY   = { asn: 1, cc: 1, uri: 1, user: 1, agent: 1, verb: 1, router: 1, host: 1, outcome: 1 };
const ATK_PULL_SCOPE   = /^(capi|lists)$/i;
const ATK_DEC_ONLY     = { origin: 1, type: 1 };

let _csDecSum     = null;
let _csVersion    = '';
let _csPaintedKey = '';
let _csDecPage    = null;
let _csDecKey     = '';
let _csPollTimer  = null;
const CS_POLL_MS  = 60000;
let _csAlerts     = [];
let _csLapiOk     = false;
let _csAlertsOk   = false;
let _csAltStatus  = 0;

function _csLimitParam() {
    const n = parseInt(window._tmAlertLimit || '0', 10);
    return (_activeAgent && n > 0) ? ('limit=' + n) : '';
}
let _csAltCapped  = false;
let _csAltLimit   = 0;
let _csAltErr     = '';
let _csDecErr     = '';
let _csFetched    = 0;
let _csSpan       = 0;
let _csHostGeo    = false;
let _csConfigured = true;
let _csBanType    = 'ban';
let _csAgeTimer   = null;
let _csSearchTimer = null;

const _atkFacet = { scenario: '', ip: '', asn: '', cc: '', uri: '', user: '', agent: '', verb: '', router: '', host: '', origin: '', type: '', outcome: '' };
let _atkView  = 'alerts';
let _atkPage  = 1;
let _atkOpen  = '';
let _atkQuery = '';

function _scenShort(s) { return String(s || '').replace(/^crowdsecurity\//, ''); }

function _uaShort(ua) {
    const s = String(ua || '');
    const inner = s.match(/\(compatible; ([A-Za-z0-9_.\-]+\/[0-9][^;)]*)/);
    if (inner) return inner[1];
    let m = s.match(/HeadlessChrome\/([0-9]+)/);
    if (m) return 'HeadlessChrome/' + m[1];
    m = s.match(/(Chrome|Firefox|Safari|Edg)\/([0-9]+)/);
    if (m) return m[1] + '/' + m[2];
    m = s.match(/^([A-Za-z0-9_.\-]+\/[0-9][^ )#]*)/);
    if (m) return m[1];
    return s.length > 26 ? s.slice(0, 25) + '...' : s;
}

function _atkClip(s, n) {
    const v = String(s || '');
    return v.length > n ? v.slice(0, n - 1) + '...' : v;
}

let _csRegionNames = null;
function _csCountryName(cc) {
    if (!cc) return '';
    if (typeof _geoNames !== 'undefined' && _geoNames[cc]) return _geoNames[cc];
    if (_csRegionNames === null) {
        try { _csRegionNames = new Intl.DisplayNames(['en'], { type: 'region' }); }
        catch (_) { _csRegionNames = false; }
    }
    if (_csRegionNames) {
        try { return _csRegionNames.of(cc) || cc; } catch (_) { return cc; }
    }
    return cc;
}

function _atkStamp(ms) {
    if (!ms) return 'unknown';
    const d = new Date(ms);
    const p = n => String(n).padStart(2, '0');
    return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate())
        + ' ' + p(d.getHours()) + ':' + p(d.getMinutes()) + ':' + p(d.getSeconds());
}

function _atkHhmm(ms) {
    if (!ms) return '--:--';
    const d = new Date(ms);
    return String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0');
}

function _atkPct(n, total) {
    const p = total ? (n / total * 100) : 0;
    return p >= 10 ? String(Math.round(p)) : String(Math.round(p * 10) / 10);
}

function _atkMetaMap(raw) {
    const out = {};
    if (!Array.isArray(raw)) return out;
    raw.forEach(m => {
        if (!m || !m.key) return;
        let arr = null;
        try { arr = JSON.parse(m.value); } catch (_) { arr = null; }
        if (!Array.isArray(arr)) arr = (m.value === undefined || m.value === null || m.value === '') ? [] : [m.value];
        const vals = arr.map(v => String(v)).filter(Boolean);
        if (vals.length) out[m.key] = (out[m.key] || []).concat(vals);
    });
    return out;
}

function _atkCc(v) {
    const s = String(v == null ? '' : v);
    return /^[A-Za-z]{2}$/.test(s) ? s.toUpperCase() : '';
}

function _atkParseAlert(a, i) {
    const s = (a && a.source) || {};
    const meta = _atkMetaMap(a && a.meta);
    const cn = _atkCc(s.cn);
    const start = Date.parse(a.start_at || a.created_at || '');
    const stopRaw = Date.parse(a.stop_at || '');
    const st = isNaN(start) ? 0 : start;
    return {
        uuid: String(a.uuid || a.id || ('cs' + i)),
        scenario: a.scenario || 'unknown',
        version: a.scenario_version || '',
        events: Math.max(0, Number(a.events_count) || 0),
        capacity: Math.max(0, Number(a.capacity) || 0),
        leakspeed: String(a.leakspeed || ''),
        simulated: a.simulated === true,
        machine: a.machine_id || '',
        message: a.message || '',
        start: st,
        stop: isNaN(stopRaw) ? st : stopRaw,
        ip: s.ip || s.value || '',
        scope: s.scope || 'Ip',
        cn: cn,
        cc: cn,
        asName: s.as_name || '',
        asNum: (s.as_number === undefined || s.as_number === null || s.as_number === '') ? '' : String(s.as_number),
        range: s.range || '',
        lat: (typeof s.latitude === 'number') ? s.latitude : null,
        lon: (typeof s.longitude === 'number') ? s.longitude : null,
        routers: meta.traefik_router_name_leaf || meta.traefik_router_name || [],
        hosts: meta.target_fqdn || [],
        uris: meta.target_uri || [],
        users: meta.target_user || [],
        verbs: meta.method || [],
        codes: meta.status || [],
        uas: meta.user_agent || [],
        handled: false,
        known: false,
    };
}

function _atkParseDecision(d) {
    return {
        id: Number(d.id) || 0,
        value: d.value || '',
        type: d.type || 'ban',
        scope: d.scope || 'Ip',
        origin: String(d.origin || '').toLowerCase(),
        scenario: d.scenario || '',
        duration: d.duration || '',
        own: !ATK_SUBSCRIBED[String(d.origin || '').toLowerCase()],
    };
}

function _atkFlag(f) {
    const dead = !f.go;
    const tag = f.tag === 'span' || dead;
    return (tag ? '<span' : '<button type="button"')
        + ' class="sig-flag ' + f.cls + (f.extra ? ' ' + f.extra : '') + (dead ? ' lg-static' : '') + '"'
        + (dead ? '' : ' data-atk="' + _esc(f.go) + '"')
        + ' title="' + _esc(f.tip || (f.n + ' ' + f.label)) + '">'
        + '<i class="' + f.ic + '"></i>'
        + (f.n === '' ? '' : '<b>' + _sdNum(f.n) + '</b>')
        + (f.label && f.words !== false ? '<span class="sig-fl">' + _esc(f.label) + '</span>' : '')
        + (tag ? '</span>' : '</button>');
}

function _atkProv(p) {
    const dead = p.n === 0 || !p.go;
    return (dead ? '<span' : '<button type="button"')
        + ' class="sig-prov' + (p.cls ? ' ' + p.cls : '') + (dead ? ' lg-static' : '') + '"'
        + (dead ? '' : ' data-atk="' + _esc(p.go) + '"')
        + ' title="' + _esc(p.tip || '') + '">'
        + '<i class="' + p.ic + '"></i><b>' + _sdNum(p.n) + '</b>'
        + '<span class="sig-pg">' + _esc(p.label) + '</span>'
        + (dead ? '</span>' : '</button>');
}

function _atkOk(txt, ic) {
    return '<span class="sig-ok"><i class="' + (ic || 'sig-dot') + '"></i>' + _esc(txt) + '</span>';
}

function _atkSub(main, tail) {
    return '<div class="sig-sub"><span class="sig-sub-main">' + main + '</span>'
        + (tail ? '<span class="sig-sub-tail">' + SD_SEP + tail + '</span>' : '') + '</div>';
}

function _atkCard(c) {
    return '<article class="sig-card' + (c.cls ? ' ' + c.cls : '') + '" data-card="' + c.key + '"'
        + (c.health ? ' data-health="' + c.health + '"' : '')
        + ' style="--tm-accent:' + c.accent + '">'
        + '<div class="sig-head"><span class="sig-ic"><i class="' + c.ic + '"></i></span>'
        + '<span class="sig-title">' + _esc(c.title) + '</span>'
        + (c.go ? '<button type="button" class="sig-explore" data-atk="' + _esc(c.go) + '" title="' + _esc(c.goTip || '') + '">'
            + _esc(c.goLabel) + ' <i class="ph-bold ph-arrow-right"></i></button>' : '')
        + '</div>'
        + '<div class="sig-metric"><span class="sig-total">' + c.total + '</span>'
        + '<span class="sig-flags">' + (c.flags || '') + '</span></div>'
        + (c.sub || '')
        + (c.body || '')
        + (c.tail || '')
        + (c.foot ? '<div class="sig-foot"><span class="sig-provs">' + c.foot + '</span></div>' : '')
        + '</article>';
}

function _atkRow(r) {
    return '<div class="lg-row" role="button" tabindex="0"'
        + (r.health ? ' data-health="' + r.health + '"' : '')
        + ' data-atk="' + _esc(r.go) + '" title="' + _esc(r.tip) + '">'
        + '<span class="lg-id">' + (r.glyph ? '<span class="lg-g">' + r.glyph + '</span>' : '')
        + '<span class="lg-name">' + _esc(r.name) + '</span>'
        + '<span class="lg-kind">' + _esc(r.kind || '') + '</span></span>'
        + (r.bad || '<span class="lg-bad"></span>')
        + '<span class="lg-n">' + _sdNum(r.n) + '</span>'
        + '<span class="lg-pct">' + r.pct + '%</span>'
        + '</div>';
}

function _atkStrip(groups, aria, opts) {
    const o = opts || {};
    const noun = o.noun || 'objects';
    const cap = o.cap || ATK_CELL_CAP;
    const live = groups.filter(g => g && g.n > 0);
    const total = live.reduce((a, g) => a + g.n, 0);
    const cell = (cls, title) => '<i class="sig-cell' + (cls ? ' ' + cls : '') + '" title="' + _esc(title) + '"></i>';
    let html = '';
    if (!total) {
        html = '<span class="sig-more" style="margin-left:0">' + _esc(o.empty || ('no ' + noun)) + '</span>';
    } else if (total <= cap) {
        live.forEach(g => { for (let i = 0; i < g.n; i++) html += cell(g.cls, g.at(i)); });
    } else {
        const per = total / cap;
        let drawn = 0;
        live.forEach((g, gi) => {
            const last = gi === live.length - 1;
            let want = last ? cap - drawn : Math.max(1, Math.round(g.n / per));
            want = Math.max(0, Math.min(want, cap - drawn));
            for (let i = 0; i < want; i++) {
                html += cell(g.cls, g.at(Math.min(g.n - 1, Math.floor(i * g.n / want))));
            }
            drawn += want;
        });
        const each = per >= 10 ? Math.round(per) : Math.round(per * 10) / 10;
        const legend = per < 1.5 ? (_sdNum(total) + ' in ' + _sdNum(drawn)) : ('1 cell = ' + each);
        const tip = _sdNum(total) + ' ' + noun + ' drawn as ' + _sdNum(drawn) + ' cells, so '
            + (per < 1.5 ? 'a few cells stand for two' : 'each cell stands for about ' + each + ' ' + noun);
        html += '<span class="sig-more" title="' + _esc(tip) + '">' + _esc(legend) + '</span>';
    }
    return '<div class="sig-strip' + (o.cls ? ' ' + o.cls : '') + '" role="img" aria-label="' + _esc(aria) + '">' + html + '</div>';
}

function _atkRank(rows, keyFn, opts) {
    const o = opts || {};
    const map = new Map();
    rows.forEach(r => {
        const keys = keyFn(r);
        (Array.isArray(keys) ? keys : [keys]).forEach(k => {
            if (k == null || k === '') return;
            let e = map.get(k);
            if (!e) { e = { key: k, n: 0, weight: 0, open: 0, sim: 0, kinds: new Map(), rows: [] }; map.set(k, e); }
            e.n++;
            e.weight += (o.weight ? o.weight(r) : 1);
            if (r.known && !r.handled) e.open++;
            if (r.simulated) e.sim++;
            e.rows.push(r);
            if (o.kind) { const kk = o.kind(r, k); if (kk) e.kinds.set(kk, (e.kinds.get(kk) || 0) + 1); }
        });
    });
    const list = Array.from(map.values());
    list.forEach(e => { e.kind = Array.from(e.kinds.keys()).slice(0, 3).join(' '); });
    list.sort((a, b) => (b.open - a.open) || (b.n - a.n) || (b.weight - a.weight)
        || String(a.key).localeCompare(String(b.key)));
    return list;
}

function _atkRankBody(list, opts) {
    const o = opts || {};
    const noun = o.noun || 'entries';
    const unit = o.unitN || 'alerts';
    const total = list.reduce((a, e) => a + e.n, 0) || 1;
    const shown = list.slice(0, ATK_ROW_CAP);
    const body = '<div class="lg-rows">' + shown.map(e => {
        const pct = _atkPct(e.n, total);
        return _atkRow({
            name: o.label ? o.label(e) : e.key,
            kind: o.kindLabel ? o.kindLabel(e) : e.kind,
            glyph: o.glyph ? o.glyph(e) : '',
            n: e.n,
            pct: pct,
            go: o.go(e),
            health: e.open === e.n ? 'down' : (e.open ? 'warn' : ''),
            bad: e.open ? _atkFlag({
                tag: 'span', extra: 'lg-bad', cls: e.open === e.n ? 'd-bad' : 'd-warn',
                ic: 'ph-bold ph-lock-open', n: e.open, words: false,
                tip: _sdNum(e.open) + ' of ' + _sdNum(e.n) + ' ' + unit
                    + ' here came from a source that holds no active decision now'
                    + (e.open === e.n ? '. Nothing on this row was ever stopped' : '')
                    + (e.sim ? '. ' + _sdNum(e.sim) + ' of them were simulated, so CrowdSec enforced nothing' : '')
            }) : '',
            tip: (o.tipName ? o.tipName(e) : String(e.key)) + ' - ' + _sdNum(e.n) + ' ' + unit + ', ' + pct + '%'
                + (e.open ? ', ' + _sdNum(e.open) + ' from sources with no active ban' : ', every source banned')
                + '. Click to filter the evidence below.'
        });
    }).join('') + '</div>';
    const tailFor = k => {
        const rest = list.slice(k);
        return _sdNum(rest.reduce((a, e) => a + e.n, 0)) + ' ' + unit + ' across ' + _sdNum(rest.length) + ' more ' + noun;
    };
    let tail = '';
    if (list.length > shown.length) tail += '<div class="lg-tail">+' + tailFor(ATK_ROW_CAP) + '</div>';
    if (list.length > 4) tail += '<div class="lg-tail lg-tail-c">+' + tailFor(4) + '</div>';
    return { body: body, tail: tail };
}

function _atkSpec(obj) {
    return Object.keys(obj).map(k => k + '=' + encodeURIComponent(obj[k])).join(';');
}

function _atkActive() { return Object.keys(_atkFacet).filter(k => _atkFacet[k]); }
function _atkClearFacets() { Object.keys(_atkFacet).forEach(k => { _atkFacet[k] = ''; }); }

function _atkRevealFeed() {
    revealBelowFold(document.querySelector('#csStats .atk-feed'));
}

function _atkOpenCsSettings() {
    if (typeof openSettingsModal !== 'function') return;
    openSettingsModal('system');
    setTimeout(() => {
        if (typeof switchSystemTab === 'function') {
            switchSystemTab('crowdsec', document.getElementById('system-tab-crowdsec'));
        }
    }, 60);
}

function _atkGo(spec) {
    const p = {};
    String(spec || '').split(';').forEach(kv => {
        const i = kv.indexOf('=');
        if (i <= 0) return;
        let v = kv.slice(i + 1);
        try { v = decodeURIComponent(v); } catch (_) {}
        p[kv.slice(0, i)] = v;
    });
    if ('clear' in p) {
        _atkClearFacets();
        if (p.clear === 'all') {
            _atkQuery = '';
            const box = document.getElementById('csSearch');
            if (box) box.value = '';
        }
        if (_atkViewAuto) { _atkView = 'alerts'; _atkViewAuto = false; }
        _atkPage = 1; _atkOpen = '';
        _csRender();
        _atkRevealFeed();
        return;
    }
    if ('cfg' in p) { _atkOpenCsSettings(); return; }
    if ('reload' in p) { _csDecPage = null; _csDecKey = ''; refreshCrowdSecTab(true); return; }
    if ('unban' in p) { csUnban(Number(p.unban)); return; }
    if ('ban' in p) { openCsBanModal(p.ban); return; }
    if ('page' in p) { _atkPage = Math.max(1, parseInt(p.page, 10) || 1); _atkOpen = ''; _csRender(); _atkRevealFeed(); return; }
    if ('open' in p) { _atkOpen = (_atkOpen === p.open) ? '' : p.open; _csRender(); _atkRevealFeed(); return; }
    if ('view' in p) {
        _atkView = p.view === 'decisions' ? 'decisions' : 'alerts';
        _atkViewAuto = false;
        _atkPage = 1; _atkOpen = '';
        if (Object.keys(p).length === 1) { _csRender(); _atkRevealFeed(); return; }
    }
    const keys = Object.keys(p).filter(k => k in _atkFacet);
    if (!keys.length) { _csRender(); _atkRevealFeed(); return; }
    const same = !('view' in p) && keys.every(k => _atkFacet[k] === p[k]);
    keys.forEach(k => { _atkFacet[k] = same ? '' : p[k]; });
    if (!('view' in p) && !same) {
        if (keys.some(k => ATK_DEC_ONLY[k])) {
            if (_atkView !== 'decisions') { _atkView = 'decisions'; _atkViewAuto = true; }
        } else if (keys.some(k => ATK_ALERT_ONLY[k]) && _atkView !== 'alerts') {
            _atkView = 'alerts'; _atkViewAuto = true;
        }
    }
    if (same && _atkViewAuto && !_atkActive().length) { _atkView = 'alerts'; _atkViewAuto = false; }
    _atkPage = 1; _atkOpen = '';
    _csRender();
    _atkRevealFeed();
}

let _atkViewAuto = false;
let _atkBound = false;
function _atkBind() {
    if (_atkBound) return;
    _atkBound = true;
    const root = () => document.getElementById('csStats');
    document.addEventListener('click', e => {
        const t = e.target.closest && e.target.closest('[data-atk]');
        if (!t) return;
        const r = root();
        if (!r || !r.contains(t)) return;
        if (t.hasAttribute('disabled')) return;
        e.preventDefault();
        _atkGo(t.getAttribute('data-atk'));
    });
    document.addEventListener('keydown', e => {
        if (e.key !== 'Enter' && e.key !== ' ') return;
        const t = e.target.closest && e.target.closest('.lg-row[data-atk], .sig-ep-row[data-atk]');
        if (!t) return;
        const r = root();
        if (!r || !r.contains(t)) return;
        e.preventDefault();
        _atkGo(t.getAttribute('data-atk'));
    });
}

function _atkTickAge() {
    clearInterval(_csAgeTimer);
    _csAgeTimer = setInterval(() => {
        const el = document.getElementById('atkAge');
        if (!el) { clearInterval(_csAgeTimer); _csAgeTimer = null; return; }
        el.textContent = _sdAgo(_csFetched);
    }, 15000);
}

function _csSearchInput() {
    clearTimeout(_csSearchTimer);
    _csSearchTimer = setTimeout(() => {
        _atkQuery = (document.getElementById('csSearch')?.value || '').trim();
        _atkPage = 1; _atkOpen = '';
        _csRender();
    }, 140);
}

function _atkMatchAlert(a, q, skip) {
    const f = _atkFacet;
    const on = k => !(skip && skip[k]) && f[k];
    if (on('scenario') && a.scenario !== f.scenario) return false;
    if (on('ip') && a.ip !== f.ip) return false;
    if (on('asn') && a.asNum !== f.asn) return false;
    if (on('cc') && a.cc !== f.cc) return false;
    if (on('uri') && a.uris.indexOf(f.uri) < 0) return false;
    if (on('user') && a.users.indexOf(f.user) < 0) return false;
    if (on('router') && a.routers.indexOf(f.router) < 0) return false;
    if (on('host') && a.hosts.indexOf(f.host) < 0) return false;
    if (on('verb') && a.verbs.indexOf(f.verb) < 0) return false;
    if (on('agent') && a.uas.map(_uaShort).indexOf(f.agent) < 0) return false;
    if (on('outcome')) {
        if (f.outcome === 'sim') { if (!a.simulated) return false; }
        else if (!a.known) return false;
        else if (f.outcome === 'banned' && !a.handled) return false;
        else if (f.outcome === 'loose' && a.handled) return false;
    }
    if (q) {
        const hay = (a.ip + ' ' + a.scenario + ' ' + a.asName + ' ' + a.cc + ' ' + a.message + ' ' + a.machine + ' '
            + a.uris.join(' ') + ' ' + a.uas.join(' ') + ' ' + a.users.join(' ') + ' ' + a.range + ' '
            + a.routers.join(' ') + ' ' + a.hosts.join(' ')).toLowerCase();
        if (hay.indexOf(q) < 0) return false;
    }
    return true;
}

function _csCountryCounts(alerts) {
    const counts = {};
    alerts.forEach(a => {
        const cc = a.cc;
        if (!cc) return;
        if (!counts[cc]) counts[cc] = { count: 0, name: _csCountryName(cc) };
        counts[cc].count++;
    });
    return counts;
}

function csGeo_click(cc) { _atkGo(_atkSpec({ cc: _atkCc(cc) })); }
function clearCsCountryFilter() { _atkFacet.cc = ''; _atkPage = 1; _csRender(); }

let _csRefreshing = false, _csRefreshQueued = false;
async function refreshCrowdSecTab(manual) {
    if (_csRefreshing) { _csRefreshQueued = true; return; }
    _csRefreshing = true;
    try {
        await _csRefreshInner(manual === true);
    } finally {
        _csRefreshing = false;
        _csSchedulePoll();
        if (_csRefreshQueued) { _csRefreshQueued = false; refreshCrowdSecTab(); }
    }
}

function _csSchedulePoll() {
    clearTimeout(_csPollTimer);
    _csPollTimer = setTimeout(() => {
        _csPollTimer = null;
        const here = typeof _activeTab !== 'undefined' && _activeTab === 'crowdsec';
        if (here && _csConfigured && document.visibilityState === 'visible') refreshCrowdSecTab();
        else _csSchedulePoll();
    }, CS_POLL_MS);
}

function _csSetConfigured(on) {
    _csConfigured = on;
    const notCfg = document.getElementById('csNotConfigured');
    const bar = document.getElementById('csFilterBar');
    const el = document.getElementById('csStats');
    if (notCfg) notCfg.style.setProperty('display', on ? 'none' : 'flex', 'important');
    if (bar) bar.style.display = on ? '' : 'none';
    if (el && !on) el.innerHTML = '';
    if (on) return;
    const onAgent = !!_activeAgent;
    const hostBlock  = document.getElementById('csNotCfgHost');
    const agentBlock = document.getElementById('csNotCfgAgent');
    const agentName  = document.getElementById('csNotCfgAgentName');
    if (hostBlock)  hostBlock.style.display  = onAgent ? 'none' : '';
    if (agentBlock) agentBlock.style.display = onAgent ? '' : 'none';
    if (agentName && onAgent) agentName.textContent = _activeAgent.name || 'this agent';
}

function _csSpinner() {
    const el = document.getElementById('csStats');
    if (!el) return;
    el.innerHTML = '<div class="text-center py-16" style="color:var(--muted)"><i class="ph-light ph-spinner-gap text-4xl block mb-3 animate-spin opacity-40"></i><p>Loading CrowdSec...</p></div>';
}

function _csEmptyDec() {
    return { ok: false, error: '', stale: '', total: 0, own: 0, subscribed: 0, wide: 0, origins: {}, types: {}, rows: [], rows_more: 0 };
}

function _csApplyDown(why) {
    _csDecSum = _csEmptyDec();
    _csLapiOk = false; _csAlertsOk = false;
    _csDecErr = why; _csAltErr = why; _csDecStale = '';
    _csAlerts = []; _csAltCapped = false; _csAltLimit = 0; _csAltStatus = 0; _csSpan = 0;
    _csVersion = ''; _csDecPage = null; _csDecKey = '';
    _csFetched = Date.now();
}

async function _csApplySummary(sum) {
    const dec = Object.assign(_csEmptyDec(), (sum && sum.decisions) || {});
    const alt = Object.assign({ ok: false, error: '', status: 0, limit: 0, capped: false, rows: [] }, (sum && sum.alerts) || {});
    dec.rows = (Array.isArray(dec.rows) ? dec.rows : []).map(_atkParseDecision);
    dec.origins = dec.origins && typeof dec.origins === 'object' ? dec.origins : {};
    dec.types = dec.types && typeof dec.types === 'object' ? dec.types : {};
    _csDecSum   = dec;
    _csLapiOk   = dec.ok === true;
    _csDecStale = _csLapiOk ? String(dec.stale || '') : '';
    _csDecErr   = _csLapiOk ? '' : (dec.error || 'CrowdSec LAPI unavailable');
    if (!_csLapiOk && /\b403\b/.test(_csDecErr) && !/bouncer/i.test(_csDecErr)) {
        _csDecErr += '. CrowdSec only accepts a bouncer key on /v1/decisions, the machine token is refused there, so CROWDSEC_API_KEY has to be set as well.';
    }
    _csAlertsOk  = alt.ok === true;
    _csAltStatus = parseInt(alt.status, 10) || 0;
    _csAltErr    = _csAlertsOk ? '' : String(alt.error || '');
    _csAltCapped = alt.capped === true;
    _csAltLimit  = parseInt(alt.limit, 10) || 0;
    _csAlerts = (Array.isArray(alt.rows) ? alt.rows : [])
        .filter(a => !ATK_PULL_SCOPE.test(String(((a || {}).source || {}).scope || '')))
        .map((a, i) => {
            const row = _atkParseAlert(a, i);
            row.known = _csLapiOk;
            row.handled = _csLapiOk && !row.simulated && a.handled === true;
            return row;
        });
    _csAlerts.sort((x, y) => y.start - x.start);
    _csSpan = _csAlerts.length > 1 ? (_csAlerts[0].start - _csAlerts[_csAlerts.length - 1].start) : 0;
    _csVersion = String((sum && sum.version) || '');
    _csDecPage = null; _csDecKey = '';

    _csHostGeo = false;
    if (_csAlerts.length && !_csAlerts.some(a => a.cn)) {
        await loadGeoStatus();
        if (_geoEnabled && _geoAvailable) {
            await geoAggregate([...new Set(_csAlerts.map(a => a.ip).filter(Boolean))]);
            _csHostGeo = true;
            _csAlerts.forEach(a => {
                const g = _geoCache[a.ip];
                if (!a.cc && g) a.cc = _atkCc(g.country_code);
            });
        }
    }
}

async function _csRefreshInner(manual) {
    const el = document.getElementById('csStats');
    if (!el) return;
    if (!_activeAgent && !window._hostCsEnabled) { _csSetConfigured(false); return; }
    _csSetConfigured(true);
    const key = _tabCacheKey('crowdsec');
    let painted = _csPaintedKey === key;
    if (!painted) {
        _csVersion = '';
        const cached = tabCacheGet('crowdsec');
        if (cached && cached.decisions && cached.alerts) {
            await _csApplySummary(cached);
            _csFetched = cached.at || Date.now();
            _atkPage = 1; _atkOpen = '';
            _csRenderBanRecent();
            _csRender();
            painted = true;
            _csPaintedKey = key;
        } else {
            _csSpinner();
        }
    }
    const params = [];
    const lim = _csLimitParam();
    if (lim) params.push(lim);
    if (painted && _csVersion) params.push('version=' + encodeURIComponent(_csVersion));
    let res;
    try {
        res = await agentFetch('/api/crowdsec/summary' + (params.length ? '?' + params.join('&') : ''));
    } catch (e) {
        const why = _netErrText(e, 'Could not reach the CrowdSec LAPI');
        if (painted) { showToast(why, 'error'); return; }
        _csApplyDown(why);
        _csPaintedKey = key;
        _csRender();
        return;
    }
    if (res.status === 404 && _activeAgent) { _csSetConfigured(false); return; }
    let sum = null;
    try { sum = await res.json(); } catch (_) { sum = null; }
    if (!res.ok || !sum || typeof sum !== 'object') {
        const why = (sum && sum.error) || ('CrowdSec summary failed (HTTP ' + res.status + ')');
        if (painted) { showToast(why, 'error'); return; }
        _csApplyDown(why);
        _csPaintedKey = key;
        _csRender();
        return;
    }
    if (sum.unchanged && painted && sum.version === _csVersion) {
        _csFetched = Date.now();
        const age = document.getElementById('atkAge');
        if (age) age.textContent = _sdAgo(_csFetched);
        if (manual) showToast('CrowdSec is up to date, nothing changed since the last read', 'success', false);
        return;
    }
    await _csApplySummary(sum);
    _csFetched = Date.now();
    tabCachePut('crowdsec', Object.assign({ at: _csFetched }, sum));
    if (!painted) { _atkPage = 1; _atkOpen = ''; }
    _csPaintedKey = key;
    _csRenderBanRecent();
    _csRender();
}

function _csDecSpec() {
    const f = _atkFacet;
    const inDec = _atkView === 'decisions';
    const spec = { origin: f.origin || '', type: f.type || '', ip: f.ip || '', scenario: f.scenario || '',
                   q: inDec ? _atkQuery : '', page: inDec ? _atkPage : 1, per: ATK_FEED_PAGE };
    spec.key = _csVersion + '|' + JSON.stringify(spec);
    return spec;
}

function _csDecNeeded(spec) {
    return _atkView === 'decisions' || !!(spec.origin || spec.type || spec.ip || spec.scenario);
}

async function _csDecFetch(spec) {
    _csDecKey = spec.key;
    const qs = ['origin', 'type', 'ip', 'scenario', 'q', 'page', 'per']
        .filter(k => spec[k] !== '' && spec[k] !== undefined && spec[k] !== null)
        .map(k => k + '=' + encodeURIComponent(spec[k])).join('&');
    let page = { rows: [], total: 0, page: 1, pages: 1, per: ATK_FEED_PAGE, facet_totals: {}, key: spec.key, error: '' };
    try {
        const res = await agentFetch('/api/crowdsec/decisions/search?' + qs);
        let data = null;
        try { data = await res.json(); } catch (_) { data = null; }
        if (res.ok && data && Array.isArray(data.rows)) {
            page = { rows: data.rows.map(_atkParseDecision), total: Number(data.total) || 0,
                     page: Number(data.page) || 1, pages: Number(data.pages) || 1, per: Number(data.per) || ATK_FEED_PAGE,
                     facet_totals: (data.facet_totals && typeof data.facet_totals === 'object') ? data.facet_totals : {},
                     key: spec.key, error: '' };
        } else {
            page.error = (data && data.error) || ('HTTP ' + res.status);
        }
    } catch (e) {
        page.error = _netErrText(e, 'Could not read decisions');
    }
    if (_csDecKey !== spec.key) return;
    _csDecPage = page;
    _csRender();
}

function _atkBlindCard(o) {
    return _atkCard({
        key: o.key, cls: 'lg-blind' + (o.wide ? ' lg-wide' : ''), accent: o.accent, ic: o.ic, title: o.title,
        total: '-', flags: _atkOk(o.state, 'ph-bold ph-info'),
        sub: _atkSub(o.sub),
        body: '<p class="lg-note">' + o.note + '</p>',
        go: o.go, goLabel: o.goLabel, goTip: o.goTip
    });
}

function _atkOwnFlag(own) {
    return own ? _atkFlag({ cls: 'd-warn', ic: 'ph-bold ph-shield-check', n: own, label: 'raised here',
        go: _atkSpec({ view: 'decisions', origin: 'own' }),
        tip: _sdNum(own) + ' decisions in force did not come from a subscription. Their alerts are outside the retention window, or the decision was added by hand' }) : '';
}

function _atkCalmCard(key, accent, ic, title, wide, line, note, extra) {
    return _atkCard({
        key: key, cls: wide ? 'lg-wide' : '', accent: accent, ic: ic, title: title,
        total: '0', flags: _atkOk(line) + (extra || ''),
        sub: _atkSub('nothing to rank in the retained window'),
        body: '<p class="lg-note">' + note + '</p>'
    });
}

function _atkFilterNote(retained) {
    return 'The retained window holds ' + _sdNum(retained) + ' alerts, and every filter on the window row is applied together, '
        + 'so this card has nothing left to rank. That is the filter talking, not the host.';
}

function _atkFilteredCard(key, accent, ic, title, wide, retained) {
    return _atkCard({
        key: key, cls: 'lg-blind' + (wide ? ' lg-wide' : ''), accent: accent, ic: ic, title: title,
        total: '-', flags: _atkOk('filtered to nothing', 'ph-bold ph-funnel'),
        sub: _atkSub('<b>0</b> of ' + _sdNum(retained) + ' retained alerts match'),
        body: '<p class="lg-note">' + _atkFilterNote(retained) + '</p>',
        go: 'clear=all', goLabel: 'clear filters', goTip: 'Remove every filter and look at the whole retained window'
    });
}

function _atkOwnNote(own) {
    return own
        ? _sdNum(own) + (own === 1 ? ' ban in force was' : ' bans in force were') + ' raised on this host, but the alerts that earned '
            + (own === 1 ? 'it' : 'them') + ' are outside the retention window or the decision was added by hand.'
        : 'Every ban still in force was subscribed rather than earned.';
}

const ATK_NEEDS_MACHINE = 'cfg=machine';
const ATK_MACHINE_NOTE = 'Set <code>CROWDSEC_MACHINE_ID</code> and <code>CROWDSEC_MACHINE_PASSWORD</code> alongside the bouncer key. '
    + 'The two credentials are complementary rather than tiered: CrowdSec refuses the machine token on <code>/v1/decisions</code>, so both must be present for the whole tab.';

function _atkCardSources(d) {
    if (!d.alertsOk) {
        return _atkBlindCard({
            key: 'sources', accent: 'var(--red)', ic: 'ph-fill ph-crosshair', title: 'Attacking sources',
            state: 'needs a watcher login', sub: 'sources are only listed on <b>/v1/alerts</b>',
            note: 'A bouncer API key reads <code>/v1/decisions</code> and nothing else. ' + ATK_MACHINE_NOTE,
            go: ATK_NEEDS_MACHINE, goLabel: 'settings', goTip: 'Open Settings, System Monitoring, CrowdSec'
        });
    }
    if (!d.retained) {
        return _atkCalmCard('sources', 'var(--red)', 'ph-fill ph-crosshair', 'Attacking sources', false,
            'nobody tripped a scenario',
            'The alert read succeeded and came back empty, which is not the same as being unable to read it. ' + _atkOwnNote(d.own),
            _atkOwnFlag(d.own));
    }
    if (!d.alerts.length) {
        return _atkFilteredCard('sources', 'var(--red)', 'ph-fill ph-crosshair', 'Attacking sources', false, d.retained);
    }
    const byIp = new Map();
    d.alerts.forEach(a => {
        if (!a.ip) return;
        let e = byIp.get(a.ip);
        if (!e) { e = { ip: a.ip, n: 0, ev: 0, handled: false, sim: false, cc: a.cc, last: 0, scen: new Set() }; byIp.set(a.ip, e); }
        e.n++; e.ev += a.events; e.handled = e.handled || a.handled; e.sim = e.sim || a.simulated;
        e.last = Math.max(e.last, a.start); e.scen.add(a.scenario);
    });
    const srcs = Array.from(byIp.values()).sort((a, b) => (b.ev - a.ev) || (b.n - a.n));
    const known = d.lapiOk;
    const banned = known ? srcs.filter(s => s.handled) : srcs;
    const loose = known ? srcs.filter(s => !s.handled) : [];
    const back = loose.filter(s => s.n > 1);
    const once = loose.filter(s => s.n === 1);
    const repeat = srcs.filter(s => s.n > 1);
    const sim = srcs.filter(s => s.sim);
    const label = s => s.ip + ' - ' + _sdNum(s.ev) + ' events, ' + _sdNum(s.n) + (s.n === 1 ? ' alert' : ' alerts') + ', '
        + Array.from(s.scen).map(_scenShort).slice(0, 2).join(' + ') + (s.cc ? ', ' + s.cc : '') + ', ' + _sdAgo(s.last)
        + (!known ? ', ban state unknown' : (s.handled ? ', banned' : (s.sim ? ', simulated, nothing was enforced' : ', no active ban')));
    const top = srcs[0];
    const ccs = new Set(srcs.map(s => s.cc).filter(Boolean));
    return _atkCard({
        key: 'sources', accent: 'var(--red)', ic: 'ph-fill ph-crosshair', title: 'Attacking sources',
        health: back.length ? 'down' : (loose.length ? 'warn' : ''),
        total: _sdNum(srcs.length),
        flags: !known
            ? _atkOk('ban state unknown', 'ph-bold ph-info')
            : loose.length
            ? _atkFlag({ cls: back.length ? 'd-bad' : 'd-warn', ic: 'ph-bold ph-lock-open', n: loose.length, label: 'loose',
                go: _atkSpec({ outcome: 'loose' }),
                tip: _sdNum(loose.length) + ' sources tripped a scenario and hold no active decision right now. Usually an expired ban rather than a miss'
                    + (sim.length ? '. ' + _sdNum(sim.length) + ' of them were simulated, so CrowdSec enforced nothing by design' : '') })
              + _atkFlag({ cls: 'd-off', ic: 'ph-bold ph-prohibit', n: banned.length, label: 'banned',
                go: _atkSpec({ outcome: 'banned' }),
                tip: _sdNum(banned.length) + ' sources hold an active ban raised by your own scenarios. Nothing to do about these' })
            : _atkOk('every source banned'),
        sub: _atkSub(top ? 'worst <b>' + _esc(top.ip) + '</b> ' + _sdNum(top.ev) + ' events' : 'no sources',
            ccs.size ? _sdNum(ccs.size) + (ccs.size === 1 ? ' country' : ' countries') : ''),
        body: _atkStrip([
            { cls: 'sig-cell-err', n: back.length, at: i => label(back[i]) },
            { cls: 'sig-cell-warn', n: once.length, at: i => label(once[i]) },
            { cls: '', n: banned.length, at: i => label(banned[i]) }
        ], _sdNum(srcs.length) + ' sources, ' + _sdNum(loose.length) + ' with no active ban',
            { noun: 'sources', empty: 'no sources' }),
        foot: _atkProv({ ic: 'ph-bold ph-repeat', n: repeat.length, label: 'repeat', go: '',
                tip: _sdNum(repeat.length) + ' sources tripped a scenario more than once, so they came back after the first ban' })
            + _atkProv({ ic: 'ph-bold ph-arrow-elbow-down-right', n: srcs.length - repeat.length, label: 'one-shot', go: '',
                tip: 'Seen exactly once. Mostly opportunistic scanners walking the whole address space' })
            + (sim.length ? _atkProv({ ic: 'ph-bold ph-eye-slash', n: sim.length, label: 'simulated', cls: 'sig-prov-warn',
                go: _atkSpec({ outcome: 'sim' }),
                tip: 'These alerts ran in simulation mode. CrowdSec saw them and enforced nothing' }) : ''),
        go: loose.length ? _atkSpec({ outcome: 'loose' }) : '', goLabel: 'loose',
        goTip: 'Show only alerts whose source holds no active ban'
    });
}

function _atkCardNetworks(d) {
    if (!d.alertsOk) {
        return _atkBlindCard({
            key: 'networks', accent: 'var(--purple)', ic: 'ph-fill ph-globe-hemisphere-west', title: 'Networks',
            state: 'needs a watcher login', sub: 'AS names ride on <b>alert.source</b>',
            note: 'Decisions carry no enrichment at all. Everything on a bouncer key comes from the seven fields <code>/v1/decisions</code> returns: '
                + '<code>value</code>, <code>type</code>, <code>scope</code>, <code>origin</code>, <code>scenario</code>, <code>duration</code>, <code>id</code>. '
                + 'No country, no ASN, no events, no time. ' + ATK_MACHINE_NOTE,
            go: ATK_NEEDS_MACHINE, goLabel: 'settings', goTip: 'Open Settings, System Monitoring, CrowdSec'
        });
    }
    if (!d.retained) {
        return _atkCalmCard('networks', 'var(--purple)', 'ph-fill ph-globe-hemisphere-west', 'Networks', false,
            'no network reached a scenario',
            'Networks are counted from <code>source.as_name</code> on alerts. With no alerts there is nothing to attribute, even though addresses may still be blocked preventively.',
            _atkOwnFlag(d.own));
    }
    if (!d.asnOn) {
        return _atkBlindCard({
            key: 'networks', accent: 'var(--purple)', ic: 'ph-fill ph-globe-hemisphere-west', title: 'Networks',
            state: 'not enriched', sub: 'this agent reports <b>ip</b> only',
            note: 'CrowdSec resolves the AS and country itself, in the <code>crowdsecurity/geoip-enrich</code> parser on the machine that raised the alert. '
                + 'The LAPI never computes them, it stores whatever the agent sent. Install that parser on the reporting machine and these alerts start carrying '
                + '<code>as_name</code>, <code>as_number</code> and <code>cn</code>.',
            go: 'clear=all', goLabel: 'clear filters', goTip: 'Remove every filter and look at the whole retained window'
        });
    }
    if (!d.alerts.length) {
        return _atkFilteredCard('networks', 'var(--purple)', 'ph-fill ph-globe-hemisphere-west', 'Networks', false, d.retained);
    }
    const list = _atkRank(d.alerts, a => a.asNum, { weight: a => a.events, kind: a => a.cc || '' });
    const nameOf = e => (e.rows[0].asName || ('AS' + e.key));
    const rb = _atkRankBody(list, {
        noun: 'networks', unitN: 'alerts',
        label: nameOf,
        kindLabel: e => 'AS' + e.key,
        glyph: e => _flagEmoji(e.rows[0].cc),
        go: e => _atkSpec({ asn: e.key }),
        tipName: e => nameOf(e) + ' (AS' + e.key + ')'
    });
    const withAs = d.alerts.filter(a => a.asNum).length;
    const ranges = new Set(d.alerts.map(a => a.range).filter(Boolean));
    return _atkCard({
        key: 'networks', accent: 'var(--purple)', ic: 'ph-fill ph-globe-hemisphere-west', title: 'Networks',
        total: _sdNum(list.length),
        flags: _atkFlag({ cls: 'd-off', ic: 'ph-bold ph-tree-structure', n: ranges.size, label: 'ranges', tag: 'span',
            tip: _sdNum(ranges.size) + ' distinct source ranges, from source.range. A subnet with several sources is usually one operator, not several' }),
        sub: _atkSub(list.length ? 'worst <b>' + _esc(nameOf(list[0])) + '</b> ' + _sdNum(list[0].n) + ' alerts' : 'no networks',
            _sdNum(withAs) + ' of ' + _sdNum(d.alerts.length) + ' alerts carry an AS'),
        body: rb.body, tail: rb.tail
    });
}

function _atkCardScenarios(d) {
    if (!d.alertsOk) {
        return _atkBlindCard({
            key: 'scenarios', wide: true, accent: 'var(--orange)', ic: 'ph-fill ph-lightning', title: 'Scenarios',
            state: 'needs a watcher login', sub: 'the decision scenario is not the same question',
            note: 'Ranking <code>/v1/decisions</code> by scenario puts the community blocklist first on every instance and tells you what the blocklist contains '
                + 'rather than what attacked this host. Alerts carry the real triggering scenario plus <code>events_count</code>, so this card ranks those instead. '
                + ATK_MACHINE_NOTE,
            go: ATK_NEEDS_MACHINE, goLabel: 'settings', goTip: 'Open Settings, System Monitoring, CrowdSec'
        });
    }
    if (!d.retained) {
        return _atkCard({
            key: 'scenarios', cls: 'lg-wide', accent: 'var(--orange)', ic: 'ph-fill ph-lightning', title: 'Scenarios',
            total: '0', flags: _atkOk('nothing tripped') + _atkOwnFlag(d.own),
            sub: _atkSub('no local scenario has fired in the retained window'),
            body: '<p class="lg-note">' + (d.own
                ? _atkOwnNote(d.own) + ' Everything else in force came from a subscribed list rather than from something this host saw.'
                : 'Every ban in force came from a subscribed list, not from something this host saw. That is the normal resting state of a homelab behind CrowdSec.')
                + '</p>'
        });
    }
    if (!d.alerts.length) {
        return _atkFilteredCard('scenarios', 'var(--orange)', 'ph-fill ph-lightning', 'Scenarios', true, d.retained);
    }
    const list = _atkRank(d.alerts, a => a.scenario, { weight: a => a.events });
    const leaky = list.filter(e => e.rows[0].capacity > 0);
    const evTotal = d.alerts.reduce((a, x) => a + x.events, 0);
    const rb = _atkRankBody(list, {
        noun: 'scenarios', unitN: 'alerts',
        label: e => _scenShort(e.key),
        kindLabel: e => {
            const c = e.rows[0];
            return c.capacity > 0 ? ('leaky ' + c.capacity + '/' + c.leakspeed) : 'trigger';
        },
        glyph: e => e.rows[0].capacity > 0 ? '<i class="ph-bold ph-drop-half-bottom"></i>' : '<i class="ph-bold ph-lightning"></i>',
        go: e => _atkSpec({ scenario: e.key }),
        tipName: e => e.key + (e.rows[0].capacity > 0
            ? ' - leaky bucket, capacity ' + e.rows[0].capacity + ', leaks every ' + e.rows[0].leakspeed
            : ' - trigger bucket, fires on the first matching event, so capacity and leakspeed say nothing here')
    });
    return _atkCard({
        key: 'scenarios', cls: 'lg-wide', accent: 'var(--orange)', ic: 'ph-fill ph-lightning', title: 'Scenarios',
        total: _sdNum(d.alerts.length) + '<span class="lg-unit">alerts</span>',
        flags: _atkFlag({ cls: 'd-off', ic: 'ph-bold ph-drop-half-bottom', n: leaky.length, label: 'leaky', tag: 'span',
                tip: 'Leaky buckets have capacity above 0, so they need sustained pressure to fire. A slow prober trickling under the leak rate never trips one' })
            + _atkFlag({ cls: 'd-off', ic: 'ph-bold ph-lightning', n: list.length - leaky.length, label: 'trigger', tag: 'span',
                tip: 'Trigger buckets have capacity 0 and fire on the first matching event. Capacity and leakspeed carry no meaning for these' }),
        sub: _atkSub('worst <b>' + _esc(_scenShort(list[0].key)) + '</b>', _sdNum(evTotal) + ' events rolled up'),
        body: rb.body, tail: rb.tail
    });
}

function _atkKnownRoute(name) {
    const bare = String(name || '').split('@')[0];
    if (!bare) return '';
    const pool = window._lastRenderedApps || (typeof APP_DATA !== 'undefined' ? APP_DATA : []) || [];
    const hit = pool.find(x => String(x.name || '').split('@')[0] === bare);
    return hit ? String(hit.name) : '';
}

function _atkCardRoutes(d) {
    const key = 'routes';
    const accent = 'var(--purple)';
    const ic = 'ph-fill ph-arrows-split';
    const title = 'Targeted routes';
    if (!d.alertsOk) {
        return _atkBlindCard({
            key: key, wide: true, accent: accent, ic: ic, title: title,
            state: 'needs a watcher login', sub: 'routers live in <b>alert.meta[]</b>',
            note: 'CrowdSec writes <code>traefik_router_name</code> and <code>target_fqdn</code> into an alert only when they are listed in its context file. '
                + 'They name the router and the host an attacker went through. ' + ATK_MACHINE_NOTE,
            go: ATK_NEEDS_MACHINE, goLabel: 'settings', goTip: 'Open Settings, System Monitoring, CrowdSec'
        });
    }
    if (!d.retained) {
        return _atkCalmCard(key, accent, ic, title, true, 'nothing was aimed at',
            'Routers come from alert-level <code>meta[]</code>. No scenario fired, so nothing wrote one.',
            _atkOwnFlag(d.own));
    }
    if (!d.alerts.length) {
        return _atkFilteredCard(key, accent, ic, title, true, d.retained);
    }
    if (!d.alerts.some(a => a.routers.length || a.hosts.length)) {
        return _atkCalmCard(key, accent, ic, title, true, 'no router in the evidence',
            'Add <code>traefik_router_name</code> and <code>target_fqdn</code> to your CrowdSec context file and they appear here, '
            + 'naming the route each attack came through.', '');
    }
    const list = _atkRank(d.alerts, a => a.routers, { weight: a => a.events, kind: a => a.hosts[0] || '' });
    const hosts = _atkRank(d.alerts, a => a.hosts, { weight: a => a.events });
    const withR = d.alerts.filter(a => a.routers.length).length;
    const rb = _atkRankBody(list, {
        noun: 'routers', unitN: 'hits',
        label: e => String(e.key).split('@')[0],
        kindLabel: e => Array.from(e.kinds.keys())[0] || '',
        glyph: e => _atkKnownRoute(e.key)
            ? '<i class="ph-bold ph-arrows-split"></i>'
            : '<i class="ph-bold ph-question"></i>',
        go: e => _atkSpec({ router: e.key }),
        tipName: e => _atkKnownRoute(e.key) ? e.key : e.key + ', no route of that name here'
    });
    return _atkCard({
        key: key, cls: 'lg-wide', accent: accent, ic: ic, title: title,
        total: _sdNum(list.length) + '<span class="lg-unit">routers</span>',
        flags: hosts.slice(0, 3).map(h => _atkFlag({
            cls: 'd-blue', ic: 'ph-bold ph-globe', n: h.n, label: h.key,
            go: _atkSpec({ host: h.key }), tip: _sdNum(h.n) + ' alerts named ' + h.key + '. Click to filter the evidence below'
        })).join(''),
        sub: _atkSub(list.length ? 'most wanted <b>' + _esc(String(list[0].key).split('@')[0]) + '</b>' : 'no routers',
            _sdNum(withR) + ' of ' + _sdNum(d.alerts.length) + ' alerts name a router'),
        body: rb.body, tail: rb.tail
    });
}

function _atkCardTargets(d) {
    const key = 'targets';
    const accent = 'var(--blue)';
    const ic = 'ph-fill ph-target';
    if (!d.alertsOk) {
        return _atkBlindCard({
            key: key, wide: true, accent: accent, ic: ic, title: 'Targeted paths',
            state: 'needs a watcher login', sub: 'paths live in <b>alert.meta[]</b>',
            note: 'The alert-level <code>meta[]</code> array carries <code>target_uri</code>, <code>method</code>, <code>status</code> and <code>user_agent</code>, '
                + 'already deduplicated by the scenario. It is the only place this tab can learn what an attacker was going after. ' + ATK_MACHINE_NOTE,
            go: ATK_NEEDS_MACHINE, goLabel: 'settings', goTip: 'Open Settings, System Monitoring, CrowdSec'
        });
    }
    if (!d.retained) {
        return _atkCalmCard(key, accent, ic, 'Targeted paths', true, 'nothing was aimed at',
            'Paths come from alert-level <code>meta[]</code>. No scenario fired, so nothing wrote one. This is a quiet host, not a host that cannot see.',
            _atkOwnFlag(d.own));
    }
    if (!d.alerts.length) {
        return _atkFilteredCard(key, accent, ic, 'Targeted paths', true, d.retained);
    }
    const httpOn = d.alerts.some(a => a.uris.length);
    const sshOn = d.alerts.some(a => a.users.length);
    if (httpOn) {
        const list = _atkRank(d.alerts, a => a.uris, { weight: a => a.events, kind: a => a.verbs.join('/') });
        const verbs = _atkRank(d.alerts, a => a.verbs, {});
        const withUri = d.alerts.filter(a => a.uris.length).length;
        const rb = _atkRankBody(list, {
            noun: 'paths', unitN: 'hits',
            label: e => e.key,
            kindLabel: e => Array.from(e.kinds.keys())[0] || '',
            glyph: () => '<i class="ph-bold ph-file-dashed"></i>',
            go: e => _atkSpec({ uri: e.key }),
            tipName: e => e.key
        });
        return _atkCard({
            key: key, cls: 'lg-wide', accent: accent, ic: ic, title: 'Targeted paths',
            total: _sdNum(list.length) + '<span class="lg-unit">paths</span>',
            flags: verbs.slice(0, 3).map(v => _atkFlag({
                cls: v.key === 'GET' ? 'd-off' : 'd-blue', ic: 'ph-bold ph-arrow-bend-right-up', n: v.n, label: v.key,
                go: _atkSpec({ verb: v.key }), tip: _sdNum(v.n) + ' alerts used ' + v.key + '. Click to filter the evidence below'
            })).join(''),
            sub: _atkSub(list.length ? 'most wanted <b>' + _esc(list[0].key) + '</b>' : 'no paths',
                _sdNum(withUri) + ' of ' + _sdNum(d.alerts.length) + ' alerts carry a path'),
            body: rb.body, tail: rb.tail
        });
    }
    if (sshOn) {
        const list = _atkRank(d.alerts, a => a.users, { weight: a => a.events });
        const withU = d.alerts.filter(a => a.users.length).length;
        const rb = _atkRankBody(list, {
            noun: 'accounts', unitN: 'hits',
            label: e => e.key, kindLabel: () => 'ssh',
            glyph: () => '<i class="ph-bold ph-user-focus"></i>',
            go: e => _atkSpec({ user: e.key }),
            tipName: e => 'login attempts against ' + e.key
        });
        return _atkCard({
            key: key, cls: 'lg-wide', accent: accent, ic: 'ph-fill ph-user-focus', title: 'Targeted accounts',
            total: _sdNum(list.length) + '<span class="lg-unit">accounts</span>',
            flags: _atkOk('no HTTP scenario fired', 'ph-bold ph-info'),
            sub: _atkSub(list.length ? 'most wanted <b>' + _esc(list[0].key) + '</b>' : 'no accounts',
                _sdNum(withU) + ' of ' + _sdNum(d.alerts.length) + ' alerts name an account'),
            body: rb.body,
            tail: rb.tail + '<p class="lg-note">SSH buckets carry <code>target_user</code> where HTTP buckets carry <code>target_uri</code>. This card follows whichever the host actually produces.</p>'
        });
    }
    return _atkBlindCard({
        key: key, wide: true, accent: accent, ic: ic, title: 'Targeted paths',
        state: 'no meta reported', sub: 'no alert carries <b>target_uri</b> or <b>target_user</b>',
        note: 'Alert-level <code>meta[]</code> is written by the scenario on the machine that raised the alert. It is absent on <code>cscli</code> alerts and on '
            + 'community blocklist pulls, so a host whose only alerts came from those sources has nothing to rank here.',
        go: 'clear=all', goLabel: 'clear filters', goTip: 'Remove every filter and look at the whole retained window'
    });
}

function _atkCardAgents(d) {
    if (!d.alertsOk) {
        return _atkBlindCard({
            key: 'agents', accent: 'var(--teal)', ic: 'ph-fill ph-robot', title: 'Tooling',
            state: 'needs a watcher login', sub: 'user agents live in <b>alert.meta[]</b>',
            note: 'Same source as the paths card: alert-level <code>meta[]</code>, reachable only with machine credentials. ' + ATK_MACHINE_NOTE,
            go: ATK_NEEDS_MACHINE, goLabel: 'settings', goTip: 'Open Settings, System Monitoring, CrowdSec'
        });
    }
    if (!d.retained) {
        return _atkCalmCard('agents', 'var(--teal)', 'ph-fill ph-robot', 'Tooling', false, 'no tool announced itself',
            'User agents come from the same <code>meta[]</code> as the paths. Nothing got far enough to leave one.',
            _atkOwnFlag(d.own));
    }
    if (!d.alerts.length) {
        return _atkFilteredCard('agents', 'var(--teal)', 'ph-fill ph-robot', 'Tooling', false, d.retained);
    }
    if (!d.alerts.some(a => a.uas.length)) {
        const httpFired = d.alerts.some(a => a.uris.length || a.verbs.length || a.codes.length);
        return _atkBlindCard({
            key: 'agents', accent: 'var(--teal)', ic: 'ph-fill ph-robot', title: 'Tooling',
            state: httpFired ? 'not logged' : 'HTTP only',
            sub: httpFired ? 'the access log carries no user agent' : 'no HTTP scenario fired here',
            note: httpFired
                ? 'HTTP scenarios did fire and their paths, methods and status codes came through, so only the '
                  + '<code>user_agent</code> key is missing. Traefik drops request headers from its access log unless '
                  + 'you keep them, so CrowdSec never sees one. Add <code>User-Agent: keep</code> under '
                  + '<code>accessLog.fields.headers.names</code> in the static config, then restart Traefik.'
                : 'The <code>user_agent</code> meta key is written by HTTP scenarios. SSH buckets such as '
                  + '<code>crowdsecurity/ssh-bf</code> share none of the HTTP keys, so this card stays out of the way '
                  + 'rather than rendering an empty list.',
            go: 'clear=all', goLabel: 'clear filters', goTip: 'Remove every filter and look at the whole retained window'
        });
    }
    const list = _atkRank(d.alerts, a => a.uas.map(_uaShort), { weight: a => a.events });
    const withUa = d.alerts.filter(a => a.uas.length).length;
    const isBot = k => !/^Chrome|^Headless|^Firefox|^Safari|^Edg|^Mozilla/.test(k);
    const bots = list.filter(e => isBot(e.key));
    const rb = _atkRankBody(list, {
        noun: 'agents', unitN: 'hits',
        label: e => e.key,
        kindLabel: e => isBot(e.key) ? 'tool' : 'browser string',
        glyph: e => isBot(e.key) ? '<i class="ph-bold ph-terminal-window"></i>' : '<i class="ph-bold ph-browser"></i>',
        go: e => _atkSpec({ agent: e.key }),
        tipName: e => (e.rows[0] && e.rows[0].uas[0]) || e.key
    });
    return _atkCard({
        key: 'agents', accent: 'var(--teal)', ic: 'ph-fill ph-robot', title: 'Tooling',
        total: _sdNum(list.length),
        flags: _atkFlag({ cls: 'd-off', ic: 'ph-bold ph-terminal-window', n: bots.length, label: 'tools', tag: 'span',
            tip: _sdNum(bots.length) + ' agents name a tool outright. The rest are copied browser strings, which tells you the operator bothered to lie' }),
        sub: _atkSub(list.length ? 'worst <b>' + _esc(list[0].key) + '</b>' : 'no agents',
            _sdNum(withUa) + ' of ' + _sdNum(d.alerts.length) + ' alerts carry one'),
        body: rb.body, tail: rb.tail
    });
}

function _atkCardBans(d) {
    if (!d.lapiOk) {
        return _atkBlindCard({
            key: 'bans', accent: 'var(--green)', ic: 'ph-fill ph-shield-check', title: 'Bans in force',
            state: 'LAPI unreachable', sub: 'nothing was read from <b>/v1/decisions</b>',
            note: 'This card reports the read failure instead of the zero it would otherwise invent. ' + _esc(d.decErr || ''),
            go: 'cfg=lapi', goLabel: 'settings', goTip: 'Check the LAPI URL and the bouncer key in Settings'
        });
    }
    const sum = d.decSum;
    const origins = sum.origins;
    const nOrigin = k => Number(origins[k]) || 0;
    const total = sum.total;
    const own = sum.own;
    const subscribed = sum.subscribed;
    const local = nOrigin('crowdsec');
    const hand = Math.max(0, own - local);
    const cscli = nOrigin('cscli') + nOrigin('manual');
    const otherNames = Object.keys(origins).filter(k => k !== 'crowdsec' && !ATK_BY_HAND[k] && !ATK_SUBSCRIBED[k] && nOrigin(k) > 0);
    const otherOwn = otherNames.reduce((a, k) => a + nOrigin(k), 0);
    const capi = nOrigin('capi');
    const lists = nOrigin('lists');
    const bans = Number(sum.types.ban) || 0;
    const captcha = Number(sum.types.captcha) || 0;
    const wide = sum.wide;
    const rows = sum.rows;
    const lab = x => x.value + ' - ' + x.type + ', ' + (x.origin || 'unknown') + ', ' + _scenShort(x.scenario)
        + (x.duration ? ', ' + x.duration + ' left' : '') + (x.scope !== 'Ip' ? ', ' + x.scope + ' scope' : '');
    return _atkCard({
        key: 'bans', accent: d.stale ? 'var(--yellow)' : 'var(--green)',
        ic: d.stale ? 'ph-fill ph-clock-countdown' : 'ph-fill ph-shield-check',
        title: d.stale ? 'Bans in force (stale)' : 'Bans in force',
        note: d.stale ? _esc(d.stale) : undefined,
        total: _sdNum(total),
        flags: _atkFlag({ cls: 'd-off', ic: 'ph-bold ph-prohibit', n: bans, label: 'ban',
                go: _atkSpec({ type: 'ban' }), tip: 'Show only ban decisions in the decisions view' })
            + (captcha ? _atkFlag({ cls: 'd-warn', ic: 'ph-bold ph-puzzle-piece', n: captcha, label: 'captcha',
                go: _atkSpec({ type: 'captcha' }), tip: 'Show only captcha decisions' }) : ''),
        sub: _atkSub('<b>' + _sdNum(own) + '</b> from this host', _sdNum(subscribed) + ' subscribed'),
        body: _atkStrip([
            { cls: 'sig-cell-warn', n: hand, at: i => (i < rows.length ? lab(rows[i]) : 'added by hand') },
            { cls: 'atk-cell-own', n: local, at: () => 'raised by your own scenarios' },
            { cls: 'sig-cell-idle', n: subscribed, at: () => 'subscribed from a blocklist' }
        ], _sdNum(total) + ' decisions, ' + _sdNum(own) + ' from this host',
            { noun: 'decisions', empty: 'nothing blocked' }),
        foot: _atkProv({ ic: 'ph-bold ph-crosshair', n: local, label: 'crowdsec', go: _atkSpec({ origin: 'crowdsec' }),
                tip: 'Raised by your own scenarios. These are the only decisions that prove something reached this host' })
            + _atkProv({ ic: 'ph-bold ph-terminal', n: cscli, label: 'by hand', cls: 'sig-prov-warn', go: _atkSpec({ origin: 'byhand' }),
                tip: 'Added by hand, from this UI or from the CLI. CrowdSec labels these cscli or manual depending on its version' })
            + _atkProv({ ic: 'ph-bold ph-users-three', n: capi, label: 'CAPI', go: _atkSpec({ origin: 'capi' }),
                tip: 'Pulled from the central API community blocklist. Preventive, not evidence of an attack on you' })
            + _atkProv({ ic: 'ph-bold ph-list-bullets', n: lists, label: 'lists', go: _atkSpec({ origin: 'lists' }),
                tip: 'Pulled from a subscribed third party blocklist' })
            + (otherOwn ? _atkProv({ ic: 'ph-bold ph-dots-three-circle', n: otherOwn, label: 'other', go: '',
                tip: 'Origins outside the four CrowdSec uses today: ' + otherNames.map(k => k || 'blank').join(', ')
                    + '. Counted as yours, because only CAPI and lists are subscriptions' }) : '')
            + (wide ? _atkProv({ ic: 'ph-bold ph-selection-all', n: wide, label: 'wide', go: '',
                tip: _sdNum(wide) + ' decisions are Range or Country scoped, so they cover far more addresses than one row suggests. '
                    + 'The loose and banned split above matches on the exact address, so a source covered only by one of these reads as loose' }) : ''),
        go: 'view=decisions', goLabel: 'decisions', goTip: 'Open the decisions view, the secondary table behind the alert stream'
    });
}

function _atkDownPanel(d) {
    return '<section class="sig-ep"><div class="sig-ep-head">'
        + '<i class="ph-fill ph-plugs sig-ep-headic d-bad"></i>'
        + '<span class="sc-sec-label">Nothing was read</span>'
        + '<span class="sc-sec-rule"></span></div>'
        + '<div class="atk-empty"><i class="ph-fill ph-warning-octagon"></i>'
        + '<div class="atk-empty-t">The LAPI did not answer</div>'
        + '<p class="lg-note">Neither <code>/v1/decisions</code> nor <code>/v1/alerts</code> responded, so there are no cards to draw. '
        + 'A grid of zeroes would be an invention. ' + _esc(d.decErr || '') + '</p>'
        + '<div class="atk-empty-do">'
        + _atkFlag({ cls: 'd-blue', ic: 'ph-bold ph-gear', n: '', label: 'check the LAPI url and key', go: 'cfg=lapi', tip: 'Open Settings, System Monitoring, CrowdSec' })
        + _atkFlag({ cls: 'd-blue', ic: 'ph-bold ph-arrows-clockwise', n: '', label: 'read again', go: 'reload=1', tip: 'Refetch both endpoints' })
        + '</div></div></section>';
}

function _atkVerdict(d, sel) {
    let health = 'up', ic = 'ph-fill ph-shield-check', txt = 'Surface held';
    const items = [];
    if (!d.lapiOk && !d.alertsOk) {
        health = 'down'; ic = 'ph-fill ph-warning-octagon'; txt = 'LAPI unreachable';
        items.push(_atkFlag({ cls: 'd-bad', ic: 'ph-bold ph-plugs', n: '', label: 'nothing was read',
            tip: d.decErr || 'Both the decisions and the alerts read failed' }));
        items.push(_atkFlag({ cls: 'd-blue', ic: 'ph-bold ph-gear', n: '', label: 'check LAPI url', go: 'cfg=lapi', tip: 'Open Settings, System Monitoring, CrowdSec' }));
    } else if (!d.lapiOk) {
        health = 'warn'; ic = 'ph-fill ph-warning-circle'; txt = 'Attacks visible, bans are not';
        items.push(_atkFlag({ cls: 'd-warn', ic: 'ph-bold ph-key', n: '', label: 'no decisions read',
            tip: (d.decErr || 'The decisions read failed.') + ' A bouncer API key is the only credential CrowdSec accepts on /v1/decisions, and the loose versus banned split needs it' }));
        items.push(_atkFlag({ cls: 'd-on', ic: 'ph-bold ph-crosshair', n: d.alerts.length, label: 'alerts readable',
            go: 'clear=all', tip: 'The machine login works, so every attack card above is live' }));
        items.push(_atkFlag({ cls: 'd-blue', ic: 'ph-bold ph-gear', n: '', label: 'add a bouncer key', go: 'cfg=lapi',
            tip: 'Set CROWDSEC_API_KEY so the tab can read active decisions' }));
    } else if (!d.alertsOk) {
        health = 'warn'; ic = 'ph-fill ph-warning-circle'; txt = 'Bans visible, attacks are not';
        items.push(_atkFlag({ cls: 'd-warn', ic: 'ph-bold ph-key', n: '',
            label: d.altStatus ? '/v1/alerts returns ' + d.altStatus : 'alerts not readable',
            tip: (d.altErr || 'A bouncer API key cannot read alerts.') + ' That is a permission boundary, not an absence of attacks' }));
        items.push(_atkFlag({ cls: 'd-on', ic: 'ph-bold ph-shield-check', n: d.decTotal, label: 'bans in force',
            go: 'view=decisions', tip: 'The decisions view works on a bouncer key alone' }));
        items.push(_atkFlag({ cls: 'd-blue', ic: 'ph-bold ph-gear', n: '', label: 'add machine login', go: ATK_NEEDS_MACHINE,
            tip: 'Set CROWDSEC_MACHINE_ID and CROWDSEC_MACHINE_PASSWORD' }));
    } else if (!d.retained) {
        ic = 'ph-fill ph-moon-stars'; txt = 'Nothing tripped a scenario';
        items.push(_atkFlag({ cls: 'd-on', ic: 'ph-bold ph-shield-check', n: d.decTotal, label: 'bans standing',
            go: 'view=decisions', tip: d.own
                ? _sdNum(d.own) + ' of them were raised here rather than subscribed, but no alert in the retained window explains them'
                : 'All of them subscribed, none earned by an attack on this host' }));
        items.push(d.own
            ? _atkOwnFlag(d.own)
            : '<span class="sig-mono">no local detection in the retained window</span>');
    } else if (!d.alerts.length) {
        ic = 'ph-fill ph-funnel'; txt = 'Nothing matches';
        items.push('<span class="sig-mono">0 of ' + _sdNum(d.retained) + ' retained alerts match every filter at once</span>');
        items.push(_atkFlag({ cls: 'd-blue', ic: 'ph-bold ph-x', n: '', label: 'clear filters', go: 'clear=all',
            tip: 'Remove every filter and the search box' }));
    } else {
        const loose = sel.sources - sel.banned;
        const ev = d.alerts.reduce((a, x) => a + x.events, 0);
        if (loose > 0) { health = 'warn'; ic = 'ph-fill ph-warning-circle'; txt = 'Actively probed'; }
        items.push(_atkFlag({ cls: 'd-off', ic: 'ph-bold ph-crosshair', n: sel.sources, label: 'sources', go: 'clear=all',
            tip: _sdNum(sel.sources) + ' distinct addresses tripped at least one scenario in the retained window' }));
        items.push(_atkFlag({ cls: 'd-off', ic: 'ph-bold ph-lightning', n: sel.scenarios, label: 'scenarios', tag: 'span',
            tip: 'Distinct scenarios that fired' }));
        items.push(_atkFlag({ cls: 'd-off', ic: 'ph-bold ph-pulse', n: ev, label: 'events', tag: 'span',
            tip: 'Sum of events_count, the raw log lines that rolled up into these alerts. Always larger than the alert count' }));
        if (d.capped) {
            items.push(_atkFlag({ cls: 'd-warn', ic: 'ph-bold ph-funnel', n: d.limit, label: 'alert cap reached', tag: 'span',
                tip: 'CrowdSec returned as many alerts as the cap allows, so older ones are not counted here. '
                   + 'Raise CROWDSEC_ALERT_LIMIT, or the alert limit in Settings, to see further back' }));
        }
        if (loose > 0) {
            items.push(_atkFlag({ cls: 'd-warn', ic: 'ph-bold ph-lock-open', n: loose, label: 'no active ban',
                go: _atkSpec({ outcome: 'loose' }),
                tip: 'These sources tripped a scenario and hold no decision now. Usually an expired ban rather than a miss' }));
        } else {
            items.push('<span class="sig-mono">every source that tripped a scenario is banned'
                + (sel.sim ? '' : ', no scenario is in simulation mode') + '</span>');
        }
        if (sel.sim) {
            items.push(_atkFlag({ cls: 'd-warn', ic: 'ph-bold ph-eye-slash', n: sel.sim, label: 'simulated',
                go: _atkSpec({ outcome: 'sim' }),
                tip: 'Simulation mode: CrowdSec matched the scenario and enforced nothing' }));
        }
    }
    return '<div class="sig-verdict" data-health="' + health + '">'
        + '<i class="' + ic + ' sig-verdict-ic"></i>'
        + '<span class="sig-verdict-txt">' + _esc(txt) + '</span>'
        + '<span class="sig-verdict-items">' + items.join('') + '</span>'
        + '<span class="sig-verdict-meta">' + (d.span ? _esc(_lgSpanTxt(d.span)) + ' of alerts' + SD_SEP : '')
        + 'read <b id="atkAge">' + _esc(_sdAgo(d.fetched)) + '</b></span></div>';
}

function _atkKeyRow(d, sel) {
    const facets = _atkActive();
    let html = '<span class="sig-key-lab">window</span>';
    if (d.alertsOk) {
        html += '<span class="sig-key-item lg-static" title="Alerts the LAPI still retains. CrowdSec prunes on its own schedule, so this is a retention window, not the start of activity">'
            + '<i class="ph-bold ph-siren"></i>retained<b>' + _sdNum(d.retained) + '</b>alerts</span>';
        if (d.span) {
            html += '<span class="sig-key-item lg-static" title="Oldest retained alert to newest, ' + _esc(_atkStamp(d.oldest)) + ' to ' + _esc(_atkStamp(d.newest)) + '">'
                + '<i class="ph-bold ph-clock-counter-clockwise"></i>span<b>' + _esc(_lgSpanTxt(d.span)) + '</b></span>';
        }
    } else {
        html += '<span class="sig-key-item sig-key-empty" title="' + _esc((d.altErr || 'The alerts endpoint refused the read.') + ' Zero is not the same as none')
            + '"><i class="ph-bold ph-siren"></i>retained<b>?</b>alerts</span>';
    }
    html += d.lapiOk
        ? '<span class="sig-key-item lg-static" title="Active decisions after expired rows are dropped. The cursor walk stops at 200 pages of 1000, so 200,000 is the undocumented ceiling">'
            + '<i class="ph-bold ph-shield-check"></i><b>' + _sdNum(d.decTotal) + '</b>bans</span>'
        : '<span class="sig-key-item sig-key-empty" title="The decisions read failed. Zero would be an invention, so this says nothing instead">'
            + '<i class="ph-bold ph-shield-check"></i><b>?</b>bans</span>';
    if (facets.length || _atkQuery) {
        html += '<span class="sig-key-lab">filters</span>';
        facets.forEach(k => {
            const v = _atkFacet[k];
            const alertOnly = !!ATK_ALERT_ONLY[k];
            const decOnly = !!ATK_DEC_ONLY[k];
            const ignored = (_atkView === 'decisions' && alertOnly) || (_atkView === 'alerts' && decOnly);
            const hit = sel.facetHits[k] || 0;
            const tip = ignored
                ? k + ' = ' + v + '. This filter only applies to ' + (alertOnly ? 'alerts' : 'decisions') + ' and is ignored in this view. Click to clear'
                : k + ' = ' + v + (hit ? ', ' + _sdNum(hit) + ' matches. Click to clear' : ', nothing matches this. Click to clear');
            html += '<button type="button" class="sig-key-item ' + ((hit && !ignored) ? 'sig-key-on' : 'sig-key-empty')
                + '" data-atk="' + _esc(_atkSpec({ [k]: v })) + '" title="' + _esc(tip) + '">'
                + '<i class="ph-bold ph-funnel"></i>' + _esc(k) + '<b>' + _esc(_atkClip(v, 24)) + '</b></button>';
        });
        if (_atkQuery) {
            html += '<span class="sig-key-item sig-key-on lg-static" title="Free text search over address, scenario, AS name, message, machine, paths, agents and accounts">'
                + '<i class="ph-bold ph-magnifying-glass"></i><b>' + _esc(_atkClip(_atkQuery, 24)) + '</b></span>';
        }
        html += '<button type="button" class="sig-key-item" data-atk="clear=all" title="Clear every filter and the search box"><i class="ph-bold ph-x"></i>clear</button>';
    }
    if (_atkView === 'decisions') {
        html += '<span class="sig-key-lab">showing</span>'
            + '<span class="sig-key-item sig-key-on lg-static" title="The feed below is listing active decisions rather than the alerts that caused them">'
            + '<i class="ph-bold ph-shield-check"></i>bans in force</span>'
            + '<button type="button" class="sig-key-item" data-atk="view=alerts" title="Go back to the attack evidence, the primary view">'
            + '<i class="ph-bold ph-crosshair"></i>back to alerts</button>';
    }
    const scoped = facets.length || _atkQuery;
    const scopeTxt = scoped
        ? _sdNum(sel.alerts.length) + ' of ' + _sdNum(d.retained) + ' retained alerts'
        : 'local detections only';
    const scopeTip = d.alertsOk
        ? 'Every card above summarises the ' + _sdNum(d.retained) + ' alerts the LAPI still retains, not every attack this host has ever seen. '
            + 'The oldest alert here is the edge of retention, not the start of activity, and CrowdSec does not report how many it pruned. '
            + 'Subscribed blocklist rows are left out on purpose because they describe the internet rather than your host. '
            + (scoped
                ? _sdNum(sel.alerts.length) + ' of them match every filter on this row at once. Click to drop the filters.'
                : 'Click to see the ' + _sdNum(sel.subscribed) + ' subscribed bans that were excluded.')
        : 'Only decisions were read. The alert stream is the source of every scenario, path, network and agent on this tab, and a bouncer key cannot see it.';
    html += (d.alertsOk && d.lapiOk)
        ? '<button type="button" class="sig-key-scope" data-atk="'
            + _esc(scoped ? 'clear=all' : _atkSpec({ view: 'decisions', origin: 'subscribed' }))
            + '" title="' + _esc(scopeTip) + '"><i class="ph-bold ph-funnel-simple"></i>' + _esc(scopeTxt) + '</button>'
        : '<span class="sig-key-scope lg-static" title="' + _esc(d.alertsOk
                ? 'Active decisions were not readable, so nothing here can say whether an attacking source is still banned.'
                : scopeTip)
            + '"><i class="ph-bold ph-eye-slash"></i>' + (d.alertsOk ? 'alerts only' : 'decisions only') + '</span>';
    return '<div class="sig-key" id="csKey">' + html + '</div>';
}

function _atkRuntime(d) {
    const f = [];
    const on = (ok, ic, txt, tip) => '<span class="sig-f ' + (ok ? 'sig-f-on' : 'sig-f-off') + '" title="' + _esc(tip) + '">'
        + '<i class="' + ic + '"></i>' + _esc(txt) + '</span>';
    f.push(on(d.lapiOk, 'ph-bold ph-key', d.lapiOk ? 'bouncer key' : 'no decisions read',
        'Reads /v1/decisions. CrowdSec rejects the machine token on that endpoint, so this key is not optional even when a watcher login exists'));
    f.push(on(d.alertsOk, 'ph-bold ph-identification-card', d.alertsOk ? 'machine login' : 'no machine login',
        'Reads /v1/alerts, the only source of scenarios, paths, networks and agents on this tab. The token lives one hour'));
    f.push(on(d.enrich, 'ph-bold ph-globe-hemisphere-west', d.enrich ? 'geoip-enrich' : 'no geoip-enrich',
        'The crowdsecurity/geoip-enrich parser on the reporting machine fills source.cn, source.as_name and the coordinates. The LAPI never computes them, it stores what the agent sent'));
    f.push(on(d.httpOn, 'ph-bold ph-target', d.httpOn ? 'HTTP meta' : 'no HTTP meta',
        'Alert meta[] carries target_uri, method, status and user_agent only for HTTP buckets'));
    f.push(on(d.sshOn, 'ph-bold ph-user-focus', d.sshOn ? 'SSH meta' : 'no SSH meta',
        'SSH buckets carry target_user instead, and share none of the HTTP keys'));
    f.push(on(d.hostGeo, 'ph-bold ph-map-pin', d.hostGeo ? 'host GeoIP DB' : 'crowdsec coordinates',
        d.hostGeo
            ? 'These alerts carry no country, so the map below was resolved by the host MaxMind database instead. Only alert sources are looked up, never the blocklist'
            : 'Countries below come straight from the alert, resolved by CrowdSec. No address is sent to the host GeoIP database'));
    return '<div class="sig-runtime" id="csRuntime">' + f.join('') + '</div>';
}

function _atkGeoPanel(alerts) {
    const counts = _csCountryCounts(alerts);
    if (!Object.keys(counts).length) return { html: '', counts: counts };
    return { html: _geoPanelHtml('csGeo', counts, _atkFacet.cc, 'clearCsCountryFilter()'), counts: counts };
}

function _atkAlertRow(a) {
    const open = _atkOpen === a.uuid;
    const drawn = Math.min(a.events, ATK_EV_CAP);
    const cellLab = i => _scenShort(a.scenario) + ' event ' + (i + 1) + ' of ' + _sdNum(a.events) + ', ' + a.ip;
    const strip = _atkStrip([{ cls: (a.handled || !a.known) ? '' : (a.simulated ? 'sig-cell-idle' : 'sig-cell-warn'), n: drawn, at: cellLab }],
        _sdNum(a.events) + ' events', { noun: 'events', cap: ATK_ROW_CELL_CAP, cls: 'sig-strip-xs' });
    const target = a.uris.length
        ? (a.verbs.join('/') + ' ' + a.uris.join(' '))
        : (a.users.length ? 'accounts ' + a.users.join(' ') : 'no target meta reported');
    const sub = [target, a.uas.length ? _uaShort(a.uas[0]) : 'no agent',
        _atkHhmm(a.start) + ' to ' + _atkHhmm(a.stop),
        a.capacity > 0 ? 'leaky ' + a.capacity + '/' + a.leakspeed : 'trigger'].join(' · ');
    let row = '<div class="sig-ep-row" role="button" tabindex="0"'
        + ((a.handled || !a.known) ? '' : (a.simulated ? ' data-health="idle"' : ' data-health="warn"'))
        + ' data-atk="' + _esc(_atkSpec({ open: a.uuid })) + '" title="' + _esc(a.message || (a.ip + ' ' + a.scenario)) + '">'
        + '<span class="sig-ep-id"><span class="sig-ep-name">' + _esc(a.ip || 'unknown') + '</span>'
        + '<span class="sig-idle-txt">' + _esc(_scenShort(a.scenario)) + '</span></span>'
        + '<span class="sig-ep-addr">'
        + (a.cc ? _flagEmoji(a.cc) + ' ' + _esc(a.cc) : '<span class="sig-idle-txt">no geo</span>')
        + (a.asName ? SD_SEP + _esc(_atkClip(a.asName, 16)) : '') + '</span>'
        + '<span class="sig-ep-strip">' + strip + '</span>'
        + '<span class="sig-ep-n">' + _sdNum(a.events) + '</span>'
        + '<span class="sig-ep-flags">'
        + (!a.known
            ? _atkFlag({ tag: 'span', cls: 'd-off', ic: 'ph-bold ph-question', n: '', label: 'unknown', words: false,
                tip: 'The decisions read failed, so whether this source is banned cannot be answered' })
            : a.handled
            ? _atkFlag({ tag: 'span', cls: 'd-off', ic: 'ph-bold ph-prohibit', n: '', label: 'banned', words: false,
                tip: 'This source holds an active ban raised by your own scenarios. Nothing to do about it' })
            : (a.simulated
                ? _atkFlag({ tag: 'span', cls: 'd-warn', ic: 'ph-bold ph-eye-slash', n: '', label: 'simulated', words: false,
                    tip: 'Simulation mode: CrowdSec matched this scenario and enforced nothing' })
                : _atkFlag({ tag: 'span', cls: 'd-warn', ic: 'ph-bold ph-lock-open', n: '', label: 'loose', words: false,
                    tip: 'No active decision for this source right now. The ban has probably expired' })))
        + ((!a.handled && a.ip)
            ? '<button type="button" class="sig-flag d-off atk-ban" data-atk="' + _esc(_atkSpec({ ban: a.ip }))
                + '" title="Ban this source. Opens the decision form with the address filled in, the type and duration stay yours to pick">'
                + '<i class="ph-bold ph-gavel"></i></button>' : '')
        + '<span class="sig-idle-txt">' + _esc(a.start ? _sdAgo(a.start) : 'no time') + '</span></span>'
        + '<span class="sig-ep-sub">' + _esc(sub) + '</span>'
        + '<span class="sig-ep-kind">' + _esc(_scenShort(a.scenario) + ' · ' + (a.uris[0] || a.users[0] || '-')) + '</span>'
        + '</div>';
    if (open) row += _atkAlertOpen(a);
    return row;
}

function _atkAlertOpen(a) {
    const kv = [];
    const push = (k, v) => kv.push('<span class="atk-k">' + _esc(k) + '</span><span class="atk-v">' + v + '</span>');
    const none = t => '<span class="atk-none">' + _esc(t) + '</span>';
    push('source', _atkFlag({ cls: 'd-blue', ic: 'ph-bold ph-crosshair', n: '', label: a.ip || 'unknown',
            go: _atkSpec({ ip: a.ip }), tip: 'Filter the evidence to this address' })
        + ' <span class="atk-none">' + _esc(a.scope + ' scope' + (a.range ? ', in ' + a.range : '') + ', ' + classifyIp(a.ip)) + '</span>');
    push('network', a.asName
        ? _atkFlag({ cls: 'd-mw', ic: 'ph-bold ph-tree-structure', n: '', label: a.asName + ' (AS' + a.asNum + ')',
            go: _atkSpec({ asn: a.asNum }), tip: 'Filter the evidence to this network' })
        : none('not reported by the agent that raised this alert'));
    push('country', a.cc
        ? _flagEmoji(a.cc) + ' ' + _esc(_csCountryName(a.cc))
            + (a.cn ? '' : ' <span class="atk-none">resolved by the host GeoIP database, the alert itself carries no country</span>')
            + (a.lat != null ? ' <span class="atk-none">' + _esc(a.lat + ', ' + a.lon
                + ' - CrowdSec coordinates, often a country centroid rather than a city') + '</span>' : '')
        : none('geoip-enrich not installed on the reporting machine'));
    push('scenario', _atkFlag({ cls: 'd-warn', ic: 'ph-bold ph-lightning', n: '', label: a.scenario,
            go: _atkSpec({ scenario: a.scenario }), tip: 'Filter the evidence to this scenario' })
        + (a.version ? ' <span class="atk-none">v' + _esc(a.version) + '</span>' : ''));
    push('bucket', a.capacity > 0
        ? _esc('leaky, capacity ' + a.capacity + ', leaks every ' + a.leakspeed)
            + ' <span class="atk-none">sustained pressure was needed to fire this</span>'
        : 'trigger <span class="atk-none">capacity 0, fires on the first matching event, so capacity and leakspeed say nothing here</span>');
    push('events', _sdNum(a.events)
        + ' <span class="atk-none">events_count is the bucket counter and is normally larger than the sampled events array the LAPI returns</span>');
    push('window', _esc(_atkStamp(a.start) + ' to ' + _atkStamp(a.stop))
        + ' <span class="atk-none">' + _esc(_lgSpanTxt(Math.max(0, a.stop - a.start))) + '</span>');
    if (a.routers.length) {
        const known = a.routers.map(rn => _atkKnownRoute(rn)).filter(Boolean);
        push('router', a.routers.map(rn => _atkFlag({ cls: 'd-blue', ic: 'ph-bold ph-arrows-split', n: '', label: String(rn).split('@')[0],
                go: _atkSpec({ router: rn }), tip: 'Filter the evidence to this router' })).join(' ')
            + known.map(rn => ' <button type="button" class="route-deep-chip" onclick="_openRouteByName(' + _jsArg(rn) + ')" title="Open this route">'
                + '<i class="ph-bold ph-arrow-square-out"></i>open</button>').join(''));
    }
    if (a.hosts.length) {
        push('host', a.hosts.map(h => _atkFlag({ cls: 'd-off', ic: 'ph-bold ph-globe', n: '', label: h,
            go: _atkSpec({ host: h }), tip: 'Filter the evidence to this host' })).join(' '));
    }
    if (a.uris.length) {
        push('paths', a.uris.map(u => _atkFlag({ cls: 'd-blue', ic: 'ph-bold ph-file-dashed', n: '', label: u,
            go: _atkSpec({ uri: u }), tip: 'Filter the evidence to this path' })).join(' '));
        push('verbs', (a.verbs.length
                ? a.verbs.map(v => _atkFlag({ cls: 'd-off', ic: 'ph-bold ph-arrow-bend-right-up', n: '', label: v,
                    go: _atkSpec({ verb: v }), tip: 'Filter the evidence to this verb' })).join(' ')
                : none('no method in meta[]'))
            + (a.codes.length ? ' <span class="atk-none">status ' + _esc(a.codes.join(' ')) + '</span>' : ''));
    } else if (a.users.length) {
        push('accounts', _esc(a.users.join(', '))
            + ' <span class="atk-none">target_user, the SSH counterpart of target_uri</span>');
    } else {
        push('target', none('this alert carries no meta[]. cscli and blocklist alerts never do'));
    }
    push('agent', a.uas.length
        ? _atkFlag({ cls: 'd-on', ic: 'ph-bold ph-robot', n: '', label: _uaShort(a.uas[0]),
            go: _atkSpec({ agent: _uaShort(a.uas[0]) }), tip: a.uas[0] })
            + ' <span class="atk-none">' + _esc(a.uas[0]) + '</span>'
        : none('no user_agent in meta[]'));
    const banAct = (!a.handled && a.ip)
        ? ' ' + _atkFlag({ cls: 'd-bad', ic: 'ph-bold ph-gavel', n: '', label: 'ban ' + a.ip,
            go: _atkSpec({ ban: a.ip }), tip: 'Open the decision form with this address filled in. Type, duration and reason stay yours to pick' })
        : '';
    push('outcome', !a.known
        ? none('the decisions read failed, so the ban state of this source is not knowable right now') + banAct
        : a.handled
        ? _atkFlag({ cls: 'd-off', ic: 'ph-bold ph-prohibit', n: '', label: 'active ban on ' + a.ip,
            go: _atkSpec({ view: 'decisions', ip: a.ip }), tip: 'Jump to the decisions view filtered to this source' })
        : (a.simulated
            ? _atkFlag({ cls: 'd-warn', ic: 'ph-bold ph-eye-slash', n: '', label: 'simulated, nothing enforced',
                go: _atkSpec({ outcome: 'sim' }), tip: 'Show every simulated alert' })
            : _atkFlag({ cls: 'd-warn', ic: 'ph-bold ph-lock-open', n: '', label: 'no active decision',
                go: _atkSpec({ outcome: 'loose' }), tip: 'Show every alert whose source is currently unbanned' })) + banAct);
    push('reported by', _esc(a.machine || 'unknown') + ' <span class="atk-none">alert ' + _esc(a.uuid) + '</span>');
    return '<div class="atk-open">' + kv.join('') + '</div>';
}

function _atkDecisionRow(x) {
    return '<div class="sig-ep-row" role="button" tabindex="0"'
        + (x.own ? (x.origin !== 'crowdsec' ? ' data-health="warn"' : '') : ' data-health="idle"')
        + ' data-atk="' + _esc(_atkSpec({ ip: x.value })) + '"'
        + ' title="' + _esc(x.value + ' - ' + x.type + ' from ' + (x.origin || 'unknown')
            + (x.duration ? ', ' + x.duration + ' remaining. The duration counts down live and is not the value originally requested' : '')) + '">'
        + '<span class="sig-ep-id"><span class="sig-ep-name">' + _esc(x.value) + '</span>'
        + '<span class="sig-idle-txt">' + _esc(x.scope) + '</span></span>'
        + '<span class="sig-ep-addr">' + _esc(_atkClip(_scenShort(x.scenario), 34)) + '</span>'
        + '<span class="sig-ep-n sig-ep-n0">' + _esc(x.duration || '-') + '</span>'
        + '<span class="sig-ep-flags">'
        + _atkFlag({ tag: 'span', cls: x.type === 'ban' ? 'd-bad' : (x.type === 'captcha' ? 'd-warn' : 'd-off'),
            ic: x.type === 'ban' ? 'ph-bold ph-prohibit' : (x.type === 'captcha' ? 'ph-bold ph-puzzle-piece' : 'ph-bold ph-check'),
            n: '', label: x.type, words: false, tip: x.type + ' decision, origin ' + (x.origin || 'unknown') })
        + (x.id ? '<button type="button" class="sig-flag d-off atk-unban" data-atk="' + _esc(_atkSpec({ unban: x.id }))
            + '" title="Remove this decision. DELETE /v1/decisions needs the machine token, a bouncer key is refused">'
            + '<i class="ph-bold ph-trash"></i></button>' : '')
        + '</span>'
        + '<span class="sig-ep-sub">' + _esc((x.origin || 'unknown') + ' origin · ' + (x.scenario || 'no scenario')
            + (x.duration ? ' · ' + x.duration + ' remaining' : '')
            + (x.scope !== 'Ip' ? ' · ' + x.scope + ' scope, one row covering many addresses' : '')) + '</span>'
        + '<span class="sig-ep-kind">' + _esc((x.origin || 'unknown') + ' ' + (x.duration || '')) + '</span></div>';
}

function _atkPager(page, pages, total, from, to, noun) {
    return '<div class="atk-page">'
        + '<button type="button" class="atk-pg" data-atk="' + _esc(_atkSpec({ page: Math.max(1, page - 1) })) + '"'
        + (page <= 1 ? ' disabled' : '') + '><i class="ph-bold ph-caret-left"></i>newer</button>'
        + '<span>' + _sdNum(from) + '-' + _sdNum(to) + ' of ' + _sdNum(total) + ' ' + _esc(noun) + '</span>'
        + '<button type="button" class="atk-pg" data-atk="' + _esc(_atkSpec({ page: Math.min(pages, page + 1) })) + '"'
        + (page >= pages ? ' disabled' : '') + '>older<i class="ph-bold ph-caret-right"></i></button>'
        + '<span class="lg-static" title="Rendered a page at a time, so a busy instance never builds tens of thousands of rows at once">page '
        + page + ' of ' + _sdNum(pages) + '</span></div>';
}

function _atkFeed(d, sel) {
    const alertsN = sel.alerts.length;
    const decN = sel.decTotal === null ? 0 : sel.decTotal;
    const isAlerts = _atkView === 'alerts';
    const altBlind = !d.alertsOk;
    const decBlind = !d.lapiOk;
    const alertsTxt = altBlind ? '?' : _sdNum(alertsN);
    const decTxt = decBlind ? '?' : (sel.decTotal === null ? '...' : _sdNum(decN));
    const altTip = (d.altErr || 'A bouncer API key cannot read alerts.') + ' Zero is not the same as none';
    const decTip = (d.decErr || 'The decisions read failed.') + ' Zero would be an invention, so this says nothing instead';
    const headBlind = isAlerts ? altBlind : decBlind;
    const head = '<div class="sig-ep-head">'
        + '<i class="' + (isAlerts ? 'ph-fill ph-crosshair' : 'ph-fill ph-shield-check') + ' sig-ep-headic"></i>'
        + '<span class="sc-sec-label">' + (isAlerts ? 'Attack evidence' : 'Bans in force') + '</span>'
        + '<span class="d-n"' + (headBlind ? ' title="' + _esc(isAlerts ? altTip : decTip) + '"' : '') + '>'
        + (isAlerts ? alertsTxt : decTxt) + '</span>'
        + '<span class="sc-sec-rule"></span>'
        + (isAlerts
            ? '<button type="button" class="atk-switch" data-atk="view=decisions" title="'
                + _esc(decBlind ? decTip : 'The resulting bans. Secondary view: decisions are what CrowdSec did, alerts are what happened') + '">'
                + '<i class="ph-bold ph-shield-check"></i>bans in force <b>' + decTxt + '</b><i class="ph-bold ph-arrow-right"></i></button>'
            : '<button type="button" class="atk-switch" data-atk="view=alerts" title="'
                + _esc(altBlind ? altTip : 'Back to the alert stream, the primary view') + '">'
                + '<i class="ph-bold ph-arrow-left"></i><i class="ph-bold ph-crosshair"></i>attack evidence <b>' + alertsTxt + '</b></button>')
        + '</div>';

    if (isAlerts && !d.alertsOk) {
        const body = '<div class="atk-empty"><i class="ph-fill ph-key"></i>'
            + '<div class="atk-empty-t">Not permitted to read alerts</div>'
            + '<p class="lg-note">The LAPI refused <code>/v1/alerts</code>'
            + (d.altStatus ? ' with <b>HTTP ' + d.altStatus + '</b>' : '') + '. '
            + 'A bouncer API key reads decisions only, and CrowdSec refuses the machine token on the decisions endpoint in return, '
            + 'so a full picture needs both credentials. The scenario, path, network and tooling cards above are not empty, they are not readable.'
            + (d.altErr ? '<br><br><code>' + _esc(d.altErr) + '</code>' : '') + '</p>'
            + '<div class="atk-empty-do">'
            + _atkFlag({ cls: 'd-blue', ic: 'ph-bold ph-gear', n: '', label: 'add machine credentials', go: ATK_NEEDS_MACHINE,
                tip: 'Set CROWDSEC_MACHINE_ID and CROWDSEC_MACHINE_PASSWORD' })
            + _atkFlag({ cls: 'd-on', ic: 'ph-bold ph-shield-check', n: '', label: 'see the ' + _sdNum(decN) + ' bans that do work',
                go: 'view=decisions', tip: 'The decisions view runs on the bouncer key alone' })
            + '</div></div>';
        return '<section class="sig-ep atk-feed">' + head + body + '</section>';
    }

    if (!isAlerts && !d.lapiOk) {
        const body = '<div class="atk-empty"><i class="ph-fill ph-key"></i>'
            + '<div class="atk-empty-t">Decisions were not read</div>'
            + '<p class="lg-note">Nothing came back from <code>/v1/decisions</code>, so this list is unknown rather than empty. '
            + 'CrowdSec accepts only a bouncer API key on that endpoint and refuses the machine token there.'
            + (d.decErr ? '<br><br><code>' + _esc(d.decErr) + '</code>' : '') + '</p>'
            + '<div class="atk-empty-do">'
            + _atkFlag({ cls: 'd-blue', ic: 'ph-bold ph-gear', n: '', label: 'check the LAPI url and key', go: 'cfg=lapi',
                tip: 'Open Settings, System Monitoring, CrowdSec' })
            + (d.alertsOk ? _atkFlag({ cls: 'd-on', ic: 'ph-bold ph-crosshair', n: '', label: 'back to the alert stream', go: 'view=alerts',
                tip: 'Alerts are readable with the machine login' }) : '')
            + '</div></div>';
        return '<section class="sig-ep atk-feed">' + head + body + '</section>';
    }

    if (!isAlerts && sel.decLoading) {
        const body = '<div class="atk-empty"><i class="ph-light ph-spinner-gap animate-spin"></i>'
            + '<div class="atk-empty-t">Reading decisions</div>'
            + '<p class="lg-note">The decisions view is paged on the server, so only the rows on screen travel to the browser.</p></div>';
        return '<section class="sig-ep atk-feed">' + head + body + '</section>';
    }
    if (!isAlerts && sel.decError) {
        const body = '<div class="atk-empty"><i class="ph-fill ph-plugs"></i>'
            + '<div class="atk-empty-t">Decisions could not be read</div>'
            + '<p class="lg-note"><code>' + _esc(sel.decError) + '</code></p>'
            + '<div class="atk-empty-do">'
            + _atkFlag({ cls: 'd-blue', ic: 'ph-bold ph-arrows-clockwise', n: '', label: 'read again', go: 'reload=1', tip: 'Refetch' })
            + '</div></div>';
        return '<section class="sig-ep atk-feed">' + head + body + '</section>';
    }
    const rows = isAlerts ? sel.alerts : sel.decisions;
    if (!rows.length) {
        const filtered = _atkActive().length || _atkQuery;
        const body = '<div class="atk-empty"><i class="' + (filtered ? 'ph-fill ph-funnel' : 'ph-fill ph-moon-stars') + '"></i>'
            + '<div class="atk-empty-t">' + (filtered ? 'Nothing matches' : (isAlerts ? 'No one has tripped a scenario' : 'Nothing is blocked')) + '</div>'
            + '<p class="lg-note">' + (filtered
                ? 'Every filter on the window row is applied together. Drop one and the rest stay.'
                : (isAlerts
                    ? 'No local scenario fired inside the retained window. Bans still standing all came from subscribed lists, which describe the internet rather than this host.'
                    : 'No decision is active. Either nothing was ever banned, or every ban has expired.')) + '</p>'
            + (filtered
                ? '<div class="atk-empty-do">'
                    + _atkFlag({ cls: 'd-blue', ic: 'ph-bold ph-x', n: '', label: 'clear filters', go: 'clear=all', tip: 'Remove every filter and the search box' })
                    + (isAlerts ? '' : _atkFlag({ cls: 'd-blue', ic: 'ph-bold ph-crosshair', n: '', label: 'back to alerts', go: 'view=alerts', tip: 'The primary view' }))
                    + '</div>'
                : '')
            + '</div>';
        return '<section class="sig-ep atk-feed">' + head + body + '</section>';
    }
    const pages = isAlerts ? Math.max(1, Math.ceil(rows.length / ATK_FEED_PAGE)) : sel.decPages;
    const page = isAlerts ? Math.min(_atkPage, pages) : sel.decPage;
    const from = (page - 1) * (isAlerts ? ATK_FEED_PAGE : sel.decPer);
    const slice = isAlerts ? rows.slice(from, from + ATK_FEED_PAGE) : rows;
    const totalRows = isAlerts ? rows.length : sel.decTotal;
    const body = '<div class="sig-ep-rows' + (isAlerts ? '' : ' atk-decs') + '">'
        + slice.map(isAlerts ? _atkAlertRow : _atkDecisionRow).join('') + '</div>'
        + _atkPager(page, pages, totalRows, from + 1, from + slice.length, isAlerts ? 'alerts' : 'decisions');
    return '<section class="sig-ep atk-feed">' + head + body + '</section>';
}

function _atkSelect() {
    const q = _atkQuery.toLowerCase();
    const alerts = _csAlerts.filter(a => _atkMatchAlert(a, q));
    const spec = _csDecSpec();
    const need = _csLapiOk && _csDecNeeded(spec);
    const page = (need && _csDecPage && _csDecPage.key === spec.key) ? _csDecPage : null;
    if (need && !page && _csDecKey !== spec.key) _csDecFetch(spec);
    const ips = new Set(alerts.map(a => a.ip));
    const bannedIps = new Set(alerts.filter(a => a.handled).map(a => a.ip));
    const facetHits = {};
    const live = _atkActive();
    if (live.length) {
        const saved = {};
        live.forEach(k => { saved[k] = _atkFacet[k]; });
        live.forEach(k => {
            if (ATK_DEC_ONLY[k]) { facetHits[k] = page ? (Number(page.facet_totals[k]) || 0) : 0; return; }
            live.forEach(o => { _atkFacet[o] = (o === k) ? saved[o] : ''; });
            facetHits[k] = _csAlerts.filter(a => _atkMatchAlert(a, q)).length;
        });
        live.forEach(k => { _atkFacet[k] = saved[k]; });
    }
    const sum = _csDecSum || _csEmptyDec();
    return {
        alerts: alerts,
        decisions: page ? page.rows : [],
        decTotal: page ? page.total : (need ? null : sum.total),
        decPage: page ? page.page : 1, decPages: page ? page.pages : 1, decPer: page ? page.per : ATK_FEED_PAGE,
        decLoading: need && !page,
        decError: page ? page.error : '',
        sources: ips.size, banned: bannedIps.size,
        sim: alerts.filter(a => a.simulated).length,
        subscribed: sum.subscribed,
        scenarios: new Set(alerts.map(a => a.scenario)).size,
        facetHits: facetHits,
    };
}

function _atkAnyFilter() {
    return _atkActive().length > 0 || !!_atkQuery
        || !!(document.getElementById('csSearch') || {}).value;
}

function clearCsFilters() {
    _atkClearFacets();
    _atkQuery = '';
    const box = document.getElementById('csSearch');
    if (box) box.value = '';
    _atkPage = 1; _atkOpen = '';
    _csRender();
}

function _atkPaintClear() {
    const wrap = document.getElementById('csClearWrap');
    if (wrap) wrap.style.display = _atkAnyFilter() ? '' : 'none';
}

function _csRender() {
    const el = document.getElementById('csStats');
    if (!el || !_csConfigured) return;
    const sel = _atkSelect();
    const d = {
        lapiOk: _csLapiOk, alertsOk: _csAlertsOk, altStatus: _csAltStatus, altErr: _csAltErr, decErr: _csDecErr,
        capped: _csAltCapped, limit: _csAltLimit,
        stale: _csDecStale,
        alerts: sel.alerts, decSum: _csDecSum || _csEmptyDec(), decTotal: sel.decTotal === null ? (_csDecSum ? _csDecSum.total : 0) : sel.decTotal,
        span: _csSpan, fetched: _csFetched,
        retained: _csAlerts.length,
        own: _csDecSum ? _csDecSum.own : 0,
        oldest: _csAlerts.length ? _csAlerts[_csAlerts.length - 1].start : 0,
        newest: _csAlerts.length ? _csAlerts[0].start : 0,
        enrich: _csAlerts.some(a => a.cn || a.asName),
        asnOn: _csAlerts.some(a => a.asName || a.asNum),
        httpOn: _csAlerts.some(a => a.uris.length),
        sshOn: _csAlerts.some(a => a.users.length),
        hostGeo: _csHostGeo,
    };
    const compact = (typeof tmPref === 'function' && tmPref('compactStatCards')) ? ' sig-compact' : '';
    let inner = _atkVerdict(d, sel) + _atkKeyRow(d, sel);
    let geo = { html: '', counts: {} };
    if (!d.lapiOk && !d.alertsOk) {
        inner += _atkRuntime(d) + _atkDownPanel(d);
    } else {
        const cards = [
            _atkCardSources(d), _atkCardNetworks(d), _atkCardScenarios(d),
            _atkCardTargets(d), _atkCardRoutes(d), _atkCardAgents(d), _atkCardBans(d),
        ].join('');
        geo = _atkGeoPanel(_csAlerts.filter(a => _atkMatchAlert(a, _atkQuery.toLowerCase(), { cc: 1 })));
        inner += '<div class="sig-grid" id="csGrid">' + cards + '</div>'
            + _atkRuntime(d) + geo.html + _atkFeed(d, sel);
    }
    el.innerHTML = '<div class="sig-wrap' + compact + '" id="csStatsPanel">' + inner + '</div>';
    _atkPaintClear();
    if (geo.html) {
        renderGeoMap(document.getElementById('csGeoMap'), geo.counts, csGeo_click, _atkFacet.cc);
    }
    _atkBind();
    _atkTickAge();
}

function openCsBanModal(prefill) {
    closeOtherPanels('csBanModal');
    document.getElementById('csBanIp').value       = typeof prefill === 'string' ? prefill : '';
    document.getElementById('csBanReason').value   = '';
    document.getElementById('csBanDuration').value = '24h';
    const errEl = document.getElementById('csBanError');
    if (errEl) errEl.style.display = 'none';
    _setCsBanType('ban');
    _csRenderBanRecent();
    document.getElementById('csBanModal').classList.add('open');
    document.getElementById('csBanBackdrop').classList.add('open');
    if (!setDetailDockOpen(true)) document.body.style.overflow = 'hidden';
    setTimeout(() => document.getElementById('csBanIp')?.focus(), 50);
}

function closeCsBanModal() {
    setDetailDockOpen(false);
    document.getElementById('csBanModal').classList.remove('open');
    document.getElementById('csBanBackdrop').classList.remove('open');
    document.body.style.overflow = '';
}

function _csRenderBanRecent() {
    const el = document.getElementById('csBanRecent');
    if (!el) return;
    const countEl = document.getElementById('csBanRecentCount');
    if (!_csLapiOk) {
        if (countEl) countEl.textContent = '';
        el.innerHTML = '<div class="text-center py-6 text-xs" style="color:var(--muted)">Decisions are not readable right now - '
            + '<code>/v1/decisions</code> needs a bouncer API key, so this list is unknown rather than empty</div>';
        return;
    }
    const mine = _csDecSum ? _csDecSum.rows : [];
    const more = _csDecSum ? (Number(_csDecSum.rows_more) || 0) : 0;
    if (countEl) countEl.textContent = mine.length ? _sdNum(mine.length + more) : '';
    if (!mine.length) {
        el.innerHTML = '<div class="text-center py-6 text-xs" style="color:var(--muted)">No custom decisions yet - decisions you add appear here</div>';
        return;
    }
    const colour = { ban: 'var(--red)', captcha: 'var(--yellow)', bypass: 'var(--green)' };
    el.innerHTML = mine.map(d => '<div class="flex items-center gap-2 py-1.5" style="border-bottom:1px solid var(--border)">'
        + '<span class="font-mono text-xs truncate" style="color:var(--text);flex:1;min-width:0" title="' + _esc(d.value || '-') + '">' + _esc(d.value || '-') + '</span>'
        + '<span class="text-xs font-semibold flex-shrink-0" style="color:' + (colour[d.type] || 'var(--muted)') + '">' + _esc(d.type || '-') + '</span>'
        + '<span class="text-xs truncate" style="color:var(--muted);max-width:150px" title="' + _esc(d.scenario || '') + '">' + _esc(d.scenario || '') + '</span>'
        + '<span class="text-xs flex-shrink-0 tabular-nums" style="color:var(--muted)" title="Time left on this decision, counting down live">' + _esc(d.duration || '-') + '</span>'
        + (d.id
            ? '<button onclick="csUnban(' + Number(d.id) + ')" class="btn-icon text-xs flex-shrink-0" title="Unban, delete this decision" style="color:var(--red)"><i class="ph-bold ph-trash"></i></button>'
            : '<span class="text-xs flex-shrink-0" style="color:var(--muted);opacity:.6">syncing...</span>')
        + '</div>').join('')
        + (more ? '<div class="text-center py-2 text-xs" style="color:var(--muted)">' + _sdNum(more) + ' more in the decisions view</div>' : '');
}

function _setCsBanType(type, btn) {
    _csBanType = type;
    document.querySelectorAll('[id^="csBanType-"]').forEach(b => b.classList.remove('active-http'));
    const el = document.getElementById('csBanType-' + type);
    if (el) el.classList.add('active-http');
}

async function submitCsBan() {
    const ip = (document.getElementById('csBanIp')?.value || '').trim();
    const errEl   = document.getElementById('csBanError');
    const errMsg  = document.getElementById('csBanErrorMsg');
    const submitBtn = document.querySelector('#csBanModal button[onclick="submitCsBan()"]');
    if (errEl) errEl.style.display = 'none';
    if (!ip) {
        if (errEl && errMsg) { errMsg.textContent = 'IP/Range is required'; errEl.style.display = 'flex'; }
        return;
    }
    const duration = document.getElementById('csBanDuration')?.value || '24h';
    const reason   = (document.getElementById('csBanReason')?.value || '').trim();
    if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = 'Adding...'; }
    try {
        const res = await agentFetch('/api/crowdsec/decisions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ..._csrfHeaders() },
            body: JSON.stringify({ value: ip, type: _csBanType, duration, reason }),
        });
        let data = {};
        try { data = await res.json() || {}; } catch (_) {}
        if (!res.ok) {
            const msg = data.error || data.message || ('Failed to add decision (HTTP ' + res.status + ')');
            if (errEl && errMsg) { errMsg.textContent = msg; errEl.style.display = 'flex'; }
            return;
        }
        document.getElementById('csBanIp').value = '';
        closeCsBanModal();
        showToast(`Decision added: ${_csBanType} ${ip} for ${duration}`, 'success');
        setTimeout(refreshCrowdSecTab, 800);
    } catch(e) {
        const msg = _netErrText(e, 'Failed to add decision');
        if (errEl && errMsg) { errMsg.textContent = msg; errEl.style.display = 'flex'; }
    } finally {
        if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = 'Add Decision'; }
    }
}

async function csUnban(id) {
    if (!id) return;
    const ok = (typeof _confirm === 'function')
        ? await _confirm('Delete decision ' + id + '? The address is unbanned immediately.', 'Remove decision', 'Delete')
        : true;
    if (!ok) return;
    try {
        const res = await agentFetch('/api/crowdsec/decisions/' + id, { method: 'DELETE' });
        let data = {};
        try { data = await res.json() || {}; } catch (_) {}
        if (res.ok && data.ok) { showToast('Decision ' + id + ' deleted', 'success'); refreshCrowdSecTab(); }
        else showToast(data.error || data.message || ('Failed to delete decision ' + id + ' (HTTP ' + res.status + ')'), 'error');
    } catch(e) { showToast(_netErrText(e, 'Failed to delete decision ' + id), 'error'); }
}

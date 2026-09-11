let _allLogLines     = [];
let _currentLogLines = 100;
const LG_CACHE_LINES = 1000;
let _logCountryFilter = '';
let _logParsed  = [];
let _logRows    = [];
let _logFacet   = { status:'', method:'', domain:'', path:'', ip:'', ipclass:'', service:'', router:'', provider:'', dur:'' };
let _lgBound    = false;
let _lgStamp    = 0;
let _lgAgeTimer = null;
let _lgSearchTimer = null;
let _lgLoadError = '';

const LG_LINE_STEPS = [100, 200, 500, 1000];
const LG_CELL_CAP   = 240;
const LG_ROW_CAP    = 6;

function setLogLines(n) {
    _currentLogLines = n;
    LG_LINE_STEPS.forEach(v => {
        document.getElementById('log-' + v)?.classList.toggle('active-http', v === n);
    });
    refreshLogs();
}

let _lgAutoTimer = null;

function _lgAutoOn() { return typeof tmPref === 'function' && tmPref('logsAutoRefresh') === true; }

function _lgAutoInterval() { return _currentLogLines >= 500 ? 30000 : 10000; }

function _lgTabLive() {
    const t = document.getElementById('tab-logs');
    return !!(t && t.classList.contains('active')) && !document.hidden;
}

function _lgAutoPaint() {
    const btn = document.getElementById('logAutoBtn');
    if (!btn) return;
    const on = _lgAutoOn();
    btn.classList.toggle('active-http', on);
    btn.innerHTML = '<i class="ph-bold ' + (on ? 'ph-pause' : 'ph-play') + '"></i>';
    btn.title = on ? 'Auto refresh every ' + (_lgAutoInterval() / 1000) + 's - click to pause' : 'Auto refresh off - click to start';
}

function _lgAutoSync() {
    clearInterval(_lgAutoTimer);
    _lgAutoTimer = null;
    _lgAutoPaint();
    if (!_lgAutoOn() || !_lgTabLive()) return;
    _lgAutoTimer = setInterval(() => {
        if (!_lgTabLive()) { _lgAutoSync(); return; }
        const el = document.activeElement;
        if (el && (el.id === 'logSearch' || el.tagName === 'INPUT' || el.tagName === 'TEXTAREA')) return;
        refreshLogs(true);
    }, _lgAutoInterval());
}

function toggleLogAutoRefresh() {
    if (typeof tmSetPref === 'function') tmSetPref('logsAutoRefresh', !_lgAutoOn());
    _lgAutoSync();
}

function _lgScrollEl() {
    const c = document.getElementById('logsContent');
    if (!c) return null;
    return [...c.querySelectorAll('div')].find(d => d.scrollHeight > d.clientHeight + 4 && getComputedStyle(d).overflowY === 'auto') || null;
}

document.addEventListener('visibilitychange', () => { if (typeof _lgAutoSync === 'function') _lgAutoSync(); });

function _lgHydrate(c) {
    _allLogLines = Array.isArray(c.lines) ? c.lines : [];
    _logParsed   = _allLogLines.map(raw => ({ raw, e: parseLogLine(raw) }));
    _lgStamp     = c.at || Date.now();
    _lgLoadError = '';
    _lgBind();
    renderLogs();
}

async function refreshLogs(silent) {
    const container = document.getElementById('logsContent');
    const stats = document.getElementById('logStats');
    if (!silent && tabCacheHydrate('logs', _lgHydrate)) silent = true;
    const keepScroll = silent ? (_lgScrollEl() || {}).scrollTop || 0 : 0;
    if (!silent) container.innerHTML = `<div class="text-center py-16" style="color:var(--muted)"><i class="ph-light ph-spinner-gap text-4xl block mb-3 animate-spin opacity-40"></i><p>Loading logs...</p></div>`;
    try {
        const logRes = await agentFetch(`/api/traefik/logs?lines=${_currentLogLines}`);
        if (!logRes.ok) {
            if (stats) stats.style.display = 'none';
            _lgLoadError = await _errText(logRes, 'Failed to load logs');
            container.innerHTML = `<div class="text-center py-16" style="color:var(--muted)">
                <i class="ph-light ph-plugs text-4xl block mb-3 opacity-40"></i>
                <p class="font-medium">Failed to load logs</p>
                <p class="text-xs mt-1 font-mono">${_esc(_lgLoadError)}</p>
                <button onclick="refreshLogs()" class="proto-btn text-xs px-3 py-1.5 mt-4"><i class="ph-bold ph-arrows-clockwise mr-1"></i>Retry</button>
            </div>`;
            return;
        }
        const res = await logRes.json();
        if (res.error) {
            if (stats) stats.style.display = 'none';
            container.innerHTML = _emptyMountState({
                icon: 'ph-terminal',
                title: 'Access log not mounted',
                description: 'Stream live Traefik access logs by enabling access logging in Traefik and mounting the log file into this container.',
                steps: [
                    { label: 'Enable access logging in your <code class="font-mono">traefik.yml</code>:',
                      code: 'accessLog:\n  filePath: "/logs/access.log"' },
                    { label: 'Add this volume to the <code class="font-mono">traefik-manager</code> service in your <code class="font-mono">docker-compose.yml</code>:',
                      code: '- /path/to/traefik/logs/access.log:/app/logs/access.log:ro' },
                ],
                note: 'Traefik must be restarted after adding <code class="font-mono">accessLog</code> to traefik.yml.'
            });
            return;
        }
        _lgLoadError = '';
        _allLogLines = res.lines || [];
        _logParsed = _allLogLines.map(raw => ({ raw, e: parseLogLine(raw) }));
        _lgStamp = Date.now();
        tabCachePut('logs', { lines: _allLogLines.slice(-LG_CACHE_LINES), at: _lgStamp });
        await loadGeoStatus();
        if (_geoEnabled && _geoAvailable) {
            await geoLookup(_logParsed.map(o => o.e && o.e.ip).filter(Boolean));
        }
        _lgBind();
        renderLogs();
        _lgAutoSync();
        if (keepScroll) {
            const sc = _lgScrollEl();
            if (sc) sc.scrollTop = keepScroll;
        }
    } catch (err) {
        if (stats) stats.style.display = 'none';
        _lgLoadError = _netErrText(err, 'Log request failed');
        container.innerHTML = `<div class="text-center py-16" style="color:var(--muted)">
            <i class="ph-light ph-plugs text-4xl block mb-3 opacity-40"></i>
            <p class="font-medium">Failed to load logs</p>
            <p class="text-xs mt-1 font-mono">${_esc(_lgLoadError)}</p>
            <button onclick="refreshLogs()" class="proto-btn text-xs px-3 py-1.5 mt-4"><i class="ph-bold ph-arrows-clockwise mr-1"></i>Retry</button>
        </div>`;
    }
}

function logGeo_click(cc) {
    _logCountryFilter = (_logCountryFilter === cc) ? '' : cc;
    renderLogs();
    _lgRevealList();
}
function clearLogCountryFilter() { _logCountryFilter = ''; renderLogs(); }

const HTTP_STATUS = {
    100:'Continue',101:'Switching Protocols',103:'Early Hints',
    200:'OK',201:'Created',202:'Accepted',204:'No Content',206:'Partial Content',
    301:'Moved Permanently',302:'Found',303:'See Other',304:'Not Modified',307:'Temporary Redirect',308:'Permanent Redirect',
    400:'Bad Request',401:'Unauthorized',402:'Payment Required',403:'Forbidden',404:'Not Found',405:'Method Not Allowed',
    406:'Not Acceptable',407:'Proxy Authentication Required',408:'Request Timeout',409:'Conflict',410:'Gone',
    411:'Length Required',413:'Payload Too Large',414:'URI Too Long',415:'Unsupported Media Type',
    418:'I am a teapot',421:'Misdirected Request',422:'Unprocessable Entity',426:'Upgrade Required',
    429:'Too Many Requests',431:'Request Header Fields Too Large',451:'Unavailable For Legal Reasons',
    500:'Internal Server Error',501:'Not Implemented',502:'Bad Gateway',503:'Service Unavailable',504:'Gateway Timeout',
    505:'HTTP Version Not Supported',507:'Insufficient Storage',511:'Network Authentication Required'
};

function _fmtLogDuration(ns) {
    if (!ns) return '';
    if (ns >= 1e9) return (ns / 1e9).toFixed(2) + 's';
    if (ns >= 1e6) return Math.round(ns / 1e6) + 'ms';
    if (ns >= 1e3) return Math.round(ns / 1e3) + 'µs';
    return ns + 'ns';
}

const LG_DUR_UNITS = { ns: 1e-6, 'µs': 1e-3, us: 1e-3, ms: 1, h: 3600000, m: 60000, s: 1000 };

function _lgParseDur(d) {
    if (d == null || d === '' || d === '-') return null;
    const s = String(d);
    const re = /(\d+(?:\.\d+)?)(ns|µs|us|ms|h|m|s)/g;
    let m, total = null;
    while ((m = re.exec(s)) !== null) total = (total || 0) + parseFloat(m[1]) * LG_DUR_UNITS[m[2]];
    if (total === null) { const v = parseFloat(s); return isNaN(v) ? null : v; }
    return total;
}

function _lgHostOnly(addr) {
    const s = String(addr || '');
    if (!s) return '';
    if (s.charAt(0) === '[') { const i = s.indexOf(']'); return i > 0 ? s.slice(1, i) : s; }
    const parts = s.split(':');
    return parts.length > 2 ? s : parts[0];
}

function parseLogLine(raw) {
    const trimmed = raw.trimStart();
    if (trimmed.startsWith('{')) {
        try {
            const j = JSON.parse(trimmed);
            if (j.RequestMethod || j.RequestPath || j.DownstreamStatus) {
                const durNs = typeof j.Duration === 'number' ? j.Duration : parseInt(j.Duration);
                const size = j.DownstreamContentSize != null ? j.DownstreamContentSize : (j.OriginContentSize != null ? j.OriginContentSize : '');
                const down = parseInt(j.DownstreamStatus);
                const orig = parseInt(j.OriginStatus);
                return {
                    format: 'json',
                    ip: j.ClientHost || _lgHostOnly(j.ClientAddr),
                    date: j.StartUTC || j.StartLocal || j.time || '',
                    method: j.RequestMethod || '',
                    path: j.RequestPath || '',
                    status: isFinite(down) ? down : (isFinite(orig) ? orig : 0),
                    origin: isFinite(orig) ? orig : null,
                    size: String(size),
                    domain: j.RequestHost || _lgHostOnly(j.RequestAddr),
                    scheme: j.RequestScheme || '',
                    ep: j.entryPointName || j.EntryPointName || '',
                    router: j.RouterName || '',
                    service: j.ServiceName || '',
                    serviceUrl: j.ServiceURL || j.ServiceAddr || '',
                    retries: Number(j.RetryAttempts) || 0,
                    tls: j.TLSVersion || '',
                    durMs: isFinite(durNs) ? durNs / 1e6 : null,
                    duration: _fmtLogDuration(isFinite(durNs) ? durNs : 0),
                    raw
                };
            }
        } catch (_) {}
    }
    const full = raw.match(
        /^(\S+) \S+ \S+ \[([^\]]+)\] "(\S+) (\S+)[^"]*" (\d+|-) (\S+) "[^"]*" "[^"]*" \S+ "([^"]*)" "([^"]*)" (\S+)/
    );
    if (full) return { format:'clf', ip:full[1], date:full[2], method:full[3], path:full[4],
        status: parseInt(full[5]) || 0, origin: null, size: full[6],
        domain: '', scheme: '', ep: '',
        router: full[7] === '-' ? '' : full[7], service: '',
        serviceUrl: full[8] === '-' ? '' : full[8],
        retries: 0, tls: '', durMs: _lgParseDur(full[9]), duration: full[9], raw };
    const basic = raw.match(/^(\S+) \S+ \S+ \[([^\]]+)\] "(\S+) (\S+)[^"]*" (\d+|-) (\S+)/);
    if (basic) return { format:'genericclf', ip:basic[1], date:basic[2], method:basic[3], path:basic[4],
        status: parseInt(basic[5]) || 0, origin: null, size: basic[6],
        domain: '', scheme: '', ep: '', router: '', service: '', serviceUrl: '',
        retries: 0, tls: '', durMs: null, duration: '', raw };
    return null;
}

const LG_MONTHS = { Jan:0, Feb:1, Mar:2, Apr:3, May:4, Jun:5, Jul:6, Aug:7, Sep:8, Oct:9, Nov:10, Dec:11 };

function _lgTime(e) {
    if (!e || !e.date) return null;
    const m = String(e.date).match(/^(\d{2})\/([A-Za-z]{3})\/(\d{4}):(\d{2}):(\d{2}):(\d{2})\s*([+-]\d{2})(\d{2})$/);
    if (m) {
        const mo = LG_MONTHS[m[2]];
        if (mo === undefined) return null;
        const base = Date.UTC(Number(m[3]), mo, Number(m[1]), Number(m[4]), Number(m[5]), Number(m[6]));
        const sgn = m[7].charAt(0) === '-' ? -1 : 1;
        return base - sgn * (Math.abs(Number(m[7])) * 60 + Number(m[8])) * 60000;
    }
    const t = Date.parse(e.date);
    return isFinite(t) ? t : null;
}

function _lgMs(v) {
    if (v == null) return '-';
    if (v >= 10000) return Math.round(v / 1000) + 's';
    if (v >= 1000) return (v / 1000).toFixed(2) + 's';
    if (v >= 1) return Math.round(v) + 'ms';
    if (v > 0) return (v.toFixed(2).replace(/0+$/, '').replace(/\.$/, '') || '0') + 'ms';
    return '0ms';
}

function _lgHeroMs(v) {
    if (v == null) return { n: '-', u: '' };
    if (v >= 1000) return { n: (v / 1000).toFixed(1), u: 's' };
    if (v >= 1) return { n: String(Math.round(v)), u: 'ms' };
    return { n: (v.toFixed(2).replace(/0+$/, '').replace(/\.$/, '') || '0'), u: 'ms' };
}

function _lgSpanOf(entries) {
    const t = entries.map(_lgTime).filter(v => v != null);
    if (t.length < 2) return null;
    return Math.max(...t) - Math.min(...t);
}

function _lgSpanTxt(ms) {
    const s = Math.max(0, Math.round(ms / 1000));
    if (s < 60) return s + 's';
    const m = Math.floor(s / 60);
    if (m < 60) return m + 'm ' + String(s % 60).padStart(2, '0') + 's';
    const h = Math.floor(m / 60);
    if (h < 24) return h + 'h ' + String(m % 60).padStart(2, '0') + 'm';
    return Math.floor(h / 24) + 'd ' + (h % 24) + 'h';
}

function _lgPattern(path) {
    const p = String(path || '').split('?')[0];
    if (!p || p.indexOf('/') < 0) return p;
    return p.split('/').map(seg => {
        if (!seg) return seg;
        if (/^\d+$/.test(seg)) return '<_>';
        if (/^\d{4}-\d{2}-\d{2}$/.test(seg)) return '<_>';
        if (/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(seg)) return '<_>';
        if (/^[0-9a-f]{12,}$/i.test(seg)) return '<_>';
        return seg;
    }).join('/');
}

function _lgProvider(name) { return String(name || '').split('@')[1] || ''; }

function _lgDurBand(v) {
    if (v == null) return '';
    if (v < 100) return 'fast';
    if (v < 500) return 'med';
    return 'slow';
}

function _lgStatusClass(s) {
    if (s >= 500 && s < 600) return '5xx';
    if (s >= 400 && s < 500) return '4xx';
    if (s >= 300 && s < 400) return '3xx';
    if (s >= 200 && s < 300) return '2xx';
    if (s >= 100 && s < 200) return '1xx';
    return 'other';
}

function _lgStatusMatch(s, spec) {
    if (spec === 'errors') return s >= 400;
    if (/^[1-5]xx$/.test(spec)) return _lgStatusClass(s) === spec;
    if (spec === 'other') return _lgStatusClass(s) === 'other';
    return String(s) === spec;
}

function _lgStatusName(s) { return s ? (HTTP_STATUS[s] || '') : 'tunnel'; }

function _lgHeldOpen(e) { return e.status === 101 || e.status === 0; }

const LG_IP_GLYPH = {
    'public':     ['ph-bold ph-globe', 'public'],
    'private':    ['ph-bold ph-house-line', 'private'],
    'cgnat':      ['ph-bold ph-arrows-in', 'cgnat'],
    'loopback':   ['ph-bold ph-circle-dashed', 'loopback'],
    'link-local': ['ph-bold ph-circle-dashed', 'link local'],
    'unknown':    ['ph-bold ph-circle-dashed', 'unknown'],
};

function _lgSpec(obj) {
    return Object.keys(obj).map(k => k + '=' + encodeURIComponent(obj[k])).join(';');
}

function _lgFacetHit(k, v, e) {
    if (!e) return false;
    switch (k) {
        case 'status':   return _lgStatusMatch(e.status, v);
        case 'method':   return e.method === v;
        case 'domain':   return e.domain === v;
        case 'path':     return v.charAt(0) === '~' ? _lgPattern(e.path) === v.slice(1) : e.path === v;
        case 'ip':       return e.ip === v;
        case 'ipclass':  return classifyIp(e.ip) === v;
        case 'service':  return e.service === v;
        case 'router':   return e.router === v;
        case 'provider': return _lgProvider(e.service || e.router) === v;
        case 'dur':      if (e.durMs == null) return false;
                         return v === 'held' ? _lgHeldOpen(e) : (!_lgHeldOpen(e) && _lgDurBand(e.durMs) === v);
    }
    return true;
}

function _lgActiveFacets() { return Object.keys(_logFacet).filter(k => _logFacet[k]); }

function _lgSelected() {
    const box = document.getElementById('logSearch');
    return !!(_lgActiveFacets().length || _logCountryFilter || (box && box.value));
}

function _lgMatch(e) {
    const keys = _lgActiveFacets();
    if (!keys.length) return true;
    if (!e) return false;
    return keys.every(k => _lgFacetHit(k, _logFacet[k], e));
}

function _lgErrStatus(e4, e5) { return (e4 && e5) ? 'errors' : (e5 ? '5xx' : '4xx'); }

function _lgClearFacets() { Object.keys(_logFacet).forEach(k => { _logFacet[k] = ''; }); }

function clearLogFilters() {
    _lgClearFacets();
    _logCountryFilter = '';
    const box = document.getElementById('logSearch');
    if (box) box.value = '';
    renderLogs();
}


function _lgRevealList() {
    revealBelowFold(document.getElementById('logsContent'));
}

function _lgGo(spec) {
    const p = {};
    String(spec || '').split(';').forEach(kv => {
        if (!kv) return;
        const i = kv.indexOf('=');
        if (i < 0) return;
        let v = kv.slice(i + 1);
        try { v = decodeURIComponent(v); } catch (_) {}
        p[kv.slice(0, i)] = v;
    });
    if ('clear' in p) {
        _lgClearFacets();
        if (p.clear === 'all') {
            _logCountryFilter = '';
            const box = document.getElementById('logSearch');
            if (box) box.value = '';
        }
        renderLogs();
        _lgRevealList();
        return;
    }
    if (p.cfg) { switchTab('static'); return; }
    if (p.lines) {
        const n = Number(p.lines);
        if (LG_LINE_STEPS.indexOf(n) >= 0 && n !== _currentLogLines) { setLogLines(n); return; }
        return;
    }
    const keys = Object.keys(p).filter(k => k in _logFacet);
    if (!keys.length) return;
    const same = keys.every(k => _logFacet[k] === p[k]);
    keys.forEach(k => { _logFacet[k] = same ? '' : p[k]; });
    renderLogs();
    _lgRevealList();
}

function _lgBind() {
    if (_lgBound) return;
    _lgBound = true;
    const inStats = el => { const r = document.getElementById('logStats'); return !!(r && el && r.contains(el)); };
    document.addEventListener('click', e => {
        const el = e.target.closest?.('[data-lg]');
        if (el && inStats(el)) { e.preventDefault(); _lgGo(el.getAttribute('data-lg')); return; }
        const row = e.target.closest?.('[data-lg-i]');
        if (!row) return;
        const list = document.getElementById('logsContent');
        if (!list || !list.contains(row)) return;
        const entry = _logRows[Number(row.getAttribute('data-lg-i'))];
        if (entry) openLogDetail(entry);
    });
    document.addEventListener('keydown', e => {
        if (e.key !== 'Enter' && e.key !== ' ') return;
        const el = e.target.closest?.('.lg-row[data-lg], .sig-ep-row[data-lg]');
        if (el && inStats(el)) { e.preventDefault(); _lgGo(el.getAttribute('data-lg')); return; }
        const row = e.target.closest?.('[data-lg-i]');
        if (!row) return;
        const list = document.getElementById('logsContent');
        if (!list || !list.contains(row)) return;
        e.preventDefault();
        const entry = _logRows[Number(row.getAttribute('data-lg-i'))];
        if (entry) openLogDetail(entry);
    });
}

function _lgTickAge() {
    clearInterval(_lgAgeTimer);
    _lgAgeTimer = setInterval(() => {
        const el = document.getElementById('logAge');
        if (!el) { clearInterval(_lgAgeTimer); _lgAgeTimer = null; return; }
        el.textContent = _sdAgo(_lgStamp);
    }, 15000);
}

function filterLogs() {
    clearTimeout(_lgSearchTimer);
    _lgSearchTimer = setTimeout(renderLogs, 120);
}

function _lgFlag(f) {
    const dead = !f.go;
    const tag = f.tag === 'span' || dead;
    return (tag ? '<span' : '<button type="button"')
        + ' class="sig-flag ' + f.cls + (f.extra ? ' ' + f.extra : '') + (dead ? ' lg-static' : '') + '"'
        + (dead ? '' : ' data-lg="' + _esc(f.go) + '"')
        + ' title="' + _esc(f.tip || (f.n + ' ' + f.label)) + '">'
        + '<i class="' + f.ic + '"></i>'
        + (f.n === '' ? '' : '<b>' + _sdNum(f.n) + '</b>')
        + (f.label && f.words !== false ? '<span class="sig-fl">' + _esc(f.label) + '</span>' : '')
        + (tag ? '</span>' : '</button>');
}

function _lgProv(p) {
    const dead = p.n === 0 || !p.go;
    return '<button type="button" class="sig-prov' + (p.cls ? ' ' + p.cls : '') + (dead ? ' lg-static' : '') + '"'
        + ' data-lg="' + _esc(dead ? '' : p.go) + '" title="' + _esc(p.tip) + '">'
        + '<i class="' + p.ic + '"></i>' + _esc(p.label)
        + (p.n === '' ? '' : '<b>' + _sdNum(p.n) + '</b>') + '</button>';
}

function _lgOk(txt, ic) {
    return '<span class="sig-ok"><i class="' + (ic || 'sig-dot') + '"></i>' + _esc(txt) + '</span>';
}

function _lgSub(main, tail) {
    return '<div class="sig-sub"><span class="sig-sub-main">' + main + '</span>'
        + (tail ? '<span class="sig-sub-tail">' + SD_SEP + tail + '</span>' : '') + '</div>';
}

function _lgCard(c) {
    return '<article class="sig-card' + (c.cls ? ' ' + c.cls : '') + '" data-card="' + c.key + '"'
        + (c.health ? ' data-health="' + c.health + '"' : '')
        + ' style="--tm-accent:' + c.accent + '">'
        + '<div class="sig-head"><span class="sig-ic"><i class="' + c.ic + '"></i></span>'
        + '<span class="sig-title">' + _esc(c.title) + '</span>'
        + (c.go ? '<button type="button" class="sig-explore" data-lg="' + _esc(c.go) + '" title="' + _esc(c.goTip || '') + '">'
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

function _lgRow(r) {
    return '<div class="lg-row" role="button" tabindex="0"'
        + (r.health ? ' data-health="' + r.health + '"' : '')
        + ' data-lg="' + _esc(r.go) + '" title="' + _esc(r.tip) + '">'
        + '<span class="lg-id">' + (r.glyph || '')
        + '<span class="lg-name">' + _esc(r.name) + '</span>'
        + (r.kind ? '<span class="lg-kind">' + _esc(r.kind) + '</span>' : '') + '</span>'
        + (r.bad || '<span class="lg-bad"></span>')
        + '<span class="lg-n">' + _sdNum(r.n) + '</span>'
        + '<span class="lg-pct">' + r.pct + '%</span></div>';
}

function _lgStrip(groups, aria, extraCls) {
    const live = groups.filter(g => g.items.length);
    const total = live.reduce((a, g) => a + g.items.length, 0);
    let html = '';
    if (!total) {
        html = '<span class="sig-more" style="margin-left:0">no requests</span>';
    } else if (total <= LG_CELL_CAP) {
        live.forEach(g => g.items.forEach(t => {
            html += '<i class="sig-cell' + (g.cls ? ' ' + g.cls : '') + '" title="' + _esc(t) + '"></i>';
        }));
    } else {
        const per = total / LG_CELL_CAP;
        let drawn = 0;
        live.forEach((g, gi) => {
            const last = gi === live.length - 1;
            let want = last ? LG_CELL_CAP - drawn : Math.max(1, Math.round(g.items.length / per));
            want = Math.max(0, Math.min(want, LG_CELL_CAP - drawn));
            for (let i = 0; i < want; i++) {
                const t = g.items[Math.min(g.items.length - 1, Math.floor(i * g.items.length / want))];
                html += '<i class="sig-cell' + (g.cls ? ' ' + g.cls : '') + '" title="' + _esc(t) + '"></i>';
            }
            drawn += want;
        });
        html += '<span class="sig-more" title="' + _sdNum(total) + ' requests drawn as ' + _sdNum(drawn)
             + ' cells, so each cell stands for about ' + Math.round(per) + ' requests">1 cell = '
             + Math.round(per) + '</span>';
    }
    return '<div class="sig-strip' + (extraCls ? ' ' + extraCls : '') + '" role="img" aria-label="'
        + _esc(aria) + '">' + html + '</div>';
}

function _lgCellLabel(e) {
    return (e.status || '-') + ' ' + _lgStatusName(e.status) + ' ' + e.method + ' ' + e.path
        + (e.ip ? ' from ' + e.ip : '')
        + (e.origin != null && e.origin !== e.status ? ' (traefik answered, backend said ' + e.origin + ')' : '');
}

function _lgRank(rows, keyFn, kindFn) {
    const m = new Map();
    rows.forEach(e => {
        const k = keyFn(e);
        if (!k || k === '-') return;
        let o = m.get(k);
        if (!o) { o = { key: k, n: 0, e4: 0, e5: 0, codes: new Map(), kinds: new Map(), rows: [] }; m.set(k, o); }
        o.n++;
        o.rows.push(e);
        if (e.status >= 500 && e.status < 600) o.e5++;
        else if (e.status >= 400 && e.status < 500) o.e4++;
        if (e.status >= 400) o.codes.set(e.status, (o.codes.get(e.status) || 0) + 1);
        if (kindFn) { const kk = kindFn(e); if (kk) o.kinds.set(kk, (o.kinds.get(kk) || 0) + 1); }
    });
    const list = [...m.values()];
    list.forEach(o => {
        o.err = o.e4 + o.e5;
        o.share = o.n ? o.err / o.n : 0;
        const worst = [...o.codes.entries()].sort((a, b) => b[1] - a[1] || b[0] - a[0])[0];
        o.worst = worst ? worst[0] : 0;
        o.worstN = worst ? worst[1] : 0;
        const kk = [...o.kinds.entries()].sort((a, b) => b[1] - a[1])[0];
        o.kind = kk ? kk[0] : '';
    });
    list.sort((a, b) => (b.e5 - a.e5) || (b.e4 - a.e4) || (b.share - a.share)
        || (b.n - a.n) || String(a.key).localeCompare(String(b.key)));
    return list;
}

function _lgRankBody(list, opts) {
    const total = opts.total || 1;
    const shown = list.slice(0, LG_ROW_CAP);
    const rows = shown.map(o => {
        const pct = Math.round((o.n / total) * 100);
        const bad = o.err ? _lgFlag({
            tag: 'span', extra: 'lg-bad',
            cls: o.e5 ? 'd-bad' : 'd-warn',
            ic: o.e5 ? 'ph-fill ph-x-circle' : 'ph-fill ph-warning',
            n: o.err, label: '', words: false,
            go: _lgSpec(Object.assign({}, opts.facet(o), { status: _lgErrStatus(o.e4, o.e5) })),
            tip: o.err + ' of ' + o.n + ' requests failed'
                + (o.worst ? ', most often ' + o.worst + ' ' + _lgStatusName(o.worst) : '')
                + '. Click to filter to just those.'
        }) : '';
        return _lgRow({
            go: _lgSpec(opts.facet(o)),
            health: o.e5 ? 'down' : (o.err && o.err === o.n ? 'warn' : ''),
            glyph: opts.glyph ? opts.glyph(o) : '',
            name: opts.label ? opts.label(o) : o.key,
            kind: o.kind,
            bad: bad,
            n: o.n,
            pct: pct,
            tip: (opts.tipName ? opts.tipName(o) : o.key) + ': ' + o.n + ' of ' + total
                + ' requests in this window (' + pct + '%)'
                + (o.err ? ', ' + o.err + ' failed' : '')
                + '. Click to filter the log list.'
        });
    });
    let tail = '';
    if (list.length > shown.length) {
        const rest = list.slice(shown.length).reduce((a, o) => a + o.n, 0);
        tail = '<div class="lg-tail">+' + _sdNum(rest) + ' requests across ' + (list.length - shown.length)
            + ' more ' + (opts.noun || 'entries') + '</div>';
    }
    if (list.length > 4) {
        const rest4 = list.slice(4).reduce((a, o) => a + o.n, 0);
        tail += '<div class="lg-tail lg-tail-c">+' + _sdNum(rest4) + ' requests across '
            + (list.length - 4) + ' more ' + (opts.noun || 'entries') + '</div>';
    }
    return { body: '<div class="lg-rows">' + rows.join('') + '</div>', tail: tail };
}

function _lgSubOffender(list, label) {
    if (!list.length) return 'nothing recorded';
    const o = list[0];
    let s = '<b>' + _esc(label ? label(o) : o.key) + '</b> ' + _sdNum(o.n) + ' requests';
    if (o.err) s += ', ' + _sdNum(o.worstN) + ' x ' + o.worst;
    const more = list.filter(x => x.err).length - (o.err ? 1 : 0);
    if (more > 0) s += ', +' + more + ' more failing';
    return s;
}

function _lgFailFlag(bad, opts) {
    const anyE5 = bad.some(o => o.e5);
    const worst = bad[0];
    const name = opts.name ? opts.name(worst) : worst.key;
    return _lgFlag({
        cls: anyE5 ? 'd-bad' : 'd-warn',
        ic: anyE5 ? 'ph-fill ph-x-circle' : 'ph-fill ph-warning',
        n: bad.length, label: opts.label,
        go: _lgSpec(Object.assign({}, opts.facet(worst), { status: _lgErrStatus(worst.e4, worst.e5) })),
        tip: bad.length + ' ' + (bad.length === 1 ? opts.one : opts.many) + ' ' + opts.verb
            + '. Click to filter to the ' + _sdNum(worst.err) + ' failing '
            + (worst.err === 1 ? 'request' : 'requests') + ' on ' + name + '.'
    });
}

function renderLogStats(visible, meta) {
    const el = document.getElementById('logStats');
    if (!el) return;
    el.style.display = '';

    const compact = (typeof tmPref === 'function' && tmPref('compactStatCards')) ? ' sig-compact' : '';
    const rows = visible.map(o => o.e).filter(Boolean);
    const total = rows.length;

    const scoped = meta.q || _logCountryFilter || _lgActiveFacets().length;
    const winRows = (meta.all && meta.all.length) ? meta.all : rows;
    const spanMs = _lgSpanOf(winRows);
    const rpm = (spanMs && spanMs > 1000) ? Math.round(winRows.length / (spanMs / 60000)) : null;
    const selSpan = scoped ? _lgSpanOf(rows) : null;

    const nextLines = LG_LINE_STEPS.find(n => n > _currentLogLines) || null;
    const scopeTip = 'These numbers summarise the last ' + _sdNum(meta.fetched)
        + ' lines of the access log, not all traffic. The oldest line here is the edge of the fetched window, '
        + 'not the start of activity. Traefik does not report the file total, so the share of overall traffic is unknown. '
        + _sdNum(meta.parsed) + ' of ' + _sdNum(meta.fetched) + ' lines parsed.'
        + (nextLines ? ' Click to widen the window to ' + nextLines + ' lines.' : '');

    const facts = [];
    facts.push('<span class="sig-key-item lg-static" title="' + _esc(scopeTip) + '"><i class="ph-bold ph-rows"></i>last<b>'
        + _sdNum(meta.fetched) + '</b>lines</span>');
    if (spanMs != null && spanMs > 0) {
        facts.push('<span class="sig-key-item lg-static" title="Oldest line to newest line in the fetched window. Filters do not change it, and earlier requests are not in the fetched tail."><i class="ph-bold ph-clock-countdown"></i>span<b>'
            + _lgSpanTxt(spanMs) + '</b></span>');
    }
    if (rpm != null) {
        facts.push('<span class="sig-key-item lg-static" title="Average request rate across the whole fetched window, not across the current selection."><i class="ph-bold ph-broadcast"></i><b>'
            + _sdNum(rpm) + '</b>req/min</span>');
    }
    facts.push('<span class="sig-key-item lg-static" title="Lines that no access log format matched. They are listed below but excluded from every number here."><i class="ph-bold ph-scroll"></i><b>'
        + _sdNum(meta.unparsed) + '</b>unparsed</span>');

    const dead = meta.facetDead || {};
    const chips = [];
    _lgActiveFacets().forEach(k => {
        const v = _logFacet[k];
        chips.push('<button type="button" class="sig-key-item ' + (dead[k] ? 'sig-key-empty' : 'sig-key-on')
            + '" data-lg="' + _esc(_lgSpec({ [k]: v }))
            + '" title="' + _esc(dead[k]
                ? 'Still filtering on ' + k + ' ' + v + ', but nothing in the current search matches it. Widen the search to bring it back, or click to clear this filter.'
                : 'Showing only ' + k + ' ' + v + '. Click to clear this filter.') + '">'
            + '<i class="ph-bold ph-funnel"></i>' + _esc(k) + '<b>' + _esc(_sdShort(v)) + '</b></button>');
    });
    if (selSpan != null && selSpan > 0) {
        chips.push('<span class="sig-key-item lg-static" title="Oldest to newest line among the requests you have selected. The window span above is unaffected."><i class="ph-bold ph-clock-countdown"></i>selection spans<b>'
            + _lgSpanTxt(selSpan) + '</b></span>');
    }
    if (_lgActiveFacets().length) {
        chips.push('<button type="button" class="sig-key-item" data-lg="clear=" title="Clear every card filter"><i class="ph-bold ph-x"></i>clear</button>');
    }

    const scopeTxt = scoped ? _sdNum(total) + ' of the last ' + _sdNum(meta.fetched) + ' lines' : 'sample, not all traffic';
    const scopeEl = nextLines
        ? '<button type="button" class="sig-key-scope" data-lg="lines=' + nextLines + '" title="' + _esc(scopeTip) + '">'
            + '<i class="ph-bold ph-funnel"></i>' + _esc(scopeTxt) + '</button>'
        : '<span class="sig-key-scope lg-static" title="' + _esc(scopeTip) + '">'
            + '<i class="ph-bold ph-funnel"></i>' + _esc(scopeTxt) + '</span>';
    const keyHtml = '<div class="sig-key" id="logKey"><span class="sig-key-lab">window</span>' + facts.join('')
        + (chips.length ? '<span class="sig-key-lab">filters</span>' + chips.join('') : '')
        + scopeEl + '</div>';

    if (!total) {
        el.innerHTML = '<div class="sig-wrap' + compact + '" id="logStatsPanel">'
            + _lgEmptyVerdict(meta) + keyHtml + '</div>';
        _lgTickAge();
        return;
    }

    const bucket = {};
    ['1xx', '2xx', '3xx', '4xx', '5xx', 'other'].forEach(k => { bucket[k] = 0; });
    const codes = new Map();
    rows.forEach(e => {
        bucket[_lgStatusClass(e.status)]++;
        if (e.status >= 400) codes.set(e.status, (codes.get(e.status) || 0) + 1);
    });
    const s4 = bucket['4xx'], s5 = bucket['5xx'];
    const codeRank = [...codes.entries()].sort((a, b) => b[1] - a[1] || a[0] - b[0]);

    const held = rows.filter(e => e.durMs != null && _lgHeldOpen(e));
    const heldMax = held.length ? held.reduce((a, b) => (b.durMs > a.durMs ? b : a), held[0]) : null;
    const timed = rows.filter(e => e.durMs != null && !_lgHeldOpen(e));
    const durs = timed.map(e => e.durMs).sort((a, b) => a - b);
    const pick = q => durs.length ? durs[Math.min(durs.length - 1, Math.floor(durs.length * q))] : null;
    const p50 = pick(0.5), p95 = pick(0.95);
    const maxDur = durs.length ? durs[durs.length - 1] : null;
    const avgDur = durs.length ? durs.reduce((a, b) => a + b, 0) / durs.length : null;
    const maxRow = timed.length ? timed.reduce((a, b) => (b.durMs > a.durMs ? b : a), timed[0]) : null;
    const fast = durs.filter(d => d < 100).length;
    const med  = durs.filter(d => d >= 100 && d < 500).length;
    const slow = durs.filter(d => d >= 500).length;
    const vslow = durs.filter(d => d >= 2000).length;
    const untimed = total - timed.length - held.length;
    const retries = rows.reduce((a, e) => a + (e.retries || 0), 0);

    const isJson = meta.format === 'json';
    const health = s5 ? 'down' : ((s4 || slow) ? 'warn' : 'up');
    const cards = [];

    cards.push(_lgStatusCard(rows, bucket, codeRank, total));
    cards.push(_lgLatencyCard(rows, timed, { p50, p95, maxDur, avgDur, maxRow, fast, med, slow, vslow,
        retries, total, untimed, held: held.length, heldMax }));
    cards.push(_lgMethodsCard(rows, total));
    cards.push(_lgDomainsCard(rows, total, isJson));
    cards.push(_lgPathsCard(rows, total));
    cards.push(_lgClientsCard(rows, total));
    cards.push(_lgServicesCard(rows, total, isJson));

    const verdict = _lgVerdict({ health, total, s4, s5, slow, codeRank, rows, spanMs, meta, maxDur, retries });
    const failPanel = _lgFailPanel(rows, total);
    const runtime = _lgRuntime(meta, rows);

    el.innerHTML = '<div class="sig-wrap' + compact + '" id="logStatsPanel">'
        + verdict + keyHtml
        + '<div class="sig-grid" id="logGrid">' + cards.join('') + '</div>'
        + failPanel + runtime + '</div>';
    _lgTickAge();
}

function _lgEmptyVerdict(meta) {
    const filtered = meta.q || _logCountryFilter || _lgActiveFacets().length;
    let ic = 'ph-fill ph-moon-stars', txt = 'No traffic yet', prose, actions = '';
    if (filtered) {
        ic = 'ph-fill ph-funnel';
        txt = 'Nothing matches';
        const bits = [];
        _lgActiveFacets().forEach(k => bits.push(k + ' ' + _logFacet[k]));
        if (_logCountryFilter) bits.push('country ' + _logCountryFilter);
        if (meta.q) bits.push('search "' + meta.q + '"');
        prose = '0 of the last ' + _sdNum(meta.fetched) + ' lines are ' + bits.join(' and ');
        actions = _lgFlag({ cls: 'd-blue', ic: 'ph-bold ph-x', n: '', label: 'clear filters', go: 'clear=all', tip: 'Clear every filter and the search box' })
            ;
        const wider = LG_LINE_STEPS.find(n => n > _currentLogLines);
        if (wider) {
            actions += _lgFlag({ cls: 'd-blue', ic: 'ph-bold ph-rows', n: '', label: 'load ' + wider + ' lines', go: 'lines=' + wider, tip: 'Refetch with a wider window' })
                ;
        }
    } else if (meta.unparsed) {
        prose = 'none of the ' + _sdNum(meta.fetched) + ' fetched lines could be parsed as a Traefik access log';
    } else {
        prose = 'the access log is empty, Traefik has not served a request since it was last rotated';
    }
    return '<div class="sig-verdict" id="logVerdict" data-health="up"><i class="' + ic + ' sig-verdict-ic"></i>'
        + '<span class="sig-verdict-txt">' + _esc(txt) + '</span>'
        + '<span class="sig-verdict-items"><span class="sig-mono">' + _esc(prose) + '</span>' + actions + '</span>'
        + '<span class="sig-verdict-meta">last <b>' + _sdNum(meta.fetched) + '</b> lines'
        + SD_SEP + '<b id="logAge">' + _sdAgo(_lgStamp) + '</b></span></div>';
}

function _lgVerdict(v) {
    const items = [];
    let ic = 'ph-fill ph-check-circle', txt = 'All clean';
    if (v.health === 'down') { ic = 'ph-fill ph-warning-octagon'; txt = _sdNum(v.s5) + ' server ' + (v.s5 === 1 ? 'error' : 'errors'); }
    else if (v.health === 'warn') {
        ic = 'ph-fill ph-warning-circle';
        txt = v.s4 ? _sdNum(v.s4) + ' client ' + (v.s4 === 1 ? 'error' : 'errors')
                   : _sdNum(v.slow) + ' slow ' + (v.slow === 1 ? 'request' : 'requests');
    }
    v.codeRank.slice(0, 3).forEach(([code, n]) => {
        const bad = code >= 500;
        items.push(_lgFlag({
            cls: bad ? 'd-bad' : 'd-warn',
            ic: bad ? 'ph-fill ph-x-circle' : 'ph-fill ph-warning',
            n: n, label: code + ' ' + (_lgStatusName(code) || 'response').toLowerCase(),
            go: _lgSpec({ status: String(code) }),
            tip: n + ' requests returned ' + code + ' ' + _lgStatusName(code) + '. Click to filter the log list.'
        }));
    });
    if (v.slow) {
        items.push(_lgFlag({
            cls: 'd-warn', ic: 'ph-fill ph-hourglass-high', n: v.slow, label: 'over 500ms',
            go: _lgSpec({ dur: 'slow' }), tip: v.slow + ' requests took longer than 500ms. Click to filter the log list.'
        }));
    }
    if (v.retries) {
        items.push(_lgFlag({
            cls: 'd-warn', ic: 'ph-fill ph-arrow-u-up-left', n: v.retries, label: 'retries',
            go: '', tip: v.retries + ' upstream retry attempts. The client never saw these, but a backend was flapping.'
        }));
    }
    const shown = items.slice(0, 4);
    if (items.length > shown.length) shown.push('<span class="sig-mono">+' + (items.length - shown.length) + ' more</span>');
    const calm = [];
    if (!v.s5) calm.push('no server errors');
    if (!v.s4 && v.s5) calm.push('no client errors');
    if (!v.slow) calm.push(v.maxDur != null ? 'nothing slower than ' + _lgMs(v.maxDur) : 'no timing recorded');
    if (calm.length) shown.push('<span class="sig-mono">' + _esc(calm.join(', ')) + '</span>');

    const meta = (v.spanMs != null && v.spanMs > 0 ? '<b>' + _lgSpanTxt(v.spanMs) + '</b> window' + SD_SEP : '')
        + '<b id="logAge">' + _sdAgo(_lgStamp) + '</b>';
    return '<div class="sig-verdict" id="logVerdict" data-health="' + v.health + '">'
        + '<i class="' + ic + ' sig-verdict-ic"></i>'
        + '<span class="sig-verdict-txt">' + _esc(txt) + '</span>'
        + '<span class="sig-verdict-items">' + shown.join('') + '</span>'
        + '<span class="sig-verdict-meta">' + meta + '</span></div>';
}

function _lgStatusCard(rows, bucket, codeRank, total) {
    const s4 = bucket['4xx'], s5 = bucket['5xx'];
    const flags = [];
    if (s5) flags.push(_lgFlag({ cls: 'd-bad', ic: 'ph-fill ph-x-circle', n: s5, label: '5xx',
        go: _lgSpec({ status: '5xx' }), tip: s5 + ' server errors. Click to filter the log list.' }));
    if (s4) flags.push(_lgFlag({ cls: 'd-warn', ic: 'ph-fill ph-warning', n: s4, label: '4xx',
        go: _lgSpec({ status: '4xx' }), tip: s4 + ' client errors. Click to filter the log list.' }));
    if (!flags.length) flags.push(_lgOk('all 2xx'));

    const groups = [
        { cls: 'sig-cell-err',  items: rows.filter(e => _lgStatusClass(e.status) === '5xx').map(_lgCellLabel) },
        { cls: 'sig-cell-warn', items: rows.filter(e => _lgStatusClass(e.status) === '4xx').map(_lgCellLabel) },
        { cls: 'sig-cell-idle', items: rows.filter(e => ['3xx', '1xx', 'other'].indexOf(_lgStatusClass(e.status)) >= 0).map(_lgCellLabel) },
        { cls: '',              items: rows.filter(e => _lgStatusClass(e.status) === '2xx').map(_lgCellLabel) },
    ];
    const aria = total + ' requests: ' + s5 + ' server errors, ' + s4 + ' client errors, '
        + bucket['3xx'] + ' redirects, ' + bucket['2xx'] + ' ok';

    const provs = [
        { key: '2xx', ic: 'ph-bold ph-check-circle', n: bucket['2xx'] },
        { key: '3xx', ic: 'ph-bold ph-arrow-bend-up-right', n: bucket['3xx'] },
        { key: '4xx', ic: 'ph-bold ph-warning', n: s4, cls: s4 ? 'sig-prov-warn' : '' },
        { key: '5xx', ic: 'ph-bold ph-x-circle', n: s5, cls: s5 ? 'sig-prov-bad' : '' },
    ];
    if (bucket['1xx']) provs.push({ key: '1xx', ic: 'ph-bold ph-arrows-left-right', n: bucket['1xx'] });
    if (bucket['other']) provs.push({ key: 'other', ic: 'ph-bold ph-question', n: bucket['other'] });

    let sub;
    if (codeRank.length) {
        sub = _lgSub('<b>' + codeRank[0][0] + '</b> ' + _lgStatusName(codeRank[0][0]).toLowerCase() + ' x' + _sdNum(codeRank[0][1]),
            codeRank.length > 1 ? '+' + (codeRank.length - 1) + ' codes' : '');
    } else {
        sub = _lgSub('<b>' + _sdNum(bucket['2xx']) + '</b> ok' + SD_SEP + '<b>' + _sdNum(bucket['3xx']) + '</b> redirects', 'clean');
    }

    return _lgCard({
        key: 'status', accent: 'var(--blue)', ic: 'ph-fill ph-pulse', title: 'Status Codes',
        health: s5 ? 'down' : (s4 ? 'warn' : ''),
        go: (s5 || s4) ? _lgSpec({ status: _lgErrStatus(s4, s5) }) : '', goLabel: 'Errors',
        goTip: 'Filter the log list to the ' + _sdNum(s4 + s5) + ' failing requests',
        total: _sdNum(total), flags: flags.join(''), sub: sub,
        body: _lgStrip(groups, aria),
        foot: provs.map(p => _lgProv({
            ic: p.ic, label: p.key, n: p.n, cls: p.cls, go: _lgSpec({ status: p.key }),
            tip: p.n ? 'Filter the log list to the ' + p.n + ' ' + p.key + ' responses'
                     : 'No ' + p.key + ' responses in this window'
        })).join('')
    });
}

function _lgLatencyCard(rows, timed, d) {
    const heldWord = d.held === 1 ? 'upgrade' : 'upgrades';
    const heldTip = d.held
        ? _sdNum(d.held) + ' protocol ' + heldWord + ', a websocket or a CONNECT tunnel, the longest held open for '
            + _lgSpanTxt(d.heldMax.durMs) + '. Traefik logs the whole connection lifetime as the duration, '
            + 'so these are left out of the average and the bands here. Click to list them.'
        : '';
    if (!timed.length) {
        return _lgCard({
            key: 'latency', cls: 'lg-blind', accent: 'var(--teal)', ic: 'ph-fill ph-timer', title: 'Response Time',
            total: '-', flags: _lgOk(d.held ? 'upgrades only' : 'not logged', 'ph-bold ph-info'),
            sub: _lgSub(d.held ? 'nothing here is a completed response' : 'this access log format carries no duration'),
            body: '<p class="lg-note">' + (d.held
                ? 'Every duration in this window belongs to a connection Traefik held open rather than to a response it completed, so there is nothing to average. ' + _esc(heldTip)
                : 'Traefik\'s generic <code>common</code> writer stops after the user agent, so no request duration reaches the log. Set <code>accessLog.format: json</code> in the static config for timings.') + '</p>',
            go: d.held ? _lgSpec({ dur: 'held' }) : 'cfg=accesslog',
            goLabel: d.held ? 'Upgrades' : 'Static Config',
            goTip: d.held ? 'Filter the log list to the held-open connections' : 'Open the Static Config tab',
            foot: d.held
                ? _lgProv({ ic: 'ph-bold ph-plugs-connected', label: heldWord, n: d.held, go: _lgSpec({ dur: 'held' }), tip: heldTip })
                : _lgProv({ ic: 'ph-bold ph-sliders-horizontal', label: 'open static config', n: '', go: 'cfg=accesslog', tip: 'Open the Static Config tab to change accessLog.format' })
        });
    }
    const hero = _lgHeroMs(d.avgDur);
    const flags = [];
    if (d.vslow) flags.push(_lgFlag({ cls: 'd-bad', ic: 'ph-fill ph-hourglass-high', n: d.vslow, label: 'over 2s',
        go: _lgSpec({ dur: 'slow' }), tip: d.vslow + ' requests took longer than 2 seconds' }));
    if (d.slow && !d.vslow) flags.push(_lgFlag({ cls: 'd-warn', ic: 'ph-fill ph-hourglass-high', n: d.slow, label: 'over 500ms',
        go: _lgSpec({ dur: 'slow' }), tip: d.slow + ' requests took longer than 500ms' }));
    if (d.retries) flags.push(_lgFlag({ cls: 'd-warn', ic: 'ph-fill ph-arrow-u-up-left', n: d.retries, label: 'retries',
        go: '', tip: d.retries + ' upstream retry attempts across this window' }));
    if (!flags.length) flags.push(_lgOk('all under 100ms'));

    const maxWhere = d.maxRow ? ' ' + d.maxRow.path : '';
    const tailBits = [];
    if (d.held) tailBits.push(_sdNum(d.held) + ' ' + heldWord + ', longest ' + _lgSpanTxt(d.heldMax.durMs));
    if (d.untimed > 0) tailBits.push(_sdNum(d.untimed) + ' untimed');
    const sub = _lgSub('p50 <b>' + _lgMs(d.p50) + '</b>' + SD_SEP + 'p95 <b>' + _lgMs(d.p95) + '</b>'
        + SD_SEP + 'max <b>' + _lgMs(d.maxDur) + '</b>' + _esc(maxWhere),
        tailBits.join(SD_SEP));

    const lab = e => _lgMs(e.durMs) + ' ' + e.method + ' ' + e.path + (e.ip ? ' from ' + e.ip : '');
    const groups = [
        { cls: 'sig-cell-err',  items: timed.filter(e => e.durMs >= 2000).sort((a, b) => b.durMs - a.durMs).map(lab) },
        { cls: 'sig-cell-warn', items: timed.filter(e => e.durMs >= 100 && e.durMs < 2000).sort((a, b) => b.durMs - a.durMs).map(lab) },
        { cls: '',              items: timed.filter(e => e.durMs < 100).sort((a, b) => b.durMs - a.durMs).map(lab) },
    ];
    const aria = timed.length + ' timed requests, median ' + _lgMs(d.p50) + ', slowest ' + _lgMs(d.maxDur);

    return _lgCard({
        key: 'latency', accent: 'var(--teal)', ic: 'ph-fill ph-timer', title: 'Response Time',
        health: d.vslow ? 'down' : (d.slow ? 'warn' : ''),
        go: d.maxRow ? _lgSpec({ path: d.maxRow.path }) : '', goLabel: 'Slowest',
        goTip: d.maxRow ? 'Filter the log list to ' + d.maxRow.path : '',
        total: hero.n + (hero.u ? '<span class="lg-unit">' + hero.u + '</span>' : ''),
        flags: flags.join(''), sub: sub,
        body: _lgStrip(groups, aria),
        foot: [
            _lgProv({ ic: 'ph-bold ph-lightning', label: 'under 100ms', n: d.fast, go: _lgSpec({ dur: 'fast' }),
                tip: d.fast ? 'Filter the log list to the ' + d.fast + ' requests faster than 100ms' : 'No request was faster than 100ms' }),
            _lgProv({ ic: 'ph-bold ph-hourglass-medium', label: '100-500ms', n: d.med, cls: d.med ? 'sig-prov-warn' : '', go: _lgSpec({ dur: 'med' }),
                tip: d.med ? 'Filter the log list to the ' + d.med + ' requests between 100ms and 500ms' : 'No request took between 100ms and 500ms' }),
            _lgProv({ ic: 'ph-bold ph-hourglass-high', label: 'over 500ms', n: d.slow, cls: d.slow ? 'sig-prov-bad' : '', go: _lgSpec({ dur: 'slow' }),
                tip: d.slow ? 'Filter the log list to the ' + d.slow + ' requests slower than 500ms' : 'No request took longer than 500ms' }),
            d.held ? _lgProv({ ic: 'ph-bold ph-plugs-connected', label: heldWord, n: d.held, go: _lgSpec({ dur: 'held' }), tip: heldTip }) : ''
        ].join('')
    });
}

function _lgMethodsCard(rows, total) {
    const list = _lgRank(rows, e => e.method);
    const byVolume = list.slice().sort((a, b) => b.n - a.n);
    const writes = rows.filter(e => ['POST', 'PUT', 'PATCH', 'DELETE'].indexOf(e.method) >= 0);
    const risky = rows.some(e => e.method === 'DELETE' || e.method === 'PUT');
    const flags = writes.length
        ? [_lgFlag({ cls: risky ? 'd-warn' : 'd-off', ic: 'ph-bold ph-pencil-simple', n: writes.length, label: 'writes',
            go: _lgSpec({ method: writes[0].method }),
            tip: writes.length + ' write requests (POST, PUT, PATCH or DELETE). Click to filter to ' + writes[0].method + '.' })]
        : [_lgOk('reads only')];
    const top = byVolume[0];
    const sub = _lgSub((top ? '<b>' + _esc(top.key) + '</b> ' + Math.round((top.n / total) * 100) + '%' : 'no method recorded')
        + ', ' + (risky ? 'PUT or DELETE present' : 'no PUT or DELETE'));
    const built = _lgRankBody(list, {
        total: total, noun: 'methods',
        facet: o => ({ method: o.key }),
    });
    return _lgCard({
        key: 'methods', accent: 'var(--orange)', ic: 'ph-fill ph-swap', title: 'Methods',
        go: top ? _lgSpec({ method: top.key }) : '', goLabel: 'Top',
        goTip: top ? 'Filter the log list to ' + top.key : '',
        total: _sdNum(list.length), flags: flags.join(''), sub: sub,
        body: built.body, tail: built.tail
    });
}

function _lgDomainsCard(rows, total, isJson) {
    const list = isJson ? _lgRank(rows, e => e.domain, e => e.ep) : [];
    if (!isJson || !list.length) {
        const sel = isJson && _lgSelected();
        const note = sel
            ? 'The requests selected right now carry no <code>RequestHost</code>. Clear the filters to rank the whole window.'
            : (isJson
                ? 'These lines carry no <code>RequestHost</code>. Add it with <code>accessLog.fields.names</code> in the static config.'
                : 'Traefik\'s <code>common</code> format cannot record the request Host. Set <code>accessLog.format: json</code> in the static config to rank domains.');
        return _lgCard({
            key: 'domains', cls: 'lg-blind', accent: 'var(--purple)', ic: 'ph-fill ph-globe-simple', title: 'Domains',
            go: sel ? 'clear=all' : 'cfg=accesslog', goLabel: sel ? 'Clear' : 'Static Config',
            goTip: sel ? 'Clear every filter and the search box' : 'Open the Static Config tab',
            total: '-', flags: _lgOk(sel ? 'none in selection' : 'not logged', 'ph-bold ph-info'),
            sub: _lgSub(sel ? 'no Host named in this selection' : (isJson ? 'no Host field in these lines' : 'the CLF access log has no Host field')),
            body: '<p class="lg-note">' + note + '</p>',
            foot: sel ? '' : _lgProv({ ic: 'ph-bold ph-sliders-horizontal', label: 'open static config', n: '', go: 'cfg=accesslog',
                tip: 'Open the Static Config tab to change the accessLog block' })
        });
    }
    const bad = list.filter(o => o.err);
    const failing = bad.length;
    const flags = failing
        ? [_lgFailFlag(bad, { label: 'with errors', one: 'domain', many: 'domains',
            verb: 'served at least one failing request', facet: o => ({ domain: o.key }) })]
        : [_lgOk('all healthy')];
    const built = _lgRankBody(list, { total: total, noun: 'domains', facet: o => ({ domain: o.key }) });
    const plain = rows.filter(e => e.scheme && e.scheme !== 'https').length;
    const secure = rows.filter(e => e.scheme === 'https').length;
    const foot = (secure || plain) ? [
        _lgProv({ ic: 'ph-bold ph-lock-simple', label: 'https', n: secure, go: '', tip: secure + ' requests arrived over TLS' }),
        _lgProv({ ic: 'ph-bold ph-lock-simple-open', label: 'plaintext', n: plain, cls: plain ? 'sig-prov-warn' : '', go: '', tip: plain + ' requests arrived without TLS' })
    ].join('') : '';
    return _lgCard({
        key: 'domains', accent: 'var(--purple)', ic: 'ph-fill ph-globe-simple', title: 'Domains',
        go: _lgSpec({ domain: list[0].key }), goLabel: failing ? 'Worst' : 'Top',
        goTip: 'Filter the log list to ' + list[0].key,
        total: _sdNum(list.length), flags: flags.join(''),
        sub: _lgSub(_lgSubOffender(list)),
        body: built.body, tail: built.tail, foot: foot
    });
}

function _lgPathsCard(rows, total) {
    const raw = _lgRank(rows, e => e.path);
    const patCount = new Map();
    raw.forEach(o => {
        const p = _lgPattern(o.key);
        patCount.set(p, (patCount.get(p) || 0) + 1);
    });
    const folded = new Set([...patCount.entries()].filter(([, n]) => n >= 2).map(([p]) => p));
    const list = _lgRank(rows, e => {
        const p = _lgPattern(e.path);
        return folded.has(p) ? '~' + p : e.path;
    });
    list.forEach(o => {
        o.folded = o.key.charAt(0) === '~';
        o.label = o.folded ? o.key.slice(1) : o.key;
        o.merged = o.folded ? (patCount.get(o.label) || 0) : 0;
    });
    const bad = list.filter(o => o.err);
    const failing = bad.length;
    const once = raw.filter(o => o.n === 1).length;
    const flags = failing
        ? [_lgFailFlag(bad, { label: 'failing', one: 'path', many: 'paths',
            verb: 'returned at least one error', facet: o => ({ path: o.key }), name: o => o.label })]
        : [_lgOk('all healthy')];
    const built = _lgRankBody(list, {
        total: total, noun: 'paths',
        facet: o => ({ path: o.key }),
        label: o => o.label,
        tipName: o => o.folded ? o.label + ' (' + o.merged + ' paths folded into this pattern)' : o.key,
        glyph: o => o.folded ? '<i class="lg-g ph-bold ph-asterisk" title="pattern, ' + o.merged + ' paths folded"></i>' : ''
    });
    return _lgCard({
        key: 'paths', cls: 'lg-wide', accent: 'var(--teal)', ic: 'ph-fill ph-path', title: 'Paths',
        go: list.length ? _lgSpec({ path: list[0].key }) : '', goLabel: failing ? 'Worst' : 'Top',
        goTip: list.length ? 'Filter the log list to ' + (list[0].label || list[0].key) : '',
        total: _sdNum(list.length), flags: flags.join(''),
        sub: _lgSub(_lgSubOffender(list, o => o.label)),
        body: built.body, tail: built.tail,
        foot: [
            _lgProv({ ic: 'ph-bold ph-asterisk', label: 'patterns', n: folded.size, go: '',
                tip: folded.size + ' path patterns collapse a numeric, date or hex segment. Only patterns that merge two or more real paths are folded.' }),
            _lgProv({ ic: 'ph-bold ph-dot-outline', label: 'seen once', n: once, go: '',
                tip: once + ' paths were requested exactly once in this window, so the ranked rows are not the whole distribution' })
        ].join('')
    });
}

function _lgClientsCard(rows, total) {
    const list = _lgRank(rows, e => e.ip, e => classifyIp(e.ip));
    const bad = list.filter(o => o.err && o.err === o.n);
    const flags = bad.length
        ? [_lgFailFlag(bad, { label: 'error only', one: 'client', many: 'clients',
            verb: 'got nothing but errors in this window', facet: o => ({ ip: o.key }) })]
        : [_lgOk('all served')];
    const built = _lgRankBody(list, {
        total: total, noun: 'clients',
        facet: o => ({ ip: o.key }),
        tipName: o => o.key + ', ' + (LG_IP_GLYPH[o.kind] || LG_IP_GLYPH.unknown)[1] + ' address',
        glyph: o => {
            const g = LG_IP_GLYPH[o.kind] || LG_IP_GLYPH.unknown;
            return '<i class="lg-g ' + g[0] + '" title="' + _esc(g[1] + ' address') + '"></i>';
        }
    });
    const byClass = new Map();
    rows.forEach(e => { const c = classifyIp(e.ip); byClass.set(c, (byClass.get(c) || 0) + 1); });
    const foot = [...byClass.entries()].sort((a, b) => b[1] - a[1]).slice(0, 4).map(([c, n]) => {
        const g = LG_IP_GLYPH[c] || LG_IP_GLYPH.unknown;
        return _lgProv({ ic: g[0], label: g[1], n: n, go: _lgSpec({ ipclass: c }),
            tip: n + ' requests from ' + g[1] + ' addresses. Click to filter the log list.' });
    }).join('');
    return _lgCard({
        key: 'clients', accent: 'var(--blue)', ic: 'ph-fill ph-users-three', title: 'Clients',
        go: list.length ? _lgSpec({ ip: list[0].key }) : '', goLabel: list.some(o => o.err) ? 'Worst' : 'Top',
        goTip: list.length ? 'Filter the log list to ' + list[0].key : '',
        total: _sdNum(list.length), flags: flags.join(''),
        sub: _lgSub(_lgSubOffender(list)),
        body: built.body, tail: built.tail, foot: foot
    });
}

function _lgServicesCard(rows, total, isJson) {
    const useRouter = !isJson;
    const what = useRouter ? 'router' : 'service';
    const list = _lgRank(rows, e => (useRouter ? e.router : e.service), e => _lgProvider(useRouter ? e.router : e.service));
    if (!list.length) {
        const sel = _lgSelected();
        const note = sel
            ? 'The requests selected right now carry no ' + what + ' name. Clear the filters to rank the whole window.'
            : (isJson
                ? 'These lines carry no <code>ServiceName</code>. Traefik omits it when it answers a request itself, and <code>accessLog.fields.names</code> in the static config controls whether it is written at all.'
                : 'The generic <code>common</code> writer stops after the user agent, so neither the router nor the service reaches the log. Set <code>accessLog.format: json</code> in the static config.');
        return _lgCard({
            key: 'services', cls: 'lg-blind', accent: 'var(--green)', ic: 'ph-fill ph-hard-drives',
            title: useRouter ? 'Routers' : 'Services',
            go: sel ? 'clear=all' : 'cfg=accesslog', goLabel: sel ? 'Clear' : 'Static Config',
            goTip: sel ? 'Clear every filter and the search box' : 'Open the Static Config tab',
            total: '-', flags: _lgOk(sel ? 'none in selection' : 'not logged', 'ph-bold ph-info'),
            sub: _lgSub(sel ? 'no ' + what + ' named in this selection'
                : (isJson ? 'no ServiceName on these lines' : 'this access log format names no ' + what)),
            body: '<p class="lg-note">' + note + '</p>',
            foot: sel ? '' : _lgProv({ ic: 'ph-bold ph-sliders-horizontal', label: 'open static config', n: '', go: 'cfg=accesslog',
                tip: 'Open the Static Config tab to change the accessLog block' })
        });
    }
    const bad = list.filter(o => o.err);
    const failing = bad.length;
    const flags = failing
        ? [_lgFailFlag(bad, { label: 'failing', one: what, many: what + 's',
            verb: 'returned at least one error', name: o => _sdShort(o.key),
            facet: o => (useRouter ? { router: o.key } : { service: o.key }) })]
        : [_lgOk('all healthy')];
    const built = _lgRankBody(list, {
        total: total, noun: useRouter ? 'routers' : 'services',
        facet: o => (useRouter ? { router: o.key } : { service: o.key }),
        label: o => _sdShort(o.key)
    });
    const byProv = new Map();
    rows.forEach(e => { const p = _lgProvider(useRouter ? e.router : e.service); if (p) byProv.set(p, (byProv.get(p) || 0) + 1); });
    const foot = [...byProv.entries()].sort((a, b) => b[1] - a[1]).slice(0, 4).map(([p, n]) =>
        _lgProv({ ic: 'ph-bold ph-cube', label: p, n: n, go: _lgSpec({ provider: p }),
            tip: n + ' requests handled by the ' + p + ' provider. Click to filter the log list.' })).join('');
    return _lgCard({
        key: 'services', accent: 'var(--green)', ic: 'ph-fill ph-hard-drives',
        title: useRouter ? 'Routers' : 'Services',
        go: _lgSpec(useRouter ? { router: list[0].key } : { service: list[0].key }),
        goLabel: failing ? 'Worst' : 'Top',
        goTip: 'Filter the log list to ' + list[0].key,
        total: _sdNum(list.length), flags: flags.join(''),
        sub: _lgSub(_lgSubOffender(list, o => _sdShort(o.key)),
            useRouter ? 'router names' : ''),
        body: built.body, tail: built.tail, foot: foot
    });
}

function _lgFailPanel(rows, total) {
    const fails = rows.filter(e => e.status >= 400);
    if (!fails.length) return '';
    const pathTotal = new Map();
    rows.forEach(e => pathTotal.set(e.path, (pathTotal.get(e.path) || 0) + 1));
    const m = new Map();
    fails.forEach(e => {
        const k = e.status + ' ' + e.path;
        let o = m.get(k);
        if (!o) {
            o = { status: e.status, path: e.path, method: e.method, n: 0,
                  svcs: new Map(), ips: new Map(), doms: new Map(), durs: [] };
            m.set(k, o);
        }
        o.n++;
        const svc = e.service || e.router;
        if (svc) o.svcs.set(svc, (o.svcs.get(svc) || 0) + 1);
        if (e.ip) o.ips.set(e.ip, (o.ips.get(e.ip) || 0) + 1);
        if (e.domain) o.doms.set(e.domain, (o.doms.get(e.domain) || 0) + 1);
        if (e.durMs != null) o.durs.push(e.durMs);
    });
    const top = m => { const x = [...m.entries()].sort((a, b) => b[1] - a[1])[0]; return x ? x[0] : ''; };
    const list = [...m.values()].sort((a, b) =>
        (b.status >= 500 ? 1 : 0) - (a.status >= 500 ? 1 : 0) || b.n - a.n || a.path.localeCompare(b.path)).slice(0, 5);

    const rowsHtml = list.map(o => {
        const denom = pathTotal.get(o.path) || o.n;
        const pct = Math.round((o.n / denom) * 100);
        const svc = top(o.svcs), ip = top(o.ips), dom = top(o.doms);
        const bad = o.status >= 500;
        const cells = [
            { cls: bad ? 'sig-cell-err' : 'sig-cell-warn', items: new Array(o.n).fill(o.status + ' ' + o.method + ' ' + o.path) },
            { cls: '', items: new Array(Math.max(0, denom - o.n)).fill('ok ' + o.path) },
        ];
        o.durs.sort((a, b) => a - b);
        const p95 = o.durs.length ? o.durs[Math.min(o.durs.length - 1, Math.floor(o.durs.length * 0.95))] : null;
        const subBits = [];
        if (ip) subBits.push(ip + ' ' + classifyIp(ip));
        if (p95 != null) subBits.push('p95 ' + _lgMs(p95));
        if (dom) subBits.push(dom);
        if (svc) subBits.push(_sdShort(svc));
        return '<div class="sig-ep-row" role="button" tabindex="0"' + (bad ? ' data-health="down"' : '')
            + ' data-lg="' + _esc(_lgSpec({ status: String(o.status), path: o.path })) + '"'
            + ' title="' + _esc(o.n + ' of the ' + denom + ' requests to ' + o.path + ' returned ' + o.status + ' '
                + _lgStatusName(o.status) + ' (' + pct + '%). Click to filter the log list to just those.') + '">'
            + '<span class="sig-ep-id"><span class="d-proto sig-proto ' + (bad ? 'd-bad' : 'd-warn') + '">' + o.status + '</span>'
            + '<span class="sig-ep-name">' + _esc(o.path) + '</span></span>'
            + '<span class="sig-ep-addr">' + _esc(svc ? _sdShort(svc) : _lgStatusName(o.status)) + '</span>'
            + '<span class="sig-ep-strip">' + _lgStrip(cells, o.n + ' of ' + denom + ' requests to ' + o.path + ' failed', 'sig-strip-xs') + '</span>'
            + '<span class="sig-ep-n">' + _sdNum(o.n) + '</span>'
            + '<span class="sig-ep-flags"><span class="lg-share ' + (pct >= 50 ? (bad ? 'd-bad' : 'd-warn') : 'd-off') + '">' + pct + '%</span></span>'
            + '<span class="sig-ep-sub">' + _esc(subBits.join(' · ')) + '</span>'
            + '<span class="sig-ep-kind">' + _esc(o.status + ' on ' + (svc ? _sdShort(svc) : o.path) + ', ' + pct + '% of that path') + '</span>'
            + '</div>';
    }).join('');

    return '<section class="sig-ep"><div class="sig-ep-head">'
        + '<i class="ph-fill ph-warning-octagon sig-ep-headic ' + (fails.some(e => e.status >= 500) ? 'd-bad' : 'd-warn') + '"></i>'
        + '<span class="sc-sec-label">Where it fails</span><span class="d-n">' + _sdNum(list.length) + '</span>'
        + '<span class="sc-sec-rule"></span>'
        + '<span class="sig-ep-tot">' + _sdNum(fails.length) + ' of ' + _sdNum(total) + ' requests</span></div>'
        + '<div class="sig-ep-rows">' + rowsHtml + '</div></section>';
}

function _lgRuntime(meta, rows) {
    const fmt = meta.format;
    const facts = [];
    facts.push('<span class="sig-f' + (fmt === 'json' ? ' sig-f-on' : (fmt === 'genericclf' ? ' sig-f-off' : ''))
        + '" title="' + _esc(fmt === 'json'
            ? 'Parsed as a Traefik JSON access log, so host, scheme, router, retries and nanosecond timing are all available.'
            : (fmt === 'clf' ? 'Parsed as Traefik\'s common (CLF) access log. No Host, no TLS, no retry count, no origin timing.'
                             : 'Parsed as a generic common log. No router, no service, no duration.'))
        + '"><i class="ph-bold ' + (fmt === 'json' ? 'ph-brackets-curly' : 'ph-scroll') + '"></i>'
        + _esc(fmt === 'json' ? 'json access log' : (fmt === 'clf' ? 'clf access log' : 'generic clf access log')) + '</span>');
    facts.push('<span class="sig-f' + (meta.unparsed ? ' sig-f-off' : '')
        + '" title="Unparsed lines are still listed below but are excluded from every number on this panel."><i class="ph-bold ph-list-magnifying-glass"></i>'
        + _sdNum(meta.parsed) + ' of ' + _sdNum(meta.fetched) + ' lines parsed</span>');
    facts.push('<span class="sig-f" title="' + _esc(fmt === 'json'
        ? 'Durations are read from the nanosecond Duration field, not re-parsed from a rounded display string.'
        : 'The common log writes whole milliseconds, so sub-millisecond timing is not knowable.')
        + '"><i class="ph-bold ph-timer"></i>' + (fmt === 'json' ? 'ns precision' : 'ms precision') + '</span>');
    const tls = rows.some(e => e.tls);
    facts.push('<span class="sig-f ' + (tls ? 'sig-f-on' : 'sig-f-off')
        + '" title="' + _esc(tls ? 'TLSVersion is present on these lines.'
            : 'No TLSVersion field on these lines. Add it with accessLog.fields.names in the static config.')
        + '"><i class="ph-bold ph-shield-check"></i>' + (tls ? 'tls fields' : 'no tls fields') + '</span>');
    facts.push('<span class="sig-f ' + (meta.geoOn ? 'sig-f-on' : 'sig-f-off')
        + '" title="' + (meta.geoOn ? 'Country lookup is on, so the Geography panel below is live.' : 'Country lookup is off.')
        + '"><i class="ph-bold ph-globe-hemisphere-west"></i>geoip ' + (meta.geoOn ? 'on' : 'off') + '</span>');
    const auto = _lgAutoOn();
    facts.push('<span class="sig-f ' + (auto ? 'sig-f-on' : 'sig-f-off') + '" title="' + _esc(auto
        ? 'This panel refetches every ' + (_lgAutoInterval() / 1000) + ' seconds while the Logs tab is open and the browser tab is visible. It pauses while you are typing in the filter box.'
        : 'This panel does not poll. It was read ' + _sdAgo(_lgStamp) + ' and only changes when you press refresh or change the window.')
        + '"><i class="ph-bold ph-arrows-clockwise"></i>auto refresh ' + (auto ? 'every ' + (_lgAutoInterval() / 1000) + 's' : 'off') + '</span>');
    return '<div class="sig-runtime" id="logRuntime">' + facts.join('') + '</div>';
}

function renderLogs() {
    const container = document.getElementById('logsContent');
    if (!container) return;
    const q = (document.getElementById('logSearch')?.value || '').toLowerCase();
    const geoOn = _geoEnabled && _geoAvailable;

    const fetched = _logParsed.length;
    const parsedN = _logParsed.reduce((a, o) => a + (o.e ? 1 : 0), 0);
    const format = (_logParsed.find(o => o.e) || {}).e?.format || null;

    const searched = q ? _logParsed.filter(o => o.raw.toLowerCase().includes(q)) : _logParsed;
    const searchedRows = searched.map(o => o.e).filter(Boolean);
    const facetDead = {};
    _lgActiveFacets().forEach(k => {
        facetDead[k] = !searchedRows.some(e => _lgFacetHit(k, _logFacet[k], e));
    });

    const faceted = searched.filter(o => _lgMatch(o.e));
    const countryData = geoOn ? _geoCountryCounts(faceted.map(o => o.e && o.e.ip).filter(Boolean)) : {};
    const visible = _logCountryFilter
        ? faceted.filter(o => o.e && _geoCache[o.e.ip] && _geoCache[o.e.ip].country_code === _logCountryFilter)
        : faceted;

    renderLogStats(visible, {
        fetched: fetched, parsed: parsedN, unparsed: fetched - parsedN,
        format: format, q: q, geoOn: geoOn,
        all: _logParsed.map(o => o.e).filter(Boolean), facetDead: facetDead
    });

    const feed = visible.slice().reverse();

    _logRows = feed.map(o => o.e);

    const statusColor = s => !s ? 'var(--muted)' : s >= 500 ? 'var(--red)' : s >= 400 ? 'var(--yellow)' : 'var(--green)';

    const cards = feed.map(({ raw, e }, i) => {
        if (!e) {
            return '<div class="sig-ep-row lg-raw" data-health="idle" title="' + _esc('No access log format matched this line') + '">'
                + '<span class="sig-ep-id"><span class="sig-ep-name">' + _esc(raw) + '</span></span>'
                + '<span class="sig-ep-flags"><span class="sig-idle-txt">unparsed</span></span></div>';
        }
        const s = Number(e.status) || 0;
        const health = s >= 500 ? 'down' : s >= 400 ? 'warn' : '';
        const statCls = s >= 500 ? 'd-bad' : s >= 400 ? 'd-warn' : s ? 'd-on' : 'd-off';
        const geo = _geoCache[e.ip];
        const cc = (geoOn && geo && geo.country_code) ? geo.country_code : '';
        const owner = _sdShort(e.service || e.router || '');
        const dur = (e.duration && e.duration !== '-') ? e.duration : '';
        const kind = [owner, dur].filter(Boolean).join(' · ');
        return '<div class="sig-ep-row" role="button" tabindex="0" data-lg-i="' + i + '"'
            + (health ? ' data-health="' + health + '"' : '')
            + ' title="' + _esc(e.method + ' ' + e.path + ' - ' + (e.status || '?') + ' ' + _lgStatusName(e.status)) + '">'
            + '<span class="sig-ep-id"><span class="sig-ep-name">' + _esc(e.path || '/') + '</span>'
            + '<span class="sig-idle-txt">' + _esc(e.method || '') + '</span></span>'
            + '<span class="sig-ep-addr">'
            + (cc ? _flagEmoji(cc) + ' ' : '') + _esc(e.ip || '') + '</span>'
            + '<span class="sig-ep-n ' + statCls + '">' + (e.status || '-') + '</span>'
            + '<span class="sig-ep-flags"><span class="sig-idle-txt">' + _esc(_lgStatusName(e.status)) + '</span></span>'
            + (kind ? '<span class="sig-ep-kind">' + _esc(kind) + '</span>' : '')
            + '</div>';
    }).join('');

    const geoPanel = (geoOn && Object.keys(countryData).length) ? _geoPanelHtml('logGeo', countryData, _logCountryFilter, 'clearLogCountryFilter()') : '';

    const emptyTxt = (q || _logCountryFilter || _lgActiveFacets().length)
        ? 'Nothing matches the active filters. Use the clear button in the panel above.'
        : (fetched ? 'No line in this window could be read as a log entry.' : 'No log lines in the fetched window.');
    const body = visible.length
        ? '<div class="sig-ep-rows lg-feed-rows">' + cards + '</div>'
        : '<div class="atk-empty"><i class="ph-fill ph-receipt"></i>'
            + '<div class="atk-empty-t">Nothing to show</div><p class="lg-note">' + _esc(emptyTxt) + '</p></div>';

    container.innerHTML = geoPanel + '<div class="sig-root"><section class="sig-ep lg-feed">'
        + '<div class="sig-ep-head">'
        + '<i class="ph-fill ph-receipt sig-ep-headic"></i>'
        + '<span class="sc-sec-label">Access log</span>'
        + '<span class="d-n">' + _sdNum(visible.length) + '</span>'
        + '<span class="sc-sec-rule"></span>'
        + '<span class="sig-idle-txt">' + _sdNum(visible.length) + ' of ' + _sdNum(fetched) + ' lines</span>'
        + '</div>' + body + '</section></div>';

    if (geoPanel) renderGeoMap(document.getElementById('logGeoMap'), countryData, logGeo_click, _logCountryFilter);
}

function openLogDetail(e) {
    closeOtherPanels('logDetailPanel');
    const sc = !e.status ? 'var(--muted)' : e.status >= 500 ? 'var(--red)' : e.status >= 400 ? 'var(--yellow)' : 'var(--green)';
    const mc = { GET:'var(--blue)', POST:'var(--green)', PUT:'var(--yellow)', DELETE:'var(--red)', PATCH:'var(--purple)' }[e.method] || 'var(--muted)';
    document.getElementById('ldBadges').innerHTML =
        `<span class="inline-flex items-center gap-1 text-xs font-bold px-2 py-1 rounded" style="background:color-mix(in srgb, ${sc} 12%, transparent);color:${sc};border:1px solid color-mix(in srgb, ${sc} 30%, transparent)">${e.status||'-'} ${_esc(_lgStatusName(e.status))}</span>` +
        `<span class="text-xs font-mono font-bold px-2 py-1 rounded" style="background:color-mix(in srgb, ${mc} 12%, transparent);color:${mc};border:1px solid color-mix(in srgb, ${mc} 30%, transparent)">${_esc(e.method)}</span>`;
    const _g = _geoCache[e.ip];
    const rows = [
        ['Path', e.path], ['IP', e.ip], ['Date', e.date],
        ...(_g && _g.country_code ? [['Country', `${_flagEmoji(_g.country_code)} ${_g.country_name || _g.country_code}`]] : []),
        ...(e.domain ? [['Domain', e.domain]] : []),
        ...(e.scheme ? [['Scheme', e.scheme]] : []),
        ...(e.ep ? [['Entry Point', e.ep]] : []),
        ...(e.size && e.size !== '-' ? [['Size', e.size]] : []),
        ...(e.duration && e.duration !== '-' ? [['Duration', e.duration]] : []),
        ...(e.origin != null && e.origin !== e.status ? [['Origin Status', e.origin + ' ' + _lgStatusName(e.origin) + ' (Traefik answered ' + e.status + ' itself)']] : []),
        ...(e.retries ? [['Retry Attempts', String(e.retries)]] : []),
        ...(e.tls ? [['TLS', e.tls]] : []),
        ...(e.router ? [['Router', e.router]] : []),
        ...(e.service ? [['Service', e.service]] : []),
        ...(e.serviceUrl && e.serviceUrl !== '-' ? [['Backend URL', e.serviceUrl]] : []),
    ];
    document.getElementById('ldGrid').innerHTML = rows.map(([k,v],i) =>
        `<div class="flex items-start gap-3 px-4 py-2.5" style="${i<rows.length-1?'border-bottom:1px solid var(--border)':''}"><span class="text-xs font-medium flex-shrink-0" style="color:var(--muted);min-width:80px">${k}</span><span class="text-xs font-mono break-all" style="color:var(--text)">${_esc(v)}</span></div>`
    ).join('');
    document.getElementById('ldRaw').textContent = e.raw;
    document.getElementById('logDetailPanel').classList.add('open');
    setDetailDockOpen(true);
    const bd = document.getElementById('logDetailBackdrop');
    if (bd) { bd.style.opacity = '1'; bd.style.pointerEvents = 'auto'; }
}

function closeLogDetail() {
    setDetailDockOpen(false);
    document.getElementById('logDetailPanel').classList.remove('open');
    const bd = document.getElementById('logDetailBackdrop');
    if (bd) { bd.style.opacity = ''; bd.style.pointerEvents = ''; }
}

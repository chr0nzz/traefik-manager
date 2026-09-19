const SD_STRIP_CAP = 150;
const SD_ANOM_CAP  = 600;
const SD_SEP = '<span class="tm-sep"> &middot; </span>';

const SD_PROV = {
    docker:            { g: 'ph-cube',          tab: 'docker' },
    swarm:             { g: 'ph-graph',         tab: 'swarm' },
    kubernetes:        { g: 'ph-circles-three', tab: 'kubernetes' },
    kubernetescrd:     { g: 'ph-circles-three', tab: 'kubernetes' },
    kubernetesingress: { g: 'ph-circles-three', tab: 'kubernetes' },
    kubernetesgateway: { g: 'ph-circles-three', tab: 'kubernetes' },
    nomad:             { g: 'ph-circles-four',  tab: 'nomad' },
    ecs:               { g: 'ph-cloud',         tab: 'ecs' },
    consulcatalog:     { g: 'ph-address-book',  tab: 'consulcatalog' },
    consul:            { g: 'ph-database',      tab: 'consul' },
    redis:             { g: 'ph-database',      tab: 'redis' },
    etcd:              { g: 'ph-database',      tab: 'etcd' },
    zookeeper:         { g: 'ph-database',      tab: 'zookeeper' },
    http:              { g: 'ph-link',          tab: 'http_provider' },
    file:              { g: 'ph-file-text',     tab: 'services' },
    internal:          { g: 'ph-traffic-signal', tab: 'internal' },
};

const SD_CARD_META = {
    http:       { title: t('HTTP Routers'),      icon: 'ph-arrows-split',          accent: 'var(--blue)',   label: t('HTTP routers') },
    stream:     { title: t('TCP / UDP Routers'), icon: 'ph-arrows-left-right', accent: 'var(--teal)',   label: t('stream routers') },
    service:    { title: t('Services'),          icon: 'ph-hard-drives',       accent: 'var(--green)',  label: tc('label', 'services') },
    middleware: { title: t('Middlewares'),       icon: 'ph-stack',   accent: 'var(--purple)', label: tc('label', 'middlewares') },
};

const SD_PROV_ALIAS = {
    kubernetescrd:     'kubernetes',
    kubernetesingress: 'kubernetes',
    kubernetesgateway: 'kubernetes',
};

const SD_ORDER = { err: 0, warn: 1, idle: 2, ok: 3 };

let _sdScope = null;
let _sdModel = null;
let _sdStamp = 0;
let _sdAgeTimer = null;
let _sdBound = false;

function _sdNum(n) { return tmNumber(n); }

function _sdShort(name) { return String(name || '').split('@')[0]; }

function _sdList(v) { return Array.isArray(v) ? v : []; }

function _sdProvKey(p) {
    const k = String(p || '').toLowerCase();
    return SD_PROV_ALIAS[k] || k;
}

function _sdProvider(o) {
    const p = o && o.provider;
    if (p) return _sdProvKey(p);
    const n = String((o && o.name) || '');
    const at = n.lastIndexOf('@');
    return at === -1 ? 'file' : _sdProvKey(n.slice(at + 1));
}

function _sdPlain(html) {
    const d = document.createElement('div');
    d.innerHTML = String(html || '');
    return (d.textContent || '').replace(/\s+/g, ' ').trim();
}

function _sdTerse(reason) {
    let r = String(reason || '').replace(/\s+/g, ' ').trim();
    r = r.replace(/(?:the )?(service|middleware|router) "([^"@]+)(?:@[^"]*)?" does not exist/gi, 'missing $1 $2');
    r = r.replace(/(?:the )?(service|middleware|router) "([^"@]+)(?:@[^"]*)?" not found/gi, 'missing $1 $2');
    if (r.length <= 40) return r;
    return r.slice(0, 39).replace(/[\s,;:.-]+$/, '') + '…';
}

function _sdProvMeta(p) {
    const k = String(p || '').toLowerCase();
    if (SD_PROV[k]) return SD_PROV[k];
    if (k.indexOf('plugin-') === 0) return { g: 'ph-puzzle-piece', tab: 'plugins' };
    return { g: 'ph-plug', tab: '' };
}

function _sdBucket(o) {
    const s = String((o && o.status) || '').toLowerCase();
    if (s === 'enabled')  return 'enabled';
    if (s === 'disabled') return 'disabled';
    if (s === 'warning')  return 'warning';
    return 'unknown';
}

function _sdErrors(o) {
    const e = o && o.error;
    if (!e) return [];
    const list = Array.isArray(e) ? e : [e];
    return list.map(x => (typeof x === 'string' ? x : (x && x.message) || JSON.stringify(x)))
               .map(x => String(x).trim())
               .filter(Boolean);
}

function _sdUsing(r) {
    if (Array.isArray(r && r.using))       return r.using.filter(Boolean).map(String);
    if (Array.isArray(r && r.entryPoints)) return r.entryPoints.filter(Boolean).map(String);
    return [];
}

function _sdBackends(s) {
    const m = s && s.serverStatus;
    if (!m || typeof m !== 'object') return null;
    const keys = Object.keys(m);
    if (!keys.length) return null;
    let up = 0;
    keys.forEach(k => { if (String(m[k]).toUpperCase() === 'UP') up++; });
    if (up === keys.length && !(s.loadBalancer && s.loadBalancer.healthCheck)) return null;
    return { total: keys.length, up: up, down: keys.length - up };
}

function _sdComposite(s) {
    if (!s || typeof s !== 'object') return '';
    if (s.weighted)            return 'weighted';
    if (s.mirroring)           return 'mirroring';
    if (s.failover)            return 'failover';
    if (s.highestRandomWeight) return t('highest random weight');
    return '';
}

function _sdSection(o) {
    const s = (o && typeof o === 'object') ? o : {};
    const n = k => (typeof s[k] === 'number' && isFinite(s[k]) ? s[k] : null);
    return { total: n('total'), warnings: n('warnings'), errors: n('errors') };
}

function _sdSumSections(list) {
    let total = null, warnings = null, errors = null;
    list.forEach(s => {
        if (s.total    !== null) total    = (total    || 0) + s.total;
        if (s.warnings !== null) warnings = (warnings || 0) + s.warnings;
        if (s.errors   !== null) errors   = (errors   || 0) + s.errors;
    });
    return { total: total, warnings: warnings, errors: errors };
}

function _sdOverview(ov) {
    const o = (ov && typeof ov === 'object' && !ov.error) ? ov : {};
    const leg = (proto, kind) => _sdSection(((o[proto] || {})[kind]) || {});
    return {
        routersHttp: leg('http', 'routers'),
        routersTcp:  leg('tcp',  'routers'),
        routersUdp:  leg('udp',  'routers'),
        svcHttp:     leg('http', 'services'),
        svcTcp:      leg('tcp',  'services'),
        svcUdp:      leg('udp',  'services'),
        mwHttp:      leg('http', 'middlewares'),
        mwTcp:       leg('tcp',  'middlewares'),
        features:    (o.features && typeof o.features === 'object') ? o.features : null,
        providers:   _sdList(o.providers)
            .map(p => _sdProvKey(p))
            .filter(p => p && p !== 'plugin'),
    };
}

function _sdObj(raw, kind, ctx) {
    const name = String((raw && raw.name) || '');
    const o = {
        name: name,
        short: _sdShort(name),
        provider: _sdProvider(raw),
        status: _sdBucket(raw),
        rawStatus: String((raw && raw.status) || ''),
        errors: _sdErrors(raw),
        cell: 'ok',
        reason: '',
        kind: kind,
    };
    if (o.status === 'disabled') {
        o.cell = 'err';
        o.reason = o.errors.length ? t('disabled - {v0}', { v0: o.errors[0] }) : t('disabled');
        return o;
    }
    if (o.status === 'warning') {
        o.cell = 'warn';
        o.reason = o.errors.length ? o.errors[0] : t('warning');
        return o;
    }
    if (o.status === 'unknown')  {
        o.cell = 'idle';
        o.reason = (raw && raw.status) ? t('unreported status "{status}"', { status: raw.status }) : t('no status reported');
        return o;
    }
    if (kind === 'http' || kind === 'stream') {
        o.using = _sdUsing(raw);
        if (!o.using.length) { o.cell = 'idle'; o.reason = t('enabled, bound to no entry point'); o.unbound = true; }
        return o;
    }
    if (kind === 'service') {
        o.backends = _sdBackends(raw);
        o.composite = _sdComposite(raw);
        if (!o.backends) {
            if (o.composite) { o.reason = t('{composite} service, health lives on its children', { composite: o.composite }); return o; }
            o.cell = 'idle'; o.reason = t('no health check configured'); o.unchecked = true; return o;
        }
        if (o.backends.down > 0 && o.backends.up === 0) {
            o.cell = 'err';
            o.reason = t('all {total} backends DOWN', { total: o.backends.total });
            o.down = true;
        } else if (o.backends.down > 0) {
            o.cell = 'warn';
            o.reason = t('{down} of {total} backends DOWN', { down: o.backends.down, total: o.backends.total });
            o.degraded = true;
        }
        return o;
    }
    if (kind === 'middleware') {
        const short = (ctx && ctx.refShort && ctx.refShort.get(o.provider)) || null;
        const used = _sdList(raw && raw.usedBy).length > 0
            || !!(ctx && ctx.refFull && ctx.refFull.has(o.name.toLowerCase()))
            || !!(short && short.has(o.short));
        if (!used) { o.cell = 'idle'; o.reason = t('referenced by no router'); o.unused = true; }
        return o;
    }
    return o;
}

function _sdTally(objs) {
    const t = { total: objs.length, err: 0, warn: 0, idle: 0, ok: 0,
                disabled: 0, warning: 0, unknown: 0, unbound: 0, unused: 0, unchecked: 0, degraded: 0,
                composite: 0, down: 0 };
    objs.forEach(o => {
        t[o.cell]++;
        if (o.status === 'disabled') t.disabled++;
        if (o.status === 'warning')  t.warning++;
        if (o.status === 'unknown')  t.unknown++;
        if (o.down)      t.down++;
        if (o.unbound)   t.unbound++;
        if (o.unused)    t.unused++;
        if (o.unchecked) t.unchecked++;
        if (o.degraded)  t.degraded++;
        if (o.composite) t.composite++;
    });
    return t;
}

function _sdProvStats(objs) {
    const map = new Map();
    objs.forEach(o => {
        let e = map.get(o.provider);
        if (!e) { e = { p: o.provider, n: 0, bad: 0, warn: 0 }; map.set(o.provider, e); }
        e.n++;
        if (o.cell === 'err')  e.bad++;
        if (o.cell === 'warn') e.warn++;
    });
    return [...map.values()].sort((a, b) => b.n - a.n || a.p.localeCompare(b.p));
}

function _sdWorstFirst(objs) {
    return objs.filter(o => o.cell === 'err' || o.cell === 'warn')
               .sort((a, b) => SD_ORDER[a.cell] - SD_ORDER[b.cell] || a.name.localeCompare(b.name));
}

function _sdCells(objs) {
    const c = { err: [], warn: [], idle: [], ok: 0 };
    objs.forEach(o => {
        if (o.cell === 'ok') { c.ok++; return; }
        c[o.cell].push((o.name || o.short) + ': ' + (o.reason || o.cell));
    });
    return c;
}

function _sdStrip(cells, aria, extraCls) {
    const err = cells.err || [], warn = cells.warn || [], idle = cells.idle || [], ok = cells.ok || 0;
    const anomalies = err.length + warn.length + idle.length;
    const total = anomalies + ok;
    const cell = (cls, title) =>
        '<i class="sig-cell' + (cls ? ' sig-cell-' + cls : '') + '"'
        + (title ? ' title="' + _esc(title) + '"' : '') + '></i>';
    let html = '';
    let budget = SD_ANOM_CAP;
    let dropped = 0;
    [['err', err], ['warn', warn], ['idle', idle]].forEach(pair => {
        pair[1].forEach(t => {
            if (budget > 0) { html += cell(pair[0], t); budget--; } else { dropped++; }
        });
    });
    const room = Math.max(0, SD_STRIP_CAP - Math.min(anomalies, SD_ANOM_CAP));
    const shownOk = Math.min(ok, room);
    for (let i = 0; i < shownOk; i++) html += cell('', '');
    const hidden = (ok - shownOk) + dropped;
    if (hidden > 0) {
        html += `<span class="sig-more" title="${th('{hidden} more objects not drawn individually', { hidden: tmHtml(_sdNum(hidden)) })}">+${_sdNum(hidden)}</span>`;
    }
    if (total === 0) {
        html = `<span class="sig-more" style="margin-left:0">${cells.blind ? th('no data') : th('nothing configured')}</span>`;
    }
    return '<div class="sig-strip' + (extraCls ? ' ' + extraCls : '') + '" role="img" aria-label="'
         + _esc(aria) + '">' + html + '</div>';
}

function _sdFlag(f, words) {
    return '<button type="button" class="sig-flag ' + f.cls + '" data-sd="' + _esc(f.go || '') + '"'
         + ' title="' + _esc(f.tip || (f.n + ' ' + f.label)) + '">'
         + '<i class="' + f.ic + '"></i><b>' + _sdNum(f.n) + '</b>'
         + (words === false ? '' : '<span class="sig-fl">' + _esc(f.label) + '</span>')
         + '</button>';
}

function _sdProvSplit(objs) {
    const by = new Map();
    _sdList(objs).forEach(o => by.set(o.provider, (by.get(o.provider) || 0) + 1));
    return [...by.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
}

function _sdOwnList(go) {
    return /^tab=(services|middlewares)/.test(String(go || ''));
}

function _sdExc(cls, ic, n, label, baseGo, objs) {
    const split = _sdProvSplit(objs);
    let go = baseGo;
    if (split.length === 1 && split[0][0] !== 'file' && split[0][0] !== 'internal' && _sdOwnList(baseGo)) {
        const tab = _sdProvMeta(split[0][0]).tab;
        if (tab && tab !== 'services' && tab !== 'live') go = 'tab=' + tab;
    }
    const foreign = split.some(x => x[0] !== 'file');
    if (Array.isArray(label)) label = n === 1 ? label[0] : label[1];
    const bits = [_sdNum(n) + ' ' + label];
    if (foreign && split.length) bits.push(split.map(x => _sdNum(x[1]) + ' ' + x[0]).join(', '));
    if (go !== baseGo) bits.push(t('opens the {v0} tab, where this provider is read-only', { v0: split[0][0] }));
    else if (foreign && _sdOwnList(baseGo)) bits.push(t('that list only holds objects from your own config files, so open the provider tab for the rest'));
    return { cls: cls, ic: ic, n: n, label: label, go: go, tip: bits.join(' - ') };
}

function _sdProvFoot(provs, note) {
    if (!provs.length) {
        return '<div class="sig-foot"><span class="sig-foot-note">' + _esc(note || t('no objects')) + '</span></div>';
    }
    const items = provs.map(p => {
        const meta  = _sdProvMeta(p.p);
        const cls   = p.bad ? ' sig-prov-bad' : p.warn ? ' sig-prov-warn' : '';
        const glyph = p.bad ? '<i class="ph-fill ph-x-circle sig-pg"></i>'
                    : p.warn ? '<i class="ph-fill ph-warning sig-pg"></i>' : '';
        const tip = p.p + ' - ' + _sdNum(p.n)
        + (p.bad  ? ', ' + tn('owns {n} failure', 'owns {n} failures', p.bad) : '')
        + (p.warn ? ', ' + tn('owns {n} warning', 'owns {n} warnings', p.warn) : '')
        + '. ' + t('Click to scope every card to this provider.');
        return '<button type="button" class="sig-prov' + cls + '" data-sd="scope=' + _esc(p.p) + '"'
             + ' title="' + _esc(tip) + '"><i class="ph-bold ' + meta.g + '"></i><b>'
             + _sdNum(p.n) + '</b>' + glyph + '</button>';
    }).join('');
    return '<div class="sig-foot"><span class="sig-provs">' + items + '</span></div>';
}

function _sdCard(c) {
    const meta = SD_CARD_META[c.key];
    const flags = c.flags.length
        ? c.flags.map(f => _sdFlag(f)).join('')
        : `<span class="sig-ok"><i class="sig-dot"></i>${thc('label', 'healthy')}</span>`;
    return '<article class="sig-card" data-health="' + c.health + '" style="--tm-accent:' + meta.accent + '">'
         + '<div class="sig-head">'
         + '<span class="sig-ic"><i class="ph-fill ' + meta.icon + '"></i></span>'
         + '<span class="sig-title">' + _esc(meta.title) + '</span>'
         + '<button type="button" class="sig-explore" data-sd="' + _esc(c.explore) + '">'
         + _esc(c.exploreLabel) + ' <i class="ph-bold ph-arrow-right"></i></button>'
         + '</div>'
         + '<div class="sig-metric"><span class="sig-total">'
         + (c.total === null ? '-' : _sdNum(c.total)) + '</span>'
         + '<span class="sig-flags">' + flags + '</span></div>'
         + '<div class="sig-sub" title="' + _esc(c.subFull || _sdPlain(c.sub)) + '">' + c.sub + '</div>'
         + _sdStrip(c.cells, c.aria)
         + _sdProvFoot(c.provs, c.provNote)
         + '</article>';
}

function _sdSubParts(main, tail) {
    return {
        html: '<span class="sig-sub-main">' + main + '</span>'
            + (tail ? '<span class="sig-sub-tail">' + SD_SEP + tail + '</span>' : ''),
        full: _sdPlain(main + (tail ? SD_SEP + tail : '')),
    };
}

function _sdSubOffender(objs, tail) {
    const worst = _sdWorstFirst(objs);
    if (!worst.length) return _sdSubParts(tail || '', '');
    const first = worst[0];
    const more = worst.length - 1;
    const head = '<b>' + _esc(first.name || first.short) + '</b> ';
    const count = more > 0 ? ', ' + th('+{count} more', { count: _sdNum(more) }) : '';
    if (tail && !more && String(first.reason || '').toLowerCase() === String(tail).toLowerCase()) tail = '';
    const parts = _sdSubParts(head + _esc(_sdTerse(first.reason)) + count, tail);
    parts.full = _sdPlain(head + _esc(first.reason) + count + (tail ? SD_SEP + tail : ''));
    return parts;
}

function _sdSubPlain(text) {
    return _sdSubParts(text, '');
}

function _sdHealth(t) {
    if (t.err > 0 || t.disabled > 0) return 'down';
    if (t.warn > 0 || t.warning > 0 || t.degraded > 0) return 'warn';
    return 'up';
}

function _sdAria(label, total, tally) {
    if (total === 0) return t('no {label} configured', { label });
    const bits = [];
    if (tally.disabled)  bits.push(t('{count} disabled', { count: tally.disabled }));
    if (tally.down)      bits.push(t('{count} unreachable', { count: tally.down }));
    if (tally.warning)   bits.push(tn('{count} warning', '{count} warnings', tally.warning, { count: tally.warning }));
    if (tally.degraded)  bits.push(t('{count} degraded', { count: tally.degraded }));
    if (tally.unbound)   bits.push(t('{count} unbound', { count: tally.unbound }));
    if (tally.unused)    bits.push(t('{count} unused', { count: tally.unused }));
    if (tally.composite) bits.push(t('{count} composite', { count: tally.composite }));
    if (tally.unchecked) bits.push(t('{count} unchecked', { count: tally.unchecked }));
    if (tally.unknown)   bits.push(t('{count} unreported', { count: tally.unknown }));
    bits.push(t('{count} healthy', { count: _sdNum(tally.ok) }));
    return t('{count} {objects}: {details}', { count: _sdNum(total), objects: label, details: bits.join(', ') });
}

function _sdAgo(ms) {
    const s = Math.max(0, Math.round((Date.now() - ms) / 1000));
    if (s < 60) return t('{s}s ago', { s });
    const m = Math.floor(s / 60);
    if (m < 60) return t('{m}m ago', { m });
    const h = Math.floor(m / 60);
    if (h < 24) return t('{h}h ago', { h });
    return t('{floor}d ago', { floor: Math.floor(h / 24) });
}

function _sdUptime(startDate) {
    const started = Date.parse(startDate || '');
    if (!started || !isFinite(started)) return null;
    let s = Math.floor((Date.now() - started) / 1000);
    if (s < 0) return null;
    const d = Math.floor(s / 86400); s -= d * 86400;
    const h = Math.floor(s / 3600);  s -= h * 3600;
    const m = Math.floor(s / 60);
    if (d) return t('up {d}d {h}h', { d, h });
    if (h) return t('up {h}h {m}m', { h, m });
    return t('up {m}m', { m });
}

const SD_UDP = { tag: 'UDP', cls: 'd-proto-udp', key: 'udp' };
const SD_TCP = { tag: 'TCP', cls: 'd-proto-tcp', key: 'tcp' };

function _sdEpProto(ep, info) {
    const addr  = String((ep && ep.address) || '');
    const httpN = (info && info.httpN) || 0;
    const tcpN  = (info && info.tcpN)  || 0;
    const udpN  = (info && info.udpN)  || 0;
    if (httpN === 0 && tcpN > 0) return SD_TCP;
    if (httpN === 0 && udpN > 0) return SD_UDP;
    if (httpN === 0 && /\/udp$/i.test(addr)) return SD_UDP;
    if (httpN === 0 && /\/tcp$/i.test(addr)) return SD_TCP;
    const port = addr.replace(/\/(tcp|udp)$/i, '').replace(/^.*:/, '');
    const tls = !!(ep && ep.http && ep.http.tls) || !!(info && info.tls)
             || port === '443' || port === '8443';
    return { tag: tls ? 'HTTPS' : 'HTTP', cls: 'd-proto-http', key: 'http' };
}

function _sdEpGlyphs(ep, info) {
    const http = (ep && ep.http) || {};
    const tls  = http.tls || null;
    const red  = (http.redirections && http.redirections.entryPoint) || null;
    const mws  = _sdList(http.middlewares);
    const pp   = _sdList(ep.proxyProtocol && ep.proxyProtocol.trustedIPs);
    const g = [];
    if (ep.asDefault) g.push(['ph-fill ph-star', 'd-warn', t('asDefault - routers that name no entry point bind here')]);
    if (tls) g.push(['ph-bold ph-lock-key', 'd-on',
        (tls.certResolver ? t('TLS terminated, certResolver {resolver}', { resolver: tls.certResolver }) : t('TLS terminated, no certResolver set'))]);
    if (ep.http3) g.push(['ph-bold ph-lightning', 'd-mw',
        (ep.http3.advertisedPort ? t('HTTP/3 advertised on port {port}', { port: ep.http3.advertisedPort }) : t('HTTP/3 advertised'))]);
    if (mws.length) g.push(['ph-bold ph-stack', 'd-mw',
        t('Entry point middlewares {mws} are prepended into every router on this entry point', { mws: mws.join(', ') })]);
    if (red) g.push(['ph-bold ph-arrow-bend-up-right', 'd-blue',
        _sdRedirectText(red)]);
    if (!red && _sdEpProto(ep, info).tag === 'HTTP') {
        g.push(['ph-bold ph-lock-simple-open', 'd-off',
            t('No entry-point-level TLS, and no router on it reports TLS either')]);
    }
    if (info.internalOnly) g.push(['ph-bold ph-traffic-signal', 'd-off', t('Serves internal routers only')]);
    if (pp.length) g.push(['ph-bold ph-shield-check', 'd-off', t('PROXY protocol trusted from {pp}', { pp: pp.join(', ') })]);
    return g.map(x => '<i class="' + x[0] + ' d-glyph ' + x[1] + '" title="' + _esc(x[2]) + '"></i>').join('');
}

function _sdRedirectText(red) {
    const to = red.to || t('another entry point');
    if (red.permanent === false) {
        return red.scheme ? t('Temporary redirect to {to} over {scheme}', { to, scheme: red.scheme }) : t('Temporary redirect to {to}', { to });
    }
    return red.scheme ? t('Permanent redirect to {to} over {scheme}', { to, scheme: red.scheme }) : t('Permanent redirect to {to}', { to });
}

function _sdEpFacts(ep, info) {
    const http = (ep && ep.http) || {};
    const tls  = http.tls || null;
    const red  = (http.redirections && http.redirections.entryPoint) || null;
    const mws  = _sdList(http.middlewares);
    const rt   = (ep.transport && ep.transport.respondingTimeouts) || {};
    const pp   = _sdList(ep.proxyProtocol && ep.proxyProtocol.trustedIPs);
    const fh   = _sdList(ep.forwardedHeaders && ep.forwardedHeaders.trustedIPs);
    const f = [];
    if (ep.asDefault) f.push('asDefault');
    if (tls) f.push(tls.certResolver ? t('TLS resolver {certResolver}', { certResolver: tls.certResolver }) : t('TLS, no certResolver'));
    if (tls && tls.options) f.push(t('TLS options {options}', { options: tls.options }));
    if (ep.http3) f.push('HTTP/3');
    if (red) {
        f.push(t('redirects to {to}', { to: red.to || t('another entry point') }));
        f.push(red.permanent === false ? t('302 temporary') : t('301 permanent'));
    }
    if (mws.length) f.push(mws.join(', '));
    if (pp.length) f.push('proxyProtocol ' + pp.join(' '));
    if (fh.length) f.push('forwardedHeaders ' + fh.join(' '));
    if (ep.udp && ep.udp.timeout && _sdEpProto(ep, info).key === 'udp') f.push(t('udp timeout {timeout}', { timeout: ep.udp.timeout }));
    if (rt.idleTimeout && rt.idleTimeout !== '0s') f.push(t('idle {timeout}', { timeout: rt.idleTimeout }));
    if (rt.readTimeout && rt.readTimeout !== '0s') f.push(t('read {timeout}', { timeout: rt.readTimeout }));
    if (ep.allowACMEByPass) f.push(t('ACME bypass allowed'));
    if (ep.reusePort) f.push('reusePort');
    return f;
}

function _sdEpKind(ep, info) {
    const p    = _sdEpProto(ep, info);
    const http = (ep && ep.http) || {};
    const red  = (http.redirections && http.redirections.entryPoint) || null;
    if (red) return (red.permanent === false
            ? t('redirects everything to {to}, 302 temporary', { to: red.to || t('another entry point') })
            : t('redirects everything to {to}, 301 permanent', { to: red.to || t('another entry point') }));
    if (info.blind) return t('router list unavailable, bindings unknown');
    if (info.n === 0) return t('no router binds this entry point');
    if (p.key === 'udp') return t('raw UDP datagrams');
    if (p.key === 'tcp') return t('raw TCP passthrough');
    if (info.internalOnly) return t('Traefik dashboard and API');
    if (p.tag === 'HTTPS') return (http.tls && http.tls.certResolver ? t('HTTPS front door, TLS via {resolver}', { resolver: http.tls.certResolver }) : t('HTTPS front door'));
    return t('plain HTTP entry point');
}

function _sdEpRow(ep, info) {
    const p = _sdEpProto(ep, info);
    const health = info.err > 0 ? 'down' : (!info.blind && info.n === 0) ? 'idle' : (info.warn > 0 ? 'warn' : 'up');
    const base = 'tab=services;proto=' + p.key + ';ep=' + ep.name;
    const go = _sdExc('', '', info.n, 'routers', base, info.objs).go;
    const flags = [];
    const disabledN = info.err - (info.down || 0);
    if (disabledN) flags.push(_sdExc('d-bad',  'ph-fill ph-x-circle', disabledN,  tc('label', 'disabled'), base + ';apistatus=disabled', info.objs.filter(o => o.cell === 'err' && !o.down)));
    if (info.down) flags.push(_sdExc('d-bad',  'ph-fill ph-warning-octagon', info.down, tc('label', 'unreachable'), base + ';apistatus=unreachable', info.objs.filter(o => o.down)));
    const degradedN = info.degraded || 0;
    const warnN = info.warn - degradedN;
    if (degradedN) flags.push(_sdExc('d-warn', 'ph-fill ph-warning-diamond', degradedN, tc('label', 'degraded'), base + ';apistatus=degraded', info.objs.filter(o => o.degraded)));
    if (warnN) flags.push(_sdExc('d-warn', 'ph-fill ph-warning',  warnN, tc('label', 'warnings'), base + ';apistatus=warning', info.objs.filter(o => o.cell === 'warn' && !o.degraded)));
    const flagHtml = flags.length
        ? flags.map(f => _sdFlag(f, false)).join('')
        : info.blind ? `<span class="sig-idle-txt">${th('no data')}</span>`
        : info.n === 0 ? `<span class="sig-idle-txt">${thc('label', 'idle')}</span>`
        : '<span class="sig-ok"><i class="sig-dot"></i></span>';
    const facts = _sdEpFacts(ep, info);
    const aria = info.blind
        ? t('router bindings for {name} could not be read from the Traefik API', { name: ep.name })
        : info.n === 0
        ? t('no routers bound to {name}', { name: ep.name })
        : tn('{count} router on {name}', '{count} routers on {name}', info.n, { count: _sdNum(info.n), name: ep.name })
          + ((info.err || info.warn)
              ? t(': {disabled} disabled, {down} unreachable, {degraded} degraded, {warnings} warnings',
                  { disabled: info.err - (info.down || 0), down: info.down || 0, degraded: degradedN, warnings: warnN })
              : t(', all live'));
    return `<div class="sig-ep-row" data-health="${health}" tabindex="0" role="button" data-sd="${_esc(go)}"><span class="sig-ep-id"><span class="d-proto ${p.cls} sig-proto">${p.tag}</span><span class="sig-ep-name">${_esc(ep.name)}</span>${_sdEpGlyphs(ep, info)}</span><span class="sig-ep-addr">${_esc(ep.address || '')}</span><span class="sig-ep-strip">${_sdStrip(info.cells, aria, 'sig-strip-xs')}</span><span class="sig-ep-n${info.blind || info.n === 0 ? ' sig-ep-n0' : ''}" title="${info.blind ? th('Router list unavailable') : th('Routers bound, counted from router.using[]')}">${info.blind ? '-' : _sdNum(info.n)}</span><span class="sig-ep-flags">${flagHtml}</span><span class="sig-ep-sub">${facts.length ? facts.map(_esc).join(SD_SEP) : th('no extra configuration')}</span><span class="sig-ep-kind">${_esc(_sdEpKind(ep, info))}</span></div>`;
}

function _sdGo(spec) {
    const p = {};
    String(spec || '').split(';').forEach(kv => {
        const i = kv.indexOf('=');
        if (i > 0) p[kv.slice(0, i)] = kv.slice(i + 1);
    });
    if (Object.prototype.hasOwnProperty.call(p, 'scope')) {
        _sdScope = (!p.scope || _sdScope === p.scope) ? null : p.scope;
        if (_sdModel) _sdRender(_sdModel);
        return;
    }
    if (p.tab && typeof switchTab === 'function') switchTab(p.tab);
    if (p.proto && typeof filterProto === 'function') filterProto(p.proto);
    if (p.apistatus && typeof filterApiStatus === 'function') filterApiStatus(p.apistatus);
    if (p.ep && typeof filterRouteEntryPoint === 'function') filterRouteEntryPoint(p.ep);
    if (p.svcstatus && typeof pickLiveStatus === 'function') {
        const labels = { all: t('All Status'), success: 'Success', warning: t('Warnings'), error: 'Errors' };
        pickLiveStatus(p.svcstatus, labels[p.svcstatus] || t('All Status'), true);
    }
    if (p.provider && typeof pickLiveProvider === 'function') pickLiveProvider(p.provider, p.provider, true);
}

function _sdBind() {
    if (_sdBound) return;
    _sdBound = true;
    const inRoot = el => {
        const r = document.getElementById('overviewSection');
        return !!(r && el && r.contains(el));
    };
    document.addEventListener('click', e => {
        const el = e.target.closest && e.target.closest('[data-sd]');
        if (!el || !inRoot(el)) return;
        e.preventDefault();
        _sdGo(el.getAttribute('data-sd'));
    });
    document.addEventListener('keydown', e => {
        if (e.key !== 'Enter' && e.key !== ' ') return;
        const el = e.target.closest && e.target.closest('.sig-ep-row[data-sd]');
        if (!el || !inRoot(el)) return;
        e.preventDefault();
        _sdGo(el.getAttribute('data-sd'));
    });
}

function _sdTickAge() {
    clearInterval(_sdAgeTimer);
    _sdAgeTimer = setInterval(() => {
        const el = document.getElementById('sigAge');
        if (!el) { clearInterval(_sdAgeTimer); _sdAgeTimer = null; return; }
        el.textContent = _sdAgo(_sdStamp);
    }, 15000);
}

function _sdBuild(data) {
    const routers  = data.routers || {};
    const services = data.services || {};
    const mws      = data.middlewares || {};
    const avail    = {
        http:       !!data.routers,
        stream:     !!data.routers,
        service:    !!data.services,
        middleware: !!data.middlewares,
    };

    const httpR = _sdList(routers.http);
    const tcpR  = _sdList(routers.tcp);
    const udpR  = _sdList(routers.udp);
    const httpS = _sdList(services.http);
    const tcpS  = _sdList(services.tcp);
    const udpS  = _sdList(services.udp);
    const httpM = _sdList(mws.http);
    const tcpM  = _sdList(mws.tcp);
    const eps   = _sdList(data.entrypoints).filter(ep => ep && ep.name);

    const refFull = new Set();
    const refShort = new Map();
    const addRef = (ref, provider) => {
        const s = String(ref || '').trim();
        if (!s) return;
        if (s.indexOf('@') !== -1) { refFull.add(s.toLowerCase()); return; }
        let set = refShort.get(provider);
        if (!set) { set = new Set(); refShort.set(provider, set); }
        set.add(s);
    };
    [httpR, tcpR, udpR].forEach(arr => arr.forEach(r => {
        _sdList(r.middlewares).forEach(m => addRef(m, _sdProvider(r)));
    }));
    [httpM, tcpM].forEach(arr => arr.forEach(m => {
        _sdList(m && m.chain && m.chain.middlewares).forEach(x => addRef(x, _sdProvider(m)));
    }));
    eps.forEach(ep => _sdList(ep.http && ep.http.middlewares).forEach(m => addRef(m, 'file')));
    const ctx = { refFull: refFull, refShort: refShort };

    const pairs = [];
    const mk = (arr, kind, proto) => arr.map(raw => {
        const obj = _sdObj(raw, kind, ctx);
        obj.proto = proto;
        pairs.push({ raw: raw, obj: obj });
        return obj;
    });

    const objs = {
        http:   mk(httpR, 'http', 'http'),
        stream: mk(tcpR, 'stream', 'tcp').concat(mk(udpR, 'stream', 'udp')),
        service: httpS.map(s => _sdObj(s, 'service', ctx))
            .concat(tcpS.map(s => _sdObj(s, 'service', ctx)))
            .concat(udpS.map(s => _sdObj(s, 'service', ctx))),
        middleware: httpM.map(m => _sdObj(m, 'middleware', ctx))
            .concat(tcpM.map(m => _sdObj(m, 'middleware', ctx))),
    };

    return {
        objs: objs,
        pairs: pairs,
        avail: avail,
        counts: { httpSvc: httpS.length, allSvc: httpS.length + tcpS.length + udpS.length },
        entrypoints: eps,
        overview: _sdOverview(data.overview),
        version: (data.version && !data.version.error) ? data.version : null,
        reachable: !!(data.version || data.overview || data.routers || data.services || data.middlewares),
    };
}

function _sdScoped(objs) {
    return _sdScope ? objs.filter(o => o.provider === _sdScope) : objs;
}

function _sdCardModel(key, objs, ov, avail) {
    const t     = _sdTally(objs);
    const provs = _sdProvStats(objs);
    const cells = _sdCells(objs);
    const groups = {
        disabled: objs.filter(o => o.status === 'disabled'),
        warning:  objs.filter(o => o.status === 'warning'),
        unknown:  objs.filter(o => o.status === 'unknown'),
        unbound:  objs.filter(o => o.unbound),
        down:     objs.filter(o => o.down),
        unused:   objs.filter(o => o.unused),
        degraded: objs.filter(o => o.degraded),
        composite: objs.filter(o => o.composite),
    };
    let total = objs.length;
    let truncated = 0;
    if (!_sdScope && ov) {
        if (ov.total !== null && ov.total > total) { truncated = ov.total - total; total = ov.total; }
        if (ov.errors   !== null && ov.errors   > t.disabled) t.disabled = ov.errors;
        if (ov.warnings !== null && ov.warnings > t.warning)  t.warning  = ov.warnings;
    }
    const listed = !!avail;
    const known = listed || !!(ov && ov.total !== null);
    if (!known) total = null;
    return { key: key, objs: objs, t: t, provs: provs, cells: cells, groups: groups,
             total: total, truncated: truncated, known: known, listed: listed };
}

function _sdBackendRoll(objs) {
    return _sdList(objs).reduce((a, o) => {
        if (o.backends) {
            a.total += o.backends.total;
            a.up    += o.backends.up;
            a.down  += o.backends.down;
            a.checked++;
        } else if (o.composite) {
            a.composite++;
        }
        return a;
    }, { total: 0, up: 0, down: 0, checked: 0, composite: 0 });
}

function _sdBackendTxt(b, total) {
    const bits = [];
    if (b.checked) {
        bits.push(b.down === 0 ? t('{up} of {total} backends up', { up: _sdNum(b.up), total: _sdNum(b.total) })
                               : t('{down} of {total} backends down', { down: _sdNum(b.down), total: _sdNum(b.total) }));
    }
    if (b.composite) bits.push(t('{count} composite', { count: _sdNum(b.composite) }));
    if (bits.length) return bits.join(SD_SEP);
    return total ? t('no health checks configured') : '';
}

function _sdShowSkeleton() {
    const panel = document.getElementById('statsPanel');
    if (panel && _sdSkeletonHtml !== null) panel.innerHTML = _sdSkeletonHtml;
}

window._sdServerChanged = function() {
    _rhMap = {};
    _rhMeta.loaded = false;
    _rhMeta.checked_at = null;
    _sdApiStatusMap = null;
    _sdModel = null;
    _sdScope = null;
    const cached = tabCacheGet('stats');
    if (cached && cached.overview !== undefined) _sdApplyPayloads(cached);
    else _sdShowSkeleton();
};

function _sdRender(model) {
    _sdBind();
    const panel = document.getElementById('statsPanel');
    if (_sdSkeletonHtml === null && panel) _sdSkeletonHtml = panel.innerHTML;
    const gridEl = document.getElementById('statsGrid');
    const verdEl = document.getElementById('sigVerdict');
    const keyEl  = document.getElementById('sigKey');
    const rtEl   = document.getElementById('sigRuntime');
    const barEl  = document.getElementById('entrypointsBar');
    const ov     = model.overview;

    const av = model.avail || {};
    _sdApplyHealth(model.objs.http);
    const m = {
        http:       _sdCardModel('http',       _sdScoped(model.objs.http),       _sdSumSections([ov.routersHttp]), av.http),
        stream:     _sdCardModel('stream',     _sdScoped(model.objs.stream),     _sdSumSections([ov.routersTcp, ov.routersUdp]), av.stream),
        service:    _sdCardModel('service',    _sdScoped(model.objs.service),    _sdSumSections([ov.svcHttp, ov.svcTcp, ov.svcUdp]), av.service),
        middleware: _sdCardModel('middleware', _sdScoped(model.objs.middleware), _sdSumSections([ov.mwHttp, ov.mwTcp]), av.middleware),
    };
    const blind    = ['http', 'stream', 'service', 'middleware'].filter(k => !m[k].known);
    const unlisted = ['http', 'stream', 'service', 'middleware'].filter(k => !m[k].listed);

    const emptyTxt = k => _sdScope
        ? t('no {label} from provider {sdScope}', { label: SD_CARD_META[k].label, sdScope: _sdScope })
        : t('no {label} configured', { label: SD_CARD_META[k].label });

    const cards = [];
    const h = m.http;
    const hGo = 'tab=services;proto=http';
    cards.push({
        key: 'http', total: h.total, health: _sdHealth(h.t), cells: h.cells, provs: h.provs,
        aria: _sdAria(t('HTTP routers'), h.total, h.t),
        explore: hGo, exploreLabel: tc('button', 'Explore'),
        sub: h.total === 0 ? _sdSubPlain(emptyTxt('http')) : _sdSubOffender(h.objs,
            (h.truncated ? th('{ok} live of {count} listed', { ok: _sdNum(h.t.ok), count: _sdNum(h.objs.length) }) : th('{ok} live', { ok: _sdNum(h.t.ok) }))
            + (h.t.unbound ? SD_SEP + th('{count} unbound', { count: _sdNum(h.t.unbound) }) : '')),
        flags: [
            h.t.disabled && _sdExc('d-bad',  'ph-fill ph-x-circle', h.t.disabled, tc('label', 'disabled'),   hGo + ';apistatus=disabled', h.groups.disabled),
            h.t.down     && _sdExc('d-bad',  'ph-fill ph-warning-octagon', h.t.down, tc('label', 'unreachable'), hGo + ';apistatus=unreachable', h.groups.down),
            h.t.degraded && _sdExc('d-warn', 'ph-fill ph-warning-diamond', h.t.degraded, tc('label', 'degraded'), hGo + ';apistatus=degraded', h.groups.degraded),
            h.t.warning  && _sdExc('d-warn', 'ph-fill ph-warning',  h.t.warning,  tc('label', 'warnings'),   hGo + ';apistatus=warning',  h.groups.warning),
            h.t.unbound  && _sdExc('d-off',  'ph-bold ph-plug',     h.t.unbound,  tc('label', 'unbound'),    hGo + ';apistatus=unbound',  h.groups.unbound),
            h.t.unknown  && _sdExc('d-off',  'ph-bold ph-question', h.t.unknown,  tc('label', 'unreported'), hGo,                         h.groups.unknown),
        ].filter(Boolean),
    });

    const s = m.stream;
    const tcpN = s.objs.filter(o => o.proto === 'tcp').length;
    const udpN = s.objs.filter(o => o.proto === 'udp').length;
    const streamProto = (tcpN === 0 && udpN > 0) ? 'udp' : 'tcp';
    const sGo = 'tab=services;proto=' + streamProto;
    cards.push({
        key: 'stream', total: s.total, health: _sdHealth(s.t), cells: s.cells, provs: s.provs,
        aria: _sdAria(t('stream routers'), s.total, s.t),
        explore: sGo, exploreLabel: tc('button', 'Explore {protocol}', { protocol: streamProto.toUpperCase() }),
        sub: s.total === 0 ? _sdSubPlain(emptyTxt('stream')) : _sdSubOffender(s.objs,
            '<span class="d-proto d-proto-tcp">TCP</span> ' + _sdNum(tcpN) + SD_SEP
          + '<span class="d-proto d-proto-udp">UDP</span> ' + _sdNum(udpN)
          + (s.t.ok === s.total ? SD_SEP + th('all forwarding') : '')),
        flags: [
            s.t.disabled && _sdExc('d-bad',  'ph-fill ph-x-circle', s.t.disabled, tc('label', 'disabled'), sGo + ';apistatus=disabled', s.groups.disabled),
            s.t.warning  && _sdExc('d-warn', 'ph-fill ph-warning',  s.t.warning,  tc('label', 'warnings'), sGo + ';apistatus=warning',  s.groups.warning),
            s.t.unbound  && _sdExc('d-off',  'ph-bold ph-plug',     s.t.unbound,  tc('label', 'unbound'),  sGo + ';apistatus=unbound',  s.groups.unbound),
        ].filter(Boolean),
    });

    const v = m.service;
    const b = _sdBackendRoll(v.objs);
    const backendTxt = _sdBackendTxt(b, v.total);
    cards.push({
        key: 'service', total: v.total, health: _sdHealth(v.t), cells: v.cells, provs: v.provs,
        aria: _sdAria(t('services'), v.total, v.t),
        explore: 'tab=live', exploreLabel: tc('button', 'Explore'),
        sub: v.total === 0 ? _sdSubPlain(emptyTxt('service')) : _sdSubOffender(v.objs, backendTxt),
        flags: [
            v.t.disabled && _sdExc('d-bad',  'ph-fill ph-x-circle',            v.t.disabled, tc('label', 'disabled'),      'tab=live;svcstatus=error',   v.groups.disabled),
            v.t.down     && _sdExc('d-bad',  'ph-fill ph-arrow-fat-line-down', v.t.down,     tc('label', 'down'),          'tab=live;svcstatus=error',   v.groups.down),
            v.t.degraded && _sdExc('d-warn', 'ph-fill ph-warning-diamond',     v.t.degraded, tc('label', 'degraded'),      'tab=live;svcstatus=warning', v.groups.degraded),
            v.t.warning  && _sdExc('d-warn', 'ph-fill ph-warning',             v.t.warning,  tc('label', 'warnings'),      'tab=live;svcstatus=warning', v.groups.warning),
            v.t.composite && _sdExc('d-off', 'ph-bold ph-share-network',        v.t.composite, tc('label', 'composite'),    'tab=live',                   v.groups.composite),
        ].filter(Boolean),
    });

    const w = m.middleware;
    cards.push({
        key: 'middleware', total: w.total, health: _sdHealth(w.t), cells: w.cells, provs: w.provs,
        aria: _sdAria(t('middlewares'), w.total, w.t),
        explore: 'tab=middlewares', exploreLabel: tc('button', 'Explore'),
        sub: w.total === 0 ? _sdSubPlain(emptyTxt('middleware')) : _sdSubOffender(w.objs,
            th('{max} in use', { max: _sdNum(Math.max(0, w.total - w.t.unused)) }) + (w.t.unused ? SD_SEP + th('{count} unused', { count: _sdNum(w.t.unused) }) : '')),
        flags: [
            w.t.disabled && _sdExc('d-bad',  'ph-fill ph-x-circle',   w.t.disabled, tc('label', 'disabled'), 'tab=middlewares', w.groups.disabled),
            w.t.warning  && _sdExc('d-warn', 'ph-fill ph-warning',    w.t.warning,  tc('label', 'warnings'), 'tab=middlewares', w.groups.warning),
            w.t.unused   && _sdExc('d-off',  'ph-bold ph-link-break', w.t.unused,   tc('label', 'unused'),   'tab=middlewares', w.groups.unused),
        ].filter(Boolean),
    });

    cards.forEach(c => {
        c.subFull = c.sub.full;
        c.sub = c.sub.html;
        c.provNote = c.total === 0 ? emptyTxt(c.key) : t('no provider data');
    });

    cards.forEach(c => {
        const cm = m[c.key];
        if (cm.listed) return;
        c.provs = [];
        c.cells = { err: [], warn: [], idle: [], ok: 0, blind: true };
        if (cm.known) {
            c.provNote = t('provider breakdown needs the object list');
            c.sub = t('total from /api/overview, the {label} list is unavailable', { label: SD_CARD_META[c.key].label });
            c.subFull = c.sub;
            c.aria = t('{total} {label} reported by /api/overview, the object list could not be read', { total: _sdNum(c.total), label: SD_CARD_META[c.key].label });
            return;
        }
        c.total = null;
        c.health = 'warn';
        c.flags = [];
        c.provNote = t('no provider data');
        c.sub = t('Traefik API unreachable');
        c.subFull = c.sub;
        c.aria = t('{label} could not be read from the Traefik API', { label: SD_CARD_META[c.key].label });
    });

    if (gridEl) gridEl.innerHTML = cards.map(_sdCard).join('');

    const total4 = ['http', 'stream', 'service', 'middleware']
        .reduce((a, k) => a + (m[k].total || 0), 0);

    if (verdEl) {
        const items = [];
        if (m.http.t.disabled)       items.push(_sdExc('d-bad',  'ph-fill ph-x-circle',            m.http.t.disabled,       tn('router disabled', 'routers disabled', m.http.t.disabled),     'tab=services;proto=http;apistatus=disabled', m.http.groups.disabled));
        if (m.http.t.down)           items.push(_sdExc('d-bad',  'ph-fill ph-warning-octagon',     m.http.t.down,           tn('route unreachable', 'routes unreachable', m.http.t.down), 'tab=services;proto=http;apistatus=unreachable', m.http.groups.down));
        if (m.http.t.degraded)       items.push(_sdExc('d-warn', 'ph-fill ph-warning-diamond',     m.http.t.degraded,       tn('route degraded', 'routes degraded', m.http.t.degraded),    'tab=services;proto=http;apistatus=degraded', m.http.groups.degraded));
        if (m.http.t.warning)        items.push(_sdExc('d-warn', 'ph-fill ph-warning',             m.http.t.warning,        tn('router warning', 'router warnings', m.http.t.warning),      'tab=services;proto=http;apistatus=warning',  m.http.groups.warning));
        if (m.stream.t.disabled)     items.push(_sdExc('d-bad',  'ph-fill ph-x-circle',            m.stream.t.disabled,     t('stream disabled'),      sGo + ';apistatus=disabled',                  m.stream.groups.disabled));
        if (m.service.t.disabled)    items.push(_sdExc('d-bad',  'ph-fill ph-x-circle',            m.service.t.disabled,    tn('service disabled', 'services disabled', m.service.t.disabled),    'tab=live;svcstatus=error',                   m.service.groups.disabled));
        if (m.service.t.down)        items.push(_sdExc('d-bad',  'ph-fill ph-arrow-fat-line-down', m.service.t.down,        tn('service down', 'services down', m.service.t.down),        'tab=live;svcstatus=error',                   m.service.groups.down));
        if (m.service.t.degraded)    items.push(_sdExc('d-warn', 'ph-fill ph-warning-diamond',     m.service.t.degraded,    tn('service degraded', 'services degraded', m.service.t.degraded),    'tab=live;svcstatus=warning',                 m.service.groups.degraded));
        if (m.service.t.warning)     items.push(_sdExc('d-warn', 'ph-fill ph-warning',             m.service.t.warning,     tn('service warning', 'service warnings', m.service.t.warning),     'tab=live;svcstatus=warning',                 m.service.groups.warning));
        if (m.middleware.t.disabled) items.push(_sdExc('d-bad',  'ph-fill ph-x-circle',            m.middleware.t.disabled, tn('middleware disabled', 'middlewares disabled', m.middleware.t.disabled), 'tab=middlewares',                            m.middleware.groups.disabled));

        const issues = items.reduce((a, x) => a + x.n, 0);
        const offenders = new Set();
        ['http', 'stream', 'service', 'middleware'].forEach(k => {
            m[k].provs.forEach(p => { if (p.bad || p.warn) offenders.add(p.p); });
        });
        const names = [...offenders].sort();
        let where = '';
        if (names.length === 1)      where = `${th('all inside {b}', { b: tmHtml(`<b>${_esc(names[0])}</b>`) })}`;
        else if (names.length === 2) where = `${th('all inside {b} and {b2}', { b: tmHtml(`<b>${_esc(names[0])}</b>`), b2: tmHtml(`<b>${_esc(names[1])}</b>`) })}`;
        else if (names.length > 2)   where = t('across {names_count} providers', { names_count: names.length });
        else if (b.total > 0)        where = t('{up} of {total} backends up', { up: _sdNum(b.up), total: _sdNum(b.total) });
        else if (total4 > 0)         where = th('{count} objects', { count: _sdNum(total4) });

        const shown = items.slice(0, 4);
        const rest  = items.length - shown.length;
        const dead  = blind.length === 4;
        const off   = unlisted.length ? unlisted : blind;
        let txt, quiet;
        if (dead) {
            txt = model.reachable ? t('Traefik API not answering') : t('Traefik API unreachable');
            quiet = t('Could not read routers, services or middlewares. Check TRAEFIK_API_URL and that api.insecure or an api@internal route is enabled.');
        } else if (off.length) {
            const labels = off.map(k => SD_CARD_META[k].label);
            const last = labels.pop();
            txt = issues ? tn('{count} issue', '{count} issues', issues, { count: _sdNum(issues) }) : t('Partial data');
            quiet = t('No object list for {objects}, so the strips and provider counts are incomplete', { objects: labels.length ? t('{items} and {last}', { items: labels.join(', '), last }) : last });
        } else if (issues) {
            txt = tn('{count} issue', '{count} issues', issues, { count: _sdNum(issues) });
            quiet = '';
        } else if (total4 === 0) {
            txt = _sdScope ? t('Nothing from {sdScope}', { sdScope: _sdScope }) : t('Nothing configured');
            quiet = _sdScope ? t('no routers, services or middlewares come from provider {sdScope}', { sdScope: _sdScope })
                             : t('Traefik is running with an empty dynamic configuration');
        } else {
            txt = t('All healthy');
            quiet = t('no errors or warnings reported');
        }
        verdEl.className = 'sig-verdict';
        verdEl.setAttribute('data-health', (issues || off.length) ? 'down' : 'up');
        verdEl.innerHTML =
            `<i class="ph-fill ${issues || off.length ? 'ph-warning-octagon' : 'ph-check-circle'} sig-verdict-ic"></i><span class="sig-verdict-txt">${_esc(txt)}</span><span class="sig-verdict-items">${shown.length ? shown.map(f => _sdFlag(f)).join('')
                            + (rest > 0 ? '<span class="sig-mono">+' + rest + ` ${thc('label', 'more')}</span>` : '') : ''}${quiet ? '<span class="sig-mono">' + _esc(quiet) + '</span>' : ''}</span><span class="sig-verdict-meta">${!dead && where ? where + SD_SEP : ''}<b id="sigAge">${_sdAgo(_sdStamp)}</b></span>`;
    }

    if (keyEl) {
        const key = new Map();
        ['http', 'stream', 'service', 'middleware'].forEach(k => {
            _sdProvStats(model.objs[k]).forEach(p => key.set(p.p, (key.get(p.p) || 0) + p.n));
        });
        if (unlisted.length < 4) ov.providers.forEach(p => { if (!key.has(p)) key.set(p, 0); });
        const list = [...key.entries()].map(x => ({ p: x[0], n: x[1] }))
                                       .sort((a, c) => c.n - a.n || a.p.localeCompare(c.p));
        const truncated = ['http', 'stream', 'service', 'middleware'].reduce((a, k) => a + m[k].truncated, 0);
        const caveats = [];
        if (_sdScope) caveats.push(t('Every card is scoped to provider {sdScope}. Click to clear.', { sdScope: _sdScope }));
        if (truncated > 0) caveats.push(t('{truncated} objects are counted in the totals but were not returned by the list endpoint, so they are missing from the strips and provider counts.', { truncated: _sdNum(truncated) }));
        if (unlisted.length) caveats.push(t('These counts only cover the object lists that could be read.'));
        keyEl.className = 'sig-key';
        keyEl.innerHTML = `<span class="sig-key-lab">${thc('label', 'providers')}</span>${list.map(k => {
                const meta = _sdProvMeta(k.p);
                const glyph = '<i class="ph-bold ' + meta.g + '"></i>' + _esc(k.p) + '<b>' + _sdNum(k.n) + '</b>';
                if (!k.n) {
                    return '<span class="sig-key-item sig-key-empty" title="'
                         + _esc(t('{p} is loaded by Traefik but owns no routers, services or middlewares', { p: k.p }))
                         + '">' + glyph + '</span>';
                }
                const on = _sdScope === k.p;
                return '<button type="button" class="sig-key-item' + (on ? ' sig-key-on' : '') + '"'
                     + ' data-sd="scope=' + _esc(k.p) + '"'
                     + ' title="' + _esc(on ? t('Clear the {p} scope', { p: k.p }) : t('Scope every card to {p}', { p: k.p })) + '">'
                     + glyph + '</button>';
            }).join('')}${caveats.length ? '<span class="sig-key-scope" data-sd="scope=" title="' + _esc(caveats.join(' ')) + '">'
                  + '<i class="ph-bold ph-funnel"></i>' + (_sdScope ? _esc(_sdScope) : th('partial')) + '</span>' : ''}`;
    }

    if (barEl) {
        const eps = model.entrypoints;
        if (eps.length) {
            const epBlind = !av.http;
            const info = new Map();
            eps.forEach(ep => info.set(ep.name, {
                n: 0, err: 0, warn: 0, idle: 0, ok: 0, down: 0, degraded: 0, tls: false,
                httpN: 0, tcpN: 0, udpN: 0, blind: epBlind, objs: [],
                cells: { err: [], warn: [], idle: [], ok: 0, blind: epBlind },
                providers: new Set(), internalOnly: false,
            }));
            model.pairs.forEach(pair => {
                const o = pair.obj;
                _sdUsing(pair.raw).forEach(name => {
                    const i = info.get(name);
                    if (!i) return;
                    i.n++;
                    if (o.proto === 'tcp') i.tcpN++;
                    else if (o.proto === 'udp') i.udpN++;
                    else i.httpN++;
                    if (pair.raw && pair.raw.tls) i.tls = true;
                    i.providers.add(o.provider);
                    i.objs.push(o);
                    if (o.down) i.down++;
                    if (o.degraded) i.degraded++;
                    if (o.cell === 'ok') { i.ok++; i.cells.ok++; }
                    else { i[o.cell]++; i.cells[o.cell].push((o.name || o.short) + ': ' + (o.reason || o.cell)); }
                });
            });
            let httpN = 0, strN = 0, idleN = 0;
            eps.forEach(ep => {
                const i = info.get(ep.name);
                i.internalOnly = i.n > 0 && i.providers.size === 1 && i.providers.has('internal');
                if (_sdEpProto(ep, i).key === 'http') httpN += i.n; else strN += i.n;
                if (!i.blind && i.n === 0) idleN++;
            });
            const summary = epBlind ? t('router list unavailable') : [
                t('{count} HTTP', { count: _sdNum(httpN) }),
                strN  ? t('{count} stream', { count: _sdNum(strN) }) : '',
                idleN ? t('{count} idle', { count: _sdNum(idleN) }) : '',
            ].filter(Boolean).join(' · ');
            barEl.innerHTML = `<div class="sig-ep-head"><i class="ph-fill ph-door-open sig-ep-headic"></i><span class="sc-sec-label">${th('Entry Points')}</span><span class="d-n">${eps.length}</span><span class="sc-sec-rule"></span><span class="sig-ep-tot">${_esc(summary)}</span></div><div class="sig-ep-rows" id="entrypointsList">${eps.map(ep => _sdEpRow(ep, info.get(ep.name))).join('')}</div>`;
        } else {
            barEl.innerHTML = '';
        }
        if (typeof _applyEntrypointsVisibility === 'function') _applyEntrypointsVisibility();
    }

    if (rtEl) {
        const ver = model.version;
        const f = [];
        if (ver && ver.Version) f.push({ ic: 'ph-traffic-signal', t: 'v' + ver.Version + (ver.Codename ? ' ' + ver.Codename : '') });
        const up = ver && _sdUptime(ver.startDate);
        if (up) f.push({ ic: 'ph-clock-clockwise', t: up });
        const feat = ov.features;
        if (feat) {
            const met = (feat.metrics && String(feat.metrics).toLowerCase() !== 'false') ? String(feat.metrics) : '';
            const tra = (feat.tracing && String(feat.tracing).toLowerCase() !== 'false') ? String(feat.tracing) : '';
            f.push({ ic: 'ph-chart-line', t: met ? t('metrics {provider}', { provider: met }) : t('metrics off'), on: !!met, off: !met });
            f.push({ ic: 'ph-scroll',     t: feat.accessLog ? t('access log on') : t('access log off'), on: !!feat.accessLog, off: !feat.accessLog });
            f.push({ ic: 'ph-crosshair',  t: tra ? t('tracing {provider}', { provider: tra }) : t('tracing off'), on: !!tra, off: !tra });
        }
        rtEl.className = 'sig-runtime';
        rtEl.innerHTML = f.map(x => '<span class="sig-f ' + (x.on ? 'sig-f-on' : x.off ? 'sig-f-off' : '') + '">'
            + '<i class="ph-bold ' + x.ic + '"></i>' + _esc(x.t) + '</span>').join('');
    }

    _sdTickAge();
}

let _sdApiStatusMap = null;
let _sdSkeletonHtml = null;
let _rhMap  = {};
const _rhMeta = { enabled: true, interval: 300, checked_at: null, loaded: false };
window._rhMeta = _rhMeta;
window._rhGet  = function(rid) { return (rid && _rhMap[rid]) || null; };
window._rhByName = function(name) {
    if (!name) return null;
    if (_rhMap[name]) return _rhMap[name];
    const hit = Object.keys(_rhMap).find(rid => (rid.includes('::') ? rid.slice(rid.indexOf('::') + 2) : rid) === name);
    return hit ? _rhMap[hit] : null;
};

function _sdApplyHealth(objs) {
    (objs || []).forEach(o => {
        if (o.baseCell === undefined) { o.baseCell = o.cell; o.baseReason = o.reason; }
        o.cell = o.baseCell; o.reason = o.baseReason; o.down = false; o.degraded = false;
        if (o.status !== 'enabled' || o.baseCell !== 'ok') return;
        const h = window._rhByName(o.short);
        if (!h) return;
        const sv = h.servers || {};
        if (h.state === 'down') {
            o.cell = 'err'; o.down = true;
            o.reason = (h.source === 'traefik' || h.source === 'servers') ? t('backend down, 0 of {total} servers up', { total: sv.total })
                : (h.error ? t('backend unreachable, {error}', { error: h.error }) : t('backend unreachable'));
        } else if (h.state === 'degraded') {
            o.cell = 'warn'; o.degraded = true;
            o.reason = t('backend degraded, {up} of {total} servers up', { up: sv.up, total: sv.total });
        }
    });
}

function _rhIngest(data) {
    if (!data || typeof data !== 'object' || !data.routes) return;
    _rhMeta.enabled    = data.enabled !== false;
    _rhMeta.interval   = data.interval || 300;
    _rhMeta.checked_at = data.checked_at || null;
    _rhMeta.loaded     = true;
    const next = {};
    Object.keys(data.routes).forEach(rid => { next[rid] = data.routes[rid]; });
    Object.keys(_rhMap).forEach(rid => {
        const mine = _rhMap[rid], theirs = next[rid];
        if (mine && mine.manual && (!theirs || (mine.at || 0) > (theirs.at || 0))) next[rid] = mine;
    });
    _rhMap = next;
}

window._rhRemember = function(rid, res) {
    if (!rid || !res) return;
    _rhMap[rid] = { state: res.state || (res.ok ? 'up' : 'down'), source: res.source || 'ping', manual: true,
                    at: Math.floor(Date.now() / 1000), latency_ms: res.latency_ms,
                    status_code: res.status_code, error: res.error, via_target: res.via_target, self: res.self,
                    unverified: res.unverified, note: res.note,
                    servers: res.servers, down_servers: res.down_servers };
};

window._rhLoad = async function(server) {
    try {
        const r = await fetch('/api/routes/health' + (server ? '?agent_id=' + encodeURIComponent(server) : ''));
        if (r.ok) _rhIngest(await r.json());
    } catch (e) {}
};

window._rhPoll = async function() {
    await window._rhLoad((typeof _activeAgent !== 'undefined' && _activeAgent) ? _activeAgent.id : '');
    if (_sdModel) _sdRender(_sdModel);
    _sdApplyRouteCards();
    const pods = document.getElementById('dashPodsContainer');
    if (pods && !pods.classList.contains('hidden') && typeof dashRender === 'function') dashRender();
};

function _rhAgo(at) {
    if (!at) return '';
    const s = Math.max(0, Math.floor(Date.now() / 1000) - at);
    if (s < 60)   return t('just now');
    if (s < 3600) return t('{floor}m ago', { floor: Math.floor(s / 60) });
    return t('{floor}h ago', { floor: Math.floor(s / 3600) });
}

function _sdHealthDot(h, noHost) {
    if (h) {
        const when = h.manual ? t('pinged {ago}', { ago: _rhAgo(h.at) }) : t('checked {ago}', { ago: _rhAgo(h.at) });
        const sv   = h.servers || {};
        if (h.state === 'up') {
            const what = h.self ? t('Online (self)')
                : h.unverified ? (h.note ? t('Proxy answered {status_code}, backend not verified. {note}', { status_code: h.status_code, note: h.note }) : t('Proxy answered {status_code}, backend not verified', { status_code: h.status_code }))
                : (h.source === 'traefik' || h.source === 'servers') ? t('Backend up, {up} of {total} servers', { up: sv.up, total: sv.total })
                : h.via_target ? t('Backend online · {latency_ms}ms', { latency_ms: h.latency_ms })
                : t('Online · {latency_ms}ms ({status_code})', { latency_ms: h.latency_ms, status_code: h.status_code });
            return { cls: 'status-online', title: what + ' · ' + when };
        }
        if (h.state === 'degraded') {
            return { cls: 'status-checking', title: (h.down_servers || []).length
                ? t('Backend degraded, {up} of {total} servers up ({servers} down) · {when}', { up: sv.up, total: sv.total, servers: h.down_servers.join(', '), when })
                : t('Backend degraded, {up} of {total} servers up · {when}', { up: sv.up, total: sv.total, when }) };
        }
        if (h.state === 'down') {
            const why = (h.source === 'traefik' || h.source === 'servers') ? t('Backend down, 0 of {total} servers up', { total: sv.total })
                : (h.error ? t('Unreachable: {error}', { error: h.error }) : t('Unreachable'));
            return { cls: 'status-offline', title: why + ' · ' + when };
        }
        if (h.state === 'pending') {
            return { cls: 'status-checking', title: (h.error ? t('Last check failed: {error}, confirming on the next pass', { error: h.error }) : t('Last check failed, confirming on the next pass')) };
        }
    }
    if (_rhMeta.loaded && !_rhMeta.enabled) return { cls: 'status-unknown', title: t('Router loaded, route checks are off in Settings') };
    if (noHost) return { cls: 'status-unknown', title: t('Router loaded, the rule has no host to check. Set a link on the Dashboard and it will be checked') };
    return { cls: 'status-unknown', title: t('Router loaded, not checked yet') };
}

window._rhDot = _sdHealthDot;

function _sdApplyRouteCards() {
    if (!_sdApiStatusMap) return;
    const map = _sdApiStatusMap;
    document.querySelectorAll('.route-card').forEach(card => {
        const routeName = card.dataset.routekey || '';
        const statusEl = card.querySelector('.status-dot');
        const entry = map[routeName];
        const apiStatus = entry ? entry.status : null;
        const apiError  = (entry && entry.error.length) ? entry.error.join(' · ') : null;
        card.dataset.apistatus = apiStatus || 'unknown';
        card.dataset.apibound = (entry && entry.unbound) ? 'unbound' : '';
        if (entry) card.dataset.eps = entry.eps.join('|');
        const health = window._rhGet(card.dataset.rid) || window._rhGet(routeName);
        card.dataset.health = !health ? '' : health.state === 'down' ? 'unreachable' : health.state;
        if (!statusEl) return;
        if (apiStatus === 'disabled') {
            statusEl.className = 'status-dot status-offline';
            statusEl.title = apiError ? t('Error: {apiError}', { apiError }) : tc('tooltip', 'Disabled');
            if (apiError) {
                let errEl = card.querySelector('.card-error-msg');
                if (!errEl) {
                    errEl = document.createElement('div');
                    errEl.className = 'card-error-msg';
                    errEl.style.cssText = 'margin-top:8px;padding:6px 10px;border-radius:6px;font-size:11px;font-family:monospace;color:var(--red);background:color-mix(in srgb, var(--red) 8%, transparent);border:1px solid color-mix(in srgb, var(--red) 25%, transparent);word-break:break-word;line-height:1.4';
                    card.appendChild(errEl);
                }
                errEl.innerHTML = '<i class="ph-bold ph-warning-circle" style="font-size:11px;margin-right:4px"></i>' + _esc(apiError);
            }
        } else if (apiStatus === 'warning') {
            statusEl.className = 'status-dot status-checking';
            statusEl.title = apiError ? t('Warning: {apiError}', { apiError }) : tc('tooltip', 'Warning');
        } else if (apiStatus && apiStatus !== 'enabled') {
            statusEl.className = 'status-dot status-unknown';
            statusEl.title = t('Status: {entry}', { entry: entry && entry.raw || apiStatus });
        } else if (apiStatus === 'enabled' && card.dataset.protocol !== 'http') {
            statusEl.className = 'status-dot status-online';
            statusEl.title = t('Enabled, stream routes are not reachability checked');
        } else if (apiStatus === 'enabled' || health) {
            const hosts = (card.dataset.domains || '').split('|').filter(d => d && !d.includes('{') && !d.includes('*'));
            const d = _sdHealthDot(health, !hosts.length);
            statusEl.className = 'status-dot ' + d.cls;
            statusEl.title = d.title;
        } else {
            statusEl.className = 'status-dot status-unknown';
            statusEl.title = t('Status unknown (API unavailable)');
        }
    });
}

function _sdApplyPayloads(p) {
    if (p.version && p.version.Version) {
        _currentVersion = p.version.Version;
        document.getElementById('versionText').textContent = t('v{currentVersion}', { currentVersion: _currentVersion });
        const vtm = document.getElementById('versionTextMobile');
        if (vtm) vtm.textContent = t('v{currentVersion}', { currentVersion: _currentVersion });
        if (tmPref('showTraefikBadge')) {
            document.getElementById('versionBadge')?.classList.remove('hidden');
            document.getElementById('versionBadgeMobile')?.classList.remove('hidden');
            document.getElementById('versionBadgeMobile')?.classList.add('flex');
        }
    }

    const model = _sdBuild({
        overview:    p.overview || null,
        routers:     p.routers || null,
        services:    p.services || null,
        middlewares: p.middlewares || null,
        version:     p.version || null,
        entrypoints: Array.isArray(p.entrypoints) ? p.entrypoints : [],
    });

    if (_sdScope) {
        const known = new Set();
        ['http', 'stream', 'service', 'middleware'].forEach(k => model.objs[k].forEach(o => known.add(o.provider)));
        if (!known.has(_sdScope)) _sdScope = null;
    }

    _sdStamp = Date.now();
    _sdModel = model;
    _sdRender(model);

    setTabCount('docker', model.pairs.filter(p => p.obj.provider === 'docker').length || '-');
    if (model.avail.service) setTabCount('live', model.counts.allSvc);

    _sdApiStatusMap = {};
    model.pairs.forEach(pair => {
        _sdApiStatusMap[pair.obj.short] = {
            status: pair.obj.status,
            raw: pair.obj.rawStatus,
            error: pair.obj.errors,
            unbound: !!pair.obj.unbound,
            eps: _sdUsing(pair.raw),
        };
    });
    _sdApplyRouteCards();
    if (typeof filterRoutes === 'function' && document.getElementById('searchRoutes')) filterRoutes();
    return model;
}

async function loadOverviewStats() {
    const runServer = _activeAgent ? _activeAgent.id : '';
    try {
        const [overview, routers, services, middlewares, version, entrypoints, health] = await Promise.allSettled([
            agentFetch('/api/traefik/overview').then(r => r.json()),
            agentFetch('/api/traefik/routers').then(r => r.json()),
            agentFetch('/api/traefik/services').then(r => r.json()),
            agentFetch('/api/traefik/middlewares').then(r => r.json()),
            agentFetch('/api/traefik/version').then(r => r.json()),
            agentFetch('/api/traefik/entrypoints').then(r => r.json()),
            fetch('/api/routes/health' + (runServer ? '?agent_id=' + encodeURIComponent(runServer) : '')).then(r => r.json()),
        ]);
        if (runServer !== (_activeAgent ? _activeAgent.id : '')) return;
        if (health.status === 'fulfilled') _rhIngest(health.value);

        const val = (res, fallback) => {
            if (res.status !== 'fulfilled') return fallback;
            const v = res.value;
            if (!v || typeof v !== 'object' || v.error) return fallback;
            return v;
        };

        const payloads = {
            overview:    val(overview, null),
            routers:     val(routers, null),
            services:    val(services, null),
            middlewares: val(middlewares, null),
            version:     val(version, null),
            entrypoints: (entrypoints.status === 'fulfilled' && Array.isArray(entrypoints.value)) ? entrypoints.value : [],
        };
        const apiUp = !!(payloads.version && payloads.version.Version);
        const dotColor = apiUp ? 'var(--green)' : 'var(--red)';
        const dotEl  = document.getElementById('apiStatusDot');
        const dotElM = document.getElementById('apiStatusDotMobile');
        if (dotEl)  dotEl.style.background  = dotColor;
        if (dotElM) dotElM.style.background = dotColor;
        if (apiUp) {
            checkForUpdate(payloads.version.Version);
            checkTraefikAdvisories(payloads.version.Version);
        }

        tabCachePut('stats', payloads);
        const model = _sdApplyPayloads(payloads);

        if (model.entrypoints.length && !_activeAgent) {
            const epNames = model.entrypoints.map(e => e.name);
            try {
                const srRes = await fetch('/api/settings/self-route');
                const sr = await srRes.json();
                if (!_activeAgent && sr.domain && sr.entry_point && !epNames.includes(sr.entry_point)) {
                    _showSelfRouteEpWarning(sr.entry_point, sr.default_entry_point || epNames[0]);
                }
            } catch (e) {}
        }

    } catch (e) {
        console.warn('Traefik API unavailable:', e);
    }

    agentFetch('/api/traefik/certs').then(r => r.json()).then(res => {
        const n = (res.certs || []).length;
        setTabCount('certs', n || '-');
    }).catch(() => {});

    agentFetch('/api/traefik/plugins').then(r => r.json()).then(res => {
        const n = (res.plugins || []).length;
        setTabCount('plugins', n || '-');
    }).catch(() => {});
}

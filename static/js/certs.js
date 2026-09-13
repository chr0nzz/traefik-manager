let _allCerts   = [];
let _certUsage  = { certs: [], unused_known: false, why: '', resolvers_known: false };

function _certKey(c) { return (c.source || '') + '|' + (c.resolver || '') + '|' + (c.main || ''); }

function _certVerdict(c) {
    return _certUsage.certs.find(u => _certKey(u) === _certKey(c)) || null;
}

let _certFilter = 'all';

function filterCertsBy(kind) {
    _certFilter = kind || 'all';
    ['all', 'unused', 'orphaned', 'expiring'].forEach(k => {
        document.getElementById('certf-' + k)?.classList.toggle('active-http', k === _certFilter);
    });
    renderCertCards();
}

function filterCerts() { renderCertCards(); }

function _certBaseDomain(name) {
    const parts = String(name || '').replace(/^\*\./, '').toLowerCase().split('.').filter(Boolean);
    return parts.length <= 2 ? parts.join('.') : parts.slice(-2).join('.');
}

function _certDomains(cert) {
    return [cert.main, ...(cert.sans || [])].filter(Boolean);
}

function _paintCertDomainFilter() {
    const sel = document.getElementById('certDomainFilter');
    if (!sel) return;
    const seen = new Map();
    _allCerts.forEach(c => _certDomains(c).forEach(d => {
        const base = _certBaseDomain(d);
        if (base) seen.set(base, (seen.get(base) || 0) + 1);
    }));
    const names = [...seen.keys()].sort();
    const keep  = names.includes(sel.value) ? sel.value : '';
    sel.innerHTML = '<option value="">All domains</option>'
        + names.map(n => `<option value="${_esc(n)}">${_esc(n)}</option>`).join('');
    sel.value = keep;
    sel.style.display = names.length > 1 ? '' : 'none';
}

function _certMatchesFilter(cert) {
    const v = _certVerdict(cert) || {};
    if (_certFilter === 'unused')   return !!v.unused;
    if (_certFilter === 'orphaned') return !!v.orphaned;
    if (_certFilter === 'expiring') {
        if (!cert.not_after) return false;
        const exp = new Date(cert.not_after);
        if (isNaN(exp)) return false;
        return Math.ceil((exp - Date.now()) / 86400000) < 30;
    }
    return true;
}


function renderCertsVerdict() {
    if (!document.getElementById('certsVerdict')) return;
    if (!_allCerts.length) { _tvStrip('certsVerdict', null); return; }
    const now = Date.now();
    let critical = 0, expiring = 0, expired = 0, next = null;
    _allCerts.forEach(c => {
        if (!c.not_after) return;
        const exp = new Date(c.not_after);
        if (isNaN(exp)) return;
        const d = Math.ceil((exp - now) / 86400000);
        if (d < 0) { expired++; return; }
        if (d < 7) critical++;
        else if (d < 30) expiring++;
        if (next === null || d < next) next = d;
    });
    const resolvers = new Set(_allCerts.map(c => c.resolver).filter(Boolean)).size;
    const flags = [{ cls: 'd-off', ic: 'ph-bold ph-shield-check', n: _allCerts.length,
                     label: _allCerts.length === 1 ? 'certificate' : 'certificates' }];
    if (expired)  flags.push({ cls: 'd-bad', ic: 'ph-fill ph-x-circle', n: expired, label: 'expired' });
    if (critical) flags.push({ cls: 'd-bad', ic: 'ph-fill ph-warning-octagon', n: critical, label: 'under 7d' });
    if (expiring) flags.push({ cls: 'd-warn', ic: 'ph-fill ph-hourglass-high', n: expiring, label: 'under 30d' });
    if (!expired && !critical && !expiring) flags.push({ cls: 'd-on', ic: 'ph-bold ph-check', n: '', label: 'none expiring soon' });
    if (resolvers > 1) flags.push({ cls: 'd-off', ic: 'ph-bold ph-certificate', n: resolvers, label: 'resolvers' });
    const unused   = _certUsage.certs.filter(u => u.unused).length;
    const orphaned = _certUsage.certs.filter(u => u.orphaned).length;
    if (unused)   flags.push({ cls: 'd-warn', ic: 'ph-bold ph-plugs', n: unused, label: 'unused' });
    if (orphaned) flags.push({ cls: 'd-warn', ic: 'ph-bold ph-link-break', n: orphaned, label: 'no resolver' });
    _tvStrip('certsVerdict', {
        health: (expired || critical) ? 'down' : expiring ? 'warn' : 'up',
        ic: (expired || critical) ? 'ph-fill ph-warning-octagon' : expiring ? 'ph-fill ph-hourglass-high' : 'ph-fill ph-check-circle',
        txt: expired  ? _sdNum(expired) + (expired === 1 ? ' certificate has expired' : ' certificates have expired')
           : critical ? _sdNum(critical) + ' expiring within 7 days'
           : expiring ? _sdNum(expiring) + ' expiring within 30 days'
           : 'All certificates healthy',
        flags,
        meta: [next !== null ? 'next expiry in <b>' + _sdNum(next) + 'd</b>' : '',
               _certUsage.why ? _esc(_certUsage.why) : ''].filter(Boolean).join(' · '),
    });
}

function _certFlags(c) {
    const v = _certVerdict(c);
    if (!v) return [];
    const out = [];
    if (v.orphaned) out.push('no resolver');
    if (v.unused)   out.push('unused');
    return out;
}

function _certFlagClass(c) { return _certFlags(c).length ? ' tm-warn' : ''; }

function _certLeft(days) {
    if (days > 0) return days + 'd left';
    if (days === 0) return 'expires today';
    return days === -1 ? 'expired yesterday' : 'expired ' + Math.abs(days) + 'd ago';
}

function _certDeleteRail(c, main, resolver, sans) {
    if (!_certCanDelete() || resolver === 'file') return '';
    if (_certBulk) {
        return `<span class="tm-rail" onclick="event.stopPropagation()">`
            + `<input type="checkbox" class="bulk-check" ${_certPicked.has(_certKey(c)) ? 'checked' : ''} `
            + `onchange="toggleCertPick(${_jsArg(_certKey(c))})" `
            + `style="width:15px;height:15px;accent-color:var(--blue);cursor:pointer"></span>`;
    }
    return `<span class="tm-rail" onclick="event.stopPropagation()">`
        + `<button type="button" class="tm-btn" title="Remove from acme.json" onclick="event.stopPropagation();removeCerts([{main:${_jsArg(main)},resolver:${_jsArg(resolver)},source:${_jsArg(c.source || '')}}])">`
        + `<i class="ph-bold ph-trash"></i></button></span>`;
}

function _certFlagText(c) {
    const flags = _certFlags(c);
    if (!flags.length) return '';
    const v = _certVerdict(c) || {};
    const why = v.orphaned ? 'no certificate resolver by this name is configured any more'
                           : 'no router on this server serves a domain this certificate covers';
    return ` · <span title="${_esc(why)}">${_esc(flags.join(' · '))}</span>`;
}

let _certManage = { available: false, reason: '' };

function _certCanDelete() { return !!_certManage.available; }

let _certBulk = false;
const _certPicked = new Set();

function toggleCertBulkMode() {
    _certBulk = !_certBulk;
    if (!_certBulk) _certPicked.clear();
    document.getElementById('certBulkBtn')?.classList.toggle('active-http', _certBulk);
    _paintCertBulkBar();
    renderCertCards();
}

function toggleCertPick(key) {
    if (_certPicked.has(key)) _certPicked.delete(key);
    else _certPicked.add(key);
    _paintCertBulkBar();
}

function selectUnusedCerts() {
    _allCerts.forEach(c => {
        const v = _certVerdict(c);
        if (v && v.unused && c.resolver && c.resolver !== 'file') _certPicked.add(_certKey(c));
    });
    _paintCertBulkBar();
    renderCertCards();
}

function _paintCertBulkBar() {
    const bar = document.getElementById('certBulkBar');
    if (bar) bar.style.display = _certBulk ? '' : 'none';
    const n = document.getElementById('certBulkCount');
    if (n) n.textContent = _certPicked.size + ' selected';
}

async function bulkRemoveCerts() {
    const rows = _allCerts.filter(c => _certPicked.has(_certKey(c)));
    if (!rows.length) return;
    const done = await removeCerts(rows);
    if (done === false) return;
    _certPicked.clear();
    _certBulk = false;
    document.getElementById('certBulkBtn')?.classList.remove('active-http');
    _paintCertBulkBar();
    renderCertCards();
}

async function _loadCertManage() {
    _certManage = { available: false, reason: '' };
    try {
        const srv = _tlsSrv();
        const res = await fetch('/api/certs/manage' + (srv ? '?server=' + encodeURIComponent(srv) : ''));
        if (res.ok) _certManage = await res.json();
    } catch (e) {}
}

async function _certsForRoutes(ids) {
    const pool = window._lastRenderedApps || (typeof APP_DATA !== 'undefined' ? APP_DATA : []) || [];
    const hosts = new Set();
    (ids || []).forEach(id => {
        const app = pool.find(a => String(a.id) === String(id));
        if (!app || !app.tls) return;
        [...String(app.rule || '').matchAll(/Host(?:SNI)?\(`([^`]+)`\)/g)].forEach(m => {
            const h = m[1].trim().toLowerCase();
            if (h && h !== '*') hosts.add(h);
        });
    });
    if (!hosts.size) return [];
    await _loadCertManage();
    if (!_certCanDelete()) return [];
    await _loadCertUsage();
    let certs = [];
    try {
        const res = await agentFetch('/api/traefik/certs');
        certs = ((await res.json()) || {}).certs || [];
    } catch (e) { return []; }
    const stillUsed = new Set();
    pool.forEach(a => {
        if (!a.tls || ids.map(String).includes(String(a.id))) return;
        [...String(a.rule || '').matchAll(/Host(?:SNI)?\(`([^`]+)`\)/g)]
            .forEach(m => stillUsed.add(m[1].trim().toLowerCase()));
    });
    return certs.filter(c => c.resolver && c.resolver !== 'file'
        && [c.main, ...(c.sans || [])].some(d => hosts.has(String(d).trim().toLowerCase()))
        && ![c.main, ...(c.sans || [])].some(d => stillUsed.has(String(d).trim().toLowerCase())));
}

async function removeCerts(rows, opts) {
    const list = (rows || []).filter(c => c && c.main);
    if (!list.length) return;
    if (opts && opts.confirmed) return _sendCertRemoval(list);
    const names = list.map(c => c.main);
    const shown = names.length <= 6 ? names.join(', ')
                : names.slice(0, 6).join(', ') + ' and ' + (names.length - 6) + ' more';
    const inUse = list.filter(c => {
        const v = _certUsage.certs.find(u => _certKey(u) === _certKey(c));
        return v && !v.unused;
    }).length;

    const notes = ['Traefik is restarted afterwards. It only reads acme.json at startup, so without that the change would be undone.'];
    if (inUse) {
        notes.push((inUse === 1 ? 'One of these still serves a route, so Traefik requests a new certificate for it'
                    : inUse + ' of these still serve routes, so Traefik requests new certificates for them')
                   + " on startup. Let's Encrypt allows five identical certificates per week.");
    }
    notes.push('A copy of acme.json is saved to your backups first, and can be restored from Settings, Backups, Certificates.');

    const answer = await _confirmWith({
        message: list.length === 1
            ? 'Remove ' + shown + ' from acme.json?'
            : 'Remove ' + list.length + ' certificates from acme.json: ' + shown + '?',
        title: list.length === 1 ? 'Remove Certificate' : 'Remove Certificates',
        okLabel: 'Remove', typeWord: 'DELETE', notes,
    });
    if (!answer.ok) return false;
    return _sendCertRemoval(list);
}

async function _sendCertRemoval(list) {
    const canWait = typeof _showRestartOverlay === 'function'
                 && typeof _hideRestartOverlay === 'function'
                 && typeof _waitForReconnect === 'function';
    const back = (removed) => {
        const n = removed || list.length;
        showToast('Removed ' + n + (n === 1 ? ' certificate' : ' certificates'));
        refreshCertsTab();
    };
    const stop = (msg) => {
        if (canWait) _hideRestartOverlay();
        showToast(msg, 'error');
    };
    if (canWait) _showRestartOverlay();
    try {
        const res = await fetch('/api/certs/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ..._csrfHeaders() },
            body: JSON.stringify({ server: _tlsSrv(), certs: list.map(c => ({ resolver: c.resolver, main: c.main })) }),
        });
        if (canWait && (res.status === 502 || res.status === 504)) {
            _waitForReconnect(true, () => back());
            return;
        }
        const body = await res.json().catch(() => ({}));
        if (!res.ok || !body.ok) {
            stop(body.error || 'Could not remove the certificate');
            return;
        }
        if (!body.restarted) {
            stop('Removed ' + body.removed + ', but Traefik did not restart'
                 + (body.restart_error ? ': ' + body.restart_error : '')
                 + '. The change is undone until it does.');
            refreshCertsTab();
            return;
        }
        if (canWait) {
            _waitForReconnect(false, () => back(body.removed));
            return;
        }
        back(body.removed);
    } catch (e) {
        if (canWait) {
            _waitForReconnect(true, () => back());
            return;
        }
        showToast(_netErrText(e, 'Could not remove the certificate'), 'error');
    }
}

async function _loadCertUsage() {
    _certUsage = { certs: [], unused_known: false, why: '', resolvers_known: false };
    try {
        const srv = _tlsSrv();
        const res = await fetch('/api/certs/usage' + (srv ? '?server=' + encodeURIComponent(srv) : ''));
        if (res.ok) _certUsage = await res.json();
    } catch (e) {}
}

function renderCertCards() {
    const q   = (document.getElementById('certsSearch')?.value || '').toLowerCase();
    const now = Date.now();
    const domain = document.getElementById('certDomainFilter')?.value || '';
    const items = _allCerts.filter(cert =>
        (!q || (cert.main||'').toLowerCase().includes(q) || (cert.sans||[]).some(d => d.toLowerCase().includes(q)))
        && (!domain || _certDomains(cert).some(d => _certBaseDomain(d) === domain))
        && _certMatchesFilter(cert)
    );
    if (items.length === 0) {
        const narrowed = _certFilter !== 'all' || domain || q;
        document.getElementById('certsContent').innerHTML =
            `<div class="text-center py-12 rounded-xl" style="color:var(--muted);border:1px solid var(--border)">`
            + (narrowed ? 'No certificates match these filters' : 'No certificates') + `</div>`;
        return;
    }
    const cards = items.map(cert => {
        const main     = cert.main || 'Unknown';
        const sans     = cert.sans || [];
        const resolver = cert.resolver || '-';
        let daysLeft = null, expiryStr = '-';
        if (cert.not_after) {
            const expiry = new Date(cert.not_after);
            if (!isNaN(expiry)) {
                daysLeft  = Math.ceil((expiry - now) / 86400000);
                expiryStr = expiry.toLocaleDateString();
            }
        }
        const expiryColor = daysLeft === null ? 'var(--muted)' : daysLeft < 7 ? 'var(--red)' : daysLeft < 30 ? 'var(--yellow)' : 'var(--green)';
        const expiryBadge = daysLeft !== null
            ? `<span class="badge" style="background:${daysLeft<7?'rgba(248,81,73,0.15)':daysLeft<30?'rgba(210,153,34,0.15)':'rgba(63,185,80,0.15)'};color:${expiryColor};border-color:${expiryColor}40">${daysLeft}d left</span>`
            : '';
        const extra = sans.filter(d => d !== main);
        const vals = extra.slice(0, 2).map(d =>
            `<div class="tm-val tm-val-host"><i class="ph-bold ph-globe-simple"></i><span class="tm-v">${_esc(d)}</span>${_tmCopy(d)}</div>`).join('')
            + (extra.length > 2 ? `<div class="tm-val"><i class="ph-bold ph-dot" style="opacity:0"></i><span class="tm-more" title="${_esc(extra.join(', '))}">+${extra.length - 2} more</span></div>` : '');
        return `<div class="tm-card tm-card-flat"${daysLeft !== null && daysLeft < 7 ? ' data-health="down"' : ''} style="--tm-accent:${expiryColor}">
            <div class="tm-head">
                <span class="tm-ic tm-ic-tile"><i class="ph-bold ph-shield-check"></i></span>
                <div class="tm-head-txt">
                    <div class="tm-title"><span class="tm-name">${_esc(main)}</span></div>
                    <div class="tm-sub">${_esc(resolver)}</div>
                </div>
                ${_certDeleteRail(cert, main, resolver, sans)}
            </div>
            ${vals ? `<div class="tm-vals">${vals}</div>` : ''}
            <div class="tm-foot"><span class="tm-meta${_certFlagClass(cert)}">${daysLeft !== null && daysLeft < 0 ? 'expired' : 'expires'} ${_esc(expiryStr)}${extra.length ? ` · ${extra.length + 1} domains` : ''}${_certFlagText(cert)}</span>${daysLeft !== null ? `<span class="tm-cf" style="color:${expiryColor}">${_certLeft(daysLeft)}</span>` : ''}</div>
        </div>`;
    }).join('');
    document.getElementById('certsContent').innerHTML =
        `<div class="tm-card-grid">${cards}</div>`;
}

async function refreshCertsTab() {
    const container = document.getElementById('certsContent');
    container.innerHTML = `<div class="text-center py-16" style="color:var(--muted)"><i class="ph-light ph-spinner-gap text-4xl block mb-3 animate-spin opacity-40"></i><p>Loading certificates...</p></div>`;
    try {
        const certRes = await agentFetch('/api/traefik/certs');
        if (!certRes.ok) {
            const msg = await _errText(certRes, 'Could not load certificate data');
            container.innerHTML = `<div class="text-center py-16 rounded-xl" style="color:var(--muted);border:1px solid var(--border)"><i class="ph-light ph-cloud-slash text-5xl block mb-3 opacity-30"></i><p>${_esc(msg)}</p></div>`;
            return;
        }
        const res  = await certRes.json();
        const certs = Array.isArray(res.certs) ? res.certs : [];

        if (res.error && certs.length === 0) {
            container.innerHTML = _emptyMountState({
                icon: 'ph-shield',
                title: 'acme.json not mounted',
                description: 'Mount your Traefik <code class="font-mono" style="color:var(--blue)">acme.json</code> into this container read-only to view and track your TLS certificates.',
                steps: [
                    { label: 'Add this volume to the <code class="font-mono">traefik-manager</code> service in your <code class="font-mono">docker-compose.yml</code>:',
                      code: '- /path/to/traefik/acme.json:/app/acme.json:ro' },
                ],
                note: 'No Traefik restart needed - only traefik-manager needs to be updated.'
            });
            setTabCount('certs', '0');
            return;
        }

        if (certs.length === 0) {
            container.innerHTML = `<div class="text-center py-16 rounded-xl" style="color:var(--muted);border:1px solid var(--border)">
                <i class="ph-light ph-shield text-5xl block mb-3 opacity-30"></i>
                <p class="font-medium">No certificates found</p>
                <p class="text-xs mt-1">acme.json may be empty - certs are issued on first request.</p>
            </div>`;
            setTabCount('certs', '0');
            return;
        }

        _allCerts = certs;
        setTabCount('certs', certs.length);
        _paintCertDomainFilter();
        renderCertsVerdict();
        renderCertCards();
        await Promise.all([_loadCertUsage(), _loadCertManage()]);
        const bulkWrap = document.getElementById('certBulkWrap');
        if (bulkWrap) bulkWrap.style.display = _certCanDelete() ? '' : 'none';
        renderCertsVerdict();
        renderCertCards();
    } catch(e) {
        container.innerHTML = `<div class="text-center py-16 rounded-xl" style="color:var(--muted);border:1px solid var(--border)"><i class="ph-light ph-cloud-slash text-5xl block mb-3 opacity-30"></i><p>${_esc(_netErrText(e, 'Could not load certificate data'))}</p></div>`;
    }
}

let _tlsOptions = [];

function _tlsSrv() {
    return (typeof _activeAgent !== 'undefined' && _activeAgent) ? _activeAgent.id : '';
}

async function refreshTlsOptionsTab() {
    const el = document.getElementById('tlsOptsContent');
    if (!el) return;
    el.innerHTML = `<div class="text-center py-16" style="color:var(--muted)"><i class="ph-light ph-spinner-gap text-4xl block mb-3 animate-spin opacity-40"></i><p>Loading TLS profiles...</p></div>`;
    try {
        const res = await fetch('/api/tls-options' + (_tlsSrv() ? '?server=' + encodeURIComponent(_tlsSrv()) : ''));
        if (!res.ok) {
            const msg = await _errText(res, 'Failed to load TLS profiles');
            el.innerHTML = `<div class="text-center py-16" style="color:var(--muted)"><i class="ph-bold ph-warning text-3xl block mb-2"></i><p>${_esc(msg)}</p></div>`;
            return;
        }
        _tlsOptions = await res.json();
        renderTlsOptions(_tlsOptions);
    } catch(e) {
        el.innerHTML = `<div class="text-center py-16" style="color:var(--muted)"><i class="ph-bold ph-warning text-3xl block mb-2"></i><p>${_esc(_netErrText(e, 'Failed to load TLS profiles'))}</p></div>`;
    }
}

function filterTlsOptions() {
    const q = (document.getElementById('tlsOptsSearch')?.value || '').toLowerCase();
    renderTlsOptions(_tlsOptions.filter(o => o.name.toLowerCase().includes(q)));
}

function _tlsVer(v) {
    return String(v).replace(/^VersionTLS(\d)(\d)$/, 'TLS $1.$2');
}

function _tlsCfChip(path) {
    if (!path) return '';
    const name = String(path).split('/').filter(Boolean).pop() || String(path);
    return `<span class="tm-cf" title="${_esc(path)}"><i class="ph-bold ph-file-code"></i>${_esc(name)}</span>`;
}

function _tmTlsOptCard(o, i) {
    const mtls = o.clientAuthType && o.clientAuthType !== 'NoClientCert';
    const sub = [
        o.minVersion ? _tlsVer(o.minVersion) + '+' : '',
        o.maxVersion ? 'max ' + _tlsVer(o.maxVersion) : '',
        o.sniStrict ? 'SNI strict' : '',
        mtls ? 'mTLS' : '',
    ].filter(Boolean).join(' \u00b7 ') || 'defaults';

    const val = (icon, text, title) => `<div class="tm-val"><i class="ph-bold ${icon}"></i><span class="tm-v" title="${_esc(title || text)}">${_esc(text)}</span></div>`;
    const vals = [
        o.cipherSuites?.length ? val('ph-list-numbers', `${o.cipherSuites.length} cipher suite${o.cipherSuites.length > 1 ? 's' : ''}`, o.cipherSuites.join('\n')) : '',
        o.curvePreferences?.length ? val('ph-circle-notch', o.curvePreferences.join(', ')) : '',
        o.alpnProtocols?.length ? val('ph-swap', o.alpnProtocols.join(', ')) : '',
        mtls ? val('ph-identification-card', o.clientAuthType) : '',
    ].filter(Boolean).join('');

    const rail = `<span class="tm-rail" onclick="event.stopPropagation()">` +
        `<button type="button" class="tm-btn" title="Details" data-idx="${i}" onclick="event.stopPropagation();_tlsOptInfo(this)"><i class="ph-bold ph-info"></i></button>` +
        `<button type="button" class="tm-btn" title="Edit" data-idx="${i}" onclick="event.stopPropagation();_tlsOptEdit(this)"><i class="ph-bold ph-pencil-simple"></i></button>` +
        `<button type="button" class="tm-btn" title="Delete" onclick="event.stopPropagation();deleteTlsOption(${_jsArg(o.name)},${_jsArg(o.configFile || '')})"><i class="ph-bold ph-trash"></i></button>` +
        '</span>';

    return `<div class="tm-card tls-opt-card" data-name="${_esc(o.name.toLowerCase())}" data-idx="${i}" style="--tm-accent:var(--green)" onclick="openTlsOptDetail(_tlsOptions[${i}])">
        <div class="tm-head">
            <span class="tm-ic tm-ic-tile"><i class="ph-bold ph-lock-key"></i></span>
            <div class="tm-head-txt">
                <div class="tm-title"><span class="tm-name">${_esc(o.name)}</span></div>
                <div class="tm-sub">${_esc(sub)}</div>
            </div>${rail}
        </div>
        ${vals ? `<div class="tm-vals">${vals}</div>` : ''}
        <div class="tm-foot"><span class="tm-meta">${_tmTlsOptUsage(o)}</span>${_tlsCfChip(o.configFile || o.configFilePath)}</div>
    </div>`;
}

function _tmTlsOptUsage(o) {
    const pool = window._lastRenderedApps || (typeof APP_DATA !== 'undefined' ? APP_DATA : []) || [];
    const n = pool.filter(r => r.tlsOptionsProfile === o.name).length;
    return n ? `used by ${n} route${n > 1 ? 's' : ''}` : 'unused';
}

function renderTlsOptions(opts) {
    const el = document.getElementById('tlsOptsContent');
    if (!el) return;
    if (!opts || opts.length === 0) {
        el.innerHTML = `<div class="text-center py-16" style="color:var(--muted)"><i class="ph-light ph-lock-key text-4xl block mb-3 opacity-30"></i><p class="text-sm">No TLS profiles defined.</p><p class="text-xs mt-1">Click <strong>Add TLS Profile</strong> to create one.</p></div>`;
        return;
    }
    const cards = opts.map(o => {
        const i = _tlsOptions.indexOf(o);
        return _tmTlsOptCard(o, i);
    }).join('');
    el.innerHTML = `<div class="tm-card-grid">${cards}</div>`;
}

function _tlsOptEdit(btn) {
    const idx = parseInt(btn.getAttribute('data-idx'));
    openTlsOptionModal(_tlsOptions[idx]);
}

function _tlsOptInfo(btn) {
    const idx = parseInt(btn.getAttribute('data-idx'));
    openTlsOptDetail(_tlsOptions[idx]);
}

function openTlsOptDetail(o) {
    closeOtherPanels('tlsOptDetailPanel');
    document.getElementById('tlsOptDetailTitle').textContent = o.name;
    document.getElementById('tlsOptDetailEditBtn').onclick = () => { closeTlsOptDetail(); openTlsOptionModal(o); };
    const rows = [
        o.configFile && ['Config File', _dText(o.configFile, 'd-off'), true],
        o.minVersion && ['Min Version', _dText(o.minVersion), true],
        o.maxVersion && ['Max Version', _dText(o.maxVersion), true],
        o.sniStrict && ['SNI Strict', _dBool(true), true],
        o.cipherSuites?.length && ['Cipher Suites', _dList(o.cipherSuites, 'd-on'), true],
        o.curvePreferences?.length && ['Curve Preferences', _dList(o.curvePreferences, 'd-on'), true],
        o.alpnProtocols?.length && ['ALPN Protocols', _dList(o.alpnProtocols, 'd-on'), true],
        (o.clientAuthType && o.clientAuthType !== 'NoClientCert') && ['Client Auth Type', _dText(o.clientAuthType), true],
        o.clientAuthCAs?.length && ['CA Files', _dList(o.clientAuthCAs, 'd-on'), true],
    ].filter(Boolean);
    const allRoutes = window._lastRenderedApps || APP_DATA || [];
    const usedBy = allRoutes.filter(r => r.tlsOptionsProfile === o.name);
    const usedByHtml = renderDetailBlock('Used by', 'ph-arrows-split',
        usedBy.length
            ? `<div class="flex flex-wrap gap-1.5">${usedBy.map(r =>
                `<button type="button" class="route-deep-chip" onclick="_openRouteByName(${_jsArg(String(r.name))})" title="Open route"><i class="ph-bold ph-arrows-split"></i>${_esc(String(r.name).split('@')[0])}</button>`).join('')}</div>`
            : `<div class="text-xs" style="color:var(--muted)">No routes using this profile.</div>`,
        _dCount(usedBy.length));
    const yamlHtml = o.yaml ? renderDetailBlock('Raw YAML', 'ph-code',
        `<div class="rounded-lg p-3 overflow-x-auto" style="background:var(--input-bg);border:1px solid var(--border)"><pre class="text-xs font-mono leading-relaxed" style="color:var(--green);margin:0">${_esc(o.yaml)}</pre></div>`) : '';
    document.getElementById('tlsOptDetailContent').innerHTML =
        `${renderSection('Profile', 'ph-lock-laminated', rows)}${usedByHtml}${yamlHtml}`;
    document.getElementById('tlsOptDetailPanel').classList.add('open');
    setDetailDockOpen(true);
    document.getElementById('tlsOptDetailBackdrop').classList.add('open');
    document.body.style.overflow = 'hidden';
}

function closeTlsOptDetail() {
    setDetailDockOpen(false);
    document.getElementById('tlsOptDetailPanel').classList.remove('open');
    document.getElementById('tlsOptDetailBackdrop').classList.remove('open');
    document.body.style.overflow = '';
}

function onTlsOptConfigFileChange(sel) {
    const newInput = document.getElementById('tlsOptNewFileName');
    if (newInput) newInput.style.display = sel.value === '__new__' ? 'block' : 'none';
}

function toggleTlsClientAuthCAs(val) {
    const row = document.getElementById('tlsClientAuthCAsRow');
    if (row) row.style.display = (val && val !== '' && val !== 'NoClientCert') ? 'block' : 'none';
}

function openTlsOptionModal(opt) {
    closeOtherPanels('tlsOptionsModal');
    const modal = document.getElementById('tlsOptionsModal');
    const isEdit = !!opt;
    document.getElementById('tlsOptionsModalTitle').textContent = isEdit ? 'Edit TLS Profile' : 'Add TLS Profile';
    document.getElementById('tlsOptEditName').value    = isEdit ? (opt.name || '') : '';
    document.getElementById('tlsOptName').value        = isEdit ? (opt.name || '') : '';
    document.getElementById('tlsOptName').readOnly     = false;
    document.getElementById('tlsOptMinVersion').value  = isEdit ? (opt.minVersion || '') : '';
    document.getElementById('tlsOptMaxVersion').value  = isEdit ? (opt.maxVersion || '') : '';
    document.getElementById('tlsOptSniStrict').checked = isEdit ? !!opt.sniStrict : false;
    document.getElementById('tlsOptCiphers').value     = isEdit ? (opt.cipherSuites || []).join('\n') : '';
    document.getElementById('tlsOptCurves').value      = isEdit ? (opt.curvePreferences || []).join('\n') : '';
    document.getElementById('tlsOptAlpn').value        = isEdit ? (opt.alpnProtocols || []).join('\n') : '';
    const caType = isEdit ? (opt.clientAuthType || '') : '';
    document.getElementById('tlsOptClientAuthType').value = caType;
    document.getElementById('tlsOptClientAuthCAs').value  = isEdit ? (opt.clientAuthCAs || []).join('\n') : '';
    toggleTlsClientAuthCAs(caType);
    const cfSel = document.getElementById('tlsOptConfigFileSelect');
    if (cfSel) cfSel.value = isEdit ? (opt.configFile || '') : '';
    const newFileInput = document.getElementById('tlsOptNewFileName');
    if (newFileInput) { newFileInput.style.display = 'none'; newFileInput.value = ''; }
    document.getElementById('tlsOptConfigFile').value = isEdit ? (opt.configFile || '') : '';
    modal.classList.add('open');
    document.getElementById('tlsOptionsBackdrop').classList.add('open');
    if (!setDetailDockOpen(true)) document.body.style.overflow = 'hidden';
}

function closeTlsOptionModal() {
    setDetailDockOpen(false);
    document.getElementById('tlsOptionsModal').classList.remove('open');
    document.getElementById('tlsOptionsBackdrop').classList.remove('open');
    document.body.style.overflow = '';
}

async function saveTlsOption() {
    const token = document.querySelector('meta[name="csrf-token"]')?.content || '';
    const name = document.getElementById('tlsOptName').value.trim();
    if (!name) { showToast('Profile name is required', 'error'); return; }
    const cfSel = document.getElementById('tlsOptConfigFileSelect');
    let configFile = cfSel ? cfSel.value : (document.getElementById('tlsOptConfigFile').value || '');
    if (configFile === '__new__') {
        const newName = (document.getElementById('tlsOptNewFileName')?.value || '').trim();
        if (!newName) { showToast('Enter a filename for the new config file', 'error'); return; }
        configFile = newName.endsWith('.yml') || newName.endsWith('.yaml') ? newName : newName + '.yml';
    }
    const toList = v => v.split('\n').map(s => s.trim()).filter(Boolean);
    const caType = document.getElementById('tlsOptClientAuthType').value;
    const body = {
        name,
        configFile,
        minVersion:        document.getElementById('tlsOptMinVersion').value,
        maxVersion:        document.getElementById('tlsOptMaxVersion').value,
        sniStrict:         document.getElementById('tlsOptSniStrict').checked,
        cipherSuites:      toList(document.getElementById('tlsOptCiphers').value),
        curvePreferences:  toList(document.getElementById('tlsOptCurves').value),
        alpnProtocols:     toList(document.getElementById('tlsOptAlpn').value),
        clientAuthType:    caType,
        clientAuthCAs:     toList(document.getElementById('tlsOptClientAuthCAs').value),
    };
    try {
        const res = await fetch('/api/tls-options', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'fetch', 'X-CSRF-Token': token },
            body: JSON.stringify({ ...body, server: _tlsSrv(),
                               originalName: (document.getElementById('tlsOptEditName')?.value || '').trim() }),
        });
        if (!res.ok) { showToast(await _errText(res, 'Save failed'), 'error'); return; }
        const json = await res.json();
        if (json.ok) {
            closeTlsOptionModal();
            showToast('TLS profile saved');
            refreshTlsOptionsTab();
            _dropTlsOptionsCache();
            _populateTlsOptionsSelect();
        } else {
            showToast(json.error || json.message || 'Save failed', 'error');
        }
    } catch(e) { showToast(_netErrText(e, 'Save failed'), 'error'); }
}

async function deleteTlsOption(name, configFile) {
    if (!confirm(`Delete TLS profile "${name}"?`)) return;
    const token = document.querySelector('meta[name="csrf-token"]')?.content || '';
    const _sv = _tlsSrv();
    const params = '?' + new URLSearchParams({ ...(configFile ? { configFile } : {}), ...(_sv ? { server: _sv } : {}) }).toString();
    try {
        const res = await fetch(`/api/tls-options/${encodeURIComponent(name)}${params}`, {
            method: 'DELETE',
            headers: { 'X-Requested-With': 'fetch', 'X-CSRF-Token': token },
        });
        if (!res.ok) { showToast(await _errText(res, 'Delete failed'), 'error'); return; }
        const json = await res.json();
        if (json.ok) {
            showToast('TLS profile deleted');
            refreshTlsOptionsTab();
            _dropTlsOptionsCache();
            _populateTlsOptionsSelect();
        } else {
            showToast(json.error || json.message || 'Delete failed', 'error');
        }
    } catch(e) { showToast(_netErrText(e, 'Delete failed'), 'error'); }
}

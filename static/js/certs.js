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
    sel.innerHTML = `<option value="">${th('All domains')}</option>${names.map(n => `<option value="${_esc(n)}">${_esc(n)}</option>`).join('')}`;
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
                     label: _allCerts.length === 1 ? tc('label', 'certificate') : tc('label', 'certificates') }];
    if (expired)  flags.push({ cls: 'd-bad', ic: 'ph-fill ph-x-circle', n: expired, label: tc('label', 'expired') });
    if (critical) flags.push({ cls: 'd-bad', ic: 'ph-fill ph-warning-octagon', n: critical, label: t('under 7d') });
    if (expiring) flags.push({ cls: 'd-warn', ic: 'ph-fill ph-hourglass-high', n: expiring, label: t('under 30d') });
    if (!expired && !critical && !expiring) flags.push({ cls: 'd-on', ic: 'ph-bold ph-check', n: '', label: t('none expiring soon') });
    if (resolvers > 1) flags.push({ cls: 'd-off', ic: 'ph-bold ph-certificate', n: resolvers, label: tc('label', 'resolvers') });
    const unused   = _certUsage.certs.filter(u => u.unused).length;
    const orphaned = _certUsage.certs.filter(u => u.orphaned).length;
    if (unused)   flags.push({ cls: 'd-warn', ic: 'ph-bold ph-plugs', n: unused, label: tc('label', 'unused') });
    if (orphaned) flags.push({ cls: 'd-warn', ic: 'ph-bold ph-link-break', n: orphaned, label: t('no resolver') });
    _tvStrip('certsVerdict', {
        health: (expired || critical) ? 'down' : expiring ? 'warn' : 'up',
        ic: (expired || critical) ? 'ph-fill ph-warning-octagon' : expiring ? 'ph-fill ph-hourglass-high' : 'ph-fill ph-check-circle',
        txt: expired  ? tn('{count} certificate has expired', '{count} certificates have expired', expired, { count: _sdNum(expired) })
           : critical ? t('{critical} expiring within 7 days', { critical: _sdNum(critical) })
           : expiring ? t('{expiring} expiring within 30 days', { expiring: _sdNum(expiring) })
           : t('All certificates healthy'),
        flags,
        meta: [next !== null ? `${th('next expiry in {d}', { d: tmHtml(`<b>${_sdNum(next)}d</b>`) })}` : '',
               _certUsage.why ? _esc(_certUsage.why) : ''].filter(Boolean).join(' · '),
    });
}

function _certFlags(c) {
    const v = _certVerdict(c);
    if (!v) return [];
    const out = [];
    if (v.orphaned) out.push(t('no resolver'));
    if (v.unused)   out.push(tc('label', 'unused'));
    return out;
}

function _certFlagClass(c) { return _certFlags(c).length ? ' tm-warn' : ''; }

function _certLeft(days) {
    if (days > 0) return t('{days}d left', { days });
    if (days === 0) return t('expires today');
    return days === -1 ? t('expired yesterday') : t('expired {abs}d ago', { abs: Math.abs(days) });
}

function _certDeleteRail(c, main, resolver, sans) {
    if (!_certCanDelete() || resolver === 'file') return '';
    if (_certBulk) {
        return `<span class="tm-rail" onclick="event.stopPropagation()">`
            + `<input type="checkbox" class="bulk-check" ${_certPicked.has(_certKey(c)) ? 'checked' : ''} `
            + `onchange="toggleCertPick(${_jsArg(_certKey(c))})" `
            + `style="width:15px;height:15px;accent-color:var(--blue);cursor:pointer"></span>`;
    }
    return `<span class="tm-rail" onclick="event.stopPropagation()"><button type="button" class="tm-btn" title="${th('Remove from acme.json')}" onclick="event.stopPropagation();removeCerts([{main:${_jsArg(main)},resolver:${_jsArg(resolver)},source:${_jsArg(c.source || '')}}],{server:${_jsArg(_certsFor)}})"><i class="ph-bold ph-trash"></i></button></span>`;
}

function _certFlagText(c) {
    const flags = _certFlags(c);
    if (!flags.length) return '';
    const v = _certVerdict(c) || {};
    const why = v.orphaned ? t('no certificate resolver by this name is configured any more')
                           : t('no router on this server serves a domain this certificate covers');
    return ` · <span title="${_esc(why)}">${_esc(flags.join(' · '))}</span>`;
}

let _certManage = { available: false, reason: '' };
let _certsFor = null;
let _certLoadSeq = 0;
let _certPickedFor = null;

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

function _scopeCertPicks() {
    if (_certPickedFor !== _certsFor) {
        _certPicked.clear();
        _certPickedFor = _certsFor;
    }
}

function toggleCertPick(key) {
    _scopeCertPicks();
    if (_certPicked.has(key)) _certPicked.delete(key);
    else _certPicked.add(key);
    _paintCertBulkBar();
}

function selectUnusedCerts() {
    _scopeCertPicks();
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
    if (n) n.textContent = t('{size} selected', { size: _certPicked.size });
}

async function bulkRemoveCerts() {
    if (_certPickedFor !== _certsFor) {
        _certPicked.clear();
        _certPickedFor = null;
        _paintCertBulkBar();
        renderCertCards();
        return;
    }
    const rows = _allCerts.filter(c => _certPicked.has(_certKey(c)));
    if (!rows.length) return;
    const done = await removeCerts(rows, { server: _certsFor });
    if (done === false) return;
    _certPicked.clear();
    _certBulk = false;
    document.getElementById('certBulkBtn')?.classList.remove('active-http');
    _paintCertBulkBar();
    renderCertCards();
}

function _certServerChanged() {
    _certLoadSeq++;
    _allCerts = [];
    _certsFor = null;
    _certUsage = { certs: [], unused_known: false, why: '', resolvers_known: false };
    _certManage = { available: false, reason: '' };
    _certPicked.clear();
    _certPickedFor = null;
    _certBulk = false;
    document.getElementById('certBulkBtn')?.classList.remove('active-http');
    const wrap = document.getElementById('certBulkWrap');
    if (wrap) wrap.style.display = 'none';
    _paintCertBulkBar();
}

async function _loadCertManage(srv) {
    const server = srv === undefined ? _tlsSrv() : srv;
    let state = { available: false, reason: '' };
    try {
        const res = await fetch('/api/certs/manage' + (server ? '?server=' + encodeURIComponent(server) : ''));
        if (res.ok) state = await res.json();
    } catch (e) {}
    if (server === _tlsSrv()) _certManage = state;
    return state;
}

async function _certsForRoutes(ids) {
    const srv = _tlsSrv();
    const wanted = (ids || []).map(String);
    const pool = window._lastRenderedApps || (typeof APP_DATA !== 'undefined' ? APP_DATA : []) || [];
    const hosts = new Set();
    wanted.forEach(id => {
        const app = pool.find(a => String(a.id) === id);
        if (!app || !app.tls) return;
        [...String(app.rule || '').matchAll(/Host(?:SNI)?\(`([^`]+)`\)/g)].forEach(m => {
            const h = m[1].trim().toLowerCase();
            if (h && h !== '*') hosts.add(h);
        });
    });
    if (!hosts.size) return [];
    const manage = await _loadCertManage(srv);
    if (!manage.available || srv !== _tlsSrv()) return [];
    let usage = null;
    let certs = [];
    try {
        const qs = new URLSearchParams();
        if (srv) qs.set('server', srv);
        wanted.forEach(id => qs.append('exclude', id));
        const [usageRes, certRes] = await Promise.all([
            fetch('/api/certs/usage?' + qs.toString()),
            agentFetch('/api/traefik/certs'),
        ]);
        if (!usageRes.ok || !certRes.ok) return [];
        usage = await usageRes.json();
        certs = ((await certRes.json()) || {}).certs || [];
    } catch (e) { return []; }
    if (!usage || !usage.unused_known || srv !== _tlsSrv()) return [];
    const unused = new Set((usage.certs || []).filter(c => c.unused).map(_certKey));
    return certs
        .filter(c => c.resolver && c.resolver !== 'file' && unused.has(_certKey(c))
            && [c.main, ...(c.sans || [])].some(d => hosts.has(String(d).trim().toLowerCase())))
        .map(c => Object.assign({}, c, { server: srv }));
}

async function removeCerts(rows, opts) {
    const list = (rows || []).filter(c => c && c.main);
    if (!list.length) return;
    const server = opts && opts.server !== undefined ? String(opts.server || '')
                 : list[0].server !== undefined ? String(list[0].server || '')
                 : String(_certsFor || '');
    if (server !== _tlsSrv()) {
        showToast(t('The server changed, reload the list and select again'), 'error');
        _certPicked.clear();
        _certPickedFor = null;
        _paintCertBulkBar();
        refreshCertsTab();
        return false;
    }
    if (opts && opts.confirmed) return _sendCertRemoval(list, server);
    const names = list.map(c => c.main);
    const shown = names.length <= 6 ? names.join(', ')
                : t('{items} and {count} more', { items: names.slice(0, 6).join(', '), count: names.length - 6 });
    const inUse = list.filter(c => {
        const v = _certUsage.certs.find(u => _certKey(u) === _certKey(c));
        return v && !v.unused;
    }).length;

    const notes = [t('Traefik is restarted afterwards. It only reads acme.json at startup, so without that the change would be undone.')];
    if (inUse) {
        notes.push((inUse === 1
            ? t("One of these still serves a route, so Traefik requests a new certificate for it on startup. Let's Encrypt allows five identical certificates per week.")
            : t("{count} of these still serve routes, so Traefik requests new certificates for them on startup. Let's Encrypt allows five identical certificates per week.", { count: inUse })));
    }
    notes.push(t('A copy of acme.json is saved to your backups first, and can be restored from Settings, Backups, Certificates.'));

    const where = server && typeof _activeAgent !== 'undefined' && _activeAgent ? ' on ' + _activeAgent.name : '';
    const answer = await _confirmWith({
        message: list.length === 1
            ? t('Remove {shown} from acme.json{where}?', { shown, where })
            : t('Remove {list_count} certificates from acme.json{where}: {shown}?', { list_count: list.length, where, shown }),
        title: list.length === 1 ? t('Remove Certificate') : t('Remove Certificates'),
        okLabel: tc('button', 'Remove'), typeWord: _confirmWordFor(names), notes,
    });
    if (!answer.ok) return false;
    return _sendCertRemoval(list, server);
}

async function _sendCertRemoval(list, server) {
    const canWait = typeof _showRestartOverlay === 'function'
                 && typeof _hideRestartOverlay === 'function'
                 && typeof _waitForReconnect === 'function';
    const back = (removed) => {
        const n = removed || list.length;
        showToast(tn('Removed {n} certificate', 'Removed {n} certificates', n));
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
            body: JSON.stringify({ server: server || '', certs: list.map(c => ({ resolver: c.resolver, main: c.main })) }),
        });
        if (canWait && (res.status === 502 || res.status === 504)) {
            _waitForReconnect(true, () => back());
            return;
        }
        const body = await res.json().catch(() => ({}));
        if (!res.ok || !body.ok) {
            if (body.partial && body.restarted && canWait) {
                showToast(body.error || t('Certificate removal stopped partway'), 'error');
                _waitForReconnect(false, () => refreshCertsTab());
                return;
            }
            stop(body.error || t('Could not remove the certificate'));
            return;
        }
        if (!body.restarted) {
            stop((body.restart_error
                ? t('Removed {removed}, but Traefik did not restart: {error}. The change is undone until it does.', { removed: body.removed, error: body.restart_error })
                : t('Removed {removed}, but Traefik did not restart. The change is undone until it does.', { removed: body.removed })));
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
        showToast(_netErrText(e, t('Could not remove the certificate')), 'error');
    }
}

async function _loadCertUsage(srv) {
    const server = srv === undefined ? _tlsSrv() : srv;
    let usage = { certs: [], unused_known: false, why: '', resolvers_known: false };
    try {
        const res = await fetch('/api/certs/usage' + (server ? '?server=' + encodeURIComponent(server) : ''));
        if (res.ok) usage = await res.json();
    } catch (e) {}
    if (server === _tlsSrv()) _certUsage = usage;
    return usage;
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
            `<div class="text-center py-12 rounded-xl" style="color:var(--muted);border:1px solid var(--border)">${narrowed ? th('No certificates match these filters') : th('No certificates')}</div>`;
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
            ? `<span class="badge" style="background:${daysLeft<7 ? 'rgba(248,81,73,0.15)' : daysLeft<30 ? 'rgba(210,153,34,0.15)' : 'rgba(63,185,80,0.15)'};color:${expiryColor};border-color:${expiryColor}40">${th('{daysLeft}d left', { daysLeft: tmHtml(daysLeft) })}</span>`
            : '';
        const extra = sans.filter(d => d !== main);
        const vals = extra.slice(0, 2).map(d =>
            `<div class="tm-val tm-val-host"><i class="ph-bold ph-globe-simple"></i><span class="tm-v">${_esc(d)}</span>${_tmCopy(d)}</div>`).join('')
            + (extra.length > 2 ? `<div class="tm-val"><i class="ph-bold ph-dot" style="opacity:0"></i><span class="tm-more" title="${_esc(extra.join(', '))}">${th('+{count} more', { count: extra.length - 2 })}</span></div>` : '');
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
            <div class="tm-foot"><span class="tm-meta${_certFlagClass(cert)}">${daysLeft !== null && daysLeft < 0 ? th('expired {date}', { date: expiryStr }) : th('expires {date}', { date: expiryStr })}${extra.length ? ' · ' + th('{count} domains', { count: extra.length + 1 }) : ''}${_certFlagText(cert)}</span>${daysLeft !== null ? `<span class="tm-cf" style="color:${expiryColor}">${_certLeft(daysLeft)}</span>` : ''}</div>
        </div>`;
    }).join('');
    document.getElementById('certsContent').innerHTML =
        `<div class="tm-card-grid">${cards}</div>`;
}

async function refreshCertsTab() {
    const seq = ++_certLoadSeq;
    const srv = _tlsSrv();
    const stale = () => seq !== _certLoadSeq || srv !== _tlsSrv();
    const settle = () => {
        if (_certsFor !== srv) {
            _certManage = { available: false, reason: '' };
            _certUsage = { certs: [], unused_known: false, why: '', resolvers_known: false };
        }
        _certsFor = srv;
    };
    const container = document.getElementById('certsContent');
    container.innerHTML = `<div class="text-center py-16" style="color:var(--muted)"><i class="ph-light ph-spinner-gap text-4xl block mb-3 animate-spin opacity-40"></i><p>${th('Loading certificates...')}</p></div>`;
    try {
        const certRes = await agentFetch('/api/traefik/certs');
        if (stale()) return;
        if (!certRes.ok) {
            const msg = await _errText(certRes, t('Could not load certificate data'));
            if (stale()) return;
            settle();
            _allCerts = [];
            renderCertsVerdict();
            container.innerHTML = `<div class="text-center py-16 rounded-xl" style="color:var(--muted);border:1px solid var(--border)"><i class="ph-light ph-cloud-slash text-5xl block mb-3 opacity-30"></i><p>${_esc(msg)}</p></div>`;
            return;
        }
        const res  = await certRes.json();
        if (stale()) return;
        const certs = Array.isArray(res.certs) ? res.certs : [];
        settle();

        if (res.error && certs.length === 0) {
            _allCerts = [];
            renderCertsVerdict();
            container.innerHTML = _emptyMountState({
                icon: 'ph-shield',
                title: t('acme.json not mounted'),
                description: `${th('Mount your Traefik {acme_json} into this container read-only to view and track your TLS certificates.', { acme_json: tmHtml(`<code class="font-mono" style="color:var(--blue)">acme.json</code>`) })}`,
                steps: [
                    { label: `${th('Add this volume to the {traefik_manager} service in your {docker_compose_yml}:', { traefik_manager: tmHtml(`<code class="font-mono">traefik-manager</code>`), docker_compose_yml: tmHtml(`<code class="font-mono">docker-compose.yml</code>`) })}`,
                      code: '- /path/to/traefik/acme.json:/app/acme.json:ro' },
                ],
                note: t('No Traefik restart needed - only traefik-manager needs to be updated.')
            });
            setTabCount('certs', '0');
            return;
        }

        if (certs.length === 0) {
            _allCerts = [];
            renderCertsVerdict();
            container.innerHTML = `<div class="text-center py-16 rounded-xl" style="color:var(--muted);border:1px solid var(--border)">
                <i class="ph-light ph-shield text-5xl block mb-3 opacity-30"></i>
                <p class="font-medium">${th('No certificates found')}</p>
                <p class="text-xs mt-1">${th('acme.json may be empty - certs are issued on first request.')}</p>
            </div>`;
            setTabCount('certs', '0');
            return;
        }

        _allCerts = certs;
        setTabCount('certs', certs.length);
        _paintCertDomainFilter();
        renderCertsVerdict();
        renderCertCards();
        await Promise.all([_loadCertUsage(srv), _loadCertManage(srv)]);
        if (stale()) return;
        const bulkWrap = document.getElementById('certBulkWrap');
        if (bulkWrap) bulkWrap.style.display = _certCanDelete() ? '' : 'none';
        renderCertsVerdict();
        renderCertCards();
    } catch(e) {
        if (stale()) return;
        container.innerHTML = `<div class="text-center py-16 rounded-xl" style="color:var(--muted);border:1px solid var(--border)"><i class="ph-light ph-cloud-slash text-5xl block mb-3 opacity-30"></i><p>${_esc(_netErrText(e, t('Could not load certificate data')))}</p></div>`;
    }
}

let _tlsOptions = [];

function _tlsSrv() {
    return (typeof _activeAgent !== 'undefined' && _activeAgent) ? _activeAgent.id : '';
}

async function refreshTlsOptionsTab() {
    const el = document.getElementById('tlsOptsContent');
    if (!el) return;
    el.innerHTML = `<div class="text-center py-16" style="color:var(--muted)"><i class="ph-light ph-spinner-gap text-4xl block mb-3 animate-spin opacity-40"></i><p>${th('Loading TLS profiles...')}</p></div>`;
    try {
        const res = await fetch('/api/tls-options' + (_tlsSrv() ? '?server=' + encodeURIComponent(_tlsSrv()) : ''));
        if (!res.ok) {
            const msg = await _errText(res, t('Failed to load TLS profiles'));
            el.innerHTML = `<div class="text-center py-16" style="color:var(--muted)"><i class="ph-bold ph-warning text-3xl block mb-2"></i><p>${_esc(msg)}</p></div>`;
            return;
        }
        _tlsOptions = await res.json();
        renderTlsOptions(_tlsOptions);
    } catch(e) {
        el.innerHTML = `<div class="text-center py-16" style="color:var(--muted)"><i class="ph-bold ph-warning text-3xl block mb-2"></i><p>${_esc(_netErrText(e, t('Failed to load TLS profiles')))}</p></div>`;
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
        o.maxVersion ? t('max {version}', { version: _tlsVer(o.maxVersion) }) : '',
        o.sniStrict ? t('SNI strict') : '',
        mtls ? 'mTLS' : '',
    ].filter(Boolean).join(' \u00b7 ') || 'defaults';

    const val = (icon, text, title) => `<div class="tm-val"><i class="ph-bold ${icon}"></i><span class="tm-v" title="${_esc(title || text)}">${_esc(text)}</span></div>`;
    const vals = [
        o.cipherSuites?.length ? val('ph-list-numbers', tn('{n} cipher suite', '{n} cipher suites', o.cipherSuites.length), o.cipherSuites.join('\n')) : '',
        o.curvePreferences?.length ? val('ph-circle-notch', o.curvePreferences.join(', ')) : '',
        o.alpnProtocols?.length ? val('ph-swap', o.alpnProtocols.join(', ')) : '',
        mtls ? val('ph-identification-card', o.clientAuthType) : '',
    ].filter(Boolean).join('');

    const rail = `<span class="tm-rail" onclick="event.stopPropagation()"><button type="button" class="tm-btn" title="${thc('tooltip', 'Details')}" data-idx="${i}" onclick="event.stopPropagation();_tlsOptInfo(this)"><i class="ph-bold ph-info"></i></button><button type="button" class="tm-btn" title="${thc('tooltip', 'Edit')}" data-idx="${i}" onclick="event.stopPropagation();_tlsOptEdit(this)"><i class="ph-bold ph-pencil-simple"></i></button><button type="button" class="tm-btn" title="${thc('tooltip', 'Delete')}" onclick="event.stopPropagation();deleteTlsOption(${_jsArg(o.name)},${_jsArg(o.configFile || '')})"><i class="ph-bold ph-trash"></i></button></span>`;

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
    return n ? tn('used by {n} route', 'used by {n} routes', n) : t('unused');
}

function renderTlsOptions(opts) {
    const el = document.getElementById('tlsOptsContent');
    if (!el) return;
    if (!opts || opts.length === 0) {
        el.innerHTML = `<div class="text-center py-16" style="color:var(--muted)"><i class="ph-light ph-lock-key text-4xl block mb-3 opacity-30"></i><p class="text-sm">${th('No TLS profiles defined.')}</p><p class="text-xs mt-1">${th('Click {add_tls_profile} to create one.', { add_tls_profile: tmHtml(`<strong>${th('Add TLS Profile')}</strong>`) })}</p></div>`;
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
        o.configFile && [t('Config File'), _dText(o.configFile, 'd-off'), true],
        o.minVersion && [t('Min Version'), _dText(o.minVersion), true],
        o.maxVersion && [t('Max Version'), _dText(o.maxVersion), true],
        o.sniStrict && [t('SNI Strict'), _dBool(true), true],
        o.cipherSuites?.length && [t('Cipher Suites'), _dList(o.cipherSuites, 'd-on'), true],
        o.curvePreferences?.length && [t('Curve Preferences'), _dList(o.curvePreferences, 'd-on'), true],
        o.alpnProtocols?.length && [t('ALPN Protocols'), _dList(o.alpnProtocols, 'd-on'), true],
        (o.clientAuthType && o.clientAuthType !== 'NoClientCert') && [t('Client Auth Type'), _dText(o.clientAuthType), true],
        o.clientAuthCAs?.length && [t('CA Files'), _dList(o.clientAuthCAs, 'd-on'), true],
    ].filter(Boolean);
    const allRoutes = window._lastRenderedApps || APP_DATA || [];
    const usedBy = allRoutes.filter(r => r.tlsOptionsProfile === o.name);
    const usedByHtml = renderDetailBlock(t('Used by'), 'ph-arrows-split',
        usedBy.length
            ? `<div class="flex flex-wrap gap-1.5">${usedBy.map(r =>
                `<button type="button" class="route-deep-chip" onclick="_openRouteByName(${_jsArg(String(r.name))})" title="${th('Open route')}"><i class="ph-bold ph-arrows-split"></i>${_esc(String(r.name).split('@')[0])}</button>`).join('')}</div>`
            : `<div class="text-xs" style="color:var(--muted)">${th('No routes using this profile.')}</div>`,
        _dCount(usedBy.length));
    const yamlHtml = o.yaml ? renderDetailBlock(t('Raw YAML'), 'ph-code',
        `<div class="rounded-lg p-3 overflow-x-auto" style="background:var(--input-bg);border:1px solid var(--border)"><pre class="text-xs font-mono leading-relaxed" style="color:var(--green);margin:0">${_esc(o.yaml)}</pre></div>`) : '';
    document.getElementById('tlsOptDetailContent').innerHTML =
        `${renderSection(tc('label', 'Profile'), 'ph-lock-laminated', rows)}${usedByHtml}${yamlHtml}`;
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
    document.getElementById('tlsOptionsModalTitle').textContent = isEdit ? t('Edit TLS Profile') : t('Add TLS Profile');
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
    if (!name) { showToast(t('Profile name is required'), 'error'); return; }
    const cfSel = document.getElementById('tlsOptConfigFileSelect');
    let configFile = cfSel ? cfSel.value : (document.getElementById('tlsOptConfigFile').value || '');
    if (configFile === '__new__') {
        const newName = (document.getElementById('tlsOptNewFileName')?.value || '').trim();
        if (!newName) { showToast(t('Enter a filename for the new config file'), 'error'); return; }
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
        if (!res.ok) { showToast(await _errText(res, t('Save failed')), 'error'); return; }
        const json = await res.json();
        if (json.ok) {
            closeTlsOptionModal();
            showToast(t('TLS profile saved'));
            refreshTlsOptionsTab();
            _dropTlsOptionsCache();
            _populateTlsOptionsSelect();
        } else {
            showToast(json.error || json.message || t('Save failed'), 'error');
        }
    } catch(e) { showToast(_netErrText(e, t('Save failed')), 'error'); }
}

async function deleteTlsOption(name, configFile) {
    if (!confirm(t('Delete TLS profile "{name}"?', { name }))) return;
    const token = document.querySelector('meta[name="csrf-token"]')?.content || '';
    const _sv = _tlsSrv();
    const params = '?' + new URLSearchParams({ ...(configFile ? { configFile } : {}), ...(_sv ? { server: _sv } : {}) }).toString();
    try {
        const res = await fetch(`/api/tls-options/${encodeURIComponent(name)}${params}`, {
            method: 'DELETE',
            headers: { 'X-Requested-With': 'fetch', 'X-CSRF-Token': token },
        });
        if (!res.ok) { showToast(await _errText(res, t('Delete failed')), 'error'); return; }
        const json = await res.json();
        if (json.ok) {
            showToast(t('TLS profile deleted'));
            refreshTlsOptionsTab();
            _dropTlsOptionsCache();
            _populateTlsOptionsSelect();
        } else {
            showToast(json.error || json.message || t('Delete failed'), 'error');
        }
    } catch(e) { showToast(_netErrText(e, t('Delete failed')), 'error'); }
}

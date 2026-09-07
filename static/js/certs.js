let _allCerts   = [];

function filterCerts() { renderCertCards(); }


function renderCertsVerdict() {
    if (!document.getElementById('certsVerdict')) return;
    if (!_allCerts.length) { _tvStrip('certsVerdict', null); return; }
    const now = Date.now();
    let critical = 0, expiring = 0, next = null;
    _allCerts.forEach(c => {
        if (!c.not_after) return;
        const exp = new Date(c.not_after);
        if (isNaN(exp)) return;
        const d = Math.ceil((exp - now) / 86400000);
        if (d < 7) critical++;
        else if (d < 30) expiring++;
        if (next === null || d < next) next = d;
    });
    const resolvers = new Set(_allCerts.map(c => c.resolver).filter(Boolean)).size;
    const flags = [{ cls: 'd-off', ic: 'ph-bold ph-shield-check', n: _allCerts.length,
                     label: _allCerts.length === 1 ? 'certificate' : 'certificates' }];
    if (critical) flags.push({ cls: 'd-bad', ic: 'ph-fill ph-warning-octagon', n: critical, label: 'under 7d' });
    if (expiring) flags.push({ cls: 'd-warn', ic: 'ph-fill ph-hourglass-high', n: expiring, label: 'under 30d' });
    if (!critical && !expiring) flags.push({ cls: 'd-on', ic: 'ph-bold ph-check', n: '', label: 'none expiring soon' });
    if (resolvers > 1) flags.push({ cls: 'd-off', ic: 'ph-bold ph-certificate', n: resolvers, label: 'resolvers' });
    _tvStrip('certsVerdict', {
        health: critical ? 'down' : expiring ? 'warn' : 'up',
        ic: critical ? 'ph-fill ph-warning-octagon' : expiring ? 'ph-fill ph-hourglass-high' : 'ph-fill ph-check-circle',
        txt: critical ? _sdNum(critical) + ' expiring within 7 days'
           : expiring ? _sdNum(expiring) + ' expiring within 30 days'
           : 'All certificates healthy',
        flags,
        meta: next !== null ? 'next expiry in <b>' + _sdNum(next) + 'd</b>' : '',
    });
}

function renderCertCards() {
    const q   = (document.getElementById('certsSearch')?.value || '').toLowerCase();
    const now = Date.now();
    const items = _allCerts.filter(cert =>
        !q || (cert.main||'').toLowerCase().includes(q) || (cert.sans||[]).some(d => d.toLowerCase().includes(q))
    );
    if (items.length === 0) {
        document.getElementById('certsContent').innerHTML =
            `<div class="text-center py-12 rounded-xl" style="color:var(--muted);border:1px solid var(--border)">No certificates match your search</div>`;
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
            </div>
            ${vals ? `<div class="tm-vals">${vals}</div>` : ''}
            <div class="tm-foot"><span class="tm-meta">expires ${_esc(expiryStr)}${extra.length ? ` · ${extra.length + 1} domains` : ''}</span>${daysLeft !== null ? `<span class="tm-cf" style="color:${expiryColor}">${daysLeft}d left</span>` : ''}</div>
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
            _populateTlsOptionsSelect();
        } else {
            showToast(json.error || json.message || 'Delete failed', 'error');
        }
    } catch(e) { showToast(_netErrText(e, 'Delete failed'), 'error'); }
}

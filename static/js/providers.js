function _tvFlag(f) {
    return '<span class="sig-flag ' + f.cls + ' lg-static" title="' + _esc(f.tip || (f.n + ' ' + f.label)) + '">'
        + '<i class="' + f.ic + '"></i>'
        + (f.n === '' ? '' : '<b>' + _sdNum(f.n) + '</b>')
        + (f.label ? '<span class="sig-fl">' + _esc(f.label) + '</span>' : '')
        + '</span>';
}

function _tvStrip(mountId, v) {
    const el = document.getElementById(mountId);
    if (!el) return;
    if (v === null) { el.innerHTML = ''; return; }
    const note = el.dataset.note || v.note || '';
    const tip = note
        ? '<span class="tm-info-btn" data-tip="' + _esc(note) + '"><i class="ph-bold ph-info"></i></span>'
        : '';
    el.innerHTML = '<div class="sig-verdict" data-health="' + (v.health || 'up') + '">'
        + '<i class="' + v.ic + ' sig-verdict-ic"></i>'
        + '<span class="sig-verdict-txt">' + _esc(v.txt) + '</span>'
        + '<span class="sig-verdict-items">' + (v.flags || []).map(_tvFlag).join('') + '</span>'
        + '<span class="sig-verdict-meta">' + (v.meta || '') + tip + '</span></div>';
}

function renderProviderVerdict(prefix, routes, mws) {
    const mountId = prefix + 'Verdict';
    if (!document.getElementById(mountId)) return;
    if (!routes || !routes.length) { _tvStrip(mountId, null); return; }
    const err = routes.filter(r => r.status && r.status !== 'enabled').length;
    const by = p => routes.filter(r => r._proto === p).length;
    const flags = [];
    const h = by('HTTP'), tcp = by('TCP'), u = by('UDP');
    if (h) flags.push({ cls: 'd-off', ic: 'ph-bold ph-globe', n: h, label: 'HTTP' });
    if (tcp) flags.push({ cls: 'd-off', ic: 'ph-bold ph-arrows-left-right', n: tcp, label: 'TCP' });
    if (u) flags.push({ cls: 'd-off', ic: 'ph-bold ph-broadcast', n: u, label: 'UDP' });
    if (err) flags.push({ cls: 'd-bad', ic: 'ph-fill ph-warning-octagon', n: err, label: t('not serving') });
    if (mws && mws.length) flags.push({ cls: 'd-off', ic: 'ph-bold ph-stack', n: mws.length,
        label: mws.length === 1 ? tc('label', 'middleware') : tc('label', 'middlewares') });
    _tvStrip(mountId, {
        health: err ? 'down' : 'up',
        ic: err ? 'ph-fill ph-warning-octagon' : 'ph-fill ph-check-circle',
        txt: err ? tn('{count} route not serving', '{count} routes not serving', err, { count: _sdNum(err) })
                 : tn('{count} route live', '{count} routes live', routes.length, { count: _sdNum(routes.length) }),
        flags,
        meta: '<b>read-only</b>',
    });
}

function renderProviderMiddlewareSection(middlewares, containerId) {
    const el = document.getElementById(containerId);
    if (!el) return;
    if (!middlewares || middlewares.length === 0) { el.innerHTML = ''; return; }
    const cards = middlewares.map(mw => {
        const name = (mw.name || '').split('@')[0];
        const type = mw.type || '';
        const st   = (mw.status || '').toLowerCase();
        const dot  = st === 'enabled' ? 'status-online' : (st === 'disabled' || st === 'error') ? 'status-offline' : 'status-unknown';
        return `<div class="tm-card tm-card-flat" style="--tm-accent:var(--purple)">
            <div class="tm-head">
                <span class="tm-ic tm-ic-tile"><i class="ph-bold ${_tmMwIcon({ yaml: type })}"></i><span class="status-dot ${dot}"></span></span>
                <div class="tm-head-txt">
                    <div class="tm-title"><span class="tm-name">${_esc(name)}</span></div>
                    ${type ? `<div class="tm-sub">${_esc(type)}</div>` : ''}
                </div>
            </div>
        </div>`;
    }).join('');
    el.innerHTML = `<div class="mt-6 pt-4" style="border-top:1px solid var(--border)">
        <div class="text-xs font-semibold uppercase tracking-wide mb-3 flex items-center gap-2" style="color:var(--muted)">
            <i class="ph-bold ph-plugs-connected"></i> ${th('Middlewares {span}', { span: tmHtml(`<span class="font-normal">(${middlewares.length})</span>`) })}
        </div>
        <div class="tm-card-grid">${cards}</div>
    </div>`;
}

function providerGridClass() {
    return 'tm-card-grid';
}

function _tmProviderCard(r, opts, ctx) {
    const { proto, name, svc, domain, isHTTP, dotCls, extUrl } = ctx;
    const glyphs = proto === 'UDP' ? ''
        : r.tls ? '<i class="ph-bold ph-lock-simple tm-glyph" style="color:var(--muted)" title="TLS"></i>'
                : `<i class="ph-bold ph-lock-simple-open tm-glyph" style="color:var(--yellow)" title="${th('No TLS')}"></i>`;

    const simpleHost = /^Host\(`[^`]+`\)(\s*\|\|\s*Host\(`[^`]+`\))*$/.test((r.rule || '').trim());
    const vals = [];
    if (isHTTP && simpleHost && domain) {
        vals.push(`<div class="tm-val tm-val-host"><i class="ph-bold ph-globe-simple"></i><span class="tm-v">${_esc(domain)}</span>${_tmCopy(domain)}</div>`);
    } else if (r.rule) {
        vals.push(`<div class="tm-val tm-val-rule"><i class="ph-bold ph-brackets-curly"></i><span class="tm-v" title="${_esc(r.rule)}">${_esc(r.rule)}</span>${_tmCopy(r.rule)}</div>`);
    }
    if (opts.target) {
        vals.push(`<div class="tm-val tm-val-target"><i class="ph-bold ph-arrow-elbow-down-right"></i><span class="tm-v">${_esc(opts.target)}</span>${_tmCopy(opts.target)}</div>`);
    }
    for (const row of (opts.rows || [])) {
        if (!row.value) continue;
        vals.push(`<div class="tm-val"><i class="ph-bold ${row.icon || 'ph-dot'}"></i><span class="tm-v" style="color:var(--muted)" title="${_esc(row.label || '')}">${_esc(row.value)}</span>${_tmCopy(row.value)}</div>`);
    }

    const meta = [
        (r.entryPoints || []).length ? `<span>${_esc((r.entryPoints || []).join(' · '))}</span>` : '',
        (r.middlewares || []).length ? `<span class="tm-mw">${(r.middlewares || []).map(mw => _esc(mw.split('@')[0])).join(' · ')}</span>` : '',
        svc ? `<span class="tm-svcname">${_esc(svc)}</span>` : '',
    ].filter(Boolean).join('<span class="tm-sep"> · </span>');

    const rail = `<span class="tm-rail tm-rail-sm" onclick="event.stopPropagation()">` +
        (extUrl ? `<a href="${_esc(extUrl)}" target="_blank" rel="noopener" class="tm-btn" title="${th('Open site')}" onclick="event.stopPropagation()"><i class="ph-bold ph-arrow-square-out"></i></a>` : '') +
        (opts.onDetailClick ? `<button type="button" class="tm-btn" title="${thc('tooltip', 'Details')}" onclick="event.stopPropagation();${opts.onDetailClick}"><i class="ph-bold ph-info"></i></button>` : '') +
        '</span>';

    return `<div class="tm-card"${opts.onDetailClick ? ` onclick="${opts.onDetailClick}"` : ''} style="--tm-accent:var(--blue)">
        <div class="tm-head">
            <span class="tm-ic-bare"><span class="status-dot ${dotCls}"></span></span>
            <div class="tm-head-txt">
                <div class="tm-title">${proto !== 'HTTP' ? `<span class="tm-proto tm-proto-${proto.toLowerCase()}">${proto}</span>` : ''}<span class="tm-name">${_esc(name)}</span>${glyphs}</div>
                ${opts.tag ? `<div class="tm-sub">${_esc(opts.tag)}</div>` : ''}
            </div>${rail}
        </div>
        ${vals.length ? `<div class="tm-vals">${vals.join('')}</div>` : ''}
        <div class="tm-foot"><span class="tm-meta">${meta}</span></div>
    </div>`;
}

function renderProviderCard(r, opts = {}) {
    const proto = (r._proto || 'HTTP').toUpperCase();
    const name  = (r.name  || '').split('@')[0];
    const svc   = (r.service || '').split('@')[0];

    const protoBadge = proto === 'TCP'  ? `<span class="badge badge-tcp">TCP</span>`
                     : proto === 'UDP'  ? `<span class="badge badge-udp">UDP</span>`
                     :                   `<span class="badge badge-http">HTTP</span>`;

    const tlsBadge = r.tls ? `<span class="badge badge-green" style="font-size:9px"><i class="ph-bold ph-lock"></i> TLS</span>` : '';

    const st = (r.status || '').toLowerCase();
    const dotCls = st === 'enabled' ? 'status-online' : (st === 'disabled' || st === 'error') ? 'status-offline' : 'status-unknown';

    const hostMatch = (r.rule || '').match(/Host\(`([^`]+)`\)/);
    const domain    = hostMatch ? hostMatch[1] : null;
    const isHTTP    = proto === 'HTTP';

    const extUrl = (domain && isHTTP && !domain.includes('{') && !domain.includes('*')) ? 'https://' + domain : '';

    return _tmProviderCard(r, opts, { proto, name, svc, domain, isHTTP, dotCls, extUrl });
}

let _allEtcdRoutes = [];
let _etcdFilter    = 'all';

async function refreshEtcdTab() {
    const container = document.getElementById('etcdContent');
    container.innerHTML = `<div class="text-center py-16" style="color:var(--muted)"><i class="ph-light ph-spinner-gap text-4xl block mb-3 animate-spin opacity-40"></i><p>${th('Loading etcd routes...')}</p></div>`;

    try {
        const [routerRes, mwRes] = await Promise.all([
            agentFetch('/api/traefik/routers').then(r => r.json()),
            agentFetch('/api/traefik/middlewares').then(r => r.json()).catch(() => ({})),
        ]);

        const http = (routerRes.http || []).map(r => ({ ...r, _proto: 'HTTP' }));
        const tcp  = (routerRes.tcp  || []).map(r => ({ ...r, _proto: 'TCP'  }));
        const udp  = (routerRes.udp  || []).map(r => ({ ...r, _proto: 'UDP'  }));
        const all  = [...http, ...tcp, ...udp];

        const getProvider = r => r.provider || (r.name || '').split('@')[1] || '';

        _allEtcdRoutes = all
            .filter(r => getProvider(r) === 'etcd')
            .sort((a, b) => (a.name || '').localeCompare(b.name || ''));

        if (all.length === 0) {
            container.innerHTML = `<div class="text-center py-16 rounded-xl" style="color:var(--muted);border:1px solid var(--border)"><i class="ph-light ph-cloud-slash text-5xl block mb-3 opacity-30"></i><p class="font-medium">${th('Traefik API not reachable')}</p><p class="text-xs mt-1">${th('Configure {traefik_api_url} in Settings', { traefik_api_url: tmHtml(`<code class="font-mono">TRAEFIK_API_URL</code>`) })}</p></div>`;
            return;
        }
        if (_allEtcdRoutes.length === 0) {
            container.innerHTML = `<div class="text-center py-16 rounded-xl" style="color:var(--muted);border:1px solid var(--border)"><i class="ph-light ph-database text-5xl block mb-3 opacity-30"></i><p class="font-medium">${th('No etcd routes found')}</p><p class="text-xs mt-1">${th('Routes stored in etcd will appear here')}</p></div>`;
            return;
        }

        const _mws = [...(mwRes.http || []), ...(mwRes.tcp || [])].filter(m => { const mwProv = m.provider || (m.name||'').split('@')[1] || ''; return mwProv === 'etcd'; });
        renderProviderVerdict('etcd', _allEtcdRoutes, _mws);
        renderProviderMiddlewareSection(_mws, 'etcdMiddlewares');
        setTabCount('etcd', _allEtcdRoutes.length);
        renderEtcdRoutes();
    } catch(e) {
        container.innerHTML = `<div class="text-center py-16 rounded-xl" style="color:var(--muted);border:1px solid var(--border)"><i class="ph-light ph-cloud-slash text-5xl block mb-3 opacity-30"></i><p class="font-medium">${th('Traefik API not reachable')}</p></div>`;
    }
}

function filterEtcd(f) {
    if (f) {
        _etcdFilter = f;
        ['all', 'http', 'tcp', 'udp'].forEach(k => {
            const btn = document.getElementById('et-' + k);
            if (btn) btn.classList.toggle('active-http', k === f);
        });
    }
    renderEtcdRoutes();
}

function renderEtcdRoutes() {
    const search = (document.getElementById('etcdSearch')?.value || '').toLowerCase();
    const items  = _allEtcdRoutes.filter(r => {
        if (_etcdFilter !== 'all' && r._proto.toLowerCase() !== _etcdFilter) return false;
        if (search && !(r.name || '').toLowerCase().includes(search) && !(r.rule || '').toLowerCase().includes(search)) return false;
        return true;
    });

    const statusDot = r => {
        const st = (r.status || '').toLowerCase();
        if (st === 'enabled')  return `<span class="status-dot status-online"></span>`;
        if (st === 'disabled' || st === 'error') return `<span class="status-dot status-offline"></span>`;
        return `<span class="status-dot status-unknown"></span>`;
    };

    const protoBadge = r => {
        if (r._proto === 'HTTP') return `<span class="badge badge-http" style="font-size:9px">HTTP</span>`;
        if (r._proto === 'TCP')  return `<span class="badge badge-tcp"  style="font-size:9px">TCP</span>`;
        return `<span class="badge badge-udp" style="font-size:9px">UDP</span>`;
    };

    const shortName = r => (r.name || '').split('@')[0];

    const tlsBadge = r => r.tls
        ? `<span class="badge badge-green" style="font-size:9px"><i class="ph-bold ph-lock"></i> TLS</span>`
        : '';

    const epBadges = r => (r.entryPoints || [])
        .map(ep => `<span class="badge badge-muted" style="font-size:9px">${ep}</span>`)
        .join(' ');

    if (items.length === 0) {
        document.getElementById('etcdContent').innerHTML =
            `<div class="text-center py-12 rounded-xl" style="color:var(--muted);border:1px solid var(--border)">${th('No routes match filter')}</div>`;
        return;
    }

    const cards = items.map(r => {
        const globalIdx = _allEtcdRoutes.indexOf(r);
        return renderProviderCard(r, { onDetailClick: `openEtcdRouteDetail(${globalIdx})` });
    }).join('');

    document.getElementById('etcdContent').innerHTML =
        `<div class="${providerGridClass()}">${cards}</div>`;
}

async function openEtcdRouteDetail(idx) {
    const r = _allEtcdRoutes[idx];
    if (!r) return;

    document.getElementById('detailEditBtn').style.display = 'none';

    const badge = `<span class="d-flat d-off ml-2"><i class="ph-bold ph-database"></i> etcd</span>`;

    const appData = {
        id:           (r.name || '').split('@')[0],
        name:         (r.name || '').split('@')[0],
        rule:         r.rule || '',
        service_name: (r.service || '').split('@')[0],
        target:       'N/A',
        middlewares:  r.middlewares || [],
        entryPoints:  r.entryPoints || [],
        protocol:     r._proto.toLowerCase(),
    };

    await openRouteDetail(appData.name, appData.protocol, appData);

    document.getElementById('detailEditBtn').style.display = 'none';
    document.getElementById('detailTitle').insertAdjacentHTML('afterend', badge);
}

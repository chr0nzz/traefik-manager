let _allDockerRoutes = [];
let _dockerFilter    = 'all';

async function refreshDockerTab() {
    const container = document.getElementById('dockerContent');
    container.innerHTML = `<div class="text-center py-16" style="color:var(--muted)"><i class="ph-light ph-spinner-gap text-4xl block mb-3 animate-spin opacity-40"></i><p>${th('Loading docker routes…')}</p></div>`;

    try {
        const [routerRes, svcRes, mwRes] = await Promise.all([
            agentFetch('/api/traefik/routers').then(r => r.json()),
            agentFetch('/api/traefik/services').then(r => r.json()).catch(() => ({})),
            agentFetch('/api/traefik/middlewares').then(r => r.json()).catch(() => ({})),
        ]);

        const svcMap = {};
        [...(svcRes.http || []), ...(svcRes.tcp || [])].forEach(s => {
            const nameParts = (s.name || '').split('@');
            const svcProvider = s.provider || nameParts[1] || '';
            if (svcProvider === 'docker') {
                const servers = s.loadBalancer?.servers || [];
                const url = servers[0]?.url || servers[0]?.address || null;
                const statusKeys = Object.keys(s.serverStatus || {});
                const bareKey = nameParts[0];
                svcMap[bareKey] = { url, containerAddr: statusKeys[0] || url };
                svcMap[s.name]  = { url, containerAddr: statusKeys[0] || url };
            }
        });

        const http = (routerRes.http || []).map(r => ({ ...r, _proto: 'HTTP' }));
        const tcp  = (routerRes.tcp  || []).map(r => ({ ...r, _proto: 'TCP'  }));
        const udp  = (routerRes.udp  || []).map(r => ({ ...r, _proto: 'UDP'  }));
        const all  = [...http, ...tcp, ...udp];

        const getProvider = r => r.provider || (r.name || '').split('@')[1] || '';

        _allDockerRoutes = all
            .filter(r => getProvider(r) === 'docker')
            .map(r => {
                const svcFull  = r.service || '';
                const svcBare  = svcFull.split('@')[0];
                const svcInfo  = svcMap[svcBare] || svcMap[svcFull] || null;
                return { ...r, _svcInfo: svcInfo };
            })
            .sort((a,b) => (a.name||'').localeCompare(b.name||''));

        if (all.length === 0) {
            container.innerHTML = `<div class="text-center py-16 rounded-xl" style="color:var(--muted);border:1px solid var(--border)"><i class="ph-light ph-cloud-slash text-5xl block mb-3 opacity-30"></i><p class="font-medium">${th('Traefik API not reachable')}</p><p class="text-xs mt-1">${th('Configure {traefik_api_url} in Settings', { traefik_api_url: tmHtml(`<code class="font-mono">TRAEFIK_API_URL</code>`) })}</p></div>`;
            return;
        }
        if (_allDockerRoutes.length === 0) {
            container.innerHTML = `<div class="text-center py-16 rounded-xl" style="color:var(--muted);border:1px solid var(--border)"><i class="ph-light ph-cube text-5xl block mb-3 opacity-30"></i><p class="font-medium">${th('No Docker routes found')}</p><p class="text-xs mt-1">${th('Routes discovered via Docker labels will appear here automatically')}</p></div>`;
            return;
        }

        setTabCount('docker', _allDockerRoutes.length);
        const dockerMws = [...(mwRes.http || []), ...(mwRes.tcp || [])].filter(m => (m.provider || (m.name||'').split('@')[1]) === 'docker');
        renderProviderVerdict('docker', _allDockerRoutes, dockerMws);
        renderProviderMiddlewareSection(dockerMws, 'dockerMiddlewares');
        renderDockerRoutes();
    } catch(e) {
        container.innerHTML = `<div class="text-center py-16 rounded-xl" style="color:var(--muted);border:1px solid var(--border)"><i class="ph-light ph-cloud-slash text-5xl block mb-3 opacity-30"></i><p class="font-medium">${th('Traefik API not reachable')}</p></div>`;
    }
}

function filterDocker(f) {
    if (f) {
        _dockerFilter = f;
        ['all','http','tcp','udp'].forEach(k => {
            const btn = document.getElementById('dk-'+k);
            if (btn) btn.classList.toggle('active-http', k === f);
        });
    }
    renderDockerRoutes();
}

function renderDockerRoutes() {
    const search = (document.getElementById('dockerSearch')?.value || '').toLowerCase();
    const items  = _allDockerRoutes.filter(r => {
        if (_dockerFilter !== 'all' && r._proto.toLowerCase() !== _dockerFilter) return false;
        if (search && !(r.name||'').toLowerCase().includes(search) && !(r.rule||'').toLowerCase().includes(search)) return false;
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

    const tlsBadge  = r => r.tls
        ? `<span class="badge badge-green" style="font-size:9px"><i class="ph-bold ph-lock"></i> TLS</span>`
        : '';

    const epBadges  = r => (r.entryPoints || [])
        .map(ep => `<span class="badge badge-muted" style="font-size:9px">${ep}</span>`)
        .join(' ');

    if (items.length === 0) {
        document.getElementById('dockerContent').innerHTML =
            `<div class="text-center py-12 rounded-xl" style="color:var(--muted);border:1px solid var(--border)">${th('No routes match filter')}</div>`;
        return;
    }

    const cards = items.map((r, i) => {
        const globalIdx = _allDockerRoutes.indexOf(r);
        const target = r._svcInfo?.containerAddr || r._svcInfo?.url || null;
        const showContainer = r._svcInfo?.containerAddr && r._svcInfo?.url && r._svcInfo.containerAddr !== r._svcInfo.url;
        return renderProviderCard(r, {
            onDetailClick: `openDockerRouteDetail(${globalIdx})`,
            target,
            rows: showContainer ? [{ label: tc('label', 'Container'), value: r._svcInfo.containerAddr, icon: 'ph-cube' }] : [],
        });
    }).join('');

    document.getElementById('dockerContent').innerHTML =
        `<div class="${providerGridClass()}">${cards}</div>`;
}

async function openDockerRouteDetail(idx) {
    const r = _allDockerRoutes[idx];
    if (!r) return;

    document.getElementById('detailEditBtn').style.display = 'none';

    const dockerBadge = `<span class="d-flat d-off ml-2"><i class="ph-bold ph-cube"></i> docker</span>`;

    let rawLabels = null;
    try {
        const proto = (r._proto || 'HTTP').toLowerCase();
        const routerName = encodeURIComponent(r.name || '');
        const detail = await agentFetch(`/api/traefik/router/${proto}/${routerName}`).then(res => res.json());
        if (detail && detail.provider === 'docker') {
            rawLabels = detail.labels || null;
        }
    } catch(e) { /* labels unavailable */ }

    const svcRaw  = r.service || '';
    const appData = {
        id:             (r.name || '').split('@')[0],
        name:           (r.name || '').split('@')[0],
        rule:           r.rule || '',
        service_name:   svcRaw.split('@')[0],
        target:         r._svcInfo?.url || 'N/A',
        containerAddr:  r._svcInfo?.containerAddr || null,
        dockerLabels:   rawLabels,
        middlewares:    r.middlewares || [],
        entryPoints:    r.entryPoints || [],
        protocol:       r._proto.toLowerCase(),
    };

    await openRouteDetail(appData.name, appData.protocol, appData);

    document.getElementById('detailEditBtn').style.display = 'none';

    document.getElementById('detailTitle').insertAdjacentHTML('afterend', dockerBadge);
}

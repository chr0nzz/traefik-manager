let _allKubernetesRoutes = [];
let _kubernetesFilter    = 'all';

const _K8S_PROVIDERS = new Set(['kubernetescrd', 'kubernetes', 'kubernetesgateway']);

async function refreshKubernetesTab() {
    const container = document.getElementById('kubernetesContent');
    container.innerHTML = `<div class="text-center py-16" style="color:var(--muted)"><i class="ph-light ph-spinner-gap text-4xl block mb-3 animate-spin opacity-40"></i><p>${th('Loading Kubernetes routes...')}</p></div>`;

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

        _allKubernetesRoutes = all
            .filter(r => _K8S_PROVIDERS.has(getProvider(r)))
            .sort((a, b) => (a.name || '').localeCompare(b.name || ''));

        if (all.length === 0) {
            container.innerHTML = `<div class="text-center py-16 rounded-xl" style="color:var(--muted);border:1px solid var(--border)"><i class="ph-light ph-cloud-slash text-5xl block mb-3 opacity-30"></i><p class="font-medium">${th('Traefik API not reachable')}</p><p class="text-xs mt-1">${th('Configure {traefik_api_url} in Settings', { traefik_api_url: tmHtml(`<code class="font-mono">TRAEFIK_API_URL</code>`) })}</p></div>`;
            return;
        }
        if (_allKubernetesRoutes.length === 0) {
            container.innerHTML = `<div class="text-center py-16 rounded-xl" style="color:var(--muted);border:1px solid var(--border)"><i class="ph-light ph-circles-three text-5xl block mb-3 opacity-30"></i><p class="font-medium">${th('No Kubernetes routes found')}</p><p class="text-xs mt-1">${th('Routes discovered via Kubernetes CRD, Ingress, or Gateway API will appear here')}</p></div>`;
            return;
        }

        const _mws = [...(mwRes.http || []), ...(mwRes.tcp || [])].filter(m => { const mwProv = m.provider || (m.name||'').split('@')[1] || ''; return new Set(['kubernetescrd','kubernetes','kubernetesgateway']).has(mwProv); });
        renderProviderVerdict('kubernetes', _allKubernetesRoutes, _mws);
        renderProviderMiddlewareSection(_mws, 'kubernetesMiddlewares');
        setTabCount('kubernetes', _allKubernetesRoutes.length);
        renderKubernetesRoutes();
    } catch(e) {
        container.innerHTML = `<div class="text-center py-16 rounded-xl" style="color:var(--muted);border:1px solid var(--border)"><i class="ph-light ph-cloud-slash text-5xl block mb-3 opacity-30"></i><p class="font-medium">${th('Traefik API not reachable')}</p></div>`;
    }
}

function filterKubernetes(f) {
    if (f) {
        _kubernetesFilter = f;
        ['all', 'http', 'tcp', 'udp'].forEach(k => {
            const btn = document.getElementById('k8s-' + k);
            if (btn) btn.classList.toggle('active-http', k === f);
        });
    }
    renderKubernetesRoutes();
}

function renderKubernetesRoutes() {
    const search = (document.getElementById('kubernetesSearch')?.value || '').toLowerCase();
    const items  = _allKubernetesRoutes.filter(r => {
        if (_kubernetesFilter !== 'all' && r._proto.toLowerCase() !== _kubernetesFilter) return false;
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

    const providerKind = r => {
        const p = r.provider || (r.name || '').split('@')[1] || '';
        return { kubernetescrd: 'CRD', kubernetes: 'Ingress', kubernetesgateway: 'Gateway' }[p] || p;
    };
    const providerBadge = r => `<span class="badge badge-muted" style="font-size:9px">${providerKind(r)}</span>`;

    const shortName = r => (r.name || '').split('@')[0];

    const tlsBadge = r => r.tls
        ? `<span class="badge badge-green" style="font-size:9px"><i class="ph-bold ph-lock"></i> TLS</span>`
        : '';

    const epBadges = r => (r.entryPoints || [])
        .map(ep => `<span class="badge badge-muted" style="font-size:9px">${ep}</span>`)
        .join(' ');

    const namespaceBadge = r => r.namespace
        ? `<span class="badge badge-muted" style="font-size:9px"><i class="ph-bold ph-folder-simple"></i> ${r.namespace}</span>`
        : '';

    if (items.length === 0) {
        document.getElementById('kubernetesContent').innerHTML =
            `<div class="text-center py-12 rounded-xl" style="color:var(--muted);border:1px solid var(--border)">${th('No routes match filter')}</div>`;
        return;
    }

    const cards = items.map(r => {
        const globalIdx = _allKubernetesRoutes.indexOf(r);
        return renderProviderCard(r, {
            onDetailClick: `openKubernetesRouteDetail(${globalIdx})`,
            extraBadges:   providerBadge(r),
            tag:           providerKind(r),
            rows:          r.namespace ? [{ label: tc('label', 'Namespace'), value: r.namespace, icon: 'ph-folder-simple' }] : [],
        });
    }).join('');

    document.getElementById('kubernetesContent').innerHTML =
        `<div class="${providerGridClass()}">${cards}</div>`;
}

async function openKubernetesRouteDetail(idx) {
    const r = _allKubernetesRoutes[idx];
    if (!r) return;

    document.getElementById('detailEditBtn').style.display = 'none';

    const provider = r.provider || (r.name || '').split('@')[1] || 'kubernetes';
    const labels = { kubernetescrd: 'CRD', kubernetes: 'Ingress', kubernetesgateway: 'Gateway' };
    const providerLabel = labels[provider] || provider;
    const k8sBadge = `<span class="d-flat d-off ml-2"><i class="ph-bold ph-circles-three"></i> ${th('k8s/{providerLabel}', { providerLabel: tmHtml(providerLabel) })}</span>`;

    const svcRaw  = r.service || '';
    const appData = {
        id:           (r.name || '').split('@')[0],
        name:         (r.name || '').split('@')[0],
        rule:         r.rule || '',
        service_name: svcRaw.split('@')[0],
        target:       'N/A',
        middlewares:  r.middlewares || [],
        entryPoints:  r.entryPoints || [],
        protocol:     r._proto.toLowerCase(),
    };

    await openRouteDetail(appData.name, appData.protocol, appData);

    document.getElementById('detailEditBtn').style.display = 'none';

    document.getElementById('detailTitle').insertAdjacentHTML('afterend', k8sBadge);
}

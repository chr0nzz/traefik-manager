let _allFileExternalRoutes = [];
let _fileExternalFilter    = 'all';

function _fileExternalEmptyState(managedFileRoutes) {
    const title = managedFileRoutes
        ? 'Every file provider route is managed here'
        : 'Traefik reports no file provider routes';
    const why = managedFileRoutes
        ? `Traefik reports ${managedFileRoutes} file provider route${managedFileRoutes === 1 ? '' : 's'}, all from a file Traefik Manager manages, so they are on the Routes tab.`
        : 'Traefik is not loading any routes through its file provider.';
    const what = 'This tab lists routes from other files your file provider loads, such as the rest of a conf.d directory. They are shown read-only.';
    return `<div class="text-center py-16 rounded-xl" style="color:var(--muted);border:1px solid var(--border)"><i class="ph-light ph-file-text text-5xl block mb-3 opacity-30"></i><p class="font-medium">${title}</p><p class="text-xs mt-1">${why}</p><p class="text-xs mt-1">${what}</p>${managedFileRoutes ? `<button type="button" onclick="switchTab('services')" class="btn-secondary text-xs mt-3">Open Routes</button>` : ''}</div>`;
}

async function refreshFileExternalTab() {
    const container = document.getElementById('fileExternalContent');
    container.innerHTML = `<div class="text-center py-16" style="color:var(--muted)"><i class="ph-light ph-spinner-gap text-4xl block mb-3 animate-spin opacity-40"></i><p>Loading file provider routes...</p></div>`;

    try {
        const [routerRes, managedNames, mwRes] = await Promise.all([
            agentFetch('/api/traefik/routers').then(r => r.json()),
            fetch('/api/manager/router-names' + (_activeAgent ? '?server=' + encodeURIComponent(_activeAgent.id) : '')).then(r => r.json()),
            agentFetch('/api/traefik/middlewares').then(r => r.json()).catch(() => ({})),
        ]);

        const managedSet = new Set(managedNames);

        const http = (routerRes.http || []).map(r => ({ ...r, _proto: 'HTTP' }));
        const tcp  = (routerRes.tcp  || []).map(r => ({ ...r, _proto: 'TCP'  }));
        const udp  = (routerRes.udp  || []).map(r => ({ ...r, _proto: 'UDP'  }));
        const all  = [...http, ...tcp, ...udp];

        const getProvider = r => r.provider || (r.name || '').split('@')[1] || '';
        const shortName   = r => (r.name || '').split('@')[0];

        const fileRoutes = all.filter(r => getProvider(r) === 'file');
        _allFileExternalRoutes = fileRoutes
            .filter(r => !managedSet.has(shortName(r)))
            .sort((a, b) => (a.name || '').localeCompare(b.name || ''));

        if (all.length === 0) {
            container.innerHTML = `<div class="text-center py-16 rounded-xl" style="color:var(--muted);border:1px solid var(--border)"><i class="ph-light ph-cloud-slash text-5xl block mb-3 opacity-30"></i><p class="font-medium">Traefik API not reachable</p><p class="text-xs mt-1">Configure <code class="font-mono">TRAEFIK_API_URL</code> in Settings</p></div>`;
            return;
        }
        if (_allFileExternalRoutes.length === 0) {
            setTabCount('file_external', 0);
            container.innerHTML = _fileExternalEmptyState(fileRoutes.length);
            return;
        }

        const _mws = [...(mwRes.http || []), ...(mwRes.tcp || [])].filter(m => { const mwProv = m.provider || (m.name||'').split('@')[1] || ''; return mwProv === 'file'; });
        renderProviderVerdict('fileExternal', _allFileExternalRoutes, _mws);
        renderProviderMiddlewareSection(_mws, 'fileExternalMiddlewares');
        setTabCount('file_external', _allFileExternalRoutes.length);
        renderFileExternalRoutes();
    } catch(e) {
        container.innerHTML = `<div class="text-center py-16 rounded-xl" style="color:var(--muted);border:1px solid var(--border)"><i class="ph-light ph-cloud-slash text-5xl block mb-3 opacity-30"></i><p class="font-medium">Traefik API not reachable</p></div>`;
    }
}

function filterFileExternal(f) {
    if (f) {
        _fileExternalFilter = f;
        ['all', 'http', 'tcp', 'udp'].forEach(k => {
            const btn = document.getElementById('fe-' + k);
            if (btn) btn.classList.toggle('active-http', k === f);
        });
    }
    renderFileExternalRoutes();
}

function renderFileExternalRoutes() {
    const search = (document.getElementById('fileExternalSearch')?.value || '').toLowerCase();
    const items  = _allFileExternalRoutes.filter(r => {
        if (_fileExternalFilter !== 'all' && r._proto.toLowerCase() !== _fileExternalFilter) return false;
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
        document.getElementById('fileExternalContent').innerHTML =
            `<div class="text-center py-12 rounded-xl" style="color:var(--muted);border:1px solid var(--border)">No routes match filter</div>`;
        return;
    }

    const cards = items.map(r => {
        const globalIdx = _allFileExternalRoutes.indexOf(r);
        return renderProviderCard(r, { onDetailClick: `openFileExternalRouteDetail(${globalIdx})` });
    }).join('');

    document.getElementById('fileExternalContent').innerHTML =
        `<div class="${providerGridClass()}">${cards}</div>`;
}

async function openFileExternalRouteDetail(idx) {
    const r = _allFileExternalRoutes[idx];
    if (!r) return;

    document.getElementById('detailEditBtn').style.display = 'none';

    const badge = `<span class="d-flat d-off ml-2"><i class="ph-bold ph-file-text"></i> file provider</span>`;

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

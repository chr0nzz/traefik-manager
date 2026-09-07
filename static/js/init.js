document.querySelectorAll('.toast-item').forEach(t => {
    setTimeout(() => {
        t.style.animation = 'slideOut 0.3s ease forwards';
        setTimeout(() => t.remove(), 300);
    }, 5000);
});

window._showRouteIcons = tmPref('showRouteIcons');
_tmAdoptLocalPrefs();
_tmSyncViewIcons();
document.addEventListener('mousedown', e => { _backdropMd = e.target; });

document.addEventListener('click', () => _closeRouteMenu());

document.addEventListener('click', e => {
    if (!e.target.closest('.live-dd')) {
        document.querySelectorAll('.live-dd-menu.open').forEach(m => m.classList.remove('open'));
        document.querySelectorAll('.live-dd-btn-inner.open').forEach(b => b.classList.remove('open'));
    }
});

document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
        if (_closeTopModal()) return;
        closeRouteDetail();
        closeMwDetail();
        closeSvcDetail();
        closePluginDetail();
        if (_shortcutsPanelOpen) { _shortcutsPanelOpen = false; document.getElementById('shortcutsPanel')?.classList.remove('open'); const b = document.getElementById('shortcutsBellBtn'); if (b) b.style.color = ''; }
    }
    if (_isTyping() || e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.shiftKey) {
        switch (e.key) {
            case 'N': e.preventDefault(); openModal(); break;
            case 'M': e.preventDefault(); openMwModal(); break;
            case 'F': {
                const el = document.querySelector('.tab-content.active input[type="search"], .tab-content.active input[type="text"]');
                if (el) { e.preventDefault(); el.focus(); }
                break;
            }
            case 'R': e.preventDefault(); switchTab('services'); break;
            case 'W': e.preventDefault(); switchTab('middlewares'); break;
            case 'S': e.preventDefault(); switchTab('live'); break;
            case 'L': e.preventDefault(); switchTab('logs'); break;
            case 'X': e.preventDefault(); openStaticYamlPopoutFromShortcut(); break;
            case 'P': e.preventDefault(); openSettingsModal(); break;
            case 'D': {
                if (_tabVisible('dashboard')) { e.preventDefault(); switchTab('dashboard'); }
                break;
            }
            case 'A': {
                if (!_agentList.length) break;
                e.preventDefault();
                const order = [null, ..._agentList.map(a => a.id)];
                const cur   = _activeAgent ? order.indexOf(_activeAgent.id) : 0;
                switchServer(order[(cur + 1) % order.length]);
                break;
            }
            case '?': e.preventDefault(); toggleShortcutsPanel(); break;
        }
    }
});

document.addEventListener('click', e => {
    if (_shortcutsPanelOpen && !e.target.closest('#shortcutsPanel') && !e.target.closest('.shortcuts-btn-wrap')) {
        _shortcutsPanelOpen = false;
        document.getElementById('shortcutsPanel')?.classList.remove('open');
        const b = document.getElementById('shortcutsBellBtn');
        if (b) b.style.color = '';
    }
});

(function() {
    const saved = localStorage.getItem('tm-theme') || window.TM_DEFAULT_THEME || 'dark';
    applyTheme(saved);
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
        if ((localStorage.getItem('tm-theme') || window.TM_DEFAULT_THEME) === 'system') applyTheme('system');
    });
})();

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', _initAutofillGuard);
else _initAutofillGuard();

if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register(tmUrl('/static/sw.js'), { scope: tmUrl('/static/') })
            .then(reg => console.log('SW registered:', reg.scope))
            .catch(err => console.warn('SW registration failed:', err));
    });
}

window.addEventListener('beforeinstallprompt', e => {
    e.preventDefault();
    _pwaInstallPrompt = e;
    document.getElementById('pwaInstallBtn')?.classList.remove('hidden');
    });

window.addEventListener('appinstalled', () => {
    _pwaInstallPrompt = null;
    document.getElementById('pwaInstallBtn')?.classList.add('hidden');
        showToast('Traefik Manager installed as app!', 'success');
});

(async () => {
    try {
        const res  = await fetch('/api/settings');
        const data = await res.json();
        const tabs = data.visible_tabs || {};
        _localTabsCache = tabs;
        applyTabVisibility(tabs);
        if (tabs.dashboard) switchTab('dashboard');
    } catch(e) {
        applyTabVisibility({});
    }
    if (typeof applyUiPrefs === 'function') applyUiPrefs();
    if (typeof _applyDocsLinkVisibility === 'function') _applyDocsLinkVisibility();
    _initMobileFilterBars();
    const _storedAgentId = localStorage.getItem('tm_active_agent');
    if (!_storedAgentId) refreshRoutes();
    loadOverviewStats();
    checkManagerVersion();
    fetchNotifications();
    fetch('/api/agents').then(r => r.json()).then(d => {
        const agents = d.agents || [];
        _updateServerSwitcherList(agents);
        if (_storedAgentId && agents.some(a => a.id === _storedAgentId)) {
            switchServer(_storedAgentId);
        } else if (_storedAgentId) {
            localStorage.removeItem('tm_active_agent');
            refreshRoutes();
        }
    }).catch(() => { if (_storedAgentId) refreshRoutes(); });
    initNavOverflow();
    if (typeof refreshStaticTabAvailability === 'function') refreshStaticTabAvailability();
    window.addEventListener('resize', () => { if (window.innerWidth >= 768) closeSideNavDrawer(); });
    document.addEventListener('keydown', e => { if (e.key === 'Escape') closeSideNavDrawer(); });
    if (typeof refreshStorageBanner === 'function') {
        refreshStorageBanner();
        setInterval(refreshStorageBanner, 300000);
    }
    setInterval(fetchNotifications, 60000);
    setInterval(() => { if (typeof window._rhPoll === 'function') window._rhPoll(); }, 60000);
})();

document.addEventListener('click', e => {
    if (_notifPanelOpen && !e.target.closest('#notifBellWrap') && !e.target.closest('#notifPanel')) {
        _notifPanelOpen = false;
        document.getElementById('notifPanel')?.classList.remove('open');
        const btn  = document.getElementById('notifBellBtn');
        if (btn)  btn.style.color  = '';
        markNotifsRead();
    }
});

if (document.getElementById('toastContainer') && document.getElementById('toastContainer').children.length > 0) {
    setTimeout(loadOverviewStats, 2000);
    setTimeout(loadOverviewStats, 5000);
}

placeStatCards();

watchTabBarForSideNav();
buildSideNav();
_initDetailPanelSizers();

(() => {
    const nav = document.querySelector('nav.sticky') || document.querySelector('nav');
    if (!nav) return;
    const banner = document.getElementById('noAuthBanner');
    const h = nav.offsetHeight + (banner ? banner.offsetHeight : 0);
    document.documentElement.style.setProperty('--tm-nav-h', h + 'px');
})();

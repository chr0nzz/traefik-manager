import puppeteer from 'puppeteer';
const BASE = 'http://tmshot-app:5000';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const browser = await puppeteer.launch({ args: ['--no-sandbox', '--disable-dev-shm-usage', '--force-color-profile=srgb'] });
const missing = [];

async function capture(theme) {
    const ctx  = await browser.createBrowserContext();
    const page = await ctx.newPage();
    await page.setViewport({ width: 1920, height: 1080, deviceScaleFactor: 2 });
    const shot = async name => { await sleep(600); await page.screenshot({ path: `/out/${theme}/${name}.png` }); console.log(`${theme}/${name}`); };
    const js = code => page.evaluate(code);
    const tab = async (t, ms=1800) => { await js(`switchTab('${t}')`); await sleep(ms); };

    await page.goto(BASE, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await js(`localStorage.setItem('tm-theme', '${theme}'); localStorage.setItem('tm-static-setup-v1', '1');`);
    await page.goto(BASE, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.goto(BASE, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await sleep(4500);
    await js(`document.querySelectorAll('body > div[style*="--red"]').forEach(b => b.remove())`);
    await js(`fetch('/api/settings/ui', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'fetch', ..._csrfHeaders() }, body: JSON.stringify({ ui_prefs: { layoutMode: 'modern', statBarScope: 'all' } }) })`);
    await js(`tmSetPref('layoutMode', 'modern'); tmSetPref('statBarScope', 'all'); applyUiPrefs();`);
    await sleep(1200);

    await tab('services');
    await shot('routes-cards');
    await js(`toggleRouteView()`); await sleep(900); await shot('routes-list'); await js(`toggleRouteView()`); await sleep(500);
    await js(`openModal()`); await sleep(900);
    await js(`document.getElementById('serviceName').value = 'jellyfin'; document.getElementById('subdomain').value = 'jellyfin';`);
    await shot('routes-add-http');
    await js(`setProtocol('tcp')`); await sleep(500); await shot('routes-add-tcp');
    await js(`setProtocol('udp')`); await sleep(500); await shot('routes-add-udp');
    await js(`setProtocol('http'); setServiceRefMode('http', true)`); await sleep(600);
    await js(`_populateServiceRefSelect('http', 'jellyfin-service')`); await sleep(1200);
    await shot('routes-add-service');
    await js(`setServiceRefMode('http', false); closeModal()`);

    await tab('middlewares');
    await shot('middlewares-cards');
    await js(`toggleMwView()`); await sleep(700); await shot('middlewares-list'); await js(`toggleMwView()`); await sleep(400);
    await js(`openMwModal()`); await sleep(900); await shot('middlewares-add');
    await js(`closeMwModal()`); await sleep(500);

    await tab('live', 2500);
    await shot('services-cards');
    await js(`toggleSvcView()`); await sleep(700); await shot('services-list'); await js(`toggleSvcView()`); await sleep(400);
    await js(`_openServiceByName('jellyfin-service')`); await sleep(1100); await shot('services-detail');
    await js(`closeSvcDetail()`); await sleep(400);
    await js(`openServiceModal()`); await sleep(1100);
    await js(`(() => {
        const name = document.getElementById('svcName');
        if (name) name.value = 'media-pool';
        const type = document.getElementById('svcType');
        if (type) { type.value = 'weighted'; if (typeof _svcTypeChanged === 'function') _svcTypeChanged(); }
    })()`);
    await sleep(500);
    await js(`addServiceRow()`); await sleep(700); await shot('services-add');
    await js(`closeServiceModal()`); await sleep(500);
    const svcIdx = await js(`_allServices.findIndex(s => (s.name || '').split('@')[0] === 'jellyfin-service')`);
    if (svcIdx >= 0) {
        await js(`openServiceModal(_allServices[${svcIdx}])`); await sleep(1200); await shot('services-edit');
        await js(`closeServiceModal()`); await sleep(500);
    } else {
        missing.push(`${theme}/services-edit: jellyfin-service is not in the list`);
    }

    await tab('dashboard', 4500);
    await shot('dashboard');
    await tab('routemap', 2500);
    await shot('route-map');
    await tab('certs');
    await shot('certs');
    const bulk = await js(`(() => {
        if (typeof toggleCertBulkMode !== 'function' || !_certCanDelete()) return 0;
        if (!_certBulk) toggleCertBulkMode();
        selectUnusedCerts();
        if (_certPicked.size < 2) _allCerts.slice(0, 2).forEach(c => toggleCertPick(_certKey(c)));
        renderCertCards();
        return _certPicked.size;
    })()`);
    if (bulk) {
        await sleep(900);
        await shot('certs-select');
        await js(`(() => { bulkRemoveCerts(); return 1; })()`); await sleep(1600);
        await js(`(() => {
            const i = document.getElementById('customConfirmType');
            const w = document.getElementById('customConfirmWord');
            if (i && w) { i.value = w.textContent; i.dispatchEvent(new Event('input', { bubbles: true })); }
        })()`);
        await shot('certs-remove');
        await js(`document.getElementById('customConfirmCancel')?.click()`); await sleep(600);
        await js(`if (_certBulk) toggleCertBulkMode()`); await sleep(500);
    } else {
        missing.push(`${theme}/certs-select and certs-remove: certificate removal is unavailable`);
    }
    await js(`if (typeof _visibleTabsCache !== 'undefined' && !_visibleTabsCache.tls) toggleTabVisibility('tls')`); await sleep(700);
    await tab('tls', 2000);
    await shot('tls-options');
    await js(`if (typeof _visibleTabsCache !== 'undefined' && !_visibleTabsCache.crowdsec) toggleTabVisibility('crowdsec')`); await sleep(700);
    await tab('crowdsec', 4000);
    await shot('crowdsec');
    await tab('logs', 3000);
    await shot('logs');
    await tab('plugins', 2000);
    await shot('plugins');
    await js(`openPluginForm()`); await sleep(1200); await shot('plugins-add');
    await js(`closePluginForm()`); await sleep(500);

    await tab('services', 600);
    await js(`openSettingsModal('ui')`); await sleep(1400); await shot('settings-interface');
    await js(`openSettingsChild('auth','password')`); await sleep(1000); await shot('settings-auth-password');
    await js(`openSettingsChild('auth','apikeys')`); await sleep(900); await shot('settings-auth-apikeys');
    await js(`openSettingsChild('auth','oidc')`); await sleep(900); await shot('settings-auth-oidc');
    await js(`openSettingsChild('backups','routes'); loadBackups()`); await sleep(1300); await shot('settings-backups');
    await js(`openSettingsChild('system','tabs')`); await sleep(1000); await shot('settings-system');
    await js(`switchSettingsPanel('routes')`); await sleep(900); await shot('settings-routes');
    await js(`switchSettingsPanel('connection')`); await sleep(900); await shot('settings-connection');
    await js(`switchSettingsPanel('notifications')`); await sleep(900); await shot('settings-notifications');
    await js(`editChannel('ch-ntfy')`); await sleep(1100);
    await js(`(() => {
        const el = document.getElementById('chDigest');
        if (!el) return;
        let n = el.parentElement;
        while (n && n !== document.body) {
            const st = getComputedStyle(n);
            if (/(auto|scroll)/.test(st.overflowY) && n.scrollHeight > n.clientHeight) {
                n.scrollTop = Math.max(0, el.offsetTop - 120);
                return;
            }
            n = n.parentElement;
        }
        el.scrollIntoView({ block: 'center' });
    })()`);
    await sleep(700); await shot('settings-notification-channel');
    await js(`cancelChannelEdit()`); await sleep(500);
    await js(`switchSettingsPanel('agents'); loadAgentsList()`);
    await page.waitForFunction(
        `!/Loading agents/.test(document.getElementById('agentsListBody')?.textContent || '')`,
        { timeout: 20000 }).catch(() => console.log('  ! agents list never finished loading'));
    await sleep(1500); await shot('settings-agents');
    const agentId = await js(`document.querySelector('#agentsListBody [data-agent-id]')?.dataset.agentId || ''`);
    if (agentId) {
        await js(`openAgentKeys('${agentId}', 'edge-vps')`);
        await sleep(2500); await shot('settings-agent-keys');
        await js(`closeAgentKeys()`); await sleep(400);
    } else {
        missing.push(`${theme}/settings-agent-keys: no agent row to open keys from`);
    }
    await js(`switchSettingsPanel('about')`); await sleep(1200); await shot('settings-about');
    await js(`closeSettingsModal()`);

    await js(`if (typeof _visibleTabsCache !== 'undefined' && !_visibleTabsCache.static) toggleTabVisibility('static')`); await sleep(800);
    await tab('static', 2500);
    await shot('static-config');

    await tab('dashboard', 3000);
    const row = await page.$('.dsk-row');
    if (row) { await row.hover(); await sleep(400); await shot('dashboard-hover'); }
    else missing.push(`${theme}/dashboard-hover: no .dsk-row on the dashboard`);

    await js(`setDashPodDensity('icons')`);
    await sleep(3000);
    await shot('dashboard-icons');
    await js(`setDashPodDensity('list')`);
    await sleep(1500);

    await page.close(); await ctx.close();
}
await capture('dark');
await capture('light');
await browser.close();
if (missing.length) {
    console.log('MISSING SHOTS, the installed copies stay at their old version:');
    missing.forEach(m => console.log('  ! ' + m));
}
console.log('done');

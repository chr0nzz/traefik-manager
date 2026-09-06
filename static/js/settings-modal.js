function _backupFetch(path, opts) {
    if (typeof agentFetch === 'function') return agentFetch(path, opts);
    return fetch(path, opts);
}

async function createAndLoadStaticBackup() {
    if (typeof _activeAgent !== 'undefined' && _activeAgent) {
        try {
            const res  = await _backupFetch('/api/backups', { method: 'POST' });
            if (!res.ok) { showToast(await _errText(res, 'Backup failed'), 'error'); return; }
            const data = await res.json();
            if (data.ok) { showToast('Backup created on ' + _activeAgent.name, 'success'); loadBackups(); }
            else showToast(data.error || data.message || 'Backup failed', 'error');
        } catch(e) { showToast(_netErrText(e, 'Backup failed'), 'error'); }
        return;
    }
    const btn = document.querySelector('[onclick="createAndLoadStaticBackup()"]');
    if (btn) { btn.disabled = true; btn.innerHTML = '<i class="ph-light ph-spinner-gap animate-spin"></i> Creating…'; }
    try {
        const res  = await fetch('/api/static/backup/create', { method: 'POST', headers: _csrfHeaders() });
        if (!res.ok) { showToast(await _errText(res, 'Backup failed'), 'error'); return; }
        const data = await res.json();
        if (data.success) {
            showToast('Static config backup created', 'success');
            loadBackups();
        } else {
            showToast('Backup failed: ' + (data.error || data.message || 'the server did not say why'), 'error');
        }
    } catch(e) { showToast(_netErrText(e, 'Backup failed'), 'error'); }
    finally {
        if (btn) { btn.disabled = false; btn.innerHTML = '<i class="ph-bold ph-plus"></i> Create Backup'; }
    }
}

function switchBackupTab(id, btn) {
    const isAgent = typeof _activeAgent !== 'undefined' && !!_activeAgent;
    const chip = document.getElementById('backupRemoteChip');
    if (chip) { chip.textContent = isAgent ? _activeAgent.name : ''; chip.style.display = isAgent ? '' : 'none'; }
    document.querySelectorAll('#mpanel-backups .auth-sub-tab').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('#mpanel-backups .auth-sub-panel').forEach(p => p.style.display = 'none');
    const activeTabBtn = btn || document.getElementById('backup-tab-' + id);
    if (activeTabBtn) activeTabBtn.classList.add('active');
    const panel = document.getElementById('backup-sub-' + id);
    if (panel) panel.style.display = 'flex';
    if (id === 'git') loadGitTab();
}

let _gitBackupEnabled  = false;
let _gitAutoPushEnabled = true;

function toggleGitBackupEnabled() {
    _gitBackupEnabled = !_gitBackupEnabled;
    const el = document.getElementById('toggle-git-backup');
    if (el) el.classList.toggle('on', _gitBackupEnabled);
}

function toggleGitAutoPush() {
    _gitAutoPushEnabled = !_gitAutoPushEnabled;
    const el = document.getElementById('toggle-git-autopush');
    if (el) el.classList.toggle('on', _gitAutoPushEnabled);
}

function _gitFetch(path, opts) {
    const isAgent = typeof _activeAgent !== 'undefined' && !!_activeAgent;
    if (isAgent && _activeAgent.git_host_backup) {
        const sep = path.includes('?') ? '&' : '?';
        return fetch(path + sep + 'agent_id=' + encodeURIComponent(_activeAgent.id), opts);
    }
    return _backupFetch(path, opts);
}

let _gitHostAgentOn = false;

function toggleGitHostAgent() {
    _gitHostAgentOn = !_gitHostAgentOn;
    const tog = document.getElementById('toggle-git-host-agent');
    if (tog) tog.classList.toggle('on', _gitHostAgentOn);
}

async function saveGitHostAgent() {
    if (!_activeAgent) return;
    const branch = (document.getElementById('gitHostAgentBranch')?.value || '').trim();
    try {
        const res  = await fetch('/api/agents/' + _activeAgent.id, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json', ..._csrfHeaders() },
            body: JSON.stringify({ git_host_backup: _gitHostAgentOn, git_host_branch: branch }),
        });
        if (!res.ok) { showToast(await _errText(res, 'Save failed'), 'error'); return; }
        const data = await res.json();
        if (data.error) { showToast(data.error, 'error'); return; }
        _activeAgent.git_host_backup = _gitHostAgentOn;
        _activeAgent.git_host_branch = branch;
        showToast('Git settings saved', 'success');
        loadGitTab();
    } catch (e) {
        showToast(_netErrText(e, 'Save failed'), 'error');
    }
}

async function loadGitTab() {
    const isAgent = typeof _activeAgent !== 'undefined' && !!_activeAgent;
    const configForm    = document.getElementById('gitConfigForm');
    const saveBtn       = document.getElementById('gitSaveSettingsBtn');
    const resetBtn      = document.getElementById('gitResetBtn');
    const envNote       = document.getElementById('gitEnvNote');
    const hostForm      = document.getElementById('gitHostAgentForm');
    const testBtn       = document.getElementById('gitTestBtn');
    if (configForm) configForm.style.display = isAgent ? 'none' : 'flex';
    if (saveBtn)    saveBtn.style.display    = isAgent ? 'none' : '';
    if (resetBtn)   resetBtn.style.display   = isAgent ? 'none' : '';
    if (testBtn)    testBtn.style.display    = isAgent ? 'none' : '';
    if (envNote)    envNote.style.display    = isAgent ? '' : 'none';
    if (hostForm)   hostForm.style.display   = isAgent ? 'flex' : 'none';
    if (isAgent) {
        _gitHostAgentOn = !!_activeAgent.git_host_backup;
        const tog = document.getElementById('toggle-git-host-agent');
        if (tog) tog.classList.toggle('on', _gitHostAgentOn);
        const br = document.getElementById('gitHostAgentBranch');
        if (br) br.value = _activeAgent.git_host_branch || (_activeAgent.name || '').toLowerCase().replace(/[^\w.-]+/g, '-').replace(/^-+|-+$/g, '');
    }
    if (!isAgent) {
        try {
            const res  = await fetch('/api/settings');
            const data = await res.json();
            _gitBackupEnabled  = bool(data.git_backup_enabled);
            _gitAutoPushEnabled = bool(data.git_backup_auto_push !== false);
            const tog1 = document.getElementById('toggle-git-backup');
            const tog2 = document.getElementById('toggle-git-autopush');
            if (tog1) tog1.classList.toggle('on', _gitBackupEnabled);
            if (tog2) tog2.classList.toggle('on', _gitAutoPushEnabled);
            _setVal('gitBackupRepo',      data.git_backup_repo || '');
            _setVal('gitBackupBranch',    data.git_backup_branch || 'main');
            _setVal('gitBackupUsername',  data.git_backup_username || '');
            _setVal('gitBackupCommitMsg', data.git_backup_commit_message || 'traefik-manager: {action} at {timestamp}');
            const tokenSet = document.getElementById('gitTokenSet');
            if (tokenSet) tokenSet.style.display = data.git_backup_token_set ? '' : 'none';
        } catch(e) {}
    }
    loadGitStatus();
    loadGitCommits();
}

async function loadGitStatus() {
    try {
        const res  = await _gitFetch('/api/backup/git/status');
        const data = await res.json();
        const line = document.getElementById('gitStatusLine');
        if (!line) return;
        if (data.last_sha) {
            line.style.display = '';
            line.innerHTML = `<i class="ph-bold ph-check-circle" style="color:var(--green)"></i> Last push: <span class="font-mono">${data.last_sha}</span> &middot; ${data.last_push || ''}`;
        } else {
            line.style.display = 'none';
        }
    } catch(e) {}
}

async function loadGitCommits() {
    const list = document.getElementById('gitCommitsList');
    if (!list) return;
    list.innerHTML = `<div class="text-center py-4" style="color:var(--muted)"><i class="ph-light ph-spinner-gap animate-spin text-xl block mb-1"></i></div>`;
    try {
        const res     = await _gitFetch('/api/backup/git/commits');
        if (!res.ok) {
            list.innerHTML = `<p class="text-xs" style="color:var(--red)">${_esc(await _errText(res, 'Failed to load commits'))}</p>`;
            return;
        }
        const commits = await res.json();
        if (!commits.length) {
            list.innerHTML = `<div class="text-center py-6" style="color:var(--muted)"><i class="ph-light ph-git-commit text-3xl block mb-2 opacity-30"></i><p class="text-xs">No commits yet</p></div>`;
            return;
        }
        list.innerHTML = commits.map(c => `
            <div class="sc-set">
                <div class="sc-set-l">
                    <div class="flex items-center gap-1.5">
                        <span class="font-mono text-xs px-1.5 py-0.5 rounded" style="background:var(--input-bg);color:var(--muted);flex-shrink:0;">${c.sha_short}</span>
                        <span class="sc-set-n truncate">${_esc(c.message)}</span>
                    </div>
                    <div class="sc-set-d">${c.timestamp}</div>
                </div>
                <div class="sc-set-v">
                    <button onclick="gitViewDiff('${c.sha}')" class="btn-secondary text-xs py-1 px-2" title="View diff">
                        <i class="ph-bold ph-code text-xs"></i>
                    </button>
                    <button onclick="gitRestoreCommit('${c.sha}', '${c.sha_short}')" class="btn-secondary text-xs py-1 px-2.5">
                        <i class="ph-bold ph-arrow-counter-clockwise text-xs"></i> Restore
                    </button>
                </div>
            </div>`).join('');
    } catch(e) {
        list.innerHTML = `<p class="text-xs" style="color:var(--red)">${_esc(_netErrText(e, 'Failed to load commits'))}</p>`;
    }
}

async function saveGitBackupSettings() {
    const btn = document.querySelector('[onclick="saveGitBackupSettings()"]');
    if (btn) { btn.disabled = true; btn.innerHTML = '<i class="ph-light ph-spinner-gap animate-spin"></i> Saving…'; }
    try {
        const settings = await (await fetch('/api/settings')).json();
        const token    = document.getElementById('gitBackupToken')?.value || '';
        const payload  = {
            ...settings,
            git_backup_enabled:        _gitBackupEnabled,
            git_backup_repo:           document.getElementById('gitBackupRepo')?.value.trim() || '',
            git_backup_branch:         document.getElementById('gitBackupBranch')?.value.trim() || 'main',
            git_backup_username:       document.getElementById('gitBackupUsername')?.value.trim() || '',
            git_backup_commit_message: document.getElementById('gitBackupCommitMsg')?.value.trim() || 'traefik-manager: {action} at {timestamp}',
            git_backup_auto_push:      _gitAutoPushEnabled,
        };
        if (token) payload.git_backup_token = token;
        const res  = await fetch('/api/settings', { method: 'POST', headers: { 'Content-Type': 'application/json', ..._csrfHeaders() }, body: JSON.stringify(payload) });
        if (!res.ok) { showToast(await _errText(res, 'Save failed'), 'error'); return; }
        const data = await res.json();
        if (data.success) {
            showToast('Git settings saved', 'success');
            document.getElementById('gitBackupToken').value = '';
            const tokenSet = document.getElementById('gitTokenSet');
            if (tokenSet && token) tokenSet.style.display = '';
        } else {
            showToast('Save failed: ' + (data.error || data.message || 'the server did not say why'), 'error');
        }
    } catch(e) { showToast(_netErrText(e, 'Save failed'), 'error'); }
    finally {
        if (btn) { btn.disabled = false; btn.innerHTML = '<i class="ph-bold ph-floppy-disk"></i> Save Git Settings'; }
    }
}

async function gitTestConnection() {
    const btn = document.getElementById('gitTestBtn');
    if (btn) { btn.disabled = true; btn.innerHTML = '<i class="ph-light ph-spinner-gap animate-spin text-xs"></i> Testing…'; }
    try {
        const isAgent = typeof _activeAgent !== 'undefined' && !!_activeAgent;
        const payload = isAgent ? {} : {
            repo_url: document.getElementById('gitBackupRepo')?.value.trim() || '',
            username: document.getElementById('gitBackupUsername')?.value.trim() || '',
        };
        const token = !isAgent && document.getElementById('gitBackupToken')?.value || '';
        if (token) payload.token = token;
        const res  = await _backupFetch('/api/backup/git/test', { method: 'POST', headers: { 'Content-Type': 'application/json', ..._csrfHeaders() }, body: JSON.stringify(payload) });
        if (!res.ok) { showToast(await _errText(res, 'Connection test failed'), 'error'); return; }
        const data = await res.json();
        if (data.ok) {
            showToast('Connection successful', 'success');
        } else {
            showToast('Connection failed: ' + (data.error || data.message || 'Could not reach repository'), 'error');
        }
    } catch(e) {
        showToast(_netErrText(e, 'Connection test failed'), 'error');
    }
    finally {
        if (btn) { btn.disabled = false; btn.innerHTML = '<i class="ph-bold ph-plugs-connected text-xs"></i> Test'; }
    }
}

async function gitPushNow() {
    const btn = document.getElementById('gitPushBtn');
    if (btn) { btn.disabled = true; btn.innerHTML = '<i class="ph-light ph-spinner-gap animate-spin text-xs"></i> Pushing…'; }
    const msgEl   = document.getElementById('gitCommitMessage');
    const message = msgEl ? msgEl.value.trim() : '';
    try {
        const res  = await _gitFetch('/api/backup/git/push', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ..._csrfHeaders() },
            body: JSON.stringify({ message }),
        });
        if (!res.ok) { showToast(await _errText(res, 'Push failed'), 'error'); return; }
        const data = await res.json();
        if (data.ok) {
            showToast('Pushed successfully', 'success');
            if (msgEl) msgEl.value = '';
            loadGitStatus();
            loadGitCommits();
        } else {
            showToast('Push failed: ' + (data.error || data.message || 'the server did not say why'), 'error');
        }
        if (typeof fetchNotifications === 'function') fetchNotifications();
    } catch(e) {
        showToast(_netErrText(e, 'Push failed'), 'error');
    }
    finally {
        if (btn) { btn.disabled = false; btn.innerHTML = '<i class="ph-bold ph-cloud-arrow-up text-xs"></i> Push Now'; }
    }
}

async function gitResetRepo() {
    if (!await _confirm('This will delete the local git repository clone. TM will re-initialize it on the next push.\n\nThis does NOT affect your remote repository or any commits.', 'Reset Git Repository', 'Reset')) return;
    const btn = document.getElementById('gitResetBtn');
    if (btn) { btn.disabled = true; }
    try {
        const res  = await _gitFetch('/api/backup/git/repo', { method: 'DELETE', headers: _csrfHeaders() });
        if (!res.ok) { showToast(await _errText(res, 'Reset failed'), 'error'); return; }
        const data = await res.json();
        if (data.ok) {
            showToast('Repository reset - push again to re-initialize', 'success');
            loadGitStatus();
            loadGitCommits();
            if (typeof fetchNotifications === 'function') fetchNotifications();
        } else {
            showToast('Reset failed: ' + (data.error || data.message || 'the server did not say why'), 'error');
        }
    } catch(e) { showToast(_netErrText(e, 'Reset failed'), 'error'); }
    finally {
        if (btn) { btn.disabled = false; }
    }
}

async function gitRestoreCommit(sha, shaShort) {
    if (!await _confirm(`Restore every config file from commit ${shaShort}? Local backups are created first.`,
                        'Git Restore', 'Restore', 'RESTORE')) return;
    try {
        const res  = await _gitFetch(`/api/backup/git/restore/${sha}`, { method: 'POST', headers: _csrfHeaders() });
        if (!res.ok) { showToast(await _errText(res, 'Restore failed'), 'error'); return; }
        const data = await res.json();
        if (data.ok) {
            showToast('Restored successfully', 'success');
            closeSettingsModal();
            setTimeout(() => location.reload(), 1500);
        } else {
            showToast('Restore failed: ' + (data.error || data.message || 'the server did not say why'), 'error');
        }
    } catch(e) { showToast(_netErrText(e, 'Restore failed'), 'error'); }
}

async function gitViewDiff(sha) {
    try {
        const res  = await _gitFetch(`/api/backup/git/commit/${sha}/diff`);
        if (!res.ok) { showToast(await _errText(res, 'Failed to load diff'), 'error'); return; }
        const data = await res.json();
        if (data.error) { showToast('Diff error: ' + data.error, 'error'); return; }
        if (!data.files || !data.files.length) { showToast('No changes in this commit', 'info'); return; }
        if (typeof openGitDiffPopout === 'function') openGitDiffPopout(sha, data.files);
    } catch(e) { showToast(_netErrText(e, 'Failed to load diff'), 'error'); }
}

function bool(v) { return v === true || v === 1 || v === 'true'; }
function _setVal(id, val) { const el = document.getElementById(id); if (el) el.value = val; }

function hideStaticDangerWarn() {
    localStorage.setItem('staticWarnHidden', '1');
    const warn = document.getElementById('staticDangerWarn');
    if (warn) warn.style.display = 'none';
}

function switchAuthTab(id, btn) {
    document.querySelectorAll('#mpanel-auth .auth-sub-tab').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('#mpanel-auth .auth-sub-panel').forEach(p => p.style.display = 'none');
    if (btn) btn.classList.add('active');
    const panel = document.getElementById('auth-sub-' + id);
    if (panel) panel.style.display = 'flex';
}

function switchSystemTab(id, btn) {
    document.querySelectorAll('#mpanel-system .auth-sub-tab').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('#mpanel-system .auth-sub-panel').forEach(p => p.style.display = 'none');
    if (btn) btn.classList.add('active');
    const panel = document.getElementById('system-sub-' + id);
    if (panel) panel.style.display = 'flex';
}

const AGENT_HIDDEN_MOBILE_ROWS = [
    "switchSettingsPanel('auth')",
    "openSettingsChild('auth'",
    "switchSettingsPanel('connection')",
    "switchSettingsPanel('notifications')",
    "openSettingsChild('system', 'crowdsec')",
];

function _updateMobileRowsForAgent(active) {
    document.querySelectorAll('#settingsMobileRoot .settings-mobile-row').forEach(btn => {
        const target = btn.getAttribute('onclick') || '';
        if (AGENT_HIDDEN_MOBILE_ROWS.some(p => target.includes(p))) {
            btn.style.display = active ? 'none' : '';
        }
    });
}

function _settleSettingsLayout() {
    const modal = document.getElementById('settingsModal');
    if (!modal || modal.style.display === 'none') return;
    ['settingsMobileRoot', 'settingsPanelWrapper'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.scrollTop = 0;
    });
    document.querySelectorAll('#settingsPanelWrapper .modal-panel').forEach(el => {
        el.scrollTop = 0;
    });
}

function _applySettingsBreakpoint() {
    const modal = document.getElementById('settingsModal');
    if (!modal || modal.style.display !== 'flex') return;
    const wrapper = document.getElementById('settingsPanelWrapper');
    const root = document.getElementById('settingsMobileRoot');
    if (!wrapper || !root) return;
    const narrow = window.innerWidth < 640;
    const onRoot = root.style.display === 'flex';
    const back = document.getElementById('settingsMobileBack');
    if (!narrow && onRoot) {
        root.style.display = 'none';
        wrapper.style.display = 'flex';
        if (back) back.style.display = 'none';
    } else if (narrow && !onRoot && wrapper.style.display !== 'flex') {
        root.style.display = 'flex';
        if (back) back.style.display = 'none';
    }
    _settleSettingsLayout();
}

window.addEventListener('resize', _applySettingsBreakpoint);
window.addEventListener('orientationchange', () => setTimeout(_applySettingsBreakpoint, 150));

function _updateSettingsSidebarForAgent(active) {
    _updateMobileRowsForAgent(active);
    const localOnly = ['auth', 'connection', 'notifications'];
    localOnly.forEach(id => {
        const btn = document.getElementById('msb-' + id);
        if (btn) btn.style.display = active ? 'none' : '';
        const mob = document.getElementById('msb-' + id + '-mobile');
        if (mob) mob.style.display = active ? 'none' : '';
    });
    const keysBtn = document.getElementById('msb-agent-keys');
    if (keysBtn) keysBtn.style.display = active ? '' : 'none';
    const keysMob = document.getElementById('msb-agent-keys-mobile');
    if (keysMob) keysMob.style.display = active ? '' : 'none';
    const csChild = document.getElementById('msc-system-crowdsec');
    if (csChild) csChild.style.display = active ? 'none' : '';
    const csTab = document.getElementById('system-tab-crowdsec');
    if (csTab) {
        csTab.style.display = active ? 'none' : '';
        if (active && csTab.classList.contains('active')) {
            const firstTab = document.querySelector('#mpanel-system .auth-sub-tab:not([style*="display: none"])');
            if (firstTab) firstTab.click();
        }
    }
}

async function _loadAboutAgentInfo() {
    const row = document.getElementById('sm-agent-version-row');
    if (!row) return;
    if (!_activeAgent) { row.classList.add('hidden'); return; }
    document.getElementById('agentVersionName').textContent = _activeAgent.name;
    document.getElementById('agentVersionCurrent').textContent = '-';
    document.getElementById('agentVersionHint').classList.add('hidden');
    row.classList.remove('hidden');
    row.style.removeProperty('display');
    try {
        const d = await fetch('/api/agents/' + _activeAgent.id + '/health').then(r => r.json());
        const cur = (d.version || '').replace(/^v/, '');
        if (!cur) return;
        document.getElementById('agentVersionCurrent').textContent = 'v' + cur;
        const latest = (document.getElementById('mgrUpdateLatestVer').textContent || '').replace(/^v/, '');
        if (latest && latest !== '-' && compareVersions(latest, cur) > 0) {
            const hint = document.getElementById('agentVersionHint');
            hint.textContent = 'v' + latest + ' available';
            hint.classList.remove('hidden');
        }
    } catch (e) {}
}

const SETTINGS_CHILDREN = {
    system:  { first: 'tabs',        switch: (k) => switchSystemTab(k) },
    auth:    { first: 'password',    switch: (k) => switchAuthTab(k) },
    backups: { first: 'routes',      switch: (k) => switchBackupTab(k) },
    static:  { first: 'entrypoints', switch: (k) => switchStaticSettingsSection(k) },
};

function openSettingsChild(parent, child) {
    switchSettingsPanel(parent);
    const spec = SETTINGS_CHILDREN[parent];
    if (spec) spec.switch(child);
    _markSettingsChild(parent, child);
    if (window.innerWidth < 640) {
        document.getElementById('settingsMobileRoot').style.display = 'none';
        document.getElementById('settingsPanelWrapper').style.display = 'flex';
        document.getElementById('settingsMobileBack').style.display = 'flex';
    }
}

function _markSettingsChild(parent, child) {
    Object.keys(SETTINGS_CHILDREN).forEach(p => {
        document.querySelectorAll('#mss-' + p + ' .modal-sidebar-btn').forEach(b => b.classList.remove('active'));
    });
    const btn = document.getElementById('msc-' + parent + '-' + child);
    if (btn) btn.classList.add('active');
}

function _syncSettingsSubmenu(id) {
    Object.keys(SETTINGS_CHILDREN).forEach(p => {
        const sub = document.getElementById('mss-' + p);
        if (sub) sub.classList.toggle('open', p === id);
    });
    const spec = SETTINGS_CHILDREN[id];
    if (!spec) return;
    const already = document.querySelector('#mss-' + id + ' .modal-sidebar-btn.active');
    if (!already) _markSettingsChild(id, spec.first);
}

function switchSettingsPanel(id, btn) {
    setTimeout(() => {
        if (typeof filterSettings === 'function') filterSettings();
        if (id === 'static') {
            if (typeof applyStaticPlacement === 'function' && typeof getStaticPlacement === 'function') {
                applyStaticPlacement(getStaticPlacement());
            }
            if (typeof openStaticTab === 'function') openStaticTab();
            if (typeof _applyStaticWarnState === 'function') _applyStaticWarnState();
        }
    }, 0);
    document.querySelectorAll('.modal-sidebar-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.modal-panel').forEach(p => p.classList.remove('active'));
    const activeBtn = btn || document.getElementById('msb-' + id);
    if (activeBtn) activeBtn.classList.add('active');
    document.getElementById('mpanel-' + id).classList.add('active');
    _syncSettingsSubmenu(id);
    if (id === 'about') _loadAboutAgentInfo();
    if (id === 'notifications') { loadChannelsList(); renderBrowserNotifs(); }
    if (window.innerWidth < 640) {
        const titles = {connection:'Connection',routes:'Route Monitoring',system:'System Monitoring',auth:'Authentication',backups:'Backups',ui:'Interface',notifications:'Notifications',about:'About','agent-keys':'API Keys',static:'Static Config'};
        document.getElementById('settingsModalTitle').textContent = titles[id] || 'Settings';
        document.getElementById('settingsGearIcon').style.display = 'none';
        document.getElementById('settingsMobileRoot').style.display = 'none';
        document.getElementById('settingsPanelWrapper').style.display = 'flex';
        document.getElementById('settingsMobileBack').style.display = 'flex';
    }
}

function settingsMobileBack() {
    document.getElementById('settingsMobileRoot').style.display = 'flex';
    document.getElementById('settingsPanelWrapper').style.display = 'none';
    document.getElementById('settingsMobileBack').style.display = 'none';
    document.getElementById('settingsGearIcon').style.display = '';
    document.getElementById('settingsModalTitle').textContent = 'Settings';
}

async function openSettingsModal(panel) {
    closeOtherPanels('settingsModal');
    document.documentElement.classList.add('tm-settings-open');
    document.getElementById('settingsSavedNotice').classList.add('hidden');
    document.getElementById('apiTestResult').textContent = '';

    ['pwCurrent','pwNew','pwConfirm'].forEach(id => { const el = document.getElementById(id); if(el) el.value = ''; });
    const msg = document.getElementById('pwChangeMsg');
    if (msg) { msg.classList.add('hidden'); msg.textContent = ''; }
    const apikeyDisplay = document.getElementById('apikeyDisplay');
    if (apikeyDisplay) apikeyDisplay.classList.add('hidden');
    const apikeyValue = document.getElementById('apikeyValue');
    if (apikeyValue) apikeyValue.value = '';

    document.getElementById('settingsModal').style.display = 'flex';
    document.body.style.overflow = 'hidden';
    _updateSettingsSidebarForAgent(!!_activeAgent);
    requestAnimationFrame(_settleSettingsLayout);

    if (window.innerWidth < 640 && !panel) {
        document.getElementById('settingsMobileRoot').style.display = 'flex';
        document.getElementById('settingsPanelWrapper').style.display = 'none';
        document.getElementById('settingsMobileBack').style.display = 'none';
        document.getElementById('settingsGearIcon').style.display = '';
        document.getElementById('settingsModalTitle').textContent = 'Settings';
    } else {
        document.getElementById('settingsMobileRoot').style.display = 'none';
        document.getElementById('settingsPanelWrapper').style.display = 'flex';
        if (panel) switchSettingsPanel(panel);
    }

    try {
        const res  = await fetch('/api/settings');
        const data = await res.json();
        document.getElementById('settingsDomains').value          = (data.domains || []).join(', ');
        syncThemeButtons(data.default_theme || 'dark');
        document.getElementById('settingsCertResolver').value     = data.cert_resolver || '';
        document.getElementById('settingsApiUrl').value           = data.traefik_api_url || '';
        document.getElementById('settingsApiUser').value          = data.traefik_api_user || '';
        const apiPwHint = document.getElementById('apiPasswordSetHint');
        if (apiPwHint) apiPwHint.classList.toggle('hidden', !data.traefik_api_password_set);
        document.getElementById('settingsAcmeJsonPath').value     = data.acme_json_path || '';
        document.getElementById('settingsAccessLogPath').value    = data.access_log_path || '';
        document.getElementById('settingsStaticConfigPath').value = data.static_config_path || '';
        document.getElementById('settingsCrowdSecUrl').value      = data.crowdsec_lapi_url || '';
        document.getElementById('settingsCrowdSecAlertLimit').value = data.crowdsec_alert_limit || '';
        window._tmAlertLimit = data.crowdsec_alert_limit || '';
        const csKeyHint = document.getElementById('crowdsecKeySetHint');
        if (csKeyHint) csKeyHint.classList.toggle('hidden', !data.crowdsec_api_key_set);
        const csMidEl = document.getElementById('settingsCrowdSecMachineId');
        if (csMidEl) csMidEl.value = data.crowdsec_machine_id || '';
        const csMachineHint = document.getElementById('crowdsecMachineSetHint');
        if (csMachineHint) csMachineHint.classList.toggle('hidden', !data.crowdsec_machine_password_set);
        const csCcEl = document.getElementById('settingsCrowdSecClientCert');
        if (csCcEl) csCcEl.value = data.crowdsec_client_cert || '';
        const csCkEl = document.getElementById('settingsCrowdSecClientKey');
        if (csCkEl) csCkEl.value = data.crowdsec_client_key || '';
        const csCaEl = document.getElementById('settingsCrowdSecCaCert');
        if (csCaEl) csCaEl.value = data.crowdsec_ca_cert || '';
        _legacyWebhook.url      = data.webhook_url || '';
        _legacyWebhook.type     = data.webhook_type || 'discord';
        _legacyWebhook.username = data.webhook_username || '';

        if (data.visible_tabs) {
            _localTabsCache = data.visible_tabs;
            if (!_activeAgent) _visibleTabsCache = data.visible_tabs;
        }
        loadTabTogglesIntoModal();
        loadUiTogglesIntoModal();
        _applyTraefikBadgeVisibility();
        _applyTmBadgeVisibility();
        _applyDocsLinkVisibility();
        _applyApiLinkVisibility();
        loadOtpStatus();
        loadApiKeyStatus();
        loadOidcStatus();
        loadSelfRoute();

        const authSection   = document.getElementById('authSection');
        const toggleBtn     = document.getElementById('authToggleBtn');
        const stateLabel    = document.getElementById('authStateLabel');
        const toggleLabel   = document.getElementById('authToggleLabel');
        const envForcedNote = document.getElementById('authEnvForcedNote');
        const changePwForm  = document.getElementById('changePwForm');

        if (data.has_password !== undefined) {
            document.getElementById('authHiddenMsg') && (document.getElementById('authHiddenMsg').classList.add('hidden'));
            const isOn = data.auth_enabled;
            stateLabel.textContent  = isOn ? 'enabled' : 'disabled';
            stateLabel.style.color  = isOn ? 'var(--green)' : 'var(--muted)';
            if (!data.auth_env_forced && toggleBtn) {
                toggleBtn.classList.remove('hidden');
                toggleLabel.textContent = isOn ? 'Disable' : 'Enable';
            } else {
                envForcedNote.classList.remove('hidden');
            }
            if (changePwForm) changePwForm.style.display = isOn ? '' : 'none';
        }
        _paintAuthState(data.no_auth, data.auth_external_ack);
    } catch(e) {
        console.error('Could not load settings', e);
    }
    const target = panel || 'ui';
    const rootWasOpen = document.getElementById('settingsMobileRoot').style.display === 'flex';
    switchSettingsPanel(target);
    if (rootWasOpen && !panel) _showSettingsMobileRoot();
    if (target === 'backups') loadBackups();
}

function _showSettingsMobileRoot() {
    document.getElementById('settingsMobileRoot').style.display = 'flex';
    document.getElementById('settingsPanelWrapper').style.display = 'none';
    document.getElementById('settingsMobileBack').style.display = 'none';
    document.getElementById('settingsGearIcon').style.display = '';
    document.getElementById('settingsModalTitle').textContent = 'Settings';
}

function closeSettingsModal() {
    document.documentElement.classList.remove('tm-settings-open');
    document.getElementById('settingsModal').style.display = 'none';
    document.body.style.overflow = '';
}

async function changePassword() {
    const current = document.getElementById('pwCurrent').value;
    const newPw   = document.getElementById('pwNew').value;
    const confirm = document.getElementById('pwConfirm').value;
    const msg     = document.getElementById('pwChangeMsg');

    const show = (text, ok) => {
        msg.textContent  = text;
        msg.style.background = ok ? 'rgba(63,185,80,0.1)' : 'rgba(248,81,73,0.1)';
        msg.style.border     = ok ? '1px solid rgba(63,185,80,0.3)' : '1px solid rgba(248,81,73,0.3)';
        msg.style.color      = ok ? 'var(--green)' : 'var(--red)';
        msg.classList.remove('hidden');
    };

    if (!current || !newPw || !confirm) return show('Please fill in all fields.', false);
    const pwErr = _passwordError(newPw, 'New password');
    if (pwErr)                         return show(pwErr, false);
    if (newPw !== confirm)             return show('Passwords do not match.', false);

    try {
        const res  = await fetch('/api/auth/change-password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': _csrfHeaders()['X-CSRF-Token'] },
            body: JSON.stringify({ current_password: current, new_password: newPw, confirm_password: confirm })
        });
        if (!res.ok) return show(await _errText(res, 'Failed to update password'), false);
        const data = await res.json();
        if (data.success) {
            show('Password updated successfully.', true);
            ['pwCurrent','pwNew','pwConfirm'].forEach(id => document.getElementById(id).value = '');
        } else {
            show(data.error || data.message || 'Failed to update password.', false);
        }
    } catch(e) {
        show(_netErrText(e, 'Request failed'), false);
    }
}

function _paintAuthState(noAuth, ack) {
    const warn = document.getElementById('noAuthWarning');
    const note = document.getElementById('authDelegatedNote');
    if (warn) warn.style.display = (noAuth && !ack) ? '' : 'none';
    if (note) note.style.display = (noAuth && ack) ? '' : 'none';
    _paintSettingsVerdict(noAuth && !ack);
}

function _paintSettingsVerdict(noAuth) {
    const el = document.getElementById('settingsVerdict');
    if (!el) return;
    const items = [];
    if (noAuth) {
        items.push('<button type="button" class="sig-flag d-bad" onclick="switchSettingsPanel(\'auth\')"'
            + ' title="No password and no OIDC - anything that reaches this instance has full access">'
            + '<i class="ph-bold ph-lock-open"></i><span class="sig-fl">no authentication</span></button>');
    }
    if (!items.length) { el.style.display = 'none'; el.innerHTML = ''; return; }
    el.style.display = '';
    el.dataset.health = 'down';
    el.innerHTML = '<i class="ph-fill ph-warning-octagon sig-verdict-ic"></i>'
        + '<span class="sig-verdict-txt">' + items.length + (items.length === 1 ? ' thing' : ' things') + ' to look at</span>'
        + '<span class="sig-verdict-items">' + items.join('') + '</span>';
}

async function setAuthExternalAck(on) {
    if (on && !await _confirm(
        'Only do this if something in front of Traefik Manager already requires a login, such as Authelia, Authentik or a forward-auth middleware. '
        + 'Traefik Manager will stop warning you, but it still does not check who you are, so anything that reaches it directly gets full access.',
        'Authentication is handled elsewhere', 'I understand')) return;
    try {
        const res = await fetch('/api/auth/external-ack', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ..._csrfHeaders() },
            body: JSON.stringify({ auth_external_ack: !!on }),
        });
        if (!res.ok) { showToast(await _errText(res, 'Failed to update'), 'error'); return; }
        const data = await res.json();
        if (!data.success) { showToast(data.error || data.message || 'Failed to update.', 'error'); return; }
        _paintAuthState(true, !!on);
        const banner = document.getElementById('noAuthBanner');
        if (banner) banner.style.display = on ? 'none' : '';
        showToast(on ? 'Warning hidden. Traefik Manager still does not authenticate anyone.' : 'Warning restored.', 'success');
    } catch (e) { showToast(_netErrText(e, 'Request failed'), 'error'); }
}

async function toggleAuth() {
    const stateLabel  = document.getElementById('authStateLabel');
    const toggleLabel = document.getElementById('authToggleLabel');
    const changePwForm = document.getElementById('changePwForm');
    const currentlyOn = stateLabel.textContent === 'enabled';
    const newState    = !currentlyOn;

    if (currentlyOn) {
        let oidcOn = false;
        try {
            const r = await fetch('/api/auth/oidc');
            oidcOn = !!(await r.json()).oidc_enabled;
        } catch (e) {
            oidcOn = false;
        }
        const warning = oidcOn
            ? 'Disable built-in authentication? Sign-in continues through your OIDC provider.'
            : 'Disable built-in authentication? Anyone who can reach this URL will have full access.';
        if (!await _confirm(warning, 'Disable Authentication', 'Disable')) return;
    }

    try {
        const res  = await fetch('/api/auth/toggle', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': _csrfHeaders()['X-CSRF-Token'] },
            body: JSON.stringify({ auth_enabled: newState })
        });
        if (!res.ok) { showToast(await _errText(res, 'Failed to update auth'), 'error'); return; }
        const data = await res.json();
        if (data.success) {
            if (data.reauth_required) return _redirectToLoginAfterAuthEnable('Authentication enabled');
            stateLabel.textContent = newState ? 'enabled' : 'disabled';
            stateLabel.style.color = newState ? 'var(--green)' : 'var(--muted)';
            toggleLabel.textContent = newState ? 'Disable' : 'Enable';
            if (changePwForm) changePwForm.style.display = newState ? '' : 'none';
            _paintAuthState(false, false);
            showToast(`Authentication ${newState ? 'enabled' : 'disabled'}.`, 'success');
        } else {
            showToast(data.error || data.message || 'Failed to update auth.', 'error');
        }
    } catch(e) {
        showToast(_netErrText(e, 'Request failed'), 'error');
    }
}

let _legacyWebhook = { url: '', type: 'discord', username: '' };

const CHANNEL_KIND_SPEC = {
    unifiedpush: { label: 'Mobile app',
                  fields: { url:         { label: 'Device endpoint', desc: 'Registered by the Traefik Manager app on your phone. Editing it stops push to that device.', ph: '' } } },
    discord:    { label: 'Discord',      fields: { url:    { label: 'Webhook URL',  desc: 'Where notifications are delivered.', ph: 'https://discord.com/api/webhooks/...' } } },
    slack:      { label: 'Slack',        fields: { url:    { label: 'Webhook URL',  desc: 'Incoming webhook created in your Slack workspace.', ph: 'https://hooks.slack.com/services/...' } } },
    ntfy:       { label: 'ntfy',         auth: true,
                  fields: { url:         { label: 'URL',         desc: 'Full topic URL on ntfy.sh or your own server.', ph: 'https://ntfy.sh/my-topic' } } },
    generic:    { label: 'Generic JSON', auth: true,
                  fields: { url:         { label: 'URL',         desc: 'Receives a JSON body you can shape downstream.', ph: 'https://example.com/hooks/traefik' } } },
    gotify:     { label: 'Gotify',
                  fields: { url:         { label: 'Server URL',  desc: 'Base URL of your Gotify server.', ph: 'https://gotify.example.com' },
                            token:       { label: 'App Token',   desc: 'Application token from Gotify. Stored encrypted.', secret: true } } },
    pushover:   { label: 'Pushover',
                  fields: { token:       { label: 'App Token',   desc: 'Application token from your Pushover app. Stored encrypted.', secret: true },
                            token2:      { label: 'User Key',    desc: 'Your Pushover user or group key. Stored encrypted.', secret: true } } },
    pushbullet: { label: 'Pushbullet',
                  fields: { token:       { label: 'Access Token', desc: 'Access token from your Pushbullet account. Stored encrypted.', secret: true } } },
    telegram:   { label: 'Telegram',
                  fields: { token:       { label: 'Bot Token',   desc: 'Token issued by BotFather. Stored encrypted.', secret: true },
                            token2:      { label: 'Chat ID',     desc: 'Target chat, group or channel to post into.', ph: '-1001234567890' } } },
};

const CHANNEL_CATEGORY_LABELS = NOTIF_CATEGORY_LABELS;

const CHANNEL_SEVERITY_LABELS = { info: 'Info', success: 'Success', warning: 'Warning', error: 'Error' };

const CHANNEL_DIGEST_LABELS = { immediate: 'Immediate', hourly: 'Hourly', daily: 'Daily' };

let _channels    = [];
let _chEditId    = null;
let _chCats      = [];
let _chSeverity  = 'info';
let _chDigest    = 'immediate';

function _channelKindLabel(kind) {
    return (CHANNEL_KIND_SPEC[kind] || {}).label || kind || '';
}

function _channelFields(kind) {
    return (CHANNEL_KIND_SPEC[kind] || {}).fields || {};
}

function _channelMissing(ch) {
    const fields = _channelFields(ch.kind);
    return Object.keys(fields).filter(k => !String(ch[k] || '').trim()).map(k => fields[k].label);
}

function _channelSummary(ch) {
    const all   = Object.keys(CHANNEL_CATEGORY_LABELS);
    const cats  = (ch.categories || []).filter(c => all.includes(c));
    const parts = [];
    parts.push(!cats.length || cats.length === all.length
        ? 'All categories'
        : cats.map(c => CHANNEL_CATEGORY_LABELS[c]).join(', '));
    const sev = ch.min_severity || 'info';
    if (sev !== 'info') parts.push((CHANNEL_SEVERITY_LABELS[sev] || sev) + ' and above');
    const digest = ch.digest || 'immediate';
    if (digest !== 'immediate') parts.push((CHANNEL_DIGEST_LABELS[digest] || digest) + ' digest');
    if (ch.quiet_hours) parts.push('Quiet ' + _esc(ch.quiet_hours) + (ch.break_through ? ', errors break through' : ''));
    return parts.join(' &middot; ');
}

async function loadChannelsList() {
    const body = document.getElementById('channelsListBody');
    if (!body) return;
    document.getElementById('channelListView').style.display = 'flex';
    document.getElementById('channelEditView').style.display = 'none';
    try {
        const res  = await fetch('/api/notifications/channels');
        if (!res.ok) {
            body.innerHTML = `<div class="text-center py-6 text-xs" style="color:var(--red)">${_esc(await _errText(res, 'Failed to load channels'))}</div>`;
            return;
        }
        const data = await res.json();
        _channels = data.channels || [];
        if (!_channels.length) {
            body.innerHTML = `<div class="text-center py-8" style="color:var(--muted)"><i class="ph-light ph-bell text-4xl block mb-2 opacity-30"></i><p class="text-xs font-medium mb-1">No channels configured</p><p class="text-xs">Add a channel to get a message when routes change, backups run or certificates expire.</p></div>`;
            return;
        }
        body.innerHTML = _channels.map(c => {
            const missing = _channelMissing(c);
            const detail  = missing.length
                ? `<span style="color:var(--yellow)">Needs ${_esc(missing.join(', '))}</span>`
                : _channelSummary(c);
            return `
            <div class="sc-set" data-channel-id="${_esc(c.id)}"${missing.length ? ' data-health="warn"' : ''}>
                <div class="sc-set-l">
                    <div class="flex items-center gap-2">
                        <span class="sc-set-n truncate">${_esc(c.name)}</span>
                        <span class="text-xs flex-shrink-0" style="color:var(--muted)">${_esc(_channelKindLabel(c.kind))}</span>
                    </div>
                    <div class="sc-set-d">${detail}</div>
                </div>
                <div class="sc-set-v">
                    <div class="toggle-switch${c.enabled ? ' on' : ''}" onclick="toggleChannelEnabled('${c.id}')" title="Enabled"><div class="toggle-knob"></div></div>
                    <button onclick="testChannelRow('${c.id}')" class="btn-icon" title="Send test"><i class="ph-bold ph-paper-plane-tilt text-xs"></i></button>
                    <button onclick="editChannel('${c.id}')" class="btn-icon" title="Edit"><i class="ph-bold ph-gear text-xs"></i></button>
                    <button onclick="deleteChannel('${c.id}')" class="btn-icon" title="Remove" style="color:var(--red)"><i class="ph-bold ph-trash text-xs"></i></button>
                </div>
            </div>`;
        }).join('');
    } catch(e) {
        body.innerHTML = `<div class="text-center py-6 text-xs" style="color:var(--red)">${_esc(_netErrText(e, 'Failed to load channels'))}</div>`;
    }
}

function _channelById(id) {
    return _channels.find(c => c.id === id) || null;
}

function _renderChannelChips() {
    const cats = document.getElementById('chCategories');
    if (cats) cats.innerHTML = Object.keys(CHANNEL_CATEGORY_LABELS).map(c =>
        `<button type="button" class="agent-chip${_chCats.includes(c) ? ' active' : ''}" onclick="toggleChannelCategory('${c}')">${CHANNEL_CATEGORY_LABELS[c]}</button>`).join('');
    const sev = document.getElementById('chSeverity');
    if (sev) sev.innerHTML = Object.keys(CHANNEL_SEVERITY_LABELS).map(s =>
        `<button type="button" class="agent-chip${_chSeverity === s ? ' active' : ''}" onclick="selectChannelSeverity('${s}')">${CHANNEL_SEVERITY_LABELS[s]}</button>`).join('');
    const dig = document.getElementById('chDigest');
    if (dig) dig.innerHTML = Object.keys(CHANNEL_DIGEST_LABELS).map(d =>
        `<button type="button" class="agent-chip${_chDigest === d ? ' active' : ''}" onclick="selectChannelDigest('${d}')">${CHANNEL_DIGEST_LABELS[d]}</button>`).join('');
}

function toggleChannelCategory(cat) {
    _chCats = _chCats.includes(cat) ? _chCats.filter(c => c !== cat) : _chCats.concat([cat]);
    _renderChannelChips();
}

function selectChannelSeverity(sev) {
    _chSeverity = sev;
    _renderChannelChips();
}

function selectChannelDigest(digest) {
    _chDigest = digest;
    _renderChannelChips();
}

function clearChannelQuietHours() {
    document.getElementById('chQuietStart').value = '';
    document.getElementById('chQuietEnd').value   = '';
}

function onChannelKindChange() {
    const kind   = document.getElementById('chKind').value;
    const spec   = CHANNEL_KIND_SPEC[kind] || {};
    const fields = spec.fields || {};
    ['url', 'token', 'token2'].forEach(key => {
        const cap  = key.charAt(0).toUpperCase() + key.slice(1);
        const wrap = document.getElementById('chFld' + cap);
        const meta = fields[key];
        wrap.style.display = meta ? '' : 'none';
        if (!meta) return;
        document.getElementById('ch' + cap + 'Label').textContent = meta.label;
        document.getElementById('ch' + cap + 'Desc').textContent  = meta.desc;
        const input = document.getElementById('ch' + cap);
        input.placeholder = meta.ph || '';
        input.type = meta.secret ? 'password' : (key === 'url' ? 'url' : 'text');
    });
    document.getElementById('chFldAuth').style.display = spec.auth ? '' : 'none';
}

function _openChannelEditor(title) {
    document.getElementById('channelEditTitle').textContent = title;
    document.getElementById('chEditErr').style.display    = 'none';
    document.getElementById('chTestResult').style.display = 'none';
    document.getElementById('channelListView').style.display = 'none';
    document.getElementById('channelEditView').style.display = 'flex';
    onChannelKindChange();
    _renderChannelChips();
}

function startAddChannel() {
    _chEditId   = null;
    _chCats     = [];
    _chSeverity = 'info';
    _chDigest   = 'immediate';
    document.getElementById('chName').value       = '';
    document.getElementById('chKind').value       = 'discord';
    document.getElementById('chUrl').value        = '';
    document.getElementById('chToken').value      = '';
    document.getElementById('chToken2').value     = '';
    document.getElementById('chUsername').value   = '';
    document.getElementById('chPassword').value   = '';
    document.getElementById('chQuietStart').value = '';
    document.getElementById('chQuietEnd').value   = '';
    document.getElementById('chEnabled').classList.add('on');
    document.getElementById('chBreakThrough').classList.remove('on');
    _openChannelEditor('Add Channel');
    setTimeout(() => document.getElementById('chName').focus(), 50);
}

function editChannel(id) {
    const ch = _channelById(id);
    if (!ch) return;
    _chEditId   = id;
    _chCats     = (ch.categories || []).filter(c => c in CHANNEL_CATEGORY_LABELS);
    _chSeverity = ch.min_severity || 'info';
    _chDigest   = ch.digest || 'immediate';
    document.getElementById('chName').value     = ch.name || '';
    document.getElementById('chKind').value     = ch.kind || 'discord';
    document.getElementById('chUrl').value      = ch.url || '';
    document.getElementById('chToken').value    = ch.token || '';
    document.getElementById('chToken2').value   = ch.token2 || '';
    document.getElementById('chUsername').value = ch.username || '';
    document.getElementById('chPassword').value = ch.password || '';
    const quiet  = String(ch.quiet_hours || '');
    const bounds = quiet.includes('-') ? quiet.split('-') : ['', ''];
    document.getElementById('chQuietStart').value = bounds[0].trim();
    document.getElementById('chQuietEnd').value   = bounds[1].trim();
    document.getElementById('chEnabled').classList.toggle('on', !!ch.enabled);
    document.getElementById('chBreakThrough').classList.toggle('on', !!ch.break_through);
    _openChannelEditor('Edit Channel');
}

function cancelChannelEdit() {
    _chEditId = null;
    document.getElementById('channelEditView').style.display = 'none';
    document.getElementById('channelListView').style.display = 'flex';
}

function _channelPayload() {
    const kind   = document.getElementById('chKind').value;
    const spec   = CHANNEL_KIND_SPEC[kind] || {};
    const fields = spec.fields || {};
    const start  = document.getElementById('chQuietStart').value.trim();
    const end    = document.getElementById('chQuietEnd').value.trim();
    const value  = key => (fields[key] ? document.getElementById('ch' + key.charAt(0).toUpperCase() + key.slice(1)).value.trim() : '');
    return {
        name:          document.getElementById('chName').value.trim(),
        kind:          kind,
        enabled:       document.getElementById('chEnabled').classList.contains('on'),
        url:           value('url'),
        token:         value('token'),
        token2:        value('token2'),
        username:      spec.auth ? document.getElementById('chUsername').value.trim() : '',
        password:      spec.auth ? document.getElementById('chPassword').value : '',
        categories:    _chCats.slice(),
        min_severity:  _chSeverity,
        digest:        _chDigest,
        quiet_hours:   start && end ? start + '-' + end : '',
        break_through: document.getElementById('chBreakThrough').classList.contains('on'),
    };
}

function _channelError(message) {
    const box = document.getElementById('chEditErr');
    if (!box) return;
    box.textContent = message;
    box.style.display = message ? '' : 'none';
}

async function _persistChannel() {
    const payload = _channelPayload();
    const missing = _channelMissing(payload);
    if (missing.length) { _channelError('Fill in ' + missing.join(' and ') + ' first.'); return null; }
    const start = document.getElementById('chQuietStart').value.trim();
    const end   = document.getElementById('chQuietEnd').value.trim();
    if (!!start !== !!end) { _channelError('Set both a start and an end time for quiet hours, or clear them both.'); return null; }
    _channelError('');
    const path   = _chEditId ? '/api/notifications/channels/' + encodeURIComponent(_chEditId) : '/api/notifications/channels';
    const method = _chEditId ? 'PUT' : 'POST';
    try {
        const res  = await fetch(path, {
            method,
            headers: { 'Content-Type': 'application/json', ..._csrfHeaders() },
            body: JSON.stringify(payload)
        });
        if (!res.ok) { _channelError(await _errText(res, 'Failed to save channel')); return null; }
        const data = await res.json();
        if (data.error) { _channelError(data.error); return null; }
        const id = (data.channel && data.channel.id) || data.id || _chEditId;
        _chEditId = id;
        return id;
    } catch(e) {
        _channelError(_netErrText(e, 'Failed to save channel'));
        return null;
    }
}

async function saveChannel() {
    const btn = document.getElementById('chSaveBtn');
    btn.disabled = true;
    const id = await _persistChannel();
    btn.disabled = false;
    if (!id) return;
    showToast('Channel saved', 'success');
    await loadChannelsList();
}

async function _sendChannelTest(id) {
    const res  = await fetch('/api/notifications/channels/' + encodeURIComponent(id) + '/test', {
        method: 'POST', headers: _csrfHeaders()
    });
    if (!res.ok) return { ok: false, error: await _errText(res, 'Test message could not be sent') };
    const data = await res.json();
    return { ok: !data.error, error: data.error || 'Test message could not be sent.' };
}

async function testChannel() {
    const out = document.getElementById('chTestResult');
    const btn = document.getElementById('chTestBtn');
    out.style.display = '';
    out.style.color = 'var(--muted)';
    out.textContent = 'Sending...';
    btn.disabled = true;
    const id = await _persistChannel();
    if (!id) { btn.disabled = false; out.style.display = 'none'; return; }
    try {
        const result = await _sendChannelTest(id);
        out.style.color   = result.ok ? 'var(--green)' : 'var(--red)';
        out.textContent   = result.ok ? 'Delivered.' : result.error;
    } catch(e) {
        out.style.color = 'var(--red)';
        out.textContent = _netErrText(e, 'Test message could not be sent');
    }
    btn.disabled = false;
}

async function testChannelRow(id) {
    try {
        const result = await _sendChannelTest(id);
        showToast(result.ok ? 'Test message delivered' : result.error, result.ok ? 'success' : 'error');
    } catch(e) {
        showToast(_netErrText(e, 'Test failed'), 'error');
    }
}

async function toggleChannelEnabled(id) {
    const ch = _channelById(id);
    if (!ch) return;
    const knob = document.querySelector(`[data-channel-id="${id}"] .toggle-switch`);
    if (knob) knob.classList.toggle('on');
    try {
        const res  = await fetch('/api/notifications/channels/' + encodeURIComponent(id), {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json', ..._csrfHeaders() },
            body: JSON.stringify({ ...ch, enabled: !ch.enabled })
        });
        if (!res.ok) { showToast(await _errText(res, 'Failed to update channel'), 'error'); loadChannelsList(); return; }
        const data = await res.json();
        if (data.error) showToast(data.error, 'error');
    } catch(e) {
        showToast(_netErrText(e, 'Failed to update channel'), 'error');
    }
    loadChannelsList();
}

async function deleteChannel(id) {
    const ch = _channelById(id);
    if (!ch) return;
    const warning = ch.kind === 'unifiedpush'
        ? `Remove "${ch.name}"? Push notifications to that phone stop until the app registers again.`
        : `Remove channel "${ch.name}"? Events will stop being delivered to it.`;
    if (!await _confirm(warning, 'Remove Channel', 'Remove')) return;
    try {
        const res  = await fetch('/api/notifications/channels/' + encodeURIComponent(id), { method: 'DELETE', headers: _csrfHeaders() });
        if (!res.ok) { showToast(await _errText(res, 'Failed to remove channel'), 'error'); return; }
        const data = await res.json();
        if (data.error) { showToast(data.error, 'error'); return; }
        showToast('Channel removed', 'success');
        loadChannelsList();
    } catch(e) {
        showToast(_netErrText(e, 'Failed to remove channel'), 'error');
    }
}

const BROWSER_NOTIF_SEVERITY_LABELS = { all: 'All events', warning: 'Warnings and errors' };

const BROWSER_NOTIF_NOTES = {
    insecure:    'Desktop notifications need a secure origin. Browsers only expose the Notification API over HTTPS or on localhost, so open Traefik Manager over HTTPS to use them.',
    unsupported: 'This browser does not support desktop notifications.',
    denied:      'This browser is blocking notifications for this site. Allow them in the site permissions, then turn this back on.',
    dismissed:   'Permission was not granted, so desktop notifications stayed off. Turn the toggle on again to ask.',
};

function _browserNotifNote(message, color) {
    const el = document.getElementById('browserNotifNote');
    if (!el) return;
    el.textContent = message || '';
    el.style.color = color || 'var(--muted)';
    el.style.display = message ? '' : 'none';
}

function renderBrowserNotifs() {
    const tog = document.getElementById('toggle-browser-notif');
    if (!tog) return;
    const support = browserNotifSupport();
    const on      = browserNotifsActive();
    tog.classList.toggle('on', on);
    tog.style.opacity = support.ok ? '' : '0.4';
    const fld = document.getElementById('browserNotifSevFld');
    if (fld) fld.style.display = on ? '' : 'none';
    const sev = document.getElementById('browserNotifSeverity');
    if (sev) sev.innerHTML = Object.keys(BROWSER_NOTIF_SEVERITY_LABELS).map(s =>
        `<button type="button" class="agent-chip${browserNotifSeverity() === s ? ' active' : ''}" onclick="selectBrowserNotifSeverity('${s}')">${BROWSER_NOTIF_SEVERITY_LABELS[s]}</button>`).join('');
    if (!support.ok) { _browserNotifNote(BROWSER_NOTIF_NOTES[support.reason], 'var(--yellow)'); return; }
    if (Notification.permission === 'denied') { _browserNotifNote(BROWSER_NOTIF_NOTES.denied, 'var(--yellow)'); return; }
    _browserNotifNote('');
}

async function toggleBrowserNotifs() {
    const support = browserNotifSupport();
    if (!support.ok) { renderBrowserNotifs(); return; }
    if (browserNotifsEnabled()) {
        disableBrowserNotifs();
        renderBrowserNotifs();
        return;
    }
    const result = await enableBrowserNotifs();
    renderBrowserNotifs();
    if (result.ok) { showToast('Desktop notifications on for this browser', 'success'); return; }
    if (Notification.permission !== 'denied') _browserNotifNote(BROWSER_NOTIF_NOTES.dismissed, 'var(--yellow)');
}

function selectBrowserNotifSeverity(sev) {
    setBrowserNotifSeverity(sev);
    renderBrowserNotifs();
}

let _geoipEnabledState = false;

async function loadGeoipSettings() {
    try {
        const r = await fetch('/api/geoip/status').then(r => r.json());
        _geoipEnabledState = !!r.enabled;
        const tog = document.getElementById('toggle-geoip');
        if (tog) tog.classList.toggle('on', _geoipEnabledState);
        if (typeof applyGeoipRelevance === 'function') applyGeoipRelevance();
        const st = document.getElementById('geoipDbStatus');
        if (st) st.textContent = r.available ? `Ready${r.db_date ? ' - ' + r.db_date : ''}` : 'Not downloaded';
        const btn = document.getElementById('geoipUpdateBtn');
        if (btn) btn.innerHTML = r.available ? '<i class="ph-bold ph-arrows-clockwise text-xs"></i> Update' : '<i class="ph-bold ph-download-simple text-xs"></i> Download';
    } catch(_) {}
}

async function toggleGeoip() {
    _geoipEnabledState = !_geoipEnabledState;
    const tog = document.getElementById('toggle-geoip');
    if (tog) tog.classList.toggle('on', _geoipEnabledState);
    try {
        const svRes = await fetch('/api/settings/geoip', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ..._csrfHeaders() },
            body: JSON.stringify({ geoip_enabled: _geoipEnabledState })
        });
        if (!svRes.ok) throw new Error(await _errText(svRes, 'Failed to save'));
        const sv = await svRes.json();
        if (!sv || sv.success === false) throw new Error((sv && (sv.error || sv.message)) || '');
        if (typeof _geoStatusLoaded !== 'undefined') { try { await loadGeoStatus(true); } catch(_) {} }
        if (_geoipEnabledState) {
            const r = await fetch('/api/geoip/status').then(r => r.json());
            if (!r.available) { showToast('Geolocation on - downloading database...', 'info'); updateGeoipDb(); }
        }
        loadGeoipSettings();
    } catch(e) {
        _geoipEnabledState = !_geoipEnabledState;
        if (tog) tog.classList.toggle('on', _geoipEnabledState);
        showToast(_netErrText(e, 'Failed to save'), 'error');
    }
}

async function updateGeoipDb(btn) {
    if (btn) { btn.disabled = true; btn.innerHTML = '<i class="ph-bold ph-spinner-gap animate-spin text-xs"></i> Downloading...'; }
    try {
        const res = await fetch('/api/geoip/update', { method: 'POST', headers: _csrfHeaders() });
        if (!res.ok) { showToast(await _errText(res, 'Download failed'), 'error'); return; }
        const r = await res.json();
        if (r.success) {
            showToast(`GeoIP database updated (DB-IP ${r.db_month})`, 'success');
            if (typeof _geoStatusLoaded !== 'undefined') { _geoStatusLoaded = false; try { await loadGeoStatus(true); } catch(_) {} }
        } else {
            showToast(r.error || r.message || 'Download failed', 'error');
        }
    } catch(e) { showToast(_netErrText(e, 'Download failed'), 'error'); }
    finally { if (btn) btn.disabled = false; loadGeoipSettings(); }
}

async function saveSettings() {
    const domains          = document.getElementById('settingsDomains').value.split(',').map(d => d.trim()).filter(Boolean);
    const resolver         = document.getElementById('settingsCertResolver').value.trim();
    const apiUrl           = document.getElementById('settingsApiUrl').value.trim();
    const acmeJsonPath     = document.getElementById('settingsAcmeJsonPath')?.value.trim() || '';
    const accessLogPath    = document.getElementById('settingsAccessLogPath')?.value.trim() || '';
    const staticConfigPath = document.getElementById('settingsStaticConfigPath')?.value.trim() || '';
    const webhookUrl        = _legacyWebhook.url;
    const webhookType       = _legacyWebhook.type;
    const webhookUsername   = _legacyWebhook.username;
    const webhookPassword   = '';
    const crowdsecLapiUrl     = document.getElementById('settingsCrowdSecUrl')?.value.trim() || '';
    const crowdsecApiKey      = document.getElementById('settingsCrowdSecKey')?.value || '';
    const crowdsecMachineId       = document.getElementById('settingsCrowdSecMachineId')?.value.trim() || '';
    const crowdsecMachinePassword = document.getElementById('settingsCrowdSecMachinePassword')?.value || '';
    const crowdsecClientCert      = document.getElementById('settingsCrowdSecClientCert')?.value.trim() || '';
    const crowdsecClientKey       = document.getElementById('settingsCrowdSecClientKey')?.value.trim() || '';
    const crowdsecCaCert          = document.getElementById('settingsCrowdSecCaCert')?.value.trim() || '';
    const traefikApiUser      = document.getElementById('settingsApiUser')?.value.trim() || '';
    const traefikApiPassword  = document.getElementById('settingsApiPassword')?.value || '';
    if (!domains.length) return;
    try {
        const res  = await fetch('/api/settings', {
            method: 'POST',
            headers: {'Content-Type': 'application/json', 'X-CSRF-Token': _csrfHeaders()['X-CSRF-Token']},
            body: JSON.stringify({ domains, cert_resolver: resolver, traefik_api_url: apiUrl, acme_json_path: acmeJsonPath, access_log_path: accessLogPath, static_config_path: staticConfigPath, webhook_url: webhookUrl, webhook_type: webhookType, webhook_username: webhookUsername, webhook_password: webhookPassword, crowdsec_lapi_url: crowdsecLapiUrl, crowdsec_api_key: crowdsecApiKey, crowdsec_alert_limit: (document.getElementById('settingsCrowdSecAlertLimit')?.value || '').trim(), crowdsec_machine_id: crowdsecMachineId, crowdsec_machine_password: crowdsecMachinePassword, crowdsec_client_cert: crowdsecClientCert, crowdsec_client_key: crowdsecClientKey, crowdsec_ca_cert: crowdsecCaCert, traefik_api_user: traefikApiUser, traefik_api_password: traefikApiPassword })
        });
        if (!res.ok) { showToast(await _errText(res, 'Failed to save settings'), 'error'); return; }
        const data = await res.json();
        if (data.success) {
            document.getElementById('settingsSavedNotice').classList.remove('hidden');
            document.getElementById('pathsSavedNotice')?.classList.remove('hidden');
            setTimeout(() => document.getElementById('pathsSavedNotice')?.classList.add('hidden'), 3000);
            document.getElementById('crowdsecSavedNotice')?.classList.remove('hidden');
            setTimeout(() => document.getElementById('crowdsecSavedNotice')?.classList.add('hidden'), 3000);
            if (crowdsecApiKey) {
                document.getElementById('settingsCrowdSecKey').value = '';
                document.getElementById('crowdsecKeySetHint')?.classList.remove('hidden');
            }
            if (crowdsecMachinePassword) {
                document.getElementById('settingsCrowdSecMachinePassword').value = '';
                document.getElementById('crowdsecMachineSetHint')?.classList.remove('hidden');
            }
            if (traefikApiPassword) {
                document.getElementById('settingsApiPassword').value = '';
                document.getElementById('apiPasswordSetHint')?.classList.remove('hidden');
            }
            if (typeof availableDomains !== 'undefined') {
                availableDomains.length = 0;
                domains.forEach(d => availableDomains.push(d));
                const sel = document.getElementById('domain');
                if (sel) sel.innerHTML = domains.map(d => `<option value="${d}">${d}</option>`).join('');
            }
            setTimeout(() => document.getElementById('settingsSavedNotice').classList.add('hidden'), 3000);
        } else {
            showToast(data.error || data.message || 'Failed to save settings', 'error');
        }
    } catch(e) {
        showToast(_netErrText(e, 'Failed to save settings'), 'error');
    }
}

async function resetCrowdSecConfig() {
    if (!confirm('Remove the saved CrowdSec LAPI URL and API key?')) return;
    document.getElementById('settingsCrowdSecUrl').value = '';
    document.getElementById('settingsCrowdSecKey').value = '';
    document.getElementById('crowdsecKeySetHint')?.classList.add('hidden');
    const csMid = document.getElementById('settingsCrowdSecMachineId');
    if (csMid) csMid.value = '';
    const csMpw = document.getElementById('settingsCrowdSecMachinePassword');
    if (csMpw) csMpw.value = '';
    document.getElementById('crowdsecMachineSetHint')?.classList.add('hidden');
    ['settingsCrowdSecClientCert', 'settingsCrowdSecClientKey', 'settingsCrowdSecCaCert'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });
    await saveSettings();
}

async function testTraefikApi() {
    const result = document.getElementById('apiTestResult');
    result.textContent = 'Testing…';
    result.style.color = 'var(--muted)';
    try {
        const url  = document.getElementById('settingsApiUrl')?.value.trim() || '';
        const user = document.getElementById('settingsApiUser')?.value.trim() || '';
        const pw   = document.getElementById('settingsApiPassword')?.value || '';
        const res  = await fetch('/api/settings/test-connection', {
            method: 'POST',
            headers: {'Content-Type': 'application/json', 'X-CSRF-Token': _csrfHeaders()['X-CSRF-Token']},
            body: JSON.stringify({ url, user, password: pw })
        });
        const d = await res.json();
        if (d.ok) {
            result.textContent = `✓ Connected - Traefik v${d.version}`;
            result.style.color = 'var(--green)';
        } else {
            const err = String(d.error || 'No response from API');
            result.textContent = `✗ ${err.length > 120 ? err.slice(0, 120) + '…' : err}`;
            result.title = err;
            result.style.color = 'var(--red)';
        }
    } catch(e) {
        result.textContent = '✗ ' + _netErrText(e, 'Connection failed');
        result.style.color = 'var(--red)';
    }
}

function _renderBackupList(containerId, backups) {
    const list = document.getElementById(containerId);
    if (!list) return;
    if (!backups.length) {
        list.innerHTML = `<div class="text-center py-8" style="color:var(--muted)"><i class="ph-light ph-archive-box text-4xl block mb-2 opacity-30"></i><p>No backups yet</p></div>`;
        return;
    }
    list.innerHTML = backups.map(b => `
        <div class="sc-set">
            <div class="sc-set-l">
                <div class="sc-set-n">${b.name}</div>
                <div class="sc-set-d">${b.modified} · ${formatBytes(b.size)}</div>
            </div>
            <div class="sc-set-v">
                ${b.restoreBlocked
                    ? `<button class="btn-secondary text-xs py-1 px-2.5" disabled style="opacity:.5;cursor:not-allowed" title="This agent is running an older version that restores static backups to the wrong path. Update the agent, then restore.">
                        <i class="ph-bold ph-arrow-counter-clockwise text-xs"></i> Restore
                    </button>`
                    : `<button onclick="restoreBackup('${b.name}')" class="btn-secondary text-xs py-1 px-2.5">
                    <i class="ph-bold ph-arrow-counter-clockwise text-xs"></i> Restore
                </button>`}
                <button onclick="deleteBackup('${b.name}')" class="btn-icon" title="Delete" style="color:var(--red)">
                    <i class="ph-bold ph-trash text-sm"></i>
                </button>
            </div>
        </div>
    `).join('');
}

async function loadBackups() {
    const isAgent    = typeof _activeAgent !== 'undefined' && !!_activeAgent;
    const staticTab  = document.getElementById('backup-tab-static');
    const chip = document.getElementById('backupRemoteChip');
    if (chip) { chip.textContent = isAgent ? _activeAgent.name : ''; chip.style.display = isAgent ? '' : 'none'; }
    const retRow     = document.getElementById('backupRetentionRow');
    const retEnvNote = document.getElementById('backupRetentionEnvNote');
    if (retRow)     retRow.style.display     = isAgent ? 'none' : 'flex';
    if (retEnvNote) retEnvNote.style.display = isAgent ? '' : 'none';
    const gitPane = document.getElementById('backup-sub-git');
    if (gitPane && gitPane.style.display !== 'none') loadGitTab();
    if (!isAgent) {
        try {
            const sres = await fetch('/api/settings');
            const sdat = await sres.json();
            _setVal('backupKeepCount', (sdat.backup_keep_count ?? 0));
        } catch (e) {}
    }
    const routesList  = document.getElementById('sm-backups-list');
    const staticList  = document.getElementById('sm-static-backups-list');
    const spinner = `<div class="text-center py-8" style="color:var(--muted)"><i class="ph-light ph-spinner-gap text-2xl animate-spin block mb-2"></i>Loading…</div>`;
    if (routesList) routesList.innerHTML = spinner;
    if (staticList) staticList.innerHTML = spinner;
    try {
        const res  = await _backupFetch('/api/backups');
        if (!res.ok) {
            const msg = await _errText(res, 'Could not load backups');
            if (routesList) routesList.innerHTML = `<p class="text-sm px-1" style="color:var(--red)">${_esc(msg)}</p>`;
            if (staticList) staticList.innerHTML = '';
            return;
        }
        const raw     = await res.json();
        const rawArr  = Array.isArray(raw) ? raw : (raw.backups || []);
        const oldAgent = isAgent && rawArr.length > 0 && !rawArr.some(b => b.kind);
        const kindOf  = b => b.kind || (/^traefik\.ya?ml\.\d{8}_\d{6}\.bak$/.test(b.name) ? 'static' : 'routes');
        const backups = rawArr.map(b => ({ ...b, kind: kindOf(b), modified: b.modified || b.date || '',
            restoreBlocked: isAgent && oldAgent && kindOf(b) === 'static' }));
        const routes  = backups.filter(b => b.kind !== 'static');
        const statics = backups.filter(b => b.kind === 'static');
        const hasStaticSide = !isAgent || !!raw.static_configured || statics.length > 0;
        if (staticTab) staticTab.style.display = hasStaticSide ? '' : 'none';
        _renderBackupList('sm-backups-list', routes);
        _renderBackupList('sm-static-backups-list', statics);
        if (isAgent && !hasStaticSide && document.getElementById('backup-sub-static')?.style.display !== 'none') {
            switchBackupTab('routes', document.getElementById('backup-tab-routes'));
        }
    } catch (e) {
        const msg = _esc(_netErrText(e, 'Failed to load backups'));
        if (routesList) routesList.innerHTML = `<p class="text-sm px-1" style="color:var(--red)">${msg}</p>`;
        if (staticList) staticList.innerHTML = `<p class="text-sm px-1" style="color:var(--red)">${msg}</p>`;
    }
}

async function saveBackupKeepCount(sourceId) {
    const input = document.getElementById(sourceId || 'backupKeepCount');
    if (!input) return;
    const btnId = 'backupKeepBtn';
    const btn   = document.getElementById(btnId);
    let n = parseInt(input.value, 10);
    if (isNaN(n) || n < 0) n = 0;
    _setVal('backupKeepCount', n);
    if (btn) { btn.disabled = true; btn.innerHTML = '<i class="ph-light ph-spinner-gap animate-spin text-xs"></i> Saving…'; }
    try {
        const res = await fetch('/api/settings/backup-retention', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ..._csrfHeaders() },
            body: JSON.stringify({ backup_keep_count: n }),
        });
        if (res.ok) showToast('Retention saved', 'success');
        else        showToast(await _errText(res, 'Failed to save retention'), 'error');
    } catch (e) {
        showToast(_netErrText(e, 'Failed to save retention'), 'error');
    }
    if (btn) { btn.disabled = false; btn.innerHTML = '<i class="ph-bold ph-floppy-disk"></i> Save'; }
}

async function createAndLoadBackups() {
    const btn = document.querySelector('[onclick="createAndLoadBackups()"]');
    if (btn) { btn.disabled = true; btn.innerHTML = '<i class="ph-light ph-spinner-gap animate-spin"></i> Creating…'; }
    try {
        const res  = await _backupFetch('/api/backup/create', { method: 'POST', headers: _csrfHeaders() });
        if (!res.ok) { showToast(await _errText(res, 'Backup failed'), 'error'); return; }
        const data = await res.json();
        if (data.success || data.ok) {
            const n = data.count || 1;
            showToast(`Backup created (${n} file${n > 1 ? 's' : ''})`, 'success');
            loadBackups();
        } else {
            showToast('Backup failed: ' + (data.error || data.message || 'the server did not say why'), 'error');
        }
    } catch(e) { showToast(_netErrText(e, 'Backup failed'), 'error'); }
    finally {
        if (btn) { btn.disabled = false; btn.innerHTML = '<i class="ph-bold ph-plus"></i> Create Backup'; }
    }
}

async function restoreBackup(name) {
    if (!await _confirm(`Restore "${name}"? This replaces the config file it came from. Your current config is backed up first.`,
                        'Restore Backup', 'Restore', 'RESTORE')) return;
    try {
        const res  = await _backupFetch(`/api/restore/${encodeURIComponent(name)}`, { method: 'POST', headers: _csrfHeaders() });
        if (!res.ok) { showToast(await _errText(res, 'Restore failed'), 'error'); return; }
        const data = await res.json();
        if (data.success || data.ok) {
            showToast('Backup restored successfully!', 'success');
            closeSettingsModal();
            setTimeout(() => location.reload(), 1500);
        } else {
            showToast('Restore failed: ' + (data.error || data.message || 'the server did not say why'), 'error');
        }
    } catch (e) {
        showToast(_netErrText(e, 'Restore failed'), 'error');
    }
}

async function deleteBackup(name) {
    if (!await _confirm(`Delete backup "${name}"?`, 'Delete Backup', 'Delete')) return;
    try {
        const res  = await _backupFetch(`/api/backup/delete/${encodeURIComponent(name)}`, { method: 'POST', headers: _csrfHeaders() });
        if (!res.ok) { showToast(await _errText(res, 'Delete failed'), 'error'); return; }
        const data = await res.json();
        if (data.success || data.ok) { showToast('Backup deleted', 'success'); loadBackups(); }
        else showToast('Delete failed: ' + (data.error || data.message || 'the server did not say why'), 'error');
    } catch(e) { showToast(_netErrText(e, 'Delete failed'), 'error'); }
}

function formatBytes(bytes) {
    if (bytes < 1024) return bytes + ' B';
    return (bytes / 1024).toFixed(1) + ' KB';
}

function toggleTraefikBadge() {
    const show = tmPref('showTraefikBadge');
    tmSetPref('showTraefikBadge', !show);
    _applyTraefikBadgeVisibility();
}

function toggleRouteIcons() {
    const show = tmPref('showRouteIcons');
    tmSetPref('showRouteIcons', !show);
    window._showRouteIcons = !show;
    const tog = document.getElementById('toggle-route-icons');
    if (tog) tog.classList.toggle('on', !show);
    if (typeof renderRouteGrid === 'function' && window._lastRenderedApps) {
        renderRouteGrid(window._lastRenderedApps);
        if (typeof filterRoutes === 'function') filterRoutes();
    }
}

function _applyTraefikBadgeVisibility() {
    const show = tmPref('showTraefikBadge');
    const hasVersion = (document.getElementById('versionText').textContent || '').trim() !== '-';
    const badge  = document.getElementById('versionBadge');
    const badgeM = document.getElementById('versionBadgeMobile');
    if (badge)  badge.classList.toggle('hidden', !show || !hasVersion);
    if (badgeM) {
        badgeM.classList.toggle('hidden', !show || !hasVersion);
        if (show && hasVersion) badgeM.classList.add('flex');
    }
    const tog = document.getElementById('toggle-traefik-badge');
    if (tog) tog.classList.toggle('on', show);
}

function toggleTmBadge() {
    const show = tmPref('showTmBadge');
    tmSetPref('showTmBadge', !show);
    _applyTmBadgeVisibility();
}

function _applyTmBadgeVisibility() {
    const show = tmPref('showTmBadge');
    const hasVersion = (document.getElementById('tmVersionText').textContent || '').trim() !== '-';
    const badge  = document.getElementById('tmVersionBadge');
    const badgeM = document.getElementById('tmVersionBadgeMobile');
    if (badge)  badge.classList.toggle('hidden', !show || !hasVersion);
    if (badgeM) {
        badgeM.classList.toggle('hidden', !show || !hasVersion);
        if (show && hasVersion) badgeM.classList.add('flex');
    }
    const tog = document.getElementById('toggle-tm-badge');
    if (tog) tog.classList.toggle('on', show);
}

function toggleShortcutsBtn() {
    const show = tmPref('showShortcutsBtn');
    tmSetPref('showShortcutsBtn', !show);
    document.documentElement.classList.toggle('tm-hide-shortcuts', show);
    const t = document.getElementById('toggle-shortcuts-btn');
    if (t) t.classList.toggle('on', !show);
}

function toggleIpDiagBtn() {
    const show = tmPref('showIpDiagBtn');
    tmSetPref('showIpDiagBtn', !show);
    document.documentElement.classList.toggle('tm-hide-ipdiag', show);
    const t = document.getElementById('toggle-ipdiag-btn');
    if (t) t.classList.toggle('on', !show);
}

function toggleDocsLink() {
    const show = tmPref('showDocsLink');
    tmSetPref('showDocsLink', !show);
    _applyDocsLinkVisibility();
}

function _applyDocsLinkVisibility() {
    const show = tmPref('showDocsLink');
    document.documentElement.classList.toggle('tm-hide-docs', !show);
    document.querySelectorAll('.nav-docs-link').forEach(el => el.classList.toggle('hidden', !show));
    const tog = document.getElementById('toggle-docs-link');
    if (tog) tog.classList.toggle('on', show);
}

function toggleApiLink() {
    const show = tmPref('showApiLink');
    tmSetPref('showApiLink', !show);
    _applyApiLinkVisibility();
}

function _applyApiLinkVisibility() {
    const show = tmPref('showApiLink');
    document.documentElement.classList.toggle('tm-hide-api', !show);
    document.querySelectorAll('.nav-api-link').forEach(el => el.classList.toggle('hidden', !show));
    const tog = document.getElementById('toggle-api-link');
    if (tog) tog.classList.toggle('on', show);
}

function renderReleaseNotes(md) {
    function esc(s) {
        return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }
    function inline(s) {
        return esc(s)
            .replace(/\*\*(.+?)\*\*/g, '<strong style="color:var(--text)">$1</strong>')
            .replace(/`([^`]+)`/g, '<code style="background:var(--border);padding:1px 5px;border-radius:3px;font-size:11px;font-family:monospace">$1</code>')
            .replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g, '<a href="$2" target="_blank" style="color:var(--blue);text-decoration:none">$1</a>');
    }
    function isTableRow(l) { const t = l.trim(); return t.startsWith('|') && t.endsWith('|'); }
    function isSepRow(l) { return l.replace(/^\||\|$/g, '').split('|').every(c => /^[\s\-:]+$/.test(c)); }
    function parseCells(l) { return l.replace(/^\||\|$/g, '').split('|').map(c => c.trim()); }

    const lines = md.replace(/\r\n/g, '\n').split('\n');
    let html = '', inList = false, i = 0;

    while (i < lines.length) {
        const line = lines[i].trimEnd();

        if (isTableRow(line)) {
            if (inList) { html += '</ul>'; inList = false; }
            const block = [];
            while (i < lines.length && isTableRow(lines[i].trimEnd())) { block.push(lines[i].trimEnd()); i++; }
            const rows = block.filter(l => !isSepRow(l));
            if (rows.length) {
                html += '<table style="width:100%;border-collapse:collapse;font-size:11px;margin:6px 0">';
                rows.forEach((row, idx) => {
                    const tag = idx === 0 ? 'th' : 'td';
                    const st  = idx === 0
                        ? 'padding:3px 8px;border-bottom:1px solid var(--border);color:var(--text);font-weight:600;text-align:left;white-space:nowrap'
                        : 'padding:3px 8px;border-bottom:1px solid var(--border);color:var(--muted)';
                    html += '<tr>' + parseCells(row).map(c => `<${tag} style="${st}">${inline(c)}</${tag}>`).join('') + '</tr>';
                });
                html += '</table>';
            }
            continue;
        }

        if (/^>\s?/.test(line)) {
            if (inList) { html += '</ul>'; inList = false; }
            const quote = [];
            while (i < lines.length && /^>\s?/.test(lines[i].trimEnd())) {
                quote.push(lines[i].trimEnd().replace(/^>\s?/, ''));
                i++;
            }
            const ALERTS = {
                NOTE:      ['var(--blue)',   'ph-info'],
                TIP:       ['var(--green)',  'ph-lightbulb'],
                IMPORTANT: ['var(--purple)', 'ph-seal-warning'],
                WARNING:   ['var(--orange)', 'ph-warning'],
                CAUTION:   ['var(--red)',    'ph-prohibit'],
            };
            const tag  = quote.length ? quote[0].trim().match(/^\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]$/i) : null;
            const key  = tag ? tag[1].toUpperCase() : null;
            const col  = key ? ALERTS[key][0] : 'var(--blue)';
            const body = (key ? quote.slice(1) : quote).filter(l => l.trim()).map(inline).join('<br>');
            const head = key
                ? `<div style="font-weight:700;color:${col};display:flex;align-items:center;gap:5px;margin-bottom:3px">`
                    + `<i class="ph-bold ${ALERTS[key][1]}"></i>${key.charAt(0)}${key.slice(1).toLowerCase()}</div>`
                : '';
            html += `<div style="margin:8px 0;padding:7px 10px;border-left:3px solid ${col};`
                + `background:color-mix(in srgb, ${col} 8%, transparent);border-radius:0 4px 4px 0;`
                + `font-size:11px;color:var(--muted)">${head}${body}</div>`;
            continue;
        }

        if (/^---+$/.test(line.trim())) {
            if (inList) { html += '</ul>'; inList = false; }
            html += '<hr style="border:none;border-top:1px solid var(--border);margin:10px 0">';
            i++; continue;
        }

        if (/^#{1,4} /.test(line)) {
            if (inList) { html += '</ul>'; inList = false; }
            const lvl   = line.match(/^(#{1,4}) /)[1].length;
            const text  = inline(line.replace(/^#{1,4} /, ''));
            const sz    = lvl <= 2 ? '12px' : '11px';
            const mt    = lvl <= 2 ? '14px' : '10px';
            const extra = lvl <= 2 ? 'border-bottom:1px solid var(--border);padding-bottom:4px;' : '';
            html += `<div style="font-weight:700;color:var(--text);font-size:${sz};margin:${mt} 0 4px;${extra}">${text}</div>`;
            i++; continue;
        }

        if (/^[-*] /.test(line)) {
            if (!inList) { html += '<ul style="margin:4px 0 6px;padding-left:16px;list-style:disc">'; inList = true; }
            html += `<li style="margin:2px 0;color:var(--text)">${inline(line.replace(/^[-*] /, ''))}</li>`;
            i++; continue;
        }

        if (line.trim() === '') {
            if (inList) { html += '</ul>'; inList = false; }
            i++; continue;
        }

        if (inList) { html += '</ul>'; inList = false; }
        html += `<p style="margin:3px 0;color:var(--muted)">${inline(line)}</p>`;
        i++;
    }

    if (inList) html += '</ul>';
    return html;
}

function _uiPref(key) { return tmPref(key); }

function _applyEntrypointsVisibility() {
    const bar  = document.getElementById('entrypointsBar');
    const list = document.getElementById('entrypointsList');
    if (!bar) return;
    const hasData = list && list.children.length > 0;
    bar.classList.toggle('hidden', !_uiPref('showEntrypoints') || !hasData);
}

function applyUiPrefs() {
    const html = document.documentElement;
    const showStats = _uiPref('showStatCards');
    const compact = tmPref('compactStatCards');
    html.classList.toggle('tm-hide-stats', !showStats);
    html.classList.toggle('tm-compact-stats', compact);
    html.classList.toggle('tm-hide-entrypoints', !_uiPref('showEntrypoints'));
    const _act = document.querySelector('.tab-content.active');
    html.classList.toggle('tm-stats-here', !!_act && _statTabSet().has(_act.id.replace(/^tab-/, '')));
    const _pref = tmPref('layoutMode');
    html.classList.toggle('tm-fixed', _pref === 'fixed' || _pref === 'classic');
    buildSideNav();
    placeStatCards();
    const statsPanelEl = document.getElementById('statsPanel');
    if (statsPanelEl) statsPanelEl.classList.toggle('hidden', !showStats);
    _applyEntrypointsVisibility();
    const overviewSection = document.getElementById('overviewSection');
    const barEl = document.getElementById('entrypointsBar');
    const barShown = !!barEl && !barEl.classList.contains('hidden');
    if (overviewSection) overviewSection.classList.toggle('hidden', !showStats && !barShown);
    const panel = document.getElementById('statsPanel');
    if (panel) panel.classList.toggle('sig-compact', compact);
    const logPanel = document.getElementById('logStatsPanel');
    if (logPanel) logPanel.classList.toggle('sig-compact', compact);
}

function loadUiTogglesIntoModal() {
    const on = _statTabSet();
    STAT_TABS.forEach(t => {
        const b = document.getElementById('scope-stats-' + t);
        if (b) b.className = 'proto-btn' + (on.has(t) ? ' active-http' : '');
    });
    const _lm = tmPref('layoutMode');
    const layout = (_lm === 'fixed' || _lm === 'classic') ? 'fixed' : 'fluid';
    const lFl = document.getElementById('layout-fluid');
    const lFx = document.getElementById('layout-fixed');
    if (lFl) lFl.className = 'proto-btn' + (layout === 'fluid' ? ' active-http' : '');
    if (lFx) lFx.className = 'proto-btn' + (layout === 'fixed' ? ' active-http' : '');
    const dens = tmPref('dashPodDensity') === 'icons' ? 'icons' : 'list';
    const dL = document.getElementById('dashdens-list');
    const dI = document.getElementById('dashdens-icons');
    if (dL) dL.className = 'proto-btn' + (dens === 'list' ? ' active-http' : '');
    if (dI) dI.className = 'proto-btn' + (dens === 'icons' ? ' active-http' : '');
    const sc = document.getElementById('toggle-ui-statcards');
    const ep = document.getElementById('toggle-ui-entrypoints');
    const cs = document.getElementById('toggle-ui-compact-stats');
    const sh = document.getElementById('toggle-shortcuts-btn');
    if (sc) sc.classList.toggle('on', _uiPref('showStatCards'));
    if (ep) ep.classList.toggle('on', _uiPref('showEntrypoints'));
    if (cs) cs.classList.toggle('on', tmPref('compactStatCards'));
    if (sh) sh.classList.toggle('on', tmPref('showShortcutsBtn'));
    const ipd = document.getElementById('toggle-ipdiag-btn');
    if (ipd) ipd.classList.toggle('on', tmPref('showIpDiagBtn'));
    const ri = document.getElementById('toggle-route-icons');
    if (ri) ri.classList.toggle('on', tmPref('showRouteIcons'));
    loadGeoipSettings();
}

function toggleUiPref(key) {
    tmSetPref(key, !tmPref(key));
    applyUiPrefs();
    loadUiTogglesIntoModal();
}

function setLayoutMode(v) {
    tmSetPref('layoutMode', v);
    loadUiTogglesIntoModal();
    applyUiPrefs();
    _rerenderCardGrids();
}

function _rerenderCardGrids() {
    if (typeof renderRouteGrid === 'function' && window._lastRenderedApps) {
        renderRouteGrid(window._lastRenderedApps);
        if (typeof filterRoutes === 'function') filterRoutes();
    }
    if (typeof renderMwGrid === 'function' && typeof _allMiddlewares !== 'undefined' && _allMiddlewares) {
        renderMwGrid(_allMiddlewares);
        if (typeof filterMw === 'function') filterMw();
    }
    if (typeof renderServicesTable === 'function' && typeof _allServices !== 'undefined' && _allServices.length) {
        renderServicesTable();
    }
    if (typeof renderCertCards === 'function' && typeof _allCerts !== 'undefined' && _allCerts.length) {
        renderCertCards();
    }
    if (typeof renderTlsOptions === 'function' && typeof _tlsOptions !== 'undefined' && _tlsOptions.length) {
        renderTlsOptions(_tlsOptions);
    }
    if (typeof rerenderStaticBody === 'function') rerenderStaticBody();
    if (typeof renderPluginCards === 'function' && typeof _allPlugins !== 'undefined' && _allPlugins.length) {
        renderPluginCards();
    }
    const active = document.querySelector('.tab-content.active');
    if (active && typeof switchTab === 'function') switchTab(active.id.replace(/^tab-/, ''));
}

function toggleStatTab(tab) {
    const on = _statTabSet();
    if (on.has(tab)) on.delete(tab); else on.add(tab);
    tmSetPref('statBarScope', STAT_TABS.filter(t => on.has(t)).join(',') || 'none');
    applyUiPrefs();
    loadUiTogglesIntoModal();
    placeStatCards();
}

function setDashPodDensity(v) {
    tmSetPref('dashPodDensity', v);
    loadUiTogglesIntoModal();
    if (typeof window.refreshDashboardTab === 'function') window.refreshDashboardTab();
}

let _otpEnabled = false;

async function loadOtpStatus() {
    try {
        const res  = await fetch('/api/auth/otp/status');
        const data = await res.json();
        _otpEnabled = !!data.otp_enabled;
        const label = document.getElementById('otpStatusLabel');
        const btn   = document.getElementById('otpToggleBtnLabel');
        if (label) {
            label.textContent  = _otpEnabled ? 'Enabled' : 'Disabled';
            label.style.color  = _otpEnabled ? 'var(--green)' : 'var(--muted)';
        }
        if (btn) btn.textContent = _otpEnabled ? 'Disable 2FA' : 'Enable 2FA';
    } catch(e) {}
}

async function otpToggleFlow() {
    if (_otpEnabled) {
        if (!await _confirm('Disable two-factor authentication?', 'Disable 2FA', 'Disable')) return;
        try {
            const res  = await fetch('/api/auth/otp/disable', { method: 'POST', headers: _csrfHeaders() });
            if (!res.ok) { showToast(await _errText(res, 'Could not disable 2FA'), 'error'); return; }
            const data = await res.json();
            if (data.success) { showToast('2FA disabled', 'success'); loadOtpStatus(); }
            else showToast(data.error || data.message || 'Could not disable 2FA', 'error');
        } catch(e) { showToast(_netErrText(e, 'Could not disable 2FA'), 'error'); }
        return;
    }
    try {
        const res  = await fetch('/api/auth/otp/setup', { method: 'POST', headers: _csrfHeaders() });
        if (!res.ok) { showToast(await _errText(res, 'Failed to start 2FA setup'), 'error'); return; }
        const data = await res.json();
        if (data.error) { showToast(data.error, 'error'); return; }

        document.getElementById('otpManualSecret').textContent = data.secret;
        const canvas = document.getElementById('otpQrCanvas');
        canvas.innerHTML = '';
        const qrDiv = document.createElement('div');
        canvas.appendChild(qrDiv);

        if (typeof QRCode !== 'undefined') {
            new QRCode(qrDiv, { text: data.uri, width: 160, height: 160, correctLevel: QRCode.CorrectLevel.M });
        } else {
            qrDiv.innerHTML = `<div class="text-xs" style="color:var(--muted)">Manual entry: use the secret below.</div>`;
        }

        const flow = document.getElementById('otpSetupFlow');
        flow.style.display = 'flex';
        flow.classList.remove('hidden');
        document.getElementById('otpVerifyCode').value = '';
        const msg = document.getElementById('otpSetupMsg');
        if (msg) msg.classList.add('hidden');
    } catch(e) { showToast(_netErrText(e, 'Failed to start 2FA setup'), 'error'); }
}

async function otpConfirmEnable() {
    const code = (document.getElementById('otpVerifyCode').value || '').trim();
    const msg  = document.getElementById('otpSetupMsg');
    const show = (text, ok) => {
        msg.textContent = text;
        msg.style.background = ok ? 'rgba(63,185,80,0.1)' : 'rgba(248,81,73,0.1)';
        msg.style.border     = ok ? '1px solid rgba(63,185,80,0.3)' : '1px solid rgba(248,81,73,0.3)';
        msg.style.color      = ok ? 'var(--green)' : 'var(--red)';
        msg.classList.remove('hidden');
    };
    if (!code || code.length !== 6) return show('Enter the 6-digit code.', false);
    try {
        const res  = await fetch('/api/auth/otp/enable', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': _csrfHeaders()['X-CSRF-Token'] },
            body: JSON.stringify({ code })
        });
        if (!res.ok) return show(await _errText(res, 'Could not enable 2FA'), false);
        const data = await res.json();
        if (data.success) {
            show('2FA enabled successfully!', true);
            setTimeout(() => { otpCancelSetup(); loadOtpStatus(); }, 1200);
        } else {
            show(data.error || 'Invalid code. Try again.', false);
        }
    } catch(e) { show(_netErrText(e, 'Could not enable 2FA'), false); }
}

function otpCancelSetup() {
    const flow = document.getElementById('otpSetupFlow');
    flow.style.display = 'none';
    flow.classList.add('hidden');
}

async function loadOidcStatus() {
    try {
        const res  = await fetch('/api/auth/oidc');
        const data = await res.json();
        const label = document.getElementById('oidcStatusLabel');
        const btn   = document.getElementById('oidcToggleBtn');
        const isOn  = !!data.oidc_enabled;
        if (label) { label.textContent = isOn ? 'Enabled' : 'Disabled'; label.style.color = isOn ? 'var(--green)' : 'var(--muted)'; }
        if (btn)   btn.textContent = isOn ? 'Disable' : 'Enable';
        const set = e => { const el = document.getElementById(e[0]); if (el) el.value = e[1] || ''; };
        set(['oidcProviderUrl', data.oidc_provider_url]);
        set(['oidcClientId',    data.oidc_client_id]);
        set(['oidcDisplayName', data.oidc_display_name]);
        set(['oidcAllowedEmails', data.oidc_allowed_emails]);
        set(['oidcAllowedGroups', data.oidc_allowed_groups]);
        set(['oidcGroupsClaim', data.oidc_groups_claim]);
        const _anyEl = document.getElementById('oidcAllowAny'); if (_anyEl) _anyEl.checked = !!data.oidc_allow_any_authenticated;
        const _autoEl = document.getElementById('oidcAutoLogin'); if (_autoEl) _autoEl.checked = !!data.oidc_auto_login;
        document.getElementById('oidcClientSecret') && (document.getElementById('oidcClientSecret').value = '');
        const secretLabel = document.getElementById('oidcSecretSetLabel');
        if (secretLabel) secretLabel.classList.toggle('hidden', !data.oidc_client_secret_set);
    } catch(e) {}
}

async function oidcToggleEnabled() {
    const btn   = document.getElementById('oidcToggleBtn');
    const label = document.getElementById('oidcStatusLabel');
    const isOn  = label && label.textContent.trim() === 'Enabled';
    const url   = document.getElementById('oidcProviderUrl')?.value.trim() || '';
    const id    = document.getElementById('oidcClientId')?.value.trim() || '';
    const sec   = document.getElementById('oidcClientSecret')?.value.trim() || '';
    const disp  = document.getElementById('oidcDisplayName')?.value.trim() || 'OIDC';
    const ae    = document.getElementById('oidcAllowedEmails')?.value.trim() || '';
    const ag    = document.getElementById('oidcAllowedGroups')?.value.trim() || '';
    const gc    = document.getElementById('oidcGroupsClaim')?.value.trim() || 'groups';
    const any   = document.getElementById('oidcAllowAny')?.checked || false;
    const auto  = document.getElementById('oidcAutoLogin')?.checked || false;
    try {
        const res = await fetch('/api/auth/oidc', {
            method: 'POST',
            headers: {'Content-Type': 'application/json', 'X-CSRF-Token': _csrfHeaders()['X-CSRF-Token']},
            body: JSON.stringify({ oidc_enabled: !isOn, oidc_provider_url: url, oidc_client_id: id, oidc_client_secret: sec, oidc_display_name: disp, oidc_allowed_emails: ae, oidc_allowed_groups: ag, oidc_groups_claim: gc, oidc_allow_any_authenticated: any, oidc_auto_login: auto })
        });
        if (!res.ok) { showToast(await _errText(res, 'Failed to update OIDC'), 'error'); return; }
        const data = await res.json();
        if (data.ok) {
            if (data.reauth_required) return _redirectToLoginAfterAuthEnable('OIDC enabled');
            loadOidcStatus();
        } else {
            showToast(data.error || data.message || 'Failed to update OIDC', 'error');
        }
    } catch(e) { showToast(_netErrText(e, 'Failed to update OIDC'), 'error'); }
}

function _redirectToLoginAfterAuthEnable(what) {
    showToast(`${what} - authentication is now required, redirecting to sign in`, 'info');
    setTimeout(() => { window.location.href = tmUrl('/login'); }, 1200);
}

async function saveOidcConfig() {
    const url  = document.getElementById('oidcProviderUrl')?.value.trim() || '';
    const id   = document.getElementById('oidcClientId')?.value.trim() || '';
    const sec  = document.getElementById('oidcClientSecret')?.value.trim() || '';
    const disp = document.getElementById('oidcDisplayName')?.value.trim() || 'OIDC';
    const ae   = document.getElementById('oidcAllowedEmails')?.value.trim() || '';
    const ag   = document.getElementById('oidcAllowedGroups')?.value.trim() || '';
    const gc   = document.getElementById('oidcGroupsClaim')?.value.trim() || 'groups';
    const any  = document.getElementById('oidcAllowAny')?.checked || false;
    const auto = document.getElementById('oidcAutoLogin')?.checked || false;
    const label = document.getElementById('oidcStatusLabel');
    const isOn  = label && label.textContent.trim() === 'Enabled';
    try {
        const res = await fetch('/api/auth/oidc', {
            method: 'POST',
            headers: {'Content-Type': 'application/json', 'X-CSRF-Token': _csrfHeaders()['X-CSRF-Token']},
            body: JSON.stringify({ oidc_enabled: isOn, oidc_provider_url: url, oidc_client_id: id, oidc_client_secret: sec, oidc_display_name: disp, oidc_allowed_emails: ae, oidc_allowed_groups: ag, oidc_groups_claim: gc, oidc_allow_any_authenticated: any, oidc_auto_login: auto })
        });
        if (!res.ok) { showToast(await _errText(res, 'Failed to save OIDC config'), 'error'); return; }
        const data = await res.json();
        if (data.ok) {
            if (data.reauth_required) return _redirectToLoginAfterAuthEnable('OIDC saved');
            const msg = document.getElementById('oidcSavedMsg');
            if (msg) { msg.classList.remove('hidden'); setTimeout(() => msg.classList.add('hidden'), 2500); }
            loadOidcStatus();
        } else {
            showToast(data.error || data.message || 'Failed to save OIDC config', 'error');
        }
    } catch(e) { showToast(_netErrText(e, 'Failed to save OIDC config'), 'error'); }
}

async function testOidcProvider() {
    const url    = document.getElementById('oidcProviderUrl')?.value.trim() || '';
    const result = document.getElementById('oidcTestResult');
    if (!url) return;
    if (result) { result.textContent = 'Testing...'; result.style.color = 'var(--muted)'; }
    try {
        const res  = await fetch('/api/auth/oidc/test', {
            method: 'POST',
            headers: {'Content-Type': 'application/json', 'X-CSRF-Token': _csrfHeaders()['X-CSRF-Token']},
            body: JSON.stringify({ provider_url: url })
        });
        const data = await res.json();
        if (result) {
            result.textContent = data.ok
                ? `Provider reachable - issuer: ${data.issuer}. Credentials are not checked until you sign in.`
                : `Error: ${data.error}`;
            result.style.color = data.ok ? 'var(--green)' : 'var(--red)';
        }
    } catch(e) {
        if (result) { result.textContent = _netErrText(e, 'Request failed'); result.style.color = 'var(--red)'; }
    }
}

let _agentWizId   = null;
let _agentWizKey  = null;
let _agentWizStep = 0;
let _agentRestartMethod = '';

async function refreshAgentRegistry() {
    try {
        const res = await fetch('/api/agents');
        if (!res.ok) return;
        const data = await res.json();
        if (typeof updateServerSwitcher === 'function') updateServerSwitcher(data.agents || []);
    } catch (e) {}
}

async function loadAgentsList() {
    const body = document.getElementById('agentsListBody');
    if (!body) return;
    document.getElementById('agentListView').style.display    = 'flex';
    document.getElementById('agentWizardView').style.display  = 'none';
    document.getElementById('agentKeysView').style.display    = 'none';
    try {
        const res  = await fetch('/api/agents');
        if (!res.ok) {
            body.innerHTML = `<div class="text-center py-6 text-xs" style="color:var(--red)">${_esc(await _errText(res, 'Failed to load agents'))}</div>`;
            return;
        }
        const data = await res.json();
        const agents = data.agents || [];
        if (!agents.length) {
            body.innerHTML = `<div class="text-center py-8" style="color:var(--muted)"><i class="ph-light ph-robot text-4xl block mb-2 opacity-30"></i><p class="text-xs font-medium mb-1">No agents configured</p><p class="text-xs">Add a remote agent to manage multiple Traefik instances from one TM.</p></div>`;
            updateServerSwitcher(agents);
            return;
        }
        body.innerHTML = agents.map(a => `
            <div class="sc-set" data-agent-id="${a.id}">
                <div class="sc-set-l">
                    <div class="flex items-center gap-2">
                        <span class="w-2 h-2 rounded-full flex-shrink-0" id="agent-dot-${a.id}" style="background:var(--muted)"></span>
                        <span class="agent-name-label sc-set-n truncate">${_esc(a.name)}</span>
                    </div>
                    <div class="flex items-center gap-1">
                        <span class="agent-url-label sc-set-d truncate">${_esc(a.url)}</span>
                    </div>
                </div>
                <div class="sc-set-v">
                    <button onclick="openAgentKeys('${a.id}',${_jsArg(a.name)})" class="btn-icon" title="API Keys"><i class="ph-bold ph-key text-xs"></i></button>
                    <button onclick="openAgentSetup('${a.id}')" class="btn-icon" title="Edit Settings"><i class="ph-bold ph-gear text-xs"></i></button>
                    <button onclick="deleteAgent('${a.id}',${_jsArg(a.name)})" class="btn-icon" title="Remove" style="color:var(--red)"><i class="ph-bold ph-trash text-xs"></i></button>
                </div>
            </div>`).join('');
        agents.forEach(a => pingAgent(a.id, a.url));
        updateServerSwitcher(agents);
    } catch(e) {
        body.innerHTML = `<div class="text-center py-6 text-xs" style="color:var(--red)">${_esc(_netErrText(e, 'Failed to load agents'))}</div>`;
    }
}

let _keysAgentId = null;

function openAgentKeys(agentId, agentName) {
    _keysAgentId = agentId;
    document.getElementById('agentKeysTitle').textContent = _esc(agentName) + ' - API Keys';
    document.getElementById('agentListView').style.display   = 'none';
    document.getElementById('agentWizardView').style.display = 'none';
    document.getElementById('agentKeysView').style.display   = 'flex';
    hideAddKeyForm();
    loadAgentKeys();
}

function closeAgentKeys() {
    document.getElementById('agentKeysView').style.display = 'none';
    loadAgentsList();
}

async function loadAgentKeys() {
    const list = document.getElementById('agentKeysList');
    if (!list || !_keysAgentId) return;
    list.innerHTML = '<div class="text-xs" style="color:var(--muted)">Loading...</div>';
    try {
        const res  = await fetch('/api/agents/proxy/' + _keysAgentId + '/keys', { headers: _csrfHeaders() });
        if (!res.ok) {
            list.innerHTML = `<div class="text-xs" style="color:var(--red)">${_esc(await _errText(res, 'Failed to load keys'))}</div>`;
            return;
        }
        const data = await res.json();
        const keys = data.keys || [];
        if (!keys.length) {
            list.innerHTML = '<div class="text-center py-6 text-xs" style="color:var(--muted)">No API keys yet. Add one to allow external clients like the mobile app to connect to this agent.</div>';
            return;
        }
        list.innerHTML = keys.map(k => `
            <div class="sc-set">
                <div class="sc-set-l">
                    <div class="sc-set-n">${_esc(k.name)}</div>
                    <div class="sc-set-d">Created ${new Date(k.created_at).toLocaleDateString()}${k.last_used_at ? ' &middot; Last used ' + new Date(k.last_used_at).toLocaleDateString() : ''}</div>
                </div>
                <div class="sc-set-v"><button onclick="deleteAgentKey('${_keysAgentId}','${k.id}',${_jsArg(k.name)})" class="btn-icon flex-shrink-0" title="Revoke" style="color:var(--red)"><i class="ph-bold ph-trash text-xs"></i></button></div>
            </div>`).join('');
    } catch(e) {
        list.innerHTML = `<div class="text-xs" style="color:var(--red)">${_esc(_netErrText(e, 'Failed to load keys'))}</div>`;
    }
}

function showAddKeyForm() {
    const form = document.getElementById('agentKeysAddForm');
    if (form) { form.style.display = 'flex'; }
    document.getElementById('agentKeyNameInput').value = '';
    document.getElementById('agentKeyNewDisplay').style.display = 'none';
    document.getElementById('agentKeyCreateErr').style.display  = 'none';
    document.getElementById('agentKeyCreateBtn').textContent = 'Create';
    setTimeout(() => document.getElementById('agentKeyNameInput').focus(), 50);
}

function hideAddKeyForm() {
    const form = document.getElementById('agentKeysAddForm');
    if (form) form.style.display = 'none';
}

async function createAgentKey() {
    const name = document.getElementById('agentKeyNameInput').value.trim();
    const errEl = document.getElementById('agentKeyCreateErr');
    if (!name) { errEl.textContent = 'Enter a name for this key'; errEl.style.display = ''; return; }
    const btn = document.getElementById('agentKeyCreateBtn');
    btn.disabled = true; btn.textContent = 'Creating...';
    errEl.style.display = 'none';
    try {
        const res  = await fetch('/api/agents/proxy/' + _keysAgentId + '/keys', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ..._csrfHeaders() },
            body: JSON.stringify({ name })
        });
        if (!res.ok) { errEl.textContent = await _errText(res, 'Failed to create key'); errEl.style.display = ''; btn.disabled = false; btn.textContent = 'Create'; return; }
        const data = await res.json();
        if (!data.ok) { errEl.textContent = data.error || data.message || 'Failed to create key'; errEl.style.display = ''; btn.disabled = false; btn.textContent = 'Create'; return; }
        document.getElementById('agentKeyNewValue').textContent = data.key;
        document.getElementById('agentKeyNewDisplay').style.display = 'flex';
        btn.textContent = 'Done';
        btn.onclick = () => { hideAddKeyForm(); loadAgentKeys(); btn.onclick = createAgentKey; };
        btn.disabled = false;
    } catch(e) {
        errEl.textContent = _netErrText(e, 'Failed to create key'); errEl.style.display = '';
        btn.disabled = false; btn.textContent = 'Create';
    }
}

function copyNewAgentKey() {
    const val = document.getElementById('agentKeyNewValue').textContent;
    navigator.clipboard.writeText(val).then(() => showToast('Key copied', 'success')).catch(() => {});
}

async function deleteAgentKey(agentId, keyId, keyName) {
    if (!await _confirm(`Revoke key "${keyName}"? Any client using it will lose access immediately.`, 'Revoke Key', 'Revoke')) return;
    try {
        const res  = await fetch('/api/agents/proxy/' + agentId + '/keys/' + keyId, { method: 'DELETE', headers: _csrfHeaders() });
        if (!res.ok) { showToast(await _errText(res, 'Revoke failed'), 'error'); return; }
        const data = await res.json();
        if (data.ok) { showToast('Key revoked', 'success'); loadAgentKeys(); }
        else showToast('Revoke failed: ' + (data.error || data.message || 'the server did not say why'), 'error');
    } catch(e) { showToast(_netErrText(e, 'Revoke failed'), 'error'); }
}

async function loadActiveAgentKeys() {
    if (!_activeAgent) return;
    const sub = document.getElementById('agentKeysSubtitle');
    if (sub) sub.textContent = _activeAgent.name;
    hideActiveAgentAddKeyForm();
    const list = document.getElementById('activeAgentKeysList');
    if (!list) return;
    list.innerHTML = '<div class="text-xs" style="color:var(--muted)">Loading...</div>';
    try {
        const res  = await fetch('/api/agents/proxy/' + _activeAgent.id + '/keys', { headers: _csrfHeaders() });
        if (!res.ok) {
            list.innerHTML = `<div class="text-xs" style="color:var(--red)">${_esc(await _errText(res, 'Failed to load keys'))}</div>`;
            return;
        }
        const data = await res.json();
        const keys = data.keys || [];
        if (!keys.length) {
            list.innerHTML = '<div class="text-center py-6 text-xs" style="color:var(--muted)">No API keys yet.<br>Add one to let external clients like the mobile app connect directly to this agent.</div>';
            return;
        }
        list.innerHTML = keys.map(k => `
            <div class="sc-set">
                <div class="sc-set-l">
                    <div class="sc-set-n">${_esc(k.name)}</div>
                    <div class="sc-set-d">Created ${new Date(k.created_at).toLocaleDateString()}${k.last_used_at ? ' &middot; Last used ' + new Date(k.last_used_at).toLocaleDateString() : ''}</div>
                </div>
                <div class="sc-set-v"><button onclick="deleteActiveAgentKey('${k.id}',${_jsArg(k.name)})" class="btn-icon flex-shrink-0" title="Revoke" style="color:var(--red)"><i class="ph-bold ph-trash text-xs"></i></button></div>
            </div>`).join('');
    } catch(e) {
        list.innerHTML = `<div class="text-xs" style="color:var(--red)">${_esc(_netErrText(e, 'Failed to load keys'))}</div>`;
    }
}

function showActiveAgentAddKeyForm() {
    const form = document.getElementById('activeAgentKeysAddForm');
    if (form) form.style.display = 'flex';
    document.getElementById('activeAgentKeyNameInput').value = '';
    document.getElementById('activeAgentKeyNewDisplay').style.display = 'none';
    document.getElementById('activeAgentKeyCreateErr').style.display  = 'none';
    const btn = document.getElementById('activeAgentKeyCreateBtn');
    btn.textContent = 'Create'; btn.onclick = createActiveAgentKey;
    setTimeout(() => document.getElementById('activeAgentKeyNameInput').focus(), 50);
}

function hideActiveAgentAddKeyForm() {
    const form = document.getElementById('activeAgentKeysAddForm');
    if (form) form.style.display = 'none';
}

async function createActiveAgentKey() {
    if (!_activeAgent) return;
    const name = document.getElementById('activeAgentKeyNameInput').value.trim();
    const errEl = document.getElementById('activeAgentKeyCreateErr');
    if (!name) { errEl.textContent = 'Enter a name for this key'; errEl.style.display = ''; return; }
    const btn = document.getElementById('activeAgentKeyCreateBtn');
    btn.disabled = true; btn.textContent = 'Creating...';
    errEl.style.display = 'none';
    try {
        const res  = await fetch('/api/agents/proxy/' + _activeAgent.id + '/keys', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ..._csrfHeaders() },
            body: JSON.stringify({ name })
        });
        if (!res.ok) { errEl.textContent = await _errText(res, 'Failed to create key'); errEl.style.display = ''; btn.disabled = false; btn.textContent = 'Create'; return; }
        const data = await res.json();
        if (!data.ok) { errEl.textContent = data.error || data.message || 'Failed to create key'; errEl.style.display = ''; btn.disabled = false; btn.textContent = 'Create'; return; }
        document.getElementById('activeAgentKeyNewValue').textContent = data.key;
        document.getElementById('activeAgentKeyNewDisplay').style.display = 'flex';
        btn.textContent = 'Done'; btn.disabled = false;
        btn.onclick = () => { hideActiveAgentAddKeyForm(); loadActiveAgentKeys(); btn.onclick = createActiveAgentKey; };
    } catch(e) {
        errEl.textContent = _netErrText(e, 'Failed to create key'); errEl.style.display = '';
        btn.disabled = false; btn.textContent = 'Create';
    }
}

function copyActiveAgentKey() {
    const val = document.getElementById('activeAgentKeyNewValue').textContent;
    navigator.clipboard.writeText(val).then(() => showToast('Key copied', 'success')).catch(() => {});
}

async function deleteActiveAgentKey(keyId, keyName) {
    if (!_activeAgent) return;
    if (!await _confirm(`Revoke key "${keyName}"? Any client using it will lose access immediately.`, 'Revoke Key', 'Revoke')) return;
    try {
        const res  = await fetch('/api/agents/proxy/' + _activeAgent.id + '/keys/' + keyId, { method: 'DELETE', headers: _csrfHeaders() });
        if (!res.ok) { showToast(await _errText(res, 'Revoke failed'), 'error'); return; }
        const data = await res.json();
        if (data.ok) { showToast('Key revoked', 'success'); loadActiveAgentKeys(); }
        else showToast('Revoke failed: ' + (data.error || data.message || 'the server did not say why'), 'error');
    } catch(e) { showToast(_netErrText(e, 'Revoke failed'), 'error'); }
}

async function pingAgent(id, url) {
    const dot = document.getElementById('agent-dot-' + id);
    if (!dot) return;
    try {
        const res  = await fetch('/api/agents/' + id + '/health');
        const data = await res.json();
        dot.style.background = data.ok ? 'var(--green)' : 'var(--red)';
    } catch(e) { if (dot) dot.style.background = 'var(--red)'; }
}


async function deleteAgent(id, name) {
    if (!await _confirm(`Remove agent "${name}"? This only removes it from TM settings - the agent service on the remote server is unaffected.`, 'Remove Agent', 'Remove')) return;
    try {
        const res  = await fetch('/api/agents/' + id, { method: 'DELETE', headers: _csrfHeaders() });
        if (!res.ok) { showToast(await _errText(res, 'Remove failed'), 'error'); return; }
        const data = await res.json();
        if (data.ok) { showToast('Agent removed', 'success'); loadAgentsList(); }
        else showToast('Remove failed: ' + (data.error || data.message || 'the server did not say why'), 'error');
    } catch(e) { showToast(_netErrText(e, 'Remove failed'), 'error'); }
}

let _agentAddMode = 'manual';

function startAddAgent() {
    document.getElementById('agentListView').style.display    = 'none';
    document.getElementById('agentWizardView').style.display  = 'none';
    document.getElementById('agentChooserView').style.display = 'flex';
}

function startAgentAdd(mode) {
    _agentAddMode        = mode === 'cli' ? 'cli' : 'manual';
    _agentWizId          = null;
    _agentWizKey         = null;
    _agentWizStep        = 1;
    _agentRestartMethod  = '';
    document.getElementById('agentChooserView').style.display = 'none';
    document.getElementById('agentListView').style.display    = 'none';
    document.getElementById('agentWizardView').style.display  = 'flex';
    document.getElementById('agentWizardTitle').textContent   = _agentAddMode === 'cli'
        ? 'Install with the tm CLI' : 'Add Agent';
    document.getElementById('agentWizardStepPills').style.display = _agentAddMode === 'cli' ? 'none' : '';
    resetAgentWizard();
    showAgentWizStep(1);
}

function _renderAgentCliStep() {
    const name = document.getElementById('agentWizName').value.trim();
    const host = document.getElementById('agentCliHostName');
    if (host) host.textContent = name || 'the remote host';
    const cmd = document.getElementById('agentCliCmd');
    if (cmd) {
        cmd.textContent = `export TMA_API_KEY='${_agentWizKey || ''}'\n`
                        + `curl -fsSL https://get-traefik.xyzlab.dev | bash -s -- --mode agent`;
    }
    const key = document.getElementById('agentCliKey');
    if (key) key.textContent = _agentWizKey || '';
    const res = _agentVerifyEl();
    if (res) { res.textContent = ''; res.style.color = 'var(--muted)'; }
}

function copyAgentCliCmd() {
    _agentCopy(document.getElementById('agentCliCmd').textContent, 'Command copied');
}

function _agentVerifyEl() {
    const summary = document.getElementById('agentSummaryView');
    if (summary && summary.style.display !== 'none' && summary.offsetParent !== null) {
        return document.getElementById('agentVerifyResultEdit');
    }
    return document.getElementById('agentVerifyResult')
        || document.getElementById('agentVerifyResultEdit');
}

async function verifyAgentInstall() {
    const btn = document.getElementById('agentVerifyBtn');
    const out = _agentVerifyEl();
    if (!_agentWizId || !out) return;
    btn.disabled = true;
    out.style.color = 'var(--muted)';
    out.textContent = 'Checking...';
    const say = (text, color) => { out.textContent = text; out.style.color = color; };
    try {
        const health = await fetch('/api/agents/' + _agentWizId + '/health').then(r => r.json());
        if (!health.ok) {
            say(health.error || 'Not reachable yet - check the URL, the port and any firewall.', 'var(--red)');
            return;
        }
        const keys = await fetch('/api/agents/proxy/' + _agentWizId + '/keys', { headers: _csrfHeaders() });
        if (keys.status === 401) {
            say('Reachable, but it is refusing this key. Re-run the command, or rotate the key.', 'var(--yellow)');
            return;
        }
        const ver = await fetch('/api/agents/proxy/' + _agentWizId + '/traefik/version', { headers: _csrfHeaders() });
        if (!ver.ok) {
            say('Agent is up, but it cannot reach Traefik yet.', 'var(--yellow)');
            return;
        }
        say('Connected. The agent is answering and can see Traefik.', 'var(--green)');
        loadAgentsList();
    } catch (e) {
        say(_netErrText(e, 'Could not check the agent'), 'var(--red)');
    } finally {
        btn.disabled = false;
    }
}

async function openAgentSetup(id, titleOverride) {
    _agentWizId = id;
    _agentWizKey = null;
    document.getElementById('agentListView').style.display   = 'none';
    document.getElementById('agentWizardView').style.display = 'flex';
    document.getElementById('agentWizardTitle').textContent  = titleOverride || 'Setup Commands';
    document.getElementById('agentWizardStepPills').style.display = 'none';
    document.getElementById('agentRotateKeyBanner').style.display = '';
    document.getElementById('agentRotatedKeyDisplay').style.display = 'none';
    document.getElementById('agentRotatedKeyText').textContent = '';
    resetAgentWizardCfgFields();
    showAgentWizStep(3);
    hideAgentComposeConfig();
    document.getElementById('agentWizardTitle').textContent = titleOverride || 'Agent';
    document.getElementById('agentWizSaveBtn').style.display = 'inline-flex';
    document.getElementById('agentWizKeyDisplay').textContent = '';
    try {
        const res  = await fetch('/api/agents');
        const data = await res.json();
        const a    = (data.agents || []).find(x => x.id === id);
        if (a) {
            document.getElementById('agCfgTraefikUrl').value = a.traefik_api_url || '';
            document.getElementById('agCfgCertResolver').value = a.cert_resolver || '';
            _applyAgentInstallMethod(a.install_method);
            _agEditOrig = { name: a.name || '', url: a.url || '' };
            document.getElementById('agEditName').value = _agEditOrig.name;
            document.getElementById('agEditUrl').value  = _agEditOrig.url;
            _agentIdentityChanged();
            document.getElementById('agCfgTraefikApiUser').value = a.traefik_api_user || '';
            document.getElementById('agCfgTraefikApiPassword').value =
                a.traefik_api_password === '***' ? '' : (a.traefik_api_password || '');
            document.getElementById('agCfgGitCommitMessage').value = a.git_backup_commit_message || '';
            const tlsEl = document.getElementById('agCfgInsecureTLS');
            if (tlsEl) { tlsEl.classList.toggle('on', !!a.traefik_insecure_skip_verify); }
            document.getElementById('agCfgConfigPath').value = a.config_path || '';
            if (a.static_config_path) document.getElementById('agCfgStaticPath').value  = a.static_config_path;
            if (a.backup_dir)         document.getElementById('agCfgBackupDir').value   = a.backup_dir;
            if (a.backup_keep_count)  { const el = document.getElementById('agCfgKeepCount'); if (el) el.value = a.backup_keep_count; }
            if (a.acme_json_path)     document.getElementById('agCfgAcmePath').value    = a.acme_json_path;
            if (a.access_log_path)    document.getElementById('agCfgLogPath').value     = a.access_log_path;
            if (a.plugins_dir)        document.getElementById('agCfgPluginsDir').value  = a.plugins_dir;
            if (a.docker_host)        document.getElementById('agCfgDockerHost').value  = a.docker_host;
            if (a.signal_file_path)   document.getElementById('agCfgSignalFile').value  = a.signal_file_path;
            if (a.crowdsec_lapi_url)  document.getElementById('agCfgCsUrl').value       = a.crowdsec_lapi_url;
            if (a.crowdsec_machine_id) document.getElementById('agCfgCsMachineId').value = a.crowdsec_machine_id;
            if (a.crowdsec_client_cert) document.getElementById('agCfgCsClientCert').value = a.crowdsec_client_cert;
            if (a.crowdsec_client_key)  document.getElementById('agCfgCsClientKey').value  = a.crowdsec_client_key;
            if (a.crowdsec_ca_cert)    document.getElementById('agCfgCsCaCert').value     = a.crowdsec_ca_cert;
            if (a.restart_method)     selectRestartMethod(a.restart_method, null);
            const container = a.traefik_container || '';
            if (container) {
                document.getElementById('agCfgContainer').value = container;
            }
            document.getElementById('agCfgGitEnabled').checked = !!a.git_backup_enabled;
            document.getElementById('agentGitFields').style.display = a.git_backup_enabled ? 'block' : 'none';
            document.getElementById('agCfgGitRepo').value   = a.git_backup_repo || '';
            document.getElementById('agCfgGitBranch').value = a.git_backup_branch || '';
            document.getElementById('agCfgGitUser').value   = a.git_backup_username || '';
            document.getElementById('agCfgGitAutoPush').checked = a.git_backup_auto_push !== false;
            if (a.tma_port)       { const el = document.getElementById('agCfgPort');      if (el) el.value = a.tma_port; }
            if (a.tma_rate_limit) { const el = document.getElementById('agCfgRateLimit'); if (el) el.value = a.tma_rate_limit; }
            if (a.domains && a.domains.length) { const el = document.getElementById('agCfgDomains'); if (el) el.value = a.domains.join(', '); }
        }
    } catch(e) {}
    agentCfgChanged();
}

function cancelAddAgent() {
    const chooser = document.getElementById('agentChooserView');
    if (chooser) chooser.style.display = 'none';
    document.getElementById('agentWizardView').style.display = 'none';
    loadAgentsList();
}

function resetAgentWizard() {
    document.getElementById('agentWizName').value = '';
    document.getElementById('agentWizUrl').value  = '';
    document.getElementById('agentWizStep1Err').style.display = 'none';
    resetAgentWizardCfgFields();
}

function toggleAgentDockerOutputs() {
    const el = document.getElementById('agentDockerOutputsWrap');
    if (!el) return;
    const open = !el.classList.contains('open');
    el.classList.toggle('open', open);
    try { localStorage.setItem('tmAgentComposeOpen', open ? '1' : '0'); } catch (e) {}
}

let _agEditOrig = { name: '', url: '' };

function showAgentComposeConfig() {
    document.getElementById('agentSummaryView').style.display = 'none';
    document.getElementById('agentComposeConfig').style.display = '';
    agentCfgChanged();
}

function hideAgentComposeConfig() {
    document.getElementById('agentComposeConfig').style.display = 'none';
    document.getElementById('agentSummaryView').style.display = '';
}

function _agentIdentityChanged() {
    const name = document.getElementById('agEditName').value.trim();
    const url  = document.getElementById('agEditUrl').value.trim();
    const btn  = document.getElementById('agEditSaveBtn');
    if (btn) btn.disabled = !name || !url || (name === _agEditOrig.name && url === _agEditOrig.url);
    const msg = document.getElementById('agEditMsg');
    if (msg) msg.textContent = '';
}

async function saveAgentIdentity() {
    if (!_agentWizId) return;
    const name = document.getElementById('agEditName').value.trim();
    const url  = document.getElementById('agEditUrl').value.trim();
    const msg  = document.getElementById('agEditMsg');
    const btn  = document.getElementById('agEditSaveBtn');
    btn.disabled = true;
    try {
        const res = await fetch('/api/agents/' + _agentWizId, {
            method: 'PUT',
            headers: { ..._csrfHeaders(), 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, url }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok || !data.ok) {
            msg.textContent = data.error || data.message || await _errText(res, 'Save failed');
            msg.style.color = 'var(--red)';
            btn.disabled = false;
            return;
        }
        _agEditOrig = { name, url };
        msg.textContent = 'Saved';
        msg.style.color = 'var(--green)';
        refreshAgentRegistry();
    } catch (e) {
        msg.textContent = _netErrText(e, 'Save failed');
        msg.style.color = 'var(--red)';
        btn.disabled = false;
    }
}

function _applyAgentInstallMethod(method) {
    const cli = method === 'cli';
    const wrap = document.getElementById('agentDockerOutputsWrap');
    if (wrap) {
        wrap.style.display = cli ? 'none' : '';
        let open = false;
        try { open = localStorage.getItem('tmAgentComposeOpen') === '1'; } catch (e) {}
        wrap.classList.toggle('open', open);
    }
    const note = document.getElementById('agentCliManagedNote');
    if (note) note.style.display = cli ? '' : 'none';
}

function resetAgentWizardCfgFields() {
    document.getElementById('agCfgTraefikUrl').value  = 'http://traefik:8080';
    document.getElementById('agCfgCertResolver').value = '';
    document.getElementById('agCfgConfigPath').value  = '/app/config';
    document.getElementById('agCfgStaticPath').value  = '';
    document.getElementById('agCfgBackupDir').value   = '';
    { const el = document.getElementById('agCfgKeepCount'); if (el) el.value = ''; }
    document.getElementById('agCfgAcmePath').value    = '';
    document.getElementById('agCfgLogPath').value     = '';
    document.getElementById('agCfgPluginsDir').value  = '';
    document.getElementById('agCfgDockerHost').value  = '';
    document.getElementById('agCfgContainer').value = 'traefik';
    _applyAgentInstallMethod('manual');
    document.getElementById('agCfgTraefikApiUser').value = '';
    document.getElementById('agCfgTraefikApiPassword').value = '';
    document.getElementById('agCfgGitCommitMessage').value = '';
    document.getElementById('agCfgSignalFile').value  = '';
    document.getElementById('agCfgGitEnabled').checked = false;
    document.getElementById('agentGitFields').style.display = 'none';
    document.getElementById('agCfgGitRepo').value     = '';
    document.getElementById('agCfgGitBranch').value   = 'main';
    document.getElementById('agCfgGitUser').value     = '';
    document.getElementById('agCfgGitToken').value    = '';
    document.getElementById('agCfgGitAutoPush').checked = true;
    document.getElementById('agCfgCsUrl').value       = '';
    const portEl = document.getElementById('agCfgPort'); if (portEl) portEl.value = '';
    const rlEl   = document.getElementById('agCfgRateLimit'); if (rlEl) rlEl.value = '';
    const domsEl = document.getElementById('agCfgDomains'); if (domsEl) domsEl.value = '';
    document.getElementById('agCfgCsKey').value       = '';
    document.getElementById('agCfgCsMachineId').value = '';
    document.getElementById('agCfgCsMachinePassword').value = '';
    document.getElementById('agCfgCsClientCert').value = '';
    document.getElementById('agCfgCsClientKey').value  = '';
    document.getElementById('agCfgCsCaCert').value     = '';
    document.getElementById('agCfgInsecureTLS')?.classList.remove('on');
    selectRestartMethod('', document.querySelector('#restartMethodChips .agent-chip'));
}

function showAgentWizStep(n) {
    const cliStep = document.getElementById('agentWizStepCli');
    if (cliStep) cliStep.style.display = n === 'cli' ? '' : 'none';
    [1,2,3].forEach(i => {
        const el = document.getElementById('agentWizStep' + i);
        if (el) el.style.display = i === n ? '' : 'none';
        const pill = document.getElementById('wiz-step-pill-' + i);
        if (pill) {
            pill.classList.toggle('on', i === n);
            pill.classList.toggle('done', i < n);
        }
    });
    _agentWizStep = n;
    if (n === 3) { switchAgentCfgTab('traefik', document.querySelector('#agentCfgTabs .auth-sub-tab')); agentCfgChanged(); }
}

async function agentWizStep1Next() {
    const name = document.getElementById('agentWizName').value.trim();
    const url  = document.getElementById('agentWizUrl').value.trim();
    const err  = document.getElementById('agentWizStep1Err');
    if (!name || !url) { err.textContent = 'Name and URL are required.'; err.style.display = ''; return; }
    const btn = document.getElementById('agentWizStep1Btn');
    btn.disabled = true; btn.innerHTML = '<i class="ph-light ph-spinner-gap animate-spin text-xs"></i> Creating…';
    try {
        const res  = await fetch('/api/agents', { method: 'POST', headers: { ..._csrfHeaders(), 'Content-Type': 'application/json' }, body: JSON.stringify({ name, url, install_method: _agentAddMode === 'cli' ? 'cli' : 'manual' }) });
        if (!res.ok) { err.textContent = await _errText(res, 'Failed to create agent'); err.style.display = ''; return; }
        const data = await res.json();
        if (!data.ok) { err.textContent = data.error || data.message || 'Failed to create agent'; err.style.display = ''; return; }
        _agentWizId  = data.agent.id;
        _agentWizKey = data.agent.api_key_raw;
        document.getElementById('agentWizKeyDisplay').textContent = _agentWizKey;
        err.style.display = 'none';
        if (_agentAddMode === 'cli') {
            _renderAgentCliStep();
            showAgentWizStep('cli');
        } else {
            showAgentWizStep(2);
        }
        refreshAgentRegistry();
    } catch(e) { err.textContent = _netErrText(e, 'Failed to create agent'); err.style.display = ''; }
    finally { btn.disabled = false; btn.innerHTML = 'Continue <i class="ph-bold ph-caret-right text-xs"></i>'; }
}

function agentWizStep2Next() {
    document.getElementById('agentRotateKeyBanner').style.display = 'none';
    showAgentWizStep(3);
    showAgentComposeConfig();
}

async function agentWizStep3Save() {
    if (!_agentWizId) return;
    const cfg = buildAgentCfgPayload();
    try {
        const res  = await fetch('/api/agents/' + _agentWizId, { method: 'PUT', headers: { ..._csrfHeaders(), 'Content-Type': 'application/json' }, body: JSON.stringify(cfg) });
        if (!res.ok) { showToast(await _errText(res, 'Save failed'), 'error'); return; }
        const data = await res.json();
        if (data.ok) { showToast('Agent config saved', 'success'); refreshAgentRegistry(); }
        else showToast('Save failed: ' + (data.error || data.message || 'the server did not say why'), 'error');
    } catch(e) { showToast(_netErrText(e, 'Save failed'), 'error'); }
}

async function agentWizDone() {
    await agentWizStep3Save();
    document.getElementById('agentWizardView').style.display = 'none';
    document.getElementById('agentListView').style.display   = 'flex';
    loadAgentsList();
}

function _agentCopy(text, okMsg) {
    if (!navigator.clipboard || !navigator.clipboard.writeText) {
        showToast('Copying needs HTTPS or localhost - select the text and copy it manually', 'warning');
        return;
    }
    navigator.clipboard.writeText(text || '')
        .then(() => showToast(okMsg, 'success'))
        .catch(() => showToast('Could not copy - select the text and copy it manually', 'error'));
}

function copyAgentKey() {
    _agentCopy(_agentWizKey || '', 'Key copied');
}

function copyAgentCompose() {
    _agentCopy(document.getElementById('agentComposeOutput').textContent, 'Copied');
}

function copyAgentRun() {
    _agentCopy(document.getElementById('agentRunOutput').textContent, 'Copied');
}

function copyRotatedKey() {
    _agentCopy(document.getElementById('agentRotatedKeyText').textContent, 'Key copied');
}

async function rotateAgentKey() {
    const btn = document.getElementById('agentRotateKeyBtn');
    btn.disabled = true;
    btn.innerHTML = '<i class="ph-bold ph-spinner-gap animate-spin text-xs"></i>';
    try {
        const res = await fetch('/api/agents/' + _agentWizId + '/rotate-key', {
            method: 'POST', headers: { ..._csrfHeaders() }
        });
        let data = {};
        try { data = await res.json(); } catch(je) { data = {}; }
        if (!res.ok) throw new Error(data.error || data.message || await _errText(res, 'Rotation failed'));
        const rotated = (data.agent && data.agent.api_key_raw) || data.api_key_raw;
        if (!rotated) throw new Error(data.error || data.message || 'The server did not return a new key.');
        _agentWizKey = rotated;
        document.getElementById('agentRotatedKeyText').textContent = _agentWizKey;
        document.getElementById('agentRotatedKeyDisplay').style.display = '';
        btn.innerHTML = '<i class="ph-bold ph-check text-xs"></i> Rotated';
        agentCfgChanged();
        showToast('API key rotated - update your agent', 'warning');
    } catch(e) {
        btn.disabled = false;
        btn.innerHTML = '<i class="ph-bold ph-arrows-clockwise text-xs"></i> Rotate Key';
        showToast(_netErrText(e, 'Rotation failed'), 'error');
    }
}

function switchAgentCfgTab(id, btn) {
    document.querySelectorAll('#agentCfgTabs .auth-sub-tab').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('[id^="agentCfgPane-"]').forEach(p => { p.style.display = 'none'; });
    if (btn) btn.classList.add('active');
    const pane = document.getElementById('agentCfgPane-' + id);
    if (pane) pane.style.display = id === 'restart' ? '' : 'flex';
}

function selectRestartMethod(method, btn) {
    _agentRestartMethod = method;
    document.querySelectorAll('#restartMethodChips .agent-chip').forEach(b => b.classList.remove('active'));
    const chip = btn || Array.from(document.querySelectorAll('#restartMethodChips .agent-chip'))
        .find(b => (b.getAttribute('data-method') || '') === (method || ''));
    if (chip) chip.classList.add('active');
    document.getElementById('restartProxyFields').style.display     = method === 'proxy'       ? '' : 'none';
    document.getElementById('restartPoisonPillFields').style.display = method === 'poison-pill' ? '' : 'none';
    document.getElementById('restartSocketFields').style.display    = method === 'socket'      ? '' : 'none';
    const containerField = document.getElementById('restartContainerField');
    if (containerField) containerField.style.display = (method === 'proxy' || method === 'socket') ? '' : 'none';
    agentCfgChanged();
}

document.getElementById('agCfgGitEnabled').addEventListener('change', function() {
    document.getElementById('agentGitFields').style.display = this.checked ? 'block' : 'none';
    agentCfgChanged();
});

function buildAgentCfgPayload() {
    return {
        traefik_api_url:          document.getElementById('agCfgTraefikUrl').value.trim(),
        cert_resolver:            document.getElementById('agCfgCertResolver').value.trim(),
        traefik_insecure_skip_verify: document.getElementById('agCfgInsecureTLS')?.classList.contains('on') || false,
        config_path:        document.getElementById('agCfgConfigPath').value.trim(),
        static_config_path: document.getElementById('agCfgStaticPath').value.trim(),
        backup_dir:         document.getElementById('agCfgBackupDir').value.trim(),
        backup_keep_count:  document.getElementById('agCfgKeepCount')?.value.trim() || '',
        acme_json_path:     document.getElementById('agCfgAcmePath').value.trim(),
        access_log_path:    document.getElementById('agCfgLogPath').value.trim(),
        plugins_dir:        document.getElementById('agCfgPluginsDir').value.trim(),
        restart_method:     _agentRestartMethod,
        traefik_container:  (document.getElementById('agCfgContainer').value || 'traefik').trim(),
        traefik_api_user:     document.getElementById('agCfgTraefikApiUser').value.trim(),
        traefik_api_password: document.getElementById('agCfgTraefikApiPassword').value,
        git_backup_commit_message: document.getElementById('agCfgGitCommitMessage').value.trim(),
        docker_host:        document.getElementById('agCfgDockerHost').value.trim(),
        signal_file_path:   document.getElementById('agCfgSignalFile').value.trim(),
        crowdsec_lapi_url:  document.getElementById('agCfgCsUrl').value.trim(),
        crowdsec_api_key:   document.getElementById('agCfgCsKey').value,
        crowdsec_machine_id:       document.getElementById('agCfgCsMachineId').value.trim(),
        crowdsec_machine_password: document.getElementById('agCfgCsMachinePassword').value,
        crowdsec_client_cert:      document.getElementById('agCfgCsClientCert').value.trim(),
        crowdsec_client_key:       document.getElementById('agCfgCsClientKey').value.trim(),
        crowdsec_ca_cert:          document.getElementById('agCfgCsCaCert').value.trim(),
        git_backup_enabled: document.getElementById('agCfgGitEnabled').checked,
        git_backup_repo:    document.getElementById('agCfgGitRepo').value.trim(),
        git_backup_branch:  document.getElementById('agCfgGitBranch').value.trim() || 'main',
        git_backup_username:document.getElementById('agCfgGitUser').value.trim(),
        git_backup_token:   document.getElementById('agCfgGitToken').value,
        git_backup_auto_push: document.getElementById('agCfgGitAutoPush').checked,
        tma_port:        (document.getElementById('agCfgPort')?.value.trim()) || '',
        tma_rate_limit:  (document.getElementById('agCfgRateLimit')?.value.trim()) || '',
        domains:         (document.getElementById('agCfgDomains')?.value || '').split(',').map(s => s.trim()).filter(Boolean),
    };
}

function agentCfgChanged() {
    const key       = _agentWizKey || '<your-api-key>';
    const traefik   = document.getElementById('agCfgTraefikUrl').value.trim() || 'http://traefik:8080';
    const configPath= document.getElementById('agCfgConfigPath').value.trim() || '/app/config';
    const staticPath= document.getElementById('agCfgStaticPath').value.trim();
    const backupDir = document.getElementById('agCfgBackupDir').value.trim();
    const acmePath  = document.getElementById('agCfgAcmePath').value.trim();
    const logPath   = document.getElementById('agCfgLogPath').value.trim();
    const pluginsDir= document.getElementById('agCfgPluginsDir').value.trim();
    const restart   = _agentRestartMethod;
    const container = (document.getElementById('agCfgContainer').value || 'traefik').trim();
    const dockerHost= document.getElementById('agCfgDockerHost').value.trim();
    const signalFile= document.getElementById('agCfgSignalFile').value.trim();
    const csUrl     = document.getElementById('agCfgCsUrl').value.trim();
    const csKey     = document.getElementById('agCfgCsKey').value.trim();
    const csMid     = document.getElementById('agCfgCsMachineId').value.trim();
    const csMpw     = document.getElementById('agCfgCsMachinePassword').value.trim();
    const csCc      = document.getElementById('agCfgCsClientCert').value.trim();
    const csCk      = document.getElementById('agCfgCsClientKey').value.trim();
    const csCa      = document.getElementById('agCfgCsCaCert').value.trim();
    const gitOn     = document.getElementById('agCfgGitEnabled').checked;
    const gitRepo   = document.getElementById('agCfgGitRepo').value.trim();
    const gitBranch = document.getElementById('agCfgGitBranch').value.trim() || 'main';
    const gitUser   = document.getElementById('agCfgGitUser').value.trim();
    const gitToken  = document.getElementById('agCfgGitToken').value.trim();
    const gitAuto   = document.getElementById('agCfgGitAutoPush').checked;

    const insecureTLS = document.getElementById('agCfgInsecureTLS')?.classList.contains('on');
    const agentPort   = document.getElementById('agCfgPort')?.value.trim() || '8090';
    const rateLimit   = document.getElementById('agCfgRateLimit')?.value.trim();
    const keepCount   = document.getElementById('agCfgKeepCount')?.value.trim();
    const envLines = [`      - TMA_API_KEY=${key}`, `      - TRAEFIK_API_URL=${traefik}`, `      - CONFIG_PATH=${configPath}`];
    if (agentPort !== '8090') envLines.push(`      - TMA_PORT=${agentPort}`);
    if (rateLimit && rateLimit !== '300') envLines.push(`      - TMA_RATE_LIMIT=${rateLimit}`);
    if (insecureTLS) envLines.push(`      - TRAEFIK_INSECURE_SKIP_VERIFY=true`);
    const tApiUser = document.getElementById('agCfgTraefikApiUser')?.value.trim() || '';
    const tApiPass = document.getElementById('agCfgTraefikApiPassword')?.value || '';
    if (tApiUser) envLines.push(`      - TRAEFIK_API_USER=${tApiUser}`);
    if (tApiPass) envLines.push(`      - TRAEFIK_API_PASSWORD=${tApiPass}`);
    const gitMsg = document.getElementById('agCfgGitCommitMessage')?.value.trim() || '';
    if (gitMsg) envLines.push(`      - GIT_BACKUP_COMMIT_MESSAGE=${gitMsg}`);
    if (staticPath)  envLines.push(`      - STATIC_CONFIG_PATH=${staticPath}`);
    if (restart)     envLines.push(`      - RESTART_METHOD=${restart}`);
    if (restart && container) envLines.push(`      - TRAEFIK_CONTAINER=${container}`);
    if (restart === 'proxy' && dockerHost)  envLines.push(`      - DOCKER_HOST=${dockerHost}`);
    if (restart === 'poison-pill' && signalFile) envLines.push(`      - SIGNAL_FILE_PATH=${signalFile}`);
    if (acmePath)    envLines.push(`      - ACME_JSON_PATH=${acmePath}`);
    if (logPath)     envLines.push(`      - ACCESS_LOG_PATH=${logPath}`);
    if (pluginsDir)  envLines.push(`      - PLUGINS_DIR=${pluginsDir}`);
    if (backupDir)   envLines.push(`      - BACKUP_DIR=${backupDir}`);
    if (keepCount && keepCount !== '0') envLines.push(`      - BACKUP_KEEP_COUNT=${keepCount}`);
    if (csUrl)       envLines.push(`      - CROWDSEC_LAPI_URL=${csUrl}`);
    if (csKey)       envLines.push(`      - CROWDSEC_API_KEY=${csKey}`);
    if (csMid)       envLines.push(`      - CROWDSEC_MACHINE_ID=${csMid}`);
    if (csMpw)       envLines.push(`      - CROWDSEC_MACHINE_PASSWORD=${csMpw}`);
    if (csCc)        envLines.push(`      - CROWDSEC_CLIENT_CERT=${csCc}`);
    if (csCk)        envLines.push(`      - CROWDSEC_CLIENT_KEY=${csCk}`);
    if (csCa)        envLines.push(`      - CROWDSEC_CA_CERT=${csCa}`);
    if (gitOn) {
        envLines.push(`      - GIT_BACKUP_ENABLED=true`);
        if (gitRepo)   envLines.push(`      - GIT_BACKUP_REPO=${gitRepo}`);
        envLines.push(`      - GIT_BACKUP_BRANCH=${gitBranch}`);
        if (gitUser)   envLines.push(`      - GIT_BACKUP_USERNAME=${gitUser}`);
        if (gitToken)  envLines.push(`      - GIT_BACKUP_TOKEN=${gitToken}`);
        envLines.push(`      - GIT_BACKUP_AUTO_PUSH=${gitAuto}`);
    }

    const volLines = [`      - ${configPath}:${configPath}`];
    if (staticPath)  volLines.push(`      - ${staticPath}:${staticPath}`);
    if (backupDir)   volLines.push(`      - ${backupDir}:/app/backups`);
    else             volLines.push(`      - tma_backups:/app/backups`);
    if (acmePath)    volLines.push(`      - ${acmePath}:${acmePath}:ro`);
    if (logPath)     volLines.push(`      - ${logPath}:${logPath}:ro`);
    if (pluginsDir)  volLines.push(`      - ${pluginsDir}:${pluginsDir}:ro`);
    if (csCc)        volLines.push(`      - ${csCc}:${csCc}:ro`);
    if (csCk)        volLines.push(`      - ${csCk}:${csCk}:ro`);
    if (csCa)        volLines.push(`      - ${csCa}:${csCa}:ro`);
    if (restart === 'socket') volLines.push(`      - /var/run/docker.sock:/var/run/docker.sock:ro`);
    if (restart === 'poison-pill') volLines.push(`      - traefik-signals:/signals`);

    const namedVols = [];
    if (!backupDir) namedVols.push(`  tma_backups:`);
    if (restart === 'poison-pill') namedVols.push(`  traefik-signals:`);

    const proxyHost = restart === 'proxy'
        ? (/^tcp:\/\/([A-Za-z][A-Za-z0-9._-]*):(\d+)/.exec(dockerHost || '') || [])
        : [];
    const proxyName = proxyHost[1] && proxyHost[1] !== 'localhost' ? proxyHost[1] : '';
    const proxyPort = proxyHost[2] || '2375';
    const proxyNet  = proxyName ? `${proxyName}-net` : '';

    let compose = `services:\n  traefik-manager-agent:\n    image: ghcr.io/chr0nzz/traefik-manager-agent:latest\n    restart: unless-stopped\n    ports:\n      - "${agentPort}:${agentPort}"\n    environment:\n${envLines.join('\n')}\n    volumes:\n${volLines.join('\n')}`;
    if (proxyName) compose += `\n    networks:\n      - ${proxyNet}`;

    if (proxyName) {
        compose += `\n\n  ${proxyName}:\n    image: tecnativa/docker-socket-proxy\n    restart: unless-stopped\n    environment:\n      CONTAINERS: 1\n      POST: 1\n    volumes:\n      - /var/run/docker.sock:/var/run/docker.sock:ro\n    networks:\n      - ${proxyNet}`;
        if (proxyPort !== '2375') compose += `\n    expose:\n      - "${proxyPort}"`;
    }

    if (namedVols.length) compose += `\n\nvolumes:\n${namedVols.join('\n')}`;
    if (proxyName) compose += `\n\nnetworks:\n  ${proxyNet}:\n    internal: true`;
    if (restart === 'poison-pill') {
        compose += `\n\n# The poison pill also needs a healthcheck on your Traefik service:\n`
            + `#   healthcheck:\n`
            + `#     test: ["CMD-SHELL", "[ ! -f ${signalFile || '/signals/restart.sig'} ] || (rm ${signalFile || '/signals/restart.sig'} && kill -TERM 1)"]\n`
            + `#     interval: 5s\n`
            + `#   volumes:\n`
            + `#     - traefik-signals:/signals`;
    }

    const runParts = [`docker run -d \\`, `  --name traefik-manager-agent \\`, `  -p ${agentPort}:${agentPort} \\`];
    envLines.forEach(e => runParts.push(`  -e ${e.replace(/^\s+- /, '')} \\`));
    volLines.forEach(v => runParts.push(`  -v ${v.replace(/^\s+- /, '')} \\`));
    runParts.push(`  ghcr.io/chr0nzz/traefik-manager-agent:latest`);

    const co = document.getElementById('agentComposeOutput');
    const ro = document.getElementById('agentRunOutput');
    if (co) co.textContent = compose;
    if (ro) ro.textContent = runParts.join('\n');
}

function updateServerSwitcher(agents) {
    if (typeof _updateServerSwitcherList === 'function') _updateServerSwitcherList(agents);
}

let _editingTemplateId = null;

function openTemplatesPanel() {
    closeOtherPanels('mwTplPanel');
    const panel = document.getElementById('mwTplPanel');
    const back  = document.getElementById('mwTplBackdrop');
    if (!panel) return;
    closeTemplateEditor(true);
    loadTemplatesList();
    panel.classList.add('open');
    if (back) back.classList.add('open');
    if (!setDetailDockOpen(true)) document.body.style.overflow = 'hidden';
}

function closeTemplatesPanel() {
    setDetailDockOpen(false);
    document.getElementById('mwTplPanel')?.classList.remove('open');
    document.getElementById('mwTplBackdrop')?.classList.remove('open');
    document.body.style.overflow = '';
}

async function loadTemplatesList() {
    const listEl = document.getElementById('templateListItems');
    if (!listEl) return;
    try {
        const res  = await fetch('/api/mw/templates');
        if (!res.ok) {
            listEl.innerHTML = `<div class="text-center py-10 text-xs" style="color:var(--red)">${_esc(await _errText(res, 'Could not load templates'))}</div>`;
            return;
        }
        const data = await res.json();
        const templates = data.templates || [];
        if (templates.length === 0) {
            listEl.innerHTML = `<div class="text-center py-10" style="color:var(--muted)">
                <i class="ph-light ph-cards text-3xl block mb-2 opacity-40"></i>
                <p class="text-xs">No custom templates yet. Click <strong>Add Template</strong> to create one.</p>
            </div>`;
            return;
        }
        listEl.innerHTML = templates.map(t => `
            <div class="flex items-center justify-between px-3 py-2.5 rounded-lg" style="background:var(--input-bg);border:1px solid var(--border)">
                <div class="flex items-center gap-2 min-w-0">
                    <i class="ph-bold ph-cards text-sm flex-shrink-0" style="color:var(--blue)"></i>
                    <span class="text-sm font-medium truncate" style="color:var(--text)">${_esc(t.name)}</span>
                </div>
                <div class="flex gap-1 flex-shrink-0">
                    <button onclick="openTemplateEditor('${t.id}')" class="btn-icon text-xs" title="Edit"><i class="ph-bold ph-pencil text-xs"></i></button>
                    <button onclick="deleteTemplate('${t.id}')" class="btn-icon text-xs" title="Delete" style="color:var(--red)"><i class="ph-bold ph-trash text-xs"></i></button>
                </div>
            </div>`).join('');
    } catch(e) {
        listEl.innerHTML = `<div class="text-xs py-4 text-center" style="color:var(--muted)">${_esc(_netErrText(e, 'Failed to load templates'))}</div>`;
    }
}

async function openTemplateEditor(id) {
    _editingTemplateId = id;
    document.getElementById('templateListView').style.display = 'none';
    document.getElementById('templateEditorView').style.display = '';
    document.getElementById('mwTplFoot').style.display = '';
    document.getElementById('mwTplPanelTitle').textContent = id ? 'Edit Template' : 'Add Template';
    document.getElementById('tplName').value = '';
    document.getElementById('tplYaml').value = '';
    if (id) {
        try {
            const res  = await fetch('/api/mw/templates');
            const data = await res.json();
            const t    = (data.templates || []).find(x => x.id === id);
            if (t) {
                document.getElementById('tplName').value = t.name;
                document.getElementById('tplYaml').value = t.yaml;
            }
        } catch(e) {}
    }
}

function closeTemplateEditor(skipReload) {
    _editingTemplateId = null;
    const ed = document.getElementById('templateEditorView');
    const li = document.getElementById('templateListView');
    const ft = document.getElementById('mwTplFoot');
    const ti = document.getElementById('mwTplPanelTitle');
    if (ed) ed.style.display = 'none';
    if (li) li.style.display = '';
    if (ft) ft.style.display = 'none';
    if (ti) ti.textContent = 'Middleware Templates';
    if (skipReload !== true) loadTemplatesList();
}

async function saveTemplate() {
    const name = document.getElementById('tplName').value.trim();
    const yaml = document.getElementById('tplYaml').value;
    if (!name) { showToast('Name is required', 'error'); return; }
    try {
        let res;
        if (_editingTemplateId) {
            res = await fetch('/api/mw/templates/' + _editingTemplateId, {
                method: 'PUT', headers: { ..._csrfHeaders(), 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, yaml })
            });
        } else {
            res = await fetch('/api/mw/templates', {
                method: 'POST', headers: { ..._csrfHeaders(), 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, yaml })
            });
        }
        if (!res.ok) { showToast(await _errText(res, 'Save failed'), 'error'); return; }
        const data = await res.json();
        if (data.ok) {
            showToast(_editingTemplateId ? 'Template updated' : 'Template created', 'success');
            closeTemplateEditor();
            if (typeof _loadCustomMwTemplates === 'function') _loadCustomMwTemplates();
        } else {
            showToast(data.error || data.message || 'Save failed', 'error');
        }
    } catch(e) { showToast(_netErrText(e, 'Save failed'), 'error'); }
}

async function deleteTemplate(id) {
    const ok = (typeof _confirm === 'function')
        ? await _confirm('Delete this template? Middlewares already created from it are not affected.', 'Delete template', 'Delete')
        : confirm('Delete this template?');
    if (!ok) return;
    try {
        const res  = await fetch('/api/mw/templates/' + id, { method: 'DELETE', headers: _csrfHeaders() });
        if (!res.ok) { showToast(await _errText(res, 'Delete failed'), 'error'); return; }
        const data = await res.json();
        if (data.ok) {
            showToast('Template deleted', 'success');
            loadTemplatesList();
            if (typeof _loadCustomMwTemplates === 'function') _loadCustomMwTemplates();
        } else {
            showToast(data.error || data.message || 'Delete failed', 'error');
        }
    } catch(e) { showToast(_netErrText(e, 'Delete failed'), 'error'); }
}

const SETTINGS_SEARCH_FIELDS = '.sc-set-n, .sc-set-d, .settings-section-label, .tab-toggle-row > span, label';

function _setUnitText(el) {
    let out = '';
    el.querySelectorAll(SETTINGS_SEARCH_FIELDS).forEach(f => { out += ' ' + f.textContent; });
    if (!out.trim()) out = el.textContent;
    el.querySelectorAll('[data-tip]').forEach(t => { out += ' ' + t.getAttribute('data-tip'); });
    out += ' ' + _setSectionText(el);
    return out.toLowerCase();
}

function _setSectionText(el) {
    let node = el;
    while (node && !node.classList.contains('modal-panel')) {
        let sib = node.previousElementSibling;
        while (sib) {
            const head = sib.classList.contains('sc-sec-head') ? sib : sib.querySelector?.('.sc-sec-head');
            if (head) {
                const tip = head.querySelector('[data-tip]')?.getAttribute('data-tip') || '';
                return (head.textContent || '') + ' ' + tip;
            }
            sib = sib.previousElementSibling;
        }
        node = node.parentElement;
    }
    return '';
}

function _settingsUnits(pane) {
    const units = [];
    pane.querySelectorAll('.sc-set, .tab-toggle-row, .sc-fld').forEach(el => units.push(el));
    if (units.length) return units;
    pane.querySelectorAll(':scope > div, :scope > .auth-sub-panel > div').forEach(el => {
        if (el.querySelector('input, select, textarea, .toggle-switch, button')) units.push(el);
    });
    return units;
}

function _scopeBlocks(pane) {
    const sub = pane.querySelectorAll(':scope > div > .auth-sub-panel');
    if (sub.length) {
        const out = [];
        sub.forEach(sp => sp.querySelectorAll(':scope > div').forEach(d => out.push(d)));
        return out;
    }
    return [...pane.querySelectorAll(':scope > div')];
}

function _scHide(el, off) {
    el.classList.toggle('sc-filtered-out', !!off);
}

function _filterOnePane(pane, q) {
    const units = _settingsUnits(pane);
    let hits = 0;
    units.forEach(el => {
        const match = !q || _setUnitText(el).indexOf(q) !== -1;
        _scHide(el, !match);
        if (match) hits++;
    });
    _scopeBlocks(pane).forEach(block => {
        const own = block.querySelectorAll('.sc-set, .tab-toggle-row, .sc-fld');
        if (!own.length) {
            if (units.indexOf(block) === -1) _scHide(block, !!q);
            return;
        }
        const alive = [...own].some(c => !c.classList.contains('sc-filtered-out'));
        _scHide(block, !!q && !alive);
    });
    pane.querySelectorAll('.sc-panel').forEach(g => {
        const kids = [...g.children].filter(c => !c.classList.contains('sc-filtered-out'));
        _scHide(g, !!q && kids.length === 0);
    });
    return hits;
}

function filterSettings() {
    const box = document.getElementById('settingsSearch');
    const q = (box ? box.value : '').trim().toLowerCase();
    const wrap = document.getElementById('settingsClearWrap');
    if (wrap) wrap.style.display = q ? '' : 'none';

    let activeHits = 0;
    const scBox = document.getElementById('staticSearch');
    if (scBox && typeof filterStatic === 'function') {
        scBox.value = q;
        filterStatic();
    }
    document.querySelectorAll('#settingsPanelWrapper .modal-panel').forEach(pane => {
        if (pane.id === 'mpanel-static' || pane.id === 'mpanel-about') return;
        const hits = _filterOnePane(pane, q);
        const btn = document.getElementById('msb-' + pane.id.replace('mpanel-', ''));
        if (btn) {
            let tag = btn.querySelector('.settings-hit');
            if (q && hits) {
                if (!tag) {
                    tag = document.createElement('span');
                    tag.className = 'settings-hit d-n';
                    btn.appendChild(tag);
                }
                tag.textContent = hits;
            } else if (tag) {
                tag.remove();
            }
        }
        if (pane.classList.contains('active')) activeHits = hits;
    });

    const elsewhere = [];
    document.querySelectorAll('.modal-sidebar-btn .settings-hit').forEach(t => {
        const btn = t.closest('.modal-sidebar-btn');
        if (btn.classList.contains('active')) return;
        const label = (btn.textContent || '').replace(t.textContent, '').trim();
        elsewhere.push({ id: btn.id.replace('msb-', ''), label, hits: t.textContent });
    });

    const empty = document.getElementById('settingsNoMatch');
    if (!empty) return;
    if (!q || activeHits) { empty.style.display = 'none'; return; }
    empty.style.display = '';
    empty.innerHTML = elsewhere.length
        ? 'No matches here. Found in '
          + elsewhere.map(e =>
              `<button type="button" class="settings-jump" onclick="switchSettingsPanel('${e.id}')">`
              + `${_esc(e.label)} <span>${_esc(e.hits)}</span></button>`).join(' ')
        : 'No settings match your search';
}

function clearSettingsSearch() {
    const box = document.getElementById('settingsSearch');
    if (box) box.value = '';
    filterSettings();
    if (box) box.focus();
}

require.config({ paths: { vs: tmUrl('/static/vendor/monaco/vs') } });

let _staticMonaco          = null;
let _staticRawContent      = '';
let _staticOriginalContent = '';
let _staticPendingChanges  = false;
let _staticSectionEdits    = false;
let _staticSaved           = false;

function _confirm(message, title, okLabel, typeWord, opts) {
    return _confirmWith({ message, title, okLabel, typeWord, ...(opts || {}) }).then(r => r.ok);
}

function _confirmWith(o) {
    const { message, title, okLabel, typeWord } = o || {};
    const notes   = (o && o.notes) || [];
    const check   = (o && o.checkbox) || null;
    const later   = (o && o.checkboxAsync) || null;
    const danger  = (o && o.danger !== undefined) ? o.danger
                    : /delete|remove|revoke|reset/i.test(String(okLabel || ''));
    return new Promise(resolve => {
        const overlay = document.getElementById('customConfirmOverlay');
        const msg     = document.getElementById('customConfirmMsg');
        const ttl     = document.getElementById('customConfirmTitle');
        const ok      = document.getElementById('customConfirmOk');
        const cancel  = document.getElementById('customConfirmCancel');
        const wrap    = document.getElementById('customConfirmTypeWrap');
        const input   = document.getElementById('customConfirmType');
        const wordEl  = document.getElementById('customConfirmWord');
        const word    = typeWord ? String(typeWord) : '';
        if (msg)    msg.textContent = message;
        if (ttl)    ttl.textContent = title || '';
        if (ok)     ok.textContent  = okLabel || 'Confirm';
        if (wrap)   wrap.style.display = word ? '' : 'none';
        if (wordEl) wordEl.textContent = word;
        if (input) { input.value = ''; input.placeholder = word; }
        const noteBox  = document.getElementById('customConfirmNotes');
        const checkWrap = document.getElementById('customConfirmCheckWrap');
        const checkBox  = document.getElementById('customConfirmCheck');
        const checkLbl  = document.getElementById('customConfirmCheckLabel');
        if (noteBox) {
            noteBox.innerHTML = notes.map(n =>
                '<div class="rounded-lg px-3 py-2.5 flex items-start gap-2 text-xs" '
                + 'style="background:rgba(239,68,68,0.06);border:1px solid rgba(239,68,68,0.25);color:var(--text)">'
                + '<i class="ph-bold ph-warning-circle shrink-0" style="color:var(--red);margin-top:1px"></i>'
                + '<span>' + _esc(n) + '</span></div>').join('');
            noteBox.style.display = notes.length ? 'flex' : 'none';
        }
        const showCheck = (c) => {
            if (checkWrap) checkWrap.style.display = c ? '' : 'none';
            if (checkBox)  checkBox.checked = !!(c && c.checked);
            if (checkLbl)  checkLbl.textContent = c ? String(c.label || '') : '';
        };
        showCheck(check);
        const icon = document.getElementById('customConfirmIcon');
        if (icon) icon.style.display = danger ? '' : 'none';
        if (ok) ok.classList.toggle('btn-red', !!danger);
        const matches = () => !word || (input && input.value.trim().toUpperCase() === word.toUpperCase());
        const sync = () => { if (ok) ok.disabled = !matches(); };
        sync();
        if (overlay) overlay.style.display = 'flex';
        if (word && input) setTimeout(() => input.focus(), 60);
        let open = true;
        if (later) {
            Promise.resolve(later).then(c => { if (open && c) showCheck(c); }).catch(() => {});
        }
        const onKey = e => {
            if (e.key === 'Escape') done(false);
            if (e.key === 'Enter' && matches()) done(true);
        };
        const done = (val) => {
            open = false;
            if (overlay) overlay.style.display = 'none';
            if (ok)     { ok.onclick = null; ok.disabled = false; }
            if (cancel) cancel.onclick = null;
            if (input)  input.oninput  = null;
            if (wordEl) { wordEl.onclick = null; wordEl.textContent = word; }
            document.removeEventListener('keydown', onKey);
            if (ok) ok.classList.remove('btn-red');
            if (icon) icon.style.display = 'none';
            resolve({ ok: !!(val && matches()),
                      checked: !!(checkBox && checkBox.checked && checkWrap && checkWrap.style.display !== 'none') });
        };
        if (input)  input.oninput   = sync;
        if (wordEl) wordEl.onclick  = () => {
            if (typeof _copyToClipboard === 'function') _copyToClipboard(word);
            const was = wordEl.textContent;
            wordEl.textContent = 'copied';
            setTimeout(() => { wordEl.textContent = was; }, 900);
            if (input) input.focus();
        };
        if (ok)     ok.onclick      = () => { if (matches()) done(true); };
        if (cancel) cancel.onclick  = () => done(false);
        document.addEventListener('keydown', onKey);
    });
}

let _mwMonacoEditor = null;
let _monacoThemesPromise = null;

function _monacoThemeName(isDark) { return isDark ? 'github-dark' : 'github-light'; }

function _ensureMonacoThemes() {
    if (_monacoThemesPromise) return _monacoThemesPromise;
    _monacoThemesPromise = Promise.all([
        fetch('/static/vendor/monaco-themes/GitHub%20Light.json').then(r => r.json()),
        fetch('/static/vendor/monaco-themes/GitHub%20Dark.json').then(r => r.json()),
    ]).then(([light, dark]) => {
        monaco.editor.defineTheme('github-light', light);
        monaco.editor.defineTheme('github-dark', dark);
    }).catch(() => { _monacoThemesPromise = null; });
    return _monacoThemesPromise;
}

function _initMwMonaco(value) {
    const container = document.getElementById('mwEditorContainer');
    if (!container) return;
    if (_mwMonacoEditor) {
        _mwMonacoEditor.setValue(value);
        setTimeout(() => _mwMonacoEditor.layout(), 50);
        return;
    }
    require(['vs/editor/editor.main'], function() {
        _ensureMonacoThemes().then(() => {
            const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
            _mwMonacoEditor = monaco.editor.create(container, {
                value: value,
                language: 'yaml',
                theme: _monacoThemeName(isDark),
                minimap: { enabled: false },
                fontSize: 13,
                lineNumbers: 'off',
                scrollBeyondLastLine: false,
                automaticLayout: true,
                wordWrap: 'off',
            });
        });
    });
}

function _initStaticMonaco(content, containerId) {
    const container = document.getElementById(containerId || 'staticYamlPopoutEditor');
    if (!container) return;
    if (_staticMonaco) {
        _staticMonaco.setValue(content);
        return;
    }
    require(['vs/editor/editor.main'], function() {
        _ensureMonacoThemes().then(() => {
            const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
            _staticMonaco = monaco.editor.create(container, {
                value: content,
                language: 'yaml',
                theme: _monacoThemeName(isDark),
                minimap: { enabled: true },
                fontSize: 13,
                lineNumbers: 'on',
                scrollBeyondLastLine: false,
                automaticLayout: true,
                wordWrap: 'off',
            });
            _staticMonaco.onDidChangeModelContent(() => {
                if (_staticMonaco.getValue() !== _staticOriginalContent) {
                    _markStaticPending();
                } else if (!_staticSectionEdits) {
                    _clearStaticPending();
                }
            });
        });
    });
}

function openStaticYamlPopout() {
    const overlay = document.getElementById('staticYamlPopout');
    if (!overlay) return;
    overlay.style.display = 'flex';
    if (_staticMonaco) {
        setTimeout(() => _staticMonaco.layout(), 50);
    } else {
        _initStaticMonaco(_staticRawContent);
    }
}

async function openStaticYamlPopoutFromShortcut() {
    if (!_staticRawContent) {
        try {
            const res  = await agentFetch(_activeAgent ? '/api/static' : '/api/static/config');
            const data = await res.json();
            const raw  = _activeAgent ? data.content : data.raw;
            if (raw) {
                _staticRawContent = raw;
                _staticOriginalContent = raw;
            }
        } catch(e) {}
    }
    openStaticYamlPopout();
}

function closeStaticYamlPopout() {
    const overlay = document.getElementById('staticYamlPopout');
    if (overlay) overlay.style.display = 'none';
}

let _gitDiffEditor  = null;
let _gitDiffFiles   = [];
let _gitDiffActive  = 0;

function openGitDiffPopout(sha, files) {
    const overlay = document.getElementById('gitDiffPopout');
    if (!overlay) return;
    const title = document.getElementById('gitDiffPopoutTitle');
    if (title) title.textContent = 'Diff - ' + sha.slice(0, 8);
    _gitDiffFiles  = files;
    _gitDiffActive = 0;
    overlay.style.display = 'flex';
    _renderGitDiffTabs();
    _showGitDiffFile(0);
}

function _renderGitDiffTabs() {
    const tabs = document.getElementById('gitDiffFileTabs');
    if (!tabs) return;
    tabs.innerHTML = _gitDiffFiles.map((f, i) => {
        const name   = f.filename.split('/').pop();
        const active = i === _gitDiffActive;
        return `<button onclick="_showGitDiffFile(${i})" id="gitDiffTab${i}" title="${f.filename}" class="btn-secondary text-xs" style="${active ? 'background:var(--input-bg);border-color:var(--blue);' : ''}">${name}</button>`;
    }).join('');
}

function _showGitDiffFile(idx) {
    _gitDiffActive = idx;
    const f = _gitDiffFiles[idx];
    if (!f) return;
    _gitDiffFiles.forEach((_, i) => {
        const t = document.getElementById('gitDiffTab' + i);
        if (t) t.style.borderColor = i === idx ? 'var(--blue)' : '';
    });
    const ext  = f.filename.split('.').pop().toLowerCase();
    const lang = (ext === 'yml' || ext === 'yaml') ? 'yaml' : 'plaintext';
    const container = document.getElementById('gitDiffPopoutEditor');
    if (_gitDiffEditor) {
        _gitDiffEditor.setModel({
            original: monaco.editor.createModel(f.old, lang),
            modified: monaco.editor.createModel(f.new, lang),
        });
    } else {
        require(['vs/editor/editor.main'], function() {
            _ensureMonacoThemes().then(() => {
                const isDark = document.documentElement.classList.contains('dark');
                _gitDiffEditor = monaco.editor.createDiffEditor(container, {
                    readOnly:           true,
                    renderSideBySide:   true,
                    theme:              _monacoThemeName(isDark),
                    fontSize:           12,
                    minimap:            { enabled: false },
                    scrollBeyondLastLine: false,
                });
                _gitDiffEditor.setModel({
                    original: monaco.editor.createModel(f.old, lang),
                    modified: monaco.editor.createModel(f.new, lang),
                });
            });
        });
    }
}

function closeGitDiffPopout() {
    const overlay = document.getElementById('gitDiffPopout');
    if (overlay) overlay.style.display = 'none';
}

async function saveStaticPopout() {
    await saveStaticConfig();
    closeStaticYamlPopout();
}

let _staticRestartNeeded = false;

function _renderStaticStateBar() {
    const bar = document.getElementById('staticStateBar');
    if (!bar) return;
    if (_staticPendingChanges) {
        bar.className = 'static-state-bar static-state-pending';
        bar.style.display = 'flex';
        bar.innerHTML = `<i class="ph-bold ph-warning"></i>
            <span class="static-state-text">Unsaved changes - nothing is written to <code>traefik.yml</code> until you save</span>
            <button onclick="discardStaticChanges()" class="btn-secondary text-xs">Discard</button>
            <button onclick="saveStaticConfig()" class="btn-primary text-xs">Save</button>`;
        return;
    }
    if (_staticRestartNeeded) {
        bar.className = 'static-state-bar static-state-restart';
        bar.style.display = 'flex';
        bar.innerHTML = `<i class="ph-bold ph-warning-circle"></i>
            <span class="static-state-text">Saved. Traefik is still running the previous config.</span>
            <button onclick="triggerTraefikRestart()" class="btn-secondary text-xs static-state-restart-btn">Restart Traefik</button>`;
        return;
    }
    bar.style.display = 'none';
    bar.innerHTML = '';
}

function _markStaticPending() {
    if (_staticPendingChanges) return;
    _staticPendingChanges = true;
    _renderStaticStateBar();
}

function _clearStaticPending() {
    _staticPendingChanges = false;
    _renderStaticStateBar();
}

function _showStaticRestartBanner() {
    _staticRestartNeeded = true;
    _renderStaticStateBar();
}

function _hideStaticRestartBanner() {
    _staticRestartNeeded = false;
    _renderStaticStateBar();
}

async function discardStaticChanges() {
    await _loadStaticFromDisk();
}

async function saveStaticConfig() {
    const content = _staticMonaco ? _staticMonaco.getValue() : _staticRawContent;
    try {
        const fetchFn = _activeAgent
            ? () => agentFetch('/api/static', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ content }) })
            : () => fetch('/api/static/config', { method: 'POST', headers: { 'Content-Type': 'application/json', ..._csrfHeaders() }, body: JSON.stringify({ content }) });
        const res  = await fetchFn();
        if (!res.ok) { showToast(await _errText(res, 'Save failed'), 'error'); return; }
        const data = await res.json();
        if (data.ok) {
            _staticRawContent = content;
            _staticOriginalContent = content;
            _staticSaved = true;
            _staticSectionEdits = false;
            _clearStaticPending();
            _showStaticRestartBanner();
            showToast('Static config saved', 'success');
            try {
                const cfgUrl = _activeAgent
                    ? '/api/static/config?server=' + encodeURIComponent(_activeAgent.id)
                    : '/api/static/config';
                const r2 = await fetch(cfgUrl);
                const d2 = await r2.json();
                if (d2.parsed) _renderStaticSections(d2.parsed);
            } catch(e) {}
        } else {
            showToast(data.error || data.message || 'Save failed', 'error');
        }
    } catch(e) {
        showToast(_netErrText(e, 'Save failed'), 'error');
    }
}

let _routeYamlMonaco  = null;
let _routeYamlId      = '';
let _routeYamlContent = '';

function _initRouteYamlMonaco(content) {
    const container = document.getElementById('routeYamlPopoutEditor');
    if (!container) return;
    if (_routeYamlMonaco) {
        _routeYamlMonaco.setValue(content);
        _routeYamlContent = content;
        setTimeout(() => _routeYamlMonaco.layout(), 50);
        return;
    }
    require(['vs/editor/editor.main'], function() {
        _ensureMonacoThemes().then(() => {
            const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
            _routeYamlMonaco = monaco.editor.create(container, {
                value: content,
                language: 'yaml',
                theme: _monacoThemeName(isDark),
                minimap: { enabled: true },
                fontSize: 13,
                lineNumbers: 'on',
                scrollBeyondLastLine: false,
                automaticLayout: true,
                wordWrap: 'off',
            });
            _routeYamlContent = content;
        });
    });
}

async function openRouteYamlEditor(id) {
    _routeYamlId = id;
    const name = id.includes('::') ? id.slice(id.indexOf('::') + 2) : id;
    const title = document.getElementById('routeYamlPopoutTitle');
    if (title) title.textContent = `Raw YAML - ${name}`;
    try {
        const res  = await agentFetch(`/api/routes/${encodeURIComponent(id)}/raw`);
        if (!res.ok) { showToast(await _errText(res, 'Failed to load route YAML'), 'error'); return; }
        const data = await res.json();
        if (data.error) { showToast(data.error, 'error'); return; }
        const overlay = document.getElementById('routeYamlPopout');
        if (overlay) overlay.style.display = 'flex';
        _initRouteYamlMonaco(data.raw || '');
    } catch(e) {
        showToast(_netErrText(e, 'Failed to load route YAML'), 'error');
    }
}

function closeRouteYamlEditor() {
    const overlay = document.getElementById('routeYamlPopout');
    if (overlay) overlay.style.display = 'none';
}

async function saveRouteYaml() {
    const content = _routeYamlMonaco ? _routeYamlMonaco.getValue() : _routeYamlContent;
    try {
        const res = await agentFetch(`/api/routes/${encodeURIComponent(_routeYamlId)}/raw`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ..._csrfHeaders() },
            body: JSON.stringify({ content }),
        });
        if (!res.ok) { showToast(await _errText(res, 'Save failed'), 'error'); return; }
        const data = await res.json();
        if (data.ok) {
            closeRouteYamlEditor();
            refreshRoutes();
            fetchNotifications();
        } else {
            showToast(data.error || data.message || 'Save failed', 'error');
        }
    } catch(e) {
        showToast(_netErrText(e, 'Save failed'), 'error');
    }
}

function _showRestartOverlay() {
    const el = document.getElementById('traefikRestartOverlay');
    if (el) el.style.display = 'flex';
}

function _hideRestartOverlay() {
    const el = document.getElementById('traefikRestartOverlay');
    if (el) el.style.display = 'none';
}

async function _waitForReconnect(immediate = false, onBack = null) {
    setTimeout(() => {
        const btn = document.getElementById('traefikRestartManualReload');
        if (btn) btn.style.display = 'inline-block';
    }, 8000);
    const agentId = _activeAgent ? _activeAgent.id : null;
    const healthOk = async () => {
        const r = await fetch(agentId ? `/api/agents/${encodeURIComponent(agentId)}/health` : '/api/health',
            { signal: AbortSignal.timeout(agentId ? 6000 : 3000) });
        if (!r.ok) return false;
        if (!agentId) return true;
        const d = await r.json();
        return d.ok === true;
    };
    if (!immediate) {
        await new Promise(r => setTimeout(r, 1500));
        let wentDown = false;
        for (let i = 0; i < 8 && !wentDown; i++) {
            await new Promise(r => setTimeout(r, 1000));
            try { if (!await healthOk()) wentDown = true; }
            catch(e) { wentDown = true; }
        }
    }
    while (true) {
        await new Promise(r => setTimeout(r, 1500));
        try {
            if (await healthOk()) {
                if (typeof onBack === 'function') { _hideRestartOverlay(); onBack(); }
                else location.reload();
                return;
            }
        } catch(e) {}
    }
}

async function triggerTraefikRestart() {
    _showRestartOverlay();
    try {
        const res  = await agentFetch('/api/static/restart', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
        });
        let data = {};
        try { data = await res.json() || {}; } catch(e) {}
        if (data.ok) {
            _hideStaticRestartBanner();
            _staticSaved = false;
            _waitForReconnect(false);
        } else if (res.status === 502 || res.status === 504) {
            _hideStaticRestartBanner();
            _staticSaved = false;
            _waitForReconnect(true);
        } else {
            _hideRestartOverlay();
            showToast(data.error || data.message || ('Restart failed (HTTP ' + res.status + ')'), 'error');
        }
    } catch(e) {
        _hideStaticRestartBanner();
        _staticSaved = false;
        _waitForReconnect(true);
    }
}

let _staticParsedData    = {};
let _staticEditState     = { section: null, name: null };
let _staticActiveSection = 'entrypoints';
let _traefikRuntime      = null;

function _sfFormKey(s)   { return {entrypoints:'Ep', resolvers:'Res', plugins:'Plugin', providers:'Provider'}[s]||''; }
function _sfFormLabel(s) { return {entrypoints:'Entrypoint', resolvers:'Resolver', plugins:'Plugin', providers:'Provider'}[s]||''; }

function _updateStaticTabArrows() {
    const bar = document.getElementById('staticTabBar');
    const lBtn = document.getElementById('staticTabArrowL');
    const rBtn = document.getElementById('staticTabArrowR');
    if (!bar || !lBtn || !rBtn) return;
    const overflow = bar.scrollWidth > bar.clientWidth + 2;
    lBtn.style.display = overflow && bar.scrollLeft > 2 ? '' : 'none';
    rBtn.style.display = overflow && bar.scrollLeft < bar.scrollWidth - bar.clientWidth - 2 ? '' : 'none';
}

function _scrollStaticTabs(dir) {
    const bar = document.getElementById('staticTabBar');
    if (bar) bar.scrollBy({ left: dir * 160, behavior: 'smooth' });
}

function switchStaticSection(section) {
    _staticActiveSection = section;
    const head = document.getElementById('scHead-' + section);
    if (head) head.scrollIntoView({ block: 'start', behavior: 'smooth' });
}

function _semverParts(v) {
    const m = String(v || '').match(/(\d+)\.(\d+)\.(\d+)/);
    return m ? [+m[1], +m[2], +m[3]] : null;
}

function _traefikSupportsUnderscoreStrategy() {
    const p = _semverParts(typeof _currentVersion !== 'undefined' ? _currentVersion : '');
    if (!p) return true;
    const [maj, min, pat] = p;
    if (maj > 3) return true;
    if (maj < 3) return false;
    if (min > 7) return true;
    if (min === 7) return pat >= 6;
    return false;
}

function _traefikSupportsAliasStrategy() {
    const p = _semverParts(typeof _currentVersion !== 'undefined' ? _currentVersion : '');
    if (!p) return true;
    const [maj, min, pat] = p;
    if (maj > 3) return true;
    if (maj < 3) return false;
    if (min > 7) return true;
    if (min === 7) return pat >= 12;
    return false;
}

function _epHeaderStrategyKey() {
    return _traefikSupportsAliasStrategy() ? 'aliasHeadersStrategy' : 'underscoreHeadersStrategy';
}

function _epHeaderStrategyValue(ep) {
    return (ep && ep.http && (ep.http.aliasHeadersStrategy || ep.http.underscoreHeadersStrategy)) || '';
}

function _updateEpUnderscoreVisibility() {
    const row = document.getElementById('sfEpUnderscoreRow');
    const supported = _traefikSupportsAliasStrategy() || _traefikSupportsUnderscoreStrategy();
    if (row) row.style.display = supported ? 'block' : 'none';
    if (!supported) return;
    const alias = _traefikSupportsAliasStrategy();
    const lbl = document.getElementById('sfEpHdrLabel');
    if (lbl) lbl.textContent = alias ? 'Alias Headers' : 'Underscore Headers';
    const del = document.getElementById('sfEpHdrDelete');
    const rej = document.getElementById('sfEpHdrReject');
    if (del) del.textContent = alias ? 'Delete - strip aliased headers' : 'Delete - strip underscore headers';
    if (rej) rej.textContent = alias ? 'Reject - 400 on aliased headers' : 'Reject - 400 on underscore headers';
    const hint = document.getElementById('sfEpHdrHint');
    if (hint) {
        hint.innerHTML = alias
            ? 'Stops aliased header names (e.g. <code class="font-mono">X_Auth_User</code>, <code class="font-mono">X.Auth.User</code>) from bypassing forwardAuth. <code class="font-mono">Delete</code> recommended. <a href="https://traefik-manager.xyzlab.dev/hardening.html" target="_blank" style="color:var(--blue)">Learn more</a>'
            : 'Stops underscore header aliases (e.g. <code class="font-mono">X_Auth_User</code>) from bypassing forwardAuth. Traefik 3.7.12 widens this to every aliased name. <code class="font-mono">Delete</code> recommended. <a href="https://traefik-manager.xyzlab.dev/hardening.html" target="_blank" style="color:var(--blue)">Learn more</a>';
    }
}

function openStaticAddForm(section) {
    if (_staticEditState.section) closeStaticForm(_staticEditState.section);
    _staticEditState = { section, name: null };
    _resetStaticForm(section);
    if (section === 'entrypoints') _updateEpUnderscoreVisibility();
    const f = document.getElementById('staticForm-' + section);
    if (f) f.style.display = 'block';
    const btn = document.getElementById('sf' + _sfFormKey(section) + 'Btn');
    if (btn) btn.textContent = 'Add ' + _sfFormLabel(section);
    if (section === 'entrypoints') document.getElementById('sfEpName')?.focus();
    if (section === 'resolvers')   document.getElementById('sfResName')?.focus();
    if (section === 'plugins')     document.getElementById('sfPluginName')?.focus();
}

function openStaticEditForm(section, name) {
    if (_staticEditState.section) closeStaticForm(_staticEditState.section);
    _staticEditState = { section, name };
    _prefillStaticForm(section, name);
    if (section === 'entrypoints') _updateEpUnderscoreVisibility();
    const f = document.getElementById('staticForm-' + section);
    if (f) f.style.display = 'block';
    const btn = document.getElementById('sf' + _sfFormKey(section) + 'Btn');
    if (btn) btn.textContent = 'Save Changes';
}

function closeStaticForm(section) {
    if (!section) return;
    const f = document.getElementById('staticForm-' + section);
    if (f) f.style.display = 'none';
    _staticEditState = { section: null, name: null };
}

function _resetStaticForm(section) {
    if (section === 'entrypoints') {
        ['sfEpName','sfEpAddr','sfEpRedirect','sfEpTrustedIps','sfEpProxyIps','sfEpMiddlewares','sfEpTlsResolver','sfEpTlsOptions','sfEpReadTimeout','sfEpWriteTimeout','sfEpIdleTimeout'].forEach(id => { const e = document.getElementById(id); if (e) e.value = ''; });
        ['sfEpHttp3','sfEpFwdInsecure','sfEpProxyInsecure','sfEpTlsEnabled','sfEpAsDefault'].forEach(id => { const e = document.getElementById(id); if (e) e.checked = false; });
        const tlsRow = document.getElementById('sfEpTlsRow'); if (tlsRow) tlsRow.style.display = 'none';
    } else if (section === 'resolvers') {
        ['sfResName','sfResEmail','sfResProvider','sfResCaServer','sfResEabKid','sfResEabHmac','sfResDnsResolvers','sfResDnsDelay'].forEach(id => { const e = document.getElementById(id); if (e) e.value = ''; });
        const kt = document.getElementById('sfResKeyType'); if (kt) kt.value = '';
        const nc = document.getElementById('sfResDnsNoCheck'); if (nc) nc.checked = false;
        const st = document.getElementById('sfResStorage'); if (st) st.value = '/acme.json';
        const ch = document.getElementById('sfResChallenge'); if (ch) ch.value = 'dnsChallenge';
        onStaticChallengeChange();
    } else if (section === 'plugins') {
        ['sfPluginName','sfPluginModule','sfPluginVersion'].forEach(id => { const e = document.getElementById(id); if (e) e.value = ''; });
        const lp = document.getElementById('sfPluginLocal'); if (lp) lp.checked = false;
        const pv = document.getElementById('sfPluginVersion'); if (pv) pv.disabled = false;
    } else if (section === 'providers') {
        const t = document.getElementById('sfProviderType'); if (t) t.value = '';
        const w = document.getElementById('sfProviderEditorWrap'); if (w) w.style.display = 'none';
        if (_providerMonaco) _providerMonaco.setValue('');
    }
}

function _prefillStaticForm(section, name) {
    _resetStaticForm(section);
    const d = _staticParsedData || {};
    if (section === 'entrypoints') {
        const ep = (d.entryPoints || d.entrypoints || {})[name] || {};
        document.getElementById('sfEpName').value    = name;
        document.getElementById('sfEpAddr').value    = ep.address || '';
        document.getElementById('sfEpRedirect').value = ep.http?.redirections?.entryPoint?.to || '';
        const h3chk = document.getElementById('sfEpHttp3'); if (h3chk) h3chk.checked = !!ep.http3;
        const uhsSel = document.getElementById('sfEpUnderscore');
        if (uhsSel) uhsSel.value = _epHeaderStrategyValue(ep);
        const fh = ep.forwardedHeaders || {};
        const pp = ep.proxyProtocol || {};
        const tipsEl = document.getElementById('sfEpTrustedIps');
        if (tipsEl) tipsEl.value = Array.isArray(fh.trustedIPs) ? fh.trustedIPs.join('\n') : '';
        const ppEl = document.getElementById('sfEpProxyIps');
        if (ppEl) ppEl.value = Array.isArray(pp.trustedIPs) ? pp.trustedIPs.join('\n') : '';
        const fiEl = document.getElementById('sfEpFwdInsecure'); if (fiEl) fiEl.checked = !!fh.insecure;
        const piEl = document.getElementById('sfEpProxyInsecure'); if (piEl) piEl.checked = !!pp.insecure;
        const mwEl = document.getElementById('sfEpMiddlewares');
        if (mwEl) mwEl.value = Array.isArray(ep.http?.middlewares) ? ep.http.middlewares.join(', ') : '';
        const tlsOn = ep.http && ep.http.tls !== undefined && ep.http.tls !== null;
        const tlsChk = document.getElementById('sfEpTlsEnabled'); if (tlsChk) tlsChk.checked = tlsOn;
        const tlsRow = document.getElementById('sfEpTlsRow'); if (tlsRow) tlsRow.style.display = tlsOn ? '' : 'none';
        const tlsObj = (tlsOn && typeof ep.http.tls === 'object') ? ep.http.tls : {};
        const trEl = document.getElementById('sfEpTlsResolver'); if (trEl) trEl.value = tlsObj.certResolver || '';
        const toEl = document.getElementById('sfEpTlsOptions'); if (toEl) toEl.value = tlsObj.options || '';
        const adEl = document.getElementById('sfEpAsDefault'); if (adEl) adEl.checked = !!ep.asDefault;
        const rts = ep.transport?.respondingTimeouts || {};
        [['sfEpReadTimeout','readTimeout'],['sfEpWriteTimeout','writeTimeout'],['sfEpIdleTimeout','idleTimeout']].forEach(([id, k]) => {
            const e = document.getElementById(id);
            if (e) e.value = rts[k] !== undefined && rts[k] !== null ? String(rts[k]) : '';
        });
    } else if (section === 'resolvers') {
        const acme = ((d.certificatesResolvers || {})[name] || {}).acme || {};
        document.getElementById('sfResName').value    = name;
        document.getElementById('sfResEmail').value   = acme.email || '';
        document.getElementById('sfResStorage').value = acme.storage || '/acme.json';
        const ct = acme.dnsChallenge ? 'dnsChallenge' : acme.httpChallenge ? 'httpChallenge' : 'tlsChallenge';
        document.getElementById('sfResChallenge').value = ct;
        document.getElementById('sfResProvider').value  = (acme.dnsChallenge || {}).provider || '';
        document.getElementById('sfResHttpEp').value    = (acme.httpChallenge || {}).entryPoint || 'web';
        document.getElementById('sfResCaServer').value  = acme.caServer || '';
        const ktEl = document.getElementById('sfResKeyType'); if (ktEl) ktEl.value = acme.keyType || '';
        document.getElementById('sfResEabKid').value  = (acme.eab || {}).kid || '';
        document.getElementById('sfResEabHmac').value = (acme.eab || {}).hmacEncoded || '';
        const dns = acme.dnsChallenge || {};
        document.getElementById('sfResDnsResolvers').value = Array.isArray(dns.resolvers) ? dns.resolvers.join('\n') : '';
        const prop = dns.propagation || {};
        document.getElementById('sfResDnsDelay').value = prop.delayBeforeChecks !== undefined && prop.delayBeforeChecks !== null ? String(prop.delayBeforeChecks) : '';
        const ncEl = document.getElementById('sfResDnsNoCheck'); if (ncEl) ncEl.checked = !!prop.disableChecks;
        onStaticChallengeChange();
    } else if (section === 'plugins') {
        const exp = d.experimental || {};
        const isLocal = !!((exp.localPlugins || {})[name]);
        const p = isLocal ? exp.localPlugins[name] || {} : (exp.plugins || {})[name] || {};
        document.getElementById('sfPluginName').value    = name;
        document.getElementById('sfPluginModule').value  = p.moduleName || '';
        document.getElementById('sfPluginVersion').value = p.version || '';
        const lp = document.getElementById('sfPluginLocal'); if (lp) lp.checked = isLocal;
        const pv = document.getElementById('sfPluginVersion'); if (pv) pv.disabled = isLocal;
    } else if (section === 'providers') {
        const sel = document.getElementById('sfProviderType');
        if (sel) sel.value = name;
        const wrap = document.getElementById('sfProviderEditorWrap');
        if (wrap) wrap.style.display = '';
        const existing = ((d.providers || {})[name] || {});
        const yamlLines = Object.entries(existing).map(([k, v]) => `${k}: ${JSON.stringify(v)}`).join('\n');
        const initialYaml = yamlLines || (PROVIDER_TEMPLATES[name] || '');
        _initProviderMonaco(initialYaml);
    }
}

function onStaticChallengeChange() {
    const ct   = document.getElementById('sfResChallenge')?.value;
    const dns  = document.getElementById('sfResDnsRow');
    const http = document.getElementById('sfResHttpRow');
    const adv  = document.getElementById('sfResDnsAdvanced');
    if (dns)  dns.style.display  = ct === 'dnsChallenge'  ? '' : 'none';
    if (http) http.style.display = ct === 'httpChallenge' ? '' : 'none';
    if (adv)  adv.style.display  = ct === 'dnsChallenge'  ? '' : 'none';
}

async function _applyStaticSectionChange(body) {
    const res  = await fetch('/api/static/section', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ..._csrfHeaders() },
        body: JSON.stringify({ ...body, current_raw: _staticRawContent }),
    });
    if (!res.ok) { showToast(await _errText(res, 'Could not update the static config'), 'error'); return; }
    const data = await res.json();
    if (!data.ok) { showToast(data.error || data.message || 'Could not update the static config', 'error'); return; }
    _staticParsedData = data.parsed || {};
    _staticRawContent = data.raw || '';
    _renderStaticSections(_staticParsedData);
    if (_staticMonaco) _staticMonaco.setValue(_staticRawContent);
    _staticSectionEdits = true;
    _markStaticPending();
}

async function submitStaticSection(section) {
    const action   = _staticEditState.name ? 'edit' : 'add';
    const old_name = _staticEditState.name || '';
    let name, payload;
    if (section === 'entrypoints') {
        name    = document.getElementById('sfEpName').value.trim();
        payload = { address: document.getElementById('sfEpAddr').value.trim(), redirect_to: document.getElementById('sfEpRedirect').value.trim(), http3: document.getElementById('sfEpHttp3')?.checked || false, underscore_headers: document.getElementById('sfEpUnderscore')?.value || '',
            headers_strategy_key: _epHeaderStrategyKey(),
            trusted_ips: document.getElementById('sfEpTrustedIps')?.value || '',
            forwarded_insecure: document.getElementById('sfEpFwdInsecure')?.checked || false,
            proxy_trusted_ips: document.getElementById('sfEpProxyIps')?.value || '',
            proxy_insecure: document.getElementById('sfEpProxyInsecure')?.checked || false,
            middlewares: document.getElementById('sfEpMiddlewares')?.value || '',
            tls_enabled: document.getElementById('sfEpTlsEnabled')?.checked || false,
            tls_cert_resolver: document.getElementById('sfEpTlsResolver')?.value.trim() || '',
            tls_options: document.getElementById('sfEpTlsOptions')?.value.trim() || '',
            as_default: document.getElementById('sfEpAsDefault')?.checked || false,
            read_timeout: document.getElementById('sfEpReadTimeout')?.value.trim() || '',
            write_timeout: document.getElementById('sfEpWriteTimeout')?.value.trim() || '',
            idle_timeout: document.getElementById('sfEpIdleTimeout')?.value.trim() || '' };
    } else if (section === 'resolvers') {
        name    = document.getElementById('sfResName').value.trim();
        payload = { email: document.getElementById('sfResEmail').value.trim(), storage: document.getElementById('sfResStorage').value.trim(), challenge_type: document.getElementById('sfResChallenge').value, provider: document.getElementById('sfResProvider').value.trim(), http_entrypoint: document.getElementById('sfResHttpEp').value.trim(),
            ca_server: document.getElementById('sfResCaServer')?.value.trim() || '',
            key_type: document.getElementById('sfResKeyType')?.value || '',
            eab_kid: document.getElementById('sfResEabKid')?.value.trim() || '',
            eab_hmac: document.getElementById('sfResEabHmac')?.value.trim() || '',
            dns_resolvers: document.getElementById('sfResDnsResolvers')?.value || '',
            dns_delay: document.getElementById('sfResDnsDelay')?.value.trim() || '',
            dns_disable_checks: document.getElementById('sfResDnsNoCheck')?.checked || false };
    } else if (section === 'plugins') {
        name    = document.getElementById('sfPluginName').value.trim();
        payload = { moduleName: document.getElementById('sfPluginModule').value.trim(), version: document.getElementById('sfPluginVersion').value.trim(), local: document.getElementById('sfPluginLocal')?.checked || false };
    }
    if (!name) { showToast('Name is required', 'error'); return; }
    try {
        await _applyStaticSectionChange({ action, section, name, old_name, data: payload });
        closeStaticForm(section);
    } catch(e) { showToast(_netErrText(e, 'Could not update the static config'), 'error'); }
}

async function removeStaticItem(section, name) {
    if (!await _confirm(`Remove "${name}"?`, 'Remove Item', 'Remove')) return;
    try {
        await _applyStaticSectionChange({ action: 'remove', section, name, data: {} });
    } catch(e) { showToast(_netErrText(e, 'Could not update the static config'), 'error'); }
}

function _scFile(path) {
    if (!path) return '';
    const name = String(path).split('/').filter(Boolean).pop() || String(path);
    return `<span class="tm-cf" title="${_esc(path)}"><i class="ph-bold ph-file-code"></i>${_esc(name)}</span>`;
}

function _scRail(section, name) {
    const nd = JSON.stringify(name);
    return `<span class="tm-rail tm-rail-sm" onclick="event.stopPropagation()">` +
        `<button type="button" class="tm-btn" title="Edit" onclick='event.stopPropagation();openStaticEditForm("${section}",${nd})'><i class="ph-bold ph-pencil-simple"></i></button>` +
        `<button type="button" class="tm-btn" title="Delete" onclick='event.stopPropagation();removeStaticItem("${section}",${nd})'><i class="ph-bold ph-trash"></i></button>` +
        '</span>';
}

function _scRowRail(section, name, glyphs) {
    const g = (glyphs || []).map(([ic, cls, tip]) =>
        `<span class="sig-flag ${cls}" title="${_esc(tip)}"><i class="ph-bold ${ic}"></i></span>`).join('');
    const nd = JSON.stringify(name);
    return '<span class="sc-rail"><span class="sc-rail-glyphs">' + g + '</span>'
        + '<span class="sc-rail-btns">'
        + `<button type="button" class="sc-btn" title="Edit" onclick='event.stopPropagation();openStaticEditForm("${section}",${_esc(nd)})'><i class="ph-bold ph-pencil-simple"></i></button>`
        + `<button type="button" class="sc-btn sc-btn-del" title="Delete" onclick='event.stopPropagation();removeStaticItem("${section}",${_esc(nd)})'><i class="ph-bold ph-trash"></i></button>`
        + '</span></span>';
}

function _scRow(o) {
    const health = o.warn ? ' data-health="warn"' : (o.idle ? ' data-health="idle"' : '');
    const sub = o.warn
        ? `<span class="sig-ep-sub d-warn"><i class="ph-bold ph-warning" style="font-size:10px"></i> ${_esc(o.warn)}</span>`
        : (o.sub ? `<span class="sig-ep-sub">${_esc(o.sub)}</span>` : '');
    const n = (o.n === undefined || o.n === null || o.n === '') ? ''
        : (o.n === 0 ? '<span style="color:var(--muted);font-weight:400">-</span>' : _sdNum(o.n));
    return `<div class="sig-ep-row"${health} role="button" tabindex="0"`
        + ` onclick='openStaticEditForm("${o.section}",${_esc(JSON.stringify(o.name))})'>`
        + `<span class="sig-ep-id"><span class="sig-ep-name">${_esc(o.name)}</span>`
        + `<span class="sig-idle-txt" style="color:${o.tagColor || 'var(--muted)'}">${_esc(o.tag || '')}</span></span>`
        + `<span class="sig-ep-addr">${_esc(o.addr || '')}</span>`
        + '<span class="sig-ep-strip"></span>'
        + `<span class="sig-ep-n">${n}</span>`
        + `<span class="sig-ep-flags">${_scRowRail(o.section, o.name, o.glyphs)}</span>`
        + sub + '</div>';
}

function _scRows(rows) {
    return '<div class="sc-panel">' + rows.join('') + '</div>';
}

function _scGrid(cards) {
    return `<div class="tm-card-grid">${cards}</div>`;
}

function _scEmpty(text) {
    return `<div class="px-5 py-8 text-center text-sm" style="color:var(--muted)">${_esc(text)}</div>`;
}

function _scEpRow(name, ep) {
    const addr  = ep.address || '';
    const redir = ep.http?.redirections?.entryPoint?.to || '';
    const uhs   = _epHeaderStrategyValue(ep);
    const tips  = Array.isArray(ep.forwardedHeaders?.trustedIPs) ? ep.forwardedHeaders.trustedIPs.length : 0;
    const insecureFwd = !!ep.forwardedHeaders?.insecure;
    const insecurePp  = !!ep.proxyProtocol?.insecure;
    const isUdp = /\/udp$/i.test(addr);
    const isTcp = /\/tcp$/i.test(addr);
    const port  = addr.replace(/\/(tcp|udp)$/i, '').replace(/^.*:/, '');
    const proto = isUdp ? ['UDP', '#e2c041'] : isTcp ? ['TCP', 'var(--teal)']
                : port === '443' ? ['HTTPS', 'var(--green)'] : ['HTTP', 'var(--blue)'];
    const glyphs = [];
    if (ep.http3) glyphs.push(['ph-lightning', 'd-mw', 'HTTP/3 enabled']);
    if (redir) glyphs.push(['ph-arrow-u-up-right', 'd-off', 'redirects to ' + redir]);
    if (tips) glyphs.push(['ph-shield', 'd-blue', 'forwardedHeaders.trustedIPs: ' + tips + ' range(s)']);
    if (uhs) glyphs.push(['ph-shield-check', 'd-on', _epHeaderStrategyKey() + ': ' + uhs]);
    let warn = '';
    if (insecureFwd) warn = 'forwardedHeaders.insecure is on, any client can set X-Forwarded-For';
    else if (insecurePp) warn = 'proxyProtocol.insecure is on, the PROXY header is trusted from any source';
    const facts = [];
    if (redir) facts.push('redirects to ' + redir);
    if (tips) facts.push(tips + ' trusted range' + (tips > 1 ? 's' : ''));
    if (uhs) facts.push('underscore headers ' + uhs);
    return _scRow({
        section: 'entrypoints', name: name, tag: proto[0], tagColor: proto[1],
        addr: addr, n: _scCount('eps', name), glyphs: glyphs, warn: warn, sub: facts.join(' · '),
    });
}

function _tmEpCard(name, ep) {
    const addr  = ep.address || '';
    const redir = ep.http?.redirections?.entryPoint?.to || '';
    const uhs   = _epHeaderStrategyValue(ep);
    const tips  = Array.isArray(ep.forwardedHeaders?.trustedIPs) ? ep.forwardedHeaders.trustedIPs.length : 0;
    const isUdp = /\/udp$/i.test(addr);
    const isTcp = /\/tcp$/i.test(addr);
    const port  = addr.replace(/\/(tcp|udp)$/i, '').replace(/^.*:/, '');
    const proto = isUdp ? ['UDP', '#e2c041'] : isTcp ? ['TCP', 'var(--teal)']
                : port === '443' ? ['HTTPS', 'var(--green)'] : ['HTTP', 'var(--blue)'];
    const glyphs = (ep.http3 ? '<i class="ph-bold ph-lightning tm-glyph" style="color:var(--purple)" title="HTTP/3 enabled"></i>' : '')
        + (tips ? `<i class="ph-bold ph-shield tm-glyph" style="color:var(--blue)" title="forwardedHeaders.trustedIPs: ${tips} range(s)"></i>` : '')
        + (uhs ? `<i class="ph-bold ph-shield-check tm-glyph" style="color:var(--green)" title="${_epHeaderStrategyKey()}: ${_esc(uhs)}"></i>` : '');
    const vals = redir
        ? `<div class="tm-vals"><div class="tm-val tm-val-target"><i class="ph-bold ph-arrow-u-up-right"></i><span class="tm-v">redirects to ${_esc(redir)}</span></div></div>`
        : '';
    const meta = [
        `<span class="d-flat" style="color:${proto[1]}">${proto[0]}${port ? ' ' + _esc(port) : ''}</span>`,
        tips ? `${tips} trusted range${tips > 1 ? 's' : ''}` : '',
        uhs ? _esc(uhs) : '',
    ].filter(Boolean).join('<span class="tm-sep"> \u00b7 </span>');
    return `<div class="tm-card tm-card-flat" style="--tm-accent:${proto[1]}">
        <div class="tm-head">
            <span class="tm-ic tm-ic-tile"><i class="ph-bold ph-door-open"></i></span>
            <div class="tm-head-txt">
                <div class="tm-title"><span class="tm-name">${_esc(name)}</span>${glyphs}</div>
            </div>${_scRail('entrypoints', name)}
        </div>
        ${vals}
        <div class="tm-foot"><span class="tm-meta">${meta}</span></div>
    </div>`;
}

function _scResolverRow(name, res) {
    const acme   = (res || {}).acme || {};
    const isDns  = !!acme.dnsChallenge;
    const isHttp = !!acme.httpChallenge;
    const tag    = isDns ? 'DNS' : isHttp ? 'HTTP' : 'TLS';
    const color  = isDns ? 'var(--teal)' : isHttp ? 'var(--green)' : 'var(--blue)';
    const glyphs = [];
    if (acme.email) glyphs.push(['ph-envelope-simple', 'd-off', acme.email]);
    if (isDns && acme.dnsChallenge.provider) glyphs.push(['ph-cloud', 'd-blue', acme.dnsChallenge.provider]);
    if (acme.caServer) glyphs.push(['ph-buildings', 'd-off', acme.caServer]);
    const facts = [];
    if (acme.email) facts.push(acme.email);
    if (isDns && acme.dnsChallenge.provider) facts.push(acme.dnsChallenge.provider);
    if (acme.keyType) facts.push(acme.keyType);
    const warn = !acme.email ? 'no email set, Let\'s Encrypt requires one to issue certificates' : '';
    return _scRow({
        section: 'resolvers', name: name, tag: tag, tagColor: color,
        addr: acme.storage ? acme.storage.split('/').pop() : '', n: _scCount('resolvers', name),
        glyphs: glyphs, warn: warn, sub: facts.join(' · '),
    });
}

function _tmResolverCard(name, res) {
    const acme  = (res || {}).acme || {};
    const isDns = !!acme.dnsChallenge, isHttp = !!acme.httpChallenge;
    const kind  = isDns ? `DNS challenge \u00b7 ${acme.dnsChallenge.provider || '?'}` : isHttp ? 'HTTP challenge' : 'TLS challenge';
    const accent = isDns ? 'var(--blue)' : isHttp ? 'var(--orange)' : 'var(--green)';

    return `<div class="tm-card tm-card-flat" style="--tm-accent:${accent}">
        <div class="tm-head">
            <span class="tm-ic tm-ic-tile"><i class="ph-bold ph-certificate"></i></span>
            <div class="tm-head-txt">
                <div class="tm-title"><span class="tm-name">${_esc(name)}</span></div>
                <div class="tm-sub">${_esc(kind)}</div>
            </div>${_scRail('resolvers', name)}
        </div>
        <div class="tm-foot"><span class="tm-meta">${acme.email ? _esc(acme.email) : 'no account email'}</span>${_scFile(acme.storage || 'acme.json')}</div>
    </div>`;
}

function _scPluginRow(name, p) {
    const pl = p || {};
    const local = !!pl._local;
    return _scRow({
        section: 'plugins', name: name, tag: local ? 'local' : 'plugin',
        tagColor: local ? 'var(--teal)' : 'var(--purple)',
        addr: local ? '' : (pl.version || ''), n: _scCount('plugins', name),
        glyphs: local
            ? [['ph-folder-open', 'd-off', 'local plugin, loaded from disk']]
            : [['ph-package', 'd-mw', pl.moduleName || name]],
        sub: local ? 'local plugin' : (pl.moduleName || ''),
    });
}

function _tmPluginCard(name, p) {
    const vals = p.moduleName
        ? `<div class="tm-vals"><div class="tm-val"><i class="ph-bold ph-package"></i><span class="tm-v" title="${_esc(p.moduleName)}">${_esc(p.moduleName)}</span>${_tmCopy(p.moduleName)}</div></div>`
        : '';
    return `<div class="tm-card tm-card-flat" style="--tm-accent:var(--purple)">
        <div class="tm-head">
            <span class="tm-ic tm-ic-tile"><i class="ph-bold ph-puzzle-piece"></i></span>
            <div class="tm-head-txt">
                <div class="tm-title"><span class="tm-name">${_esc(name)}</span></div>
                <div class="tm-sub">${p._local ? 'local plugin' : _esc(p.version || 'no version pinned')}</div>
            </div>${_scRail('plugins', name)}
        </div>
        ${vals}
        <div class="tm-foot"><span class="tm-meta">${p._local ? 'plugins-local directory' : 'declared in traefik.yml'}</span></div>
    </div>`;
}

function _renderStaticEntrypoints(eps) {
    const keys = Object.keys(eps || {});
    const cnt  = document.getElementById('staticEpCount');
    if (cnt) cnt.textContent = keys.length;
    const el = document.getElementById('staticEpList');
    if (!el) return;
    if (!keys.length) {
        el.innerHTML = _scEmpty('No entrypoints configured');
        return;
    }
    el.innerHTML = _scRows(keys.map(name => _scEpRow(name, eps[name] || {})));
}

function _renderStaticResolvers(resolvers) {
    const keys = Object.keys(resolvers || {});
    const cnt  = document.getElementById('staticResolverCount');
    if (cnt) cnt.textContent = keys.length;
    const el = document.getElementById('staticResolverList');
    if (!el) return;
    if (!keys.length) {
        el.innerHTML = _scEmpty('No certificate resolvers configured');
        return;
    }
    el.innerHTML = _scRows(keys.map(name => _scResolverRow(name, resolvers[name])));
}

function _renderStaticPlugins(plugins, localPlugins) {
    const all = {};
    Object.entries(plugins || {}).forEach(([n, p]) => { all[n] = p || {}; });
    Object.entries(localPlugins || {}).forEach(([n, p]) => { all[n] = { ...(p || {}), _local: true }; });
    const keys = Object.keys(all);
    const cnt  = document.getElementById('staticPluginCount');
    if (cnt) cnt.textContent = keys.length;
    const el = document.getElementById('staticPluginList');
    if (!el) return;
    if (!keys.length) {
        el.innerHTML = _scEmpty('No plugins installed');
        return;
    }
    el.innerHTML = _scRows(keys.map(name => _scPluginRow(name, all[name])));
}

let _scCounts = null;

async function _scLoadCounts() {
    try {
        const [routers, certs, mws] = await Promise.all([
            agentFetch('/api/traefik/routers').then(r => r.json()).catch(() => null),
            agentFetch('/api/traefik/certs').then(r => r.json()).catch(() => null),
            agentFetch('/api/traefik/middlewares').then(r => r.json()).catch(() => null),
        ]);
        if (!routers || routers.error) return null;
        const eps = {}, provs = {}, resolvers = {}, plugins = {};
        const all = [].concat(routers.http || [], routers.tcp || [], routers.udp || []);
        all.forEach(r => {
            (typeof _sdUsing === 'function' ? _sdUsing(r) : (r.entryPoints || [])).forEach(e => {
                eps[e] = (eps[e] || 0) + 1;
            });
            const p = String(r.provider || String(r.name || '').split('@')[1] || '').trim();
            if (p) provs[p] = (provs[p] || 0) + 1;
        });
        if (certs && Array.isArray(certs.certs)) {
            certs.certs.forEach(c => {
                const rn = c.resolver || '';
                if (rn) resolvers[rn] = (resolvers[rn] || 0) + 1;
            });
        }
        if (mws) {
            [].concat(mws.http || [], mws.tcp || []).forEach(m => {
                const t = m && m.type ? String(m.type) : '';
                if (t) plugins[t] = (plugins[t] || 0) + 1;
            });
        }
        return { eps, provs, resolvers, plugins, certsOk: !!(certs && Array.isArray(certs.certs)) };
    } catch (e) { return null; }
}

function _scCount(kind, key) {
    if (!_scCounts) return null;
    const map = _scCounts[kind] || {};
    return map[key] === undefined ? 0 : map[key];
}

function _scHas(v) { return v !== undefined && v !== null; }

function _scFindings(d) {
    const out = [];
    const eps = d.entryPoints || d.entrypoints || {};
    Object.keys(eps).forEach(name => {
        const ep = eps[name] || {};
        if (ep.forwardedHeaders && ep.forwardedHeaders.insecure) {
            out.push(['ph-shield-warning', name + ' trusts forwarded headers from anyone', 'entrypoints']);
        }
        if (ep.proxyProtocol && ep.proxyProtocol.insecure) {
            out.push(['ph-shield-warning', name + ' trusts PROXY protocol from anyone', 'entrypoints']);
        }
    });
    const api = d.api;
    if (_scHas(api) && api && api.insecure) {
        out.push(['ph-lock-open', 'API is exposed without authentication', 'api']);
    }
    if (!_scHas(d.accessLog)) {
        out.push(['ph-scroll', 'no access log, the Logs tab has nothing to read', 'log']);
    }
    Object.keys(d.certificatesResolvers || {}).forEach(name => {
        const acme = (d.certificatesResolvers[name] || {}).acme || {};
        if (!acme.email) out.push(['ph-certificate', name + ' has no ACME email', 'resolvers']);
    });
    return out;
}

function _renderStaticVerdict(d) {
    const el = document.getElementById('staticVerdict');
    if (!el) return;
    const found = _scFindings(d);
    const shown = found.slice(0, 4);
    const more  = found.length - shown.length;
    const path  = window._staticConfigPath || '';
    const meta  = path
        ? `<span class="sig-verdict-meta"><b>${_esc(path.split('/').pop())}</b> ${_esc(path)}</span>`
        : '';
    if (!found.length) {
        el.innerHTML = '<div class="sig-verdict">'
            + '<i class="ph-fill ph-check-circle sig-verdict-ic"></i>'
            + '<span class="sig-verdict-txt">Nothing to flag</span>'
            + '<span class="sig-verdict-items"><span class="sig-ok">every section reads as configured</span></span>'
            + meta + '</div>';
        return;
    }
    const items = shown.map(([ic, txt, sec]) =>
        `<button type="button" class="sig-flag d-warn" onclick="_scJump('${sec}')" title="Go to ${_esc(sec)}">`
        + `<i class="ph-bold ${ic}"></i><span class="sig-fl">${_esc(txt)}</span></button>`).join('');
    el.innerHTML = '<div class="sig-verdict" data-health="warn">'
        + '<i class="ph-fill ph-warning-circle sig-verdict-ic"></i>'
        + `<span class="sig-verdict-txt">${found.length} to look at</span>`
        + `<span class="sig-verdict-items">${items}`
        + (more > 0 ? `<span class="sig-ok">+${more} more</span>` : '')
        + '</span>' + meta + '</div>';
}

function _scJump(section) {
    const fold = document.getElementById('scFold-' + section);
    if (fold && !fold.classList.contains('open')) toggleStaticFold(section);
    const target = fold || document.querySelector(`.sc-sec[data-sc-sec="${section}"]`);
    if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function toggleStaticNote(key) {
    const el = document.getElementById('scNotice-' + key);
    if (!el) return;
    const open = !el.classList.contains('open');
    el.classList.toggle('open', open);
    try { localStorage.setItem('scNote_' + key, open ? '1' : '0'); } catch (e) {}
}

function _scApplyNoteState() {
    document.querySelectorAll('.sc-notice').forEach(el => {
        const key = (el.id || '').replace('scNotice-', '');
        let open = false;
        try { open = localStorage.getItem('scNote_' + key) === '1'; } catch (e) {}
        el.classList.toggle('open', open);
    });
}

function _renderStaticPluginNotice() {
    const el = document.getElementById('staticPluginNotice');
    if (!el) return;
    el.innerHTML = _scNotice('plugins', 'Installing plugins',
        'These rows are what <code class="font-mono" style="background:var(--input-bg);padding:1px 4px;border-radius:3px">traefik.yml</code> declares. '
        + 'The <button type="button" onclick="closeSettingsModal();switchTab(\'plugins\')" style="color:var(--blue);background:none;border:none;cursor:pointer;padding:0;font:inherit;text-decoration:underline">Plugins tab</button> '
        + 'installs and removes them for you, and writes the middleware that uses them.');
}

function _scSetState(key, txt) {
    const el = document.getElementById('scState-' + key);
    if (el) el.innerHTML = txt;
}

function _scWarnTxt(t) { return `<span class="d-warn">${_esc(t)}</span>`; }

function _renderStaticFoldStates(d) {
    const api = d.api;
    const apiOn = _scHas(api);
    _scSetState('api', [
        apiOn ? 'enabled' : _scWarnTxt('disabled'),
        apiOn && (api || {}).dashboard !== false ? 'dashboard on' : 'dashboard off',
        (api || {}).insecure ? _scWarnTxt('insecure on') : 'insecure off',
        (api || {}).debug ? 'debug on' : 'debug off',
    ].join(' &middot; '));

    const log = d.log || {};
    _scSetState('log', [
        log.level || 'ERROR',
        log.format || 'text',
        log.filePath || 'stdout',
        _scHas(d.accessLog) ? 'access log on' : _scWarnTxt('access log off'),
    ].join(' &middot; '));

    const prom = (d.metrics || {}).prometheus;
    _scSetState('observability', [
        _scHas(d.ping) ? 'ping on' : 'ping off',
        _scHas(prom) ? 'metrics on' : 'metrics off',
        _scHas(d.tracing) ? 'tracing on' : 'tracing off',
    ].join(' &middot; '));

    const g = d['global'] || {};
    const core = d.core || {};
    _scSetState('system', [
        g.checkNewVersion === false ? 'version check off' : 'version check on',
        g.sendAnonymousUsage ? 'usage stats on' : 'usage stats off',
        'rule syntax ' + (core.defaultRuleSyntax === 'v2' ? 'v2' : 'v3'),
    ].join(' &middot; '));

    const plugins = Object.keys((d.experimental || {}).plugins || {})
        .concat(Object.keys((d.experimental || {}).localPlugins || {}));
    _scSetState('plugins', plugins.length ? _esc(plugins.join(' &middot; ')) : 'none installed');

    const prov = d.providers || {};
    const provBits = [];
    if (_scHas(prov.docker)) provBits.push('docker on'); else provBits.push('docker off');
    if (_scHas(prov.file)) {
        provBits.push('file ' + ((prov.file || {}).directory || (prov.file || {}).filename || 'on'));
    } else {
        provBits.push('file off');
    }
    const others = Object.keys(prov).filter(k => k !== 'docker' && k !== 'file' && k !== 'providersThrottleDuration');
    if (others.length) provBits.push(others.join(', '));
    _scSetState('providers', _esc(provBits.join(' · ')));
}

function _renderStaticSections(parsed) {
    _staticParsedData = parsed || {};
    _renderStaticEntrypoints(_staticParsedData.entryPoints || _staticParsedData.entrypoints || {});
    _renderStaticResolvers(_staticParsedData.certificatesResolvers || {});
    _renderStaticPlugins((_staticParsedData.experimental || {}).plugins || {}, (_staticParsedData.experimental || {}).localPlugins || {});
    _renderStaticApi(_staticParsedData.api);
    _renderStaticLog(_staticParsedData.log, _staticParsedData.accessLog);
    _renderStaticObservability(_staticParsedData.metrics, _staticParsedData.tracing, _staticParsedData.ping);
    _renderStaticSystem(_staticParsedData['global'], _staticParsedData.core, _staticParsedData.serversTransport);
    _renderStaticProviders(_staticParsedData.providers);
    _renderStaticVerdict(_staticParsedData);
    _renderStaticFoldStates(_staticParsedData);
    _renderStaticPluginNotice();
    _scApplyNoteState();
}

function onPromToggle() {
    staticToggle('promEnabled');
    const fields = document.getElementById('promFields');
    if (fields) fields.style.display = _staticToggleState('promEnabled') ? '' : 'none';
}

function onTraceToggle() {
    staticToggle('traceEnabled');
    const fields = document.getElementById('traceFields');
    if (fields) fields.style.display = _staticToggleState('traceEnabled') ? '' : 'none';
}

function _renderStaticObservability(metrics, tracing, ping) {
    _setStaticToggle('pingEnabled', ping !== undefined && ping !== null);
    const prom = (metrics || {}).prometheus;
    const hasProm = prom !== undefined && prom !== null;
    _setStaticToggle('promEnabled', hasProm);
    const pf = document.getElementById('promFields');
    if (pf) pf.style.display = hasProm ? '' : 'none';
    const p = prom || {};
    _setStaticToggle('promEpLabels', p.addEntryPointsLabels !== false);
    _setStaticToggle('promRouterLabels', !!p.addRoutersLabels);
    _setStaticToggle('promSvcLabels', p.addServicesLabels !== false);
    const hasTrace = tracing !== undefined && tracing !== null;
    _setStaticToggle('traceEnabled', hasTrace);
    const tf = document.getElementById('traceFields');
    if (tf) tf.style.display = hasTrace ? '' : 'none';
    const t = tracing || {};
    const ts = document.getElementById('sfTraceService'); if (ts) ts.value = t.serviceName || '';
    const tr = document.getElementById('sfTraceSample'); if (tr) tr.value = t.sampleRate !== undefined && t.sampleRate !== null ? String(t.sampleRate) : '';
    const te = document.getElementById('sfTraceEndpoint'); if (te) te.value = t.otlp?.http?.endpoint || '';
}

function _renderStaticSystem(globalData, coreData, serversTransport) {
    const g = globalData || {};
    _setStaticToggle('checkNewVersion', g.checkNewVersion !== false);
    _setStaticToggle('sendUsage', !!g.sendAnonymousUsage);
    const rs = document.getElementById('sfRuleSyntax');
    if (rs) rs.value = (coreData || {}).defaultRuleSyntax === 'v2' ? 'v2' : '';
    const st = serversTransport || {};
    _setStaticToggle('stInsecure', !!st.insecureSkipVerify);
    const cas = document.getElementById('sfStRootCAs');
    if (cas) cas.value = Array.isArray(st.rootCAs) ? st.rootCAs.join('\n') : '';
    const mi = document.getElementById('sfStMaxIdle');
    if (mi) mi.value = st.maxIdleConnsPerHost !== undefined && st.maxIdleConnsPerHost !== null ? String(st.maxIdleConnsPerHost) : '';
    const ft = st.forwardingTimeouts || {};
    [['sfStDialTimeout', 'dialTimeout'], ['sfStRespHeaderTimeout', 'responseHeaderTimeout'], ['sfStIdleConnTimeout', 'idleConnTimeout']].forEach(([id, k]) => {
        const e = document.getElementById(id);
        if (e) e.value = ft[k] !== undefined && ft[k] !== null ? String(ft[k]) : '';
    });
}

function staticToggle(id) {
    const el = document.getElementById('staticT-' + id);
    if (el) el.classList.toggle('on');
}
function _staticToggleState(id) {
    const el = document.getElementById('staticT-' + id);
    return el ? el.classList.contains('on') : false;
}
function _setStaticToggle(id, on) {
    const el = document.getElementById('staticT-' + id);
    if (el) el.classList.toggle('on', !!on);
}

function _syncStaticApiWarn() {
    const warn = document.getElementById('staticApiWarn');
    if (warn) warn.style.display = _staticToggleState('apiEnabled') ? 'none' : '';
}

function onApiEnabledToggle() {
    staticToggle('apiEnabled');
    _syncStaticApiWarn();
}

function onAccessLogToggle() {
    staticToggle('accessLog');
    const row = document.getElementById('accessLogPathRow');
    if (row) row.style.display = _staticToggleState('accessLog') ? '' : 'none';
}
function onDockerProviderToggle() {
    staticToggle('dockerEnabled');
    const fields = document.getElementById('dockerProviderFields');
    if (fields) fields.style.display = _staticToggleState('dockerEnabled') ? '' : 'none';
}
function onFileProviderToggle() {
    staticToggle('fileEnabled');
    const fields = document.getElementById('fileProviderFields');
    if (fields) fields.style.display = _staticToggleState('fileEnabled') ? '' : 'none';
}

function _renderStaticApi(apiData) {
    const enabled = apiData !== undefined && apiData !== null;
    _setStaticToggle('apiEnabled', enabled);
    const api = apiData || {};
    _setStaticToggle('dashboardEnabled', api.dashboard !== false);
    _setStaticToggle('insecure', !!api.insecure);
    _setStaticToggle('debugMode', !!api.debug);
    _syncStaticApiWarn();
}

function _renderStaticLog(logData, accessLogData) {
    const log = logData || {};
    const sel = document.getElementById('sfLogLevel');
    if (sel) sel.value = (log.level || 'ERROR').toUpperCase();
    const lfm = document.getElementById('sfLogFormat'); if (lfm) lfm.value = log.format === 'json' ? 'json' : '';
    const lfile = document.getElementById('sfLogFile'); if (lfile) lfile.value = log.filePath || '';
    const rot = document.getElementById('logRotationRow'); if (rot) rot.style.display = log.filePath ? '' : 'none';
    [['sfLogMaxSize', 'maxSize'], ['sfLogMaxBackups', 'maxBackups'], ['sfLogMaxAge', 'maxAge']].forEach(([id, k]) => {
        const e = document.getElementById(id);
        if (e) e.value = log[k] !== undefined && log[k] !== null ? String(log[k]) : '';
    });
    const lc = document.getElementById('sfLogCompress'); if (lc) lc.checked = !!log.compress;
    const hasAL = accessLogData !== undefined && accessLogData !== null;
    _setStaticToggle('accessLog', hasAL);
    const al = accessLogData || {};
    const inp = document.getElementById('sfAccessLogPath');
    if (inp) inp.value = al.filePath || '';
    const afm = document.getElementById('sfALFormat'); if (afm) afm.value = al.format === 'json' ? 'json' : '';
    const abuf = document.getElementById('sfALBuffering'); if (abuf) abuf.value = al.bufferingSize !== undefined && al.bufferingSize !== null ? String(al.bufferingSize) : '';
    const filt = al.filters || {};
    const asc = document.getElementById('sfALStatusCodes'); if (asc) asc.value = Array.isArray(filt.statusCodes) ? filt.statusCodes.join(', ') : '';
    const amd = document.getElementById('sfALMinDuration'); if (amd) amd.value = filt.minDuration !== undefined && filt.minDuration !== null ? String(filt.minDuration) : '';
    const art = document.getElementById('sfALRetry'); if (art) art.checked = !!filt.retryAttempts;
    const ahm = document.getElementById('sfALHeadersMode'); if (ahm) ahm.value = ((al.fields || {}).headers || {}).defaultMode || '';
    const row = document.getElementById('accessLogPathRow');
    if (row) row.style.display = hasAL ? '' : 'none';
}

function _scToggleProvider(key) {
    const card = document.getElementById('scProvCard-' + key);
    if (!card) return;
    const open = card.dataset.scOpen === '1';
    document.querySelectorAll('#staticProviderCards > [id^="scProvCard-"]').forEach(c => {
        c.dataset.scOpen = '0';
        c.style.display = 'none';
    });
    if (!open) { card.dataset.scOpen = '1'; card.style.display = ''; }
}

function _scProviderRow(key, label, on, addr, count, glyphs, warn) {
    const health = warn ? ' data-health="warn"' : (on ? '' : ' data-health="idle"');
    const sub = warn
        ? `<span class="sig-ep-sub d-warn"><i class="ph-bold ph-warning" style="font-size:10px"></i> ${_esc(warn)}</span>`
        : '';
    const g = (glyphs || []).map(([ic, cls, tip]) =>
        `<span class="sig-flag ${cls}" title="${_esc(tip)}"><i class="ph-bold ${ic}"></i></span>`).join('');
    const n = count === null || count === undefined ? ''
        : (count === 0 ? '<span style="color:var(--muted);font-weight:400">-</span>' : _sdNum(count));
    return `<div class="sig-ep-row"${health} role="button" tabindex="0" onclick="_scToggleProvider('${key}')">`
        + `<span class="sig-ep-id"><span class="sig-ep-name">${_esc(label)}</span>`
        + `<span class="sig-idle-txt" style="color:${on ? 'var(--green)' : 'var(--muted)'}">${on ? 'enabled' : 'disabled'}</span></span>`
        + `<span class="sig-ep-addr">${_esc(addr || '')}</span>`
        + '<span class="sig-ep-strip"></span>'
        + `<span class="sig-ep-n">${n}</span>`
        + `<span class="sig-ep-flags"><span class="sc-rail"><span class="sc-rail-glyphs">${g}</span>`
        + '<span class="sc-rail-btns"><button type="button" class="sc-btn" title="Edit"><i class="ph-bold ph-pencil-simple"></i></button></span>'
        + '</span></span>' + sub + '</div>';
}

function _scRenderProviderRows(prov) {
    const el = document.getElementById('staticProviderRows');
    if (!el) return;
    const configured = Object.keys(prov).filter(k => k !== 'providersThrottleDuration' && _scHas(prov[k]));
    const cnt = document.getElementById('staticProviderCount');
    if (cnt) cnt.textContent = configured.length;
    const rows = [];
    const hasDocker = _scHas(prov.docker);
    const d = prov.docker || {};
    rows.push(_scProviderRow('docker', 'docker', hasDocker,
        hasDocker ? (d.endpoint || 'unix:///var/run/docker.sock') : 'not configured',
        hasDocker ? _scCount('provs', 'docker') : null,
        hasDocker && d.watch !== false ? [['ph-eye', 'd-on', 'watch on']] : [],
        hasDocker && d.exposedByDefault !== false ? 'exposedByDefault is on, every container is routable unless it opts out' : ''));
    const hasFile = _scHas(prov.file);
    const f = prov.file || {};
    rows.push(_scProviderRow('file', 'file', hasFile,
        hasFile ? (f.directory || f.filename || 'no path set') : 'not configured',
        hasFile ? _scCount('provs', 'file') : null,
        hasFile && f.watch !== false ? [['ph-eye', 'd-on', 'watch on']] : [],
        hasFile && !f.directory && !f.filename ? 'neither directory nor filename is set' : ''));
    Object.keys(prov).filter(k => k !== 'docker' && k !== 'file' && k !== 'providersThrottleDuration')
        .forEach(k => {
            rows.push(_scProviderRow(k, k, true, 'configured in traefik.yml', _scCount('provs', k), [], ''));
        });
    el.innerHTML = _scRows(rows);
}

function _renderStaticProviders(providersData) {
    const prov = providersData || {};
    _scRenderProviderRows(prov);
    document.querySelectorAll('#staticProviderCards > [id^="scProvCard-"]').forEach(c => {
        if (c.dataset.scOpen !== '1') c.style.display = 'none';
    });
    const hasDocker = prov.docker !== undefined && prov.docker !== null;
    _setStaticToggle('dockerEnabled', hasDocker);
    const dockerFields = document.getElementById('dockerProviderFields');
    if (dockerFields) dockerFields.style.display = hasDocker ? '' : 'none';
    if (hasDocker) {
        const ep = document.getElementById('sfDockerEndpoint');
        if (ep) ep.value = (prov.docker || {}).endpoint || 'unix:///var/run/docker.sock';
        _setStaticToggle('dockerExposedByDefault', (prov.docker || {}).exposedByDefault !== false);
        _setStaticToggle('dockerWatch', (prov.docker || {}).watch !== false);
    }
    const hasFile = prov.file !== undefined && prov.file !== null;
    _setStaticToggle('fileEnabled', hasFile);
    const fileFields = document.getElementById('fileProviderFields');
    if (fileFields) fileFields.style.display = hasFile ? '' : 'none';
    if (hasFile) {
        const dir = document.getElementById('sfFileDirectory');
        if (dir) dir.value = (prov.file || {}).directory || '';
        _setStaticToggle('fileWatch', (prov.file || {}).watch !== false);
    }
    const thr = document.getElementById('sfProvidersThrottle');
    if (thr) thr.value = prov.providersThrottleDuration !== undefined && prov.providersThrottleDuration !== null ? String(prov.providersThrottleDuration) : '';
    const otherEl = document.getElementById('staticOtherProvidersList');
    if (otherEl) {
        const others = Object.keys(prov).filter(k => k !== 'docker' && k !== 'file');
        if (others.length) {
            otherEl.innerHTML = `<div style="margin:0 16px 8px;background:var(--input-bg);border:1px solid var(--border);border-radius:8px;overflow:hidden;">` +
                others.map((k, i) => `
                    <div style="display:flex;align-items:center;justify-content:space-between;padding:10px 14px;${i > 0 ? 'border-top:1px solid var(--border)' : ''}">
                        <div class="flex items-center gap-2 text-sm">
                            <i class="ph-bold ph-cloud" style="color:var(--teal)"></i>
                            <span class="font-medium">${_esc(k)}</span>
                        </div>
                        <button onclick="removeStaticItem('providers',${_jsArg(k)})" class="btn-secondary text-xs flex items-center gap-1" style="height:24px;padding:0 8px;color:var(--red)">
                            <i class="ph-bold ph-trash text-sm"></i>
                        </button>
                    </div>`).join('') +
                `</div>`;
        } else {
            otherEl.innerHTML = '';
        }
    }
}

const PROVIDER_TEMPLATES = {
    swarm:              `endpoint: "unix:///var/run/docker.sock"\nexposedByDefault: false\nwatch: true`,
    http:               `endpoint: "http://your-config-server/api/config"\npollInterval: "5s"\npollTimeout: "5s"`,
    kubernetesCRD:      `endpoint: ""\ntoken: ""\ncertAuthFilePath: ""\nnamespaces: []\nlabelselector: ""`,
    kubernetesIngress:  `endpoint: ""\ntoken: ""\nnamespaces: []\ningressClass: ""\ningressEndpoint:\n  publishedService: ""`,
    kubernetesGateway:  `endpoint: ""\nexperimentalChannel: false`,
    nomad:              `endpoint: "http://localhost:4646"\nprefix: "traefik"\nstale: false\nnamespaces: []`,
    ecs:                `clusters:\n  - default\nautoDiscoverClusters: false\nregion: "us-east-1"\nexposedByDefault: true`,
    consulCatalog:      `prefix: "traefik"\nrefreshInterval: "15s"\nendpoint:\n  address: "127.0.0.1:8500"\n  scheme: ""\n  datacenter: ""\n  token: ""\nexposedByDefault: true`,
    consul:             `endpoints:\n  - "127.0.0.1:8500"\nrootKey: "traefik"\nnamespace: ""\ntoken: ""`,
    redis:              `endpoints:\n  - "127.0.0.1:6379"\nrootKey: "traefik"\npassword: ""\ndb: 0`,
    etcd:               `endpoints:\n  - "127.0.0.1:2379"\nrootKey: "traefik"\nusername: ""\npassword: ""`,
    zooKeeper:          `endpoints:\n  - "127.0.0.1:2181"\nrootKey: "traefik"\nusername: ""\npassword: ""`,
};

let _providerMonaco = null;

function _initProviderMonaco(value) {
    const container = document.getElementById('sfProviderEditorContainer');
    if (!container) return;
    if (_providerMonaco) {
        _providerMonaco.setValue(value);
        setTimeout(() => _providerMonaco.layout(), 50);
        return;
    }
    require(['vs/editor/editor.main'], function() {
        _ensureMonacoThemes().then(() => {
            const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
            _providerMonaco = monaco.editor.create(container, {
                value: value,
                language: 'yaml',
                theme: _monacoThemeName(isDark),
                minimap: { enabled: false },
                fontSize: 13,
                lineNumbers: 'off',
                scrollBeyondLastLine: false,
                automaticLayout: true,
                wordWrap: 'off',
            });
        });
    });
}

function onProviderTypeSelect(val) {
    const wrap = document.getElementById('sfProviderEditorWrap');
    if (!val) { if (wrap) wrap.style.display = 'none'; return; }
    if (wrap) wrap.style.display = '';
    const tpl = PROVIDER_TEMPLATES[val] || '';
    _initProviderMonaco(tpl);
}

async function submitStaticProvider() {
    const type = (document.getElementById('sfProviderType')?.value || '').trim();
    if (!type) { showToast('Select a provider type', 'error'); return; }
    const yaml_config = _providerMonaco ? _providerMonaco.getValue() : '';
    const action   = _staticEditState.name ? 'edit' : 'add';
    const old_name = _staticEditState.name || '';
    try {
        await _applyStaticSectionChange({ action, section: 'providers', name: type, old_name, data: { yaml_config } });
        closeStaticForm('providers');
    } catch(e) { showToast(_netErrText(e, 'Could not update the static config'), 'error'); }
}

async function saveStaticSingleSection(section) {
    let data = {};
    if (section === 'api') {
        data = {
            enabled: _staticToggleState('apiEnabled'),
            dashboard: _staticToggleState('dashboardEnabled'),
            insecure: _staticToggleState('insecure'),
            debug: _staticToggleState('debugMode'),
        };
    } else if (section === 'log') {
        data = {
            level: document.getElementById('sfLogLevel')?.value || 'ERROR',
            log_format: document.getElementById('sfLogFormat')?.value || '',
            log_file: document.getElementById('sfLogFile')?.value.trim() || '',
            log_max_size: document.getElementById('sfLogMaxSize')?.value.trim() || '',
            log_max_backups: document.getElementById('sfLogMaxBackups')?.value.trim() || '',
            log_max_age: document.getElementById('sfLogMaxAge')?.value.trim() || '',
            log_compress: document.getElementById('sfLogCompress')?.checked || false,
            accessLog: _staticToggleState('accessLog'),
            accessLogPath: document.getElementById('sfAccessLogPath')?.value.trim() || '',
            al_format: document.getElementById('sfALFormat')?.value || '',
            al_buffering: document.getElementById('sfALBuffering')?.value.trim() || '',
            al_status_codes: document.getElementById('sfALStatusCodes')?.value || '',
            al_min_duration: document.getElementById('sfALMinDuration')?.value.trim() || '',
            al_retry: document.getElementById('sfALRetry')?.checked || false,
            al_headers_mode: document.getElementById('sfALHeadersMode')?.value || '',
        };
    } else if (section === 'observability') {
        data = {
            ping: _staticToggleState('pingEnabled'),
            prometheus: _staticToggleState('promEnabled'),
            prom_ep_labels: _staticToggleState('promEpLabels'),
            prom_router_labels: _staticToggleState('promRouterLabels'),
            prom_svc_labels: _staticToggleState('promSvcLabels'),
            tracing: _staticToggleState('traceEnabled'),
            trace_service: document.getElementById('sfTraceService')?.value.trim() || '',
            trace_sample: document.getElementById('sfTraceSample')?.value.trim() || '',
            trace_endpoint: document.getElementById('sfTraceEndpoint')?.value.trim() || '',
        };
    } else if (section === 'system') {
        data = {
            check_new_version: _staticToggleState('checkNewVersion'),
            send_usage: _staticToggleState('sendUsage'),
            rule_syntax: document.getElementById('sfRuleSyntax')?.value || '',
            st_insecure: _staticToggleState('stInsecure'),
            st_root_cas: document.getElementById('sfStRootCAs')?.value || '',
            st_max_idle: document.getElementById('sfStMaxIdle')?.value.trim() || '',
            st_dial: document.getElementById('sfStDialTimeout')?.value.trim() || '',
            st_resp_header: document.getElementById('sfStRespHeaderTimeout')?.value.trim() || '',
            st_idle_conn: document.getElementById('sfStIdleConnTimeout')?.value.trim() || '',
        };
    } else if (section === 'providers') {
        data = {
            docker: _staticToggleState('dockerEnabled'),
            dockerEndpoint: document.getElementById('sfDockerEndpoint')?.value.trim() || '',
            dockerExposedByDefault: _staticToggleState('dockerExposedByDefault'),
            dockerWatch: _staticToggleState('dockerWatch'),
            file: _staticToggleState('fileEnabled'),
            fileDirectory: document.getElementById('sfFileDirectory')?.value.trim() || '',
            fileWatch: _staticToggleState('fileWatch'),
            providers_throttle: document.getElementById('sfProvidersThrottle')?.value.trim() || '',
        };
    }
    try {
        await _applyStaticSectionChange({ action: 'set', section, name: '', data });
        const save = document.querySelector(`.sc-save[data-sc-save="${section}"]`);
        if (save) save.style.display = 'none';
    } catch(e) { showToast(_netErrText(e, 'Could not update the static config'), 'error'); }
}

function _buildStaticTabHTML() {
    return '<div class="sig-root sc-root">' + _buildStaticOnePage() + '</div>';
}

function _scSectionHead(key, label, icon, color, countId, addLabel) {
    const count = countId ? `<span class="d-n sc-count" id="${countId}">0</span>` : '';
    const add = addLabel
        ? `<div class="flex gap-1 p-1 rounded-lg" style="background:var(--input-bg);border:1px solid var(--border)"><button onclick="openStaticAddForm('${key}')" class="proto-btn text-xs px-3 py-1.5" title="Add ${addLabel}"><i class="ph-bold ph-plus"></i></button></div>`
        : '';
    return `<div class="sc-sec-head" id="scHead-${key}"><i class="ph-bold ${icon} sc-sec-icon" style="color:${color}"></i><span class="sc-sec-label">${label}</span>${count}<span class="sc-sec-rule"></span>${add}</div>`;
}

function _scHeadActions() {
    const grp = (fn, icon, title) =>
        `<div class="flex gap-1 p-1 rounded-lg" style="background:var(--input-bg);border:1px solid var(--border)">`
        + `<button type="button" onclick="${fn}" class="proto-btn text-xs px-3 py-1.5" title="${title}">`
        + `<i class="ph-bold ${icon}"></i></button></div>`;
    return '<div class="sc-head-actions">'
        + grp('openTrustedIpsHelper()', 'ph-shield-check', 'Add trusted proxy IPs to an entrypoint')
        + grp('openStaticYamlPopout()', 'ph-code', 'Raw YAML editor')
        + grp('refreshStaticTab()', 'ph-arrows-clockwise', 'Reload from disk')
        + '</div>';
}

const SC_SECTIONS = [
    ['entrypoints',   'Entrypoints',           'ph-door-open',   'var(--blue)',   'staticEpCount',       'Entrypoint'],
    ['resolvers',     'Certificate resolvers', 'ph-certificate', 'var(--green)',  'staticResolverCount', 'Resolver'],
    ['providers',     'Providers',             'ph-cloud',       'var(--teal)',   'staticProviderCount', 'Provider'],
    ['api',           'API and dashboard',     'ph-gauge',       'var(--orange)', null,                  null],
    ['log',           'Logging',               'ph-scroll',      '#ca8a04',       null,                  null],
    ['observability', 'Observability',         'ph-heartbeat',   'var(--green)',  null,                  null],
    ['system',        'System',                'ph-gear-six',    'var(--muted)',  null,                  null],
    ['plugins',       'Plugins',               'ph-plug',        'var(--purple)', 'staticPluginCount',   'Plugin'],
];

const SC_GROUPS = [
    ['Traffic in',   ['entrypoints', 'providers']],
    ['Certificates', ['resolvers']],
    ['Operations',   ['api', 'log', 'observability', 'system', 'plugins']],
];

const SC_LIST_SECTIONS = ['entrypoints', 'resolvers', 'providers', 'plugins'];

function _scIsList(key) { return SC_LIST_SECTIONS.indexOf(key) !== -1; }

function _scFoldOpen(key) {
    if (_scIsList(key)) return true;
    const open = tmPref('staticOpenSections');
    if (Array.isArray(open)) return open.indexOf(key) !== -1;
    return false;
}

function toggleStaticFold(key) {
    const el = document.getElementById('scFold-' + key);
    if (!el) return;
    const nowOpen = !el.classList.contains('open');
    el.classList.toggle('open', nowOpen);
    const cur = tmPref('staticOpenSections');
    const list = Array.isArray(cur) ? cur.slice() : [];
    const at = list.indexOf(key);
    if (nowOpen && at === -1) list.push(key);
    if (!nowOpen && at !== -1) list.splice(at, 1);
    tmSetPref('staticOpenSections', list);
}

function _scFoldHead(key, label, icon, color, countId) {
    const count = countId ? `<span class="d-n sc-count" id="${countId}">0</span>` : '';
    return `<button type="button" class="sc-fold-head" onclick="toggleStaticFold('${key}')">`
        + `<i class="ph-bold ph-caret-right sc-fold-caret"></i>`
        + `<i class="ph-bold ${icon} sc-sec-icon" style="color:${color}"></i>`
        + `<span class="sc-sec-label">${label}</span>${count}`
        + `<span class="sc-sec-rule"></span>`
        + `<span class="sc-fold-state" id="scState-${key}"></span></button>`;
}

function _buildStaticOnePage() {
    const classic = document.createElement('div');
    classic.innerHTML = _buildStaticClassicHTML();
    const byKey = {};
    SC_SECTIONS.forEach(([key, label, icon, color, countId, addLabel]) => {
        const panel = classic.querySelector('#staticPanel-' + key);
        if (!panel) return;
        panel.style.display = '';
        const warn = panel.querySelector('#staticEpWarning');
        const form = panel.querySelector('#staticForm-' + key);
        if (warn && form) form.insertBefore(warn, form.firstChild);
        byKey[key] = _scIsList(key)
            ? `<section class="sc-sec" data-sc-sec="${key}">`
                + '<div class="sc-head-row">'
                + _scSectionHead(key, label, icon, color, countId, addLabel)
                + _scHeadActions() + '</div>'
                + panel.outerHTML + '</section>'
            : `<div class="sc-fold${_scFoldOpen(key) ? ' open' : ''}" id="scFold-${key}" data-sc-sec="${key}">`
                + '<div class="sc-head-row">'
                + _scFoldHead(key, label, icon, color, countId)
                + _scHeadActions() + '</div>'
                + '<div class="sc-fold-body">' + panel.outerHTML + '</div></div>';
    });
    return '<div id="staticVerdict"></div>'
        + SC_GROUPS.map(([label, keys]) => {
            const body = keys.map(k => byKey[k] || '').join('');
            return body ? `<div class="sc-grp">${label}</div>${body}` : '';
        }).join('');
}

function _buildStaticClassicHTML() {
    return `
    <div style="border-bottom:1px solid var(--border);flex-shrink:0;padding:12px 16px 0;display:flex;align-items:flex-end;gap:2px;">
        <button id="staticTabArrowL" onclick="_scrollStaticTabs(-1)" style="display:none;flex-shrink:0;background:none;border:none;cursor:pointer;padding:4px 3px 6px;color:var(--muted)" title="Scroll left"><i class="ph-bold ph-caret-left text-sm"></i></button>
        <div id="staticTabBar" style="display:flex;gap:2px;overflow-x:auto;scrollbar-width:none;-webkit-overflow-scrolling:touch;flex:1;" onscroll="_updateStaticTabArrows()">
            <button onclick="switchStaticSection('entrypoints')" id="ssnBtn-entrypoints" class="auth-sub-tab active">
                <i class="ph-bold ph-plugs" style="color:var(--blue)"></i>
                Entrypoints
                <span id="staticEpCount" style="display:inline-flex;align-items:center;min-width:14px;height:16px;padding:0 2px;font-size:10.5px;font-weight:700;color:var(--blue)">0</span>
            </button>
            <button onclick="switchStaticSection('resolvers')" id="ssnBtn-resolvers" class="auth-sub-tab">
                <i class="ph-bold ph-seal-check" style="color:var(--green)"></i>
                Cert Resolvers
                <span id="staticResolverCount" style="display:inline-flex;align-items:center;min-width:14px;height:16px;padding:0 2px;font-size:10.5px;font-weight:700;color:var(--green)">0</span>
            </button>
            <button onclick="switchStaticSection('plugins')" id="ssnBtn-plugins" class="auth-sub-tab">
                <i class="ph-bold ph-puzzle-piece" style="color:var(--purple)"></i>
                Plugins
                <span id="staticPluginCount" style="display:inline-flex;align-items:center;min-width:14px;height:16px;padding:0 2px;font-size:10.5px;font-weight:700;color:var(--purple)">0</span>
            </button>
            <button onclick="switchStaticSection('api')" id="ssnBtn-api" class="auth-sub-tab">
                <i class="ph-bold ph-gauge" style="color:var(--orange)"></i>
                API
            </button>
            <button onclick="switchStaticSection('log')" id="ssnBtn-log" class="auth-sub-tab">
                <i class="ph-bold ph-scroll" style="color:#ca8a04"></i>
                Logging
            </button>
            <button onclick="switchStaticSection('observability')" id="ssnBtn-observability" class="auth-sub-tab">
                <i class="ph-bold ph-heartbeat" style="color:var(--green)"></i>
                Observability
            </button>
            <button onclick="switchStaticSection('system')" id="ssnBtn-system" class="auth-sub-tab">
                <i class="ph-bold ph-gear-six" style="color:var(--muted)"></i>
                System
            </button>
            <button onclick="switchStaticSection('providers')" id="ssnBtn-providers" class="auth-sub-tab">
                <i class="ph-bold ph-cloud" style="color:var(--teal)"></i>
                Providers
            </button>
        </div>
        <button id="staticTabArrowR" onclick="_scrollStaticTabs(1)" style="display:none;flex-shrink:0;background:none;border:none;cursor:pointer;padding:4px 3px 6px;color:var(--muted)" title="Scroll right"><i class="ph-bold ph-caret-right text-sm"></i></button>
    </div>

    <div id="staticPanel-entrypoints">
        <div id="staticEpWarning"></div>
        <div id="staticEpList"></div>
        <div id="staticForm-entrypoints" style="display:none;border-top:1px solid var(--border);background:var(--input-bg)" class="px-5 py-4 space-y-3">
            <p class="text-xs font-semibold uppercase tracking-wide" style="color:var(--muted)" id="sfEpFormTitle">New Entrypoint</p>
            <div class="grid grid-cols-2 gap-3">
                <div>
                    <label class="text-xs block mb-1" style="color:var(--muted)">Name</label>
                    <input id="sfEpName" type="text" class="input-field text-sm" placeholder="websecure">
                </div>
                <div>
                    <label class="text-xs block mb-1" style="color:var(--muted)">Address</label>
                    <input id="sfEpAddr" type="text" class="input-field text-sm" placeholder=":443">
                </div>
            </div>
            <div>
                <label class="text-xs block mb-1" style="color:var(--muted)">HTTP → HTTPS redirect <span style="color:var(--muted);font-weight:400">(optional)</span></label>
                <input id="sfEpRedirect" type="text" class="input-field text-sm" placeholder="Name of the HTTPS entrypoint to redirect to, e.g. websecure">
            </div>
            <div class="flex items-center gap-2">
                <input type="checkbox" id="sfEpHttp3" class="rounded" style="accent-color:var(--blue)">
                <span class="text-xs" style="color:var(--text)">Enable HTTP/3 (QUIC)</span>
                <span class="text-xs" style="color:var(--muted)">- adds <code class="font-mono">http3: {}</code> to this entrypoint</span>
            </div>
            <div id="sfEpUnderscoreRow" style="display:none">
                <label class="text-xs block mb-1" style="color:var(--muted)"><span id="sfEpHdrLabel">Alias Headers</span> <span style="color:var(--muted);font-weight:400">(security)</span></label>
                <select id="sfEpUnderscore" class="input-field text-sm">
                    <option value="">Keep (default)</option>
                    <option id="sfEpHdrDelete" value="delete">Delete - strip aliased headers</option>
                    <option id="sfEpHdrReject" value="reject">Reject - 400 on aliased headers</option>
                </select>
                <p id="sfEpHdrHint" class="text-xs mt-1" style="color:var(--muted)">Stops aliased header names (e.g. <code class="font-mono">X_Auth_User</code>, <code class="font-mono">X.Auth.User</code>) from bypassing forwardAuth. <code class="font-mono">Delete</code> recommended. <a href="https://traefik-manager.xyzlab.dev/hardening.html" target="_blank" style="color:var(--blue)">Learn more</a></p>
            </div>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                    <label class="text-xs block mb-1" style="color:var(--muted)">Trusted IPs - forwarded headers <span style="font-weight:400">(optional)</span></label>
                    <textarea id="sfEpTrustedIps" class="input-field text-sm font-mono" rows="3" placeholder="173.245.48.0/20&#10;10.0.0.0/8" style="resize:vertical"></textarea>
                    <p class="text-xs mt-1" style="color:var(--muted)">IPs/CIDRs allowed to set <code class="font-mono">X-Forwarded-*</code>, one per line. The <i class="ph-bold ph-shield-check"></i> helper above can bulk-add Cloudflare ranges.</p>
                </div>
                <div>
                    <label class="text-xs block mb-1" style="color:var(--muted)">Trusted IPs - PROXY protocol <span style="font-weight:400">(optional)</span></label>
                    <textarea id="sfEpProxyIps" class="input-field text-sm font-mono" rows="3" placeholder="192.168.1.10/32" style="resize:vertical"></textarea>
                    <p class="text-xs mt-1" style="color:var(--muted)">Enables PROXY protocol from these load balancers, one per line.</p>
                </div>
            </div>
            <div class="flex items-center gap-2">
                <input type="checkbox" id="sfEpFwdInsecure" class="rounded" style="accent-color:var(--red)">
                <span class="text-xs" style="color:var(--text)">Trust forwarded headers from everyone</span>
                <span class="text-xs" style="color:var(--red)">- insecure, lets any client forge its IP</span>
            </div>
            <div class="flex items-center gap-2">
                <input type="checkbox" id="sfEpProxyInsecure" class="rounded" style="accent-color:var(--red)">
                <span class="text-xs" style="color:var(--text)">Accept PROXY protocol from everyone</span>
                <span class="text-xs" style="color:var(--red)">- insecure, testing only</span>
            </div>
            <div>
                <label class="text-xs block mb-1" style="color:var(--muted)">Middleware chain <span style="font-weight:400">(optional)</span></label>
                <input id="sfEpMiddlewares" type="text" class="input-field text-sm font-mono" placeholder="secure-headers@file, rate-limit@file">
                <p class="text-xs mt-1" style="color:var(--muted)">Prepended to every router on this entrypoint, comma separated, provider suffix included.</p>
            </div>
            <div class="flex items-center gap-2">
                <input type="checkbox" id="sfEpTlsEnabled" class="rounded" style="accent-color:var(--blue)" onchange="document.getElementById('sfEpTlsRow').style.display = this.checked ? '' : 'none'">
                <span class="text-xs" style="color:var(--text)">TLS on every router</span>
                <span class="text-xs" style="color:var(--muted)">- adds <code class="font-mono">http.tls</code> so routers here get TLS by default</span>
            </div>
            <div id="sfEpTlsRow" class="grid grid-cols-1 sm:grid-cols-2 gap-3" style="display:none">
                <div>
                    <label class="text-xs block mb-1" style="color:var(--muted)">Default cert resolver <span style="font-weight:400">(optional)</span></label>
                    <input id="sfEpTlsResolver" type="text" class="input-field text-sm" placeholder="cloudflare">
                </div>
                <div>
                    <label class="text-xs block mb-1" style="color:var(--muted)">Default TLS options <span style="font-weight:400">(optional)</span></label>
                    <input id="sfEpTlsOptions" type="text" class="input-field text-sm" placeholder="modern@file">
                </div>
            </div>
            <div class="flex items-center gap-2">
                <input type="checkbox" id="sfEpAsDefault" class="rounded" style="accent-color:var(--blue)">
                <span class="text-xs" style="color:var(--text)">Default entrypoint</span>
                <span class="text-xs" style="color:var(--muted)">- used by routers that list no entrypoints</span>
            </div>
            <div>
                <label class="text-xs block mb-1" style="color:var(--muted)">Responding timeouts <span style="font-weight:400">(optional, e.g. 60s, 1m30s, 0 = unlimited)</span></label>
                <div class="grid grid-cols-3 gap-3">
                    <input id="sfEpReadTimeout" type="text" class="input-field text-sm" placeholder="read (60s)">
                    <input id="sfEpWriteTimeout" type="text" class="input-field text-sm" placeholder="write (0)">
                    <input id="sfEpIdleTimeout" type="text" class="input-field text-sm" placeholder="idle (180s)">
                </div>
            </div>
            <div class="flex gap-2 justify-end pt-1">
                <button onclick="closeStaticForm('entrypoints')" class="btn-secondary text-xs">Cancel</button>
                <button onclick="submitStaticSection('entrypoints')" class="btn-primary text-xs" id="sfEpBtn">Add Entrypoint</button>
            </div>
        </div>
    </div>

    <div id="staticPanel-resolvers" style="display:none">
        <div id="staticResolverList"></div>
        <div id="staticForm-resolvers" style="display:none;border-top:1px solid var(--border);background:var(--input-bg)" class="px-5 py-4 space-y-3">
            <p class="text-xs font-semibold uppercase tracking-wide" style="color:var(--muted)" id="sfResFormTitle">New Resolver</p>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                    <label class="text-xs block mb-1" style="color:var(--muted)">Name</label>
                    <input id="sfResName" type="text" class="input-field text-sm" placeholder="cloudflare">
                </div>
                <div>
                    <label class="text-xs block mb-1" style="color:var(--muted)">Email</label>
                    <input id="sfResEmail" type="email" class="input-field text-sm" placeholder="you@example.com">
                </div>
                <div>
                    <label class="text-xs block mb-1" style="color:var(--muted)">Storage path</label>
                    <input id="sfResStorage" type="text" class="input-field text-sm" placeholder="/acme.json" value="/acme.json">
                </div>
                <div>
                    <label class="text-xs block mb-1" style="color:var(--muted)">Challenge type</label>
                    <select id="sfResChallenge" class="input-field text-sm" onchange="onStaticChallengeChange()">
                        <option value="dnsChallenge">DNS Challenge</option>
                        <option value="httpChallenge">HTTP Challenge</option>
                        <option value="tlsChallenge">TLS Challenge</option>
                    </select>
                </div>
                <div id="sfResDnsRow">
                    <label class="text-xs block mb-1" style="color:var(--muted)">DNS Provider</label>
                    <input id="sfResProvider" type="text" class="input-field text-sm" placeholder="cloudflare">
                </div>
                <div id="sfResHttpRow" style="display:none">
                    <label class="text-xs block mb-1" style="color:var(--muted)">HTTP Entrypoint</label>
                    <input id="sfResHttpEp" type="text" class="input-field text-sm" placeholder="web" value="web">
                </div>
                <div>
                    <label class="text-xs block mb-1" style="color:var(--muted)">CA server <span style="font-weight:400">(optional)</span></label>
                    <input id="sfResCaServer" type="text" class="input-field text-sm" placeholder="default: Let's Encrypt production">
                </div>
                <div>
                    <label class="text-xs block mb-1" style="color:var(--muted)">Key type <span style="font-weight:400">(optional)</span></label>
                    <select id="sfResKeyType" class="input-field text-sm">
                        <option value="">Default (RSA4096)</option>
                        <option value="EC256">EC256</option>
                        <option value="EC384">EC384</option>
                        <option value="RSA2048">RSA2048</option>
                        <option value="RSA3072">RSA3072</option>
                        <option value="RSA4096">RSA4096</option>
                        <option value="RSA8192">RSA8192</option>
                    </select>
                </div>
                <div>
                    <label class="text-xs block mb-1" style="color:var(--muted)">EAB key ID <span style="font-weight:400">(optional)</span></label>
                    <input id="sfResEabKid" type="text" class="input-field text-sm" placeholder="for CAs requiring external account binding">
                </div>
                <div>
                    <label class="text-xs block mb-1" style="color:var(--muted)">EAB HMAC <span style="font-weight:400">(optional)</span></label>
                    <input id="sfResEabHmac" type="text" class="input-field text-sm" placeholder="base64-encoded HMAC key">
                </div>
            </div>
            <div id="sfResDnsAdvanced" class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                    <label class="text-xs block mb-1" style="color:var(--muted)">DNS check resolvers <span style="font-weight:400">(optional)</span></label>
                    <textarea id="sfResDnsResolvers" class="input-field text-sm font-mono" rows="2" placeholder="1.1.1.1:53&#10;8.8.8.8:53" style="resize:vertical"></textarea>
                    <p class="text-xs mt-1" style="color:var(--muted)">Used to verify the DNS record before requesting the certificate, one per line.</p>
                </div>
                <div>
                    <label class="text-xs block mb-1" style="color:var(--muted)">Propagation delay <span style="font-weight:400">(optional)</span></label>
                    <input id="sfResDnsDelay" type="text" class="input-field text-sm" placeholder="e.g. 30s">
                    <div class="flex items-center gap-2 mt-2">
                        <input type="checkbox" id="sfResDnsNoCheck" class="rounded" style="accent-color:var(--blue)">
                        <span class="text-xs" style="color:var(--text)">Disable propagation checks</span>
                    </div>
                </div>
            </div>
            <div class="flex gap-2 justify-end pt-1">
                <button onclick="closeStaticForm('resolvers')" class="btn-secondary text-xs">Cancel</button>
                <button onclick="submitStaticSection('resolvers')" class="btn-primary text-xs" id="sfResBtn">Add Resolver</button>
            </div>
        </div>
    </div>

    <div id="staticPanel-plugins" style="display:none">
        <div id="staticPluginNotice"></div>
        <div id="staticPluginList"></div>
        <div id="staticForm-plugins" style="display:none;border-top:1px solid var(--border);background:var(--input-bg)" class="px-5 py-4 space-y-3">
            <p class="text-xs font-semibold uppercase tracking-wide" style="color:var(--muted)" id="sfPluginFormTitle">New Plugin</p>
            <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                    <label class="text-xs block mb-1" style="color:var(--muted)">Name</label>
                    <input id="sfPluginName" type="text" class="input-field text-sm" placeholder="my-plugin">
                </div>
                <div>
                    <label class="text-xs block mb-1" style="color:var(--muted)">Module</label>
                    <input id="sfPluginModule" type="text" class="input-field text-sm" placeholder="github.com/user/plugin">
                </div>
                <div>
                    <label class="text-xs block mb-1" style="color:var(--muted)">Version</label>
                    <input id="sfPluginVersion" type="text" class="input-field text-sm" placeholder="v1.0.0">
                </div>
            </div>
            <div class="flex items-center gap-2">
                <input type="checkbox" id="sfPluginLocal" class="rounded" style="accent-color:var(--teal)" onchange="document.getElementById('sfPluginVersion').disabled = this.checked">
                <span class="text-xs" style="color:var(--text)">Local plugin</span>
                <span class="text-xs" style="color:var(--muted)">- loaded from the <code class="font-mono">plugins-local</code> directory, no version needed</span>
            </div>
            <div class="flex gap-2 justify-end pt-1">
                <button onclick="closeStaticForm('plugins')" class="btn-secondary text-xs">Cancel</button>
                <button onclick="submitStaticSection('plugins')" class="btn-primary text-xs" id="sfPluginBtn">Add Plugin</button>
            </div>
        </div>
    </div>

    <div id="staticPanel-api" style="display:none">
        <div class="px-4 py-4 space-y-1.5">
            <div id="staticApiWarn" class="mb-3 rounded-lg px-3 py-2.5 flex items-start gap-2.5 text-xs" style="display:none;background:rgba(234,179,8,0.08);border:1px solid rgba(234,179,8,0.25);color:#ca8a04">
                <i class="ph-bold ph-warning text-sm shrink-0 mt-0.5"></i>
                <span>Traefik Manager reads your routes, services and middlewares from the Traefik API. With it disabled those tabs will be empty until you turn it back on and restart Traefik.</span>
            </div>
            <div class="tab-toggle-row" onclick="onApiEnabledToggle()">
                <span class="flex items-center gap-2 text-sm"><i class="ph-bold ph-terminal-window" style="color:var(--muted)"></i> API Enabled</span>
                <div class="toggle-switch" id="staticT-apiEnabled"><div class="toggle-knob"></div></div>
            </div>
            <div class="tab-toggle-row" onclick="staticToggle('dashboardEnabled')">
                <span class="flex items-center gap-2 text-sm"><i class="ph-bold ph-layout" style="color:var(--muted)"></i> Dashboard</span>
                <div class="toggle-switch" id="staticT-dashboardEnabled"><div class="toggle-knob"></div></div>
            </div>
            <div class="tab-toggle-row" onclick="staticToggle('insecure')">
                <span class="flex items-center gap-2 text-sm">
                    <i class="ph-bold ph-lock-open" style="color:var(--red)"></i>
                    <span>Insecure Mode</span>
                    <span class="text-xs" style="color:var(--muted)">(exposes API without auth)</span>
                </span>
                <div class="toggle-switch" id="staticT-insecure"><div class="toggle-knob"></div></div>
            </div>
            <div class="tab-toggle-row" onclick="staticToggle('debugMode')">
                <span class="flex items-center gap-2 text-sm"><i class="ph-bold ph-bug" style="color:var(--muted)"></i> Debug Mode</span>
                <div class="toggle-switch" id="staticT-debugMode"><div class="toggle-knob"></div></div>
            </div>
            <div class="flex justify-end pt-2 sc-save" data-sc-save="api" style="display:none">
                <button onclick="saveStaticSingleSection('api')" class="btn-primary text-xs">Save Changes</button>
            </div>
        </div>
    </div>

    <div id="staticPanel-log" style="display:none">
        <div class="px-4 py-4 space-y-3">
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                    <label class="text-xs block mb-1" style="color:var(--muted)">Log Level</label>
                    <select id="sfLogLevel" class="input-field text-sm">
                        <option value="DEBUG">DEBUG</option>
                        <option value="INFO">INFO</option>
                        <option value="WARN">WARN</option>
                        <option value="ERROR" selected>ERROR</option>
                    </select>
                </div>
                <div>
                    <label class="text-xs block mb-1" style="color:var(--muted)">Log Format</label>
                    <select id="sfLogFormat" class="input-field text-sm">
                        <option value="">Text (default)</option>
                        <option value="json">JSON</option>
                    </select>
                </div>
                <div class="sm:col-span-2">
                    <label class="text-xs block mb-1" style="color:var(--muted)">Traefik log file <span style="font-weight:400">(leave empty for stdout)</span></label>
                    <input id="sfLogFile" type="text" class="input-field text-sm" placeholder="/var/log/traefik/traefik.log" oninput="document.getElementById('logRotationRow').style.display = this.value.trim() ? '' : 'none'">
                </div>
            </div>
            <div id="logRotationRow" style="display:none">
                <label class="text-xs block mb-1" style="color:var(--muted)">Rotation <span style="font-weight:400">(optional)</span></label>
                <div class="grid grid-cols-3 gap-3">
                    <input id="sfLogMaxSize" type="text" class="input-field text-sm" placeholder="max size (MB)">
                    <input id="sfLogMaxBackups" type="text" class="input-field text-sm" placeholder="max backups">
                    <input id="sfLogMaxAge" type="text" class="input-field text-sm" placeholder="max age (days)">
                </div>
                <div class="flex items-center gap-2 mt-2">
                    <input type="checkbox" id="sfLogCompress" class="rounded" style="accent-color:var(--blue)">
                    <span class="text-xs" style="color:var(--text)">Compress rotated files</span>
                </div>
            </div>
            <div class="tab-toggle-row" onclick="onAccessLogToggle()">
                <span class="flex items-center gap-2 text-sm"><i class="ph-bold ph-file-text" style="color:var(--muted)"></i> Access Log</span>
                <div class="toggle-switch" id="staticT-accessLog"><div class="toggle-knob"></div></div>
            </div>
            <div id="accessLogPathRow" style="display:none" class="space-y-3">
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                        <label class="text-xs block mb-1" style="color:var(--muted)">Access log file <span style="font-weight:400">(empty = stdout)</span></label>
                        <input id="sfAccessLogPath" type="text" class="input-field text-sm" placeholder="/var/log/traefik/access.log">
                    </div>
                    <div>
                        <label class="text-xs block mb-1" style="color:var(--muted)">Format</label>
                        <select id="sfALFormat" class="input-field text-sm">
                            <option value="">CLF (default)</option>
                            <option value="json">JSON</option>
                        </select>
                    </div>
                    <div>
                        <label class="text-xs block mb-1" style="color:var(--muted)">Status code filter <span style="font-weight:400">(optional)</span></label>
                        <input id="sfALStatusCodes" type="text" class="input-field text-sm font-mono" placeholder="400-499, 500">
                        <p class="text-xs mt-1" style="color:var(--muted)">Only log these responses, comma separated codes or ranges.</p>
                    </div>
                    <div>
                        <label class="text-xs block mb-1" style="color:var(--muted)">Min duration filter <span style="font-weight:400">(optional)</span></label>
                        <input id="sfALMinDuration" type="text" class="input-field text-sm" placeholder="e.g. 200ms">
                        <p class="text-xs mt-1" style="color:var(--muted)">Only log requests slower than this.</p>
                    </div>
                    <div>
                        <label class="text-xs block mb-1" style="color:var(--muted)">Buffering <span style="font-weight:400">(lines, optional)</span></label>
                        <input id="sfALBuffering" type="text" class="input-field text-sm" placeholder="e.g. 100">
                    </div>
                    <div>
                        <label class="text-xs block mb-1" style="color:var(--muted)">Headers</label>
                        <select id="sfALHeadersMode" class="input-field text-sm">
                            <option value="">Drop (default)</option>
                            <option value="keep">Keep</option>
                            <option value="redact">Redact</option>
                        </select>
                    </div>
                </div>
                <div class="flex items-center gap-2">
                    <input type="checkbox" id="sfALRetry" class="rounded" style="accent-color:var(--blue)">
                    <span class="text-xs" style="color:var(--text)">Only log retry attempts</span>
                </div>
            </div>
            <div class="flex justify-end pt-1 sc-save" data-sc-save="log" style="display:none">
                <button onclick="saveStaticSingleSection('log')" class="btn-primary text-xs">Save Changes</button>
            </div>
        </div>
    </div>

    <div id="staticPanel-observability" style="display:none">
        <div class="px-4 py-4 space-y-3">
            <div class="tab-toggle-row" onclick="staticToggle('pingEnabled')">
                <span class="flex items-center gap-2 text-sm"><i class="ph-bold ph-heartbeat" style="color:var(--green)"></i> Ping endpoint <span class="text-xs" style="color:var(--muted)">/ping health check</span></span>
                <div class="toggle-switch" id="staticT-pingEnabled"><div class="toggle-knob"></div></div>
            </div>
            <div class="tab-toggle-row" onclick="onPromToggle()">
                <span class="flex items-center gap-2 text-sm"><i class="ph-bold ph-chart-line" style="color:var(--orange)"></i> Prometheus metrics <span class="text-xs" style="color:var(--muted)">/metrics</span></span>
                <div class="toggle-switch" id="staticT-promEnabled"><div class="toggle-knob"></div></div>
            </div>
            <div id="promFields" class="space-y-2" style="display:none">
                <div class="tab-toggle-row" onclick="staticToggle('promEpLabels')">
                    <span class="text-sm" style="color:var(--muted)">Entrypoint labels</span>
                    <div class="toggle-switch" id="staticT-promEpLabels"><div class="toggle-knob"></div></div>
                </div>
                <div class="tab-toggle-row" onclick="staticToggle('promRouterLabels')">
                    <span class="text-sm" style="color:var(--muted)">Router labels</span>
                    <div class="toggle-switch" id="staticT-promRouterLabels"><div class="toggle-knob"></div></div>
                </div>
                <div class="tab-toggle-row" onclick="staticToggle('promSvcLabels')">
                    <span class="text-sm" style="color:var(--muted)">Service labels</span>
                    <div class="toggle-switch" id="staticT-promSvcLabels"><div class="toggle-knob"></div></div>
                </div>
            </div>
            <div class="tab-toggle-row" onclick="onTraceToggle()">
                <span class="flex items-center gap-2 text-sm"><i class="ph-bold ph-waveform" style="color:var(--purple)"></i> Tracing <span class="text-xs" style="color:var(--muted)">OTLP</span></span>
                <div class="toggle-switch" id="staticT-traceEnabled"><div class="toggle-knob"></div></div>
            </div>
            <div id="traceFields" style="display:none">
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                        <label class="text-xs block mb-1" style="color:var(--muted)">Service name <span style="font-weight:400">(optional)</span></label>
                        <input id="sfTraceService" type="text" class="input-field text-sm" placeholder="traefik">
                    </div>
                    <div>
                        <label class="text-xs block mb-1" style="color:var(--muted)">Sample rate <span style="font-weight:400">(0 to 1, optional)</span></label>
                        <input id="sfTraceSample" type="text" class="input-field text-sm" placeholder="1.0">
                    </div>
                    <div class="sm:col-span-2">
                        <label class="text-xs block mb-1" style="color:var(--muted)">OTLP HTTP endpoint <span style="font-weight:400">(optional, default localhost:4318)</span></label>
                        <input id="sfTraceEndpoint" type="text" class="input-field text-sm" placeholder="http://collector:4318/v1/traces">
                    </div>
                </div>
            </div>
            <div class="flex justify-end pt-1 sc-save" data-sc-save="observability" style="display:none">
                <button onclick="saveStaticSingleSection('observability')" class="btn-primary text-xs">Save Changes</button>
            </div>
        </div>
    </div>

    <div id="staticPanel-system" style="display:none">
        <div class="px-4 py-4 space-y-3">
            <div class="tab-toggle-row" onclick="staticToggle('checkNewVersion')">
                <span class="flex items-center gap-2 text-sm"><i class="ph-bold ph-arrows-clockwise" style="color:var(--blue)"></i> Check for new Traefik versions</span>
                <div class="toggle-switch" id="staticT-checkNewVersion"><div class="toggle-knob"></div></div>
            </div>
            <div class="tab-toggle-row" onclick="staticToggle('sendUsage')">
                <span class="flex items-center gap-2 text-sm"><i class="ph-bold ph-chart-pie-slice" style="color:var(--muted)"></i> Send anonymous usage statistics</span>
                <div class="toggle-switch" id="staticT-sendUsage"><div class="toggle-knob"></div></div>
            </div>
            <div>
                <label class="text-xs block mb-1" style="color:var(--muted)">Default rule syntax</label>
                <select id="sfRuleSyntax" class="input-field text-sm">
                    <option value="">v3 (default)</option>
                    <option value="v2">v2 (compatibility)</option>
                </select>
                <p class="text-xs mt-1" style="color:var(--muted)">Only change this while migrating rules written for Traefik v2.</p>
            </div>
            <div>
                <p class="text-xs font-semibold uppercase tracking-wide mb-2" style="color:var(--muted)">Servers transport defaults</p>
                <div class="tab-toggle-row" onclick="staticToggle('stInsecure')">
                    <span class="text-sm" style="color:var(--text)">Skip backend TLS verification <span class="text-xs" style="color:var(--red)">- insecure</span></span>
                    <div class="toggle-switch" id="staticT-stInsecure"><div class="toggle-knob"></div></div>
                </div>
            </div>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                    <label class="text-xs block mb-1" style="color:var(--muted)">Root CAs <span style="font-weight:400">(optional, one path per line)</span></label>
                    <textarea id="sfStRootCAs" class="input-field text-sm font-mono" rows="2" placeholder="/certs/internal-ca.pem" style="resize:vertical"></textarea>
                </div>
                <div>
                    <label class="text-xs block mb-1" style="color:var(--muted)">Max idle conns per host <span style="font-weight:400">(optional)</span></label>
                    <input id="sfStMaxIdle" type="text" class="input-field text-sm" placeholder="default 200">
                </div>
            </div>
            <div>
                <label class="text-xs block mb-1" style="color:var(--muted)">Forwarding timeouts <span style="font-weight:400">(optional, e.g. 30s)</span></label>
                <div class="grid grid-cols-3 gap-3">
                    <input id="sfStDialTimeout" type="text" class="input-field text-sm" placeholder="dial (30s)">
                    <input id="sfStRespHeaderTimeout" type="text" class="input-field text-sm" placeholder="resp header (0)">
                    <input id="sfStIdleConnTimeout" type="text" class="input-field text-sm" placeholder="idle conn (90s)">
                </div>
            </div>
            <div class="flex justify-end pt-1 sc-save" data-sc-save="system" style="display:none">
                <button onclick="saveStaticSingleSection('system')" class="btn-primary text-xs">Save Changes</button>
            </div>
        </div>
    </div>

    <div id="staticPanel-providers" style="display:none">
        <div id="staticProviderRows"></div>
        <div id="staticOtherProvidersList" class="pt-3"></div>
        <div class="px-4 pb-4 space-y-3" id="staticProviderCards">
            <div class="rounded-lg p-3" id="scProvCard-docker" style="border:1px solid var(--border)">
                <div class="tab-toggle-row" onclick="onDockerProviderToggle()">
                    <span class="flex items-center gap-2 text-sm font-medium"><i class="ph-bold ph-cube" style="color:var(--blue)"></i> Docker</span>
                    <div class="toggle-switch" id="staticT-dockerEnabled"><div class="toggle-knob"></div></div>
                </div>
                <div id="dockerProviderFields" class="mt-3 space-y-2" style="display:none">
                    <div>
                        <label class="text-xs block mb-1" style="color:var(--muted)">Endpoint</label>
                        <input id="sfDockerEndpoint" type="text" class="input-field text-sm" placeholder="unix:///var/run/docker.sock">
                    </div>
                    <div class="tab-toggle-row" onclick="staticToggle('dockerExposedByDefault')">
                        <span class="text-sm" style="color:var(--muted)">Expose by default</span>
                        <div class="toggle-switch" id="staticT-dockerExposedByDefault"><div class="toggle-knob"></div></div>
                    </div>
                    <div class="tab-toggle-row" onclick="staticToggle('dockerWatch')">
                        <span class="text-sm" style="color:var(--muted)">Watch</span>
                        <div class="toggle-switch" id="staticT-dockerWatch"><div class="toggle-knob"></div></div>
                    </div>
                </div>
            </div>
            <div class="rounded-lg p-3" id="scProvCard-file" style="border:1px solid var(--border)">
                <div class="tab-toggle-row" onclick="onFileProviderToggle()">
                    <span class="flex items-center gap-2 text-sm font-medium"><i class="ph-bold ph-file-code" style="color:var(--green)"></i> File</span>
                    <div class="toggle-switch" id="staticT-fileEnabled"><div class="toggle-knob"></div></div>
                </div>
                <div id="fileProviderFields" class="mt-3 space-y-2" style="display:none">
                    <div>
                        <label class="text-xs block mb-1" style="color:var(--muted)">Directory</label>
                        <input id="sfFileDirectory" type="text" class="input-field text-sm" placeholder="/etc/traefik/dynamic">
                    </div>
                    <div class="tab-toggle-row" onclick="staticToggle('fileWatch')">
                        <span class="text-sm" style="color:var(--muted)">Watch</span>
                        <div class="toggle-switch" id="staticT-fileWatch"><div class="toggle-knob"></div></div>
                    </div>
                </div>
            </div>
            <div>
                <label class="text-xs block mb-1" style="color:var(--muted)">Providers throttle <span style="font-weight:400">(optional, e.g. 2s)</span></label>
                <input id="sfProvidersThrottle" type="text" class="input-field text-sm" placeholder="minimum time between config reloads (default 2s)">
            </div>
            <div class="flex justify-end pt-1 sc-save" data-sc-save="providers" style="display:none">
                <button onclick="saveStaticSingleSection('providers')" class="btn-primary text-xs">Save Changes</button>
            </div>
        </div>
        <div id="staticForm-providers" style="display:none;border-top:1px solid var(--border);background:var(--input-bg)" class="px-5 py-4 space-y-3">
            <p class="text-xs font-semibold uppercase tracking-wide" style="color:var(--muted)" id="sfProviderFormTitle">Add Provider</p>
            <div>
                <label class="text-xs block mb-1" style="color:var(--muted)">Provider Type</label>
                <select id="sfProviderType" class="input-field text-sm" onchange="onProviderTypeSelect(this.value)">
                    <option value="">Select provider...</option>
                    <option value="swarm">Docker Swarm</option>
                    <option value="http">HTTP</option>
                    <option value="kubernetesCRD">Kubernetes (CRD)</option>
                    <option value="kubernetesIngress">Kubernetes Ingress</option>
                    <option value="kubernetesGateway">Kubernetes Gateway</option>
                    <option value="nomad">HashiCorp Nomad</option>
                    <option value="ecs">AWS ECS</option>
                    <option value="consulCatalog">Consul Catalog</option>
                    <option value="consul">Consul KV</option>
                    <option value="redis">Redis KV</option>
                    <option value="etcd">etcd KV</option>
                    <option value="zooKeeper">ZooKeeper KV</option>
                </select>
            </div>
            <div id="sfProviderEditorWrap" style="display:none">
                <label class="text-xs block mb-1" style="color:var(--muted)">Configuration</label>
                <div id="sfProviderEditorContainer" style="height:220px;border:1px solid var(--border);border-radius:8px;overflow:hidden;"></div>
            </div>
            <div class="flex gap-2 justify-end pt-1">
                <button onclick="closeStaticForm('providers')" class="btn-secondary text-xs">Cancel</button>
                <button onclick="submitStaticProvider()" class="btn-primary text-xs" id="sfProviderBtn">Add Provider</button>
            </div>
        </div>
    </div>`;
}

function _scNotice(key, title, body) {
    return `<div class="sc-notice rounded-lg" id="scNotice-${key}" style="background:rgba(59,130,246,0.07);border:1px solid rgba(59,130,246,0.2)">
        <button type="button" onclick="toggleStaticNote('${key}')" class="w-full px-4 py-2.5 flex items-center gap-2 text-left" style="background:none;border:none;cursor:pointer">
            <i class="ph-bold ph-info text-sm shrink-0" style="color:var(--blue)"></i>
            <span class="text-xs font-semibold flex-1" style="color:var(--text)">${title}</span>
            <i class="ph-bold ph-caret-right sc-notice-caret text-xs" style="color:var(--muted)"></i>
        </button>
        <div class="sc-notice-body px-4 pb-3 text-xs" style="color:var(--muted)">${body}</div>
    </div>`;
}

function _renderEpRuntimeWarning() {
    const el = document.getElementById('staticEpWarning');
    if (!el) return;
    const rt = _traefikRuntime;
    if (!rt) return;
    let title = '', body = '';
    if (rt.runtime === 'docker') {
        title = 'New entrypoints also need a port mapping in your compose file';
        body  = `After adding an entrypoint here, open your <code class="font-mono" style="background:var(--input-bg);padding:1px 4px;border-radius:3px">docker-compose.yml</code> and add the port under <code class="font-mono" style="background:var(--input-bg);padding:1px 4px;border-radius:3px">ports:</code>, then run:
                 <code class="font-mono block mt-1.5 mb-1 px-2 py-1 rounded" style="background:var(--input-bg);border:1px solid var(--border)">docker compose up -d</code>
                 Without this the port will not be reachable outside the container even after restarting Traefik.`;
    } else if (rt.runtime === 'native') {
        title = 'New entrypoints need the port open on your system';
        body  = `After adding an entrypoint and restarting Traefik, ensure the port is accessible:
                 <code class="font-mono block mt-1.5 mb-1 px-2 py-1 rounded" style="background:var(--input-bg);border:1px solid var(--border)">sudo ufw allow PORT/tcp</code>
                 For ports below 1024, Traefik needs <code class="font-mono" style="background:var(--input-bg);padding:1px 4px;border-radius:3px">NET_BIND_SERVICE</code> capability or must run as root.`;
    } else {
        title = 'New entrypoints require additional steps after saving';
        body  = `<span class="font-medium" style="color:var(--text)">Docker / Podman / Unraid:</span> add the port under <code class="font-mono" style="background:var(--input-bg);padding:1px 4px;border-radius:3px">ports:</code> in your compose file and run <code class="font-mono" style="background:var(--input-bg);padding:1px 4px;border-radius:3px">docker compose up -d</code>
                 <span class="block mt-1"><span class="font-medium" style="color:var(--text)">Native Linux:</span> open the port in your firewall, e.g. <code class="font-mono" style="background:var(--input-bg);padding:1px 4px;border-radius:3px">sudo ufw allow PORT/tcp</code></span>`;
    }
    el.innerHTML = _scNotice('entrypoints', title, body);
    _scApplyNoteState();
}

async function _loadStaticFromDisk() {
    const wrapper = document.getElementById('staticSettingsContent');
    if (!wrapper) return;
    try {
        const cfgUrl = _activeAgent
            ? '/api/static/config?server=' + encodeURIComponent(_activeAgent.id)
            : '/api/static/config';
        _traefikRuntime = null;
        const fetches = [fetch(cfgUrl)];
        if (_activeAgent) {
            fetches.push(agentFetch('/api/static/status').then(r => r.json()).catch(() => null));
        } else {
            fetches.push(fetch('/api/traefik/runtime').then(r => r.json()).catch(() => null));
        }
        const results = await Promise.all(fetches);
        const res = results[0];
        if (_activeAgent) {
            const st = results[1];
            if (st && ['proxy', 'socket'].includes(st.restart_method)) {
                _traefikRuntime = { method: st.restart_method, runtime: 'docker', container: st.traefik_container || '' };
            }
        } else if (results[1]) {
            _traefikRuntime = results[1];
        }
        const data = await res.json();
        if (data.error) {
            _staticLoadedFor = null;
            const bar = document.getElementById('staticStateBar');
            if (bar) bar.style.display = 'none';
            const acts = document.querySelector('#tab-static .fb-secondary');
            if (acts) acts.style.display = 'none';
            const notMounted = res.ok || res.status === 404;
            wrapper.innerHTML = (!_activeAgent && notMounted && typeof _emptyMountState === 'function')
                ? _emptyMountState({
                    icon: 'ph-sliders',
                    title: 'traefik.yml not mounted',
                    description: 'Mount your Traefik <code class="font-mono" style="color:var(--blue)">traefik.yml</code> read-write to edit entrypoints, certificate resolvers, plugins and providers from here.',
                    steps: [
                        { label: 'Add this volume to the <code class="font-mono">traefik-manager</code> service in your <code class="font-mono">docker-compose.yml</code>:',
                          code: '- /path/to/traefik/traefik.yml:/app/traefik.yml' },
                    ],
                    note: 'Mount it read-write, without <code class="font-mono">:ro</code> - this tab writes to the file. A backup is taken before every save.'
                })
                : `<div class="text-center py-16" style="color:var(--muted)">
                    <i class="ph-light ph-warning-circle text-4xl block mb-3 opacity-40"></i>
                    <p>${_esc(data.error)}</p></div>`;
            return;
        }
        const acts = document.querySelector('#tab-static .fb-secondary');
        if (acts) acts.style.display = '';
        if (_staticMonaco) { _staticMonaco.dispose(); _staticMonaco = null; }
        if (_providerMonaco) { _providerMonaco.dispose(); _providerMonaco = null; }
        _staticRawContent = data.raw || '';
        _staticOriginalContent = _staticRawContent;
        _staticSectionEdits = false;
        _clearStaticPending();
        _staticPendingChanges = false;
        if (!_staticSaved) _hideStaticRestartBanner();
        const hdrAddBtn = document.getElementById('staticHdrAddBtn');
        if (hdrAddBtn) hdrAddBtn.style.display = '';
        window._staticConfigPath = data.path || '';
        _scCounts = await _scLoadCounts();
        wrapper.innerHTML = _buildStaticTabHTML();
        initStaticDirtyTracking();
        _renderStaticSections(data.parsed || {});
        _renderEpRuntimeWarning();
        _applyStaticSettingsView();
        requestAnimationFrame(_updateStaticTabArrows);
    } catch(e) {
        wrapper.innerHTML = `<div class="text-center py-16" style="color:var(--muted)">
            <i class="ph-light ph-warning-circle text-4xl block mb-3 opacity-40"></i>
            <p>${_esc(_netErrText(e, 'Failed to load static config'))}</p></div>`;
    }
}

let _staticLoadedFor = null;

let _staticSettingsChild = 'entrypoints';

function _staticInSettings() {
    return document.documentElement.classList.contains('tm-static-in-settings');
}

function switchStaticSettingsSection(key) {
    _staticSettingsChild = key;
    _staticActiveSection = key;
    _applyStaticSettingsView();
    const panel = document.getElementById('mpanel-static');
    if (panel) panel.scrollTop = 0;
}

function _applyStaticSettingsView() {
    const q = (document.getElementById('staticSearch')?.value || '').trim();
    if (q) return;
    const inSettings = _staticInSettings();
    const key = _staticSettingsChild;
    document.querySelectorAll('#staticSettingsContent .sc-grp').forEach(g => {
        g.style.display = inSettings ? 'none' : '';
    });
    document.querySelectorAll('#staticSettingsContent [data-sc-sec]').forEach(el => {
        const on = !inSettings || el.dataset.scSec === key;
        el.style.display = on ? '' : 'none';
        if (el.classList.contains('sc-fold')) {
            el.classList.toggle('open',
                (inSettings && el.dataset.scSec === key) || _scFoldOpen(el.dataset.scSec));
        }
    });
}

function _scMarkSectionDirty(el) {
    const sec = el.closest ? el.closest('.sc-sec, [id^="staticPanel-"]') : null;
    const key = sec ? (sec.dataset.scSec || (sec.id || '').replace('staticPanel-', '')) : null;
    if (!key) return;
    const save = document.querySelector(`.sc-save[data-sc-save="${key}"]`);
    if (save) save.style.display = '';
}

function _scResetSaves() {
    document.querySelectorAll('.sc-save').forEach(el => { el.style.display = 'none'; });
}

function initStaticDirtyTracking() {
    const root = document.getElementById('staticSettingsContent');
    if (!root || root.dataset.dirtyBound) return;
    root.dataset.dirtyBound = '1';
    const mark = e => {
        if (e.target.closest('.sc-save')) return;
        _scMarkSectionDirty(e.target);
    };
    root.addEventListener('input', mark);
    root.addEventListener('change', mark);
    root.addEventListener('click', e => {
        if (e.target.closest('.tab-toggle-row')) mark(e);
    });
}

function rerenderStaticBody() {
    const wrapper = document.getElementById('staticSettingsContent');
    if (!wrapper || _staticLoadedFor === null || _activeAgent) return;
    wrapper.innerHTML = _buildStaticTabHTML();
    initStaticDirtyTracking();
    _renderStaticSections(_staticParsedData);
    _renderEpRuntimeWarning();
    _renderStaticStateBar();
    filterStatic();
    _applyStaticSettingsView();
}

function _filterStaticModern(q) {
    let shown = 0;
    document.querySelectorAll('#staticSettingsContent .sc-sec').forEach(sec => {
        const label = (sec.querySelector('.sc-sec-label')?.textContent || '').toLowerCase();
        const rows  = sec.querySelectorAll('.sig-ep-row');
        const labelHit = !!q && label.includes(q);
        let hits = 0;
        rows.forEach(row => {
            const match = !q || labelHit || row.textContent.toLowerCase().includes(q);
            row.style.display = match ? '' : 'none';
            if (match) hits++;
        });
        const keep = !q || hits > 0 || labelHit;
        sec.style.display = keep ? '' : 'none';
        if (q && keep) shown += hits || 1;
    });
    document.querySelectorAll('#staticSettingsContent .sc-fold').forEach(fold => {
        const key = fold.dataset.scSec || '';
        const keep = !q || fold.textContent.toLowerCase().includes(q);
        fold.style.display = keep ? '' : 'none';
        if (q) {
            if (keep) { fold.classList.add('open'); shown++; }
        } else {
            fold.classList.toggle('open', _scFoldOpen(key));
        }
    });
    document.querySelectorAll('#staticSettingsContent .sc-grp').forEach(grp => {
        let el = grp.nextElementSibling;
        let any = false;
        while (el && !el.classList.contains('sc-grp')) {
            if ((el.classList.contains('sc-sec') || el.classList.contains('sc-fold'))
                && el.style.display !== 'none') { any = true; break; }
            el = el.nextElementSibling;
        }
        grp.style.display = any ? '' : 'none';
    });
    const verdict = document.getElementById('staticVerdict');
    if (verdict) verdict.style.display = q ? 'none' : '';
    if (!q) _applyStaticSettingsView();
    return shown;
}

function filterStatic() {
    const q = (document.getElementById('staticSearch')?.value || '').trim().toLowerCase();
    const shown = _filterStaticModern(q);
    const empty = document.getElementById('staticNoMatch');
    if (empty) empty.style.display = (q && shown === 0) ? '' : 'none';
}

function _applyStaticWarnState() {
    const warn = document.getElementById('staticDangerWarn');
    if (!warn) return;
    let hidden = false;
    try { hidden = localStorage.getItem('staticWarnHidden') === '1'; } catch (e) {}
    warn.style.display = hidden ? 'none' : '';
}

function openStaticTab() {
    _applyStaticWarnState();
    const warn = document.getElementById('staticDangerWarn');
    const server = _activeAgent ? _activeAgent.id : 'host';
    if (_staticLoadedFor !== server) {
        _staticLoadedFor = server;
        _loadStaticFromDisk();
    } else {
        _renderStaticStateBar();
        requestAnimationFrame(_updateStaticTabArrows);
    }
    const tip = document.getElementById('staticTrustedIpsWrap');
    if (tip) tip.style.display = '';
    _applyStaticSettingsView();
}

async function refreshStaticTab() {
    if (_staticPendingChanges) {
        if (!await _confirm('You have unsaved changes. Discard and reload?', 'Unsaved Changes', 'Discard')) return;
    }
    await _loadStaticFromDisk();
}

let _tipData = null;

function _tipBaseRaw() {
    return _staticMonaco ? _staticMonaco.getValue() : _staticRawContent;
}

function _tipInvalidatePreview() {
    if (_tipData) _tipData.preview = null;
    const pv = document.getElementById('tipPreviewBox'); if (pv) pv.innerHTML = '';
    const applyBtn = document.getElementById('tipApplyBtn'); if (applyBtn) applyBtn.disabled = true;
}

function openTrustedIpsHelper() {
    const modal = document.getElementById('trustedIpsModal');
    if (!modal) return;
    _tipData = null;
    document.getElementById('tipEntrypoint').innerHTML = '<option value="">Loading...</option>';
    document.getElementById('tipCurrent').innerHTML = '';
    document.getElementById('tipPreviewBox').innerHTML = '';
    document.getElementById('tipCustom').value = '';
    document.getElementById('tipSrcCloudflare').checked = true;
    document.getElementById('tipSrcPrivate').checked = false;
    document.getElementById('tipApplyBtn').disabled = true;
    modal.classList.add('open');
    document.getElementById('trustedIpsBackdrop').classList.add('open');
    if (!setDetailDockOpen(true)) document.body.style.overflow = 'hidden';
    _tipInspect();
}

function closeTrustedIpsModal() {
    setDetailDockOpen(false);
    document.getElementById('trustedIpsModal').classList.remove('open');
    document.getElementById('trustedIpsBackdrop').classList.remove('open');
    document.body.style.overflow = '';
}

async function _tipInspect() {
    try {
        const res = await fetch('/api/static/trusted-ips/preview', { method: 'POST', headers: { 'Content-Type': 'application/json', ..._csrfHeaders() }, body: JSON.stringify({ current_raw: _tipBaseRaw() }) });
        if (!res.ok) { showToast(await _errText(res, 'Failed to read static config'), 'error'); closeTrustedIpsModal(); return; }
        const d = await res.json();
        if (d.error) { showToast(d.error, 'error'); closeTrustedIpsModal(); return; }
        _tipData = d;
        const sel = document.getElementById('tipEntrypoint');
        if (!d.entrypoints.length) {
            sel.innerHTML = '<option value="">No entrypoints found</option>';
        } else {
            sel.innerHTML = d.entrypoints.map(e => `<option value="${_esc(e.name)}">${_esc(e.name)}${e.address ? ' (' + _esc(e.address) + ')' : ''}</option>`).join('');
        }
        const cf = document.getElementById('tipCfLabel');
        if (cf) cf.textContent = `Cloudflare edge ranges (${(d.cloudflare_ranges || []).length}, captured ${d.cloudflare_captured})`;
        _tipRenderCurrent();
    } catch (e) { showToast(_netErrText(e, 'Failed to read static config'), 'error'); closeTrustedIpsModal(); }
}

function _tipRenderCurrent() {
    if (_tipData) _tipData.preview = null;
    const applyBtn = document.getElementById('tipApplyBtn');
    if (applyBtn) applyBtn.disabled = true;
    const pv = document.getElementById('tipPreviewBox');
    if (pv) pv.innerHTML = '';
    const sel = document.getElementById('tipEntrypoint');
    const name = sel ? sel.value : '';
    const ep = (_tipData && _tipData.entrypoints || []).find(e => e.name === name);
    const box = document.getElementById('tipCurrent');
    if (!box) return;
    const cur = (ep && ep.trusted_ips) || [];
    if (!cur.length) {
        box.innerHTML = `<span class="text-xs" style="color:var(--muted)">No <code class="font-mono">trustedIPs</code> on this entrypoint yet.</span>`;
    } else {
        box.innerHTML = `<div class="text-xs mb-1" style="color:var(--muted)">Current <code class="font-mono">trustedIPs</code> (${cur.length}):</div><div class="flex flex-wrap gap-1">` + cur.map(c => `<span class="text-xs font-mono px-1.5 py-0.5 rounded" style="background:var(--input-bg);color:var(--text)">${_esc(c)}</span>`).join('') + `</div>`;
    }
}

async function tipPreview() {
    const sel = document.getElementById('tipEntrypoint');
    const entrypoint = sel ? sel.value : '';
    if (!entrypoint) { showToast('Pick an entrypoint', 'error'); return; }
    const cloudflare = document.getElementById('tipSrcCloudflare').checked;
    const priv = document.getElementById('tipSrcPrivate').checked;
    const custom = document.getElementById('tipCustom').value;
    if (!cloudflare && !priv && !custom.trim()) { showToast('Select at least one source', 'error'); return; }
    try {
        const res = await fetch('/api/static/trusted-ips/preview', { method: 'POST', headers: { 'Content-Type': 'application/json', ..._csrfHeaders() }, body: JSON.stringify({ current_raw: _tipBaseRaw(), entrypoint, cloudflare, private: priv, custom_cidrs: custom }) });
        if (!res.ok) { showToast(await _errText(res, 'Preview failed'), 'error'); return; }
        const d = await res.json();
        if (d.error) { showToast(d.error, 'error'); return; }
        if (_tipData) _tipData.preview = d;
        _tipRenderPreview(d);
    } catch (e) { showToast(_netErrText(e, 'Preview failed'), 'error'); }
}

function _tipRenderPreview(d) {
    const box = document.getElementById('tipPreviewBox');
    if (!box) return;
    const added = d.added || [], invalid = d.invalid || [], existing = d.existing || [];
    let html = '';
    if (!added.length && !invalid.length) {
        html += `<div class="text-xs px-3 py-2 rounded" style="background:rgba(234,179,8,0.1);color:#ca8a04">Nothing new to add - every selected range is already trusted on <span class="font-mono">${_esc(d.entrypoint)}</span>.</div>`;
    }
    if (added.length) {
        html += `<div class="text-xs mb-1" style="color:var(--green)"><i class="ph-bold ph-plus-circle"></i> Adding ${added.length} range${added.length > 1 ? 's' : ''}:</div><div class="flex flex-wrap gap-1 mb-2">` + added.map(c => `<span class="text-xs font-mono px-1.5 py-0.5 rounded" style="background:rgba(63,185,80,0.12);color:var(--green)">${_esc(c)}</span>`).join('') + `</div>`;
    }
    if (invalid.length) {
        html += `<div class="text-xs mb-1" style="color:var(--red)"><i class="ph-bold ph-warning"></i> Skipped ${invalid.length} invalid entr${invalid.length > 1 ? 'ies' : 'y'}:</div><div class="flex flex-wrap gap-1 mb-2">` + invalid.map(c => `<span class="text-xs font-mono px-1.5 py-0.5 rounded" style="background:rgba(239,68,68,0.12);color:var(--red)">${_esc(c)}</span>`).join('') + `</div>`;
    }
    html += `<div class="text-xs" style="color:var(--muted)">Result: <span style="color:var(--text);font-weight:600">${d.final.length}</span> trusted range${d.final.length !== 1 ? 's' : ''} on <span class="font-mono">${_esc(d.entrypoint)}</span> (was ${existing.length}).</div>`;
    box.innerHTML = html;
    document.getElementById('tipApplyBtn').disabled = !added.length;
}

async function tipApply() {
    const d = _tipData && _tipData.preview;
    if (!d || !d.raw) return;
    _staticRawContent = d.raw;
    if (_staticMonaco) _staticMonaco.setValue(d.raw);
    closeTrustedIpsModal();
    await saveStaticConfig();
}

const _origSetTheme = setTheme;
setTheme = function(theme) {
    _origSetTheme(theme);
    if (_staticMonaco || _mwMonacoEditor || _pluginStaticMonaco || _pluginMwMonaco || _providerMonaco) {
        const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
        _ensureMonacoThemes().then(() => monaco.editor.setTheme(_monacoThemeName(isDark)));
    }
};

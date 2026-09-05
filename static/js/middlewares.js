function setMwProtocol(proto) {
    const hid = document.getElementById('mwProtocol');
    if (hid) hid.value = proto;
    const hbtn = document.getElementById('mwProtoHTTP');
    const tbtn = document.getElementById('mwProtoTCP');
    if (hbtn) hbtn.classList.toggle('active-http', proto === 'http');
    if (tbtn) tbtn.classList.toggle('active-http', proto === 'tcp');
    const tplWrap = document.getElementById('mwTemplateWrap');
    if (tplWrap) tplWrap.style.display = proto === 'tcp' ? 'none' : '';
    const wizBtn = document.getElementById('mwModeWizBtn');
    if (wizBtn) wizBtn.style.display = proto === 'tcp' ? 'none' : '';
    if (proto === 'tcp') {
        const tplSel = document.getElementById('mwTemplate');
        if (tplSel) tplSel.value = '';
        setMwMode('yaml');
        _showMwWizard('');
    }
}

function openMwModal() {
    closeOtherPanels('mwModal');
    const nameEl = document.getElementById('middlewareName');
    const contentEl = document.getElementById('middlewareContent');
    const editEl = document.getElementById('isMwEdit');
    const titleEl = document.getElementById('mwModalTitle');
    const modal = document.getElementById('mwModal');
    if (!modal) { console.error('mwModal not found'); return; }
    if (editEl) editEl.value = 'false';
    if (nameEl) nameEl.value = '';
    if (contentEl) contentEl.value = '';
    if (titleEl) titleEl.innerText = 'Add Middleware';
    const mwCfSel = document.getElementById('mwConfigFileSelect');
    const mwCfHid = document.getElementById('mwConfigFile');
    const newMwInput = document.getElementById('newMwFileName');
    if (newMwInput) { newMwInput.style.display = 'none'; newMwInput.value = ''; }
    _populateConfigFileSelect('mw').then(() => { _openMwPanel(); });
    const mwTplSel = document.getElementById('mwTemplate');
    if (mwTplSel) mwTplSel.value = '';
    setMwProtocol('http');
    const origProtoEl = document.getElementById('originalMwProtocol');
    if (origProtoEl) origProtoEl.value = '';
    setMwMode('yaml');
    _showMwWizard('');
    _initMwMonaco('');
    _loadCustomMwTemplates();
}

function _openMwPanel() {
    document.getElementById('mwModal').classList.add('open');
    document.getElementById('mwBackdrop').classList.add('open');
    if (!setDetailDockOpen(true)) document.body.style.overflow = 'hidden';
}

function closeMwModal() {
    setDetailDockOpen(false);
    document.getElementById('mwModal').classList.remove('open');
    document.getElementById('mwBackdrop').classList.remove('open');
    document.body.style.overflow = '';
}

function togglePwVis(inputId, btn) {
    const el = document.getElementById(inputId);
    if (!el) return;
    const show = el.type === 'password';
    el.type = show ? 'text' : 'password';
    btn.innerHTML = show ? '<i class="ph-bold ph-eye-slash text-sm"></i>' : '<i class="ph-bold ph-eye text-sm"></i>';
}

async function generateDigestAuth() {
    const user  = (document.getElementById('wizDaGenUser')?.value || '').trim();
    const realm = (document.getElementById('wizDaGenRealm')?.value || '').trim();
    const pass  = (document.getElementById('wizDaGenPass')?.value || '');
    if (!user || !realm || !pass) { showToast('Enter a username, realm and password', 'error'); return; }
    const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
    try {
        const res  = await fetch('/api/tools/digestauth', { method:'POST', headers:{'Content-Type':'application/json','X-CSRF-Token': csrf}, body: JSON.stringify({username: user, realm, password: pass}) });
        if (!res.ok) { showToast(await _errText(res, 'Error generating hash'), 'error'); return; }
        const json = await res.json();
        if (!json.ok) { showToast(json.error || json.message || 'Error generating hash', 'error'); return; }
        const ta = document.getElementById('wizDaUsers');
        if (ta) ta.value = (ta.value.trim() ? ta.value.trim() + '\n' : '') + json.hash;
        document.getElementById('wizDaGenUser').value = '';
        document.getElementById('wizDaGenRealm').value = '';
        document.getElementById('wizDaGenPass').value = '';
    } catch(e) { showToast(_netErrText(e, 'Error generating hash'), 'error'); }
}

async function generateHtpasswd() {
    const user = (document.getElementById('wizBaGenUser')?.value || '').trim();
    const pass = (document.getElementById('wizBaGenPass')?.value || '');
    if (!user || !pass) { showToast('Enter a username and password', 'error'); return; }
    const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
    try {
        const res  = await fetch('/api/tools/htpasswd', { method:'POST', headers:{'Content-Type':'application/json','X-CSRF-Token': csrf}, body: JSON.stringify({username: user, password: pass}) });
        if (!res.ok) { showToast(await _errText(res, 'Error generating hash'), 'error'); return; }
        const json = await res.json();
        if (!json.ok) { showToast(json.error || json.message || 'Error generating hash', 'error'); return; }
        const ta = document.getElementById('wizBaUsers');
        if (ta) ta.value = (ta.value.trim() ? ta.value.trim() + '\n' : '') + json.hash;
        document.getElementById('wizBaGenUser').value = '';
        document.getElementById('wizBaGenPass').value = '';
    } catch(e) { showToast(_netErrText(e, 'Error generating hash'), 'error'); }
}

function setMwMode(mode) {
    document.getElementById('mwCurrentMode').value = mode;
    const wizBtn  = document.getElementById('mwModeWizBtn');
    const yamlBtn = document.getElementById('mwModeYamlBtn');
    const wizSec  = document.getElementById('mwWizardSection');
    const edSec   = document.getElementById('mwEditorSection');
    if (mode === 'wizard') {
        wizBtn.classList.add('active-http');
        yamlBtn.classList.remove('active-http');
        if (wizSec) wizSec.style.display = '';
        if (edSec)  edSec.style.display  = 'none';
    } else {
        yamlBtn.classList.add('active-http');
        wizBtn.classList.remove('active-http');
        if (wizSec) wizSec.style.display = 'none';
        if (edSec)  edSec.style.display  = '';
        const tpl = document.getElementById('mwTemplate')?.value;
        if (tpl && _wizardTemplates.has(tpl)) {
            buildYamlFromWizard();
            const yaml = document.getElementById('middlewareContent')?.value || '';
            if (_mwMonacoEditor) {
                _mwMonacoEditor.setValue(yaml);
                setTimeout(() => _mwMonacoEditor.layout(), 50);
            } else {
                _initMwMonaco(yaml);
            }
        } else if (_mwMonacoEditor) {
            setTimeout(() => _mwMonacoEditor.layout(), 50);
        }
    }
}

const _wizardTemplates = new Set(['basicAuth','digestAuth','forwardAuth','forwardAuthAuthentik','forwardAuthAuthelia','forwardAuthGatekeeper','oidcAuth','ipAllowList','ipAllowListPrivate','rateLimit','secureHeaders','corsHeaders','encodedCharacters','redirectScheme','redirectRegex','stripPrefix','addPrefix','replacePath','compress','retry','circuitBreaker','buffering','chain','inFlightReq','stripPrefixRegex','replacePathRegex','errors','contentType','grpcWeb','passTLSClientCert']);

const _wizKeyMap = {
    forwardAuthAuthentik: 'forwardAuth', forwardAuthAuthelia: 'forwardAuth',
    ipAllowListPrivate: 'ipAllowList',
};

function _wizIpStrategySync() {
    const mode = document.getElementById('wizIpStrategy')?.value || 'direct';
    const depthRow = document.getElementById('wizIpDepthRow');
    const exRow    = document.getElementById('wizIpExcludedRow');
    if (depthRow) depthRow.style.display = mode === 'depth' ? '' : 'none';
    if (exRow)    exRow.style.display    = mode === 'excluded' ? '' : 'none';
}

async function _populateMwErrorService() {
    const sel = document.getElementById('wizErrService');
    if (!sel) return;
    sel.innerHTML = '<option value="">Loading services...</option>';
    let svcs = [];
    try { svcs = (await _ensureServicesList()).http || []; } catch (e) { svcs = []; }
    sel.innerHTML = svcs.length
        ? svcs.map(n => `<option value="${_esc(n)}">${_esc(n)}</option>`).join('')
        : '<option value="">No HTTP services defined yet</option>';
}

function _showMwWizard(tpl) {
    document.querySelectorAll('.mw-wiz-form').forEach(el => el.style.display = 'none');
    const none = document.getElementById('mwWiz-none');
    if (!tpl || !_wizardTemplates.has(tpl)) { if (none) none.style.display = ''; return; }
    const key = _wizKeyMap[tpl] || tpl;
    const sec = document.getElementById('mwWiz-' + key);
    if (sec) {
        sec.style.display = '';
        sec.querySelectorAll('input:not([type=checkbox]):not([type=radio]), textarea').forEach(el => { el.value = ''; });
        sec.querySelectorAll('input[type=checkbox]').forEach(el => { el.checked = el.defaultChecked; });
    }
    if (key === 'errors') _populateMwErrorService();
    if (key === 'passTLSClientCert') {
        const info = document.getElementById('wizPtcInfoFields');
        if (info) info.style.display = 'none';
    }
    if (key === 'ipAllowList') {
        const strat = document.getElementById('wizIpStrategy');
        if (strat) strat.value = 'direct';
        const depth = document.getElementById('wizIpDepth');
        if (depth) depth.value = '1';
        _wizIpStrategySync();
    }
    if (tpl === 'forwardAuthAuthentik') {
        const el = document.getElementById('wizFaAddress'); if (el) el.value = 'http://authentik-server:9000/outpost.goauthentik.io/auth/traefik';
        const hd = document.getElementById('wizFaHeaders'); if (hd) hd.value = 'X-authentik-username\nX-authentik-groups\nX-authentik-email\nX-authentik-name\nX-authentik-uid';
    } else if (tpl === 'forwardAuthAuthelia') {
        const el = document.getElementById('wizFaAddress'); if (el) el.value = 'http://authelia:9091/api/authz/forward-auth';
        const hd = document.getElementById('wizFaHeaders'); if (hd) hd.value = 'Remote-User\nRemote-Groups\nRemote-Name\nRemote-Email';
    } else if (tpl === 'forwardAuthGatekeeper') {
        const hd = document.getElementById('wizGkHeaders'); if (hd) hd.value = 'X-Auth-User\nX-Auth-Email\nX-Auth-Groups';
        const ga = document.getElementById('wizGkAuthorization'); if (ga) ga.checked = false;
    } else if (tpl === 'oidcAuth') {
        const sc = document.getElementById('wizOidcScopes'); if (sc) sc.value = 'openid\nprofile\nemail';
        const hd = document.getElementById('wizOidcHeaders'); if (hd) hd.value = 'X-Forwarded-User: preferred_username\nX-Forwarded-Email: email\nX-Forwarded-Name: name';
        const mx = document.getElementById('wizOidcSessionMaxAge'); if (mx) mx.value = '86400';
    } else if (tpl === 'ipAllowListPrivate') {
        const el = document.getElementById('wizIpCidrs'); if (el) el.value = '10.0.0.0/8\n172.16.0.0/12\n192.168.0.0/16\n127.0.0.1/32';
    }
}

function buildYamlFromWizard() {
    const tpl = document.getElementById('mwTemplate')?.value;
    if (!tpl || !_wizardTemplates.has(tpl)) return;
    let yaml = '';
    const key = _wizKeyMap[tpl] || tpl;

    const _q = (v) => JSON.stringify(String(v ?? ''));
    const _lines = (id) => (document.getElementById(id)?.value || '').trim().split('\n').map(l => l.trim()).filter(Boolean);
    const _val   = (id, def='') => (document.getElementById(id)?.value || def).trim();
    const _chk   = (id, def=false) => document.getElementById(id)?.checked ?? def;

    if (key === 'basicAuth') {
        const users = _lines('wizBaUsers');
        const realm = _val('wizBaRealm');
        yaml = 'basicAuth:\n  users:\n' + users.map(l => '    - ' + _q(l) + '').join('\n');
        if (realm) yaml += '\n  realm: ' + _q(realm) + '';

    } else if (key === 'digestAuth') {
        const users = _lines('wizDaUsers');
        yaml = 'digestAuth:\n  users:\n' + users.map(l => '    - ' + _q(l) + '').join('\n');

    } else if (key === 'forwardAuth') {
        const addr  = _val('wizFaAddress');
        const trust = _chk('wizFaTrust', true);
        const hdrs  = _lines('wizFaHeaders');
        const maxBody = _val('wizFaMaxBody');
        yaml = 'forwardAuth:\n  address: ' + _q(addr) + '\n  trustForwardHeader: ' + trust;
        if (hdrs.length) yaml += '\n  authResponseHeaders:\n' + hdrs.map(h => '    - ' + _q(h) + '').join('\n');
        if (maxBody && /^\d+$/.test(maxBody)) yaml += '\n  maxResponseBodySize: ' + maxBody;

    } else if (key === 'forwardAuthGatekeeper') {
        const url    = _val('wizGkUrl').replace(/\/+$/, '');
        const policy = _val('wizGkPolicy');
        const addr   = url ? url + '/auth/verify' + (policy ? '?policy=' + policy : '') : '';
        const trust  = _chk('wizGkTrust', false);
        const auth   = _chk('wizGkAuthorization', false);
        const hdrs   = _lines('wizGkHeaders');
        const allHdrs = auth ? ['Authorization', ...hdrs.filter(h => h !== 'Authorization')] : hdrs;
        const gkMaxBody = _val('wizGkMaxBody');
        yaml = 'forwardAuth:\n  address: ' + _q(addr) + '\n  trustForwardHeader: ' + trust;
        if (allHdrs.length) yaml += '\n  authResponseHeaders:\n' + allHdrs.map(h => '    - ' + _q(h) + '').join('\n');
        if (gkMaxBody && /^\d+$/.test(gkMaxBody)) yaml += '\n  maxResponseBodySize: ' + gkMaxBody;

    } else if (key === 'oidcAuth') {
        const providerUrl    = _val('wizOidcProviderUrl');
        const clientId       = _val('wizOidcClientId');
        const clientSecret   = _val('wizOidcClientSecret');
        const secret         = _val('wizOidcSecret');
        const scopes         = _lines('wizOidcScopes');
        const maxAge         = parseInt(_val('wizOidcSessionMaxAge','86400')) || 86400;
        const headerLines    = _lines('wizOidcHeaders');
        const bypassLines    = _lines('wizOidcBypass');
        const headers = headerLines.map(l => {
            const idx = l.indexOf(':');
            return idx > -1 ? { Name: l.slice(0, idx).trim(), Value: '{' + '{`' + '{' + '{ .claims.' + l.slice(idx+1).trim() + ' }' + '}`' + '}' + '}' } : null;
        }).filter(Boolean);
        yaml = 'plugin:\n  traefik-oidc-auth:';
        if (secret) yaml += '\n    Secret: ' + _q(secret) + '';
        yaml += '\n    Provider:';
        if (providerUrl) yaml += '\n      Url: ' + _q(providerUrl) + '';
        if (clientId)    yaml += '\n      ClientId: ' + _q(clientId) + '';
        if (clientSecret) yaml += '\n      ClientSecret: ' + _q(clientSecret) + '';
        if (scopes.length) yaml += '\n    Scopes:\n' + scopes.map(s => '      - ' + s).join('\n');
        yaml += '\n    SessionCookie:\n      MaxAge: ' + maxAge;
        if (headers.length) yaml += '\n    Headers:\n' + headers.map(h => '      - Name: ' + _q(h.Name) + '\n        Value: ' + _q(h.Value) + '').join('\n');
        if (bypassLines.length) yaml += '\n    BypassAuthenticationRule:\n' + bypassLines.map(r => '      - ' + _q(r) + '').join('\n');

    } else if (key === 'rateLimit') {
        yaml = 'rateLimit:\n  average: ' + _val('wizRlAvg','100') + '\n  burst: ' + _val('wizRlBurst','50') + '\n  period: ' + _val('wizRlPeriod','1s');

    } else if (key === 'ipAllowList') {
        const cidrs = _lines('wizIpCidrs');
        yaml = 'ipAllowList:\n  sourceRange:\n' + cidrs.map(c => '    - ' + _q(c) + '').join('\n');
        const strat = _val('wizIpStrategy', 'direct');
        if (strat === 'depth') {
            const depth = _val('wizIpDepth', '1');
            yaml += '\n  ipStrategy:\n    depth: ' + (/^\d+$/.test(depth) && +depth > 0 ? depth : '1');
        } else if (strat === 'excluded') {
            const excluded = _lines('wizIpExcluded');
            if (excluded.length) yaml += '\n  ipStrategy:\n    excludedIPs:\n' + excluded.map(c => '      - ' + _q(c) + '').join('\n');
        }

    } else if (key === 'secureHeaders') {
        const lines = ['headers:'];
        if (_chk('wizShSsl'))     lines.push('  sslRedirect: true');
        if (_chk('wizShHsts')) {
            lines.push('  forceSTSHeader: true');
            lines.push('  stsSeconds: ' + _val('wizShHstsAge','315360000'));
            if (_chk('wizShSub'))     lines.push('  stsIncludeSubdomains: true');
            if (_chk('wizShPreload')) lines.push('  stsPreload: true');
        }
        if (_chk('wizShNosniff'))  lines.push('  contentTypeNosniff: true');
        if (_chk('wizShXss'))      lines.push('  browserXssFilter: true');
        if (_chk('wizShFrame'))    lines.push('  frameDeny: true');
        if (_chk('wizShReferrer')) lines.push('  referrerPolicy: "same-origin"');
        yaml = lines.join('\n');

    } else if (key === 'corsHeaders') {
        const methods = ['GET','POST','PUT','DELETE','PATCH','OPTIONS','HEAD']
            .filter(m => _chk('wizCors' + m.charAt(0) + m.slice(1).toLowerCase()));
        const origins = _lines('wizCorsOrigins');
        const hdrs    = _lines('wizCorsHeaders');
        const maxAge  = _val('wizCorsMaxAge','100');
        const vary    = _chk('wizCorsVary', true);
        const lines = ['headers:'];
        if (methods.length) lines.push('  accessControlAllowMethods:\n' + methods.map(m => '    - ' + m).join('\n'));
        if (hdrs.length)    lines.push('  accessControlAllowHeaders:\n' + hdrs.map(h => '    - ' + _q(h) + '').join('\n'));
        if (origins.length) lines.push('  accessControlAllowOriginList:\n' + origins.map(o => '    - ' + _q(o) + '').join('\n'));
        lines.push('  accessControlMaxAge: ' + maxAge);
        if (vary) lines.push('  addVaryHeader: true');
        yaml = lines.join('\n');

    } else if (key === 'encodedCharacters') {
        const opts = [
            ['allowEncodedSlash', 'wizEcSlash'],
            ['allowEncodedBackSlash', 'wizEcBackSlash'],
            ['allowEncodedSemicolon', 'wizEcSemicolon'],
            ['allowEncodedPercent', 'wizEcPercent'],
            ['allowEncodedQuestionMark', 'wizEcQuestion'],
            ['allowEncodedHash', 'wizEcHash'],
        ];
        const enabled = opts.filter(([k, id]) => _chk(id, false)).map(([k]) => k);
        yaml = enabled.length
            ? 'encodedCharacters:\n' + enabled.map(k => '  ' + k + ': true').join('\n')
            : 'encodedCharacters: {}';

    } else if (key === 'redirectScheme') {
        yaml = 'redirectScheme:\n  scheme: ' + _val('wizRsScheme','https') + '\n  permanent: ' + _chk('wizRsPermanent',true);

    } else if (key === 'redirectRegex') {
        yaml = 'redirectRegex:\n  regex: ' + _q(_val('wizRrRegex')) + '\n  replacement: ' + _q(_val('wizRrReplacement')) + '\n  permanent: ' + _chk('wizRrPermanent',true);

    } else if (key === 'stripPrefixRegex') {
        const rx = _lines('wizSprRegex');
        yaml = 'stripPrefixRegex:\n  regex:\n' + rx.map(r => '    - ' + _q(r)).join('\n');
    } else if (key === 'replacePathRegex') {
        yaml = 'replacePathRegex:\n  regex: ' + _q(_val('wizRprRegex'))
             + '\n  replacement: ' + _q(_val('wizRprReplacement'));
    } else if (key === 'errors') {
        const st = _lines('wizErrStatus');
        const q = _val('wizErrQuery');
        yaml = 'errors:\n  status:\n' + st.map(x => '    - ' + _q(x) + '\n').join('')
             + '  service: ' + _q(_val('wizErrService'))
             + (q ? '\n  query: ' + _q(q) : '');
    } else if (key === 'contentType') {
        yaml = 'contentType:\n  autoDetect: ' + (_chk('wizCtAutoDetect') ? 'true' : 'false');
    } else if (key === 'grpcWeb') {
        const og = _lines('wizGrpcOrigins');
        yaml = 'grpcWeb:\n  allowOrigins:\n' + og.map(o => '    - ' + _q(o)).join('\n');
    } else if (key === 'passTLSClientCert') {
        const info = _chk('wizPtcInfo');
        yaml = 'passTLSClientCert:\n  pem: ' + (_chk('wizPtcPem', true) ? 'true' : 'false');
        if (info) {
            const sub = _chk('wizPtcSubjectCN', true);
            const iss = _chk('wizPtcIssuerCN');
            yaml += '\n  info:';
            if (_chk('wizPtcSerial')) yaml += '\n    serialNumber: true';
            if (_chk('wizPtcNotAfter')) yaml += '\n    notAfter: true';
            if (sub) yaml += '\n    subject:\n      commonName: true';
            if (iss) yaml += '\n    issuer:\n      commonName: true';
        }
    } else if (key === 'stripPrefix') {
        const prefixes = _lines('wizSpPrefixes');
        yaml = 'stripPrefix:\n  prefixes:\n' + prefixes.map(p => '    - ' + _q(p) + '').join('\n');

    } else if (key === 'addPrefix') {
        yaml = 'addPrefix:\n  prefix: ' + _q(_val('wizApPrefix')) + '';

    } else if (key === 'replacePath') {
        yaml = 'replacePath:\n  path: ' + _q(_val('wizRpPath')) + '';

    } else if (key === 'compress') {
        yaml = 'compress:\n  minResponseBodyBytes: ' + _val('wizCmpMin','1200');

    } else if (key === 'retry') {
        yaml = 'retry:\n  attempts: ' + _val('wizRtAttempts','4') + '\n  initialInterval: ' + _val('wizRtInterval','100ms');

    } else if (key === 'circuitBreaker') {
        yaml = 'circuitBreaker:\n  expression: ' + _q(_val('wizCbExpr')) + '';

    } else if (key === 'buffering') {
        const retryExpr = _val('wizBufRetry');
        yaml = 'buffering:\n  maxRequestBodyBytes: ' + _val('wizBufReq','10485760') + '\n  maxResponseBodyBytes: ' + _val('wizBufRes','10485760');
        if (retryExpr) yaml += '\n  retryExpression: ' + _q(retryExpr) + '';

    } else if (key === 'chain') {
        const mws = _lines('wizChMiddlewares');
        yaml = 'chain:\n  middlewares:\n' + mws.map(m => '    - ' + m).join('\n');

    } else if (key === 'inFlightReq') {
        yaml = 'inFlightReq:\n  amount: ' + _val('wizIfAmount','10');
    }

    if (yaml) {
        document.getElementById('middlewareContent').value = yaml;
        if (_mwMonacoEditor) _mwMonacoEditor.setValue(yaml);
    }
}

function onMwConfigFileChange(sel) {
    const newInput = document.getElementById('newMwFileName');
    const cfHid    = document.getElementById('mwConfigFile');
    if (sel.value === '__new__') {
        if (newInput) newInput.style.display = '';
        const mwName = (document.getElementById('middlewareName')?.value || '').trim().toLowerCase().replace(/[^a-z0-9-]/g, '-');
        if (newInput && !newInput.value && mwName) newInput.value = `middlewares-${mwName}.yml`;
        if (cfHid) cfHid.value = newInput?.value || '';
    } else {
        if (newInput) { newInput.style.display = 'none'; newInput.value = ''; }
        if (cfHid) cfHid.value = sel.value;
    }
}

async function saveMwAjax(event) {
    event.preventDefault();
    const _mwCfWrap = document.getElementById('mwConfigFileSelectWrap');
    const _mwCfSel  = document.getElementById('mwConfigFileSelect');
    if (_mwCfWrap && _mwCfWrap.style.display !== 'none' && _mwCfSel && !_mwCfSel.value
            && !document.getElementById('mwConfigFile').value) {
        showToast('Select a config file for this middleware', 'error');
        return;
    }
    const mwMode = document.getElementById('mwCurrentMode')?.value;
    if (mwMode === 'wizard') {
        const tpl = document.getElementById('mwTemplate')?.value || '';
        if (tpl === 'basicAuth' || tpl === 'digestAuth') {
            const usersEl = document.getElementById(tpl === 'basicAuth' ? 'wizBaUsers' : 'wizDaUsers');
            const users = (usersEl?.value || '').trim().split('\n').map(l => l.trim()).filter(Boolean);
            if (!users.length) { showToast('Add at least one user before saving', 'error'); return; }
        }
        if (['forwardAuth','forwardAuthAuthentik','forwardAuthAuthelia'].includes(tpl)) {
            const addr = (document.getElementById('wizFaAddress')?.value || '').trim();
            if (!addr) { showToast('Forward auth address is required', 'error'); return; }
        }
        if (tpl === 'forwardAuthGatekeeper') {
            const url = (document.getElementById('wizGkUrl')?.value || '').trim();
            if (!url) { showToast('Gatekeeper URL is required', 'error'); return; }
        }
        buildYamlFromWizard();
    } else {
        const content = _mwMonacoEditor ? _mwMonacoEditor.getValue() : (document.getElementById('middlewareContent')?.value || '');
        if (_mwMonacoEditor) document.getElementById('middlewareContent').value = content;
        if (!content.trim()) { showToast('Middleware content cannot be empty', 'error'); return; }
    }
    const form = event.target;
    const mwFn = document.getElementById('newMwFileName');
    if (mwFn && mwFn.style.display !== 'none' && mwFn.value && !/\.ya?ml$/.test(mwFn.value)) {
        mwFn.value += '.yml';
        document.getElementById('mwConfigFile').value = mwFn.value;
    }
    const btn = form.querySelector('button[type=submit]');
    btn.disabled = true;
    try {
        const fd = new FormData(form);
        if (_activeAgent) fd.append('agent_id', _activeAgent.id);
        const res = await fetch(form.action, { method:'POST', headers:{'X-Requested-With':'fetch'}, body: fd });
        if (!res.ok) { showToast(await _errText(res, 'Error saving middleware'), 'error'); return; }
        const json = await res.json();
        showToast(json.message || json.error || 'Error saving middleware', json.ok ? 'success' : 'error');
        if (json.ok) { closeMwModal(); _cachedMiddlewares = null; refreshRoutes(); fetchNotifications(); if (typeof window.rmInvalidateData === 'function') window.rmInvalidateData(); setTimeout(fetchNotifications, 8000); }
    } catch(e) {
        showToast(_netErrText(e, 'Error saving middleware'), 'error');
    } finally {
        btn.disabled = false;
    }
}

async function deleteMw(name, configFile) {
    if (!await _confirm('Delete middleware "' + name + '"?', 'Delete Middleware', 'Delete', 'DELETE')) return;
    await _sendMwDelete(name, configFile, false);
}

async function _sendMwDelete(name, configFile, force) {
    const data = new FormData();
    data.append('csrf_token', document.querySelector('meta[name="csrf-token"]')?.content || '');
    if (configFile) data.append('configFile', configFile);
    if (_activeAgent) data.append('agent_id', _activeAgent.id);
    if (force) data.append('force', 'true');
    try {
        const res = await fetch('/delete-middleware/' + encodeURIComponent(name), { method:'POST', headers:{'X-Requested-With':'fetch'}, body: data });
        const json = await res.json().catch(() => null);
        if (res.status === 409 && json && (json.inUseBy || []).length) {
            const routes = json.inUseBy;
            const shown = routes.slice(0, 5).join(', ') + (routes.length > 5 ? ' and ' + (routes.length - 5) + ' more' : '');
            const label = routes.length === 1 ? '1 route' : routes.length + ' routes';
            if (await _confirm('"' + name + '" is still used by ' + shown + '. Remove it from ' + label + ' and delete it?',
                               'Middleware In Use', 'Remove and delete', 'DELETE')) {
                await _sendMwDelete(name, configFile, true);
            }
            return;
        }
        if (!res.ok) { showToast((json && (json.message || json.error)) || await _errText(res, 'Error deleting middleware'), 'error'); return; }
        showToast((json && (json.message || json.error)) || 'Error deleting middleware', json && json.ok ? 'success' : 'error');
        if (json && json.ok) { _cachedMiddlewares = null; refreshRoutes(); fetchNotifications(); if (typeof window.rmInvalidateData === 'function') window.rmInvalidateData(); }
    } catch(e) { showToast(_netErrText(e, 'Error deleting middleware'), 'error'); }
}

function _tmMwIcon(mw) {
    const y = (mw.yaml || '').toLowerCase();
    if (y.includes('forwardauth') || y.includes('basicauth') || y.includes('digestauth')) return 'ph-shield-check';
    if (y.includes('ratelimit'))     return 'ph-gauge';
    if (y.includes('ipallowlist') || y.includes('ipwhitelist')) return 'ph-funnel';
    if (y.includes('redirect'))      return 'ph-arrow-u-up-right';
    if (y.includes('headers'))       return 'ph-brackets-curly';
    if (y.includes('plugin'))        return 'ph-plug';
    if (y.includes('compress'))      return 'ph-file-zip';
    return 'ph-dots-three-circle';
}

function _tmMwKind(mw) {
    const m = (mw.yaml || '').match(/^\s*([A-Za-z]+)\s*:/m);
    return m ? m[1] : 'middleware';
}

function _tmMwUsage(mw) {
    const pool = window._lastRenderedApps || (typeof APP_DATA !== 'undefined' ? APP_DATA : []) || [];
    const bare = String(mw.name).split('@')[0];
    const hit = x => String(x).split('@')[0] === bare;
    return pool.filter(a => (a.middlewares || []).some(hit) || (a.entrypointMiddlewares || []).some(hit)).length;
}

function _tmMwChained(mw) {
    const bare = String(mw.name).split('@')[0];
    const esc = bare.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const re = new RegExp('(^|[\\s\\[,\'"])' + esc + '(@[\\w.-]+)?([\\s\\],\'"]|$)', 'm');
    return (_allMiddlewares || []).some(o => o.name !== mw.name && re.test(o.yaml || ''));
}

function _tmMwCard(mw, showCf) {
    const mwJson = JSON.stringify(mw).replace(/'/g, '&#39;');
    const cfArg  = `,${_jsArg(mw.configFile || '')}`;
    const typeLower = (mw.type || 'http').toLowerCase();
    const used = _tmMwUsage(mw);
    const chained = used ? false : _tmMwChained(mw);
    const usage = used ? `used by ${used} route${used > 1 ? 's' : ''}`
                       : chained ? 'used in a chain' : 'unused';
    const yaml = String(mw.yaml || '').split('\n').slice(0, 4).join('\n');
    const rail = `<span class="tm-rail tm-rail-sm" onclick="event.stopPropagation()">` +
        `<button type="button" class="tm-btn" title="Edit" data-mw='${mwJson}' onclick="event.stopPropagation();handleMwEdit(this)"><i class="ph-bold ph-pencil-simple"></i></button>` +
        `<button type="button" class="tm-btn" title="Delete" onclick="event.stopPropagation();deleteMw(${_jsArg(mw.name)}${cfArg})"><i class="ph-bold ph-trash"></i></button>` +
        '</span>';
    return `<div class="tm-card mw-card" data-mwname="${_esc(mw.name.toLowerCase())}" data-mwtype="${typeLower}" style="--tm-accent:var(--purple)" data-mw='${mwJson}' onclick="openMwDetail(this)">
        <div class="tm-head">
            <span class="tm-ic tm-ic-tile"><i class="ph-bold ${_tmMwIcon(mw)}"></i></span>
            <div class="tm-head-txt">
                <div class="tm-title">${typeLower === 'tcp' ? '<span class="tm-proto tm-proto-tcp">TCP</span>' : ''}<span class="tm-name">${_esc(mw.name)}</span></div>
                <div class="tm-sub">${_esc(_tmMwKind(mw))}</div>
            </div>${rail}
        </div>
        <div class="tm-code">${_esc(yaml)}</div>
        <div class="tm-foot"><span class="tm-meta ${used || chained ? '' : 'tm-warn'}">${usage}</span>${showCf ? _tmCf(mw.configFile) : ''}</div>
    </div>`;
}

function renderMwGrid(middlewares) {
    _allMiddlewares = middlewares;
    const grid = document.getElementById('mwGrid');
    if (!grid) return;
    const staticEmpty = document.getElementById('mwStaticEmpty');
    if (staticEmpty) staticEmpty.style.display = 'none';
    const _tmOn = _mwViewMode !== 'list';
    const _tmCfShow = _tmOn && new Set(middlewares.map(m => m.configFile).filter(Boolean)).size > 1;
    grid.innerHTML = middlewares.map(mw => {
        if (_tmOn) return _tmMwCard(mw, _tmCfShow);
        const typeLower = (mw.type || 'http').toLowerCase();
        const typeUpper = typeLower === 'tcp' ? 'TCP' : 'HTTP';
        const badgeClass = typeLower === 'tcp' ? 'badge-tcp' : 'badge-http';
        const mwJson = JSON.stringify(mw).replace(/'/g, '&#39;');
        const mwCfArg = `,${_jsArg(mw.configFile || '')}`;
        const mwCfBadge = mw.configFile ? `<span class="badge badge-muted" style="font-size:9px;white-space:nowrap">${_esc(mw.configFile)}</span>` : '';
        const dataAttrs = `data-mwname="${_esc(mw.name.toLowerCase())}" data-mwtype="${typeLower}"`;
        const actions = `<div class="flex gap-1.5"><button type="button" data-mw='${mwJson}' onclick="openMwDetail(this)" class="pill-btn pill-btn-blue" title="View details"><i class="ph-bold ph-info text-xs"></i></button><button type="button" onclick="deleteMw(${_jsArg(mw.name)}${mwCfArg})" class="pill-btn pill-btn-red" title="Delete"><i class="ph-bold ph-trash text-xs"></i></button><button type="button" data-mw='${mwJson}' onclick="handleMwEdit(this)" class="pill-btn pill-btn-blue" title="Edit"><i class="ph-bold ph-pencil-simple text-xs"></i></button></div>`;
        if (_mwViewMode === 'list') {
            return `<div class="svc-list-row mw-list-grid mw-card" ${dataAttrs}><div style="display:flex;align-items:center"><span class="d-flat d-proto d-proto-${typeLower}">${typeUpper}</span></div><div class="svc-list-col-name">${_esc(mw.name)}</div><div>${mw.configFile ? `<span class="d-flat d-off" style="white-space:nowrap">${_esc(mw.configFile)}</span>` : ''}</div>${actions}</div>`;
        }
        return `<div class="card p-4 mw-card" ${dataAttrs}><div class="flex justify-between items-start mb-3"><div><div class="flex items-center gap-1.5 mb-1.5"><span class="badge ${badgeClass} w-fit">${typeUpper}</span>${mwCfBadge}</div><h3 class="font-bold text-sm" style="color:var(--text)">${_esc(mw.name)}</h3></div>${actions}</div><div class="rounded-md p-3 overflow-x-auto" style="background:var(--input-bg);border:1px solid var(--border)"><pre class="text-xs font-mono leading-relaxed" style="color:var(--green)">${_esc(mw.yaml)}</pre></div></div>`;
    }).join('');

    if (_mwViewMode === 'list') {
        const header = `<div class="svc-list-header mw-list-grid"><div>Protocol</div><div>Name</div><div>Config File</div><div class="rl-actions-head">Actions</div></div>`;
        grid.className = '';
        grid.innerHTML = `<div class="svc-list">${header}${grid.innerHTML}</div>`;
    } else if (_tmOn) {
        grid.className = 'tm-card-grid';
    } else {
        grid.className = 'grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4';
    }
    _mwCardEls = Array.from(grid.querySelectorAll('.mw-card'));
    setTabCount('middlewares', middlewares.length);
    filterMw();
}

async function handleMwEdit(btn) {
    const mw = JSON.parse(btn.getAttribute('data-mw'));
    document.getElementById('isMwEdit').value = 'true';
    document.getElementById('originalMwId').value = mw.name;
    document.getElementById('middlewareName').value = mw.name;
    document.getElementById('mwModalTitle').innerText = 'Edit ' + mw.name;
    document.getElementById('mwConfigFile').value = mw.configFile || '';
    const newMwInput = document.getElementById('newMwFileName');
    if (newMwInput) { newMwInput.style.display = 'none'; newMwInput.value = ''; }
    const mwTplSel2 = document.getElementById('mwTemplate');
    if (mwTplSel2) mwTplSel2.value = '';
    const mwProto = (mw.type || 'http').toLowerCase();
    setMwProtocol(mwProto);
    const origProtoEl2 = document.getElementById('originalMwProtocol');
    if (origProtoEl2) origProtoEl2.value = mwProto;
    setMwMode('yaml');
    _showMwWizard('');
    await _populateConfigFileSelect('mw');
    const cfSel = document.getElementById('mwConfigFileSelect');
    if (mw.configFile) {
        if (cfSel) cfSel.value = mw.configFile;
        document.getElementById('mwConfigFile').value = mw.configFile;
    }
    _openMwPanel();
    _initMwMonaco(mw.yaml.trim());
    _loadCustomMwTemplates();
}

async function _loadCustomMwTemplates() {
    const grp = document.getElementById('mwCustomOptgroup');
    if (!grp) return;
    try {
        const res  = await fetch('/api/mw/templates');
        const data = await res.json();
        const templates = data.templates || [];
        grp.innerHTML = templates.map(t => `<option value="custom:${t.id}">${_esc(t.name)}</option>`).join('');
        grp.style.display = templates.length ? '' : 'none';
    } catch(e) {
        grp.style.display = 'none';
    }
}

function applyMwTemplate(select) {
    const tpl = select.value;
    if (!tpl) return;
    if (tpl.startsWith('custom:')) {
        const id = tpl.slice(7);
        fetch('/api/mw/templates').then(r => r.json()).then(data => {
            const t = (data.templates || []).find(x => x.id === id);
            if (t) {
                setMwMode('yaml');
                if (_mwMonacoEditor) _mwMonacoEditor.setValue(t.yaml);
                else document.getElementById('middlewareContent').value = t.yaml;
            }
        });
    } else if (_wizardTemplates.has(tpl)) {
        _showMwWizard(tpl);
        setMwMode('wizard');
    }
}

let _mwFilter = 'all';
let _mwCardEls = [];
function filterMw(f) {
    if (f) {
        _mwFilter = f;
        ['all','http','tcp'].forEach(k => {
            document.getElementById('mwf-'+k)?.classList.toggle('active-http', k === f);
        });
    }
    const search = (document.getElementById('searchMw')?.value || '').toLowerCase();
    let visible = 0;
    for (const card of _mwCardEls) {
        const show = card.dataset.mwname.includes(search) && (_mwFilter === 'all' || card.dataset.mwtype === _mwFilter);
        card.style.display = show ? '' : 'none';
        if (show) visible++;
    }
    const emptyEl = document.getElementById('mwEmpty');
    const emptyText = document.getElementById('mwEmptyText');
    if (emptyEl) {
        emptyEl.classList.toggle('hidden', visible > 0 || _mwCardEls.length === 0);
        if (emptyText) emptyText.textContent = search ? `No middlewares match "${search}"` : 'No middlewares found';
    }
}
let _mwViewMode = tmPref('mwViewMode');

function toggleMwView() {
    _mwViewMode = _mwViewMode === 'grid' ? 'list' : 'grid';
    tmSetPref('mwViewMode', _mwViewMode);
    const icon = document.getElementById('mwViewIcon');
    if (icon) icon.className = _mwViewMode === 'grid' ? 'ph-bold ph-list' : 'ph-bold ph-squares-four';
    renderMwGrid(_allMiddlewares);
}

function openMwDetail(btn) {
    closeOtherPanels('mwDetailPanel');
    const mw = JSON.parse(btn.getAttribute('data-mw'));
    const panel = document.getElementById('mwDetailPanel');
    const backdrop = document.getElementById('mwDetailBackdrop');
    const badge = document.getElementById('mwDetailProtoBadge');
    const title = document.getElementById('mwDetailTitle');
    const content = document.getElementById('mwDetailContent');
    const editBtn = document.getElementById('mwDetailEditBtn');

    const typeLower = (mw.type || 'http').toLowerCase();
    badge.className = 'd-flat d-proto' + (typeLower === 'tcp' ? ' d-on' : '');
    badge.textContent = typeLower === 'tcp' ? 'TCP' : 'HTTP';
    title.textContent = mw.name;

    const isFileMw = !mw.provider || mw.provider === 'file';
    editBtn.style.display = isFileMw ? '' : 'none';
    if (isFileMw) {
        editBtn.onclick = () => {
            closeMwDetail();
            const fakeBtn = document.createElement('button');
            fakeBtn.setAttribute('data-mw', JSON.stringify(mw));
            handleMwEdit(fakeBtn);
        };
    }

    content.innerHTML = renderMwDetailPanel(mw);
    panel.classList.add('open');
    backdrop.classList.add('open');
    if (!setDetailDockOpen(true)) document.body.style.overflow = 'hidden';
}

function closeMwDetail() {
    setDetailDockOpen(false);
    document.getElementById('mwDetailPanel').classList.remove('open');
    document.getElementById('mwDetailBackdrop').classList.remove('open');
    document.body.style.overflow = '';
}

function _mwOpenRoute(id) {
    const pool = window._lastRenderedApps || [];
    const a = pool.find(x => String(x.id) === id);
    if (!a) return;
    closeMwDetail();
    openRouteDetail(a.name, (a.protocol || 'http').toLowerCase(), a);
}

function _mwOpenSibling(name) {
    const sib = (_allMiddlewares || []).find(m => m.name === name);
    if (!sib) return;
    const fakeBtn = document.createElement('button');
    fakeBtn.setAttribute('data-mw', JSON.stringify(sib));
    openMwDetail(fakeBtn);
}

function _openMwByName(name) {
    const bare = String(name).split('@')[0];
    const hit = (_allMiddlewares || []).find(m => String(m.name).split('@')[0] === bare);
    if (!hit) return;
    const fakeBtn = document.createElement('button');
    fakeBtn.setAttribute('data-mw', JSON.stringify(hit));
    openMwDetail(fakeBtn);
}

function _mwRoutesUsing(mw) {
    const pool = window._lastRenderedApps || (typeof APP_DATA !== 'undefined' ? APP_DATA : []) || [];
    const bare = String(mw.name).split('@')[0];
    const hit = x => String(x).split('@')[0] === bare;
    return pool.filter(a => (a.middlewares || []).some(hit) || (a.entrypointMiddlewares || []).some(hit))
        .map(a => ({ a, viaEp: !(a.middlewares || []).some(hit) }));
}

function _mwChainsUsing(mw) {
    const bare = String(mw.name).split('@')[0];
    const esc = bare.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const re = new RegExp('(^|[\\s\\[,\'"])' + esc + '(@[\\w.-]+)?([\\s\\],\'"]|$)', 'm');
    return (_allMiddlewares || []).filter(o => o.name !== mw.name && re.test(o.yaml || ''));
}

function renderMwDetailPanel(mw) {
    const rows = [];

    const kind = ((mw.yaml || '').match(/^([\w-]+)\s*:/m) || [])[1] || '';
    const pluginName = kind === 'plugin'
        ? (((mw.yaml || '').match(/^\s+([\w-]+)\s*:/m) || [])[1] || '')
        : '';

    rows.push(['Name', _dText(mw.name), true]);
    if (kind) rows.push(['Type', _dText(kind) + (pluginName ? ` <span class="d-flat d-off">(${_esc(pluginName)})</span>` : ''), true]);
    if (mw.type) rows.push(['Protocol', _dText((mw.type || '').toUpperCase()), true]);
    if (mw.provider && mw.provider !== 'file') rows.push(['Provider', _dText(mw.provider, 'd-off'), true]);
    if (mw.status && mw.status !== 'enabled') rows.push(['Status', `<span class="d-flat" style="color:var(--red)">${_esc(mw.status)}</span>`, true]);
    if (mw.error) rows.push(['Error', `<span class="d-flat" style="color:var(--red)">${_esc(Array.isArray(mw.error) ? mw.error.join(', ') : mw.error)}</span>`, true]);
    if (mw.configFile) rows.push(['Config File', _dText(mw.configFile, 'd-off'), true]);

    const routes = _mwRoutesUsing(mw);
    const chains = _mwChainsUsing(mw);
    let usedHtml = '';
    if (!routes.length && !chains.length) {
        usedHtml += '<div class="text-xs" style="color:var(--yellow)">Not referenced by any route</div>';
    } else {
        usedHtml += '<div class="flex flex-wrap gap-1.5">'
            + routes.map(({ a, viaEp }) =>
                `<button type="button" class="route-deep-chip" onclick="_mwOpenRoute(${_jsArg(String(a.id))})" title="${viaEp ? 'Attached via entry point' : 'Open route'}">`
                + `<i class="ph-bold ${viaEp ? 'ph-arrows-in' : 'ph-arrows-split'}"></i>${_esc(a.name)}</button>`).join('')
            + chains.map(c =>
                `<button type="button" class="route-deep-chip" onclick="_mwOpenSibling(${_jsArg(c.name)})" title="Referenced by this middleware">`
                + `<i class="ph-bold ph-stack"></i>${_esc(c.name.split('@')[0])}</button>`).join('')
            + '</div>';
    }
    usedHtml = renderDetailBlock('Used by', 'ph-stack', usedHtml);

    let yamlHtml = '';
    if (mw.yaml) {
        yamlHtml = renderDetailBlock('Configuration', 'ph-code',
            `<div class="rounded-lg p-3 overflow-x-auto" style="background:var(--input-bg);border:1px solid var(--border)"><pre class="text-xs font-mono leading-relaxed whitespace-pre-wrap" style="color:var(--green);margin:0">${_esc(mw.yaml)}</pre></div>`);
    }

    return `${renderSection('Details', 'ph-info', rows)}${usedHtml}${yamlHtml}`;
}

let _allPlugins = [];

let _pluginCanManage = false;
let _pluginEditName  = null;
let _pluginStaticMonaco = null;
let _pluginMwMonaco = null;

async function refreshPluginsTab() {
    const container = document.getElementById('pluginsContent');
    container.innerHTML = `<div class="text-center py-16" style="color:var(--muted)"><i class="ph-light ph-spinner-gap text-4xl block mb-3 animate-spin opacity-40"></i><p>Loading plugins...</p></div>`;
    try {
        const availP = _activeAgent
            ? agentFetch('/api/static/status').then(r => r.json()).then(d => ({ available: d.configured === true })).catch(() => ({ available: false }))
            : fetch('/api/static/available').then(r => r.json());
        const [pluginsRes, avail] = await Promise.all([
            agentFetch('/api/traefik/plugins'),
            availP,
        ]);
        if (!pluginsRes.ok) {
            const why = await _errText(pluginsRes, 'Could not load plugin data');
            container.innerHTML = `<div class="text-center py-16 rounded-xl" style="color:var(--muted);border:1px solid var(--border)"><i class="ph-light ph-cloud-slash text-5xl block mb-3 opacity-30"></i><p>${_esc(why)}</p></div>`;
            setTabCount('plugins', '0');
            return;
        }
        const res = await pluginsRes.json();
        _pluginCanManage = avail.available === true;
        const addBtn = document.getElementById('pluginAddBtnWrap');
        if (addBtn) addBtn.style.display = _pluginCanManage ? 'flex' : 'none';

        const plugins = Array.isArray(res.plugins) ? res.plugins : [];

        if (res.error && plugins.length === 0) {
            const svcName = _activeAgent ? 'traefik-manager-agent' : 'traefik-manager';
            const docsUrl = _activeAgent
                ? 'https://traefik-manager.xyzlab.dev/agent#static-config-editing'
                : 'https://traefik-manager.xyzlab.dev/env-vars#static-config-path';
            container.innerHTML = `
            <div class="text-center py-10 rounded-xl" style="border:1px solid var(--border);color:var(--muted)">
                <i class="ph-light ph-puzzle-piece text-5xl block mb-3 opacity-30"></i>
                <p class="font-semibold mb-1" style="color:var(--text)">Static config not configured${_activeAgent ? ' on this agent' : ''}</p>
                <p class="text-xs max-w-xs mx-auto mb-5">To list plugins here, mount the Traefik static config into the <code class="font-mono" style="color:var(--blue)">${svcName}</code> service and set <code class="font-mono" style="color:var(--blue)">STATIC_CONFIG_PATH</code>.</p>
                <div class="flex flex-col gap-2 items-center text-xs">
                    <a href="https://get-traefik.xyzlab.dev" target="_blank" class="btn-secondary" style="text-decoration:none"><i class="ph-bold ph-terminal"></i> Install script</a>
                    <a href="${docsUrl}" target="_blank" class="btn-secondary" style="text-decoration:none"><i class="ph-bold ph-book-open"></i> Setup docs</a>
                </div>
                <div class="mt-5 mx-auto text-left rounded-lg p-3 text-xs font-mono" style="max-width:420px;background:var(--input-bg);border:1px solid var(--border);color:var(--muted)">
                    <div style="color:var(--text);margin-bottom:4px">docker-compose.yml - ${svcName}</div>
                    environment:<br>
                    &nbsp;&nbsp;- STATIC_CONFIG_PATH=/traefik.yml<br>
                    volumes:<br>
                    &nbsp;&nbsp;- /path/to/traefik.yml:/traefik.yml
                </div>
            </div>`;
            setTabCount('plugins', '0');
            return;
        }

        if (plugins.length === 0) {
            const addHint = _pluginCanManage
                ? `<button onclick="openPluginForm()" class="btn-primary text-xs mt-3"><i class="ph-bold ph-plus"></i> Add Plugin</button>`
                : `<p class="text-xs max-w-sm mx-auto mt-1">Add plugins under <code class="font-mono">experimental.plugins</code> in your <code class="font-mono">traefik.yml</code>.</p>`;
            container.innerHTML = `<div class="text-center py-16 rounded-xl" style="color:var(--muted);border:1px solid var(--border)">
                <i class="ph-light ph-puzzle-piece text-5xl block mb-3 opacity-30"></i>
                <p class="font-medium mb-1">No plugins configured</p>
                ${addHint}
            </div>`;
            setTabCount('plugins', '0');
            return;
        }

        _allPlugins = plugins;
        setTabCount('plugins', plugins.length);
        _pluginCatalog = {};
        renderPluginsVerdict();
        renderPluginCards();
        fetch('/api/plugins/catalog').then(r => r.json()).then(d => {
            _pluginCatalog = d.plugins || {};
            renderPluginsVerdict();
            renderPluginCards();
        }).catch(() => {});
    } catch(e) {
        container.innerHTML = `<div class="text-center py-16 rounded-xl" style="color:var(--muted);border:1px solid var(--border)"><i class="ph-light ph-cloud-slash text-5xl block mb-3 opacity-30"></i><p>${_esc(_netErrText(e, 'Could not load plugin data'))}</p></div>`;
    }
}

function filterPlugins() { renderPluginCards(); }

function _initPluginStaticMonaco(value) {
    const container = document.getElementById('pluginStaticEditorContainer');
    if (!container) return;
    if (_pluginStaticMonaco) {
        _pluginStaticMonaco.setValue(value);
        setTimeout(() => _pluginStaticMonaco.layout(), 50);
        return;
    }
    require(['vs/editor/editor.main'], function() {
        _ensureMonacoThemes().then(() => {
            const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
            _pluginStaticMonaco = monaco.editor.create(container, {
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

function _initPluginMwMonaco(value) {
    const container = document.getElementById('pluginMwEditorContainer');
    if (!container) return;
    if (_pluginMwMonaco) {
        _pluginMwMonaco.setValue(value);
        setTimeout(() => _pluginMwMonaco.layout(), 50);
        return;
    }
    require(['vs/editor/editor.main'], function() {
        _ensureMonacoThemes().then(() => {
            const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
            _pluginMwMonaco = monaco.editor.create(container, {
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

function openPluginForm(idx = -1) {
    const form = document.getElementById('pluginForm');
    const title = document.getElementById('pluginFormTitle');
    const addSection = document.getElementById('pluginFormAdd');
    const editSection = document.getElementById('pluginFormEdit');
    if (!form) return;
    if (idx >= 0 && idx < _allPlugins.length) {
        const p = _allPlugins[idx];
        document.getElementById('pluginFormName').value    = p.name || '';
        document.getElementById('pluginFormModule').value  = p.moduleName || '';
        document.getElementById('pluginFormVersion').value = p.version || '';
        _pluginEditName = p.name;
        if (title) title.textContent = 'Edit Plugin';
        if (addSection) addSection.style.display = 'none';
        if (editSection) editSection.style.display = 'block';
        _openPluginPanel();
        setTimeout(() => document.getElementById('pluginFormName')?.focus(), 50);
    } else {
        _pluginEditName = null;
        if (title) title.textContent = 'Add Plugin';
        if (addSection) addSection.style.display = 'block';
        if (editSection) editSection.style.display = 'none';
        const rb = document.getElementById('pluginRestartBanner');
        if (rb) rb.style.display = 'none';
        _openPluginPanel();
        _populateConfigFileSelect('pluginMw').then(() => {
            const sel = document.getElementById('pluginMwFileSelect');
            if (sel && !sel.value) {
                const opt = [...sel.options].find(o => o.value && (o.value === 'plugin-middlewares.yml' || o.value.endsWith('/plugin-middlewares.yml')));
                if (opt) { sel.value = opt.value; onPluginMwFileChange(sel); }
            }
        });
        setTimeout(() => {
            _initPluginStaticMonaco('experimental:\n  plugins:\n    myPlugin:\n      moduleName: github.com/author/plugin\n      version: v0.1.0');
            _initPluginMwMonaco('http:\n  middlewares:\n    my-myPlugin:\n      plugin:\n        myPlugin:\n          setting: value');
        }, 50);
    }
}

function _openPluginPanel() {
    document.getElementById('pluginForm').classList.add('open');
    document.getElementById('pluginFormBackdrop').classList.add('open');
    if (!setDetailDockOpen(true)) document.body.style.overflow = 'hidden';
}

function closePluginForm() {
    setDetailDockOpen(false);
    document.getElementById('pluginForm').classList.remove('open');
    document.getElementById('pluginFormBackdrop').classList.remove('open');
    document.body.style.overflow = '';
    _pluginEditName = null;
}

async function savePlugin() {
    if (_pluginEditName) {
        const name       = document.getElementById('pluginFormName').value.trim();
        const moduleName = document.getElementById('pluginFormModule').value.trim();
        const version    = document.getElementById('pluginFormVersion').value.trim();
        if (!name || !moduleName || !version) { showToast('Name, module, and version are required', 'error'); return; }
        const d1 = await _pluginSectionWrite({ section: 'plugins', action: 'edit', name, old_name: _pluginEditName, data: { moduleName, version } });
        if (!d1) return;
        closePluginForm();
        showToast('Plugin saved - restart Traefik to apply', 'success');
        refreshPluginsTab();
    } else {
        const staticYaml = _pluginStaticMonaco ? _pluginStaticMonaco.getValue().trim() : '';
        const mwYaml = _pluginMwMonaco ? _pluginMwMonaco.getValue().trim() : '';
        if (!staticYaml) { showToast('Paste the static config snippet', 'error'); return; }
        const res = await fetch('/api/plugins/install', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ..._csrfHeaders() },
            body: JSON.stringify({ static_yaml: staticYaml, middleware_yaml: mwYaml, middleware_file: _pluginMwFileChoice(), server: _activeAgent ? _activeAgent.id : '' }),
        });
        if (!res.ok) { showToast(await _errText(res, 'Failed to install plugin'), 'error'); return; }
        const data = await res.json();
        if (!data.ok) { showToast(data.error || data.message || 'Failed to install plugin', 'error'); return; }
        closePluginForm();
        const banner = document.getElementById('pluginRestartBanner');
        const detail = document.getElementById('pluginRestartBannerDetail');
        if (banner) {
            const names = (data.plugins || []).join(', ');
            const hasMw = mwYaml.length > 0 && !data.warning;
            if (detail) detail.textContent = `Plugin${data.plugins?.length > 1 ? 's' : ''} "${names}" saved to traefik.yml${hasMw ? ` and middleware saved to ${data.middleware_file || 'plugin-middlewares.yml'}` : ''}.`;
            banner.style.display = 'block';
        }
        if (data.warning) showToast(data.warning, 'warning');
        refreshPluginsTab();
    }
}

function onPluginMwFileChange(sel) {
    const newInput = document.getElementById('pluginMwNewFileName');
    if (!newInput) return;
    if (sel.value === '__new__') {
        newInput.style.display = '';
        if (!newInput.value) newInput.value = 'plugin-middlewares.yml';
    } else {
        newInput.style.display = 'none';
        newInput.value = '';
    }
}

function _pluginMwFileChoice() {
    const sel = document.getElementById('pluginMwFileSelect');
    if (!sel || sel.offsetParent === null) return '';
    if (sel.value === '__new__') return (document.getElementById('pluginMwNewFileName')?.value || '').trim();
    return sel.value;
}

async function _pluginSectionWrite(body) {
    if (_activeAgent) {
        let cur = null;
        try {
            const curRes = await agentFetch('/api/static');
            if (!curRes.ok) { showToast(await _errText(curRes, 'Cannot read the agent static config'), 'error'); return null; }
            cur = await curRes.json();
        } catch (e) {
            showToast(_netErrText(e, 'Cannot read the agent static config'), 'error');
            return null;
        }
        if (!cur || cur.content === undefined) { showToast('Cannot read the agent static config', 'error'); return null; }
        body.current_raw = cur.content;
    }
    const r1 = await fetch('/api/static/section', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ..._csrfHeaders() },
        body: JSON.stringify(body),
    });
    if (!r1.ok) { showToast(await _errText(r1, 'Could not update the static config'), 'error'); return null; }
    const d1 = await r1.json();
    if (!d1.ok) { showToast(d1.error || d1.message || 'Could not update the static config', 'error'); return null; }
    const r2 = _activeAgent
        ? await agentFetch('/api/static', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ content: d1.raw }) })
        : await fetch('/api/static/config', { method: 'POST', headers: { 'Content-Type': 'application/json', ..._csrfHeaders() }, body: JSON.stringify({ content: d1.raw }) });
    if (!r2.ok) { showToast(await _errText(r2, 'Failed to save the static config'), 'error'); return null; }
    const d2 = await r2.json();
    if (!d2.ok) { showToast(d2.error || d2.message || 'Failed to save the static config', 'error'); return null; }
    return d1;
}

async function deletePlugin(name) {
    const users = _pluginMwsUsing(name).map(m => m.name);
    if (users.length) {
        const shown = users.slice(0, 5).join(', ') + (users.length > 5 ? ' and ' + (users.length - 5) + ' more' : '');
        await _confirm(`"${name}" is still used by ${shown}. Delete those middlewares first.`,
                       'Plugin In Use', 'OK');
        return;
    }
    if (!await _confirm(`Remove plugin "${name}"?`, 'Remove Plugin', 'Remove')) return;
    const d1 = await _pluginSectionWrite({ section: 'plugins', action: 'remove', name, old_name: name, data: {} });
    if (!d1) return;
    showToast('Plugin removed - restart Traefik to apply', 'success');
    refreshPluginsTab();
}

function _pluginMwsUsing(name) {
    const esc = String(name).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const re = new RegExp('^\\s*' + esc + '\\s*:', 'm');
    return (_allMiddlewares || []).filter(m => /(^|\n)\s*plugin\s*:/.test(m.yaml || '') && re.test(m.yaml || ''));
}

function _tmPluginUsage(name) {
    return _pluginMwsUsing(name).length;
}

function _pluginOpenMw(name) {
    if (typeof closePluginDetail === 'function') closePluginDetail();
    _mwOpenSibling(name);
}


let _pluginCatalog = {};

function _pluginLatest(p) {
    const mod = (p.moduleName || '').trim().toLowerCase();
    const latest = mod && _pluginCatalog[mod];
    if (!latest || !p.version) return null;
    const norm = v => String(v).replace(/^v/, '');
    if (typeof compareVersions === 'function' && compareVersions(norm(latest), norm(p.version)) > 0) return latest;
    return null;
}

function renderPluginsVerdict() {
    if (!document.getElementById('pluginsVerdict')) return;
    if (!_allPlugins.length) { _tvStrip('pluginsVerdict', null); return; }
    const updates = _allPlugins.filter(p => _pluginLatest(p)).length;
    const used = _allPlugins.filter(p => _tmPluginUsage(p.name || '') > 0).length;
    const unused = _allPlugins.length - used;
    const known = Object.keys(_pluginCatalog).length > 0;
    const flags = [{ cls: 'd-off', ic: 'ph-bold ph-puzzle-piece', n: _allPlugins.length,
                     label: _allPlugins.length === 1 ? 'plugin' : 'plugins' }];
    if (used) flags.push({ cls: 'd-on', ic: 'ph-bold ph-plugs-connected', n: used, label: 'in use' });
    if (unused) flags.push({ cls: 'd-off', ic: 'ph-bold ph-plugs', n: unused, label: 'unused' });
    if (updates) flags.push({ cls: 'd-warn', ic: 'ph-fill ph-arrow-circle-up', n: updates,
                              label: updates === 1 ? 'update available' : 'updates available' });
    else if (known) flags.push({ cls: 'd-on', ic: 'ph-bold ph-check', n: '', label: 'all current' });
    _tvStrip('pluginsVerdict', {
        health: updates ? 'warn' : 'up',
        ic: updates ? 'ph-fill ph-arrow-circle-up' : 'ph-fill ph-check-circle',
        txt: updates ? _sdNum(updates) + (updates === 1 ? ' update available' : ' updates available')
           : known ? 'All plugins current'
           : _sdNum(_allPlugins.length) + (_allPlugins.length === 1 ? ' plugin' : ' plugins'),
        flags,
        meta: known ? 'catalog checked <b>daily</b>' : '',
    });
}

function renderPluginCards() {
    const q = (document.getElementById('pluginsSearch')?.value || '').toLowerCase();
    const items = _allPlugins.filter(p =>
        !q || (p.name||'').toLowerCase().includes(q) || (p.moduleName||'').toLowerCase().includes(q)
    );
    if (items.length === 0) {
        document.getElementById('pluginsContent').innerHTML =
            `<div class="text-center py-12 rounded-xl" style="color:var(--muted);border:1px solid var(--border)">No plugins match your search</div>`;
        return;
    }
    const cards = items.map(p => {
        const idx        = _allPlugins.indexOf(p);
        const name       = p.name || 'Unknown';
        const version    = p.version || '-';
        const latest     = _pluginLatest(p);
        const moduleName = p.moduleName || '';
        const repoUrl    = moduleName.startsWith('github.com/') ? 'https://' + moduleName : '';
        const mgmtBtns   = _pluginCanManage ? `
            <button onclick="openPluginForm(${idx})" class="btn-icon" title="Edit" style="padding:4px 6px"><i class="ph-bold ph-pencil text-sm"></i></button>
            <button onclick="deletePlugin(${_jsArg(name)})" class="btn-icon" title="Remove" style="padding:4px 6px;color:var(--red)"><i class="ph-bold ph-trash text-sm"></i></button>` : '';
        const pluginUse = _tmPluginUsage(name);
        const rail = `<span class="tm-rail" onclick="event.stopPropagation()">` +
            (repoUrl ? `<a href="${_esc(repoUrl)}" target="_blank" rel="noopener" class="tm-btn" title="View on GitHub" onclick="event.stopPropagation()"><i class="ph-bold ph-github-logo"></i></a>` : '') +
            `<button type="button" class="tm-btn" title="Details" onclick="event.stopPropagation();openPluginDetail(${idx})"><i class="ph-bold ph-info"></i></button>` +
            (_pluginCanManage
                ? `<button type="button" class="tm-btn" title="Edit" onclick="event.stopPropagation();openPluginForm(${idx})"><i class="ph-bold ph-pencil-simple"></i></button>` +
                  `<button type="button" class="tm-btn" title="Remove" onclick="event.stopPropagation();deletePlugin(${_jsArg(name)})"><i class="ph-bold ph-trash"></i></button>`
                : '') +
            '</span>';
        return `<div class="tm-card" style="--tm-accent:var(--blue)" onclick="openPluginDetail(${idx})">
            <div class="tm-head">
                <span class="tm-ic tm-ic-tile"><i class="ph-bold ph-puzzle-piece"></i></span>
                <div class="tm-head-txt">
                    <div class="tm-title"><span class="tm-name">${_esc(name)}</span></div>
                    <div class="tm-sub">${_esc(version.startsWith('v') ? version : 'v' + version)}${latest ? ` <span class="sig-flag d-warn lg-static" style="margin-left:4px" title="Update available: change the version in traefik.yml and restart Traefik"><i class="ph-fill ph-arrow-circle-up"></i><b>${_esc(latest)}</b></span>` : ''}</div>
                </div>${rail}
            </div>
            ${moduleName ? `<div class="tm-vals"><div class="tm-val"><i class="ph-bold ph-package"></i><span class="tm-v" title="${_esc(moduleName)}">${_esc(moduleName)}</span>${_tmCopy(moduleName)}</div></div>` : ''}
            <div class="tm-foot"><span class="tm-meta ${pluginUse ? '' : 'tm-warn'}">${pluginUse ? `used by ${pluginUse} middleware${pluginUse > 1 ? 's' : ''}` : 'not referenced'}</span></div>
        </div>`;
    }).join('');
    document.getElementById('pluginsContent').innerHTML =
        `<div class="tm-card-grid">${cards}</div>`;
}

function openPluginDetail(idx) {
    closeOtherPanels('pluginDetailPanel');
    const p = _allPlugins[idx];
    if (!p) return;

    const name       = p.name || 'Unknown';
    const version    = p.version || '-';
    const moduleName = p.moduleName || '';
    const repoUrl    = moduleName.startsWith('github.com/') ? 'https://' + moduleName : '';

    document.getElementById('pluginDetailTitle').textContent = name;

    const latest = _pluginLatest(p);
    const known = Object.keys(_pluginCatalog).length > 0;
    const versionVal = latest
        ? `${_esc(version)} <span class="sig-flag d-warn lg-static" style="margin-left:6px"><i class="ph-fill ph-arrow-circle-up"></i><b>${_esc(latest)} available</b></span>`
        : known && _pluginCatalog[(moduleName || '').trim().toLowerCase()]
        ? `${_esc(version)} <span style="color:var(--green)"><i class="ph-bold ph-check"></i> latest</span>`
        : _esc(version);
    const rows = [
        ['Name',        _esc(name)],
        ['Version',     versionVal],
        ['Module',      _esc(moduleName || '-')],
        ...(repoUrl ? [['Repository', `<a href="${_esc(repoUrl)}" target="_blank" style="color:var(--blue)">${_esc(repoUrl)} <i class="ph-bold ph-arrow-square-out text-sm"></i></a>`]] : []),
    ];

    const infoRows = rows.map(([k, v]) =>
        [_esc(k), `<span class="font-mono" style="color:var(--text)">${v}</span>`, true]);

    const settingsSection = p.settings ? `
        ${renderDetailBlock('Configuration Schema', 'ph-sliders',
            `<pre class="text-xs font-mono leading-relaxed overflow-x-auto" style="color:var(--muted);max-height:300px;margin:0">${JSON.stringify(p.settings, null, 2).replace(/</g,'&lt;')}</pre>`)}` : '';

    const mws = _pluginMwsUsing(name);
    const usedSection = `
        ${renderDetailBlock('Used by', 'ph-stack', mws.length
            ? '<div class="flex flex-wrap gap-1.5">' + mws.map(m =>
                `<button type="button" class="route-deep-chip" onclick="_pluginOpenMw(${_jsArg(m.name)})" title="Open middleware"><i class="ph-bold ph-stack"></i>${_esc(m.name.split('@')[0])}</button>`).join('') + '</div>'
            : '<span class="text-xs" style="color:var(--yellow)">No middleware references this plugin</span>')}`;

    document.getElementById('pluginDetailBody').innerHTML = `
        ${renderSection('Plugin Info', 'ph-info', infoRows)}
        ${usedSection}
        ${settingsSection}`;

    document.getElementById('pluginDetailPanel').classList.add('open');
    document.getElementById('pluginDetailBackdrop').classList.add('open');
    if (!setDetailDockOpen(true)) document.body.style.overflow = 'hidden';
}

function closePluginDetail() {
    setDetailDockOpen(false);
    document.getElementById('pluginDetailPanel').classList.remove('open');
    document.getElementById('pluginDetailBackdrop').classList.remove('open');
    document.body.style.overflow = '';
}

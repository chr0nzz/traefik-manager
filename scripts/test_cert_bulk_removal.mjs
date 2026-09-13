import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import vm from 'node:vm';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');

function el(id) {
    return { id, style: {}, textContent: '', value: '', innerHTML: '',
             classes: new Set(),
             classList: { add(c) { this.o.classes.add(c); }, remove(c) { this.o.classes.delete(c); },
                          toggle(c, on) { on ? this.o.classes.add(c) : this.o.classes.delete(c); } } };
}

function harness(deleteBody) {
    const nodes = {};
    for (const id of ['certBulkBar', 'certBulkCount', 'certBulkBtn', 'certBulkWrap', 'certsContent'])
        { nodes[id] = el(id); nodes[id].classList.o = nodes[id]; }
    const log = { toasts: [], posted: null, reloaded: false, overlay: 'none', shown: false, refreshed: 0, rendered: 0 };
    const ctx = {
        console,
        document: { getElementById: id => nodes[id] || null, querySelectorAll: () => [], body: { style: {} } },
        setTimeout, clearTimeout, Promise, JSON, Math, Set, Map, Array, Object, String, Number, Date, AbortSignal,
        showToast: (m, k) => log.toasts.push([m, k || 'ok']),
        _csrfHeaders: () => ({}),
        _tlsSrv: () => '',
        _esc: s => String(s),
        _jsArg: s => JSON.stringify(s),
        _netErrText: (e, f) => f,
        _errText: async (r, f) => f,
        agentFetch: async () => ({ ok: true, json: async () => ({ certs: [] }) }),
        _showRestartOverlay: () => { log.overlay = 'flex'; log.shown = true; },
        _hideRestartOverlay: () => { log.overlay = 'none'; },
        _waitForReconnect: async (immediate, onBack) => {
            if (typeof onBack === 'function') { log.overlay = 'none'; onBack(); }
            else log.reloaded = true;
        },
        fetch: async (url, opt) => {
            if (String(url).startsWith('/api/certs/delete')) {
                log.posted = JSON.parse(opt.body);
                return { ok: true, json: async () => deleteBody };
            }
            return { ok: true, json: async () => ({}) };
        },
    };
    ctx.window = ctx;
    ctx.globalThis = ctx;
    vm.createContext(ctx);
    vm.runInContext(readFileSync(join(root, 'static', 'js', 'certs.js'), 'utf8'), ctx);
    vm.runInContext(`
        _certManage = { available: true };
        _certUsage  = { certs: [] };
        _allCerts   = [
            { resolver: 'le', main: 'a.example.com', sans: [], source: '/acme.json' },
            { resolver: 'le', main: 'b.example.com', sans: [], source: '/acme.json' },
        ];
        var _confirmSeen = null;
        _confirmWith = async (o) => { _confirmSeen = o; return { ok: true }; };
        refreshCertsTab  = async () => { __log.refreshed++; };
        renderCertCards  = () => { __log.rendered++; };
    `, Object.assign(ctx, { __log: log }));
    return { ctx, log, nodes };
}

let fails = 0;
const check = (label, cond, detail) => {
    console.log(`  ${cond ? 'ok  ' : 'FAIL'} ${label}${detail !== undefined && !cond ? '  -> ' + detail : ''}`);
    if (!cond) fails++;
};

console.log('bulk selection');
{
    const { ctx, nodes } = harness({ ok: true, removed: 2, restarted: true });
    vm.runInContext('toggleCertBulkMode()', ctx);
    check('the bar opens with bulk mode, so Select unused is reachable', nodes.certBulkBar.style.display === '');
    check('the toolbar button marks itself active like the routes tab', nodes.certBulkBtn.classes.has('active-http'));
    vm.runInContext('selectUnusedCerts()', ctx);
    check('nothing unused means nothing selected', nodes.certBulkCount.textContent === '0 selected',
          nodes.certBulkCount.textContent);
    vm.runInContext('toggleCertPick(_certKey(_allCerts[0]))', ctx);
    check('picking one counts it', nodes.certBulkCount.textContent === '1 selected', nodes.certBulkCount.textContent);
    vm.runInContext('toggleCertBulkMode()', ctx);
    check('leaving bulk mode hides the bar', nodes.certBulkBar.style.display === 'none');
    check('leaving bulk mode drops the selection', vm.runInContext('_certPicked.size', ctx) === 0);
}

console.log('removing several at once');
{
    const { ctx, log } = harness({ ok: true, removed: 2, restarted: true });
    await vm.runInContext(`(async () => {
        toggleCertBulkMode();
        toggleCertPick(_certKey(_allCerts[0]));
        toggleCertPick(_certKey(_allCerts[1]));
        await bulkRemoveCerts();
    })()`, ctx);
    check('both certificates were sent', log.posted && log.posted.certs.length === 2, JSON.stringify(log.posted));
    check('the confirm names them', /a\.example\.com/.test(vm.runInContext('_confirmSeen.message', ctx))
          && /b\.example\.com/.test(vm.runInContext('_confirmSeen.message', ctx)),
          vm.runInContext('_confirmSeen.message', ctx));
    check('a bulk removal shows the restart screen, not a bare toast', log.shown === true);
    check('the page is never reloaded under the user', log.reloaded === false);
    check('the certs tab is refreshed once Traefik is back', log.refreshed === 1, log.refreshed);
    check('the restart screen is taken down again', log.overlay === 'none', log.overlay);
    check('bulk mode is left afterwards', vm.runInContext('_certBulk', ctx) === false);
    check('the cards are repainted without their checkboxes', log.rendered >= 1, log.rendered);
    check('one toast, naming the count', log.toasts.length === 1 && /2 certificates/.test(log.toasts[0][0]),
          JSON.stringify(log.toasts));
}

console.log('a cancelled confirm');
{
    const { ctx, log } = harness({ ok: true, removed: 2, restarted: true });
    vm.runInContext('_confirmWith = async () => ({ ok: false });', ctx);
    await vm.runInContext(`(async () => {
        toggleCertBulkMode();
        toggleCertPick(_certKey(_allCerts[0]));
        await bulkRemoveCerts();
    })()`, ctx);
    check('nothing is sent', log.posted === null);
    check('the selection survives so it need not be redone', vm.runInContext('_certPicked.size', ctx) === 1);
    check('bulk mode stays on', vm.runInContext('_certBulk', ctx) === true);
}

console.log('a restart that did not happen');
{
    const { ctx, log } = harness({ ok: true, removed: 1, restarted: false, restart_error: 'no method' });
    await vm.runInContext(`(async () => {
        toggleCertBulkMode();
        toggleCertPick(_certKey(_allCerts[0]));
        await bulkRemoveCerts();
    })()`, ctx);
    check('the user is told the change is undone until Traefik restarts',
          log.toasts.length === 1 && log.toasts[0][1] === 'error' && /did not restart/.test(log.toasts[0][0]),
          JSON.stringify(log.toasts));
    check('no restart screen is shown for a restart that never ran', log.shown === false);
}

console.log(fails ? `\n${fails} failed` : '\nall passed');
process.exit(fails ? 1 : 0);

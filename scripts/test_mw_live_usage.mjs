import { readFileSync } from 'node:fs';
import { i18nPrelude } from './i18n_test_prelude.mjs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const src = readFileSync(join(root, 'static', 'js', 'middlewares.js'), 'utf8');

function slice(from, to) {
    const start = src.indexOf(from);
    const end = src.indexOf(to, start);
    if (start < 0 || end < 0) {
        console.error(`could not find ${from} in static/js/middlewares.js`);
        process.exit(1);
    }
    return src.slice(start, end);
}

const code = [
    slice('async function _sendMwDelete(', 'function _tmMwIcon('),
    slice('let _mwLive = null;', 'function _tmMwChained('),
    slice('function _mwRoutesUsing(', 'let _allPlugins = [];'),
].join('\n');

let failed = 0;
function check(ok, label, got) {
    if (ok) return;
    failed++;
    console.error('FAIL ' + label + (got === undefined ? '' : ': ' + JSON.stringify(got)));
}

function harness({ live = {}, pool = [], mws = [] } = {}) {
    const state = { renders: 0, confirms: [], posts: [], replies: [] };
    const window = { _lastRenderedApps: pool };
    const api = new Function('window', 'live', 'state', 'mws', `
        ${i18nPrelude()}
        let _activeAgent = null;
        let _allMiddlewares = mws;
        let _cachedMiddlewares = null;
        const tmList = a => a.join(', ');
        const _esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
        const _jsArg = s => JSON.stringify(s);
        const _dText = s => _esc(s);
        const renderSection = () => '';
        const renderDetailBlock = (title, icon, html) => html;
        const renderMwGrid = list => { state.renders++; _allMiddlewares = list; };
        const showToast = (msg, kind) => state.replies.push([kind, msg]);
        const refreshRoutes = () => {}, fetchNotifications = () => {};
        const _errText = async () => 'error', _netErrText = () => 'error';
        const _confirmWordFor = name => name;
        const _confirm = async (msg, title, label) => { state.confirms.push({ msg, title, label }); return state.answer; };
        const document = { querySelector: () => null };
        class FormData { constructor() { this.data = {}; } append(k, v) { this.data[k] = v; } }
        const agentFetch = async () => {
            const v = live[_activeAgent ? _activeAgent.id : ''];
            if (v === 'fail') throw new Error('network');
            if (v === 502) return { ok: false, status: 502 };
            if (v && v.wait) await v.wait;
            return { ok: true, json: async () => (v && v.data) || v };
        };
        const fetch = async (url, opts) => {
            state.posts.push({ url, force: opts.body.data.force });
            const r = state.deleteReplies.shift();
            return { ok: r.status < 300, status: r.status, json: async () => r.body };
        };
        ${code}
        return { refresh: refreshMwLiveUsage, usage: _tmMwUsage, users: _tmMwLiveUsers, detail: renderMwDetailPanel,
                 del: _sendMwDelete, setAgent: a => { _activeAgent = a; } };
    `)(window, live, state, mws);
    return { api, state, window };
}

const AUTH = { name: 'auth', type: 'http', yaml: 'basicAuth: {}\n', configFile: '' };
const LIVE = {
    http: [
        { name: 'auth@file', provider: 'file', usedBy: ['whoami@docker', 'web@file'] },
        { name: 'compress@docker', provider: 'docker', usedBy: ['whoami@docker'] },
        { name: 'compress@file', provider: 'file', usedBy: [] },
    ],
    tcp: [{ name: 'auth@file', provider: 'file', usedBy: ['db@docker'] }],
};

{
    const { api, state } = harness({ live: { '': LIVE }, mws: [AUTH] });
    check(api.usage(AUTH) === 0, 'before the live data arrives only files count', api.usage(AUTH));
    await api.refresh();
    check(api.usage(AUTH) === 1, 'a Docker router counts as a user', api.usage(AUTH));
    check(state.renders === 1, 'the grid is repainted once the live data arrives', state.renders);
    await api.refresh();
    check(state.renders === 1, 'unchanged live data does not repaint', state.renders);
    check(JSON.stringify(api.users(AUTH)) === '["whoami@docker"]', 'file routers from Traefik are left to the config', api.users(AUTH));
    check(api.usage({ name: 'compress', type: 'http' }) === 0, 'a same named Docker middleware does not count', api.usage({ name: 'compress', type: 'http' }));
    check(JSON.stringify(api.users({ name: 'auth', type: 'tcp' })) === '["db@docker"]', 'tcp is kept apart from http', api.users({ name: 'auth', type: 'tcp' }));
    check(api.users({ name: 'auth', type: 'http', provider: 'docker' }).length === 0, 'only file middlewares get live users');
}

{
    const pool = [{ id: 'site::web', name: 'web', middlewares: ['auth'], provider: 'file' }];
    const { api } = harness({ live: { '': LIVE }, pool, mws: [AUTH] });
    await api.refresh();
    check(api.usage(AUTH) === 2, 'file and Docker routers add up', api.usage(AUTH));
    const html = api.detail(AUTH);
    check(html.includes('whoami@docker') && html.includes('web'), 'the detail panel lists both', html);
    check(!html.includes('Not referenced by any route'), 'the detail panel does not call it unused', html);
    check(html.includes('Managed by docker - read only'), 'the Docker chip says where it lives', html);
}

{
    const pool = [{ id: 'whoami@docker', name: 'whoami', middlewares: ['auth@file'], provider: 'docker' }];
    const { api } = harness({ live: { a1: LIVE }, pool, mws: [AUTH] });
    api.setAgent({ id: 'a1' });
    await api.refresh();
    check(api.usage(AUTH) === 1, 'an agent router already in the pool is not counted twice', api.usage(AUTH));
}

for (const reply of ['fail', 502]) {
    const { api, state } = harness({ live: { '': reply }, mws: [AUTH] });
    await api.refresh();
    check(api.usage(AUTH) === 0, `${reply}: an unreachable Traefik falls back to the files`, api.usage(AUTH));
    check(api.detail(AUTH).includes('Not referenced by any route'), `${reply}: the detail panel falls back too`);
    check(state.renders === 0, `${reply}: nothing to repaint`, state.renders);
}

{
    let release;
    const wait = new Promise(r => { release = r; });
    const { api } = harness({ live: { '': { wait, data: LIVE }, a2: { http: [], tcp: [] } }, mws: [AUTH] });
    const pending = api.refresh();
    api.setAgent({ id: 'a2' });
    release();
    await pending;
    check(api.usage(AUTH) === 0, 'a reply for another server is dropped', api.usage(AUTH));
}

{
    const { api, state } = harness({ mws: [AUTH] });
    state.answer = true;
    state.deleteReplies = [
        { status: 409, body: { ok: false, inUseBy: ['whoami@docker'], externalUsers: ['whoami@docker'] } },
        { status: 200, body: { ok: true, message: 'deleted' } },
    ];
    await api.del('auth', '', false);
    const c = state.confirms[0] || {};
    check(!/Remove it from/.test(c.msg || ''), 'the prompt does not offer to edit Docker labels', c.msg);
    check(/cannot edit whoami@docker/.test(c.msg || '') && /Delete it anyway\?$/.test(c.msg || ''), 'the prompt says what breaks', c.msg);
    check(!/config files/.test(c.msg || ''), 'no config file line without file routers', c.msg);
    check(c.label === 'Delete anyway', 'the button says it deletes anyway', c.label);
    check(state.posts.length === 2 && state.posts[1].force === 'true', 'confirming sends force', state.posts);
}

{
    const { api, state } = harness({ mws: [AUTH] });
    state.answer = false;
    state.deleteReplies = [{ status: 409, body: { ok: false, inUseBy: ['web', 'a@docker', 'b@docker'], externalUsers: ['a@docker', 'b@docker'] } }];
    await api.del('auth', '', false);
    const c = state.confirms[0] || {};
    check(/removes it from 1 route in your config files/.test(c.msg || ''), 'the file router is counted apart', c.msg);
    check(/cannot edit a@docker, b@docker, because .* defines them\. They stop working/.test(c.msg || ''), 'the Docker routers use the plural', c.msg);
    check(state.posts.length === 1, 'cancelling sends nothing more', state.posts);
}

{
    const { api, state } = harness({ mws: [AUTH] });
    state.answer = false;
    state.deleteReplies = [{ status: 409, body: { ok: false, inUseBy: ['web', 'api'] } }];
    await api.del('auth', '', false);
    const c = state.confirms[0] || {};
    check(c.msg === '"auth" is still used by web, api. Remove it from 2 routes and delete it?', 'file only prompts are unchanged', c.msg);
    check(c.label === 'Remove and delete', 'file only button is unchanged', c.label);
}

if (failed) {
    console.error(`${failed} check(s) failed`);
    process.exit(1);
}
console.log('mw live usage: all checks passed');

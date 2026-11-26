import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import vm from 'node:vm';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const src = readFileSync(join(root, 'static', 'js', 'static-config.js'), 'utf8');
const grab = (head) => {
    const start = src.indexOf(head);
    if (start < 0) throw new Error(`${head} not found in static-config.js`);
    return src.slice(start, src.indexOf('\n}\n', start) + 2);
};

function makeContext(response) {
    const calls = { closed: [], toasts: [], rendered: 0 };
    const saveBtn = { style: { display: '' } };
    const ctx = {
        calls, saveBtn,
        fetch: async () => response,
        showToast: (msg, kind) => calls.toasts.push([kind, msg]),
        t: (s) => s,
        _errText: async (res, fallback) => (await res.json()).error || fallback,
        _netErrText: (e, fallback) => fallback,
        _csrfHeaders: () => ({}),
        closeStaticForm: (section) => calls.closed.push(section),
        _renderStaticSections: () => { calls.rendered++; },
        _markStaticPending: () => {},
        _staticToggleState: () => false,
        _epHeaderStrategyPayload: () => ({}),
        _epVersion: { pending: Promise.resolve() },
        _staticEditState: { name: 'websecure' },
        _staticRawContent: 'entryPoints: {}\n',
        _staticParsedData: {},
        _staticMonaco: null,
        _providerMonaco: { getValue: () => 'docker: {}\n' },
        _staticSectionEdits: false,
        document: {
            getElementById: (id) => ({ value: id === 'sfProviderType' ? 'docker' : 'x', checked: false }),
            querySelector: () => saveBtn,
        },
    };
    vm.createContext(ctx);
    for (const head of ['async function _applyStaticSectionChange(', 'async function submitStaticSection(',
                        'async function submitStaticProvider(', 'async function saveStaticSingleSection(']) {
        vm.runInContext(grab(head), ctx);
    }
    return ctx;
}

const reply = (status, body) => ({ ok: status < 400, status, json: async () => body });
const rejected = () => reply(400, { error: 'HTTP/3 advertised port must be a whole number from 1 to 65535' });
const accepted = () => reply(200, { ok: true, raw: 'entryPoints: {}\n', parsed: {} });
const notOk    = () => reply(200, { ok: false, error: 'nope' });

let fails = 0;
const check = (label, cond) => {
    console.log(`  ${cond ? 'ok  ' : 'FAIL'} ${label}`);
    if (!cond) fails++;
};

const forms = [
    ['entry point', 'entrypoints', (c) => c.submitStaticSection('entrypoints')],
    ['resolver',    'resolvers',   (c) => c.submitStaticSection('resolvers')],
    ['plugin',      'plugins',     (c) => c.submitStaticSection('plugins')],
    ['provider',    'providers',   (c) => c.submitStaticProvider()],
];
for (const [label, section, submit] of forms) {
    for (const [why, res] of [['a 400', rejected], ['ok: false', notOk]]) {
        const c = makeContext(res());
        await submit(c);
        check(`${label} form stays open after ${why}`, c.calls.closed.length === 0);
        check(`${label} form shows the error after ${why}`, c.calls.toasts.some(([k]) => k === 'error'));
        check(`${label} form keeps the config untouched after ${why}`, c.calls.rendered === 0 && c._staticSectionEdits === false);
    }
    const c = makeContext(accepted());
    await submit(c);
    check(`${label} form closes after a successful save`, c.calls.closed.length === 1 && c.calls.closed[0] === section);
    check(`${label} form shows no error after a successful save`, c.calls.toasts.length === 0);
}

for (const [why, res] of [['a 400', rejected], ['ok: false', notOk]]) {
    const c = makeContext(res());
    await c.saveStaticSingleSection('api');
    check(`single section keeps its Save button after ${why}`, c.saveBtn.style.display === '');
}
{
    const c = makeContext(accepted());
    await c.saveStaticSingleSection('api');
    check('single section hides its Save button after a successful save', c.saveBtn.style.display === 'none');
}

console.log(fails ? `\n${fails} check(s) failed` : '\nall checks passed');
process.exit(fails ? 1 : 0);

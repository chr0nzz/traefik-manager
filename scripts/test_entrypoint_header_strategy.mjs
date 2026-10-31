import { readFileSync } from 'node:fs';
import { i18nPrelude } from './i18n_test_prelude.mjs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const src = readFileSync(join(root, 'static', 'js', 'static-config.js'), 'utf8');
const start = src.indexOf('function _semverParts(v)');
const end = src.indexOf('function openStaticAddForm(section)');
if (start < 0 || end < 0) {
    console.error('could not find the header strategy code in static/js/static-config.js');
    process.exit(1);
}

function harness({ versions, parsed = {}, name = null, agent = null }) {
    const els = {};
    const el = id => (els[id] ||= { id, style: {}, value: '', textContent: '', innerHTML: '',
        remove() { delete els[id]; },
        insertBefore(child) { els[child.id] = child; } });
    ['sfEpUnderscoreRow', 'sfEpUnderscore', 'sfEpHdrLabel', 'sfEpHdrDefault', 'sfEpHdrDelete', 'sfEpHdrReject', 'sfEpHdrHint'].forEach(el);
    const document = {
        getElementById: id => els[id] || null,
        createElement: () => ({ style: {}, remove() { delete els[this.id]; } }),
    };
    const api = new Function('document', 'versions', 'parsed', 'name', 'agent', `
        ${i18nPrelude()}
        let _activeAgent = agent;
        let _staticParsedData = parsed;
        let _staticEditState = { section: 'entrypoints', name };
        const agentFetch = async () => {
            const v = versions[_activeAgent ? _activeAgent.id : ''];
            if (v === 'fail') throw new Error('network');
            if (v === '500') return { ok: false };
            return { ok: true, json: async () => (v ? { Version: v } : {}) };
        };
        ${src.slice(start, end)}
        return {
            load: _loadEpVersion, clear: _clearEpVersion, show: _showEpHeaderField, state: _epHeaderStrategyState,
            payload: _epHeaderStrategyPayload, file: _epFileHeaderStrategy, value: _epHeaderStrategyValue,
            setAgent: a => { _activeAgent = a; }, pending: () => _epVersion.pending,
        };
    `)(document, versions, parsed, name, agent);
    return { api, els };
}

let failed = 0;
const check = (ok, why, got) => {
    if (!ok) { console.error(`FAIL ${why}${got === undefined ? '' : ': got ' + JSON.stringify(got)}`); failed++; }
};

const entry = http => ({ entryPoints: { websecure: { address: ':443', http } } });
const UNDERSCORE = 'underscoreHeadersStrategy';
const ALIAS = 'aliasHeadersStrategy';

for (const [version, want] of [
    ['3.7.17', 'alias'], ['3.7.12', 'alias'], ['3.8.0-rc.1', 'alias'], ['4.0.0', 'alias'],
    ['3.7.11', 'underscore'], ['3.7.6', 'underscore'],
    ['3.7.5', 'unsupported'], ['3.6.25', 'unsupported'], ['2.11.61', 'unsupported'],
    ['', 'unknown'], ['fail', 'unknown'], ['500', 'unknown'], ['master', 'unknown'],
]) {
    const { api } = harness({ versions: { '': version } });
    await api.load();
    check(api.state() === want, `Traefik "${version}" should be ${want}`, api.state());
}

{
    const { api } = harness({ versions: { '': '3.7.17' } });
    check(api.state() === 'unknown', 'no version is known before it has loaded', api.state());
}

for (const [version, key] of [['3.7.17', ALIAS], ['3.7.8', UNDERSCORE]]) {
    const { api, els } = harness({ versions: { '': version } });
    await api.load();
    els.sfEpUnderscore.value = 'delete';
    const p = api.payload();
    check(p.underscore_headers === 'delete' && p.headers_strategy_key === key, `${version} sends the chosen value on ${key}`, p);
}

{
    const parsed = entry({ [UNDERSCORE]: 'delete' });
    const { api, els } = harness({ versions: { '': '3.6.25' }, parsed, name: 'websecure' });
    await api.load();
    els.sfEpUnderscore.value = 'delete';
    const p = api.payload();
    check(p.underscore_headers === '' && p.headers_strategy_key === UNDERSCORE, 'old Traefik sends an empty value', p);
}

for (const [http, value, key] of [
    [{ [ALIAS]: 'delete' }, 'delete', ALIAS],
    [{ [UNDERSCORE]: 'reject' }, 'reject', UNDERSCORE],
    [{ [ALIAS]: 'keep', [UNDERSCORE]: 'reject' }, 'keep', ALIAS],
    [{}, '', UNDERSCORE],
]) {
    const { api, els } = harness({ versions: { '': 'fail' }, parsed: entry(http), name: 'websecure' });
    await api.load();
    els.sfEpUnderscore.value = 'reject';
    const p = api.payload();
    check(p.underscore_headers === value && p.headers_strategy_key === key, `unknown version keeps ${JSON.stringify(http)}`, p);
}

{
    const { api } = harness({ versions: { '': 'fail' }, name: null });
    await api.load();
    const p = api.payload();
    check(p.underscore_headers === '' && p.headers_strategy_key === UNDERSCORE, 'unknown version on a new entry point writes nothing', p);
}

for (const [version, shown] of [['3.7.17', 'block'], ['3.7.8', 'block'], ['3.6.25', 'none'], ['fail', 'none']]) {
    const { api, els } = harness({ versions: { '': version } });
    api.show();
    check(els.sfEpUnderscoreRow.style.display === 'none', `${version}: hidden while the version loads`);
    await api.pending();
    await Promise.resolve();
    check(els.sfEpUnderscoreRow.style.display === shown, `${version}: row should be ${shown}`, els.sfEpUnderscoreRow.style.display);
}

{
    const { api, els } = harness({ versions: { '': '3.7.17' } });
    api.show();
    await api.pending();
    await Promise.resolve();
    check(els.sfEpUnderscoreRow.style.display === 'block', 'the field shows once the version is known');
    api.show();
    check(els.sfEpUnderscoreRow.style.display === 'none', 'reopening the form hides the field until the version reloads');
    check(api.state() === 'unknown', 'reopening the form does not reuse the last version', api.state());
}

{
    const versions = { '': '3.7.17', a: '3.6.25', b: 'fail' };
    const { api } = harness({ versions });
    await api.load();
    api.setAgent({ id: 'a' });
    check(api.state() === 'unknown', 'a version from another server is not trusted', api.state());
    await api.load();
    check(api.state() === 'unsupported', 'the active agent decides', api.state());
    api.clear();
    check(api.state() === 'unknown', 'switching server clears the version', api.state());
    api.setAgent({ id: 'b' });
    await api.load();
    check(api.state() === 'unknown', 'a failed fetch does not reuse the earlier version', api.state());
}

{
    const versions = { '': '3.7.17', a: '3.6.25' };
    const { api } = harness({ versions });
    const late = api.load();
    api.setAgent({ id: 'a' });
    api.clear();
    await late;
    check(api.state() === 'unknown', 'a late answer from the previous server is dropped', api.state());
}

{
    const parsed = { ...entry({}), global: { [ALIAS]: 'delete' } };
    const { api, els } = harness({ versions: { '': '3.7.17' }, parsed, name: 'websecure' });
    api.show();
    await api.pending();
    await Promise.resolve();
    check(!!els.sfEpHdrKeep, 'a global default offers an explicit Keep');
    check(/delete/.test(els.sfEpHdrDefault.textContent), 'the default option names the global value', els.sfEpHdrDefault.textContent);
}

{
    const { api, els } = harness({ versions: { '': '3.7.17' }, parsed: entry({ [ALIAS]: 'keep' }), name: 'websecure' });
    api.show();
    await api.pending();
    await Promise.resolve();
    check(els.sfEpHdrKeep && els.sfEpUnderscore.value === 'keep', 'an explicit keep in the file stays selected', els.sfEpUnderscore.value);
    check(api.payload().underscore_headers === 'keep', 'an explicit keep is sent back', api.payload());
}

{
    const { api, els } = harness({ versions: { '': '3.7.17' }, parsed: entry({}), name: 'websecure' });
    api.show();
    await api.pending();
    await Promise.resolve();
    check(!els.sfEpHdrKeep, 'no second Keep without a global default');
    check(els.sfEpHdrDefault.textContent === 'Keep (default)', 'the default label stays', els.sfEpHdrDefault.textContent);
}

{
    const { api } = harness({ versions: {} });
    check(api.file({ http: { [UNDERSCORE]: 'delete' } }).key === UNDERSCORE, 'the row shows the key in the file');
    check(api.value({ http: { [ALIAS]: 'delete', [UNDERSCORE]: 'reject' } }) === 'delete', 'alias is read first');
}

if (failed) { console.error(`${failed} check(s) failed`); process.exit(1); }
console.log('entry point header strategy: all checks passed');

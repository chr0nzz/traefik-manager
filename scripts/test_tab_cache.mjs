import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const src = readFileSync(join(root, 'static', 'js', 'core.js'), 'utf8');

const block = src.split("const TAB_CACHE_PREFIX = 'tm.tab.';")[1].split('\nfunction tabCacheHydrate(')[0];
const hydrate = 'function tabCacheHydrate(' + src.split('\nfunction tabCacheHydrate(')[1].split('\n}\n')[0] + '\n}';

function makeStorage(limit) {
    const map = new Map();
    return {
        map,
        get length() { return map.size; },
        key(i) { return Array.from(map.keys())[i] ?? null; },
        getItem(k) { return map.has(k) ? map.get(k) : null; },
        setItem(k, v) {
            let used = 0;
            map.forEach((val, key) => { if (key !== k) used += val.length; });
            if (used + v.length > limit) { const e = new Error('quota'); e.name = 'QuotaExceededError'; throw e; }
            map.set(k, v);
        },
        removeItem(k) { map.delete(k); },
    };
}

function harness(storage, agent) {
    const code = `
const TAB_CACHE_PREFIX = 'tm.tab.';
${block}
${hydrate}
return { tabCacheGet, tabCachePut, tabCacheDrop, tabCacheClear, tabCacheHydrate, tabCacheForgetAll, _tabCacheKey,
         setAgent(a) { _activeAgent = a; } };
`;
    const window = { _tmAssetVersion: '1.14.0-abc' };
    return new Function('sessionStorage', 'window', '_activeAgent', 'console', code)(storage, window, agent, console);
}

let fails = 0;
const check = (label, cond, detail) => {
    console.log(`  ${cond ? 'ok  ' : 'FAIL'} ${label}${detail ? '  -> ' + detail : ''}`);
    if (!cond) fails++;
};

console.log('scoping');
{
    const st = makeStorage(1e6);
    const api = harness(st, null);
    api.tabCachePut('routes', { apps: [1, 2] });
    check('host key carries version and host', api._tabCacheKey('routes') === 'tm.tab.1.14.0-abc.host.routes', api._tabCacheKey('routes'));
    check('round trip', JSON.stringify(api.tabCacheGet('routes')) === '{"apps":[1,2]}');
    api.setAgent({ id: 'ag1' });
    check('agent sees nothing from host', api.tabCacheGet('routes') === null);
    api.tabCachePut('routes', { apps: [9] });
    check('agent key is separate', api._tabCacheKey('routes') === 'tm.tab.1.14.0-abc.ag1.routes');
    api.setAgent(null);
    check('host entry untouched', api.tabCacheGet('routes').apps.length === 2);
    check('two keys stored', st.length === 2, String(st.length));
}

console.log('hydrate once per key');
{
    const st = makeStorage(1e6);
    const api = harness(st, null);
    let paints = 0;
    check('no data, no paint', api.tabCacheHydrate('logs', () => paints++) === false && paints === 0);
    api.tabCachePut('logs', { lines: ['a'] });
    check('first hydrate paints', api.tabCacheHydrate('logs', () => paints++) === true && paints === 1);
    check('second hydrate skipped', api.tabCacheHydrate('logs', () => paints++) === false && paints === 1);
    api.setAgent({ id: 'ag1' });
    api.tabCachePut('logs', { lines: ['b'] });
    check('other server hydrates on its own', api.tabCacheHydrate('logs', () => paints++) === true && paints === 2);
    api.tabCacheClear();
    check('clear empties storage', st.length === 0);
    api.tabCachePut('logs', { lines: ['c'] });
    check('clear resets the once guard', api.tabCacheHydrate('logs', () => paints++) === true && paints === 3);
    check('paint that throws is reported as no hydrate', api.tabCacheHydrate('nope', () => { throw new Error('x'); }) === false);
    api.tabCacheForgetAll();
    check('forget all keeps the data', api.tabCacheGet('logs') !== null);
    check('forget all lets the same server hydrate again', api.tabCacheHydrate('logs', () => paints++) === true && paints === 4);
}

console.log('quota');
{
    const st = makeStorage(120);
    const api = harness(st, null);
    check('small entry fits', api.tabCachePut('routes', { a: 1 }) === true);
    check('crowdsec entry fits', api.tabCachePut('crowdsec', { rows: 'xxxxxxxxxxxxxxxxxxxx' }) === true);
    const ok = api.tabCachePut('logs', { lines: 'y'.repeat(90) });
    check('crowdsec dropped to make room', ok === true && api.tabCacheGet('crowdsec') === null && api.tabCacheGet('routes') !== null);
    const huge = api.tabCachePut('crowdsec', { rows: 'z'.repeat(500) });
    check('oversized entry is skipped, nothing else lost', huge === false && api.tabCacheGet('routes') !== null && api.tabCacheGet('logs') !== null);
}

console.log('storage that throws');
{
    const broken = { get length() { throw new Error('blocked'); }, key() { throw new Error('blocked'); },
                     getItem() { throw new Error('blocked'); }, setItem() { throw new Error('blocked'); }, removeItem() { throw new Error('blocked'); } };
    const api = harness(broken, null);
    check('get returns null', api.tabCacheGet('routes') === null);
    check('put returns false', api.tabCachePut('routes', { a: 1 }) === false);
    let threw = false;
    try { api.tabCacheClear(); api.tabCacheDrop('routes'); } catch (_) { threw = true; }
    check('clear and drop never throw', !threw);
}

console.log(fails ? `\n${fails} check(s) failed` : '\nall checks passed');
process.exit(fails ? 1 : 0);

import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

const ENTITIES = {
    '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&#39;': "'",
    '&middot;': '·', '&nbsp;': ' ',
};

function textOf(html) {
    return String(html || '')
        .replace(/<[^>]*>/g, '')
        .replace(/&[#\w]+;/g, m => (m in ENTITIES ? ENTITIES[m] : m));
}

function makeElement() {
    return {
        _text: '',
        set innerHTML(v) { this._text = textOf(v); },
        get innerHTML() { return this._text; },
        get textContent() { return this._text; },
    };
}

const sandbox = {
    console,
    setInterval: () => 0,
    clearInterval: () => {},
    document: {
        createElement: () => makeElement(),
        getElementById: () => null,
        querySelectorAll: () => [],
        addEventListener: () => {},
    },
    _esc(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    },
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;

const ctx = vm.createContext(sandbox);
const SRC = fs.readFileSync(path.join(ROOT, 'static', 'js', 'dashboard.js'), 'utf8');
vm.runInContext(SRC, ctx, { filename: 'dashboard.js' });

const M = name => vm.runInContext(name, ctx);

const _sdBucket    = M('_sdBucket');
const _sdProvider  = M('_sdProvider');
const _sdTally     = M('_sdTally');
const _sdEpProto   = M('_sdEpProto');
const _sdBuild     = M('_sdBuild');
const _sdCardModel = M('_sdCardModel');
const _sdTerse     = M('_sdTerse');
const _sdSubOffender = M('_sdSubOffender');
const _sdHealth      = M('_sdHealth');
const _sdAria        = M('_sdAria');
const _sdComposite   = M('_sdComposite');
const _sdBackendRoll = M('_sdBackendRoll');
const _sdBackendTxt  = M('_sdBackendTxt');

const failures = [];
let ran = 0;

function test(name, fn) {
    ran++;
    try {
        fn();
    } catch (e) {
        failures.push(name + '\n    ' + (e && e.message ? e.message : e));
    }
}

const router = (name, extra) => Object.assign({ name: name, status: 'enabled' }, extra || {});

test('provider comes from the name suffix and the kubernetes family is one bucket', () => {
    assert.equal(_sdProvider({ name: 'a@docker' }), 'docker');
    assert.equal(_sdProvider({ name: 'a' }), 'file');
    assert.equal(_sdProvider({ name: 'a@kubernetescrd' }), 'kubernetes');
    assert.equal(_sdProvider({ name: 'a@kubernetesingress' }), 'kubernetes');
    assert.equal(_sdProvider({ provider: 'KubernetesGateway', name: 'a@whatever' }), 'kubernetes');
});

test('status buckets keep enabled, disabled and warning apart from anything else', () => {
    assert.equal(_sdBucket({ status: 'enabled' }), 'enabled');
    assert.equal(_sdBucket({ status: 'Disabled' }), 'disabled');
    assert.equal(_sdBucket({ status: 'warning' }), 'warning');
    assert.equal(_sdBucket({ status: 'error' }), 'unknown');
    assert.equal(_sdBucket({}), 'unknown');
});

test('the tally counts every cell and every exception', () => {
    const t = _sdTally([
        { cell: 'err', status: 'disabled' },
        { cell: 'warn', status: 'warning' },
        { cell: 'idle', status: 'enabled', unbound: true },
        { cell: 'ok', status: 'enabled' },
    ]);
    assert.deepEqual([t.total, t.err, t.warn, t.idle, t.ok], [4, 1, 1, 1, 1]);
    assert.deepEqual([t.disabled, t.warning, t.unbound], [1, 1, 1]);
});

test('the services card counts http, tcp and udp services', () => {
    const model = _sdBuild({
        services: {
            http: [{ name: 'a@file', status: 'enabled' }],
            tcp:  [{ name: 'b@file', status: 'enabled' }],
            udp:  [{ name: 'c@file', status: 'enabled' }],
        },
    });
    assert.equal(model.objs.service.length, 3);
});

test('the stream card holds tcp and udp routers and tags each with its protocol', () => {
    const model = _sdBuild({
        routers: {
            http: [router('h@file')],
            tcp:  [router('t@file'), router('t2@file')],
            udp:  [router('u@file')],
        },
    });
    assert.equal(model.objs.http.length, 1);
    assert.equal(model.objs.stream.length, 3);
    assert.equal(model.objs.stream.filter(o => o.proto === 'tcp').length, 2);
    assert.equal(model.objs.stream.filter(o => o.proto === 'udp').length, 1);
});

test('an entry point carrying only tcp routers is a tcp entry point', () => {
    const p = _sdEpProto({ name: 'postgres', address: ':5432' }, { httpN: 0, tcpN: 1, udpN: 0, tls: true });
    assert.equal(p.key, 'tcp');
    assert.equal(p.tag, 'TCP');
});

test('an entry point carrying http routers stays http even with tcp beside it', () => {
    const p = _sdEpProto({ name: 'websecure', address: ':443' }, { httpN: 3, tcpN: 1, udpN: 0 });
    assert.equal(p.key, 'http');
    assert.equal(p.tag, 'HTTPS');
});

test('port 443 is https even when tls is declared on the routers, not the entry point', () => {
    assert.equal(_sdEpProto({ name: 'websecure', address: ':443', http: {} }, { httpN: 3 }).tag, 'HTTPS');
    assert.equal(_sdEpProto({ name: 'websecure', address: ':8443', http: {} }, {}).tag, 'HTTPS');
    assert.equal(_sdEpProto({ name: 'web', address: ':80', http: {} }, { httpN: 3, tls: true }).tag, 'HTTPS');
    assert.equal(_sdEpProto({ name: 'web', address: ':80', http: {} }, { httpN: 3 }).tag, 'HTTP');
});

test('a udp address with no router bound is still a udp entry point', () => {
    assert.equal(_sdEpProto({ name: 'wg', address: ':51820/udp' }, { httpN: 0, tcpN: 0, udpN: 0 }).key, 'udp');
});

test('an overview total larger than the list marks the card truncated', () => {
    const objs = [{ provider: 'file', cell: 'ok', status: 'enabled', name: 'a@file', short: 'a' }];
    const card = _sdCardModel('http', objs, { total: 1500, warnings: null, errors: null }, true);
    assert.equal(card.total, 1500);
    assert.equal(card.truncated, 1499);
});

test('a total known only from the overview is reported as unlisted', () => {
    const card = _sdCardModel('http', [], { total: 4, warnings: null, errors: null }, false);
    assert.equal(card.known, true);
    assert.equal(card.listed, false);
    assert.equal(card.total, 4);
});

test('an unused middleware is not rescued by a same-name middleware in another provider', () => {
    const model = _sdBuild({
        routers: { http: [router('r@file', { middlewares: ['auth@file'] })] },
        middlewares: {
            http: [{ name: 'auth@file', status: 'enabled' }, { name: 'auth@docker', status: 'enabled' }],
        },
    });
    const byName = Object.fromEntries(model.objs.middleware.map(o => [o.name, o]));
    assert.equal(!!byName['auth@file'].unused, false);
    assert.equal(!!byName['auth@docker'].unused, true);
});

test('an unqualified middleware reference only matches its own provider', () => {
    const model = _sdBuild({
        routers: { http: [router('r@docker', { middlewares: ['auth'] })] },
        middlewares: {
            http: [{ name: 'auth@file', status: 'enabled' }, { name: 'auth@docker', status: 'enabled' }],
        },
    });
    const byName = Object.fromEntries(model.objs.middleware.map(o => [o.name, o]));
    assert.equal(!!byName['auth@docker'].unused, false);
    assert.equal(!!byName['auth@file'].unused, true);
});

test('a long traefik error is shortened for the sub line but kept whole in the title', () => {
    const long = 'the service "very-long-service-name-that-goes-on@file" does not exist';
    assert.ok(_sdTerse(long).length <= 44, _sdTerse(long));
    assert.ok(_sdTerse(long).startsWith('missing service'), _sdTerse(long));
    const sub = _sdSubOffender(
        [{ cell: 'err', name: 'r@file', short: 'r', reason: 'disabled - ' + long }], '21 live');
    assert.ok(textOf(sub.html).length < sub.full.length, textOf(sub.html));
    assert.ok(!textOf(sub.html).includes('very-long-service-name-that-goes-on'));
    assert.ok(sub.full.includes('very-long-service-name-that-goes-on'), sub.full);
    assert.ok(sub.full.includes('21 live'), sub.full);
    assert.ok(sub.html.includes('sig-sub-tail'), sub.html);
    assert.ok(sub.html.includes('21 live'), sub.html);
});

test('a router bound to no entry point is idle, not healthy', () => {
    const model = _sdBuild({ routers: { http: [router('r@file', { using: [] })] } });
    assert.equal(model.objs.http[0].cell, 'idle');
    assert.equal(model.objs.http[0].unbound, true);
});

test('a service with a DOWN backend is degraded', () => {
    const model = _sdBuild({
        services: { http: [{ name: 's@file', status: 'enabled', serverStatus: { a: 'UP', b: 'DOWN' } }] },
    });
    assert.equal(model.objs.service[0].degraded, true);
    assert.equal(model.objs.service[0].cell, 'warn');
});

const svc = (name, extra) => Object.assign({ name: name, status: 'enabled' }, extra || {});
const svcModel = list => _sdBuild({ services: { http: list } }).objs.service;
const noOv = { total: null, warnings: null, errors: null };

test('every composite kind is named instead of being bucketed as unchecked', () => {
    const kinds = {
        weighted:            'weighted',
        mirroring:           'mirroring',
        failover:            'failover',
        highestRandomWeight: 'highest random weight',
    };
    Object.keys(kinds).forEach(key => {
        const raw = svc('c@file');
        raw[key] = { services: [{ name: 'child@file' }] };
        const o = svcModel([raw])[0];
        assert.equal(o.composite, kinds[key], key + ' was not recognised as a composite');
        assert.equal(o.cell, 'ok', key + ' must not land in the idle bucket');
        assert.equal(!!o.unchecked, false, key + ' has no servers of its own to health check');
        assert.equal(o.backends, null, key + ' must report no backends of its own');
    });
});

test('a load balancer with no serverStatus is still unchecked', () => {
    const o = svcModel([svc('s@file', { loadBalancer: { servers: [{ url: 'http://a:80' }] } })])[0];
    assert.equal(o.composite, '');
    assert.equal(o.cell, 'idle');
    assert.equal(o.unchecked, true);
    assert.equal(_sdComposite(null), '');
    assert.equal(_sdComposite({ loadBalancer: { servers: [] } }), '');
});

test('a composite never moves the backends up and down counts', () => {
    const objs = svcModel([
        svc('lb@file', { loadBalancer: { healthCheck: { path: '/' } }, serverStatus: { a: 'UP', b: 'UP' } }),
        svc('w@file',  { weighted: { services: [{ name: 'lb@file' }] } }),
    ]);
    const b = _sdBackendRoll(objs);
    assert.deepEqual([b.total, b.up, b.down, b.checked, b.composite], [2, 2, 0, 1, 1]);
    assert.equal(textOf(_sdBackendTxt(b, objs.length)), '2 of 2 backends up · 1 composite');
});

test('composites alone do not flip the services card to no health checks configured', () => {
    const objs = svcModel([
        svc('w@file', { weighted: { services: [] } }),
        svc('m@file', { mirroring: { service: 'a@file' } }),
    ]);
    const txt = textOf(_sdBackendTxt(_sdBackendRoll(objs), objs.length));
    assert.equal(txt, '2 composite');
    assert.ok(!txt.includes('no health check'), txt);
});

test('services with no health data at all still say so', () => {
    const objs = svcModel([svc('s@file')]);
    assert.equal(_sdBackendTxt(_sdBackendRoll(objs), objs.length), 'no health checks configured');
    assert.equal(_sdBackendTxt(_sdBackendRoll([]), 0), '');
});

test('the tally, the groups and the aria line all surface composites', () => {
    const objs = svcModel([
        svc('w@file',  { weighted: { services: [] } }),
        svc('lb@file', { loadBalancer: { healthCheck: { path: '/' } }, serverStatus: { a: 'UP' } }),
    ]);
    const card = _sdCardModel('service', objs, noOv, true);
    assert.equal(card.t.composite, 1);
    assert.equal(card.t.unchecked, 0);
    assert.equal(card.groups.composite.length, 1);
    assert.equal(card.groups.composite[0].name, 'w@file');
    assert.equal(_sdHealth(card.t), 'up', 'a healthy composite must not turn the card amber');
    assert.ok(_sdAria('services', 2, card.t).includes('1 composite'), _sdAria('services', 2, card.t));
});

test('a composite that does report server status is still judged on it', () => {
    const o = svcModel([svc('w@file', { weighted: { services: [] }, serverStatus: { a: 'DOWN' } })])[0];
    assert.equal(o.degraded, true);
    assert.equal(o.cell, 'warn');
});

test('the services card carries a composite chip so composites are visible, not silent', () => {
    assert.ok(/v\.t\.composite && _sdExc\('d-off', 'ph-bold ph-share-network'/.test(SRC),
        'the composite count needs its own neutral flag on the services card');
});

if (failures.length) {
    console.error(failures.length + ' of ' + ran + ' dashboard model checks failed:\n');
    failures.forEach(f => console.error('  ' + f + '\n'));
    process.exit(1);
}
console.log(ran + ' dashboard model checks passed');

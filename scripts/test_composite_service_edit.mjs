import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const src = readFileSync(join(root, 'static', 'js', 'services.js'), 'utf8');
const grab = name => 'function ' + name + '(' + src.split('function ' + name + '(')[1].split('\n}\n')[0] + '\n}';
const rowsFor = new Function(
    'const _ownedChildNames = new Set(); const _allServices = []; const _svcBareName = n => String(n).split("@")[0];\n'
    + 'const _SVC_SCHEME_RE = /^(https?|h2c):\\/\\//i;\n'
    + [grab('_compositeChildren'), grab('_svcUrlToRow'), grab('_svcChildToRow')].join('\n')
    + '\nreturn s => _compositeChildren(s).map(_svcChildToRow);')();

let fails = 0;
const check = (label, svc, want) => {
    const got = JSON.stringify(rowsFor(svc));
    const ok = got === JSON.stringify(want);
    console.log(`  ${ok ? 'ok  ' : 'FAIL'} ${label} -> ${got}${ok ? '' : ' (want ' + JSON.stringify(want) + ')'}`);
    if (!ok) fails++;
};

check('weighted keeps names and weights',
    { weighted: { services: [{ name: 'a-backend-1', weight: 3 }, { name: 'a-backend-2', weight: 1 }] } },
    [{ kind: 'service', name: 'a-backend-1', weight: '3' }, { kind: 'service', name: 'a-backend-2', weight: '1' }]);
check('weighted without weights defaults to 1',
    { weighted: { services: [{ name: 'a' }, { name: 'b' }] } },
    [{ kind: 'service', name: 'a', weight: 1 }, { kind: 'service', name: 'b', weight: 1 }]);
check('mirroring keeps the main service and mirror percents',
    { mirroring: { service: 'main', mirrors: [{ name: 'copy', percent: 10 }] } },
    [{ kind: 'service', name: 'main', weight: 1 }, { kind: 'service', name: 'copy', weight: '10' }]);
check('failover keeps primary and fallback',
    { failover: { service: 'primary', fallback: 'backup' } },
    [{ kind: 'service', name: 'primary', weight: 1 }, { kind: 'service', name: 'backup', weight: 1 }]);
check('provider-qualified names survive',
    { weighted: { services: [{ name: 'svc@docker', weight: 2 }] } },
    [{ kind: 'service', name: 'svc@docker', weight: '2' }]);

console.log(fails ? `\n${fails} check(s) failed` : '\nall checks passed');
process.exit(fails ? 1 : 0);

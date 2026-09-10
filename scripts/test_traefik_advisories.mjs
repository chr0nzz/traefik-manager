import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const src = readFileSync(join(root, 'static', 'js', 'settings.js'), 'utf8');

const listSrc = src.split('const TRAEFIK_ADVISORIES = ')[1]?.split('\n];')[0];
if (!listSrc) {
    console.error('could not find TRAEFIK_ADVISORIES in static/js/settings.js');
    process.exit(1);
}
const ADVISORIES = eval(listSrc + '\n]');

const parts = v => {
    const m = String(v || '').match(/(\d+)\.(\d+)\.(\d+)/);
    return m ? [+m[1], +m[2], +m[3]] : null;
};
const shown = v => {
    const hit = ADVISORIES.find(a => a.affected(parts(v)));
    return hit ? hit.id : null;
};

const GHSA = 'GHSA-rf44-j88r-hh8c';
const CVE  = 'CVE-2026-39858';
const CRIT = 'CVE-2026-88007';

const cases = [
    ['2.11.56', CRIT, 'last affected 2.x, critical HTTP/3 advisory outranks the rest'],
    ['2.11.57', null, 'patched 2.x'],
    ['3.7.12',  CRIT, 'last affected 3.x'],
    ['3.7.13',  null, 'patched 3.x'],
    ['3.8.0',   null, 'later minor is clean'],
    ['4.0.0',   null, 'later major is clean'],
    ['3.0.0',   CRIT, 'every 3.x before 3.7.13 is hit by the critical one'],
    ['2.10.9',  'CVE-2026-88009', '2.x below 2.11 is only hit by the rootless-target advisory'],
];

const only = (v, id) => ADVISORIES.filter(a => a.affected(parts(v))).map(a => a.id).includes(id);
const rangeChecks = [
    ['3.1.9',  'CVE-2026-88004', false, 'trailer bypass starts at 3.2.0'],
    ['3.2.0',  'CVE-2026-88004', true,  'trailer bypass starts at 3.2.0'],
    ['3.4.1',  'CVE-2026-88008', false, 'h2c smuggling starts at 3.4.2'],
    ['3.4.2',  'CVE-2026-88008', true,  'h2c smuggling starts at 3.4.2'],
    ['2.11.25','CVE-2026-88008', false, 'h2c smuggling starts at 2.11.26'],
    ['2.11.26','CVE-2026-88008', true,  'h2c smuggling starts at 2.11.26'],
    ['3.6.10', 'CVE-2026-88010', false, 'basic auth oracle starts at 3.6.11'],
    ['3.6.11', 'CVE-2026-88010', true,  'basic auth oracle starts at 3.6.11'],
    ['3.7.11', GHSA,             true,  'the dot-alias advisory still applies below 3.7.12'],
    ['3.7.12', GHSA,             false, 'the dot-alias advisory is fixed in 3.7.12'],
    ['3.6.13', CVE,              true,  'the underscore-alias CVE still applies below 3.6.14'],
];

let failed = 0;
for (const [version, want, why] of cases) {
    const got = shown(version);
    if (got !== want) {
        console.error(`FAIL v${version} (${why}): expected ${want || 'no advisory'}, got ${got || 'no advisory'}`);
        failed++;
    }
}

for (const [version, id, want, why] of rangeChecks) {
    const got = only(version, id);
    if (got !== want) {
        console.error(`FAIL v${version} ${id} (${why}): expected ${want ? 'affected' : 'clean'}, got ${got ? 'affected' : 'clean'}`);
        failed++;
    }
}

const crit = ADVISORIES.find(a => a.id === CRIT);
if (!crit) { console.error(`FAIL ${CRIT} is missing`); failed++; }
else if (!/3\.7\.13/.test(crit.fixedIn || '')) { console.error('FAIL the critical advisory must name v3.7.13'); failed++; }
if (ADVISORIES[0].id !== CRIT) { console.error('FAIL the critical advisory must be first so it wins the popup'); failed++; }

const ghsa = ADVISORIES.find(a => a.id === GHSA);
if (!ghsa) { console.error(`FAIL ${GHSA} is missing`); failed++; }
else {
    if (!ghsa.forwardAuthRelated) { console.error('FAIL the advisory must be flagged forwardAuthRelated'); failed++; }
    if (!/3\.7\.12/.test(ghsa.fixedIn || '')) { console.error('FAIL fixedIn must name v3.7.12'); failed++; }
    if (!/^https:\/\/github\.com\/traefik\/traefik\/security\/advisories\//.test(ghsa.url || '')) {
        console.error('FAIL advisory url must point at the GitHub advisory'); failed++;
    }
}

for (const a of ADVISORIES) {
    if (!/v\d+\.\d+\.\d+/.test(a.fixedIn || '')) {
        console.error(`FAIL ${a.id} has no fixedIn, so the UI cannot say which release to move to`);
        failed++;
    }
}

if (failed) { console.error(`${failed} advisory check(s) failed`); process.exit(1); }
console.log(`ok - ${cases.length} version boundaries, ${rangeChecks.length} range edges and the field checks`);

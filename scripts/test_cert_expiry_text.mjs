import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const src = readFileSync(join(root, 'static', 'js', 'certs.js'), 'utf8');

const certLeft = new Function(
    src.slice(src.indexOf('function _certLeft('), src.indexOf('async function _loadCertUsage')) +
    '; return _certLeft;')();

let fails = 0;
const check = (label, got, want) => {
    const ok = got === want;
    if (!ok) fails++;
    console.log(`  ${ok ? 'ok  ' : 'FAIL'} ${label}${ok ? '' : `  got ${JSON.stringify(got)} want ${JSON.stringify(want)}`}`);
};

console.log('days remaining');
check('a normal certificate counts down', certLeft(63), '63d left');
check('one day left', certLeft(1), '1d left');
check('expiring today', certLeft(0), 'expires today');
check('expired yesterday reads as words', certLeft(-1), 'expired yesterday');
check('expired a while ago', certLeft(-5), 'expired 5d ago');
check('no negative day count is ever shown', /-\d/.test(certLeft(-9)), false);

console.log('summary strip');
const verdict = src.slice(src.indexOf('function renderCertsVerdict()'), src.indexOf('function _certFlags('));
check('expired certificates are counted apart', verdict.includes("label: 'expired'"), true);
check('an expired certificate is not called expiring', verdict.includes('if (d < 0) { expired++; return; }'), true);
check('next expiry skips what already expired', verdict.indexOf('expired++; return;') < verdict.indexOf('if (next === null'), true);
check('the headline mentions expiry first', verdict.includes('certificate has expired'), true);
check('healthy only when nothing expired either', verdict.includes('if (!expired && !critical && !expiring)'), true);

console.log(fails ? `\n${fails} check(s) failed` : '\nall checks passed');
process.exit(fails ? 1 : 0);

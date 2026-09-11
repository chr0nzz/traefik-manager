import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const src = readFileSync(join(root, 'static', 'js', 'services.js'), 'utf8');
const fn = 'function _svcDurationShort(' + src.split('function _svcDurationShort(')[1].split('\n}\n')[0] + '\n}';
const short = new Function(fn + '\nreturn _svcDurationShort;')();

let fails = 0;
const check = (input, want) => {
    const got = short(input);
    console.log(`  ${got === want ? 'ok  ' : 'FAIL'} ${JSON.stringify(input)} -> ${JSON.stringify(got)}${got === want ? '' : ' (want ' + JSON.stringify(want) + ')'}`);
    if (got !== want) fails++;
};
check('1h0m0s', '1h');
check('0h5m0s', '5m');
check('1m30s', '1m30s');
check('10s', '10s');
check('3600s', '3600s');
check('500ms', '500ms');
check('2h30m0s', '2h30m');
check('0s', '0s');
check('', '');
check(undefined, '');
check('weird', 'weird');
console.log(fails ? `\n${fails} check(s) failed` : '\nall checks passed');
process.exit(fails ? 1 : 0);

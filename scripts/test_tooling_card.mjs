import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { i18nPrelude } from './i18n_test_prelude.mjs';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const src = readFileSync(join(root, 'static', 'js', 'crowdsec.js'), 'utf8');
const fn = 'function _atkCardAgents' + src.split('function _atkCardAgents')[1].split('\n}\n')[0] + '\n}';

const calls = [];
const stub = name => (...args) => { calls.push({ name, args }); return name; };
const api = new Function('rec', i18nPrelude() + `
const _atkBlindCard = a => { rec.push({ card: 'blind', ...a }); return 'blind'; };
const _atkCalmCard = (...a) => { rec.push({ card: 'calm', a }); return 'calm'; };
const _atkFilteredCard = (...a) => { rec.push({ card: 'filtered', a }); return 'filtered'; };
const _atkOwnFlag = () => '';
const ATK_MACHINE_NOTE = '';
const ATK_NEEDS_MACHINE = '';
${fn}
return d => { rec.length = 0; _atkCardAgents(d); return rec[0]; };
`)(calls);

const alert = o => ({ uas: [], uris: [], verbs: [], codes: [], ...o });
let fails = 0;
const check = (label, cond, detail) => {
    console.log(`  ${cond ? 'ok  ' : 'FAIL'} ${label}${detail ? '  -> ' + detail : ''}`);
    if (!cond) fails++;
};

const httpNoUa = api({ alertsOk: true, retained: 155, own: 0,
    alerts: [alert({ uris: ['/wp-login.php'], verbs: ['GET'], codes: ['404'] })] });
check('HTTP fired but no user agent is not blamed on scenarios',
      !/no HTTP scenario fired/.test(httpNoUa.sub || ''), httpNoUa.sub);
check('it names the access log instead', /access log/.test(httpNoUa.sub || ''), httpNoUa.sub);
check('it gives the Traefik fix', /User-Agent: keep/.test(httpNoUa.note || ''));

const sshOnly = api({ alertsOk: true, retained: 20, own: 0, alerts: [alert({})] });
check('no HTTP at all keeps the original explanation',
      /no HTTP scenario fired/.test(sshOnly.sub || ''), sshOnly.sub);

let reachedRealCard = false;
try {
    const withUa = api({ alertsOk: true, retained: 10, own: 0,
        alerts: [alert({ uas: ['curl/8.5.0'], uris: ['/'] })] });
    reachedRealCard = !withUa || withUa.card !== 'blind';
} catch (e) {
    reachedRealCard = true;
}
check('alerts carrying a user agent skip both blind branches', reachedRealCard);

if (fails) { console.error(`${fails} tooling card check(s) failed`); process.exit(1); }
console.log('ok - 5 tooling card checks');

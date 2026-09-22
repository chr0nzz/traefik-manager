import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { i18nPrelude } from './i18n_test_prelude.mjs';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const src = readFileSync(join(root, 'static', 'js', 'core.js'), 'utf8');

const labels = 'const NOTIF_CATEGORY_LABELS = ' + src.split('const NOTIF_CATEGORY_LABELS = ')[1].split('};')[0] + '};';
const fn     = 'function _renderNotifFilters()' + src.split('function _renderNotifFilters()')[1].split('\n}\n')[0] + '\n}';

const row = { style: {}, innerHTML: '' };
const tabDefs = 'const TAB_DEFS = ' + src.split('const TAB_DEFS = ')[1].split('\n];')[0] + '\n];';
const tabIcon = 'const _tabIcon = ' + src.split('const _tabIcon = ')[1].split(';')[0] + ';';
const icons = tabDefs + '\n' + tabIcon + '\nconst NOTIF_CATEGORY_ICONS = '
            + src.split('const NOTIF_CATEGORY_ICONS = ')[1].split('};')[0] + '};';
const harness = `
${i18nPrelude()}
${labels}
${icons}
let _notifData = [];
let _notifCatFilter = '';
const _esc = s => String(s);
const _jsArg = v => JSON.stringify(v == null ? '' : String(v));
const document = { getElementById: () => row };
${fn}
return {
    run(data, filter) { _notifData = data; _notifCatFilter = filter || ''; _renderNotifFilters(); return _notifCatFilter; },
};
`;
const api = new Function('row', harness)(row);

const chips = () => [...row.innerHTML.matchAll(/title="([A-Za-z]+) \((\d+)\)"/g)]
    .map(m => `${m[1]}:${m[2]}`).join('  ');
const iconsOf = () => [...row.innerHTML.matchAll(/<i class="ph-bold (ph-[a-z-]+)"/g)].map(m => m[1]).join(' ');

let fails = 0;
const check = (label, cond, detail) => {
    console.log(`  ${cond ? 'ok  ' : 'FAIL'} ${label}${detail ? '  -> ' + detail : ''}`);
    if (!cond) fails++;
};

api.run([{category:'security'},{category:'security'},{category:'crowdsec'},{category:'certs'}]);
check('chips carry label and count in the title', chips() === 'All:4  Security:2  Certificates:1  CrowdSec:1', chips());
check('row is visible', row.style.display === '');
check('every chip renders an icon', iconsOf() === 'ph-stack ph-lock-simple ph-shield-check ph-shield', iconsOf());
check('no visible text, so they stay on one row', !/>[A-Za-z]{2,}</.test(row.innerHTML));

api.run([{category:'config'},{category:'config'}]);
check('single category hides the row', row.style.display === 'none');

api.run([{}, {category:'agent'}]);
check('a missing category counts as Config', chips() === 'All:2  Config:1  Agents:1', chips());
check('agent uses the app robot icon', iconsOf().includes('ph-robot'), iconsOf());

const left = api.run([{category:'security'},{category:'certs'}], 'crowdsec');
check('a filter whose category vanished is cleared', left === '', JSON.stringify(left));

const kept = api.run([{category:'security'},{category:'certs'}], 'certs');
check('a filter still present is kept', kept === 'certs', JSON.stringify(kept));
check('the active chip is marked', row.innerHTML.includes('notif-cat-chip active'));

api.run([{category:'security'},{category:'certs'}]);
check('All leads the row and is active when nothing is filtered',
      /^<button class="notif-cat-chip active"[^>]*title="All/.test(row.innerHTML), row.innerHTML.slice(0, 70));
check('All clears the filter when clicked',
      /onclick="setNotifCategory\(("|&quot;){2}, event\)"/.test(row.innerHTML),
      row.innerHTML.match(/onclick="setNotifCategory[^"]*/)?.[0]);
const TABS = new Function(i18nPrelude() + tabDefs + '; return TAB_DEFS;')();
const ICONS = new Function(i18nPrelude() + icons + '; return NOTIF_CATEGORY_ICONS;')();
const tabIconOf = id => (TABS.find(t => t.id === id) || {}).icon;
check('certs uses the Certs tab icon', ICONS.certs === tabIconOf('certs'),
      `${ICONS.certs} vs tab ${tabIconOf('certs')}`);
check('crowdsec uses the CrowdSec tab icon', ICONS.crowdsec === tabIconOf('crowdsec'),
      `${ICONS.crowdsec} vs tab ${tabIconOf('crowdsec')}`);
check('certs and crowdsec are not the same icon', ICONS.certs !== ICONS.crowdsec);

const labelKeys = Object.keys(new Function(i18nPrelude() + labels + '; return NOTIF_CATEGORY_LABELS;')());
const iconKeys  = Object.keys(new Function(i18nPrelude() + icons  + '; return NOTIF_CATEGORY_ICONS;')());
const missing   = labelKeys.filter(k => !iconKeys.includes(k));
check('every category in the label map has an icon', missing.length === 0, missing.join(','));

if (fails) { console.error(`${fails} notification filter check(s) failed`); process.exit(1); }
console.log('ok - 15 notification filter checks');

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const src = readFileSync(join(root, 'static', 'js', 'core.js'), 'utf8');
const block = src.split('const REFRESH_SPIN_MIN_MS = 400;')[1].split("\ndocument.addEventListener('click'")[0];

function button(onclick, withIcon = true) {
    const icon = { classes: new Set(), classList: { add(c) { icon.classes.add(c); }, remove(c) { icon.classes.delete(c); } } };
    const btn = {
        disabled: false, onclick, icon,
        getAttribute(n) { return n === 'onclick' ? onclick : null; },
        querySelector(sel) { return sel === '.ph-arrows-clockwise' && withIcon ? icon : null; },
        closest() { return this; },
    };
    return btn;
}

const calls = [];
const harness = `
const REFRESH_SPIN_MIN_MS = 5;
${block}
return { _refreshSpinTarget, _spinRefreshButton };
`;
globalThis.refreshCrowdSecTab = (m) => { calls.push('cs:' + m); return new Promise(r => setTimeout(r, 20)); };
globalThis.refreshRoutemapTab = (f) => { calls.push('rm:' + f); };
globalThis.refreshLogs = () => { calls.push('logs'); throw new Error('boom'); };
const api = new Function(harness)();

let fails = 0;
const check = (label, cond, detail) => {
    console.log(`  ${cond ? 'ok  ' : 'FAIL'} ${label}${detail ? '  -> ' + detail : ''}`);
    if (!cond) fails++;
};

console.log('targets');
check('refresh call with icon is a target', api._refreshSpinTarget(button('refreshCrowdSecTab(true)')) !== null);
check('refresh call with argument is a target', api._refreshSpinTarget(button('refreshRoutemapTab(true)')) !== null);
check('no icon is not a target', api._refreshSpinTarget(button('refreshLogs()', false)) === null);
check('other handlers are not targets', api._refreshSpinTarget(button('openCsBanModal()')) === null);
check('compound code is not a target', api._refreshSpinTarget(button('refreshLogs(); alert(1)')) === null);
check('null element is safe', api._refreshSpinTarget(null) === null);

console.log('spin');
{
    const b = button('refreshCrowdSecTab(true)');
    const p = api._spinRefreshButton(b);
    check('disabled and spinning while running', b.disabled === true && b.icon.classes.has('animate-spin'));
    check('handler called with its argument', calls.includes('cs:true'));
    await p;
    await new Promise(r => setTimeout(r, 1));
    check('restored when the promise settles', b.disabled === false && !b.icon.classes.has('animate-spin'));
}
{
    const b = button('refreshRoutemapTab(true)');
    const t0 = Date.now();
    await api._spinRefreshButton(b);
    check('sync handler still spins for the minimum', Date.now() - t0 >= 4 && calls.includes('rm:true'));
}
{
    const b = button('refreshLogs()');
    await api._spinRefreshButton(b);
    await new Promise(r => setTimeout(r, 1));
    check('a throwing handler still restores the button', b.disabled === false && !b.icon.classes.has('animate-spin'));
}
console.log(fails ? `\n${fails} check(s) failed` : '\nall checks passed');
process.exit(fails ? 1 : 0);

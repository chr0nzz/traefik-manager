import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { i18nPrelude } from './i18n_test_prelude.mjs';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const src = readFileSync(join(root, 'static', 'js', 'tab-file_external.js'), 'utf8');
const start = src.indexOf('function _fileExternalEmptyState(');
const end = src.indexOf('async function refreshFileExternalTab(');
const { _fileExternalEmptyState } = new Function(i18nPrelude() + src.slice(start, end) + '\nreturn { _fileExternalEmptyState };')();

let failures = 0;
function check(label, cond) {
    if (!cond) { failures++; console.error('FAIL ' + label); }
}

const managed = _fileExternalEmptyState(2);
check('managed title', managed.includes('Every file provider route is managed here'));
check('managed count', managed.includes('reports 2 file provider routes'));
check('managed links to routes', managed.includes("switchTab('services')"));
const one = _fileExternalEmptyState(1);
check('singular', one.includes('reports 1 file provider route,'));
const none = _fileExternalEmptyState(0);
check('none title', none.includes('Traefik reports no file provider routes'));
check('none has no routes button', !none.includes("switchTab('services')"));

const body = src.slice(src.indexOf('if (_allFileExternalRoutes.length === 0) {'));
check('count is set to 0 before the empty state returns',
      body.indexOf("setTabCount('file_external', 0)") !== -1 &&
      body.indexOf("setTabCount('file_external', 0)") < body.indexOf('return;'));

if (failures) { console.error(failures + ' check(s) failed'); process.exit(1); }
console.log('file external empty state: all checks passed');

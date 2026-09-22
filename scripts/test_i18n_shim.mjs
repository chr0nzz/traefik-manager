import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const src = readFileSync(join(root, 'static', 'js', 'i18n.js'), 'utf8');

function load(catalog) {
    const window = {};
    const document = {
        documentElement: { lang: 'en' },
        getElementById: id => (id === 'i18n-catalog' && catalog !== undefined ? { textContent: catalog } : null),
    };
    new Function('window', 'document', src)(window, document);
    return window;
}

let failures = 0;
function check(label, got, want) {
    if (got !== want) {
        failures++;
        console.error(`FAIL ${label}: got ${JSON.stringify(got)}, want ${JSON.stringify(want)}`);
    }
}

const en = load(JSON.stringify({ locale: 'en', plural: { one: 0, other: 1 }, messages: {} }));
check('en passthrough', en.t('Save'), 'Save');
check('en params', en.t('Remove {name}', { name: 'api' }), 'Remove api');
check('en missing param kept', en.t('Remove {name}'), 'Remove {name}');
check('en plural one', en.tn('{n} route', '{n} routes', 1), '1 route');
check('en plural other', en.tn('{n} route', '{n} routes', 3), '3 routes');
check('en context', en.tc('status', 'Down'), 'Down');
check('en locale', en.TM_LOCALE, 'en');

const ru = load(JSON.stringify({
    locale: 'ru',
    plural: { one: 0, few: 1, many: 2 },
    messages: {
        'Save': 'Сохранить',
        'Remove {name}': 'Удалить {name}',
        'statusDown': 'Недоступен',
        '{n} route': ['{n} маршрут', '{n} маршрута', '{n} маршрутов'],
        'Half {n} item': ['', '{n} пункта', ''],
    },
}));
check('ru translated', ru.t('Save'), 'Сохранить');
check('ru params', ru.t('Remove {name}', { name: 'api' }), 'Удалить api');
check('ru context', ru.tc('status', 'Down'), 'Недоступен');
check('ru context falls back', ru.tc('other', 'Down'), 'Down');
check('ru one', ru.tn('{n} route', '{n} routes', 21), '21 маршрут');
check('ru few', ru.tn('{n} route', '{n} routes', 3), '3 маршрута');
check('ru many', ru.tn('{n} route', '{n} routes', 11), '11 маршрутов');
check('ru empty form falls back', ru.tn('Half {n} item', 'Half {n} items', 5), 'Half 5 items');
check('ru untranslated plural', ru.tn('{n} file', '{n} files', 2), '2 files');
check('ru extra params', ru.tn('{n} route', '{n} routes', 1, { n: 'ignored' }), 'ignored маршрут');
check('ru untranslated', ru.t('Cancel'), 'Cancel');
check('ru no html', ru.t('<b>{x}</b>', { x: '<i>' }), '<b><i></b>');

const broken = load('{not json');
check('broken catalogue falls back', broken.t('Save'), 'Save');
check('broken catalogue plural', broken.tn('{n} route', '{n} routes', 2), '2 routes');

const missing = load(undefined);
check('missing block falls back', missing.t('Save'), 'Save');

const unknownLocale = load(JSON.stringify({ locale: 'not a locale!', messages: { Save: 'X' } }));
check('invalid locale still translates', unknownLocale.t('Save'), 'X');
check('invalid locale plural', unknownLocale.tn('{n} route', '{n} routes', 2), '2 routes');

const hostile = load(JSON.stringify({
    locale: 'de',
    plural: { one: 0, other: 1 },
    messages: {
        'Remove {name}': '<img src=x onerror=alert(1)> {name} entfernen',
        'status\u0004Down': '"><svg onload=alert(1)>',
        '{n} route': ['<b>{n}</b> Route', '{n} Routen'],
    },
}));
check('th escapes the translation', hostile.th('Remove {name}', { name: 'api' }), '&lt;img src=x onerror=alert(1)&gt; api entfernen');
check('th escapes values', en.th('Remove {name}', { name: '<script>' }), 'Remove &lt;script&gt;');
check('th escapes quotes in values', en.th('Remove {name}', { name: `a"b'c` }), 'Remove a&quot;b&#39;c');
check('th passes marked markup', en.th('Remove {name}', { name: en.tmHtml('<code>api</code>') }), 'Remove <code>api</code>');
check('thc escapes', hostile.thc('status', 'Down'), '&quot;&gt;&lt;svg onload=alert(1)&gt;');
check('thn escapes the form', hostile.thn('{n} route', '{n} routes', 1), '&lt;b&gt;1&lt;/b&gt; Route');
check('thn plural', hostile.thn('{n} route', '{n} routes', 3), '3 Routen');
check('th untranslated', en.th('Save <now>'), 'Save &lt;now&gt;');

check('english ago seconds', en.tmAgo(12), '12s ago');
check('english ago minutes', en.tmAgo(125), '2m ago');
check('english ago hours', en.tmAgo(7300), '2h ago');
check('english ago days', en.tmAgo(200000), '2d ago');
check('english ago floor', en.tmAgo(30, 'minute'), '0m ago');
check('english ago zero', en.tmAgo(0), '0s ago');
check('german ago uses Intl', ru.tmAgo(7300) !== '2h ago', true);
check('number english', en.tmNumber(1234567), (1234567).toLocaleString());
check('number german locale', load(JSON.stringify({ locale: 'de', messages: {} })).tmNumber(1234567), '1.234.567');
check('date invalid', en.tmDate('not a date'), '');

const confirmSrc = readFileSync(join(root, 'static', 'js', 'static-config.js'), 'utf8');
const cStart = confirmSrc.indexOf('function _confirmWordFor(');
const cEnd = confirmSrc.indexOf('function _confirm(');
const { _confirmWordFor } = new Function(confirmSrc.slice(cStart, cEnd) + '\nreturn { _confirmWordFor };')();
check('one route asks for its name', _confirmWordFor('immich'), 'immich');
check('one item in a list asks for its name', _confirmWordFor(['  immich  ']), 'immich');
check('several ask for the count', _confirmWordFor(['a', 'b', 'c']), '3');
check('empty names are ignored', _confirmWordFor(['a', '', null]), 'a');

if (failures) {
    console.error(`${failures} i18n shim check(s) failed`);
    process.exit(1);
}
console.log('i18n shim: all checks passed');

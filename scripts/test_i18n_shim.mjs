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

if (failures) {
    console.error(`${failures} i18n shim check(s) failed`);
    process.exit(1);
}
console.log('i18n shim: all checks passed');

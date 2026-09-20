import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const src = readFileSync(join(root, 'static', 'js', 'routes.js'), 'utf8');
const start = src.indexOf('function _simpleHttpRule(');
const end = src.indexOf('function _applyHttpRuleToForm(');
if (start < 0 || end < 0) {
    console.error('could not find _simpleHttpRule and _splitHostRule in routes.js');
    process.exit(1);
}
const { _simpleHttpRule, _splitHostRule } = new Function(src.slice(start, end) + '\nreturn { _simpleHttpRule, _splitHostRule };')();

const DOMAINS = ['example.com', 'example.fr', 'sub.example.com'];
let failures = 0;

function saveUnchanged(rule, domains = DOMAINS) {
    const split = _splitHostRule(rule, domains);
    return split ? _simpleHttpRule(split.subdomain, split.domains) : rule.trim();
}

function check(label, got, want) {
    const a = JSON.stringify(got);
    const b = JSON.stringify(want);
    if (a !== b) {
        failures++;
        console.error(`FAIL ${label}: got ${a}, want ${b}`);
    }
}

const issue179 = 'Host(`example.com`) || Host(`www.example.com`) || Host(`example.fr`) || Host(`www.example.fr`)';
check('issue 179 opens in advanced', _splitHostRule(issue179, DOMAINS), null);
check('issue 179 saves unchanged', saveUnchanged(issue179), issue179);

const advanced = [
    'Host(`a.example.com`) || Host(`b.example.com`)',
    'Host(`app.example.com`) || Host(`app.other.org`)',
    'Host(`one.other.org`) || Host(`two.other.org`)',
    'Host(`a.b.example.com`)',
    'Host(`app.example.com`)||Host(`app.example.fr`)',
    'Host(`app.example.fr`) || Host(`app.example.com`) || Host(`app.example.fr`)',
    'Host(`app.example.com`) && PathPrefix(`/api`)',
    'HostRegexp(`^.+\\.example\\.com$`)',
    'PathPrefix(`/`)',
];
for (const rule of advanced) {
    check(`advanced: ${rule}`, _splitHostRule(rule, DOMAINS), null);
    check(`saves unchanged: ${rule}`, saveUnchanged(rule), rule);
}

const simple = [
    ['Host(`app.example.com`)', { subdomain: 'app', domains: ['example.com'] }],
    ['Host(`app.example.com`) || Host(`app.example.fr`)', { subdomain: 'app', domains: ['example.com', 'example.fr'] }],
    ['Host(`app.example.fr`) || Host(`app.example.com`)', { subdomain: 'app', domains: ['example.fr', 'example.com'] }],
    ['Host(`example.com`)', { subdomain: '', domains: ['example.com'] }],
    ['Host(`example.com`) || Host(`example.fr`)', { subdomain: '', domains: ['example.com', 'example.fr'] }],
    ['Host(`app.sub.example.com`)', { subdomain: 'app', domains: ['sub.example.com'] }],
    ['Host(`app.other.org`)', { subdomain: 'app.other.org', domains: [] }],
    ['  Host(`app.example.com`)  ', { subdomain: 'app', domains: ['example.com'] }],
];
for (const [rule, want] of simple) {
    check(`simple: ${rule}`, _splitHostRule(rule, DOMAINS), want);
    check(`saves unchanged: ${rule}`, saveUnchanged(rule), rule.trim());
}

check('no known domains, one host', _splitHostRule('Host(`app.example.com`)', []), { subdomain: 'app.example.com', domains: [] });
check('no known domains, two hosts', _splitHostRule(issue179, []), null);
check('empty rule', _splitHostRule('', DOMAINS), null);

check('rebuild with dotted subdomain', _simpleHttpRule('app.other.org', ['example.com']), 'Host(`app.other.org`)');
check('rebuild apex', _simpleHttpRule('', ['example.com', 'example.fr']), 'Host(`example.com`) || Host(`example.fr`)');
check('rebuild subdomain', _simpleHttpRule('www', ['example.com']), 'Host(`www.example.com`)');

function between(from, to) {
    const a = src.indexOf(from);
    const b = src.indexOf(to, a);
    if (a < 0 || b < 0) {
        console.error(`could not find ${from} in routes.js`);
        process.exit(1);
    }
    return src.slice(a, b);
}

function fakeElement() {
    const classes = new Set();
    return {
        value: '', disabled: false, textContent: '', style: {},
        classList: { toggle: (c, on) => (on ? classes.add(c) : classes.delete(c)), contains: c => classes.has(c) },
    };
}

const ids = ['httpModeSimpleBtn', 'httpModeAdvancedBtn', 'httpSimpleFields', 'httpAdvancedFields',
    'httpSimpleLossNote', 'httpRule', 'subdomain', 'domainSelect'];
const els = Object.fromEntries(ids.map(id => [id, fakeElement()]));
const form = new Function('document', 'window', '_domainsForForm', '_updateRouteModalForAgent', '_initDomainChips',
    src.slice(start, end)
    + between('let _httpRuleFitsSimple', 'function _applyServiceTypeNotice(')
    + '\nfunction requestAnimationFrame(fn) { fn(); }\n'
    + between('function _applyHttpRuleToForm(', 'async function cloneRoute(')
    + '\nreturn { setHttpRuleMode, _applyHttpRuleToForm, typeInAdvanced() { _httpRuleAdvTouched = true; } };'
)({ getElementById: id => els[id] || null }, {}, () => DOMAINS, () => {}, () => {});

const mode = () => (els.httpModeAdvancedBtn.classList.contains('active-http') ? 'advanced' : 'simple');
const sent = () => (els.httpRule.disabled ? null : els.httpRule.value);
const warned = () => els.httpSimpleLossNote.style.display !== 'none';

form._applyHttpRuleToForm(issue179);
check('issue 179 opens advanced and sends the rule as is', [mode(), sent()], ['advanced', issue179]);
form.setHttpRuleMode('simple');
check('switching to simple keeps the rule, sends nothing and warns', [els.httpRule.value, sent(), warned()], [issue179, null, true]);
form.setHttpRuleMode('advanced');
form.setHttpRuleMode('simple');
form.setHttpRuleMode('advanced');
check('advanced to simple and back leaves the rule untouched', [sent(), warned()], [issue179, false]);

form._applyHttpRuleToForm('Host(`app.example.com`)');
check('a simple rule opens simple and sends only the simple fields', [mode(), sent(), warned()], ['simple', null, false]);
els.subdomain.value = 'web';
form.setHttpRuleMode('advanced');
check('advanced follows the simple fields until typed in', sent(), 'Host(`web.example.com`)');
els.httpRule.value = 'Host(`web.example.com`) && PathPrefix(`/api`)';
form.typeInAdvanced();
form.setHttpRuleMode('simple');
form.setHttpRuleMode('advanced');
check('a typed advanced rule survives a trip through simple', sent(), 'Host(`web.example.com`) && PathPrefix(`/api`)');

if (failures) {
    console.error(`${failures} host rule check(s) failed`);
    process.exit(1);
}
console.log('host rule split: all checks passed');

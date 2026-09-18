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

if (failures) {
    console.error(`${failures} host rule check(s) failed`);
    process.exit(1);
}
console.log('host rule split: all checks passed');

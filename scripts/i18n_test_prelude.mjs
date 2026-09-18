import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const src = readFileSync(join(root, 'static', 'js', 'i18n.js'), 'utf8');

export function i18nPrelude() {
    return `const __tmI18n = {};
(function (window, document) {
${src}
})(__tmI18n, { getElementById: () => null, documentElement: { lang: 'en' } });
const { t, tn, tc, th, thn, thc, tmHtml, tmNumber, tmDate, tmAgo, tmEscapeHtml } = __tmI18n;
`;
}

import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as acorn from 'acorn';

const ROOT = join(fileURLToPath(new URL('.', import.meta.url)), '..', '..');
const KEYWORDS = {
    t: { msgid: 0 },
    tn: { msgid: 0, plural: 1 },
    tc: { context: 0, msgid: 1 },
};

function walkFiles(dir, suffix) {
    const out = [];
    for (const name of readdirSync(dir).sort()) {
        const full = join(dir, name);
        if (statSync(full).isDirectory()) out.push(...walkFiles(full, suffix));
        else if (name.endsWith(suffix)) out.push(full);
    }
    return out;
}

function maskJinja(text) {
    return text.replace(/\{\{[\s\S]*?\}\}|\{%[\s\S]*?%\}|\{#[\s\S]*?#\}/g, m => {
        const inner = m.replace(/[^\n]/g, ' ');
        return m.startsWith('{{') ? 'null' + inner.slice(4) : inner;
    });
}

function inlineScripts(html) {
    const blocks = [];
    const re = /<script\b([^>]*)>([\s\S]*?)<\/script\s*>/gi;
    let m;
    while ((m = re.exec(html))) {
        const attrs = m[1];
        if (/\bsrc\s*=/i.test(attrs)) continue;
        const type = /\btype\s*=\s*["']?([^"'\s>]+)/i.exec(attrs);
        if (type && !/javascript|module/i.test(type[1])) continue;
        const start = m.index + m[0].indexOf('>') + 1;
        const line = html.slice(0, start).split('\n').length;
        blocks.push({ code: maskJinja(m[2]), line });
    }
    return blocks;
}

function literal(node) {
    if (!node) return null;
    if (node.type === 'Literal' && typeof node.value === 'string') return node.value;
    if (node.type === 'TemplateLiteral' && node.expressions.length === 0) return node.quasis[0].value.cooked;
    return null;
}

function visit(node, fn) {
    if (!node || typeof node.type !== 'string') return;
    fn(node);
    for (const key of Object.keys(node)) {
        if (key === 'loc' || key === 'start' || key === 'end') continue;
        const value = node[key];
        if (Array.isArray(value)) value.forEach(v => visit(v, fn));
        else if (value && typeof value.type === 'string') visit(value, fn);
    }
}

function extract(code, file, lineOffset, messages, errors) {
    let ast;
    try {
        ast = acorn.parse(code, { ecmaVersion: 'latest', sourceType: 'script', locations: true, allowHashBang: true });
    } catch (e) {
        errors.push(`${file}:${(e.loc ? e.loc.line : 1) + lineOffset}: cannot parse: ${e.message}`);
        return;
    }
    visit(ast, node => {
        if (node.type !== 'CallExpression' || node.callee.type !== 'Identifier') return;
        const spec = KEYWORDS[node.callee.name];
        if (!spec) return;
        const line = node.loc.start.line + lineOffset;
        const where = `${file}:${line}`;
        const needed = Math.max(...Object.values(spec)) + 1;
        if (node.arguments.length < needed) {
            errors.push(`${where}: ${node.callee.name}() needs ${needed} string arguments`);
            return;
        }
        const entry = { context: null, msgid: null, plural: null, location: where };
        for (const [role, index] of Object.entries(spec)) {
            const value = literal(node.arguments[index]);
            if (value === null) {
                errors.push(`${where}: ${node.callee.name}() argument ${index + 1} must be a plain string literal`);
                return;
            }
            entry[role] = value;
        }
        if (!entry.msgid) {
            errors.push(`${where}: ${node.callee.name}() has an empty message`);
            return;
        }
        messages.push(entry);
    });
}

export function run(root = ROOT) {
    const messages = [];
    const errors = [];
    const rel = f => relative(root, f).split(sep).join('/');
    for (const file of walkFiles(join(root, 'static', 'js'), '.js')) {
        extract(readFileSync(file, 'utf8'), rel(file), 0, messages, errors);
    }
    for (const file of walkFiles(join(root, 'templates'), '.html')) {
        for (const block of inlineScripts(readFileSync(file, 'utf8'))) {
            extract(block.code, rel(file), block.line - 1, messages, errors);
        }
    }
    return { messages, errors };
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
    const root = process.argv[2] || ROOT;
    process.stdout.write(JSON.stringify(run(root)));
}

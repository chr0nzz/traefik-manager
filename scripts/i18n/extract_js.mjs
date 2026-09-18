import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as acorn from 'acorn';

const ROOT = join(fileURLToPath(new URL('.', import.meta.url)), '..', '..');
const KEYWORDS = {
    t: { msgid: 0 },
    tn: { msgid: 0, plural: 1 },
    tc: { context: 0, msgid: 1 },
    th: { msgid: 0 },
    thn: { msgid: 0, plural: 1 },
    thc: { context: 0, msgid: 1 },
};
const TEXT_ONLY = new Set(['t', 'tn', 'tc']);
const PARAMS_AT = { t: 1, th: 1, tc: 2, thc: 2, tn: 3, thn: 3 };

function paramProblem(node, entry) {
    const wanted = new Set();
    for (const text of [entry.msgid, entry.plural || '']) {
        for (const m of text.matchAll(/\{(\w+)\}/g)) wanted.add(m[1]);
    }
    const given = new Set(PARAMS_AT[node.callee.name] === 3 ? ['n'] : []);
    const arg = node.arguments[PARAMS_AT[node.callee.name]];
    if (arg) {
        if (arg.type !== 'ObjectExpression') return null;
        for (const prop of arg.properties) {
            if (prop.type !== 'Property' || prop.computed) return null;
            given.add(prop.key.type === 'Identifier' ? prop.key.name : String(prop.key.value));
        }
    }
    const missing = [...wanted].filter(k => !given.has(k));
    const unused = [...given].filter(k => k !== 'n' && !wanted.has(k));
    if (missing.length) return `has no value for ${missing.map(k => '{' + k + '}').join(', ')}`;
    if (unused.length) return `passes ${unused.join(', ')} but the message has no such placeholder`;
    return null;
}
const ESCAPERS = new Set(['_esc', 'tmEscapeHtml', 'escapeHtml']);
const HTML_PROPS = new Set(['innerHTML', 'outerHTML']);

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

function visit(node, fn, parents = []) {
    if (!node || typeof node.type !== 'string') return;
    fn(node, parents);
    const next = parents.concat([node]);
    for (const key of Object.keys(node)) {
        if (key === 'loc' || key === 'start' || key === 'end') continue;
        const value = node[key];
        if (Array.isArray(value)) value.forEach(v => visit(v, fn, next));
        else if (value && typeof value.type === 'string') visit(value, fn, next);
    }
}

function htmlString(node) {
    if (!node) return false;
    if (node.type === 'Literal' && typeof node.value === 'string') return /<[a-zA-Z\/!]/.test(node.value);
    if (node.type === 'TemplateLiteral') return node.quasis.some(q => /<[a-zA-Z\/!]/.test(q.value.cooked || ''));
    if (node.type === 'BinaryExpression' && node.operator === '+') return htmlString(node.left) || htmlString(node.right);
    return false;
}

const HTML_ARGS = { _lgSub: [0, 1], _sdSubParts: [0, 1], _sdSubPlain: [0], _sdSubOffender: [1] };

function htmlSink(parents, node) {
    let child = node;
    for (let i = parents.length - 1; i >= 0; i--) {
        const p = parents[i];
        if (p.type === 'CallExpression') {
            const name = p.callee.type === 'Identifier' ? p.callee.name
                : p.callee.type === 'MemberExpression' && !p.callee.computed ? p.callee.property.name : '';
            if (ESCAPERS.has(name)) return false;
            if (name === 'insertAdjacentHTML' || name === 'write' || name === 'writeln') return true;
            if (HTML_ARGS[name] && child && HTML_ARGS[name].includes(p.arguments.indexOf(child))) return true;
            if (child && p.callee === child) { child = p; continue; }
            return false;
        }
        if (p.type === 'TemplateLiteral') return htmlString(p);
        if (p.type === 'BinaryExpression' && p.operator === '+') {
            if (htmlString(p)) return true;
            child = p;
            continue;
        }
        if (p.type === 'AssignmentExpression') {
            const left = p.left;
            return left.type === 'MemberExpression' && !left.computed && HTML_PROPS.has(left.property.name);
        }
        if (p.type === 'ConditionalExpression' || p.type === 'LogicalExpression' || p.type === 'ParenthesizedExpression') {
            child = p;
            continue;
        }
        if (/Function|Statement|Declaration|Property|ArrayExpression|ObjectExpression/.test(p.type)) return false;
        child = p;
    }
    return false;
}

const CODE_PROPS = new Set(['className', 'id', 'name', 'type', 'href', 'src', 'value']);
const CODE_CALLS = new Set(['add', 'remove', 'toggle', 'replace', 'setProperty', 'getElementById', 'querySelector', 'querySelectorAll']);

function codeSink(node, parents) {
    let child = node;
    for (let i = parents.length - 1; i >= 0; i--) {
        const p = parents[i];
        if (p.type === 'ConditionalExpression' || p.type === 'LogicalExpression' || p.type === 'ParenthesizedExpression') {
            if (p.type === 'ConditionalExpression' && p.test === child) return false;
            child = p;
            continue;
        }
        if (p.type === 'AssignmentExpression' && p.right === child) {
            const left = p.left;
            if (left.type !== 'MemberExpression' || left.computed) return false;
            if (CODE_PROPS.has(left.property.name)) return true;
            const owner = left.object;
            return owner.type === 'MemberExpression' && !owner.computed && ['style', 'dataset'].includes(owner.property.name);
        }
        if (p.type === 'CallExpression' && p.arguments.includes(child)) {
            return p.callee.type === 'MemberExpression' && !p.callee.computed && CODE_CALLS.has(p.callee.property.name);
        }
        return false;
    }
    return false;
}

function bindings(pattern, out) {
    if (!pattern) return out;
    if (pattern.type === 'Identifier') out.add(pattern.name);
    else if (pattern.type === 'ObjectPattern') pattern.properties.forEach(q => bindings(q.value || q.argument, out));
    else if (pattern.type === 'ArrayPattern') pattern.elements.forEach(e => bindings(e, out));
    else if (pattern.type === 'AssignmentPattern') bindings(pattern.left, out);
    else if (pattern.type === 'RestElement') bindings(pattern.argument, out);
    return out;
}

function declares(scope, name) {
    const names = new Set();
    let body = [];
    if (/Function/.test(scope.type)) {
        scope.params.forEach(p => bindings(p, names));
        if (scope.body.type === 'BlockStatement') body = scope.body.body;
    } else if (scope.type === 'BlockStatement' || scope.type === 'StaticBlock') {
        body = scope.body;
    } else if (scope.type === 'CatchClause') {
        bindings(scope.param, names);
    } else if (/^For/.test(scope.type)) {
        const init = scope.init || scope.left;
        if (init && init.type === 'VariableDeclaration') init.declarations.forEach(d => bindings(d.id, names));
    }
    for (const stmt of body) {
        if (stmt.type === 'VariableDeclaration') stmt.declarations.forEach(d => bindings(d.id, names));
        if ((stmt.type === 'FunctionDeclaration' || stmt.type === 'ClassDeclaration') && stmt.id) names.add(stmt.id.name);
    }
    return names.has(name);
}

function extract(code, file, lineOffset, messages, errors) {
    let ast;
    try {
        ast = acorn.parse(code, { ecmaVersion: 'latest', sourceType: 'script', locations: true, allowHashBang: true });
    } catch (e) {
        errors.push(`${file}:${(e.loc ? e.loc.line : 1) + lineOffset}: cannot parse: ${e.message}`);
        return;
    }
    visit(ast, (node, parents) => {
        if (node.type !== 'CallExpression' || node.callee.type !== 'Identifier') return;
        const spec = KEYWORDS[node.callee.name];
        if (!spec) return;
        const line = node.loc.start.line + lineOffset;
        const where = `${file}:${line}`;
        if (parents.some(p => declares(p, node.callee.name))) {
            errors.push(`${where}: ${node.callee.name}() is hidden by a local variable of the same name; rename the variable`);
            return;
        }
        if (codeSink(node, parents)) {
            errors.push(`${where}: ${node.callee.name}() is used as a style, class, id or selector, which must stay untranslated`);
            return;
        }
        if (TEXT_ONLY.has(node.callee.name) && htmlSink(parents, node)) {
            errors.push(`${where}: ${node.callee.name}() is placed into HTML unescaped; use th()${node.callee.name === 't' ? '' : node.callee.name === 'tn' ? ' as thn()' : ' as thc()'} or wrap it in _esc()`);
            return;
        }
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
        const mismatch = paramProblem(node, entry);
        if (mismatch) {
            errors.push(`${where}: ${node.callee.name}() ${mismatch}`);
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

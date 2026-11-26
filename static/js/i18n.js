(function () {
    let data = {};
    try {
        const el = document.getElementById('i18n-catalog');
        data = JSON.parse(el ? el.textContent : '{}') || {};
    } catch (e) {
        data = {};
    }
    const messages = data.messages || {};
    const pluralIndex = data.plural || { one: 0, other: 1 };
    const locale = data.locale || document.documentElement.lang || 'en';
    let rules;
    try {
        rules = new Intl.PluralRules(locale);
    } catch (e) {
        rules = new Intl.PluralRules('en');
    }
    const CONTEXT = '';

    function escapeHtml(value) {
        return String(value == null ? '' : value)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    const TECHNICAL_PARAM = /^(code|codes|status|statuses|port|ports|version|ver|year|ip|addr|address|host|http|tls|pid|id)$/i;
    const NUMERIC_TEXT = /^-?[\d.,\u00a0\u202f\u066b\u066c]+$/;
    let nativeDigitMap;

    function nativeDigits() {
        if (nativeDigitMap === undefined) {
            nativeDigitMap = null;
            try {
                const f = new Intl.NumberFormat(formatLocale(), { useGrouping: false });
                const digits = '0123456789'.split('').map(d => f.format(Number(d)));
                if (digits.join('') !== '0123456789' && digits.every(d => d.length === 1)) nativeDigitMap = digits;
            } catch (e) {
                nativeDigitMap = null;
            }
        }
        return nativeDigitMap;
    }

    function tmDigits(value) {
        const text = String(value == null ? '' : value);
        const map = nativeDigits();
        return map ? text.replace(/[0-9]/g, d => map[d]) : text;
    }

    function fillValue(key, value) {
        if (TECHNICAL_PARAM.test(key)) return String(value);
        if (typeof value === 'number' || (typeof value === 'string' && NUMERIC_TEXT.test(value))) return tmDigits(value);
        return String(value);
    }

    function fill(text, params) {
        if (!params) return text;
        return text.replace(/\{(\w+)\}/g, (match, key) =>
            Object.prototype.hasOwnProperty.call(params, key) ? fillValue(key, params[key]) : match);
    }

    function lookup(key) {
        const value = messages[key];
        return typeof value === 'string' && value ? value : null;
    }

    function pluralForm(singular, plural, n) {
        const forms = messages[singular];
        if (Array.isArray(forms)) {
            const index = pluralIndex[rules.select(n)];
            if (index !== undefined && forms[index]) return forms[index];
        }
        return n === 1 ? singular : plural;
    }

    function htmlParams(params) {
        const out = {};
        for (const key of Object.keys(params || {})) {
            const value = params[key];
            out[key] = value && typeof value === 'object' && typeof value.__html === 'string'
                ? value.__html : escapeHtml(value);
        }
        return out;
    }

    function t(msgid, params) {
        return fill(lookup(msgid) || msgid, params);
    }

    function tc(context, msgid, params) {
        return fill(lookup(context + CONTEXT + msgid) || msgid, params);
    }

    function tn(singular, plural, n, params) {
        return fill(pluralForm(singular, plural, n), Object.assign({ n: n }, params || {}));
    }

    function th(msgid, params) {
        return fill(escapeHtml(lookup(msgid) || msgid), htmlParams(params));
    }

    function thc(context, msgid, params) {
        return fill(escapeHtml(lookup(context + CONTEXT + msgid) || msgid), htmlParams(params));
    }

    function thn(singular, plural, n, params) {
        return fill(escapeHtml(pluralForm(singular, plural, n)), htmlParams(Object.assign({ n: n }, params || {})));
    }

    let sources = null;

    function tmSources(text) {
        if (!sources) {
            sources = {};
            for (const key of Object.keys(messages)) {
                const value = messages[key];
                const msgid = key.slice(key.indexOf(CONTEXT) + 1);
                for (const form of Array.isArray(value) ? value : [value]) {
                    if (typeof form === 'string' && form) (sources[form] = sources[form] || []).push(msgid);
                }
            }
        }
        const s = String(text == null ? '' : text);
        return [s].concat(sources[s] || []);
    }

    function tmHtml(markup) {
        return { __html: String(markup == null ? '' : markup) };
    }

    function formatLocale() {
        return locale === 'en' ? undefined : locale;
    }

    function tmNumber(value, options) {
        try {
            return new Intl.NumberFormat(formatLocale(), options).format(Number(value || 0));
        } catch (e) {
            return String(value);
        }
    }

    function tmDate(value, options) {
        const date = value instanceof Date ? value : new Date(value);
        if (isNaN(date.getTime())) return '';
        try {
            return new Intl.DateTimeFormat(formatLocale(), options).format(date);
        } catch (e) {
            return date.toLocaleString();
        }
    }

    function tmList(items, type) {
        const list = (items || []).map(String);
        try {
            return new Intl.ListFormat(formatLocale(), { style: 'long', type: type || 'conjunction' }).format(list);
        } catch (e) {
            return list.join(', ');
        }
    }

    const UNITS = [['day', 86400, 'd'], ['hour', 3600, 'h'], ['minute', 60, 'm'], ['second', 1, 's']];

    function tmAgo(seconds, smallest) {
        const s = Math.max(0, Math.floor(Number(seconds) || 0));
        const floor = smallest || 'second';
        let pick = UNITS[UNITS.length - 1];
        for (const unit of UNITS) {
            pick = unit;
            if (s >= unit[1] || unit[0] === floor) break;
        }
        const amount = Math.floor(s / pick[1]);
        if (locale === 'en') return amount + pick[2] + ' ago';
        try {
            return new Intl.RelativeTimeFormat(locale, { style: 'narrow', numeric: 'always' }).format(-amount, pick[0]);
        } catch (e) {
            return amount + pick[2] + ' ago';
        }
    }

    window.TM_LOCALE = locale;
    window.t = t;
    window.tc = tc;
    window.tn = tn;
    window.th = th;
    window.thc = thc;
    window.thn = thn;
    window.tmHtml = tmHtml;
    window.tmEscapeHtml = escapeHtml;
    window.tmNumber = tmNumber;
    window.tmDigits = tmDigits;
    window.tmDate = tmDate;
    window.tmAgo = tmAgo;
    window.tmList = tmList;
    window.tmSources = tmSources;
})();

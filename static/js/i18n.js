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

    function fill(text, params) {
        if (!params) return text;
        return text.replace(/\{(\w+)\}/g, (match, key) =>
            Object.prototype.hasOwnProperty.call(params, key) ? String(params[key]) : match);
    }

    function lookup(key) {
        const value = messages[key];
        return typeof value === 'string' && value ? value : null;
    }

    function t(msgid, params) {
        return fill(lookup(msgid) || msgid, params);
    }

    function tc(context, msgid, params) {
        return fill(lookup(context + '' + msgid) || msgid, params);
    }

    function tn(singular, plural, n, params) {
        const values = Object.assign({ n: n }, params || {});
        const forms = messages[singular];
        if (Array.isArray(forms)) {
            const index = pluralIndex[rules.select(n)];
            if (index !== undefined && forms[index]) return fill(forms[index], values);
        }
        return fill(n === 1 ? singular : plural, values);
    }

    window.TM_LOCALE = locale;
    window.t = t;
    window.tc = tc;
    window.tn = tn;
})();

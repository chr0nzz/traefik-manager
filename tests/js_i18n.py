import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def i18n_prelude():
    with open(os.path.join(ROOT, 'static', 'js', 'i18n.js'), encoding='utf-8') as fh:
        src = fh.read()
    return ('const __tmI18n = {};\n'
            '(function (window, document) {\n' + src + '\n'
            "})(__tmI18n, { getElementById: () => null, documentElement: { lang: 'en' } });\n"
            'const { t, tn, tc, th, thn, thc, tmHtml, tmNumber, tmDate, tmAgo, tmEscapeHtml } = __tmI18n;\n')

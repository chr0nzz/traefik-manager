import argparse
import os
import re
import sys

from babel.messages.catalog import Catalog
from babel.messages.mofile import write_mo
from babel.messages.pofile import write_po

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tmi18n  # noqa: E402

PSEUDO_LOCALE = 'eo'
OPEN, CLOSE = '⟦', '⟧'
ACCENTS = dict(zip(
    'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ',
    'åƀçđéƒĝĥîĵķļɱñöþǫŕšţûṽŵẋýžÅƁÇĐÉƑĜĤÎĴĶĻṀÑÖÞǪŔŠŢÛṼŴẊÝŽ'))
KEEP_RE = re.compile('|'.join((tmi18n.URL_RE.pattern.replace('(?i)', ''), r'\{[^{}]*\}', tmi18n.PRINTF_RE.pattern,
                               r'&[a-z]+;')), re.I)


def pseudo(text):
    out, last = [], 0
    for m in KEEP_RE.finditer(text):
        out.append(''.join(ACCENTS.get(ch, ch) for ch in text[last:m.start()]))
        out.append(m.group(0))
        last = m.end()
    out.append(''.join(ACCENTS.get(ch, ch) for ch in text[last:]))
    body = ''.join(out)
    lead = body[:len(body) - len(body.lstrip())]
    trail = body[len(body.rstrip()):]
    core = body.strip()
    if not core:
        return body
    gap = ' ' if tmi18n.URL_RE.search(core.rsplit(' ', 1)[-1]) else ''
    return lead + OPEN + core + gap + CLOSE + trail


def build(out_dir, pot_path=tmi18n.POT_PATH, identifier=PSEUDO_LOCALE):
    template = tmi18n.read_catalog(pot_path)
    catalog = Catalog(locale=identifier, project=tmi18n.PROJECT, fuzzy=False)
    for message in template:
        if not message.id:
            continue
        if isinstance(message.id, (list, tuple)):
            string = [pseudo(message.id[0])] + [pseudo(message.id[1])] * (catalog.num_plurals - 1)
        else:
            string = pseudo(message.id)
        catalog.add(message.id, string, context=message.context, locations=message.locations,
                    auto_comments=message.auto_comments, flags=message.flags)
    target = os.path.join(out_dir, identifier, 'LC_MESSAGES')
    os.makedirs(target, exist_ok=True)
    with open(os.path.join(target, 'messages.po'), 'wb') as fh:
        write_po(fh, catalog, width=0)
    with open(os.path.join(target, 'messages.mo'), 'wb') as fh:
        write_mo(fh, catalog)
    with open(os.path.join(out_dir, 'LINGUAS'), 'w', encoding='utf-8') as fh:
        fh.write(identifier + '\n')
    return os.path.join(target, 'messages.po')


def main():
    parser = argparse.ArgumentParser(description='Build a pseudo-translated catalogue that marks every translated string.')
    parser.add_argument('out_dir', help='directory to write the catalogue to, never locale/')
    args = parser.parse_args()
    out = os.path.abspath(args.out_dir)
    if out == os.path.abspath(tmi18n.LOCALE_DIR) or out.startswith(os.path.abspath(tmi18n.LOCALE_DIR) + os.sep):
        parser.error('the pseudo catalogue must not be written into locale/, it is never shipped')
    print(build(out))


if __name__ == '__main__':
    main()

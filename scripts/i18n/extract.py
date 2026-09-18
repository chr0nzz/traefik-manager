import argparse
import sys

import tmi18n


def main(argv=None):
    parser = argparse.ArgumentParser(description='Rebuild locale/messages.pot and update every catalogue.')
    parser.add_argument('--init', action='append', default=[], metavar='LOCALE',
                        help='create a catalogue for this locale, for example de or zh_Hans')
    parser.add_argument('--starter', action='store_true', help='create the starter catalogues')
    args = parser.parse_args(argv)
    init = list(args.init) + (list(tmi18n.STARTER_LOCALES) if args.starter else [])
    problems = tmi18n.update_catalogues(init=init)
    for problem in problems:
        print(problem, file=sys.stderr)
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())

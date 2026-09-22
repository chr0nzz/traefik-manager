import argparse
import sys

import tmi18n


def main(argv=None):
    parser = argparse.ArgumentParser(description='Check the translation catalogues and the code that uses them.')
    parser.add_argument('--require-tools', action='store_true',
                        help='fail when msgfmt or pofilter is missing instead of skipping them')
    args = parser.parse_args(argv)
    problems = tmi18n.check_all(require_tools=args.require_tools)
    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        print(f'{len(problems)} translation problem(s)', file=sys.stderr)
        return 1
    print('translations: all checks passed')
    return 0


if __name__ == '__main__':
    sys.exit(main())

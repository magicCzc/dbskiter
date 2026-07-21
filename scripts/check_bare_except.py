"""Pre-commit hook: check for bare except clauses."""
import re
import sys


def main():
    ok = True
    for path in sys.argv[1:]:
        with open(path, encoding='utf-8') as f:
            for i, line in enumerate(f, 1):
                if re.match(r'^\s*except\s*:', line):
                    print(f'{path}:{i}: bare except: -- use except Exception: instead')
                    ok = False
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
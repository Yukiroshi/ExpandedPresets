#!/usr/bin/env python3
"""
Usage:
  script.py [check] [ATTR] [files...]   Report values that need fixing (read-only)
  script.py fix ATTR [files...]         Fix them automatically

ATTR is one of: display_value, name, text, all
(check defaults to all; fix requires it.)

With no files, ExpandedPresets.xml next to this script is used.
"""
import re
import sys
from dataclasses import dataclass
from pathlib import Path

CHECKED_ATTRS = ('display_value', 'name', 'text')
CHOICES = CHECKED_ATTRS + ('all',)

ATTR_RE = re.compile(
    r'(?<![\w.-])'                                   # don't match inside e.g. display_name=
    r'(?P<head>(?:[A-Za-z_][\w.-]*\.)?(?P<attr>' + '|'.join(CHECKED_ATTRS) + r'))='
    r'(?P<q>["\'])(?P<val>.*?)(?P=q)'
)


@dataclass
class Finding:
    line: int
    col: int
    attr: str
    original: str
    fixed: str


def sentence_case(value: str) -> str:
    if not value:
        return value
    first = value[:1]
    if first.isalpha():
        return first.upper() + value[1:]
    return value


def quantity(count: int, singular: str) -> str:
    suffix = '' if count == 1 else 's'
    return f'{count} {singular}{suffix}'


def first_two_words(value: str) -> str:
    words = value.split()
    return ' '.join(words[:2]) if words else ''


def location(text: str, pos: int) -> tuple[int, int]:
    line = text.count('\n', 0, pos) + 1
    col = pos - (text.rfind('\n', 0, pos) + 1) + 1
    return line, col


def scan(text: str, attrs: tuple[str, ...]) -> tuple[int, list[Finding]]:
    processed = 0
    findings: list[Finding] = []
    for match in ATTR_RE.finditer(text):
        if match.group('attr') not in attrs:
            continue
        processed += 1
        original = match.group('val')
        fixed = sentence_case(original)
        if fixed != original:
            line, col = location(text, match.start())
            findings.append(Finding(line, col, match.group('attr'), original, fixed))
    return processed, findings


def apply_fix(text: str, attrs: tuple[str, ...]) -> str:
    def replace(match: re.Match[str]) -> str:
        if match.group('attr') not in attrs:
            return match.group(0)
        q = match.group('q')
        return f"{match.group('head')}={q}{sentence_case(match.group('val'))}{q}"
    return ATTR_RE.sub(replace, text)


def report(prefix: str, resolved: Path, findings: list[Finding]) -> None:
    for f in findings:
        # path:line:col is clickable in VS Code and most terminals
        print(
            f'{prefix}{resolved}:{f.line}:{f.col}  [{f.attr}]  '
            f'"{first_two_words(f.original)}" -> "{first_two_words(f.fixed)}"'
        )


def check_file(path: Path, attrs: tuple[str, ...]) -> tuple[int, int]:
    text = path.read_text(encoding='utf-8')
    processed, findings = scan(text, attrs)
    report('', path.resolve(), findings)
    return processed, len(findings)


def fix_file(path: Path, attrs: tuple[str, ...]) -> tuple[int, int]:
    text = path.read_text(encoding='utf-8')
    processed, findings = scan(text, attrs)
    if findings:
        path.write_text(apply_fix(text, attrs), encoding='utf-8')
        report('Fixed ', path.resolve(), findings)
    return processed, len(findings)


def usage() -> None:
    print(
        'Usage:\n'
        f'  check [{"|".join(CHOICES)}] [files...]\n'
        f'  fix {{{"|".join(CHOICES)}}} [files...]',
        file=sys.stderr,
    )


def parse_args(argv: list[str]):
    mode = 'check'
    args = list(argv)
    if args and args[0] in ('check', 'fix'):
        mode = args.pop(0)

    choice = None
    if args and args[0] in CHOICES + ('type_of_string',):
        choice = args.pop(0)
        if choice == 'type_of_string':   # old name, treated as "all"
            choice = 'all'

    if mode == 'fix' and choice is None:
        usage()
        return None

    attrs = CHECKED_ATTRS if choice in (None, 'all') else (choice,)
    return mode, attrs, args


def main() -> int:
    parsed = parse_args(sys.argv[1:])
    if parsed is None:
        return 2
    mode, attrs, targets = parsed
    if not targets:
        targets = [str(Path(__file__).resolve().parent / 'ExpandedPresets.xml')]

    total_processed = 0
    total_found = 0
    for raw_target in targets:
        path = Path(raw_target)
        if not path.exists():
            print(f'Missing file: {path}', file=sys.stderr)
            return 1
        processed, found = (fix_file if mode == 'fix' else check_file)(path, attrs)
        total_processed += processed
        total_found += found

    verb = 'fixed' if mode == 'fix' else 'need fixing'
    print(
        f'Total: {quantity(total_found, "value")} {verb}, '
        f'{quantity(total_processed - total_found, "value")} fine '
        f'({quantity(total_processed, "attribute")} checked: {", ".join(attrs)}).'
    )
    if mode == 'check' and total_found:
        print('Run "fix <attr|all>" to fix them (e.g. fix name).')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
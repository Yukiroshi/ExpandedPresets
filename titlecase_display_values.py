#!/usr/bin/env python3
import re
import sys
from pathlib import Path

ATTR_RE = re.compile(r'((?:[A-Za-z_][\w.-]*\.)?display_value=)(["\'])(.*?)(\2)')


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


def update_file(path: Path) -> tuple[int, int]:
    text = path.read_text(encoding='utf-8')
    processed = 0
    changed = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal processed, changed
        processed += 1
        original = match.group(3)
        updated_value = sentence_case(original)
        if updated_value != original:
            changed += 1
        return f"{match.group(1)}{match.group(2)}{updated_value}{match.group(2)}"

    updated = ATTR_RE.sub(replace, text)
    if updated != text:
        path.write_text(updated, encoding='utf-8')
    return processed, changed


def main() -> int:
    targets = sys.argv[1:]
    if not targets:
        targets = [str(Path(__file__).resolve().parent / 'ExpandedPresets.xml')]

    total_processed = 0
    total_changed = 0
    for raw_target in targets:
        path = Path(raw_target)
        if not path.exists():
            print(f'Missing file: {path}', file=sys.stderr)
            return 1
        processed, changed = update_file(path)
        total_processed += processed
        total_changed += changed
        unchanged = processed - changed
        if changed:
            print(
                f'Updated {path}: {quantity(changed, "value")} changed, '
                f'{quantity(unchanged, "value")} unchanged '
                f'({quantity(processed, "display_value attribute")} processed).'
            )
    if not total_changed:
        scope = 'overall' if len(targets) > 1 else f'in {Path(targets[0])}'
        print(
            f'No values changed {scope} '
            f'({quantity(total_processed, "display_value attribute")} checked).'
        )
    elif len(targets) > 1:
        print(
            f'Total: {quantity(total_changed, "value")} changed, '
            f'{quantity(total_processed - total_changed, "value")} unchanged '
            f'({quantity(total_processed, "display_value attribute")} processed).'
        )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

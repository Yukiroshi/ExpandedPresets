#!/usr/bin/env python3
"""Check a JOSM tagging preset XML file for common authoring errors."""

from __future__ import annotations

import difflib
import re
import sys
from pathlib import Path
from xml.parsers import expat

LANGUAGE_ATTRIBUTE = re.compile(r"^[a-z]{2}(?:_[A-Z]{2})?\.(.+)$")

REQUIRED_ATTRIBUTES = {
    "group": ("name",),
    "item": ("name",),
    "label": ("text",),
    "key": ("key",),
    "text": ("key",),
    "combo": ("key",),
    "multiselect": ("key",),
    "check": ("key",),
    "role": ("key",),
    "chunk": ("id",),
    "reference": ("ref",),
    "list_entry": ("value",),
    "preset_link": ("preset_name",),
}

PROHIBITED_ATTRIBUTES = {
    "presets": {"text", "type"},
    "group": {"text", "type"},
    "item": {"text"},
    "link": {"name"},
    "preset_link": {"name"},
    "label": {"name"},
    "text": {"type", "name", "value", "values"},
    "combo": {"type", "value", "name", "delete-if-empty", "display-values"},
    "multiselect": {"type", "value", "name", "delete-if-empty", "display-values"},
    "check": {"name", "type", "value"},
}

LOCALIZED_ATTRIBUTES = {
    "presets": {"description", "shortdescription", "link"},
    "group": {"name"},
    "item": {"name"},
    "optional": {"text"},
    "label": {"text"},
    "preset_link": {"text"},
    "text": {"text"},
    "combo": {"text", "values", "display_values"},
    "multiselect": {"text", "values", "display_values"},
    "check": {"text"},
    "role": {"text"},
    "list_entry": {"display_value", "short_description", "icon"},
}

KNOWN_ATTRIBUTES = {
    "author", "baselanguage", "description", "shortdescription", "link",
    "version", "icon", "icon_size", "name", "name_context", "name_template",
    "name_template_filter", "match_expression", "preset_name_label", "regions",
    "exclude_regions", "text", "text_context", "multiline", "normalize",
    "key", "default", "use_last_as_default", "auto_increment", "match",
    "length", "alternative_autocomplete_keys", "value_template", "value",
    "value_context", "display_value", "short_description", "values",
    "values_from", "values_context", "values_no_i18n", "values_no_i18",
    "values_sort", "values_searchable", "display_values", "delimiter",
    "editable", "rows", "columns", "value_on", "value_off", "disable_off",
    "type", "count", "requisite", "member_expression", "regexp", "id", "ref",
    "wiki", "href", "preset_name", "ext_context", "values_i18n",
}

BOOLEAN_ATTRIBUTES = {
    "disable_off", "editable", "exclude_regions", "multiline", "normalize",
    "preset_name_label", "regexp", "values_no_i18n", "values_no_i18",
    "values_searchable", "values_sort",
}


class PresetValidator:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.errors: list[tuple[int, str]] = []
        self.notices: list[tuple[int, str]] = []
        self.chunk_ids: dict[str, int] = {}
        self.references: list[tuple[str, int]] = []
        self.stack: list[str] = []
        self.has_list_entries: list[bool] = []
        self.current_attributes: list[dict[str, str]] = []
        self.element_lines: list[int] = []
        self.root_seen = False

    def error(self, line: int, message: str) -> None:
        self.errors.append((line, message))

    def notice(self, line: int, message: str) -> None:
        self.notices.append((line, message))

    def start_element(
        self, name: str, attributes: dict[str, str], parser: expat.XMLParserType
    ) -> None:
        line = parser.CurrentLineNumber
        element = name.rsplit("}", 1)[-1]
        if not self.stack:
            self.root_seen = True
            if element != "presets":
                self.error(line, f"expected <presets> as the root element, not <{element}>")
        if self.stack and self.stack[-1] in {"combo", "multiselect"}:
            if element in {"list_entry", "reference"}:
                self.has_list_entries[-1] = True
        self.stack.append(element)
        self.has_list_entries.append(False)
        self.current_attributes.append(attributes)
        self.element_lines.append(line)

        for attribute in REQUIRED_ATTRIBUTES.get(element, ()):
            if attribute not in attributes:
                self.error(
                    line,
                    f"<{element}> is missing required attribute '{attribute}'",
                )

        for attribute in attributes:
            if attribute in PROHIBITED_ATTRIBUTES.get(element, set()):
                suggestion = {
                    ("item", "text"): "name",
                    ("group", "text"): "name",
                    ("text", "name"): "text",
                    ("label", "name"): "text",
                }.get((element, attribute))
                hint = f"; did you mean '{suggestion}'?" if suggestion else ""
                if element == "text" and attribute == "values":
                    hint = "; did you mean <combo> or <multiselect>?"
                self.error(
                    line,
                    f"attribute '{attribute}' is not valid on <{element}>{hint}",
                )

            localized = LANGUAGE_ATTRIBUTE.fullmatch(attribute)
            if localized:
                base_attribute = localized.group(1)
                valid_bases = LOCALIZED_ATTRIBUTES.get(element, set())
                if base_attribute not in valid_bases:
                    expected_base = {
                        "name": "text",
                        "text": "name",
                    }.get(base_attribute)
                    if expected_base not in valid_bases:
                        expected_base = None
                    suggestion = difflib.get_close_matches(
                        base_attribute, sorted(valid_bases), n=1, cutoff=0.65
                    )
                    expected_base = expected_base or (suggestion[0] if suggestion else None)
                    hint = (
                        f"; did you mean '{attribute.split('.', 1)[0]}.{expected_base}'?"
                        if expected_base
                        else ""
                    )
                    self.error(
                        line,
                        f"localized attribute '{attribute}' is not valid on "
                        f"<{element}>{hint}",
                    )
            elif attribute not in KNOWN_ATTRIBUTES:
                suggestion = difflib.get_close_matches(
                    attribute, sorted(KNOWN_ATTRIBUTES), n=1, cutoff=0.82
                )
                if suggestion:
                    self.error(
                        line,
                        f"unrecognized attribute '{attribute}'; "
                        f"did you mean '{suggestion[0]}'?",
                    )

            if attribute in BOOLEAN_ATTRIBUTES and attributes[attribute] not in {
                "true",
                "false",
            }:
                self.error(
                    line,
                    f"attribute '{attribute}' must be 'true' or 'false', "
                    f"not {attributes[attribute]!r}",
                )

        if element == "check" and attributes.get("default") == "":
            self.notice(line, "empty 'default' on <check> is treated as 'off'")
        elif element == "check" and attributes.get("default") not in {
            None, "on", "off",
        }:
            self.error(line, "attribute 'default' on <check> must be 'on' or 'off'")

        if element == "checkgroup" and "columns" not in attributes:
            self.notice(line, "<checkgroup> works without a 'columns' attribute")

        if element == "check" and attributes.get("use_last_as_default") is not None:
            self.error(line, "<check> does not support 'use_last_as_default'")

        if element == "link" and not (attributes.get("wiki") or attributes.get("href")):
            self.error(line, "<link> requires either 'wiki' or 'href'")

        if element == "chunk":
            chunk_id = attributes.get("id")
            if chunk_id:
                if chunk_id in self.chunk_ids:
                    self.error(
                        line,
                        f"duplicate chunk id {chunk_id!r} "
                        f"(first declared on line {self.chunk_ids[chunk_id]})",
                    )
                else:
                    self.chunk_ids[chunk_id] = line

        if element == "reference" and attributes.get("ref"):
            self.references.append((attributes["ref"], line))

    def end_element(self, _name: str) -> None:
        element = self.stack[-1]
        if element in {"combo", "multiselect"} and not self.has_list_entries[-1]:
            if not self.current_attributes[-1].get("values") and not self.current_attributes[
                -1
            ].get("values_from"):
                self.error(
                    self.element_lines[-1],
                    f"<{element}> requires 'values', 'values_from', or a "
                    "<list_entry>/<reference> child",
                )
        self.stack.pop()
        self.has_list_entries.pop()
        self.current_attributes.pop()
        self.element_lines.pop()

    def validate(self) -> list[tuple[int, str]]:
        parser = expat.ParserCreate(namespace_separator="}")
        parser.StartElementHandler = lambda name, attrs: self.start_element(
            name, attrs, parser
        )
        parser.EndElementHandler = self.end_element

        try:
            with self.path.open("rb") as source:
                parser.ParseFile(source)
        except expat.ExpatError as exc:
            self.error(exc.lineno, f"invalid XML: {expat.ErrorString(exc.code)}")
        except OSError as exc:
            self.error(1, f"cannot read file: {exc}")

        if not self.root_seen:
            self.error(1, "document is empty; expected a <presets> root element")

        for reference, line in self.references:
            if reference not in self.chunk_ids:
                self.error(line, f"reference to unknown chunk id {reference!r}")

        return self.errors


def main(arguments: list[str]) -> int:
    paths = [Path(argument) for argument in arguments]
    if not paths:
        paths = [Path(__file__).resolve().with_name("ExpandedPresets.xml")]

    total_errors = 0
    for path in paths:
        validator = PresetValidator(path)
        errors = validator.validate()
        for line, message in validator.notices:
            print(f"{path}:{line}: notice: {message}")
        if errors:
            total_errors += len(errors)
            for line, message in errors:
                print(f"{path}:{line}: error: {message}", file=sys.stderr)
        else:
            print(f"{path}: all good =)")

    if total_errors:
        print(f"Found {total_errors} error(s).", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

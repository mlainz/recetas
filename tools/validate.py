#!/usr/bin/env python3
"""Validate every recipe in recetas/ against recipe.schema.json.

    python3 tools/validate.py

Exits non-zero and prints every problem it found, so one run tells you
everything rather than one thing at a time. This is what CI runs before
building the site.

Deliberately stdlib only -- no `jsonschema` dependency. It interprets the
subset of JSON Schema this repo actually uses (type, required,
additionalProperties, minLength, minItems, nested objects and arrays), and
reads the contract from recipe.schema.json so there is ONE description of the
format rather than a schema for humans and a checker that has drifted from it.

It also makes three checks JSON Schema cannot express:

  * the filename matches a slug derived from the title, because the slug is
    part of the public URL and a mismatch is invisible until someone shares a
    link;
  * every referenced image actually exists in imagenes/;
  * units come from the established vocabulary (a warning, not an error --
    a genuinely new unit is allowed, a typo for an existing one is not
    detectable any other way).
"""

from __future__ import annotations

import json
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECIPES = ROOT / "recetas"
IMAGES = ROOT / "imagenes"
SCHEMA = ROOT / "recipe.schema.json"

KNOWN_UNITS = {
    "g", "ml", "ud", "uds", "cda", "cdta",
    "puñado", "chorro", "al gusto", "cantidad necesaria",
}

JSON_TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "number": (int, float),
    "boolean": bool,
}


def slugify(title: str) -> str:
    """Title -> ASCII slug, matching the convention in CLAUDE.md."""
    decomposed = unicodedata.normalize("NFKD", title)
    ascii_only = "".join(c for c in decomposed if not unicodedata.combining(c))
    ascii_only = ascii_only.replace("ñ", "n").replace("Ñ", "N")
    kept = [c if (c.isalnum() or c.isspace()) else " " for c in ascii_only]
    return "_".join("".join(kept).lower().split())


def type_ok(value, spec) -> bool:
    types = spec if isinstance(spec, list) else [spec]
    for t in types:
        if t == "null":
            if value is None:
                return True
            continue
        # bool is a subclass of int in Python; JSON treats them as distinct.
        if t == "number" and isinstance(value, bool):
            continue
        py = JSON_TYPES.get(t)
        if py and isinstance(value, py):
            return True
    return False


def check(value, schema: dict, where: str, errors: list[str]) -> None:
    if "type" in schema and not type_ok(value, schema["type"]):
        errors.append(f"{where}: expected {schema['type']}, got {type(value).__name__}")
        return

    if isinstance(value, str) and value is not None:
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{where}: must not be empty")

    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{where}: missing required key '{key}'")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in props:
                    errors.append(f"{where}: unexpected key '{key}'")
        for key, sub in props.items():
            if key in value:
                check(value[key], sub, f"{where}.{key}", errors)

    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{where}: needs at least {schema['minItems']} item(s)")
        item_schema = schema.get("items")
        if item_schema:
            for i, item in enumerate(value):
                check(item, item_schema, f"{where}[{i}]", errors)


def main() -> int:
    if not SCHEMA.is_file():
        print(f"missing {SCHEMA}", file=sys.stderr)
        return 2
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    files = sorted(RECIPES.glob("*.json"))
    if not files:
        print(f"no recipes found in {RECIPES}", file=sys.stderr)
        return 2

    errors: list[str] = []
    warnings: list[str] = []

    for path in files:
        rel = f"recetas/{path.name}"
        try:
            recipe = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{rel}: invalid JSON -- {exc}")
            continue

        check(recipe, schema, rel, errors)

        title = recipe.get("title")
        if isinstance(title, str) and title:
            expected = slugify(title)
            actual = path.stem
            if expected != actual:
                # A warning rather than an error: a recipe may legitimately be
                # renamed without moving its file, because the filename is a
                # published URL and keeping it stable is the point.
                warnings.append(
                    f"{rel}: filename does not match title -- "
                    f"title '{title}' slugifies to '{expected}'. "
                    f"Keep the filename if the URL is already published."
                )

        for i, ing in enumerate(recipe.get("ingredients") or []):
            if isinstance(ing, dict):
                unit = ing.get("unit")
                if isinstance(unit, str) and unit not in KNOWN_UNITS:
                    warnings.append(
                        f"{rel}: ingredients[{i}] uses unit '{unit}', "
                        f"not in the established vocabulary"
                    )

        referenced = [recipe.get("image")] + [
            s.get("image") for s in (recipe.get("instructions") or [])
            if isinstance(s, dict)
        ]
        for name in referenced:
            if isinstance(name, str) and name:
                if "/" in name or name.startswith("http"):
                    errors.append(
                        f"{rel}: image '{name}' must be a bare filename inside imagenes/"
                    )
                elif not (IMAGES / name).is_file():
                    errors.append(f"{rel}: image '{name}' not found in imagenes/")

    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")

    print(
        f"\n{len(files)} recipes checked, {len(errors)} error(s), "
        f"{len(warnings)} warning(s)."
    )
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

# Recetas — how to add one

This repository is the **source of truth** for Manuel's recipes. Everything else
is generated from it:

- the public website, built by GitHub Actions and served from GitHub Pages;
- a read-only mirror in **Mealie**, a recipe manager on the home server, which
  imports from here on a timer and never writes back.

So this repo is the only place a recipe is edited. A malformed file breaks the
website build and the Mealie import together, which is why the format below is
strict and why `recipe.schema.json` sets `additionalProperties: false`.

## The one rule

**One recipe per file, at `recetas/<slug>.json`.**

`<slug>` is derived from the title: lowercase, ASCII only, words joined by
underscores. Strip accents and ñ (`Champiñones al vino tinto` →
`champinones_al_vino_tinto`, `Espaguetis santoñeses` →
`espaguetis_santoneses`). Never put a space or an accent in a filename — the
slug becomes part of the public URL.

The **title** keeps its accents. Only the filename is ASCII.

## Format

Validate against `recipe.schema.json` before committing. Every key listed as
required must be present, using `null` when the recipe does not specify it.

```json
{
    "title": "Champiñones al vino tinto",
    "description": "Inspirados en los champiñones estofados de DELICIO, en Santander.",
    "ingredients": [
        { "name": "Champiñones", "quantity": 500, "unit": "g" },
        { "name": "Vino tinto", "quantity": 250, "unit": "ml" },
        { "name": "Aceite de oliva", "quantity": null, "unit": "al gusto" }
    ],
    "instructions": [
        { "description": "Sofreír el ajo y la cebolla cortada fina, unos 15 min." },
        { "description": "Añadir los champiñones cortados en mitades y rehogar." }
    ],
    "time": "45m",
    "servings": 4,
    "tags": ["guiso", "vegetariano"],
    "image": null
}
```

Conventions, all of them already established by the existing files:

- **Spanish.** Titles, descriptions, ingredients, steps and tags are all in
  Spanish. If a source recipe is in another language, translate it.
- **Ingredient names** start with a capital letter: `Champiñones`, not
  `champiñones`.
- **Quantities in base units.** 1 kg → `1000` with unit `"g"`; ½ l → `500` with
  unit `"ml"`.
- **Unit vocabulary** — reuse these rather than inventing new ones:
  `g`, `ml`, `ud`, `uds`, `cda` (cucharada), `cdta` (cucharadita), `puñado`,
  `chorro`, `al gusto`, `cantidad necesaria`.
- **Steps are not numbered.** The array order is the order. Do not write
  `"1. Sofreír…"`.
- **Tags** are lowercase Spanish words. Existing ones worth reusing: `guiso`,
  `vegetariano`, `pasta`, `crema`, `aperitivo`, `picante`, `frío`, `curry`,
  `pollo`, `cerdo`, `setas`, `fideua`.
- **4-space indent, accents written literally** (not `ñ`), one trailing
  newline.

## Do not invent

`time` and `servings` are `null` whenever the original recipe does not state
them. Several existing recipes have `"time": null` for exactly this reason.
Guessing a cooking time is worse than leaving it open — someone will follow it.

Equally: do not silently "improve" a recipe. Transcribe what the source says.
If a step is ambiguous, keep the ambiguity rather than resolving it invisibly.

## Images

`image` is a **bare filename** inside `imagenes/`, e.g.
`"Caponata_siciliana.jpeg"` — not a path and not a URL. Put the file in
`imagenes/` in the same commit. `null` when there is no photo, which is the
common case.

A step may also carry its own `image`, same rule.

## Adding a recipe from a web page

This is the common case. Read the page, then transcribe it into the format
above — do not paste raw HTML or a link and call it done. Keep the amounts the
source gives (converted to base units), keep the steps in order, and put the
source URL at the end of `description` only if it adds something; there is no
dedicated field for it.

## Leave everything else alone

- Do not edit or reformat other recipes while adding one.
- Do not add fields that are not in the schema — the schema rejects them, so
  the build will fail.
- Do not touch `.github/`, `recipe.schema.json` or this file unless that is
  explicitly the task.

## Checking your work

```sh
python3 tools/validate.py          # validates every recipe against the schema
```

That script is what CI runs. If it passes, the site will build and Mealie will
import cleanly.

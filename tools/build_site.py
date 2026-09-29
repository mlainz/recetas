#!/usr/bin/env python3
"""Render recetas/*.json into a static site in public/.

    python3 tools/build_site.py [--out public]

Replaces the old Jekyll setup, and the reason is not taste: that site was built
by GitLab CI from `image: ruby:latest`, which has since moved to Ruby 4.0, and
Jekyll pulls in `eventmachine` 1.2.7 -- a C extension last released in 2018
that has to compile. The build had not run since February 2023. This has no
dependencies beyond the Python standard library, so there is nothing to drift.

All links are RELATIVE, so the output works whether it is served from a domain
root or from a subpath like /recetas/. Do not introduce absolute paths.
"""

from __future__ import annotations

import argparse
import html
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECIPES = ROOT / "recetas"
IMAGES = ROOT / "imagenes"

CSS = """
:root {
  --bg: #fdfcfa; --fg: #23201c; --muted: #6b635a; --line: #e5ded4;
  --card: #ffffff; --accent: #8c3b1e; --chip: #f2ece4;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #171513; --fg: #ece7e1; --muted: #a29a90; --line: #2f2b27;
    --card: #1f1c19; --accent: #e08a5f; --chip: #2a2622;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--fg);
  font: 16px/1.6 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}
.wrap { max-width: 46rem; margin: 0 auto; padding: 2rem 1rem 4rem; }
a { color: var(--accent); }
header.site { border-bottom: 1px solid var(--line); margin-bottom: 2rem; }
header.site h1 { font-size: 1.6rem; margin: 0 0 .25rem; letter-spacing: -.01em; }
header.site p { color: var(--muted); margin: 0 0 1.25rem; }
.grid { display: grid; gap: 1rem; grid-template-columns: repeat(auto-fill, minmax(15rem, 1fr)); }
.card {
  background: var(--card); border: 1px solid var(--line); border-radius: .6rem;
  overflow: hidden; display: flex; flex-direction: column;
}
.card a.t { text-decoration: none; color: inherit; padding: .9rem 1rem; display: block; }
.card a.t:hover h2 { color: var(--accent); }
.card h2 { font-size: 1.05rem; margin: 0 0 .35rem; }
.card img { width: 100%; height: 9rem; object-fit: cover; display: block; }
.chips { display: flex; flex-wrap: wrap; gap: .3rem; margin-top: .5rem; }
.chip {
  background: var(--chip); color: var(--muted); border-radius: 1rem;
  padding: .1rem .55rem; font-size: .75rem;
}
.meta { color: var(--muted); font-size: .85rem; }
article h1 { font-size: 1.8rem; margin: 0 0 .4rem; letter-spacing: -.01em; }
article .lede { color: var(--muted); margin: 0 0 1rem; }
article img.hero { width: 100%; border-radius: .6rem; margin: 1rem 0; }
h2.sec {
  font-size: 1.1rem; margin: 2rem 0 .6rem; padding-bottom: .3rem;
  border-bottom: 1px solid var(--line);
}
ul.ingr { list-style: none; padding: 0; margin: 0; }
ul.ingr li { padding: .35rem 0; border-bottom: 1px dashed var(--line); display: flex; gap: .75rem; }
ul.ingr .q { color: var(--muted); min-width: 7rem; }
ol.steps { padding-left: 1.4rem; }
ol.steps li { margin: .6rem 0; }
.back { display: inline-block; margin-bottom: 1.5rem; font-size: .9rem; text-decoration: none; }
footer { margin-top: 3rem; padding-top: 1rem; border-top: 1px solid var(--line); color: var(--muted); font-size: .85rem; }
@media print {
  body { background: #fff; color: #000; }
  .back, footer { display: none; }
}
"""

PAGE = """<!doctype html>
<html lang="es">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<style>{css}</style>
<div class="wrap">
{body}
</div>
</html>
"""


def e(s) -> str:
    return html.escape(str(s), quote=True)


def fmt_quantity(q) -> str:
    if q is None:
        return ""
    if isinstance(q, float) and q.is_integer():
        q = int(q)
    return str(q)


def chips(tags) -> str:
    if not tags:
        return ""
    return (
        '<div class="chips">'
        + "".join(f'<span class="chip">{e(t)}</span>' for t in tags)
        + "</div>"
    )


def meta_line(recipe: dict) -> str:
    bits = []
    if recipe.get("time"):
        bits.append(e(recipe["time"]))
    if recipe.get("servings"):
        n = recipe["servings"]
        bits.append(f"{e(n)} comensales" if n != 1 else "1 comensal")
    return f'<p class="meta">{" · ".join(bits)}</p>' if bits else ""


def render_recipe(recipe: dict) -> str:
    out = ['<a class="back" href="../">← Todas las recetas</a>', "<article>"]
    out.append(f"<h1>{e(recipe['title'])}</h1>")
    if recipe.get("description"):
        out.append(f'<p class="lede">{e(recipe["description"])}</p>')
    out.append(meta_line(recipe))
    out.append(chips(recipe.get("tags")))

    if recipe.get("image"):
        out.append(
            f'<img class="hero" src="../imagenes/{e(recipe["image"])}" '
            f'alt="{e(recipe["title"])}">'
        )

    out.append('<h2 class="sec">Ingredientes</h2><ul class="ingr">')
    for ing in recipe.get("ingredients", []):
        q = fmt_quantity(ing.get("quantity"))
        unit = ing.get("unit") or ""
        # "al gusto" and "cantidad necesaria" read as a qualifier, not an
        # amount, so they go after the name rather than in the quantity column.
        if q:
            left, right = f"{q} {unit}".strip(), e(ing.get("name", ""))
        else:
            left, right = "", f'{e(ing.get("name", ""))} <span class="meta">({e(unit)})</span>'
        out.append(f'<li><span class="q">{e(left) if left else ""}</span><span>{right}</span></li>')
    out.append("</ul>")

    out.append('<h2 class="sec">Preparación</h2><ol class="steps">')
    for step in recipe.get("instructions", []):
        out.append(f"<li>{e(step.get('description', ''))}")
        if step.get("image"):
            out.append(f'<img class="hero" src="../imagenes/{e(step["image"])}" alt="">')
        out.append("</li>")
    out.append("</ol></article>")
    out.append('<footer>Generado desde <code>recetas/*.json</code>.</footer>')
    return "\n".join(x for x in out if x)


def render_index(entries: list[tuple[str, dict]]) -> str:
    out = [
        '<header class="site"><h1>Recetas</h1>',
        f"<p>{len(entries)} recetas.</p></header>",
        '<div class="grid">',
    ]
    for slug, recipe in entries:
        out.append('<div class="card">')
        if recipe.get("image"):
            out.append(
                f'<a href="./{e(slug)}/"><img src="./imagenes/{e(recipe["image"])}" '
                f'alt="{e(recipe["title"])}" loading="lazy"></a>'
            )
        out.append(f'<a class="t" href="./{e(slug)}/"><h2>{e(recipe["title"])}</h2>')
        if recipe.get("time"):
            out.append(f'<p class="meta">{e(recipe["time"])}</p>')
        out.append(chips(recipe.get("tags")))
        out.append("</a></div>")
    out.append("</div>")
    out.append('<footer>Generado desde <code>recetas/*.json</code>.</footer>')
    return "\n".join(x for x in out if x)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="public")
    args = ap.parse_args()

    out = ROOT / args.out
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    entries = []
    for path in sorted(RECIPES.glob("*.json")):
        recipe = json.loads(path.read_text(encoding="utf-8"))
        entries.append((path.stem, recipe))

    # Alphabetical by title, with Spanish accents folded so "Ñ" and "Á" sort
    # where a reader expects rather than after "Z".
    import unicodedata

    def key(item):
        t = unicodedata.normalize("NFKD", item[1]["title"])
        return "".join(c for c in t if not unicodedata.combining(c)).lower()

    entries.sort(key=key)

    for slug, recipe in entries:
        d = out / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(
            PAGE.format(
                title=e(recipe["title"]),
                desc=e(recipe.get("description") or recipe["title"]),
                css=CSS,
                body=render_recipe(recipe),
            ),
            encoding="utf-8",
        )

    (out / "index.html").write_text(
        PAGE.format(
            title="Recetas",
            desc="Recetas de Manuel",
            css=CSS,
            body=render_index(entries),
        ),
        encoding="utf-8",
    )

    if IMAGES.is_dir():
        shutil.copytree(IMAGES, out / "imagenes")

    print(f"built {len(entries)} recipes into {out.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()

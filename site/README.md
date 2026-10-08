# The Lekh website

The website at <https://sushant-kataria.github.io/Lekh/> is made by a Lekh
program. Everything here is Lekh except the stylesheet, a 30-line script for
the theme switch and copy buttons, and the icons.

```bash
python3 lekh.py site/build.lekh          # writes the site to site/dist/ (about 7 seconds)
python3 lekh.py site/check_links.lekh    # every href, src and #anchor must exist
python3 tools/check_html.py site/dist    # tags balanced, ids unique, one <h1>, ...
python3 lekh.py test site/tests          # unit tests for the pieces below
```

`lekh build site/build.lekh` works too: the translated generator writes the
exact same site, about four times faster.

## How it works

| File | What it does |
|---|---|
| `build.lekh` | the generator: decides the pages, renders them and writes `dist/` |
| `lib/markdown.lekh` | turns the Markdown in `docs/` into HTML (headings with ids, lists, tables, quotes, code) |
| `lib/highlight.lekh` | colours Lekh, Rust and shell code while the site is built, so the browser needs no script for it |
| `lib/layout.lekh` | the frame around every page: header, navigation, footer, logo, relative links |
| `lib/html.lekh` | escaping and heading ids |
| `lib/links.lekh` + `check_links.lekh` | the link checker |
| `content/` | what isn't in `docs/`: the home page text, the example list, the About page, code snippets |
| `static/` | copied as is: `style.css`, `site.js`, the logo and icons |
| `banner.lekh` | draws `assets/lekh-banner.svg` for the README (`tools/render_banner.py` makes the PNG) |

1. Each page in `docs/` is read, run through `markdown.lekh`, and links between
   the Markdown files are rewritten to point at the matching page (or at the
   file on GitHub when the site has no page for it).
2. Every link is relative (`../style.css`, not `/style.css`), because GitHub
   Pages serves the site from `/Lekh/`.
3. The example programs and the snippets on the home page are **run** during
   the build (`run_command`), so every output on the site, including the error
   message, is what Lekh really prints.
4. The page is wrapped in the layout and written out with `write_file`; the
   static files are copied with `copy_file`.

GitHub Actions (`.github/workflows/pages.yml`) runs the build, the link
checker and the HTML checker on every push to `main`, then publishes `dist/`.

#!/usr/bin/env python3
"""Turn the SVG pictures into PNGs with headless Chromium (needs: pip install playwright).

    python3 lekh.py site/banner.lekh     # draws assets/lekh-banner.svg
    python3 tools/render_banner.py       # writes the PNGs below

  assets/lekh-banner.svg    -> assets/lekh-banner.png          (1280x640, README + social preview)
  site/static/favicon.svg   -> site/static/favicon.png         (32x32)
                            -> site/static/apple-touch-icon.png (180x180)
"""
import os
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def shoot(browser, svg, png, width, height, scale=1):
    page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=scale)
    page.goto("file://" + os.path.join(ROOT, svg))
    page.wait_for_load_state("networkidle")
    page.evaluate("document.fonts.ready")
    page.screenshot(path=os.path.join(ROOT, png), clip={"x": 0, "y": 0, "width": width, "height": height},
                    omit_background=True)
    page.close()
    print("wrote", png)

# an SVG with only a viewBox fills the window, so the window size sets the PNG size
with sync_playwright() as p:
    browser = p.chromium.launch()
    shoot(browser, "assets/lekh-banner.svg", "assets/lekh-banner.png", 1280, 640)
    for size, name in ((32, "favicon.png"), (180, "apple-touch-icon.png")):
        page = browser.new_page(viewport={"width": size, "height": size})
        svg = open(os.path.join(ROOT, "site/static/favicon.svg")).read()
        page.set_content('<style>html,body{margin:0;background:transparent}svg{display:block;width:%dpx;height:%dpx}</style>%s'
                         % (size, size, svg))
        page.screenshot(path=os.path.join(ROOT, "site/static", name), omit_background=True,
                        clip={"x": 0, "y": 0, "width": size, "height": size})
        page.close()
        print("wrote site/static/" + name)
    browser.close()

#!/usr/bin/env python3
"""Screenshot pages of the built website with headless Chromium (needs: pip install playwright).

    python3 tools/site_screenshots.py [site/dist] [output folder]
"""
import functools, http.server, os, sys, threading
from playwright.sync_api import sync_playwright

dist = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "site/dist")
out = os.path.abspath(sys.argv[2] if len(sys.argv) > 2 else "/workspace/lekh-site-shots")
pages = sys.argv[3].split(",") if len(sys.argv) > 3 else ["index.html"]
os.makedirs(out, exist_ok=True)

# serve the site under /Lekh/, like GitHub Pages does, to prove relative links work there
class Handler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        if path.startswith("/Lekh/"):
            path = path[len("/Lekh"):]
        return super().translate_path(path)
    def log_message(self, *a):
        pass

srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=dist))
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = "http://127.0.0.1:%d/Lekh/" % srv.server_address[1]

shots = [("desktop", 1280, 800, 1), ("mobile", 390, 844, 2)]
with sync_playwright() as p:
    browser = p.chromium.launch()
    for page_name in pages:
        for label, w, h, scale in shots:
            for theme in ("light", "dark"):
                ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=scale,
                                          color_scheme=theme)
                page = ctx.new_page()
                errors = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.goto(base + page_name, wait_until="networkidle")
                stem = "home" if page_name == "index.html" else page_name.replace("/", "_").replace(".html", "")
                name = "%s-%s-%s.png" % (stem, label, theme)
                page.screenshot(path=os.path.join(out, name), full_page=True)
                if label == "desktop" and theme == "light":
                    page.screenshot(path=os.path.join(out, "%s-%s-top.png" % (stem, label)))
                print("saved", name, ("JS errors: %s" % errors) if errors else "")
                ctx.close()
    browser.close()
srv.shutdown()

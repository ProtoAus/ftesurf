#!/usr/bin/env python3
"""Loopback-only World of Surf web preview/falsifier using synthetic test data.

Requires Playwright plus Flask and an installed Chromium browser. Saves sample
screenshots to --out, opens no real Steam/service connections and stops its own
server/browser. This is not a live nginx, account-path or release test.
"""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import mimetypes
import os
from pathlib import Path
import re
import sys
import tempfile
import threading
from urllib.parse import urlsplit
from urllib.error import HTTPError
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "surfd"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    # Test modules create disposable homes; contain all of them in this context.
    with tempfile.TemporaryDirectory(prefix="brand-fixtures-", dir=args.out) as tmp:
        previous_temp = tempfile.tempdir
        previous_env = dict(os.environ)
        tempfile.tempdir = tmp
        for key in list(os.environ):
            if key.startswith("SURFD_"):
                del os.environ[key]
        os.environ.update(SURFD_BOARD_URL="https://example.invalid/worldofsurf/board",
                          SURFD_GAME=tmp, SURFD_TOOLS=str(ROOT / "tools"))
        try:
            verify(args)
        finally:
            logging.shutdown()
            tempfile.tempdir = previous_temp
            os.environ.clear()
            os.environ.update(previous_env)


def verify(args):
    import test_web as tw
    m = tw.fresh()
    account = tw.get(m, "/board/link")
    assert account.status_code == 200
    assert b"World of Surf" in account.data
    tw.submit(m, "bhop_eazy", "sample", 3000, name="SAMPLE PLAYER (local fixture)")
    rid = tw.api_board(m, "bhop_eazy")["rows"][0]["rep"]
    tw.write_rec(m, "run", "bhop_eazy", 0, 0, tw.leaf(3000, "sample"))
    tw.add_verdict(m, rid, "PASS", int(m.time.now) + 5)
    from PIL import Image, ImageDraw
    shot = Image.new("RGB", (640, 360), "#10151e")
    ImageDraw.Draw(shot).text((32, 160), "LOCAL SAMPLE IMAGE - NOT MAP ART", fill="#59bfff")
    shot.save(Path(os.environ["SURFD_WEBSHOTS"]) / "bhop_eazy.jpg")
    who = json.loads(tw.get(m, "/board/api/map?map=bhop_eazy").data)["rows"][0]["who"]

    site = ROOT / "src/release/site"
    files = {p.name: p.read_bytes() for p in site.iterdir() if p.is_file()}
    files["BebasNeueRegular.ttf"] = (ROOT / "ftesurf/gfx/fonts/BebasNeueRegular.ttf").read_bytes()
    files["LICENSE.txt"] = (ROOT / "LICENSE").read_bytes()
    files["OFL.txt"] = (ROOT / "ftesurf/gfx/fonts/OFL.txt").read_bytes()
    template = (ROOT / "src/release/page.template.html").read_text(encoding="utf-8")
    # Render the Linux blocks as well; all values are explicitly sample data.
    template = template.replace("<!--LINUX-BEGIN-->", "").replace("<!--LINUX-END-->", "")
    values = {"VERSION": "LOCAL PREVIEW", "FILENAME": "ftesurf-preview.7z", "URL": "#sample-download",
              "SIZE_HUMAN": "sample size", "SIZE_BYTES": "0", "SHA256": "0" * 64,
              "DATE": "not a release", "QCBUILD": "unchanged", "ENGINEPATCH": "unchanged",
              "LINUX_URL": "#sample-linux", "LINUX_FILENAME": "ftesurf-preview.tar.xz",
              "LINUX_SIZE_HUMAN": "sample size", "LINUX_SIZE_BYTES": "0", "LINUX_SHA256": "0" * 64,
              "LINUX_GLIBC": "sample", "LINUX_ENGINE": "unchanged"}
    for key, value in values.items():
        template = template.replace("@@" + key + "@@", value)
    assert not re.search(r"@@[A-Z0-9_]+@@", template)
    files["index.html"] = template.encode("utf-8")
    files.update({"release/site/" + name: data for name, data in list(files.items())})
    files.update({"brand/" + p.name: p.read_bytes() for p in (ROOT / "src/brand").iterdir() if p.is_file()})

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *unused):
            pass

        def do_GET(self):
            path = urlsplit(self.path).path
            for prefix in ("/ftesurf/", "/worldofsurf/"):
                if path.startswith(prefix):
                    rest = path[len(prefix):]
                    if rest == "board/link":
                        data, mime, status = account.data, "text/html", 200
                    elif rest.startswith("board/"):
                        reply = m.app.test_client().get("/" + self.path[len(prefix):])
                        data, mime, status = reply.data, reply.content_type, reply.status_code
                    else:
                        name = rest or "index.html"
                        data = files.get(name)
                        status = 200 if data is not None else 404
                        mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
                    self.send_response(status)
                    self.send_header("Content-Type", mime)
                    self.end_headers()
                    self.wfile.write(data if data is not None else b"Not found")
                    return
            self.send_error(404)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = "http://127.0.0.1:" + str(server.server_port)
    errors = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=args.browser, headless=True)
            try:
                page = browser.new_page(reduced_motion="reduce", device_scale_factor=1, color_scheme="dark")
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on("response", lambda response: errors.append(f"HTTP {response.status}: {urlsplit(response.url).path}") if response.status >= 400 else None)
                page.route("**/*", lambda route: route.continue_() if urlsplit(route.request.url).hostname == "127.0.0.1" else route.abort())
                routes = [("board/", "World of Surf Leaderboard"),
                          ("board/#m=bhop_eazy", "bhop_eazy · World of Surf Leaderboard"),
                          ("board/#r=" + str(rid), "SAMPLE PLAYER (local fixture) on bhop_eazy · World of Surf"),
                          ("board/#who=", "Players · World of Surf"),
                          ("board/#p=" + who, "SAMPLE PLAYER (local fixture) · World of Surf")]
                for prefix in ("ftesurf", "worldofsurf"):
                    url = base + "/" + prefix + "/"
                    # Acted HTTP control, including new asset names, both base paths and misses.
                    for name in ("worldofsurf-wordmark.svg", "favicon.svg", "og-worldofsurf.png", "apple-touch-icon.png"):
                        with urlopen(url + name) as response:
                            assert response.status == 200 and len(response.read()) > 100
                    try:
                        urlopen(url + "missing-rebrand-control.png")
                        raise AssertionError("missing-resource control did not 404")
                    except HTTPError as error:
                        assert error.code == 404
                    for width in (320, 390, 768, 1440):
                        page.set_viewport_size({"width": width, "height": 900})
                        for name in ("", "anticheat.html", "board/", "board/link"):
                            page.goto(url + name, wait_until="networkidle")
                            page.evaluate("document.fonts.ready")
                            assert "World of Surf" in page.title(), (url + name, page.title())
                            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (name, width)
                            if name in ("", "anticheat.html", "board/"):
                                mark = page.locator(".brand")
                                assert mark.get_attribute("aria-label") == "World of Surf home"
                                assert page.locator(".links").evaluate("e => e.scrollWidth <= e.clientWidth + 1"), (name, width, "clipped nav")
                                for nav in page.locator(".links a:visible").all():
                                    assert nav.is_visible()
                            slug = name.replace("/", "-") or "landing"
                            page.screenshot(path=str(args.out / f"sample-{prefix}-{slug}-{width}.png"), full_page=True)
                        if width == 390:
                            page.emulate_media(color_scheme="light")
                            page.goto(url + "board/link", wait_until="networkidle")
                            page.screenshot(path=str(args.out / f"sample-{prefix}-account-light.png"), full_page=True)
                            page.emulate_media(color_scheme="dark")
                    for route, title in routes:
                        page.goto(url + route, wait_until="networkidle")
                        expect(page).to_have_title(title)
                        expect(page.locator("#err")).to_be_hidden()
                        if route == "board/#who=":
                            expect(page.locator("#people-list")).to_contain_text("SAMPLE PLAYER")
                    page.goto(url + "board/#m=bhop_eazy", wait_until="networkidle")
                    expect(page).to_have_title("bhop_eazy · World of Surf Leaderboard")
                    button = page.locator("#srcs button").filter(has_text="WOS")
                    expect(button).to_have_count(1)
                    with page.expect_response(lambda r: "/board/api/map?" in r.url and "tier=ranked" in r.url) as acted:
                        button.click()
                    assert acted.value.json()["tier"] == "ranked"
                    page.wait_for_function("location.hash.includes('tier=ranked')")
                    expect(button).to_have_attribute("aria-pressed", "true")
                    expect(page.locator("#rows")).to_contain_text("SAMPLE PLAYER")
                    print(prefix, "four viewport sizes, pages, five board titles, WOS->ranked ACTED")
                for width in (390, 1024):
                    page.set_viewport_size({"width": width, "height": 900})
                    page.goto(base + "/worldofsurf/brand/index.html", wait_until="networkidle")
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                    page.screenshot(path=str(args.out / f"brand-kit-{width}.png"), full_page=True)
                plain = browser.new_page(java_script_enabled=False, viewport={"width": 390, "height": 900})
                plain.route("**/*", lambda route: route.continue_() if urlsplit(route.request.url).hostname == "127.0.0.1" else route.abort())
                plain.goto(base + "/worldofsurf/", wait_until="networkidle")
                assert plain.locator("h1 img").get_attribute("alt") == "World of Surf"
                assert plain.locator("h1 img").evaluate("e => e.complete && e.naturalWidth > 0")
                plain.close()
                assert not errors, errors
                print("Browser", browser.version, "page/resource errors", len(errors), "no-JS identity PASS")
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    print("Local preview PASS; no live service or release verification claimed.")


if __name__ == "__main__":
    main()

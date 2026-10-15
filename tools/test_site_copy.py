#!/usr/bin/env python3
"""Public-site copy/structure checks. --revision checks a Git predecessor control."""
import argparse
from html.parser import HTMLParser
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
REVISION = None
HOME = "src/release/page.template.html"
ANTI = "src/release/site/anticheat.html"


class Content(HTMLParser):
    def __init__(self, doc):
        super().__init__(convert_charrefs=True)
        self.in_main = False
        self.text = []
        self.sections = 0
        self.attrs = []
        self.feed(doc)

    def handle_starttag(self, tag, attrs):
        self.attrs.append((tag, dict(attrs)))
        if tag == "main":
            self.in_main = True
        if tag == "section" and self.in_main:
            self.sections += 1

    def handle_endtag(self, tag):
        if tag == "main":
            self.in_main = False

    def handle_data(self, data):
        if self.in_main:
            self.text.append(data)

    @property
    def words(self):
        return " ".join(" ".join(self.text).split())


def source(path):
    if REVISION:
        return subprocess.check_output(["git", "show", f"{REVISION}:{path}"], cwd=ROOT).decode("utf-8")
    return (ROOT / path).read_text(encoding="utf-8")


class CopyTests(unittest.TestCase):
    def test_parser_control(self):
        page = Content("<header>ignore</header><main><section>Keep &amp; read</section></main><footer>ignore</footer>")
        self.assertEqual(page.words, "Keep & read")
        self.assertEqual(page.sections, 1)

    def test_home_is_compact(self):
        doc = source(HOME)
        page = Content(doc)
        self.assertEqual(page.sections, 1)
        self.assertLessEqual(len(page.words.split()), 100)
        self.assertIn(('body', {'class': 'landing'}), page.attrs)
        for old_layout in ('class="bento"', 'class="stats"', 'class="band"', '<details', 'class="split"'):
            self.assertNotIn(old_layout, doc)

    def test_anti_is_compact(self):
        page = Content(source(ANTI))
        self.assertLessEqual(page.sections, 4)
        self.assertLessEqual(len(page.words.split()), 290)

    def test_no_retired_slogans(self):
        for path in (HOME, ANTI):
            doc = source(path)
            for slogan in ("Surf, rebuilt", "Every run leaves a line", "Everything a run needs",
                           "Nothing it doesn", "Fair by design", "doesn&rsquo;t just trust",
                           "It checks the run that set it", "record a player can trust",
                           "A public record. A private playbook", "One tier. One level"):
                with self.subTest(path=path, slogan=slogan):
                    self.assertNotIn(slogan, doc)

    def test_verification_facts_and_limits(self):
        words = Content(source(ANTI)).words
        for fact in ("movement inputs", "view angles", "position and velocity", "map build",
                     "timing zones", "physics settings", "re-simulates", "finish time",
                     "Verified badge", "developer approval", "before they have this badge",
                     "signs of automation", "input assistance", "Community", "Momentum Mod", "KSF"):
            with self.subTest(fact=fact):
                self.assertIn(fact, words)
        self.assertNotIn("checked before it counts", words)

    def test_direct_platform_downloads_and_receipt(self):
        doc = source(HOME)
        page = Content(doc)
        for platform in ('', 'LINUX_'):
            with self.subTest(platform=platform or 'WINDOWS'):
                buttons = [attrs for tag, attrs in page.attrs
                           if tag == 'a' and attrs.get('href') == f'@@{platform}URL@@']
                self.assertEqual(len(buttons), 1)
                self.assertEqual(buttons[0]['download'], f'@@{platform}FILENAME@@')
                self.assertIn(f'@@{platform}SHA256@@', buttons[0]['title'])
                self.assertIn(f'@@{platform}SIZE_BYTES@@', buttons[0]['title'])
                self.assertIn('btn', buttons[0]['class'].split())
        for value in ('id="download"', '<code>ftesurf.bat</code>', '<code>./ftesurf.sh</code>',
                      'Momentum Mod Playtest', 'Counter-Strike: Source', 'Half-Life 2',
                      'beta, unranked', 'Tested in WSL only', 'href="version.json"',
                      'href="LICENSE.txt"', 'QuakeC build @@QCBUILD@@', 'patch @@ENGINEPATCH@@'):
            with self.subTest(value=value):
                self.assertIn(value, doc)
        outside = re.sub(r"<!--LINUX-BEGIN-->.*?<!--LINUX-END-->", "", doc, flags=re.S)
        self.assertEqual(set(re.findall(r"@@([A-Z0-9_]+)@@", outside)),
                         {"VERSION", "FILENAME", "URL", "SIZE_HUMAN", "SIZE_BYTES", "SHA256", "DATE", "QCBUILD", "ENGINEPATCH"})
        self.assertEqual(set(re.findall(r"@@(LINUX_[A-Z0-9_]+)@@", doc)),
                         {"LINUX_URL", "LINUX_FILENAME", "LINUX_SIZE_HUMAN", "LINUX_SIZE_BYTES",
                          "LINUX_SHA256", "LINUX_GLIBC", "LINUX_ENGINE"})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision")
    args, remaining = parser.parse_known_args()
    REVISION = args.revision
    unittest.main(argv=[__file__, *remaining])

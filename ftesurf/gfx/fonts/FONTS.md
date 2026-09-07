# Fonts

Three third-party fonts, **all SIL Open Font License 1.1**. The full licence text
is in [OFL.txt](OFL.txt) beside this file; the copyright notices it requires are
reproduced below and are also intact inside each font's own name table.

They are loaded by `src/shared/sh_font.qc`, which **hardcodes these exact
filenames** — do not rename them. (If one is missing the game does not fail; it
prints a warning and falls back to the built-in 8px bitmap font.)

| File | Family | Copyright |
|---|---|---|
| `Roboto.ttf` | Roboto Regular, v3.015 | Copyright 2011 The Roboto Project Authors — <https://github.com/googlefonts/roboto-classic> |
| `BebasNeueRegular.ttf` | Bebas Neue Regular, v2.000 (Ryoichi Tsunekawa, Dharma Type) | Copyright 2019 The Bebas Neue Project Authors — <https://github.com/dharmatype/Bebas-Neue> |
| `GoogleMed.ttf` | Google Sans Code Medium, v7.000 | Copyright 2025 The Google Sans Code Project Authors — <https://github.com/googlefonts/googlesans-code> |

Notes:

- **`GoogleMed.ttf` is an unmodified copy of `GoogleSansCode-Medium.ttf`** under a
  shorter filename. The font binary is untouched. None of the three declares a
  Reserved Font Name, so renaming the file is permitted under OFL §1–3.
- Roboto moved from Apache-2.0 to OFL 1.1 in 2024; this is the OFL-era release,
  which is why its name table cites `openfontlicense.org` rather than the older
  `scripts.sil.org` URL.
- The trademark notices in these fonts ("Roboto is a trademark of Google",
  "Google Sans and Google Sans Code are trademarks of Google LLC", "Bebas Neue is
  a trademark of Dharma Type") constrain what a *product* may be called. They do
  not restrict shipping the fonts, and FTESurf makes no claim to any of them.
- These fonts are **not** covered by FTESurf's GPLv2 licence. The OFL and the GPL
  apply to different files in this repository; see the licence section of the
  [README](../../../README.md).

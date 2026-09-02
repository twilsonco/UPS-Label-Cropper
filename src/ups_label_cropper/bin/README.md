# Bundled SumatraPDF

Place the portable `SumatraPDF.exe` binary here for silent PDF printing on Windows.

Download from: https://www.sumatrapdfreader.org/download-free-pdf-viewer.html
Choose the "portable" ZIP version and extract `SumatraPDF.exe` into this directory.

## Pinned version

The CI pipeline verifies this file against a pinned SHA-256 and fails the build
on mismatch. A modified copy loses SumatraPDF's own Authenticode signature and
would be a genuine antivirus detection, so **never** edit, strip, repack, or
re-compress it — replace it only with an untouched download from the official
site above.

| File | SHA-256 |
|------|---------|
| `SumatraPDF.exe` | `719f689b34f47be8ca105ce8484948474dafde0e106bab599e4a89326070c3d0` |

To upgrade SumatraPDF: download the new portable build, verify its signature
(right-click → Properties → Digital Signatures), then update the hash here **and**
in `.github/workflows/ci.yml` (the "Verify bundled SumatraPDF integrity" step).

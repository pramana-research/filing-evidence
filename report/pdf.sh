#!/usr/bin/env bash
# PDFs of the research pages (the same HTML, with the print stylesheet), via headless Chrome.
#
#   bash report/pdf.sh ../pramana-research-landing      # -> research/filing-evidence/pdf/*.pdf
#
# The pages link their stylesheet as /research/assets/research.css (site-absolute), so they are printed from a
# temporary copy whose stylesheet link points at the file on disk.
set -euo pipefail
SITE="$(cd "$1" && pwd)"
SRC="$SITE/research"
OUT="$SRC/filing-evidence/pdf"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
CHROME="$(command -v google-chrome || command -v chromium || command -v chromium-browser)"

cp -r "$SRC" "$TMP/"
find "$TMP/research" -name "*.html" -exec sed -i "s#href=\"/research/assets/research.css\"#href=\"file://$TMP/research/assets/research.css\"#" {} \;
mkdir -p "$OUT"

print() {  # page.html -> name.pdf
  "$CHROME" --headless=new --disable-gpu --no-pdf-header-footer --virtual-time-budget=8000 \
    --print-to-pdf="$OUT/$2" "file://$TMP/research/filing-evidence/$1" 2>/dev/null
  echo "  $2 ($(du -h "$OUT/$2" | cut -f1))"
}
print index.html filing-evidence.pdf
for f in "$TMP"/research/filing-evidence/*.html; do
  b="$(basename "$f" .html)"
  [ "$b" = index ] || print "$b.html" "$b.pdf"
done

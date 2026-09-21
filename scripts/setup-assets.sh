#!/bin/sh
set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENDOR="$REPO_ROOT/static/vendor"
FETCH="$REPO_ROOT/scripts/fetch-asset.sh"   # verifies every download against vendor-assets.sha256
cd "$REPO_ROOT"

mkdir -p "$VENDOR/monaco" "$VENDOR/fonts/inter" "$VENDOR/fonts/jetbrains-mono" "$VENDOR/phosphor" "$VENDOR/monaco-themes"

echo "Downloading Phosphor icons..."
"$FETCH" --tar-xz "https://registry.npmjs.org/@phosphor-icons/web/-/web-2.1.1.tgz" /tmp
for w in regular bold fill thin light duotone; do
  cat /tmp/package/src/$w/style.css
done | sed 's|url("./|url("./phosphor/|g' > "$VENDOR/phosphor.css"
cp /tmp/package/src/*/Phosphor*.woff2 "$VENDOR/phosphor/"
cp /tmp/package/src/*/Phosphor*.woff "$VENDOR/phosphor/"
rm -rf /tmp/package

echo "Downloading QRCode..."
"$FETCH" "https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js" "$VENDOR/qrcode.min.js"

echo "Downloading Dagre..."
"$FETCH" "https://cdn.jsdelivr.net/npm/@dagrejs/dagre@3.1.1/dist/dagre.min.js" "$VENDOR/dagre.min.js"

echo "Downloading Monaco Editor..."
"$FETCH" --tar-xz "https://registry.npmjs.org/monaco-editor/-/monaco-editor-0.52.0.tgz" /tmp
rm -rf "$VENDOR/monaco/vs"
mv /tmp/package/min/vs "$VENDOR/monaco/vs"
rm -rf /tmp/package

echo "Downloading Monaco themes..."
"$FETCH" "https://cdn.jsdelivr.net/npm/monaco-themes@0.4.4/themes/GitHub%20Light.json" "$VENDOR/monaco-themes/GitHub Light.json"
"$FETCH" "https://cdn.jsdelivr.net/npm/monaco-themes@0.4.4/themes/GitHub%20Dark.json" "$VENDOR/monaco-themes/GitHub Dark.json"

echo "Downloading Inter font..."
"$FETCH" --tar-xz "https://registry.npmjs.org/@fontsource/inter/-/inter-5.1.1.tgz" /tmp
cp /tmp/package/index.css "$VENDOR/fonts/inter.css"
sed -i \
  -e "s|url('./files/|url('./inter/|g" \
  -e 's|url("./files/|url("./inter/|g' \
  -e "s|url(./files/|url(./inter/|g" \
  "$VENDOR/fonts/inter.css"
cp /tmp/package/files/* "$VENDOR/fonts/inter/"
rm -rf /tmp/package

echo "Downloading JetBrains Mono font..."
"$FETCH" --tar-xz "https://registry.npmjs.org/@fontsource/jetbrains-mono/-/jetbrains-mono-5.1.0.tgz" /tmp
cp /tmp/package/index.css "$VENDOR/fonts/jetbrains-mono.css"
sed -i \
  -e "s|url('./files/|url('./jetbrains-mono/|g" \
  -e 's|url("./files/|url("./jetbrains-mono/|g' \
  -e "s|url(./files/|url(./jetbrains-mono/|g" \
  "$VENDOR/fonts/jetbrains-mono.css"
cp /tmp/package/files/* "$VENDOR/fonts/jetbrains-mono/"
rm -rf /tmp/package

echo "Downloading country flag font..."
"$FETCH" --tar-xz "https://registry.npmjs.org/country-flag-emoji-polyfill/-/country-flag-emoji-polyfill-0.1.10.tgz" /tmp
cp /tmp/package/dist/TwemojiCountryFlags.woff2 "$VENDOR/fonts/"
cp /tmp/package/LICENSE.md "$VENDOR/fonts/TwemojiCountryFlags-LICENSE.md"
rm -rf /tmp/package

echo "Building Tailwind CSS..."
TW_BIN="$(command -v tailwindcss || true)"
if [ -z "$TW_BIN" ]; then
  ARCH="$(uname -m)"
  case "$ARCH" in
    x86_64)  TW_ARCH="linux-x64" ;;
    aarch64) TW_ARCH="linux-arm64" ;;
    armv7*)  TW_ARCH="linux-armv7" ;;
    *)       echo "Unsupported arch: $ARCH"; exit 1 ;;
  esac
  echo "Downloading tailwindcss ($TW_ARCH)..."
  if [ -w /usr/local/bin ]; then
    TW_BIN=/usr/local/bin/tailwindcss
  else
    TW_BIN="$(mktemp -d)/tailwindcss"
  fi
  "$FETCH" "https://github.com/tailwindlabs/tailwindcss/releases/download/v3.4.17/tailwindcss-$TW_ARCH" \
    "$TW_BIN"
  chmod +x "$TW_BIN"
fi

"$TW_BIN" -c "$REPO_ROOT/tailwind.config.js" \
  -i "$REPO_ROOT/static/css/tailwind.input.css" \
  -o "$REPO_ROOT/static/css/tailwind.css" --minify

if ! grep -q "\.flex{" "$REPO_ROOT/static/css/tailwind.css"; then
  echo "ERROR: Tailwind build produced no utility classes - check that $REPO_ROOT/templates exists and is readable."
  exit 1
fi

PYBABEL=""
if [ -x "$REPO_ROOT/venv/bin/pybabel" ]; then
  PYBABEL="$REPO_ROOT/venv/bin/pybabel"
elif command -v pybabel >/dev/null 2>&1; then
  PYBABEL="pybabel"
fi
if [ -d "$REPO_ROOT/locale" ]; then
  if [ -n "$PYBABEL" ]; then
    echo "Compiling translations..."
    "$PYBABEL" compile -d "$REPO_ROOT/locale" -D messages || echo "WARNING: translations did not compile, the interface stays in English."
  else
    echo "WARNING: pybabel not found, the interface stays in English. Install requirements.txt and run this script again."
  fi
fi

echo "Done."

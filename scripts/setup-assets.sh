#!/bin/sh
set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENDOR="$REPO_ROOT/static/vendor"

mkdir -p "$VENDOR/monaco" "$VENDOR/fonts/inter" "$VENDOR/fonts/jetbrains-mono" "$VENDOR/phosphor" "$VENDOR/monaco-themes"

echo "Downloading Phosphor icons..."
curl -sL "https://registry.npmjs.org/@phosphor-icons/web/-/web-2.1.1.tgz" | tar -xz -C /tmp
for w in regular bold fill thin light duotone; do
  cat /tmp/package/src/$w/style.css
done | sed 's|url("./|url("./phosphor/|g' > "$VENDOR/phosphor.css"
cp /tmp/package/src/*/Phosphor*.woff2 "$VENDOR/phosphor/"
cp /tmp/package/src/*/Phosphor*.woff "$VENDOR/phosphor/"
rm -rf /tmp/package

echo "Downloading QRCode..."
curl -sLo "$VENDOR/qrcode.min.js" "https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"

echo "Downloading Dagre..."
curl -sLo "$VENDOR/dagre.min.js" "https://cdn.jsdelivr.net/npm/dagre@0.8.5/dist/dagre.min.js"

echo "Downloading Monaco Editor..."
curl -sL "https://registry.npmjs.org/monaco-editor/-/monaco-editor-0.52.0.tgz" | tar -xz -C /tmp
rm -rf "$VENDOR/monaco/vs"
mv /tmp/package/min/vs "$VENDOR/monaco/vs"
rm -rf /tmp/package

echo "Downloading Monaco themes..."
curl -sLo "$VENDOR/monaco-themes/GitHub Light.json" "https://cdn.jsdelivr.net/npm/monaco-themes@0.4.4/themes/GitHub%20Light.json"
curl -sLo "$VENDOR/monaco-themes/GitHub Dark.json" "https://cdn.jsdelivr.net/npm/monaco-themes@0.4.4/themes/GitHub%20Dark.json"

echo "Downloading Inter font..."
curl -sL "https://registry.npmjs.org/@fontsource/inter/-/inter-5.1.1.tgz" | tar -xz -C /tmp
cp /tmp/package/index.css "$VENDOR/fonts/inter.css"
sed -i \
  -e "s|url('./files/|url('./inter/|g" \
  -e 's|url("./files/|url("./inter/|g' \
  -e "s|url(./files/|url(./inter/|g" \
  "$VENDOR/fonts/inter.css"
cp /tmp/package/files/* "$VENDOR/fonts/inter/"
rm -rf /tmp/package

echo "Downloading JetBrains Mono font..."
curl -sL "https://registry.npmjs.org/@fontsource/jetbrains-mono/-/jetbrains-mono-5.1.0.tgz" | tar -xz -C /tmp
cp /tmp/package/index.css "$VENDOR/fonts/jetbrains-mono.css"
sed -i \
  -e "s|url('./files/|url('./jetbrains-mono/|g" \
  -e 's|url("./files/|url("./jetbrains-mono/|g' \
  -e "s|url(./files/|url(./jetbrains-mono/|g" \
  "$VENDOR/fonts/jetbrains-mono.css"
cp /tmp/package/files/* "$VENDOR/fonts/jetbrains-mono/"
rm -rf /tmp/package

echo "Building Tailwind CSS..."
if ! command -v tailwindcss > /dev/null 2>&1; then
  ARCH="$(uname -m)"
  case "$ARCH" in
    x86_64)  TW_ARCH="linux-x64" ;;
    aarch64) TW_ARCH="linux-arm64" ;;
    armv7*)  TW_ARCH="linux-armv7" ;;
    *)       echo "Unsupported arch: $ARCH"; exit 1 ;;
  esac
  echo "Downloading tailwindcss ($TW_ARCH)..."
  curl -sLo /usr/local/bin/tailwindcss \
    "https://github.com/tailwindlabs/tailwindcss/releases/download/v3.4.17/tailwindcss-$TW_ARCH"
  chmod +x /usr/local/bin/tailwindcss
fi

tailwindcss -c "$REPO_ROOT/tailwind.config.js" \
  -i "$REPO_ROOT/static/css/tailwind.input.css" \
  -o "$REPO_ROOT/static/css/tailwind.css" --minify 2>&1 | grep -v "caniuse-lite\|npx update-browserslist-db"

echo "Done."

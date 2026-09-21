#!/bin/sh
# Download one third-party asset and refuse to hand it over unless it matches the SHA-256
# recorded in scripts/vendor-assets.sha256.
#
# Usage:  fetch-asset.sh <url> <destination>
#         fetch-asset.sh --tar-xz <url> <directory>   # verify, then extract into <directory>
#
# There is deliberately no "write to stdout" mode. Piping into tar would put this script on the
# left of a pipe, where its exit status is discarded unless the caller sets pipefail, and a
# checksum failure would be ignored by every shell that does not.
#
# Two things this fixes. curl was called as `curl -sL` with no --fail, so an HTTP 404 or 502
# exited 0 and the error page was written to the destination as if it were the asset. And
# nothing checked what arrived, so a redirected, cached or replaced download went straight
# into the image and, in the case of tailwindcss, was executed.
set -e

MODE=copy
if [ "$1" = "--tar-xz" ]; then
  MODE=tar-xz
  shift
fi
URL="$1"
DEST="$2"
SUMS="$(cd "$(dirname "$0")" && pwd)/vendor-assets.sha256"

if [ -z "$URL" ] || [ -z "$DEST" ]; then
  echo "usage: $0 [--tar-xz] <url> <destination>" >&2
  exit 2
fi

EXPECTED="$(awk -v u="$URL" '$2 == u { print $1 }' "$SUMS")"
if [ -z "$EXPECTED" ]; then
  echo "fetch-asset: no checksum recorded for $URL" >&2
  echo "             add one to $SUMS before this URL can be used." >&2
  exit 1
fi

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

# --fail turns an HTTP error into a non-zero exit instead of a downloaded error page.
if ! curl --fail --silent --show-error --location --retry 3 --retry-delay 2 \
          --max-time 300 -o "$TMP" "$URL"; then
  echo "fetch-asset: download failed for $URL" >&2
  exit 1
fi

ACTUAL="$(sha256sum "$TMP" | cut -d' ' -f1)"
if [ "$ACTUAL" != "$EXPECTED" ]; then
  echo "fetch-asset: checksum mismatch for $URL" >&2
  echo "             expected $EXPECTED" >&2
  echo "             got      $ACTUAL" >&2
  echo "             refusing to use this file." >&2
  exit 1
fi

if [ "$MODE" = "tar-xz" ]; then
  mkdir -p "$DEST"
  tar -xzf "$TMP" -C "$DEST"
else
  mkdir -p "$(dirname "$DEST")"
  cp "$TMP" "$DEST"
fi

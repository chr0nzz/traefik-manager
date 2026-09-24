#!/bin/sh
set -e

if [ -z "$PUID" ] && [ -z "$PGID" ]; then
    exec "$@"
fi

uid="${PUID:-1000}"
gid="${PGID:-$uid}"
case "$uid:$gid" in
    *[!0-9:]*|:*|*:)
        echo "PUID and PGID must be numbers, got PUID='$PUID' PGID='$PGID'" >&2
        exit 1
        ;;
esac
if [ "$uid" = 0 ]; then
    exec "$@"
fi

name_for() {
    awk -F: -v id="$2" '$3 == id { print $1; exit }' "$1"
}

group=$(name_for /etc/group "$gid")
if [ -z "$group" ]; then
    group=tm
    addgroup -g "$gid" "$group"
fi

user=$(name_for /etc/passwd "$uid")
if [ -z "$user" ]; then
    user=tm
    adduser -D -H -h /tmp -s /sbin/nologin -u "$uid" -G "$group" "$user"
else
    addgroup "$user" "$group" 2>/dev/null || true
fi

if [ -S /var/run/docker.sock ]; then
    sock_gid=$(stat -c %g /var/run/docker.sock)
    sock_group=$(name_for /etc/group "$sock_gid")
    if [ -z "$sock_group" ]; then
        sock_group=docker-sock
        addgroup -g "$sock_gid" "$sock_group"
    fi
    addgroup "$user" "$sock_group" 2>/dev/null || true
fi

for dir in /app/config /app/backups; do
    mkdir -p "$dir"
    if ! awk -v d="$dir" '$5 == d { found = 1 } END { exit !found }' /proc/self/mountinfo; then
        chown "$uid:$gid" "$dir"
    fi
done

config_dir=$(dirname "${SETTINGS_PATH:-/app/config/manager.yml}")
su-exec "$user" mkdir -p "$config_dir" 2>/dev/null || true
if ! su-exec "$user" sh -c 'test -w "$1"' sh "$config_dir"; then
    echo "PUID/PGID is set to $uid:$gid, but $config_dir is not writable by that user." >&2
    echo "Give the user the mounted directory on the host (chown -R $uid:$gid <host path>)," >&2
    echo "or remove PUID and PGID to run as root as before." >&2
    exit 1
fi

exec su-exec "$user" "$@"

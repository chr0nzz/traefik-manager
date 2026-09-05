# Traefik Security Hardening

Traefik Manager can configure several Traefik security controls from the UI. This page explains what they defend against and how to enable them. These harden **Traefik and your backends** - they are separate from [Traefik Manager's own security](security.md).

All of them apply to the Host and to remote agents: the Static Config editor and the middleware wizards work the same for both.

---

## Header alias spoofing

### The problem

Go - and therefore Traefik - treats `X-Auth-User`, `X_Auth_User` and `X.Auth.User` as three **different** headers. A forwardAuth middleware manages the dash form, so an attacker-supplied alias passes through untouched.

It becomes exploitable at the backend: CGI, WSGI (Python), PHP, and some application-server setups uppercase the name and replace every character that is neither a letter nor a digit with an underscore, collapsing all three into the same variable (`HTTP_X_AUTH_USER`). The app then reads the attacker's alias instead of the identity your auth server set - an authentication bypass behind an otherwise correct forwardAuth setup (Authelia, Authentik, Gatekeeper, etc.).

### The fix: `aliasHeadersStrategy`

**Traefik 3.7.12 or newer.** Covers every aliasing name: any header whose name contains a character that is not a letter, a digit or a dash, including `_`, `.`, `!`, `#`, `$`, `%`, `&`, `'`, `*`, `+`, `^`, `` ` ``, `|` and `~`.

| Strategy | Behaviour |
|---|---|
| `keep` | Forward aliasing headers as-is (Traefik default). |
| `delete` | Silently strip them. **Recommended.** |
| `reject` | Reject the request with `400 Bad Request`. |

**In Traefik Manager:** open **Static Config → Entrypoints**, edit the entry point that handles your external HTTPS traffic, and set **Alias Headers** to `Delete` (or `Reject`).

```yaml
entryPoints:
  websecure:   # your external HTTPS entry point, whatever its name
    address: ":443"
    http:
      aliasHeadersStrategy: delete
```

If you use the forwardAuth wizards, enabling this is strongly recommended.

### On older Traefik: `underscoreHeadersStrategy`

**Traefik 3.7.6 through 3.7.11 only.** It takes the same three values but covers **underscores alone**, so dot-form aliases like `X.Auth.User` still get through. It is deprecated in favour of `aliasHeadersStrategy`.

> **No 3.6.x release has either option.** Traefik does not ignore an option it does not know - it refuses to start with `field not found, node: underscoreHeadersStrategy`, taking the proxy down until the file is corrected. Traefik Manager only offers the field on versions that actually have it, and writes whichever name your Traefik supports.

Upgrading to 3.7.12 or newer is the real fix. Traefik Manager reads either name, so switching over is just re-saving the entry point.

### Related advisories

| Advisory | Severity | Fixed in |
|---|---|---|
| [GHSA-rf44-j88r-hh8c](https://github.com/traefik/traefik/security/advisories/GHSA-rf44-j88r-hh8c) - ForwardAuth identity spoofing via dot-form header aliases | Moderate (CVSS 5.3) | **2.11.56 / 3.7.12** |
| **CVE-2026-39858** - underscore aliases of *forwarded* headers (e.g. `X_Forwarded_Proto`) bypassing ForwardAuth | High (CVSS 7.8) | **2.11.43 / 3.6.14 / 3.7.0-rc.2** |

Both are fixed by upgrading Traefik, not by configuration. Traefik Manager warns you when your running version is affected, and says which release to move to.

---

## Encoded path characters

Ambiguous percent-encoded characters in a request path (e.g. `%2F` for `/`, `%2E` for `.`) can be used to sneak past path-based routing or access controls. Traefik sanitizes paths by default since 3.3.6 (removing `..`, `.`, and duplicate slashes), but rejecting ambiguous encoded characters is opt-in.

**Traefik 3.7+** provides an `encodedCharacters` middleware. Add it from **Add Middleware** - template **Encoded Characters** - and attach it to sensitive routes. Every character is rejected by default; tick one only if a backend genuinely needs it.

---

## ForwardAuth response size limit

A compromised or misbehaving auth server could return a very large response body to the forwardAuth subrequest. **Traefik 3.7+** adds `maxResponseBodySize` to cap it. The forwardAuth wizards (including Authentik, Authelia, and Gatekeeper) fill it as **Max Response Body Size** with `4096`, which suits the tiny responses auth servers return. Raise it if your provider returns a larger body, since Traefik fails the request when the response exceeds the limit.

---

## Traefik security advisories

Traefik Manager checks your running Traefik version against a list of known security advisories and shows a warning when your Traefik is affected - with extra urgency when a forwardAuth middleware is configured, since those are the most exposed. Keep Traefik updated; the update-available badge in the navbar shows when a newer Traefik is out.

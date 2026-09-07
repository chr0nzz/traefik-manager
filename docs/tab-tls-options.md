# TLS Options Tab

The **TLS Options** tab manages `tls.options` profiles in your dynamic config. These profiles control TLS version, cipher suites, curve preferences, and client authentication for routers that reference them.

Enable this tab via **Settings - Interface - Tabs - TLS Options**.

## What it shows

A card per named TLS options profile defined across all mounted config files. Each card shows the profile name, a summary line (min version, max version, SNI strict, mTLS), the cipher-suite count, curves, ALPN protocols and client auth type, how many routes reference the profile, and the config file it lives in.

Details, edit and delete live in a hover rail in the card's top right; clicking anywhere else opens the detail panel, which adds the routes using the profile and its raw YAML.

## Creating a profile

Click **Add TLS Profile** and fill in:

| Field | Description |
|---|---|
| Config File | Shown when multiple config files are mounted. Select an existing file or **+ New file...** to name one. |
| Profile Name | The key used in `tls.options` and referenced in router configs (e.g. `modern`, `strict`, `default`). Cannot be changed after creation. |
| Min TLS Version | Default, TLS 1.0, 1.1, 1.2 or 1.3. Recommended: TLS 1.2. |
| Max TLS Version | Default, or an upper bound. |
| SNI Strict | Reject connections with no or mismatched SNI. Requires non-wildcard certificates. |
| Cipher Suites | One cipher per line. Leave empty to use Traefik defaults. Only applies to TLS 1.0-1.2 (TLS 1.3 ciphers are not configurable). |
| Curve Preferences | ECDH curve names, one per line (e.g. `X25519`, `CurveP256`). Leave empty for Traefik defaults. |
| ALPN Protocols | One per line. Leave empty for Traefik's default `h2, http/1.1, acme-tls/1`; if you set them, keep `acme-tls/1` when using ACME TLS challenges. |
| Client Auth Type | Enables mTLS. Options: `NoClientCert`, `RequestClientCert`, `RequireAnyClientCert`, `VerifyClientCertIfGiven`, `RequireAndVerifyClientCert`. |
| CA Files | Paths to CA certificate files inside the container, one per line. Shown once a client auth type is selected. |

## Example - hardened modern profile

```yaml
tls:
  options:
    modern:
      minVersion: VersionTLS12
      sniStrict: true
      cipherSuites:
        - TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384
        - TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384
        - TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305
        - TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305
      curvePreferences:
        - X25519
        - CurveP256
        - CurveP384
```

## Renaming and deleting

Renaming a profile moves every router using it to the new name. Deleting one a router still uses is refused, and the message names the routers.

## Assigning a profile to a router

In the **Add / Edit Route** form, select a profile from the **TLS Options Profile** dropdown, which appears once TLS is enabled on the route. TM writes `tls.options: <name>` to the router config.

Traefik documentation: [TLS Options](https://doc.traefik.io/traefik/reference/routing-configuration/http/tls/tls-options/)

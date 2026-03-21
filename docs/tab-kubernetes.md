# Kubernetes Tab

The **Kubernetes** tab shows all routes discovered by Traefik's Kubernetes providers in read-only mode.

## Supported providers

| Provider | Traefik string | Description |
|---|---|---|
| Kubernetes CRD | `kubernetescrd` | Routes defined via `IngressRoute`, `IngressRouteTCP`, `IngressRouteUDP` custom resources |
| Kubernetes Ingress | `kubernetes` | Routes defined via standard `Ingress` resources |
| Kubernetes Gateway API | `kubernetesgateway` | Routes defined via Gateway API resources (`HTTPRoute`, `TCPRoute`, etc.) |

All three variants are shown together in one tab, each with a badge indicating which provider manages it (CRD / Ingress / Gateway).

## What it shows

- Route name, rule, status (enabled/disabled/error)
- Protocol (HTTP / TCP / UDP)
- Provider badge (CRD, Ingress, or Gateway)
- TLS indicator
- Service name
- Namespace (if returned by the Traefik API)
- Entry points
- Full detail view via the info button

Routes are **read-only** - edit them via your Kubernetes manifests or Helm values.

## Enabling the tab

### During setup wizard
Toggle **Kubernetes** on in the "Optional monitoring" step.

### After setup
Go to **Settings → Optional Tabs** and enable Kubernetes.

## Requirements

Traefik must be configured with at least one Kubernetes provider in your `traefik.yml` (or Helm values). Example for CRD + Ingress:

```yaml
providers:
  kubernetesCRD: {}
  kubernetesIngress: {}
```

No extra file mounts into the traefik-manager container are needed - data is pulled live from the Traefik API.

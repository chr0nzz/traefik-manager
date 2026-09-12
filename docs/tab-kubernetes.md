# Kubernetes Tab

The **Kubernetes** tab lists the routes Traefik discovered through its Kubernetes providers. All three variants share one tab.

| Provider | Traefik string | Badge | Routes defined via |
|---|---|---|---|
| Kubernetes CRD | `kubernetescrd` | CRD | `IngressRoute`, `IngressRouteTCP`, `IngressRouteUDP` |
| Kubernetes Ingress | `kubernetes` | Ingress | standard `Ingress` resources |
| Kubernetes Gateway API | `kubernetesgateway` | Gateway | Gateway API resources (`HTTPRoute`, `TCPRoute`, ...) |

## What it shows

- One card per route: status, name, rule, protocol, TLS state, service, entry points, middlewares
- The provider kind (CRD, Ingress or Gateway) as the card subtitle, plus a Namespace row when the Traefik API returns one
- Summary strip: route counts per protocol, the provider's middleware count, any route not serving, and a read-only marker
- Middlewares from the Kubernetes providers, listed under the routes, when the provider has at least one route
- Search, protocol filter, refresh

Click a card for its detail panel.

Routes are **read-only** - edit them via your Kubernetes manifests or Helm values.

## Enabling the tab

This tab switches itself on the first time Traefik reports routers from this provider, and the setup wizard pre-selects it when the provider is already running. Turn it off and it stays off.

| Where | Path |
|---|---|
| Setup wizard | Monitoring step → Provider tabs → Kubernetes |
| Later | Settings → Route Monitoring → Kubernetes |

## Requirements

Traefik must be configured with at least one Kubernetes provider in your `traefik.yml` or Helm values. Example for CRD + Ingress:

```yaml
providers:
  kubernetesCRD: {}
  kubernetesIngress: {}
```

No mounts into traefik-manager needed - data comes live from the Traefik API.

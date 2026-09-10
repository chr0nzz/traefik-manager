# Internal Tab

Traefik creates a handful of routers and services for itself: the dashboard, the API, the ping
endpoint, the metrics endpoint and the ACME HTTP challenge. This tab lists them, read only.

They are not in any config file, so there is nothing to edit here. Turn them on or off in your
static config.

| Object | What it is |
|---|---|
| `api@internal` | The Traefik API |
| `dashboard@internal` | The Traefik dashboard |
| `ping@internal` | The ping endpoint |
| `prometheus@internal` | The metrics endpoint |
| `acme-http@internal` | The ACME HTTP challenge responder |
| `noop@internal` | Answers nothing, for routers whose whole job is a middleware |

A router you wrote yourself belongs in [Routes](tab-routes.md), even when it points at one of these
services. A hand-written dashboard route pointing at `api@internal` is your route, and it is listed
and edited there. Only Traefik's own routers appear in this tab.

`noop@internal` is offered in the route form, so a redirect-only router needs no invented backend.
See [Routes](tab-routes.md).

## Enabling the tab

Settings, Route Monitoring, then turn on **Internal**. It is off by default.

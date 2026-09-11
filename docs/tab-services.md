# Services Tab

The **Services** tab shows all services registered in Traefik across every provider - `@file`, `@docker`, `@kubernetes`, and so on - pulled live from the Traefik API. HTTP services from your own config files can be created and edited here; TCP and UDP services, and services from other providers, are read only.

## What it shows

- Service name and provider (e.g. `my-app@file`, `nginx@docker`)
- Status badge: Success, Warning, or Error
- HTTP, TCP, and UDP services

## Views

Toggle between **grid** (default) and **list** view using the button in the filter bar. List view shows a compact table with Status, Protocol, Name, Backend URL, Provider, Servers, and Used By columns.

Grid view shows the service name with its type and provider below it, a status dot on the icon, its first two backend server URLs (each with a copy button, the rest behind a `+N more`), and a footer line with the server count, healthy-server ratio, and sticky or health-check flags. The number of routes using the service sits at the footer's right. Clicking the card opens the service detail panel.

## Filtering

- **Search** - service name
- **Status** - All / Success / Warnings / Errors
- **Protocol** - the protocols actually present
- **Provider** - the providers actually present

The bar also carries a button to clear every filter and one to refresh the list.

A service Traefik reports as `enabled` counts as a warning when any of its backends is not `UP`, which is what the stat panel's **backends down** count measures. Services whose status Traefik does not report at all also land in the Warnings filter, so the two counts can differ.

Composite services (`weighted`, `mirroring`, `failover`, `highestRandomWeight`) carry no backend
status of their own in Traefik - their health lives on the services they point at. They are counted
separately rather than as unchecked, and never move the backends up and down numbers.

## Creating and editing services

The **+** button in the filter bar creates a service without needing a route first. Pick a type:

| Type          | Backends                                                              |
| ---------------| -----------------------------------------------------------------------|
| Load Balancer | A list of addresses, each with its scheme                             |
| Weighted      | Rows that are each an IP:Port or an existing service, split by weight |
| Mirroring     | The first row serves; the rest receive a copy by percentage           |
| Failover      | The first row serves; the second takes over if it fails               |

Each IP:Port row in a composite becomes its own child service named `<name>-backend-<n>`, so every
row carries its own weight. A row referencing an existing service is stored by name and never
copied, so changes to that service follow automatically. The generated children are hidden from
the list and shown on their parent's card; searching reveals them.

An HTTP `@file` service opened from its card or detail panel shows an **Edit** button, whoever
wrote it. Editing keeps settings the form does not manage - `sticky`, `service.middlewares`,
mirror body options - and only replaces what you changed.

### Health check

A plain load balancer has a **Health check** section covering every field Traefik takes: path,
interval, timeout, interval when down, method, expected status, scheme, port, host header, mode
and headers. All are optional; with no path Traefik probes the server root.

Without one, Traefik reports every server as up and keeps sending traffic to a dead one, so a pool
of two or more servers with no health check carries a warning on its card that opens this section.
The route form edits `path`, `interval` and `timeout` on its own service; the other fields set here
survive a route save. Change the name
in that form to rename the service: the old key and its generated children go, and the new name
takes over their ownership.

Deleting refuses while a route still points at the service, while another service lists it as a
backend, when one of its generated children is still used elsewhere, or when it is a composite
Traefik Manager does not manage. Editing always writes to the config file the service already
lives in, whichever file is selected.

**Manage this service** in the detail panel records ownership of a hand-written composite without
touching the file - it stays byte for byte unchanged. Ownership is what deleting, renaming and
choosing that service as a route backend require; editing it in place does not.

## Detail panel

Clicking a card opens the panel on the right.

| Block | Shows |
|---|---|
| Service Details | Type, provider, status, pass host header, and a **backend of** chip on a generated child |
| Backends | For a composite, each backend with its role and share; for a load balancer, its servers |
| Management | Composites only: whether Traefik Manager manages it, and the button to change that |
| Used by Routers | Every router pointing at the service |

## Requirements

Viewing needs no volume mounts: the list is read from the Traefik API (`/api/http/services`, `/api/tcp/services`, `/api/udp/services`), and the Traefik API URL must be configured in **Settings - Connection**.

Creating, editing and deleting write to your dynamic config files, so those need the same mount the Routes tab uses. Without it the tab still works as a read-only view.

With a remote agent selected, the same actions write to that agent's config files instead, and ownership is recorded against that server.

Deleting a service a route still points at, or that another service lists as a backend, is refused and the message names them. Confirm and Traefik Manager deletes those routes, removes the service from the parents that listed it, deletes any parent left with no backends, and then deletes the service. A generated child another service still uses is kept.

A weighted, mirroring or failover service cannot use itself as a backend, directly or through another service. Traefik expands such a loop forever on load and runs out of memory, so the save is refused before anything is written.

## Notes

- This tab is always visible - it cannot be disabled
- Use the **Routes** tab to create and manage routes; a route's backend rows can reference services created here

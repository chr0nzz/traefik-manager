# Route Map Tab

The **Route Map** tab shows a topology view of your Traefik routing setup as a 4-column connection map.

## Enabling the tab

The Route Map tab is hidden by default. To show it, go to **Settings - Interface - Tabs** and toggle **Route Map** on. The preference is saved to `manager.yml` and persists across restarts.

---

## Topology view

A 4-column connection map: **Entry Points - Routes - Middlewares - Services**, connected by Bezier curves.

Node positions are computed automatically using the [dagre](https://github.com/dagrejs/dagre) graph layout engine. Columns spread to fill the full available width and bezier curves are drawn from live DOM element positions, so connections are always pixel-accurate regardless of filtering or grouping.

Each column has a solid colored header and semi-transparent node cards:

| Column | Color |
|--------|-------|
| Entry Points | Teal |
| Routes - HTTP | Blue |
| Routes - TCP | Green |
| Routes - UDP | Amber |
| Middlewares | Purple |
| Services | Orange |

Bezier curves run between columns. Curves are drawn above column lane backgrounds but below node cards so they remain visible when crossing through intermediate columns (e.g. a direct route-to-service connection that passes through the middleware lane).

**Hover** a route node to highlight its full path:
- All unrelated nodes dim to 10% opacity
- The active route, its entry point(s), middleware(s), and service highlight with a box shadow
- A tooltip shows the route's target, entry points, and middlewares
- Move the mouse away to reset

**Click** any node to open a focused popup:
- The background dims and a mini route map appears centered on screen
- The mini map uses the same 4-column layout and node styles, scoped to only the selected node's connections
- A **details strip** below the header shows contextual information for the selected node: domain(s), target URL, protocol, TLS status, cert resolver, entry point address, or connected route count depending on node type
- Hover and click interactions work inside the popup - hover highlights a path, click drills into any connected node
- Clicking a **group node** opens the popup showing all routes in that group with their full topology
- Press **Esc** or click outside the popup to close it

Middleware nodes show a usage count badge (e.g. `3x`) when they are used by more than one route, reducing visual noise from dense curve fans.

---

## Route grouping

Each route is shown as an individual node in the topology. Routes that share a name prefix are visually related — clicking any route node opens the popup, and clicking a related node within the popup drills into its connections.

---

## Filtering

Open the **Filters** dropdown to access all filter options. An active-filter badge on the button shows how many non-default filters are set.

| Filter | Description |
|--------|-------------|
| Protocol | Show only HTTP, TCP, or UDP routes |
| Provider | Filter by Traefik provider (file, docker, kubernetes, etc.). Only shown when routes from more than one provider are present |
| Entry Point | Filter to routes that use a specific entry point. Only shown when more than one entry point exists |
| Group By | Control how routes are grouped - by name prefix (default), by domain, by first middleware, or ungrouped |

**Clear filters** resets all options to their defaults.

The Entry Points column updates to show only the entry points used by the currently visible (filtered) routes.

---

## Data source

Fetches from:

- `/api/routes` - routes from all providers (file-managed + live from Traefik API)
- `/api/traefik/entrypoints` - entry point names from the Traefik API

No extra mounts or configuration required beyond a working Traefik API connection.

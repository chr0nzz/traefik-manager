# Route Map Tab

The **Route Map** tab shows a topology view of your Traefik routing setup as a 4-column connection map.

## Enabling the tab

The Route Map tab is hidden by default. To show it, go to **Settings - Interface - Tabs** and toggle **Route Map** on. The preference is saved to `manager.yml` and persists across restarts.

---

## Topology view

A 4-column connection map: **Entry Points - Routes - Middlewares - Services**, connected by Bezier curves.

Each column has a solid colored header and semi-transparent node cards:

| Column | Color |
|--------|-------|
| Entry Points | Blue |
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
- Hover and click interactions work inside the popup - hover highlights a path, click drills into any connected node
- Press **Esc** or click outside the popup to close it

Middleware nodes show a usage count badge (e.g. `3x`) when they are used by more than one route, reducing visual noise from dense curve fans.

---

## Route grouping

Routes that share a name prefix are collapsed into a single group node showing a count badge (e.g. `x2`). The prefix is the first word when the name is split on `-`, `_`, or whitespace, with trailing digits stripped.

Examples: `komodo` and `komodo-redis` both get the prefix `komodo` and are grouped. `ph1` and `ph2` get the prefix `ph` and are grouped.

**Hover a group node** to expand it and reveal the individual child routes. The group stays expanded while the mouse is anywhere within the group area (header or children). Moving out collapses it and redraws curves.

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

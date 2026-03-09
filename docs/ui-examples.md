# Traefik Manager – UI Examples

This page showcases the **Traefik Manager UI** and the main workflows available in the interface.

All screenshots below are from the live interface.

---

# Initial Setup

When first launching Traefik Manager, you are guided through a simple setup process.

## Step 1

![Setup Step 1](images/setup-1.png)

## Step 2

![Setup Step 2](images/setup-2.png)

## Step 3

![Setup Step 3](images/setup-3.png)

## Step 4

![Setup Step 4](images/setup-4.png)

---

# Routes

Routes define how traffic is forwarded to services.

## Routes Overview

![Routes](images/routes.png)

## Route Details

![Route Edit](images/route-details.png)

## Editing a Route

![Route Edit](images/route-edit.png)

---

# Services

Services represent the backend targets that Traefik routes traffic to.

## Services Overview

![Services](images/services.png)

## Service Details

![Service Details](images/service-details.png)

---

# Middlewares

Middlewares allow you to modify requests before they reach your services.

Examples include:

* Authentication
* Rate limiting
* Headers
* Redirects

## Middleware List

![Middlewares](images/middlewares.png)

## Editing Middleware

![Middleware Editing](images/middleware-editing.png)

## Adding Middleware

![Add Middleware](images/add-middleware.png)

---

# Plugins

View and Monitor Active Plugins.

## Plugin List

![Plugins](images/plugins.png)

## Plugin Details

![Plugin Details](images/plugins-details.png)

---

# Certificates

View and Monitor TLS certificates used by Traefik.

## Certificates View

![Certificates](images/certs.png)

---

# Settings

Set new Password, Add domains and hide unused monitors

![Settings](images/setings.png)

# Summary

Traefik Manager provides a clean interface to manage and monitor:

* Routes
* Services
* Middlewares
* Plugins
* Certificates

All configuration is accessible through the UI, allowing quick inspection and editing of your Traefik configuration.


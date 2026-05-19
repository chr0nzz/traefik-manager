# Notification Webhooks

Traefik Manager can fire an HTTP POST to a webhook URL on every notification event - route saved, route deleted, backup restored, ping results, and more.

Configure webhooks in **Settings - Notifications**.

---

## Setup

1. Open **Settings** and go to the **Notifications** panel.
2. Select the **Type** that matches your destination.
3. Paste the **Webhook URL**.
4. For ntfy or generic endpoints that require authentication, fill in **Username** and **Password** (leave blank if not needed).
5. Click **Test** to send a test payload immediately.
6. Settings save automatically on blur.

---

## Supported types

### Discord

Select **Discord** and paste your Discord webhook URL (`https://discord.com/api/webhooks/...`).

Payload format:
```json
{
  "embeds": [{
    "title": "Route my-app saved",
    "color": 4088960,
    "footer": { "text": "Traefik Manager - 2026-05-18 12:00:00" }
  }]
}
```

Color changes by event type: green for success, yellow for warnings, red for errors, blue for info.

---

### Slack

Select **Slack** and paste an incoming webhook URL (`https://hooks.slack.com/...`).

Payload format:
```json
{ "text": ":white_check_mark: *Traefik Manager* - Route my-app saved" }
```

---

### ntfy.sh / self-hosted ntfy

Select **ntfy** and paste your topic URL - either the hosted service or a self-hosted instance.

```
https://ntfy.sh/your-topic
https://ntfy.yourdomain.com/your-topic
```

If your ntfy instance requires authentication, fill in **Username** and **Password**.

Headers sent:

| Header | Value |
|---|---|
| `X-Title` | `Traefik Manager` |
| `X-Priority` | `4` for warnings/errors, `3` for info/success |
| `X-Tags` | `warning`, `rotating_light`, `white_check_mark`, or `information_source` |

---

### Generic JSON

Sends a plain JSON body to any HTTP endpoint. Optionally set **Username** and **Password** for basic auth.

Payload format:
```json
{
  "event": "route_saved",
  "message": "Route my-app saved",
  "timestamp": "2026-05-18 12:00:00"
}
```

---

## Event types

| Type | When |
|---|---|
| `success` | Route saved, middleware saved, backup created |
| `warning` | Route deleted, backup restored, ping failures |
| `error` | Save errors, restore errors |
| `info` | Login events, ping all results, version updates |

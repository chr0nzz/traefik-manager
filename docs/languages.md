# Languages

Traefik Manager speaks more than English. Every page, dialog, tooltip, toast, notification and server message is translated, and the whole interface switches at once.

<img class="screenshot light-only" src="/images/light-multilingual.png" alt="Traefik Manager in four languages">
<img class="screenshot dark-only" src="/images/dark-multilingual.png" alt="Traefik Manager in four languages">

## Shipped languages

| Language | Tag |
|---|---|
| Čeština | `cs` |
| Dansk | `da` |
| Deutsch | `de` |
| English (Canada) | `en` |
| English (United Kingdom) | `en-GB` |
| English (United States) | `en-US` |
| Español | `es` |
| Français | `fr` |
| Français (Canada) | `fr-CA` |
| Nederlands | `nl` |
| Português | `pt` |
| Português (Brasil) | `pt-BR` |
| Русский | `ru` |
| 한국어 | `ko` |
| 中文 (简体) | `zh-Hans` |

The source text is Canadian English. The United Kingdom and United States variants only change spelling. A string that has no translation yet falls back to English.

## Picking a language

- **Language button** in the nav bar, left of the docs link. Hide it in **Settings - Interface - Navbar**.
- **Settings - Interface - General - Language**.
- **Setup wizard**: the Welcome step has the same list, so setup runs in your language and saves it when you finish.
- **Sign-in page**: the flag button in the top right corner switches the page for that visit, without changing the setting.
- **Follow system** (the default) uses each browser's language, and English when Traefik Manager does not have it.

The choice is saved in [`manager.yml`](/manager-yml#default-language) as `default_language`, so it follows you across browsers and devices.

To open one page in another language without changing the setting, put the tag in front of the path, such as `/de/` or `/fr-CA/routes`, or add `?lang=de`.

## What else follows the language

| | Language |
|---|---|
| Numbers, dates and times | The chosen language |
| Notifications in the bell | Each viewer's own language, even for events raised before they switched |
| Webhooks and digests (Discord, Slack, ntfy and the rest) | The language set in Settings, English when it is Follow system |
| API responses to an API key | Always English, so scripts keep working |
| Logs | Always English |

## Help translate

Translations happen on [Weblate](https://hosted.weblate.org/projects/traefik-manager/web-app/). Anyone can suggest a translation, and each language has a reviewer. To ask for a new language or report a wrong translation, open an issue in [tm-locale](https://github.com/chr0nzz/tm-locale).

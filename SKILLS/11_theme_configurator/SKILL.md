# Skill 11 -- Theme Configurator

## Description

Configures Shopify theme settings via the Shopify Admin REST API. Applies colour
schemes, sticky cart settings, and custom overrides to the active (main) theme.

## Endpoint

```
POST /theme-configurator/run
```

### Authentication

Pass a Bearer token in the `Authorization` header.

```
Authorization: Bearer <user_id>
```

## Input

| Field              | Type   | Required | Default      | Description                          |
|--------------------|--------|----------|--------------|--------------------------------------|
| `shop_domain`      | `str`  | Yes      | --           | Shopify store domain.                |
| `theme_preset`     | `str`  | No       | `"shrine"`   | Theme preset name.                   |
| `primary_color`    | `str`  | No       | `"#000000"`  | Primary colour hex.                  |
| `secondary_color`  | `str`  | No       | `"#ffffff"`  | Secondary colour hex.                |
| `accent_color`     | `str`  | No       | `"#ff6b35"`  | Accent colour hex.                   |
| `enable_sticky_cart`| `bool`| No       | `true`       | Enable sticky/drawer cart.           |
| `custom_overrides` | `dict` | No       | `{}`         | Additional theme setting overrides.  |

## Output

| Field               | Type     | Description                              |
|---------------------|----------|------------------------------------------|
| `shop_domain`       | `str`    | Echo of the shop domain.                 |
| `theme_id`          | `str`    | ID of the modified theme.                |
| `theme_name`        | `str`    | Name of the modified theme.              |
| `settings_modified` | `str[]`  | List of setting keys that were changed.  |
| `success`           | `bool`   | Whether the operation succeeded.         |

## Caching

No caching -- this is a write operation.

---
name: shopify-product-cloner
description: Clona prodotti su Shopify da qualsiasi URL — pagina prodotto singola, collezione, o homepage di uno store. Usa questa skill ogni volta che l'utente vuole importare, clonare, copiare o "koopyare" prodotti da un sito esterno verso il proprio Shopify, anche se non menziona esplicitamente la parola "clona". Gestisce automaticamente: estrazione dati (ibrido Shopify /products.json + Playwright fallback), download e re-upload immagini su CDN Shopify, deduplica, rewrite o traduzione copy via AI, pricing con markup, retry e rate limiting. Input: URL sorgente + credenziali Shopify + opzioni. Output: lista prodotti importati con ID Shopify.
---

# Shopify Product Cloner

Skill autonoma per clonare prodotti verso uno store Shopify partendo da qualsiasi URL sorgente.
È il motore "Koopy" universale: funziona su store Shopify (via `/products.json`) e su qualsiasi altro ecom (via Playwright + JSON-LD + heuristics).

## Quando triggerare

Attiva questa skill quando l'utente esprime intenti come:

- "clona questo prodotto / questa collezione / questo store"
- "importami i prodotti da <url>"
- "koopya <url>"
- "copia il catalogo di <brand> sul mio shop"
- "prendi questo prodotto e mettilo sul mio Shopify con markup 2x"
- "traduci e importa questi prodotti in inglese"
- "fammi il rewrite delle descrizioni e caricale"

Attiva anche quando l'utente incolla un URL che sembra una pagina prodotto/collezione/homepage di un ecom, e chiede operazioni sul proprio store Shopify.

## Input (JSON)

L'agent madre prepara un file JSON con questa shape e lo passa come `--input <path>`:

```json
{
  "source_url": "https://example.com/products/awesome-item",
  "shopify_shop": "mystore.myshopify.com",
  "shopify_access_token": "shpat_xxx",
  "options": {
    "markup_multiplier": 2.5,
    "target_language": "en",
    "target_market": "US",
    "copy_mode": "rewrite",
    "rewrite_instructions": "tono più urgente, aggiungi scarcity",
    "publish": false,
    "collection_handle": "imported-products",
    "max_products": 50
  }
}
```

### Campi input

| Campo | Tipo | Required | Default | Note |
|---|---|---|---|---|
| `source_url` | string | sì | — | Può puntare a prodotto, collezione o homepage |
| `shopify_shop` | string | sì | — | `mystore.myshopify.com` |
| `shopify_access_token` | string | sì | — | Admin API token, scope `write_products` |
| `options.markup_multiplier` | number | no | `1.0` | Es. `2.5` = prezzo × 2.5 |
| `options.target_language` | string (ISO) | no | lingua sorgente | Se presente e diversa, traduce |
| `options.target_market` | string | no | — | Es. `US`, `IT` (influenza rounding prezzo) |
| `options.copy_mode` | `clone`\|`rewrite`\|`translate` | no | `clone` | |
| `options.rewrite_instructions` | string | no | — | Custom prompt AI per rewrite |
| `options.publish` | boolean | no | `false` | `true` = `ACTIVE`, altrimenti `DRAFT` |
| `options.collection_handle` | string | no | — | Collezione Shopify destinazione |
| `options.max_products` | number | no | `100` | Hard cap modalità collezione/homepage |

## Come invocare

```bash
cd shopify-product-cloner
node scripts/clone.js --input /path/to/input.json
```

### Env richieste

L'agent madre deve iniettare:

- `OPENROUTER_API_KEY` — solo se `copy_mode !== "clone"` (usa DeepSeek V3 via OpenRouter)

Le credenziali Shopify NON vanno in env: arrivano nel JSON input (multi-tenant).

### Installazione dipendenze (una tantum)

```bash
cd shopify-product-cloner/scripts
npm install
npx playwright install chromium
```

## Output

Su **stdout**, un JSON array:

```json
[
  {
    "source_url": "https://example.com/products/x",
    "shopify_product_id": "gid://shopify/Product/1234567890",
    "shopify_handle": "awesome-item-clone",
    "status": "created",
    "images_uploaded": 6,
    "variants_count": 9
  },
  {
    "source_url": "https://example.com/products/y",
    "shopify_product_id": null,
    "shopify_handle": null,
    "status": "skipped",
    "skipped_reason": "already_imported"
  },
  {
    "source_url": "https://example.com/products/z",
    "shopify_product_id": null,
    "shopify_handle": null,
    "status": "error",
    "error": "Extraction failed: no JSON-LD and no matching selectors"
  }
]
```

Su **stderr**, log umano-leggibile con prefisso `[clone]`.

Valori possibili di `status`: `created`, `skipped`, `error`.

## Logica di routing (riassunto)

1. Parser URL:
   - `/products/<handle>` → single product
   - `/collections/<handle>` (no `/products/`) → collection
   - Root (`/` o solo dominio) → homepage (tutti i prodotti)
2. Detection Shopify: `GET {origin}/products.json?limit=1` — se 200 + JSON valido con `products` array → Path A (nativo).
3. Altrimenti → Path B (Playwright + JSON-LD + heuristics).

## Pipeline per ogni prodotto

1. **Dedup check** — handle esistente o metafield `custom.source_url` matching → skip.
2. **Copy transform** — `clone` / `rewrite` / `translate` (AI via OpenRouter se non clone).
3. **SEO** — slugify handle (≤80 char), title ≤70 char se `target_market`, image alt generato, `meta_description` via metafield `global.description_tag`.
4. **Pricing** — `price = source × markup`, rounding `.99`/`.00`/`.95` in base a `target_market`, `compare_at_price = price × 1.3` se markup > 1.
5. **productCreate** (GraphQL 2025-10) con `status: ACTIVE|DRAFT`, salva `custom.source_url` metafield.
6. **Upload immagini** — `stagedUploadsCreate` → PUT → `productCreateMedia`. Retry con `Referer` header su hotlink 403.
7. **Collection assignment** — `collectionAddProducts` se `collection_handle` fornito.

## Quando leggere le references

- **Sito non-Shopify non estrae correttamente** (WooCommerce/Magento/BigCommerce/Squarespace/Shopify custom) → leggi `references/extraction-patterns.md` per i selettori specifici e decidere se aggiungere un pattern.
- **Errori 429/430 o GraphQL throttle / varianti mismatch / immagini 403** → leggi `references/troubleshooting.md`.
- **Dubbi su mutation GraphQL, shape input, metafield** → leggi `references/shopify-api.md`.

## Limiti noti

- Siti con **Cloudflare Turnstile** / Bot Fight Mode aggressivo → Playwright può essere bloccato. Ritorna `status: error` per il singolo URL.
- Siti JS-heavy con **auth wall** (login-gated shop) → non supportato.
- **Varianti a matrice** su alcuni WooCommerce v2 custom → estrazione parziale, documentata in `references/troubleshooting.md`.
- **Digital products** / subscriptions / bundles → clonati come physical standard, l'agent madre dovrebbe riconfigurarli post-import se necessario.
- Immagini servite via **signed URL** a scadenza breve → se il download avviene molto dopo l'estrazione, può fallire. La pipeline mantiene `extract → upload` ravvicinato per mitigare.

## Idempotenza

Rilanciare la stessa `input.json` è sicuro: il dedup (handle + metafield `custom.source_url`) fa skip dei prodotti già importati. Per re-importare davvero, cancellare manualmente il prodotto Shopify o rimuovere la metafield.

## Quando NON usare questa skill

- L'utente vuole **modificare** prodotti esistenti su Shopify (usa una skill di editing).
- L'utente vuole creare prodotti da zero senza sorgente (usa una skill di PDP building).
- L'utente vuole sincronizzare in tempo reale (questa è una clonazione one-shot).

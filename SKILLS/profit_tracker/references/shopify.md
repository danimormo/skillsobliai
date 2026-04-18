# Shopify Admin API — implementation notes

All reads go through the **GraphQL Admin API** (`/admin/api/{version}/graphql.json`).
We pin `SHOPIFY_API_VERSION` (see `INTEGRATION.md`) because REST/GraphQL
field names drift between quarterly versions.

---

## 1. Required scopes

```
read_orders
read_all_orders                    # needed for >60 days of history
read_products                      # for variant.cost (COGS)
read_inventory                     # same
read_shipping                      # fulfillment.shipping_cost
read_fulfillments
read_shopify_payments_payouts      # for accurate SP fees
read_shopify_payments_disputes     # chargeback fees
read_shopify_payments_bank_accounts
```

Without `read_all_orders` Shopify returns only the last 60 days of orders
and silently truncates older pages. `shopify_client.py` detects this by
inspecting the first page's `pageInfo.startCursor` age and raises
`InvalidApiKeyError("missing read_all_orders scope")` if the user asked
for >60 d.

---

## 2. Pagination & rate limits

- GraphQL uses **cost-based** throttling. Each query consumes points; the
  bucket is 1000 pts with a 50 pts/s leak (Plus: 2000 / 100).
- Response headers include `X-Shopify-Shop-Api-Call-Limit` and the
  `extensions.cost` block — we read both.
- `shopify_client.py::paginate` backs off with
  `sleep = max(0, (requested_cost - actually_available) / 50)` whenever
  `extensions.cost.throttleStatus.currentlyAvailable < 100`.
- Max page size for orders: 250. We default to 100 to keep query cost
  under 400 points.

---

## 3. Orders query (the big one)

```graphql
query Orders($first: Int!, $after: String, $query: String!) {
  orders(first: $first, after: $after, query: $query, sortKey: CREATED_AT) {
    pageInfo { hasNextPage endCursor }
    nodes {
      id
      createdAt
      displayFinancialStatus
      currencyCode
      currentTotalPriceSet     { shopMoney { amount currencyCode } }
      currentSubtotalPriceSet  { shopMoney { amount currencyCode } }
      totalDiscountsSet        { shopMoney { amount currencyCode } }
      totalShippingPriceSet    { shopMoney { amount currencyCode } }
      totalTaxSet              { shopMoney { amount currencyCode } }
      totalRefundedSet         { shopMoney { amount currencyCode } }
      transactions(first: 10) {
        gateway                # "shopify_payments" | "stripe" | "paypal" | "airwallex" | …
        kind                   # "sale" | "refund" | "capture" | …
        status
        amountSet { shopMoney { amount currencyCode } }
        fees {
          amount { amount currencyCode }
          flatFee { amount currencyCode }
          flatFeeName
          rate                 # decimal, e.g. 0.024
          type                 # "acquirer" | "intl" | "currency" | …
        }
      }
      lineItems(first: 100) {
        nodes {
          quantity
          variant {
            id
            inventoryItem {
              unitCost { amount currencyCode }     # ← this is COGS
            }
          }
        }
      }
      fulfillments(first: 10) {
        totalCostSet { shopMoney { amount currencyCode } }
      }
    }
  }
}
```

The `$query` filter we use:

```
created_at:>=YYYY-MM-DDT00:00:00Z created_at:<=YYYY-MM-DDT23:59:59Z
```

**Timezone gotcha:** Shopify interprets these as UTC. If the store runs in
`Europe/Rome` we shift the bounds ±2 h before sending, then trust
`createdAt` (which is UTC) when bucketing into daily rows.

---

## 4. Why we use `currentTotalPriceSet`, not `totalPriceSet`

`totalPrice` is frozen at the moment of checkout. `currentTotalPrice` is
updated after refunds, edits and cancellations — which is what you want for
P&L reconciliation. Triple Whale and Shopify Analytics both use the
`current*` family; we do the same for parity.

---

## 5. `transactions.fees` — the magic field

Since API version `2023-07` Shopify exposes actual processor fees per
transaction *for Shopify Payments*. For non-SP gateways the `fees` array is
empty and we fall back to the fee tables in
`references/payment_processors.md`.

The detection logic lives at
`scripts/processing_fees.py::fees_for_transaction`:

1. If `transaction.fees` is non-empty → sum as-is (this is ground truth).
2. Else → look up the gateway in our fee table and estimate.
3. Mark the processor as `estimated` in `DataQuality`.

---

## 6. Variant cost (COGS)

`variant.inventoryItem.unitCost` is the merchant-set cost. It can be:

- `null` — the merchant never filled it in. `pnl_builder` treats this as
  zero AND adds a warning
  `"cogs missing on N variants (M orders affected)"`.
- Stored in the **store's currency**, not the order currency. The client
  re-labels it with `currencyCode` of the shop (fetched once at init from
  the `shop` query).

---

## 7. Refunds

We don't query `refunds` separately — `currentTotalPrice` already reflects
them. However we DO pull each refund's transaction to attribute the refund
fee correctly per processor (Stripe, for instance, refunds the %% fee but
*not* the fixed 0.25 €; PayPal refunds nothing since Nov 2019).

---

## 8. Shopify Payments payouts

Used as a cross-check, not as a primary source. Payouts lag by 2 business
days and don't break down by order, so they are unreliable for per-order
attribution. We read them via:

```graphql
query Payouts($first:Int!, $after:String, $query:String!) {
  shopifyPaymentsAccount {
    payouts(first:$first, after:$after, query:$query) {
      nodes {
        issuedAt
        net { amount currencyCode }
        gross { amount currencyCode }
        adjustments { amount { amount currencyCode } type }
      }
    }
  }
}
```

and log `sum(net) − sum(computed_net)` as a `data_quality.warnings` entry
if the delta >1 %.

# Payment processors — fee tables and edge cases

Triple Whale's dirty secret is that most fees are **computed**, not
**fetched**, because processor APIs either don't expose per-transaction
fees or lag too much. We do the same: we prefer ground truth where Shopify
gives it (`transaction.fees` for Shopify Payments) and fall back to tables
for everyone else.

All percentages are applied to the transaction's gross amount (inclusive of
tax & shipping — matching Stripe/PayPal's actual billing behaviour).

---

## 1. Shopify Payments

**Source of truth:** `transaction.fees` in the Shopify GraphQL response
(see `references/shopify.md` §5). No estimation needed.

If `fees` is empty (rare, happens on test orders or very old accounts) use
this fallback:

| Region       | Online card          | Domestic        | International   |
|--------------|----------------------|-----------------|-----------------|
| US           | 2.9 % + $0.30        | —               | +1.5 %          |
| UK           | 1.5 % + £0.20        | —               | +2.0 %          |
| EU (Ireland) | 1.6 % + €0.25        | —               | +0.3–1.5 %      |
| AU           | 1.7 % + A$0.30       | —               | +2.0 %          |

---

## 2. Stripe

Stripe's API *does* expose `balance_transaction.fee` per charge, but
calling Stripe for every order doubles latency. We compute from the fee
table instead and optionally reconcile with the Stripe payout export.

| Plan       | Europe cards          | Non-EEA cards   | Currency conversion |
|------------|-----------------------|-----------------|---------------------|
| Standard   | 1.5 % + €0.25         | 2.5 % + €0.25   | +2 %                |
| UK cards   | 1.5 % + £0.20         | 2.5 % + £0.20   | +2 %                |
| US cards   | 2.9 % + $0.30         | 3.9 % + $0.30   | +1 %                |

### Refunds
- The fixed fee (€0.25 / £0.20 / $0.30) is **not** returned on refund.
- The percentage fee **is** returned (since Sep 2019).
- Chargebacks cost €15 flat, non-refundable.

### Implementation
`processing_fees.stripe_fee(amount, currency, card_region)` returns
`(fee, estimated=True)`. The `estimated` flag is propagated to
`DataQuality.estimated_channels`.

---

## 3. PayPal

PayPal is the worst offender: their Transaction API exists but requires a
separate OAuth flow and has a 3-day lag. We fall back to their commercial
rate card:

| Flow                              | EU domestic     | Intra-EEA       | International   |
|-----------------------------------|-----------------|-----------------|-----------------|
| Commercial payment (card/wallet)  | 2.49 % + €0.35  | 2.99 %          | 4.99 %          |
| Express Checkout                  | 2.49 % + €0.35  | 2.99 %          | 4.99 %          |
| Micropayments (<€10, opt-in)      | 4.99 % + €0.05  | —               | —               |

### Refunds
- **Nothing** is returned on refund since Nov 2019. We therefore count the
  full fee as a cost even when the order is fully refunded.

### Currency conversion
- PayPal adds 3–4 % to the ECB mid-rate. If the order currency differs
  from the merchant's payout currency, add 3.5 % to the computed fee.

---

## 4. Airwallex

Airwallex is the new-kid on the block; their Payments API `/payment_intents`
endpoint returns `fee.amount` directly. Prefer that over the table below
whenever the Airwallex integration is configured.

| Card type          | Rate            |
|--------------------|-----------------|
| Local card         | 1.4 % + €0.20   |
| Premium card       | 1.9 % + €0.20   |
| International card | 2.7 % + €0.20   |
| Currency conversion| +0.6 %          |

### Refunds
- Percentage **and** fixed fee are returned on refund. Unusual but documented.

---

## 5. Other / fallback

If we see a gateway name we don't recognise (e.g. `klarna`, `mollie`,
`sofort`) we apply a conservative **2.5 %** flat fee and flag the order.
The user sees `"unknown gateway: klarna — applied 2.5% estimate"` in
`DataQuality.warnings`.

---

## 6. Apple Pay / Google Pay / Shop Pay

These are *not* separate gateways. They are routed through the underlying
processor (usually Shopify Payments or Stripe) and share its fee schedule.
`transaction.gateway` will read `shopify_payments` even when
`transaction.paymentDetails` says `apple_pay`. No special handling needed.

---

## 7. Cross-check

At the end of each run `processing_fees.reconcile()` compares our computed
total with the Shopify Payments payout total (if available) and emits a
warning if the delta >1 %. This is the fastest early-warning for a
fee-table that has drifted against reality.

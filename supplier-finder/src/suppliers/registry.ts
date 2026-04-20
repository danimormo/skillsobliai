import type { BaseSupplier } from './base.js';
import type { SupplierName } from '../types.js';
import { AliExpressSupplier } from './aliexpress.js';

/**
 * Registry of supplier crawlers.
 *
 * Step 5 wires only AliExpress; Step 6 fills in the rest. Any key mapped to
 * `undefined` here is surfaced by the orchestrator as
 * `{status: NOT_AVAILABLE, reason: "crawler not implemented"}` so the shape
 * of the final response is always stable.
 */
export const SUPPLIER_REGISTRY: Record<SupplierName, BaseSupplier | undefined> = {
  AliExpress: new AliExpressSupplier(),
  Alibaba: undefined,
  '1688': undefined,
  Temu: undefined,
  Shein: undefined,
  Taobao: undefined,
  DHgate: undefined,
  CJDropshipping: undefined,
  Spocket: undefined,
};

export function getSupplier(name: SupplierName): BaseSupplier | undefined {
  return SUPPLIER_REGISTRY[name];
}

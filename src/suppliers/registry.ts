import type { BaseSupplier } from './base.js';
import type { SupplierName } from '../types.js';
import { AliExpressSupplier } from './aliexpress.js';
import { AlibabaSupplier } from './alibaba.js';
import { Alibaba1688Supplier } from './alibaba1688.js';
import { TemuSupplier } from './temu.js';
import { SheinSupplier } from './shein.js';
import { TaobaoSupplier } from './taobao.js';
import { DHgateSupplier } from './dhgate.js';
import { CJDropshippingSupplier } from './cjdropshipping.js';
import { SpocketSupplier } from './spocket.js';

/**
 * Registry of supplier crawlers. Order matches the declared priority.
 * A `null` value would signal "crawler not implemented" — we now have all
 * nine online; the orchestrator still handles the missing case defensively.
 */
export const SUPPLIER_REGISTRY: Record<SupplierName, BaseSupplier> = {
  AliExpress: new AliExpressSupplier(),
  Alibaba: new AlibabaSupplier(),
  '1688': new Alibaba1688Supplier(),
  Temu: new TemuSupplier(),
  Shein: new SheinSupplier(),
  Taobao: new TaobaoSupplier(),
  DHgate: new DHgateSupplier(),
  CJDropshipping: new CJDropshippingSupplier(),
  Spocket: new SpocketSupplier(),
};

export function getSupplier(name: SupplierName): BaseSupplier | undefined {
  return SUPPLIER_REGISTRY[name];
}

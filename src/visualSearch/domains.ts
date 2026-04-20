import type { SupplierName } from '../types.js';

/**
 * Map from supplier name to the set of root domains the supplier uses.
 * A single supplier can own multiple TLDs (Taobao ↔ tmall, Alibaba ↔ aliexpress)
 * or different regional hosts. Matching is performed against the *suffix* of
 * the candidate URL's hostname so subdomains like `m.aliexpress.com` or
 * `id.shein.com` are captured.
 */
export const SUPPLIER_DOMAINS: Record<SupplierName, readonly string[]> = {
  AliExpress: ['aliexpress.com', 'aliexpress.us', 'aliexpress.ru'],
  Alibaba: ['alibaba.com'],
  '1688': ['1688.com'],
  Temu: ['temu.com'],
  Shein: ['shein.com', 'sheinside.com'],
  Taobao: ['taobao.com', 'tmall.com'],
  DHgate: ['dhgate.com'],
  CJDropshipping: ['cjdropshipping.com', 'cjdropshipping.cn'],
  Spocket: ['spocket.co', 'spocketapp.com'],
};

export const ALL_SUPPLIER_DOMAINS: readonly string[] = Object.values(SUPPLIER_DOMAINS).flat();

export function matchSupplier(hostname: string): SupplierName | undefined {
  const h = hostname.toLowerCase();
  for (const [name, domains] of Object.entries(SUPPLIER_DOMAINS) as [
    SupplierName,
    readonly string[],
  ][]) {
    if (domains.some((d) => h === d || h.endsWith(`.${d}`))) return name;
  }
  return undefined;
}

/** True if the hostname belongs to any known supplier (for pre-filtering). */
export function isSupplierDomain(hostname: string): boolean {
  return matchSupplier(hostname) !== undefined;
}

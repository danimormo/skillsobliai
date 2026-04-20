import { log, toHandle } from './utils.js';

/**
 * Check if a product is already imported by handle OR by custom.source_url metafield.
 * @param {import('./shopify-client.js').ShopifyClient} client
 * @param {{ title: string, sourceUrl: string }} draft
 * @returns {Promise<{exists: boolean, reason?: string, existing?: {id:string,handle:string}}>}
 */
export async function checkDuplicate(client, draft) {
  const handle = toHandle(draft.title);
  try {
    const byHandle = await client.findProductByHandle(handle);
    if (byHandle) {
      log.info(`Dedup: handle "${handle}" already exists → skip`);
      return { exists: true, reason: 'already_imported', existing: byHandle };
    }
  } catch (err) {
    log.warn(`Dedup by handle failed (continuing): ${err.message}`);
  }

  try {
    const bySource = await client.findProductBySourceUrl(draft.sourceUrl);
    if (bySource) {
      log.info(`Dedup: metafield source_url matches existing product → skip`);
      return { exists: true, reason: 'already_imported', existing: bySource };
    }
  } catch (err) {
    log.warn(`Dedup by metafield failed (continuing): ${err.message}`);
  }

  return { exists: false };
}

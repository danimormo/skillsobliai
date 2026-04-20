import { log, retry, originOf } from './utils.js';

const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36';

/**
 * Guess a MIME type from an image URL.
 */
function guessMime(url) {
  const u = url.toLowerCase().split('?')[0];
  if (u.endsWith('.png')) return 'image/png';
  if (u.endsWith('.webp')) return 'image/webp';
  if (u.endsWith('.gif')) return 'image/gif';
  if (u.endsWith('.avif')) return 'image/avif';
  return 'image/jpeg';
}

/**
 * Extract a safe filename from a URL.
 */
function filenameFromUrl(url, fallback = 'image.jpg') {
  try {
    const u = new URL(url);
    const name = u.pathname.split('/').pop();
    if (!name) return fallback;
    const clean = name.split('?')[0];
    return clean || fallback;
  } catch {
    return fallback;
  }
}

/**
 * Fetch image bytes with a browser-like header set. Retries once with Referer on 403.
 * @param {string} url
 * @returns {Promise<{ buffer: ArrayBuffer, mimeType: string, filename: string }>}
 */
async function fetchImage(url) {
  return retry(
    async () => {
      const headers = { 'User-Agent': UA, Accept: 'image/*,*/*;q=0.8' };
      let res = await fetch(url, { headers });
      if (res.status === 403 || res.status === 401) {
        log.warn(`Image ${res.status}, retry with Referer: ${url}`);
        headers.Referer = originOf(url) || '';
        res = await fetch(url, { headers });
      }
      if (!res.ok) throw new Error(`Image fetch failed ${res.status} for ${url}`);
      const buffer = await res.arrayBuffer();
      return {
        buffer,
        mimeType: res.headers.get('content-type') || guessMime(url),
        filename: filenameFromUrl(url),
      };
    },
    { retries: 3, baseMs: 1500, maxMs: 10000, onRetry: (e, n) => log.warn(`image retry ${n}: ${e.message}`) }
  );
}

/**
 * PUT the image buffer to a Shopify staged upload target.
 * Shopify staged uploads for images default to AWS S3 with POST + form-data OR a direct PUT.
 * We support both: if target.parameters present → POST form-data, else → PUT.
 */
async function uploadToStagedTarget(target, buffer, mimeType, filename) {
  if (target.parameters && target.parameters.length > 0) {
    // POST multipart form-data
    const form = new FormData();
    for (const p of target.parameters) form.append(p.name, p.value);
    form.append('file', new Blob([buffer], { type: mimeType }), filename);
    const res = await fetch(target.url, { method: 'POST', body: form });
    if (!res.ok && res.status !== 201 && res.status !== 204) {
      const t = await res.text();
      throw new Error(`Staged upload (POST) failed ${res.status}: ${t.slice(0, 300)}`);
    }
  } else {
    const res = await fetch(target.url, {
      method: 'PUT',
      headers: { 'Content-Type': mimeType, 'Content-Length': String(buffer.byteLength) },
      body: buffer,
    });
    if (!res.ok) {
      const t = await res.text();
      throw new Error(`Staged upload (PUT) failed ${res.status}: ${t.slice(0, 300)}`);
    }
  }
}

/**
 * Upload all images for a product: fetch → stagedUploadsCreate → PUT → productCreateMedia.
 * @param {import('./shopify-client.js').ShopifyClient} client
 * @param {string} productId  gid
 * @param {Array<{ src: string, alt?: string, position?: number }>} images
 * @param {string} productTitle  used as fallback alt
 * @returns {Promise<number>}  count of successfully uploaded images
 */
export async function uploadProductImages(client, productId, images, productTitle) {
  if (!images || !images.length) return 0;
  const mediaForProduct = [];
  let uploaded = 0;

  for (const img of images) {
    try {
      const { buffer, mimeType, filename } = await fetchImage(img.src);
      const target = await client.stagedUploadCreate({
        filename,
        mimeType,
        fileSize: buffer.byteLength,
        httpMethod: 'POST',
        resource: 'IMAGE',
      });
      await uploadToStagedTarget(target, buffer, mimeType, filename);
      mediaForProduct.push({
        originalSource: target.resourceUrl,
        alt: img.alt || `${productTitle} - image ${img.position || mediaForProduct.length + 1}`,
        mediaContentType: 'IMAGE',
      });
      uploaded++;
    } catch (err) {
      log.warn(`Image upload failed, skipping: ${img.src} → ${err.message}`);
    }
  }

  if (mediaForProduct.length) {
    await client.productCreateMedia(productId, mediaForProduct);
  }
  return uploaded;
}

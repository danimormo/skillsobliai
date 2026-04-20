import { log, retry } from './utils.js';

const OPENROUTER_URL = 'https://openrouter.ai/api/v1/chat/completions';
const MODEL = 'deepseek/deepseek-chat'; // DeepSeek V3 via OpenRouter

/**
 * Call OpenRouter chat completion with retry + timeout.
 * Returns the plain string response from the first choice.
 * @param {Array<{role:string,content:string}>} messages
 * @param {{ temperature?: number, maxTokens?: number }} [opts]
 */
async function chat(messages, opts = {}) {
  const key = process.env.OPENROUTER_API_KEY;
  if (!key) throw new Error('OPENROUTER_API_KEY env var required for copy transformation');

  return retry(
    async () => {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 60000);
      try {
        const res = await fetch(OPENROUTER_URL, {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${key}`,
            'Content-Type': 'application/json',
            'HTTP-Referer': 'https://skillsobliai',
            'X-Title': 'shopify-product-cloner',
          },
          body: JSON.stringify({
            model: MODEL,
            messages,
            temperature: opts.temperature ?? 0.7,
            max_tokens: opts.maxTokens ?? 2000,
          }),
          signal: controller.signal,
        });
        if (!res.ok) {
          const txt = await res.text();
          throw new Error(`OpenRouter HTTP ${res.status}: ${txt.slice(0, 400)}`);
        }
        const json = await res.json();
        const content = json?.choices?.[0]?.message?.content;
        if (!content) throw new Error('OpenRouter returned empty content');
        return content;
      } finally {
        clearTimeout(timeout);
      }
    },
    { retries: 3, baseMs: 1500, maxMs: 10000, onRetry: (e, n) => log.warn(`OpenRouter retry ${n}: ${e.message}`) }
  );
}

/**
 * Extract JSON object from a possibly-chatty LLM response.
 * @param {string} text
 */
function parseLooseJson(text) {
  try {
    return JSON.parse(text);
  } catch {}
  const match = text.match(/\{[\s\S]*\}/);
  if (match) {
    try {
      return JSON.parse(match[0]);
    } catch {}
  }
  return null;
}

/**
 * Sanitize and return the title as-is for clone mode.
 */
function cloneMode(product) {
  return {
    title: product.title,
    bodyHtml: product.bodyHtml,
    images: product.images,
  };
}

/**
 * Rewrite the copy (same language) to improve hook, benefit, scarcity.
 * @param {import('./extractor-shopify.js').ExtractedProduct} product
 * @param {{ instructions?: string }} opts
 */
async function rewriteMode(product, opts = {}) {
  const sys = `You are an expert DTC copywriter. Rewrite product title and HTML description to maximize conversion.
Preserve the original language exactly. Preserve HTML structure and tags from the input description.
Improve: hook (first sentence), clear benefits, scarcity/urgency when appropriate, scannability.
Do NOT invent features that the original doesn't mention. Do NOT mention competitor brand names.
Return ONLY valid JSON: {"title": "...", "bodyHtml": "..."} — no prose, no markdown fences.`;

  const user = `Original title: ${product.title}
Original description (HTML):
${product.bodyHtml || '<i>(empty)</i>'}

${opts.instructions ? `Additional instructions: ${opts.instructions}` : ''}

Return the rewritten title and bodyHtml as JSON.`;

  const raw = await chat(
    [
      { role: 'system', content: sys },
      { role: 'user', content: user },
    ],
    { temperature: 0.8, maxTokens: 2000 }
  );
  const parsed = parseLooseJson(raw);
  if (!parsed || !parsed.title) {
    log.warn('Rewrite failed to parse, falling back to clone');
    return cloneMode(product);
  }
  return {
    title: parsed.title,
    bodyHtml: parsed.bodyHtml || product.bodyHtml,
    images: product.images,
  };
}

/**
 * Translate title + bodyHtml + image alt to a target language.
 */
async function translateMode(product, opts = {}) {
  const targetLang = opts.targetLanguage;
  if (!targetLang) return cloneMode(product);

  const sys = `You are a professional ecommerce translator. Translate product copy to language code "${targetLang}".
Preserve HTML structure and tags EXACTLY. Translate only text nodes and attribute values like alt/title.
Return ONLY valid JSON: {"title": "...", "bodyHtml": "...", "imageAlts": ["...","..."]} — no prose.
imageAlts must have one entry per input image, in the same order.`;

  const user = `Title: ${product.title}
Description (HTML):
${product.bodyHtml || '<p></p>'}

Image alts to translate (in order):
${JSON.stringify(product.images.map((img) => img.alt || ''))}`;

  const raw = await chat(
    [
      { role: 'system', content: sys },
      { role: 'user', content: user },
    ],
    { temperature: 0.3, maxTokens: 3000 }
  );
  const parsed = parseLooseJson(raw);
  if (!parsed || !parsed.title) {
    log.warn('Translate failed to parse, falling back to clone');
    return cloneMode(product);
  }
  const images = product.images.map((img, i) => ({
    ...img,
    alt: (parsed.imageAlts && parsed.imageAlts[i]) || img.alt,
  }));
  return {
    title: parsed.title,
    bodyHtml: parsed.bodyHtml || product.bodyHtml,
    images,
  };
}

/**
 * Transform copy according to mode.
 * @param {import('./extractor-shopify.js').ExtractedProduct} product
 * @param {{ mode: 'clone'|'rewrite'|'translate', targetLanguage?: string, instructions?: string }} opts
 * @returns {Promise<{ title: string, bodyHtml: string, images: import('./extractor-shopify.js').ExtractedImage[] }>}
 */
export async function transformCopy(product, opts) {
  const mode = opts.mode || 'clone';
  if (mode === 'clone') return cloneMode(product);
  if (mode === 'rewrite') return rewriteMode(product, { instructions: opts.instructions });
  if (mode === 'translate') return translateMode(product, { targetLanguage: opts.targetLanguage });
  log.warn(`Unknown copy_mode "${mode}", using clone`);
  return cloneMode(product);
}

import { describe, it, expect } from 'vitest';
import { yandexImageSearch } from '../src/visualSearch/yandexImages.js';
import { bingVisualSearch } from '../src/visualSearch/bingVisual.js';
import type { SearchInput } from '../src/types.js';

/**
 * Both Yandex and Bing require a public `sourceImageUrl` to operate. These
 * tests confirm the early-return guard fires before any browser context is
 * opened — without this invariant the orchestrator would waste ~800ms per
 * request on a doomed navigation whenever the input is a local upload.
 */
const baseInput: SearchInput = {
  requestId: 'guard',
  inputType: 'image',
  imagePath: '/tmp/x.jpg',
  keywords: [],
  warnings: [],
};

describe('visual search engine guards', () => {
  it('yandexImageSearch returns [] when no sourceImageUrl is set', async () => {
    const out = await yandexImageSearch(baseInput);
    expect(out).toEqual([]);
  });

  it('bingVisualSearch returns [] when no sourceImageUrl is set', async () => {
    const out = await bingVisualSearch(baseInput);
    expect(out).toEqual([]);
  });
});

/**
 * Lightweight string similarity helpers used to cross-check a candidate
 * supplier listing's title against the reference title/keywords when CLIP
 * is borderline (60-70 range) or unavailable.
 */

/** Classic iterative Levenshtein distance with O(min(|a|,|b|)) memory. */
export function levenshtein(a: string, b: string): number {
  if (a === b) return 0;
  if (!a.length) return b.length;
  if (!b.length) return a.length;
  // Ensure `a` is the shorter string for memory.
  if (a.length > b.length) [a, b] = [b, a];
  const prev = new Array<number>(a.length + 1);
  const curr = new Array<number>(a.length + 1);
  for (let i = 0; i <= a.length; i++) prev[i] = i;
  for (let j = 1; j <= b.length; j++) {
    curr[0] = j;
    for (let i = 1; i <= a.length; i++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      curr[i] = Math.min(
        curr[i - 1]! + 1, // insertion
        prev[i]! + 1, // deletion
        prev[i - 1]! + cost, // substitution
      );
    }
    for (let i = 0; i <= a.length; i++) prev[i] = curr[i]!;
  }
  return prev[a.length]!;
}

/** Normalized similarity (0-100) based on Levenshtein distance. */
export function textSimilarity(a: string, b: string): number {
  const A = normalize(a);
  const B = normalize(b);
  if (!A && !B) return 0;
  const maxLen = Math.max(A.length, B.length);
  if (maxLen === 0) return 0;
  const d = levenshtein(A, B);
  return Math.round((1 - d / maxLen) * 100);
}

/** Jaccard token overlap (0-100) — good for multi-word product titles. */
export function tokenOverlap(a: string, b: string): number {
  const ta = tokenize(a);
  const tb = tokenize(b);
  if (ta.size === 0 || tb.size === 0) return 0;
  let inter = 0;
  for (const t of ta) if (tb.has(t)) inter++;
  const union = ta.size + tb.size - inter;
  return Math.round((inter / union) * 100);
}

/**
 * Composite score used when validating a candidate title against the
 * reference: max of Jaccard token overlap and normalized Levenshtein.
 * Jaccard wins for reordered titles; Levenshtein wins for near-identical
 * strings with small typos. Taking the max is the simplest robust combiner.
 */
export function titleScore(reference: string, candidate: string): number {
  return Math.max(tokenOverlap(reference, candidate), textSimilarity(reference, candidate));
}

/** How many reference keywords appear (substring) in the candidate title. */
export function keywordHitRate(keywords: readonly string[], candidate: string): number {
  if (keywords.length === 0) return 0;
  const c = normalize(candidate);
  let hits = 0;
  for (const kw of keywords) if (c.includes(normalize(kw))) hits++;
  return Math.round((hits / keywords.length) * 100);
}

function normalize(s: string): string {
  return (s ?? '')
    .toLowerCase()
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function tokenize(s: string): Set<string> {
  return new Set(
    normalize(s)
      .split(/[^a-z0-9]+/)
      .filter((t) => t.length >= 2),
  );
}

// Base44 React component for the Shopify Saturation Scanner.
//
// Drop this into the Base44 dashboard (any page with a form + results area).
// The component:
//   1. accepts either a product URL or an image upload,
//   2. kicks off an async scan via the backend `POST /api/saturation-scan`
//      endpoint (which internally calls `enqueueScan`),
//   3. polls `/api/saturation-scan/:jobId` every 1.5 s for progress,
//   4. renders a live progress bar, store counter, zone badge, and a
//      per-market breakdown + a minimal heatmap table.
//
// The backend endpoint shape is intentionally simple so Base44 fetch works
// without any SDK.

import React, { useEffect, useMemo, useRef, useState } from "react";

const ZONE_STYLE = {
  green:  { bg: "#DCFCE7", fg: "#166534", label: "Blue ocean" },
  yellow: { bg: "#FEF9C3", fg: "#854D0E", label: "Moderate competition" },
  red:    { bg: "#FEE2E2", fg: "#991B1B", label: "Saturated market" },
};

function Badge({ zone }) {
  const s = ZONE_STYLE[zone] ?? { bg: "#E5E7EB", fg: "#111827", label: zone };
  return (
    <span style={{
      background: s.bg, color: s.fg, padding: "4px 10px",
      borderRadius: 999, fontWeight: 600, fontSize: 12, letterSpacing: 0.3,
    }}>
      {s.label.toUpperCase()}
    </span>
  );
}

function ProgressBar({ pct, stage }) {
  return (
    <div style={{ width: "100%" }}>
      <div style={{
        height: 8, borderRadius: 4, background: "#F3F4F6", overflow: "hidden",
      }}>
        <div style={{
          width: `${Math.min(100, Math.max(0, pct ?? 0))}%`,
          height: "100%",
          background: "linear-gradient(90deg,#6366F1,#8B5CF6)",
          transition: "width 0.4s ease",
        }} />
      </div>
      <div style={{ marginTop: 6, fontSize: 12, color: "#6B7280" }}>
        {stage ? `Stage: ${stage}` : "Starting…"} — {Math.round(pct ?? 0)}%
      </div>
    </div>
  );
}

function MarketRow({ row }) {
  const s = ZONE_STYLE[row.saturation_level] ?? ZONE_STYLE.green;
  return (
    <tr>
      <td style={{ padding: "8px 12px", fontWeight: 600 }}>{row.country}</td>
      <td style={{ padding: "8px 12px" }}>{row.store_count}</td>
      <td style={{ padding: "8px 12px" }}>
        <span style={{ background: s.bg, color: s.fg, padding: "2px 8px", borderRadius: 6 }}>
          {row.saturation_level}
        </span>
      </td>
      <td style={{ padding: "8px 12px" }}>{row.avg_price_usd ? `$${row.avg_price_usd}` : "—"}</td>
      <td style={{ padding: "8px 12px" }}>
        {row.opportunity_flag === "BLUE_OCEAN"
          ? <span style={{ color: "#0F766E", fontWeight: 600 }}>🌊 Blue ocean</span>
          : row.top_stores?.[0]?.domain ?? "—"}
      </td>
    </tr>
  );
}

export default function Base44Scanner({
  apiBaseUrl = "/api/saturation-scan",
  userId,
  onComplete,
}) {
  const [mode, setMode] = useState("url");            // "url" | "image"
  const [url, setUrl] = useState("");
  const [file, setFile] = useState(null);
  const [jobId, setJobId] = useState(null);
  const [progress, setProgress] = useState({ pct: 0, stage: null });
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const pollRef = useRef(null);

  const busy = jobId && !result && !error;

  useEffect(() => () => clearInterval(pollRef.current), []);

  async function startScan(e) {
    e.preventDefault();
    setError(null); setResult(null); setProgress({ pct: 0, stage: "submitting" });

    let body, headers;
    if (mode === "url") {
      headers = { "Content-Type": "application/json" };
      body = JSON.stringify({ url, userId });
    } else {
      if (!file) { setError("Select an image first"); return; }
      const fd = new FormData();
      fd.append("image", file);
      if (userId) fd.append("userId", userId);
      body = fd;
    }

    let res;
    try {
      res = await fetch(apiBaseUrl, { method: "POST", headers, body });
    } catch (err) {
      setError(`Network error: ${err.message}`); return;
    }
    if (!res.ok) { setError(`Scan kickoff failed: ${res.status}`); return; }
    const { jobId: id } = await res.json();
    setJobId(id);

    pollRef.current = setInterval(async () => {
      try {
        const r = await fetch(`${apiBaseUrl}/${id}`);
        if (!r.ok) return;
        const data = await r.json();
        if (data.progress) setProgress(data.progress);
        if (data.status === "done") {
          clearInterval(pollRef.current);
          setResult(data.result);
          onComplete?.(data.result);
        } else if (data.status === "failed") {
          clearInterval(pollRef.current);
          setError(data.error ?? "Scan failed");
        }
      } catch { /* keep polling */ }
    }, 1500);
  }

  const markets = useMemo(() => {
    if (!result) return [];
    const rows = [...result.markets];
    for (const bo of result.blue_ocean_details ?? []) {
      if (!rows.find((r) => r.country === bo.country)) rows.push(bo);
    }
    return rows;
  }, [result]);

  return (
    <div style={{
      fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, sans-serif",
      maxWidth: 900, margin: "0 auto", padding: 24,
    }}>
      <h2 style={{ marginBottom: 4 }}>Shopify Saturation Scanner</h2>
      <p style={{ color: "#6B7280", marginTop: 0 }}>
        Scopri quanti store vendono già questo prodotto e dove c'è ancora spazio.
      </p>

      <form onSubmit={startScan} style={{
        display: "flex", flexDirection: "column", gap: 12,
        padding: 16, border: "1px solid #E5E7EB", borderRadius: 12, background: "#FAFAFA",
      }}>
        <div style={{ display: "flex", gap: 8 }}>
          <button type="button"
            onClick={() => setMode("url")}
            style={{
              padding: "6px 12px", borderRadius: 8, border: "1px solid #D1D5DB",
              background: mode === "url" ? "#111827" : "#fff",
              color: mode === "url" ? "#fff" : "#111827", cursor: "pointer",
            }}>
            Product URL
          </button>
          <button type="button"
            onClick={() => setMode("image")}
            style={{
              padding: "6px 12px", borderRadius: 8, border: "1px solid #D1D5DB",
              background: mode === "image" ? "#111827" : "#fff",
              color: mode === "image" ? "#fff" : "#111827", cursor: "pointer",
            }}>
            Upload image
          </button>
        </div>

        {mode === "url" ? (
          <input
            type="url" placeholder="https://store.com/products/slug"
            value={url} onChange={(e) => setUrl(e.target.value)} required
            style={{ padding: "10px 12px", borderRadius: 8, border: "1px solid #D1D5DB", fontSize: 14 }}
          />
        ) : (
          <input
            type="file" accept="image/*" onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            style={{ padding: 8 }}
          />
        )}

        <button type="submit" disabled={busy} style={{
          padding: "10px 14px", borderRadius: 8, border: "none",
          background: busy ? "#9CA3AF" : "#4F46E5", color: "#fff",
          fontWeight: 600, cursor: busy ? "wait" : "pointer",
        }}>
          {busy ? "Scanning…" : "Start scan"}
        </button>
      </form>

      {error && (
        <div style={{
          marginTop: 16, padding: 12, borderRadius: 8,
          background: "#FEE2E2", color: "#991B1B",
        }}>
          {error}
        </div>
      )}

      {busy && (
        <div style={{ marginTop: 20 }}>
          <ProgressBar pct={progress.pct} stage={progress.stage} />
          {progress.confirmed_count != null && (
            <div style={{ marginTop: 8, fontSize: 13, color: "#374151" }}>
              Store confermati finora: <strong>{progress.confirmed_count}</strong>
              {progress.new_store && (
                <span style={{ marginLeft: 8, color: "#6B7280" }}>
                  + {progress.new_store}
                </span>
              )}
            </div>
          )}
        </div>
      )}

      {result && (
        <div style={{ marginTop: 24 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
            <h3 style={{ margin: 0 }}>
              Score: <span style={{ color: "#4F46E5" }}>{result.saturation_score}</span>/100
            </h3>
            <Badge zone={result.saturation_zone} />
            <span style={{ color: "#6B7280", fontSize: 13 }}>
              {result.total_shopify_stores} store — {Math.round(result.duration_ms / 1000)}s
            </span>
          </div>

          <p style={{ background: "#F9FAFB", padding: 12, borderRadius: 8, borderLeft: "4px solid #4F46E5" }}>
            {result.recommendation}
          </p>

          <h4 style={{ marginTop: 24 }}>Mercati</h4>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
            <thead>
              <tr style={{ background: "#F3F4F6", textAlign: "left" }}>
                <th style={{ padding: "8px 12px" }}>Country</th>
                <th style={{ padding: "8px 12px" }}>Stores</th>
                <th style={{ padding: "8px 12px" }}>Level</th>
                <th style={{ padding: "8px 12px" }}>Avg price</th>
                <th style={{ padding: "8px 12px" }}>Top / Flag</th>
              </tr>
            </thead>
            <tbody>
              {markets.map((row) => <MarketRow key={row.country} row={row} />)}
            </tbody>
          </table>

          <details style={{ marginTop: 16 }}>
            <summary style={{ cursor: "pointer", color: "#6366F1" }}>Raw JSON</summary>
            <pre style={{
              background: "#0F172A", color: "#E2E8F0", padding: 12,
              borderRadius: 8, overflow: "auto", fontSize: 12,
            }}>{JSON.stringify(result, null, 2)}</pre>
          </details>
        </div>
      )}
    </div>
  );
}

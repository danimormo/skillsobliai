import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

export const ShopifyNotification: React.FC<{
  amount: string;
  startFrame: number;
  style?: React.CSSProperties;
}> = ({ amount, startFrame, style }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const local = frame - startFrame;

  const slide = spring({
    frame: local,
    fps,
    from: 0,
    to: 1,
    config: { damping: 14, stiffness: 140 },
  });
  const x = interpolate(slide, [0, 1], [420, 0]);
  const opacity = interpolate(local, [0, 6], [0, 1], { extrapolateRight: "clamp" });

  return (
    <div
      style={{
        position: "absolute",
        transform: `translateX(${x}px)`,
        opacity,
        width: 360,
        background: "#ffffff",
        borderRadius: 12,
        boxShadow: "0 12px 32px rgba(0,0,0,0.45), 0 0 0 1px rgba(0,0,0,0.08)",
        padding: "14px 16px",
        display: "flex",
        alignItems: "center",
        gap: 12,
        fontFamily: "'Inter', system-ui, sans-serif",
        ...style,
      }}
    >
      <div
        style={{
          width: 40,
          height: 40,
          borderRadius: 10,
          background: "#96bf48",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "#fff",
          fontWeight: 900,
          fontSize: 22,
          fontFamily: "Inter, sans-serif",
        }}
      >
        S
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 12, color: "#667", fontWeight: 500, letterSpacing: 0.3 }}>
          Shopify
        </div>
        <div style={{ fontSize: 15, fontWeight: 700, color: "#111", marginTop: 2 }}>
          New order: {amount}
        </div>
      </div>
    </div>
  );
};

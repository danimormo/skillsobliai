import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { COLORS, FONTS } from "../theme";
import { FilmGrain, Vignette } from "../components/FilmGrain";

// Brand Guru office — sterile startup aesthetic
// Lasts 5 seconds (frames 0–150) within Act 1
export const BrandHQScene: React.FC = () => {
  const frame = useCurrentFrame();
  const push = interpolate(frame, [0, 150], [1.0, 1.12]);
  const drift = interpolate(frame, [0, 150], [0, -26]);

  return (
    <AbsoluteFill style={{ background: "#0a0a0c", overflow: "hidden" }}>
      {/* Camera transform */}
      <AbsoluteFill
        style={{
          transform: `scale(${push}) translateY(${drift}px)`,
          transformOrigin: "center 55%",
        }}
      >
        {/* Ceiling */}
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            height: "32%",
            background: `linear-gradient(180deg, ${COLORS.brandGray.bg2} 0%, ${COLORS.brandGray.bg1} 100%)`,
          }}
        />
        {/* Ceiling panels */}
        <div
          style={{
            position: "absolute",
            top: "2%",
            left: "8%",
            right: "8%",
            height: "8%",
            display: "flex",
            gap: 6,
            opacity: 0.35,
          }}
        >
          {Array.from({ length: 8 }).map((_, i) => (
            <div
              key={i}
              style={{
                flex: 1,
                background: "rgba(255,255,255,0.18)",
                boxShadow: "inset 0 -3px 8px rgba(0,0,0,0.15)",
              }}
            />
          ))}
        </div>

        {/* Back wall */}
        <div
          style={{
            position: "absolute",
            top: "32%",
            left: 0,
            right: 0,
            height: "42%",
            background: `linear-gradient(180deg, ${COLORS.brandGray.bg1} 0%, ${COLORS.brandGray.wall} 100%)`,
          }}
        />

        {/* Floor */}
        <div
          style={{
            position: "absolute",
            top: "74%",
            left: 0,
            right: 0,
            bottom: 0,
            background: `linear-gradient(180deg, ${COLORS.brandGray.floor} 0%, #3e4145 100%)`,
          }}
        />
        {/* Floor perspective lines */}
        <svg
          width="100%"
          height="100%"
          style={{ position: "absolute", inset: 0, opacity: 0.18 }}
          preserveAspectRatio="none"
          viewBox="0 0 1920 1080"
        >
          <line x1="960" y1="799" x2="0" y2="1080" stroke="#1a1a1a" strokeWidth="2" />
          <line x1="960" y1="799" x2="1920" y2="1080" stroke="#1a1a1a" strokeWidth="2" />
          <line x1="960" y1="799" x2="380" y2="1080" stroke="#1a1a1a" strokeWidth="1" />
          <line x1="960" y1="799" x2="1540" y2="1080" stroke="#1a1a1a" strokeWidth="1" />
        </svg>

        {/* Whiteboard */}
        <div
          style={{
            position: "absolute",
            top: "34%",
            left: "24%",
            width: "52%",
            height: "34%",
            background: COLORS.brandGray.whiteboard,
            borderRadius: 4,
            boxShadow:
              "0 2px 8px rgba(0,0,0,0.25), inset 0 0 0 8px #1a1a1a, inset 0 0 0 12px #cbb58a",
            padding: 40,
            paddingTop: 56,
            fontFamily: FONTS.heading,
            color: "#1a1a24",
          }}
        >
          <div
            style={{
              fontSize: 28,
              letterSpacing: 2,
              color: "#8a6d2a",
              marginBottom: 24,
              fontWeight: 400,
            }}
          >
            Q4 · BRAND STRATEGY
          </div>
          <div
            style={{
              fontSize: 78,
              lineHeight: 0.95,
              fontWeight: 400,
              letterSpacing: -1,
              color: "#1a1a24",
            }}
          >
            TRANSITION TO
            <br />
            PRIVATE LABEL
          </div>
          <div
            style={{
              position: "absolute",
              bottom: 40,
              left: 40,
              right: 40,
              display: "flex",
              gap: 18,
              fontFamily: FONTS.body,
              fontSize: 18,
              color: "#555",
              fontWeight: 500,
            }}
          >
            <span>→ hire team</span>
            <span>→ warehouse</span>
            <span>→ build moat</span>
          </div>
        </div>

        {/* Bookshelf right */}
        <div
          style={{
            position: "absolute",
            right: "4%",
            top: "40%",
            width: "14%",
            height: "34%",
            display: "flex",
            flexDirection: "column",
            gap: 10,
            padding: 10,
            background: "rgba(120, 100, 80, 0.3)",
            boxShadow: "inset 0 0 0 4px rgba(40,30,20,0.5)",
          }}
        >
          {[
            { t: "BRAND BUILDERS", c: "#2e4f74" },
            { t: "$100M BRAND", c: "#9a2c2c" },
            { t: "PRIVATE LABEL PLAYBOOK", c: "#33553b" },
            { t: "EXIT AT 8 FIGURES", c: "#4a3966" },
          ].map((b, i) => (
            <div
              key={i}
              style={{
                height: 44,
                background: b.c,
                color: "#fff",
                fontFamily: FONTS.heading,
                fontSize: 15,
                letterSpacing: 1,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                boxShadow: "inset 0 -3px 6px rgba(0,0,0,0.3)",
                paddingInline: 4,
                textAlign: "center",
              }}
            >
              {b.t}
            </div>
          ))}
        </div>

        {/* Plant left */}
        <div
          style={{
            position: "absolute",
            left: "4%",
            bottom: "4%",
            width: 180,
            height: 260,
          }}
        >
          <svg viewBox="0 0 180 260" width="100%" height="100%">
            <ellipse cx="90" cy="240" rx="70" ry="14" fill="rgba(0,0,0,0.35)" />
            <rect x="38" y="170" width="104" height="70" fill="#6b4a2a" rx="4" />
            <g fill="#2b4a2a" opacity="0.9">
              <ellipse cx="60" cy="110" rx="34" ry="60" />
              <ellipse cx="110" cy="95" rx="38" ry="64" transform="rotate(12 110 95)" />
              <ellipse cx="90" cy="70" rx="28" ry="56" />
              <ellipse cx="140" cy="130" rx="26" ry="52" transform="rotate(22 140 130)" />
              <ellipse cx="45" cy="140" rx="24" ry="48" transform="rotate(-18 45 140)" />
            </g>
          </svg>
        </div>

        {/* Brand guru silhouette — center stage */}
        <div
          style={{
            position: "absolute",
            left: "50%",
            bottom: "4%",
            transform: "translateX(-50%)",
            width: 280,
            height: 560,
          }}
        >
          <svg viewBox="0 0 280 560" width="100%" height="100%">
            {/* Shadow */}
            <ellipse cx="140" cy="540" rx="110" ry="16" fill="rgba(0,0,0,0.5)" />
            {/* Head */}
            <circle cx="140" cy="80" r="44" fill="#1a1a1f" />
            {/* Neck + Turtleneck */}
            <rect x="120" y="118" width="40" height="26" fill="#1a1a1f" />
            {/* Torso - cardigan */}
            <path
              d="M 60 150 Q 60 138 72 138 L 208 138 Q 220 138 220 150 L 230 360 Q 230 372 218 372 L 62 372 Q 50 372 50 360 Z"
              fill="#1a1a1f"
            />
            {/* Arms */}
            <rect x="40" y="150" width="32" height="210" fill="#1a1a1f" rx="12" />
            <rect x="208" y="150" width="32" height="210" fill="#1a1a1f" rx="12" />
            {/* Legs - slacks */}
            <rect x="82" y="368" width="48" height="180" fill="#16161a" />
            <rect x="150" y="368" width="48" height="180" fill="#16161a" />
            {/* Shoes */}
            <ellipse cx="102" cy="548" rx="30" ry="8" fill="#0a0a0a" />
            <ellipse cx="178" cy="548" rx="30" ry="8" fill="#0a0a0a" />
            {/* Hand gesture — pointer raised */}
            <ellipse cx="56" cy="160" rx="14" ry="18" fill="#1a1a1f" transform="rotate(-30 56 160)" />
          </svg>
        </div>

        {/* Subtle window light beam from left */}
        <div
          style={{
            position: "absolute",
            top: "20%",
            left: 0,
            width: "45%",
            height: "60%",
            background:
              "linear-gradient(100deg, rgba(255,255,240,0.15) 0%, rgba(255,255,240,0) 60%)",
            pointerEvents: "none",
          }}
        />
      </AbsoluteFill>

      {/* Color grade: desaturate + slight cool tint */}
      <AbsoluteFill
        style={{
          pointerEvents: "none",
          background:
            "linear-gradient(180deg, rgba(20,30,50,0.22) 0%, rgba(20,10,20,0.28) 100%)",
          mixBlendMode: "multiply",
        }}
      />

      <Vignette strength={0.75} />
      <FilmGrain opacity={0.2} />
    </AbsoluteFill>
  );
};

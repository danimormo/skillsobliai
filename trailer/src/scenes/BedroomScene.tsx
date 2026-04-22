import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { COLORS, FONTS } from "../theme";
import { FilmGrain, Vignette } from "../components/FilmGrain";
import { ShopifyNotification } from "../components/ShopifyNotification";

// Dropshipper bedroom at 3am — dark, monitor-lit
// Lasts 3 seconds (90 frames) — scene-relative frame (0..89) inside a <Sequence>
export const BedroomScene: React.FC = () => {
  const local = useCurrentFrame(); // 0..89

  // Slow pull-in on laptop glow
  const push = interpolate(local, [0, 90], [1.0, 1.15]);
  const drift = interpolate(local, [0, 90], [0, -14]);

  // Laptop glow pulse
  const glowPulse = 0.85 + 0.15 * Math.sin(local * 0.18);

  // At frame ~45 (mid-scene), cut into close-up (change zoom target)
  const isCloseup = local >= 45;
  const closeupScale = interpolate(local, [45, 60], [1.15, 1.8], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ background: COLORS.bedroom.wallDark, overflow: "hidden" }}>
      <AbsoluteFill
        style={{
          transform: isCloseup
            ? `scale(${closeupScale}) translate(-6%, -6%)`
            : `scale(${push}) translateY(${drift}px)`,
          transformOrigin: "center 50%",
        }}
      >
        {/* Wall gradient (dark room) */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: `radial-gradient(ellipse at 50% 42%, ${COLORS.bedroom.wallMid} 0%, ${COLORS.bedroom.wallDark} 70%, #050507 100%)`,
          }}
        />

        {/* Floor */}
        <div
          style={{
            position: "absolute",
            bottom: 0,
            left: 0,
            right: 0,
            height: "22%",
            background: "linear-gradient(180deg, #0c0e14 0%, #050608 100%)",
          }}
        />

        {/* Desk */}
        <div
          style={{
            position: "absolute",
            bottom: "22%",
            left: "16%",
            width: "68%",
            height: "6%",
            background: "linear-gradient(180deg, #3a2a1e 0%, #221510 100%)",
            boxShadow: "0 6px 20px rgba(0,0,0,0.7)",
          }}
        />

        {/* Laptop body */}
        <div
          style={{
            position: "absolute",
            bottom: "28%",
            left: "36%",
            width: "28%",
            height: 18,
            background: "#1a1d22",
            borderRadius: 3,
            boxShadow: "0 4px 10px rgba(0,0,0,0.6)",
          }}
        />

        {/* Laptop screen + glow halo */}
        <div
          style={{
            position: "absolute",
            bottom: "30%",
            left: "36%",
            width: "28%",
            height: "30%",
            background: "#0d1220",
            borderRadius: "6px 6px 2px 2px",
            border: "3px solid #1a1d22",
            boxShadow: `0 0 80px 30px rgba(122,167,255,${0.35 * glowPulse}), 0 0 180px 60px rgba(122,167,255,${0.18 * glowPulse})`,
            overflow: "hidden",
            padding: 12,
            display: "flex",
            flexDirection: "column",
          }}
        >
          {/* Mock Shopify admin header */}
          <div
            style={{
              background: "#1f2937",
              color: "#fff",
              fontFamily: FONTS.body,
              fontSize: 10,
              padding: "4px 8px",
              display: "flex",
              alignItems: "center",
              gap: 6,
              borderRadius: 3,
            }}
          >
            <span
              style={{
                width: 14,
                height: 14,
                background: "#96bf48",
                borderRadius: 3,
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#fff",
                fontWeight: 900,
                fontSize: 9,
              }}
            >
              S
            </span>
            <span style={{ fontWeight: 600 }}>admin.shopify.com</span>
          </div>
          <div
            style={{
              marginTop: 8,
              color: "#cfe0ff",
              fontFamily: FONTS.heading,
              fontSize: 18,
              letterSpacing: 1,
            }}
          >
            TODAY
          </div>
          <div
            style={{
              color: "#ffffff",
              fontFamily: FONTS.heading,
              fontSize: 54,
              lineHeight: 1,
              marginTop: 2,
              textShadow: "0 0 12px rgba(150,191,72,0.7)",
            }}
          >
            $4,821
          </div>
          <div
            style={{
              marginTop: 4,
              color: "#96bf48",
              fontSize: 10,
              fontFamily: FONTS.body,
              fontWeight: 700,
            }}
          >
            +32 orders · live
          </div>
          {/* Mini chart */}
          <svg
            style={{ position: "absolute", left: 12, right: 12, bottom: 10, width: "calc(100% - 24px)", height: "24%" }}
            viewBox="0 0 240 50"
            preserveAspectRatio="none"
          >
            <path
              d="M 0 44 L 20 40 L 40 36 L 60 38 L 80 28 L 100 30 L 120 22 L 140 20 L 160 10 L 180 12 L 200 4 L 220 6 L 240 2"
              fill="none"
              stroke="#96bf48"
              strokeWidth="2"
            />
            <path
              d="M 0 44 L 20 40 L 40 36 L 60 38 L 80 28 L 100 30 L 120 22 L 140 20 L 160 10 L 180 12 L 200 4 L 220 6 L 240 2 L 240 50 L 0 50 Z"
              fill="url(#g)"
              opacity="0.5"
            />
            <defs>
              <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#96bf48" stopOpacity="0.6" />
                <stop offset="100%" stopColor="#96bf48" stopOpacity="0" />
              </linearGradient>
            </defs>
          </svg>
        </div>

        {/* AliExpress boxes stacked left */}
        <div
          style={{
            position: "absolute",
            bottom: "5%",
            left: "8%",
            width: 260,
            height: 300,
          }}
        >
          <svg viewBox="0 0 260 300" width="100%" height="100%">
            {/* Bottom box */}
            <rect x="10" y="200" width="220" height="88" fill={COLORS.bedroom.cardboard} stroke={COLORS.bedroom.cardboardDark} strokeWidth="2" />
            <rect x="10" y="200" width="220" height="4" fill={COLORS.bedroom.cardboardDark} />
            <line x1="120" y1="204" x2="120" y2="288" stroke={COLORS.bedroom.cardboardDark} strokeWidth="2" />
            <rect x="80" y="220" width="100" height="20" fill="#fff" opacity="0.9" />
            <text x="130" y="235" fontFamily="Impact" fontSize="14" fill={COLORS.bedroom.orange} textAnchor="middle" fontWeight="700">
              AliExpress
            </text>
            {/* Middle box (rotated) */}
            <g transform="rotate(-6 130 150)">
              <rect x="30" y="110" width="190" height="90" fill={COLORS.bedroom.cardboard} stroke={COLORS.bedroom.cardboardDark} strokeWidth="2" />
              <line x1="125" y1="114" x2="125" y2="196" stroke={COLORS.bedroom.cardboardDark} strokeWidth="2" />
              <rect x="80" y="128" width="90" height="18" fill="#fff" opacity="0.9" />
              <text x="125" y="142" fontFamily="Impact" fontSize="12" fill={COLORS.bedroom.orange} textAnchor="middle" fontWeight="700">
                AliExpress
              </text>
              <rect x="70" y="156" width="110" height="10" fill="#fff" opacity="0.7" />
              <text x="125" y="164" fontFamily="Inter" fontSize="8" fill="#1a1a1a" textAnchor="middle">
                TO: you · FROM: Shenzhen
              </text>
            </g>
            {/* Top small box */}
            <rect x="68" y="44" width="118" height="70" fill={COLORS.bedroom.cardboard} stroke={COLORS.bedroom.cardboardDark} strokeWidth="2" />
            <line x1="127" y1="48" x2="127" y2="110" stroke={COLORS.bedroom.cardboardDark} strokeWidth="2" />
          </svg>
        </div>

        {/* Red Bull cans right */}
        <div
          style={{
            position: "absolute",
            bottom: "8%",
            right: "10%",
            width: 220,
            height: 180,
          }}
        >
          <svg viewBox="0 0 220 180" width="100%" height="100%">
            {[
              { x: 20, tilt: -4 },
              { x: 80, tilt: 2 },
              { x: 140, tilt: -6 },
            ].map((c, i) => (
              <g key={i} transform={`translate(${c.x} 60) rotate(${c.tilt} 30 60)`}>
                <rect x="0" y="0" width="50" height="112" fill="#1b3e8f" rx="4" />
                <rect x="0" y="0" width="50" height="16" fill="#9ca3af" rx="4" />
                <rect x="0" y="96" width="50" height="16" fill="#9ca3af" rx="4" />
                <text x="25" y="60" fontFamily="Impact" fontSize="14" fill="#e61a2b" textAnchor="middle" fontWeight="900">
                  RED
                </text>
                <text x="25" y="74" fontFamily="Impact" fontSize="12" fill="#f2c94c" textAnchor="middle" fontWeight="900">
                  BULL
                </text>
              </g>
            ))}
          </svg>
        </div>

        {/* Pizza slice */}
        <div
          style={{
            position: "absolute",
            bottom: "24%",
            right: "30%",
            width: 110,
            height: 70,
          }}
        >
          <svg viewBox="0 0 110 70" width="100%" height="100%">
            <polygon points="0,60 110,50 55,0" fill="#e8b768" stroke="#a66f1f" strokeWidth="2" />
            <polygon points="6,56 102,49 55,8" fill="#f3c877" />
            <circle cx="40" cy="38" r="6" fill="#c1393d" />
            <circle cx="70" cy="28" r="5" fill="#c1393d" />
            <circle cx="55" cy="50" r="4" fill="#c1393d" />
            <circle cx="85" cy="42" r="5" fill="#c1393d" />
          </svg>
        </div>

        {/* Phone on desk with TikTok-like UI glow (small accent) */}
        <div
          style={{
            position: "absolute",
            bottom: "25%",
            left: "22%",
            width: 60,
            height: 110,
            background: "#000",
            borderRadius: 10,
            border: "3px solid #1a1d22",
            boxShadow: "0 0 30px 5px rgba(255,90,140,0.25)",
            overflow: "hidden",
          }}
        >
          <div
            style={{
              background: "linear-gradient(160deg, #ff0050 0%, #000 40%, #00f2ea 100%)",
              width: "100%",
              height: "100%",
              opacity: 0.7,
            }}
          />
        </div>

        {/* Silhouette of dropshipper sitting at desk — back view, hoodie */}
        <div
          style={{
            position: "absolute",
            bottom: "22%",
            left: "50%",
            transform: "translateX(-50%)",
            width: 380,
            height: 420,
          }}
        >
          <svg viewBox="0 0 380 420" width="100%" height="100%">
            {/* Chair back hint */}
            <rect x="140" y="280" width="100" height="140" fill="#0a0a0c" opacity="0.6" />
            {/* Body - hoodie */}
            <path
              d="M 70 420 L 70 220 Q 70 180 110 170 L 270 170 Q 310 180 310 220 L 310 420 Z"
              fill="#0a0a0c"
            />
            {/* Shoulders/hood bump */}
            <path d="M 90 200 Q 190 150 290 200 L 290 240 L 90 240 Z" fill="#0a0a0c" />
            {/* Head (back of head, slight hood) */}
            <ellipse cx="190" cy="130" rx="58" ry="68" fill="#0a0a0c" />
            {/* Hood outline */}
            <path
              d="M 120 130 Q 120 60 190 58 Q 260 60 260 130 Q 240 180 190 180 Q 140 180 120 130 Z"
              fill="#0a0a0c"
              opacity="0.9"
            />
            {/* Ear rim highlight from monitor */}
            <path
              d="M 132 120 Q 140 90 170 80"
              stroke="rgba(122,167,255,0.3)"
              strokeWidth="2"
              fill="none"
            />
          </svg>
        </div>

        {/* Shopify notification toast (slides in mid-scene) */}
        <ShopifyNotification
          amount="$4,821.00"
          startFrame={20}
          style={{ top: "18%", right: "6%" }}
        />

        {/* Glasses/eyes reflection overlay for close-up moment */}
        {isCloseup && (
          <div
            style={{
              position: "absolute",
              top: "38%",
              left: "50%",
              transform: "translate(-50%, 0)",
              width: 600,
              height: 180,
              display: "flex",
              justifyContent: "space-between",
            }}
          >
            {/* Left lens */}
            <div
              style={{
                width: 260,
                height: 180,
                background: "radial-gradient(ellipse, rgba(10,10,14,0.92) 30%, rgba(10,10,14,0.4) 70%, transparent 100%)",
                borderRadius: "50%",
                position: "relative",
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  position: "absolute",
                  inset: "20%",
                  background:
                    "linear-gradient(135deg, rgba(122,167,255,0.5) 0%, rgba(0,0,0,0.9) 100%)",
                  borderRadius: "50%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "#96bf48",
                  fontFamily: FONTS.heading,
                  fontSize: 22,
                  textShadow: "0 0 8px #96bf48",
                }}
              >
                $98,432
              </div>
            </div>
            {/* Right lens */}
            <div
              style={{
                width: 260,
                height: 180,
                background: "radial-gradient(ellipse, rgba(10,10,14,0.92) 30%, rgba(10,10,14,0.4) 70%, transparent 100%)",
                borderRadius: "50%",
                position: "relative",
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  position: "absolute",
                  inset: "20%",
                  background:
                    "linear-gradient(135deg, rgba(122,167,255,0.5) 0%, rgba(0,0,0,0.9) 100%)",
                  borderRadius: "50%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "#96bf48",
                  fontFamily: FONTS.heading,
                  fontSize: 22,
                  textShadow: "0 0 8px #96bf48",
                }}
              >
                THIS MONTH
              </div>
            </div>
          </div>
        )}
      </AbsoluteFill>

      <Vignette strength={0.82} />
      <FilmGrain opacity={0.22} />
    </AbsoluteFill>
  );
};

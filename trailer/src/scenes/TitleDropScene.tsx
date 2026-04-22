import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { COLORS, FONTS } from "../theme";
import { FilmGrain, Vignette } from "../components/FilmGrain";

// 8–10s: Vice City dawn skyline + "OBLIVION PRESENTS" — scene-relative frame
export const TitleDropScene: React.FC = () => {
  const local = useCurrentFrame();
  const { fps } = useVideoConfig();

  const whiteFlash = interpolate(local, [0, 4, 12], [1, 0.7, 0], {
    extrapolateRight: "clamp",
  });

  const textPop = spring({
    frame: local - 6,
    fps,
    from: 0,
    to: 1,
    config: { damping: 14, stiffness: 140 },
  });
  const textScale = interpolate(textPop, [0, 1], [0.85, 1.0]);
  const textOpacity = interpolate(local, [6, 14], [0, 1], { extrapolateRight: "clamp" });
  const subOpacity = interpolate(local, [16, 22], [0, 1], { extrapolateRight: "clamp" });

  const parallax = interpolate(local, [0, 60], [0, 20]);
  const zoom = interpolate(local, [0, 60], [1.02, 1.08]);

  return (
    <AbsoluteFill style={{ overflow: "hidden", background: "#000" }}>
      <AbsoluteFill
        style={{
          transform: `scale(${zoom}) translateY(${-parallax * 0.3}px)`,
          transformOrigin: "center 60%",
        }}
      >
        {/* Sky gradient dawn */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: `linear-gradient(180deg, ${COLORS.sky.dawn4} 0%, ${COLORS.sky.dawn3} 28%, ${COLORS.sky.dawn2} 58%, ${COLORS.sky.dawn1} 82%, #f2d38a 100%)`,
          }}
        />

        {/* Sun glow */}
        <div
          style={{
            position: "absolute",
            bottom: "22%",
            left: "50%",
            transform: "translateX(-50%)",
            width: 600,
            height: 600,
            borderRadius: "50%",
            background:
              "radial-gradient(circle, rgba(255,220,140,0.85) 0%, rgba(255,160,90,0.4) 40%, rgba(255,90,60,0) 70%)",
            filter: "blur(2px)",
          }}
        />

        {/* Distant back skyline */}
        <svg
          viewBox="0 0 1920 260"
          width="100%"
          style={{ position: "absolute", bottom: "28%", left: 0, opacity: 0.5 }}
          preserveAspectRatio="none"
        >
          <path
            d="M 0 260 L 0 200 L 80 200 L 80 160 L 140 160 L 140 180 L 200 180 L 200 120 L 260 120 L 260 170 L 340 170 L 340 140 L 420 140 L 420 160 L 500 160 L 500 100 L 560 100 L 560 150 L 640 150 L 640 130 L 720 130 L 720 80 L 800 80 L 800 150 L 880 150 L 880 110 L 960 110 L 960 60 L 1040 60 L 1040 130 L 1120 130 L 1120 100 L 1200 100 L 1200 170 L 1280 170 L 1280 140 L 1360 140 L 1360 160 L 1440 160 L 1440 110 L 1520 110 L 1520 150 L 1600 150 L 1600 130 L 1680 130 L 1680 170 L 1760 170 L 1760 150 L 1840 150 L 1840 180 L 1920 180 L 1920 260 Z"
            fill="#2a1a3a"
          />
        </svg>

        {/* Front skyline */}
        <svg
          viewBox="0 0 1920 360"
          width="100%"
          style={{
            position: "absolute",
            bottom: `calc(18% - ${parallax}px)`,
            left: 0,
          }}
          preserveAspectRatio="none"
        >
          <path
            d="M 0 360 L 0 260 L 70 260 L 70 210 L 140 210 L 140 240 L 220 240 L 220 150 L 290 150 L 290 230 L 370 230 L 370 180 L 450 180 L 450 220 L 540 220 L 540 120 L 620 120 L 620 200 L 700 200 L 700 150 L 780 150 L 780 80 L 870 80 L 870 170 L 950 170 L 950 100 L 1030 100 L 1030 200 L 1110 200 L 1110 130 L 1190 130 L 1190 220 L 1270 220 L 1270 180 L 1350 180 L 1350 210 L 1440 210 L 1440 140 L 1520 140 L 1520 200 L 1610 200 L 1610 170 L 1690 170 L 1690 230 L 1770 230 L 1770 200 L 1850 200 L 1850 240 L 1920 240 L 1920 360 Z"
            fill="#0e0b1a"
          />
          {/* Scattered window lights */}
          {[
            [90, 240],
            [160, 220],
            [240, 180],
            [310, 210],
            [460, 200],
            [560, 160],
            [640, 180],
            [720, 120],
            [800, 110],
            [900, 150],
            [1050, 170],
            [1200, 170],
            [1360, 200],
            [1540, 180],
            [1700, 210],
          ].map(([x, y], i) => (
            <rect
              key={i}
              x={x}
              y={y}
              width="3"
              height="6"
              fill={i % 2 ? "#ffd69a" : "#ffaa66"}
              opacity={0.85}
            />
          ))}
        </svg>

        {/* Palm silhouettes foreground */}
        <svg
          viewBox="0 0 1920 400"
          width="100%"
          style={{ position: "absolute", bottom: 0, left: 0 }}
          preserveAspectRatio="none"
        >
          {/* Ground */}
          <rect x="0" y="340" width="1920" height="60" fill="#06050a" />

          {/* Palm 1 left */}
          <g transform="translate(180 200)">
            <rect x="-8" y="0" width="16" height="200" fill="#06050a" />
            <g fill="#06050a">
              <path d="M 0 0 Q -40 -40 -120 -40 Q -100 -20 -60 -10 Q -20 -2 0 0 Z" />
              <path d="M 0 0 Q 40 -40 120 -40 Q 100 -20 60 -10 Q 20 -2 0 0 Z" />
              <path d="M 0 0 Q -60 -80 -180 -110 Q -140 -60 -90 -40 Q -40 -20 0 0 Z" />
              <path d="M 0 0 Q 60 -80 180 -110 Q 140 -60 90 -40 Q 40 -20 0 0 Z" />
              <path d="M 0 0 Q 0 -100 -40 -180 Q 30 -120 10 -40 Z" />
            </g>
          </g>
          {/* Palm 2 right */}
          <g transform="translate(1700 180)">
            <rect x="-8" y="0" width="16" height="220" fill="#06050a" />
            <g fill="#06050a">
              <path d="M 0 0 Q -40 -40 -120 -40 Q -100 -20 -60 -10 Q -20 -2 0 0 Z" />
              <path d="M 0 0 Q 40 -40 120 -40 Q 100 -20 60 -10 Q 20 -2 0 0 Z" />
              <path d="M 0 0 Q -60 -80 -180 -110 Q -140 -60 -90 -40 Q -40 -20 0 0 Z" />
              <path d="M 0 0 Q 60 -80 180 -110 Q 140 -60 90 -40 Q 40 -20 0 0 Z" />
              <path d="M 0 0 Q -20 -100 -60 -170 Q 20 -120 10 -40 Z" />
            </g>
          </g>
          {/* Palm 3 left-mid smaller */}
          <g transform="translate(420 260)">
            <rect x="-5" y="0" width="10" height="140" fill="#06050a" opacity="0.85" />
            <g fill="#06050a" opacity="0.85">
              <path d="M 0 0 Q -30 -30 -80 -30 Q -70 -14 -40 -6 Z" />
              <path d="M 0 0 Q 30 -30 80 -30 Q 70 -14 40 -6 Z" />
              <path d="M 0 0 Q -50 -60 -120 -70 Q -90 -30 -50 -18 Z" />
              <path d="M 0 0 Q 50 -60 120 -70 Q 90 -30 50 -18 Z" />
            </g>
          </g>
        </svg>

        {/* Heat haze top sky */}
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            height: "30%",
            background:
              "linear-gradient(180deg, rgba(255,255,255,0.12) 0%, transparent 100%)",
          }}
        />
      </AbsoluteFill>

      {/* White flash hit */}
      <AbsoluteFill
        style={{
          background: "#fff5e0",
          opacity: whiteFlash,
          pointerEvents: "none",
        }}
      />

      {/* OBLIVION PRESENTS */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          pointerEvents: "none",
          zIndex: 80,
        }}
      >
        <div
          style={{
            fontFamily: FONTS.heading,
            fontSize: 168,
            color: "#fff",
            letterSpacing: 8,
            textTransform: "uppercase",
            transform: `scale(${textScale})`,
            opacity: textOpacity,
            textShadow:
              "0 4px 0 #000, 0 0 30px rgba(0,0,0,0.85), 0 0 80px rgba(255,200,120,0.4)",
            WebkitTextStroke: "3px #000",
            lineHeight: 0.9,
          }}
        >
          OBLIVION
        </div>
        <div
          style={{
            fontFamily: FONTS.heading,
            fontSize: 52,
            color: "#fff",
            letterSpacing: 12,
            textTransform: "uppercase",
            marginTop: 12,
            opacity: subOpacity,
            textShadow: "0 2px 0 #000, 0 0 16px rgba(0,0,0,0.9)",
            WebkitTextStroke: "2px #000",
          }}
        >
          PRESENTS
        </div>
      </div>

      <Vignette strength={0.5} />
      <FilmGrain opacity={0.18} />
    </AbsoluteFill>
  );
};

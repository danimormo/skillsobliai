import React from "react";
import { interpolate, useCurrentFrame, spring, useVideoConfig } from "remotion";

export const WantedStars: React.FC<{ startFrame: number; stars?: number }> = ({
  startFrame,
  stars = 5,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const local = frame - startFrame;

  return (
    <div
      style={{
        position: "absolute",
        right: 56,
        top: 42,
        display: "flex",
        gap: 4,
        fontFamily: "Impact, sans-serif",
        fontSize: 46,
        color: "#fff",
        textShadow: "0 2px 6px rgba(0,0,0,0.7)",
        letterSpacing: -2,
        zIndex: 60,
      }}
    >
      {Array.from({ length: stars }).map((_, i) => {
        const starFrame = local - i * 3;
        const s = spring({
          frame: starFrame,
          fps,
          config: { damping: 12, stiffness: 180 },
          from: 0,
          to: 1,
        });
        return (
          <span
            key={i}
            style={{
              display: "inline-block",
              transform: `scale(${s}) rotate(${(1 - s) * 90}deg)`,
              opacity: s,
            }}
          >
            ★
          </span>
        );
      })}
    </div>
  );
};

export const MoneyCounter: React.FC<{ amount: string; startFrame: number }> = ({
  amount,
  startFrame,
}) => {
  const frame = useCurrentFrame();
  const local = frame - startFrame;
  const opacity = interpolate(local, [0, 10], [0, 1], { extrapolateRight: "clamp" });
  const y = interpolate(local, [0, 14], [-20, 0], { extrapolateRight: "clamp" });

  return (
    <div
      style={{
        position: "absolute",
        right: 56,
        top: 104,
        fontFamily: "Impact, 'Bebas Neue', sans-serif",
        fontSize: 56,
        color: "#fff",
        textShadow: "0 3px 8px rgba(0,0,0,0.85)",
        letterSpacing: 1,
        zIndex: 60,
        opacity,
        transform: `translateY(${y}px)`,
      }}
    >
      {amount}
    </div>
  );
};

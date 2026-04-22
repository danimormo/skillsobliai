import React from "react";
import { interpolate, useCurrentFrame } from "remotion";

export const Subtitle: React.FC<{
  text: string;
  startFrame: number;
  durationFrames: number;
}> = ({ text, startFrame, durationFrames }) => {
  const frame = useCurrentFrame();
  const local = frame - startFrame;
  if (local < 0 || local > durationFrames) return null;

  const fadeIn = interpolate(local, [0, 4], [0, 1], { extrapolateRight: "clamp" });
  const fadeOut = interpolate(
    local,
    [durationFrames - 4, durationFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const opacity = Math.min(fadeIn, fadeOut);

  return (
    <div
      style={{
        position: "absolute",
        left: 0,
        right: 0,
        bottom: 108,
        textAlign: "center",
        fontFamily: "'Inter', system-ui, sans-serif",
        fontWeight: 600,
        fontSize: 40,
        color: "#fff",
        textShadow:
          "0 0 2px rgba(0,0,0,0.95), 0 2px 6px rgba(0,0,0,0.95), 0 0 12px rgba(0,0,0,0.6)",
        letterSpacing: 0.2,
        opacity,
        zIndex: 70,
        padding: "0 120px",
      }}
    >
      {text}
    </div>
  );
};

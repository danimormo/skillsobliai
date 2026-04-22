import { AbsoluteFill, useCurrentFrame } from "remotion";

export const FilmGrain: React.FC<{ opacity?: number }> = ({ opacity = 0.18 }) => {
  const frame = useCurrentFrame();
  const offset = (frame * 37) % 200;
  return (
    <AbsoluteFill
      style={{
        pointerEvents: "none",
        opacity,
        mixBlendMode: "overlay",
        backgroundImage: `url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='300' height='300'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='1.8' numOctaves='2' stitchTiles='stitch'/><feColorMatrix type='matrix' values='0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 1.2 0'/></filter><rect width='100%' height='100%' filter='url(%23n)' opacity='0.55'/></svg>")`,
        backgroundSize: "300px 300px",
        backgroundPosition: `${offset}px ${offset * 0.6}px`,
      }}
    />
  );
};

export const Vignette: React.FC<{ strength?: number }> = ({ strength = 0.55 }) => (
  <AbsoluteFill
    style={{
      pointerEvents: "none",
      background: `radial-gradient(ellipse at center, transparent 40%, rgba(0,0,0,${strength}) 100%)`,
    }}
  />
);

export const Letterbox: React.FC = () => (
  <>
    <div
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        right: 0,
        height: 80,
        background: "#000",
        zIndex: 50,
      }}
    />
    <div
      style={{
        position: "absolute",
        bottom: 0,
        left: 0,
        right: 0,
        height: 80,
        background: "#000",
        zIndex: 50,
      }}
    />
  </>
);

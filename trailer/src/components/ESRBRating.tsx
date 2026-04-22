import React from "react";

export const ESRBRating: React.FC = () => (
  <div
    style={{
      position: "absolute",
      left: 48,
      bottom: 48,
      width: 110,
      background: "#ffffff",
      border: "2px solid #000",
      fontFamily: "Impact, 'Bebas Neue', sans-serif",
      color: "#000",
      userSelect: "none",
      zIndex: 60,
      boxShadow: "0 4px 16px rgba(0,0,0,0.4)",
    }}
  >
    <div
      style={{
        fontSize: 11,
        padding: "3px 6px",
        borderBottom: "1px solid #000",
        letterSpacing: 0.5,
        fontWeight: 700,
      }}
    >
      MATURE 17+
    </div>
    <div
      style={{
        fontSize: 78,
        lineHeight: 1,
        padding: "8px 0 4px",
        textAlign: "center",
        fontWeight: 900,
      }}
    >
      M
    </div>
    <div
      style={{
        fontSize: 8,
        padding: "3px 4px",
        textAlign: "center",
        letterSpacing: 0.3,
        fontWeight: 700,
      }}
    >
      CONTENT RATED BY
    </div>
    <div
      style={{
        fontSize: 14,
        padding: "0 4px 5px",
        textAlign: "center",
        fontWeight: 900,
        letterSpacing: 1,
      }}
    >
      ESRB
    </div>
  </div>
);

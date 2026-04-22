import { staticFile } from "remotion";

let loaded = false;

export const loadFonts = () => {
  if (loaded) return;
  loaded = true;
  if (typeof document === "undefined") return;
  const style = document.createElement("style");
  style.textContent = `
@font-face {
  font-family: 'Bebas Neue';
  src: url(${staticFile("fonts/bebas.woff2")}) format('woff2');
  font-weight: 400;
  font-display: block;
}
@font-face {
  font-family: 'Inter';
  src: url(${staticFile("fonts/inter.woff2")}) format('woff2');
  font-weight: 100 900;
  font-display: block;
}
@font-face {
  font-family: 'Anton';
  src: url(${staticFile("fonts/anton.ttf")}) format('truetype');
  font-weight: 400;
  font-display: block;
}
`;
  document.head.appendChild(style);
};

loadFonts();

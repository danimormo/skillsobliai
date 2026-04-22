import React from "react";
import { AbsoluteFill, Sequence, useCurrentFrame } from "remotion";
import "../fonts";

import { BrandHQScene } from "../scenes/BrandHQScene";
import { BedroomScene } from "../scenes/BedroomScene";
import { TitleDropScene } from "../scenes/TitleDropScene";
import { Subtitle } from "../components/Subtitle";
import { ESRBRating } from "../components/ESRBRating";
import { WantedStars, MoneyCounter } from "../components/WantedStars";
import { Letterbox } from "../components/FilmGrain";

// 30 fps · 10 s · 300 frames
// Option C VO (5 lines):
//   0:00 "Everyone said dropshipping was over."        f0  →  f54
//   0:02 "That the good days were gone."                f54 → f99
//   0:04 "That we had to grow up."                      f99 → f150
//   0:05 "We didn't."                                   f150 → f195
//   0:06 "We kept dropshipping."                        f195 → f240
//   0:08  [title drop]                                  f240 → f300

const BRAND_HQ_END = 150;
const BEDROOM_END = 240;
const TITLE_END = 300;

export const Act1: React.FC = () => {
  const frame = useCurrentFrame();

  return (
    <AbsoluteFill style={{ background: "#000" }}>
      {/* Scenes */}
      <Sequence from={0} durationInFrames={BRAND_HQ_END}>
        <BrandHQScene />
      </Sequence>

      <Sequence from={BRAND_HQ_END} durationInFrames={BEDROOM_END - BRAND_HQ_END}>
        <BedroomScene />
      </Sequence>

      <Sequence from={BEDROOM_END} durationInFrames={TITLE_END - BEDROOM_END}>
        <TitleDropScene />
      </Sequence>

      {/* HUD — only during the Bedroom close-up, wanted stars + counter */}
      {frame >= BRAND_HQ_END + 45 && frame < BEDROOM_END && (
        <>
          <WantedStars startFrame={BRAND_HQ_END + 45} />
          <MoneyCounter amount="$98,432" startFrame={BRAND_HQ_END + 50} />
        </>
      )}

      {/* ESRB only during act 1 pre-title */}
      {frame < BEDROOM_END && <ESRBRating />}

      {/* Letterbox for cinematic feel, not on title card */}
      {frame < BEDROOM_END && <Letterbox />}

      {/* Subtitles (burned in) */}
      <Subtitle text="Everyone said dropshipping was over." startFrame={0} durationFrames={54} />
      <Subtitle text="That the good days were gone." startFrame={54} durationFrames={45} />
      <Subtitle text="That we had to grow up." startFrame={99} durationFrames={51} />
      <Subtitle text="We didn't." startFrame={150} durationFrames={45} />
      <Subtitle text="We kept dropshipping." startFrame={195} durationFrames={45} />
    </AbsoluteFill>
  );
};

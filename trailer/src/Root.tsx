import React from "react";
import { Composition } from "remotion";
import { Act1 } from "./compositions/Act1";

export const Root: React.FC = () => {
  return (
    <>
      <Composition
        id="Act1"
        component={Act1}
        durationInFrames={300}
        fps={30}
        width={1920}
        height={1080}
      />
    </>
  );
};

import { loadFont } from "@remotion/fonts";
import {
  AbsoluteFill,
  Composition,
  Easing,
  interpolate,
  registerRoot,
  staticFile,
  useCurrentFrame,
} from "remotion";
import { DATA } from "./data";

loadFont({
  family: "Noto Sans SC",
  url: staticFile("fonts/NotoSansSC-VF.ttf"),
});

const FPS = 30;
const DURATION = 8 * FPS;

export const AnimatedChart = () => {
  const frame = useCurrentFrame();
  const max = Math.max(...DATA.items.map((d) => d.value));

  const titleIn = interpolate(frame, [0, 40], [0, 1], {
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });

  return (
    <AbsoluteFill
      style={{
        background: "#0E0F13",
        color: "#FFFFFF",
        fontFamily: "Noto Sans SC",
        padding: 90,
      }}
    >
      <div
        style={{
          opacity: titleIn,
          translate: `0 ${interpolate(frame, [0, 40], [40, 0], {
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.16, 1, 0.3, 1),
          })}px`,
        }}
      >
        <div style={{ fontSize: 68, fontWeight: 700, letterSpacing: -1 }}>
          {DATA.title}
        </div>
        <div style={{ fontSize: 28, opacity: 0.65, marginTop: 14 }}>
          {DATA.subtitle}
        </div>
      </div>

      <AbsoluteFill
        style={{
          top: 280,
          left: 90,
          right: 90,
          bottom: 180,
          flexDirection: "row",
          alignItems: "flex-end",
          gap: 60,
        }}
      >
        {DATA.items.map((item, i) => {
          const start = 30 + i * 12;
          const h = interpolate(frame, [start, start + 50], [0, 1], {
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.16, 1, 0.3, 1),
          });
          return (
            <div
              key={item.label}
              style={{
                flex: 1,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "flex-end",
                height: "100%",
              }}
            >
              <div style={{ fontSize: 40, fontWeight: 800, marginBottom: 16 }}>
                {Math.round(item.value * h)}
              </div>
              <div
                style={{
                  width: "100%",
                  height: `${(item.value / max) * 100 * h}%`,
                  background: "#E8B84B",
                  borderRadius: 18,
                }}
              />
              <div style={{ fontSize: 30, opacity: 0.75, marginTop: 18 }}>
                {item.label}
              </div>
            </div>
          );
        })}
      </AbsoluteFill>

      <div
        style={{
          position: "absolute",
          left: 90,
          right: 90,
          bottom: 70,
          fontSize: 24,
          opacity: 0.45,
          textAlign: "center",
        }}
      >
        {DATA.source}
      </div>
    </AbsoluteFill>
  );
};

export const RemotionRoot = () => {
  return (
    <Composition
      id="AnimatedChart"
      component={AnimatedChart}
      durationInFrames={DURATION}
      fps={FPS}
      width={1920}
      height={1080}
    />
  );
};

registerRoot(RemotionRoot);

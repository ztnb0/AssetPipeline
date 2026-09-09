import { loadFont } from "@remotion/fonts";
import {
  AbsoluteFill,
  Composition,
  Easing,
  interpolate,
  registerRoot,
  Sequence,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { DATA, type ChartData } from "./data";
import { Counter } from "@/remotion/primitives/counter";
import { FadeIn } from "@/remotion/primitives/fade-in";

loadFont({
  family: "Noto Sans SC",
  url: staticFile("fonts/NotoSansSC-VF.ttf"),
});

const FPS = 30;
const DURATION = 8 * FPS;

const ACCENT_LEFT = "#D4A574";
const ACCENT_RIGHT = "#67C5A8";
const ACCENT_HIGHLIGHT = "#F0C060";
const BG = "#0E0F13";
const TEXT_PRIMARY = "#FFFFFF";
const TEXT_SECONDARY = "rgba(255,255,255,0.55)";
const TEXT_MUTE = "rgba(255,255,255,0.35)";

type DataCardProps = {
  side: "left" | "right";
  note: string;
  label: string;
  value: string;
  numericValue: number;
  unit?: string;
};

const DataCard: React.FC<DataCardProps> = ({
  side,
  note,
  label,
  value,
  numericValue,
  unit,
}) => {
  const frame = useCurrentFrame();
  const { width } = useVideoConfig();
  const accent = side === "left" ? ACCENT_LEFT : ACCENT_RIGHT;

  const scale = interpolate(frame, [0, 25], [0.92, 1], {
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });

  const opacity = interpolate(frame, [0, 30], [0, 1], {
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });

  const lineY = interpolate(frame, [30, 60], [0, 1], {
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });

  const cardW = Math.min(340, width * 0.28);

  return (
    <div
      style={{
        opacity,
        scale,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 0,
      }}
    >
      {/* Note badge */}
      <div
        style={{
          fontSize: 15,
          color: accent,
          fontWeight: 500,
          letterSpacing: "0.02em",
          opacity: interpolate(frame, [15, 45], [0, 1], {
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.16, 1, 0.3, 1),
          }),
        }}
      >
        {note}
      </div>

      {/* Card container */}
      <div
        style={{
          position: "relative",
          width: cardW,
          minHeight: 340,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          paddingTop: 24,
          paddingBottom: 32,
          paddingLeft: 20,
          paddingRight: 20,
          background: "rgba(255,255,255,0.035)",
          borderRadius: 20,
          border: `1px solid rgba(255,255,255,0.08)`,
        }}
      >
        {/* Top guide line */}
        <div
          style={{
            position: "absolute",
            top: 0,
            left: "50%",
            width: 1,
            height: 20,
            background: accent,
            opacity: interpolate(frame, [20, 50], [0, 0.5], {
              extrapolateRight: "clamp",
              easing: Easing.bezier(0.16, 1, 0.3, 1),
            }),
          }}
        />

        {/* Accent bar at top */}
        <div
          style={{
            position: "absolute",
            top: 0,
            left: "50%",
            transform: "translateX(-50%)",
            width: 50,
            height: 3,
            background: accent,
            borderRadius: 2,
            opacity: interpolate(frame, [25, 55], [0, 1], {
              extrapolateRight: "clamp",
              easing: Easing.bezier(0.16, 1, 0.3, 1),
            }),
          }}
        />

        {/* Main data — Counter */}
        <div
          style={{
            display: "flex",
            alignItems: "baseline",
            justifyContent: "center",
            marginBottom: 10,
          }}
        >
          <Counter
            from={0}
            to={numericValue}
            durationInFrames={50}
            delayInFrames={30}
            decimals={0}
            suffix={unit ? unit : ""}
            fontSize={72}
            fontWeight={800}
            color={TEXT_PRIMARY}
            fontFamily="Noto Sans SC"
            grouping={side === "left"}
            style={{
              opacity: interpolate(frame, [30, 55], [0, 1], {
                extrapolateRight: "clamp",
                easing: Easing.bezier(0.16, 1, 0.3, 1),
              }),
            }}
          />
        </div>

        {/* Data highlight line */}
        <div
          style={{
            width: 40,
            height: 2,
            background: accent,
            borderRadius: 1,
            marginBottom: 20,
            scale: interpolate(frame, [40, 70], [0, 1], {
              extrapolateRight: "clamp",
              easing: Easing.bezier(0.16, 1, 0.3, 1),
            }),
          }}
        />

        {/* Value note */}
        <div
          style={{
            fontSize: 28,
            fontWeight: 700,
            color: accent,
            letterSpacing: "-0.01em",
            marginBottom: 8,
            opacity: interpolate(frame, [30, 60], [0, 1], {
              extrapolateRight: "clamp",
              easing: Easing.bezier(0.16, 1, 0.3, 1),
            }),
          }}
        >
          {value}
        </div>

        {/* Label */}
        <div
          style={{
            fontSize: 18,
            color: TEXT_SECONDARY,
            fontWeight: 500,
            opacity: interpolate(frame, [45, 75], [0, 1], {
              extrapolateRight: "clamp",
              easing: Easing.bezier(0.16, 1, 0.3, 1),
            }),
          }}
        >
          {label}
        </div>

        {/* Bottom guide line */}
        <div
          style={{
            position: "absolute",
            bottom: 0,
            left: "50%",
            width: 1,
            height: 20,
            background: accent,
            opacity: interpolate(frame, [30, 60], [0, 0.4], {
              extrapolateRight: "clamp",
              easing: Easing.bezier(0.16, 1, 0.3, 1),
            }),
          }}
        />
      </div>

      {/* Y axis guide */}
      <svg
        width="1"
        height={120 * lineY}
        style={{ display: "block", marginTop: 0 }}
      >
        <line
          x1="0"
          y1="0"
          x2="0"
          y2={120 * lineY}
          stroke={TEXT_MUTE}
          strokeWidth="1"
        />
      </svg>

      {/* Axis ticks */}
      <svg width="100" height="120" style={{ display: "block" }}>
        {[0, 1, 2, 3].map((i) => {
          const tickY = 20 + i * 30;
          const tickOpacity = interpolate(frame, [50 + i * 8, 70 + i * 8], [0, 0.4], {
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.16, 1, 0.3, 1),
          });
          return (
            <line
              key={i}
              x1="-40"
              y1={tickY}
              x2="-4"
              y2={tickY}
              stroke={TEXT_MUTE}
              strokeWidth="0.5"
              opacity={tickOpacity}
            />
          );
        })}
      </svg>
    </div>
  );
};

const ArrowConnection: React.FC = () => {
  const frame = useCurrentFrame();

  const opacity = interpolate(frame, [55, 90], [0, 0.7], {
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });

  const arrowScale = interpolate(frame, [60, 90], [0.7, 1], {
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        opacity,
        scale: arrowScale,
        gap: 6,
      }}
    >
      <svg width="60" height="40" viewBox="0 0 60 40">
        {/* Left line */}
        <line
          x1="0"
          y1="20"
          x2="20"
          y2="20"
          stroke={ACCENT_HIGHLIGHT}
          strokeWidth="1.5"
          strokeDasharray="3 2"
        />
        {/* Arrow head */}
        <path
          d="M 20 13 L 30 20 L 20 27"
          fill="none"
          stroke={ACCENT_HIGHLIGHT}
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        {/* Right line */}
        <line
          x1="30"
          y1="20"
          x2="60"
          y2="20"
          stroke={ACCENT_HIGHLIGHT}
          strokeWidth="1.5"
          strokeDasharray="3 2"
        />
      </svg>
      <div
        style={{
          fontSize: 12,
          color: ACCENT_HIGHLIGHT,
          fontWeight: 600,
          letterSpacing: "0.06em",
          textTransform: "uppercase",
          opacity: interpolate(frame, [65, 95], [0, 0.8], {
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.16, 1, 0.3, 1),
          }),
        }}
      >
        杠杆效应
      </div>
    </div>
  );
};

const ConclusionLine: React.FC = () => {
  const frame = useCurrentFrame();

  const opacity = interpolate(frame, [110, 150], [0, 1], {
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });

  const highlightOpacity = interpolate(frame, [130, 180], [0, 1], {
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });

  const { width } = useVideoConfig();

  return (
    <div
      style={{
        position: "absolute",
        bottom: 100,
        left: "50%",
        transform: "translateX(-50%)",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        opacity,
      }}
    >
      {/* Separator line */}
      <div
        style={{
          width: Math.min(500, width * 0.5),
          height: 1,
          background: "rgba(255,255,255,0.1)",
          marginBottom: 24,
        }}
      />

      <div
        style={{
          fontSize: 32,
          color: TEXT_PRIMARY,
          fontWeight: 600,
          letterSpacing: "-0.01em",
        }}
      >
        {DATA.subtitle}
      </div>

      {/* Highlighted conclusion */}
      <div
        style={{
          marginTop: 16,
          padding: "10px 32px",
          background: `${ACCENT_HIGHLIGHT}15`,
          border: `1px solid ${ACCENT_HIGHLIGHT}40`,
          borderRadius: 8,
          opacity: highlightOpacity,
        }}
      >
        <span style={{ fontSize: 22, color: ACCENT_HIGHLIGHT, fontWeight: 700 }}>
          核心结论：10% 首付撬动 100% 资产增值
        </span>
      </div>

      {/* Source */}
      <div
        style={{
          marginTop: 28,
          fontSize: 14,
          color: TEXT_MUTE,
          letterSpacing: "0.02em",
        }}
      >
        {DATA.source}
      </div>
    </div>
  );
};

export const AnimatedChart = () => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();

  const titleOpacity = interpolate(frame, [0, 35], [0, 1], {
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });

  const titleTranslate = interpolate(frame, [0, 35], [-30, 0], {
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });

  const safeX = width * 0.08;
  const contentW = width * 0.84;

  return (
    <AbsoluteFill
      style={{
        background: BG,
        color: TEXT_PRIMARY,
        fontFamily: "Noto Sans SC",
        overflow: "hidden",
      }}
    >
      {/* Background subtle grid */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage: `
            linear-gradient(rgba(255,255,255,0.015) 1px, transparent 1px),
            linear-gradient(90deg, rgba(255,255,255,0.015) 1px, transparent 1px)
          `,
          backgroundSize: "80px 80px",
          backgroundPosition: "center center",
        }}
      />

      {/* Background radial glow */}
      <div
        style={{
          position: "absolute",
          top: "30%",
          left: "50%",
          transform: "translate(-50%, -50%)",
          width: contentW * 0.9,
          height: 500,
          background: "radial-gradient(ellipse 50% 50%, rgba(240,192,96,0.04), transparent 70%)",
          pointerEvents: "none",
        }}
      />

      {/* Title */}
      <div
        style={{
          position: "absolute",
          top: 70,
          left: "50%",
          transform: "translateX(-50%)",
          opacity: titleOpacity,
          translate: `0 ${titleTranslate}px`,
          textAlign: "center",
        }}
      >
        <div style={{ fontSize: 56, fontWeight: 700, letterSpacing: "-0.02em" }}>
          {DATA.title}
        </div>
        <div
          style={{
            fontSize: 22,
            color: TEXT_SECONDARY,
            marginTop: 12,
            fontWeight: 400,
            letterSpacing: "0.01em",
          }}
        >
          财经课程 · 杠杆原理与首付撬动效应
        </div>
      </div>

      {/* Comparison area */}
      <div
        style={{
          position: "absolute",
          top: 220,
          left: safeX,
          width: contentW,
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "center",
          gap: 0,
        }}
      >
        {/* Left card */}
        <FadeIn from={0} to={1} durationInFrames={30} delayInFrames={5}>
          <div style={{ flex: 1, maxWidth: 420 }}>
            <DataCard
              side="left"
              note={DATA.left.note}
              label={DATA.left.label}
              value={DATA.left.value}
              numericValue={100000}
              unit=""
            />
          </div>
        </FadeIn>

        {/* Arrow connection */}
        <div style={{ flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center", height: 340 }}>
          <ArrowConnection />
        </div>

        {/* Right card */}
        <FadeIn from={0} to={1} durationInFrames={30} delayInFrames={15}>
          <div style={{ flex: 1, maxWidth: 420 }}>
            <DataCard
              side="right"
              note={DATA.right.note}
              label={DATA.right.label}
              value={DATA.right.value}
              numericValue={100}
              unit="%"
            />
          </div>
        </FadeIn>
      </div>

      {/* Conclusion line */}
      <ConclusionLine />
    </AbsoluteFill>
  );
};

export const RemotionRoot = () => {
  return (
    <Composition
      id="Chart-e5ba41d7e5f0"
      component={AnimatedChart}
      durationInFrames={DURATION}
      fps={FPS}
      width={1920}
      height={1080}
    />
  );
};

registerRoot(RemotionRoot);

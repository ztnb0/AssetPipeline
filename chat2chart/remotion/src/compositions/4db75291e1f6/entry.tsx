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
import { DATA } from "./data";
import { Counter } from "@/remotion/primitives/counter";

// ── Font ──────────────────────────────────────────────────────────
loadFont({
  family: "Noto Sans SC",
  url: staticFile("fonts/NotoSansSC-VF.ttf"),
});

// ── Constants ─────────────────────────────────────────────────────
const FPS = 30;
const DURATION = 240;

const clamp = {
  extrapolateLeft: "clamp" as const,
  extrapolateRight: "clamp" as const,
};

// ── Easing presets ────────────────────────────────────────────────
const smooth = Easing.bezier(0.16, 1, 0.3, 1);
const snapBack = Easing.bezier(0.34, 1.56, 0.64, 1);

// ── Dynamic Background ────────────────────────────────────────────
const DynamicBackground = () => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();

  const drift = interpolate(frame, [0, DURATION], [0, 50], clamp);
  const mid = DURATION / 2;
  const glow1 = interpolate(frame, [0, mid, DURATION], [0.035, 0.065, 0.035], clamp);
  const glow2 = interpolate(frame, [0, mid, DURATION], [0.04, 0.07, 0.04], clamp);
  const glow3 = interpolate(frame, [0, mid, DURATION], [0.02, 0.04, 0.02], clamp);
  const sweepX = interpolate(
    frame,
    [0, DURATION * 1.2],
    [-width * 0.3, width * 1.3],
    clamp
  );

  return (
    <AbsoluteFill
      style={{
        background:
          "linear-gradient(160deg, #080E1A 0%, #0D1930 30%, #111E3C 55%, #0B1528 100%)",
      }}
    >
      {/* Noise texture */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          opacity: 0.018,
          backgroundImage:
            "url(\"data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E\")",
          backgroundSize: "128px 128px",
        }}
      />

      {/* Perspective grid */}
      <svg
        width={width}
        height={height}
        style={{ position: "absolute", inset: 0, opacity: 0.035 }}
      >
        <defs>
          <pattern
            id="grid"
            width="80"
            height="80"
            patternUnits="userSpaceOnUse"
            x={-(drift % 80)}
            y={-(drift % 80)}
          >
            <path
              d="M 80 0 L 0 0 0 80"
              fill="none"
              stroke="#4A8FE7"
              strokeWidth="0.5"
            />
          </pattern>
        </defs>
        <rect width={width} height={height} fill="url(#grid)" />
      </svg>

      {/* Radial glows — breathing */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: `radial-gradient(ellipse 40% 35% at 28% 42%, #1A5090${Math.round(glow1 * 255).toString(16).padStart(2, "0")}, transparent 75%)`,
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: `radial-gradient(ellipse 38% 32% at 72% 48%, #2A6AB8${Math.round(glow2 * 255).toString(16).padStart(2, "0")}, transparent 75%)`,
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: `radial-gradient(ellipse 60% 50% at 50% 50%, #0E2A55${Math.round(glow3 * 255).toString(16).padStart(2, "0")}, transparent 70%)`,
        }}
      />

      {/* Light sweep */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: `linear-gradient(${135}deg, transparent 40%, rgba(74, 143, 231, 0.025) 45%, rgba(74, 143, 231, 0.04) 50%, rgba(74, 143, 231, 0.025) 55%, transparent 60%)`,
          transform: `translateX(${sweepX}px)`,
        }}
      />
    </AbsoluteFill>
  );
};

// ── Title & Subtitle ──────────────────────────────────────────────
const TitleArea = () => {
  const frame = useCurrentFrame();

  const titleIn = interpolate(frame, [0, 35], [0, 1], { easing: smooth, ...clamp });
  const titleUp = interpolate(frame, [0, 35], [24, 0], { easing: smooth, ...clamp });
  const subIn = interpolate(frame, [25, 60], [0, 1], { easing: smooth, ...clamp });
  const subUp = interpolate(frame, [25, 60], [16, 0], { easing: smooth, ...clamp });

  return (
    <div
      style={{
        position: "absolute",
        top: 100,
        left: 154,
        right: 154,
        opacity: titleIn,
        translate: `0 ${titleUp}px`,
      }}
    >
      <div
        style={{
          fontSize: 64,
          fontWeight: 800,
          color: "#FFFFFF",
          letterSpacing: "-0.02em",
          fontFamily: "'Noto Sans SC'",
        }}
      >
        {DATA.shortTitle}
      </div>
      <div
        style={{
          fontSize: 30,
          fontWeight: 400,
          color: `rgba(180, 210, 255, ${0.7 * subIn})`,
          marginTop: 16,
          letterSpacing: "0.02em",
          translate: `0 ${subUp}px`,
          fontFamily: "'Noto Sans SC'",
        }}
      >
        {DATA.subtitle}
      </div>
    </div>
  );
};

// ── Comparison Panel (left or right) ──────────────────────────────
const ComparisonPanel = ({
  side,
  note,
  label,
  value,
  glowColor,
  accentColor,
  panelOpacity,
  panelScale,
  panelTranslate,
  iconVisible,
  contentVisible,
  valueVisible,
  accentOn,
  contentUp,
}: {
  side: "left" | "right";
  note: string;
  label: string;
  value: string;
  glowColor: string;
  accentColor: string;
  panelOpacity: number;
  panelScale: number;
  panelTranslate: string;
  iconVisible: number;
  contentVisible: number;
  valueVisible: number;
  accentOn: number;
  contentUp: number;
}) => {
  const { width } = useVideoConfig();
  const isLeft = side === "left";
  const panelWidth = isLeft ? 480 : 560;

  return (
    <div
      style={{
        position: "absolute",
        ...(isLeft
          ? { left: 150, top: 310 }
          : { right: 150, top: 310 }),
        width: panelWidth,
        opacity: panelOpacity,
        scale: panelScale,
        translate: panelTranslate,
      }}
    >
      {/* Panel glow behind */}
      <div
        style={{
          position: "absolute",
          inset: -20,
          borderRadius: 36,
          background: `radial-gradient(ellipse at center, ${glowColor}22, transparent 70%)`,
          filter: "blur(16px)",
        }}
      />

      {/* Panel card */}
      <div
        style={{
          position: "relative",
          background: `linear-gradient(145deg, rgba(20, 35, 65, 0.65), rgba(12, 22, 42, 0.55))`,
          backdropFilter: "blur(12px)",
          border: `1px solid rgba(74, 143, 231, ${0.12 + accentOn * 0.1})`,
          borderRadius: 28,
          padding: isLeft ? 44 : 48,
          overflow: "hidden",
        }}
      >
        {/* Top accent line */}
        <div
          style={{
            position: "absolute",
            top: 0,
            left: isLeft ? 40 : "auto",
            right: isLeft ? "auto" : 40,
            width: 60,
            height: 3,
            background: accentColor,
            borderRadius: 2,
            opacity: accentOn,
          }}
        />

        {/* Icon */}
        <div
          style={{
            opacity: iconVisible,
            marginBottom: 20,
          }}
        >
          {isLeft ? (
            <svg width="36" height="36" viewBox="0 0 36 36" fill="none">
              <circle cx="18" cy="18" r="14" stroke={accentColor} strokeWidth="1.5" opacity="0.6" />
              <text
                x="18"
                y="23"
                textAnchor="middle"
                fill={accentColor}
                fontSize="14"
                fontWeight="700"
                fontFamily="'Noto Sans SC'"
              >
                ¥
              </text>
            </svg>
          ) : (
            <svg width="36" height="36" viewBox="0 0 36 36" fill="none">
              <path
                d="M6 28 L14 18 L20 22 L30 10"
                stroke={accentColor}
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                opacity="0.7"
              />
              <path d="M24 10 L30 10 L30 16" stroke={accentColor} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          )}
        </div>

        {/* Note badge */}
        <div
          style={{
            fontSize: 20,
            color: `rgba(150, 185, 240, ${0.55 * iconVisible})`,
            marginBottom: 18,
            fontFamily: "'Noto Sans SC'",
            fontStyle: "italic",
          }}
        >
          {note}
        </div>

        {/* Label */}
        <div
          style={{
            fontSize: 24,
            fontWeight: 600,
            color: `rgba(200, 220, 255, ${0.7 * contentVisible})`,
            marginBottom: 24,
            translate: `0 ${contentUp}px`,
            fontFamily: "'Noto Sans SC'",
          }}
        >
          {label}
        </div>

        {/* Value */}
        <div
          style={{
            fontSize: 120,
            fontWeight: 800,
            color: "#FFFFFF",
            lineHeight: 1,
            letterSpacing: "-0.03em",
            opacity: valueVisible,
            translate: `0 ${contentUp}px`,
            fontFamily: "'Noto Sans SC'",
            textShadow: `0 0 40px ${accentColor}44`,
          }}
        >
          {value}
        </div>
      </div>
    </div>
  );
};

// ── Lever Visual (SVG) ────────────────────────────────────────────
const LeverVisual = ({
  visible,
  drawProgress,
  accentPulse,
}: {
  visible: number;
  drawProgress: number;
  accentPulse: number;
}) => {
  const { width, height } = useVideoConfig();
  const cx = width / 2;
  const cy = 600;
  const leftX = 390;
  const rightX = 1530;

  // Glow ring behind fulcrum
  const glowScale = interpolate(accentPulse, [0, 1], [0.8, 1.2], clamp);
  const glowOpacity = interpolate(accentPulse, [0, 1], [0, 0.5], clamp);

  return (
    <div
      style={{
        position: "absolute",
        left: 0,
        right: 0,
        top: 0,
        bottom: 0,
        opacity: visible,
        pointerEvents: "none",
      }}
    >
      <svg
        width={width}
        height={height}
        style={{ overflow: "visible" }}
      >
        <defs>
          <linearGradient id="leverGrad" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#4A8FE7" stopOpacity="0.6" />
            <stop offset="100%" stopColor="#E8B84B" stopOpacity="0.9" />
          </linearGradient>
          <filter id="glow">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Left → Right arrow (amplification path) */}
        <line
          x1={leftX + 20}
          y1={cy}
          x2={leftX + (rightX - leftX - 40) * drawProgress}
          y2={cy}
          stroke="url(#leverGrad)"
          strokeWidth="2.5"
          strokeLinecap="round"
        />

        {/* Arrowhead */}
        {drawProgress > 0.5 && (
          <g transform={`translate(${leftX + (rightX - leftX - 40) * drawProgress}, ${cy})`}>
            <path
              d="M0,-6 L14,0 L0,6 Z"
              fill="#E8B84B"
              opacity={interpolate(drawProgress, [0.5, 0.65], [0, 1], clamp)}
            />
          </g>
        )}

        {/* Amplification label along the line */}
        {drawProgress > 0.7 && (
          <g
            opacity={interpolate(drawProgress, [0.7, 0.85], [0, 1], clamp)}
            transform={`translate(${cx}, ${cy - 30})`}
          >
            <rect
              x="-70"
              y="-16"
              width="140"
              height="32"
              rx="16"
              fill="rgba(10, 18, 35, 0.7)"
              stroke="#E8B84B"
              strokeWidth="1"
              opacity="0.7"
            />
            <text
              x="0"
              y="5"
              textAnchor="middle"
              fill="#E8B84B"
              fontSize="18"
              fontWeight="700"
              fontFamily="'Noto Sans SC'"
            >
              杠杆放大 →
            </text>
          </g>
        )}

        {/* Fulcrum (triangle) */}
        <g transform={`translate(${cx}, ${cy + 2})`}>
          {/* Glow */}
          <circle
            cx="0"
            cy="0"
            r={16 * glowScale}
            fill="#E8B84B"
            opacity={glowOpacity}
          />
          {/* Triangle */}
          <path
            d="M0,-14 L-12,10 L12,10 Z"
            fill="none"
            stroke="#E8B84B"
            strokeWidth="1.5"
            filter="url(#glow)"
          />
        </g>

        {/* Left connection dot */}
        <circle
          cx={leftX + 10}
          cy={cy}
          r={4 + accentPulse * 2}
          fill="#4A8FE7"
          opacity={0.6 + accentPulse * 0.3}
        />

        {/* Right connection dot */}
        <circle
          cx={rightX - 10}
          cy={cy}
          r={4 + accentPulse * 2}
          fill="#E8B84B"
          opacity={0.6 + accentPulse * 0.3}
        />
      </svg>
    </div>
  );
};

// ── Conclusion ────────────────────────────────────────────────────
const ConclusionArea = ({
  visible,
  glowIntensity,
  textUp,
}: {
  visible: number;
  glowIntensity: number;
  textUp: number;
}) => {
  return (
    <div
      style={{
        position: "absolute",
        top: 740,
        left: 154,
        right: 154,
        opacity: visible,
        translate: `0 ${textUp}px`,
      }}
    >
      {/* Glow behind conclusion */}
      <div
        style={{
          position: "absolute",
          inset: -16,
          borderRadius: 24,
          background: `radial-gradient(ellipse at center, rgba(232, 184, 75, ${glowIntensity * 0.08}), transparent 70%)`,
          filter: "blur(12px)",
        }}
      />

      {/* Conclusion box */}
      <div
        style={{
          position: "relative",
          textAlign: "center",
          padding: "24px 40px",
          borderRadius: 20,
          background: `linear-gradient(135deg, rgba(20, 35, 65, ${0.5 + glowIntensity * 0.2}), rgba(12, 22, 42, ${0.4 + glowIntensity * 0.15}))`,
          border: `1px solid rgba(232, 184, 75, ${0.15 + glowIntensity * 0.2})`,
        }}
      >
        <div
          style={{
            fontSize: 44,
            fontWeight: 800,
            color: "#FFFFFF",
            fontFamily: "'Noto Sans SC'",
            letterSpacing: "-0.01em",
          }}
        >
          <span style={{ color: "#E8B84B" }}>10% 首付</span>
          {" "}撬动{" "}
          <span style={{ color: "#E8B84B" }}>100%</span> 资产增值
        </div>
      </div>

      {/* Source */}
      <div
        style={{
          textAlign: "center",
          fontSize: 20,
          color: "rgba(130, 160, 210, 0.4)",
          marginTop: 18,
          fontFamily: "'Noto Sans SC'",
        }}
      >
        {DATA.source}
      </div>
    </div>
  );
};

// ── Main Composition ──────────────────────────────────────────────
const Chart = () => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();

  // ── Title ──
  const titleIn = interpolate(frame, [0, 30], [0, 1], { easing: smooth, ...clamp });
  const titleUp = interpolate(frame, [0, 30], [20, 0], { easing: smooth, ...clamp });

  // ── Subtitle ──
  const subIn = interpolate(frame, [20, 50], [0, 1], { easing: smooth, ...clamp });
  const subUp = interpolate(frame, [20, 50], [14, 0], { easing: smooth, ...clamp });

  // ── Left panel ──
  const leftPanelIn = interpolate(frame, [40, 85], [0, 1], { easing: smooth, ...clamp });
  const leftPanelUp = interpolate(frame, [40, 85], [30, 0], { easing: smooth, ...clamp });
  const leftIconIn = interpolate(frame, [55, 80], [0, 1], { easing: smooth, ...clamp });
  const leftContentIn = interpolate(frame, [55, 90], [0, 1], { easing: smooth, ...clamp });
  const leftContentUp = interpolate(frame, [55, 90], [16, 0], { easing: smooth, ...clamp });
  const leftValueIn = interpolate(frame, [60, 100], [0, 1], { easing: smooth, ...clamp });
  const leftAccentPulse = interpolate(frame, [90, 100], [0, 1], clamp);

  // ── Right panel ──
  const rightPanelIn = interpolate(frame, [65, 110], [0, 1], { easing: smooth, ...clamp });
  const rightPanelUp = interpolate(frame, [65, 110], [30, 0], { easing: smooth, ...clamp });
  const rightIconIn = interpolate(frame, [80, 105], [0, 1], { easing: smooth, ...clamp });
  const rightContentIn = interpolate(frame, [80, 115], [0, 1], { easing: smooth, ...clamp });
  const rightContentUp = interpolate(frame, [80, 115], [16, 0], { easing: smooth, ...clamp });
  const rightValueIn = interpolate(frame, [85, 125], [0, 1], { easing: smooth, ...clamp });
  const rightAccentPulse = interpolate(frame, [115, 125], [0, 1], clamp);

  // ── Lever ──
  const leverIn = interpolate(frame, [80, 100], [0, 1], { easing: smooth, ...clamp });
  const leverDraw = interpolate(frame, [90, 130], [0, 1], { easing: smooth, ...clamp });
  const leverPulse = interpolate(frame, [110, 130], [0, 1], clamp);

  // ── Counter timing ──
  const counterDelay = 65;
  const counterDur = 55;
  const counterVisible = interpolate(
    frame,
    [counterDelay - 10, counterDelay],
    [0, 1],
    clamp
  );

  // ── Conclusion ──
  const conclusionIn = interpolate(frame, [120, 165], [0, 1], { easing: smooth, ...clamp });
  const conclusionUp = interpolate(frame, [120, 165], [24, 0], { easing: smooth, ...clamp });
  const conclusionGlow = interpolate(frame, [150, 180], [0, 1], clamp);
  const conclusionSweep = interpolate(
    frame,
    [140, 180, 200],
    [0, 1, 0],
    clamp
  );

  // ── Hold: fade everything slightly after conclusion ──
  const fadeOut = interpolate(frame, [210, 235], [1, 0.92], clamp);

  return (
    <AbsoluteFill
      style={{
        fontFamily: "'Noto Sans SC'",
        opacity: fadeOut,
      }}
    >
      {/* Background */}
      <DynamicBackground />

      {/* Title */}
      <Sequence from={0}>
        <div
          style={{
            position: "absolute",
            top: 100,
            left: 154,
            right: 154,
            opacity: titleIn,
            translate: `0 ${titleUp}px`,
          }}
        >
          <div
            style={{
              fontSize: 64,
              fontWeight: 800,
              color: "#FFFFFF",
              letterSpacing: "-0.02em",
            }}
          >
            {DATA.shortTitle}
          </div>
          <div
            style={{
              fontSize: 30,
              fontWeight: 400,
              color: `rgba(180, 210, 255, ${subIn * 0.7})`,
              marginTop: 16,
              letterSpacing: "0.02em",
              translate: `0 ${interpolate(frame, [20, 50], [14, 0], { easing: smooth, ...clamp })}px`,
            }}
          >
            {DATA.subtitle}
          </div>
        </div>
      </Sequence>

      {/* Left Panel */}
      <Sequence from={0}>
        <ComparisonPanel
          side="left"
          note={DATA.left.note}
          label={DATA.left.label}
          value={DATA.left.value}
          glowColor="#4A8FE7"
          accentColor="#4A8FE7"
          panelOpacity={leftPanelIn}
          panelScale={interpolate(leftPanelIn, [0, 1], [0.92, 1], clamp)}
          panelTranslate={`0 ${leftPanelUp}px`}
          iconVisible={leftIconIn}
          contentVisible={leftContentIn}
          valueVisible={leftValueIn}
          accentOn={leftAccentPulse}
          contentUp={leftContentUp}
        />
      </Sequence>

      {/* Right Panel */}
      <Sequence from={0}>
        <ComparisonPanel
          side="right"
          note={DATA.right.note}
          label={DATA.right.label}
          value={DATA.right.value}
          glowColor="#E8B84B"
          accentColor="#E8B84B"
          panelOpacity={rightPanelIn}
          panelScale={interpolate(rightPanelIn, [0, 1], [0.92, 1], clamp)}
          panelTranslate={`0 ${rightPanelUp}px`}
          iconVisible={rightIconIn}
          contentVisible={rightContentIn}
          valueVisible={rightValueIn}
          accentOn={rightAccentPulse}
          contentUp={rightContentUp}
        />
      </Sequence>

      {/* Lever visual */}
      <Sequence from={0}>
        <LeverVisual
          visible={leverIn}
          drawProgress={leverDraw}
          accentPulse={leverPulse}
        />
      </Sequence>

      {/* Counter values overlaid on panels */}
      <Sequence from={counterDelay}>
        <AbsoluteFill>
          {/* Left counter — "10" → "10" with suffix "万" */}
          <div
            style={{
              position: "absolute",
              left: 230,
              top: 530,
              opacity: counterVisible,
              fontFamily: "'Noto Sans SC'",
            }}
          >
            <Counter
              from={0}
              to={10}
              durationInFrames={counterDur}
              decimals={0}
              roll={true}
              suffix="万"
              fontSize={140}
              fontWeight={800}
              color="#FFFFFF"
              settle={true}
            />
          </div>

          {/* Right counter — "100" → "100" with suffix "%" */}
          <div
            style={{
              position: "absolute",
              right: 260,
              top: 510,
              opacity: counterVisible,
              fontFamily: "'Noto Sans SC'",
            }}
          >
            <Counter
              from={0}
              to={100}
              durationInFrames={counterDur}
              decimals={0}
              roll={true}
              suffix="%"
              fontSize={140}
              fontWeight={800}
              color="#FFFFFF"
              settle={true}
            />
          </div>
        </AbsoluteFill>
      </Sequence>

      {/* Conclusion */}
      <Sequence from={0}>
        <ConclusionArea
          visible={conclusionIn}
          glowIntensity={conclusionGlow}
          textUp={conclusionUp}
        />
      </Sequence>
    </AbsoluteFill>
  );
};

// ── Composition Export ────────────────────────────────────────────
export const RemotionRoot = () => {
  return (
    <Composition
      id="Chart-4db75291e1f6"
      component={Chart}
      durationInFrames={DURATION}
      fps={FPS}
      width={1920}
      height={1080}
    />
  );
};

registerRoot(RemotionRoot);

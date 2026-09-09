import { loadFont } from "@remotion/fonts";
import {
  AbsoluteFill,
  Composition,
  Easing,
  interpolate,
  registerRoot,
  Sequence,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { VIDEO_DATA, TREND_DATA, COMPARISON_DATA } from "./data";

loadFont({
  family: "Noto Sans SC",
  url: staticFile("fonts/NotoSansSC-VF.ttf"),
});

const FPS = 30;
const DURATION = 240;

const US_COLOR = "#3b82f6";
const CN_COLOR = "#e8b84b";
const BG = "#0E0F13";

const TitleCard = () => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();

  const titleIn = interpolate(frame, [0, 35], [0, 1], {
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });
  const subtitleIn = interpolate(frame, [20, 55], [0, 1], {
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });
  const scale = interpolate(frame, [0, 35], [0.85, 1], {
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });

  return (
    <AbsoluteFill
      style={{
        background: BG,
        color: "#fff",
        fontFamily: "Noto Sans SC",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          opacity: titleIn,
          scale: scale,
          translate: `0 ${interpolate(frame, [0, 35], [30, 0], {
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.16, 1, 0.3, 1),
          })}px`,
        }}
      >
        <div
          style={{
            fontSize: 72,
            fontWeight: 800,
            letterSpacing: -1,
            textAlign: "center",
            background: "linear-gradient(135deg, #e8b84b 0%, #f0d080 50%, #e8b84b 100%)",
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
          }}
        >
          {VIDEO_DATA.title}
        </div>
      </div>
      <div
        style={{
          marginTop: 28,
          fontSize: 32,
          opacity: subtitleIn,
          color: "rgba(255,255,255,0.55)",
          fontWeight: 500,
        }}
      >
        {VIDEO_DATA.subtitle}
      </div>
      <div
        style={{
          position: "absolute",
          bottom: 80,
          fontSize: 24,
          opacity: interpolate(frame, [40, 60], [0, 0.4], {
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.16, 1, 0.3, 1),
          }),
          color: "rgba(255,255,255,0.6)",
          textAlign: "center",
        }}
      >
        {VIDEO_DATA.source}
      </div>
    </AbsoluteFill>
  );
};

const TrendChart = () => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();

  const chartIn = interpolate(frame, [0, 25], [0, 1], {
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });

  // Line draw progress: frames 15-90
  const lineDraw = interpolate(frame, [15, 90], [0, 1], {
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });

  // Value label appear: frames 70-100
  const valueIn = interpolate(frame, [70, 100], [0, 1], {
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });

  // Legend fade in
  const legendIn = interpolate(frame, [50, 75], [0, 1], {
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });

  // Chart dimensions
  const padding = { top: 140, right: 100, bottom: 100, left: 100 };
  const chartW = width - padding.left - padding.right;
  const chartH = height - padding.top - padding.bottom;

  // Data ranges
  const minVal = 0;
  const maxVal = 9000;
  const years = TREND_DATA.map((d) => d.year);
  const minYear = years[0];
  const maxYear = years[years.length - 1];

  // Value label format
  const formatValue = (v: number) => Math.round(v).toLocaleString();

  return (
    <AbsoluteFill
      style={{
        background: BG,
        fontFamily: "Noto Sans SC",
      }}
    >
      {/* Header */}
      <div
        style={{
          position: "absolute",
          top: 50,
          left: padding.left,
          right: padding.right,
          opacity: chartIn,
        }}
      >
        <div style={{ fontSize: 48, fontWeight: 700, color: "#fff" }}>
          黄金储备趋势
        </div>
        <div style={{ fontSize: 26, color: "rgba(255,255,255,0.5)", marginTop: 8 }}>
          中国 vs 美国 · 2014 — 2024
        </div>
      </div>

      {/* Chart area */}
      <div
        style={{
          position: "absolute",
          top: padding.top,
          left: padding.left,
          width: chartW,
          height: chartH,
          opacity: chartIn,
        }}
      >
        <svg
          width={chartW}
          height={chartH}
          style={{ overflow: "visible" }}
        >
          {/* Gridlines */}
          {[0, 0.25, 0.5, 0.75, 1].map((pct) => {
            const y = chartH - pct * chartH;
            return (
              <line
                key={pct}
                x1={0}
                y1={y}
                x2={chartW}
                y2={y}
                stroke="rgba(255,255,255,0.06)"
                strokeWidth={1}
              />
            );
          })}

          {/* Y-axis labels */}
          {[0, 2000, 4000, 6000, 8000].map((val) => {
            const y = chartH - ((val - minVal) / (maxVal - minVal)) * chartH;
            return (
              <text
                key={val}
                x={-16}
                y={y + 6}
                textAnchor="end"
                fill="rgba(255,255,255,0.35)"
                fontSize={20}
                fontFamily="Noto Sans SC"
              >
                {formatValue(val)}
              </text>
            );
          })}

          {/* X-axis labels */}
          {years.map((year, i) => {
            const x = (i / (years.length - 1)) * chartW;
            const labelIn = interpolate(frame, [20 + i * 5, 35 + i * 5], [0, 1], {
              extrapolateRight: "clamp",
              easing: Easing.bezier(0.16, 1, 0.3, 1),
            });
            return (
              <text
                key={year}
                x={x}
                y={chartH + 30}
                textAnchor="middle"
                fill={`rgba(255,255,255,${0.35 * labelIn})`}
                fontSize={20}
                fontFamily="Noto Sans SC"
              >
                {year}
              </text>
            );
          })}

          {/* US line */}
          {(() => {
            const usPoints = TREND_DATA.map((d, i) => ({
              x: (i / (TREND_DATA.length - 1)) * chartW,
              y: chartH - ((d.us - minVal) / (maxVal - minVal)) * chartH,
            }));

            let usPath = "";
            usPoints.forEach((p, i) => {
              usPath += (i === 0 ? "M" : "L") + `${p.x},${p.y}`;
            });

            const usTotalLen = 3000;
            const usDrawLen = usTotalLen * lineDraw;

            return (
              <g>
                <path
                  d={usPath}
                  fill="none"
                  stroke={US_COLOR}
                  strokeWidth={4}
                  strokeLinecap="round"
                  strokeDasharray={usTotalLen}
                  strokeDashoffset={Math.max(0, usTotalLen - usDrawLen)}
                  opacity={Math.min(1, lineDraw * 2)}
                />
                {/* US end dot */}
                {lineDraw > 0.85 && (
                  <circle
                    cx={usPoints[usPoints.length - 1].x}
                    cy={usPoints[usPoints.length - 1].y}
                    r={8}
                    fill={US_COLOR}
                    opacity={interpolate(frame, [90, 105], [0, 1], {
                      extrapolateRight: "clamp",
                      easing: Easing.bezier(0.16, 1, 0.3, 1),
                    })}
                  />
                )}
              </g>
            );
          })()}

          {/* China line */}
          {(() => {
            const cnPoints = TREND_DATA.map((d, i) => ({
              x: (i / (TREND_DATA.length - 1)) * chartW,
              y: chartH - ((d.china - minVal) / (maxVal - minVal)) * chartH,
            }));

            let cnPath = "";
            cnPoints.forEach((p, i) => {
              cnPath += (i === 0 ? "M" : "L") + `${p.x},${p.y}`;
            });

            const cnTotalLen = 3000;
            const cnDrawLen = cnTotalLen * Math.max(0, (lineDraw - 0.1) / 0.9);

            return (
              <g>
                <path
                  d={cnPath}
                  fill="none"
                  stroke={CN_COLOR}
                  strokeWidth={4}
                  strokeLinecap="round"
                  strokeDasharray={cnTotalLen}
                  strokeDashoffset={Math.max(0, cnTotalLen - cnDrawLen)}
                  opacity={Math.min(1, lineDraw * 2)}
                />
                {/* China end dot */}
                {lineDraw > 0.9 && (
                  <circle
                    cx={cnPoints[cnPoints.length - 1].x}
                    cy={cnPoints[cnPoints.length - 1].y}
                    r={8}
                    fill={CN_COLOR}
                    opacity={interpolate(frame, [95, 110], [0, 1], {
                      extrapolateRight: "clamp",
                      easing: Easing.bezier(0.16, 1, 0.3, 1),
                    })}
                  />
                )}
              </g>
            );
          })()}

          {/* Value labels at end points */}
          {(() => {
            const usLast = TREND_DATA[TREND_DATA.length - 1];
            const cnLast = TREND_DATA[TREND_DATA.length - 1];
            const usX = chartW;
            const usY = chartH - ((usLast.us - minVal) / (maxVal - minVal)) * chartH;
            const cnY = chartH - ((cnLast.china - minVal) / (maxVal - minVal)) * chartH;
            const cnX = chartW;

            return (
              <g>
                {/* US label */}
                <g
                  opacity={valueIn}
                  transform={`translate(${usX + 20}, ${usY - 10})`}
                >
                  <text
                    fill={US_COLOR}
                    fontSize={28}
                    fontWeight={700}
                    fontFamily="Noto Sans SC"
                  >
                    {formatValue(usLast.us)}
                  </text>
                  <text
                    y={28}
                    fill="rgba(255,255,255,0.5)"
                    fontSize={22}
                    fontFamily="Noto Sans SC"
                  >
                    (美国)
                  </text>
                </g>
                {/* China label */}
                <g
                  opacity={valueIn}
                  transform={`translate(${cnX + 20}, ${cnY - 10})`}
                >
                  <text
                    fill={CN_COLOR}
                    fontSize={28}
                    fontWeight={700}
                    fontFamily="Noto Sans SC"
                  >
                    {formatValue(cnLast.china)}
                  </text>
                  <text
                    y={28}
                    fill="rgba(255,255,255,0.5)"
                    fontSize={22}
                    fontFamily="Noto Sans SC"
                  >
                    (中国)
                  </text>
                </g>
              </g>
            );
          })()}

          {/* Legend */}
          <g
            opacity={legendIn}
            transform={`translate(${chartW - 240}, 10)`}
          >
            <line x1={0} y1={0} x2={30} y2={0} stroke={US_COLOR} strokeWidth={4} strokeLinecap="round" />
            <text x={40} y={6} fill="rgba(255,255,255,0.7)" fontSize={22} fontFamily="Noto Sans SC">美国</text>

            <line x1={0} y1={30} x2={30} y2={30} stroke={CN_COLOR} strokeWidth={4} strokeLinecap="round" />
            <text x={40} y={36} fill="rgba(255,255,255,0.7)" fontSize={22} fontFamily="Noto Sans SC">中国</text>
          </g>
        </svg>
      </div>
    </AbsoluteFill>
  );
};

const ComparisonChart = () => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();

  const barIn = interpolate(frame, [0, 40], [0, 1], {
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });

  const formatValue = (v: number) => Math.round(v).toLocaleString();

  return (
    <AbsoluteFill
      style={{
        background: BG,
        fontFamily: "Noto Sans SC",
      }}
    >
      {/* Header */}
      <div
        style={{
          position: "absolute",
          top: 50,
          left: 90,
          right: 90,
        }}
      >
        <div style={{ fontSize: 48, fontWeight: 700, color: "#fff" }}>
          2024 年黄金储备对比
        </div>
        <div style={{ fontSize: 26, color: "rgba(255,255,255,0.5)", marginTop: 8 }}>
          美国领先中国约 3.6 倍
        </div>
      </div>

      {/* Bar chart area */}
      <div
        style={{
          position: "absolute",
          top: 200,
          left: 90,
          right: 90,
          bottom: 120,
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          gap: 60,
        }}
      >
        {COMPARISON_DATA.map((item, i) => {
          const maxVal = 9000;
          const barH = 80;
          const barMaxW = width - 400;
          const valueIn = spring({
            frame: frame - 10 - i * 8,
            fps: FPS,
            config: { damping: 20, stiffness: 120, mass: 0.8 },
            durationInFrames: 60,
          });
          const barW = (item.value / maxVal) * barMaxW * valueIn;
          const labelIn = interpolate(frame, [5 + i * 8, 20 + i * 8], [0, 1], {
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.16, 1, 0.3, 1),
          });

          return (
            <div
              key={item.label}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 30,
                opacity: labelIn,
                translate: `0 ${interpolate(frame, [0, 20 + i * 8], [40, 0], {
                  extrapolateRight: "clamp",
                  easing: Easing.bezier(0.16, 1, 0.3, 1),
                })}px`,
              }}
            >
              <div
                style={{
                  width: 100,
                  fontSize: 36,
                  fontWeight: 700,
                  color: "#fff",
                  textAlign: "right",
                  flexShrink: 0,
                }}
              >
                {item.label}
              </div>
              <div
                style={{
                  flex: 1,
                  height: barH,
                  background: "rgba(255,255,255,0.05)",
                  borderRadius: 16,
                  position: "relative",
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    position: "absolute",
                    top: 0,
                    left: 0,
                    height: "100%",
                    width: barW,
                    background: `linear-gradient(90deg, ${item.color}cc 0%, ${item.color} 80%)`,
                    borderRadius: 16,
                    transition: "none",
                  }}
                />
                {/* Value label inside bar */}
                <div
                  style={{
                    position: "absolute",
                    right: 20,
                    top: "50%",
                    transform: "translateY(-50%)",
                    fontSize: 28,
                    fontWeight: 700,
                    color: "#fff",
                    opacity: barIn,
                  }}
                >
                  {formatValue(item.value)} 吨
                </div>
              </div>
              <div
                style={{
                  width: 120,
                  fontSize: 24,
                  color: "rgba(255,255,255,0.5)",
                  flexShrink: 0,
                }}
              >
                {item.delta && (
                  <span
                    style={{
                      color: item.delta.startsWith("+") ? "#22c55e" : "rgba(255,255,255,0.5)",
                      fontWeight: 600,
                    }}
                  >
                    {item.delta}
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Source */}
      <div
        style={{
          position: "absolute",
          bottom: 50,
          left: 90,
          right: 90,
          fontSize: 22,
          color: "rgba(255,255,255,0.35)",
          textAlign: "center",
          opacity: interpolate(frame, [30, 50], [0, 1], {
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.16, 1, 0.3, 1),
          }),
        }}
      >
        {VIDEO_DATA.source}
      </div>
    </AbsoluteFill>
  );
};

const Conclusion = () => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();

  const textIn = interpolate(frame, [0, 40], [0, 1], {
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });
  const scale = interpolate(frame, [0, 40], [0.9, 1], {
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });
  const fadeOut = interpolate(frame, [55, 70], [1, 0], {
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });

  return (
    <AbsoluteFill
      style={{
        background: BG,
        color: "#fff",
        fontFamily: "Noto Sans SC",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        opacity: textIn * fadeOut,
      }}
    >
      <div
        style={{
          fontSize: 52,
          fontWeight: 700,
          textAlign: "center",
          maxWidth: 1400,
          lineHeight: 1.4,
          scale,
          translate: `0 ${interpolate(frame, [0, 40], [20, 0], {
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.16, 1, 0.3, 1),
          })}px`,
        }}
      >
        <span style={{ color: CN_COLOR }}>中国</span>黄金储备
        <span style={{ color: "#fff", fontWeight: 400 }}> 十年增长 </span>
        <span
          style={{
            color: "#22c55e",
            fontSize: 72,
            fontWeight: 800,
            margin: "0 16px",
          }}
        >
          +115%
        </span>
        <span style={{ color: "#fff" }}></span>
      </div>
      <div
        style={{
          marginTop: 40,
          fontSize: 30,
          color: "rgba(255,255,255,0.5)",
          textAlign: "center",
        }}
      >
        美国保持 {formatNumber(8133.5)} 吨稳定储备
      </div>
      <div
        style={{
          marginTop: 80,
          fontSize: 24,
          color: "rgba(255,255,255,0.3)",
          textAlign: "center",
        }}
      >
        {VIDEO_DATA.source}
      </div>
    </AbsoluteFill>
  );
};

function formatNumber(v: number): string {
  return Math.round(v).toLocaleString();
}

export const AnimatedChart = () => {
  return (
    <AbsoluteFill style={{ background: BG }}>
      <Sequence from={0} durationInFrames={55}>
        <TitleCard />
      </Sequence>
      <Sequence from={55} durationInFrames={75}>
        <TrendChart />
      </Sequence>
      <Sequence from={130} durationInFrames={90}>
        <ComparisonChart />
      </Sequence>
      <Sequence from={220} durationInFrames={20}>
        <Conclusion />
      </Sequence>
    </AbsoluteFill>
  );
};

export const RemotionRoot = () => {
  return (
    <Composition
      id="Chart-8b56e5fe3e31"
      component={AnimatedChart}
      durationInFrames={DURATION}
      fps={FPS}
      width={1920}
      height={1080}
    />
  );
};

registerRoot(RemotionRoot);

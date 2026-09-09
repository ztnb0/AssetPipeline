export type TrendPoint = {
  year: number;
  china: number;
  us: number;
};

export type ComparisonItem = {
  label: string;
  value: number;
  color: string;
  delta?: string;
  caption?: string;
};

export const TREND_DATA: TrendPoint[] = [
  { year: 2014, china: 1054, us: 8133.5 },
  { year: 2015, china: 1434, us: 8133.5 },
  { year: 2016, china: 1553, us: 8133.5 },
  { year: 2017, china: 1698, us: 8133.5 },
  { year: 2018, china: 1862, us: 8133.5 },
  { year: 2019, china: 1947, us: 8133.5 },
  { year: 2020, china: 1950, us: 8133.5 },
  { year: 2021, china: 2006, us: 8133.5 },
  { year: 2022, china: 2113, us: 8133.5 },
  { year: 2023, china: 2235, us: 8133.5 },
  { year: 2024, china: 2264, us: 8133.5 },
];

export const COMPARISON_DATA: ComparisonItem[] = [
  {
    label: "美国",
    value: 8133.5,
    color: "#3b82f6",
    caption: "约 26,150 吨",
    delta: "稳定",
  },
  {
    label: "中国",
    value: 2264,
    color: "#ef4444",
    caption: "约 7,280 万盎司",
    delta: "+115%",
  },
];

export const VIDEO_DATA = {
  title: "中美黄金储备对比",
  subtitle: "2014 — 2024 · 中国数据由 AKShare 获取",
  source: "数据来源：World Gold Council / 中国人民银行 / AKShare",
  conclusion: "美国黄金储备长期稳定在 8,133 吨，过去十年中国黄金储备增长约 115%",
};

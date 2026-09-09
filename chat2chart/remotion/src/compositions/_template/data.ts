export type ChartDatum = {
  label: string;
  value: number;
};

export type ChartData = {
  title: string;
  subtitle: string;
  source: string;
  items: ChartDatum[];
};

export const DATA: ChartData = {
  title: "示例：对比各渠道转化率",
  subtitle: "单位：% · 口径：示例数据 · 时间范围：2026",
  source: "示例来源",
  items: [
    { label: "渠道 A", value: 82 },
    { label: "渠道 B", value: 64 },
    { label: "渠道 C", value: 47 },
    { label: "渠道 D", value: 35 },
  ],
};

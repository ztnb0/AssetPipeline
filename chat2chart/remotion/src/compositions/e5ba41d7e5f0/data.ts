export type SideDatum = {
  note: string;
  label: string;
  value: string;
};

export type ChartData = {
  title: string;
  subtitle: string;
  source: string;
  left: SideDatum;
  right: SideDatum;
};

export const DATA: ChartData = {
  title: "10% 首付 · 100% 增值",
  subtitle: "仅 10% 首付资金，撬动 100% 资产增值",
  source: "示意图 · 仅作教学用途",
  left: {
    note: "仅10%首付资金",
    label: "投入本金",
    value: "10万",
  },
  right: {
    note: "资产涨10万即翻倍",
    label: "净资产增值",
    value: "100%",
  },
};

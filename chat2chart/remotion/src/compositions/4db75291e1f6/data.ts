export type CompareItem = {
  label: string;
  value: string;
  note: string;
};

export type CompareData = {
  shortTitle: string;
  subtitle: string;
  left: CompareItem;
  right: CompareItem;
  conclusion: string;
  source: string;
};

export const DATA: CompareData = {
  shortTitle: "首付与收益对比",
  subtitle: "小本金撬动大增值 · 杠杆效应可视化",
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
  conclusion: "10%首付撬动100%资产增值",
  source: "示例测算，非投资建议",
};

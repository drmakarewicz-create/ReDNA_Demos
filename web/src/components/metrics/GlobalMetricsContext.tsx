import { createContext } from "react";

export type GlobalMetricsValue = {
  data: any;
  refresh: () => void;
} | null;

export const GlobalMetricsContext = createContext<GlobalMetricsValue>(null);

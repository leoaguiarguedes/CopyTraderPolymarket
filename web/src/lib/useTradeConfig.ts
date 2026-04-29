"use client";
import { useState, useEffect } from "react";

export type TradeConfig = {
  maxOpenPositions: number;
  capitalUsd: number;
  positionSizeUsd: number;
  maxHoldingHours: number;
};

export const TRADE_CONFIG_DEFAULTS: TradeConfig = {
  maxOpenPositions: 15,
  capitalUsd: 1000,
  positionSizeUsd: 20,
  maxHoldingHours: 4,
};

const STORAGE_KEY = "copytrader_config";

function _readFromStorage(): TradeConfig {
  try {
    if (typeof window === "undefined") return TRADE_CONFIG_DEFAULTS;
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return { ...TRADE_CONFIG_DEFAULTS, ...JSON.parse(raw) };
  } catch {}
  return TRADE_CONFIG_DEFAULTS;
}

export function useTradeConfig() {
  // Read localStorage synchronously on first render to avoid flash of default values
  const [config, setConfig] = useState<TradeConfig>(_readFromStorage);

  function save(next: TradeConfig) {
    setConfig(next);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch {}
  }

  return { config, save };
}

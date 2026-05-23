// Config types (Phase 10-B)

export interface SecretsStatus {
  openai: boolean;
  anthropic: boolean;
  gemini: boolean;
  finmind: boolean;
  google: boolean;
  deepseek: boolean;
}

export interface AiConfig {
  enabled: boolean;
  provider: string;
  model: string;
}

export interface UiConfig {
  theme: string;
  use_extras: boolean;
}

export interface AppConfig {
  ai: AiConfig;
  ui: UiConfig;
  risk: Record<string, unknown>;
  backtest: Record<string, unknown>;
  strategies: StrategyPresetConfig[];
}

export interface StrategyPresetConfig {
  name: string;
  type: string;
  params: Record<string, number | string | boolean>;
}

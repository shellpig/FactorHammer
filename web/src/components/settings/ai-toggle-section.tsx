"use client";

import { useState, useEffect, useRef } from "react";
import { useConfig, updateConfig, CONFIG_SWR_KEY } from "@/hooks/use-config";
import { useToast } from "@/hooks/use-toast";
import { mutate } from "swr";

const PROVIDERS = ["anthropic", "openai", "gemini", "deepseek"] as const;
type Provider = (typeof PROVIDERS)[number];

const DEFAULT_MODELS: Record<Provider, string> = {
  anthropic: "claude-haiku-4-5-20251001",
  openai: "gpt-4o-mini",
  gemini: "gemini-2.0-flash",
  deepseek: "deepseek-v4-flash",
};

export function AiToggleSection() {
  const { config, isLoading } = useConfig();
  const toast = useToast();
  const [enabled, setEnabled] = useState(false);
  const [provider, setProvider] = useState<Provider>("anthropic");
  const [model, setModel] = useState(DEFAULT_MODELS.anthropic);
  const [saving, setSaving] = useState(false);
  const isDirty = useRef(false);

  useEffect(() => {
    if (isLoading || isDirty.current) return;
    const ai = config?.ai;
    if (!ai) return;
    setEnabled(!!ai.enabled);
    const p = ai.provider as Provider;
    const validProvider = PROVIDERS.includes(p) ? p : "anthropic";
    setProvider(validProvider);
    setModel(ai.model || DEFAULT_MODELS[validProvider]);
  }, [config, isLoading]);

  function handleToggle() {
    isDirty.current = true;
    setEnabled((v) => !v);
  }

  function handleProviderChange(p: Provider) {
    isDirty.current = true;
    setProvider(p);
    setModel(DEFAULT_MODELS[p]);
  }

  function handleModelChange(m: string) {
    isDirty.current = true;
    setModel(m);
  }

  async function handleSave() {
    setSaving(true);
    try {
      await updateConfig({ ai: { enabled, provider, model } });
      await mutate(CONFIG_SWR_KEY);
      isDirty.current = false;
      toast.success("AI 設定已儲存");
    } catch {
      toast.error("儲存失敗，請稍後再試");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section aria-labelledby="ai-toggle-heading">
      <h2
        id="ai-toggle-heading"
        className="mb-4 text-lg font-semibold text-foreground"
      >
        AI 分析
      </h2>
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <span className="text-sm text-muted-foreground">AI 分析功能</span>
          <button
            data-testid="ai-toggle"
            role="switch"
            aria-checked={enabled}
            onClick={handleToggle}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
              enabled ? "bg-blue-600" : "bg-slate-700"
            }`}
          >
            <span
              className="inline-block h-4 w-4 rounded-full bg-white shadow transition-transform"
              style={{
                transform: enabled
                  ? "translateX(1.375rem)"
                  : "translateX(0.125rem)",
              }}
            />
          </button>
        </div>

        <div className="flex items-center gap-3">
          <label
            htmlFor="ai-provider-select"
            className="w-20 shrink-0 text-sm text-muted-foreground"
          >
            Provider
          </label>
          <select
            id="ai-provider-select"
            data-testid="ai-provider-select"
            value={provider}
            onChange={(e) => handleProviderChange(e.target.value as Provider)}
            disabled={!enabled}
            className="rounded border border-slate-700 bg-slate-800 px-3 py-1.5 text-sm text-slate-100 disabled:opacity-50"
          >
            {PROVIDERS.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-3">
          <label
            htmlFor="ai-model-input"
            className="w-20 shrink-0 text-sm text-muted-foreground"
          >
            Model
          </label>
          <input
            id="ai-model-input"
            data-testid="ai-model-input"
            type="text"
            value={model}
            onChange={(e) => handleModelChange(e.target.value)}
            disabled={!enabled}
            className="flex-1 rounded border border-slate-700 bg-slate-800 px-3 py-1.5 text-sm text-slate-100 disabled:opacity-50"
          />
        </div>

        <button
          data-testid="ai-save-btn"
          onClick={handleSave}
          disabled={saving}
          className="rounded bg-blue-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50"
        >
          {saving ? "儲存中…" : "儲存"}
        </button>
      </div>
    </section>
  );
}

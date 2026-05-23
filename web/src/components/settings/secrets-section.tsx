"use client";

import { useState } from "react";
import { useSecretsStatus, updateSecrets } from "@/hooks/use-config";
import { useToast } from "@/hooks/use-toast";

const PROVIDERS = [
  { key: "openai", label: "OpenAI API Key" },
  { key: "anthropic", label: "Anthropic API Key" },
  { key: "gemini", label: "Gemini API Key" },
  { key: "deepseek", label: "DeepSeek API Key" },
  { key: "finmind", label: "FinMind Token" },
  { key: "google", label: "Google API Key" },
] as const;

export function SecretsSection() {
  const { status, mutate } = useSecretsStatus();
  const toast = useToast();
  const [inputs, setInputs] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  async function handleSave() {
    const toUpdate = Object.fromEntries(
      Object.entries(inputs).filter(([, v]) => v.trim() !== ""),
    );
    if (Object.keys(toUpdate).length === 0) return;
    setSaving(true);
    try {
      await updateSecrets(toUpdate);
      setInputs({});
      await mutate();
      toast.success("API Key 已更新");
    } catch {
      toast.error("更新失敗，請稍後再試");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section aria-labelledby="secrets-heading">
      <h2
        id="secrets-heading"
        className="mb-4 text-lg font-semibold text-foreground"
      >
        API Key 管理
      </h2>
      <div className="space-y-3">
        {PROVIDERS.map(({ key, label }) => (
          <div key={key} className="flex items-center gap-3">
            <div className="w-44 shrink-0">
              <span className="text-sm text-muted-foreground">{label}</span>
              <span
                className={`ml-2 text-xs ${status[key] ? "text-green-400" : "text-slate-500"}`}
              >
                {status[key] ? "✓" : "未設定"}
              </span>
            </div>
            <input
              type="password"
              data-testid={`secret-input-${key}`}
              placeholder="輸入新 Key（留空表示不變）"
              value={inputs[key] ?? ""}
              onChange={(e) =>
                setInputs((prev) => ({ ...prev, [key]: e.target.value }))
              }
              className="flex-1 rounded border border-slate-700 bg-slate-800 px-3 py-1.5 text-sm text-slate-100 placeholder:text-slate-500"
            />
          </div>
        ))}
      </div>
      <button
        data-testid="secrets-save-btn"
        onClick={handleSave}
        disabled={saving}
        className="mt-4 rounded bg-blue-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50"
      >
        {saving ? "儲存中…" : "儲存"}
      </button>
    </section>
  );
}

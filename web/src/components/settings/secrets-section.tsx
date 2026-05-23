"use client";

import { useState } from "react";
import { useSecretsStatus } from "@/hooks/use-config";
import { useToast } from "@/hooks/use-toast";

// 15-A-2：移除 google（Google API Key 為 legacy，後續不讀不寫不顯示）
const PROVIDERS = [
  { key: "openai", label: "OpenAI API Key" },
  { key: "anthropic", label: "Anthropic API Key" },
  { key: "deepseek", label: "DeepSeek API Key" },
  { key: "gemini", label: "Gemini API Key" },
  { key: "finmind", label: "FinMind Token" },
] as const;

type ProviderKey = (typeof PROVIDERS)[number]["key"];

type ValidationStatus = "ok" | "invalid_key" | "no_quota" | "unreachable" | "skipped";
type ProviderResult = { status: ValidationStatus; message: string };

function ValidationBadge({ result }: { result: ProviderResult }) {
  if (result.status === "skipped") return null;
  const cfg = {
    ok: { icon: "✓", cls: "text-green-400" },
    no_quota: { icon: "⚠", cls: "text-yellow-400" },
    invalid_key: { icon: "✗", cls: "text-red-400" },
    unreachable: { icon: "✗", cls: "text-red-400" },
  }[result.status] ?? { icon: "?", cls: "text-slate-400" };

  return (
    <span className={`ml-2 text-xs ${cfg.cls}`} title={result.message}>
      {cfg.icon} {result.message}
    </span>
  );
}

export function SecretsSection() {
  const { status, mutate } = useSecretsStatus();
  const toast = useToast();
  const [inputs, setInputs] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [results, setResults] = useState<Record<string, ProviderResult>>({});

  async function handleValidateSave() {
    // Build payload — only include non-empty inputs
    const payload: Record<string, string> = {};
    for (const { key } of PROVIDERS) {
      const val = (inputs[key] ?? "").trim();
      if (val) payload[key] = val;
    }
    if (Object.keys(payload).length === 0) return;

    setSaving(true);
    setResults({});
    try {
      const resp = await fetch("/api/config/secrets/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const body = await resp.json();

      if (!resp.ok) {
        // Unexpected HTTP error (e.g. 500 ENV_WRITE_FAILED)
        const msg = body?.detail?.error?.message ?? "驗證失敗，請稍後再試";
        toast.error(msg);
        return;
      }

      const newResults: Record<string, ProviderResult> = body?.data?.results ?? {};
      setResults(newResults);

      const saved: string[] = body?.data?.saved ?? [];
      const failCount = Object.values(newResults).filter(
        (r) => r.status !== "ok" && r.status !== "no_quota",
      ).length;

      // FinMind failure → warn specifically
      const finmindResult = newResults["finmind"];
      if (finmindResult && finmindResult.status !== "ok" && finmindResult.status !== "no_quota") {
        toast.error(`FinMind 為必填，整包未儲存：${finmindResult.message}`);
        return;
      }

      if (saved.length > 0) {
        const msg =
          failCount > 0
            ? `${saved.length} 項已儲存、${failCount} 項失敗`
            : `${saved.length} 項已儲存`;
        toast.success(msg);
      } else {
        toast.error("未儲存任何 key，請確認 FinMind Token 正確");
      }

      setInputs({});
      await mutate();
    } catch {
      toast.error("驗證失敗，請確認網路連線後重試");
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
          <div key={key} className="flex flex-col gap-1">
            <div className="flex items-center gap-3">
              <div className="w-44 shrink-0">
                <span className="text-sm text-muted-foreground">{label}</span>
                {!results[key] && (
                  <span
                    className={`ml-2 text-xs ${status[key] ? "text-green-400" : "text-slate-500"}`}
                  >
                    {status[key] ? "✓" : "未設定"}
                  </span>
                )}
                {results[key] && <ValidationBadge result={results[key]} />}
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
          </div>
        ))}
      </div>
      <button
        data-testid="secrets-save-btn"
        onClick={handleValidateSave}
        disabled={saving}
        className="mt-4 rounded bg-blue-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50"
      >
        {saving ? "驗證中…" : "驗證並儲存"}
      </button>
    </section>
  );
}

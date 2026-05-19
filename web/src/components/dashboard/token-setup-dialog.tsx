"use client";

import { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { Eye, EyeOff, Loader2 } from "lucide-react";
import { ApiClientError, apiPost } from "@/lib/api-client";

type ValidateRequestBody = {
  finmind: string;
  anthropic?: string;
  openai?: string;
  gemini?: string;
};

export function TokenSetupDialog({
  open,
  onSaved,
}: {
  open: boolean;
  onSaved: () => void | Promise<void>;
}) {
  const [finmind, setFinmind] = useState("");
  const [anthropic, setAnthropic] = useState("");
  const [openai, setOpenai] = useState("");
  const [gemini, setGemini] = useState("");
  const [showFinmind, setShowFinmind] = useState(false);
  const [aiKeysExpanded, setAiKeysExpanded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const finmindToken = finmind.trim();
  const saveDisabled = saving || finmindToken === "";

  async function handleSave() {
    if (finmindToken === "") return;
    setSaving(true);
    setErrorMsg(null);

    const body: ValidateRequestBody = { finmind: finmindToken };
    if (anthropic.trim()) body.anthropic = anthropic.trim();
    if (openai.trim()) body.openai = openai.trim();
    if (gemini.trim()) body.gemini = gemini.trim();

    try {
      await apiPost<{ updated: boolean }>("/api/config/secrets/validate", body);
      await onSaved();
    } catch (error) {
      if (error instanceof ApiClientError) {
        if (error.code === "FINMIND_REQUIRED") {
          setErrorMsg("FinMind Token 為必填");
        } else if (error.code === "FINMIND_TOKEN_INVALID") {
          setErrorMsg("Token 無效，請確認從 FinMind 使用者資訊頁複製正確。");
        } else if (error.code === "FINMIND_UNREACHABLE") {
          setErrorMsg("無法連線至 FinMind 伺服器，請檢查網路後重試。");
        } else {
          setErrorMsg(error.message);
        }
      } else {
        setErrorMsg("儲存失敗，請稍後重試。");
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={() => undefined}>
      <Dialog.Portal>
        <Dialog.Overlay
          data-testid="token-setup-overlay"
          className="fixed inset-0 z-50 bg-black/70"
        />
        <Dialog.Content
          data-testid="token-setup-content"
          className="fixed left-1/2 top-1/2 z-50 w-[92vw] max-w-lg -translate-x-1/2 -translate-y-1/2 rounded-xl border border-slate-800 bg-slate-950 p-5 text-slate-100"
          onEscapeKeyDown={(event) => event.preventDefault()}
          onPointerDownOutside={(event) => event.preventDefault()}
        >
          <Dialog.Title className="text-base font-semibold">設定 API Token</Dialog.Title>
          <Dialog.Description className="mt-1 text-sm text-slate-300">
            在 FinMind 官網註冊並登入後，於使用者資訊頁複製 API Token。
          </Dialog.Description>

          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
            <a
              href="https://finmindtrade.com/analysis/#/data/api"
              target="_blank"
              rel="noopener noreferrer"
              className="text-sky-400 hover:text-sky-300"
            >
              FinMind 官網
            </a>
            <a
              href="https://finmindtrade.com/analysis/#/account/user"
              target="_blank"
              rel="noopener noreferrer"
              className="text-sky-400 hover:text-sky-300"
            >
              取得 API Token
            </a>
          </div>

          <div className="mt-4 space-y-3">
            <label className="block space-y-1">
              <span className="text-sm text-slate-200">FinMind Token</span>
              <div className="flex items-center gap-2">
                <input
                  aria-label="FinMind Token"
                  type={showFinmind ? "text" : "password"}
                  value={finmind}
                  onChange={(event) => setFinmind(event.target.value)}
                  disabled={saving}
                  className="flex-1 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 disabled:opacity-70"
                  placeholder="貼上 FinMind API Token"
                />
                <button
                  type="button"
                  aria-label={showFinmind ? "隱藏 FinMind Token" : "顯示 FinMind Token"}
                  onClick={() => setShowFinmind((prev) => !prev)}
                  disabled={saving}
                  className="rounded-lg border border-slate-700 px-2 py-2 text-slate-300 hover:bg-slate-800 disabled:opacity-70"
                >
                  {showFinmind ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </label>

            <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-3">
              <button
                type="button"
                onClick={() => setAiKeysExpanded((prev) => !prev)}
                disabled={saving}
                className="text-sm text-slate-200 hover:text-slate-100 disabled:opacity-70"
              >
                AI API Keys（選填）
              </button>

              {aiKeysExpanded ? (
                <div className="mt-3 space-y-2">
                  <label className="block space-y-1">
                    <span className="text-xs text-slate-400">Anthropic API Key</span>
                    <input
                      aria-label="Anthropic API Key"
                      type="password"
                      value={anthropic}
                      onChange={(event) => setAnthropic(event.target.value)}
                      disabled={saving}
                      className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 disabled:opacity-70"
                      placeholder="留空代表不更新"
                    />
                  </label>
                  <label className="block space-y-1">
                    <span className="text-xs text-slate-400">OpenAI API Key</span>
                    <input
                      aria-label="OpenAI API Key"
                      type="password"
                      value={openai}
                      onChange={(event) => setOpenai(event.target.value)}
                      disabled={saving}
                      className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 disabled:opacity-70"
                      placeholder="留空代表不更新"
                    />
                  </label>
                  <label className="block space-y-1">
                    <span className="text-xs text-slate-400">Gemini API Key</span>
                    <input
                      aria-label="Gemini API Key"
                      type="password"
                      value={gemini}
                      onChange={(event) => setGemini(event.target.value)}
                      disabled={saving}
                      className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 disabled:opacity-70"
                      placeholder="留空代表不更新"
                    />
                  </label>
                </div>
              ) : null}
            </div>

            {errorMsg ? <p className="text-sm text-red-300">{errorMsg}</p> : null}
          </div>

          <div className="mt-4 flex justify-end">
            <button
              type="button"
              onClick={() => void handleSave()}
              disabled={saveDisabled}
              className="rounded-lg bg-slate-200 px-4 py-2 text-sm font-medium text-slate-900 hover:bg-white disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
            >
              {saving ? (
                <span className="inline-flex items-center gap-1.5">
                  <Loader2
                    data-testid="token-setup-saving-spinner"
                    className="h-4 w-4 animate-spin"
                  />
                  儲存中...
                </span>
              ) : (
                "儲存並繼續"
              )}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

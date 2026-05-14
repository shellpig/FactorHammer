"use client";

// Single-step delete confirmation dialog (Phase 10-C-1)

import * as Dialog from "@radix-ui/react-dialog";
import { AlertTriangle, Trash2, X } from "lucide-react";
import type { SymbolRow } from "@/types/data";

interface DeleteConfirmDialogProps {
  open: boolean;
  row: SymbolRow | null;
  onClose: () => void;
  onConfirm: () => void;
  isDeleting?: boolean;
}

export function DeleteConfirmDialog({
  open,
  row,
  onClose,
  onConfirm,
  isDeleting = false,
}: DeleteConfirmDialogProps) {
  const symbol = row?.symbol ?? "";
  const marketLabel = row?.market === "us" ? "美股" : "台股";

  return (
    <Dialog.Root open={open} onOpenChange={(o) => !o && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-slate-950/70 backdrop-blur-sm" />
        <Dialog.Content
          data-testid="delete-dialog"
          className="fixed left-1/2 top-1/2 z-50 w-[480px] -translate-x-1/2 -translate-y-1/2 rounded-xl border border-slate-800 bg-slate-900 p-6 shadow-2xl"
        >
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-3">
              <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-rose-500/15">
                <AlertTriangle className="h-5 w-5 text-rose-500" />
              </div>
              <div>
                <Dialog.Title className="text-base font-semibold text-slate-100">
                  確認刪除{" "}
                  <code className="font-mono text-[15px]">{symbol}</code>{" "}
                  本機快取
                </Dialog.Title>
                <Dialog.Description className="mt-1.5 text-[13px] leading-relaxed text-slate-300">
                  此動作將刪除「{marketLabel} ·{" "}
                  <code className="font-mono">{symbol}</code>
                  」的原始與調整後資料。可隨時重新下載；歷史快取無法復原。
                </Dialog.Description>
              </div>
            </div>
            <Dialog.Close
              data-testid="delete-dialog-close"
              disabled={isDeleting}
              className="-mr-1 -mt-1 rounded-md p-1 text-slate-500 hover:text-slate-300 disabled:opacity-40"
            >
              <X className="h-4 w-4" />
            </Dialog.Close>
          </div>

          <div className="mt-6 flex items-center justify-end gap-2 border-t border-slate-800 pt-4">
            <button
              data-testid="delete-dialog-cancel"
              onClick={onClose}
              disabled={isDeleting}
              className="h-9 rounded-md border border-slate-700/80 bg-slate-900/40 px-4 text-sm text-slate-200 hover:bg-slate-800/60 disabled:opacity-50"
            >
              取消
            </button>
            <button
              data-testid="delete-dialog-confirm"
              onClick={onConfirm}
              disabled={isDeleting}
              className="inline-flex h-9 items-center gap-1.5 rounded-md bg-rose-600 px-4 text-sm font-medium text-white hover:bg-rose-500 disabled:bg-rose-900/40 disabled:text-rose-300/40"
            >
              <Trash2 className="h-3.5 w-3.5" />
              {isDeleting ? "刪除中…" : "確認刪除"}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

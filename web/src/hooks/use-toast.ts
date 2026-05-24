"use client";

import { toast } from "sonner";

const DEFAULT_DURATION = 3000;

export type ToastApi = {
  success: (message: string, opts?: { duration?: number }) => void;
  error: (message: string, opts?: { duration?: number }) => void;
  warning: (message: string, opts?: { duration?: number }) => void;
  info: (message: string, opts?: { duration?: number }) => void;
  dismiss: (id?: string | number) => void;
};

export function useToast(): ToastApi {
  return {
    success: (message, opts) =>
      toast.success(message, { duration: opts?.duration ?? DEFAULT_DURATION }),
    error: (message, opts) =>
      toast.error(message, { duration: opts?.duration ?? DEFAULT_DURATION }),
    warning: (message, opts) =>
      toast.warning(message, { duration: opts?.duration ?? DEFAULT_DURATION }),
    info: (message, opts) =>
      toast.info(message, { duration: opts?.duration ?? DEFAULT_DURATION }),
    dismiss: (id) => toast.dismiss(id),
  };
}

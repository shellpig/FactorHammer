// SWR-free hook for managing a data update/rebuild job with SSE streaming (Phase 10-C-2)

import { useCallback, useRef, useState } from "react";
import { apiFetch } from "@/lib/api-client";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

export type DataJobStatus = "idle" | "running" | "complete" | "error";

export interface DataJobState {
  status: DataJobStatus;
  current: number;
  total: number;
  currentSymbol: string;
  succeeded: string[];
  failed: Array<{ symbol: string; error: string }>;
  warnings: Array<{ symbol: string; message: string }>;
  errors: Array<{ symbol: string; message: string }>;
  errorMsg: string | null;
}

const IDLE_STATE: DataJobState = {
  status: "idle",
  current: 0,
  total: 0,
  currentSymbol: "",
  succeeded: [],
  failed: [],
  warnings: [],
  errors: [],
  errorMsg: null,
};

export function useDataJob(onComplete?: () => void) {
  const [state, setState] = useState<DataJobState>(IDLE_STATE);
  const esRef = useRef<EventSource | null>(null);

  const startJob = useCallback(
    async (type: string, params: Record<string, unknown>) => {
      // Close any prior stream
      esRef.current?.close();
      esRef.current = null;

      setState({ ...IDLE_STATE, status: "running" });

      try {
        const resp = await apiFetch<{ job_id: string }>("/api/jobs", {
          method: "POST",
          body: JSON.stringify({ type, params }),
        });

        const jobId = resp.job_id;
        const es = new EventSource(`${BASE_URL}/api/jobs/${jobId}/events`);
        esRef.current = es;

        es.addEventListener("progress", (e: MessageEvent) => {
          const data = JSON.parse(e.data) as {
            current: number;
            total: number;
            current_symbol: string;
            status: string;
            error?: string;
          };
          setState((prev) => ({
            ...prev,
            current: data.current,
            total: data.total,
            currentSymbol: data.current_symbol,
          }));
        });

        es.addEventListener("result", (e: MessageEvent) => {
          const data = JSON.parse(e.data) as {
            succeeded: string[];
            failed: Array<{ symbol: string; error: string }>;
            warnings?: Array<{ symbol: string; message: string }>;
            errors?: Array<{ symbol: string; message: string }>;
          };
          setState((prev) => ({
            ...prev,
            status: "complete",
            succeeded: data.succeeded,
            failed: data.failed,
            warnings: data.warnings ?? [],
            errors: data.errors ?? [],
          }));
          es.close();
          esRef.current = null;
          onComplete?.();
        });

        es.onerror = () => {
          setState((prev) => ({
            ...prev,
            status: "error",
            errorMsg: "連線中斷，請檢查後端服務",
          }));
          es.close();
          esRef.current = null;
        };
      } catch (e) {
        setState({
          ...IDLE_STATE,
          status: "error",
          errorMsg: e instanceof Error ? e.message : "操作失敗",
        });
      }
    },
    [onComplete],
  );

  const resetJob = useCallback(() => {
    esRef.current?.close();
    esRef.current = null;
    setState(IDLE_STATE);
  }, []);

  return { ...state, startJob, resetJob };
}

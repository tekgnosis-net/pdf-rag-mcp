import { useCallback, useEffect, useMemo, useState } from "react";
import axios from "axios";

export type JobStatus = "queued" | "processing" | "completed" | "failed";

export interface ProcessingJob {
  id: string;
  filename: string;
  status: JobStatus;
  progress: number;
  queuedAt?: string;
  updatedAt?: string;
  error?: string;
  documentId?: number;
  title?: string;
}

export interface QueueState {
  queue: ProcessingJob[];
  inProgress: ProcessingJob[];
  completed: ProcessingJob[];
  failed: ProcessingJob[];
}

const initialState: QueueState = {
  queue: [],
  inProgress: [],
  completed: [],
  failed: []
};

interface UseProcessingQueueResult extends QueueState {
  isUploading: boolean;
  error: string | null;
  enqueueFiles: (files: FileList | File[]) => Promise<void>;
  refresh: () => Promise<void>;
}

const normalizeJob = (candidate: Partial<ProcessingJob>): ProcessingJob => ({
  id: candidate.id ?? crypto.randomUUID(),
  filename: candidate.filename ?? candidate.title ?? "unknown.pdf",
  status: candidate.status ?? "queued",
  progress: candidate.progress ?? 0,
  queuedAt: candidate.queuedAt,
  updatedAt: candidate.updatedAt,
  error: candidate.error,
  documentId: candidate.documentId,
  title: candidate.title
});

export const useProcessingQueue = (): UseProcessingQueueResult => {
  const [state, setState] = useState<QueueState>(initialState);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const { data } = await axios.get("/api/process/status");
      const queue = (data.queue ?? []).map(normalizeJob);
      const inProgress = (data.in_progress ?? []).map(normalizeJob);
      const completed = (data.completed ?? []).map(normalizeJob);
      const failed = (data.failed ?? []).map(normalizeJob);
      setState({ queue, inProgress, completed, failed });
      setError(null);
    } catch (err) {
      if (!state.queue.length && !state.inProgress.length && !state.completed.length && !state.failed.length) {
        setError("Waiting for backend status endpoint...");
      }
    }
  }, [state.completed.length, state.failed.length, state.inProgress.length, state.queue.length]);

  useEffect(() => {
    void refresh();
    const interval = window.setInterval(() => {
      void refresh();
    }, 3500);
    return () => window.clearInterval(interval);
  }, [refresh]);

  const enqueueFiles = useCallback(
    async (files: FileList | File[]) => {
      const fileArray = Array.from(files);
      if (!fileArray.length) {
        return;
      }
      const formData = new FormData();
      fileArray.forEach((file) => {
        formData.append("files", file, file.name);
      });

      setIsUploading(true);
      try {
        const { data } = await axios.post("/api/process", formData, {
          headers: { "Content-Type": "multipart/form-data" }
        });
        const queue = (data.jobs ?? fileArray.map((file) => ({ filename: file.name }))).map(normalizeJob);
  setState((prev: QueueState): QueueState => ({
          queue: [...queue, ...prev.queue],
          inProgress: prev.inProgress,
          completed: prev.completed,
          failed: prev.failed
        }));
        setError(null);
      } catch (err) {
        setError("Failed to enqueue files. Please check the backend logs.");
      } finally {
        setIsUploading(false);
      }
    },
    []
  );

  return useMemo(
    () => ({
      queue: state.queue,
      inProgress: state.inProgress,
      completed: state.completed,
      failed: state.failed,
      isUploading,
      error,
      enqueueFiles,
      refresh
    }),
    [state, isUploading, error, enqueueFiles, refresh]
  );
};

/**
 * useTaskPolling - 任務輪詢 Hook
 * 
 * 統一處理任務執行與狀態輪詢，包括：
 * - 自動輪詢 job 狀態
 * - 處理 success/failed/cancelled 三種終止狀態
 * - 檢查 result.status 是否為 error
 * - 提供 loading/statusMsg/statusType 等 UI 狀態
 */
import { useState, useEffect, useCallback } from 'react';
import { tasksApi } from '../api/tasks';
import type { Job, JobResult } from '../api/tasks';

// Re-export for backward compatibility
export type { JobResult };

// JobData 是 Job 的簡化版本，用於 hook 內部狀態
export type JobData = Pick<Job, 'id' | 'status' | 'progress' | 'result' | 'error'>;

export interface UseTaskPollingOptions {
    /** 輪詢間隔 (預設 1500ms) */
    pollInterval?: number;
    /** 成功時的回調 */
    onSuccess?: (result: JobResult) => void;
    /** 失敗時的回調 */
    onError?: (error: string) => void;
    /** 取消時的回調 */
    onCancelled?: () => void;
}

export interface UseTaskPollingReturn {
    /** 是否正在執行任務 */
    loading: boolean;
    /** 當前進度 (0-100) */
    progress: number | undefined;
    /** 當前 job 狀態 */
    jobStatus: JobData | null;
    /** 狀態訊息 (用於 UI 顯示) */
    statusMsg: string | null;
    /** 狀態類型 (info/success/error) */
    statusType: 'info' | 'success' | 'error';
    /** Google Sheets 連結 (若有) */
    sheetUrl: string | null;
    /** 執行任務 */
    runTask: (taskId: string, params?: Record<string, any>) => Promise<string | null>;
    /** 重置狀態 */
    reset: () => void;
}

export function useTaskPolling(options: UseTaskPollingOptions = {}): UseTaskPollingReturn {
    const { pollInterval = 1500, onSuccess, onError, onCancelled } = options;

    const [loading, setLoading] = useState(false);
    const [jobId, setJobId] = useState<string | null>(null);
    const [jobStatus, setJobStatus] = useState<JobData | null>(null);
    const [statusMsg, setStatusMsg] = useState<string | null>(null);
    const [statusType, setStatusType] = useState<'info' | 'success' | 'error'>('info');
    const [sheetUrl, setSheetUrl] = useState<string | null>(null);

    // 輪詢 Job 狀態
    useEffect(() => {
        if (!jobId) return;

        const interval = setInterval(async () => {
            try {
                const data = await tasksApi.getJob(jobId) as JobData;
                setJobStatus(data);
                // 📌 通知 BackgroundTasksIndicator 同步更新
                window.dispatchEvent(new CustomEvent('job-updated'));

                if (data.status === 'success') {
                    setLoading(false);
                    clearInterval(interval);

                    const result = data.result;

                    // 📌 重要：檢查 result.status 是否為 error
                    if (result?.status === 'error') {
                        const errorMsg = result?.details?.join(', ') || '執行失敗';
                        setStatusMsg(errorMsg);
                        setStatusType('error');
                        onError?.(errorMsg);
                    } else {
                        const msg = result?.message ||
                            (result?.updated_cells !== undefined
                                ? `執行成功，已更新 ${result.updated_cells} 個儲存格`
                                : '執行成功');
                        setStatusMsg(msg);
                        setSheetUrl(result?.sheet_url || null);
                        setStatusType('success');
                        onSuccess?.(result || {});
                    }
                } else if (data.status === 'failed') {
                    setLoading(false);
                    clearInterval(interval);
                    const errorMsg = data.error || '執行失敗';
                    setStatusMsg(errorMsg);
                    setStatusType('error');
                    onError?.(errorMsg);
                } else if (data.status === 'cancelled') {
                    setLoading(false);
                    clearInterval(interval);
                    setStatusMsg('任務已取消');
                    setStatusType('info');
                    onCancelled?.();
                }
            } catch (e) {
                console.error('Failed to poll job status:', e);
            }
        }, pollInterval);

        return () => clearInterval(interval);
    }, [jobId, pollInterval, onSuccess, onError, onCancelled]);

    // 執行任務
    const runTask = useCallback(async (taskId: string, params?: Record<string, any>): Promise<string | null> => {
        setLoading(true);
        setStatusMsg(null);
        setJobStatus(null);
        setSheetUrl(null);
        setStatusType('info');

        const eipId = localStorage.getItem('eip_id');
        const eipPsw = localStorage.getItem('eip_psw');

        try {
            const { job_id } = await tasksApi.run(taskId, {
                params: params || {},
                eip_id: eipId || undefined,
                eip_psw: eipPsw || undefined
            });
            setJobId(job_id);
            setStatusMsg('任務執行中...');
            // 📌 通知 BackgroundTasksIndicator 立即更新
            window.dispatchEvent(new CustomEvent('task-started'));
            return job_id;
        } catch (e: any) {
            setLoading(false);
            const errorMsg = e.message || '執行失敗';
            setStatusMsg(errorMsg);
            setStatusType('error');
            onError?.(errorMsg);
            return null;
        }
    }, [onError]);

    // 重置狀態
    const reset = useCallback(() => {
        setLoading(false);
        setJobId(null);
        setJobStatus(null);
        setStatusMsg(null);
        setStatusType('info');
        setSheetUrl(null);
    }, []);

    return {
        loading,
        progress: jobStatus?.progress,
        jobStatus,
        statusMsg,
        statusType,
        sheetUrl,
        runTask,
        reset
    };
}

// =============================================================================
// 📌 pollJobResult - 同步等待任務結果
// =============================================================================
// 用於多步驟流程 (如 IviPage, SurgeryPage)，需要等待結果後再繼續執行
// 與 useTaskPolling 的差異：
// - useTaskPolling: 背景輪詢，更新 UI 狀態
// - pollJobResult: 同步等待，返回結果後繼續執行

export interface PollJobOptions {
    /** 最大輪詢次數 (預設 180，約 3 分鐘) */
    maxAttempts?: number;
    /** 輪詢間隔 ms (預設 1000) */
    intervalMs?: number;
    /** 進度回調 (每次輪詢時呼叫) */
    onProgress?: (progress: number, message?: string) => void;
    /** 靜默模式：不派發 job-updated 事件到 BackgroundTasksIndicator */
    silent?: boolean;
}

/**
 * 同步等待任務完成並返回結果
 * 
 * @example
 * const { job_id } = await tasksApi.run('my_task', { ... });
 * const result = await pollJobResult(job_id, {
 *     onProgress: (p, msg) => setProgress(p),
 *     silent: true // 不顯示在背景任務指示器
 * });
 * // 處理結果...
 */
export async function pollJobResult<T = any>(
    jobId: string,
    options: PollJobOptions = {}
): Promise<T> {
    const { maxAttempts = 180, intervalMs = 1000, onProgress, silent = false } = options;

    for (let i = 0; i < maxAttempts; i++) {
        await new Promise(r => setTimeout(r, intervalMs));
        const jobData = await tasksApi.getJob(jobId);

        // 回報進度
        if (onProgress && jobData.progress !== undefined) {
            onProgress(jobData.progress, (jobData as any).status_message);
        }

        // 通知 BackgroundTasksIndicator 同步更新 (除非 silent mode)
        if (!silent) {
            window.dispatchEvent(new CustomEvent('job-updated'));
        }

        if (jobData.status === 'success') {
            // 檢查 result.status 是否為 error
            if (jobData.result?.status === 'error') {
                const errorMsg = jobData.result?.details?.join(', ') || '執行失敗';
                throw new Error(errorMsg);
            }
            return jobData.result as T;
        }
        if (jobData.status === 'failed') {
            throw new Error(jobData.error || '執行失敗');
        }
        if (jobData.status === 'cancelled') {
            throw new Error('任務已取消');
        }
    }
    throw new Error('任務超時');
}

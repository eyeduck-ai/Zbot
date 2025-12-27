/**
 * Tasks API - 任務相關 API 封裝
 * 
 * 功能：
 * - 執行任務 (runTask)
 * - 查詢任務狀態 (getJob)
 * - 列出所有任務 (listJobs)
 * - 取消任務 (cancelJob)
 */

import { apiClient } from './client';

// =============================================================================
// Types
// =============================================================================

/** 任務定義 */
export interface CrawlerTask {
    id: string;
    name: string;
    description: string;
    params_schema: Record<string, unknown>;
    allowed: boolean;
}

/** 執行任務請求 */
export interface RunTaskRequest {
    params: Record<string, unknown>;
    eip_id?: string;
    eip_psw?: string;
}

/** 執行任務回應 */
export interface RunTaskResponse {
    job_id: string;
    status: string;
}

/** Job 狀態 */
export type JobStatus = 'pending' | 'running' | 'success' | 'failed' | 'cancelled';

/** Job 詳細資訊 */
export interface Job {
    id: string;
    crawler_id?: string;        // 可選（向後相容）
    task_id?: string;           // 任務 ID
    task_type?: string;         // 任務類型
    status: JobStatus;
    progress?: number;
    error?: string;
    result?: JobResult;
    created_at: string;
    completed_at?: string;      // 完成時間（別名）
    finished_at?: string;       // 完成時間
    cancelled?: boolean;        // 是否已取消
}

/** Job 結果 (各任務可能有不同格式) */
export interface JobResult {
    status?: string;
    message?: string;
    sheet_url?: string;
    updated_rows?: number;
    updated_cells?: number;
    total?: number;
    success?: number;
    failed?: number;
    details?: string[];
    [key: string]: unknown;
}

// =============================================================================
// API Functions
// =============================================================================

export const tasksApi = {
    /**
     * 列出所有可用任務
     */
    list: async (): Promise<CrawlerTask[]> => {
        return apiClient.get<CrawlerTask[]>('/api/tasks');
    },

    /**
     * 執行任務
     * @param taskId 任務 ID
     * @param payload 執行參數
     */
    run: async (taskId: string, payload: RunTaskRequest): Promise<RunTaskResponse> => {
        return apiClient.post<RunTaskResponse>(`/api/tasks/${taskId}/run`, payload);
    },

    /**
     * 查詢 Job 狀態
     * @param jobId Job ID
     */
    getJob: async (jobId: string): Promise<Job> => {
        return apiClient.get<Job>(`/api/tasks/jobs/${jobId}`);
    },

    /**
     * 列出最近的 Jobs
     * @param limit 數量限制
     */
    listJobs: async (limit: number = 10): Promise<Job[]> => {
        // 後端回傳 { jobs: [...], count: N }，需解構取出 jobs
        const response = await apiClient.get<{ jobs: Job[]; count: number }>(`/api/tasks/jobs?limit=${limit}`);
        return response.jobs || [];
    },

    /**
     * 取消 Job
     * @param jobId Job ID
     */
    cancelJob: async (jobId: string): Promise<{ success: boolean; message?: string }> => {
        return apiClient.post<{ success: boolean; message?: string }>(`/api/tasks/jobs/${jobId}/cancel`);
    },
};

// =============================================================================
// Helper Functions
// =============================================================================

/**
 * 輪詢 Job 狀態直到完成
 * @param jobId Job ID
 * @param onProgress 進度回呼
 * @param intervalMs 輪詢間隔 (毫秒)
 * @param timeoutMs 超時時間 (毫秒)
 */
export const pollJobUntilDone = async (
    jobId: string,
    onProgress?: (job: Job) => void,
    intervalMs: number = 1500,
    timeoutMs: number = 300000
): Promise<Job> => {
    const startTime = Date.now();

    while (true) {
        const job = await tasksApi.getJob(jobId);

        if (onProgress) {
            onProgress(job);
        }

        if (job.status === 'success' || job.status === 'failed' || job.status === 'cancelled') {
            return job;
        }

        if (Date.now() - startTime > timeoutMs) {
            throw new Error('Job polling timeout');
        }

        await new Promise(resolve => setTimeout(resolve, intervalMs));
    }
};

// =============================================================================
// Lookup API (查詢服務)
// =============================================================================

/**
 * 根據醫師登號查詢姓名
 * @param code 4位數字的醫師登號 (例如 "4102")
 * @returns 醫師姓名，若查詢失敗則返回空字串
 */
export const lookupDoctorName = async (code: string): Promise<string> => {
    if (!/^\d{4}$/.test(code)) return '';

    // 取得 EIP 憑證
    const eipId = localStorage.getItem('user');
    const eipPsw = localStorage.getItem('eip_psw');

    if (!eipId || !eipPsw) return '';

    try {
        const token = localStorage.getItem('token');
        const res = await fetch(`/api/lookup/doctor-name/${code}`, {
            method: 'GET',
            headers: {
                'Authorization': token ? `Bearer ${token}` : '',
                'X-Eip-Id': eipId,
                'X-Eip-Psw': eipPsw,
            },
        });

        if (!res.ok) return '';

        const data = await res.json();
        return data.name || '';
    } catch {
        return '';
    }
};

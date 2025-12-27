/**
 * API Client - 統一的 HTTP 請求封裝
 * 
 * 功能：
 * - 自動附加 Authorization header (Bearer token)
 * - 統一錯誤處理
 * - 支援 GET, POST, DELETE 方法
 * 
 * 使用方式：
 * ```ts
 * import { apiClient } from '@/api/client';
 * 
 * // GET 請求
 * const data = await apiClient.get<MyType>('/api/endpoint');
 * 
 * // POST 請求
 * const result = await apiClient.post<MyResult>('/api/endpoint', { key: 'value' });
 * ```
 */

/**
 * 取得認證 Token
 */
const getAuthToken = (): string | null => {
    return localStorage.getItem('token');
};

/**
 * 建立請求 Headers
 */
const createHeaders = (isJson: boolean = false): Record<string, string> => {
    const headers: Record<string, string> = {};
    const token = getAuthToken();

    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    if (isJson) {
        headers['Content-Type'] = 'application/json';
    }

    return headers;
};

/**
 * 處理 Response 錯誤
 */
const handleResponseError = async (res: Response): Promise<never> => {
    let errorMessage = `HTTP ${res.status}`;

    try {
        const errorData = await res.json();
        errorMessage = errorData.detail || errorData.message || errorMessage;
    } catch {
        // 無法解析 JSON，使用預設錯誤訊息
    }

    // 401 未授權 - 可在此處理自動登出
    if (res.status === 401) {
        console.warn('[API Client] Unauthorized - token may be expired');
        // 可選：觸發登出事件
        // window.dispatchEvent(new CustomEvent('auth:logout'));
    }

    throw new Error(errorMessage);
};

/**
 * API Client 物件
 */
export const apiClient = {
    /**
     * GET 請求
     */
    get: async <T>(path: string): Promise<T> => {
        const res = await fetch(path, {
            method: 'GET',
            headers: createHeaders(),
        });

        if (!res.ok) {
            await handleResponseError(res);
        }

        return res.json();
    },

    /**
     * POST 請求
     */
    post: async <T>(path: string, body?: unknown): Promise<T> => {
        const isFormData = body instanceof FormData;
        const res = await fetch(path, {
            method: 'POST',
            headers: createHeaders(!isFormData),
            body: isFormData ? (body as BodyInit) : (body ? JSON.stringify(body) : undefined),
        });

        if (!res.ok) {
            await handleResponseError(res);
        }

        return res.json();
    },

    /**
     * DELETE 請求
     */
    delete: async <T>(path: string): Promise<T> => {
        const res = await fetch(path, {
            method: 'DELETE',
            headers: createHeaders(),
        });

        if (!res.ok) {
            await handleResponseError(res);
        }

        return res.json();
    },

    /**
     * PUT 請求
     */
    put: async <T>(path: string, body?: unknown): Promise<T> => {
        const isFormData = body instanceof FormData;
        const res = await fetch(path, {
            method: 'PUT',
            headers: createHeaders(!isFormData),
            body: isFormData ? (body as BodyInit) : (body ? JSON.stringify(body) : undefined),
        });

        if (!res.ok) {
            await handleResponseError(res);
        }

        return res.json();
    },
};

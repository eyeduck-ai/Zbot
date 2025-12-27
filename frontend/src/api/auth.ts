/**
 * Auth API - 認證相關 API 封裝
 * 
 * 功能：
 * - 登入 (login)
 * - 檢查系統狀態 (checkStatus)
 * - Google Sheets 設定 (getGSheetStatus, updateGSheetSettings)
 */

import { apiClient } from './client';

// =============================================================================
// Types
// =============================================================================

/** 登入請求 */
export interface LoginRequest {
    username: string;
    password: string;
}

/** 登入回應 */
export interface LoginResponse {
    access_token: string;
    token_type: string;
    user: {
        id: string;
        username: string;
        role: string;
    };
}

/** 系統狀態 */
export interface SystemStatus {
    status: string;
    eip?: string;
    supabase?: string;
}

/** GSheet 狀態 */
export interface GSheetStatus {
    configured: boolean;
    sheet_id?: string;
    worksheet?: string;
    status?: 'connected' | 'error' | 'not_configured';
    message?: string;
}

/** GSheet 設定 */
export interface GSheetSettings {
    sheet_id: string;
    worksheet: string;
}

// =============================================================================
// API Functions
// =============================================================================

export const authApi = {
    /**
     * 登入
     */
    login: async (credentials: LoginRequest): Promise<LoginResponse> => {
        // 登入 API 不需要 token，直接使用 fetch
        const res = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(credentials),
        });

        if (!res.ok) {
            const error = await res.json().catch(() => ({}));
            throw new Error(error.detail || `登入失敗 (HTTP ${res.status})`);
        }

        return res.json();
    },

    /**
     * 檢查系統狀態 (不需認證)
     */
    checkStatus: async (): Promise<SystemStatus> => {
        const res = await fetch('/api/status');

        if (!res.ok) {
            throw new Error('無法連線至伺服器');
        }

        return res.json();
    },

    /**
     * 取得 GSheet 連線狀態
     */
    getGSheetStatus: async (): Promise<GSheetStatus> => {
        return apiClient.get<GSheetStatus>('/api/auth/me/gsheet-status');
    },

    /**
     * 更新 GSheet 設定
     */
    updateGSheetSettings: async (settings: GSheetSettings): Promise<{ success: boolean; message?: string }> => {
        return apiClient.post<{ success: boolean; message?: string }>('/api/auth/me/gsheet-settings', settings);
    },

    /**
     * 取得當前使用者資訊
     */
    getCurrentUser: async (): Promise<LoginResponse['user']> => {
        return apiClient.get<LoginResponse['user']>('/api/auth/me');
    },
};

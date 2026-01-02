/**
 * CacheCheckDialog - 快取檢查對話框
 * 
 * 當使用者執行統計任務前，若有未上傳的快取，顯示此對話框讓使用者選擇：
 * 1. 重新上傳 - 使用快取資料嘗試上傳
 * 2. 忽略並重新爬取 - 捨棄快取，重新執行任務
 */
import React, { useState } from 'react';
import { Upload, RefreshCw, Loader2, AlertTriangle } from 'lucide-react';
import { Button } from './ui/Button';
import { TASK_NAMES } from '../constants/taskNames';

// =============================================================================
// Types
// =============================================================================

export interface CacheInfo {
    id: string;
    task_id: string;
    created_at: string;
}

export interface CacheCheckDialogProps {
    cache: CacheInfo;
    /** 點擊重新上傳時的回調 */
    onRetry: () => Promise<void>;
    /** 點擊忽略並重新爬取時的回調 */
    onIgnore: () => void;
    /** 點擊取消時的回調 */
    onCancel: () => void;
}

// =============================================================================
// Component
// =============================================================================

export const CacheCheckDialog: React.FC<CacheCheckDialogProps> = ({
    cache,
    onRetry,
    onIgnore,
    onCancel,
}) => {
    const [isRetrying, setIsRetrying] = useState(false);

    const handleRetry = async () => {
        setIsRetrying(true);
        try {
            await onRetry();
        } finally {
            setIsRetrying(false);
        }
    };

    // 格式化日期時間
    const formatDateTime = (dateStr: string) => {
        const date = new Date(dateStr);
        return date.toLocaleString('zh-TW', {
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
        });
    };

    return (
        <>
            {/* 背景遮罩 */}
            <div
                style={{
                    position: 'fixed',
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    backgroundColor: 'rgba(0, 0, 0, 0.5)',
                    backdropFilter: 'blur(4px)',
                    zIndex: 9998,
                }}
                onClick={onCancel}
            />

            {/* 對話框 */}
            <div
                style={{
                    position: 'fixed',
                    top: '50%',
                    left: '50%',
                    transform: 'translate(-50%, -50%)',
                    backgroundColor: '#ffffff',
                    borderRadius: '16px',
                    padding: '28px 32px',
                    boxShadow: '0 20px 60px rgba(0, 0, 0, 0.25)',
                    zIndex: 9999,
                    minWidth: '360px',
                    maxWidth: '420px',
                }}
            >
                {/* 警告圖示 */}
                <div
                    style={{
                        width: '56px',
                        height: '56px',
                        borderRadius: '50%',
                        backgroundColor: '#fef2f2',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        margin: '0 auto 16px',
                    }}
                >
                    <AlertTriangle size={28} style={{ color: '#ef4444' }} />
                </div>

                {/* 標題 */}
                <h2
                    style={{
                        fontSize: '18px',
                        fontWeight: 600,
                        color: '#1f2937',
                        marginBottom: '8px',
                        textAlign: 'center',
                    }}
                >
                    發現未上傳的資料
                </h2>

                {/* 說明文字 */}
                <p
                    style={{
                        fontSize: '14px',
                        color: '#6b7280',
                        marginBottom: '20px',
                        lineHeight: 1.6,
                        textAlign: 'center',
                    }}
                >
                    <strong style={{ color: '#1f2937' }}>
                        {TASK_NAMES[cache.task_id] || cache.task_id}
                    </strong>
                    <br />
                    有 1 筆資料尚未成功上傳到 Google Sheets
                    <br />
                    <span style={{ fontSize: '12px', color: '#9ca3af' }}>
                        建立時間: {formatDateTime(cache.created_at)}
                    </span>
                </p>

                {/* 按鈕組 */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    <Button
                        variant="primary"
                        onClick={handleRetry}
                        disabled={isRetrying}
                        style={{
                            width: '100%',
                            fontSize: '14px',
                            fontWeight: 600,
                            height: '44px',
                        }}
                    >
                        {isRetrying ? (
                            <>
                                <Loader2 size={18} style={{ marginRight: '8px' }} className="animate-spin" />
                                上傳中...
                            </>
                        ) : (
                            <>
                                <Upload size={18} style={{ marginRight: '8px' }} />
                                重新上傳
                            </>
                        )}
                    </Button>
                    <Button
                        variant="secondary"
                        onClick={onIgnore}
                        disabled={isRetrying}
                        style={{
                            width: '100%',
                            fontSize: '14px',
                            fontWeight: 500,
                            height: '44px',
                        }}
                    >
                        <RefreshCw size={18} style={{ marginRight: '8px' }} />
                        忽略並重新爬取
                    </Button>
                    <button
                        onClick={onCancel}
                        disabled={isRetrying}
                        style={{
                            background: 'none',
                            border: 'none',
                            color: '#9ca3af',
                            fontSize: '13px',
                            cursor: 'pointer',
                            padding: '8px',
                            marginTop: '4px',
                        }}
                    >
                        取消
                    </button>
                </div>
            </div>
        </>
    );
};

export default CacheCheckDialog;

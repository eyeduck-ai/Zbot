import React, { useState, useEffect, useCallback } from 'react';
import { Clock, X, Loader2, CheckCircle, XCircle, AlertCircle, Upload, Trash2 } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { tasksApi } from '../api/tasks';
import type { Job, CacheItem } from '../api/tasks';
import { TASK_NAMES } from '../constants/taskNames';

interface BackgroundTasksIndicatorProps {
    className?: string;
}

export const BackgroundTasksIndicator: React.FC<BackgroundTasksIndicatorProps> = ({ className }) => {
    const { token } = useAuth();
    const [jobs, setJobs] = useState<Job[]>([]);
    const [caches, setCaches] = useState<CacheItem[]>([]);  // 待上傳快取
    const [isOpen, setIsOpen] = useState(false);
    const [retryingId, setRetryingId] = useState<string | null>(null);  // 正在重試的快取 ID

    // 取得任務列表
    const fetchJobs = useCallback(async () => {
        if (!token) return;
        try {
            const data = await tasksApi.listJobs(10) as Job[];
            // 過濾掉 IVI/Surgery 的 fetch/preview 任務 (只保留 submit 任務)
            const HIDDEN_TASK_TYPES = [
                'ivi_fetch',
                'opnote_preview',
                'note_surgery_fetch_schedule',
                'note_surgery_fetch_details',
                'note_surgery_preview',
            ];
            const filteredData = Array.isArray(data)
                ? data.filter(job => !HIDDEN_TASK_TYPES.includes(job.task_type || job.task_id || ''))
                : [];
            setJobs(filteredData);
        } catch (e) {
            console.error('Failed to fetch jobs:', e);
            setJobs([]); // 錯誤時設為空陣列
        }
    }, [token]);

    // 取得待上傳快取列表
    const fetchCaches = useCallback(async () => {
        if (!token) return;
        try {
            const data = await tasksApi.listCaches();
            setCaches(data);
        } catch (e) {
            console.error('Failed to fetch caches:', e);
            setCaches([]);
        }
    }, [token]);

    // 重試快取上傳
    const handleRetryCache = async (cacheId: string) => {
        setRetryingId(cacheId);
        try {
            const result = await tasksApi.retryCache(cacheId);
            if (result.status === 'success') {
                // 重新載入快取列表
                fetchCaches();
            }
        } catch (e) {
            console.error('Failed to retry cache:', e);
        } finally {
            setRetryingId(null);
        }
    };

    // 刪除快取
    const handleDeleteCache = async (cacheId: string) => {
        try {
            await tasksApi.deleteCache(cacheId);
            fetchCaches();
        } catch (e) {
            console.error('Failed to delete cache:', e);
        }
    };

    // 📌 監聽任務啟動事件，立即觸發輪詢
    useEffect(() => {
        const handleTaskStarted = () => {
            fetchJobs();
        };
        const handleJobUpdated = () => {
            fetchJobs();
            fetchCaches();  // 任務完成後也檢查快取
        };
        window.addEventListener('task-started', handleTaskStarted);
        window.addEventListener('job-updated', handleJobUpdated);
        return () => {
            window.removeEventListener('task-started', handleTaskStarted);
            window.removeEventListener('job-updated', handleJobUpdated);
        };
    }, [fetchJobs, fetchCaches]);

    // 取消任務
    const handleCancelJob = async (jobId: string) => {
        if (!token) return;
        try {
            await tasksApi.cancelJob(jobId);
            fetchJobs(); // 重新載入
        } catch (e) {
            console.error('Failed to cancel job:', e);
        }
    };

    // 定期輪詢 (智慧節流：有執行中任務才頻繁輪詢)
    const hasRunningJobsRef = React.useRef(false);

    useEffect(() => {
        // 更新 ref 值
        hasRunningJobsRef.current = jobs.some(j => j.status === 'running' || j.status === 'pending');
    }, [jobs]);

    useEffect(() => {
        fetchJobs(); // 初次載入
        fetchCaches(); // 初次載入快取

        // 使用動態間隔輪詢
        let timeoutId: ReturnType<typeof setTimeout>;

        const poll = () => {
            // 有任務執行中 → 每 3 秒，無 → 每 30 秒
            const interval = hasRunningJobsRef.current ? 3000 : 30000;
            timeoutId = setTimeout(async () => {
                await fetchJobs();
                await fetchCaches();
                poll(); // 遞迴繼續
            }, interval);
        };

        // 📌 修正：首次快速輪詢 (3 秒後)，確保能及時偵測新任務
        timeoutId = setTimeout(() => {
            fetchJobs();
            fetchCaches();
            poll();
        }, 3000);

        return () => clearTimeout(timeoutId);
    }, [fetchJobs, fetchCaches]);

    // 計算進行中的任務數量 + 待上傳快取數量
    const runningCount = jobs.filter(j => j.status === 'running' || j.status === 'pending').length;
    const pendingCacheCount = caches.length;
    const totalBadgeCount = runningCount + pendingCacheCount;

    // 狀態圖示
    const getStatusIcon = (status: string) => {
        switch (status) {
            case 'running':
            case 'pending':
                return <Loader2 size={14} className="animate-spin" style={{ color: '#f59e0b' }} />;
            case 'success':
                return <CheckCircle size={14} style={{ color: '#22c55e' }} />;
            case 'failed':
                return <XCircle size={14} style={{ color: '#ef4444' }} />;
            case 'cancelled':
                return <AlertCircle size={14} style={{ color: '#9ca3af' }} />;
            default:
                return null;
        }
    };

    // 格式化時間
    const formatTime = (dateStr: string) => {
        const date = new Date(dateStr);
        return date.toLocaleTimeString('zh-TW', { hour: '2-digit', minute: '2-digit' });
    };

    // 格式化日期時間 (用於快取)
    const formatDateTime = (dateStr: string) => {
        const date = new Date(dateStr);
        return date.toLocaleString('zh-TW', {
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    };

    return (
        <div style={{ position: 'relative' }} className={className}>
            {/* 指示器按鈕 */}
            <button
                onClick={() => setIsOpen(!isOpen)}
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '8px 12px',
                    borderRadius: '8px',
                    border: '1px solid #e0e7ee',
                    backgroundColor: totalBadgeCount > 0 ? '#fef3c7' : '#ffffff',
                    cursor: 'pointer',
                    fontSize: '13px',
                    fontWeight: 500,
                    color: '#4b5563',
                    transition: 'all 0.2s',
                }}
                onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = totalBadgeCount > 0 ? '#fde68a' : '#f3f4f6';
                }}
                onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = totalBadgeCount > 0 ? '#fef3c7' : '#ffffff';
                }}
            >
                {runningCount > 0 ? (
                    <Loader2 size={16} className="animate-spin" style={{ color: '#f59e0b' }} />
                ) : pendingCacheCount > 0 ? (
                    <Upload size={16} style={{ color: '#f59e0b' }} />
                ) : (
                    <Clock size={16} style={{ color: '#6b7280' }} />
                )}
                <span>背景任務</span>
                {totalBadgeCount > 0 && (
                    <span style={{
                        backgroundColor: pendingCacheCount > 0 && runningCount === 0 ? '#ef4444' : '#f59e0b',
                        color: 'white',
                        fontSize: '11px',
                        fontWeight: 600,
                        padding: '2px 6px',
                        borderRadius: '10px',
                        minWidth: '18px',
                        textAlign: 'center',
                    }}>
                        {totalBadgeCount}
                    </span>
                )}
            </button>

            {/* 下拉面板 */}
            {isOpen && (
                <div style={{
                    position: 'absolute',
                    top: 'calc(100% + 8px)',
                    right: 0,
                    width: '360px',
                    backgroundColor: '#ffffff',
                    borderRadius: '12px',
                    boxShadow: '0 4px 20px rgba(0, 0, 0, 0.15)',
                    border: '1px solid #e0e7ee',
                    zIndex: 1000,
                    overflow: 'hidden',
                }}>
                    {/* 標題 */}
                    <div style={{
                        padding: '12px 16px',
                        borderBottom: '1px solid #e0e7ee',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                    }}>
                        <span style={{ fontWeight: 600, color: '#1f2937' }}>背景任務</span>
                        <button
                            onClick={() => setIsOpen(false)}
                            style={{
                                background: 'none',
                                border: 'none',
                                cursor: 'pointer',
                                padding: '4px',
                                color: '#6b7280',
                            }}
                        >
                            <X size={16} />
                        </button>
                    </div>

                    {/* 待重新上傳區塊 */}
                    {caches.length > 0 && (
                        <div style={{
                            backgroundColor: '#fef2f2',
                            borderBottom: '1px solid #fecaca',
                        }}>
                            <div style={{
                                padding: '10px 16px',
                                display: 'flex',
                                alignItems: 'center',
                                gap: '8px',
                                color: '#dc2626',
                                fontWeight: 600,
                                fontSize: '13px',
                            }}>
                                <Upload size={14} />
                                待重新上傳 ({caches.length})
                            </div>
                            {caches.map(cache => (
                                <div
                                    key={cache.id}
                                    style={{
                                        padding: '10px 16px',
                                        borderTop: '1px solid #fecaca',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'space-between',
                                    }}
                                >
                                    <div>
                                        <div style={{ fontSize: '13px', fontWeight: 500, color: '#1f2937' }}>
                                            {TASK_NAMES[cache.task_id] || cache.task_id}
                                        </div>
                                        <div style={{ fontSize: '11px', color: '#6b7280' }}>
                                            {formatDateTime(cache.created_at)}
                                        </div>
                                    </div>
                                    <div style={{ display: 'flex', gap: '6px' }}>
                                        <button
                                            onClick={() => handleRetryCache(cache.id)}
                                            disabled={retryingId === cache.id}
                                            style={{
                                                padding: '4px 10px',
                                                fontSize: '11px',
                                                borderRadius: '4px',
                                                border: 'none',
                                                backgroundColor: '#3b82f6',
                                                color: 'white',
                                                cursor: retryingId === cache.id ? 'not-allowed' : 'pointer',
                                                fontWeight: 500,
                                                display: 'flex',
                                                alignItems: 'center',
                                                gap: '4px',
                                                opacity: retryingId === cache.id ? 0.7 : 1,
                                            }}
                                        >
                                            {retryingId === cache.id ? (
                                                <Loader2 size={12} className="animate-spin" />
                                            ) : (
                                                <Upload size={12} />
                                            )}
                                            重新上傳
                                        </button>
                                        <button
                                            onClick={() => handleDeleteCache(cache.id)}
                                            style={{
                                                padding: '4px 8px',
                                                fontSize: '11px',
                                                borderRadius: '4px',
                                                border: '1px solid #e0e7ee',
                                                backgroundColor: '#ffffff',
                                                color: '#6b7280',
                                                cursor: 'pointer',
                                            }}
                                        >
                                            <Trash2 size={12} />
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}

                    {/* 任務列表 */}
                    <div style={{ maxHeight: '300px', overflowY: 'auto' }}>
                        {jobs.length === 0 && caches.length === 0 ? (
                            <div style={{
                                padding: '24px',
                                textAlign: 'center',
                                color: '#9ca3af',
                                fontSize: '13px',
                            }}>
                                尚無任務
                            </div>
                        ) : (
                            jobs.map(job => (
                                <div
                                    key={job.id}
                                    style={{
                                        padding: '12px 16px',
                                        borderBottom: '1px solid #f3f4f6',
                                    }}
                                >
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                                        {/* 狀態圖示 */}
                                        <div style={{ flexShrink: 0 }}>
                                            {getStatusIcon(job.status)}
                                        </div>

                                        {/* 任務資訊 */}
                                        <div style={{ flex: 1, minWidth: 0 }}>
                                            <div style={{
                                                fontSize: '13px',
                                                fontWeight: 500,
                                                color: '#1f2937',
                                                marginBottom: '2px',
                                            }}>
                                                {TASK_NAMES[job.task_id || job.crawler_id || ''] || job.task_id || job.crawler_id || 'Unknown'}
                                            </div>
                                            <div style={{
                                                fontSize: '11px',
                                                color: '#6b7280',
                                                display: 'flex',
                                                alignItems: 'center',
                                                gap: '8px',
                                            }}>
                                                <span>{formatTime(job.created_at)}</span>
                                                {(job.status === 'running' || job.status === 'pending') && (
                                                    <span style={{ color: '#f59e0b' }}>{job.progress}%</span>
                                                )}
                                                {job.status === 'success' && (
                                                    <span style={{ color: '#22c55e' }}>完成</span>
                                                )}
                                                {job.status === 'failed' && (
                                                    <span style={{ color: '#ef4444' }}>失敗</span>
                                                )}
                                                {job.status === 'cancelled' && (
                                                    <span style={{ color: '#9ca3af' }}>已取消</span>
                                                )}
                                            </div>
                                        </div>

                                        {/* 取消按鈕 */}
                                        {(job.status === 'running' || job.status === 'pending') && (
                                            <button
                                                onClick={() => handleCancelJob(job.id)}
                                                style={{
                                                    padding: '4px 8px',
                                                    fontSize: '11px',
                                                    borderRadius: '4px',
                                                    border: '1px solid #e0e7ee',
                                                    backgroundColor: '#ffffff',
                                                    color: '#ef4444',
                                                    cursor: 'pointer',
                                                    fontWeight: 500,
                                                }}
                                                onMouseEnter={(e) => {
                                                    e.currentTarget.style.backgroundColor = '#fee2e2';
                                                }}
                                                onMouseLeave={(e) => {
                                                    e.currentTarget.style.backgroundColor = '#ffffff';
                                                }}
                                            >
                                                取消
                                            </button>
                                        )}
                                    </div>

                                    {/* 結果訊息 (成功時顯示) */}
                                    {job.status === 'success' && job.result && (() => {
                                        // 判斷是否為手術記錄送出任務
                                        const taskType = job.task_type || job.task_id || '';
                                        const isIviSubmit = taskType === 'opnote_submit' || taskType === 'note_ivi_submit';
                                        const isSurgerySubmit = taskType === 'note_surgery_submit';

                                        // 為送出任務顯示友善訊息
                                        let displayMessage = '';
                                        if (typeof job.result === 'object' && job.result.total !== undefined) {
                                            const success = job.result.success || 0;
                                            if (isIviSubmit) {
                                                displayMessage = `成功送出 ${success} 筆`;
                                            } else if (isSurgerySubmit) {
                                                displayMessage = `成功送出 ${success} 筆`;
                                            } else if (job.result.message || job.result.status) {
                                                displayMessage = job.result.message || job.result.status || '';
                                            } else {
                                                displayMessage = JSON.stringify(job.result).slice(0, 80);
                                            }
                                        } else if (typeof job.result === 'object') {
                                            displayMessage = job.result.message || job.result.status || JSON.stringify(job.result).slice(0, 80);
                                        } else {
                                            displayMessage = String(job.result).slice(0, 80);
                                        }

                                        return (
                                            <div style={{
                                                marginTop: '8px',
                                                padding: '8px 10px',
                                                backgroundColor: 'rgba(34, 197, 94, 0.08)',
                                                borderRadius: '6px',
                                                fontSize: '11px',
                                                color: '#15803d',
                                                lineHeight: 1.4,
                                                display: 'flex',
                                                alignItems: 'center',
                                                gap: '6px',
                                            }}>
                                                <span>{displayMessage}</span>
                                                {job.result?.sheet_url && (
                                                    <a
                                                        href={job.result.sheet_url}
                                                        target="_blank"
                                                        rel="noopener noreferrer"
                                                        style={{
                                                            color: '#137fec',
                                                            textDecoration: 'underline',
                                                            flexShrink: 0,
                                                        }}
                                                        onClick={(e) => e.stopPropagation()}
                                                    >
                                                        開啟
                                                    </a>
                                                )}
                                            </div>
                                        );
                                    })()}
                                    {job.status === 'failed' && job.error && (
                                        <div style={{
                                            marginTop: '8px',
                                            padding: '8px 10px',
                                            backgroundColor: 'rgba(239, 68, 68, 0.08)',
                                            borderRadius: '6px',
                                            fontSize: '11px',
                                            color: '#dc2626',
                                            lineHeight: 1.4,
                                        }}>
                                            {job.error.slice(0, 100)}
                                        </div>
                                    )}
                                </div>
                            ))
                        )}
                    </div>
                </div>
            )}

            {/* 點擊外部關閉 */}
            {isOpen && (
                <div
                    style={{
                        position: 'fixed',
                        top: 0,
                        left: 0,
                        right: 0,
                        bottom: 0,
                        zIndex: 999,
                    }}
                    onClick={() => setIsOpen(false)}
                />
            )}

            <style>{`
                @keyframes spin {
                    from { transform: rotate(0deg); }
                    to { transform: rotate(360deg); }
                }
                .animate-spin {
                    animation: spin 1s linear infinite;
                }
            `}</style>
        </div>
    );
};

export default BackgroundTasksIndicator;

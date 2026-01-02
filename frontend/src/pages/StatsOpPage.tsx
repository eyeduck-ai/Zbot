import React, { useState, useCallback } from 'react';
import { BarChart3, Play, ChevronDown, ChevronUp, Check, AlertCircle, Loader2 } from 'lucide-react';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { useTaskPolling } from '../hooks/useTaskPolling';
import { useTaskStats } from '../hooks/useTaskStats';
import { TrustBadge } from '../components/TrustBadge';
import { CacheCheckDialog } from '../components/CacheCheckDialog';
import type { CacheInfo } from '../components/CacheCheckDialog';
import { tasksApi } from '../api/tasks';

const TASK_ID = 'stats_op_update';

export const StatsOpPage: React.FC = () => {
    // 預設為上個月 (YYYY-MM 格式)
    const getLastMonthStr = () => {
        const now = new Date();
        const lastMonth = new Date(now.getFullYear(), now.getMonth() - 1, 1);
        const y = lastMonth.getFullYear();
        const m = String(lastMonth.getMonth() + 1).padStart(2, '0');
        return `${y}-${m}`;
    };

    const lastMonthStr = getLastMonthStr();

    // 日期範圍狀態
    const [useCustomRange, setUseCustomRange] = useState(false);
    const [startMonth, setStartMonth] = useState(lastMonthStr);
    const [endMonth, setEndMonth] = useState(lastMonthStr);

    // 📌 快取檢查狀態
    const [pendingCache, setPendingCache] = useState<CacheInfo | null>(null);
    const [showCacheDialog, setShowCacheDialog] = useState(false);

    // 📌 使用 useTaskPolling hook
    const { loading, progress, statusMsg, statusType, sheetUrl, runTask } = useTaskPolling();

    // 📌 使用 useTaskStats 取得累積統計
    const { stats } = useTaskStats(TASK_ID);

    // 建立任務參數
    const buildParams = useCallback(() => {
        const params: Record<string, number> = {};
        if (useCustomRange) {
            const [sy, sm] = startMonth.split('-').map(Number);
            const [ey, em] = endMonth.split('-').map(Number);
            params.year = sy;
            params.month = sm;
            params.end_year = ey;
            params.end_month = em;
        }
        return params;
    }, [useCustomRange, startMonth, endMonth]);

    // 執行任務 (跳過快取檢查)
    const executeTask = useCallback(async () => {
        await runTask(TASK_ID, buildParams());
    }, [runTask, buildParams]);

    // 重試快取上傳
    const handleRetryCache = useCallback(async () => {
        if (!pendingCache) return;
        try {
            const result = await tasksApi.retryCache(pendingCache.id);
            if (result.status === 'success') {
                setShowCacheDialog(false);
                setPendingCache(null);
            }
        } catch (e) {
            console.error('Failed to retry cache:', e);
        }
    }, [pendingCache]);

    // 忽略快取並重新執行
    const handleIgnoreCache = useCallback(async () => {
        if (pendingCache) {
            await tasksApi.deleteCache(pendingCache.id);
        }
        setShowCacheDialog(false);
        setPendingCache(null);
        await executeTask();
    }, [pendingCache, executeTask]);

    // 執行任務 (先檢查快取)
    const handleRun = useCallback(async () => {
        try {
            const cacheResult = await tasksApi.checkCache(TASK_ID);
            if (cacheResult.has_cache && cacheResult.cache) {
                setPendingCache(cacheResult.cache);
                setShowCacheDialog(true);
                return;
            }
        } catch (e) {
            console.error('Failed to check cache:', e);
        }
        await executeTask();
    }, [executeTask]);

    // 解析顯示的月份範圍
    const displayRange = useCustomRange
        ? `${startMonth.replace('-', '/')} ~ ${endMonth.replace('-', '/')}`
        : `${lastMonthStr.replace('-', '/')} (上個月)`;

    return (
        <div className="bg-[#F5F5F7] min-h-full flex flex-col p-8 font-sans">


            <div className="relative z-10 w-full max-w-3xl mx-auto my-auto">
                {/* Header */}
                <header className="mb-8">
                    <div className="flex items-end justify-between mb-2">
                        <div className="flex items-center gap-4">
                            <div style={{
                                width: '48px',
                                height: '48px',
                                borderRadius: '14px',
                                background: 'linear-gradient(135deg, #eef4fd 0%, #dbeafe 100%)',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                            }}>
                                <BarChart3 size={24} color="#137fec" />
                            </div>
                            <div>
                                <h2 className="text-2xl font-bold text-gray-900 tracking-tight">手術統計</h2>
                                <p className="text-sm text-gray-500">查詢月份手術排程 → 統計 → 更新 Google Sheet</p>
                            </div>
                        </div>
                        {/* 信任徽章 */}
                        {!loading && stats && stats.total_items > 0 && (
                            <TrustBadge taskId="stats_op_update" totalItems={stats.total_items} />
                        )}
                    </div>
                </header>

                {/* 控制區 */}
                <Card className="shadow-xl backdrop-blur-xl bg-white/70 border border-white/50 p-6 mb-6">
                    {/* 日期選擇 */}
                    <div className="mb-6">
                        <div className="flex items-center justify-between mb-3">
                            <label className="text-sm font-semibold text-gray-700">查詢範圍</label>
                            <button
                                onClick={() => setUseCustomRange(!useCustomRange)}
                                className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 transition-colors"
                            >
                                {useCustomRange ? '使用預設' : '自訂範圍'}
                                {useCustomRange ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                            </button>
                        </div>

                        {/* 預設顯示 */}
                        {!useCustomRange && (
                            <div className="bg-blue-50/50 border border-blue-100 rounded-xl px-4 py-3">
                                <span className="text-gray-700 font-medium">{displayRange}</span>
                            </div>
                        )}

                        {/* 自訂範圍 */}
                        {useCustomRange && (
                            <div className="bg-gray-50 border border-gray-200 rounded-xl p-4 space-y-4">
                                {/* 開始 */}
                                <div className="flex items-center gap-3">
                                    <span className="text-sm text-gray-500 w-12">開始</span>
                                    <input
                                        type="month"
                                        value={startMonth}
                                        onChange={e => setStartMonth(e.target.value)}
                                        className="flex-1 bg-white border border-gray-200 rounded-lg px-4 py-2 text-sm focus:ring-2 focus:ring-blue-500/50 focus:border-blue-400"
                                    />
                                </div>
                                {/* 結束 */}
                                <div className="flex items-center gap-3">
                                    <span className="text-sm text-gray-500 w-12">結束</span>
                                    <input
                                        type="month"
                                        value={endMonth}
                                        onChange={e => setEndMonth(e.target.value)}
                                        className="flex-1 bg-white border border-gray-200 rounded-lg px-4 py-2 text-sm focus:ring-2 focus:ring-blue-500/50 focus:border-blue-400"
                                    />
                                </div>
                            </div>
                        )}
                    </div>

                    {/* 執行按鈕 */}
                    <Button
                        variant="primary"
                        onClick={handleRun}
                        disabled={loading}
                        className="w-full shadow-lg h-12 flex items-center justify-center text-base"
                    >
                        {loading ? (
                            <>
                                <Loader2 size={20} className="mr-2 animate-spin" />
                                執行中...{progress !== undefined && ` (${progress}%)`}
                            </>
                        ) : (
                            <>
                                <Play size={20} className="mr-2" />
                                執行統計
                            </>
                        )}
                    </Button>
                </Card>

                {/* 狀態訊息 */}
                {statusMsg && (
                    <Card className="shadow-xl backdrop-blur-xl bg-white/70 border border-white/50 p-3">
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <Badge
                                variant={statusType === 'error' ? 'error' : statusType === 'success' ? 'success' : 'info'}
                                className="text-sm"
                            >
                                {statusType === 'success' && <Check size={16} className="mr-1" />}
                                {statusType === 'error' && <AlertCircle size={16} className="mr-1" />}
                                {statusType === 'info' && <Loader2 size={16} className="mr-1 animate-spin" />}
                                {statusMsg}
                            </Badge>
                            {statusType === 'success' && sheetUrl && (
                                <a
                                    href={sheetUrl}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    style={{
                                        color: '#137fec',
                                        fontSize: '14px',
                                        textDecoration: 'underline',
                                    }}
                                >
                                    開啓 Google Sheets
                                </a>
                            )}
                        </div>
                    </Card>
                )}
            </div>

            {/* 快取檢查對話框 */}
            {showCacheDialog && pendingCache && (
                <CacheCheckDialog
                    cache={pendingCache}
                    onRetry={handleRetryCache}
                    onIgnore={handleIgnoreCache}
                    onCancel={() => {
                        setShowCacheDialog(false);
                        setPendingCache(null);
                    }}
                />
            )}
        </div>
    );
};

import React, { useState, useCallback } from 'react';
import { BedDouble, Play, ChevronDown, ChevronUp, Check, AlertCircle, Loader2 } from 'lucide-react';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { useTaskPolling } from '../hooks/useTaskPolling';
import { useTaskStats } from '../hooks/useTaskStats';
import { TrustBadge } from '../components/TrustBadge';

export const DashboardBedPage: React.FC = () => {
    // 預設今天 (使用本地時區)
    const now = new Date();
    const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;

    // 設定狀態
    const [useCustomSettings, setUseCustomSettings] = useState(false);
    const [date, setDate] = useState(today);
    const [crawlDetailDays, setCrawlDetailDays] = useState(3);

    // 📌 使用 useTaskPolling hook
    const { loading, progress, statusMsg, statusType, sheetUrl, runTask } = useTaskPolling();

    // 📌 使用 useTaskStats 取得累積統計
    const { stats } = useTaskStats('dashboard_bed');

    // 執行任務
    const handleRun = useCallback(async () => {
        const params: Record<string, string | number> = {};

        if (useCustomSettings) {
            params.date = date;
            params.crawl_detail_days = crawlDetailDays;
        }

        await runTask('dashboard_bed', params);
    }, [useCustomSettings, date, crawlDetailDays, runTask]);

    const displaySettings = useCustomSettings
        ? `${date}，詳細爬取 ${crawlDetailDays} 天`
        : `今天 (${today})，詳細爬取 3 天`;

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
                                <BedDouble size={24} color="#137fec" />
                            </div>
                            <div>
                                <h2 className="text-2xl font-bold text-gray-900 tracking-tight">待床追蹤</h2>
                                <p className="text-sm text-gray-500">爬取手術排程 → 過濾待床資訊 → 更新 Google Sheet</p>
                            </div>
                        </div>
                        {/* 信任徽章 */}
                        {!loading && stats && stats.total_items > 0 && (
                            <TrustBadge taskId="dashboard_bed" totalItems={stats.total_items} />
                        )}
                    </div>
                </header>

                {/* 控制區 */}
                <Card className="shadow-xl backdrop-blur-xl bg-white/70 border border-white/50 p-6 mb-6">
                    {/* 設定 */}
                    <div className="mb-6">
                        <div className="flex items-center justify-between mb-3">
                            <label className="text-sm font-semibold text-gray-700">執行設定</label>
                            <button
                                onClick={() => setUseCustomSettings(!useCustomSettings)}
                                className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 transition-colors"
                            >
                                {useCustomSettings ? '使用預設' : '自訂設定'}
                                {useCustomSettings ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                            </button>
                        </div>

                        {/* 預設顯示 */}
                        {!useCustomSettings && (
                            <div className="bg-blue-50/50 border border-blue-100 rounded-xl px-4 py-3">
                                <span className="text-gray-700 font-medium">{displaySettings}</span>
                            </div>
                        )}

                        {/* 自訂設定 */}
                        {useCustomSettings && (
                            <div className="bg-white/50 border border-gray-200 rounded-xl p-4 space-y-4">
                                {/* 日期 */}
                                <div className="flex items-center gap-3">
                                    <span className="text-sm text-gray-500 w-24">起始日期</span>
                                    <input
                                        type="date"
                                        value={date}
                                        onChange={e => setDate(e.target.value)}
                                        className="flex-1 bg-white border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500/50"
                                    />
                                </div>
                                {/* 詳細天數 */}
                                <div className="flex items-center gap-3">
                                    <span className="text-sm text-gray-500 w-24">詳細爬取</span>
                                    <select
                                        value={crawlDetailDays}
                                        onChange={e => setCrawlDetailDays(Number(e.target.value))}
                                        className="flex-1 bg-white border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500/50"
                                    >
                                        <option value={1}>1 天</option>
                                        <option value={3}>3 天 (預設)</option>
                                        <option value={5}>5 天</option>
                                        <option value={7}>7 天 (⚠ 較長天數可能被封鎖)</option>
                                    </select>
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
                                執行追蹤
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
                                    開啟 Google Sheets
                                </a>
                            )}
                        </div>
                    </Card>
                )}
            </div>
        </div>
    );
};

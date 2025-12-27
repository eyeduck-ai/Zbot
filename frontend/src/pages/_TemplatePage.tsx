/**
 * 📌 _TemplatePage.tsx - 新頁面範本
 * 
 * 此檔案作為建立新工具頁面的起點。
 * 複製此檔案並修改以下部分：
 * 1. 頁面標題和描述
 * 2. Icon 和主題色
 * 3. 參數表單
 * 4. API 呼叫邏輯
 * 
 * @example 建立新頁面：
 * 1. cp _TemplatePage.tsx MyNewPage.tsx
 * 2. 修改 TASK_ID, PAGE_TITLE, PAGE_DESCRIPTION
 * 3. 在 App.tsx 加入路由
 * 4. 在 Sidebar.tsx 加入導航
 */

import React, { useState, useCallback } from 'react';
// 📌 從 lucide-react 選擇適合的 icon
import { Wrench, Play, Check, AlertCircle, Loader2 } from 'lucide-react';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
// Badge is available: import { Badge } from '../components/ui/Badge';
import { Input } from '../components/ui/Input';
// 📌 使用 useTaskPolling hook 統一處理任務輪詢
import { useTaskPolling } from '../hooks/useTaskPolling';
// 📌 使用 useTaskStats + TrustBadge 顯示累積完成數
import { useTaskStats } from '../hooks/useTaskStats';
import { TrustBadge } from '../components/TrustBadge';
import { THEME } from '../styles/theme';

// =============================================================================
// 📌 頁面設定 - 修改這些常數
// =============================================================================

const TASK_ID = 'my_new_task';           // 對應後端 Task ID
const PAGE_TITLE = '工具名稱';            // 頁面標題
const PAGE_DESCRIPTION = '工具描述說明';   // 頁面副標題

// =============================================================================
// 📌 元件
// =============================================================================

export const _TemplatePage: React.FC = () => {
    // -------------------------------------------------------------------------
    // 狀態管理
    // -------------------------------------------------------------------------

    // 表單參數
    const [param1, setParam1] = useState('');
    const [param2, setParam2] = useState('');

    // 📌 使用 useTaskPolling hook (取代手動輪詢邏輯)
    // 這個 hook 自動處理：
    // - EIP 憑證讀取
    // - 任務提交與輪詢
    // - success/failed/cancelled 狀態
    // - result.status === 'error' 檢查
    const { loading, statusMsg, statusType, runTask } = useTaskPolling();

    // 📌 使用 useTaskStats 取得任務統計，配合 TrustBadge 顯示
    const { stats } = useTaskStats(TASK_ID);

    // -------------------------------------------------------------------------
    // 📌 執行任務 - 使用 useTaskPolling hook
    // -------------------------------------------------------------------------

    const handleRun = useCallback(async () => {
        // 簡單呼叫 runTask，hook 會自動處理輪詢和狀態更新
        await runTask(TASK_ID, {
            param1,
            param2,
        });
    }, [param1, param2, runTask]);

    // -------------------------------------------------------------------------
    // 📌 渲染
    // -------------------------------------------------------------------------

    return (
        // 📌 注意：外層使用 min-h-full flex flex-col 搭配內層 my-auto 達成動態置中
        <div className="bg-[#F5F5F7] min-h-full flex flex-col p-8 font-sans">
            <div className="relative z-10 w-full max-w-3xl mx-auto my-auto">

                {/* ============================================================
                    Header - 標準結構
                    ============================================================ */}
                <header className="mb-8">
                    <div className="flex items-center justify-between mb-4">
                        <div className="flex items-center gap-4">
                            {/* 📌 Icon 容器 - 統一樣式 */}
                            <div style={{
                                width: '48px',
                                height: '48px',
                                borderRadius: '14px',
                                background: `linear-gradient(135deg, ${THEME.primaryLight} 0%, #dbeafe 100%)`,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                            }}>
                                <Wrench size={24} color={THEME.primary} />
                            </div>

                            {/* 📌 標題區 */}
                            <div>
                                <h2 className="text-2xl font-bold text-gray-900 tracking-tight">
                                    {PAGE_TITLE}
                                </h2>
                                <p className="text-sm text-gray-500">
                                    {PAGE_DESCRIPTION}
                                </p>
                            </div>
                        </div>
                    </div>
                </header>

                {/* ============================================================
                    📌 信任徽章 - 顯示累積完成數，建立使用者信心
                    只在 loading = false 且有統計數據時顯示
                    ============================================================ */}
                {!loading && stats && stats.total_items > 0 && (
                    <TrustBadge taskId={TASK_ID} totalItems={stats.total_items} />
                )}

                {/* ============================================================
                    主要內容區
                    ============================================================ */}
                <Card style={{ padding: '24px' }}>
                    {/* 📌 參數表單 */}
                    <div style={{ marginBottom: '20px' }}>
                        <Input
                            label="參數 1"
                            placeholder="請輸入..."
                            value={param1}
                            onChange={e => setParam1(e.target.value)}
                        />

                        <Input
                            label="參數 2"
                            placeholder="請輸入..."
                            value={param2}
                            onChange={e => setParam2(e.target.value)}
                        />
                    </div>

                    {/* 📌 執行按鈕 */}
                    <Button
                        onClick={handleRun}
                        disabled={loading}
                        isLoading={loading}
                        variant="primary"
                        size="lg"
                        style={{ width: '100%' }}
                    >
                        <Play size={16} style={{ marginRight: '8px' }} />
                        執行任務
                    </Button>
                </Card>

                {/* ============================================================
                    狀態訊息 - 根據 statusType 顯示不同樣式
                    ============================================================ */}
                {statusMsg && (
                    <div
                        className="mt-4"
                        style={{
                            padding: '12px 16px',
                            borderRadius: '8px',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '8px',
                            // 📌 根據狀態切換顏色
                            ...(statusType === 'success' && {
                                backgroundColor: 'rgba(34, 197, 94, 0.1)',
                                border: '1px solid rgba(34, 197, 94, 0.2)',
                                color: '#15803d',
                            }),
                            ...(statusType === 'error' && {
                                backgroundColor: 'rgba(239, 68, 68, 0.1)',
                                border: '1px solid rgba(239, 68, 68, 0.2)',
                                color: '#dc2626',
                            }),
                            ...(statusType === 'info' && {
                                backgroundColor: 'rgba(59, 130, 246, 0.1)',
                                border: '1px solid rgba(59, 130, 246, 0.2)',
                                color: '#2563eb',
                            }),
                        }}
                    >
                        {statusType === 'success' && <Check size={16} />}
                        {statusType === 'error' && <AlertCircle size={16} />}
                        {statusType === 'info' && <Loader2 size={16} className="animate-spin" />}
                        {statusMsg}
                    </div>
                )}

            </div>
        </div>
    );
};

// 📌 注意：使用 named export，不要用 default export

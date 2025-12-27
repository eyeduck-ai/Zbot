import React, { useState, useCallback, useEffect } from 'react';
import { Scissors, Calendar, ChevronLeft, Check, Loader2, ExternalLink, AlertCircle } from 'lucide-react';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Toast } from '../components/ui/Toast';
import { useAuth } from '../context/AuthContext';
import { tasksApi } from '../api/tasks';
import { pollJobResult } from '../hooks/useTaskPolling';
import { useTaskStats } from '../hooks/useTaskStats';
import { TrustBadge } from '../components/TrustBadge';
import { StepIndicator } from '../components/StepIndicator';
import { THEME } from '../styles/theme';
import { DEMO_MODE } from '../config';
import { MOCK_SCHEDULE, MOCK_DETAILS } from '../mocks/surgeryMocks';
import type { ScheduleItem, DetailItem } from '../mocks/surgeryMocks';

// =============================================================================
// Types
// =============================================================================

// Types are imported from mocks/surgeryMocks.ts
// Re-export for internal use if needed
export type { ScheduleItem, DetailItem } from '../mocks/surgeryMocks';

// 步驟定義 (4 步)
type Step = 'fetch' | 'select' | 'edit' | 'done';
const STEPS: { id: Step; label: string }[] = [
    { id: 'fetch', label: '抓取排程' },
    { id: 'select', label: '選擇病人' },
    { id: 'edit', label: '確認編輯' },
    { id: 'done', label: '完成' },
];

// =============================================================================
// Component
// =============================================================================

interface SurgeryPageProps {
    onNavigate?: (tool: string) => void;
}

export const SurgeryPage: React.FC<SurgeryPageProps> = ({ onNavigate }) => {
    const { } = useAuth(); // Keep useAuth for future use
    const { stats } = useTaskStats('note_surgery_submit');

    // Demo 模式 (使用模擬資料，由 config.ts 控制)
    const [previewMode] = useState(DEMO_MODE);

    // 日期與醫師設定
    const now = new Date();
    const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
    const [date, setDate] = useState(today);
    const [vsCode, setVsCode] = useState('');

    // 助手燈號 (用於 fetch_details 和 preview)
    const loginEipId = localStorage.getItem('user') || '';
    const defaultRCode = loginEipId.match(/\d{4}/)?.[0] || '';
    const [rCode] = useState(defaultRCode);

    // 狀態
    const [step, setStep] = useState<Step>('fetch');
    const [loading, setLoading] = useState(false);
    const [progress, setProgress] = useState<number | undefined>(undefined);
    const [fetchProgress, setFetchProgress] = useState<number | undefined>(undefined);
    const [statusMsg, setStatusMsg] = useState<string | null>(null);
    const [statusType, setStatusType] = useState<'info' | 'success' | 'error'>('info');

    // 資料
    const [scheduleItems, setScheduleItems] = useState<ScheduleItem[]>([]);
    const [detailItems, setDetailItems] = useState<DetailItem[]>([]);
    const [, setColumnMap] = useState<Record<string, string | null>>({});
    const [lastClickedScheduleIndex, setLastClickedScheduleIndex] = useState<number | null>(null);

    // 批次編輯 (只適用於基本欄位，不包含 COL_* 動態欄位)
    const [batchSide, setBatchSide] = useState('');
    const [batchAnesthesia, setBatchAnesthesia] = useState('');
    const [batchOpType, setBatchOpType] = useState('');
    const [batchPreOpDx, setBatchPreOpDx] = useState('');
    const [batchOpName, setBatchOpName] = useState('');

    // 動態手術類型選項 (從 API 取得)
    const [opTypes, setOpTypes] = useState<string[]>(['PHACO', 'LENSX']);

    // 醫師刀表設定資訊
    const [doctorSheetInfo, setDoctorSheetInfo] = useState<{
        configured: boolean;
        sheet_id?: string;
        worksheet?: string;
    } | null>(null);

    // 載入手術類型選項
    useEffect(() => {
        const fetchOpTypes = async () => {
            try {
                const token = localStorage.getItem('token');
                const res = await fetch('/api/templates/op-types', {
                    headers: { Authorization: `Bearer ${token}` }
                });
                if (res.ok) {
                    const data = await res.json();
                    if (data.op_types && data.op_types.length > 0) {
                        setOpTypes(data.op_types);
                    }
                }
            } catch (e) {
                console.warn('Failed to fetch op_types, using defaults');
            }
        };
        fetchOpTypes();
    }, []);

    // =========================================================================
    // Step 1: 抓取排程
    // =========================================================================
    const handleFetchSchedule = useCallback(async () => {
        if (previewMode) {
            const mockData = MOCK_SCHEDULE.map(item => ({ ...item }));
            setScheduleItems(mockData);
            setStep('select');
            setStatusMsg(`找到 ${mockData.length} 筆排程`);
            setStatusType('success');
            return;
        }

        if (!vsCode) {
            setStatusMsg('請輸入主治醫師燈號');
            setStatusType('error');
            return;
        }

        setLoading(true);
        setStatusMsg(null);

        const eipId = localStorage.getItem('user');
        const eipPsw = localStorage.getItem('eip_psw');

        try {
            const jobData = await tasksApi.run('note_surgery_fetch_schedule', {
                params: { date, doc_code: vsCode },
                eip_id: eipId || undefined,
                eip_psw: eipPsw || undefined
            });

            // Poll job
            for (let i = 0; i < 30; i++) {
                await new Promise(r => setTimeout(r, 1000));
                const job = await tasksApi.getJob(jobData.job_id);
                if (job.status === 'success') {
                    const result = job.result;
                    if ((result as any)?.count > 0) {
                        setScheduleItems((result as any).items.map((item: ScheduleItem) => ({
                            ...item,
                            selected: true
                        })));
                        setStep('select');
                        setStatusMsg(`找到 ${(result as any).count} 筆排程`);
                        setStatusType('success');

                        // 查詢醫師的刀表設定
                        try {
                            const token = localStorage.getItem('token');
                            const sheetRes = await fetch(`/api/sheets/doc/${vsCode}`, {
                                headers: { Authorization: `Bearer ${token}` }
                            });
                            if (sheetRes.ok) {
                                const sheetData = await sheetRes.json();
                                setDoctorSheetInfo(sheetData);
                            }
                        } catch (e) {
                            console.warn('Failed to fetch doctor sheet info');
                        }
                    } else {
                        setStatusMsg((result as any)?.message || '找不到排程');
                        setStatusType('info');
                    }
                    break;
                }
                if (job.status === 'failed') throw new Error(job.error);
                if (job.status === 'cancelled') throw new Error('任務已取消');
            }

        } catch (e: any) {
            setStatusMsg(`抓取排程失敗: ${e.message}`);
            setStatusType('error');
        } finally {
            setLoading(false);
        }
    }, [date, vsCode, previewMode]);

    // =========================================================================
    // Step 2: 抓取詳情 (選擇病人後)
    // =========================================================================
    const handleFetchDetails = useCallback(async () => {
        const selected = scheduleItems.filter(i => i.selected);
        if (selected.length === 0) {
            setStatusMsg('請選擇至少一位病人');
            setStatusType('error');
            return;
        }

        if (previewMode) {
            // Mock: 根據選中的病人過濾
            const mockResults = MOCK_DETAILS.filter(d =>
                selected.some(s => s.hisno === d.hisno)
            );
            setDetailItems(mockResults.map(item => ({ ...item })));
            setStep('edit');
            setStatusMsg(`共 ${mockResults.length} 筆可編輯`);
            setStatusType('success');
            return;
        }

        setLoading(true);
        setStatusMsg('正在抓取詳細資料...');
        setStatusType('info');

        const eipId = localStorage.getItem('user');
        const eipPsw = localStorage.getItem('eip_psw');

        try {
            // 1. Fetch Details
            const detailJob = await tasksApi.run('note_surgery_fetch_details', {
                params: {
                    date,
                    doc_code: vsCode,
                    r_code: rCode || defaultRCode,
                    items: selected.map(i => ({
                        hisno: i.hisno,
                        name: i.name,
                        link: i.link,
                        op_date: i.op_date,
                        op_time: i.op_time,
                        pre_op_dx: i.pre_op_dx,
                        op_name: i.op_name,
                        op_room_info: i.op_room_info,
                    }))
                },
                eip_id: eipId || undefined,
                eip_psw: eipPsw || undefined
            });

            // Poll detail job (使用 pollJobResult 並顯示進度)
            setFetchProgress(0);
            const detailData = await pollJobResult(detailJob.job_id, {
                silent: true,
                onProgress: (p) => setFetchProgress(p)
            });

            setFetchProgress(undefined);
            setColumnMap(detailData.column_map || {});

            // 2. Preview (建構 Payload)
            setStatusMsg('正在建構預覽...');
            const previewJob = await tasksApi.run('note_surgery_preview', {
                params: {
                    date,
                    doc_code: vsCode,
                    r_code: rCode || defaultRCode,
                    column_map: detailData.column_map || {},
                    items: detailData.items.map((i: any) => ({
                        hisno: i.hisno,
                        name: i.name,
                        op_type: i.op_type,
                        op_side: i.op_side,
                        op_sect: i.op_sect,
                        op_bed: i.op_bed,
                        op_anesthesia: i.op_anesthesia,
                        web9_data: i.web9_data,
                        gsheet_data: i.gsheet_data
                    }))
                },
                eip_id: eipId || undefined,
                eip_psw: eipPsw || undefined
            });

            // Poll preview job
            let previewData: any = null;
            for (let i = 0; i < 30; i++) {
                await new Promise(r => setTimeout(r, 1000));
                const job = await tasksApi.getJob(previewJob.job_id);
                if (job.status === 'success') {
                    previewData = job.result;
                    break;
                }
                if (job.status === 'failed') throw new Error(job.error);
                if (job.status === 'cancelled') throw new Error('任務已取消');
            }

            if (!previewData) throw new Error('Preview timeout');

            // 合併 detail 和 preview 資料
            const mergedItems: DetailItem[] = detailData.items.map((d: any, idx: number) => {
                const preview = previewData.previews[idx] || {};
                // 如果沒有對應模板，自動取消勾選
                const hasNoTemplate = preview.status === 'no_template';
                // 從 payload 取得 diagn 和 diaga (這些是後端計算的預設值)
                const diagn = preview.payload?.diagn || d.pre_op_dx || '';
                const diaga = preview.payload?.diaga || '';
                return {
                    ...d,
                    diagn,   // 術前診斷 (可編輯)
                    diaga,   // 術後診斷 (可編輯)
                    payload: preview.payload,
                    missing_fields: preview.missing_fields,
                    status: preview.status || d.status || 'ready',  // 保留 status
                    selected: hasNoTemplate ? false : true,  // 無模板時自動取消勾選
                    // 儲存原始值用於追蹤編輯
                    _original: {
                        pre_op_dx: d.pre_op_dx || '',
                        op_name: d.op_name || '',
                        op_side: d.op_side || '',
                        op_type: d.op_type || '',
                        col_fields: d.col_fields || {},  // 動態欄位原始值
                        diagn,
                        diaga,
                    },
                };
            });

            // 統計無模板的數量
            const noTemplateCount = mergedItems.filter(i => i.status === 'no_template').length;

            setDetailItems(mergedItems);
            setStep('edit');
            if (noTemplateCount > 0) {
                setStatusMsg(`共 ${mergedItems.length} 筆可編輯，其中 ${noTemplateCount} 筆無對應模板已跳過`);
                setStatusType('info');
            } else {
                setStatusMsg(`共 ${mergedItems.length} 筆可編輯`);
                setStatusType('success');
            }

        } catch (e: any) {
            setStatusMsg(`抓取詳情失敗: ${e.message}`);
            setStatusType('error');
        } finally {
            setLoading(false);
        }
    }, [scheduleItems, date, vsCode, rCode, previewMode, defaultRCode]);

    // =========================================================================
    // Step 3: 送出
    // =========================================================================
    const handleSubmit = useCallback(async () => {
        const selected = detailItems.filter(i => i.selected);
        if (selected.length === 0) {
            setStatusMsg('請選擇要送出的項目');
            setStatusType('error');
            return;
        }

        if (previewMode) {
            setDetailItems(prev => prev.map(item => ({
                ...item,
                status: item.selected ? 'success' : item.status
            })));
            setStatusMsg(`已送出 ${selected.length} 筆`);
            setStatusType('success');
            setStep('done');
            return;
        }

        setLoading(true);
        setStatusMsg('正在送出...');
        setStatusType('info');

        const eipId = localStorage.getItem('user');
        const eipPsw = localStorage.getItem('eip_psw');

        try {
            const submitJob = await tasksApi.run('note_surgery_submit', {
                params: {
                    items: selected.map(i => ({
                        hisno: i.hisno,
                        // 可編輯欄位 (覆蓋値)
                        diagn: i.diagn,
                        op_name: i.op_name,  // 後端會用這個構建 diaga
                        op_side: i.op_side,
                        op_type: i.op_type,
                        col_fields: i.col_fields,  // 動態欄位
                    }))
                },
                eip_id: eipId || undefined,
                eip_psw: eipPsw || undefined
            });

            // 使用 pollJobResult 並顯示進度
            setProgress(0);
            const result = await pollJobResult(submitJob.job_id, {
                onProgress: (p, msg) => {
                    setProgress(p);
                    if (msg) setStatusMsg(msg);
                }
            });

            setStatusMsg(`送出完成: ${result?.success || 0}/${result?.total || 0} 成功`);
            // 如果 success < total，表示有失敗，顯示警告
            setStatusType((result?.success || 0) < (result?.total || 0) ? 'error' : 'success');
            setStep('done');
            setProgress(undefined);

        } catch (e: any) {
            setStatusMsg(`送出失敗: ${e.message}`);
            setStatusType('error');
        } finally {
            setLoading(false);
        }
    }, [detailItems, previewMode]);

    // =========================================================================
    // 操作
    // =========================================================================
    const handleSelectSchedule = (index: number, event?: React.MouseEvent) => {
        if (event?.shiftKey && lastClickedScheduleIndex !== null) {
            // Shift+Click: 選取區間
            const start = Math.min(lastClickedScheduleIndex, index);
            const end = Math.max(lastClickedScheduleIndex, index);
            const targetState = !scheduleItems[index].selected;
            setScheduleItems(prev => prev.map((item, i) =>
                i >= start && i <= end ? { ...item, selected: targetState } : item
            ));
        } else {
            // 普通點擊: 切換單一項目
            setScheduleItems(prev => prev.map((item, i) =>
                i === index ? { ...item, selected: !item.selected } : item
            ));
        }
        setLastClickedScheduleIndex(index);
    };

    const handleSelectAllSchedule = () => {
        const allSelected = scheduleItems.every(i => i.selected);
        setScheduleItems(prev => prev.map(item => ({ ...item, selected: !allSelected })));
    };

    const handleSelectDetail = (index: number) => {
        setDetailItems(prev => prev.map((item, i) => {
            // 無模板的項目不能被勾選
            if (i === index && item.status === 'no_template') return item;
            return i === index ? { ...item, selected: !item.selected } : item;
        }));
    };

    const handleSelectAllDetail = () => {
        // 排除無模板的項目
        const selectableItems = detailItems.filter(i => i.status !== 'no_template');
        const allSelected = selectableItems.length > 0 && selectableItems.every(i => i.selected);
        setDetailItems(prev => prev.map(item => {
            if (item.status === 'no_template') return item;  // 無模板項目保持不勾選
            return { ...item, selected: !allSelected };
        }));
    };

    const updateDetailItem = (index: number, field: keyof DetailItem, value: any) => {
        setDetailItems(prev => prev.map((item, i) => {
            if (i !== index) return item;

            const updated = { ...item, [field]: value };

            // 同步關聯欄位
            // pre_op_dx 編輯時同步更新 diagn
            if (field === 'pre_op_dx') {
                updated.diagn = value;
            }
            // diagn 直接編輯時也更新 pre_op_dx (保持一致)
            if (field === 'diagn') {
                updated.pre_op_dx = value;
            }

            return updated;
        }));
    };

    const handleBatchApply = () => {
        const count = detailItems.filter(i => i.selected).length;
        if (count === 0) {
            setStatusMsg('請先勾選要套用的項目');
            setStatusType('error');
            return;
        }

        setDetailItems(prev => prev.map(item => {
            if (!item.selected) return item;
            return {
                ...item,
                op_side: batchSide || item.op_side,
                op_anesthesia: batchAnesthesia || item.op_anesthesia,
                op_type: batchOpType || item.op_type,
                pre_op_dx: batchPreOpDx || item.pre_op_dx,
                op_name: batchOpName || item.op_name,
                // COL_* 欄位不支援批次編輯，因每筆手術需要的欄位不同
            };
        }));

        // 清空批次編輯欄位
        setBatchSide('');
        setBatchAnesthesia('');
        setBatchOpType('');
        setBatchPreOpDx('');
        setBatchOpName('');

        setStatusMsg(`已套用批次設定到 ${count} 筆`);
        setStatusType('success');
    };

    const handleReset = () => {
        setScheduleItems([]);
        setDetailItems([]);
        setStep('fetch');
        setStatusMsg(null);
    };

    const goToStep = (s: Step) => {
        setStep(s);
        setStatusMsg(null);
    };

    const scheduleSelectedCount = scheduleItems.filter(i => i.selected).length;
    const detailSelectedCount = detailItems.filter(i => i.selected).length;

    // =========================================================================
    // Render
    // =========================================================================
    return (
        <div className="bg-[#F5F5F7] min-h-full flex flex-col p-4 font-sans">
            <div className="relative z-10 w-full max-w-5xl mx-auto my-auto">
                {/* Header */}
                <header className="mb-4">
                    <div className="flex items-end justify-between mb-4">
                        <div className="flex items-center gap-4">
                            <div style={{
                                width: '48px',
                                height: '48px',
                                borderRadius: '14px',
                                background: `linear-gradient(135deg, ${THEME.primaryLight} 0%, #dbeafe 100%)`,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                            }}>
                                <Scissors size={24} color={THEME.primary} />
                            </div>
                            <div>
                                <h2 className="text-2xl font-bold text-gray-900 tracking-tight">Surgery 手術記錄</h2>
                                <p className="text-sm text-gray-500">抓取排程 → 選擇病人 → 確認編輯 → 送出 Web9</p>
                            </div>
                        </div>

                        {/* 信任徽章 */}
                        {!loading && stats && stats.total_items > 0 && (
                            <TrustBadge taskId="note_surgery_submit" totalItems={stats.total_items} />
                        )}
                    </div>

                    {/* Stepper */}
                    <StepIndicator
                        steps={STEPS}
                        currentStepId={step}
                        onStepClick={(stepId) => goToStep(stepId as Step)}
                        disableNavigation={step === 'done'}
                    />
                </header>

                {/* Step 1: 抓取排程 */}
                {step === 'fetch' && (
                    <Card className="shadow-xl backdrop-blur-xl bg-white/70 border border-white/50 p-6">
                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-2">手術排程查詢日期</label>
                                <input
                                    type="date"
                                    value={date}
                                    onChange={e => setDate(e.target.value)}
                                    className="w-full bg-white border border-gray-200 rounded-xl px-4 py-3 text-sm focus:ring-2 focus:border-blue-400"
                                />
                            </div>

                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-2">主治醫師燈號 (VS)</label>
                                <input
                                    type="text"
                                    value={vsCode}
                                    onChange={e => setVsCode(e.target.value)}
                                    onKeyDown={e => {
                                        if (e.key === 'Enter' && !loading && (previewMode || vsCode)) {
                                            handleFetchSchedule();
                                        }
                                    }}
                                    placeholder="例: 4106"
                                    className="w-full bg-white border border-gray-200 rounded-xl px-4 py-3 text-sm font-mono focus:ring-2 focus:border-blue-400"
                                />
                            </div>

                            <Button
                                variant="primary"
                                onClick={handleFetchSchedule}
                                disabled={loading || (!previewMode && !vsCode)}
                                className="w-full shadow-lg h-12 flex items-center justify-center text-base"
                                style={{ backgroundColor: THEME.primary }}
                            >
                                {loading ? (
                                    <>
                                        <Loader2 size={20} className="mr-2 animate-spin" />
                                        抓取中...
                                    </>
                                ) : (
                                    <>
                                        <Calendar size={20} className="mr-2" />
                                        抓取排程
                                    </>
                                )}
                            </Button>
                        </div>
                    </Card>
                )}

                {/* Step 2: 選擇病人 */}
                {step === 'select' && (
                    <div className="space-y-4">
                        {/* 操作區 */}
                        <Card noPadding className="shadow-xl backdrop-blur-xl bg-white/70 border border-white/50 p-3">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-4">
                                    <div className="rounded-xl px-4 py-1.5" style={{ backgroundColor: THEME.primaryLight }}>
                                        <span className="text-sm text-gray-600">
                                            已選擇 <span className="font-bold text-lg" style={{ color: THEME.primary }}>{scheduleSelectedCount}</span> / {scheduleItems.length} 位病人
                                        </span>
                                    </div>
                                    {/* 刀表設定資訊 */}
                                    {doctorSheetInfo && (
                                        <div className="flex items-center gap-2">
                                            {doctorSheetInfo.configured ? (
                                                <button
                                                    onClick={() => onNavigate?.('sheets_settings')}
                                                    className="flex items-center gap-2 text-xs text-gray-600 hover:text-blue-600 transition-colors px-3 py-1.5 rounded-lg border border-gray-200 bg-gray-50 hover:bg-blue-50 hover:border-blue-200"
                                                    title="點擊前往 Google 刀表設定"
                                                >
                                                    <span className="font-medium">Google刀表:</span>
                                                    <span className="text-gray-700 font-medium">{doctorSheetInfo.worksheet}</span>
                                                    <span className="text-gray-400 font-mono text-[10px]">({doctorSheetInfo.sheet_id?.substring(0, 8)}...)</span>
                                                    <ExternalLink size={12} className="text-gray-400" />
                                                </button>
                                            ) : (
                                                <button
                                                    onClick={() => onNavigate?.('sheets_settings')}
                                                    className="flex items-center gap-2 text-xs text-orange-600 hover:text-orange-700 transition-colors px-3 py-1.5 rounded-lg bg-orange-50 hover:bg-orange-100"
                                                >
                                                    <AlertCircle size={14} />
                                                    <span>尚未設定 Google 刀表，點擊前往設定</span>
                                                </button>
                                            )}
                                        </div>
                                    )}
                                </div>
                                <div className="flex items-center gap-3">
                                    <Button variant="secondary" onClick={() => goToStep('fetch')} className="px-4">
                                        <ChevronLeft size={16} className="mr-1" /> 上一步
                                    </Button>
                                    <Button
                                        variant="primary"
                                        onClick={handleFetchDetails}
                                        disabled={scheduleSelectedCount === 0 || loading}
                                        style={{ backgroundColor: THEME.primary }}
                                        className="px-6"
                                    >
                                        {loading ? (
                                            <>
                                                <Loader2 size={16} className="mr-2 animate-spin" />
                                                {fetchProgress !== undefined ? `爬取中... (${fetchProgress}%)` : '爬取詳情...'}
                                            </>
                                        ) : (
                                            <>
                                                下一步：爬取詳情 <Check size={16} className="ml-1" />
                                            </>
                                        )}
                                    </Button>
                                </div>
                            </div>
                        </Card>

                        {/* 排程表格 */}
                        <Card className="overflow-hidden shadow-2xl backdrop-blur-xl bg-white/40 border border-white/60 p-0">
                            <div className="overflow-auto max-h-[60vh]">
                                <table className="w-full text-left border-collapse min-w-[900px]">
                                    <thead>
                                        <tr className="bg-white/80 border-b border-white/40 text-gray-600 text-xs font-bold uppercase sticky top-0 z-10">
                                            <th className="p-3 w-12 text-center">
                                                <button
                                                    onClick={handleSelectAllSchedule}
                                                    className="w-6 h-6 rounded flex items-center justify-center transition-all mx-auto"
                                                    style={{
                                                        backgroundColor: scheduleItems.every(i => i.selected) ? THEME.primary : '#e5e7eb',
                                                        color: scheduleItems.every(i => i.selected) ? 'white' : '#9ca3af',
                                                    }}
                                                >
                                                    <Check size={14} />
                                                </button>
                                            </th>
                                            <th className="p-3">手術日期</th>
                                            <th className="p-3">手術時間</th>
                                            <th className="p-3">病歷號</th>
                                            <th className="p-3 whitespace-nowrap">姓名</th>
                                            <th className="p-3">開刀房號</th>
                                            <th className="p-3 max-w-24">術前診斷</th>
                                            <th className="p-3 min-w-48">手術名稱</th>
                                            <th className="p-3">手術室資訊</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-white/20">
                                        {scheduleItems.map((item, i) => (
                                            <tr
                                                key={i}
                                                className="transition-all hover:bg-white/30"
                                                style={{
                                                    backgroundColor: item.selected ? 'rgba(19, 127, 236, 0.05)' : 'transparent',
                                                }}
                                            >
                                                <td className="p-3 text-center">
                                                    <input
                                                        type="checkbox"
                                                        checked={item.selected}
                                                        onChange={() => { }} // 由 onClick 處理
                                                        onClick={(e) => handleSelectSchedule(i, e)}
                                                        className="w-4 h-4 rounded border-gray-300"
                                                        style={{ accentColor: THEME.primary }}
                                                    />
                                                </td>
                                                <td className="p-3 text-sm text-gray-600">{item.op_date}</td>
                                                <td className="p-3 text-sm">{item.op_time}</td>
                                                <td className="p-3 font-mono text-sm text-gray-600">{item.hisno}</td>
                                                <td className="p-3 font-semibold whitespace-nowrap">{item.name}</td>
                                                <td className="p-3 text-sm">{item.op_room}</td>
                                                <td className="p-3 text-sm text-gray-600 max-w-24" title={item.pre_op_dx}>{item.pre_op_dx}</td>
                                                <td className="p-3 text-sm text-gray-600 min-w-48" title={item.op_name}>{item.op_name}</td>
                                                <td className="p-3 text-sm text-gray-500">{item.op_room_info}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </Card>
                    </div>
                )}

                {/* Step 3: 確認編輯 */}
                {step === 'edit' && (
                    <div className="space-y-4">
                        {/* 送出確認區 */}
                        <Card noPadding className="shadow-xl backdrop-blur-xl bg-white/70 border border-white/50 p-3">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-4">
                                    <div className="rounded-xl px-4 py-1.5" style={{ backgroundColor: THEME.primaryLight }}>
                                        <span className="text-sm text-gray-600">
                                            已選擇 <span className="font-bold text-lg" style={{ color: THEME.primary }}>{detailSelectedCount}</span> / {detailItems.length} 筆
                                        </span>
                                    </div>
                                </div>
                                <div className="flex items-center gap-3">
                                    <Button variant="secondary" onClick={() => goToStep('select')} className="px-4">
                                        <ChevronLeft size={16} className="mr-1" /> 上一步
                                    </Button>
                                    <Button
                                        variant="primary"
                                        onClick={handleSubmit}
                                        disabled={detailSelectedCount === 0 || loading}
                                        style={{ backgroundColor: THEME.primary }}
                                        className="px-6"
                                    >
                                        {loading ? (
                                            <>
                                                <Loader2 size={16} className="mr-2 animate-spin" />
                                                送出中...{progress !== undefined && ` (${progress}%)`}
                                            </>
                                        ) : (
                                            <>
                                                確認送出 ({detailSelectedCount} 筆) <Check size={16} className="ml-1" />
                                            </>
                                        )}
                                    </Button>
                                </div>
                            </div>
                        </Card>

                        {/* 詳情表格 (精簡版 + 填充資訊子列) */}
                        <Card className="overflow-hidden shadow-2xl backdrop-blur-xl bg-white/40 border border-white/60 p-0">
                            <div className="overflow-auto max-h-[60vh]">
                                <table className="w-full text-left border-collapse min-w-[800px]">
                                    <thead>
                                        {/* 批次編輯列 */}
                                        <tr className="bg-blue-50/80 border-b border-blue-100 sticky top-0 z-20">
                                            <th className="p-2 w-12"></th>
                                            <th className="p-2 w-20">
                                                <Button
                                                    variant="primary"
                                                    size="sm"
                                                    onClick={handleBatchApply}
                                                    disabled={detailSelectedCount === 0}
                                                    style={{ backgroundColor: THEME.primary }}
                                                    className="w-full text-xs whitespace-nowrap"
                                                >
                                                    圈選多筆套用
                                                </Button>
                                            </th>
                                            <th className="p-2 w-20"></th>
                                            <th className="p-2 w-24"></th>
                                            <th className="p-2">
                                                <input
                                                    type="text"
                                                    value={batchPreOpDx}
                                                    onChange={e => setBatchPreOpDx(e.target.value)}
                                                    className="w-full bg-white border border-gray-200 rounded px-2 py-1 text-xs"
                                                    placeholder="批次診斷"
                                                />
                                            </th>
                                            <th className="p-2">
                                                <input
                                                    type="text"
                                                    value={batchOpName}
                                                    onChange={e => setBatchOpName(e.target.value)}
                                                    className="w-full bg-white border border-gray-200 rounded px-2 py-1 text-xs"
                                                    placeholder="批次手術名稱"
                                                />
                                            </th>
                                            <th className="p-2 w-14">
                                                <select
                                                    value={batchSide}
                                                    onChange={e => setBatchSide(e.target.value)}
                                                    className="w-full bg-white border border-gray-200 rounded px-2 py-1 text-xs"
                                                >
                                                    <option value="">側別</option>
                                                    <option value="OD">OD</option>
                                                    <option value="OS">OS</option>
                                                    <option value="OU">OU</option>
                                                </select>
                                            </th>
                                            <th className="p-2">
                                                <select
                                                    value={batchOpType}
                                                    onChange={e => setBatchOpType(e.target.value)}
                                                    className="w-full bg-white border border-gray-200 rounded px-2 py-1 text-xs"
                                                >
                                                    <option value="">範本類型</option>
                                                    {opTypes.map(t => <option key={t} value={t}>{t}</option>)}
                                                </select>
                                            </th>
                                        </tr>
                                        {/* 表頭 */}
                                        <tr className="bg-white/80 border-b border-white/40 text-gray-600 text-xs font-bold uppercase sticky top-[41px] z-10">
                                            <th className="p-3 w-12 text-center">
                                                <button
                                                    onClick={handleSelectAllDetail}
                                                    className="w-6 h-6 rounded flex items-center justify-center transition-all mx-auto"
                                                    style={{
                                                        backgroundColor: detailItems.every(i => i.selected) ? THEME.primary : '#e5e7eb',
                                                        color: detailItems.every(i => i.selected) ? 'white' : '#9ca3af',
                                                    }}
                                                >
                                                    <Check size={14} />
                                                </button>
                                            </th>
                                            <th className="p-3 w-20">病歷號</th>
                                            <th className="p-3 w-20">姓名</th>
                                            <th className="p-3 w-24">手術室資訊</th>
                                            <th className="p-3">術前診斷</th>
                                            <th className="p-3">手術名稱</th>
                                            <th className="p-3 w-14">側別</th>
                                            <th className="p-3 min-w-[90px]">
                                                範本類型<span className="text-blue-600">⚠請確認</span>
                                            </th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {detailItems.map((item, i) => (
                                            <React.Fragment key={i}>
                                                {/* 主資料列 */}
                                                <tr
                                                    className="transition-all"
                                                    style={{
                                                        backgroundColor: item.status === 'no_template'
                                                            ? 'rgba(239, 68, 68, 0.1)'  // 紅色背景表示無模板
                                                            : item.selected
                                                                ? 'transparent'
                                                                : THEME.disabled,
                                                        opacity: item.status === 'no_template' ? 0.7 : item.selected ? 1 : 0.5,
                                                    }}
                                                >
                                                    <td className="p-3 text-center" rowSpan={2}>
                                                        {item.status === 'no_template' ? (
                                                            <span className="text-red-500 text-xs font-bold" title="無對應手術模板，無法送出">
                                                                ✕
                                                            </span>
                                                        ) : (
                                                            <input
                                                                type="checkbox"
                                                                checked={item.selected}
                                                                onChange={() => handleSelectDetail(i)}
                                                                className="w-4 h-4 rounded border-gray-300"
                                                                style={{ accentColor: THEME.primary }}
                                                            />
                                                        )}
                                                    </td>
                                                    {/* 唯讀欄位 */}
                                                    <td className="p-3 font-mono text-sm text-gray-600">{item.hisno}</td>
                                                    <td className="p-3 font-semibold text-sm">{item.name}</td>
                                                    <td className="p-3 text-sm text-gray-500">{item.op_room_info}</td>
                                                    {/* 可編輯欄位 */}
                                                    <td className="p-3">
                                                        <input
                                                            value={item.pre_op_dx}
                                                            onChange={e => updateDetailItem(i, 'pre_op_dx', e.target.value)}
                                                            disabled={!item.selected}
                                                            className="w-full bg-transparent hover:bg-white/50 focus:bg-white focus:ring-1 rounded px-2 py-1 text-sm transition-all disabled:cursor-not-allowed"
                                                            style={{
                                                                border: item._original && item.pre_op_dx !== item._original.pre_op_dx
                                                                    ? '2px solid #86efac' : 'none'
                                                            }}
                                                        />
                                                    </td>
                                                    <td className="p-3">
                                                        <input
                                                            value={item.op_name}
                                                            onChange={e => updateDetailItem(i, 'op_name', e.target.value)}
                                                            disabled={!item.selected}
                                                            className="w-full bg-transparent hover:bg-white/50 focus:bg-white focus:ring-1 rounded px-2 py-1 text-sm transition-all disabled:cursor-not-allowed"
                                                            style={{
                                                                border: item._original && item.op_name !== item._original.op_name
                                                                    ? '2px solid #86efac' : 'none'
                                                            }}
                                                        />
                                                    </td>
                                                    <td className="p-3">
                                                        <select
                                                            value={item.op_side}
                                                            onChange={e => updateDetailItem(i, 'op_side', e.target.value)}
                                                            disabled={!item.selected}
                                                            className="bg-transparent hover:bg-white/50 focus:ring-1 rounded px-2 py-1 text-sm transition-all disabled:cursor-not-allowed"
                                                            style={{
                                                                border: item._original && item.op_side !== item._original.op_side
                                                                    ? '2px solid #86efac' : 'none'
                                                            }}
                                                        >
                                                            <option value="OD">OD</option>
                                                            <option value="OS">OS</option>
                                                            <option value="OU">OU</option>
                                                        </select>
                                                    </td>
                                                    <td className="p-3">
                                                        <select
                                                            value={item.op_type}
                                                            onChange={e => updateDetailItem(i, 'op_type', e.target.value)}
                                                            disabled={!item.selected}
                                                            className="w-full bg-transparent hover:bg-white/50 focus:ring-1 rounded px-2 py-1 text-sm transition-all disabled:cursor-not-allowed"
                                                            style={{
                                                                border: '2px solid #3b82f6',
                                                                backgroundColor: 'rgba(59, 130, 246, 0.05)',
                                                            }}
                                                        >
                                                            {opTypes.map(t => <option key={t} value={t}>{t}</option>)}
                                                        </select>
                                                    </td>
                                                </tr>
                                                {/* 填充資訊子列 */}
                                                <tr
                                                    className="transition-all border-b-2 border-gray-300"
                                                    style={{
                                                        backgroundColor: item.selected ? 'rgba(238, 244, 253, 0.5)' : THEME.disabled,
                                                        opacity: item.selected ? 1 : 0.5,
                                                    }}
                                                >
                                                    <td colSpan={7} className="px-3 py-2">
                                                        <div className="flex items-center gap-4 text-xs flex-wrap">
                                                            {(item.editable_fields?.length > 0) ? (
                                                                <>
                                                                    <span className="text-gray-500 font-medium">填充資訊:</span>
                                                                    {item.editable_fields.map(field => {
                                                                        // 欄位標籤對應 (移除 COL_ 前綴顯示)
                                                                        const FIELD_LABELS: Record<string, string> = {
                                                                            'IOL': 'IOL', 'FINAL': 'Final', 'TARGET': 'Target',
                                                                            'SN': 'SN', 'CDE': 'CDE', 'COMPLICATIONS': '併發症',
                                                                            'LENSX': 'LenSx', 'LASER_WATT': '雷射瓦數', 'LASER_SPOT': '雷射數量'
                                                                        };
                                                                        const currentVal = item.col_fields?.[field] || '';
                                                                        const originalVal = item._original?.col_fields?.[field] || '';
                                                                        const isEdited = currentVal !== originalVal;

                                                                        return (
                                                                            <div key={field} className="flex items-center gap-1">
                                                                                <label className="text-gray-500 whitespace-nowrap">{FIELD_LABELS[field] || field}</label>
                                                                                <input
                                                                                    value={currentVal}
                                                                                    onChange={e => {
                                                                                        // 更新 col_fields 中的特定欄位
                                                                                        setDetailItems(prev => prev.map((it, idx) => {
                                                                                            if (idx !== i) return it;
                                                                                            return {
                                                                                                ...it,
                                                                                                col_fields: { ...it.col_fields, [field]: e.target.value }
                                                                                            };
                                                                                        }));
                                                                                    }}
                                                                                    disabled={!item.selected}
                                                                                    className="w-24 bg-white/70 hover:bg-white focus:bg-white focus:ring-1 rounded px-2 py-1 text-sm transition-all disabled:cursor-not-allowed"
                                                                                    style={{
                                                                                        border: isEdited ? '2px solid #86efac' : '1px solid #e5e7eb'
                                                                                    }}
                                                                                />
                                                                            </div>
                                                                        );
                                                                    })}
                                                                </>
                                                            ) : (
                                                                <span className="text-gray-400 italic">此手術類型無填充欄位</span>
                                                            )}
                                                        </div>
                                                    </td>
                                                </tr>
                                            </React.Fragment>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </Card>
                    </div>
                )}

                {/* Step 4: 完成 */}
                {step === 'done' && (
                    <Card className="shadow-xl backdrop-blur-xl bg-white/70 border border-white/50 p-8 text-center">
                        {statusType === 'success' ? (
                            <div
                                className="w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4"
                                style={{ backgroundColor: THEME.successLight }}
                            >
                                <Check size={32} style={{ color: THEME.success }} />
                            </div>
                        ) : (
                            <div
                                className="w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4"
                                style={{ backgroundColor: '#fff3cd' }}
                            >
                                <AlertCircle size={32} style={{ color: '#f59e0b' }} />
                            </div>
                        )}
                        <h3 className="text-xl font-bold text-gray-900 mb-2">
                            {statusType === 'success' ? '送出完成' : '部分送出異常'}
                        </h3>
                        <p className={`mb-6 ${statusType === 'success' ? 'text-gray-500' : 'text-amber-600'}`}>
                            {statusMsg}
                        </p>
                        <Button variant="primary" onClick={handleReset} style={{ backgroundColor: THEME.primary }}>
                            開始新的作業
                        </Button>
                    </Card>
                )}

                {/* Toast 通知 */}
                {statusMsg && step !== 'done' && (
                    <Toast
                        message={statusMsg}
                        type={statusType}
                        duration={5000}
                        onClose={() => setStatusMsg(null)}
                    />
                )}
            </div>
        </div >
    );
}

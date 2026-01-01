import React, { useState, useCallback } from 'react';
import { Syringe, Calendar, ChevronLeft, Check, Loader2, ChevronDown, ChevronUp } from 'lucide-react';
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
import { MOCK_ITEMS } from '../mocks/iviMocks';
import type { IviScheduleItem } from '../mocks/iviMocks';

// Type is imported from mocks/iviMocks.ts
export type { IviScheduleItem } from '../mocks/iviMocks';

// 步驟定義 (簡化為 3 步)
type Step = 'fetch' | 'edit' | 'done';
const STEPS: { id: Step; label: string }[] = [
    { id: 'fetch', label: '抓取排程' },
    { id: 'edit', label: '確認送出' },
    { id: 'done', label: '完成' },
];

export const IviPage: React.FC = () => {
    const { } = useAuth(); // Keep useAuth for future use
    const { stats } = useTaskStats('note_ivi_submit');

    // Demo 模式 (使用模擬資料，由 config.ts 控制)
    const [previewMode] = useState(DEMO_MODE);

    // 日期
    const now = new Date();
    const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
    const [useCustomRange, setUseCustomRange] = useState(false);
    const [startDate, setStartDate] = useState(today);
    const [endDate, setEndDate] = useState(today);

    // 資料狀態
    const [items, setItems] = useState<IviScheduleItem[]>([]);
    const [loading, setLoading] = useState(false);
    const [progress, setProgress] = useState<number | undefined>(undefined);
    const [statusMsg, setStatusMsg] = useState<string | null>(null);
    const [statusType, setStatusType] = useState<'info' | 'success' | 'error'>('info');
    const [lastClickedIndex, setLastClickedIndex] = useState<number | null>(null);

    // 步驟控制
    const [currentStep, setCurrentStep] = useState<Step>('fetch');

    // 批次編輯狀態
    const [batchDiagnosis, setBatchDiagnosis] = useState('');
    const [batchSide, setBatchSide] = useState('');
    const [batchDrug, setBatchDrug] = useState('');
    const [batchVsCode, setBatchVsCode] = useState('');

    // 助手登號 (獨立，送出時使用)
    const loginEipId = localStorage.getItem('user') || '';
    const defaultRCode = loginEipId.match(/\d{4}/)?.[0] || '';
    const [rCode, setRCode] = useState(defaultRCode);
    const [rName, setRName] = useState('');

    // Demo 模式：使用 Mock 資料 (顯示訊息與正常模式相同)
    const loadMockData = () => {
        const mockData = MOCK_ITEMS.map(item => ({ ...item }));
        setItems(mockData);
        setCurrentStep('edit');
        setStatusMsg(`找到 ${mockData.length} 筆排程`);
        setStatusType('success');
    };

    // Step 1: 抓取排程
    const handleFetch = useCallback(async () => {
        if (previewMode) {
            loadMockData();
            return;
        }

        setLoading(true);
        setStatusMsg(null);

        const eipId = localStorage.getItem('user');
        const eipPsw = localStorage.getItem('eip_psw');

        try {
            const data = await tasksApi.run('ivi_fetch', {
                params: {
                    start_date: startDate,
                    end_date: useCustomRange ? endDate : startDate
                },
                eip_id: eipId || undefined,
                eip_psw: eipPsw || undefined
            });

            const pollResult = async (): Promise<any> => {
                for (let i = 0; i < 30; i++) {
                    await new Promise(r => setTimeout(r, 1000));
                    const jobData = await tasksApi.getJob(data.job_id);
                    if (jobData.status === 'success') return jobData.result;
                    if (jobData.status === 'failed') throw new Error(jobData.error);
                    if (jobData.status === 'cancelled') throw new Error('任務已取消');
                }
                throw new Error('Timeout');
            };

            const result = await pollResult();

            if (result.count > 0) {
                const fetchedItems = result.data.map((item: IviScheduleItem) => ({
                    ...item,
                    selected: true,
                    status: 'pending' as const,
                    // 儲存原始值用於追蹤編輯
                    _original: {
                        vs_code: item.vs_code,
                        vs_name: item.vs_name,
                        diagnosis: item.diagnosis,
                        side: item.side,
                        drug: item.drug,
                    },
                }));
                setItems(fetchedItems);
                setCurrentStep('edit');
                setStatusMsg(`抓取完成，共 ${result.count} 筆`);
                setStatusType('success');
            } else {
                setStatusMsg(result.message || '該日期沒有 IVI 排程');
                setStatusType('info');
                setItems([]);
            }
        } catch (e: any) {
            setStatusMsg(`抓取失敗: ${e.message}`);
            setStatusType('error');
        } finally {
            setLoading(false);
        }
    }, [startDate, endDate, useCustomRange, previewMode]);

    // 送出
    const handleSubmit = useCallback(async () => {
        const selectedItems = items.filter(i => i.selected);
        if (selectedItems.length === 0) {
            setStatusMsg('請先選擇要送出的項目');
            setStatusType('error');
            return;
        }

        if (!rCode) {
            setStatusMsg('請輸入助手登號');
            setStatusType('error');
            return;
        }

        if (previewMode) {
            setItems(prev => prev.map(item => ({
                ...item,
                status: item.selected ? 'success' : item.status
            })));
            setStatusMsg(`已送出 ${selectedItems.length} 筆`);
            setStatusType('success');
            setCurrentStep('done');
            return;
        }

        setLoading(true);
        setStatusMsg('正在建構 Payload...');
        setStatusType('info');

        const eipId = localStorage.getItem('user');
        const eipPsw = localStorage.getItem('eip_psw');

        try {
            const previewJob = await tasksApi.run('opnote_preview', {
                params: {
                    source_type: 'ivi',
                    vs_code: selectedItems[0].vs_code,
                    r_code: rCode,
                    date: startDate,
                    eip_id: eipId,
                    items: selectedItems.map(item => ({
                        hisno: item.hisno,
                        name: item.name,
                        diagnosis: item.diagnosis,
                        side: item.side,
                        drug: item.drug,
                        charge_type: item.charge_type,
                        op_start: item.op_start,
                        op_end: item.op_end,
                        vs_code: item.vs_code,
                        vs_name: item.vs_name,
                        r_code: rCode,
                        r_name: rName,
                    }))
                },
                eip_id: eipId || undefined,
                eip_psw: eipPsw || undefined
            });

            setStatusMsg('正在準備資料...');
            let previewData: any = null;
            for (let i = 0; i < 30; i++) {
                await new Promise(r => setTimeout(r, 1000));
                const jobData = await tasksApi.getJob(previewJob.job_id);
                if (jobData.status === 'success') {
                    previewData = jobData.result;
                    break;
                }
                if (jobData.status === 'failed') throw new Error(jobData.error);
                if (jobData.status === 'cancelled') throw new Error('任務已取消');
            }

            if (!previewData) throw new Error('Preview timeout');

            setStatusMsg('正在送出...');
            setProgress(0);
            const submitJob = await tasksApi.run('opnote_submit', {
                params: {
                    items: previewData.previews?.map((p: any) => ({
                        hisno: p.hisno,
                        payload: p.payload
                    })) || [],
                    force_mock: false
                },
                eip_id: eipId || undefined,
                eip_psw: eipPsw || undefined
            });

            // 使用 pollJobResult 並顯示進度
            const result = await pollJobResult(submitJob.job_id, {
                onProgress: (p, msg) => {
                    setProgress(p);
                    if (msg) setStatusMsg(msg);
                }
            });

            setStatusMsg(`送出完成: ${result?.success || 0}/${result?.total || 0} 成功`);
            setStatusType('success');
            setItems(prev => prev.map(item => ({
                ...item,
                status: item.selected ? 'success' : item.status
            })));
            setCurrentStep('done');
            setProgress(undefined);
        } catch (e: any) {
            setStatusMsg(`送出失敗: ${e.message}`);
            setStatusType('error');
        } finally {
            setLoading(false);
        }
    }, [items, rCode, startDate, previewMode]);

    // 操作函數
    const handleSelectAll = () => {
        const allSelected = items.every(i => i.selected);
        setItems(prev => prev.map(item => ({ ...item, selected: !allSelected })));
    };

    const handleSelectItem = (index: number, event?: React.MouseEvent) => {
        if (event?.shiftKey && lastClickedIndex !== null) {
            // Shift+Click: 選取區間
            const start = Math.min(lastClickedIndex, index);
            const end = Math.max(lastClickedIndex, index);
            const targetState = !items[index].selected;
            setItems(prev => prev.map((item, i) =>
                i >= start && i <= end ? { ...item, selected: targetState } : item
            ));
        } else {
            // 普通點擊: 切換單一項目
            setItems(prev => prev.map((item, i) =>
                i === index ? { ...item, selected: !item.selected } : item
            ));
        }
        setLastClickedIndex(index);
    };

    const updateItem = (index: number, field: keyof IviScheduleItem, value: string) => {
        setItems(prev => prev.map((item, i) =>
            i === index ? { ...item, [field]: value } : item
        ));
    };

    const handleReset = () => {
        setItems([]);
        setCurrentStep('fetch');
        setStatusMsg(null);
    };

    // 批次套用 (套用後清空欄位)
    const handleBatchApply = () => {
        const count = items.filter(i => i.selected).length;
        if (count === 0) {
            setStatusMsg('請先勾選要套用的項目');
            setStatusType('error');
            return;
        }

        setItems(prev => prev.map(item => {
            if (!item.selected) return item;
            return {
                ...item,
                diagnosis: batchDiagnosis || item.diagnosis,
                side: batchSide || item.side,
                drug: batchDrug || item.drug,
                vs_code: batchVsCode || item.vs_code,
                vs_name: batchVsCode ? '' : item.vs_name,
            };
        }));

        // 清空批次編輯欄位
        setBatchDiagnosis('');
        setBatchSide('');
        setBatchDrug('');
        setBatchVsCode('');

        setStatusMsg(`已套用批次設定到 ${count} 筆`);
        setStatusType('success');
    };

    const goToStep = (step: Step) => {
        setCurrentStep(step);
        setStatusMsg(null);
    };

    const selectedCount = items.filter(i => i.selected).length;

    return (
        <div className="bg-[#F5F5F7] p-4 min-h-full flex flex-col font-sans">


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
                                <Syringe size={24} color={THEME.primary} />
                            </div>
                            <div>
                                <h2 className="text-2xl font-bold text-gray-900 tracking-tight">IVI 注射記錄</h2>
                                <p className="text-sm text-gray-500">抓取IVI排程 → 確認編輯 → 送出至 Web9</p>
                            </div>
                        </div>

                        {/* 信任徽章 */}
                        {!loading && stats && stats.total_items > 0 && (
                            <TrustBadge taskId="note_ivi_submit" totalItems={stats.total_items} />
                        )}
                    </div>

                    {/* Stepper */}
                    <StepIndicator
                        steps={STEPS}
                        currentStepId={currentStep}
                        onStepClick={(stepId) => goToStep(stepId as Step)}
                        disableNavigation={currentStep === 'done'}
                    />
                </header>

                {/* Step 1: 抓取排程 */}
                {currentStep === 'fetch' && (
                    <Card className="shadow-xl backdrop-blur-xl bg-white/70 border border-white/50 p-6">
                        <div className="mb-6">
                            <div className="flex items-center justify-between mb-3">
                                <label className="text-sm font-semibold text-gray-700">查詢日期</label>
                                <button
                                    onClick={() => setUseCustomRange(!useCustomRange)}
                                    className="flex items-center gap-1 text-xs transition-colors"
                                    style={{ color: THEME.primary }}
                                >
                                    {useCustomRange ? '使用單日' : '日期範圍'}
                                    {useCustomRange ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                                </button>
                            </div>

                            {!useCustomRange ? (
                                <input
                                    type="date"
                                    value={startDate}
                                    onChange={e => setStartDate(e.target.value)}
                                    className="w-full bg-white border border-gray-200 rounded-xl px-4 py-3 text-sm focus:ring-2 focus:border-blue-400"
                                />
                            ) : (
                                <div className="flex items-center gap-3">
                                    <input
                                        type="date"
                                        value={startDate}
                                        onChange={e => setStartDate(e.target.value)}
                                        className="flex-1 bg-white border border-gray-200 rounded-xl px-4 py-3 text-sm focus:ring-2"
                                    />
                                    <span className="text-gray-400">~</span>
                                    <input
                                        type="date"
                                        value={endDate}
                                        onChange={e => setEndDate(e.target.value)}
                                        className="flex-1 bg-white border border-gray-200 rounded-xl px-4 py-3 text-sm focus:ring-2"
                                    />
                                </div>
                            )}
                        </div>

                        <Button
                            variant="primary"
                            onClick={handleFetch}
                            disabled={loading}
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
                    </Card>
                )}

                {/* Step 2: 確認編輯與送出 */}
                {currentStep === 'edit' && (
                    <div className="space-y-4">
                        {/* 送出確認區 */}
                        <Card noPadding className="shadow-xl backdrop-blur-xl bg-white/70 border border-white/50 p-3">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-4">
                                    <div className="rounded-xl px-4 py-1.5" style={{ backgroundColor: THEME.primaryLight }}>
                                        <span className="text-sm text-gray-600">
                                            已選擇 <span className="font-bold text-lg" style={{ color: THEME.primary }}>{selectedCount}</span> / {items.length} 筆
                                        </span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <span className="text-sm text-gray-500">助手登號</span>
                                        <div className="relative flex items-center gap-2">
                                            <input
                                                type="text"
                                                value={rCode}
                                                onChange={async e => {
                                                    const code = e.target.value.replace(/\D/g, '').slice(0, 4);
                                                    setRCode(code);
                                                    // 清除舊的姓名
                                                    setRName('');
                                                    // 當輸入4位數時自動查詢姓名
                                                    if (code.length === 4) {
                                                        const { lookupDoctorName } = await import('../api/tasks');
                                                        const name = await lookupDoctorName(code);
                                                        if (name) {
                                                            setRName(name);
                                                        }
                                                    }
                                                }}
                                                className={`w-16 bg-white border rounded-lg px-2 py-2 text-sm font-mono text-center focus:ring-2 transition-all ${!rCode && selectedCount > 0
                                                    ? 'border-red-300 focus:ring-red-500/50 animate-pulse'
                                                    : 'border-gray-200 focus:ring-blue-500/50'
                                                    }`}
                                                placeholder="必填"
                                                maxLength={4}
                                            />
                                            {rName && (
                                                <span className="text-sm text-gray-600 whitespace-nowrap">{rName}</span>
                                            )}
                                            {!rCode && selectedCount > 0 && (
                                                <span className="text-xs text-red-500 whitespace-nowrap">
                                                    ⚠ 必填
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                </div>
                                <div className="flex items-center gap-3">
                                    <Button variant="secondary" onClick={() => goToStep('fetch')} className="px-4">
                                        <ChevronLeft size={16} className="mr-1" /> 上一步
                                    </Button>
                                    <Button
                                        variant="primary"
                                        onClick={handleSubmit}
                                        disabled={selectedCount === 0 || loading || !rCode}
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
                                                確認送出 ({selectedCount} 筆) <Check size={16} className="ml-1" />
                                            </>
                                        )}
                                    </Button>
                                </div>
                            </div>
                        </Card>

                        {/* 表格 (可滾動，高度限制 60vh，表頭固定) */}
                        <Card className="overflow-hidden shadow-2xl backdrop-blur-xl bg-white/40 border border-white/60 p-0">
                            <div className="overflow-auto max-h-[60vh]">
                                <table className="w-full text-left border-collapse min-w-[800px]">
                                    {/* 批次編輯列 (與表頭對齊) */}
                                    <thead>
                                        <tr className="bg-blue-50/80 border-b border-blue-100 sticky top-0 z-20">
                                            <th className="p-2 w-12"></th>
                                            <th className="p-2 w-20">
                                                <Button
                                                    variant="primary"
                                                    size="sm"
                                                    onClick={handleBatchApply}
                                                    disabled={selectedCount === 0}
                                                    style={{ backgroundColor: THEME.primary }}
                                                    className="w-full text-xs whitespace-nowrap"
                                                >
                                                    圈選多筆套用
                                                </Button>
                                            </th>
                                            <th className="p-2 w-20"></th>
                                            <th className="p-2">
                                                <input
                                                    type="text"
                                                    value={batchDiagnosis}
                                                    onChange={e => setBatchDiagnosis(e.target.value)}
                                                    className="w-full bg-white border border-gray-200 rounded px-2 py-1 text-xs"
                                                    placeholder="批次診斷"
                                                />
                                            </th>
                                            <th className="p-2 w-20">
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
                                                <input
                                                    type="text"
                                                    value={batchDrug}
                                                    onChange={e => setBatchDrug(e.target.value)}
                                                    className="w-full bg-white border border-gray-200 rounded px-2 py-1 text-xs"
                                                    placeholder="批次藥物"
                                                />
                                            </th>
                                            <th className="p-2">
                                                <input
                                                    type="text"
                                                    value={batchVsCode}
                                                    onChange={e => setBatchVsCode(e.target.value)}
                                                    className="w-full bg-white border border-gray-200 rounded px-2 py-1 text-xs font-mono text-center"
                                                    placeholder="醫師登號"
                                                    maxLength={4}
                                                />
                                            </th>
                                            <th className="p-2"></th>
                                        </tr>
                                        <tr className="bg-white/80 border-b border-white/40 text-gray-600 text-xs font-bold uppercase sticky top-[41px] z-10">
                                            <th className="p-3 w-12 text-center">
                                                <button
                                                    onClick={handleSelectAll}
                                                    className="w-6 h-6 rounded flex items-center justify-center transition-all mx-auto"
                                                    style={{
                                                        backgroundColor: items.every(i => i.selected) ? THEME.primary : '#e5e7eb',
                                                        color: items.every(i => i.selected) ? 'white' : '#9ca3af',
                                                    }}
                                                    title={items.every(i => i.selected) ? '取消全選' : '全選'}
                                                >
                                                    <Check size={14} />
                                                </button>
                                            </th>
                                            <th className="p-3" style={{ width: '90px' }}>病歷號</th>
                                            <th className="p-3" style={{ width: '70px' }}>姓名</th>
                                            <th className="p-3" style={{ minWidth: '100px', width: '15%' }}>診斷</th>
                                            <th className="p-3" style={{ width: '60px' }}>側別</th>
                                            <th className="p-3" style={{ minWidth: '140px', width: '25%' }}>藥物</th>
                                            <th className="p-3 whitespace-nowrap" style={{ width: '70px' }}>醫師登號</th>
                                            <th className="p-3 whitespace-nowrap" style={{ width: '70px' }}>醫師姓名</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-white/20">
                                        {items.map((item, i) => (
                                            <tr
                                                key={i}
                                                className="transition-all"
                                                style={{
                                                    backgroundColor: item.selected ? 'transparent' : THEME.disabled,
                                                    opacity: item.selected ? 1 : 0.5,
                                                }}
                                            >
                                                <td className="p-3 text-center">
                                                    <input
                                                        type="checkbox"
                                                        checked={item.selected}
                                                        onChange={() => { }} // 由 onClick 處理
                                                        onClick={(e) => handleSelectItem(i, e)}
                                                        className="w-4 h-4 rounded border-gray-300"
                                                        style={{ accentColor: THEME.primary }}
                                                    />
                                                </td>
                                                <td className="p-3 font-mono text-sm text-gray-600">{item.hisno}</td>
                                                <td className="p-3 font-semibold text-sm max-w-16 break-words">{item.name}</td>
                                                <td className="p-3">
                                                    <input
                                                        value={item.diagnosis}
                                                        onChange={e => updateItem(i, 'diagnosis', e.target.value)}
                                                        disabled={!item.selected}
                                                        className="w-full bg-transparent hover:bg-white/50 focus:bg-white focus:ring-1 rounded px-2 py-1 text-sm transition-all disabled:cursor-not-allowed"
                                                        style={{
                                                            border: item._original && item.diagnosis !== item._original.diagnosis
                                                                ? '2px solid #86efac' : 'none'
                                                        }}
                                                    />
                                                </td>
                                                <td className="p-3">
                                                    <select
                                                        value={item.side}
                                                        onChange={e => updateItem(i, 'side', e.target.value)}
                                                        disabled={!item.selected}
                                                        className="bg-transparent hover:bg-white/50 focus:ring-1 rounded px-2 py-1 text-sm transition-all disabled:cursor-not-allowed"
                                                        style={{
                                                            border: item._original && item.side !== item._original.side
                                                                ? '2px solid #86efac' : 'none'
                                                        }}
                                                    >
                                                        <option value="OD">OD</option>
                                                        <option value="OS">OS</option>
                                                        <option value="OU">OU</option>
                                                    </select>
                                                </td>
                                                <td className="p-3 min-w-32">
                                                    <input
                                                        value={item.drug}
                                                        onChange={e => updateItem(i, 'drug', e.target.value)}
                                                        disabled={!item.selected}
                                                        className="w-full bg-transparent hover:bg-white/50 focus:bg-white focus:ring-1 rounded px-2 py-1 text-sm transition-all disabled:cursor-not-allowed"
                                                        style={{
                                                            border: item._original && item.drug !== item._original.drug
                                                                ? '2px solid #86efac' : 'none'
                                                        }}
                                                    />
                                                </td>
                                                {/* 醫師登號 - 可編輯 */}
                                                <td className="p-3 whitespace-nowrap">
                                                    <input
                                                        value={item.vs_code}
                                                        onChange={async e => {
                                                            const code = e.target.value.replace(/\D/g, '').slice(0, 4);
                                                            updateItem(i, 'vs_code', code);
                                                            // 當輸入4位數時自動查詢姓名
                                                            if (code.length === 4) {
                                                                const { lookupDoctorName } = await import('../api/tasks');
                                                                const name = await lookupDoctorName(code);
                                                                if (name) {
                                                                    updateItem(i, 'vs_name', name);
                                                                }
                                                            }
                                                        }}
                                                        disabled={!item.selected}
                                                        className="w-14 bg-transparent hover:bg-white/50 focus:bg-white focus:ring-1 rounded px-2 py-1 text-sm font-mono text-center transition-all disabled:cursor-not-allowed"
                                                        style={{
                                                            border: item._original && item.vs_code !== item._original.vs_code
                                                                ? '2px solid #86efac' : 'none'
                                                        }}
                                                        placeholder="4位數"
                                                        maxLength={4}
                                                    />
                                                </td>
                                                {/* 醫師姓名 - 唯讀 */}
                                                <td className="p-3 whitespace-nowrap">
                                                    <span
                                                        className="rounded px-2 py-1 text-sm text-gray-600 inline-block"
                                                        style={{
                                                            border: item._original && item.vs_name !== item._original.vs_name
                                                                ? '2px solid #86efac' : 'none'
                                                        }}
                                                    >
                                                        {item.vs_name || '-'}
                                                    </span>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </Card>
                    </div>
                )}

                {/* Step 3: 完成 */}
                {currentStep === 'done' && (
                    <Card className="shadow-xl backdrop-blur-xl bg-white/70 border border-white/50 p-8 text-center">
                        <div
                            className="w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4"
                            style={{ backgroundColor: THEME.successLight }}
                        >
                            <Check size={32} style={{ color: THEME.success }} />
                        </div>
                        <h3 className="text-xl font-bold text-gray-900 mb-2">送出完成</h3>
                        <p className="text-gray-500 mb-6">{statusMsg}</p>
                        <Button variant="primary" onClick={handleReset} style={{ backgroundColor: THEME.primary }}>
                            開始新的作業
                        </Button>
                    </Card>
                )}

                {/* Toast 通知 */}
                {statusMsg && currentStep !== 'done' && (
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

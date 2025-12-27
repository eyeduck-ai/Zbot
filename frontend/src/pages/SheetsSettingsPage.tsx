import { useState, useEffect } from 'react';
import { FileSpreadsheet, Edit2, Loader2, AlertCircle, Check, RefreshCw, Plus, X } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { apiClient } from '../api/client';
import { useAuth } from '../context/AuthContext';

// 必要欄位定義 (永遠顯示)
const REQUIRED_FIELDS = [
    { key: 'COL_HISNO', label: '病歷號', defaultValue: '', required: true },
    { key: 'COL_SIDE_OR_DIAGNOSIS', label: '側別/診斷', defaultValue: '', required: true },
    { key: 'COL_OP', label: '術式', defaultValue: '', required: true },
];

// 欄位 key 到顯示標籤的映射
const FIELD_LABELS: Record<string, string> = {
    'COL_HISNO': '病歷號',
    'COL_SIDE_OR_DIAGNOSIS': '側別/診斷',
    'COL_OP': '術式',
    'COL_IOL': 'IOL',
    'COL_FINAL': 'Final',
    'COL_TARGET': 'Target',
    'COL_SN': 'SN',
    'COL_CDE': 'CDE',
    'COL_LENSX': 'Lensx',
    'COL_COMPLICATIONS': '併發症',
    'COL_LASER_WATT': '雷射瓦數',
    'COL_LASER_SPOT': '雷射數量',
};

interface SheetSettings {
    doc_code: string;
    sheet_id: string;
    worksheet: string;
    column_map?: Record<string, string | null>;
    header_row?: number;  // 標題列行號 (1-indexed)
    created_at?: string;
    updated_at?: string;
}

interface WorksheetInfo {
    title: string;
    index: number;
}

export default function SheetsSettingsPage() {
    const { token } = useAuth();
    const [sheets, setSheets] = useState<SheetSettings[]>([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [successMessage, setSuccessMessage] = useState<string | null>(null);
    const [showHelp, setShowHelp] = useState(false);
    const [userDocCode, setUserDocCode] = useState<string>('');
    const [userRole, setUserRole] = useState<string>('');

    // 工作表選擇器
    const [worksheets, setWorksheets] = useState<WorksheetInfo[]>([]);
    const [loadingWorksheets, setLoadingWorksheets] = useState(false);
    const [showWorksheetDropdown, setShowWorksheetDropdown] = useState(false);

    // 表單狀態
    const [editMode, setEditMode] = useState<'create' | 'edit'>('create');
    const [editingDocCode, setEditingDocCode] = useState<string | null>(null);  // 追蹤目前編輯的 doc_code
    const [formData, setFormData] = useState({
        doc_code: '',
        sheet_id: '',
        worksheet: '',
        header_row: 1,  // 預設第 1 列
        column_map: {} as Record<string, string>
    });

    // 自訂欄位對應 (key-value pairs)
    const [customColumns, setCustomColumns] = useState<Array<{ key: string, value: string }>>([]);

    // 動態欄位 (從 API 載入的選用欄位)
    const [dynamicColumnKeys, setDynamicColumnKeys] = useState<string[]>([]);

    // 必要欄位的 key set (用於過濾)
    const requiredKeys = new Set(REQUIRED_FIELDS.map(f => f.key));

    // 合併後的所有欄位 (必要 + 動態，用於表格顯示)
    const allColumnFields = [
        ...REQUIRED_FIELDS,
        ...dynamicColumnKeys
            .filter(k => !requiredKeys.has(k))
            .map(k => ({ key: k, label: FIELD_LABELS[k] || k.replace('COL_', ''), defaultValue: '' }))
    ];

    // 從 JWT 取得使用者的 doc_code
    useEffect(() => {
        if (token) {
            try {
                const payload = JSON.parse(atob(token.split('.')[1]));
                if (payload.doc_code) {
                    setUserDocCode(payload.doc_code);
                    setFormData(prev => ({ ...prev, doc_code: payload.doc_code }));
                }
                if (payload.zbot_role) {
                    setUserRole(payload.zbot_role);
                }
            } catch { /* ignore */ }
        }
    }, [token]);

    // 載入所有刀表設定
    const loadSheets = async () => {
        setLoading(true);
        try {
            const data = await apiClient.get<SheetSettings[]>('/api/sheets');
            if (Array.isArray(data)) {
                // 將自己的刀表排在最前面
                const sorted = [...data].sort((a, b) => {
                    if (a.doc_code === userDocCode) return -1;
                    if (b.doc_code === userDocCode) return 1;
                    return a.doc_code.localeCompare(b.doc_code);
                });
                setSheets(sorted);
            }
        } catch (e: unknown) {
            const err = e as { message?: string };
            setError(err.message || '載入失敗');
        } finally {
            setLoading(false);
        }
    };

    // 載入動態欄位 keys
    const loadColumnKeys = async () => {
        try {
            const keys = await apiClient.get<string[]>('/api/sheets/column-keys');
            if (Array.isArray(keys)) {
                setDynamicColumnKeys(keys);
            }
        } catch (e) {
            console.error('Failed to load column keys:', e);
        }
    };

    useEffect(() => {
        loadSheets();
        loadColumnKeys();
    }, [userDocCode]);  // 當 userDocCode 變更時重新載入排序

    // 查詢工作表列表
    const fetchWorksheets = async () => {
        if (!formData.sheet_id.trim()) {
            setError('請先輸入 Spreadsheet ID');
            return;
        }

        setLoadingWorksheets(true);
        setWorksheets([]);
        setShowWorksheetDropdown(false);
        try {
            const data = await apiClient.get<WorksheetInfo[]>(`/api/sheets/worksheets/${formData.sheet_id}`);
            if (Array.isArray(data) && data.length > 0) {
                setWorksheets(data);
                setShowWorksheetDropdown(true);
                setError(null);
            } else {
                setError('此試算表沒有工作表');
            }
        } catch (e: unknown) {
            const err = e as { message?: string };
            setError(err.message || '無法取得工作表列表');
        } finally {
            setLoadingWorksheets(false);
        }
    };

    // 選擇工作表
    const selectWorksheet = (title: string) => {
        setFormData(prev => ({ ...prev, worksheet: title }));
        setShowWorksheetDropdown(false);
    };

    // 處理欄位變更
    const handleColumnChange = (key: string, value: string) => {
        setFormData(prev => ({
            ...prev,
            column_map: { ...prev.column_map, [key]: value }
        }));
    };

    // 點擊編輯 icon（toggle 功能）
    const handleEditClick = (sheet: SheetSettings) => {
        // 如果已經在編輯這個，就取消編輯
        if (editMode === 'edit' && editingDocCode === sheet.doc_code) {
            resetForm();
            return;
        }

        // 進入編輯模式
        setEditMode('edit');
        setEditingDocCode(sheet.doc_code);

        // 分離固定欄位和自訂欄位
        const fixedKeys = new Set(allColumnFields.map((f: { key: string }) => f.key));
        const columnMap: Record<string, string> = {};
        const customCols: Array<{ key: string, value: string }> = [];

        if (sheet.column_map) {
            Object.entries(sheet.column_map).forEach(([key, value]) => {
                if (fixedKeys.has(key)) {
                    columnMap[key] = value || '';
                } else if (key && value) {
                    customCols.push({ key, value });
                }
            });
        }

        // 確保所有固定欄位都有值
        allColumnFields.forEach((field: { key: string }) => {
            if (!(field.key in columnMap)) {
                columnMap[field.key] = '';
            }
        });

        setFormData({
            doc_code: sheet.doc_code,
            sheet_id: sheet.sheet_id,
            worksheet: sheet.worksheet,
            header_row: sheet.header_row || 1,
            column_map: columnMap
        });
        setCustomColumns(customCols);
        setWorksheets([]);
        setError(null);
        setSuccessMessage(null);
        window.scrollTo({ top: 0, behavior: 'smooth' });
    };

    // 重設表單
    const resetForm = () => {
        setEditMode('create');
        setEditingDocCode(null);
        setFormData({
            doc_code: userDocCode,
            sheet_id: '',
            worksheet: '',
            header_row: 1,
            column_map: {}
        });
        setCustomColumns([]);
        setWorksheets([]);
        setError(null);
        setSuccessMessage(null);
    };

    // 儲存設定
    const handleSave = async () => {
        if (!formData.doc_code.trim()) {
            setError('請輸入醫師代碼');
            return;
        }
        if (!formData.sheet_id.trim()) {
            setError('請輸入 Spreadsheet ID');
            return;
        }
        if (!formData.worksheet.trim()) {
            setError('請輸入工作表名稱');
            return;
        }

        setSaving(true);
        setError(null);
        setSuccessMessage(null);

        try {
            // 合併固定欄位和自訂欄位
            const mergedColumnMap: Record<string, string> = { ...formData.column_map };
            customColumns.forEach(col => {
                if (col.key.trim()) {
                    mergedColumnMap[col.key.trim()] = col.value.trim();
                }
            });

            const payload = {
                doc_code: formData.doc_code.trim(),
                sheet_id: formData.sheet_id.trim(),
                worksheet: formData.worksheet.trim(),
                header_row: formData.header_row,
                column_map: mergedColumnMap
            };

            if (editMode === 'edit') {
                await apiClient.put(`/api/sheets/${formData.doc_code}`, payload);
                setSuccessMessage('設定已更新');
            } else {
                await apiClient.post('/api/sheets', payload);
                setSuccessMessage('設定已新增');
            }

            loadSheets();
            if (editMode === 'create') {
                resetForm();
            }
        } catch (e: unknown) {
            const err = e as { message?: string };
            setError(err.message || '儲存失敗');
        } finally {
            setSaving(false);
        }
    };

    // 檢查是否可以編輯 (admin/vs 可編輯所有人，其他人只能編輯自己的)
    const canEdit = (docCode: string) =>
        userRole === 'admin' || userRole === 'vs' || userDocCode === docCode;

    // 格式化欄位對應顯示
    const formatColumnMap = (columnMap?: Record<string, string | null>) => {
        if (!columnMap) return allColumnFields.map(() => '-');
        return allColumnFields.map((field: { key: string }) => columnMap[field.key] || '-');
    };

    return (
        <div className="bg-[#F5F5F7] min-h-full flex flex-col p-8 font-sans">
            <div className="relative z-10 w-full max-w-[1400px] mx-auto my-auto">
                {/* 頁面標題 */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '20px' }}>
                    <div style={{
                        width: '48px',
                        height: '48px',
                        borderRadius: '12px',
                        background: 'linear-gradient(135deg, #eef4fd 0%, #dbeafe 100%)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                    }}>
                        <FileSpreadsheet size={24} color="#137fec" />
                    </div>
                    <div>
                        <h1 style={{ margin: 0, fontSize: '24px', fontWeight: 700, color: '#1f2937' }}>
                            Google 刀表設定
                        </h1>
                        <p style={{ margin: '4px 0 0', fontSize: '14px', color: '#6b7280' }}>
                            設定醫師的 Google Sheets 刀表連結
                        </p>
                    </div>
                </div>

                {/* 設定表單卡片 */}
                <Card style={{ padding: '20px 24px', marginBottom: '16px', overflow: 'visible' }}>
                    {/* 標題列 */}
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
                        <h2 style={{ margin: 0, fontSize: '16px', fontWeight: 600, color: '#1f2937' }}>
                            {editMode === 'edit' ? '編輯刀表設定' : '新增刀表設定'}
                        </h2>
                        <div style={{ display: 'flex', gap: '8px' }}>
                            {editMode === 'edit' && (
                                <Button variant="ghost" size="sm" onClick={resetForm}>
                                    取消編輯
                                </Button>
                            )}
                            <Button
                                variant="primary"
                                onClick={handleSave}
                                disabled={saving}
                            >
                                {saving && <Loader2 size={16} className="animate-spin" style={{ marginRight: '8px' }} />}
                                {editMode === 'edit' ? '更新設定' : '新增設定'}
                            </Button>
                        </div>
                    </div>

                    {/* 兩欄佈局: 左欄 40%, 右欄 60% */}
                    <div style={{ display: 'grid', gridTemplateColumns: '2fr 3fr', gap: '32px' }}>
                        {/* 左側：基本設定 + 權限提示 */}
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', position: 'relative', zIndex: 100 }}>
                            {/* 權限提示 */}
                            <div style={{
                                padding: '10px 12px',
                                backgroundColor: '#fffbeb',
                                border: '1px solid #fcd34d',
                                borderRadius: '8px',
                                fontSize: '12px',
                            }}>
                                <p style={{ margin: 0, color: '#92400e', fontWeight: 500 }}>
                                    ⚠ 設定前請先分享權限
                                </p>
                                <p style={{ margin: '4px 0 0', color: '#a16207', fontSize: '11px' }}>
                                    將以下帳號加入為編輯者：
                                </p>
                                <code style={{
                                    display: 'block',
                                    marginTop: '4px',
                                    padding: '4px 6px',
                                    backgroundColor: '#fef3c7',
                                    borderRadius: '4px',
                                    fontSize: '10px',
                                    color: '#78350f',
                                    wordBreak: 'break-all',
                                }}>
                                    python-bot@vghbot.iam.gserviceaccount.com
                                </code>
                            </div>

                            <div>
                                <label style={{ fontSize: '12px', color: '#6b7280', display: 'block', marginBottom: '4px' }}>
                                    醫師代碼 <span style={{ color: '#ef4444' }}>*</span>
                                </label>
                                <input
                                    type="text"
                                    value={formData.doc_code}
                                    onChange={e => setFormData(prev => ({ ...prev, doc_code: e.target.value }))}
                                    placeholder="4050"
                                    disabled={editMode === 'edit'}
                                    style={{
                                        width: '100%',
                                        padding: '8px 10px',
                                        border: '1px solid #d1d5db',
                                        borderRadius: '6px',
                                        fontSize: '14px',
                                        backgroundColor: editMode === 'edit' ? '#f3f4f6' : '#fff',
                                    }}
                                />
                            </div>
                            <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-end' }}>
                                <div style={{ flex: 1 }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                                        <label style={{ fontSize: '12px', color: '#6b7280' }}>
                                            Spreadsheet ID <span style={{ color: '#ef4444' }}>*</span>
                                        </label>
                                        <button
                                            type="button"
                                            onClick={() => setShowHelp(!showHelp)}
                                            style={{
                                                background: 'none',
                                                border: 'none',
                                                padding: 0,
                                                color: '#3b82f6',
                                                fontSize: '11px',
                                                cursor: 'pointer',
                                                textDecoration: 'underline',
                                            }}
                                        >
                                            不知道在哪?
                                        </button>
                                    </div>
                                    <input
                                        type="text"
                                        value={formData.sheet_id}
                                        onChange={e => setFormData(prev => ({ ...prev, sheet_id: e.target.value }))}
                                        placeholder="1Tt5In-IvJYmahxVqrUh..."
                                        style={{
                                            width: '100%',
                                            padding: '8px 10px',
                                            border: '1px solid #d1d5db',
                                            borderRadius: '6px',
                                            fontSize: '13px',
                                            fontFamily: 'monospace',
                                        }}
                                    />
                                </div>
                                <div style={{ width: '80px' }}>
                                    <label style={{ fontSize: '12px', color: '#6b7280', display: 'block', marginBottom: '4px' }}>
                                        標題列
                                    </label>
                                    <input
                                        type="number"
                                        min="1"
                                        max="10"
                                        value={formData.header_row}
                                        onChange={e => setFormData(prev => ({ ...prev, header_row: Math.max(1, parseInt(e.target.value) || 1) }))}
                                        style={{
                                            width: '100%',
                                            padding: '8px 10px',
                                            border: '1px solid #d1d5db',
                                            borderRadius: '6px',
                                            fontSize: '13px',
                                        }}
                                    />
                                </div>
                            </div>
                            <div style={{ position: 'relative' }}>
                                <label style={{ fontSize: '12px', color: '#6b7280', display: 'block', marginBottom: '4px' }}>
                                    工作表名稱 <span style={{ color: '#ef4444' }}>*</span>
                                </label>
                                <div style={{ display: 'flex', gap: '6px' }}>
                                    <input
                                        type="text"
                                        value={formData.worksheet}
                                        onChange={e => setFormData(prev => ({ ...prev, worksheet: e.target.value }))}
                                        placeholder="2412-01"
                                        style={{
                                            flex: 1,
                                            padding: '8px 10px',
                                            border: '1px solid #d1d5db',
                                            borderRadius: '6px',
                                            fontSize: '14px',
                                        }}
                                    />
                                    <Button
                                        variant="secondary"
                                        size="sm"
                                        onClick={fetchWorksheets}
                                        disabled={loadingWorksheets || !formData.sheet_id.trim()}
                                        style={{ whiteSpace: 'nowrap', padding: '8px 12px' }}
                                    >
                                        {loadingWorksheets ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
                                        <span style={{ marginLeft: '6px' }}>查詢可用工作表名稱</span>
                                    </Button>
                                </div>

                                {/* 工作表選擇下拉選單 */}
                                {showWorksheetDropdown && worksheets.length > 0 && (
                                    <div style={{
                                        position: 'absolute',
                                        top: '100%',
                                        left: 0,
                                        right: 0,
                                        marginTop: '4px',
                                        backgroundColor: '#fff',
                                        border: '1px solid #d1d5db',
                                        borderRadius: '8px',
                                        boxShadow: '0 10px 25px -5px rgba(0,0,0,0.15)',
                                        zIndex: 1000,
                                        maxHeight: '200px',
                                        overflowY: 'auto',
                                    }}>
                                        <div style={{ padding: '6px 10px', borderBottom: '1px solid #e5e7eb', fontSize: '11px', color: '#6b7280' }}>
                                            點擊選擇工作表
                                        </div>
                                        {worksheets.map(ws => (
                                            <button
                                                key={ws.index}
                                                onClick={() => selectWorksheet(ws.title)}
                                                style={{
                                                    display: 'block',
                                                    width: '100%',
                                                    padding: '10px 12px',
                                                    textAlign: 'left',
                                                    background: 'none',
                                                    border: 'none',
                                                    cursor: 'pointer',
                                                    fontSize: '13px',
                                                    color: '#374151',
                                                    borderBottom: '1px solid #f3f4f6',
                                                }}
                                                onMouseEnter={e => e.currentTarget.style.backgroundColor = '#eef4fd'}
                                                onMouseLeave={e => e.currentTarget.style.backgroundColor = 'transparent'}
                                            >
                                                {ws.title}
                                            </button>
                                        ))}
                                        <button
                                            onClick={() => setShowWorksheetDropdown(false)}
                                            style={{
                                                display: 'block',
                                                width: '100%',
                                                padding: '8px 12px',
                                                textAlign: 'center',
                                                background: '#f9fafb',
                                                border: 'none',
                                                cursor: 'pointer',
                                                fontSize: '11px',
                                                color: '#6b7280',
                                                borderRadius: '0 0 8px 8px',
                                            }}
                                        >
                                            關閉
                                        </button>
                                    </div>
                                )}
                            </div>

                            {/* 只能編輯自己的提示 (admin/vs 不顯示) */}
                            {editMode === 'edit' && formData.doc_code !== userDocCode && userRole !== 'admin' && userRole !== 'vs' && (
                                <div style={{
                                    padding: '8px 10px',
                                    borderRadius: '6px',
                                    backgroundColor: 'rgba(239, 68, 68, 0.1)',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '6px',
                                    fontSize: '12px',
                                }}>
                                    <AlertCircle size={14} color="#ef4444" />
                                    <span style={{ color: '#991b1b' }}>只能更新自己的刀表設定</span>
                                </div>
                            )}
                        </div>

                        {/* 右側：欄位對應 */}
                        <div>
                            <div style={{ marginBottom: '10px' }}>
                                <h3 style={{ fontSize: '13px', fontWeight: 600, color: '#374151', margin: 0 }}>
                                    欄位對應
                                </h3>
                                <p style={{ fontSize: '11px', color: '#9ca3af', margin: '2px 0 0' }}>
                                    填入對應欄位的名稱，留空表示無此欄位
                                </p>
                            </div>
                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '10px' }}>
                                {allColumnFields.map((field: { key: string; label: string; defaultValue: string; required?: boolean }) => (
                                    <div key={field.key} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                        <label style={{
                                            fontSize: '12px',
                                            color: '#6b7280',
                                            width: '60px',
                                            flexShrink: 0,
                                        }}>
                                            {field.label}
                                            {field.required && <span style={{ color: '#ef4444', marginLeft: '2px' }}>*</span>}
                                        </label>
                                        <input
                                            type="text"
                                            value={editMode === 'edit'
                                                ? (formData.column_map[field.key] ?? '')
                                                : (formData.column_map[field.key] ?? field.defaultValue)}
                                            onChange={e => handleColumnChange(field.key, e.target.value)}
                                            placeholder={field.defaultValue || '(空)'}
                                            style={{
                                                flex: 1,
                                                padding: '8px 10px',
                                                border: '1px solid #e5e7eb',
                                                borderRadius: '6px',
                                                fontSize: '13px',
                                            }}
                                        />
                                    </div>
                                ))}
                            </div>

                            {/* 自訂欄位對應 - 在右欄下方 */}
                            <div style={{ marginTop: '16px', paddingTop: '16px', borderTop: '1px solid #e5e7eb' }}>
                                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                                    <h4 style={{ fontSize: '12px', fontWeight: 600, color: '#374151', margin: 0 }}>
                                        自訂欄位
                                    </h4>
                                    <button
                                        type="button"
                                        onClick={() => setCustomColumns(prev => [...prev, { key: '', value: '' }])}
                                        style={{
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: '4px',
                                            padding: '4px 8px',
                                            border: '1px solid #d1d5db',
                                            borderRadius: '4px',
                                            background: '#fff',
                                            cursor: 'pointer',
                                            fontSize: '11px',
                                            color: '#374151',
                                        }}
                                    >
                                        <Plus size={12} />
                                        新增
                                    </button>
                                </div>
                                {customColumns.length === 0 ? (
                                    <p style={{ fontSize: '11px', color: '#9ca3af', margin: 0 }}>
                                        點擊「新增」加入自訂欄位對應
                                    </p>
                                ) : (
                                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '8px' }}>
                                        {customColumns.map((col, idx) => (
                                            <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                                <input
                                                    type="text"
                                                    value={col.key}
                                                    onChange={e => {
                                                        const newCols = [...customColumns];
                                                        newCols[idx].key = e.target.value;
                                                        setCustomColumns(newCols);
                                                    }}
                                                    placeholder="key"
                                                    style={{
                                                        width: '80px',
                                                        padding: '6px 8px',
                                                        border: '1px solid #e5e7eb',
                                                        borderRadius: '4px',
                                                        fontSize: '12px',
                                                    }}
                                                />
                                                <span style={{ color: '#9ca3af' }}>=</span>
                                                <input
                                                    type="text"
                                                    value={col.value}
                                                    onChange={e => {
                                                        const newCols = [...customColumns];
                                                        newCols[idx].value = e.target.value;
                                                        setCustomColumns(newCols);
                                                    }}
                                                    placeholder="欄位名稱"
                                                    style={{
                                                        flex: 1,
                                                        padding: '6px 8px',
                                                        border: '1px solid #e5e7eb',
                                                        borderRadius: '4px',
                                                        fontSize: '12px',
                                                    }}
                                                />
                                                <button
                                                    type="button"
                                                    onClick={() => setCustomColumns(prev => prev.filter((_, i) => i !== idx))}
                                                    style={{
                                                        padding: '4px',
                                                        border: 'none',
                                                        background: 'none',
                                                        cursor: 'pointer',
                                                        color: '#9ca3af',
                                                    }}
                                                >
                                                    <X size={14} />
                                                </button>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>

                    {/* 錯誤/成功訊息 */}
                    {error && (
                        <div style={{
                            marginTop: '12px',
                            padding: '10px',
                            borderRadius: '6px',
                            backgroundColor: 'rgba(239, 68, 68, 0.1)',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '6px',
                        }}>
                            <AlertCircle size={14} color="#ef4444" />
                            <span style={{ fontSize: '12px', color: '#991b1b' }}>{error}</span>
                        </div>
                    )}
                    {successMessage && (
                        <div style={{
                            marginTop: '12px',
                            padding: '10px',
                            borderRadius: '6px',
                            backgroundColor: 'rgba(34, 197, 94, 0.1)',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '6px',
                        }}>
                            <Check size={14} color="#22c55e" />
                            <span style={{ fontSize: '12px', color: '#166534' }}>{successMessage}</span>
                        </div>
                    )}
                </Card>

                {/* 現有刀表設定 - 表格 */}
                <Card style={{ padding: '20px 24px' }}>
                    <h2 style={{ margin: '0 0 12px', fontSize: '16px', fontWeight: 600, color: '#1f2937' }}>
                        現有刀表設定
                    </h2>

                    {loading ? (
                        <div style={{ textAlign: 'center', padding: '32px', color: '#6b7280' }}>
                            <Loader2 size={24} className="animate-spin" style={{ margin: '0 auto 8px' }} />
                            載入中...
                        </div>
                    ) : sheets.length === 0 ? (
                        <div style={{ textAlign: 'center', padding: '32px', color: '#9ca3af' }}>
                            尚無刀表設定
                        </div>
                    ) : (
                        <div style={{ overflowX: 'auto', fontFamily: '"Inter", "Noto Sans TC", sans-serif', fontSize: '13px' }}>
                            <table style={{ borderCollapse: 'collapse', width: '100%', minWidth: '800px' }}>
                                <thead>
                                    <tr style={{ borderBottom: '2px solid #e5e7eb' }}>
                                        <th style={{ padding: '10px 12px', width: '40px' }}></th>
                                        <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, color: '#374151', whiteSpace: 'nowrap' }}>醫師代碼</th>
                                        <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, color: '#374151', whiteSpace: 'nowrap' }}>工作表名稱</th>
                                        <th style={{ padding: '10px 12px', textAlign: 'center', fontWeight: 600, color: '#374151', whiteSpace: 'nowrap' }}>標題列</th>
                                        {allColumnFields.map((field: { key: string; label: string }) => (
                                            <th key={field.key} style={{ padding: '10px 12px', textAlign: 'center', fontWeight: 600, color: '#374151', whiteSpace: 'nowrap' }}>
                                                {field.label}
                                            </th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {sheets.map(sheet => {
                                        const columns = formatColumnMap(sheet.column_map);
                                        return (
                                            <tr
                                                key={sheet.doc_code}
                                                style={{
                                                    borderBottom: '1px solid #e5e7eb',
                                                    backgroundColor: editingDocCode === sheet.doc_code ? '#eef4fd' : 'transparent',
                                                }}
                                            >
                                                <td style={{ padding: '10px 12px', textAlign: 'center' }}>
                                                    {canEdit(sheet.doc_code) && (
                                                        <button
                                                            onClick={() => handleEditClick(sheet)}
                                                            style={{
                                                                background: 'none',
                                                                border: 'none',
                                                                cursor: 'pointer',
                                                                padding: '4px',
                                                                borderRadius: '4px',
                                                                color: editingDocCode === sheet.doc_code ? '#ef4444' : '#137fec',
                                                                display: 'flex',
                                                                alignItems: 'center',
                                                                justifyContent: 'center',
                                                            }}
                                                            title={editingDocCode === sheet.doc_code ? '取消編輯' : '編輯'}
                                                        >
                                                            <Edit2 size={15} />
                                                        </button>
                                                    )}
                                                </td>
                                                <td style={{ padding: '10px 12px', fontWeight: 600, color: '#1f2937', whiteSpace: 'nowrap' }}>
                                                    {sheet.doc_code}
                                                    {sheet.doc_code === userDocCode && (
                                                        <span style={{
                                                            marginLeft: '6px',
                                                            padding: '2px 5px',
                                                            backgroundColor: '#dbeafe',
                                                            color: '#1e40af',
                                                            borderRadius: '4px',
                                                            fontSize: '10px',
                                                        }}>我</span>
                                                    )}
                                                </td>
                                                <td style={{ padding: '10px 12px', color: '#374151', whiteSpace: 'nowrap' }}>
                                                    {sheet.worksheet}
                                                </td>
                                                <td style={{ padding: '10px 12px', textAlign: 'center', color: '#374151', whiteSpace: 'nowrap' }}>
                                                    {sheet.header_row || 1}
                                                </td>
                                                {columns.map((value, idx) => (
                                                    <td key={idx} style={{ padding: '10px 12px', textAlign: 'center', color: value === '-' ? '#d1d5db' : '#374151', whiteSpace: 'nowrap' }}>
                                                        {value}
                                                    </td>
                                                ))}
                                            </tr>
                                        );
                                    })}
                                </tbody>
                            </table>
                        </div>
                    )}
                </Card>

                {/* Help Panel */}
                {showHelp && (
                    <div
                        onClick={() => setShowHelp(false)}
                        style={{
                            position: 'fixed',
                            top: 0, left: 0, right: 0, bottom: 0,
                            backgroundColor: 'rgba(0,0,0,0.3)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            zIndex: 9999,
                        }}
                    >
                        <div
                            onClick={e => e.stopPropagation()}
                            style={{
                                backgroundColor: '#fff',
                                borderRadius: '12px',
                                padding: '20px',
                                maxWidth: '500px',
                                boxShadow: '0 25px 50px -12px rgba(0,0,0,0.25)',
                            }}
                        >
                            <p style={{ margin: '0 0 12px', fontSize: '14px', color: '#374151', fontWeight: 500 }}>
                                Spreadsheet ID 在網址列中 <code style={{ backgroundColor: '#f3f4f6', padding: '2px 6px', borderRadius: '4px' }}>/d/</code> 和 <code style={{ backgroundColor: '#f3f4f6', padding: '2px 6px', borderRadius: '4px' }}>/edit</code> 之間
                            </p>
                            <img
                                src="/help-spreadsheet-id.png"
                                alt="Spreadsheet ID 位置說明"
                                style={{
                                    maxWidth: '100%',
                                    borderRadius: '8px',
                                    border: '1px solid #e5e7eb',
                                }}
                            />
                            <p style={{ margin: '12px 0 0', fontSize: '12px', color: '#9ca3af', textAlign: 'center' }}>
                                點擊任意處關閉
                            </p>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}

import { useState, useEffect, useRef } from 'react';
import { FileText, Edit2, Loader2, AlertCircle, Check, Plus, Trash2, GripVertical, X, Copy } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { CodeMirrorEditor } from '../components/ui/CodeMirrorEditor';
import { JsonEditor } from '../components/ui/JsonEditor';
import { apiClient } from '../api/client';
import { useAuth } from '../context/AuthContext';

// 欄位 key 到顯示標籤的映射
const FIELD_LABELS: Record<string, string> = {
    'IOL': 'IOL',
    'FINAL': 'Final',
    'TARGET': 'Target',
    'SN': 'SN',
    'CDE': 'CDE',
    'LENSX': 'Lensx',
    'COMPLICATIONS': '併發症',
    'LASER_WATT': '雷射瓦數',
    'LASER_SPOT': '雷射數量',
};

interface Template {
    id: string;
    op_type: string;
    doc_code: string | null;
    op_name: string;
    op_code: string | null;
    template: string | null;
    icd_codes: Record<string, any> | null;
    required_fields: string[] | null;
    optional_fields: string[] | null;
    created_at?: string;
    updated_at?: string;
}

export default function TemplatesSettingsPage() {
    const { token } = useAuth();
    const [templates, setTemplates] = useState<Template[]>([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [successMessage, setSuccessMessage] = useState<string | null>(null);
    const [userDocCode, setUserDocCode] = useState<string>('');
    const [userRole, setUserRole] = useState<string>('');

    // 動態欄位 (其他範本可用欄位)
    const [availableFields, setAvailableFields] = useState<string[]>([]);

    // 新增欄位輸入
    const [newFieldName, setNewFieldName] = useState('');

    // 編輯狀態
    const [editMode, setEditMode] = useState<'create' | 'edit' | 'copy'>('create');
    const [editingId, setEditingId] = useState<string | null>(null);
    const [formData, setFormData] = useState({
        op_type: '',
        doc_code: null as string | null,
        op_name: '',
        op_code: '',
        template: '',
        icd_codes: null as Record<string, any> | null,
        icd_codes_json: '',
        required_fields: [] as string[],
    });

    // JSON 驗證狀態
    const [jsonError, setJsonError] = useState<string | null>(null);

    // CodeMirror 編輯器 ref
    const editorRef = useRef<HTMLDivElement>(null);

    // 從 JWT 取得使用者資訊
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

    // 載入範本列表
    const loadTemplates = async () => {
        setLoading(true);
        try {
            const data = await apiClient.get<Template[]>('/api/templates');
            if (Array.isArray(data)) {
                const sorted = [...data].sort((a, b) => {
                    if (!a.doc_code && b.doc_code) return -1;
                    if (a.doc_code && !b.doc_code) return 1;
                    if (a.doc_code === userDocCode) return -1;
                    if (b.doc_code === userDocCode) return 1;
                    return a.op_type.localeCompare(b.op_type);
                });
                setTemplates(sorted);
            }
        } catch (e: unknown) {
            const err = e as { message?: string };
            setError(err.message || '載入失敗');
        } finally {
            setLoading(false);
        }
    };

    // 載入可用欄位
    const loadFieldKeys = async () => {
        try {
            const keys = await apiClient.get<string[]>('/api/templates/field-keys');
            if (Array.isArray(keys)) {
                setAvailableFields(keys);
            }
        } catch (e) {
            console.error('Failed to load field keys:', e);
        }
    };

    useEffect(() => {
        loadTemplates();
        loadFieldKeys();
    }, [userDocCode]);

    // 檢查編輯權限
    const canEdit = (template: Template) => {
        if (userRole === 'admin') return true;
        if (!template.doc_code) return false;
        if (userRole === 'vs') return true;
        return userDocCode === template.doc_code;
    };

    // 處理編輯
    const handleEditClick = (template: Template) => {
        setEditMode('edit');
        setEditingId(template.id);
        const icdJson = template.icd_codes ? JSON.stringify(template.icd_codes, null, 2) : '';
        setFormData({
            op_type: template.op_type,
            doc_code: template.doc_code,
            op_name: template.op_name,
            op_code: template.op_code || '',
            template: template.template || '',
            icd_codes: template.icd_codes,
            icd_codes_json: icdJson,
            required_fields: template.required_fields || [],
        });
        setError(null);
        setSuccessMessage(null);
    };

    // 處理複製 (複製作為新範本)
    const handleCopyClick = (template: Template) => {
        setEditMode('copy');
        setEditingId(null);
        const icdJson = template.icd_codes ? JSON.stringify(template.icd_codes, null, 2) : '';
        setFormData({
            op_type: template.op_type + '_COPY',
            doc_code: userDocCode || null,
            op_name: template.op_name,
            op_code: template.op_code || '',
            template: template.template || '',
            icd_codes: template.icd_codes,
            icd_codes_json: icdJson,
            required_fields: template.required_fields || [],
        });
        setError(null);
        setSuccessMessage('已複製範本，請修改範本名稱後儲存');
    };

    // 重置表單
    const resetForm = () => {
        setEditMode('create');
        setEditingId(null);
        setFormData({
            op_type: '',
            doc_code: userDocCode || null,
            op_name: '',
            op_code: '',
            template: '',
            icd_codes: null,
            icd_codes_json: '',
            required_fields: [],
        });
        setNewFieldName('');
    };

    // 儲存範本
    const handleSave = async () => {
        if (!formData.op_type.trim() || !formData.op_name.trim()) {
            setError('請填寫範本名稱和手術名稱');
            return;
        }

        if (formData.icd_codes_json.trim()) {
            try {
                JSON.parse(formData.icd_codes_json);
            } catch {
                setError('ICD 編碼 JSON 格式錯誤');
                return;
            }
        }

        setSaving(true);
        setError(null);

        try {
            // 非必填的欄位都視為選填
            const allFieldsInTemplate = formData.template.match(/\$([A-Z0-9_]+)/g)?.map(m => m.slice(1)) || [];
            const optionalFields = allFieldsInTemplate.filter(f => !formData.required_fields.includes(f));

            const payload = {
                op_type: formData.op_type,
                doc_code: formData.doc_code,
                op_name: formData.op_name,
                op_code: formData.op_code || null,
                template: formData.template || null,
                icd_codes: formData.icd_codes,
                required_fields: formData.required_fields,
                optional_fields: optionalFields,
            };

            if (editMode === 'edit' && editingId) {
                await apiClient.put(`/api/templates/${editingId}`, payload);
                setSuccessMessage('範本已更新');
            } else {
                await apiClient.post('/api/templates', payload);
                setSuccessMessage('範本已新增');
            }

            await loadTemplates();
            await loadFieldKeys();
            resetForm();
        } catch (e: unknown) {
            const err = e as { message?: string };
            setError(err.message || '儲存失敗');
        } finally {
            setSaving(false);
        }
    };

    // 刪除範本
    const handleDelete = async (templateId: string) => {
        if (!confirm('確定要刪除此範本嗎？')) return;

        try {
            await apiClient.delete(`/api/templates/${templateId}`);
            setSuccessMessage('範本已刪除');
            await loadTemplates();
        } catch (e: unknown) {
            const err = e as { message?: string };
            setError(err.message || '刪除失敗');
        }
    };

    // 拖拽開始
    const handleDragStart = (e: React.DragEvent, field: string) => {
        e.dataTransfer.setData('text/plain', `$${field}`);
        e.dataTransfer.effectAllowed = 'copy';
    };

    // 雙擊插入佔位符 (透過 CodeMirror insertText)
    const handleDoubleClick = (field: string) => {
        const editor = editorRef.current;
        if (editor && (editor as any).insertText) {
            (editor as any).insertText(`$${field}`);
        }
    };

    // 單擊切換必填狀態
    const toggleRequired = (field: string) => {
        setFormData(prev => {
            const isRequired = prev.required_fields.includes(field);
            if (isRequired) {
                return { ...prev, required_fields: prev.required_fields.filter(f => f !== field) };
            } else {
                return { ...prev, required_fields: [...prev.required_fields, field] };
            }
        });
    };

    // 新增自訂欄位
    const handleAddField = () => {
        if (!newFieldName.trim()) return;

        // 統一格式: COL_FIELDNAME (後端相容)
        let fieldKey = newFieldName.toUpperCase().replace(/[^A-Z0-9_]/g, '_');
        if (!fieldKey.startsWith('COL_')) {
            fieldKey = 'COL_' + fieldKey;
        }

        // 檢查是否已存在
        if (availableFields.includes(fieldKey)) {
            setError(`欄位 ${fieldKey} 已存在`);
            return;
        }

        setAvailableFields(prev => [...prev, fieldKey]);
        setNewFieldName('');
        setError(null);
    };

    // 取得欄位狀態
    const isRequired = (field: string): boolean => formData.required_fields.includes(field);

    return (
        <div className="bg-[#F5F5F7] min-h-full flex flex-col p-8 font-sans">
            <div className="relative z-10 w-full max-w-[1400px] mx-auto my-auto">
                {/* 頁面標題 */}
                <div style={{ marginBottom: '24px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                        <FileText size={28} color="#3b82f6" />
                        <div>
                            <h1 style={{ fontSize: '22px', fontWeight: 700, color: '#1f2937', margin: 0 }}>
                                手術範本設定
                            </h1>
                            <p style={{ fontSize: '13px', color: '#6b7280', margin: '4px 0 0' }}>
                                編輯手術記錄範本，支援拖拽或雙擊欄位插入佔位符
                            </p>
                        </div>
                    </div>
                </div>

                <Card style={{ padding: '24px' }}>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '32px' }}>
                        {/* 左側：表單 + 欄位面板 */}
                        <div>
                            <h2 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '16px' }}>
                                {editMode === 'copy' ? '複製範本' : editMode === 'edit' ? '編輯範本' : '新增範本'}
                            </h2>

                            {/* 訊息提示 */}
                            {error && (
                                <div style={{ padding: '10px', background: '#fef2f2', borderRadius: '8px', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                                    <AlertCircle size={16} color="#dc2626" />
                                    <span style={{ color: '#dc2626', fontSize: '13px' }}>{error}</span>
                                </div>
                            )}
                            {successMessage && (
                                <div style={{ padding: '10px', background: '#f0fdf4', borderRadius: '8px', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                                    <Check size={16} color="#16a34a" />
                                    <span style={{ color: '#16a34a', fontSize: '13px' }}>{successMessage}</span>
                                </div>
                            )}

                            {/* 基本資訊 */}
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '16px' }}>
                                <div>
                                    <label style={{ fontSize: '12px', color: '#6b7280' }}>範本名稱 *</label>
                                    <input
                                        type="text"
                                        value={formData.op_type}
                                        onChange={e => setFormData(prev => ({ ...prev, op_type: e.target.value.toUpperCase() }))}
                                        placeholder="如: PHACO, VT, LENSX"
                                        style={{ width: '100%', padding: '8px 12px', border: '1px solid #e5e7eb', borderRadius: '6px', fontSize: '13px', marginTop: '4px' }}
                                    />
                                </div>
                                <div>
                                    <label style={{ fontSize: '12px', color: '#6b7280' }}>範本權限</label>
                                    <select
                                        value={formData.doc_code || 'GLOBAL'}
                                        onChange={e => setFormData(prev => ({ ...prev, doc_code: e.target.value === 'GLOBAL' ? null : e.target.value }))}
                                        style={{ width: '100%', padding: '8px 12px', border: '1px solid #e5e7eb', borderRadius: '6px', fontSize: '13px', marginTop: '4px' }}
                                        disabled={userRole !== 'admin'}
                                    >
                                        {userRole === 'admin' && <option value="GLOBAL">GLOBAL (系統)</option>}
                                        <option value={userDocCode}>個人 ({userDocCode})</option>
                                    </select>
                                </div>
                            </div>

                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '16px' }}>
                                <div>
                                    <label style={{ fontSize: '12px', color: '#6b7280' }}>手術名稱 *</label>
                                    <input
                                        type="text"
                                        value={formData.op_name}
                                        onChange={e => setFormData(prev => ({ ...prev, op_name: e.target.value }))}
                                        placeholder="如: PHACOEMULSIFICATION WITH IOL..."
                                        style={{ width: '100%', padding: '8px 12px', border: '1px solid #e5e7eb', borderRadius: '6px', fontSize: '13px', marginTop: '4px' }}
                                    />
                                </div>
                                <div>
                                    <label style={{ fontSize: '12px', color: '#6b7280' }}>手術代碼</label>
                                    <input
                                        type="text"
                                        value={formData.op_code}
                                        onChange={e => setFormData(prev => ({ ...prev, op_code: e.target.value }))}
                                        placeholder="如: OPH 1342"
                                        style={{ width: '100%', padding: '8px 12px', border: '1px solid #e5e7eb', borderRadius: '6px', fontSize: '13px', marginTop: '4px' }}
                                    />
                                </div>
                            </div>

                            {/* ICD 編碼 JSON 編輯器 */}
                            <div style={{ marginBottom: '16px' }}>
                                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                                    <label style={{ fontSize: '12px', color: '#6b7280' }}>ICD 編碼 (JSON)</label>
                                    <button
                                        type="button"
                                        onClick={() => {
                                            const template = JSON.stringify({
                                                "OD": { "code": "H26.9", "name": "Cataract, unspecified" },
                                                "OS": { "code": "H26.9", "name": "Cataract, unspecified" }
                                            }, null, 2);
                                            setFormData(prev => ({
                                                ...prev,
                                                icd_codes_json: template,
                                                icd_codes: JSON.parse(template)
                                            }));
                                            setJsonError(null);
                                        }}
                                        style={{
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: '4px',
                                            padding: '4px 8px',
                                            fontSize: '11px',
                                            color: '#6b7280',
                                            background: '#f3f4f6',
                                            border: '1px solid #e5e7eb',
                                            borderRadius: '4px',
                                            cursor: 'pointer',
                                        }}
                                    >
                                        <FileText size={12} />
                                        插入範本
                                    </button>
                                </div>
                                <JsonEditor
                                    value={formData.icd_codes_json}
                                    onChange={(val) => {
                                        setFormData(prev => ({ ...prev, icd_codes_json: val }));
                                        try {
                                            if (val.trim()) {
                                                const parsed = JSON.parse(val);
                                                setFormData(prev => ({ ...prev, icd_codes: parsed }));
                                                setJsonError(null);
                                            } else {
                                                setFormData(prev => ({ ...prev, icd_codes: null }));
                                                setJsonError(null);
                                            }
                                        } catch {
                                            // JsonEditor 會顯示行內錯誤
                                        }
                                    }}
                                    onValidChange={(isValid, error) => {
                                        setJsonError(isValid ? null : (error || 'JSON 格式錯誤'));
                                    }}
                                    placeholder='{"OD": {"code": "H26.9", "name": "Cataract"}}'
                                    height="120px"
                                    style={jsonError ? { border: '2px solid #ef4444' } : {}}
                                />
                                {jsonError && (
                                    <p style={{ fontSize: '11px', color: '#ef4444', marginTop: '4px' }}>{jsonError}</p>
                                )}
                            </div>

                            {/* 欄位面板 */}
                            <div style={{ marginBottom: '16px', padding: '16px', background: '#f9fafb', borderRadius: '8px' }}>
                                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
                                    <h3 style={{ fontSize: '13px', fontWeight: 600, color: '#374151', margin: 0 }}>
                                        其他範本可用欄位
                                    </h3>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px', fontSize: '11px', color: '#6b7280' }}>
                                        <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                                            <span style={{ width: '10px', height: '10px', background: '#dbeafe', border: '1px solid #3b82f6', borderRadius: '3px' }}></span>
                                            必填
                                        </span>
                                        <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                                            <span style={{ width: '10px', height: '10px', background: '#f3f4f6', border: '1px solid #e5e7eb', borderRadius: '3px' }}></span>
                                            選填
                                        </span>
                                    </div>
                                </div>

                                <p style={{ fontSize: '11px', color: '#9ca3af', marginBottom: '12px' }}>
                                    單擊切換必填/選填，雙擊或拖拽插入到範本
                                </p>

                                {/* 可用欄位列表 */}
                                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '12px' }}>
                                    {availableFields.map(field => (
                                        <div
                                            key={field}
                                            draggable
                                            onDragStart={e => handleDragStart(e, field)}
                                            onClick={() => toggleRequired(field)}
                                            onDoubleClick={() => handleDoubleClick(field)}
                                            style={{
                                                display: 'flex',
                                                alignItems: 'center',
                                                gap: '4px',
                                                padding: '6px 10px',
                                                background: isRequired(field) ? '#dbeafe' : '#f3f4f6',
                                                border: `1px solid ${isRequired(field) ? '#3b82f6' : '#e5e7eb'}`,
                                                borderRadius: '16px',
                                                fontSize: '12px',
                                                cursor: 'grab',
                                                userSelect: 'none',
                                            }}
                                        >
                                            <GripVertical size={12} color="#9ca3af" />
                                            <span>${FIELD_LABELS[field] || field}</span>
                                        </div>
                                    ))}
                                </div>

                                {/* 新增欄位 */}
                                <div style={{ display: 'flex', gap: '8px' }}>
                                    <input
                                        type="text"
                                        value={newFieldName}
                                        onChange={e => setNewFieldName(e.target.value)}
                                        placeholder="新增自訂欄位..."
                                        style={{ flex: 1, padding: '6px 10px', border: '1px solid #e5e7eb', borderRadius: '6px', fontSize: '12px' }}
                                    />
                                    <Button variant="secondary" onClick={handleAddField}>
                                        <Plus size={14} />
                                    </Button>
                                </div>
                            </div>

                            {/* 按鈕 */}
                            <div style={{ display: 'flex', gap: '12px' }}>
                                <Button onClick={handleSave} disabled={saving}>
                                    {saving ? <Loader2 size={16} className="animate-spin" /> : <Check size={16} />}
                                    {editMode === 'edit' ? '更新' : '新增'}
                                </Button>
                                {(editMode === 'edit' || editMode === 'copy') && (
                                    <Button variant="secondary" onClick={resetForm}>
                                        <X size={16} />
                                        取消
                                    </Button>
                                )}
                            </div>
                        </div>

                        {/* 右側：範本內容 (CodeMirror 編輯器) */}
                        <div>
                            <h2 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '16px' }}>
                                範本內容
                                <span style={{ fontSize: '11px', color: '#9ca3af', fontWeight: 400, marginLeft: '12px' }}>
                                    (⌘Z 撤銷 | 拖曳欄位插入)
                                </span>
                            </h2>
                            <p style={{ fontSize: '11px', color: '#9ca3af', marginBottom: '12px' }}>
                                從左側欄位拖拽或雙擊插入佔位符 (如 $IOL, $FINAL)
                            </p>

                            <div ref={editorRef}>
                                <CodeMirrorEditor
                                    value={formData.template}
                                    onChange={(val) => setFormData(prev => ({ ...prev, template: val }))}
                                    placeholder="輸入範本內容，可拖拽或雙擊左側欄位插入佔位符..."
                                    style={{ minHeight: '400px' }}
                                />
                            </div>
                        </div>
                    </div>
                </Card>

                {/* 範本列表 */}
                <Card style={{ marginTop: '24px', padding: '24px' }}>
                    <h2 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '16px' }}>
                        現有範本
                    </h2>

                    {loading ? (
                        <div style={{ textAlign: 'center', padding: '40px' }}>
                            <Loader2 size={32} className="animate-spin" style={{ margin: '0 auto', color: '#3b82f6' }} />
                            <p style={{ marginTop: '12px', color: '#6b7280' }}>載入中...</p>
                        </div>
                    ) : templates.length === 0 ? (
                        <div style={{ textAlign: 'center', padding: '40px', color: '#9ca3af' }}>
                            尚無範本，請新增
                        </div>
                    ) : (
                        <div style={{ overflowX: 'auto' }}>
                            <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: '13px' }}>
                                <thead>
                                    <tr style={{ borderBottom: '2px solid #e5e7eb' }}>
                                        <th style={{ padding: '10px 12px', width: '60px' }}></th>
                                        <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600 }}>範本名稱</th>
                                        <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600 }}>權限</th>
                                        <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600 }}>手術名稱</th>
                                        <th style={{ padding: '10px 12px', textAlign: 'center', fontWeight: 600 }}>必填欄位</th>
                                        <th style={{ padding: '10px 12px', textAlign: 'center', fontWeight: 600 }}>選填欄位</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {templates.map(template => (
                                        <tr
                                            key={template.id}
                                            style={{
                                                borderBottom: '1px solid #f3f4f6',
                                                background: template.doc_code === null ? '#eff6ff' : editingId === template.id ? '#f0fdf4' : 'transparent',
                                            }}
                                        >
                                            <td style={{ padding: '10px 12px' }}>
                                                <div style={{ display: 'flex', gap: '4px' }}>
                                                    {canEdit(template) ? (
                                                        <>
                                                            <button
                                                                onClick={() => handleEditClick(template)}
                                                                style={{ padding: '4px', background: 'none', border: 'none', cursor: 'pointer' }}
                                                                title="編輯"
                                                            >
                                                                <Edit2 size={14} color="#3b82f6" />
                                                            </button>
                                                            <button
                                                                onClick={() => handleCopyClick(template)}
                                                                style={{ padding: '4px', background: 'none', border: 'none', cursor: 'pointer' }}
                                                                title="複製"
                                                            >
                                                                <Copy size={14} color="#6b7280" />
                                                            </button>
                                                            <button
                                                                onClick={() => handleDelete(template.id)}
                                                                style={{ padding: '4px', background: 'none', border: 'none', cursor: 'pointer' }}
                                                                title="刪除"
                                                            >
                                                                <Trash2 size={14} color="#dc2626" />
                                                            </button>
                                                        </>
                                                    ) : (
                                                        <button
                                                            onClick={() => handleCopyClick(template)}
                                                            style={{ padding: '4px', background: 'none', border: 'none', cursor: 'pointer' }}
                                                            title="複製"
                                                        >
                                                            <Copy size={14} color="#6b7280" />
                                                        </button>
                                                    )}
                                                </div>
                                            </td>
                                            <td style={{ padding: '10px 12px', fontWeight: 500 }}>{template.op_type}</td>
                                            <td style={{ padding: '10px 12px' }}>
                                                {template.doc_code === null ? (
                                                    <span style={{ padding: '2px 8px', background: '#dbeafe', borderRadius: '10px', fontSize: '11px' }}>GLOBAL</span>
                                                ) : (
                                                    <span style={{ padding: '2px 8px', background: '#f3f4f6', borderRadius: '10px', fontSize: '11px' }}>{template.doc_code}</span>
                                                )}
                                            </td>
                                            <td style={{ padding: '10px 12px', maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                                {template.op_name}
                                            </td>
                                            <td style={{ padding: '10px 12px', textAlign: 'center' }}>
                                                {template.required_fields?.length || 0}
                                            </td>
                                            <td style={{ padding: '10px 12px', textAlign: 'center' }}>
                                                {template.optional_fields?.length || 0}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </Card>
            </div>
        </div>
    );
}

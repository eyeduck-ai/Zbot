/**
 * ConfigSetupPage - 首次環境設定頁面
 * 
 * 當系統偵測到沒有設定檔時顯示，讓使用者設定 Supabase 連線資訊。
 */

import { useState } from 'react';
import { Settings, CheckCircle, XCircle, Loader2, HelpCircle } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Logo } from '../components/ui/Logo';

interface ConfigSetupPageProps {
    onComplete: () => void;
    configPath: string;
}

export default function ConfigSetupPage({ onComplete, configPath }: ConfigSetupPageProps) {
    // Form state
    const [supabaseUrl, setSupabaseUrl] = useState('');
    const [supabaseKey, setSupabaseKey] = useState('');
    const [devMode, setDevMode] = useState(false);
    const [logLevel, setLogLevel] = useState('INFO');
    // Advanced - EIP Test Account
    const [testEipId, setTestEipId] = useState('');
    const [testEipPsw, setTestEipPsw] = useState('');

    // UI state
    const [testing, setTesting] = useState(false);
    const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');

    // Test connection
    const handleTest = async () => {
        setTesting(true);
        setTestResult(null);
        setError('');

        try {
            const res = await fetch('/api/config/test', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    supabase_url: supabaseUrl,
                    supabase_key: supabaseKey,
                }),
            });

            const data = await res.json();
            setTestResult(data);
        } catch (err: any) {
            setTestResult({ success: false, message: '無法連接到伺服器' });
        } finally {
            setTesting(false);
        }
    };

    // Save config
    const handleSave = async () => {
        setSaving(true);
        setError('');

        try {
            const res = await fetch('/api/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    supabase_url: supabaseUrl,
                    supabase_key: supabaseKey,
                    dev_mode: devMode,
                    log_level: logLevel,
                    test_eip_id: testEipId || undefined,
                    test_eip_psw: testEipPsw || undefined,
                }),
            });

            const data = await res.json();

            if (data.success) {
                onComplete();
            } else {
                setError(data.detail || '儲存失敗');
            }
        } catch (err: any) {
            setError(err.message || '發生錯誤');
        } finally {
            setSaving(false);
        }
    };

    const isFormValid = supabaseUrl.startsWith('https://') && supabaseKey.length > 20;

    return (
        <div className="min-h-screen w-full flex flex-col items-center justify-center bg-[#F5F5F7] p-4 relative overflow-hidden">
            {/* Ambient Background */}
            <div className="absolute top-[-20%] left-[-10%] w-[60%] h-[60%] bg-amber-200/30 rounded-full blur-3xl opacity-50 pointer-events-none"></div>
            <div className="absolute bottom-[-10%] right-[-5%] w-[50%] h-[50%] bg-orange-200/30 rounded-full blur-3xl opacity-50 pointer-events-none"></div>

            <div className="w-full max-w-[480px] relative z-10">
                <div className="flex flex-col items-center mb-8">
                    <Logo size={48} />
                    <p style={{
                        fontSize: '0.875rem',
                        color: '#6b7280',
                        marginTop: '16px',
                        textAlign: 'center'
                    }}>
                        歡迎使用 Zbot！請先完成環境設定
                    </p>
                </div>

                <Card className="w-full shadow-2xl backdrop-blur-xl bg-white/80 border border-white/40 ring-1 ring-black/5">
                    {error && (
                        <div className="mb-4 flex justify-center">
                            <Badge variant="error" className="py-1 px-3 w-full justify-center text-center">
                                {error}
                            </Badge>
                        </div>
                    )}

                    <div className="space-y-5 p-2">
                        {/* Supabase URL */}
                        <div>
                            <Input
                                label="Supabase URL"
                                placeholder="https://xxxxx.supabase.co"
                                value={supabaseUrl}
                                onChange={e => setSupabaseUrl(e.target.value)}
                                required
                            />
                            <p style={{ fontSize: '0.75rem', color: '#9ca3af', marginTop: '4px' }}>
                                從 Supabase Dashboard → Settings → API → Project URL 取得
                            </p>
                        </div>

                        {/* Supabase Key */}
                        <div>
                            <Input
                                label="Supabase Key"
                                placeholder="sb_publishable_xxxxx 或 eyJhbGciOi..."
                                value={supabaseKey}
                                onChange={e => setSupabaseKey(e.target.value)}
                                required
                            />
                            <p style={{ fontSize: '0.75rem', color: '#9ca3af', marginTop: '4px' }}>
                                建議使用 anon/public key（從 Project API keys 取得）
                            </p>
                        </div>

                        {/* Test Connection Button */}
                        <div>
                            <Button
                                type="button"
                                variant="secondary"
                                onClick={handleTest}
                                disabled={!isFormValid || testing}
                                className="w-full"
                            >
                                {testing ? (
                                    <>
                                        <Loader2 size={16} className="animate-spin mr-2" />
                                        測試中...
                                    </>
                                ) : (
                                    '測試連線'
                                )}
                            </Button>

                            {testResult && (
                                <div style={{
                                    marginTop: '8px',
                                    padding: '8px 12px',
                                    borderRadius: '8px',
                                    backgroundColor: testResult.success ? '#f0fdf4' : '#fef2f2',
                                    border: `1px solid ${testResult.success ? '#bbf7d0' : '#fecaca'}`,
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '8px',
                                }}>
                                    {testResult.success ? (
                                        <CheckCircle size={16} style={{ color: '#22c55e' }} />
                                    ) : (
                                        <XCircle size={16} style={{ color: '#ef4444' }} />
                                    )}
                                    <span style={{
                                        fontSize: '0.875rem',
                                        color: testResult.success ? '#166534' : '#dc2626'
                                    }}>
                                        {testResult.message}
                                    </span>
                                </div>
                            )}
                        </div>

                        {/* Divider */}
                        <hr style={{ border: 'none', borderTop: '1px solid #e5e7eb', margin: '16px 0' }} />

                        {/* Advanced Settings */}
                        <details style={{ fontSize: '0.875rem' }}>
                            <summary style={{
                                cursor: 'pointer',
                                color: '#6b7280',
                                display: 'flex',
                                alignItems: 'center',
                                gap: '4px'
                            }}>
                                <Settings size={14} />
                                進階設定
                            </summary>
                            <div style={{ marginTop: '12px', paddingLeft: '18px' }} className="space-y-4">
                                {/* Dev Mode */}
                                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                                    <input
                                        type="checkbox"
                                        checked={devMode}
                                        onChange={e => setDevMode(e.target.checked)}
                                        style={{ width: '16px', height: '16px' }}
                                    />
                                    <span>開發模式（不實際送出資料到內網）</span>
                                </label>

                                {/* Log Level */}
                                <div>
                                    <label style={{ display: 'block', marginBottom: '4px', color: '#374151' }}>
                                        日誌等級
                                    </label>
                                    <select
                                        value={logLevel}
                                        onChange={e => setLogLevel(e.target.value)}
                                        style={{
                                            width: '100%',
                                            padding: '8px 12px',
                                            borderRadius: '8px',
                                            border: '1px solid #e5e7eb',
                                            backgroundColor: 'white',
                                            fontSize: '0.875rem',
                                        }}
                                    >
                                        <option value="DEBUG">DEBUG</option>
                                        <option value="INFO">INFO</option>
                                        <option value="WARNING">WARNING</option>
                                        <option value="ERROR">ERROR</option>
                                    </select>
                                </div>

                                {/* Divider in advanced */}
                                <hr style={{ border: 'none', borderTop: '1px dashed #e5e7eb', margin: '12px 0' }} />

                                {/* TEST EIP Account */}
                                <p style={{ fontSize: '0.75rem', color: '#9ca3af', marginBottom: '8px' }}>
                                    測試用 EIP 帳號（可選，用於開發測試）
                                </p>
                                <div style={{ display: 'flex', gap: '8px' }}>
                                    <input
                                        type="text"
                                        placeholder="EIP ID (e.g. DOC4050H)"
                                        value={testEipId}
                                        onChange={e => setTestEipId(e.target.value)}
                                        style={{
                                            flex: 1,
                                            padding: '8px 12px',
                                            borderRadius: '8px',
                                            border: '1px solid #e5e7eb',
                                            fontSize: '0.875rem',
                                        }}
                                    />
                                    <input
                                        type="password"
                                        placeholder="Password"
                                        value={testEipPsw}
                                        onChange={e => setTestEipPsw(e.target.value)}
                                        style={{
                                            flex: 1,
                                            padding: '8px 12px',
                                            borderRadius: '8px',
                                            border: '1px solid #e5e7eb',
                                            fontSize: '0.875rem',
                                        }}
                                    />
                                </div>
                            </div>
                        </details>

                        {/* Save Button */}
                        <Button
                            type="button"
                            variant="primary"
                            onClick={handleSave}
                            disabled={!isFormValid || saving}
                            className="w-full mt-4"
                            size="lg"
                            isLoading={saving}
                        >
                            儲存並繼續
                        </Button>
                    </div>
                </Card>

                {/* Config Path Info */}
                <div className="mt-4 text-center">
                    <p style={{
                        fontSize: '0.75rem',
                        color: '#9ca3af',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '4px'
                    }}>
                        <HelpCircle size={12} />
                        設定檔將儲存於: {configPath}
                    </p>
                </div>
            </div>
        </div>
    );
}

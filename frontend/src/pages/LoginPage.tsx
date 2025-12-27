
import React, { useState, useEffect } from 'react';
import { Eye, EyeOff } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Logo } from '../components/ui/Logo';
import { authApi } from '../api/auth';

// 狀態類型
interface SystemStatus {
    intranet: { status: 'ok' | 'error' | 'unknown' };
    database: { status: 'ok' | 'error' | 'unknown' };
}

// 狀態指標元件 - 支援 loading 狀態
const StatusDot = ({ status, isLoading }: { status: 'ok' | 'error' | 'unknown', isLoading?: boolean }) => {
    const color = isLoading ? '#60a5fa' :
        status === 'ok' ? '#22c55e' :
            status === 'error' ? '#ef4444' : '#9ca3af';

    return (
        <span style={{
            display: 'inline-block',
            width: '8px',
            height: '8px',
            borderRadius: '50%',
            backgroundColor: color,
            marginRight: '8px',
            boxShadow: status === 'ok' && !isLoading ? '0 0 4px rgba(34, 197, 94, 0.5)' : 'none',
            animation: isLoading ? 'pulse 1.5s ease-in-out infinite' : 'none',
        }} />
    );
};

export default function LoginPage() {
    const { login } = useAuth();
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const [statusLoading, setStatusLoading] = useState(true); // 狀態檢查中
    const [systemStatus, setSystemStatus] = useState<SystemStatus>({
        intranet: { status: 'unknown' },
        database: { status: 'unknown' }
    });


    // 檢查系統狀態並取得角色定義
    useEffect(() => {
        const checkStatus = async () => {
            setStatusLoading(true);
            try {
                const data = await authApi.checkStatus();
                setSystemStatus({
                    intranet: { status: (data as any).intranet?.status || 'unknown' },
                    database: { status: (data as any).database?.status || 'unknown' }
                });

                // 儲存角色定義到 localStorage 供 Sidebar 使用
                if ((data as any).role_definitions) {
                    localStorage.setItem('role_definitions', JSON.stringify((data as any).role_definitions));
                }
            } catch {
                // 無法連線到後端，保持 unknown
            } finally {
                setStatusLoading(false);
            }
        };

        checkStatus();
        // 每 30 秒重新檢查
        const interval = setInterval(checkStatus, 30000);
        return () => clearInterval(interval);
    }, []);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setLoading(true);

        try {
            // 登入 API 使用 x-www-form-urlencoded 格式
            const formData = new URLSearchParams();
            formData.append('username', username);
            formData.append('password', password);

            const res = await fetch('/api/auth/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: formData,
            });

            if (!res.ok) {
                throw new Error('登入失敗，請檢查帳號密碼');
            }

            const data = await res.json();
            // 從 JWT 解析 displayName 和 role
            const payload = JSON.parse(atob(data.access_token.split('.')[1]));
            // 傳遞 EIP 帳密供爬蟲任務使用 (使用 zbot_role 作為應用程式角色)
            login(data.access_token, username, payload.display_name || username, payload.zbot_role || '', username, password);
        } catch (err: any) {
            setError(err.message || 'An error occurred');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen w-full flex flex-col items-center justify-center bg-[#F5F5F7] p-4 relative overflow-hidden">
            {/* Ambient Background */}
            <div className="absolute top-[-20%] left-[-10%] w-[60%] h-[60%] bg-blue-200/30 rounded-full blur-3xl opacity-50 pointer-events-none"></div>
            <div className="absolute bottom-[-10%] right-[-5%] w-[50%] h-[50%] bg-purple-200/30 rounded-full blur-3xl opacity-50 pointer-events-none"></div>

            <div className="w-full max-w-[400px] relative z-10">
                <div className="flex flex-col items-center mb-10">
                    <Logo size={56} />
                </div>

                <Card className="w-full shadow-2xl backdrop-blur-xl bg-white/70 border border-white/40 ring-1 ring-black/5">
                    {error && (
                        <div className="mb-6 flex justify-center">
                            <Badge variant="error" className="py-1 px-3 w-full justify-center text-center">{error}</Badge>
                        </div>
                    )}

                    <form onSubmit={handleSubmit} className="space-y-5 p-2">
                        <Input
                            label="WEB9 / EIP ID"
                            placeholder="e.g. DOC4123J"
                            value={username}
                            onChange={e => setUsername(e.target.value)}
                            required
                        />

                        <div style={{ position: 'relative' }}>
                            <Input
                                label="Password"
                                type={showPassword ? 'text' : 'password'}
                                value={password}
                                onChange={e => setPassword(e.target.value)}
                                required
                            />
                            <button
                                type="button"
                                onClick={() => setShowPassword(!showPassword)}
                                style={{
                                    position: 'absolute',
                                    right: '12px',
                                    bottom: '10px',
                                    background: 'none',
                                    border: 'none',
                                    cursor: 'pointer',
                                    padding: '4px',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    color: '#6b7280',
                                }}
                                tabIndex={-1}
                            >
                                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                            </button>
                        </div>

                        <Button
                            type="submit"
                            variant="primary"
                            className="w-full mt-2"
                            size="lg"
                            isLoading={loading}
                            disabled={!statusLoading && (
                                // 非 DOC 帳號（平台帳號）：只需資料庫連線
                                // DOC 帳號：需要內網 + 資料庫
                                !username.toUpperCase().startsWith('DOC')
                                    ? systemStatus.database.status === 'error'
                                    : (systemStatus.intranet.status === 'error' || systemStatus.database.status === 'error')
                            )}
                        >
                            Sign In
                        </Button>
                    </form>
                </Card>

                {/* 連線狀態指標 */}
                <div className="mt-6 flex justify-center gap-6 text-xs text-[var(--text-secondary)]">
                    <div className="flex items-center">
                        <StatusDot status={systemStatus.intranet.status} isLoading={statusLoading} />
                        <span style={{ opacity: 0.8 }}>內網{statusLoading ? '連線中...' : '連線'}</span>
                    </div>
                    <div className="flex items-center">
                        <StatusDot status={systemStatus.database.status} isLoading={statusLoading} />
                        <span style={{ opacity: 0.8 }}>資料庫{statusLoading ? '連線中...' : '連線'}</span>
                    </div>
                </div>

                {/* 連線錯誤警告 */}
                {!statusLoading && (systemStatus.intranet.status === 'error' || systemStatus.database.status === 'error') && (
                    <div className="mt-4 text-center p-3 bg-red-50 border border-red-200 rounded-lg">
                        <p className="text-xs text-red-600" style={{ lineHeight: 1.6 }}>
                            {systemStatus.intranet.status === 'error' && systemStatus.database.status === 'error' && (
                                <>⚠️ 內網及資料庫連線異常，無法登入<br />請確認您在院內網路環境，並聯繫系統管理員</>
                            )}
                            {systemStatus.intranet.status === 'error' && systemStatus.database.status !== 'error' && (
                                <>⚠️ 內網連線異常，無法登入<br />請確認您在院內 VPN 或院區網路環境</>
                            )}
                            {systemStatus.intranet.status !== 'error' && systemStatus.database.status === 'error' && (
                                <>⚠️ 資料庫連線異常，無法登入<br />請稍後再試或聯繫系統管理員</>
                            )}
                        </p>
                    </div>
                )}

                {/* CSS Animation for pulse */}
                <style>{`
                    @keyframes pulse {
                        0%, 100% { opacity: 1; transform: scale(1); }
                        50% { opacity: 0.5; transform: scale(0.85); }
                    }
                `}</style>

                <div className="mt-4 text-center">
                    <p className="text-xs text-[var(--text-secondary)] opacity-60">
                        &copy; 2025 Zbot. All rights reserved.
                    </p>
                </div>
            </div>
        </div>
    );
}

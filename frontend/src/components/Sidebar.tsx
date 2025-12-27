import React from 'react';
import { useAuth } from '../context/AuthContext';
import {
    Syringe,
    Stethoscope,
    BedDouble,
    BarChart3,
    Receipt,
    LogOut,
    Lock,
    ChevronLeft,
    ChevronRight,
    FileSpreadsheet,
    FileText,
    ClipboardList,
    ShieldCheck,
    Boxes,
    Bug,
    FlaskConical,
    Activity,
} from 'lucide-react';
import { LOGO_IMAGE_PATH } from './ui/Logo';

export type ToolId = 'ivi' | 'surgery' | 'bed' | 'stats_op' | 'stats_fee' | 'opd_order' | 'nhi_review' | 'sheets_settings' | 'templates_settings' | 'opd_set' | 'bug_report' | 'pricing' | 'task_stats';

interface Tool {
    id: ToolId;
    name: string;
    icon: React.ReactNode;
    prefix: string; // 權限前綴
    isBeta?: boolean; // 是否為測試中功能
}

// 工具列表
const TOOLS: Tool[] = [
    { id: 'ivi', name: 'IVI紀錄', icon: <Syringe size={20} />, prefix: 'note_ivi_' },
    { id: 'surgery', name: '手術紀錄', icon: <Stethoscope size={20} />, prefix: 'note_' },
    { id: 'bed', name: '待床追蹤', icon: <BedDouble size={20} />, prefix: 'dashboard_' },
    { id: 'stats_op', name: '統計_手術排程', icon: <BarChart3 size={20} />, prefix: 'stats_' },
    { id: 'stats_fee', name: '統計_收費碼', icon: <Receipt size={20} />, prefix: 'stats_' },
    { id: 'opd_order', name: '門診系統開單', icon: <ClipboardList size={20} />, prefix: 'tool_opd_order', isBeta: true },
    { id: 'nhi_review', name: '健保事審', icon: <ShieldCheck size={20} />, prefix: 'tool_nhi_review', isBeta: true },
];

// 設定列表
const SETTINGS: Tool[] = [
    { id: 'sheets_settings', name: 'Google刀表設定', icon: <FileSpreadsheet size={20} />, prefix: 'settings_gsheets' },
    { id: 'templates_settings', name: '手術範本設定', icon: <FileText size={20} />, prefix: 'settings_templates' },
    { id: 'opd_set', name: '門診系統組套', icon: <Boxes size={20} />, prefix: 'settings_opd_set', isBeta: true },
    { id: 'bug_report', name: 'Bug/升等申請', icon: <Bug size={20} />, prefix: 'settings_bug_report' },
    // { id: 'pricing', name: '方案選擇', icon: <CreditCard size={20} />, prefix: 'settings_pricing', isBeta: true },
    { id: 'task_stats', name: '任務統計', icon: <Activity size={20} />, prefix: 'admin_only_' },  // Admin 專用，放最下面
];

// 預設角色權限 (fallback when not loaded from DB)
const DEFAULT_ROLE_PERMISSIONS: Record<string, string[]> = {
    admin: ['*'],
    basic_0: [],  // 初心者Lv.0: 無權限
    basic_1: ['note_ivi_', 'opnote_'],  // 初心者Lv.1: 僅 IVI
    basic_2: ['note_', 'opnote_'],  // 奴工: IVI + Surgery
    cr: ['note_', 'opnote_', 'dashboard_', 'stats_'],
    '': [],  // 未設定角色: 無權限 (同 basic_0)
};

const DEFAULT_ROLE_NAMES: Record<string, string> = {
    admin: '管理員',
    cr: 'CR',
    basic_2: '奴工',
    basic_1: '初心者Lv.1',
    basic_0: '初心者Lv.0',
    '': '初心者Lv.0',
};

// 從 localStorage 取得角色定義
function getRoleDefinitions(): Record<string, { display_name: string; allowed_prefixes: string[] }> {
    try {
        const stored = localStorage.getItem('role_definitions');
        if (stored) {
            return JSON.parse(stored);
        }
    } catch {
        // 解析失敗，使用預設值
    }
    return {};
}

// 取得角色允許的前綴
function getAllowedPrefixes(role: string): string[] {
    const defs = getRoleDefinitions();
    if (defs[role]?.allowed_prefixes) {
        return defs[role].allowed_prefixes;
    }
    return DEFAULT_ROLE_PERMISSIONS[role] || [];
}

// 取得角色顯示名稱
function getRoleDisplayName(role: string): string {
    const defs = getRoleDefinitions();
    if (defs[role]?.display_name) {
        return defs[role].display_name;
    }
    return DEFAULT_ROLE_NAMES[role] || '初心者Lv.0';
}

interface SidebarProps {
    activeTool: ToolId;
    onToolSelect: (tool: ToolId) => void;
    collapsed: boolean;
    onToggleCollapse: () => void;
}

// 自訂 Tooltip 元件
const Tooltip = ({ children, text, show }: { children: React.ReactNode; text: string; show: boolean }) => {
    const [isHovered, setIsHovered] = React.useState(false);

    if (!show) return <>{children}</>;

    return (
        <div
            style={{ position: 'relative', display: 'contents' }}
            onMouseEnter={() => setIsHovered(true)}
            onMouseLeave={() => setIsHovered(false)}
        >
            {children}
            {isHovered && (
                <div style={{
                    position: 'fixed',
                    left: '50%',
                    transform: 'translateX(-50%)',
                    bottom: '80px',
                    backgroundColor: 'rgba(31, 41, 55, 0.95)',
                    color: 'white',
                    padding: '8px 12px',
                    borderRadius: '6px',
                    fontSize: '12px',
                    fontWeight: 500,
                    whiteSpace: 'nowrap',
                    zIndex: 9999,
                    boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
                    animation: 'fadeIn 0.15s ease-out',
                }}>
                    {text}
                </div>
            )}
            <style>{`
                @keyframes fadeIn {
                    from { opacity: 0; transform: translateX(-50%) translateY(4px); }
                    to { opacity: 1; transform: translateX(-50%) translateY(0); }
                }
            `}</style>
        </div>
    );
};

export const Sidebar: React.FC<SidebarProps> = ({ activeTool, onToolSelect, collapsed, onToggleCollapse }) => {
    const { user, displayName, role, logout } = useAuth();

    // 檢查權限 (使用動態角色定義)
    const hasPermission = (prefix: string): boolean => {
        // 空 prefix 表示所有登入使用者可用 (如 sheets_settings)
        if (prefix === '') return true;
        // 只有 null/undefined 才視為無權限
        if (role === null || role === undefined) return false;
        // admin_only_ 前綴只有 admin 可用 (開發者專用)
        if (prefix.startsWith('admin_only_')) {
            return role === 'admin';
        }
        const allowedPrefixes = getAllowedPrefixes(role);
        if (allowedPrefixes.includes('*')) return true;
        return allowedPrefixes.some((p: string) => prefix.startsWith(p) || p.startsWith(prefix));
    };

    // 收合模式的寬度與樣式
    const sidebarWidth = collapsed ? '64px' : '280px';

    return (
        <aside style={{
            width: sidebarWidth,
            minWidth: sidebarWidth,
            height: '100vh',
            position: 'sticky',
            top: 0,
            backgroundColor: '#ffffff',
            borderRight: '1px solid #e0e7ee',
            display: 'flex',
            flexDirection: 'column',
            fontFamily: '"Manrope", "Noto Sans", sans-serif',
            transition: 'width 0.3s ease, min-width 0.3s ease',
            zIndex: 1000,
        }}>
            {/* Toggle Button */}
            <button
                onClick={onToggleCollapse}
                style={{
                    position: 'absolute',
                    top: '72px',
                    right: '-12px',
                    width: '24px',
                    height: '24px',
                    borderRadius: '50%',
                    border: '1px solid #e0e7ee',
                    backgroundColor: '#ffffff',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    cursor: 'pointer',
                    zIndex: 9999,
                    boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
                    transition: 'all 0.2s',
                }}
                onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = '#eef4fd';
                    e.currentTarget.style.borderColor = '#137fec';
                }}
                onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = '#ffffff';
                    e.currentTarget.style.borderColor = '#e0e7ee';
                }}
                title={collapsed ? '展開選單' : '收合選單'}
            >
                {collapsed ? <ChevronRight size={14} color="#6b7280" /> : <ChevronLeft size={14} color="#6b7280" />}
            </button>

            {/* Logo */}
            {/* Logo - 更換 logo 只需修改 Logo.tsx 中的 LOGO_IMAGE_PATH */}
            <div style={{
                height: '64px',
                display: 'flex',
                alignItems: 'center',
                padding: collapsed ? '0 16px' : '0 24px',
                borderBottom: '1px solid #e0e7ee',
                justifyContent: collapsed ? 'center' : 'flex-start',
                overflow: 'hidden',
            }}>
                <img
                    src={LOGO_IMAGE_PATH}
                    alt="Zbot Logo"
                    style={{
                        width: '32px',
                        height: '32px',
                        objectFit: 'contain',
                        marginRight: collapsed ? '0' : '12px',
                        flexShrink: 0,
                    }}
                />
                {!collapsed && (
                    <span style={{
                        fontFamily: '"Oxanium", sans-serif',
                        fontSize: '1.25rem',
                        fontWeight: 600,
                        color: '#1f2937',
                        letterSpacing: '-0.025em',
                        wordSpacing: '0.1em',
                        whiteSpace: 'nowrap',
                    }}>
                        Zbot <span style={{ fontWeight: 400, color: '#4b5563', fontSize: '0.95em' }}>Workflow</span>
                    </span>
                )}
            </div>

            {/* Navigation */}
            <nav style={{
                flex: 1,
                overflowY: 'auto',
                padding: collapsed ? '24px 8px' : '24px 16px',
            }}>
                {!collapsed && (
                    <p style={{
                        fontSize: '11px',
                        fontWeight: 600,
                        color: '#6b7280',
                        textTransform: 'uppercase',
                        letterSpacing: '0.05em',
                        padding: '0 12px',
                        marginBottom: '8px',
                    }}>工具</p>
                )}

                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    {TOOLS.map(tool => {
                        const isActive = activeTool === tool.id;
                        const allowed = hasPermission(tool.prefix);

                        return (
                            <Tooltip
                                key={tool.id}
                                text={`${tool.name} - 等級不夠無法使用`}
                                show={!allowed}
                            >
                                <button
                                    onClick={() => allowed && onToolSelect(tool.id)}
                                    disabled={!allowed}
                                    style={{
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: collapsed ? 'center' : 'flex-start',
                                        gap: collapsed ? '0' : '12px',
                                        padding: collapsed ? '10px' : '10px 12px',
                                        borderRadius: '8px',
                                        border: isActive ? '1px solid rgba(19, 127, 236, 0.2)' : '1px solid transparent',
                                        backgroundColor: isActive ? 'rgba(19, 127, 236, 0.1)' : 'transparent',
                                        color: isActive ? '#137fec' : allowed ? '#6b7280' : '#9ca3af',
                                        cursor: allowed ? 'pointer' : 'not-allowed',
                                        opacity: allowed ? 1 : 0.6,
                                        transition: 'all 0.2s',
                                        width: '100%',
                                        textAlign: 'left',
                                        fontSize: '14px',
                                        fontWeight: 500,
                                    }}
                                    onMouseEnter={(e) => {
                                        if (allowed && !isActive) {
                                            e.currentTarget.style.backgroundColor = '#eef4fd';
                                            e.currentTarget.style.color = '#1f2937';
                                        }
                                    }}
                                    onMouseLeave={(e) => {
                                        if (allowed && !isActive) {
                                            e.currentTarget.style.backgroundColor = 'transparent';
                                            e.currentTarget.style.color = '#6b7280';
                                        }
                                    }}
                                    title={collapsed ? tool.name : undefined}
                                >
                                    <span style={{
                                        color: isActive ? '#137fec' : allowed ? '#6b7280' : '#9ca3af',
                                        flexShrink: 0,
                                    }}>
                                        {tool.icon}
                                    </span>
                                    {!collapsed && (
                                        <>
                                            <span style={{ flex: 1 }}>{tool.name}</span>
                                            {!allowed ? (
                                                <span style={{
                                                    display: 'flex',
                                                    alignItems: 'center',
                                                    gap: '4px',
                                                    fontSize: '11px',
                                                    color: '#9ca3af',
                                                }}>
                                                    <Lock size={12} />
                                                    <span style={{ whiteSpace: 'nowrap' }}>等級不夠</span>
                                                </span>
                                            ) : tool.isBeta && (
                                                <span style={{
                                                    display: 'flex',
                                                    alignItems: 'center',
                                                    gap: '4px',
                                                    fontSize: '11px',
                                                    color: '#d97706',
                                                    backgroundColor: '#fef3c7',
                                                    padding: '2px 6px',
                                                    borderRadius: '4px',
                                                }}>
                                                    <FlaskConical size={10} />
                                                    <span style={{ whiteSpace: 'nowrap' }}>測試中..</span>
                                                </span>
                                            )}
                                        </>
                                    )}
                                </button>
                            </Tooltip>
                        );
                    })}
                </div>

                {/* 設定區塊分隔線 */}
                <div style={{
                    height: '1px',
                    backgroundColor: '#e5e7eb',
                    margin: collapsed ? '16px 4px' : '16px 12px',
                }} />

                {!collapsed && (
                    <p style={{
                        fontSize: '11px',
                        fontWeight: 600,
                        color: '#6b7280',
                        textTransform: 'uppercase',
                        letterSpacing: '0.05em',
                        padding: '0 12px',
                        marginBottom: '8px',
                    }}>設定</p>
                )}

                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    {SETTINGS
                        // 過濾 admin_only_ 前綴項目：對非 admin 完全隱藏
                        .filter(tool => !tool.prefix.startsWith('admin_only_') || role === 'admin')
                        .map(tool => {
                            const isActive = activeTool === tool.id;
                            const allowed = hasPermission(tool.prefix);

                            return (
                                <Tooltip
                                    key={tool.id}
                                    text={`${tool.name} - 等級不夠無法使用`}
                                    show={!allowed}
                                >
                                    <button
                                        onClick={() => allowed && onToolSelect(tool.id)}
                                        disabled={!allowed}
                                        style={{
                                            display: 'flex',
                                            alignItems: 'center',
                                            justifyContent: collapsed ? 'center' : 'flex-start',
                                            gap: collapsed ? '0' : '12px',
                                            padding: collapsed ? '10px' : '10px 12px',
                                            borderRadius: '8px',
                                            border: isActive ? '1px solid rgba(19, 127, 236, 0.2)' : '1px solid transparent',
                                            backgroundColor: isActive ? 'rgba(19, 127, 236, 0.1)' : 'transparent',
                                            color: isActive ? '#137fec' : allowed ? '#6b7280' : '#9ca3af',
                                            cursor: allowed ? 'pointer' : 'not-allowed',
                                            opacity: allowed ? 1 : 0.6,
                                            transition: 'all 0.2s',
                                            width: '100%',
                                            textAlign: 'left',
                                            fontSize: '14px',
                                            fontWeight: 500,
                                        }}
                                        onMouseEnter={(e) => {
                                            if (allowed && !isActive) {
                                                e.currentTarget.style.backgroundColor = '#eef4fd';
                                                e.currentTarget.style.color = '#1f2937';
                                            }
                                        }}
                                        onMouseLeave={(e) => {
                                            if (allowed && !isActive) {
                                                e.currentTarget.style.backgroundColor = 'transparent';
                                                e.currentTarget.style.color = '#6b7280';
                                            }
                                        }}
                                        title={collapsed ? tool.name : undefined}
                                    >
                                        <span style={{
                                            color: isActive ? '#137fec' : allowed ? '#6b7280' : '#9ca3af',
                                            flexShrink: 0,
                                        }}>
                                            {tool.icon}
                                        </span>
                                        {!collapsed && (
                                            <>
                                                <span style={{ flex: 1 }}>{tool.name}</span>
                                                {!allowed ? (
                                                    <span style={{
                                                        display: 'flex',
                                                        alignItems: 'center',
                                                        gap: '4px',
                                                        fontSize: '11px',
                                                        color: '#9ca3af',
                                                    }}>
                                                        <Lock size={12} />
                                                        <span style={{ whiteSpace: 'nowrap' }}>等級不夠</span>
                                                    </span>
                                                ) : tool.isBeta && (
                                                    <span style={{
                                                        display: 'flex',
                                                        alignItems: 'center',
                                                        gap: '4px',
                                                        fontSize: '11px',
                                                        color: '#d97706',
                                                        backgroundColor: '#fef3c7',
                                                        padding: '2px 6px',
                                                        borderRadius: '4px',
                                                    }}>
                                                        <FlaskConical size={10} />
                                                        <span style={{ whiteSpace: 'nowrap' }}>測試中..</span>
                                                    </span>
                                                )}
                                            </>
                                        )}
                                    </button>
                                </Tooltip>
                            );
                        })}
                </div>
            </nav>

            {/* User Info */}
            <div style={{
                padding: collapsed ? '12px 8px' : '16px',
                borderTop: '1px solid #e0e7ee',
            }}>
                <div style={{
                    backgroundColor: '#eef4fd',
                    borderRadius: '12px',
                    padding: collapsed ? '10px' : '12px',
                    display: 'flex',
                    alignItems: collapsed ? 'center' : 'center',
                    justifyContent: collapsed ? 'center' : 'flex-start',
                    flexDirection: collapsed ? 'column' : 'row',
                    gap: collapsed ? '8px' : '12px',
                }}>
                    <div style={{
                        width: '36px',
                        height: '36px',
                        borderRadius: '50%',
                        background: 'linear-gradient(135deg, #137fec 0%, #0d5bba 100%)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: 'white',
                        fontWeight: 600,
                        fontSize: '14px',
                        flexShrink: 0,
                    }}>
                        {(displayName || user || 'U').charAt(0).toUpperCase()}
                    </div>
                    {!collapsed && (
                        <>
                            <div style={{ flex: 1, overflow: 'hidden' }}>
                                <p style={{
                                    fontSize: '14px',
                                    fontWeight: 600,
                                    color: '#1f2937',
                                    margin: 0,
                                    whiteSpace: 'nowrap',
                                    overflow: 'hidden',
                                    textOverflow: 'ellipsis',
                                }}>
                                    {displayName || user || '使用者'}
                                </p>
                                <p style={{
                                    fontSize: '12px',
                                    color: '#6b7280',
                                    margin: 0,
                                }}>
                                    {getRoleDisplayName(role || '')}
                                </p>
                            </div>
                        </>
                    )}
                    <button
                        onClick={logout}
                        style={{
                            padding: '8px',
                            borderRadius: '8px',
                            border: 'none',
                            backgroundColor: 'transparent',
                            color: '#6b7280',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                        }}
                        onMouseEnter={(e) => {
                            e.currentTarget.style.backgroundColor = '#fee2e2';
                            e.currentTarget.style.color = '#ef4444';
                        }}
                        onMouseLeave={(e) => {
                            e.currentTarget.style.backgroundColor = 'transparent';
                            e.currentTarget.style.color = '#6b7280';
                        }}
                        title="登出"
                    >
                        <LogOut size={18} />
                    </button>
                </div>
            </div>
        </aside>
    );
};

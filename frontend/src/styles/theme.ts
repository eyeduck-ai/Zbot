/**
 * Theme Constants - 共用主題常數
 * 
 * 用於統一應用程式中的色彩和樣式定義。
 * 避免在各頁面重複定義相同的 THEME 常數。
 * 
 * @example
 * import { THEME, STATUS_STYLES } from '../styles/theme';
 * 
 * <div style={{ backgroundColor: THEME.primaryLight }}>
 *     ...
 * </div>
 */

// =============================================================================
// 主題色常數
// =============================================================================

export const THEME = {
    // 主要色
    primary: '#137fec',
    primaryLight: '#eef4fd',
    primaryBorder: 'rgba(19, 127, 236, 0.2)',

    // 成功色
    success: '#22c55e',
    successLight: '#dcfce7',
    successBorder: 'rgba(34, 197, 94, 0.2)',

    // 錯誤色
    error: '#ef4444',
    errorLight: 'rgba(239, 68, 68, 0.1)',
    errorBorder: 'rgba(239, 68, 68, 0.2)',

    // 警告色
    warning: '#f59e0b',
    warningLight: '#fef3c7',
    warningBorder: 'rgba(245, 158, 11, 0.2)',

    // 中性色
    disabled: '#f3f4f6',
    border: '#e5e7eb',
    textPrimary: '#1f2937',
    textSecondary: '#6b7280',
    textMuted: '#9ca3af',
} as const;

// =============================================================================
// 狀態訊息樣式
// =============================================================================

export const STATUS_STYLES = {
    success: {
        backgroundColor: 'rgba(34, 197, 94, 0.1)',
        border: '1px solid rgba(34, 197, 94, 0.2)',
        color: '#15803d',
    },
    error: {
        backgroundColor: 'rgba(239, 68, 68, 0.1)',
        border: '1px solid rgba(239, 68, 68, 0.2)',
        color: '#dc2626',
    },
    info: {
        backgroundColor: 'rgba(59, 130, 246, 0.1)',
        border: '1px solid rgba(59, 130, 246, 0.2)',
        color: '#2563eb',
    },
    warning: {
        backgroundColor: 'rgba(245, 158, 11, 0.1)',
        border: '1px solid rgba(245, 158, 11, 0.2)',
        color: '#d97706',
    },
} as const;

// =============================================================================
// 間距常數
// =============================================================================

export const SPACING = {
    xs: '4px',
    sm: '8px',
    md: '16px',
    lg: '24px',
    xl: '32px',
} as const;

// =============================================================================
// 圓角常數
// =============================================================================

export const RADIUS = {
    sm: '4px',
    md: '8px',
    lg: '12px',
    xl: '16px',
    pill: '9999px',
} as const;

// =============================================================================
// 類型定義
// =============================================================================

export type ThemeColor = keyof typeof THEME;
export type StatusType = keyof typeof STATUS_STYLES;

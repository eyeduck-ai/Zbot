/**
 * Toast 通知元件
 * 
 * 用於顯示頂部通知訊息，支援自動消失和點擊關閉
 * 
 * @example
 * ```tsx
 * const [toast, setToast] = useState<ToastProps | null>(null);
 * 
 * <Toast 
 *   message="操作成功！" 
 *   type="success" 
 *   onClose={() => setToast(null)} 
 * />
 * ```
 */

import React, { useEffect, useState } from 'react';
import { X, CheckCircle, AlertCircle, Info } from 'lucide-react';

export type ToastType = 'success' | 'error' | 'info' | 'warning';

export interface ToastProps {
    message: string;
    type?: ToastType;
    duration?: number;  // 自動消失時間 (毫秒)，預設 5000
    onClose: () => void;
}

const TOAST_STYLES: Record<ToastType, { bg: string; border: string; text: string; icon: typeof CheckCircle }> = {
    success: {
        bg: 'bg-green-50',
        border: 'border-green-200',
        text: 'text-green-700',
        icon: CheckCircle,
    },
    error: {
        bg: 'bg-red-50',
        border: 'border-red-200',
        text: 'text-red-700',
        icon: AlertCircle,
    },
    warning: {
        bg: 'bg-amber-50',
        border: 'border-amber-200',
        text: 'text-amber-700',
        icon: AlertCircle,
    },
    info: {
        bg: 'bg-blue-50',
        border: 'border-blue-200',
        text: 'text-blue-700',
        icon: Info,
    },
};

export const Toast: React.FC<ToastProps> = ({
    message,
    type = 'info',
    duration = 5000,
    onClose
}) => {
    const [isVisible, setIsVisible] = useState(true);
    const [isExiting, setIsExiting] = useState(false);

    const style = TOAST_STYLES[type];
    const IconComponent = style.icon;

    const handleClose = () => {
        setIsExiting(true);
        setTimeout(() => {
            setIsVisible(false);
            onClose();
        }, 300); // 等待淡出動畫完成
    };

    useEffect(() => {
        if (duration > 0) {
            const timer = setTimeout(handleClose, duration);
            return () => clearTimeout(timer);
        }
    }, [duration]);

    if (!isVisible) return null;

    // 計算主內容區域的中心位置
    // Sidebar 展開時: 280px, 收合時: 64px
    // 使用 CSS calc 讓 Toast 位於主內容區域中心
    return (
        <div
            className={`
                fixed top-3 z-50
                flex items-center gap-1.5 rounded-lg shadow-md border
                ${style.bg} ${style.border} ${style.text}
                transition-all duration-300 ease-in-out cursor-pointer
                ${isExiting ? 'opacity-0 -translate-y-2' : 'opacity-100 translate-y-0'}
            `}
            style={{
                // 計算位置：從 sidebar 右邊開始的區域中心
                left: '50%',
                transform: isExiting
                    ? 'translateX(calc(-50% + 140px)) translateY(-8px)'
                    : 'translateX(calc(-50% + 140px))',
                padding: '8px 12px',
                fontSize: '13px',
                fontWeight: 500,
            }}
            onClick={handleClose}
            role="alert"
        >
            <IconComponent size={16} className="flex-shrink-0" />
            <span>{message}</span>
            <button
                onClick={(e) => {
                    e.stopPropagation();
                    handleClose();
                }}
                className="flex-shrink-0 p-0.5 rounded-full hover:bg-black/5 transition-colors ml-1"
            >
                <X size={14} />
            </button>
        </div>
    );
};

export default Toast;

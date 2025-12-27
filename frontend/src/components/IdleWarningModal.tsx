/**
 * IdleWarningModal - 閒置警告對話框
 * 
 * 當使用者閒置時顯示警告，並提供倒數計時與繼續使用按鈕。
 * 倒數秒數由 config.ts 的 IDLE_COUNTDOWN_SECONDS 決定。
 */
import React, { useState, useEffect } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { Button } from './ui/Button';
import { IDLE_COUNTDOWN_SECONDS } from '../config';

// =============================================================================
// Types
// =============================================================================

export interface IdleWarningModalProps {
    /** 倒數秒數，預設 30 */
    countdownSeconds?: number;
    /** 點擊繼續使用時的回調 */
    onContinue: () => void;
    /** 倒數結束時的回調 */
    onLogout: () => void;
}

// =============================================================================
// Component
// =============================================================================

export const IdleWarningModal: React.FC<IdleWarningModalProps> = ({
    countdownSeconds = IDLE_COUNTDOWN_SECONDS,
    onContinue,
    onLogout,
}) => {
    const [remaining, setRemaining] = useState(countdownSeconds);

    // 倒數計時
    useEffect(() => {
        if (remaining <= 0) {
            onLogout();
            return;
        }

        const timer = setInterval(() => {
            setRemaining(prev => prev - 1);
        }, 1000);

        return () => clearInterval(timer);
    }, [remaining, onLogout]);

    return (
        <>
            {/* 背景遮罩 */}
            <div
                style={{
                    position: 'fixed',
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    backgroundColor: 'rgba(0, 0, 0, 0.5)',
                    backdropFilter: 'blur(4px)',
                    zIndex: 9998,
                }}
            />

            {/* 對話框 */}
            <div
                style={{
                    position: 'fixed',
                    top: '50%',
                    left: '50%',
                    transform: 'translate(-50%, -50%)',
                    backgroundColor: '#ffffff',
                    borderRadius: '16px',
                    padding: '32px 40px',
                    boxShadow: '0 20px 60px rgba(0, 0, 0, 0.25)',
                    zIndex: 9999,
                    textAlign: 'center',
                    minWidth: '320px',
                    maxWidth: '400px',
                }}
            >
                {/* 警告圖示 */}
                <div
                    style={{
                        width: '64px',
                        height: '64px',
                        borderRadius: '50%',
                        backgroundColor: '#fef3c7',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        margin: '0 auto 20px',
                    }}
                >
                    <AlertTriangle size={32} style={{ color: '#f59e0b' }} />
                </div>

                {/* 標題 */}
                <h2
                    style={{
                        fontSize: '20px',
                        fontWeight: 600,
                        color: '#1f2937',
                        marginBottom: '12px',
                    }}
                >
                    久未操作
                </h2>

                {/* 說明文字 */}
                <p
                    style={{
                        fontSize: '15px',
                        color: '#6b7280',
                        marginBottom: '24px',
                        lineHeight: 1.5,
                    }}
                >
                    系統將於{' '}
                    <span
                        style={{
                            fontSize: '24px',
                            fontWeight: 700,
                            color: '#ef4444',
                            padding: '0 4px',
                        }}
                    >
                        {remaining}
                    </span>{' '}
                    秒後自動登出
                </p>

                {/* 繼續使用按鈕 */}
                <Button
                    variant="primary"
                    size="lg"
                    onClick={onContinue}
                    style={{
                        width: '100%',
                        fontSize: '15px',
                        fontWeight: 600,
                    }}
                >
                    <RefreshCw size={18} style={{ marginRight: '8px' }} />
                    繼續使用
                </Button>
            </div>
        </>
    );
};

export default IdleWarningModal;

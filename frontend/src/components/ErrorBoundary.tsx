/**
 * Error Boundary Component
 * 
 * 捕捉 React 元件錯誤並顯示錯誤 UI，同時回報給後端。
 */
import React, { Component, type ReactNode } from 'react';
import { reportReactError } from '../services/errorTracking';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { Button } from './ui/Button';

interface Props {
    children: ReactNode;
    fallback?: ReactNode;
}

interface State {
    hasError: boolean;
    error?: Error;
}

export class ErrorBoundary extends Component<Props, State> {
    constructor(props: Props) {
        super(props);
        this.state = { hasError: false };
    }

    static getDerivedStateFromError(error: Error): State {
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, errorInfo: React.ErrorInfo): void {
        // 回報錯誤給後端
        reportReactError(error, errorInfo.componentStack || '');

        // 同時輸出到 console
        console.error('[ErrorBoundary] Caught error:', error);
        console.error('[ErrorBoundary] Component stack:', errorInfo.componentStack);
    }

    handleReload = (): void => {
        window.location.reload();
    };

    handleReset = (): void => {
        this.setState({ hasError: false, error: undefined });
    };

    render(): ReactNode {
        if (this.state.hasError) {
            // 如果有自訂 fallback，使用它
            if (this.props.fallback) {
                return this.props.fallback;
            }

            // 預設錯誤 UI
            return (
                <div style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    minHeight: '400px',
                    padding: '32px',
                    textAlign: 'center',
                }}>
                    <div style={{
                        width: '64px',
                        height: '64px',
                        borderRadius: '50%',
                        backgroundColor: '#fef2f2',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        marginBottom: '20px',
                    }}>
                        <AlertTriangle size={32} style={{ color: '#ef4444' }} />
                    </div>

                    <h2 style={{
                        fontSize: '20px',
                        fontWeight: 600,
                        color: '#1f2937',
                        marginBottom: '8px',
                    }}>
                        發生錯誤
                    </h2>

                    <p style={{
                        fontSize: '14px',
                        color: '#6b7280',
                        marginBottom: '24px',
                        maxWidth: '400px',
                    }}>
                        頁面發生錯誤，已自動回報給開發團隊。
                        <br />
                        請重新整理頁面或稍後再試。
                    </p>

                    <div style={{ display: 'flex', gap: '12px' }}>
                        <Button
                            variant="primary"
                            onClick={this.handleReload}
                        >
                            <RefreshCw size={16} style={{ marginRight: '6px' }} />
                            重新整理
                        </Button>
                        <Button
                            variant="secondary"
                            onClick={this.handleReset}
                        >
                            返回
                        </Button>
                    </div>

                    {/* 開發模式顯示錯誤詳情 */}
                    {import.meta.env.DEV && this.state.error && (
                        <details style={{
                            marginTop: '24px',
                            padding: '16px',
                            backgroundColor: '#f9fafb',
                            borderRadius: '8px',
                            textAlign: 'left',
                            maxWidth: '600px',
                            fontSize: '12px',
                            color: '#6b7280',
                        }}>
                            <summary style={{ cursor: 'pointer', marginBottom: '8px' }}>
                                錯誤詳情 (開發模式)
                            </summary>
                            <pre style={{
                                whiteSpace: 'pre-wrap',
                                wordBreak: 'break-all',
                                margin: 0,
                            }}>
                                {this.state.error.stack}
                            </pre>
                        </details>
                    )}
                </div>
            );
        }

        return this.props.children;
    }
}

export default ErrorBoundary;

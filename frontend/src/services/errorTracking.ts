/**
 * Error Tracking Service
 * 
 * 捕捉前端 JavaScript 錯誤並回報給後端。
 * 包含：
 * - 全域錯誤處理 (window.onerror)
 * - Promise 錯誤處理 (unhandledrejection)
 * - React Error Boundary 集成
 */

interface ErrorReport {
    message: string;
    stack?: string;
    url: string;
    userAgent: string;
    timestamp: string;
    componentStack?: string;
    user?: string;
}

// 記錄已回報的錯誤，避免重複回報
const reportedErrors = new Set<string>();

/**
 * 回報錯誤到後端
 */
async function reportError(error: ErrorReport): Promise<void> {
    // 使用錯誤訊息 + URL 作為唯一識別，避免重複回報
    const errorKey = `${error.message}:${error.url}`;
    if (reportedErrors.has(errorKey)) {
        return;
    }
    reportedErrors.add(errorKey);

    // 限制集合大小避免記憶體洩漏
    if (reportedErrors.size > 100) {
        reportedErrors.clear();
    }

    try {
        await fetch('/api/frontend-error', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(error),
        });
    } catch (e) {
        // 靜默失敗，不要因為錯誤回報又造成錯誤
        console.error('[ErrorTracking] Failed to report error:', e);
    }
}

/**
 * 從 Error 物件建立回報資料
 */
function createErrorReport(
    error: Error | string,
    componentStack?: string
): ErrorReport {
    const message = error instanceof Error ? error.message : String(error);
    const stack = error instanceof Error ? error.stack : undefined;
    const user = localStorage.getItem('user') || undefined;

    return {
        message,
        stack,
        url: window.location.href,
        userAgent: navigator.userAgent,
        timestamp: new Date().toISOString(),
        componentStack,
        user,
    };
}

/**
 * 初始化全域錯誤捕捉
 * 在 App 啟動時呼叫一次
 */
export function initErrorTracking(): void {
    // 捕捉同步錯誤
    window.onerror = (message, source, lineno, colno, error) => {
        const report = createErrorReport(
            error || String(message)
        );
        report.stack = report.stack || `at ${source}:${lineno}:${colno}`;
        reportError(report);
        // 不阻止預設行為
        return false;
    };

    // 捕捉 Promise 錯誤
    window.onunhandledrejection = (event) => {
        const error = event.reason;
        const report = createErrorReport(
            error instanceof Error ? error : String(error)
        );
        reportError(report);
    };

    console.log('[ErrorTracking] Initialized');
}

/**
 * React Error Boundary 專用的錯誤回報
 */
export function reportReactError(
    error: Error,
    componentStack: string
): void {
    const report = createErrorReport(error, componentStack);
    reportError(report);
}

/**
 * 手動回報錯誤（用於 try-catch 區塊）
 */
export function captureError(error: Error, context?: string): void {
    const report = createErrorReport(error);
    if (context) {
        report.message = `[${context}] ${report.message}`;
    }
    reportError(report);
}

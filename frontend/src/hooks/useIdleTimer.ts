/**
 * useIdleTimer - 閒置計時器 Hook
 * 
 * 偵測使用者是否閒置，並在閒置時間到達且無背景任務執行時觸發回調。
 * 
 * @example
 * ```tsx
 * const { isIdle, resetTimer } = useIdleTimer({
 *     idleTimeoutMs: 2 * 60 * 1000, // 2 分鐘
 *     onIdle: () => setShowWarning(true),
 * });
 * ```
 */
import { useState, useEffect, useCallback, useRef } from 'react';
import { tasksApi } from '../api/tasks';
import { IDLE_TIMEOUT_MS } from '../config';

// =============================================================================
// Types
// =============================================================================

export interface UseIdleTimerOptions {
    /** 閒置超時時間 (毫秒)，預設 120000 (2分鐘) */
    idleTimeoutMs?: number;
    /** 閒置時的回調 (無背景任務執行時才會觸發) */
    onIdle: () => void;
    /** 是否啟用，預設 true */
    enabled?: boolean;
}

export interface UseIdleTimerReturn {
    /** 是否處於閒置狀態 */
    isIdle: boolean;
    /** 重置計時器 */
    resetTimer: () => void;
}

// =============================================================================
// Constants
// =============================================================================

/** 使用者活動事件列表 */
const ACTIVITY_EVENTS = ['mousemove', 'keydown', 'click', 'scroll', 'touchstart'] as const;

/** 節流間隔：避免頻繁重置計時器 (500ms) */
const THROTTLE_MS = 500;

// =============================================================================
// Hook Implementation
// =============================================================================

export function useIdleTimer(options: UseIdleTimerOptions): UseIdleTimerReturn {
    const {
        idleTimeoutMs = IDLE_TIMEOUT_MS,
        onIdle,
        enabled = true,
    } = options;

    const [isIdle, setIsIdle] = useState(false);
    const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const lastActivityRef = useRef<number>(Date.now());
    const onIdleRef = useRef(onIdle);

    // 更新 onIdle ref (避免 useEffect 依賴變化)
    useEffect(() => {
        onIdleRef.current = onIdle;
    }, [onIdle]);

    // 檢查是否有執行中的背景任務
    const hasRunningTasks = useCallback(async (): Promise<boolean> => {
        try {
            const jobs = await tasksApi.listJobs(20);
            const running = jobs.some(job => job.status === 'running' || job.status === 'pending');
            console.log('[useIdleTimer] Running tasks check:', running, jobs);
            return running;
        } catch (e) {
            console.error('[useIdleTimer] Failed to check running tasks:', e);
            // API 失敗時，視為沒有執行中任務（允許觸發閒置登出）
            return false;
        }
    }, []);

    // 處理閒置超時
    const handleIdleTimeout = useCallback(async () => {
        console.log('[useIdleTimer] Timeout reached, checking tasks...');

        // 檢查是否有背景任務執行中
        const hasTasks = await hasRunningTasks();

        if (hasTasks) {
            // 有任務執行中，延遲 10 秒後再檢查
            console.log('[useIdleTimer] Has running tasks, delaying idle check...');
            timeoutRef.current = setTimeout(handleIdleTimeout, 10000);
            return;
        }

        // 無任務執行中，觸發閒置狀態
        console.log('[useIdleTimer] Idle timeout triggered, showing modal');
        setIsIdle(true);
        onIdleRef.current();
    }, [hasRunningTasks]);

    // 重置計時器
    const resetTimer = useCallback(() => {
        // 清除現有計時器
        if (timeoutRef.current) {
            clearTimeout(timeoutRef.current);
            timeoutRef.current = null;
        }

        // 重置狀態
        setIsIdle(false);
        lastActivityRef.current = Date.now();

        // 啟動新計時器
        if (enabled) {
            timeoutRef.current = setTimeout(handleIdleTimeout, idleTimeoutMs);
        }
    }, [enabled, idleTimeoutMs, handleIdleTimeout]);

    // 活動事件處理 (節流)
    useEffect(() => {
        if (!enabled) return;

        let throttleTimeout: ReturnType<typeof setTimeout> | null = null;

        const handleActivity = () => {
            // 節流：500ms 內只處理一次
            const now = Date.now();
            if (now - lastActivityRef.current < THROTTLE_MS) {
                return;
            }

            // 如果已經在閒置狀態，不自動重置 (需要使用者明確點擊繼續)
            if (isIdle) {
                return;
            }

            // 節流處理
            if (throttleTimeout) return;
            throttleTimeout = setTimeout(() => {
                throttleTimeout = null;
            }, THROTTLE_MS);

            // 重置計時器
            resetTimer();
        };

        // 綁定事件
        ACTIVITY_EVENTS.forEach(event => {
            window.addEventListener(event, handleActivity, { passive: true });
        });

        // 初始化計時器
        resetTimer();

        // 清理
        return () => {
            ACTIVITY_EVENTS.forEach(event => {
                window.removeEventListener(event, handleActivity);
            });
            if (timeoutRef.current) {
                clearTimeout(timeoutRef.current);
            }
            if (throttleTimeout) {
                clearTimeout(throttleTimeout);
            }
        };
    }, [enabled, isIdle, resetTimer]);

    return {
        isIdle,
        resetTimer,
    };
}

export default useIdleTimer;

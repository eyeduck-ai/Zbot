/**
 * useDebounce - 防抖 Hook
 * 
 * 用途：延遲更新值，減少頻繁觸發的操作（如 API 請求、搜尋）
 * 
 * @example
 * const [searchTerm, setSearchTerm] = useState('');
 * const debouncedSearch = useDebounce(searchTerm, 300);
 * 
 * useEffect(() => {
 *     if (debouncedSearch) {
 *         // 只有在用戶停止輸入 300ms 後才執行搜尋
 *         searchApi(debouncedSearch);
 *     }
 * }, [debouncedSearch]);
 */

import { useState, useEffect } from 'react';

/**
 * 防抖 Hook
 * @param value 要防抖的值
 * @param delay 延遲時間 (毫秒)，預設 300ms
 * @returns 防抖後的值
 */
export function useDebounce<T>(value: T, delay: number = 300): T {
    const [debouncedValue, setDebouncedValue] = useState<T>(value);

    useEffect(() => {
        // 設定定時器
        const timer = setTimeout(() => {
            setDebouncedValue(value);
        }, delay);

        // 清理：如果 value 在 delay 內再次變化，取消前一個定時器
        return () => {
            clearTimeout(timer);
        };
    }, [value, delay]);

    return debouncedValue;
}

export default useDebounce;

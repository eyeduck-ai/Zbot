import React from 'react';
import { CheckCircle2 } from 'lucide-react';

interface TrustBadgeProps {
    /** 任務 ID，用於顯示對應的統計 */
    taskId: string;
    /** 累計處理筆數 */
    totalItems: number;
}

/**
 * 信任徽章元件 (低調質感版)
 * 
 * 在任務頁面初始步驟顯示累積完成筆數，建立使用者信任感。
 * 
 * 使用方式：
 * ```tsx
 * const { stats } = useTaskStats('note_surgery_submit');
 * 
 * {!loading && stats && stats.total_items > 0 && (
 *     <TrustBadge taskId="note_surgery_submit" totalItems={stats.total_items} />
 * )}
 * ```
 */
export const TrustBadge: React.FC<TrustBadgeProps> = ({ totalItems }) => {
    if (totalItems <= 0) return null;

    return (
        <div className="flex items-center gap-1.5 text-sm text-gray-400">
            <CheckCircle2 size={14} className="text-green-500" />
            <span>
                累積完成 <span className="text-gray-500 font-medium">{totalItems}</span> 筆
            </span>
        </div>
    );
};

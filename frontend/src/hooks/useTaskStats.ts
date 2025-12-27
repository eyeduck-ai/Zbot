import { useState, useEffect } from 'react';
import { apiClient } from '../api/client';

interface TaskStats {
    task_id: string;
    total_runs: number;
    total_success: number;
    total_items: number;
    last_run_at: string | null;
}

/**
 * 獲取單一任務的累計統計
 * 
 * @param taskId 任務 ID (如 note_surgery_submit)
 * @returns { stats, loading, error }
 */
export function useTaskStats(taskId: string) {
    const [stats, setStats] = useState<TaskStats | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const fetchStats = async () => {
            try {
                setLoading(true);
                const data = await apiClient.get<TaskStats>(`/api/stats/tasks/${taskId}/count`);
                setStats(data);
                setError(null);
            } catch (e: any) {
                // 非 admin 用戶會收到 403，靜默處理
                setError(e.message);
                setStats(null);
            } finally {
                setLoading(false);
            }
        };

        if (taskId) {
            fetchStats();
        }
    }, [taskId]);

    return { stats, loading, error };
}

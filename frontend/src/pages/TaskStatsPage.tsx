import React, { useState, useEffect } from 'react';
import { Activity, TrendingUp, Users, RefreshCw, CheckCircle, XCircle, AlertCircle } from 'lucide-react';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { apiClient } from '../api/client';
import { getTaskName } from '../constants/taskNames';
import { THEME } from '../styles/theme';

interface TaskStats {
    task_id: string;
    total_runs: number;
    total_success: number;
    total_items: number;
    last_run_at: string | null;
}

interface TaskLog {
    id: string;
    task_id: string;
    operator_eip_id: string;
    target_doc_code: string | null;
    status: string;
    items_processed: number;
    error_message: string | null;
    started_at: string;
    completed_at: string;
}

const formatDateTime = (isoStr: string | null): string => {
    if (!isoStr) return '-';
    const d = new Date(isoStr);
    return d.toLocaleString('zh-TW', {
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit'
    });
};

export const TaskStatsPage: React.FC = () => {
    const [stats, setStats] = useState<TaskStats[]>([]);
    const [logs, setLogs] = useState<TaskLog[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchData = async () => {
        setLoading(true);
        setError(null);
        try {
            const [statsRes, logsRes] = await Promise.all([
                apiClient.get<TaskStats[]>('/api/stats/tasks/summary'),
                apiClient.get<TaskLog[]>('/api/stats/tasks/recent?limit=30')
            ]);
            setStats(statsRes || []);
            setLogs(logsRes || []);
        } catch (e: any) {
            setError(e.message || '無法載入統計資料');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
    }, []);

    // 總計
    const totalRuns = stats.reduce((sum, s) => sum + s.total_runs, 0);
    const totalSuccess = stats.reduce((sum, s) => sum + s.total_success, 0);
    const totalItems = stats.reduce((sum, s) => sum + s.total_items, 0);
    const successRate = totalRuns > 0 ? Math.round((totalSuccess / totalRuns) * 100) : 0;

    return (
        <div className="bg-[#F5F5F7] min-h-full flex flex-col p-8 font-sans">
            <div className="relative z-10 w-full max-w-5xl mx-auto">
                {/* Header */}
                <header className="mb-8">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-4">
                            <div style={{
                                width: '48px',
                                height: '48px',
                                borderRadius: '14px',
                                background: `linear-gradient(135deg, ${THEME.primaryLight} 0%, #dbeafe 100%)`,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                            }}>
                                <Activity size={24} color={THEME.primary} />
                            </div>
                            <div>
                                <h2 className="text-2xl font-bold text-gray-900 tracking-tight">任務統計</h2>
                                <p className="text-sm text-gray-500">追蹤所有任務執行情況</p>
                            </div>
                        </div>
                        <Button variant="secondary" onClick={fetchData} disabled={loading}>
                            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
                            <span className="ml-2">重新整理</span>
                        </Button>
                    </div>
                </header>

                {error && (
                    <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl text-red-700">
                        {error}
                    </div>
                )}

                {/* 總覽卡片 */}
                <div className="grid grid-cols-4 gap-4 mb-8">
                    <Card className="p-4">
                        <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-xl bg-blue-100 flex items-center justify-center">
                                <TrendingUp size={20} className="text-blue-600" />
                            </div>
                            <div>
                                <p className="text-sm text-gray-500">總執行次數</p>
                                <p className="text-xl font-bold text-gray-900">{totalRuns}</p>
                            </div>
                        </div>
                    </Card>
                    <Card className="p-4">
                        <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-xl bg-green-100 flex items-center justify-center">
                                <CheckCircle size={20} className="text-green-600" />
                            </div>
                            <div>
                                <p className="text-sm text-gray-500">成功率</p>
                                <p className="text-xl font-bold text-gray-900">{successRate}%</p>
                            </div>
                        </div>
                    </Card>
                    <Card className="p-4">
                        <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-xl bg-purple-100 flex items-center justify-center">
                                <Activity size={20} className="text-purple-600" />
                            </div>
                            <div>
                                <p className="text-sm text-gray-500">累計處理筆數</p>
                                <p className="text-xl font-bold text-gray-900">{totalItems}</p>
                            </div>
                        </div>
                    </Card>
                    <Card className="p-4">
                        <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-xl bg-orange-100 flex items-center justify-center">
                                <Users size={20} className="text-orange-600" />
                            </div>
                            <div>
                                <p className="text-sm text-gray-500">任務種類</p>
                                <p className="text-xl font-bold text-gray-900">{stats.length}</p>
                            </div>
                        </div>
                    </Card>
                </div>

                {/* 任務統計表 */}
                <Card className="mb-8">
                    <div className="p-4 border-b border-gray-100">
                        <h3 className="font-semibold text-gray-900">各任務統計</h3>
                    </div>
                    <div className="overflow-x-auto">
                        <table className="w-full">
                            <thead className="bg-gray-50">
                                <tr>
                                    <th className="px-4 py-3 text-left text-sm font-medium text-gray-600">任務</th>
                                    <th className="px-4 py-3 text-right text-sm font-medium text-gray-600">執行次數</th>
                                    <th className="px-4 py-3 text-right text-sm font-medium text-gray-600">成功次數</th>
                                    <th className="px-4 py-3 text-right text-sm font-medium text-gray-600">處理筆數</th>
                                    <th className="px-4 py-3 text-right text-sm font-medium text-gray-600">最後執行</th>
                                </tr>
                            </thead>
                            <tbody>
                                {stats.length === 0 ? (
                                    <tr>
                                        <td colSpan={5} className="px-4 py-8 text-center text-gray-400">
                                            尚無統計資料
                                        </td>
                                    </tr>
                                ) : (
                                    stats.map(s => (
                                        <tr key={s.task_id} className="border-t border-gray-100 hover:bg-gray-50">
                                            <td className="px-4 py-3 text-sm text-gray-900">{getTaskName(s.task_id)}</td>
                                            <td className="px-4 py-3 text-sm text-gray-700 text-right">{s.total_runs}</td>
                                            <td className="px-4 py-3 text-sm text-gray-700 text-right">{s.total_success}</td>
                                            <td className="px-4 py-3 text-sm text-gray-700 text-right font-medium">{s.total_items}</td>
                                            <td className="px-4 py-3 text-sm text-gray-500 text-right">{formatDateTime(s.last_run_at)}</td>
                                        </tr>
                                    ))
                                )}
                            </tbody>
                        </table>
                    </div>
                </Card>

                {/* 最近執行記錄 */}
                <Card>
                    <div className="p-4 border-b border-gray-100">
                        <h3 className="font-semibold text-gray-900">最近執行記錄</h3>
                    </div>
                    <div className="overflow-x-auto">
                        <table className="w-full">
                            <thead className="bg-gray-50">
                                <tr>
                                    <th className="px-4 py-3 text-left text-sm font-medium text-gray-600">任務</th>
                                    <th className="px-4 py-3 text-left text-sm font-medium text-gray-600">操作者</th>
                                    <th className="px-4 py-3 text-center text-sm font-medium text-gray-600">狀態</th>
                                    <th className="px-4 py-3 text-right text-sm font-medium text-gray-600">筆數</th>
                                    <th className="px-4 py-3 text-right text-sm font-medium text-gray-600">完成時間</th>
                                </tr>
                            </thead>
                            <tbody>
                                {logs.length === 0 ? (
                                    <tr>
                                        <td colSpan={5} className="px-4 py-8 text-center text-gray-400">
                                            尚無執行記錄
                                        </td>
                                    </tr>
                                ) : (
                                    logs.map(log => (
                                        <tr key={log.id} className="border-t border-gray-100 hover:bg-gray-50">
                                            <td className="px-4 py-3 text-sm text-gray-900">{getTaskName(log.task_id)}</td>
                                            <td className="px-4 py-3 text-sm text-gray-700">{log.operator_eip_id}</td>
                                            <td className="px-4 py-3 text-center">
                                                <Badge variant={
                                                    log.status === 'success' ? 'success' :
                                                        log.status === 'failed' ? 'error' :
                                                            'warning'
                                                }>
                                                    {log.status === 'success' && <CheckCircle size={12} className="mr-1" />}
                                                    {log.status === 'failed' && <XCircle size={12} className="mr-1" />}
                                                    {log.status === 'cancelled' && <AlertCircle size={12} className="mr-1" />}
                                                    {log.status}
                                                </Badge>
                                            </td>
                                            <td className="px-4 py-3 text-sm text-gray-700 text-right">{log.items_processed}</td>
                                            <td className="px-4 py-3 text-sm text-gray-500 text-right">{formatDateTime(log.completed_at)}</td>
                                        </tr>
                                    ))
                                )}
                            </tbody>
                        </table>
                    </div>
                </Card>
            </div>
        </div>
    );
};

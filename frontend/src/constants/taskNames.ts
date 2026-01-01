/**
 * Task Names - 任務 ID 對應中文名稱
 * 
 * 統一管理所有任務的顯示名稱，避免各檔案重複定義。
 * 
 * @example
 * import { TASK_NAMES, getTaskName } from '../constants/taskNames';
 * 
 * // 直接使用
 * const name = TASK_NAMES['note_surgery_submit']; // '手術紀錄'
 * 
 * // 安全取值 (fallback 到 taskId)
 * const name = getTaskName('unknown_task'); // 'unknown_task'
 */

// =============================================================================
// Constants
// =============================================================================

export const TASK_NAMES: Record<string, string> = {
    // Dashboard
    dashboard_bed: '待床追蹤',
    dashboard_bed_update: '待床追蹤更新',

    // Statistics
    stats_op_update: '手術統計',
    stats_fee_update: '費用統計',

    // IVI
    ivi_fetch: 'IVI 排程',
    opnote_submit: 'IVI手術紀錄',
    opnote_preview: 'IVI 預覽',
    note_ivi_submit: 'IVI手術紀錄',

    // Surgery
    note_surgery_fetch_schedule: '手術排程',
    note_surgery_fetch_details: '手術詳情',
    note_surgery_preview: '手術預覽',
    note_surgery_submit: '手術紀錄',
};

// =============================================================================
// Helper Functions
// =============================================================================

/**
 * 取得任務顯示名稱
 * @param taskId 任務 ID
 * @returns 中文名稱，若無對應則回傳原 taskId
 */
export const getTaskName = (taskId: string): string =>
    TASK_NAMES[taskId] || taskId;

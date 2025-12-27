/**
 * IVI 頁面 Mock 資料
 * 
 * 用於 Demo 模式錄製影片，避免真實病患隱私問題。
 */

// =============================================================================
// Types
// =============================================================================

export interface IviScheduleItem {
    hisno: string;
    name: string;
    schedule_name: string;
    schedule_date: string;
    doc_code: string;
    vs_name: string;
    op_start: string;
    op_end: string;
    diagnosis: string;
    side: string;
    drug: string;
    charge_type: string;
    raw_content: string;
    selected?: boolean;
    status?: 'pending' | 'ready' | 'success' | 'error';
    _original?: {
        doc_code: string;
        vs_name: string;
        diagnosis: string;
        side: string;
        drug: string;
    };
}

// =============================================================================
// Mock Data
// =============================================================================

export const MOCK_ITEMS: IviScheduleItem[] = [
    {
        hisno: '12345678',
        name: '王小明',
        schedule_name: 'IVI',
        schedule_date: '2025-12-11',
        doc_code: '4106',
        vs_name: '林醫師',
        op_start: '0900',
        op_end: '0902',
        diagnosis: 'AMD',
        side: 'OD',
        drug: 'Eylea',
        charge_type: 'NHI',
        raw_content: '',
        selected: true,
        status: 'pending'
    },
    {
        hisno: '23456789',
        name: '李小華',
        schedule_name: 'IVI',
        schedule_date: '2025-12-11',
        doc_code: '4106',
        vs_name: '林醫師',
        op_start: '0910',
        op_end: '0912',
        diagnosis: 'DME',
        side: 'OS',
        drug: 'Lucentis',
        charge_type: 'NHI',
        raw_content: '',
        selected: true,
        status: 'pending'
    },
    {
        hisno: '34567890',
        name: '張大同',
        schedule_name: 'IVI',
        schedule_date: '2025-12-11',
        doc_code: '4107',
        vs_name: '陳醫師',
        op_start: '0920',
        op_end: '0922',
        diagnosis: 'BRVO',
        side: 'OD',
        drug: 'Avastin',
        charge_type: 'SP-A',
        raw_content: '',
        selected: false,
        status: 'pending'
    },
];

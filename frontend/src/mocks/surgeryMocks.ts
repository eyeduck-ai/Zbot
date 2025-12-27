/**
 * Surgery 頁面 Mock 資料
 * 
 * 用於 Demo 模式錄製影片，避免真實病患隱私問題。
 */

// =============================================================================
// Types (從 SurgeryPage.tsx 匯出時需確保一致)
// =============================================================================

export interface ScheduleItem {
    hisno: string;
    name: string;
    op_date: string;
    op_time: string;
    op_room: string;
    pre_op_dx: string;
    op_name: string;
    op_room_info: string;
    link: string;
    selected?: boolean;
}

export interface DetailItem {
    hisno: string;
    name: string;
    op_date: string;
    op_time: string;
    op_room: string;
    pre_op_dx: string;
    op_name: string;
    op_room_info: string;
    op_sect: string;
    op_bed: string;
    op_anesthesia: string;
    op_side: string;
    op_type: string;
    col_fields: Record<string, string>;
    editable_fields: string[];
    diagn: string;
    diaga: string;
    web9_data: Record<string, any>;
    gsheet_data: Record<string, any>;
    status: string;
    error?: string;
    selected?: boolean;
    payload?: Record<string, any>;
    missing_fields?: string[];
    _original?: {
        pre_op_dx: string;
        op_name: string;
        op_side: string;
        op_type: string;
        col_fields: Record<string, string>;
        diagn: string;
        diaga: string;
    };
}

// =============================================================================
// Mock Data
// =============================================================================

export const MOCK_SCHEDULE: ScheduleItem[] = [
    {
        hisno: '11111111',
        name: '陳大文',
        op_date: '01141211',
        op_time: '0800',
        op_room: 'B07',
        pre_op_dx: 'CATA OD',
        op_name: 'PHACO-IOL OD',
        op_room_info: '',
        link: '#',
        selected: true
    },
    {
        hisno: '22222222',
        name: '林小美',
        op_date: '01141211',
        op_time: '0930',
        op_room: 'B07',
        pre_op_dx: 'CATA OS',
        op_name: 'LENSX-PHACO-IOL OS',
        op_room_info: 'Luxsmart',
        link: '#',
        selected: true
    },
    {
        hisno: '33333333',
        name: '王建國',
        op_date: '01141211',
        op_time: '1100',
        op_room: 'B08',
        pre_op_dx: 'CATA OU',
        op_name: 'PHACO-IOL OU',
        op_room_info: '',
        link: '#',
        selected: false
    },
    {
        hisno: '44444444',
        name: '李明華',
        op_date: '01141211',
        op_time: '1400',
        op_room: 'B09',
        pre_op_dx: 'RRD OD',
        op_name: 'PPV OD',
        op_room_info: 'ICB',
        link: '#',
        selected: true
    },
];

export const MOCK_DETAILS: DetailItem[] = [
    {
        hisno: '11111111',
        name: '陳大文',
        op_date: '01141211',
        op_time: '0800',
        op_room: 'B07',
        pre_op_dx: 'CATA OD',
        op_name: 'PHACO-IOL OD',
        op_room_info: '',
        op_type: 'PHACO',
        op_side: 'OD',
        op_sect: 'OPH',
        op_bed: '12-A',
        op_anesthesia: 'LA',
        col_fields: { IOL: 'Tecnis ZCB00', FINAL: '-0.5D', TARGET: '-0.25D', SN: 'SN123456', CDE: '', COMPLICATIONS: '' },
        editable_fields: ['IOL', 'FINAL', 'TARGET', 'SN', 'CDE', 'COMPLICATIONS'],
        diagn: 'CATA OD',
        diaga: 'Ditto s/p Phaco-IOL OD',
        web9_data: {},
        gsheet_data: {},
        status: 'ready',
        selected: true
    },
    {
        hisno: '22222222',
        name: '林小美',
        op_date: '01141211',
        op_time: '0930',
        op_room: 'B07',
        pre_op_dx: 'CATA OS',
        op_name: 'LENSX-PHACO-IOL OS',
        op_room_info: 'Luxsmart',
        op_type: 'LENSX',
        op_side: 'OS',
        op_sect: 'OPH',
        op_bed: '12-B',
        op_anesthesia: 'LA',
        col_fields: { IOL: 'Vivity', FINAL: '-0.25D', TARGET: '0D', SN: 'SN789012', CDE: 'CDE01', COMPLICATIONS: '' },
        editable_fields: ['IOL', 'FINAL', 'TARGET', 'SN', 'CDE', 'COMPLICATIONS'],
        diagn: 'CATA OS',
        diaga: 'Ditto s/p LENSX-PHACO-IOL OS',
        web9_data: {},
        gsheet_data: {},
        status: 'ready',
        selected: true
    },
    {
        hisno: '44444444',
        name: '李明華',
        op_date: '01141211',
        op_time: '1400',
        op_room: 'B09',
        pre_op_dx: 'RRD OD',
        op_name: 'PPV OD',
        op_room_info: 'ICB',
        op_type: 'VT',
        op_side: 'OD',
        op_sect: 'OPH',
        op_bed: '15-A',
        op_anesthesia: 'GA',
        col_fields: { COMPLICATIONS: 'PCR' },
        editable_fields: ['COMPLICATIONS'],
        diagn: 'RRD OD',
        diaga: 'Ditto s/p PPV OD',
        web9_data: {},
        gsheet_data: {},
        status: 'ready',
        selected: true,
        missing_fields: ['COL_FINAL']
    },
];

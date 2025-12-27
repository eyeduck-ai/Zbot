"""
OpNote 模組 - Payload 建構器

核心建構邏輯：
- PayloadBuilder: 建構 IVI 和 Surgery 的 Web9 Payload
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from string import Template

from .models import (
    OpNotePayloadDefaults,
    IviPayloadFields,
    SurgeryPayloadFields,
    OpTemplate,
    transform_side,
    contains_side_info,
)

logger = logging.getLogger(__name__)


class PayloadBuilder:
    """
    手術紀錄 Payload 建構器
    
    負責：
    1. 合併多來源資料 (Web9, 排程, 刀表)
    2. 依模板解析佔位符
    3. 識別缺失的必填欄位
    """
    
    def __init__(self):
        self._defaults = OpNotePayloadDefaults()
    
    def build_ivi_payload(
        self,
        web9_data: Dict[str, Any],
        ivi_fields: IviPayloadFields,
        op_date: str,
        vs_name: str = "",
        r_name: str = "",
        template_content: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        建構 IVI 注射的 Payload
        
        Args:
            web9_data: Web9 病人基本資料
            ivi_fields: IVI 專用欄位
            op_date: 手術日期 (民國格式)
            vs_name: 主治醫師姓名 (從 CKS 排程的 CreateName 取得)
            r_name: 住院醫師姓名 (從 Supabase users 表的 display_name 取得)
            template_content: IVI 病歷模板內容
            
        Returns:
            完整的 Web9 POST payload
        """
        # 基礎預設值
        payload = self._defaults.model_dump()
        
        # Web9 病人基本資料
        payload.update({
            "sect1": web9_data.get("sect1", ""),
            "name": web9_data.get("name", ""),
            "sex": web9_data.get("sex", ""),
            "hisno": web9_data.get("hisno", ""),
            "age": web9_data.get("age", ""),
            "idno": web9_data.get("idno", ""),
            "birth": web9_data.get("birth", ""),
            "_antyp": web9_data.get("_antyp", ""),
            "opbbgndt": web9_data.get("opbbgndt", ""),
            "opbbgntm": web9_data.get("opbbgntm", ""),
        })
        
        # IVI 固定欄位
        # Web9 期望 opacod 格式尾部有空格 (如 OPH1476 )
        def format_opcode(code: str) -> str:
            """在 op_code 尾部加上空格"""
            return code if code.endswith(" ") else code + " "
        
        payload.update({
            "sect": ivi_fields.sect,
            "ward": ivi_fields.ward,
            "antyp": ivi_fields.antyp,
            "opacod1": format_opcode(ivi_fields.opacod1),
            "opaicd0": ivi_fields.opaicd0,
            "opaicdnm0": ivi_fields.opaicdnm0,
        })
        
        # 動態欄位
        payload.update({
            "man": ivi_fields.doc_code,
            "mann": vs_name or ivi_fields.doc_code,
            "ass1": ivi_fields.r_code,
            "ass1n": r_name or ivi_fields.r_code,
            "bgndt": op_date,
            "enddt": op_date,
            "bgntm": ivi_fields.op_start,
            "endtm": ivi_fields.op_end,
            "sel_opck": "",
            "diagn": ivi_fields.get_diagn(),
            "diaga": ivi_fields.get_diaga(),
            "opanam1": ivi_fields.get_opanam1(),
            "op2data": template_content or "##########",
        })
        
        return payload

    def build_surgery_payload(
        self,
        web9_data: Dict[str, Any],
        surgery_fields: SurgeryPayloadFields,
        op_template: OpTemplate,
        op_date: str,
        placeholder_values: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], List[str]]:
        """
        建構一般手術的 Payload
        
        Args:
            web9_data: Web9 病人基本資料
            surgery_fields: 手術專用欄位
            op_template: 手術組套模板
            op_date: 手術日期 (民國格式)
            placeholder_values: 佔位符對應值 (來自排程+刀表)
            
        Returns:
            (payload, missing_required): Payload 與缺失的必填欄位清單
        """
        # 基礎預設值
        payload = self._defaults.model_dump()
        
        # Web9 病人基本資料 # TODO:這未來應該要大幅度用surgery_fields取代
        payload.update({
            "sect1": web9_data.get("sect1", ""),
            "name": web9_data.get("name", ""),
            "sex": web9_data.get("sex", ""),
            "hisno": web9_data.get("hisno", ""),
            "age": web9_data.get("age", ""),
            "idno": web9_data.get("idno", ""),
            "birth": web9_data.get("birth", ""),
            "_antyp": web9_data.get("_antyp", ""),
            "opbbgndt": web9_data.get("opbbgndt", ""),
            "opbbgntm": web9_data.get("opbbgntm", ""),
            "diagn": surgery_fields.pre_op_dx or web9_data.get("diagn", ""),  # 優先用排程資料
            "sel_opck": web9_data.get("sel_opck", ""),
            "bgntm": web9_data.get("bgntm", ""),
            "endtm": web9_data.get("endtm", ""),
        })
        
        # 排程欄位
        payload.update({
            "sect": surgery_fields.op_sect,
            "ward": surgery_fields.op_bed,
            "antyp": surgery_fields.op_anesthesia,
        })
        
        # 醫師資訊 (主刀 + 助手)
        payload.update({
            "man": surgery_fields.doc_code,
            "mann": surgery_fields.vs_name,
            "ass1": surgery_fields.r_code,
            "ass1n": surgery_fields.r_name,
            "ass2": surgery_fields.ass2,
            "ass2n": surgery_fields.ass2n,
            "ass3": surgery_fields.ass3,
            "ass3n": surgery_fields.ass3n,
            "bgndt": op_date,
            "enddt": op_date,
        })
        
        # 手術名稱與代碼
        # Web9 期望 opacod 格式尾部有空格 (如 OPH1342 )
        def format_opcode(code: str) -> str:
            """在 op_code 尾部加上空格"""
            return code if code.endswith(" ") else code + " "
        
        payload.update({
            "opanam1": op_template.op_name,
            "opacod1": format_opcode(op_template.op_code),
        })
        
        # ICD 碼 (依側別)
        op_side = surgery_fields.op_side.upper()
        icd = op_template.icd_codes.get(op_side)
        if icd:
            payload["opaicd0"] = icd.code
            payload["opaicdnm0"] = icd.name
        
        # OU (雙側) 特殊處理
        if op_side == "OU":
            icd_od = op_template.icd_codes.get("OD")
            icd_os = op_template.icd_codes.get("OS")
            if icd_od and icd_os:
                payload["opanam2"] = op_template.op_name
                payload["opacod2"] = format_opcode(op_template.op_code)
                payload["opaicd0"] = icd_od.code
                payload["opaicdnm0"] = icd_od.name
                payload["opaicd1"] = icd_os.code
                payload["opaicdnm1"] = icd_os.name
        
        # 自動加入 TRANSFORMED_SIDE
        placeholder_values["TRANSFORMED_SIDE"] = transform_side(op_side)
        placeholder_values["OP_SIDE"] = op_side
        
        # 確保同時有 COL_ 和非 COL_ 前綴的鍵 (向下相容)
        # 因為模板可能使用 $COL_IOL 或 $IOL
        for key in ["IOL", "FINAL", "TARGET", "SN", "CDE", "COMPLICATIONS", "OP"]:
            col_key = f"COL_{key}"
            if key in placeholder_values and col_key not in placeholder_values:
                placeholder_values[col_key] = placeholder_values[key]
            elif col_key in placeholder_values and key not in placeholder_values:
                placeholder_values[key] = placeholder_values[col_key]
        
        # 術後診斷 (diaga)
        # 優先: GSheet COL_OP > ScheduleItem op_name > op_template.op_type
        op_name_source = (
            placeholder_values.get('COL_OP') or 
            surgery_fields.op_name or 
            op_template.op_type or 
            ''
        )
        
        # 只有當 op_name 不包含側別資訊時，才加上 op_side
        if op_name_source and not contains_side_info(op_name_source) and op_side:
            op_name_with_side = f"{op_name_source} {op_side}"
        else:
            op_name_with_side = op_name_source
        
        payload["diaga"] = f"Ditto s/p {op_name_with_side}" if op_name_with_side else ""
        
        # 動態生成特殊佔位符
        if "COL_COMPLICATIONS" not in placeholder_values or not placeholder_values.get("COL_COMPLICATIONS"):
            placeholder_values["COL_COMPLICATIONS"] = "Nil"
        
        # # DETAILS_OF_IOL => 目前沒有使用
        # iol = placeholder_values.get("COL_IOL", "") or placeholder_values.get("IOL", "")
        # final = placeholder_values.get("COL_FINAL", "") or placeholder_values.get("FINAL", "")
        # target = placeholder_values.get("COL_TARGET", "") or placeholder_values.get("TARGET", "")
        # sn = placeholder_values.get("COL_SN", "") or placeholder_values.get("SN", "")
        # cde = placeholder_values.get("COL_CDE", "") or placeholder_values.get("CDE", "")
        
        # details_lines = []
        # if iol:
        #     iol_line = f"IOL: {iol}"
        #     if final:
        #         iol_line += f" {final}D"
        #     if target:
        #         iol_line += f" (Target: {target})"
        #     details_lines.append(iol_line)
        # if sn:
        #     details_lines.append(f"S/N: {sn}")
        # if cde:
        #     details_lines.append(f"CDE: {cde}")
        
        # placeholder_values["DETAILS_OF_IOL"] = "\n".join(details_lines) if details_lines else ""
        
        # 模板填充
        if op_template.template:
            try:
                result = Template(op_template.template).safe_substitute(placeholder_values)
                # 清理未填充的佔位符 (形如 $COL_* 或 $VAR)
                import re
                result = re.sub(r'\$[A-Z_]+', '', result)
                # 清理多餘的空白行和尾隨空白
                result = re.sub(r'\n\s*\n', '\n', result)
                result = re.sub(r':\s*$', ':', result, flags=re.MULTILINE)
                payload["op2data"] = result
            except Exception as e:
                logger.warning(f"Template substitution failed: {e}")
                payload["op2data"] = ""
        
        # 檢查必填欄位
        missing = []
        for field in op_template.required_fields:
            if field not in placeholder_values or not placeholder_values[field]:
                missing.append(field)
        
        return payload, missing

    def resolve_placeholders(
        self,
        required_fields: List[str],
        optional_fields: List[str],
        schedule_data: Dict[str, Any],
        gsheet_data: Dict[str, Any],
        column_map: Dict[str, Optional[str]],
    ) -> Tuple[Dict[str, Any], List[str]]:
        """
        解析佔位符，合併多來源資料
        
        資料優先順序：schedule_data > gsheet_data
        
        Args:
            required_fields: 必填佔位符清單
            optional_fields: 選填佔位符清單
            schedule_data: 內網排程資料
            gsheet_data: Google Sheet 原始資料
            column_map: 佔位符 → 欄位名對應
            
        Returns:
            (resolved_values, missing_required)
        """
        all_fields = required_fields + optional_fields
        resolved = {}
        
        for placeholder in all_fields:
            value = None
            
            # 優先從排程取得
            if placeholder in schedule_data and schedule_data[placeholder]:
                value = schedule_data.get(placeholder)
            
            # 回退到 Google Sheet (透過 column_map)
            if value is None:
                col_name = column_map.get(placeholder)
                if col_name and col_name in gsheet_data:
                    value = gsheet_data.get(col_name)
            
            if value is not None:
                resolved[placeholder] = value
        
        # 識別缺失的必填欄位
        missing = [f for f in required_fields if f not in resolved or not resolved[f]]
        
        return resolved, missing

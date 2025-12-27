"""
OpNote 模組

提供手術紀錄相關功能：
- 資料模型 (models)
- Payload 建構器 (builder)  
- Supabase 設定服務 (config)
- 共用 Tasks (shared)
"""

# 資料模型
from .models import (
    OpNotePayloadDefaults,
    DataSource,
    IviPayloadFields,
    SurgeryPayloadFields,
    IcdCode,
    OpTemplate,
    DoctorSheet,
    transform_side,
    SIDE_TRANSFORM,
    check_op_side,
    contains_side_info,
    existandnotnone,
)

# Payload 建構器
from .builder import PayloadBuilder

# 設定服務
from .config import (
    OpNoteConfigService,
    get_opnote_config_service,
    SurkeycodeService,
    get_surkeycode_service,
)

# 共用 Tasks
from .shared import (
    SourceType,
    PreviewItem,
    PreviewParams,
    PreviewResult,
    SubmitParams,
    SubmitResult,
    OpNoteBaseTask,
    OpNotePreviewTask,
    OpNoteSubmitTask,
)

__all__ = [
    # Models
    "OpNotePayloadDefaults",
    "DataSource",
    "IviPayloadFields",
    "SurgeryPayloadFields",
    "IcdCode",
    "OpTemplate",
    "DoctorSheet",
    "transform_side",
    "SIDE_TRANSFORM",
    "check_op_side",
    "check_op_type",
    "contains_side_info",
    "existandnotnone",
    # Builder
    "PayloadBuilder",
    # Config
    "OpNoteConfigService",
    "get_opnote_config_service",
    "SurkeycodeService",
    "get_surkeycode_service",
    # Shared Tasks
    "SourceType",
    "PreviewItem",
    "PreviewParams",
    "PreviewResult",
    "SubmitParams",
    "SubmitResult",
    "OpNoteBaseTask",
    "OpNotePreviewTask",
    "OpNoteSubmitTask",
]

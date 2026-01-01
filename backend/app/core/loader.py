"""Task Loader - 註冊所有 vghsdk 和 app tasks"""
import logging
from app.core.registry import TaskRegistry

# ===== VGHSDK Function-based Tasks =====

# Consent (4 tasks)
from vghsdk.modules.consent import (
    consent_opschedule, consent_list, consent_search, consent_pdf_bytes
)

# IVI (1 task)
from vghsdk.modules.ivi import ivi_fetch

# Surgery (3 tasks)
from vghsdk.modules.surgery import (
    surgery_doc_schedule, surgery_dept_schedule, surgery_detail
)

# Doctor (4 tasks)
from vghsdk.modules.doctor import (
    doc_opd_list_previous, doc_opd_schedule, doc_opd_list_appointment, doc_batch_opd_note
)

# Patient (15 tasks)
from vghsdk.modules.patient import (
    patient_search, patient_info, patient_opd_list, patient_opd_note,
    patient_op_list, patient_op_schedule, patient_op_note,
    patient_ad_list, patient_ad_note,
    patient_drug_list, patient_drug_content,
    patient_consult_list, patient_consult_note,
    patient_scaned_note, patient_opd_list_search
)

# ===== App Composite Tasks =====
import app.tasks.note_ivi
import app.tasks.opnote
import app.tasks.note_surgery
import app.tasks.stats_fee
import app.tasks.stats_op
import app.tasks.dashboard_bed

logger = logging.getLogger(__name__)


def register_all_tasks():
    """註冊所有 crawler tasks。"""
    logger.info("Registering all crawler tasks...")
    
    # === Consent ===
    TaskRegistry.register(consent_opschedule)
    TaskRegistry.register(consent_list)
    TaskRegistry.register(consent_search)
    TaskRegistry.register(consent_pdf_bytes)
    
    # === IVI ===
    TaskRegistry.register(ivi_fetch)
    
    # === Surgery ===
    TaskRegistry.register(surgery_doc_schedule)
    TaskRegistry.register(surgery_dept_schedule)
    TaskRegistry.register(surgery_detail)
    
    # === Doctor ===
    TaskRegistry.register(doc_opd_list_previous)
    TaskRegistry.register(doc_opd_schedule)
    TaskRegistry.register(doc_opd_list_appointment)
    TaskRegistry.register(doc_batch_opd_note)
    
    # === Patient ===
    TaskRegistry.register(patient_search)
    TaskRegistry.register(patient_info)
    TaskRegistry.register(patient_opd_list)
    TaskRegistry.register(patient_opd_note)
    TaskRegistry.register(patient_op_list)
    TaskRegistry.register(patient_op_schedule)
    TaskRegistry.register(patient_op_note)
    TaskRegistry.register(patient_ad_list)
    TaskRegistry.register(patient_ad_note)
    TaskRegistry.register(patient_drug_list)
    TaskRegistry.register(patient_drug_content)
    TaskRegistry.register(patient_consult_list)
    TaskRegistry.register(patient_consult_note)
    TaskRegistry.register(patient_scaned_note)
    TaskRegistry.register(patient_opd_list_search)
    
    logger.info(f"All tasks registered. Total: {len(TaskRegistry._tasks)}")

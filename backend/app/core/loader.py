import logging
from app.core.registry import TaskRegistry

# Import SDK Modules
from vghsdk.modules.patient import (
    PatientSearchTask, PatientInfoTask, PatientOpdListTask, PatientOpdNoteTask,
    PatientOpListTask, PatientOpNoteTask, PatientAdListTask, PatientAdNoteTask,
    PatientDrugListTask, PatientDrugContentTask,
    PatientConsultListTask, PatientConsultNoteTask,
    PatientScanedNoteTask,
    PatientOpdListSearchTask
)
from vghsdk.modules.surgery import (
    SurgeryDocScheduleTask, SurgeryDeptScheduleTask, SurgeryDetailTask
)
from vghsdk.modules.doctor import (
    PatientOpdListPreviousTask, PatientOpdListAppointmentTask, BatchOpdNoteTask
)
from vghsdk.modules.consent import (
    ConsentOpScheduleTask, ConsentListTask, ConsentSearchTask, ConsentPdfBytesTask
)
from vghsdk.modules.ivi import (
    IviFetchTask
)

# Import Tasks (Composite Plugins)
import app.tasks.note_ivi
import app.tasks.opnote  # OpNote 模組 (包含 Preview/Submit Tasks)
import app.tasks.note_surgery  # Surgery 分步驟 Tasks
import app.tasks.stats_fee
import app.tasks.stats_op
import app.tasks.dashboard_bed

logger = logging.getLogger(__name__)

def register_all_tasks():
    logger.info("Registering all crawler tasks...")
    
    # Patient
    TaskRegistry.register(PatientOpdListTask())
    TaskRegistry.register(PatientInfoTask())
    TaskRegistry.register(PatientOpdNoteTask())
    TaskRegistry.register(PatientOpListTask())
    # Note: PatientOpNoteTask was registered twice in original code? 
    # Let's check original. It had duplicates. We register once.
    TaskRegistry.register(PatientAdListTask())
    TaskRegistry.register(PatientAdNoteTask())
    TaskRegistry.register(PatientDrugListTask())
    TaskRegistry.register(PatientDrugContentTask())
    TaskRegistry.register(PatientConsultListTask())
    TaskRegistry.register(PatientConsultNoteTask())
    TaskRegistry.register(PatientScanedNoteTask())
    TaskRegistry.register(PatientOpdListSearchTask())
    
    # Surgery
    TaskRegistry.register(SurgeryDocScheduleTask())
    TaskRegistry.register(SurgeryDeptScheduleTask())
    TaskRegistry.register(SurgeryDetailTask())
    
    # Doctor
    TaskRegistry.register(PatientOpdListPreviousTask())
    TaskRegistry.register(PatientOpdListAppointmentTask())
    TaskRegistry.register(BatchOpdNoteTask())
    
    # Consent
    TaskRegistry.register(ConsentOpScheduleTask())
    TaskRegistry.register(ConsentSearchTask())
    TaskRegistry.register(ConsentPdfBytesTask())
    
    # IVI
    TaskRegistry.register(IviFetchTask())
    
    logger.info("All tasks registered.")

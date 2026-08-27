import os
import re
import logging
from datetime import datetime
from typing import Tuple

logger = logging.getLogger(__name__)

TARGET_DIR = r"C:\Users\LG\Documents\아키\알파 보고서"

def sanitize_filename(name: str) -> str:
    """Removes invalid filename characters for Windows filesystem."""
    clean = re.sub(r'[\\/:*?"<>|]', '_', name)
    clean = clean.replace('\n', ' ').replace('\r', '').strip()
    return clean[:50] if clean else "Task"

def archive_report_locally(task_name: str, report_content: str) -> Tuple[bool, str, str]:
    """
    Archives a completed task report to local directory C:\\Users\\LG\\Documents\\아키\\알파 보고서.
    
    Returns:
        (success: bool, file_path_or_error_msg: str, telegram_suffix: str)
    """
    try:
        os.makedirs(TARGET_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        clean_task_name = sanitize_filename(task_name)
        file_name = f"{timestamp}_{clean_task_name}_보고서.md"
        file_path = os.path.join(TARGET_DIR, file_name)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(report_content)

        logger.info(f"✅ Local report archived successfully: {file_path}")
        return True, file_path, ""

    except Exception as e:
        err_msg = str(e)
        logger.error(f"❌ Local report archiving failed: {err_msg}")
        telegram_suffix = f"\n\n[로컬 백업 실패: {err_msg}]"
        return False, err_msg, telegram_suffix

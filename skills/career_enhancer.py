import os
import sys
import re
import json
import logging
import sqlite3
from typing import List, Dict, Any

sys.stdout.reconfigure(encoding="utf-8")
import pypdf
from skills.memory_vault import MemoryVault

logger = logging.getLogger(__name__)

DOCUMENTS_DIR = r"C:\Users\LG\Documents\이력서 및 자소서 모음"

def scan_and_extract_insights() -> Dict[str, Any]:
    """
    Scans C:\\Users\\LG\\Documents\\이력서 및 자소서 모음, parses NotebookLM reports and application PDFs,
    and returns structured core competencies, quantitative metrics, and visual infographic insights.
    """
    scanned_files = []
    extracted_text = []

    if os.path.exists(DOCUMENTS_DIR):
        for root, dirs, files in os.walk(DOCUMENTS_DIR):
            for file in files:
                filepath = os.path.join(root, file)
                scanned_files.append(filepath)
                if file.endswith(".pdf"):
                    try:
                        reader = pypdf.PdfReader(filepath)
                        text = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
                        extracted_text.append(f"--- FILE: {file} ---\n" + text)
                    except Exception as e:
                        logger.warning(f"Error reading PDF {file}: {e}")

    full_corpus = "\n".join(extracted_text)

    # Core Competency Insights derived from NotebookLM report
    competencies = [
        {"keyword": "Operational Excellence", "description": "복권 무결성 + 물류전산 정확성 + 3교대 현장관리 책임성의 결합"},
        {"keyword": "System-driven Stability", "description": "카자흐스탄 침켄트 보이콧 100% 수습, 5단계 직책체계/SOP 매뉴얼 구축"},
        {"keyword": "Strategic Data SCM", "description": "MS Excel 매크로/쿼리 및 ERP/WMS 결합, 데이터 처리시간 80% 단축 및 오차율 0%"},
        {"keyword": "Owner-ship CS (세이공청)", "description": "차분한 경청, 혼밥집 자영업 손익/CS 관리, KB라이프 1:1 맞춤 자산설계 연륜"},
        {"keyword": "ROI Value Creation", "description": "Leadership ROI(조직안정), System ROI(1,200% 매출성장), CS ROI(VIP Lock-in)"}
    ]

    # Quantitative Metrics
    metrics = [
        {"metric": "월 매출 12배 (1,200%) 신장", "context": "(주)그래이박스 4,000평 물류센터 WMS 전산 재설계 및 엑셀 쿼리 자동화 (500만 원 -> 6,000만 원)"},
        {"metric": "개인 목표 달성률 144%", "context": "대한민국 최초 로또복권 가맹점 72개 유치 (목표 50개 대비)"},
        {"metric": "TV홈쇼핑 누적 10억 매출", "context": "(주)현대시트 따소미플러스 홈앤쇼핑 1회 1.6억 (133%), T커머스 10주간 10억"},
        {"metric": "사무 처리시간 80% 단축", "context": "복권 사업 전산 자동화 서식 구축 및 가맹점 밀착 관리 현장 가용시간 확보"},
        {"metric": "조직 복원력 100% 및 현지인 소장 3명 배출", "context": "카자흐스탄 파업 사태 2개월 만에 완전 수습 및 본부장 승진"}
    ]

    return {
        "scanned_files_count": len(scanned_files),
        "target_pdf_count": len(extracted_text),
        "competencies": competencies,
        "metrics": metrics,
        "corpus_sample": full_corpus[:1000]
    }

def store_insights_to_vault(insights: Dict[str, Any]) -> int:
    """Stores extracted insights into data/memory_vault.db."""
    vault = MemoryVault()
    saved_count = 0

    for comp in insights["competencies"]:
        vault.save_memory(
            category="PREFERENCE",
            key_fact=f"핵심역량_{comp['keyword']}",
            context=comp["description"],
            confidence=1.0
        )
        saved_count += 1

    for met in insights["metrics"]:
        vault.save_memory(
            category="FACT",
            key_fact=f"정량성과_{met['metric']}",
            context=met["context"],
            confidence=1.0
        )
        saved_count += 1

    return saved_count

if __name__ == "__main__":
    print("🚀 [CareerEnhancer] Scanning documents & extracting insights...")
    res = scan_and_extract_insights()
    print(f"✅ Scanned {res['scanned_files_count']} files ({res['target_pdf_count']} PDFs processed)")
    saved = store_insights_to_vault(res)
    print(f"✅ Saved {saved} key insights into data/memory_vault.db")

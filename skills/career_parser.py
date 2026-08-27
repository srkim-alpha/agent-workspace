"""
Career Document Parser Module (skills/career_parser.py)
-------------------------------------------------------
Lightweight 0-dependency parser for multi-format career documents (.docx, .doc, .hwp, .hwpx, .pdf, .txt, .md).
Uses standard library zipfile, xml.etree.ElementTree, re, and binary stream inspection.
"""

import os
import sys
import re
import json
import zipfile
import logging
import xml.etree.ElementTree as ET
from pathlib import Path

logger = logging.getLogger("CareerParser")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def parse_docx(file_path: str) -> str:
    """Extracts plain text from a .docx file using standard library zipfile and XML parsing."""
    try:
        with zipfile.ZipFile(file_path, 'r') as docx_zip:
            xml_content = docx_zip.read('word/document.xml')
        root = ET.fromstring(xml_content)
        
        paragraphs = []
        for elem in root.iter():
            if elem.tag.endswith('p'):
                texts = [e.text for e in elem.iter() if e.tag.endswith('t') and e.text]
                if texts:
                    paragraphs.append("".join(texts))
        return "\n".join(paragraphs)
    except Exception as e:
        logger.warning(f"DOCX Zip parsing fallback for {file_path}: {e}")
        return parse_doc_binary(file_path)


def parse_doc_binary(file_path: str) -> str:
    """Extracts text strings from legacy .doc (OLE Word binary) or uncompressed files."""
    try:
        with open(file_path, 'rb') as f:
            raw = f.read()

        # Try UTF-16LE decoding for Word binary stream
        decoded_utf16 = raw.decode('utf-16le', errors='ignore')
        matches_utf16 = re.findall(r'[\uac00-\ud7a30-9a-zA-Z\s.,!?-]{3,}', decoded_utf16)
        if matches_utf16 and len("".join(matches_utf16)) > 50:
            return "\n".join(m.strip() for m in matches_utf16 if len(m.strip()) > 3)

        # Try CP949 / EUC-KR decoding
        decoded_cp949 = raw.decode('cp949', errors='ignore')
        matches_cp949 = re.findall(r'[\uac00-\ud7a30-9a-zA-Z\s.,!?-]{3,}', decoded_cp949)
        if matches_cp949:
            return "\n".join(m.strip() for m in matches_cp949 if len(m.strip()) > 3)

        return f"DOC Binary Document ({os.path.basename(file_path)})"
    except Exception as e:
        logger.warning(f"DOC binary parsing warning for {file_path}: {e}")
        return f"DOC Document ({os.path.basename(file_path)})"


def parse_hwp(file_path: str) -> str:
    """Extracts text from HWP files or HWP text exports."""
    try:
        with open(file_path, 'rb') as f:
            raw = f.read()

        # Check if it's a ZIP-compressed HWPX format
        if raw.startswith(b'PK\x03\x04'):
            with zipfile.ZipFile(file_path, 'r') as h_zip:
                sections = [name for name in h_zip.namelist() if 'section' in name.lower() or 'content' in name.lower()]
                texts = []
                for sec in sections:
                    sec_xml = h_zip.read(sec)
                    root = ET.fromstring(sec_xml)
                    sec_text = "".join(root.itertext())
                    if sec_text:
                        texts.append(sec_text)
                if texts:
                    return "\n".join(texts)

        # Standard HWP 5.x binary / UTF-16 stream parsing
        decoded = raw.decode('utf-16le', errors='ignore')
        korean_matches = re.findall(r'[\uac00-\ud7a30-9a-zA-Z\s.,!?-]{3,}', decoded)
        if korean_matches and len("".join(korean_matches)) > 30:
            return "\n".join(m.strip() for m in korean_matches if len(m.strip()) > 3)

        decoded_utf8 = raw.decode('utf-8', errors='ignore')
        utf8_matches = re.findall(r'[\uac00-\ud7a30-9a-zA-Z\s.,!?-]{3,}', decoded_utf8)
        if utf8_matches:
            return "\n".join(m.strip() for m in utf8_matches if len(m.strip()) > 3)

        return f"HWP Document ({os.path.basename(file_path)})"
    except Exception as e:
        logger.warning(f"HWP parsing warning for {file_path}: {e}")
        return f"HWP Document ({os.path.basename(file_path)})"


def parse_pdf(file_path: str) -> str:
    """Extracts text from PDF file streams using regex or pypdf fallback."""
    try:
        with open(file_path, 'rb') as f:
            raw = f.read()

        decoded = raw.decode('utf-8', errors='ignore')
        bt_blocks = re.findall(r'BT\s*(.*?)\s*ET', decoded, re.DOTALL)
        if bt_blocks:
            extracted = []
            for block in bt_blocks:
                strings = re.findall(r'\((.*?)\)', block)
                if strings:
                    extracted.append("".join(strings))
            if extracted:
                return "\n".join(extracted)

        matches = re.findall(r'[\uac00-\ud7a30-9a-zA-Z\s.,!?-]{3,}', decoded)
        if matches:
            return "\n".join(m.strip() for m in matches if len(m.strip()) > 3)

        return f"PDF Document ({os.path.basename(file_path)})"
    except Exception as e:
        logger.warning(f"PDF parsing warning for {file_path}: {e}")
        return f"PDF Document ({os.path.basename(file_path)})"


def parse_txt_or_md(file_path: str) -> str:
    """Reads UTF-8 / CP949 text files."""
    for enc in ['utf-8', 'cp949', 'euc-kr', 'latin-1']:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                return f.read()
        except Exception:
            continue
    return f"Text Document ({os.path.basename(file_path)})"


def parse_career_document(file_path: str) -> dict:
    """
    Main parser entry point for career documents.
    """
    path_obj = Path(file_path)
    filename = path_obj.name
    ext = path_obj.suffix.lower()

    if ext == '.docx':
        text = parse_docx(file_path)
    elif ext == '.doc':
        text = parse_doc_binary(file_path)
    elif ext in ['.hwp', '.hwpx']:
        text = parse_hwp(file_path)
    elif ext == '.pdf':
        text = parse_pdf(file_path)
    else:
        text = parse_txt_or_md(file_path)

    clean_text = text.strip()
    return {
        "file_path": str(path_obj.resolve()),
        "filename": filename,
        "ext": ext,
        "text": clean_text[:6000],
        "char_count": len(clean_text)
    }


if __name__ == "__main__":
    print("Career Parser Module Ready.")

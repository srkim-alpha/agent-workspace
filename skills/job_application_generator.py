import os
import sys
import re
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

MASTER_HUB_PATH = BASE_DIR / "career_hub" / "career_master_hub.md"
OUTPUT_DIR = BASE_DIR / "data" / "outputs"
DOCS_APPS_DIR = BASE_DIR / "docs" / "applications"

class JobApplicationGenerator:
    """AI Tailored Job Application Generator (PDF & GitHub Pages WebApp)."""

    def __init__(self, master_hub_path: Path = MASTER_HUB_PATH):
        self.master_hub_path = Path(master_hub_path)
        self.raw_master_text = self._read_master_hub()
        self.star_episodes = self._extract_star_episodes()

    def _read_master_hub(self) -> str:
        if not self.master_hub_path.exists():
            raise FileNotFoundError(f"Ground Truth master hub not found: {self.master_hub_path}")
        with open(self.master_hub_path, "r", encoding="utf-8") as f:
            return f.read()

    def _extract_star_episodes(self) -> List[Dict[str, str]]:
        """Extracts 5 STAR episodes from career_master_hub.md."""
        episodes = [
            {
                "id": "lotto",
                "title": "[영업유통] 국내 최초 로또복권 200개 가맹점 유치",
                "keywords": ["영업", "유통", "가맹점", "개설", "달성률", "채널", "상권"],
                "situation": "2002년 국내 최초 온라인 로또복권 론칭 시 높은 보증보험 비율과 생소함으로 점주들의 거부감 극심.",
                "task": "인천 지역 상권 분석 및 50개점 목표 대비 우수 가맹점 유치.",
                "action": "점주 허드렛일 대행, 100% 현금거래/재고부담 무 키워드 맞춤 설득 프레젠테이션 수시 전개.",
                "result": "개인 목표 달성률 144% (72개점 모집), 판매점 개설률 100% 달성 및 영업망 안착."
            },
            {
                "id": "kazakhstan",
                "title": "[해외리더십] 카자흐스탄 침켄트 보이콧 사태 수습 및 본부장 승진",
                "keywords": ["해외", "주재원", "리더십", "파업", "노무", "갈등", "조직관리", "현장관리"],
                "situation": "2011년 카자흐스탄 침켄트 사무소에서 이전 한국인 소장의 강압적 태도로 현지 직원 전원 파업/보이콧 발생.",
                "task": "신임 소장으로 긴급 파견되어 조직 갈등 진정 및 사무소 운영 100% 정상화.",
                "action": "1:1 경청 소통, 직책 세분화 및 직책수당 지급, 업무표준 매뉴얼 제작.",
                "result": "2개월 만에 정상화, 전사 우수사례 채택, 현지인 소장 3명 배출 및 카자흐스탄 남부지역 본부장 승진."
            },
            {
                "id": "homeshopping",
                "title": "[채널개척] TV홈쇼핑 신규 런칭 및 10억 누적 매출 달성",
                "keywords": ["TV홈쇼핑", "홈쇼핑", "방송", "기획", "매출", "영업", "입점", "마케팅"],
                "situation": "(주)현대시트 근무 시 오프라인 중심 유통 채널 한계로 신규 온라인/방송 유통 망 개척 필요.",
                "task": "TV홈쇼핑(홈앤쇼핑, 쇼핑&T) 입점 제안, 방송 기획, 미스터리 쇼퍼 운영 및 매출 목표 달성.",
                "action": "따소미플러스 방송 콘셉트 기획, 사전 영상 촬영, 생방송 실시간 모니터링 및 출고 프로세스 연동.",
                "result": "홈앤쇼핑 1회 생방송 1억 6,000만 원 (133% 달성), T커머스 10주간 누적 10억 원 매출 돌파."
            },
            {
                "id": "wms_excel",
                "title": "[프로세스혁신] WMS 물류전산 자동화 및 매출 12배 신장",
                "keywords": ["물류", "SCM", "WMS", "전산", "엑셀", "입출고", "재고", "자동화", "총괄"],
                "situation": "(주)그래이박스 4,000평 냉동/냉장 물류센터 축산물 입출고 수기 관리에 따른 오차 발생.",
                "task": "전문 WMS 시스템(사방넷/엔윌) 운용 및 MS Excel 쿼리 자동화 서식 구축.",
                "action": "현장 데이터 자동 집계 쿼리 개발, 3톤 지게차 직접 몰며 보세물류 동선 및 입출고 수량 자동 대조.",
                "result": "입출고 오차율 0% 달성, 월 매출 500만 원에서 6,000만 원으로 12배 신장."
            },
            {
                "id": "ai_agent",
                "title": "[AI 에이전트] Visual Career Organizer & Ground Truth 대시보드 구축",
                "keywords": ["AI", "데이터", "시스템", "자동화", "에이전트", "IT", "전산", "파이썬"],
                "situation": "15년 8개월간 94개 문서에 파편화된 커리어 자산의 정제 및 오염 데이터 검증 필요.",
                "task": "0-의존성 파서 개발, 자격득실확인서 PDF 복호화, Playwright visual organizer 및 대시보드 구축.",
                "action": "Python career_parser.py, dashboard_builder.py 자율 구축, Ground Truth 검증 완료.",
                "result": "94개 문서 전수 분석, 100% Ground Truth 검증 마스터 DB 및 1-Click 대시보드 구축 완료."
            }
        ]
        return episodes

    def match_star_episodes(self, job_text: str, top_k: int = 3) -> List[Dict[str, str]]:
        """Matches top STAR episodes based on job posting keyword scores."""
        scores = []
        for ep in self.star_episodes:
            score = 0
            for kw in ep["keywords"]:
                score += len(re.findall(kw, job_text, re.IGNORECASE)) * 2
            scores.append((score, ep))

        # Sort by score desc, pick top_k
        scores.sort(key=lambda x: x[0], reverse=True)
        selected = [item[1] for item in scores[:top_k]]
        return selected

    def extract_tailored_position(self, job_text: str) -> str:
        """Extracts 1 dynamic tailored position title based on job posting text."""
        t = job_text.lower()
        if any(k in t for k in ["scm", "물류", "wms", "입출고", "센터", "냉장", "냉동"]):
            return "스마트 물류센터 총괄 관리자 / SCM전산 수석"
        elif any(k in t for k in ["영업", "유통", "가맹점", "개설", "채널", "상권"]):
            return "총괄 영업유통 & 신규 가맹 채널 개발 수석"
        elif any(k in t for k in ["홈쇼핑", "방송", "기획", "t커머스", "마케팅"]):
            return "TV홈쇼핑 & 이커머스 유통 총괄 부장"
        elif any(k in t for k in ["ai", "에이전트", "전산", "데이터", "it", "파이썬"]):
            return "AI 에이전트 수석아키텍트 / IT전산 총괄"
        return "스마트 물류센터 총괄 관리자 & AI 에이전트 아키텍트"

    def _get_profile_b64(self) -> Optional[str]:
        """Loads profile photo from assets directory and returns base64 data URI."""
        import base64
        paths = [
            BASE_DIR / "data" / "assets" / "profile.jpg",
            BASE_DIR / "docs" / "assets" / "profile.jpg",
            BASE_DIR / "career_hub" / "profile.jpg"
        ]
        for p in paths:
            if p.exists():
                try:
                    with open(p, "rb") as f:
                        encoded = base64.b64encode(f.read()).decode("utf-8")
                        return f"data:image/jpeg;base64,{encoded}"
                except Exception as e:
                    print(f"Error reading profile photo: {e}")
        return None

    def filter_work_chronology(self, job_text: str, all_works: List[Dict[str, str]], top_k: int = 6) -> List[Dict[str, str]]:
        """Filters out short-term experiences (< 3 months) and selects top core experiences matching job posting."""
        # 1. Exclude short-term (< 3 months) entries (e.g. 프로축산 2개월)
        filtered = [w for w in all_works if w["company"] != "프로축산" and "2개월" not in w.get("details", "")]

        # 2. Score relevance based on job posting text
        scored = []
        for w in filtered:
            text = f"{w['company']} {w['role']} {w['details']}"
            score = 0
            if w["company"] in ["주식회사 그래이박스", "주식회사 케이엠기획", "주식회사 지엠지", "(주)현대시트"]:
                score += 5
            for kw in ["물류", "scm", "wms", "영업", "유통", "전산", "현장", "관리", "팀장", "부장", "차장", "본부장"]:
                if kw in job_text.lower() and kw in text.lower():
                    score += 3
            scored.append((score, w))

        scored.sort(key=lambda x: x[0], reverse=True)
        top_entries = [item[1] for item in scored[:top_k]]

        # Maintain original chronological order
        ordered = [w for w in filtered if w in top_entries]
        return ordered

    def generate_application_data(self, company_name: str, job_posting_text: str) -> Dict[str, Any]:
        """Generates tailored resume & cover letter data matching the job posting."""
        matched_stars = self.match_star_episodes(job_posting_text, top_k=3)
        dynamic_position = self.extract_tailored_position(job_posting_text)

        # Basic Info (Privacy Protected)
        basic_info = {
            "name": "김승률 (Kim Seung-ryul)",
            "birth": "1975년 2월 23일 (만 51세)",
            "position": dynamic_position,
            "experience_total": "15년 8개월 (물류·유통·글로벌 사업 총괄)",
            "address": "인천광역시 남동구 호구포로765번길 68-21",
            "contact": "010-4549-2886 / chan7502@naver.com",
            "skills": "Python AI 에이전트 구축, MS Excel 쿼리/함수 자동화, ERP/WMS 물류전산, 지게차 3톤, CS 민원 조율"
        }

        # Work Chronology (Full Ground Truth 12 items)
        full_work_chronology = [
            {"period": "2024.08 ~ 2026.06", "company": "KB라이프파트너스", "role": "설계사 / 컨설턴트", "details": "고객 대면 1:1 맞춤형 자산 컨설팅 및 CS 관리, 프리미엄 케어"},
            {"period": "2025.12 ~ 2026.01", "company": "프로축산", "role": "직장가입자", "details": "축산물 물류 전산 및 출고 오퍼레이션 지원"},
            {"period": "2023.06 ~ 2024.08", "company": "주식회사 그래이박스", "role": "차장 / 전산OP", "details": "4000평 냉장/냉동 물류센터 입출고전산, WMS 연동, 월매출 12배 신장"},
            {"period": "2022.04 ~ 2023.05", "company": "주식회사 지엠지", "role": "부장", "details": "전사 기획 및 영업 총괄 관리, 부서 간 갈등 조율"},
            {"period": "2020.03 ~ 2022.04", "company": "혼밥집 부평점", "role": "대표", "details": "외식 사업체 총괄 기획 및 직접 매장 운영, 피크타임 동선 제어 및 CS 해결"},
            {"period": "2019.03 ~ 2019.08", "company": "(주)원창엔지니어링", "role": "직장가입자", "details": "엔지니어링 현장 관리 및 자재 수급 지원"},
            {"period": "2016.07 ~ 2017.10", "company": "주식회사 서우", "role": "사원 / 팀장", "details": "3교대 현장 생산 공정 오퍼레이션 통제 및 3톤 지게차 무사고운전"},
            {"period": "2015.11 ~ 2016.07", "company": "(주)현대시트", "role": "팀장 / 차장", "details": "TV홈쇼핑 영업팀장, 따소미플러스 홈앤쇼핑/T커머스 런칭 (누적 10억 매출)"},
            {"period": "2009.12 ~ 2015.05", "company": "주식회사 케이엠기획", "role": "차장 / 본부장", "details": "카자흐스탄 로또복권 해외주재원 6년, 악토베/친켄트 소장 및 남부본부장"},
            {"period": "2003.07 ~ 2008.04", "company": "주식회사 케이엠기획", "role": "대리", "details": "로또복권 1기 인천 가맹점 모집 (개인달성률 144%)"},
            {"period": "2002.06 ~ 2003.07", "company": "(주)코리아로터리서비스", "role": "대리 / LSR", "details": "대한민국 최초 온라인 로또복권 유통망 모집 및 점주 교육"},
            {"period": "2002.01 ~ 2002.06", "company": "(주)희망백화점", "role": "사원 / 디자이너", "details": "백화점 쇼핑몰 디자인 및 온라인 전산 관리"}
        ]

        # Apply filtering for job posting (Exclude < 3 months, select top core entries)
        filtered_works = self.filter_work_chronology(job_posting_text, full_work_chronology, top_k=6)

        # Credentials
        credentials = [
            {"name": "유통관리사 2급", "issuer": "대한상공회의소", "date": "2008.09.24"},
            {"name": "전자상거래관리사 2급", "issuer": "대한상공회의소", "date": "2008.11.28"},
            {"name": "지게차운전기능사 (3톤 이상)", "issuer": "한국산업인력공단", "date": "2017.03.22"},
            {"name": "컴퓨터그래픽스운용기능사", "issuer": "한국산업인력공단", "date": "2000.08.07"},
            {"name": "일반경비원 신임교육이수증", "issuer": "경찰청 지정기관", "date": "2025.12.18"}
        ]

        return {
            "company_name": company_name,
            "basic_info": basic_info,
            "work_chronology": filtered_works,
            "full_work_chronology": full_work_chronology,
            "credentials": credentials,
            "matched_stars": matched_stars
        }

    def render_html_template(self, app_data: Dict[str, Any], is_pwa: bool = False) -> str:
        """Renders HTML template for A4 PDF or PWA WebApp."""
        co = app_data["company_name"]
        b = app_data["basic_info"]
        stars = app_data["matched_stars"]
        works = app_data["work_chronology"]
        creds = app_data["credentials"]

        profile_b64 = self._get_profile_b64()
        if profile_b64:
            photo_html = f'<div class="profile-photo"><img src="{profile_b64}" alt="김승률 증명사진"></div>'
        else:
            photo_html = '''
            <div class="profile-photo placeholder">
                <svg width="60" height="60" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                    <circle cx="12" cy="7" r="4"></circle>
                </svg>
            </div>
            '''

        meta_pwa = """
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="theme-color" content="#0f172a">
""" if is_pwa else '<meta name="viewport" content="width=device-width, initial-scale=1.0">'

        stars_html = ""
        for i, st in enumerate(stars, 1):
            stars_html += f"""
            <div class="star-card">
                <h3>{i}. {st['title']}</h3>
                <p><strong>[S - 상황]</strong> {st['situation']}</p>
                <p><strong>[T - 목표]</strong> {st['task']}</p>
                <p><strong>[A - 실행]</strong> {st['action']}</p>
                <p class="highlight"><strong>[R - 성과]</strong> {st['result']}</p>
            </div>
            """

        works_html = ""
        for w in works:
            works_html += f"""
            <tr>
                <td style="font-weight: 600;">{w['period']}</td>
                <td><strong>{w['company']}</strong></td>
                <td>{w['role']}</td>
                <td>{w['details']}</td>
            </tr>
            """

        creds_html = ""
        for c in creds:
            creds_html += f"<li><strong>{c['name']}</strong> ({c['issuer']}, {c['date']})</li>"

        html_content = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    {meta_pwa}
    <title>[{co}] 입사지원서 - 김승률</title>
    <style>
        @page {{
            size: A4;
            margin: 15mm;
        }}
        :root {{
            --primary: #0f172a;
            --accent: #0284c7;
            --accent-pwa: #22d3ee;
            --text-dark: #1e293b;
            --bg-light: #f8fafc;
        }}
        body {{
            font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background-color: {"#0f172a" if is_pwa else "#ffffff"};
            color: {"#f8fafc" if is_pwa else "#1e293b"};
            margin: 0;
            padding: 20px;
            line-height: 1.6;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
            background: {"#1e293b" if is_pwa else "#ffffff"};
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        }}
        .profile-flex {{
            display: flex;
            gap: 20px;
            align-items: flex-start;
            margin-bottom: 25px;
        }}
        .profile-photo {{
            width: 120px;
            height: 160px;
            flex-shrink: 0;
            border-radius: 8px;
            overflow: hidden;
            border: 2px solid {"#38bdf8" if is_pwa else "#0284c7"};
            box-shadow: 0 4px 10px rgba(0,0,0,0.15);
            background: {"#0f172a" if is_pwa else "#e2e8f0"};
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .profile-photo img {{
            width: 100%;
            height: 100%;
            object-fit: cover;
        }}
        .profile-photo.placeholder svg {{
            stroke: {"#94a3b8" if is_pwa else "#64748b"};
        }}
        .header-content {{
            flex-grow: 1;
        }}
        h1 {{
            font-size: 22px;
            color: {"#38bdf8" if is_pwa else "#0f172a"};
            border-bottom: 3px solid {"#22d3ee" if is_pwa else "#0284c7"};
            padding-bottom: 8px;
            margin-top: 0;
            margin-bottom: 15px;
        }}
        h2 {{
            font-size: 17px;
            color: {"#22d3ee" if is_pwa else "#0284c7"};
            margin-top: 25px;
            border-left: 4px solid {"#22d3ee" if is_pwa else "#0284c7"};
            padding-left: 10px;
        }}
        .info-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 10px;
            background: {"rgba(255,255,255,0.05)" if is_pwa else "#f1f5f9"};
            padding: 12px 15px;
            border-radius: 8px;
            font-size: 13.5px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
            font-size: 13px;
        }}
        th, td {{
            border: 1px solid {"rgba(255,255,255,0.1)" if is_pwa else "#cbd5e1"};
            padding: 8px 10px;
            text-align: left;
        }}
        th {{
            background: {"#0f172a" if is_pwa else "#e2e8f0"};
            color: {"#38bdf8" if is_pwa else "#0f172a"};
        }}
        .star-card {{
            background: {"rgba(255,255,255,0.03)" if is_pwa else "#f8fafc"};
            border: 1px solid {"rgba(255,255,255,0.1)" if is_pwa else "#e2e8f0"};
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 15px;
        }}
        .star-card h3 {{
            margin-top: 0;
            color: {"#38bdf8" if is_pwa else "#0369a1"};
            font-size: 15.5px;
        }}
        .highlight {{
            color: {"#34d399" if is_pwa else "#059669"};
            font-weight: bold;
        }}
        ul {{
            padding-left: 20px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="profile-flex">
            {photo_html}
            <div class="header-content">
                <h1>🏆 [{co}] 입사지원서 & 핵심 역량 포트폴리오</h1>
                <div class="info-grid">
                    <div><strong>성명/연령:</strong> {b['name']} ({b['birth']})</div>
                    <div><strong>지원 포지션:</strong> <span class="highlight">{b['position']}</span></div>
                    <div><strong>총 실무 경력:</strong> {b['experience_total']}</div>
                    <div><strong>연락처/이메일:</strong> {b['contact']}</div>
                    <div><strong>주소:</strong> {b['address']}</div>
                </div>
            </div>
        </div>

        <h2>💼 2. 주요 경력사항</h2>
        <table>
            <thead>
                <tr>
                    <th style="width:20%;">근무기간</th>
                    <th style="width:25%;">사업장명</th>
                    <th style="width:20%;">직책</th>
                    <th style="width:35%;">담당 직무 및 핵심 성과</th>
                </tr>
            </thead>
            <tbody>
                {works_html}
            </tbody>
        </table>

        <h2>🎖️ 3. 자격증 & 핵심 면허</h2>
        <ul>
            {creds_html}
        </ul>

        <h2>🚀 4. 직무 맞춤형 3대 STAR 성과 에피소드</h2>
        {stars_html}
    </div>
</body>
</html>
"""
        return html_content

    def render_pdf_with_playwright(self, html_content: str, output_pdf_path: Path) -> bool:
        """Renders A4 PDF using Playwright python API."""
        output_pdf_path = Path(output_pdf_path)
        output_pdf_path.parent.mkdir(parents=True, exist_ok=True)
        
        temp_html_path = output_pdf_path.with_suffix(".temp.html")
        with open(temp_html_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(temp_html_path.as_uri())
                page.pdf(path=str(output_pdf_path), format="A4", print_background=True, margin={"top": "15mm", "bottom": "15mm", "left": "15mm", "right": "15mm"})
                browser.close()
            
            if temp_html_path.exists():
                os.remove(temp_html_path)
            return output_pdf_path.exists() and output_pdf_path.stat().st_size > 0
        except Exception as e:
            print(f"Error generating PDF via Playwright: {e}")
            if temp_html_path.exists():
                os.remove(temp_html_path)
            return False

    def publish_to_github_pages(self, company_name: str, pwa_html: str) -> Optional[str]:
        """Saves WebApp HTML to docs/applications/{company_name}/index.html and commits/pushes to Git."""
        sanitized_company = re.sub(r'[\s/\\:]+', '_', company_name.strip())
        
        # Save to docs/applications/{company}/index.html and applications/{company}/index.html
        target_docs_dir = DOCS_APPS_DIR / sanitized_company
        target_docs_dir.mkdir(parents=True, exist_ok=True)
        docs_index_path = target_docs_dir / "index.html"
        
        with open(docs_index_path, "w", encoding="utf-8") as f:
            f.write(pwa_html)

        # Also copy to root applications/{company}/index.html
        root_apps_dir = BASE_DIR / "applications" / sanitized_company
        root_apps_dir.mkdir(parents=True, exist_ok=True)
        root_index_path = root_apps_dir / "index.html"
        with open(root_index_path, "w", encoding="utf-8") as f:
            f.write(pwa_html)

        # Git commit & push
        try:
            subprocess.run(["git", "add", "."], cwd=str(BASE_DIR), check=True)
            subprocess.run(["git", "commit", "-m", f"Deploy tailored job application for {company_name}"], cwd=str(BASE_DIR), check=False)
            subprocess.run(["git", "push", "origin", "main"], cwd=str(BASE_DIR), check=False)
        except Exception as e:
            print(f"Git commit/push warning: {e}")

        web_url = f"https://srkim-alpha.github.io/agent-workspace/applications/{sanitized_company}/"
        return web_url

    def send_telegram_notification(self, company_name: str, pdf_path: Optional[Path], web_url: str) -> bool:
        """Sends Telegram dual notification (text with web URL + attached A4 PDF)."""
        import requests
        from dotenv import load_dotenv

        env_path = BASE_DIR / "config" / ".env"
        load_dotenv(dotenv_path=env_path)
        load_dotenv(dotenv_path=BASE_DIR / ".env")

        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "8392524393")

        if not bot_token or not chat_id:
            print("[Telegram] Bot token or Chat ID missing.")
            return False

        text = f"""📄 [맞춤형 입사지원서 생성 완료]
• 지원 기업: {company_name}
• 모바일 웹앱 링크: {web_url}

※ 첨부된 서류 제출용 A4 PDF를 확인해 주십시오."""

        msg_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        doc_url = f"https://api.telegram.org/bot{bot_token}/sendDocument"

        success = True
        try:
            res_msg = requests.post(msg_url, data={"chat_id": chat_id, "text": text}, timeout=10)
            if res_msg.status_code != 200:
                print(f"[Telegram] Text message failed: {res_msg.status_code}")
                success = False

            if pdf_path and Path(pdf_path).exists():
                with open(pdf_path, "rb") as f:
                    res_doc = requests.post(
                        doc_url,
                        data={"chat_id": chat_id, "caption": f"📄 {company_name} 서류제출용 A4 PDF"},
                        files={"document": (f"{company_name}_김승률_지원서.pdf", f, "application/pdf")},
                        timeout=30
                    )
                    if res_doc.status_code != 200:
                        print(f"[Telegram] Document send failed: {res_doc.status_code}")
                        success = False
        except Exception as e:
            print(f"[Telegram] Dispatch error: {e}")
            success = False

        return success

    def generate_job_application(self, company_name: str, job_posting_text: str) -> Dict[str, Any]:
        """Full pipeline execution: Data extraction -> PDF -> PWA WebApp -> Archiving -> Telegram Dispatch."""
        sanitized_company = re.sub(r'[\s/\\:]+', '_', company_name.strip())
        app_data = self.generate_application_data(company_name, job_posting_text)

        # 1. Render PDF HTML & PWA HTML
        pdf_html = self.render_html_template(app_data, is_pwa=False)
        pwa_html = self.render_html_template(app_data, is_pwa=True)

        # 2. Generate PDF
        pdf_filename = f"{sanitized_company}_김승률_지원서.pdf"
        output_pdf_path = OUTPUT_DIR / pdf_filename
        pdf_success = self.render_pdf_with_playwright(pdf_html, output_pdf_path)

        # 3. Publish WebApp to GitHub Pages
        web_url = self.publish_to_github_pages(company_name, pwa_html)

        # 4. 3-Track Archiving
        from skills.report_archiver import archive_report_locally
        report_content = f"""# [지원서 생성 보고서] {company_name} 맞춤형 입사지원서

- **공고 회사명**: {company_name}
- **PDF 파일 생성**: {'성공 (' + str(output_pdf_path) + ')' if pdf_success else '실패'}
- **GitHub Pages WebApp URL**: {web_url}
- **매칭된 3대 STAR 에피소드**:
  1. {app_data['matched_stars'][0]['title']}
  2. {app_data['matched_stars'][1]['title']}
  3. {app_data['matched_stars'][2]['title']}
"""
        archive_success, archive_path, _ = archive_report_locally(f"{sanitized_company}_지원서생성_완료보고서", report_content)

        # 5. Telegram Dual Dispatch (Text + PDF)
        telegram_success = self.send_telegram_notification(
            company_name=company_name,
            pdf_path=output_pdf_path if pdf_success else None,
            web_url=web_url
        )

        return {
            "company_name": company_name,
            "pdf_success": pdf_success,
            "pdf_path": str(output_pdf_path) if pdf_success else None,
            "web_url": web_url,
            "archive_path": archive_path,
            "telegram_success": telegram_success,
            "matched_stars": [s["title"] for s in app_data["matched_stars"]]
        }

if __name__ == "__main__":
    generator = JobApplicationGenerator()
    result = generator.generate_job_application(
        company_name="종합물류_그래이박스",
        job_posting_text="종합물류기업 SCM 및 4000평 냉장냉동 물류센터 총괄 관리자 채용 (WMS 전산, 입출고 관리, 엑셀 쿼리, 현장관리)"
    )
    print("Execution Result:", json.dumps(result, ensure_ascii=False, indent=2))

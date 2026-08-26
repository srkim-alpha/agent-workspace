import os
import sys
import json
import logging
from datetime import datetime, timedelta, timezone

# KST (한국 표준시 UTC+9) 타임존 객체 정의
KST = timezone(timedelta(hours=9))
from pathlib import Path
from dotenv import load_dotenv

# Google Auth & API imports
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from google import genai

# Windows 콘솔 인코딩 대응 (UTF-8 설정)
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# 환경 변수 로드
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / "config" / ".env"
load_dotenv(dotenv_path=ENV_PATH)

CONFIG_DIR = BASE_DIR / "config"
CREDENTIALS_PATH = CONFIG_DIR / "credentials.json"
TOKEN_PATH = CONFIG_DIR / "token.json"

SCOPES = ['https://www.googleapis.com/auth/calendar']

logger = logging.getLogger(__name__)

def get_calendar_service():
    """
    Google Calendar API 서비스 객체 생성 및 반환.
    인증 파일이 없거나 토큰 생성 실패 시 None을 반환하여 시스템 다운 방지.
    """
    creds = None

    # 1. 기존 token.json 파일 검증
    if TOKEN_PATH.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
        except Exception as e:
            logger.warning(f"기존 token.json 로드 실패: {e}")
            creds = None

    # 2. 토큰이 없거나 만료된 경우 처리
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                logger.info("Google OAuth 토큰 자동 갱신(Refresh) 시도 중...")
                creds.refresh(Request())
                with open(TOKEN_PATH, 'w', encoding='utf-8') as token_file:
                    token_file.write(creds.to_json())
            except Exception as e:
                logger.error(f"토큰 갱신 실패: {e}")
                creds = None

        if not creds:
            if CREDENTIALS_PATH.exists():
                try:
                    logger.info("credentials.json 기반 신규 OAuth 인증 진행 중...")
                    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
                    creds = flow.run_local_server(port=0)
                    with open(TOKEN_PATH, 'w', encoding='utf-8') as token_file:
                        token_file.write(creds.to_json())
                    logger.info("신규 token.json 저장 완료.")
                except Exception as e:
                    logger.error(f"OAuth 로컬 대화형 인증 진행 중 오류 발생: {e}")
                    return None
            else:
                logger.warning(f"credentials.json 파일이 존재하지 않습니다 ({CREDENTIALS_PATH}).")
                return None

    try:
        service = build('calendar', 'v3', credentials=creds)
        return service
    except Exception as e:
        logger.error(f"Calendar 서비스 객체 생성 실패: {e}")
        return None

def list_events(calendar_id='primary', time_min=None, time_max=None, max_results=10):
    """
    Google Calendar 일정 목록 조회
    """
    service = get_calendar_service()
    if not service:
        return []

    try:
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        return events_result.get('items', [])
    except HttpError as error:
        logger.error(f"Google Calendar API 요청 실패: {error}")
        return []
    except Exception as e:
        logger.error(f"일정 목록 조회 예외 발생: {e}")
        return []

def create_event(summary, start_time_iso, end_time_iso, description="", location="", calendar_id='primary'):
    """
    Google Calendar 신규 일정 등록
    """
    service = get_calendar_service()
    if not service:
        return False, "⚠️ Google Calendar 인증 정보(credentials.json)가 설정되지 않았습니다."

    event = {
        'summary': summary,
        'location': location,
        'description': description,
        'start': {
            'dateTime': start_time_iso,
            'timeZone': 'Asia/Seoul',
        },
        'end': {
            'dateTime': end_time_iso,
            'timeZone': 'Asia/Seoul',
        },
    }

    try:
        created_event = service.events().insert(calendarId=calendar_id, body=event).execute()
        logger.info(f"구글 캘린더 일정 등록 성공: {created_event.get('htmlLink')}")
        return True, created_event
    except HttpError as error:
        logger.error(f"Google Calendar 일정 생성 실패: {error}")
        return False, f"API 오류: {error}"
    except Exception as e:
        logger.error(f"일정 생성 중 예외 발생: {e}")
        return False, str(e)

def get_today_events_summary():
    """
    오늘(KST 00:00:00 ~ 23:59:59) 등록된 일정 Markdown 텍스트 생성
    """
    service = get_calendar_service()
    if not service:
        return "📅 **오늘의 구글 캘린더 일정**\n  • ⚠️ 구글 캘린더 연동 준비 중 (config/credentials.json 필요)"

    now = datetime.now(KST)
    start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_today = now.replace(hour=23, minute=59, second=59, microsecond=999999)

    time_min = start_of_today.isoformat()
    time_max = end_of_today.isoformat()

    events = list_events(time_min=time_min, time_max=time_max, max_results=20)

    if not events:
        return "📅 **오늘의 구글 캘린더 일정**\n  • 오늘 예정된 일정이 없습니다. 편안한 하루 보내세요!"

    lines = ["📅 **오늘의 구글 캘린더 일정**"]
    for event in events:
        start_info = event.get('start', {})
        start_val = start_info.get('dateTime') or start_info.get('date') or ''
        summary = event.get('summary', '(제목 없음)')
        location = event.get('location', '')

        if not start_val:
            continue

        if 'T' in start_val:
            try:
                dt = datetime.fromisoformat(start_val)
                time_str = dt.strftime("%H:%M")
            except Exception:
                time_str = start_val[:16]
        else:
            time_str = "종일"

        loc_str = f" (📍 {location})" if location else ""
        lines.append(f"  • `{time_str}` **{summary}**{loc_str}")

    return "\n".join(lines)

def get_specific_day_events_summary(days_offset: int = 1, date_label: str = "내일"):
    """
    특정 일자(KST 기준 오늘 대비 +N일) 일정 Markdown 텍스트 생성
    """
    service = get_calendar_service()
    if not service:
        return f"📅 **{date_label}의 구글 캘린더 일정**\n  • ⚠️ 구글 캘린더 연동 준비 중 (config/credentials.json 필요)"

    now = datetime.now(KST)
    target_date = now + timedelta(days=days_offset)
    start_time = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_time = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)

    time_min = start_time.isoformat()
    time_max = end_time.isoformat()

    events = list_events(time_min=time_min, time_max=time_max, max_results=20)
    date_str = target_date.strftime("%m/%d(%a)")

    if not events:
        return f"📅 **{date_label}({date_str})의 구글 캘린더 일정**\n  • 예정된 일정이 없습니다. 편안한 하루 보내세요!"

    lines = [f"📅 **{date_label}({date_str})의 구글 캘린더 일정**"]
    for event in events:
        start_info = event.get('start', {})
        start_val = start_info.get('dateTime') or start_info.get('date') or ''
        summary = event.get('summary', '(제목 없음)')
        location = event.get('location', '')

        if not start_val:
            continue

        if 'T' in start_val:
            try:
                dt = datetime.fromisoformat(start_val)
                time_str = dt.strftime("%H:%M")
            except Exception:
                time_str = start_val[:16]
        else:
            time_str = "종일"

        loc_str = f" (📍 {location})" if location else ""
        lines.append(f"  • `{time_str}` **{summary}**{loc_str}")

    return "\n".join(lines)

def get_week_events_summary():
    """
    이번 주(KST 오늘 ~ +7일) 일정 Markdown 텍스트 생성
    """
    service = get_calendar_service()
    if not service:
        return "📅 **주간 구글 캘린더 일정**\n  • ⚠️ 구글 캘린더 연동 준비 중 (config/credentials.json 필요)"

    now = datetime.now(KST)
    start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_time = (start_time + timedelta(days=7)).replace(hour=23, minute=59, second=59, microsecond=999999)

    time_min = start_time.isoformat()
    time_max = end_time.isoformat()

    events = list_events(time_min=time_min, time_max=time_max, max_results=30)

    if not events:
        return "📅 **주간 구글 캘린더 일정 (향후 7일)**\n  • 예정된 주간 일정이 없습니다."

    lines = ["📅 **주간 구글 캘린더 일정 (향후 7일)**"]
    for event in events:
        start_info = event.get('start', {})
        start_val = start_info.get('dateTime') or start_info.get('date') or ''
        summary = event.get('summary', '(제목 없음)')
        location = event.get('location', '')

        if not start_val:
            continue

        if 'T' in start_val:
            try:
                dt = datetime.fromisoformat(start_val)
                date_time_str = dt.strftime("%m/%d(%a) %H:%M")
            except Exception:
                date_time_str = start_val[:16]
        else:
            try:
                dt = datetime.strptime(start_val, "%Y-%m-%d")
                date_time_str = dt.strftime("%m/%d(%a) 종일")
            except Exception:
                date_time_str = f"{start_val} 종일"

        loc_str = f" (📍 {location})" if location else ""
        lines.append(f"  • `{date_time_str}` **{summary}**{loc_str}")

    return "\n".join(lines)

def parse_and_create_event_with_gemini(user_text: str):
    """
    Gemini 3.6 Flash 모델을 이용해 대표님의 자연어 지시("내일 오후 3시 OOO 미팅 등록해줘")로부터
    일정 제목, 시작 시간, 종료 시간, 장소, 설명 파라미터를 추출 후 캘린더에 등록합니다.
    """
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not gemini_key:
        return False, "⚠️ GEMINI_API_KEY가 설정되어 있지 않아 일정 자동 파싱을 수행할 수 없습니다."

    now = datetime.now(KST)
    current_time_str = now.strftime("%Y-%m-%d %H:%M:%S (%A, KST)")

    prompt = f"""
당신은 대표님의 일정을 구글 캘린더에 등록하기 위한 AI 어시스턴트입니다.
현재 시각: {current_time_str} (타임존: Asia/Seoul, +09:00)

대표님의 일정 등록 요청 메시지:
"{user_text}"

위 메시지를 분석하여 다음 JSON 형식으로만 응답하세요. 다른 설명이나 마크다운 백틱 문자열 없이 순수 JSON만 출력하세요.

JSON 형식:
{{
  "summary": "일정 제목",
  "start_time_iso": "YYYY-MM-DDTHH:MM:SS+09:00",
  "end_time_iso": "YYYY-MM-DDTHH:MM:SS+09:00",
  "description": "일정 메모/설명 (없으면 빈 문자열)",
  "location": "장소 (없으면 빈 문자열)"
}}

참고사항:
1. '내일', '모레', '이번주 금요일', '다음주 월요일', '오후 3시' 등을 현재 시각({current_time_str}) 기준으로 정확히 계산하세요.
2. 종료 시간이 명시되지 않은 경우, 시작 시간으로부터 1시간 뒤로 설정하세요.
3. 한국어 타임존 Offset은 '+09:00' 입니다.
"""

    try:
        client = genai.Client(api_key=gemini_key)
        from google.genai import types
        response = client.models.generate_content(
            model='gemini-3.6-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=256,
                temperature=0.1
            )
        )
        
        raw_output = response.text.strip()
        # 마크다운 백틱 제거
        if raw_output.startswith("```"):
            raw_output = raw_output.split("```")[1]
            if raw_output.startswith("json"):
                raw_output = raw_output[4:]
        raw_output = raw_output.strip()

        event_data = json.loads(raw_output)

        summary = event_data.get("summary", "새 일정")
        start_iso = event_data.get("start_time_iso")
        end_iso = event_data.get("end_time_iso")
        description = event_data.get("description", "")
        location = event_data.get("location", "")

        if not start_iso or not end_iso:
            return False, "⚠️ 일정 날짜/시간 파싱에 실패했습니다."

        # 구글 캘린더 생성 호출
        success, result = create_event(
            summary=summary,
            start_time_iso=start_iso,
            end_time_iso=end_iso,
            description=description,
            location=location
        )

        if success:
            start_dt = datetime.fromisoformat(start_iso).strftime("%Y년 %m월 %d일 %H:%M")
            end_dt = datetime.fromisoformat(end_iso).strftime("%H:%M")
            link = result.get('htmlLink', '')
            
            confirm_msg = (
                f"📅 **[구글 캘린더 일정 등록 완료]**\n\n"
                f"• **일정 제목**: `{summary}`\n"
                f"• **일시**: {start_dt} ~ {end_dt}\n"
                f"{f'• **장소**: {location}\n' if location else ''}"
                f"{f'• **메모**: {description}\n' if description else ''}"
                f"\n🫡 구글 캘린더에 성공적으로 등록되었습니다!"
            )
            return True, confirm_msg
        else:
            return False, f"⚠️ 캘린더 등록 실패: {result}"

    except Exception as e:
        logger.error(f"Gemini 일정 파싱 및 등록 중 오류 발생: {e}")
        return False, f"⚠️ 일정 파싱 중 오류가 발생했습니다: {e}"

def delete_event(event_id: str, calendar_id: str = 'primary'):
    """
    Google Calendar 일정 삭제
    """
    service = get_calendar_service()
    if not service:
        return False, "⚠️ Google Calendar 인증 정보(credentials.json)가 설정되지 않았습니다."

    try:
        service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
        logger.info(f"구글 캘린더 일정 삭제 성공 (Event ID: {event_id})")
        return True, "삭제 성공"
    except HttpError as error:
        logger.error(f"Google Calendar 일정 삭제 실패: {error}")
        return False, f"API 오류: {error}"
    except Exception as e:
        logger.error(f"일정 삭제 중 예외 발생: {e}")
        return False, str(e)

def delete_event_with_gemini(user_text: str):
    """
    Gemini 모델을 이용해 대표님의 자연어 지시("내일 3시 일정 삭제", "내일 대표님 전략 수석 미팅 삭제" 등)로부터
    삭제 대상 일자 및 검색 키워드를 파싱하고, 구글 캘린더에서 검색하여 해당 일정을 완전히 삭제합니다.
    """
    service = get_calendar_service()
    if not service:
        return False, "⚠️ Google Calendar 인증 정보(credentials.json)가 설정되지 않았습니다."

    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not gemini_key:
        return False, "⚠️ GEMINI_API_KEY가 설정되어 있지 않아 일정 자동 파싱을 수행할 수 없습니다."

    now = datetime.now(KST)
    current_time_str = now.strftime("%Y-%m-%d %H:%M:%S (%A, KST)")

    prompt = f"""
당신은 대표님의 구글 캘린더 일정 삭제 요청을 분석하여 대상 일자와 검색 키워드를 추출하는 AI 어시스턴트입니다.
현재 시각: {current_time_str} (타임존: Asia/Seoul, +09:00)

대표님의 일정 삭제 요청 메시지:
"{user_text}"

위 메시지를 분석하여 삭제 대상 일자(target_date: YYYY-MM-DD)와 제목/장소/시간 키워드(keywords: 문자열 배열)를 JSON으로 추출하세요.
설명이나 백틱 없이 순수 JSON으로만 응답하세요.

JSON 포맷:
{{
  "target_date": "YYYY-MM-DD",
  "keywords": ["키워드1", "키워드2"]
}}

참고사항:
1. '내일', '모레', '오늘' 등을 현재 시각({current_time_str}) 기준 YYYY-MM-DD 날짜로 정밀 계산하세요.
2. keywords에는 "전략 수석", "미팅", "15:00", "3시" 등 제목이나 시각을 특정할 수 있는 단어를 포함하세요.
"""

    try:
        client = genai.Client(api_key=gemini_key)
        from google.genai import types
        response = client.models.generate_content(
            model='gemini-3.6-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=256,
                temperature=0.1
            )
        )

        raw_output = response.text.strip()
        if raw_output.startswith("```"):
            raw_output = raw_output.split("```")[1]
            if raw_output.startswith("json"):
                raw_output = raw_output[4:]
        raw_output = raw_output.strip()

        parse_data = json.loads(raw_output)
        target_date_str = parse_data.get("target_date")
        keywords = parse_data.get("keywords", [])

        if not target_date_str:
            if "내일" in user_text:
                target_date_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")
            else:
                target_date_str = now.strftime("%Y-%m-%d")

        try:
            target_dt = datetime.strptime(target_date_str, "%Y-%m-%d")
        except Exception:
            target_dt = now + timedelta(days=1)
            target_date_str = target_dt.strftime("%Y-%m-%d")

        start_of_day = datetime(target_dt.year, target_dt.month, target_dt.day, 0, 0, 0, tzinfo=KST)
        end_of_day = datetime(target_dt.year, target_dt.month, target_dt.day, 23, 59, 59, tzinfo=KST)

        events = list_events(time_min=start_of_day.isoformat(), time_max=end_of_day.isoformat(), max_results=20)

        if not events:
            return False, f"⚠️ {target_date_str} 일자에 등록된 캘린더 일정이 없습니다."

        target_event = None
        if len(events) == 1:
            target_event = events[0]
        else:
            for event in events:
                summary = event.get('summary', '')
                location = event.get('location', '')
                start_info = event.get('start', {})
                start_val = start_info.get('dateTime') or start_info.get('date') or ''

                match_count = sum(1 for kw in keywords if kw in summary or kw in location or kw in start_val or kw in user_text)
                if match_count > 0:
                    target_event = event
                    break

            if not target_event:
                target_event = events[0]

        event_id = target_event.get('id')
        summary = target_event.get('summary', '(제목 없음)')
        start_info = target_event.get('start', {})
        start_val = start_info.get('dateTime') or start_info.get('date') or ''

        if 'T' in start_val:
            try:
                dt = datetime.fromisoformat(start_val)
                time_str = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                time_str = f"{target_date_str} {start_val[11:16]}"
        else:
            time_str = f"{target_date_str} 종일"

        del_success, del_msg = delete_event(event_id)
        if del_success:
            confirm_msg = f"🗑️ **[일정 삭제 완료]** {time_str} '{summary}' 일정이 구글 캘린더에서 정상 삭제되었습니다."
            logger.info(confirm_msg)
            return True, confirm_msg
        else:
            return False, f"⚠️ 캘린더 일정 삭제 실패: {del_msg}"

    except Exception as e:
        logger.error(f"Gemini 일정 삭제 처리 중 오류 발생: {e}")
        return False, f"⚠️ 일정 삭제 처리 중 오류가 발생했습니다: {e}"

def update_calendar_event(target_date_str: str, old_title_keyword: str, new_title: str = None, new_time_iso: str = None, calendar_id: str = 'primary'):
    """
    Google Calendar 일정 수정 (Patch)
    - target_date_str: YYYY-MM-DD
    - old_title_keyword: 기존 일정 검색 키워드
    - new_title: 변경할 새 일정 제목
    - new_time_iso: 변경할 시작 시각 (ISO 포맷)
    """
    service = get_calendar_service()
    if not service:
        return False, "⚠️ Google Calendar 인증 정보가 설정되지 않았습니다."

    try:
        dt = datetime.strptime(target_date_str, "%Y-%m-%d")
    except Exception:
        dt = datetime.now(KST) + timedelta(days=1)
        target_date_str = dt.strftime("%Y-%m-%d")

    start_of_day = datetime(dt.year, dt.month, dt.day, 0, 0, 0, tzinfo=KST)
    end_of_day = datetime(dt.year, dt.month, dt.day, 23, 59, 59, tzinfo=KST)

    events = list_events(time_min=start_of_day.isoformat(), time_max=end_of_day.isoformat(), max_results=20)
    if not events:
        return False, f"⚠️ {target_date_str} 일자에 등록된 캘린더 일정이 없습니다."

    target_event = None
    if len(events) == 1:
        target_event = events[0]
    else:
        for event in events:
            summary = event.get('summary', '')
            if old_title_keyword and old_title_keyword.replace(" ", "") in summary.replace(" ", ""):
                target_event = event
                break
        if not target_event:
            target_event = events[0]

    event_id = target_event.get('id')
    old_summary = target_event.get('summary', '(제목 없음)')
    start_info = target_event.get('start', {})
    start_val = start_info.get('dateTime') or start_info.get('date') or ''

    if 'T' in start_val:
        try:
            time_str = datetime.fromisoformat(start_val).strftime("%H:%M")
        except Exception:
            time_str = start_val[11:16]
    else:
        time_str = "종일"

    patch_body = {}
    if new_title:
        patch_body['summary'] = new_title

    if new_time_iso:
        patch_body['start'] = {'dateTime': new_time_iso, 'timeZone': 'Asia/Seoul'}

    if not patch_body:
        return False, "⚠️ 변경할 일정 정보가 제공되지 않았습니다."

    try:
        updated_event = service.events().patch(calendarId=calendar_id, eventId=event_id, body=patch_body).execute()
        updated_title = updated_event.get('summary', new_title or old_summary)
        
        confirm_msg = f"✅ **[일정 수정 완료]** {target_date_str} {time_str} '{old_summary}' ➔ '{updated_title}'로 수정 완료되었습니다."
        logger.info(confirm_msg)
        return True, confirm_msg
    except HttpError as error:
        logger.error(f"Google Calendar 일정 Patch 실패: {error}")
        return False, f"API 오류: {error}"
    except Exception as e:
        logger.error(f"일정 수정 중 예외 발생: {e}")
        return False, str(e)

def update_event_with_gemini(user_text: str):
    """
    Gemini 모델을 이용해 대표님의 자연어 수정 지시("내일 4시 민성 수영 강자를 민성수영강좌로 바꿔줘")에서
    대상 날짜, 기존 키워드, 변경할 새 제목을 파싱한 후 Google Calendar Patch API를 호출합니다.
    """
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not gemini_key:
        return False, "⚠️ GEMINI_API_KEY가 설정되어 있지 않아 일정 자동 파싱을 수행할 수 없습니다."

    now = datetime.now(KST)
    current_time_str = now.strftime("%Y-%m-%d %H:%M:%S (%A, KST)")

    prompt = f"""
당신은 대표님의 구글 캘린더 일정 수정 요청을 분석하여 파라미터를 추출하는 AI 어시스턴트입니다.
현재 시각: {current_time_str} (타임존: Asia/Seoul, +09:00)

대표님의 일정 수정 요청 메시지:
"{user_text}"

위 메시지를 분석하여 다음 JSON 형식으로만 응답하세요. 설명이나 마크다운 백틱 없이 순수 JSON만 출력하세요.

JSON 형식:
{{
  "target_date": "YYYY-MM-DD",
  "old_title_keyword": "기존 일정 제목 또는 키워드",
  "new_title": "변경할 새 일정 제목"
}}

참고사항:
1. '내일', '모레', '오늘' 등을 현재 시각({current_time_str}) 기준 YYYY-MM-DD 포맷으로 변환하세요.
2. 예: "민성 수영 강자를 민성수영강좌로 바꿔줘" -> old_title_keyword: "민성 수영 강자", new_title: "민성수영강좌"
"""

    try:
        client = genai.Client(api_key=gemini_key)
        from google.genai import types
        response = client.models.generate_content(
            model='gemini-3.6-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=256,
                temperature=0.1
            )
        )

        raw_output = response.text.strip()
        if raw_output.startswith("```"):
            raw_output = raw_output.split("```")[1]
            if raw_output.startswith("json"):
                raw_output = raw_output[4:]
        raw_output = raw_output.strip()

        data = json.loads(raw_output)
        target_date = data.get("target_date")
        old_title_keyword = data.get("old_title_keyword", "")
        new_title = data.get("new_title", "")

        if not target_date:
            if "내일" in user_text:
                target_date = (now + timedelta(days=1)).strftime("%Y-%m-%d")
            else:
                target_date = now.strftime("%Y-%m-%d")

        return update_calendar_event(
            target_date_str=target_date,
            old_title_keyword=old_title_keyword,
            new_title=new_title
        )

    except Exception as e:
        logger.error(f"Gemini 일정 수정 파싱 오류: {e}")
        return False, f"⚠️ 일정 수정 중 오류가 발생했습니다: {e}"

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("=== Google Calendar Manager Standalone Test ===")
    print(get_today_events_summary())
    print("\n" + get_specific_day_events_summary(1, "내일"))
    print("\n" + get_week_events_summary())


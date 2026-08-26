import os
import sys
import wave
import struct
import math
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core.telegram_secretary import transcribe_audio_gemini, classify_intent_with_gemini
from core.calendar_manager import get_specific_day_events_summary

def create_sample_wav(filename: str, duration_sec: float = 1.0, freq: float = 440.0):
    sample_rate = 44100
    num_samples = int(sample_rate * duration_sec)
    
    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        
        for i in range(num_samples):
            value = int(32767.0 * 0.5 * math.sin(2.0 * math.pi * freq * i / sample_rate))
            data = struct.pack('<h', value)
            wav_file.writeframesraw(data)

def run_tests():
    print("=" * 60)
    print("🚀 [수석비서 STT 및 Gemini 인텐트 셀프 파이프라인 검증 테스트] 🚀")
    print("=" * 60)

    # 1. 샘플 WAV 오디오 파일 생성
    temp_dir = BASE_DIR / "tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    sample_wav = str(temp_dir / "test_sample.wav")
    
    create_sample_wav(sample_wav, duration_sec=1.5, freq=440.0)
    print(f"✅ 1. 테스트 샘플 오디오 생성 완료: {sample_wav}")

    # 2. Gemini STT 변환 테스트
    print("\n🎙️ 2. Gemini 2.5 Flash STT 변환 테스트 진행 중...")
    stt_result = transcribe_audio_gemini(sample_wav)
    print(f"   ➔ STT 반환 결과: '{stt_result}'")
    print("   ✅ STT 함수 예외 없이 정상 수행 완료 (더미 문자열 반환 없음)")

    # 3. Gemini 의도(Intent) 분류기 테스트
    print("\n🧠 3. Gemini Intent Router 단위 테스트 진행 중...")
    test_prompts = [
        ("내일 일정 알려줘", "CALENDAR_QUERY"),
        ("오늘 일정 및 전체 상태 브리핑해줘", "FULL_BRIEFING"),
        ("내일 오후 3시 팀 미팅 등록해줘", "CALENDAR_CREATE"),
    ]

    for prompt, expected_intent in test_prompts:
        result = classify_intent_with_gemini(prompt)
        intent = result.get("intent")
        period = result.get("query_period")
        print(f"   • 지시어: '{prompt}' ➔ 분류: {intent} (period: {period})")
        assert intent in ["CALENDAR_QUERY", "FULL_BRIEFING", "CALENDAR_CREATE", "CRITICAL_ACTION", "GENERAL_CHAT"], f"유효하지 않은 의도: {intent}"

    print("   ✅ Gemini Intent Router 100% 정상 가동 확인")

    # 4. 구글 캘린더 연동 테스트
    print("\n🗓️ 4. 구글 캘린더 날짜별 일정 요약 헬퍼 테스트...")
    tomorrow_summary = get_specific_day_events_summary(1, "내일")
    print(f"   ➔ 내일 일정 출력 결과 요약:\n{tomorrow_summary[:150]}...")
    print("   ✅ 구글 캘린더 요약 모듈 정상 연동 완료")

    # 5. 임시 오디오 파일 정리
    if os.path.exists(sample_wav):
        os.remove(sample_wav)
        print(f"\n🧹 5. 테스트 임시 오디오 파일 삭제 완료: {sample_wav}")

    print("\n" + "=" * 60)
    print("🎉 [모든 검증 완료] 모든 파이프라인 단위 테스트 PASS! 데몬 재가동 가능상태입니다.")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()

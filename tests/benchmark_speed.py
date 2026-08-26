import sys
import time
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path("c:/agent-workspace")))

from core.telegram_secretary import (
    classify_intent_with_gemini,
    generate_gemini_general_reply,
    collect_realtime_metrics,
    generate_gemini_briefing,
)
from core.calendar_manager import get_specific_day_events_summary, parse_and_create_event_with_gemini

async def run_benchmark():
    print("=" * 60)
    print("🚀 [Telegram Secretary Speed Benchmark Test]")
    print("=" * 60)

    # 1. Intent Classification Speed
    t0 = time.perf_counter()
    intent = await asyncio.to_thread(classify_intent_with_gemini, "내일 일정 알려줘")
    t1 = time.perf_counter()
    intent_dur = t1 - t0
    print(f"1. Intent Classification Latency: {intent_dur:.3f}s (Result: {intent.get('intent')})")

    # 2. Calendar Query Speed
    t0 = time.perf_counter()
    cal_summary = await asyncio.to_thread(get_specific_day_events_summary, 1, "내일")
    t1 = time.perf_counter()
    cal_dur = t1 - t0
    print(f"2. Google Calendar Query Latency: {cal_dur:.3f}s")

    # 3. General Reply Generation Speed
    t0 = time.perf_counter()
    reply = await asyncio.to_thread(generate_gemini_general_reply, "오늘 비 오려나? 날씨 어때?")
    t1 = time.perf_counter()
    reply_dur = t1 - t0
    print(f"3. Gemini General Reply Latency: {reply_dur:.3f}s")

    # 4. Metrics Collection & Briefing Generation Speed
    t0 = time.perf_counter()
    metrics = await asyncio.to_thread(collect_realtime_metrics)
    t1 = time.perf_counter()
    metrics_dur = t1 - t0
    print(f"4-a. Shallow Metrics Collection Latency: {metrics_dur:.3f}s")

    t0 = time.perf_counter()
    briefing = await asyncio.to_thread(generate_gemini_briefing, metrics)
    t1 = time.perf_counter()
    briefing_dur = t1 - t0
    print(f"4-b. Gemini Briefing Generation Latency: {briefing_dur:.3f}s")

    total_pipeline_time = intent_dur + cal_dur
    print("-" * 60)
    print(f"⚡ End-to-End Voice Calendar Query Total Time: {total_pipeline_time:.3f} seconds")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(run_benchmark())

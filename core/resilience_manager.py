"""
Enterprise Unified Resilience Middleware (core/resilience_manager.py)
Centralizes API Rate-limit Exponential Backoff, 15s Tool Execution Timeouts, and Error Sanitization.
"""

import os
import sys
import json
import logging
import asyncio
import functools
import time
from typing import Callable, Any

logger = logging.getLogger(__name__)

FALLBACK_ERROR_MESSAGE = "⚠️ 현재 AI 서버 요청이 집중되어 잠시 대기 중입니다. 5초 뒤 다시 브리핑하겠습니다."


def sanitize_user_facing_error(error_input: Any) -> str:
    """
    대표님께 시스템 raw error JSON, API 키, Traceback이 절대 노출되지 않도록
    정제된 한국어 비서 메시지로 변환합니다.
    """
    err_str = str(error_input)
    if not err_str:
        return FALLBACK_ERROR_MESSAGE

    if any(kw in err_str for kw in ["429", "RESOURCE_EXHAUSTED", "Quota exceeded", "RateLimit"]):
        return FALLBACK_ERROR_MESSAGE
    
    if any(kw in err_str.lower() for kw in ["connect", "timeout", "network", "httpx"]):
        return "⚠️ 네트워크 연결 상태가 불안정하여 잠시 후 재시도하겠습니다."

    # General error masking
    return f"⚠️ [시스템 안정화 알림] 작업 처리 중 일시적 지연이 발생했습니다 ({err_str[:60]}). 다시 시도해 주십시오."


import re

STT_FALLBACK_MESSAGE = "⚠️ 현재 음성 처리 서버 요청이 집중되어 지연되고 있습니다. 10초 뒤 다시 말씀해 주시면 즉시 처리하겠습니다."


def safe_gemini_call(
    max_retries: int = 3,
    initial_delay: float = 17.0,
    backoff_factor: float = 1.2,
    custom_fallback: str = None
):
    """
    Gemini API 호출 통합 데코레이터 / 래퍼:
    - 429 RESOURCE_EXHAUSTED 발생 시 에러 메시지의 'retry in XXs' 파싱 또는 최소 initial_delay(기본 17초) 이상 자동 대기 후 재시도
    - max_retries회 연속 실패 시 custom_fallback 또는 정제된 한국어 비서 메시지 반환
    """
    def parse_retry_delay(err_str: str, default_delay: float) -> float:
        match = re.search(r'retry in (\d+(?:\.\d+)?)s', err_str, re.IGNORECASE)
        if match:
            try:
                parsed_s = float(match.group(1)) + 1.0  # 1s safety margin
                return max(parsed_s, default_delay)
            except ValueError:
                pass
        return default_delay

    fallback_msg = custom_fallback or FALLBACK_ERROR_MESSAGE

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            delay = initial_delay
            for attempt in range(1, max_retries + 1):
                try:
                    if asyncio.iscoroutinefunction(func):
                        res = await func(*args, **kwargs)
                    else:
                        res = await asyncio.to_thread(func, *args, **kwargs)
                    return res
                except Exception as e:
                    err_str = str(e)
                    is_rate_limit = any(kw in err_str for kw in ["429", "RESOURCE_EXHAUSTED", "Quota exceeded", "RateLimit"])
                    is_net_err = any(kw in err_str.lower() for kw in ["timeout", "connect", "connection", "http"])

                    if (is_rate_limit or is_net_err) and attempt < max_retries:
                        calculated_delay = parse_retry_delay(err_str, delay)
                        logger.warning(
                            f"⚠️ [safe_gemini_call] API Request Notice (Attempt {attempt}/{max_retries}). "
                            f"Sleeping for {calculated_delay:.1f}s before retry... Error: {err_str[:90]}"
                        )
                        await asyncio.sleep(calculated_delay)
                        delay = calculated_delay * backoff_factor
                    else:
                        logger.error(f"❌ [safe_gemini_call] Execution failed after attempt {attempt}: {e}")
                        if attempt >= max_retries:
                            break

            return fallback_msg

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            delay = initial_delay
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    err_str = str(e)
                    is_rate_limit = any(kw in err_str for kw in ["429", "RESOURCE_EXHAUSTED", "Quota exceeded", "RateLimit"])
                    is_net_err = any(kw in err_str.lower() for kw in ["timeout", "connect", "connection", "http"])

                    if (is_rate_limit or is_net_err) and attempt < max_retries:
                        calculated_delay = parse_retry_delay(err_str, delay)
                        logger.warning(
                            f"⚠️ [safe_gemini_call] Sync API Request Notice (Attempt {attempt}/{max_retries}). "
                            f"Sleeping for {calculated_delay:.1f}s before retry... Error: {err_str[:90]}"
                        )
                        time.sleep(calculated_delay)
                        delay = calculated_delay * backoff_factor
                    else:
                        logger.error(f"❌ [safe_gemini_call] Sync execution failed after attempt {attempt}: {e}")
                        if attempt >= max_retries:
                            break

            return fallback_msg

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def tool_timeout_guard(seconds: float = 15.0):
    """
    외부 도구 비동기 15초 제한 데코레이터
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await asyncio.wait_for(func(*args, **kwargs), timeout=seconds)
                else:
                    return await asyncio.wait_for(asyncio.to_thread(func, *args, **kwargs), timeout=seconds)
            except asyncio.TimeoutError:
                func_name = getattr(func, '__name__', 'tool')
                logger.warning(f"⏰ [tool_timeout_guard] Tool '{func_name}' exceeded {seconds}s timeout.")
                return f"⚠️ [도구 실행 {int(seconds)}초 타임아웃] {func_name} 실행이 제한시간({int(seconds)}초)을 초과하여 대기 없이 즉시 LLM 대화형 브리핑으로 전환합니다."
            except Exception as e:
                func_name = getattr(func, '__name__', 'tool')
                logger.error(f"❌ [tool_timeout_guard] Tool '{func_name}' exception: {e}")
                return f"⚠️ [도구 실행 오류] {func_name} 실행 실패 ({e}). LLM 대화형 브리핑으로 전환합니다."
        return wrapper
    return decorator


async def execute_tool_with_resilience(fn: Callable, fn_args: dict, timeout_seconds: float = 15.0) -> str:
    """
    도구 실행을 resilience 가드로 안전 실행하고 결과를 문자열로 정제하는 비동기 헬퍼
    """
    try:
        if asyncio.iscoroutinefunction(fn):
            res = await asyncio.wait_for(fn(**fn_args), timeout=timeout_seconds)
        else:
            res = await asyncio.wait_for(asyncio.to_thread(fn, **fn_args), timeout=timeout_seconds)

        if isinstance(res, dict):
            return json.dumps(res, ensure_ascii=False)
        return str(res)
    except asyncio.TimeoutError:
        func_name = getattr(fn, '__name__', 'tool')
        logger.warning(f"⏰ [execute_tool_with_resilience] Tool '{func_name}' timed out after {timeout_seconds}s.")
        return f"⚠️ [도구 실행 {int(timeout_seconds)}초 타임아웃] {func_name} 도구 실행이 15초를 초과하여 대기 없이 즉시 LLM 자체 지식을 활용한 대화형 브리핑으로 전환합니다."
    except Exception as e:
        func_name = getattr(fn, '__name__', 'tool')
        logger.error(f"❌ [execute_tool_with_resilience] Tool '{func_name}' exception: {e}")
        return f"⚠️ [도구 실행 오류] {func_name} 실행 중 예외가 발생했습니다 ({e}). LLM 대화형 브리핑으로 전환합니다."

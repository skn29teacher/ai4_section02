import hashlib
import time
from datetime import datetime, timezone
from langchain_core.output_parsers import StrOutputParser
from app.prompts import get_prompt
from app.pipeline import load_policy
from app.providers import friendly_error


def fingerprint(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def observations(text):
    # 단순 관측값이다. 사실성·정책 준수·인사 유무의 의미 판정이 아니다.
    return {"characters": len(text), "within_500_chars": len(text) <= 500,
            "mentions_7_days_literal": "7일" in text,
            "nonempty": bool(text.strip())}


def compare_versions(model, settings, cases, repeats=1):
    if type(repeats) is not int or not 1 <= repeats <= 3:
        raise ValueError("repeats는 1~3이어야 합니다.")
    records = []
    context = load_policy()
    for repeat in range(repeats):
        # 순서 영향을 줄이기 위해 반복마다 버전 순서를 순환한다.
        versions = ["weak", "role", "designed"]
        versions = versions[repeat:] + versions[:repeat]
        for case in cases:
            for version in versions:
                prompt = get_prompt(version)
                inputs = {"context": context, "inquiry": case["inquiry"]}
                rendered = prompt.invoke(inputs)
                started = time.perf_counter()
                record = {"case_id": case["id"], "version": version,
                          "repeat": repeat + 1, "provider": settings.provider,
                          "model": settings.model, "temperature": settings.temperature,
                          "max_output": settings.max_output,
                          "checked_at": datetime.now(timezone.utc).isoformat(),
                          "context_hash": fingerprint(context),
                          "inquiry_hash": fingerprint(case["inquiry"]),
                          "prompt_hash": fingerprint(rendered.to_string()),
                          "mode": "mocked" if settings.provider == "mock" else "remote"}
                try:
                    # AIMessage를 받는 지점에서 사용량을 기록한 뒤 텍스트를 추출한다.
                    message = (prompt | model).invoke(inputs)
                    text = StrOutputParser().invoke(message)
                    record.update(status="ok", output=text,
                                  usage=message.usage_metadata,
                                  observations=observations(text))
                except Exception as error:
                    record.update(status="error", error=friendly_error(error))
                record["elapsed_seconds"] = round(time.perf_counter() - started, 4)
                records.append(record)
                if record.get("error", "").startswith("호출/토큰/크레딧"):
                    return records  # 429에서 추가 호출을 중단한다.
    return records

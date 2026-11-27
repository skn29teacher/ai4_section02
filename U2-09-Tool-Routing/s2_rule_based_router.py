# 규칙기반 사전필터 & 보안/긴급 분기
# LLM 라우터 앞에 규칙기반 라우터를 위치
    # 속도와 비용:정규식, 사용자 메타데이터,명백한 인젝션 패턴은 LLM을 부르지 않고 즉시 분기
    # 보안 통제 : 프롬프트 인젝션 시그니처가 감지되면 LLM 판단전에 SECURITY_BLOCK 경로로 격리
from langchain_core.runnables import RunnableBranch, RunnableLambda,RunnablePassthrough
INJECTION_PATTERNS = [
    # 이전 지시를 무시하거나 따르지 말라는 명령    
        r"(?:이전|기존|앞선|모든)\s*(?:규칙|지시(?:사항)?|지침|명령)",
        r"\s*(?:을|를|은|는)?\s*(?:(?:모두|전부)\s*)?",
        r"(?:무시\s*(?:하고|해(?:\s*(?:줘|주세요))?|하라|하세요)",
        r"|잊어(?:\s*버려)?|따르지\s*마(?:세요)?|무시(?=\s*[.!?]*\s*$))\b",    
    # 시스템 또는 개발자 프롬프트를 공개하라는 명령    
        r"(?:시스템|개발자|내부)\s*(?:프롬프트|메시지|지시사항)",
        r"\s*(?:을|를|은|는)?\s*(?:(?:그대로|모두|전부)\s*)?",
        r"(?:(?:출력|공개)\s*(?:해(?:\s*(?:줘|주세요))?|하라|하세요)",
        r"|(?:보여|알려)\s*(?:줘(?:요)?|주세요|주라))\b",    
    # 영어로 이전 지시를 무시하라는 명령    
        r"(?i)(?<!\bdo\snot\s)(?<!\bdon['’]t\s)(?<!\bnever\s)",
        r"\b(?:ignore|disregard|forget|override|do\s+not\s+follow)\s+",
        r"(?:(?:all|the|your|any)\s+)*",
        r"(?:(?:previous|prior|earlier|above|existing|original)\s+(?:instructions?|rules?|guidelines?|directives?)",
        r"|(?:instructions?|rules?|guidelines?|directives?)\s+(?:above|given\s+earlier))\b",    
    # 영어로 시스템 또는 개발자 프롬프트를 공개하라는 명령    
        r"(?i)(?<!\bdo\snot\s)(?<!\bdon['’]t\s)(?<!\bnever\s)",
        r"\b(?:(?:show|tell|give)\s+me|reveal|print|display|output|disclose|repeat|share)\s+",
        r"(?:(?:the|your|full|entire|original|current|hidden)\s+)*",
        r"(?:system|developer|internal)[\s-]+(?:prompts?|messages?|instructions?)\b",
]

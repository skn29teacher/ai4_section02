from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda, RunnablePassthrough

SYSTEM = (
    '당신은 사내 안내문 작성자입니다. 제공된 사실만 사용하세요. '
    '날짜·장소가 없으면 확인 필요라고 표시하세요. '
    '제목:, 핵심:, 행동: 세 항목으로 한국어 안내문을 작성하세요.'
)

def make_prompt():
    return ChatPromptTemplate.from_messages([
        ('system', SYSTEM),
        ('human', '독자: {audience}\n어조: {tone}\n사실: {notice}'),
    ])

def validate_input(data):
    if not isinstance(data, dict):
        raise TypeError('입력은 dict여야 합니다.')
    result = {}
    for key, limit in [('audience', 80), ('tone', 80), ('notice', 1200)]:
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(key + ': 비어 있지 않은 문자열이 필요합니다.')
        if len(value) > limit:
            raise ValueError(key + ': 길이 제한 초과')
        result[key] = value.strip()
    return result

def build_chain(model):
    return RunnableLambda(validate_input) | make_prompt() | model | StrOutputParser()

def build_review_chain(model):
    draft = build_chain(model)
    review_prompt = ChatPromptTemplate.from_messages([
        ('system', '원문과 초안을 비교해 원문에 없는 사실이나 빠진 행동을 2줄 이내로 지적하세요. 없으면 추가 확인 없음이라고 답하세요.'),
        ('human', '원문: {notice}\n초안: {draft}'),
    ])
    # assign은 원래 dict를 유지하고 새 키를 추가한다. 원문이 검토 단계에 도달한다.
    return (RunnableLambda(validate_input)
            | RunnablePassthrough.assign(draft=draft)
            | RunnablePassthrough.assign(review=review_prompt | model | StrOutputParser()))

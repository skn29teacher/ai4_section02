"""결과 객체 저장과 안전한 다중 행 HTML 표시."""
import json
from html import escape
from datetime import datetime
from app.core import ROOT, SOURCE

STYLE = '''body{font-family:"Noto Sans CJK KR","Malgun Gothic",sans-serif;max-width:1050px;
margin:36px auto;padding:0 24px;color:#1c2940;line-height:1.75;background:#f4f7fb}
header,article{background:white;padding:24px;margin:18px 0;border-radius:12px;border:1px solid #dce3ed}
h1{font-size:26px}h2{font-size:20px}h3{font-size:16px;color:#176e78}
.result-text{white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.7}
.badge{background:#def3ed;padding:5px 10px;border-radius:6px}
@media print{body{margin:0;background:white;font-size:10pt}article{break-inside:auto}
.result-text{white-space:pre-wrap;overflow:visible;max-height:none}}'''


def text_block(label, value):
    return f'<h3>{escape(label)}</h3><div class="result-text">{escape(str(value))}</div>'


def save_report(session, results):
    folder = ROOT / 'results'
    folder.mkdir(exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    stem = folder / f's{session:02}_{stamp}'
    stem.with_suffix('.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    cards = []
    for item in results:
        row = item['record']
        body = text_block('제공 데이터 위치', f'D04 · openai/gsm8k · config=main · split=test\n원본 행={row["row_index"]} (0부터) · 수업용 ID={row["id"]}\n원본 필드=question, answer; 수업용 ID는 파생값')
        body += text_block('원본 question', row['question'])
        body += text_block('방식 / 실행 모드', f'{item["strategy"]} / {item["mode"]}\n공급자={item["provider"]} · 모델={item["model"]} · 상태={item["status"]}')
        body += text_block('처리 결과', item['text'])
        for event in item.get('events', []):
            body += text_block(f'{event["turn"]}회 · {event["kind"]}', event['text'])
        body += text_block('정답 대조 (모델 입력에는 제외)', f'예측={item.get("predicted")} · 원본 정답={item.get("expected")} · 일치={item.get("correct")}')
        if item.get('metrics'):
            body += text_block('실측 API 사용량', json.dumps(item['metrics'], ensure_ascii=False, indent=2))
        # GSM8K answer는 이 표본에서 literal \n을 사용한다. 이 필드의 표시만 복원한다.
        body += text_block('원본 answer (표시용 개행 복원)', row['answer'].replace('\\n', '\n'))
        cards.append('<article>' + body + '</article>')
    comparable = [x for x in results if x['strategy'] != 'local']
    matched = sum(x.get('correct') is True for x in comparable)
    parsed = sum(x.get('predicted') is not None for x in comparable)
    summary = f'비교 항목 {len(comparable)}건 · 숫자 파싱 {parsed}건 · 정답 일치 {matched}건' if comparable else '로컬 구조 실습 · 모델 성능 비교 없음'
    html = f'''<!doctype html><html lang="ko"><meta charset="utf-8"><title>U2-02 실습 결과</title>
<style>{STYLE}</style><header><h1>2026-11-18 · CoT·ReAct 실습 결과</h1>
<p>제공 데이터: D04 GSM8K · <a href="{SOURCE}">{SOURCE}</a></p>
<p>{summary}</p><p>모의 대본의 정답 일치 수는 모델 성능 지표가 아닙니다. 소표본 결과를 GSM8K 전체 점수로 일반화하지 않습니다.</p>
<p>model=공개 응답 / tool=실제 로컬 계산 / mock=교사 작성 대본. 공개 풀이를 내부 사고 기록으로 해석하지 않습니다.</p></header>{''.join(cards)}</html>'''
    stem.with_suffix('.html').write_text(html, encoding='utf-8')
    return stem.with_suffix('.html')

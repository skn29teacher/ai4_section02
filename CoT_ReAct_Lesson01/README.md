# 1차시 · 같은 문제를 두 가지 프롬프트로 풀기

수업은 lesson.html 또는 lesson.pdf에서 시작한다. lesson.py를 열어 두 프롬프트를 작성하고 계산 결과가 다음 요청에 전달되는 과정을 살펴본다.

압축을 풀고 이 파일이 있는 폴더에서 실행한다. Python 3.11 이상을 사용한다.

Windows PowerShell
```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe lesson.py
```

macOS / Linux
```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python lesson.py
```

API 실습은 .env.example을 .env로 복사하고 선택한 공급자의 API_KEY와 MODEL을 채운다. 위 실행 명령 끝에 --provider groq, --provider gemini 또는 --provider openai 중 하나를 붙인다. Groq·Gemini는 수업 계정에서 무료 한도가 확인된 모델을 사용한다. OpenAI는 유료 선택 실습이다.

실행 기록은 results/에 저장된다. HTML을 브라우저로 열고 인쇄 메뉴에서 PDF로 저장할 수 있다.

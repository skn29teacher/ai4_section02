import json
import tempfile
import unittest
from pathlib import Path

from lesson import MAX_REACT_TURNS, REACT, calculate, prompt, react
from s02 import records
from s06 import answer_numbers, compare
from s08 import report


class ScriptedRemote:
    model = "test-model"

    def __init__(self, replies):
        self.replies = iter(replies)
        self.calls = 0

    def __call__(self, messages):
        self.calls += 1
        return next(self.replies)


class CompareTests(unittest.TestCase):
    def test_extracts_multiple_values_from_final_answer(self):
        answer = (
            "계산 설명\n최종 정답:\n"
            "- 판매 수익: \\boxed{108 \\text{달러}}\n"
            "- 판매하지 않은 달걀: 12개"
        )
        self.assertEqual(answer_numbers(answer), [108.0, 12.0])
        self.assertEqual(answer_numbers("답: 수익 108달러, 남은 달걀 24개"),
                         [108.0, 24.0])

    def test_extracts_value_from_natural_sentence_ending(self):
        self.assertEqual(answer_numbers("총거리는 540미터입니다."), [540.0])

    def test_percent_of_and_numeric_validation(self):
        self.assertEqual(calculate("percent_of", 60, 20), 12)
        self.assertEqual(calculate("percent_of", 48, 25), 12)
        with self.assertRaises(ValueError):
            calculate("percent_of", 60, "20")

    def test_compare_scores_each_answer_and_counts_api_requests(self):
        react_steps = [
            {"action": "multiply", "a": 12, "b": 5},
            {"action": "percent_of", "a": 60, "b": 20},
            {"action": "subtract", "a": 60, "b": 12},
            {"action": "percent_of", "a": 48, "b": 25},
            {"action": "subtract", "a": 48, "b": 12},
            {"action": "multiply", "a": 36, "b": 3},
            {"action": "add", "a": 12, "b": 12},
            {"final": "판매 수익 108달러, 판매하지 않은 달걀 24개"},
        ]
        remote = ScriptedRemote([
            "최종 정답:\n- 수익 108달러\n- 판매하지 않은 달걀 12개",
            "답: 수익 108달러, 판매하지 않은 달걀 24개",
            *[json.dumps(step, ensure_ascii=False) for step in react_steps],
        ])

        cases = compare(records()[0], remote, "openai")

        self.assertEqual([case["status"] for case in cases],
                         ["정답 불일치", "정답 일치", "정답 일치"])
        self.assertEqual([case["api_requests"] for case in cases], [1, 1, 8])
        self.assertEqual([case["tools"] for case in cases], [0, 0, 7])
        self.assertEqual(cases[1]["predicted"], [108.0, 24.0])
        self.assertEqual(remote.calls, 10)

    def test_demo_covers_both_problems_and_all_methods(self):
        cases = [
            case
            for row in records()
            for case in compare(row, None, "demo")
        ]

        self.assertEqual(len(cases), 6)
        self.assertTrue(all(case["correct"] for case in cases))
        self.assertTrue(all(case["api_requests"] == 0 for case in cases))

    def test_demo_rejects_questions_without_a_matching_fixture(self):
        changed_row = dict(records()[0])
        changed_row["question"] += " 조건이 변경되었습니다."

        cases = compare(changed_row, None, "demo")

        self.assertTrue(all(case["status"] == "실행 중단" for case in cases))
        self.assertTrue(all(case["api_requests"] == 0 for case in cases))

    def test_report_uses_normalized_answer_values_and_shows_api_count(self):
        case = {
            "row": 3,
            "method": "react",
            "provider": "openai",
            "model": "test-model",
            "status": "완료",
            "predicted": 540.0,
            "expected": "540",
            "api_requests": 3,
            "tools": 2,
            "question": "question",
            "instruction": "instruction",
            "events": [],
            "reference": "answer",
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "comparison.json"
            path.write_text(json.dumps([case]), encoding="utf-8")

            html = report(path).read_text(encoding="utf-8")

        self.assertIn("수치 일치", html)
        self.assertIn("API 요청 3회", html)
        self.assertIn("도구 실행 2회", html)

    def test_react_allows_final_answer_after_seven_tool_steps(self):
        replies = [
            {"action": "multiply", "a": 12, "b": 5},
            {"action": "percent_of", "a": 60, "b": 20},
            {"action": "subtract", "a": 60, "b": 12},
            {"action": "percent_of", "a": 48, "b": 25},
            {"action": "subtract", "a": 48, "b": 12},
            {"action": "multiply", "a": 36, "b": 3},
            {"action": "add", "a": 12, "b": 12},
            {"final": "108달러, 24개"},
        ]
        events = []
        responses = iter(json.dumps(reply, ensure_ascii=False) for reply in replies)

        react(prompt(REACT, records()[0]["question"]),
              lambda messages: next(responses), events)

        self.assertEqual(MAX_REACT_TURNS, 8)
        self.assertEqual(
            sum(label == "ReAct · 모델 응답" for label, _ in events), 8
        )
        self.assertEqual(events[-1][0], "ReAct · 모델 응답")


if __name__ == "__main__":
    unittest.main()

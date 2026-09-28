"""정답basic_3.ipynb를 실행하고 검색 평가 + RAG 답변 결과를 확인하는 스크립트."""
import nbformat
from nbconvert.preprocessors import ExecutePreprocessor

SRC, OUT = "정답basic_3.ipynb", "결과basic_3.ipynb"
nb = nbformat.read(SRC, as_version=4)
nb.cells += [
    nbformat.v4.new_markdown_cell("## 실행 확인 (run_rag.py 추가 셀)"),
    nbformat.v4.new_code_cell(
        'show_search_results(test_cases[8]["question"])\n'
        'report = evaluate_retrieval(test_cases, k=4)'
    ),
    nbformat.v4.new_code_cell(
        'for c in test_cases[:3]:\n'
        '    print("Q:", c["question"]); print("A:", ask(c["question"])); print()'
    ),
]
ExecutePreprocessor(timeout=600, kernel_name="python3").preprocess(nb, {"metadata": {"path": "."}})
nbformat.write(nb, OUT)
for cell in nb.cells[-2:]:
    for o in cell.get("outputs", []):
        print(o.get("text", ""))

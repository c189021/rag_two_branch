# rag_two_branch — 가상Tech 업무가이드 RAG 실습

가상Tech 업무가이드 PDF(9쪽)를 대상으로 RAG를 단계별로 구현하고 평가하는 실습 프로젝트입니다.
PDF 로딩 → chunk 분할 → ChromaDB 저장 → 검색 → 근거 기반 답변 → 평가 순서로 진행합니다.

## 노트북 구성

| 노트북 | 내용 |
|---|---|
| `정답basic_1.ipynb` | **RAG 기본 실행.** `PyPDFLoader`로 PDF를 읽고 `RecursiveCharacterTextSplitter`(size 500 / overlap 50)로 분할한 뒤, 메모리 Chroma에 저장해 retriever를 만듭니다. |
| `정답basic_2.ipynb` | **영속성 DB 저장.** `pypdf`로 페이지별 `Document`(page_number 메타데이터)를 만들고 `./chroma_db/basic`에 저장합니다. DB가 있으면 재사용합니다. |
| `정답basic_3.ipynb` | **완성형 RAG + 자체 평가.** 아래에서 자세히 설명합니다. |
| `tryRagas.ipynb` | **Ragas 입문.** 예제 1건("대한민국의 수도는?")으로 Ragas 0.4.3의 지표 4개(Faithfulness, AnswerRelevancy, ContextPrecisionWithReference, ContextRecall) 사용법을 익힙니다. 가상Tech RAG와는 연결돼 있지 않습니다. |

### 정답basic_3 상세

1. **로더:** 페이지별 `Document` 생성, 메타데이터에 `page_number`, `section`, `source_name` 부여.
2. **chunk:** size 800 / overlap 120, 한국어 문장 구분자 우선. `p02-c01` 형식의 `chunk_id` 부여.
3. **ChromaDB:** PDF 내용의 SHA-256 해시 앞 12자리로 DB 경로(`./chroma_db/<hash>`)를 정합니다. PDF가 그대로면 기존 DB를 로드하고, 바뀌면 새로 임베딩합니다. 컬렉션은 `virtualtech-guide`, 임베딩은 `text-embedding-3-small`, `k=4`.
4. **테스트 케이스 15개:** 질문, 정답 페이지, 핵심 키워드(anchors), 기준 답변, 정답 chunk ID.
5. **검색 평가(직접 구현):** Hit@4, MRR@4, Anchor hit rate. 합격 기준은 Hit@4 ≥ 0.90, MRR@4 ≥ 0.75.
6. **답변 생성:** `gpt-4.1-mini`(temperature 0)가 검색된 chunk만 근거로 답하고 `[근거: p02-c01]` 형태로 출처를 표시합니다. 근거가 없으면 "문서에서 확인할 수 없습니다."라고 답합니다.

> 정답basic_3의 평가는 규칙 기반 지표이며 Ragas를 사용하지 않습니다. 답변 품질(faithfulness 등)의 자동 채점은 하지 않습니다.

## 실행 결과 (정답basic_3, 2026-09-28)

| 지표 | 값 |
|---|---|
| Hit@4 | 0.933 |
| MRR@4 | 0.867 |
| Anchor hit rate | 0.933 |

답변 예시: "핵심 협업시간은?" → "평일 11:00부터 16:00까지입니다. [근거: p02-c01]"

## 환경 설정

- Python 3.12, 패키지 관리는 [uv](https://docs.astral.sh/uv/)
- OpenAI API 키가 필요합니다. 프로젝트 루트의 `.env`에 `OPENAI_API_KEY=...`를 넣거나 환경변수로 설정합니다.

```bash
uv sync                                   # .venv 생성 및 pyproject.toml/uv.lock 기준 설치
uv pip install ipykernel nbconvert nbformat   # 노트북/스크립트 실행용 (선택)
```

의존성 관리 파일:
- `pyproject.toml`, `uv.lock` — 설치 기준(권장)
- `pre-requierments.txt` — 직접 필요한 패키지 목록
- `requirements.txt` — `uv pip freeze` 결과(유지보수용). 원작성자의 로컬 경로(`-e file:///E:/...`)가 포함돼 있어 그대로 설치하지 마세요.
- `설치가이드.txt`, `import가이드.txt` — 설치 절차와 ragas import 메모

## 실행 방법

- **노트북:** VS Code나 Jupyter에서 `.venv` 커널로 `정답basic_3.ipynb`를 실행합니다.
- **스크립트:** 검색 평가와 답변 3건까지 한 번에 실행하고 `결과basic_3.ipynb`로 저장합니다.

```powershell
$env:PYTHONUTF8=1; .venv\Scripts\python run_rag.py
```

## 폴더 구조

```
data/          원본 PDF (가상Tech_업무가이드.pdf)
chroma_db/     저장된 벡터 DB (basic/, <pdf-hash>/)
src/           패키지 골격
run_rag.py     정답basic_3 실행 + 평가 결과 확인 스크립트
```

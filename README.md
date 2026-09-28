# rag_two_branch — 가상Tech 업무가이드 RAG 실습

가상Tech 업무가이드 PDF(9쪽)를 대상으로 **RAG를 단계별로 구현**하고, **검색·답변 품질을 평가**하는 실습 프로젝트입니다.

```
PDF → 페이지별 Document → chunk 분할 → 임베딩 → ChromaDB 저장
     → 질문 → 유사도 검색(top-k) → LLM 답변(+근거 chunk ID) → 평가
```

## 목차

1. [프로젝트 구성](#1-프로젝트-구성)
2. [환경 설정과 실행](#2-환경-설정과-실행)
3. [노트북 상세](#3-노트북-상세)
4. [RAG 평가와 Ragas](#4-rag-평가와-ragas)
5. [정답basic_3 자체 평가 vs Ragas](#5-정답basic_3-자체-평가-vs-ragas)
6. [실행 결과](#6-실행-결과)
7. [폴더 구조](#7-폴더-구조)

---

## 1. 프로젝트 구성

| 노트북 | 단계 | 핵심 내용 |
|---|---|---|
| `정답basic_1.ipynb` | 기본 RAG | `PyPDFLoader`로 PDF 로드, chunk 500/50 분할, 메모리 Chroma, retriever 생성 |
| `정답basic_2.ipynb` | DB 영속성 | `pypdf`로 페이지별 Document 생성, `./chroma_db/basic`에 저장, 있으면 재사용 |
| `정답basic_3.ipynb` | 완성형 RAG | 메타데이터·chunk ID, 해시 기반 DB 캐싱, 테스트 15개, 자체 검색 평가, 근거 표시 답변 |
| `tryRagas.ipynb` | 평가 도구 입문 | 예제 1건으로 Ragas 지표 4개 사용법과 점수 변화 실험 |

권장 학습 순서: basic_1 → basic_2 → basic_3 → tryRagas

## 2. 환경 설정과 실행

- Python 3.12, 패키지 관리는 [uv](https://docs.astral.sh/uv/)
- OpenAI API 키 필요. 프로젝트 루트 `.env`에 `OPENAI_API_KEY=sk-...`를 넣거나 환경변수로 설정합니다. (`.env`는 `.gitignore`에 포함되어 커밋되지 않습니다.)

```bash
uv sync                                        # .venv 생성 + pyproject.toml/uv.lock 기준 설치
uv pip install ipykernel nbconvert nbformat    # 노트북/스크립트 실행용 (선택)
```

| 파일 | 역할 |
|---|---|
| `pyproject.toml`, `uv.lock` | 설치 기준 (권장) |
| `pre-requierments.txt` | 직접 필요한 패키지: ragas, python-dotenv, langchain 계열, chromadb, pypdf, datasets |
| `requirements.txt` | `uv pip freeze` 결과(유지보수용). 원작성자 로컬 경로(`-e file:///E:/...`)가 있어 **그대로 설치하지 마세요.** |
| `설치가이드.txt`, `import가이드.txt` | uv 프로젝트 생성·설치 절차, ragas import 메모 |

> `langchain-community==0.3.31`로 고정되어 있습니다. Ragas 0.4.3이 이 버전에 있는 옛 VertexAI 모듈을 import하기 때문입니다. (`pyproject.toml` 주석 참고)

**실행 방법**

- 노트북: VS Code/Jupyter에서 `.venv` 커널을 선택하고 위에서부터 실행합니다.
- 스크립트: 정답basic_3의 검색 평가와 답변 3건을 한 번에 실행하고 `결과basic_3.ipynb`로 저장합니다.

```powershell
$env:PYTHONUTF8=1; .venv\Scripts\python run_rag.py
```

## 3. 노트북 상세

### 3.1 정답basic_1 — RAG 기본 실행

1. `PyPDFLoader("./data/가상Tech_업무가이드.pdf").load()`로 PDF를 페이지 단위 Document로 로드
2. `RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)`로 분할
3. `OpenAIEmbeddings(model="text-embedding-3-small")`로 임베딩
4. `Chroma.from_documents(docs, embeddings)`로 벡터 저장소 생성 (메모리, 저장 안 됨)
5. `vectorstore.as_retriever()`로 retriever 생성

### 3.2 정답basic_2 — 영속성 DB 저장

- `pypdf.PdfReader`로 페이지마다 `Document(page_content, metadata)` 생성. 메타데이터는 `source`, `page`(0부터), `page_number`(1부터).
- 같은 chunk 설정(500/50)으로 분할하고 `./chroma_db/basic`에 컬렉션 `virtualtech-guide`로 저장.
- `chroma.sqlite3`가 이미 있으면 다시 임베딩하지 않고 로드 → 임베딩 API 비용 절감.
- `as_retriever(search_kwargs={"k": 4})`로 상위 4개 chunk를 검색.

### 3.3 정답basic_3 — 완성형 RAG + 자체 평가

| 단계 | 내용 |
|---|---|
| 1. 로더 | 페이지별 Document 생성. 텍스트가 없는 페이지(스캔 이미지)는 `""` 처리, OCR은 미지원 |
| 메타데이터 | `page_number`, 페이지별 `section`(예: 2쪽 "회사와 근무 원칙", 9쪽 "FAQ와 연락처"), `source_name` |
| 2. chunk | `chunk_size=800`, `overlap=120`, 구분자 `\n\n → \n → ". " → "다." → "요." → 공백`. 페이지별 번호를 매겨 `p02-c01` 형식 `chunk_id` 부여 |
| 3. ChromaDB | PDF 바이트의 SHA-256 앞 12자리로 DB 경로 결정 → `./chroma_db/<hash>`. PDF가 같으면 기존 DB 로드, 바뀌면 자동으로 새 DB 생성. `chunk_id`를 Chroma `ids`로 사용 |
| 4. 테스트 | 질문 15개. 각 케이스에 정답 페이지, 정답 근거 키워드(anchors), 기준 답변, 정답 chunk ID(키워드가 가장 많이 포함된 chunk 자동 산출) |
| 5. 검색 평가 | `evaluate_retrieval()`: Hit@4, MRR@4, Anchor hit rate |
| 6. 답변 생성 | `ask()`: 검색 chunk를 `[chunk_id] p.N` 헤더와 함께 컨텍스트로 넘기고 `gpt-4.1-mini`(temperature 0)가 답변 |

**환각 방지 프롬프트:** 검색된 문서만 근거로 한국어로 답하고, 숫자·시간·담당자·예외를 빠뜨리지 않으며, 근거가 없으면 "문서에서 확인할 수 없습니다."라고 답하고, 마지막에 `[근거: p02-c01]`처럼 chunk ID를 표시하게 합니다.

**자체 평가 지표 (규칙 기반, LLM 호출 없음)**

| 지표 | 의미 | 배점 |
|---|---|---|
| Hit@4 | top-4 검색 결과에 정답 페이지가 포함된 비율 | 30 |
| MRR@4 | 정답 페이지가 몇 번째로 나왔는지의 역수 평균 (1위=1, 2위=0.5 …) | 15 |
| Anchor hit rate | 검색된 chunk에 핵심 키워드가 1개 이상 포함된 비율 | 5 |

노트북 안내 기준: 검색 품질 50점 + 답변 품질 50점(정확성 20, 근거 충실성 15, 완결성 10, 출처 표시 5). 통과선은 `Hit@4 ≥ 0.90`, `MRR@4 ≥ 0.75`, 총점 80점 이상. 보안·권한·운영 관련 답에서 정책을 반대로 말하거나 없는 정책을 만들면 치명 오류로 감점합니다.

### 3.4 tryRagas — Ragas 입문

Ragas 0.4.3 기준으로, 질문 1건 · 검색 문서 2개 · 답변 1개 · 기준 답변 1개(`대한민국의 수도는?`)에 지표 4개를 적용해 보고, 요소를 하나씩 바꿔 점수가 어떻게 변하는지 확인하는 노트북입니다. 자세한 설명은 다음 절을 참고하세요.

---

## 4. RAG 평가와 Ragas

### 4.1 Ragas란

**Ragas(RAG Assessment)** 는 RAG 시스템의 품질을 자동으로 채점하는 오픈소스 평가 라이브러리입니다. 사람이 일일이 답을 읽고 판단하는 대신, **평가용 LLM(과 임베딩 모델)이 판정관 역할**을 해서 0~1 점수를 냅니다. 점수가 높을수록 해당 기준을 잘 충족한 것입니다.

RAG 품질은 두 영역으로 나눠서 봅니다.

- **검색(Retrieval):** 필요한 문서를 찾았는가?
- **생성(Generation):** 검색된 문서에 근거해 질문에 답했는가?

이렇게 나누면 답이 틀렸을 때 원인이 "검색이 문서를 못 찾음"인지 "LLM이 문서를 무시하고 답함"인지 구분할 수 있습니다.

### 4.2 평가 데이터 형식

Ragas는 RAG 실행 결과 1건을 아래 4개 필드로 받습니다.

| 필드 | 의미 | 예시 |
|---|---|---|
| `user_input` | 사용자 질문 | 대한민국의 수도는 어디인가요? |
| `retrieved_contexts` | 검색된 문서 조각 목록 (검색 순서대로) | ["서울은 대한민국의 수도이다.", "부산은 … 항구 도시이다."] |
| `response` | RAG가 생성한 답변 | 대한민국의 수도는 서울이다. |
| `reference` | 사람이 작성한 기준 답변(정답) | 대한민국의 수도는 서울이다. |

### 4.3 핵심 지표 4개

| 영역 | 지표 (클래스) | 묻는 것 | 필요한 입력 |
|---|---|---|---|
| 생성 | `Faithfulness` | 답변이 검색 문서에 **근거**하는가 (환각 여부) | user_input, response, retrieved_contexts |
| 생성 | `AnswerRelevancy` | 답변이 **질문과 관련**되는가 | user_input, response (+임베딩) |
| 검색 | `ContextPrecisionWithReference` | 유용한 문서가 **앞쪽**에 배치됐는가 (순위 품질) | user_input, reference, retrieved_contexts |
| 검색 | `ContextRecall` | 정답에 필요한 정보가 검색 문서에 **빠짐없이** 있는가 | user_input, reference, retrieved_contexts |

`reference`(정답)가 필요한 지표는 검색 쪽 두 개이고, 생성 쪽 두 개는 정답 없이도 계산됩니다.

### 4.4 사용 방법 (tryRagas 코드 흐름)

**1) 평가용 LLM·임베딩 준비.** `ascore()`가 비동기 메서드이므로 `AsyncOpenAI` 클라이언트를 사용합니다.

```python
from openai import AsyncOpenAI
from ragas.embeddings import OpenAIEmbeddings
from ragas.llms import llm_factory

evaluator_llm = llm_factory(model="gpt-4o-mini", client=AsyncOpenAI(), temperature=0)
evaluator_embeddings = OpenAIEmbeddings(client=AsyncOpenAI(), model="text-embedding-3-small")
```

**2) 지표별로 `ascore()` 호출.** 노트북에서는 셀에서 `await`를 바로 쓸 수 있습니다. 일반 스크립트에서는 `asyncio.run()` 안에서 호출합니다.

```python
from ragas.metrics.collections import (
    AnswerRelevancy, ContextPrecisionWithReference, ContextRecall, Faithfulness,
)

faithfulness = await Faithfulness(llm=evaluator_llm).ascore(
    user_input=q, response=answer, retrieved_contexts=contexts)

answer_relevancy = await AnswerRelevancy(
    llm=evaluator_llm, embeddings=evaluator_embeddings, strictness=1
).ascore(user_input=q, response=answer)

context_precision = await ContextPrecisionWithReference(llm=evaluator_llm).ascore(
    user_input=q, reference=ref, retrieved_contexts=contexts)

context_recall = await ContextRecall(llm=evaluator_llm).ascore(
    user_input=q, reference=ref, retrieved_contexts=contexts)
```

**3) 결과는 `.value`로 읽습니다.** 각 호출이 반환하는 점수 객체의 `.value`가 0~1 실수입니다.

> 주의: 이 단계부터 **OpenAI API 사용량(비용)이 발생**합니다. LLM 판정 방식이라 실행마다 점수가 조금씩 달라질 수 있습니다.

### 4.5 지표 동작 원리 (요약)

아래는 Ragas 문서 기준의 일반적인 설명이며, 세부 프롬프트는 버전에 따라 다를 수 있습니다.

- **Faithfulness:** 답변을 여러 주장(statement)으로 쪼개고, 각 주장이 검색 문서에서 뒷받침되는지 LLM이 판정합니다. (뒷받침되는 주장 수 / 전체 주장 수)
- **AnswerRelevancy:** LLM이 답변으로부터 "이 답변이 나올 만한 질문"을 역으로 생성하고, 원래 질문과의 임베딩 유사도를 봅니다. **답이 맞는지가 아니라 질문과 같은 주제인지**를 보는 지표입니다.
- **ContextPrecisionWithReference:** 검색 문서를 순서대로 보며 각 문서가 정답 도출에 유용한지 판정하고, 유용한 문서가 앞에 있을수록 높은 점수를 줍니다.
- **ContextRecall:** 기준 답변의 각 문장이 검색 문서에서 찾아지는지 판정합니다.

### 4.6 점수 변화 실험 (실제 실행 결과)

한 번에 한 요소만 바꿔서 어떤 지표가 반응하는지 확인했습니다. (2026-09-28 실행, 평가 LLM gpt-4o-mini)

| 실험 | Faithfulness | AnswerRelevancy | ContextPrecision | ContextRecall |
|---|---:|---:|---:|---:|
| 기본 (서울 문서, 부산 문서 / 답 "서울") | 1.0 | 0.273 | 1.0 | 1.0 |
| ① 답변을 "부산이다."로 변경 | **0.0** | 0.273 | 1.0 | 1.0 |
| ② 서울 문서 삭제 | **0.0** | 0.273 | **0.0** | **0.0** |
| ③ 부산 문서를 1번째로 이동 | 1.0 | 0.273 | **0.5** | 1.0 |

읽는 법:

- ① 문서에 없는 내용을 답하면 **Faithfulness가 0**으로 떨어집니다. (환각 탐지)
- ② 정답 근거 문서가 아예 없으면 **Recall이 0**이 되고 Precision도 0입니다. (검색 실패 탐지)
- ③ 정답 문서가 뒤로 밀리면 **Precision만 0.5**로 내려갑니다. (순위 문제 탐지)
- AnswerRelevancy는 세 실험 모두 0.273으로 같았습니다. 답이 틀려도(①) 질문과 같은 주제("수도")를 말하면 점수가 변하지 않는다는 뜻이며, 정답 여부는 Faithfulness·Recall이 잡아냅니다. 정답인 기본 케이스에서도 0.273으로 낮게 나오므로, 이 지표는 단독으로 좋고 나쁨을 판단하기보다 비교용으로 보는 편이 안전합니다. (`strictness=1`과 짧은 한 문장 질문·답변의 영향일 수 있으나 원인은 따로 검증하지 않았습니다.)

## 5. 정답basic_3 자체 평가 vs Ragas

평가한다는 목적은 같지만 방식이 다르고, **정답basic_3 노트북은 Ragas를 사용하지 않습니다.**

| | 정답basic_3 (직접 구현) | Ragas |
|---|---|---|
| 정답 기준 | 미리 정한 정답 페이지와 키워드 | 기준 답변(reference)과 LLM 판정 |
| 방식 | 코드 규칙 계산 (Hit, MRR, anchor) | LLM이 문장 단위로 판정 |
| 평가 시 LLM 호출 | 없음 (임베딩 검색만) | 있음 (지표당 여러 번) |
| 비용·재현성 | 거의 무료, 결과 항상 동일 | 비용 발생, 실행마다 약간 변동 |
| 잡아내는 것 | 검색이 맞는 페이지를 가져오는가 | 답변의 근거 충실성, 질문 관련성 등 |
| 못 잡는 것 | 답변 품질의 자동 채점 | 규칙 기반의 정확 일치 |

두 방식은 대체 관계가 아니라 **보완 관계**입니다. 검색 회귀 테스트는 자체 지표로 싸게 자주 돌리고, 답변 품질은 Ragas로 점검하는 조합이 실용적입니다.

**다음 단계 (미구현):** 정답basic_3의 `ask()`와 `test_cases` 15개에서 `retrieved_contexts`, `response`, `reference`를 뽑아 Ragas 지표로 일괄 평가하기. 원본 저장소에 `f/Ragas` 브랜치가 있지만 이 저장소에는 포함되어 있지 않습니다.

## 6. 실행 결과

### 정답basic_3 검색 평가 (15 케이스, k=4, 2026-09-28)

| 지표 | 값 | 기준 |
|---|---:|---|
| Hit@4 | 0.933 (14/15) | ≥ 0.90 통과 |
| MRR@4 | 0.867 | ≥ 0.75 통과 |
| Anchor hit rate | 0.933 | — |

### 답변 예시 (근거 chunk ID 포함)

- Q. 핵심 협업시간은? → 평일 11:00부터 16:00까지입니다. `[근거: p02-c01]`
- Q. 신입 첫날 18시까지 할 일은? → HRIS 프로필 작성, 보안 교육 수강, MFA 등록, 팀 채널 입장, 버디와 30분 온보딩 `[근거: p02-c02]`
- Q. 계정 탈취가 의심되면? → 네트워크를 끊고 02-555-0142 또는 #security-incident로 신고 `[근거: p03-c01]`

## 7. 폴더 구조

```
rag_two_branch/
├─ data/                 원본 PDF (가상Tech_업무가이드.pdf)
├─ chroma_db/
│  ├─ basic/             정답basic_2가 만든 DB
│  └─ <pdf-hash>/        정답basic_3가 만든 DB (PDF 해시 기반)
├─ 정답basic_1.ipynb      기본 RAG
├─ 정답basic_2.ipynb      DB 영속성
├─ 정답basic_3.ipynb      완성형 RAG + 자체 평가
├─ tryRagas.ipynb        Ragas 입문
├─ run_rag.py            정답basic_3 실행·결과 확인 스크립트
├─ pyproject.toml / uv.lock / requirements.txt / pre-requierments.txt
├─ 설치가이드.txt / import가이드.txt
└─ src/rag_two_branch/   패키지 골격
```

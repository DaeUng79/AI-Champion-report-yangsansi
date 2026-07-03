# Naive vs Advanced RAG 감사 문서 비교

2024년 정부합동감사 공개 데이터를 기반으로, Naive RAG와 Advanced RAG 검색 결과를 나란히 비교하는 Streamlit 애플리케이션입니다. 사용자가 질문을 입력하면 두 데이터셋에서 관련 문서를 검색하고, OpenRouter API를 통해 각각의 답변과 비교 요약을 생성합니다.

## 주요 기능

- Advanced RAG와 Naive RAG 검색 결과를 좌우 패널로 비교
- 검색된 문서의 유사도 점수, 메타데이터, 본문 근거 확인
- 같은 질문에 대한 두 답변의 공통점과 차이점 요약
- Streamlit 사이드바에서 OpenRouter API 키 입력
- Supabase REST API 기반 문서 조회

## 프로젝트 구조

```text
.
├── streamlit_rag_compare.py      # RAG 비교 Streamlit 앱
├── requirements.txt              # 앱 실행에 필요한 Python 패키지
├── Advanced_RAG.json             # Advanced RAG 데이터 샘플/결과 파일
├── Naive_RAG.json                # Naive RAG 데이터 샘플/결과 파일
├── 24년 충북(공개본).pdf          # 원천 감사 PDF
```

## 실행 방법

1. 가상환경을 생성하고 활성화합니다.

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. 의존성을 설치합니다.

```bash
pip install -r requirements.txt
```

3. `.env` 파일을 준비합니다.

```env
SUPABASE_URL="your-supabase-url"
SUPABASE_KEY="your-supabase-key"
OPENROUTER_API_KEY="your-openrouter-api-key"
```

4. Streamlit 앱을 실행합니다.

```bash
streamlit run streamlit_rag_compare.py
```

5. 브라우저에서 앱이 열리면 사이드바의 `OpenRouter API 키` 입력란을 확인한 뒤 질문을 입력합니다.

## 환경변수

| 변수명 | 설명 |
| --- | --- |
| `SUPABASE_URL` | Supabase 프로젝트 URL. 공개 저장소에 포함해도 됩니다. |
| `SUPABASE_KEY` | Supabase REST API 접근 키. 클라이언트 앱에서는 공개 가능한 `anon` 키를 사용하세요. |
| `OPENROUTER_API_KEY` | OpenRouter API 키 |

`SUPABASE_URL`과 Supabase `anon` 키는 공개되어도 괜찮습니다. 단, `service_role` 키처럼 관리자 권한을 가진 키는 절대 공개 저장소에 올리지 마세요. `streamlit_rag_compare.py`는 `OPENROUTER_API_KEY`, `OPEN_ROUTER_API_KEY`, `OpenRouter_API_KEY` 중 하나를 읽을 수 있습니다.

## 사용 모델

| 용도 | 모델 |
| --- | --- |
| 질의 임베딩 | `openai/text-embedding-3-small` |
| 답변 생성 | `openai/gpt-4.1-mini` |

OpenRouter의 OpenAI 호환 엔드포인트(`https://openrouter.ai/api/v1`)를 사용합니다.

## Supabase 테이블

앱은 다음 두 테이블을 조회합니다.

| 구분 | 테이블명 |
| --- | --- |
| Advanced RAG | `audit_documents` |
| Naive RAG | `audit_pdf_documents` |

각 테이블에는 최소한 `content`, `metadata`, `embedding` 컬럼이 필요합니다. PDF 기반 테이블은 `pdf_record`, `embedding_text` 컬럼을 함께 사용합니다.

## PDF 전처리 스크립트

`Aca/pdf.py`는 감사 PDF에서 텍스트를 추출하고, 지적사항 단위로 청킹한 뒤 Supabase 업로드용 JSON 또는 SQL을 생성하는 보조 스크립트입니다.

예시:

```bash
python Aca/pdf.py --pdf-path "24년 충북(공개본).pdf" --output-json audit_pdf_chunks.json
```

Supabase 테이블 생성 SQL을 확인하려면 다음 명령을 사용할 수 있습니다.

```bash
python Aca/pdf.py --print-sql
```

PDF 전처리 및 업로드까지 실행하려면 `PyPDF2`, `python-dotenv`, `supabase`, `tqdm` 패키지가 추가로 필요할 수 있습니다.

## 주의사항

- `SUPABASE_URL`과 Supabase `anon` 키는 공개해도 되지만, Supabase `service_role` 키와 OpenRouter API 키는 공개 저장소에 올리지 마세요.
- 현재 앱은 Supabase에서 최대 2,000개 행을 가져와 로컬에서 코사인 유사도를 계산합니다.
- 대용량 데이터셋에서는 Supabase `pgvector` RPC 검색으로 전환하면 응답 속도와 비용을 개선할 수 있습니다.
- 생성 답변은 검색 문맥을 기반으로 하지만, 중요한 판단에는 원문 PDF와 검색 근거를 함께 확인하는 것이 좋습니다.

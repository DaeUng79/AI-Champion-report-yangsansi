import json
from pathlib import Path
from typing import Any

import numpy as np
import requests
import streamlit as st
from openai import OpenAI


ENV_PATH = Path(".env")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
EMBED_MODEL = "openai/text-embedding-3-small"
ANSWER_MODEL = "openai/gpt-4.1-mini"
LEFT_TABLE = "audit_documents"
RIGHT_TABLE = "audit_pdf_documents"
LEFT_LABEL = "Advanced RAG 조회 결과"
RIGHT_LABEL = "Naive RAG 조회 결과"


if "messages" not in st.session_state:
    st.session_state.messages = []
    # 서비스 시작 시 초기 메시지 추가
    st.session_state.messages.append({
        "role": "assistant",
        "content": "안녕하세요! Advanced 및 Naive RAG 데이터를 비교해보세요. 궁금한 질문을 입력해 주세요.",
    })

def load_env_file(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


ENV = load_env_file(ENV_PATH)
HARDCODED_SUPABASE_URL = "https://gakgsiegaaraaedqsxmd.supabase.co"
HARDCODED_SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imdha2dzaWVnYWFyYWFlZHFzeG1kIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4Mjk3NTc0NSwiZXhwIjoyMDk4NTUxNzQ1fQ.CtcjVWbmB9wqO2_PssCqlRgAKYGXZ6RCKvh9Ldq1Ti0"  # 공개 가능한 Supabase anon key만 여기에 입력하세요.
SUPABASE_URL = HARDCODED_SUPABASE_URL or ENV.get("SUPABASE_URL", "")
SUPABASE_KEY = HARDCODED_SUPABASE_KEY or ENV.get("SUPABASE_KEY", "")
OPENROUTER_API_KEY = (
    ENV.get("OPENROUTER_API_KEY")
    or ENV.get("OPEN_ROUTER_API_KEY")
    or ENV.get("OpenRouter_API_KEY")
    or ""
)


def validate_config() -> list[str]:
    missing = []
    for key, value in {
        "SUPABASE_URL": SUPABASE_URL,
        "SUPABASE_KEY": SUPABASE_KEY,
    }.items():
        if not value:
            missing.append(key)
    return missing


def build_headers() -> dict[str, str]:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def parse_embedding(value: Any) -> np.ndarray:
    if isinstance(value, list):
        return np.asarray(value, dtype=float)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return np.asarray([], dtype=float)
        return np.asarray(json.loads(text), dtype=float)
    return np.asarray([], dtype=float)


@st.cache_resource
def get_openai_client(api_key: str) -> OpenAI:
    return OpenAI(
        api_key=api_key,
        base_url=OPENROUTER_BASE_URL,
    )


@st.cache_data(show_spinner=False, ttl=300)
def fetch_table_rows(table_name: str) -> list[dict[str, Any]]:
    url = f"{SUPABASE_URL}/rest/v1/{table_name}"
    params = {
        "select": "*",
        "limit": "2000",
    }
    response = requests.get(url, headers=build_headers(), params=params, timeout=60)
    response.raise_for_status()
    rows = response.json()

    normalized = []
    for row in rows:
        embedding = parse_embedding(row.get("embedding"))
        if embedding.size == 0:
            continue
        normalized.append(
            {
                "id": row.get("id"),
                "content": row.get("content", ""),
                "metadata": row.get("metadata") or {},
                "embedding": embedding,
                "audit_record": row.get("audit_record") or {},
                "pdf_record": row.get("pdf_record") or {},
                "embedding_text": row.get("embedding_text", ""),
            }
        )
    return normalized


def cosine_similarity(query_vector: np.ndarray, doc_vector: np.ndarray) -> float:
    q_norm = np.linalg.norm(query_vector)
    d_norm = np.linalg.norm(doc_vector)
    if q_norm == 0 or d_norm == 0:
        return 0.0
    return float(np.dot(query_vector, doc_vector) / (q_norm * d_norm))


def make_query_embedding(question: str, api_key: str) -> np.ndarray:
    client = get_openai_client(api_key)
    response = client.embeddings.create(model=EMBED_MODEL, input=question)
    return np.asarray(response.data[0].embedding, dtype=float)


def retrieve_documents(query_vector: np.ndarray, table_name: str, top_k: int) -> list[dict[str, Any]]:
    rows = fetch_table_rows(table_name)
    scored = []
    for row in rows:
        score = cosine_similarity(query_vector, row["embedding"])
        scored.append(
            {
                "score": score,
                "content": row["content"],
                "metadata": row["metadata"],
                "audit_record": row["audit_record"],
                "pdf_record": row["pdf_record"],
                "embedding_text": row["embedding_text"],
            }
        )
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:top_k]


def compact_text(value: Any, limit: int = 180) -> str:
    text = str(value).replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def describe_result(item: dict[str, Any]) -> str:
    metadata = item["metadata"]
    audit_record = item.get("audit_record") or {}
    pdf_record = item.get("pdf_record") or {}

    lines = [f"score={item['score']:.4f}"]

    if audit_record:
        lines.append(f"피감기관: {audit_record.get('피감기관', '')}")
        lines.append(f"사건제목: {audit_record.get('사건제목', '')}")
        if audit_record.get("연관단어"):
            lines.append(f"연관단어: {compact_text(audit_record['연관단어'], 120)}")
    elif pdf_record:
        lines.append(f"대상기관: {pdf_record.get('institution', '')}")
        lines.append(f"지적사항 제목: {pdf_record.get('issue_title', '')}")
        lines.append(f"섹션: {pdf_record.get('section_title', '')}")
        lines.append(f"페이지: {pdf_record.get('page_start', '')}~{pdf_record.get('page_end', '')}")
    else:
        for key in ["document_title", "source", "section_title"]:
            value = metadata.get(key)
            if value not in (None, ""):
                lines.append(f"{key}: {value}")

    lines.append(f"본문: {compact_text(item['content'], 320)}")
    return "\n".join(line for line in lines if line.split(":", 1)[-1].strip() or line.startswith("score="))


def format_context(results: list[dict[str, Any]]) -> str:
    blocks = []
    for idx, item in enumerate(results, start=1):
        metadata = item["metadata"]
        audit_record = item.get("audit_record") or {}
        pdf_record = item.get("pdf_record") or {}

        context_lines = [f"[문서 {idx}] score={item['score']:.4f}"]

        if audit_record:
            for key in [
                "피감기관",
                "사건제목",
                "사건개요",
                "관계법령_및_판단기준",
                "감사결과_확인된_문제점",
                "검토결과",
                "판단",
                "조치할사항",
                "연관단어",
            ]:
                value = audit_record.get(key)
                if value:
                    context_lines.append(f"{key}: {value}")
        elif pdf_record:
            for key in [
                "record_type",
                "institution",
                "issue_title",
                "action_type",
                "section_title",
                "page_start",
                "page_end",
            ]:
                value = pdf_record.get(key)
                if value not in (None, ""):
                    context_lines.append(f"{key}: {value}")
            context_lines.append(f"content: {item['content']}")
        else:
            for key, value in metadata.items():
                if value not in (None, ""):
                    context_lines.append(f"{key}: {value}")
            context_lines.append(f"content: {item['content']}")

        blocks.append("\n".join(context_lines))

    return "\n\n".join(blocks)


def generate_answer(question: str, table_label: str, results: list[dict[str, Any]], api_key: str) -> str:
    context = format_context(results)
    client = get_openai_client(api_key)
    prompt = f"""
당신은 정부합동감사 결과 문서를 기반으로 답하는 한국어 RAG 도우미입니다.
아래 검색 결과는 `{table_label}` 데이터셋에서 찾은 문맥입니다.
반드시 문맥에 근거해서만 답변하세요.
문맥에 직접 근거가 부족하면 모른다고 말하고, 추정이라고 명시하세요.
답변 뒤에는 "근거"라는 제목 아래 2~4개 bullet로 핵심 근거를 짧게 정리하세요.

[질문]
{question}

[검색 문맥]
{context}
""".strip()

    response = client.chat.completions.create(
        model=ANSWER_MODEL,
        messages=[
            {
                "role": "system",
                "content": "당신은 검색 문맥에 근거해 정확하게 답하는 한국어 어시스턴트입니다.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    return response.choices[0].message.content or ""

def generate_comparison_summary(
    question: str,
    left_label: str,
    left_answer: str,
    right_label: str,
    right_answer: str,
    api_key: str,
):
    client = get_openai_client(api_key)
    prompt = f"""
아래는 같은 질문에 대해 두 개의 RAG 데이터셋이 생성한 답변입니다.
두 답변을 비교해서 다음 형식으로 한국어로 정리하세요.

1. 공통점
2. 차이점
3. 어느 쪽이 더 구체적인지
4. 사용자가 추가로 확인하면 좋은 점

질문: {question}

[{left_label} 답변]
{left_answer}

[{right_label} 답변]
{right_answer}
""".strip()

    response = client.chat.completions.create(
        model=ANSWER_MODEL,
        messages=[
            {
                "role": "system",
                "content": "당신은 두 개의 RAG 답변을 비교 분석하는 한국어 어시스턴트입니다.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        stream=True,
    )

    # return 제거, 변수명 response로 통일
    for chunk in response:
        content = chunk.choices[0].delta.content
        if content:
            yield content


def metadata_caption(item: dict[str, Any]) -> str:
    metadata = item["metadata"]
    audit_record = item.get("audit_record") or {}
    pdf_record = item.get("pdf_record") or {}

    if audit_record:
        parts = []
        for key in ["피감기관", "사건제목", "문서출처"]:
            value = audit_record.get(key)
            if value not in (None, ""):
                parts.append(f"{key}={compact_text(value, 50)}")
        return " | ".join(parts) if parts else "audit_record 있음"

    if pdf_record:
        parts = []
        for key in ["institution", "issue_title", "section_title"]:
            value = pdf_record.get(key)
            if value not in (None, ""):
                parts.append(f"{key}={compact_text(value, 50)}")
        page_start = pdf_record.get("page_start")
        page_end = pdf_record.get("page_end")
        if page_start and page_end:
            parts.append(f"page={page_start}~{page_end}")
        return " | ".join(parts) if parts else "pdf_record 있음"

    parts = []
    for key in ["document_title", "source", "section_title"]:
        value = metadata.get(key)
        if value not in (None, ""):
            parts.append(f"{key}={compact_text(value, 50)}")
    return " | ".join(parts) if parts else "metadata 없음"


def render_result_panel(title: str, answer: str, results: list[dict[str, Any]]) -> None:
    st.subheader(title)
    with st.container(height=300):
        st.markdown(answer)
    st.divider()
    st.caption("RAG 조회 데이터")
    for idx, item in enumerate(results, start=1):
        with st.expander(f"Top {idx} | score={item['score']:.4f}", expanded=False):
            st.caption(metadata_caption(item))
            st.code(describe_result(item), language="text")
            st.write(item["content"])

def main() -> None:
    st.set_page_config(page_title="감사 RAG 비교", layout="wide")
    st.title("Naive VS Advanced RAG 결과 비교 검토")
    st.caption("2024년 정부합동감사 공개 데이터")


    missing = validate_config()
    if missing:
        st.error(f".env 설정이 부족합니다: {', '.join(missing)}")
        st.stop()

    # ── 사이드바 설정 ──────────────────────────────────────
    with st.sidebar:
        api_key = st.text_input(
            "OpenRouter API 키",
            value=st.session_state.get("openrouter_api_key", OPENROUTER_API_KEY),
            type="password",
            help="입력한 키는 현재 세션에서만 사용됩니다.",
        ).strip()
        st.session_state.openrouter_api_key = api_key
        top_k = st.slider("검색 문서 수", min_value=2, max_value=10, value=4)
        show_comparison = st.checkbox("답변 비교 요약 생성", value=True)
        st.text_input("임베딩 모델", value=EMBED_MODEL, disabled=True)
        st.text_input("답변 모델", value=ANSWER_MODEL, disabled=True)
        if st.button("캐시 새로고침"):
            fetch_table_rows.clear()
            st.cache_resource.clear()
            st.success("캐시를 비웠습니다.")

    if not api_key:
        st.warning("사이드바 설정에서 OpenRouter API 키를 입력해 주세요.")
        st.stop()

    # ── 채팅 히스토리 초기화 ───────────────────────────────
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # ── 이전 대화 표시 ────────────────────────────────────
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # ── 사용자 입력 ───────────────────────────────────────
    if question := st.chat_input("예: 시스템 구축 추진 부적정 사례의 핵심 문제와 조치사항은 무엇인가요?"):

        # 사용자 메시지 표시 및 저장
        with st.chat_message("user"):
            st.markdown(question)
        st.session_state.messages.append({"role": "user", "content": question})

        # 어시스턴트 응답 생성
        with st.chat_message("assistant"):
            try:
                with st.spinner("두 데이터셋에서 검색하고 답변을 생성하는 중입니다..."):
                    query_vector = make_query_embedding(question, api_key)
                    left_results  = retrieve_documents(query_vector, LEFT_TABLE,  top_k)
                    right_results = retrieve_documents(query_vector, RIGHT_TABLE, top_k)
                    left_answer   = generate_answer(question, LEFT_LABEL,  left_results, api_key)
                    right_answer  = generate_answer(question, RIGHT_LABEL, right_results, api_key)
                    comparison_summary = ""
                # 비교 요약 출력 (스트리밍)
                if show_comparison:
                    st.subheader("비교 요약")
                    comparison_summary = st.write_stream(
                        generate_comparison_summary(
                            question,
                            LEFT_LABEL, left_answer,
                            RIGHT_LABEL, right_answer,
                            api_key,
                        )
                    )
                    st.divider()

                # 좌/우 패널 출력
                left_col, right_col = st.columns(2)
                with left_col:
                    render_result_panel(LEFT_LABEL,  left_answer,  left_results)
                with right_col:
                    render_result_panel(RIGHT_LABEL, right_answer, right_results)

                # 히스토리에 저장할 텍스트 구성
                saved_content = (
                    f"**비교 요약**\n\n{comparison_summary}\n\n---\n\n"
                    f"**{LEFT_LABEL}**\n\n{left_answer}\n\n"
                    f"**{RIGHT_LABEL}**\n\n{right_answer}"
                )

            except requests.HTTPError as exc:
                detail = exc.response.text if exc.response is not None else str(exc)
                saved_content = f"❌ Supabase 조회 중 오류가 발생했습니다.\n\n{detail}"
                st.error(saved_content)
            except Exception as exc:
                saved_content = f"❌ 실행 중 오류가 발생했습니다: {exc}"
                st.error(saved_content)

        st.session_state.messages.append({"role": "assistant", "content": saved_content})

if __name__ == "__main__":
    main()

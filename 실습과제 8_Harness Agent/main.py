import asyncio
import os
from pathlib import Path
from typing import Any, TypeVar

import streamlit as st
from agents import RunConfig, Runner
from dotenv import load_dotenv

from app_agents import (
    CriticAssessment,
    ResearchAssessment,
    SupervisorAssessment,
    create_agents,
)


load_dotenv(Path(__file__).with_name(".env"))

DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
ENVIRONMENT_KEYS = ("OPENAI_API_KEY", "TAVILY_API_KEY")
MAX_STAGE_INPUT_CHARS = 45_000
AGENT_RUNTIME_VERSION = "markdown-render-v2"
StructuredOutput = TypeVar(
    "StructuredOutput",
    ResearchAssessment,
    CriticAssessment,
    SupervisorAssessment,
)

st.set_page_config(page_title="Multi-Agent Orchestration", layout="wide")
st.title("Multi-Agent Orchestration")
st.caption("OpenAI Agents SDK 기반 보고서 작성 에이전트 팀")


def deidentified_api_key(key_name: str) -> str | None:
    api_key = st.session_state.get(key_name)
    if not api_key:
        return None
    if len(api_key) <= 12:
        return "••••••"
    return f"{api_key[:6]}...{api_key[-6:]}"


def apply_environment_config() -> None:
    """.env 값을 현재 Streamlit 세션의 기본 설정으로 적용합니다."""
    if st.session_state.get("ignore_environment_keys"):
        return

    for key_name in ENVIRONMENT_KEYS:
        value = os.getenv(key_name)
        if value and key_name not in st.session_state:
            st.session_state[key_name] = value


def reset_conversation() -> None:
    st.session_state["messages"] = []
    st.session_state["agent_input"] = []


def normalize_markdown(content: Any) -> str:
    """모델이 보고서 전체를 감싼 Markdown 코드 펜스를 제거합니다."""
    text = str(content or "").strip()
    lines = text.splitlines()
    if len(lines) < 2:
        return text

    opening_fence = lines[0].strip().lower()
    closing_fence = lines[-1].strip()
    markdown_fences = {"```", "```markdown", "```md", "~~~", "~~~markdown", "~~~md"}
    if opening_fence in markdown_fences and closing_fence in {"```", "~~~"}:
        return "\n".join(lines[1:-1]).strip()
    return text


def run_async(coroutine: Any) -> Any:
    """Streamlit 재실행 사이에서도 동일한 비동기 이벤트 루프를 사용합니다."""
    event_loop = st.session_state.get("event_loop")
    if event_loop is None or event_loop.is_closed():
        event_loop = asyncio.new_event_loop()
        st.session_state["event_loop"] = event_loop
    return event_loop.run_until_complete(coroutine)


apply_environment_config()


with st.sidebar:
    st.markdown("🔑 API Key 설정")

    openai_api_key = None
    tavily_api_key = None
    if "OPENAI_API_KEY" not in st.session_state:
        st.markdown("🔐 [OpenAI API 키 발급방법](https://platform.openai.com/api-keys)")
        openai_api_key = st.text_input("🤖 OPENAI API 키", type="password")

    if "TAVILY_API_KEY" not in st.session_state:
        st.markdown("🔎 [Tavily API 키 발급방법](https://app.tavily.com/)")
        tavily_api_key = st.text_input("🌐 TAVILY API 키(선택)", type="password")

    if openai_api_key is not None or tavily_api_key is not None:
        if st.button("✅ 적용", type="primary"):
            if openai_api_key:
                st.session_state["OPENAI_API_KEY"] = openai_api_key
            if tavily_api_key:
                st.session_state["TAVILY_API_KEY"] = tavily_api_key
            st.rerun()
    else:
        if st.button("🗑️ 키 초기화"):
            st.session_state["ignore_environment_keys"] = True
            st.session_state.pop("OPENAI_API_KEY", None)
            st.session_state.pop("TAVILY_API_KEY", None)
            st.session_state.pop("agents", None)
            st.session_state.pop("agent_config", None)
            reset_conversation()
            st.rerun()

    masked_openai_key = deidentified_api_key("OPENAI_API_KEY")
    masked_tavily_key = deidentified_api_key("TAVILY_API_KEY")
    if masked_openai_key:
        st.markdown(f"🔑 **OPENAI API 키**\n\n`{masked_openai_key}`")
    if masked_tavily_key:
        st.markdown(f"🔑 **TAVILY API 키**\n\n`{masked_tavily_key}`")

    model_name = st.text_input(
        "사용 모델",
        value=st.session_state.get("model_name", DEFAULT_MODEL),
        help=".env의 OPENAI_MODEL 값이 없으면 gpt-4o를 사용합니다.",
    ).strip()
    st.session_state["model_name"] = model_name or DEFAULT_MODEL

    show_workflow_details = st.checkbox(
        "단계별 처리 결과 표시",
        value=True,
        help="검색 근거, 초안, 감수 결과와 최종 검토 의견을 표시합니다.",
    )

    if st.button("🗑️ 대화 내용 초기화"):
        reset_conversation()
        st.rerun()


if not st.session_state.get("OPENAI_API_KEY"):
    st.warning("OPENAI API 키가 설정되지 않았습니다.")
    st.stop()

if not st.session_state.get("TAVILY_API_KEY"):
    st.info("Tavily API 키가 없어 웹 검색 도구 없이 실행합니다.")


agent_config = (
    st.session_state["OPENAI_API_KEY"],
    st.session_state.get("TAVILY_API_KEY"),
    st.session_state["model_name"],
)


def agents_use_current_schema() -> bool:
    """Streamlit 세션에 남은 에이전트가 현재 출력 스키마를 사용하는지 확인합니다."""
    agents = st.session_state.get("agents")
    return bool(
        isinstance(agents, dict)
        and getattr(agents.get("researcher"), "output_type", None)
        is ResearchAssessment
        and getattr(agents.get("critic"), "output_type", None) is CriticAssessment
        and getattr(agents.get("supervisor"), "output_type", None)
        is SupervisorAssessment
    )


config_changed = st.session_state.get("agent_config") != agent_config
runtime_changed = (
    st.session_state.get("agent_runtime_version") != AGENT_RUNTIME_VERSION
)
if config_changed or runtime_changed or not agents_use_current_schema():
    st.session_state["agents"] = create_agents(*agent_config)
    st.session_state["agent_config"] = agent_config
    st.session_state["agent_runtime_version"] = AGENT_RUNTIME_VERSION
    if config_changed:
        reset_conversation()

st.session_state.setdefault("messages", [])
st.session_state.setdefault("agent_input", [])


for message in st.session_state["messages"]:
    with st.chat_message(message["role"]):
        st.markdown(normalize_markdown(message["content"]))
        if show_workflow_details and message.get("workflow_details"):
            with st.expander("🔍 단계별 처리 결과", expanded=False):
                for detail in message["workflow_details"]:
                    st.markdown(f"### {detail['title']}")
                    st.markdown(normalize_markdown(detail["content"]))
                    st.divider()


def tool_name_from_event(event: Any) -> str:
    raw_item = getattr(getattr(event, "item", None), "raw_item", None)
    return getattr(raw_item, "name", None) or "도구"


async def run_stage(agent: Any, task: str, workflow_status: Any) -> Any:
    """에이전트 한 단계를 실행하고 도구 사용 상황을 화면에 표시합니다."""
    compact_task = limit_text(task, MAX_STAGE_INPUT_CHARS)
    if compact_task != task:
        workflow_status.write("✂️ 모델 입력 한도에 맞게 이전 단계 내용을 압축했습니다.")
    result = Runner.run_streamed(
        agent,
        input=compact_task,
        max_turns=10,
        run_config=RunConfig(tracing_disabled=True),
    )
    async for event in result.stream_events():
        if event.type != "run_item_stream_event":
            continue
        if event.name == "tool_called":
            workflow_status.write(f"🔎 {tool_name_from_event(event)} 실행 중")
        elif event.name == "tool_output":
            workflow_status.write("✅ 검색 결과 수집 완료")
    return result.final_output


def limit_text(text: str, max_chars: int) -> str:
    """긴 텍스트의 앞뒤 핵심 부분을 남겨 컨텍스트 초과를 방지합니다."""
    if len(text) <= max_chars:
        return text
    marker = "\n\n[입력 길이 제한으로 중간 내용이 생략되었습니다.]\n\n"
    available_chars = max_chars - len(marker)
    head_size = int(available_chars * 0.7)
    tail_size = available_chars - head_size
    return text[:head_size] + marker + text[-tail_size:]


def parse_structured_output(
    value: Any,
    output_type: type[StructuredOutput],
    agent_name: str,
) -> StructuredOutput:
    """hot-reload 전후의 Pydantic 객체·dict·JSON 문자열을 현재 스키마로 변환합니다."""
    try:
        if isinstance(value, output_type):
            return value
        if hasattr(value, "model_dump"):
            value = value.model_dump()
        if isinstance(value, str):
            return output_type.model_validate_json(value)
        return output_type.model_validate(value)
    except Exception as exc:
        value_type = type(value).__name__
        raise TypeError(
            f"{agent_name} 결과 형식({value_type})을 구조화된 출력으로 변환하지 못했습니다."
        ) from exc


def list_as_markdown(items: list[str], empty_text: str = "없음") -> str:
    if not items:
        return empty_text
    return "\n".join(f"- {item}" for item in items)


def format_research_review(
    research: ResearchAssessment,
    review: SupervisorAssessment,
) -> str:
    sources = "\n".join(
        f"- [{source.title}]({source.url}) — {source.supports}"
        for source in research.sources
    ) or "- 확인된 출처 없음"
    return f"""
**Research Agent 충분성 판단:** {'충분' if research.sufficient else '추가 조사 필요'}  
**Supervisor 승인:** {'승인' if review.approved else '보완 필요'}

#### 조사 요약

{research.summary}

#### 사용한 검색어

{list_as_markdown(research.search_queries)}

#### 핵심 발견

{list_as_markdown(research.findings)}

#### 확인한 출처

{sources}

#### 부족하거나 불확실한 내용

{list_as_markdown(research.gaps)}

#### Supervisor 검토 의견

{list_as_markdown(review.review_notes)}
"""


def format_critic_review(critique: CriticAssessment) -> str:
    return f"""
**감수 판정:** {'승인' if critique.approved else '수정 필요'}

#### 발견 및 개선 사항

{list_as_markdown(critique.issues)}

#### 감수·수정된 보고서

{normalize_markdown(critique.revised_report)}
"""


def format_supervisor_review(review: SupervisorAssessment) -> str:
    return f"""
**최종 판정:** {'승인' if review.approved else '추가 수정 필요'}

#### 검토 의견

{list_as_markdown(review.review_notes)}
"""


def build_research_material(rounds: list[ResearchAssessment]) -> str:
    """중복 원문 없이 보고서 작성에 필요한 검증 결과만 압축합니다."""
    sections = []
    for index, research in enumerate(rounds, start=1):
        source_lines = "\n".join(
            f"- {source.title}: {source.supports} ({source.url})"
            for source in research.sources[:10]
        ) or "- 출처 없음"
        sections.append(
            f"""
## 조사 {index}차

### 요약
{limit_text(research.summary, 4_000)}

### 핵심 발견
{list_as_markdown(research.findings[:20])}

### 출처
{source_lines}

### 남은 한계
{list_as_markdown(research.gaps[:10])}
""".strip()
        )
    return limit_text("\n\n".join(sections), 30_000)


async def run_agent_workflow(
    user_input: str,
) -> tuple[str, list[dict[str, str]]]:
    """조사, 작성, 비평, 최종 승인을 순서대로 자동 실행합니다."""
    agents = st.session_state["agents"]
    workflow_details: list[dict[str, str]] = []

    with st.chat_message("assistant"):
        chat_container = st.empty()
        with st.status("Supervisor가 자동 보고서 작업을 시작했습니다.", expanded=True) as status:
            def record_detail(title: str, content: str) -> None:
                content = normalize_markdown(content)
                workflow_details.append({"title": title, "content": content})
                if show_workflow_details:
                    with st.expander(title, expanded=False):
                        st.markdown(content)

            research_rounds: list[ResearchAssessment] = []
            research_approved = False
            research_task = f"""
사용자 요청:
{user_input}

이 요청에 답하는 보고서를 작성할 수 있도록 최신 정보를 검색하고 교차 검증하세요.
핵심 주장마다 신뢰할 수 있는 출처를 확인하고, 근거가 부족하면 추가 검색이 필요하다고 판정하세요.
"""

            for round_number in range(1, 4):
                status.write(f"### 1단계 · 조사 및 검증 ({round_number}/3)")
                research = parse_structured_output(
                    await run_stage(agents["researcher"], research_task, status),
                    ResearchAssessment,
                    "Research Agent",
                )
                research_rounds.append(research)

                status.write("🧭 Supervisor가 조사 내용과 출처를 검증합니다.")
                research_review = parse_structured_output(
                    await run_stage(
                        agents["supervisor"],
                        f"""
사용자 요청:
{user_input}

Research Agent 조사 결과:
{research.model_dump_json(indent=2)}

아직 보고서를 작성하지 마세요. 사용자의 핵심 질문을 답하기에 조사가 충분한지,
주요 주장에 신뢰할 수 있는 출처가 연결되어 있는지, 최신성과 교차 검증이 적절한지 확인하세요.
Writing Agent 단계로 진행해도 될 때만 approved를 참으로 판정하세요.
부족하면 review_notes에 추가로 확인할 내용과 검색 방향을 구체적으로 작성하세요.
""",
                        status,
                    ),
                    SupervisorAssessment,
                    "Supervisor Agent",
                )

                record_detail(
                    f"조사·검증 {round_number}차",
                    format_research_review(research, research_review),
                )

                if research.sufficient and research_review.approved:
                    research_approved = True
                    status.write("✅ Supervisor가 조사 결과를 승인했습니다.")
                    break

                status.write("🔁 Supervisor 판단에 따라 부족한 근거를 다시 검색합니다.")
                research_task = f"""
사용자 요청:
{user_input}

이전 조사 결과:
{research.model_dump_json(indent=2)}

Supervisor 검증 결과:
승인 여부: {research_review.approved}
보완 의견:
{list_as_markdown(research_review.review_notes)}

부족한 내용을 보완하세요. 추가 검색어와 Supervisor의 검증 의견을 반영해 다시 검색하고,
출처 간 내용을 교차 검증한 뒤 조사 충분성을 다시 판정하세요.
"""
            else:
                status.update(
                    label="조사 결과가 검증 기준을 충족하지 못했습니다.",
                    state="error",
                )

            if not research_approved:
                raise RuntimeError(
                    "세 차례 조사 후에도 Supervisor 승인을 받지 못해 보고서 작성을 중단했습니다. "
                    "질문의 범위를 조금 더 구체적으로 지정해 주세요."
                )

            research_material = build_research_material(research_rounds)

            status.write("### 2단계 · Writing Agent 보고서 작성")
            draft = await run_stage(
                agents["writer"],
                f"""
사용자 요청:
{user_input}

검증된 조사 자료:
{research_material}

조사 자료에 근거하여 완성된 한국어 보고서를 작성하세요.
확인되지 않은 내용은 단정하지 말고 조사 한계를 명확하게 표시하세요.
""",
                status,
            )
            if not isinstance(draft, str):
                draft = str(draft)
            draft = normalize_markdown(draft)
            record_detail("Writing Agent 초안", draft)

            status.write("### 3단계 · Critic Agent 감수 및 수정")
            critique = parse_structured_output(
                await run_stage(
                    agents["critic"],
                    f"""
사용자 요청:
{user_input}

검증된 조사 자료:
{research_material}

Writing Agent 초안:
{draft}

초안의 사실성, 출처 일치, 논리, 구성과 표현을 감수하고 문제를 직접 수정하세요.
""",
                    status,
                ),
                CriticAssessment,
                "Critic Agent",
            )
            record_detail("Critic Agent 1차 감수", format_critic_review(critique))

            report_for_review = normalize_markdown(critique.revised_report)
            supervisor_review: SupervisorAssessment | None = None
            for review_round in range(1, 3):
                status.write(f"### 4단계 · Supervisor 최종 확인 ({review_round}/2)")
                supervisor_review = parse_structured_output(
                    await run_stage(
                        agents["supervisor"],
                        f"""
사용자 요청:
{user_input}

검증된 조사 자료:
{research_material}

Critic Agent 감수 결과:
감수 승인 여부: {critique.approved}
발견 및 개선 사항:
{list_as_markdown(critique.issues)}

최종 검토 대상 보고서:
{report_for_review}

사용자 요구 충족 여부, 조사 근거와의 일치, 논리와 완결성을 최종 확인하세요.
필요한 수정은 final_report에 직접 반영하세요.
""",
                        status,
                    ),
                    SupervisorAssessment,
                    "Supervisor Agent",
                )
                report_for_review = normalize_markdown(supervisor_review.final_report)
                record_detail(
                    f"Supervisor 최종 검토 {review_round}차",
                    format_supervisor_review(supervisor_review),
                )

                if supervisor_review.approved:
                    status.update(label="자동 검토가 완료되었습니다.", state="complete")
                    break

                if review_round == 1:
                    status.write("🔁 Supervisor 지적 사항을 Critic Agent가 다시 수정합니다.")
                    critique = parse_structured_output(
                        await run_stage(
                            agents["critic"],
                            f"""
사용자 요청:
{user_input}

현재 보고서:
{report_for_review}

Supervisor 수정 요구:
{list_as_markdown(supervisor_review.review_notes)}

지적 사항을 모두 반영하여 보고서를 다시 감수하고 수정하세요.
""",
                            status,
                        ),
                        CriticAssessment,
                        "Critic Agent",
                    )
                    report_for_review = normalize_markdown(critique.revised_report)
                    record_detail("Critic Agent 재감수", format_critic_review(critique))

            if supervisor_review is None:
                raise RuntimeError("최종 검토 결과가 생성되지 않았습니다.")
            if not supervisor_review.approved:
                status.update(
                    label="최대 검토 횟수에 도달해 현재 최선의 보고서를 제공합니다.",
                    state="complete",
                )

        report_for_review = normalize_markdown(report_for_review)
        chat_container.markdown(report_for_review)
        return report_for_review, workflow_details


user_input = st.chat_input("보고서 주제나 요청을 입력하세요")
if user_input:
    st.chat_message("user").markdown(user_input)
    st.session_state["messages"].append({"role": "user", "content": user_input})

    try:
        ai_answer, workflow_details = run_async(run_agent_workflow(user_input))
    except Exception as exc:
        st.error(f"에이전트 실행 중 오류가 발생했습니다: {exc}")
    else:
        st.session_state["messages"].append(
            {
                "role": "assistant",
                "content": ai_answer,
                "workflow_details": workflow_details,
            }
        )

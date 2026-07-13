from pathlib import Path
from typing import Any

from agents import Agent, AsyncOpenAI, OpenAIResponsesModel, function_tool
from pydantic import BaseModel, Field
from tavily import TavilyClient


AGENT_DIR = Path(__file__).parent / ".agent"
MAX_SEARCH_CONTENT_CHARS = 2_500


class ResearchSource(BaseModel):
    title: str = Field(description="출처 제목 또는 기관명")
    url: str = Field(description="출처 URL")
    supports: str = Field(description="이 출처가 뒷받침하는 핵심 내용")


class ResearchAssessment(BaseModel):
    sufficient: bool = Field(description="보고서 작성에 필요한 조사가 충분한지 여부")
    summary: str = Field(description="검증된 조사 결과 요약")
    search_queries: list[str] = Field(description="이번 조사에서 실제 사용한 검색어")
    findings: list[str] = Field(description="근거가 확인된 핵심 발견")
    sources: list[ResearchSource] = Field(description="검증에 사용한 주요 출처")
    gaps: list[str] = Field(description="아직 부족하거나 확인되지 않은 내용")
    follow_up_queries: list[str] = Field(description="추가 조사에 사용할 검색어")


class CriticAssessment(BaseModel):
    approved: bool = Field(description="수정된 보고서가 최종 검토 가능한 수준인지 여부")
    issues: list[str] = Field(description="발견한 문제와 적용한 개선 사항")
    revised_report: str = Field(description="개선 사항을 반영한 전체 보고서")


class SupervisorAssessment(BaseModel):
    approved: bool = Field(description="현재 결과물이 다음 단계로 진행 가능한 수준인지 여부")
    review_notes: list[str] = Field(description="검증 결과와 보완해야 할 사항")
    final_report: str = Field(description="검증·수정을 마친 결과물 또는 최종 보고서")


def read_instruction(prompt_name: str) -> str:
    """.agent 디렉터리에서 Markdown 에이전트 지침을 읽습니다."""
    agent_name = prompt_name.removesuffix(".md")
    instruction_path = AGENT_DIR / f"{agent_name}.md"
    return instruction_path.read_text(encoding="utf-8")


def create_agents(
    openai_api_key: str,
    tavily_api_key: str | None = None,
    model_name: str = "gpt-4o",
) -> dict[str, Agent[Any]]:
    """OpenAI Agents SDK 기반의 보고서 작성 에이전트 팀을 생성합니다."""
    openai_client = AsyncOpenAI(api_key=openai_api_key)
    model = OpenAIResponsesModel(model=model_name, openai_client=openai_client)

    tools = []
    if tavily_api_key:
        tavily_client = TavilyClient(api_key=tavily_api_key)

        @function_tool
        def search_on_web(query: str) -> list[dict[str, str]]:
            """웹에서 최신 자료를 검색하고 출처와 내용을 반환합니다."""
            response = tavily_client.search(
                query,
                search_depth="advanced",
                max_results=5,
                include_raw_content=False,
            )
            return [
                {
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "content": (result.get("content") or "")[
                        :MAX_SEARCH_CONTENT_CHARS
                    ],
                }
                for result in response.get("results", [])
            ]

        tools.append(search_on_web)

    supervisor = Agent(
        name="Supervisor",
        instructions=read_instruction("supervisor"),
        model=model,
        output_type=SupervisorAssessment,
    )
    researcher = Agent(
        name="Research Agent",
        instructions=read_instruction("research"),
        model=model,
        tools=tools,
        output_type=ResearchAssessment,
    )
    writer = Agent(
        name="Writing Agent",
        instructions=read_instruction("writer"),
        model=model,
    )
    critic = Agent(
        name="Critic Agent",
        instructions=read_instruction("critic"),
        model=model,
        output_type=CriticAssessment,
    )

    return {
        "supervisor": supervisor,
        "researcher": researcher,
        "writer": writer,
        "critic": critic,
    }

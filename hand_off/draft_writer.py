try:
    from langchain_openai import ChatOpenAI
except ImportError:
    from langchain.chat_models import ChatOpenAI

try:
    from langchain_core.prompts import ChatPromptTemplate
except ImportError:
    from langchain.prompts import ChatPromptTemplate

# 1. 맥북에서 실행 중인 llama-server 연결
# 답변 작성이므로 약간의 다양성을 위해 temperature를 0.4로 조정합니다.
llm = ChatOpenAI(
    base_url="http://localhost:8080/v1",
    api_key="not-needed",
    model="gemma-4-E2B-it",
    temperature=0.4
)

# 2. 초안 작성 프롬프트 설정
draft_prompt = ChatPromptTemplate.from_messages([
    ("system", """당신은 행정기관의 민원 답변 초안을 작성하는 유능한 전문 에이전트입니다.
주어진 [민원 데이터]와 앞선 에이전트가 분석한 [분류 및 분석 정보]를 바탕으로, 담당 공무원의 톤앤매너로 정중하고 신뢰감 있는 답변 초안을 작성하세요.

[답변 필수 포함 항목]
1. 민원 접수에 대한 감사 및 확인 인사 (민원신청번호 언급)
2. 분류된 카테고리와 시급성에 맞춘 현장 확인 및 조치 계획
3. 향후 처리 일정 안내 및 추가 문의 안내
4. 원활한 행정 발전을 위한 감사 인사 마무리"""),
    ("human", """
[분류 및 분석 정보]
- 카테고리: {category}
- 시급성: {urgency}
- 분석 이유: {reason}

[민원 데이터]
- 민원신청번호: {structure}
- 제목: {title}
- 본문: {content}
""")
])

# 3. 에이전트 체인 생성
draft_chain = draft_prompt | llm

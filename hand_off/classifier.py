from typing import Literal
from pydantic import BaseModel, Field

try:
    from langchain_openai import ChatOpenAI
except ImportError:
    from langchain.chat_models import ChatOpenAI

try:
    from langchain_core.prompts import ChatPromptTemplate
except ImportError:
    from langchain.prompts import ChatPromptTemplate

# 1. 맥북에서 실행 중인 llama-server 연결
llm = ChatOpenAI(
    base_url="http://localhost:8080/v1",
    api_key="not-needed",
    model="gemma-4-E2B-it",
    temperature=0.0  # 일관된 분류 결과를 위해 온도를 0으로 설정
)

# 2. 분류 결과 구조 정의 (Pydantic)
# Literal을 사용하여 모델이 지정된 카테고리 외의 딴소리를 하지 못하도록 강제합니다.
class ComplaintClassification(BaseModel):
    category: Literal["교통/도로", "환경/위생", "주택/건축", "일반행정", "기타"] = Field(
        description="민원 내용에 가장 적합한 카테고리를 선택하세요."
    )
    urgency: Literal["높음", "보통", "낮음"] = Field(
        description="민원의 시급성을 평가하세요."
    )
    reason: str = Field(
        description="이 카테고리와 시급성으로 분류한 이유를 1문장으로 요약하세요."
    )

# 3. 모델에 구조화된 출력(Structured Output) 적용
# 이 설정을 적용하면 gemma 모델이 반드시 위 JSON 규격에 맞춰 답변합니다.
classifier_agent = llm.with_structured_output(ComplaintClassification)

# 4. 분류 프롬프트 작성
prompt = ChatPromptTemplate.from_messages([
    ("system", "당신은 접수된 민원 데이터를 분석하고 대분류 카테고리를 지정하는 행정 에이전트입니다. 주어진 정보를 바탕으로 정확하게 분류하세요."),
    ("human", """
[민원 데이터]
- 민원신청번호: {structure}
- 제목: {title}
- 본문: {content}
""")
])

# 5. 에이전트 체인 생성
classification_chain = prompt | classifier_agent

# 6. 실전 테스트 데이터 실행
if __name__ == "__main__":
    # 테스트용 샘플 민원 데이터
    sample_complaint = {
        "structure": "개인 / 모바일접수",
        "title": "우리 동네 사거리 신호등 고장으로 사고 위험이 큽니다.",
        "content": "공덕역 4번 출구 앞 사거리 횡단보도 신호등이 어제 저녁부터 불이 들어오지 않고 있습니다. 지나다니는 차량과 보행자가 엉켜서 큰 사고가 날 것 같아요. 빠른 조치 부탁드립니다."
    }
    
    print("🚦 민원 데이터 분류 중...\n")
    
    # 에이전트 호출
    result = classification_chain.invoke({
        "structure": sample_complaint["structure"],
        "title": sample_complaint["title"],
        "content": sample_complaint["content"]
    })
    
    # 결과 출력
    print(f"📌 분류 결과 (카테고리): {result.category}")
    print(f"🚨 시급성: {result.urgency}")
    print(f"💬 분류 사유: {result.reason}")

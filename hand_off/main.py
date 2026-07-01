import sys
# 작성한 개별 에이전트 파일들로부터 체인을 불러옵니다.
from hand_off.classifier import classification_chain
from hand_off.draft_writer import draft_chain

def run_complaint_agent_pipeline(complaint_data: dict):
    print("🚦 [1/2] 민원 분류 에이전트 구동 중...")
    
    # 1. 분류 에이전트 실행
    try:
        class_result = classification_chain.invoke({
            "structure": complaint_data["structure"],
            "title": complaint_data["title"],
            "content": complaint_data["content"]
        })
    except Exception as e:
        print(f"❌ 분류 에이전트 실행 실패: {e}")
        return
        
    print(f"✅ 분류 완료! -> 카테고리: [{class_result.category}] | 시급성: [{class_result.urgency}]")
    print(f"💬 분석 사유: {class_result.reason}\n")
    
    print("📝 [2/2] 답변 초안 작성 에이전트로 데이터 이전(Handoff) 및 구동 중...")
    
    # 2. 핸드오프: 분류 결과 데이터(class_result)를 초안 에이전트 인풋에 결합하여 전달
    try:
        draft_result = draft_chain.invoke({
            "category": class_result.category,
            "urgency": class_result.urgency,
            "reason": class_result.reason,
            "structure": complaint_data["structure"],
            "title": complaint_data["title"],
            "content": complaint_data["content"]
        })
    except Exception as e:
        print(f"❌ 초안 작성 에이전트 실행 실패: {e}")
        return

    print("✅ 초안 작성 완료!\n")
    return class_result, draft_result.content


if __name__ == "__main__":
    # 테스트용 샘플 민원 데이터
    sample_complaint = {
        "structure": "제2026-0626호", # 원본의 구조 항목을 민원번호 형태로 예시 적용
        "title": "우리 동네 사거리 신호등 고장으로 사고 위험이 큽니다.",
        "content": "공덕역 4번 출구 앞 사거리 횡단보도 신호등이 어제 저녁부터 불이 들어오지 않고 있습니다. 지나다니는 차량과 보행자가 엉켜서 큰 사고가 날 것 같아요. 빠른 조치 부탁드립니다."
    }
    
    print("================== 🚀 민원 처리 시스템 가동 ==================")
    print(f"📋 민원 제목: {sample_complaint['title']}\n")
    
    # 파이프라인 가동
    classification, final_draft = run_complaint_agent_pipeline(sample_complaint)
    
    print("===================== 📝 최종 생성된 답변 초안 =====================")
    print(final_draft)
    print("==================================================================")

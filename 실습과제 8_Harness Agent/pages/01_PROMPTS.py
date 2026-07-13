import streamlit as st
from app_agents import create_agents
import base64

st.title("Agent 별 프롬프트 테스트")

st.markdown("아래의 프롬프트 적용 후 `main` 에서 바로 테스트 해볼 수 있습니다.")

with st.expander("멀티 에이전트 설계도"):
    st.image("assets/multi-agent.png")

if "OPENAI_API_KEY" not in st.session_state:
    st.warning("먼저 main 페이지에서 OpenAI API 키를 설정해 주세요.")
    st.stop()

agent_config = (
    st.session_state["OPENAI_API_KEY"],
    st.session_state.get("TAVILY_API_KEY"),
    st.session_state.get("model_name", "gpt-4o"),
)
if st.session_state.get("agent_config") != agent_config:
    st.session_state["agents"] = create_agents(*agent_config)
    st.session_state["agent_config"] = agent_config

tab1, tab2, tab3, tab4 = st.tabs(["Supervisor", "Researcher", "Writer", "Critic"])


def download_markdown(text, filename, label="Supervisor"):
    b64 = base64.b64encode(text.encode()).decode()
    href = f'<a href="data:text/markdown;base64,{b64}" download="{filename}">{label} 프롬프트 다운로드</a>'
    return href


with tab1:
    update_btn1 = st.button("프롬프트 업데이트", key="supervisor_btn", type="primary")
    msg1 = st.empty()
    supervisor_prompt = st.text_area(
        "Supervisor Prompt",
        st.session_state["agents"]["supervisor"].instructions,
        height=1200,
    )

    if update_btn1:
        st.session_state["agents"]["supervisor"].instructions = supervisor_prompt
        msg1.markdown(f"**Supervisor 프롬프트가 업데이트되었습니다.**")

with tab2:
    update_btn2 = st.button("프롬프트 업데이트", key="researcher_btn", type="primary")
    msg2 = st.empty()
    researcher_prompt = st.text_area(
        "Researcher Prompt",
        st.session_state["agents"]["researcher"].instructions,
        height=1200,
    )

    if update_btn2:
        st.session_state["agents"]["researcher"].instructions = researcher_prompt
        msg2.markdown(f"**Researcher 프롬프트가 업데이트되었습니다.**")
with tab3:
    update_btn3 = st.button("프롬프트 업데이트", key="writer_btn", type="primary")
    msg3 = st.empty()
    writer_prompt = st.text_area(
        "Writer Prompt", st.session_state["agents"]["writer"].instructions, height=1200
    )

    if update_btn3:
        st.session_state["agents"]["writer"].instructions = writer_prompt
        msg3.markdown(f"**Writer 프롬프트가 업데이트되었습니다.**")
with tab4:
    update_btn4 = st.button("프롬프트 업데이트", key="critic_btn", type="primary")
    msg4 = st.empty()
    critic_prompt = st.text_area(
        "Critic Prompt", st.session_state["agents"]["critic"].instructions, height=1200
    )

    if update_btn4:
        st.session_state["agents"]["critic"].instructions = critic_prompt
        msg4.markdown(f"**Critic 프롬프트가 업데이트되었습니다.**")


# 사이드바에 다운로드 링크 추가
with st.sidebar:
    st.markdown("### 프롬프트 다운로드")
    st.markdown(
        download_markdown(
            supervisor_prompt,
            "supervisor.md",
            "Supervisor",
        ),
        unsafe_allow_html=True,
    )
    st.markdown(
        download_markdown(
            researcher_prompt,
            "research.md",
            "Researcher",
        ),
        unsafe_allow_html=True,
    )
    st.markdown(
        download_markdown(
            writer_prompt,
            "writer.md",
            "Writer",
        ),
        unsafe_allow_html=True,
    )
    st.markdown(
        download_markdown(
            critic_prompt,
            "critic.md",
            "Critic",
        ),
        unsafe_allow_html=True,
    )

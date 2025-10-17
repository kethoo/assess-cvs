import streamlit as st
from cv_assessment import CVAssessmentSystem
import tempfile
import os
import re
from docx import Document
import pandas as pd
import json

# ------------------- STREAMLIT CONFIG -------------------

st.set_page_config(page_title="Deep CV Assessment System", layout="wide")
st.title("📄 Deep CV Assessment System")

# ------------------- SESSION STATE INITIALIZATION -------------------

if 'expert_section_text' not in st.session_state:
    st.session_state.expert_section_text = ""

if 'custom_criteria' not in st.session_state:
    st.session_state.custom_criteria = None

if 'criteria_generated' not in st.session_state:
    st.session_state.criteria_generated = False

# ------------------- API KEY -------------------

api_key = st.text_input("🔑 Enter OpenAI API Key", type="password")

# ------------------- UPLOAD TENDER -------------------

req_file = st.file_uploader("📄 Upload Tender / Job Description", type=["pdf", "docx", "doc"])
tender_text = ""
tender_path = None

if req_file:
    suffix = os.path.splitext(req_file.name)[1] or ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(req_file.read())
        tender_path = tmp.name

    st.success(f"✅ Tender uploaded: {req_file.name}")

    system_temp = CVAssessmentSystem(api_key=api_key or None)
    tender_text = system_temp.load_job_requirements(tender_path)
    st.info("📘 Tender text loaded successfully.")

# ------------------- ROLE FOCUS SELECTION -------------------

st.markdown("### 🎯 Select Evaluation Focus")
role_focus = st.radio(
    "Choose the type of assessment focus:",
    ["Specific Role (80/20 weighting)", "General Role (100% general weighting)"],
    index=0,
)

# ------------------- SUPPORT FUNCTIONS -------------------

def extract_expert_section_llm(full_text: str, expert_name: str, api_key: str) -> str:
    """Use LLM to intelligently extract expert section requirements"""
    if not full_text or not expert_name or not api_key:
        return ""
    try:
        import openai
        client = openai.OpenAI(api_key=api_key)
        prompt = f"""You are analyzing a tender document to extract requirements for a specific expert position.

EXPERT POSITION TO EXTRACT: "{expert_name}"

Extract ALL relevant sections describing this expert’s role, qualifications, experience, and deliverables.
Separate multiple matches with "---SECTION BREAK---".
Return ONLY the extracted text, no commentary.
DOCUMENT:
{full_text[:30000]}"""
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Extract only the requested section, no explanations."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=4000,
        )
        extracted = resp.choices[0].message.content.strip()
        if extracted == "NOT_FOUND" or not extracted:
            return ""
        return extracted.replace("---SECTION BREAK---", "\n\n" + "-" * 60 + "\n\n")
    except Exception as e:
        st.error(f"LLM extraction error: {e}")
        return ""


def generate_criteria_and_weights(expert_section: str, general_context: str, api_key: str, total_weight: int = 80) -> dict:
    """Generate custom assessment criteria with weights"""
    if not expert_section or not api_key:
        return None
    try:
        import openai
        client = openai.OpenAI(api_key=api_key)
        prompt = f"""You are analyzing tender requirements to generate assessment criteria with appropriate weights.
Identify 6–10 key criteria and assign weights that total {total_weight}%.
Use JSON format:
{{"criteria": [{{"name": "...", "weight": 25, "rationale": "..."}}]}}
REQUIREMENTS:
{expert_section[:8000]}
GENERAL CONTEXT:
{general_context[:2000]}"""
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Return only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=2000,
        )
        text = resp.choices[0].message.content.strip()
        text = re.sub(r"^```(json)?", "", text)
        text = re.sub(r"```$", "", text)
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match:
            text = match.group(1)
        data = json.loads(text)
        total = sum(c['weight'] for c in data['criteria'])
        if abs(total - total_weight) > 2:
            factor = total_weight / total
            for c in data['criteria']:
                c['weight'] = round(c['weight'] * factor, 1)
        return data
    except Exception as e:
        st.error(f"Error generating criteria: {e}")
        return None

# ------------------- SPECIFIC ROLE FLOW -------------------

expert_name = ""

if role_focus == "Specific Role (80/20 weighting)":
    st.markdown("### 🧩 Enter the Expert Role Title")
    expert_name = st.text_input(
        "Example: Key Expert 1, Team Leader",
        placeholder="Type 'Key Expert 1', 'Team Leader', etc.",
        key="expert_name_input"
    )

    st.info("💡 **AI Extraction**: The system will use GPT to intelligently identify and extract all requirements for this expert position.")

    extract_button = st.button("🔍 Extract Expert Section (AI-Powered)", disabled=not (req_file and expert_name.strip() and tender_path and api_key))
    if extract_button:
        with st.spinner("🤖 Extracting requirements..."):
            section = extract_expert_section_llm(tender_text, expert_name, api_key)
            if section:
                st.session_state.expert_section_text = section
                st.success(f"✅ Extracted section for: {expert_name}")
            else:
                st.warning("⚠️ Could not find relevant section.")

    if req_file and expert_name.strip():
        st.markdown("### 📝 Expert Section Preview & Edit")
        edited_section = st.text_area(
            "Expert Section Content (editable)",
            value=st.session_state.expert_section_text,
            height=400
        )
        st.session_state.expert_section_text = edited_section

        # ------------------- GENERATE CRITERIA (SPECIFIC ROLE) -------------------

        if st.session_state.expert_section_text and api_key:
            st.markdown("---")
            st.markdown("### 🎯 Generate Custom Assessment Criteria (80/20 weighting)")
            if st.button("🧠 Generate Criteria (Specific Role)", disabled=not st.session_state.expert_section_text):
                with st.spinner("🤖 Generating criteria and weights..."):
                    criteria = generate_criteria_and_weights(st.session_state.expert_section_text, tender_text, api_key, total_weight=80)
                    if criteria:
                        st.session_state.custom_criteria = criteria
                        st.session_state.criteria_generated = True
                        st.success("✅ Custom criteria generated!")

            if st.session_state.criteria_generated and st.session_state.custom_criteria:
                df = pd.DataFrame([
                    {"Criterion": c["name"], "Weight (%)": c["weight"], "Rationale": c["rationale"]}
                    for c in st.session_state.custom_criteria["criteria"]
                ])
                general_row = pd.DataFrame([{
                    "Criterion": "General Tender Context",
                    "Weight (%)": 20,
                    "Rationale": "Understanding of overall project and regional context"
                }])
                df_display = pd.concat([general_row, df], ignore_index=True)
                total = df_display["Weight (%)"].sum()
                with st.expander("📋 View Generated Criteria"):
                    st.dataframe(df_display, use_container_width=True, hide_index=True)
                if total == 100:
                    st.success("✅ Weights sum to 100% - ready for assessment.")
                else:
                    st.warning(f"⚠️ Weights sum to {total}% (should be 100%).")

# ------------------- GENERAL ROLE FLOW -------------------

if role_focus == "General Role (100% general weighting)":
    st.markdown("### 🧠 Generate General Assessment Criteria (100%)")
    if st.button("🧠 Generate Criteria (General Role)", disabled=not (req_file and api_key)):
        with st.spinner("🤖 Analyzing tender to generate general evaluation criteria..."):
            criteria = generate_criteria_and_weights(tender_text, tender_text, api_key, total_weight=100)
            if criteria:
                st.session_state.custom_criteria = criteria
                st.session_state.criteria_generated = True
                st.success("✅ General role criteria generated!")

    if st.session_state.criteria_generated and st.session_state.custom_criteria:
        df = pd.DataFrame([
            {"Criterion": c["name"], "Weight (%)": c["weight"], "Rationale": c["rationale"]}
            for c in st.session_state.custom_criteria["criteria"]
        ])
        with st.expander("📋 View Generated Criteria"):
            st.dataframe(df, use_container_width=True, hide_index=True)
        total = df["Weight (%)"].sum()
        if total == 100:
            st.success("✅ Weights sum to 100% - ready for assessment.")
        else:
            st.warning(f"⚠️ Weights sum to {total}% (should be 100%).")

# ------------------- UPLOAD CVS -------------------

cv_files = st.file_uploader(
    "👤 Upload Candidate CVs",
    type=["pdf", "docx", "doc"],
    accept_multiple_files=True
)

# ------------------- RUN ASSESSMENT -------------------

st.markdown("---")
st.markdown("### 🚀 Step 4: Run Assessment")

st.info(f"🧩 Current Mode: {role_focus}")

if st.button("🚀 Run Assessment") and req_file and cv_files and (api_key or os.getenv("OPENAI_API_KEY")):
    with tempfile.TemporaryDirectory() as tmpdir:
        cv_folder = os.path.join(tmpdir, "cvs")
        os.makedirs(cv_folder, exist_ok=True)
        for file in cv_files:
            path = os.path.join(cv_folder, file.name)
            with open(path, "wb") as f:
                f.write(file.read())

        st.info("⏳ Processing CVs...")
        system = CVAssessmentSystem(api_key=api_key or None)

        # Role-based weighting
        if role_focus == "Specific Role (80/20 weighting)":
            combined_text = (
                f"--- GENERAL TENDER CONTEXT (20% weight) ---\n\n"
                f"{tender_text[:5000]}\n\n"
                f"--- SPECIFIC EXPERT REQUIREMENTS (80% weight) ---\n\n"
                f"{st.session_state.expert_section_text or tender_text}"
            )
        else:
            combined_text = f"--- GENERAL ROLE (100% weighting) ---\n\n{tender_text}"

        system.job_requirements = combined_text
        custom = st.session_state.custom_criteria if st.session_state.criteria_generated else None
        results = system.process_cv_folder(cv_folder, mode="critical", custom_criteria=custom)

        st.success(f"✅ Processed {len(results)} candidate(s)")

        ranked = sorted(results, key=lambda x: x.get("final_score", 0), reverse=True)
        st.markdown("## 🏆 Candidate Ranking")
        st.table([
            {"Rank": i + 1, "Candidate": r["candidate_name"], "Final Score": f"{r['final_score']:.2f}"}
            for i, r in enumerate(ranked)
        ])
        for r in ranked:
            with st.expander(f"{r['candidate_name']} — Critical Evaluation"):
                report = r["report"]
                if "✂️ Tailoring Suggestions" in report:
                    main, tailoring = report.split("✂️ Tailoring Suggestions", 1)
                    st.markdown(main)
                    with st.expander("✂️ Tailoring Suggestions"):
                        st.markdown("✂️ Tailoring Suggestions" + tailoring)
                else:
                    st.markdown(report)
                st.markdown(f"**🧮 Final Score:** {r['final_score']:.2f} / 1.00")

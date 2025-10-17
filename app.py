import streamlit as st
from cv_assessment import CVAssessmentSystem
import tempfile
import os
import re
from docx import Document
import pandas as pd

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

# ------------------- MODE SELECTION (LOCKED TO CRITICAL NARRATIVE) -------------------

mode = "Critical Narrative"  # Fixed mode

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

    # Load tender text
    system_temp = CVAssessmentSystem(api_key=api_key or None)
    tender_text = system_temp.load_job_requirements(tender_path)
    st.info("📘 Tender text loaded successfully.")

# ------------------- EXPERT NAME -------------------

st.markdown("### 🎯 Enter the Expert Role Title")
expert_name = st.text_input(
    "Example: Key Expert 1, Team Leader",
    placeholder="Type 'Key Expert 1', 'Key expert 1', etc.",
    key="expert_name_input"
)

# ------------------- ROLE FOCUS SELECTION -------------------

st.markdown("### 🎯 Select Evaluation Focus")
role_focus = st.radio(
    "Choose the type of assessment focus:",
    ["Specific Role (80/20 weighting)", "General Role (100% general weighting)"],
    index=0,
)

# ------------------- EXTRACTION FUNCTIONS -------------------

def extract_expert_section_llm(full_text: str, expert_name: str, api_key: str) -> str:
    """Use LLM to intelligently extract expert section requirements"""
    if not full_text or not expert_name or not api_key:
        return ""
    
    try:
        import openai
        client = openai.OpenAI(api_key=api_key)
        
        prompt = f"""You are analyzing a tender document to extract requirements for a specific expert position.

EXPERT POSITION TO EXTRACT: "{expert_name}"

Your task:
1. Find ALL sections in the document that describe requirements, qualifications, responsibilities, or deliverables for this specific expert position
2. Extract the COMPLETE text for this position, including:
   - Job title and role description
   - Required qualifications (education, certifications)
   - Required experience (years, specific domains)
   - Technical skills and competencies
   - Responsibilities and tasks
   - Deliverables and outputs expected
   - Language requirements
   - Any other relevant requirements

IMPORTANT:
- Extract ONLY information relevant to "{expert_name}"
- Do NOT include information about other expert positions (e.g., if extracting Key Expert 1, exclude Key Expert 2, 3, etc.)
- Do NOT include general project background, budget, or administrative sections
- If the position appears in multiple places in the document, extract ALL occurrences
- Preserve the original text as much as possible
- If you find multiple sections, separate them with "---SECTION BREAK---"

TENDER DOCUMENT:
{full_text[:30000]}

Return ONLY the extracted text for "{expert_name}". If nothing is found, return exactly: "NOT_FOUND"
"""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a precise document extraction assistant. Extract only the requested content."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=4000
        )
        
        extracted = response.choices[0].message.content.strip()
        
        if extracted == "NOT_FOUND" or not extracted:
            return ""
        
        # Replace section breaks with consistent separator
        extracted = extracted.replace("---SECTION BREAK---", "\n\n" + "-"*60 + "\n\n")
        
        return extracted
    
    except Exception as e:
        st.error(f"LLM extraction error: {e}")
        return ""

# ------------------- EXTRACT BUTTON -------------------

st.info("💡 **AI Extraction**: The system will use GPT to intelligently identify and extract all requirements specific to your chosen expert position, automatically excluding other positions and irrelevant sections.")

extract_button = st.button("🔍 Extract Expert Section (AI-Powered)", disabled=not (req_file and expert_name.strip() and tender_path and api_key))

if extract_button:
    with st.spinner("🤖 Using AI to intelligently extract requirements for this position..."):        
        expert_section = extract_expert_section_llm(tender_text, expert_name, api_key)
        
        if expert_section:
            st.session_state.expert_section_text = expert_section
            # Count sections (separated by the long dashes)
            num_sections = expert_section.count('------------------------------------------------------------') + 1
            st.success(f"✅ Extracted {len(expert_section)} characters from {num_sections} section(s) for: {expert_name}")
            st.info("📜 Scroll down to review the extracted content in the text area below ⬇️")
        else:
            st.session_state.expert_section_text = ""
            st.warning("⚠️ AI couldn't find specific requirements for this position. Try:\n- Different spelling (e.g., 'Key Expert 1' vs 'Expert 1')\n- Or paste content manually below")

# ------------------- EDITABLE PREVIEW -------------------

if req_file and expert_name.strip():
    st.markdown("### 📝 Expert Section Preview & Edit")
    
    edited_section = st.text_area(
        "Expert Section Content (editable)",
        value=st.session_state.expert_section_text,
        height=400,
        help="Edit as needed. This will be used with 80% weight if 'Specific Role' mode is selected."
    )
    
    # Update session state if user edits
    st.session_state.expert_section_text = edited_section

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

        # 🔹 Determine the weighting based on role_focus
        if role_focus == "Specific Role (80/20 weighting)":
            if st.session_state.expert_section_text.strip():
                combined_text = (
                    f"--- GENERAL TENDER CONTEXT (20% weight) ---\n\n"
                    f"{tender_text[:5000]}\n\n"
                    f"--- SPECIFIC EXPERT REQUIREMENTS (80% weight) ---\n\n"
                    f"{st.session_state.expert_section_text}"
                )
            else:
                combined_text = f"--- FULL REQUIREMENTS (100%) ---\n\n{tender_text}"
        else:
            combined_text = f"--- GENERAL ROLE (100% weighting) ---\n\n{tender_text}"

        system.job_requirements = combined_text
        
        results = system.process_cv_folder(cv_folder, mode="critical")

        st.success(f"✅ Processed {len(results)} candidate(s)")

        # ------------------- DISPLAY RESULTS -------------------

        ranked = sorted(results, key=lambda x: x.get("final_score", 0), reverse=True)
        st.markdown("## 🏆 Candidate Ranking")
        st.table([
            {
                "Rank": i + 1,
                "Candidate": r["candidate_name"],
                "Final Score": f"{r['final_score']:.2f}"
            }
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

else:
    if not api_key and not os.getenv("OPENAI_API_KEY"):
        st.warning("⚠️ Enter OpenAI API key to enable AI extraction and assessment")
    elif not req_file:
        st.warning("⚠️ Upload tender file")
    elif not cv_files:
        st.warning("⚠️ Upload CVs")

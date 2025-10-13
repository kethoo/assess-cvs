import streamlit as st
from cv_assessment import CVAssessmentSystem
import tempfile
import os
import re
from docx import Document

# ------------------- STREAMLIT CONFIG -------------------

st.set_page_config(page_title="Deep CV Assessment System", layout="wide")
st.title("📄 Deep CV Assessment System")

# ------------------- SESSION STATE INITIALIZATION (MUST BE FIRST) -------------------

if 'expert_section_text' not in st.session_state:
    st.session_state.expert_section_text = ""

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
    
    # Debug: Show what's in session state
    if st.session_state.expert_section_text:
        st.write(f"🔍 Debug: Session state has {len(st.session_state.expert_section_text)} characters")
    
    edited_section = st.text_area(
        "Expert Section Content (editable)",
        value=st.session_state.expert_section_text,
        height=400,
        help="Edit as needed. This will be used with 80% weight."
    )
    
    # Update session state if user edits
    st.session_state.expert_section_text = edited_section
    
    if st.session_state.expert_section_text:
        num_sections = st.session_state.expert_section_text.count('----------------------------------------------------------') + 1
        st.info(f"📊 {len(st.session_state.expert_section_text)} chars | {num_sections} section(s) found | Sections separated by dashes")
    else:
        st.info("👆 Click 'Extract Expert Section' button above to automatically extract, or paste content manually here")

# ------------------- UPLOAD CVS -------------------

cv_files = st.file_uploader(
    "👤 Upload Candidate CVs",
    type=["pdf", "docx", "doc"],
    accept_multiple_files=True
)

# ------------------- RUN ASSESSMENT -------------------

if st.button("🚀 Run Assessment") and req_file and cv_files and expert_name.strip() and (api_key or os.getenv("OPENAI_API_KEY")):
    with tempfile.TemporaryDirectory() as tmpdir:
        cv_folder = os.path.join(tmpdir, "cvs")
        os.makedirs(cv_folder, exist_ok=True)

        for file in cv_files:
            path = os.path.join(cv_folder, file.name)
            with open(path, "wb") as f:
                f.write(file.read())

        st.info("⏳ Processing CVs...")

        system = CVAssessmentSystem(api_key=api_key or None)
        expert_section = st.session_state.expert_section_text

        if not expert_section:
            st.warning("⚠️ No expert section. Using full tender.")
            combined_text = tender_text
        else:
            combined_text = (
                f"--- GENERAL TENDER CONTEXT (20% weight) ---\n\n"
                f"{tender_text[:5000]}\n\n"
                f"--- SPECIFIC EXPERT REQUIREMENTS (80% weight) ---\n\n"
                f"{expert_section}"
            )
            st.success(f"✅ Using expert section")

        system.job_requirements = combined_text
        results = system.process_cv_folder(cv_folder, mode="critical")

        st.success(f"✅ Processed {len(results)} candidate(s)")

        # ------------------- DISPLAY RESULTS (CRITICAL NARRATIVE MODE) -------------------

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

# ------------------- WARNINGS -------------------

else:
    if not api_key and not os.getenv("OPENAI_API_KEY"):
        st.warning("⚠️ Enter OpenAI API key to enable AI extraction and assessment")
    elif not expert_name.strip():
        st.warning("⚠️ Enter expert role title")
    elif not req_file:
        st.warning("⚠️ Upload tender file")
    elif not cv_files:
        st.warning("⚠️ Upload CVs")

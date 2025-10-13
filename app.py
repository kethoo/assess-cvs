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

if 'extracted_section' not in st.session_state:
    st.session_state.extracted_section = ""
if 'section_extracted' not in st.session_state:
    st.session_state.section_extracted = False

# ------------------- API KEY -------------------

api_key = st.text_input("🔑 Enter OpenAI API Key", type="password")

# ------------------- MODE SELECTION -------------------

mode = st.radio("Select Evaluation Mode:", ["Structured (Dashboard)", "Critical Narrative"])

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

def extract_expert_section(file_path: str, expert_name: str) -> str:
    """Extract expert section from Word document"""
    if not file_path or not expert_name:
        return ""
    
    if not file_path.lower().endswith(('.docx', '.doc')):
        return extract_from_text(tender_text, expert_name)
    
    try:
        doc = Document(file_path)
        result_parts = []
        started = False
        current_text = []
        
        # Extract number from expert name
        expert_num_match = re.search(r'(\d+)', expert_name)
        my_number = expert_num_match.group(1) if expert_num_match else None
        
        def is_bold(para):
            if not para.runs:
                return False
            bold_runs = sum(1 for r in para.runs if r.bold)
            return bold_runs > len(para.runs) / 2
        
        def is_different_expert(text):
            if not my_number:
                return False
            matches = re.findall(r'(?:key\s+expert|expert|ke)\s*[:\-\(]?\s*(?:ke\s*)?(\d+)', text, re.IGNORECASE)
            for found_num in matches:
                if found_num != my_number:
                    return True
            return False
        
        # Check if this is the last expert
        all_text = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        found_start = False
        is_last_expert = True
        
        for txt in all_text:
            if not found_start:
                if expert_name.lower() in txt.lower():
                    found_start = True
            elif found_start:
                if is_different_expert(txt):
                    is_last_expert = False
                    break
        
        # Extract the section
        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            
            # Start extraction
            if not started:
                if expert_name.lower() in text.lower():
                    started = True
                    current_text.append(text)
                continue
            
            # Once started...
            if started:
                # STOP: Different expert
                if is_different_expert(text):
                    break
                
                # STOP: Last expert + bold
                if is_last_expert and is_bold(para):
                    break
                
                # CONTINUE: Bold subsection (not last expert)
                if not is_last_expert and is_bold(para):
                    if current_text:
                        result_parts.append(' '.join(current_text))
                        current_text = []
                    result_parts.append('\n----------------------------------------------------------\n')
                    result_parts.append(text)
                else:
                    current_text.append(text)
        
        # Add remaining
        if current_text:
            result_parts.append(' '.join(current_text))
        
        return '\n\n'.join(result_parts).strip()
    
    except Exception as e:
        st.error(f"Extraction error: {e}")
        return ""


def extract_from_text(full_text: str, expert_name: str) -> str:
    """Fallback: extract from plain text (for PDFs)"""
    if not full_text or not expert_name:
        return ""
    
    num_match = re.search(r'(\d+)', expert_name)
    my_num = num_match.group(1) if num_match else None
    
    if my_num:
        pattern = rf"({re.escape(expert_name)}.*?)(?=(?:key\s+expert|expert|ke)\s*[:\-\(]?\s*(?!{my_num})\d+|$)"
    else:
        pattern = rf"({re.escape(expert_name)}.*?)(?=expert\s+\d+|$)"
    
    match = re.search(pattern, full_text, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    
    return ""

# ------------------- EXTRACT BUTTON -------------------

extract_button = st.button("🔍 Extract Expert Section", disabled=not (req_file and expert_name.strip() and tender_path))

if extract_button:
    with st.spinner("Extracting..."):
        st.write(f"Debug: Looking for '{expert_name}'")
        
        if req_file.name.lower().endswith('.docx'):
            expert_section = extract_expert_section(tender_path, expert_name)
        else:
            expert_section = extract_from_text(tender_text, expert_name)
        
        st.write(f"Debug: Extracted {len(expert_section)} characters")
        
        if expert_section:
            st.session_state.extracted_section = expert_section
            st.session_state.section_extracted = True
            st.success(f"✅ Extracted {len(expert_section)} characters for: {expert_name}")
            # Force rerun to update text area
            try:
                st.rerun()
            except AttributeError:
                st.experimental_rerun()
        else:
            st.session_state.extracted_section = ""
            st.session_state.section_extracted = False
            st.warning("⚠️ Nothing found. Try different spelling or paste manually below.")

# ------------------- EDITABLE PREVIEW -------------------

if req_file and expert_name.strip():
    st.markdown("### 📝 Expert Section Preview & Edit")
    
    # Force text area to show current session state value
    current_value = st.session_state.extracted_section
    
    edited_section = st.text_area(
        "Expert Section Content (editable)",
        value=current_value,
        height=400,
        help="Edit as needed. This will be used with 80% weight.",
        key="expert_section_editor"
    )
    
    # Only update if user actually edited (different from current)
    if edited_section != current_value:
        st.session_state.extracted_section = edited_section
    
    if current_value:
        separator_count = current_value.count('----------------------------------------------------------')
        st.info(f"📊 {len(current_value)} chars | {separator_count + 1} subsections")

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
        expert_section = st.session_state.extracted_section

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
        results = system.process_cv_folder(
            cv_folder,
            mode="critical" if mode == "Critical Narrative" else "structured"
        )

        st.success(f"✅ Processed {len(results)} candidate(s)")

        # ------------------- DISPLAY RESULTS -------------------

        if mode == "Structured (Dashboard)":
            ranked = sorted(results, key=lambda x: x.overall_score, reverse=True)
            st.markdown("## 🏆 Candidate Ranking")
            st.table([
                {
                    "Rank": i + 1,
                    "Candidate": r.candidate_name,
                    "Score": r.overall_score,
                    "Fit Level": r.fit_level
                }
                for i, r in enumerate(ranked)
            ])

        else:
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
    if not expert_name.strip():
        st.warning("⚠️ Enter expert role title")
    elif not req_file:
        st.warning("⚠️ Upload tender file")
    elif not cv_files:
        st.warning("⚠️ Upload CVs")

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
    """Extract ALL occurrences of expert section from Word document"""
    if not file_path or not expert_name:
        return ""
    
    if not file_path.lower().endswith(('.docx', '.doc')):
        return extract_from_text(tender_text, expert_name)
    
    try:
        doc = Document(file_path)
        all_sections = []  # Will hold multiple extracted sections
        current_section = []
        started = False
        
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
        
        def is_major_section(text):
            """Check if this is a major document section break"""
            text_lower = text.lower().strip()
            major_keywords = [
                'part b', 'part a', 'annex', 'background information', 
                'contracting authority', 'location and duration', 
                'reports and deliverables', 'tender specifications'
            ]
            return any(kw in text_lower for kw in major_keywords)
        
        # Extract ALL occurrences
        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            
            # Check if this starts our expert section (must be a header, not just a mention)
            if expert_name.lower() in text.lower():
                # Only start new section if this looks like a header/title
                # (short line, or has colon, or is bold, or starts with the expert name)
                is_header = (
                    len(text) < 150 or  # Short lines are usually headers
                    ':' in text or  # Has colon like "Key expert 1 (KE 1):"
                    is_bold(para) or  # Bold text
                    text.lower().startswith(expert_name.lower()[:10])  # Starts with expert name
                )
                
                if is_header:
                    # Save previous section if exists
                    if current_section:
                        all_sections.append(' '.join(current_section))
                        current_section = []
                    
                    # Start new section
                    started = True
                    current_section.append(text)
                    continue
            
            # If we're currently extracting
            if started:
                # STOP: Different expert
                if is_different_expert(text):
                    # Save this section
                    if current_section:
                        all_sections.append(' '.join(current_section))
                        current_section = []
                    started = False
                    continue
                
                # STOP: Major section break (like Part B)
                if is_bold(para) and is_major_section(text):
                    # Save this section
                    if current_section:
                        all_sections.append(' '.join(current_section))
                        current_section = []
                    started = False
                    continue
                
                # CONTINUE: Regular content
                current_section.append(text)
        
        # Add last section if exists
        if current_section:
            all_sections.append(' '.join(current_section))
        
        # Combine all sections with separator
        if all_sections:
            return '\n\n----------------------------------------------------------\n\n'.join(all_sections).strip()
        
        return ""
    
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
        if req_file.name.lower().endswith('.docx'):
            expert_section = extract_expert_section(tender_path, expert_name)
        else:
            expert_section = extract_from_text(tender_text, expert_name)
        
        if expert_section:
            st.session_state.expert_section_text = expert_section
            # Count sections (separated by the long dashes)
            num_sections = expert_section.count('----------------------------------------------------------') + 1
            st.success(f"✅ Extracted {len(expert_section)} characters from {num_sections} section(s) for: {expert_name}")
            st.info("Scroll down to see the extracted content in the text area below ⬇️")
        else:
            st.session_state.expert_section_text = ""
            st.warning("⚠️ Nothing found. Try different spelling or paste manually below.")

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

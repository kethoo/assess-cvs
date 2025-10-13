import streamlit as st
from cv_assessment import CVAssessmentSystem
import tempfile
import os
import re
from docx import Document

# ------------------- STREAMLIT CONFIG -------------------

st.set_page_config(page_title="Deep CV Assessment System", layout="wide")
st.title("📄 Deep CV Assessment System")

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

st.markdown("### 🎯 Enter the Expert Role Title (exactly as in the tender file)")
expert_name = st.text_input(
    "Example: Key Expert 1, Team Leader",
    placeholder="Enter the expert role title (e.g., 'Key Expert 1', 'Expert 2', 'KE 3')"
)

# ------------------- SESSION STATE INITIALIZATION -------------------

if 'extracted_section' not in st.session_state:
    st.session_state.extracted_section = ""
if 'section_extracted' not in st.session_state:
    st.session_state.section_extracted = False

# ------------------- INTELLIGENT STRUCTURE-AWARE EXTRACTION -------------------

def extract_expert_section_with_structure(file_path: str, expert_name: str) -> str:
    """
    Extract expert section from Word document with intelligent structure detection.
    - Starts from the specified expert
    - Adds separators (----) when encountering bold sections WITHIN the expert
    - Stops at: next numbered expert OR (if last expert) bold section indicating new document part
    """
    if not file_path or not expert_name:
        return ""
    
    # Only works with Word documents for now
    if not file_path.lower().endswith(('.docx', '.doc')):
        return extract_expert_section_fallback(tender_text, expert_name)
    
    try:
        doc = Document(file_path)
        extracted_parts = []
        started = False
        current_section = []
        found_next_expert = False
        
        # Regex to detect other numbered experts (to know when to stop)
        expert_pattern = re.compile(
            r'\b(Key\s*Expert|Expert|KE|Non[-\s]*Key\s*Expert)\s*[#\-]?\s*(\d+|[IVX]+)\b',
            re.IGNORECASE
        )
        
        # Bold sections that indicate END of document sections (not part of expert description)
        end_section_keywords = [
            'annex', 'annexe', 'general conditions', 'terms and conditions', 
            'terms of reference', 'appendix', 'attachment', 'payment terms',
            'contract', 'award criteria', 'submission', 'deadline', 'evaluation',
            'administrative', 'technical specifications', 'deliverables'
        ]
        
        # Bold sections that are PART OF expert descriptions (should continue)
        expert_description_keywords = [
            'qualifications', 'education', 'experience', 'skills', 'responsibilities',
            'tasks', 'duties', 'requirements', 'competencies', 'expertise',
            'knowledge', 'languages', 'language', 'background', 'role', 'objective'
        ]
        
        # Extract the number from the target expert name
        target_match = re.search(r'(\d+|[IVX]+)', expert_name)
        target_number = target_match.group(1) if target_match else None
        
        def is_bold(paragraph):
            """Check if paragraph has bold text"""
            if not paragraph.runs:
                return False
            # Check if majority of runs are bold
            bold_runs = sum(1 for run in paragraph.runs if run.bold)
            return bold_runs > len(paragraph.runs) / 2
        
        def is_different_expert(text):
            """Check if this is a different numbered expert"""
            match = expert_pattern.search(text)
            if match and target_number:
                found_number = match.group(2)
                # Different expert number found
                return found_number != target_number
            return False
        
        def is_end_section(text):
            """Check if this bold text indicates end of expert sections"""
            text_lower = text.lower()
            return any(keyword in text_lower for keyword in end_section_keywords)
        
        def is_expert_description(text):
            """Check if this bold text is part of expert description"""
            text_lower = text.lower()
            return any(keyword in text_lower for keyword in expert_description_keywords)
        
        # First pass: check if there's another expert after this one
        all_paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        start_index = -1
        
        for i, text in enumerate(all_paragraphs):
            if expert_name.lower() in text.lower():
                start_index = i
                break
        
        if start_index >= 0:
            # Look ahead to see if there's another expert
            for text in all_paragraphs[start_index + 1:]:
                if is_different_expert(text):
                    found_next_expert = True
                    break
        
        # Now do the actual extraction
        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            
            # Check if we should start
            if not started:
                if expert_name.lower() in text.lower():
                    started = True
                    current_section.append(text)
                continue
            
            # Check stopping conditions
            if started:
                # STOP CONDITION 1: Another numbered expert
                if is_different_expert(text):
                    break
                
                # STOP CONDITION 2: If this is the LAST expert and we hit an end-section bold
                if not found_next_expert and is_bold(para) and is_end_section(text):
                    break
                
                # Check if this is a bold section
                if is_bold(para):
                    # If it's part of expert description, add with separator
                    if is_expert_description(text) or len(text.split()) <= 5:  # Short bold headers are usually section titles
                        # Save previous section
                        if current_section:
                            extracted_parts.append('\n'.join(current_section))
                            current_section = []
                        
                        # Add separator and bold section
                        extracted_parts.append('\n----------------------------\n')
                        extracted_parts.append(text)
                    else:
                        # Unknown bold text - include it but check next iteration
                        current_section.append(text)
                else:
                    current_section.append(text)
        
        # Add any remaining content
        if current_section:
            extracted_parts.append('\n'.join(current_section))
        
        # Also check tables
        for table in doc.tables:
            table_started = False
            table_text = []
            
            for row in table.rows:
                row_text = ' | '.join(cell.text.strip() for cell in row.cells if cell.text.strip())
                
                if not table_started:
                    if expert_name.lower() in row_text.lower():
                        table_started = True
                        table_text.append(row_text)
                    continue
                
                if table_started:
                    # Check if we hit another expert
                    if is_different_expert(row_text):
                        break
                    # Check if we hit end section (last expert)
                    if not found_next_expert and is_end_section(row_text):
                        break
                    table_text.append(row_text)
            
            if table_text and started:
                extracted_parts.append('\n----------------------------\n')
                extracted_parts.append('TABLE CONTENT:')
                extracted_parts.extend(table_text)
        
        result = '\n\n'.join(extracted_parts)
        return result.strip() if result else ""
    
    except Exception as e:
        print(f"Error in structure-aware extraction: {e}")
        return extract_expert_section_fallback(tender_text, expert_name)


def extract_expert_section_fallback(full_text: str, expert_name: str) -> str:
    """
    Fallback regex-based extraction for PDFs or when structure extraction fails
    """
    if not full_text or not expert_name:
        return ""

    # Extract number from expert name
    target_match = re.search(r'(\d+|[IVX]+)', expert_name)
    target_number = target_match.group(1) if target_match else None
    
    # Create pattern that stops at next numbered expert OR end sections
    if target_number:
        # Match the target expert, capture everything until next numbered expert or end section
        pattern = re.compile(
            rf"({re.escape(expert_name)}.*?)(?=(?:Key\s*Expert|Expert|KE|Non[-\s]*Key)\s*[#\-]?\s*(?!{re.escape(target_number)})\d+|Annex|Annexe|General\s+Conditions|Terms\s+and\s+Conditions|Appendix|END|$)",
            re.IGNORECASE | re.DOTALL,
        )
    else:
        # No number found, use original pattern
        pattern = re.compile(
            rf"({re.escape(expert_name)}.*?)(?=(?:Key\s*Expert\s*\d|KE\s*\d|Expert\s+in|Non[-\s]*Key|Annex|General\s+Conditions|Terms|END|$))",
            re.IGNORECASE | re.DOTALL,
        )

    match = pattern.search(full_text)
    if match:
        section = match.group(1)
        # Clean spacing
        section = re.sub(r"\n{3,}", "\n\n", section)
        section = re.sub(r"  +", " ", section)
        return section.strip()

    return ""

# ------------------- EXTRACT EXPERT SECTION BUTTON -------------------

if st.button("🔍 Extract Expert Section", disabled=not (req_file and expert_name.strip() and tender_path)):
    with st.spinner("Extracting expert section with structure detection..."):
        
        # Try structure-aware extraction for Word docs
        if req_file.name.lower().endswith('.docx'):
            expert_section = extract_expert_section_with_structure(tender_path, expert_name)
            if expert_section:
                st.info("✅ Extracted using structure-aware method (bold sections preserved with separators)")
            else:
                # Fallback to regex
                expert_section = extract_expert_section_fallback(tender_text, expert_name)
                if expert_section:
                    st.info("🟨 Extracted using regex fallback method")
        else:
            # For PDFs, use regex method
            expert_section = extract_expert_section_fallback(tender_text, expert_name)
            if expert_section:
                st.info("📄 Extracted from PDF using text-based method")
        
        # Store in session state
        if expert_section:
            st.session_state.extracted_section = expert_section
            st.session_state.section_extracted = True
            st.success(f"✅ Extracted expert section for: {expert_name}")
        else:
            st.session_state.extracted_section = ""
            st.session_state.section_extracted = False
            st.warning("⚠️ Could not locate that expert section. You can manually paste it below, or the full tender will be used.")

# ------------------- EDITABLE PREVIEW SECTION -------------------

if req_file and expert_name.strip():
    st.markdown("### 📝 Expert Section Preview & Edit")
    st.markdown("*Review and edit the extracted section. Bold sections within the expert are separated with dashes (---):*")
    
    edited_section = st.text_area(
        "Expert Section Content (editable)",
        value=st.session_state.extracted_section,
        height=400,
        help="This section will be used with 80% weight. Edit as needed. Separators (----) mark different subsections within the expert profile.",
        key="expert_section_editor"
    )
    
    # Update session state with edited content
    st.session_state.extracted_section = edited_section
    
    if edited_section:
        separator_count = edited_section.count('----------------------------')
        st.info(f"📊 Section length: {len(edited_section)} characters | Subsections: {separator_count + 1}")

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

        # Save uploaded CVs
        for file in cv_files:
            path = os.path.join(cv_folder, file.name)
            with open(path, "wb") as f:
                f.write(file.read())

        st.info("⏳ Processing CVs — please wait...")

        # Initialize system
        system = CVAssessmentSystem(api_key=api_key or None)

        # ------------------- USE EDITED EXPERT SECTION -------------------
        expert_section = st.session_state.extracted_section

        # ------------------- IF NOTHING IN EDITOR -------------------
        if not expert_section:
            st.warning("⚠️ No expert section provided. The full tender will be used as context.")
            combined_text = tender_text
        else:
            combined_text = (
                f"--- GENERAL TENDER CONTEXT (20% weight) ---\n\n"
                f"{tender_text[:5000]}\n\n"
                f"--- SPECIFIC EXPERT REQUIREMENTS (80% weight) ---\n\n"
                f"{expert_section}"
            )
            st.success(f"✅ Using expert section for: {expert_name}")

        # ------------------- RUN ASSESSMENTS -------------------

        system.job_requirements = combined_text
        results = system.process_cv_folder(
            cv_folder,
            mode="critical" if mode == "Critical Narrative" else "structured"
        )

        st.success(f"✅ Processed {len(results)} candidate(s)")

        # ------------------- STRUCTURED (DASHBOARD) MODE -------------------

        if mode == "Structured (Dashboard)":
            ranked = sorted(results, key=lambda x: x.overall_score, reverse=True)
            st.markdown("## 🏆 Candidate Ranking (Based on Structured Scores)")
            st.table([
                {
                    "Rank": i + 1,
                    "Candidate": r.candidate_name,
                    "Score": r.overall_score,
                    "Fit Level": r.fit_level
                }
                for i, r in enumerate(ranked)
            ])

        # ------------------- CRITICAL (NARRATIVE) MODE -------------------

        else:
            ranked = sorted(results, key=lambda x: x.get("final_score", 0), reverse=True)
            st.markdown("## 🏆 Candidate Ranking (Based on Final Scores)")
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
                        with st.expander("✂️ Tailoring Suggestions (How to Strengthen CV for This Role)"):
                            st.markdown("✂️ Tailoring Suggestions" + tailoring)
                    else:
                        st.markdown(report)

                    st.markdown(f"**🧮 Final Score:** {r['final_score']:.2f} / 1.00")

# ------------------- SAFEGUARDS -------------------

else:
    if not expert_name.strip():
        st.warning("⚠️ Please enter the expert role title before running the assessment.")
    elif not req_file:
        st.warning("⚠️ Please upload a tender or job description first.")
    elif not cv_files:
        st.warning("⚠️ Please upload at least one candidate CV before running the assessment.")

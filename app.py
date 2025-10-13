import streamlit as st
from cv_assessment import CVAssessmentSystem
import tempfile
import os
import re

st.set_page_config(page_title="Deep CV Assessment System", layout="wide")
st.title("📄 Deep CV Assessment System")

# --- API Key Input ---
api_key = st.text_input("🔑 Enter OpenAI API Key", type="password")

# --- Mode Selection ---
mode = st.radio("Select Evaluation Mode:", ["Structured (Dashboard)", "Critical Narrative"])

# --- Upload Tender ---
req_file = st.file_uploader("📄 Upload Tender / Job Description", type=["pdf", "docx", "doc"])
tender_text = ""
tender_path = ""

if req_file:
    suffix = os.path.splitext(req_file.name)[1] or ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(req_file.read())
        tender_path = tmp.name

    st.success(f"✅ Tender uploaded: {req_file.name}")

    # Initialize CV system
    system_temp = CVAssessmentSystem(api_key=api_key or None)
    tender_text = system_temp.load_job_requirements(tender_path)
    st.info("📘 Tender text loaded successfully.")

# --- Expert Name Input ---
st.markdown("### 🎯 Enter the EXACT Expert Role Title (as in the tender)")
expert_name = st.text_input(
    "Example: Key expert 1 (KE 1): Team leader Expert in Employment",
    placeholder="Enter the exact expert heading (case-insensitive)"
)

# --- Regex fallback extractor ---
def extract_expert_section_regex(full_text: str, expert_name: str) -> str:
    if not full_text or not expert_name:
        return ""

    text = re.sub(r"\s+", " ", full_text)
    num_match = re.search(r"\bKey\s*Expert\s*(\d+)\b", expert_name, re.IGNORECASE)
    current_num = int(num_match.group(1)) if num_match else 1
    next_num = current_num + 1

    stop_pattern = re.compile(
        rf"(?:(?<!\d)(?:Key|KE)?\s*Expert\s*(?:{next_num}|[1-9]\d*)\b|"
        r"(?<!\w)(?:Reports?|Deliverables?|Annex(?:es)?|Incidental|"
        r"Expenditure|Verification|Lump\s*Sums?|Terms|Conditions?|"
        r"Background|Monitoring|Evaluation|Practical\s*Information)\b)",
        re.IGNORECASE,
    )

    pattern_start = re.compile(re.escape(expert_name), re.IGNORECASE)
    starts = [m.start() for m in pattern_start.finditer(text)]
    if not starts:
        return ""

    sections = []
    for s in starts:
        stop_match = stop_pattern.search(text, s)
        end_index = stop_match.start() if stop_match else len(text)
        block = text[s:end_index].strip()
        if block:
            sections.append(block)
    return "\n\n---------------\n\n".join(sections)

# --- Upload CVs ---
cv_files = st.file_uploader(
    "👤 Upload Candidate CVs",
    type=["pdf", "docx", "doc"],
    accept_multiple_files=True
)

# --- Step 1: Extract Expert Section ---
edited_expert_section = ""
if st.button("📘 Extract Expert Section") and req_file and expert_name.strip():
    system = CVAssessmentSystem(api_key=api_key or None)

    # If DOCX, prefer bold-based extraction
    if tender_path.lower().endswith(".docx"):
        expert_section = system.extract_expert_sections_by_bold(tender_path, expert_name)
    else:
        expert_section = extract_expert_section_regex(tender_text, expert_name)

    if not expert_section or expert_section.strip() == "":
        st.warning("⚠️ Could not locate that expert section.")
    else:
        st.success(f"✅ Extracted expert section(s) for: {expert_name}")
        edited_expert_section = st.text_area(
            "✏️ Preview & Edit Extracted Expert Section (you can modify text before running assessment):",
            expert_section,
            height=700,
        )

# --- Step 2: Run Assessment ---
if st.button("🚀 Run Assessment") and req_file and cv_files and (api_key or os.getenv("OPENAI_API_KEY")):
    system = CVAssessmentSystem(api_key=api_key or None)

    expert_section = edited_expert_section.strip() if edited_expert_section else (
        system.extract_expert_sections_by_bold(tender_path, expert_name)
        if tender_path.lower().endswith(".docx")
        else extract_expert_section_regex(tender_text, expert_name)
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        cv_folder = os.path.join(tmpdir, "cvs")
        os.makedirs(cv_folder, exist_ok=True)

        for file in cv_files:
            path = os.path.join(cv_folder, file.name)
            with open(path, "wb") as f:
                f.write(file.read())

        st.info("⏳ Processing CVs — please wait...")

        combined_text = (
            f"--- GENERAL TENDER CONTEXT (20% weight) ---\n\n"
            f"{tender_text[:5000]}\n\n"
            f"--- SPECIFIC EXPERT REQUIREMENTS (80% weight) ---\n\n"
            f"{expert_section}"
        )

        system.job_requirements = combined_text
        results = system.process_cv_folder(cv_folder, mode="critical" if mode == "Critical Narrative" else "structured")
        st.success(f"✅ Processed {len(results)} candidate(s)")

        # ---------- STRUCTURED MODE ----------
        if mode == "Structured (Dashboard)":
            ranked = sorted(results, key=lambda x: x["overall_score"], reverse=True)
            st.markdown("## 🏆 Candidate Ranking (Based on Structured Scores)")
            st.table([
                {"Rank": i + 1, "Candidate": r["candidate_name"], "Score": r["overall_score"], "Fit Level": r["fit_level"]}
                for i, r in enumerate(ranked)
            ])

        # ---------- CRITICAL NARRATIVE MODE ----------
        else:
            ranked = sorted(results, key=lambda x: x["final_score"], reverse=True)
            st.markdown("## 🏆 Candidate Ranking (Based on Final Scores)")
            st.table([
                {"Rank": i + 1, "Candidate": r["candidate_name"], "Final Score": f"{r['final_score']:.2f}"}
                for i, r in enumerate(ranked)
            ])

            for r in ranked:
                with st.expander(f"{r['candidate_name']} — Critical Evaluation"):
                    report = r["report"]
                    st.markdown(report)
                    st.markdown(f"**🧮 Final Score:** {r['final_score']:.2f} / 1.00")

else:
    if not expert_name.strip():
        st.warning("⚠️ Please enter the expert role title before running the assessment.")

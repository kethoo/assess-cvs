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

    # --- Debug: view tender length or ending ---
    st.write(f"Tender text length: {len(tender_text)} characters")
    if st.checkbox("Show tail of tender (last 1000 chars)"):
        st.text(tender_text[-1000:])

# --- Expert Name Input ---
st.markdown("### 🎯 Enter the EXACT Expert Role Title (as in the tender)")
expert_name = st.text_input(
    "Example: Key expert 1",
    placeholder="Enter the exact expert heading (case-insensitive)"
)

# --- FINAL Expert Section Extraction ---
def extract_expert_section(full_text: str, expert_name: str) -> str:
    """
    Extract all 'Key Expert N' sections:
    - Starts at each occurrence of the given expert name.
    - Ends right before the next higher-numbered expert (Key Expert N+1).
    - Joins all found blocks with a separator '---------------'.
    """
    if not full_text or not expert_name:
        return ""

    # Normalize whitespace
    text = re.sub(r"\s+", " ", full_text)

    # Identify which expert number we’re extracting (default 1)
    num_match = re.search(r"\bKey\s*Expert\s*(\d+)\b", expert_name, re.IGNORECASE)
    current_num = int(num_match.group(1)) if num_match else 1
    next_num = current_num + 1

    # Find all occurrences of this expert name
    pattern_start = re.compile(re.escape(expert_name), re.IGNORECASE)
    starts = [m.start() for m in pattern_start.finditer(text)]
    if not starts:
        return ""

    # Define where to stop (Key Expert next number)
    stop_pattern = re.compile(
        rf"(?:(?<!\d)(?:Key|KE)?\s*Expert\s*{next_num}\b)",
        re.IGNORECASE,
    )

    sections = []
    for s in starts:
        stop_match = stop_pattern.search(text, s)
        end_index = stop_match.start() if stop_match else len(text)
        block = text[s:end_index].strip()
        if block:
            sections.append(block)

    # Join all sections with separator
    return "\n\n---------------\n\n".join(sections)


# --- Upload CVs ---
cv_files = st.file_uploader(
    "👤 Upload Candidate CVs",
    type=["pdf", "docx", "doc"],
    accept_multiple_files=True
)

# --- Run Assessment ---
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

        # Extract expert section dynamically
        expert_section = extract_expert_section(tender_text, expert_name)

        if not expert_section:
            st.warning("⚠️ Could not locate that expert section. Using full tender as fallback context.")
            combined_text = tender_text
        else:
            combined_text = (
                f"--- GENERAL TENDER CONTEXT (20% weight) ---\n\n"
                f"{tender_text[:5000]}\n\n"
                f"--- SPECIFIC EXPERT REQUIREMENTS (80% weight) ---\n\n"
                f"{expert_section}"
            )
            st.success(f"✅ Extracted expert section(s) for: {expert_name}")
            st.text_area("📘 Preview of Extracted Expert Section", expert_section, height=700)

        # Assign requirements text for evaluation
        system.job_requirements = combined_text

        # Process CVs
        results = system.process_cv_folder(
            cv_folder,
            mode="critical" if mode == "Critical Narrative" else "structured"
        )

        st.success(f"✅ Processed {len(results)} candidate(s)")

        # ---------- STRUCTURED MODE ----------
        if mode == "Structured (Dashboard)":
            ranked = sorted(results, key=lambda x: x.overall_score, reverse=True)
            st.markdown("## 🏆 Candidate Ranking (Based on Structured Scores)")
            st.table([
                {"Rank": i + 1, "Candidate": r.candidate_name, "Score": r.overall_score, "Fit Level": r.fit_level}
                for i, r in enumerate(ranked)
            ])

        # ---------- CRITICAL NARRATIVE MODE ----------
        else:
            ranked = sorted(results, key=lambda x: x.get("final_score", 0), reverse=True)
            st.markdown("## 🏆 Candidate Ranking (Based on Final Scores)")
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
                        with st.expander("✂️ Tailoring Suggestions (How to Strengthen CV for This Role)"):
                            st.markdown("✂️ Tailoring Suggestions" + tailoring)
                    else:
                        st.markdown(report)
                    st.markdown(f"**🧮 Final Score:** {r['final_score']:.2f} / 1.00")

else:
    if not expert_name.strip():
        st.warning("⚠️ Please enter the expert role title before running the assessment.")

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

# --- Expert Name Input ---
st.markdown("### 🎯 Enter the EXACT Expert Role Title (as in the tender)")
expert_name = st.text_input(
    "Example: Team leader Expert in Employment",
    placeholder="Enter exact expert role title (case-insensitive)"
)

# --- FINAL Expert Section Extraction (Annex-safe version) ---
def extract_expert_section(full_text: str, expert_name: str) -> str:
    """
    Finds EVERY instance of the exact expert_name and extracts everything that follows
    until the next 'Key Expert 2', 'KE 2', 'Expert 2', or higher-numbered expert.
    Ignores internal 'Expert in …' phrases and 'Annex' inside the same block.
    """
    if not full_text or not expert_name:
        return ""

    # Normalize whitespace for cleaner regex behaviour
    text = re.sub(r"\s+", " ", full_text)

    # --- STOP only at Key Expert 2 or higher (Annex removed) ---
    stop_pattern = re.compile(
        r"(?:Key\s*Expert\s*[2-9]\b|KE\s*[2-9]\b|Expert\s+[2-9]\b|Non[-\s]*Key|General\s+Conditions|Terms|Reimbursement|END)",
        re.IGNORECASE,
    )

    # --- Find all occurrences of the expert name ---
    starts = [m.start() for m in re.finditer(re.escape(expert_name), text, re.IGNORECASE)]
    if not starts:
        return ""

    sections = []
    for s in starts:
        # Find next stop marker after this start
        stop = stop_pattern.search(text, s)
        end = stop.start() if stop else len(text)
        part = text[s:end].strip()
        if part:
            sections.append(part)

    # Join all found sections
    return "\n\n---\n\n".join(sections)


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
            st.success(f"✅ Extracted expert section for: {expert_name}")
            st.text_area("📘 Preview of Extracted Expert Section", expert_section[:4000], height=350)

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

import streamlit as st
from cv_assessment import CVAssessmentSystem
import tempfile
import os
import re

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

# ------------------- EXPERT NAME -------------------

st.markdown("### 🎯 Enter the Expert Role Title (exactly as in the tender file)")
expert_name = st.text_input(
    "Example: Team Leader, International Expert",
    placeholder="Enter the expert role title or partial match (e.g., 'Key Expert 1', 'Procurement Expert')"
)

# ------------------- REGEX-BASED EXTRACTION FUNCTION -------------------

def extract_expert_section(full_text: str, expert_name: str) -> str:
    """
    Extracts the full text for a specific expert, including both table and paragraph content.
    Handles multiple formatting styles using regex.
    """
    if not full_text or not expert_name:
        return ""

    # Stops at next expert, annex, or general section
    pattern = re.compile(
        rf"({re.escape(expert_name)}.*?)(?=(?:Key\s*Expert\s*\d|KE\s*\d|Expert\s+in|Non[-\s]*Key|Annex|General\s+Conditions|Terms|END|$))",
        re.IGNORECASE | re.DOTALL,
    )

    match = pattern.search(full_text)
    if match:
        section = match.group(1)
        # Clean spacing
        section = re.sub(r"\n{2,}", "\n", section)
        section = re.sub(r"\s{2,}", " ", section)
        return section.strip()

    return ""

# ------------------- EXPERT SECTION EXTRACTION PREVIEW -------------------

expert_section = ""
if req_file and expert_name.strip():
    suffix = os.path.splitext(req_file.name)[1] or ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(req_file.read())
        tender_path = tmp.name

    # Initialize temporary system to extract tender text
    system_temp = CVAssessmentSystem(api_key=api_key or None)
    tender_text = system_temp.load_job_requirements(tender_path)

    st.info("📘 Tender text loaded successfully.")

    # 🧩 Try bold + expert-aware extraction first (NEW LOGIC)
    if req_file.name.lower().endswith(".docx"):
        expert_section = system_temp.extract_expert_sections_by_bold(tender_path, expert_name)
        if expert_section and not expert_section.startswith("⚠️"):
            st.info("🧠 Expert section extracted using bold + expert-aware logic.")
        else:
            expert_section = extract_expert_section(tender_text, expert_name)
    else:
        # PDF fallback
        expert_section = extract_expert_section(tender_text, expert_name)

    # If still nothing found
    if not expert_section or expert_section.startswith("⚠️"):
        st.warning("⚠️ Could not locate that expert section automatically.")
    else:
        st.success(f"✅ Extracted expert section for: {expert_name}")

    # 📝 Editable preview box (visible before assessment)
    expert_section = st.text_area(
        "📘 Preview & Edit Extracted Expert Section",
        expert_section,
        height=350,
        help="You can review and edit this section before running the assessment."
    )

# ------------------- UPLOAD CVS -------------------

cv_files = st.file_uploader(
    "👤 Upload Candidate CVs",
    type=["pdf", "docx", "doc"],
    accept_multiple_files=True
)

# ------------------- RUN ASSESSMENT -------------------

if st.button("🚀 Run Assessment") and req_file and cv_files and (api_key or os.getenv("OPENAI_API_KEY")):
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

        # Combine tender + expert section
        if not expert_section:
            combined_text = tender_text
        else:
            combined_text = (
                f"--- GENERAL TENDER CONTEXT (20% weight) ---\n\n"
                f"{tender_text[:5000]}\n\n"
                f"--- SPECIFIC EXPERT REQUIREMENTS (80% weight) ---\n\n"
                f"{expert_section}"
            )

        system.job_requirements = combined_text

        # Run assessments
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


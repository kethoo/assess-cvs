import streamlit as st
from cv_assessment import CVAssessmentSystem
import tempfile
import os

st.set_page_config(page_title="Deep CV Assessment System", layout="wide")
st.title("📄 Deep CV Assessment System")

# --- API Key Input ---
api_key = st.text_input("🔑 Enter OpenAI API Key", type="password")

# --- Mode Selection ---
mode = st.radio("Select Evaluation Mode:", ["Structured (Dashboard)", "Critical Narrative"])

# --- Upload Tender ---
req_file = st.file_uploader("📄 Upload Tender / Job Description (general context)", type=["pdf", "docx", "doc"])
tender_text = ""

if req_file:
    suffix = os.path.splitext(req_file.name)[1] or ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(req_file.read())
        tender_path = tmp.name

    st.success(f"✅ Tender file uploaded: {req_file.name}")

    # Load the general tender context
    system_temp = CVAssessmentSystem(api_key=api_key or None)
    tender_text = system_temp.load_job_requirements(tender_path)

# --- Manual Expert Input ---
st.markdown("### ✍️ Enter or paste the specific Expert Role requirements below")
expert_text = st.text_area(
    "Paste the text of the role you are assessing for (from the tender’s expert section or custom JD).",
    placeholder=(
        "Example:\n"
        "Key Expert 1 – Road Traffic Expert (Team Leader):\n"
        "- Master’s degree in technical sciences or equivalent\n"
        "- 10 years of experience in road transport policy or safety management\n"
        "- Proven experience leading EU-funded TA projects\n"
    ),
    height=250
)

# --- Upload CVs ---
cv_files = st.file_uploader(
    "👤 Upload Candidate CVs",
    type=["pdf", "docx", "doc"],
    accept_multiple_files=True
)

# --- Run Assessment Button ---
if st.button("🚀 Run Assessment") and req_file and cv_files and expert_text.strip() and (api_key or os.getenv("OPENAI_API_KEY")):
    with tempfile.TemporaryDirectory() as tmpdir:
        cv_folder = os.path.join(tmpdir, "cvs")
        os.makedirs(cv_folder, exist_ok=True)

        # Save uploaded CVs
        for file in cv_files:
            path = os.path.join(cv_folder, file.name)
            with open(path, "wb") as f:
                f.write(file.read())

        st.info("⏳ Processing CVs — please wait...")

        # Initialize the system
        system = CVAssessmentSystem(api_key=api_key or None)

        # Weighted combination of tender context (20%) and expert requirements (80%)
        combined_text = (
            f"--- GENERAL TENDER CONTEXT (20% weight) ---\n\n"
            f"{tender_text[:5000]}\n\n"
            f"--- SPECIFIC EXPERT REQUIREMENTS (80% weight) ---\n\n"
            f"{expert_text.strip()}"
        )

        system.job_requirements = combined_text

        # Process CVs
        results = system.process_cv_folder(cv_folder, mode="critical" if mode == "Critical Narrative" else "structured")
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
    if not expert_text.strip():
        st.warning("⚠️ Please paste the specific expert requirements before running the assessment.")

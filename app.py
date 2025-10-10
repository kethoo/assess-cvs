import streamlit as st
from cv_assessment import CVAssessmentSystem
import tempfile, os

st.set_page_config(page_title="CV Assessment System", layout="wide")
st.title("📄 Deep CV Assessment System")
st.write("Upload job requirements + candidate CVs to get detailed, weighted AI assessments.")

api_key = st.text_input("🔑 Enter OpenAI API Key", type="password")
if not api_key and not os.getenv("OPENAI_API_KEY"):
    st.warning("Please enter an API key to continue.")

req_file = st.file_uploader("Upload Job Description", type=["pdf", "docx", "doc"])
cv_files = st.file_uploader("Upload Candidate CVs", type=["pdf", "docx", "doc"], accept_multiple_files=True)

if st.button("🚀 Run Deep Assessment") and req_file and cv_files:
    with tempfile.TemporaryDirectory() as tmpdir:
        req_path = os.path.join(tmpdir, req_file.name)
        with open(req_path, "wb") as f:
            f.write(req_file.read())

        cv_folder = os.path.join(tmpdir, "cvs")
        os.makedirs(cv_folder, exist_ok=True)
        for cv in cv_files:
            path = os.path.join(cv_folder, cv.name)
            with open(path, "wb") as f:
                f.write(cv.read())

        system = CVAssessmentSystem(api_key=api_key)
        system.load_job_requirements(req_path)
        results = system.process_cv_folder(cv_folder)

        st.success(f"✅ Processed {len(results)} candidates")

        for r in results:
            with st.expander(f"{r.candidate_name} — {r.overall_score}/100 ({r.fit_level})"):
                st.json({
                    "Education": r.education_details,
                    "Experience": r.experience_details,
                    "Skills": r.skills_details,
                    "Job Fit": r.job_fit_details
                })

                st.write("### 🧭 Executive Summary")
                st.json(r.executive_summary)

                st.write("### 💬 Recommendation")
                st.json(r.recommendation)

                st.write("### 🎯 Interview Focus Areas")
                for i in r.interview_focus_areas:
                    st.markdown(f"- {i}")

                if r.red_flags:
                    st.write("### ⚠️ Red Flags")
                    for rf in r.red_flags:
                        st.markdown(f"- {rf}")

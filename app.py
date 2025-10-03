import streamlit as st
from cv_assessment import CVAssessmentSystem
import tempfile
import os

st.set_page_config(page_title="CV Assessment System", layout="wide")

st.title("📄 Comprehensive CV Assessment System")
st.write("Upload job requirements + candidate CVs, and get ultra-detailed assessments.")

# --- API Key ---
api_key = st.text_input("🔑 Enter OpenAI API Key", type="password")
if not api_key and not os.getenv("OPENAI_API_KEY"):
    st.warning("Please enter an OpenAI API key to continue.")

# --- Upload Job Requirements ---
st.header("Step 1: Upload Job Requirements")
req_file = st.file_uploader("Upload Job Description (Word or PDF)", type=["pdf", "docx", "doc"])

# --- Upload CVs ---
st.header("Step 2: Upload Candidate CVs")
cv_files = st.file_uploader("Upload Candidate CVs (multiple allowed)", type=["pdf", "docx", "doc"], accept_multiple_files=True)

# --- Run Button ---
if st.button("🚀 Run Assessment") and req_file and cv_files and (api_key or os.getenv("OPENAI_API_KEY")):
    # Save uploads to temp folder
    with tempfile.TemporaryDirectory() as tmpdir:
        req_path = os.path.join(tmpdir, req_file.name)
        with open(req_path, "wb") as f:
            f.write(req_file.read())

        cv_folder = os.path.join(tmpdir, "cvs")
        os.makedirs(cv_folder, exist_ok=True)
        for file in cv_files:
            path = os.path.join(cv_folder, file.name)
            with open(path, "wb") as f:
                f.write(file.read())

        # Run system
        system = CVAssessmentSystem(api_key=api_key or None)
        system.load_job_requirements(req_path)
        assessments = system.process_cv_folder(cv_folder, mode="detailed")

        # Display results
        st.success(f"✅ Processed {len(assessments)} candidates")

        for c in assessments:
            with st.expander(f"{c.candidate_name} — {c.overall_score}/100 ({c.fit_level})"):
                st.markdown(f"**Recommendation:** {c.recommendation.upper()} (Confidence: {c.confidence_level})")
                st.progress(c.overall_score / 100)

                st.subheader("📊 Score Breakdown")
                st.write(f"**Experience:** {c.experience_score}/100")
                st.write(f"**Skills:** {c.skills_score}/100")
                st.write(f"**Education:** {c.education_score}/100")
                st.write(f"**Cultural Fit:** {c.cultural_fit_score}/100")

                st.subheader("✅ Strengths")
                for s in c.key_strengths: st.markdown(f"- {s}")

                st.subheader("⚠️ Weaknesses")
                for w in c.key_weaknesses: st.markdown(f"- {w}")

                if c.critical_gaps:
                    st.subheader("🚨 Critical Gaps")
                    for g in c.critical_gaps: st.markdown(f"- {g}")

                if c.red_flags:
                    st.subheader("⛔ Red Flags")
                    for r in c.red_flags: st.markdown(f"- {r}")

                st.subheader("📝 Executive Summary")
                st.info(c.executive_summary)

                st.subheader("💡 Why This Score")
                st.write(c.why_this_score)

                st.subheader("🎯 Interview Focus Areas")
                for i in c.interview_focus_areas: st.markdown(f"- {i}")

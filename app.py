import streamlit as st
from cv_assessment import CVAssessmentSystem
import tempfile
import os

st.set_page_config(page_title="Deep CV Assessment System", layout="wide")
st.title("📄 Deep CV Assessment System")
st.write("Upload job description and candidate CVs to get detailed AI-driven analysis with rich reasoning.")

api_key = st.text_input("🔑 Enter OpenAI API Key", type="password")
if not api_key and not os.getenv("OPENAI_API_KEY"):
    st.warning("Please enter an API key to continue.")

req_file = st.file_uploader("Upload Job Description (Word or PDF)", type=["pdf", "docx", "doc"])
cv_files = st.file_uploader("Upload Candidate CVs", type=["pdf", "docx", "doc"], accept_multiple_files=True)

def render_section(title, section):
    st.markdown(f"### {title}")
    if not section:
        st.info("No data available for this section.")
        return
    score = section.get("score", "N/A")
    weight = section.get("weight", "")
    st.write(f"**Score:** {score}/100 | **Weight:** {weight}")
    details = section.get("details", {})
    if isinstance(details, dict):
        for key, value in details.items():
            label = key.replace("_", " ").capitalize()
            if isinstance(value, list):
                st.markdown(f"**{label}:**")
                for v in value:
                    st.markdown(f"- {v}")
            elif value:
                st.markdown(f"**{label}:** {value}")
    st.divider()

if st.button("🚀 Run Deep Assessment") and req_file and cv_files and (api_key or os.getenv("OPENAI_API_KEY")):
    with tempfile.TemporaryDirectory() as tmpdir:
        # Save job description
        req_path = os.path.join(tmpdir, req_file.name)
        with open(req_path, "wb") as f:
            f.write(req_file.read())

        # Save CVs
        cv_folder = os.path.join(tmpdir, "cvs")
        os.makedirs(cv_folder, exist_ok=True)
        for file in cv_files:
            path = os.path.join(cv_folder, file.name)
            with open(path, "wb") as f:
                f.write(file.read())
            st.write(f"✅ Saved {file.name}")

        # Run inside temp directory
        st.info("⏳ Processing CVs — please wait...")
        system = CVAssessmentSystem(api_key=api_key or None)
        system.load_job_requirements(req_path)
        results = system.process_cv_folder(cv_folder)

        st.success(f"✅ Processed {len(results)} candidate(s)")

        for r in results:
            with st.expander(f"{r.candidate_name} — {r.overall_score}/100 ({r.fit_level})"):
                st.markdown("## 🧭 Executive Summary")
                summary = r.executive_summary or {}
                st.write(f"**Have:** {summary.get('have', '-')}")
                st.write(f"**Lack:** {summary.get('lack', '-')}")
                if summary.get("risks_gaps"):
                    st.markdown("**Risks & Gaps:**")
                    for g in summary["risks_gaps"]:
                        st.markdown(f"- {g}")
                st.markdown(f"**Recommendation:** {summary.get('recommendation', '-')}")
                st.divider()

                st.markdown("## 🎓 Education")
                render_section("Education", r.education_details)

                st.markdown("## 💼 Experience")
                render_section("Experience", r.experience_details)

                st.markdown("## 🧠 Skills")
                render_section("Skills", r.skills_details)

                st.markdown("## 🎯 Job Fit")
                render_section("Job Fit", r.job_fit_details)

                st.markdown("## 💬 Final Recommendation")
                rec = r.recommendation or {}
                st.write(f"**Verdict:** {rec.get('verdict', '-')}")
                st.write(f"**Confidence:** {rec.get('confidence', '-')}")
                st.write(f"**Rationale:** {rec.get('rationale', '-')}")

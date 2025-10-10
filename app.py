import streamlit as st
from cv_assessment import CVAssessmentSystem
import tempfile
import os

st.set_page_config(page_title="Deep CV Assessment System", layout="wide")
st.title("📄 Deep CV Assessment System")

api_key = st.text_input("🔑 Enter OpenAI API Key", type="password")

mode = st.radio("Select Evaluation Mode:", ["Structured (Dashboard)", "Critical Narrative"])

req_file = st.file_uploader("📄 Upload Job Description", type=["pdf", "docx", "doc"])
cv_files = st.file_uploader("👤 Upload Candidate CVs", type=["pdf", "docx", "doc"], accept_multiple_files=True)

def render_section(title, section):
    st.markdown(f"### {title}")
    if not section:
        st.info("No data available.")
        return
    score = section.get("score", "N/A")
    weight = section.get("weight", "")
    st.write(f"**Score:** {score}/100 | **Weight:** {weight}")
    details = section.get("details", {})
    if isinstance(details, dict):
        for k, v in details.items():
            if isinstance(v, list):
                st.markdown(f"**{k.replace('_',' ').capitalize()}:**")
                for i in v:
                    st.markdown(f"- {i}")
            elif v:
                st.markdown(f"**{k.replace('_',' ').capitalize()}:** {v}")
    st.divider()

if st.button("🚀 Run Assessment") and req_file and cv_files and (api_key or os.getenv("OPENAI_API_KEY")):
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

        st.info("⏳ Processing CVs — please wait...")
        system = CVAssessmentSystem(api_key=api_key or None)
        system.load_job_requirements(req_path)

        if mode == "Critical Narrative":
            results = system.process_cv_folder(cv_folder, mode="critical")
            st.success(f"✅ Processed {len(results)} candidate(s)")

            for r in results:
                with st.expander(f"{r['candidate_name']} — Critical Evaluation"):
                    st.markdown(r["report"])
        else:
            results = system.process_cv_folder(cv_folder, mode="structured")
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

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
            else:
                if value:
                    st.markdown(f"**{label}:** {value}")
    st.divider()


if st.button("🚀 Run Deep Assessment") and req_file and cv_files and (api_key or os.getenv("OPENAI_API_KEY")):
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

        system = CVAssessmentSystem(api_key=api_key or None)
        system.load_job_requirements(req_path)
        results = system.process_cv_folder(cv_folder)

        st.success(f"✅ Processed {len(results)} candidates")

        for r in results:
            with st.expander(f"{r.candidate_name} — {r.overall_score}/100 ({r.fit_level})"):
                st.markdown("## 🧭 Executive Summary")
                summary = r.executive_summary or {}
                st.write(f"**What they have:** {summary.get('have', '—')}")
                st.write(f"**What they lack:** {summary.get('lack', '—')}")
                if summary.get("risks_gaps"):
                    st.markdown("**Risks & Gaps:**")
                    for g in summary["risks_gaps"]:
                        st.markdown(f"- {g}")
                st.markdown(f"**Recommendation Summary:** {summary.get('recommendation', '—')}")
                st.divider()

                st.markdown("## 🎓 Education")
                render_section("Education", r.education_details)

                st.markdown("## 💼 Experience")
                render_section("Experience", r.experience_details)

                st.markdown("## 🧠 Skills")
                render_section("Skills", r.skills_details)

                st.markdown("## 🎯 Job Fit — Deep Requirement Comparison")
                jf = r.job_fit_details or {}
                st.write(f"**Score:** {jf.get('score', 'N/A')}/100 | **Weight:** {jf.get('weight', '')}")
                job_details = jf.get("details", {})
                st.markdown(f"**Summary:** {job_details.get('alignment_summary', '—')}")
                if job_details.get("matched_requirements"):
                    st.markdown("**Matched Requirements (detailed reasoning):**")
                    for item in job_details["matched_requirements"]:
                        st.markdown(f"- {item}")
                if job_details.get("missing_requirements"):
                    st.markdown("**Missing Requirements (detailed reasoning):**")
                    for item in job_details["missing_requirements"]:
                        st.markdown(f"- {item}")
                if job_details.get("reasoning"):
                    st.markdown("**Overall Reasoning:**")
                    st.write(job_details["reasoning"])
                st.divider()

                st.markdown("## 💬 Final Recommendation — Full Reasoning")
                rec = r.recommendation or {}
                st.write(f"**Verdict:** {rec.get('verdict', '—')}")
                st.write(f"**Confidence:** {rec.get('confidence', '—')}")
                st.markdown("**Rationale (detailed):**")
                st.write(rec.get("rationale", "No detailed reasoning provided."))

                if r.interview_focus_areas:
                    st.divider()
                    st.markdown("## 🎯 Interview Focus Areas")
                    for i in r.interview_focus_areas:
                        st.markdown(f"- {i}")

                if r.red_flags:
                    st.divider()
                    st.markdown("## ⚠️ Red Flags")
                    for rf in r.red_flags:
                        st.markdown(f"- {rf}")

                if r.potential_concerns:
                    st.divider()
                    st.markdown("## 🟠 Potential Concerns")
                    for pc in r.potential_concerns:
                        st.markdown(f"- {pc}")

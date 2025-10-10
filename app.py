import streamlit as st
from cv_assessment import CVAssessmentSystem
import tempfile
import os


# --- PAGE SETUP ---
st.set_page_config(page_title="Deep CV Assessment System", layout="wide")

st.title("📄 Deep CV Assessment System")
st.write(
    """
    Upload your **Job Description** and multiple **Candidate CVs**, then let AI generate a
    *deep, weighted, and human-readable* analysis of each candidate’s suitability.
    """
)

# --- API KEY ---
api_key = st.text_input("🔑 Enter OpenAI API Key", type="password")
if not api_key and not os.getenv("OPENAI_API_KEY"):
    st.warning("Please enter an OpenAI API key to continue.")

# --- FILE UPLOADS ---
st.header("Step 1: Upload Job Description")
req_file = st.file_uploader("Upload Job Description (PDF or Word)", type=["pdf", "docx", "doc"])

st.header("Step 2: Upload Candidate CVs")
cv_files = st.file_uploader(
    "Upload Candidate CVs (you can select multiple files)",
    type=["pdf", "docx", "doc"],
    accept_multiple_files=True,
)

# --- HELPER FUNCTION TO RENDER SECTIONS ---
def render_section(title, section):
    """Nicely format a structured section of the AI’s JSON output."""
    st.markdown(f"### {title}")
    if not section:
        st.info("No data available for this section.")
        return

    score = section.get("score", "N/A")
    weight = section.get("weight", "")
    st.write(f"**Score:** {score}/100 &nbsp;&nbsp;|&nbsp;&nbsp; **Weight:** {weight}")

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


# --- RUN ASSESSMENT BUTTON ---
if st.button("🚀 Run Deep Assessment") and req_file and cv_files and (api_key or os.getenv("OPENAI_API_KEY")):
    with tempfile.TemporaryDirectory() as tmpdir:
        # Save job requirements file
        req_path = os.path.join(tmpdir, req_file.name)
        with open(req_path, "wb") as f:
            f.write(req_file.read())

        # Save CVs to temporary folder
        cv_folder = os.path.join(tmpdir, "cvs")
        os.makedirs(cv_folder, exist_ok=True)
        for file in cv_files:
            cv_path = os.path.join(cv_folder, file.name)
            with open(cv_path, "wb") as f:
                f.write(file.read())

        # Initialize and run assessment system
        st.info("⏳ Processing CVs... this may take several minutes depending on file size and AI response.")
        system = CVAssessmentSystem(api_key=api_key or None)
        system.load_job_requirements(req_path)
        results = system.process_cv_folder(cv_folder)

        st.success(f"✅ Processed {len(results)} candidate(s) successfully!")

        # --- DISPLAY RESULTS ---
        for r in results:
            with st.expander(f"{r.candidate_name} — {r.overall_score}/100 ({r.fit_level})"):
                st.markdown("## 🧭 Executive Summary")
                summary = r.executive_summary or {}
                st.write(f"**What they have:** {summary.get('have', '—')}")
                st.write(f"**What they lack:** {summary.get('lack', '—')}")
                if summary.get("risks_gaps"):
                    st.markdown("**Risks / Gaps:**")
                    for g in summary["risks_gaps"]:
                        st.markdown(f"- {g}")
                st.markdown(f"**Recommendation:** {summary.get('recommendation', '—')}")
                st.divider()

                st.markdown("## 🎓 Education")
                render_section("Education", r.education_details)

                st.markdown("## 💼 Experience")
                render_section("Experience", r.experience_details)

                st.markdown("## 🧠 Skills")
                render_section("Skills", r.skills_details)

                st.markdown("## 🎯 Job Fit")
                render_section("Job Fit", r.job_fit_details)

                st.markdown("## 💬 Recommendation")
                rec = r.recommendation or {}
                st.write(f"**Verdict:** {rec.get('verdict', '—')}")
                st.write(f"**Confidence:** {rec.get('confidence', '—')}")
                st.write(f"**Rationale:** {rec.get('rationale', '—')}")
                st.divider()

                st.markdown("## 🎯 Interview Focus Areas")
                if r.interview_focus_areas:
                    for i in r.interview_focus_areas:
                        st.markdown(f"- {i}")
                else:
                    st.info("No interview focus areas identified.")
                st.divider()

                if r.red_flags:
                    st.markdown("## ⚠️ Red Flags")
                    for rf in r.red_flags:
                        st.markdown(f"- {rf}")
                    st.divider()

                if r.potential_concerns:
                    st.markdown("## 🟠 Potential Concerns")
                    for pc in r.potential_concerns:
                        st.markdown(f"- {pc}")

                st.markdown("## 💰 Salary Recommendation")
                st.write(r.salary_recommendation or "Not specified.")

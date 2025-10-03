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
    with tempfile.TemporaryDirectory() as tmpdir:
        # Save job requirements
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

        # Run system
        system = CVAssessmentSystem(api_key=api_key or None)
        system.load_job_requirements(req_path)
        assessments = system.process_cv_folder(cv_folder, mode="detailed")

        st.success(f"✅ Processed {len(assessments)} candidates")

        for c in assessments:
            with st.expander(f"{c.candidate_name} — {c.overall_score}/100 ({c.fit_level})"):
                st.markdown(f"**Recommendation:** {c.recommendation.upper()} (Confidence: {c.confidence_level})")
                st.progress(c.overall_score / 100 if c.overall_score else 0)

                # ---------- SCORE BREAKDOWN ----------
                st.subheader("📊 Score Breakdown")

                def colored_bar(label, score):
                    if score >= 80:
                        color = "🟢"
                    elif score >= 50:
                        color = "🟡"
                    else:
                        color = "🔴"
                    st.write(f"**{label}: {score}/100 {color}**")
                    st.progress(score / 100 if score else 0)

                colored_bar("Experience", c.experience_score)
                colored_bar("Skills", c.skills_score)
                colored_bar("Education", c.education_score)
                colored_bar("Cultural Fit", c.cultural_fit_score)

                # ---------- STRENGTHS & WEAKNESSES ----------
                st.subheader("✅ Strengths")
                if c.key_strengths:
                    for s in c.key_strengths:
                        st.markdown(f"- {s}")
                else:
                    st.info("No strengths identified.")

                st.subheader("⚠️ Weaknesses")
                if c.key_weaknesses:
                    for w in c.key_weaknesses:
                        st.markdown(f"- {w}")
                else:
                    st.info("No weaknesses identified.")

                # ---------- EXECUTIVE SUMMARY ----------
                st.subheader("📝 Executive Summary")
                try:
                    summary = c.executive_summary
                    if isinstance(summary, dict):
                        st.markdown("**What they have:**")
                        st.write(summary.get("have", ""))
                        st.markdown("**What they lack:**")
                        st.write(summary.get("lack", ""))
                        st.markdown("**Risks & Gaps:**")
                        st.write(summary.get("risks_gaps", ""))
                        st.markdown("**Recommendation:**")
                        st.write(summary.get("recommendation", ""))
                    else:
                        st.text_area("Executive Summary", summary, height=300)
                except Exception:
                    st.text_area("Executive Summary", str(c.executive_summary), height=300)

                # ---------- WHY THIS SCORE ----------
                st.subheader("💡 Why This Score")
                try:
                    explanation = c.why_this_score
                    if isinstance(explanation, dict):
                        st.markdown("**Fully Met Requirements:**")
                        st.write(explanation.get("fully_met_requirements", ""))
                        st.markdown("**Partially Met Requirements:**")
                        st.write(explanation.get("partially_met_requirements", ""))
                        st.markdown("**Missing Requirements:**")
                        st.write(explanation.get("missing_requirements", ""))
                        st.markdown("**Explanation:**")
                        st.write(explanation.get("explanation", ""))
                    else:
                        st.text_area("Why This Score", explanation, height=300)
                except Exception:
                    st.text_area("Why This Score", str(c.why_this_score), height=300)

                # ---------- INTERVIEW FOCUS AREAS ----------
                st.subheader("🎯 Interview Focus Areas")
                if c.interview_focus_areas:
                    for i in c.interview_focus_areas:
                        st.markdown(f"- {i}")
                else:
                    st.info("No interview focus areas suggested.")

                # ---------- CRITICAL GAPS ----------
                if c.critical_gaps:
                    st.subheader("🚨 Critical Gaps")
                    for g in c.critical_gaps:
                        st.markdown(f"- {g}")

                # ---------- RED FLAGS ----------
                if c.red_flags:
                    st.subheader("⛔ Red Flags")
                    for r in c.red_flags:
                        st.markdown(f"- {r}")

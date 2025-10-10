import streamlit as st
from cv_assessment import CVAssessmentSystem
import tempfile
import os

st.set_page_config(page_title="Deep CV Assessment System", layout="wide")
st.title("📄 Deep CV Assessment System")

api_key = st.text_input("🔑 Enter OpenAI API Key", type="password")
mode = st.radio("Select Evaluation Mode:", ["Structured (Dashboard)", "Critical Narrative"])

# --- Upload Tender ---
req_file = st.file_uploader("📄 Upload Tender / Job Description", type=["pdf", "docx", "doc"])
selected_expert = None
job_text = ""

if req_file:
    suffix = os.path.splitext(req_file.name)[1] or ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(req_file.read())
        tender_path = tmp.name

    system_temp = CVAssessmentSystem(api_key=api_key or None)
    system_temp.load_job_requirements(tender_path)

    experts = system_temp.get_expert_names()
    if experts:
        selected_expert = st.selectbox("🎯 Select the specific Expert Role to evaluate for:", experts)
        if selected_expert:
            job_text = system_temp.get_expert_section(selected_expert)
            st.success(f"✅ Selected: {selected_expert}")
            st.text_area("📘 Preview of Selected Expert Requirements", job_text[:2000], height=250)
    else:
        st.warning("⚠️ No expert roles detected in this document.")

# --- Upload CVs ---
cv_files = st.file_uploader("👤 Upload Candidate CVs", type=["pdf", "docx", "doc"], accept_multiple_files=True)

if st.button("🚀 Run Assessment") and req_file and cv_files and (api_key or os.getenv("OPENAI_API_KEY")):
    with tempfile.TemporaryDirectory() as tmpdir:
        cv_folder = os.path.join(tmpdir, "cvs")
        os.makedirs(cv_folder, exist_ok=True)
        for file in cv_files:
            path = os.path.join(cv_folder, file.name)
            with open(path, "wb") as f:
                f.write(file.read())

        st.info("⏳ Processing CVs — please wait...")
        system = CVAssessmentSystem(api_key=api_key or None)

        if selected_expert and job_text:
            system.job_requirements = job_text
        else:
            system.load_job_requirements(tender_path)

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

            st.divider()
            st.markdown("## 🏆 Candidate Ranking (Based on Final Scores)")
            st.table([
                {"Rank": i + 1, "Candidate": r["candidate_name"], "Final Score": f"{r['final_score']:.2f}"}
                for i, r in enumerate(ranked)
            ])

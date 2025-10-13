import streamlit as st
import tempfile
import os
from cv_assessment import CVAssessmentSystem

# ======================================================
# 🎯 Streamlit App Setup
# ======================================================
st.set_page_config(page_title="CV Assessment System", layout="wide")
st.title("📊 CV Assessment System")

st.markdown("""
Use this tool to evaluate CVs against tender requirements.

**Steps:**
1. Upload the tender (Word or PDF)
2. Enter the exact expert position name (e.g. “Key Expert 1” or “KE1”)
3. Extract and review the expert section (editable)
4. Upload CVs for assessment
""")

# ======================================================
# ⚙️ Initialize System
# ======================================================
api_key = st.text_input("🔑 Enter your OpenAI API key:", type="password")
system = CVAssessmentSystem(api_key=api_key) if api_key else None

if not api_key:
    st.warning("Please enter your OpenAI API key to continue.")
    st.stop()

# ======================================================
# 📄 Upload Tender File
# ======================================================
tender_file = st.file_uploader("📁 Upload Tender File (DOCX or PDF)", type=["docx", "pdf"])
expert_name = st.text_input("🎯 Enter Expert Position Name (e.g. 'Key Expert 1', 'KE1', 'Key Expert 2')")

expert_section_text = ""

if tender_file and expert_name:
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(tender_file.name)[1]) as tmp:
        tmp.write(tender_file.read())
        tmp_path = tmp.name

    with st.spinner("🔍 Extracting expert section..."):
        expert_section_text = system.extract_expert_sections_by_bold(tmp_path, expert_name)

    if expert_section_text.strip():
        st.success(f"✅ Extracted Expert Section for '{expert_name}'")

        # -----------------------------------------------------
        # 🧩 Editable Preview before Assessment
        # -----------------------------------------------------
        st.subheader("📘 Preview of Extracted Expert Section (editable)")
        edited_expert_text = st.text_area("You can refine this text before assessment:", expert_section_text, height=400)

        expert_section_text = edited_expert_text
    else:
        st.warning("⚠️ Could not precisely locate that expert section. Please verify the name or content.")
        expert_section_text = ""

# ======================================================
# 🧾 Upload CV Folder
# ======================================================
cv_folder = st.text_input("📂 Enter CV Folder Path (on this server):")

if not cv_folder:
    st.info("Please provide the path to the folder containing CV files (.docx or .pdf).")
    st.stop()

mode = st.radio("🧠 Choose Evaluation Mode", ["Structured (80/20 Scoring)", "Critical Narrative"], horizontal=True)

if st.button("🚀 Run Assessment"):
    if not expert_section_text.strip():
        st.warning("⚠️ Please extract or provide an Expert Section before running the assessment.")
        st.stop()

    with st.spinner("⏳ Processing CVs — please wait..."):
        results = system.process_cv_folder(
            cv_folder=cv_folder,
            expert_section=expert_section_text,
            mode="critical" if "Critical" in mode else "structured"
        )

    if results:
        st.success("✅ Assessment Complete!")

        for res in results:
            st.markdown("---")
            st.subheader(f"👤 Candidate: {res['candidate_name']}")
            if res.get("overall_score") is not None:
                st.write(f"**Overall Score:** {res['overall_score']}/100")
            if res.get("fit_level"):
                st.write(f"**Fit Level:** {res['fit_level']}")

            st.markdown("### 📋 Evaluation Report")

            # ======================================================
            # 🧩 FIXED: Proper Markdown Rendering for Tables
            # ======================================================
            report = res["report"].strip()
            if report.startswith("|") or "### Evaluation Summary Table" in report:
                # Markdown mode: show tables & headings nicely formatted
                st.markdown("\n" + report, unsafe_allow_html=False)
            else:
                # Fallback for narrative outputs
                st.text(report)
    else:
        st.warning("⚠️ No results generated. Please check your inputs.")

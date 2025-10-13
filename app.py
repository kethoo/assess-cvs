import streamlit as st
import tempfile
import os
from cv_assessment import CVAssessmentSystem


st.set_page_config(page_title="CV Assessor", layout="wide")
st.title("📄 CV Assessment Tool")

# Keep expert section persistent
if "expert_section" not in st.session_state:
    st.session_state.expert_section = ""

api_key = st.text_input("🔑 Enter your OpenAI API Key", type="password")
system = CVAssessmentSystem(api_key=api_key)

st.markdown("---")

# --- 1️⃣ Upload Tender File ---
st.header("1️⃣ Upload Tender File")
tender_file = st.file_uploader("Upload the Tender Document (.docx or .pdf)", type=["docx", "pdf", "txt"])

tender_path = None
if tender_file:
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(tender_file.name)[1]) as tmp:
        tmp.write(tender_file.read())
        tender_path = tmp.name
    st.success(f"Tender uploaded: {tender_file.name}")

st.markdown("---")

# --- 2️⃣ Extract Expert Section ---
st.header("2️⃣ Extract Expert Section")
expert_name = st.text_input("Enter Expert Role (e.g., 'Key Expert 1', 'KE1', or 'Key expert 2')")

if tender_file and expert_name:
    if st.button("📘 Extract Expert Section"):
        extracted = system.extract_expert_sections_by_bold(tender_path, expert_name)
        if extracted.strip():
            st.session_state.expert_section = extracted
            st.success("✅ Expert section(s) extracted successfully!")
        else:
            st.warning("⚠️ Could not locate that expert section. Try a slightly different phrasing.")

# --- 📘 Expert Section Preview / Edit ---
if st.session_state.expert_section.strip():
    st.subheader("📘 Expert Section Preview (Editable):")
    st.session_state.expert_section = st.text_area(
        "You can edit the extracted section before assessment:",
        value=st.session_state.expert_section,
        height=400,
    )

st.markdown("---")

# --- 3️⃣ Upload CVs ---
st.header("3️⃣ Upload Candidate CVs")
cv_files = st.file_uploader("Upload one or more CVs (.docx or .pdf)", type=["docx", "pdf"], accept_multiple_files=True)
uploaded_cv_folder = None

if cv_files:
    uploaded_cv_folder = tempfile.mkdtemp()
    for cv_file in cv_files:
        cv_path = os.path.join(uploaded_cv_folder, cv_file.name)
        with open(cv_path, "wb") as f:
            f.write(cv_file.read())
    st.success(f"✅ {len(cv_files)} CV(s) uploaded and ready for assessment.")

st.markdown("---")

# --- 4️⃣ Choose Mode ---
st.header("4️⃣ Choose Evaluation Mode")
mode = st.radio(
    "Select Evaluation Mode:",
    ["Structured Evaluation", "Critical Narrative"],
    horizontal=True
)

st.markdown("---")

# --- 5️⃣ Run Assessment ---
if st.button("🚀 Run Assessment"):
    if not cv_files:
        st.error("⚠️ Please upload at least one CV before running.")
    elif not st.session_state.expert_section.strip():
        st.error("⚠️ Please extract or provide an Expert Section first.")
    else:
        with st.spinner("⏳ Processing CVs — please wait..."):
            try:
                results = system.process_cv_folder(
                    uploaded_cv_folder,
                    st.session_state.expert_section,
                    mode="critical" if mode == "Critical Narrative" else "structured"
                )
                st.success("✅ CV assessment completed!")

                for res in results:
                    with st.expander(f"👤 {res['candidate_name']}", expanded=False):
                        st.markdown(res["report"])
                        if res.get("overall_score"):
                            st.write(f"**Score:** {res['overall_score']}")
                        if res.get("fit_level"):
                            st.write(f"**Fit Level:** {res['fit_level']}")
                        st.markdown("---")

            except Exception as e:
                st.error(f"❌ Error during assessment: {e}")

st.markdown("---")

if st.button("🧹 Clear Expert Section"):
    st.session_state.expert_section = ""
    st.success("Expert section cleared. You can extract another one now.")

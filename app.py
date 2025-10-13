import streamlit as st
import tempfile
import os
from cv_assessment import CVAssessmentSystem

# --- Streamlit setup ---
st.set_page_config(page_title="CV Assessment Tool", layout="wide")
st.title("📄 CV Assessment Tool")

# --- Initialize session state ---
if "expert_section" not in st.session_state:
    st.session_state.expert_section = ""

# --- API Key input ---
api_key = st.text_input("🔑 Enter your OpenAI API Key", type="password")
system = CVAssessmentSystem(api_key=api_key)

st.markdown("---")

# --- 1️⃣ Upload Tender File ---
st.header("1️⃣ Upload Tender File")
tender_file = st.file_uploader("Upload the Tender Document (.docx or .pdf)", type=["docx", "pdf", "txt"])

tender_path = None
tender_text = ""

if tender_file:
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(tender_file.name)[1]) as tmp:
        tmp.write(tender_file.read())
        tender_path = tmp.name

    st.success(f"Tender uploaded: {tender_file.name}")

    tender_text = system.load_job_requirements(tender_path)
    st.write(f"📏 Tender text length: {len(tender_text)} characters")

    if st.checkbox("Show last 1000 characters of tender text"):
        st.text(tender_text[-1000:])

st.markdown("---")

# --- 2️⃣ Extract Expert Section ---
st.header("2️⃣ Extract Expert Section")

expert_name = st.text_input("Enter Expert Role (e.g., 'Key Expert 1', 'KE1', or 'Key expert 2')")

if tender_file and expert_name:
    if st.button("📘 Extract Expert Section"):
        if tender_file.name.lower().endswith(".docx"):
            extracted = system.extract_expert_sections_by_bold(tender_path, expert_name)
        else:
            extracted = system.load_job_requirements(tender_path)  # fallback for PDFs

        if extracted.strip():
            st.session_state.expert_section = extracted
            st.success("✅ Expert section(s) extracted successfully!")
        else:
            st.warning("⚠️ Could not locate that expert section. Try a different variant like 'KE1' or 'Key Expert 1'.")

# --- Expert section preview and editing ---
if st.session_state.expert_section.strip():
    st.subheader("📘 Preview of Extracted Expert Section:")
    st.session_state.expert_section = st.text_area(
        "You can edit the extracted text below before assessment:",
        value=st.session_state.expert_section,
        height=400,
    )

st.markdown("---")

# --- 3️⃣ Upload Candidate CVs ---
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

# --- 4️⃣ Select Evaluation Mode ---
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
        st.error("⚠️ Please upload at least one CV file before running the assessment.")
    elif not st.session_state.expert_section.strip():
        st.error("⚠️ Please extract or provide an Expert Section before running the assessment.")
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
                        if res.get("fit_level"):
                            st.write(f"**Mode:** {res['fit_level']}")
                        st.markdown("---")

            except Exception as e:
                st.error(f"❌ Error during assessment: {e}")

st.markdown("---")

# --- Optional reset button ---
if st.button("🧹 Clear Expert Section"):
    st.session_state.expert_section = ""
    st.success("Expert section cleared. You can extract another one now.")

import streamlit as st
from cv_assessment import CVAssessmentSystem
import tempfile
import os
import re
import pandas as pd
import json
from docx import Document
from io import BytesIO
from docx.shared import Inches
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL

# ------------------- STREAMLIT CONFIG -------------------

st.set_page_config(page_title="Deep CV Assessment System", layout="wide")
st.title("📄 Deep CV Assessment System")

# ------------------- SESSION STATE INITIALIZATION -------------------

if 'expert_section_text' not in st.session_state:
    st.session_state.expert_section_text = ""

if 'custom_criteria' not in st.session_state:
    st.session_state.custom_criteria = None

if 'criteria_generated' not in st.session_state:
    st.session_state.criteria_generated = False

if 'editable_df' not in st.session_state:
    st.session_state.editable_df = None

# ------------------- API KEY -------------------

api_key = st.text_input("🔑 Enter OpenAI API Key", type="password")

# ------------------- UPLOAD TENDER -------------------

req_file = st.file_uploader("📄 Upload Tender / Job Description", type=["pdf", "docx", "doc"])
tender_text = ""
tender_path = None

if req_file:
    suffix = os.path.splitext(req_file.name)[1] or ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(req_file.read())
        tender_path = tmp.name

    st.success(f"✅ Tender uploaded: {req_file.name}")

    system_temp = CVAssessmentSystem(api_key=api_key or None)
    tender_text = system_temp.load_job_requirements(tender_path)
    st.info("📘 Tender text loaded successfully.")

# ------------------- ROLE FOCUS SELECTION -------------------

st.markdown("### 🎯 Select Evaluation Focus")
role_focus = st.radio(
    "Choose the type of assessment focus:",
    ["Specific Role (80/20 weighting)", "General Role (100% general weighting)"],
    index=0,
)

# ------------------- SUPPORT FUNCTIONS -------------------

def extract_expert_section_llm(full_text: str, expert_name: str, api_key: str) -> str:
    """Extract expert section"""
    if not full_text or not expert_name or not api_key:
        return ""
    try:
        import openai
        client = openai.OpenAI(api_key=api_key)
        prompt = f"""You are analyzing a tender to extract requirements for "{expert_name}".
Extract only that expert's relevant content, preserving structure.
Separate multiple matches with "---SECTION BREAK---".
Document:
{full_text[:30000]}"""
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Extract only the requested section, no commentary."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=4000,
        )
        text = resp.choices[0].message.content.strip()
        if text == "NOT_FOUND" or not text:
            return ""
        return text.replace("---SECTION BREAK---", "\n\n" + "-" * 60 + "\n\n")
    except Exception as e:
        st.error(f"LLM extraction error: {e}")
        return ""


def generate_criteria_and_weights(section_text: str, general_context: str, api_key: str, total_weight: int = 80) -> dict:
    """Generate criteria JSON"""
    if not section_text or not api_key:
        return None
    try:
        import openai
        client = openai.OpenAI(api_key=api_key)
        prompt = f"""Generate 6–10 assessment criteria and assign weights totaling {total_weight}%.
Each item must include name, weight, rationale.
Return ONLY valid JSON like:
{{"criteria":[{{"name":"...","weight":25,"rationale":"..."}}]}}
TEXT:
{section_text[:8000]}
GENERAL CONTEXT:
{general_context[:2000]}"""
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Return only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=2000,
        )
        text = resp.choices[0].message.content.strip()
        text = re.sub(r"^```(json)?", "", text)
        text = re.sub(r"```$", "", text)
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match:
            text = match.group(1)
        data = json.loads(text)
        total = sum(c['weight'] for c in data['criteria'])
        if abs(total - total_weight) > 2:
            factor = total_weight / total
            for c in data['criteria']:
                c['weight'] = round(c['weight'] * factor, 1)
        return data
    except Exception as e:
        st.error(f"Error generating criteria: {e}")
        return None

# ------------------- SPECIFIC ROLE MODE -------------------

expert_name = ""

if role_focus == "Specific Role (80/20 weighting)":
    st.markdown("### 🧩 Enter the Expert Role Title")
    expert_name = st.text_input("Example: Key Expert 1, Team Leader", placeholder="Type role title")

    st.info("💡 Use AI to extract the section for this expert.")
    if st.button("🔍 Extract Expert Section (AI)", disabled=not (req_file and api_key and expert_name)):
        with st.spinner("Extracting..."):
            extracted = extract_expert_section_llm(tender_text, expert_name, api_key)
            st.session_state.expert_section_text = extracted or ""
            st.success("✅ Extracted successfully!")

    edited_section = st.text_area("📝 Expert Section Content (editable)", value=st.session_state.expert_section_text, height=400)
    st.session_state.expert_section_text = edited_section

    if st.session_state.expert_section_text and api_key:
        st.markdown("---")
        st.markdown("### 🎯 Generate or Edit Criteria (Specific Role)")
        if st.button("🧠 Generate Criteria (80/20 weighting)"):
            with st.spinner("Generating criteria..."):
                data = generate_criteria_and_weights(st.session_state.expert_section_text, tender_text, api_key, 80)
                if data:
                    st.session_state.custom_criteria = data
                    st.session_state.criteria_generated = True
                    st.session_state.editable_df = pd.DataFrame(data["criteria"])
                    st.success("✅ Criteria generated!")

# ------------------- GENERAL ROLE MODE -------------------

if role_focus == "General Role (100% general weighting)" and api_key and req_file:
    st.markdown("### 🧠 Generate or Edit Criteria (General Role)")
    if st.button("🧠 Generate Criteria (100% weighting)"):
        with st.spinner("Generating general criteria..."):
            data = generate_criteria_and_weights(tender_text, tender_text, api_key, 100)
            if data:
                st.session_state.custom_criteria = data
                st.session_state.criteria_generated = True
                st.session_state.editable_df = pd.DataFrame(data["criteria"])
                st.success("✅ General criteria generated!")

# ------------------- EDIT & SAVE CRITERIA -------------------

if st.session_state.criteria_generated and st.session_state.custom_criteria:
    st.markdown("---")
    st.markdown("### ✏️ Edit Your Criteria Table")
    st.info("You can add, edit, or remove rows. Click 💾 Save when finished.")
    edited_df = st.data_editor(
        st.session_state.editable_df,
        use_container_width=True,
        num_rows="dynamic",
        key="criteria_editor"
    )

    if st.button("💾 Save Final Criteria"):
        st.session_state.editable_df = edited_df
        st.session_state.custom_criteria = {"criteria": edited_df.to_dict(orient="records")}
        st.success("✅ Final criteria saved and ready for assessment!")

# ------------------- UPLOAD CVS -------------------

cv_files = st.file_uploader("👤 Upload Candidate CVs", type=["pdf", "docx", "doc"], accept_multiple_files=True)

# ------------------- RUN ASSESSMENT -------------------

st.markdown("---")
st.markdown("### 🚀 Step 4: Run Assessment")

results = []
ranked = []

if st.button("🚀 Run Assessment") and req_file and cv_files and (api_key or os.getenv("OPENAI_API_KEY")):
    with tempfile.TemporaryDirectory() as tmpdir:
        cv_folder = os.path.join(tmpdir, "cvs")
        os.makedirs(cv_folder, exist_ok=True)
        for file in cv_files:
            path = os.path.join(cv_folder, file.name)
            with open(path, "wb") as f:
                f.write(file.read())

        system = CVAssessmentSystem(api_key=api_key or None)

        if role_focus == "Specific Role (80/20 weighting)":
            combined = (
                f"--- GENERAL TENDER CONTEXT (20%) ---\n\n{tender_text[:5000]}\n\n"
                f"--- SPECIFIC EXPERT REQUIREMENTS (80%) ---\n\n{st.session_state.expert_section_text}"
            )
        else:
            combined = f"--- GENERAL ROLE (100%) ---\n\n{tender_text}"

        system.job_requirements = combined
        criteria = st.session_state.custom_criteria if st.session_state.criteria_generated else None
        results = system.process_cv_folder(cv_folder, mode="critical", custom_criteria=criteria)

        st.success(f"✅ Processed {len(results)} candidate(s)")
        ranked = sorted(results, key=lambda x: x.get("final_score", 0), reverse=True)
        st.table([{"Rank": i + 1, "Candidate": r["candidate_name"], "Final Score": f"{r['final_score']:.2f}"} for i, r in enumerate(ranked)])
        for r in ranked:
            with st.expander(f"{r['candidate_name']} — Critical Evaluation"):
                st.markdown(r["report"])

# ------------------- FINAL COMPARISON SUMMARY -------------------

if results:
    st.markdown("---")
    st.markdown("## 🧾 Final Candidate Comparison Summary")

    summary_rows = []
    for i, r in enumerate(ranked):
        report_text = r["report"]
        strengths_match = re.search(r"Strengths(.*?)Weaknesses", report_text, re.DOTALL | re.IGNORECASE)
        weaknesses_match = re.search(r"Weaknesses(.*?)(?:Tailoring|$)", report_text, re.DOTALL | re.IGNORECASE)
        strengths = strengths_match.group(1).strip().replace("\n", " ")[:200] if strengths_match else "-"
        weaknesses = weaknesses_match.group(1).strip().replace("\n", " ")[:200] if weaknesses_match else "-"
        summary_rows.append({
            "Rank": i + 1,
            "Candidate": r["candidate_name"],
            "Final Score": round(r["final_score"], 2),
            "Fit Level": r.get("fit_level", "N/A"),
            "Top Strengths": strengths,
            "Key Weaknesses": weaknesses
        })

    summary_df = pd.DataFrame(summary_rows)
    st.dataframe(summary_df, use_container_width=True, hide_index=True)

# ------------------- EXPORT RESULTS TO WORD -------------------

if results:
    st.markdown("---")
    st.markdown("### 📥 Download All Results")

    doc = Document()
    doc.add_heading("CV Assessment Results", level=1)

    # ----- Criteria Table -----
    if st.session_state.criteria_generated and st.session_state.custom_criteria:
        doc.add_heading("Assessment Criteria", level=2)
        table = doc.add_table(rows=1, cols=3, style="Table Grid")
        hdr_cells = table.rows[0].cells
        hdr_cells[0].text = 'Criterion'
        hdr_cells[1].text = 'Weight (%)'
        hdr_cells[2].text = 'Rationale'
        for c in st.session_state.custom_criteria["criteria"]:
            row_cells = table.add_row().cells
            row_cells[0].text = str(c.get("name", ""))
            row_cells[1].text = str(c.get("weight", ""))
            row_cells[2].text = str(c.get("rationale", ""))
        doc.add_paragraph("")

    # ----- Comparison Summary -----
    doc.add_heading("Candidate Comparison Summary", level=2)
    compare_table = doc.add_table(rows=1, cols=5, style="Table Grid")
    ch = compare_table.rows[0].cells
    ch[0].text = "Rank"
    ch[1].text = "Candidate"
    ch[2].text = "Final Score"
    ch[3].text = "Top Strengths"
    ch[4].text = "Key Weaknesses"
    for row in summary_rows:
        r_cells = compare_table.add_row().cells
        r_cells[0].text = str(row["Rank"])
        r_cells[1].text = row["Candidate"]
        r_cells[2].text = str(row["Final Score"])
        r_cells[3].text = row["Top Strengths"]
        r_cells[4].text = row["Key Weaknesses"]
    doc.add_paragraph("")

    # ----- Detailed Reports with Markdown-to-Table Conversion -----
    doc.add_heading("Detailed Evaluations", level=2)

    def add_markdown_table(doc, markdown_text):
        lines = [line.strip() for line in markdown_text.strip().split("\n") if "|" in line]
        if len(lines) < 2:
            return False
        headers = [h.strip() for h in lines[0].split("|") if h.strip()]
        rows = []
        for line in lines[2:]:
            row = [c.strip() for c in line.split("|") if c.strip()]
            if row:
                rows.append(row)
        table = doc.add_table(rows=1, cols=len(headers), style="Table Grid")
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        hdr_cells = table.rows[0].cells
        for i, h in enumerate(headers):
            hdr_cells[i].text = h
            for p in hdr_cells[i].paragraphs:
                p.runs[0].font.bold = True
        for row in rows:
            row_cells = table.add_row().cells
            for i, cell_text in enumerate(row):
                if i < len(row_cells):
                    row_cells[i].text = cell_text
        doc.add_paragraph("")
        return True

    for i, r in enumerate(ranked):
        doc.add_heading(f"{i+1}. {r['candidate_name']}", level=3)
        report_text = r["report"].replace("**", "").replace("#", "")
        segments = re.split(r"(\|.*\|)", report_text)
        for seg in segments:
            if "|" in seg and "---" in report_text:
                if not add_markdown_table(doc, seg):
                    doc.add_paragraph(seg)
            else:
                doc.add_paragraph(seg)
        doc.add_paragraph("-" * 80)

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)

    st.download_button(
        label="📥 Download Full Assessment Report (Word)",
        data=buffer,
        file_name="CV_Assessment_Report.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

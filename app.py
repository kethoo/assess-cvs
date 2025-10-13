import streamlit as st
from cv_assessment import CVAssessmentSystem
import tempfile
import os
import re
from docx import Document
import pandas as pd

# ------------------- STREAMLIT CONFIG -------------------

st.set_page_config(page_title="Deep CV Assessment System", layout="wide")
st.title("📄 Deep CV Assessment System")

# ------------------- SESSION STATE INITIALIZATION (MUST BE FIRST) -------------------

if 'expert_section_text' not in st.session_state:
    st.session_state.expert_section_text = ""

if 'custom_criteria' not in st.session_state:
    st.session_state.custom_criteria = None

if 'criteria_generated' not in st.session_state:
    st.session_state.criteria_generated = False

# ------------------- API KEY -------------------

api_key = st.text_input("🔑 Enter OpenAI API Key", type="password")

# ------------------- MODE SELECTION (LOCKED TO CRITICAL NARRATIVE) -------------------

mode = "Critical Narrative"  # Fixed mode

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

    # Load tender text
    system_temp = CVAssessmentSystem(api_key=api_key or None)
    tender_text = system_temp.load_job_requirements(tender_path)
    st.info("📘 Tender text loaded successfully.")

# ------------------- EXPERT NAME -------------------

st.markdown("### 🎯 Enter the Expert Role Title")
expert_name = st.text_input(
    "Example: Key Expert 1, Team Leader",
    placeholder="Type 'Key Expert 1', 'Key expert 1', etc.",
    key="expert_name_input"
)

# ------------------- EXTRACTION FUNCTIONS -------------------

def extract_expert_section_llm(full_text: str, expert_name: str, api_key: str) -> str:
    """Use LLM to intelligently extract expert section requirements"""
    if not full_text or not expert_name or not api_key:
        return ""
    
    try:
        import openai
        client = openai.OpenAI(api_key=api_key)
        
        prompt = f"""You are analyzing a tender document to extract requirements for a specific expert position.

EXPERT POSITION TO EXTRACT: "{expert_name}"

Your task:
1. Find ALL sections in the document that describe requirements, qualifications, responsibilities, or deliverables for this specific expert position
2. Extract the COMPLETE text for this position, including:
   - Job title and role description
   - Required qualifications (education, certifications)
   - Required experience (years, specific domains)
   - Technical skills and competencies
   - Responsibilities and tasks
   - Deliverables and outputs expected
   - Language requirements
   - Any other relevant requirements

IMPORTANT:
- Extract ONLY information relevant to "{expert_name}"
- Do NOT include information about other expert positions (e.g., if extracting Key Expert 1, exclude Key Expert 2, 3, etc.)
- Do NOT include general project background, budget, or administrative sections
- If the position appears in multiple places in the document, extract ALL occurrences
- Preserve the original text as much as possible
- If you find multiple sections, separate them with "---SECTION BREAK---"

TENDER DOCUMENT:
{full_text[:30000]}

Return ONLY the extracted text for "{expert_name}". If nothing is found, return exactly: "NOT_FOUND"
"""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a precise document extraction assistant. Extract only the requested content."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=4000
        )
        
        extracted = response.choices[0].message.content.strip()
        
        if extracted == "NOT_FOUND" or not extracted:
            return ""
        
        # Replace section breaks with consistent separator
        extracted = extracted.replace("---SECTION BREAK---", "\n\n" + "-"*60 + "\n\n")
        
        return extracted
    
    except Exception as e:
        st.error(f"LLM extraction error: {e}")
        return ""


def generate_criteria_and_weights(expert_section: str, general_context: str, api_key: str) -> dict:
    """Analyze expert requirements and generate custom criteria with appropriate weights"""
    if not expert_section or not api_key:
        return None
    
    try:
        import openai
        import json
        client = openai.OpenAI(api_key=api_key)
        
        prompt = f"""You are analyzing tender requirements to generate assessment criteria with appropriate weights.

Analyze the EXPERT REQUIREMENTS below and identify the most important evaluation criteria.

Your task:
1. Identify 6-10 key criteria that matter most for this position
2. Assign weights (as percentages) based on importance signals:
   - "REQUIRED", "MANDATORY", "ESSENTIAL" → Higher weight (20-30%)
   - "MUST HAVE", "MINIMUM" → High weight (15-20%)
   - "PREFERRED", "DESIRABLE", "ADVANTAGEOUS" → Medium weight (10-15%)
   - "BENEFICIAL", "ASSET" → Lower weight (5-10%)
3. Consider the job nature (Team Leader needs more leadership weight, Technical Expert needs more technical weight)
4. Ensure total weight = 80% (this covers the expert-specific requirements)

Return ONLY valid JSON in this exact format:
{{
  "criteria": [
    {{
      "name": "Leadership and team management experience",
      "weight": 25,
      "rationale": "Position requires managing a team of 5+ experts - explicitly marked as ESSENTIAL"
    }},
    {{
      "name": "Water sector domain expertise (10+ years)",
      "weight": 20,
      "rationale": "Minimum 10 years experience REQUIRED per ToR section 3.2"
    }}
  ]
}}

EXPERT REQUIREMENTS (80% focus):
{expert_section[:8000]}

GENERAL CONTEXT (for reference only):
{general_context[:2000]}

Return ONLY the JSON object with criteria and weights that sum to exactly 80."""

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at analyzing job requirements and determining assessment criteria importance. Return ONLY valid JSON."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=2000
        )
        
        result_text = response.choices[0].message.content.strip()
        
        # Clean JSON
        result_text = re.sub(r"^```(json)?", "", result_text)
        result_text = re.sub(r"```$", "", result_text)
        match = re.search(r"(\{.*\})", result_text, re.DOTALL)
        if match:
            result_text = match.group(1).strip()
        
        criteria_data = json.loads(result_text)
        
        # Validate weights sum to 80
        total_weight = sum(c['weight'] for c in criteria_data['criteria'])
        if abs(total_weight - 80) > 2:  # Allow 2% tolerance
            # Normalize to 80
            factor = 80 / total_weight
            for c in criteria_data['criteria']:
                c['weight'] = round(c['weight'] * factor, 1)
        
        return criteria_data
        
    except Exception as e:
        st.error(f"Error generating criteria: {e}")
        return None

# ------------------- EXTRACT BUTTON -------------------

st.info("💡 **AI Extraction**: The system will use GPT to intelligently identify and extract all requirements specific to your chosen expert position, automatically excluding other positions and irrelevant sections.")

extract_button = st.button("🔍 Extract Expert Section (AI-Powered)", disabled=not (req_file and expert_name.strip() and tender_path and api_key))

if extract_button:
    with st.spinner("🤖 Using AI to intelligently extract requirements for this position..."):        
        expert_section = extract_expert_section_llm(tender_text, expert_name, api_key)
        
        if expert_section:
            st.session_state.expert_section_text = expert_section
            # Count sections (separated by the long dashes)
            num_sections = expert_section.count('------------------------------------------------------------') + 1
            st.success(f"✅ Extracted {len(expert_section)} characters from {num_sections} section(s) for: {expert_name}")
            st.info("📜 Scroll down to review the extracted content in the text area below ⬇️")
        else:
            st.session_state.expert_section_text = ""
            st.warning("⚠️ AI couldn't find specific requirements for this position. Try:\n- Different spelling (e.g., 'Key Expert 1' vs 'Expert 1')\n- Or paste content manually below")

# ------------------- EDITABLE PREVIEW -------------------

if req_file and expert_name.strip():
    st.markdown("### 📝 Expert Section Preview & Edit")
    
    # Debug: Show what's in session state
    if st.session_state.expert_section_text:
        st.write(f"🔍 Debug: Session state has {len(st.session_state.expert_section_text)} characters")
    
    edited_section = st.text_area(
        "Expert Section Content (editable)",
        value=st.session_state.expert_section_text,
        height=400,
        help="Edit as needed. This will be used with 80% weight."
    )
    
    # Update session state if user edits
    st.session_state.expert_section_text = edited_section
    
    if st.session_state.expert_section_text:
        num_sections = st.session_state.expert_section_text.count('----------------------------------------------------------') + 1
        st.info(f"📊 {len(st.session_state.expert_section_text)} chars | {num_sections} section(s) found | Sections separated by dashes")
    else:
        st.info("👆 Click 'Extract Expert Section' button above to automatically extract, or paste content manually here")

# ------------------- GENERATE ASSESSMENT CRITERIA -------------------

if st.session_state.expert_section_text and api_key:
    st.markdown("---")
    st.markdown("### 🎯 Step 3: Generate Custom Assessment Criteria")
    
    st.info("💡 **Adaptive Weighting**: The AI will analyze your expert requirements and create custom criteria with weights based on what's REQUIRED vs PREFERRED in the tender.")
    
    if st.button("🧠 Generate Assessment Criteria", disabled=not st.session_state.expert_section_text):
        with st.spinner("🤖 Analyzing requirements and generating weighted criteria..."):
            criteria_data = generate_criteria_and_weights(
                st.session_state.expert_section_text,
                tender_text,
                api_key
            )
            
            if criteria_data:
                st.session_state.custom_criteria = criteria_data
                st.session_state.criteria_generated = True
                st.success("✅ Custom assessment criteria generated!")
                st.rerun()
    
    # Display generated criteria
    if st.session_state.criteria_generated and st.session_state.custom_criteria:
        st.markdown("#### 📋 Assessment Criteria & Weights")
        
        import pandas as pd
        
        # Create dataframe for display
        criteria_list = st.session_state.custom_criteria['criteria']
        df = pd.DataFrame([
            {
                "Criterion": c['name'],
                "Weight (%)": c['weight'],
                "Rationale": c['rationale']
            }
            for c in criteria_list
        ])
        
        # Add general context row
        general_row = pd.DataFrame([{
            "Criterion": "General Tender Context",
            "Weight (%)": 20,
            "Rationale": "Understanding of overall project and regional context"
        }])
        
        df_display = pd.concat([general_row, df], ignore_index=True)
        
        # Calculate total
        total_weight = df_display["Weight (%)"].sum()
        total_row = pd.DataFrame([{
            "Criterion": "**TOTAL**",
            "Weight (%)": f"**{total_weight}%**",
            "Rationale": ""
        }])
        
        df_display = pd.concat([df_display, total_row], ignore_index=True)
        
        st.dataframe(df_display, use_container_width=True, hide_index=True)
        
        if total_weight == 100:
            st.success("✅ Weights sum to 100% - Ready for assessment!")
        else:
            st.warning(f"⚠️ Weights sum to {total_weight}% (should be 100%)")
        
        # Option to regenerate
        if st.button("🔄 Regenerate Criteria"):
            st.session_state.criteria_generated = False
            st.session_state.custom_criteria = None
            st.rerun()
        
        st.markdown("---")

# ------------------- UPLOAD CVS -------------------

cv_files = st.file_uploader(
    "👤 Upload Candidate CVs",
    type=["pdf", "docx", "doc"],
    accept_multiple_files=True
)

# ------------------- RUN ASSESSMENT -------------------

st.markdown("---")
st.markdown("### 🚀 Step 4: Run Assessment")

# Show status of preparation
if st.session_state.expert_section_text:
    st.success("✅ Expert section loaded")
else:
    st.warning("⚠️ No expert section loaded")

if st.session_state.criteria_generated:
    st.success("✅ Custom criteria generated")
else:
    st.info("💡 **Tip**: Generate custom criteria first for more accurate weighting!")

if st.button("🚀 Run Assessment") and req_file and cv_files and expert_name.strip() and (api_key or os.getenv("OPENAI_API_KEY")):
    with tempfile.TemporaryDirectory() as tmpdir:
        cv_folder = os.path.join(tmpdir, "cvs")
        os.makedirs(cv_folder, exist_ok=True)

        for file in cv_files:
            path = os.path.join(cv_folder, file.name)
            with open(path, "wb") as f:
                f.write(file.read())

        st.info("⏳ Processing CVs...")

        system = CVAssessmentSystem(api_key=api_key or None)
        expert_section = st.session_state.expert_section_text

        if not expert_section:
            st.warning("⚠️ No expert section. Using full tender.")
            combined_text = tender_text
        else:
            combined_text = (
                f"--- GENERAL TENDER CONTEXT (20% weight) ---\n\n"
                f"{tender_text[:5000]}\n\n"
                f"--- SPECIFIC EXPERT REQUIREMENTS (80% weight) ---\n\n"
                f"{expert_section}"
            )
            st.success(f"✅ Using expert section")

        system.job_requirements = combined_text
        
        # Pass custom criteria if available
        custom_criteria_data = st.session_state.custom_criteria if st.session_state.criteria_generated else None
        if custom_criteria_data:
            st.info(f"🎯 Using {len(custom_criteria_data['criteria'])} custom weighted criteria")
        
        results = system.process_cv_folder(cv_folder, mode="critical", custom_criteria=custom_criteria_data)

        st.success(f"✅ Processed {len(results)} candidate(s)")

        # ------------------- DISPLAY RESULTS (CRITICAL NARRATIVE MODE) -------------------

        ranked = sorted(results, key=lambda x: x.get("final_score", 0), reverse=True)
        st.markdown("## 🏆 Candidate Ranking")
        st.table([
            {
                "Rank": i + 1,
                "Candidate": r["candidate_name"],
                "Final Score": f"{r['final_score']:.2f}"
            }
            for i, r in enumerate(ranked)
        ])

        for r in ranked:
            with st.expander(f"{r['candidate_name']} — Critical Evaluation"):
                report = r["report"]
                if "✂️ Tailoring Suggestions" in report:
                    main, tailoring = report.split("✂️ Tailoring Suggestions", 1)
                    st.markdown(main)
                    with st.expander("✂️ Tailoring Suggestions"):
                        st.markdown("✂️ Tailoring Suggestions" + tailoring)
                else:
                    st.markdown(report)
                st.markdown(f"**🧮 Final Score:** {r['final_score']:.2f} / 1.00")

# ------------------- WARNINGS -------------------

else:
    if not api_key and not os.getenv("OPENAI_API_KEY"):
        st.warning("⚠️ Enter OpenAI API key to enable AI extraction and assessment")
    elif not expert_name.strip():
        st.warning("⚠️ Enter expert role title")
    elif not req_file:
        st.warning("⚠️ Upload tender file")
    elif not cv_files:
        st.warning("⚠️ Upload CVs")

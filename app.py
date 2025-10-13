import os
import re
import mammoth
from docx import Document
from openai import OpenAI

class CVAssessmentSystem:
    def __init__(self, api_key=None):
        self.api_key = api_key
        self.client = OpenAI(api_key=api_key) if api_key else None
        self.job_requirements = None

    # --- LOAD JOB REQUIREMENTS ---
    def load_job_requirements(self, file_path):
        """
        Loads tender/job description text.
        Uses mammoth for .docx, PyPDF2 for .pdf, and plain read for .txt/.doc.
        """
        ext = os.path.splitext(file_path)[1].lower()

        try:
            if ext == ".docx":
                with open(file_path, "rb") as f:
                    result = mammoth.extract_raw_text(f)
                return result.value

            elif ext == ".pdf":
                from PyPDF2 import PdfReader
                reader = PdfReader(file_path)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() or ""
                return text

            else:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    return f.read()

        except Exception as e:
            return f"⚠️ Error loading file: {e}"

    # --- NEW FLEXIBLE EXTRACTION (KE1/KE 1/Key Expert 1...) ---
    def extract_expert_sections_by_bold(self, docx_path, target_expert_name):
        """
        Extracts all occurrences of a given expert section (e.g. 'Key Expert 2' or 'KE2')
        and separates each block with ---------------.
        Case-insensitive, tolerant of spacing or abbreviation (Key Expert 1 == KE1).
        """
        try:
            doc = Document(docx_path)
        except Exception as e:
            return f"⚠️ Could not open document: {e}"

        text = " ".join(p.text.strip() for p in doc.paragraphs if p.text.strip())
        text = " ".join(text.split())  # normalize spaces

        target_expert_name = (
            target_expert_name.lower()
            .replace("(", "")
            .replace(")", "")
            .strip()
        )

        num_match = re.search(r"(?:key\s*expert\s*|ke\s*)(\d+)", target_expert_name, re.IGNORECASE)
        current_num = int(num_match.group(1)) if num_match else 1
        next_num = current_num + 1

        pattern = re.compile(
            rf"(?i)((?:Key\s*Expert\s*{current_num}\b|KE\s*{current_num}\b).*?)"
            rf"(?=(?:Key\s*Expert\s*(?:{next_num}|[1-9]\d*)\b|KE\s*(?:{next_num}|[1-9]\d*)\b|$))"
        )

        matches = pattern.findall(text)
        if not matches:
            matches = re.findall(
                rf"(?i)(?:Key\s*Expert\s*{current_num}\b|KE\s*{current_num}\b).*?(?=(?:Key\s*Expert|KE|$))",
                text,
            )

        clean_sections = [m.strip() for m in matches if len(m.strip()) > 30]
        if not clean_sections:
            return ""

        return "\n\n---------------\n\n".join(clean_sections)

    # --- INTERNAL OPENAI CALL WRAPPER ---
    def _ask_openai(self, prompt, temperature=0.2):
        if not self.client:
            return "⚠️ No OpenAI API key provided."
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"⚠️ Error from OpenAI API: {e}"

    # --- STRUCTURED EVALUATION (Classic Table with 80/20 split) ---
    def structured_assessment(self, cv_text, expert_section):
        """
        Compare CV to tender expert section using structured analysis with weighted scores.
        - 80% General experience
        - 20% Specific experience
        """
        prompt = f"""
You are an expert evaluator for EU tender CVs.

Compare the following CV to the expert requirements and provide a detailed structured assessment.

### EXPERT REQUIREMENTS:
{expert_section}

### CANDIDATE CV:
{cv_text}

Evaluate across these categories:

1. **Academic Qualifications**
   - Relevance of degree(s)
   - Minimum years required

2. **General Professional Experience**
   - Breadth of relevant experience
   - Duration and seniority
   - Management / leadership exposure

3. **Specific Professional Experience**
   - Experience in similar thematic fields or regions
   - Technical alignment with assignment
   - EU project exposure

4. **Language and Other Skills**
   - Languages required vs present
   - Other essential skills (communication, analytical, etc.)

Scoring rules:
- Each category is scored 0–100.
- Apply 80/20 weighting between General and Specific experience to form the overall score.
- Present your response as a markdown table followed by a concise narrative summary.

Output format example:

| Category | Score | Weight | Weighted Score | Notes |
|-----------|-------|---------|----------------|--------|
| Academic Qualifications | 90 | - | - | Degree matches requirements |
| General Experience | 85 | 0.8 | 68 | 12+ years, solid management background |
| Specific Experience | 75 | 0.2 | 15 | 5 years in target field |
| Language & Other Skills | 100 | - | - | Fluent English |
| **TOTAL** | **-** | **-** | **83** | Overall fit strong |

Then provide:
- **Strengths**
- **Weaknesses**
- **Final Evaluation Summary** (Short paragraph)
"""
        return self._ask_openai(prompt, temperature=0.2)

    # --- CRITICAL (DETAILED GAP) EVALUATION ---
    def critical_assessment(self, cv_text, expert_section):
        """
        Produces a critical risk/gap evaluation with recommendations.
        """
        prompt = f"""
You are a senior evaluator for EU tender experts.

### EXPERT REQUIREMENTS:
{expert_section}

### CANDIDATE CV:
{cv_text}

Perform a **critical narrative evaluation**:
- Identify explicit and implicit gaps between CV and requirements.
- Point out missing or weak criteria (e.g., lack of years, region experience).
- Highlight risks to eligibility or competitiveness.
- Conclude with a recommendation: **Highly Suitable / Suitable / Borderline / Not Suitable**.
"""
        return self._ask_openai(prompt, temperature=0.3)

    # --- MAIN CV PROCESSING PIPELINE ---
    def process_cv_folder(self, cv_folder, expert_section, mode="structured"):
        """
        Processes all CVs in a folder for structured or critical evaluation.
        """
        if not os.path.exists(cv_folder):
            return [{"candidate_name": "⚠️ Folder not found", "report": "", "fit_level": ""}]

        results = []
        for file_name in os.listdir(cv_folder):
            file_path = os.path.join(cv_folder, file_name)
            if not os.path.isfile(file_path):
                continue

            candidate_name = os.path.splitext(file_name)[0]

            # --- Extract CV text ---
            ext = os.path.splitext(file_name)[1].lower()
            if ext == ".docx":
                with open(file_path, "rb") as f:
                    cv_text = mammoth.extract_raw_text(f).value
            elif ext == ".pdf":
                from PyPDF2 import PdfReader
                reader = PdfReader(file_path)
                cv_text = "".join([p.extract_text() or "" for p in reader.pages])
            else:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    cv_text = f.read()

            # --- Choose mode ---
            if mode == "critical":
                report = self.critical_assessment(cv_text, expert_section)
                fit = "Critical Narrative"
            else:
                report = self.structured_assessment(cv_text, expert_section)
                fit = "Structured Evaluation"

            results.append({
                "candidate_name": candidate_name,
                "report": report,
                "fit_level": fit
            })

        return results

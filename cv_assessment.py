import os
import re
import mammoth
from openai import OpenAI
from docx import Document
from models import *


class CVAssessmentSystem:
    def __init__(self, api_key=None):
        self.api_key = api_key
        self.client = OpenAI(api_key=api_key) if api_key else None
        self.job_requirements = None
        self.model_temperature = 0.3

    # ======================================================
    # 🧩 NEW FLEXIBLE EXTRACTION METHOD (Bold + KE-aware)
    # ======================================================
    def extract_expert_sections_by_bold(self, docx_path, target_expert_name):
        """
        Extract all occurrences of a given expert section (e.g. 'Key Expert 2' or 'KE2')
        and separate each block with ---------------.
        Case-insensitive, tolerant of spacing or abbreviation (Key Expert 1 == KE1).
        """
        try:
            doc = Document(docx_path)
        except Exception as e:
            return f"⚠️ Could not open document: {e}"

        text = " ".join(p.text.strip() for p in doc.paragraphs if p.text.strip())
        text = " ".join(text.split())

        # Normalize expert name
        target_expert_name = (
            target_expert_name.lower()
            .replace("(", "")
            .replace(")", "")
            .strip()
        )

        # Extract expert number (1,2,3...)
        num_match = re.search(r"(?:key\s*expert\s*|ke\s*)(\d+)", target_expert_name, re.IGNORECASE)
        current_num = int(num_match.group(1)) if num_match else 1
        next_num = current_num + 1

        # Regex to find each expert section
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

    # ======================================================
    # 📄 JOB REQUIREMENT LOADER
    # ======================================================
    def load_job_requirements(self, file_path):
        ext = os.path.splitext(file_path)[1].lower()
        try:
            if ext == ".docx":
                with open(file_path, "rb") as f:
                    result = mammoth.extract_raw_text(f)
                return result.value
            elif ext == ".pdf":
                from PyPDF2 import PdfReader
                reader = PdfReader(file_path)
                return "".join([page.extract_text() or "" for page in reader.pages])
            else:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    return f.read()
        except Exception as e:
            return f"⚠️ Error loading file: {e}"

    # ======================================================
    # 📜 CV TEXT EXTRACTION
    # ======================================================
    def _extract_text_from_cv(self, path):
        ext = os.path.splitext(path)[1].lower()
        if ext == ".docx":
            with open(path, "rb") as f:
                return mammoth.extract_raw_text(f).value
        elif ext == ".pdf":
            from PyPDF2 import PdfReader
            reader = PdfReader(path)
            return "".join([p.extract_text() or "" for p in reader.pages])
        else:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()

    # ======================================================
    # 🧮 ORIGINAL STRUCTURED ASSESSMENT (80/20)
    # ======================================================
    def structured_assessment(self, cv_text, expert_section):
        """
        Returns markdown table-based evaluation (80/20 weighting) exactly like before.
        """
        prompt = f"""
You are an EU tender evaluator. Compare the CV to the Expert Requirements.

### EXPERT REQUIREMENTS
{expert_section}

### CANDIDATE CV
{cv_text}

Evaluate strictly in this format:

## Evaluation of Candidate CV Against Expert Requirements

### Evaluation Summary Table
| Category | Description | Weight | Score (0–100) | Weighted Score | Notes |
|-----------|--------------|---------|----------------|----------------|--------|
| Academic Qualifications | Education level and relevance | - | [score] | - | [brief note] |
| General Professional Experience | Years, managerial exposure, relevance | 0.8 | [score] | [score*0.8] | [brief note] |
| Specific Professional Experience | Relevance to field/geography/EU context | 0.2 | [score] | [score*0.2] | [brief note] |
| Language & Other Skills | English, communication, IT | - | [score] | - | [brief note] |

**Total Weighted Score:** [total_score]/100  
**Fit Level:** High / Medium / Low  

### Major Strengths
- Bullet points summarizing clear strengths

### Weaknesses / Gaps
- Bullet points summarizing missing or weak points

### Summary
Short 3–5 line summary of overall fit.
"""
        return self._ask_openai(prompt, temperature=0.25)

    # ======================================================
    # 🧩 ORIGINAL CRITICAL ASSESSMENT (unchanged)
    # ======================================================
    def critical_assessment(self, cv_text, expert_section):
        """
        Critical narrative mode (same as old version).
        """
        prompt = f"""
You are an EU tender evaluator performing a critical assessment.

### EXPERT REQUIREMENTS
{expert_section}

### CANDIDATE CV
{cv_text}

Write the evaluation exactly as before:

## Evaluation of Candidate CV Against Expert Requirements

### Major Strengths
[List bullet points]

### Weaknesses / Gaps
[List bullet points]

### Risks Related to Eligibility or Delivery
[List bullet points]

### Final Recommendation
Conclude with one line: Highly Suitable / Suitable / Borderline / Not Suitable

Then restate:
**Fit Level:** Critical Narrative
"""
        return self._ask_openai(prompt, temperature=0.3)

    # ======================================================
    # 🧠 OPENAI HELPER
    # ======================================================
    def _ask_openai(self, prompt, temperature=0.25):
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

    # ======================================================
    # 🔎 SCORE & FIT HELPERS
    # ======================================================
    def _extract_score_from_text(self, text):
        match = re.search(r"(\b\d{1,3}\b)\s*/\s*100", text)
        if match:
            try:
                val = int(match.group(1))
                return min(max(val, 0), 100)
            except:
                return None
        match = re.search(r"Total\s*Weighted\s*Score\s*[:\-]?\s*(\d{1,3})", text)
        if match:
            return int(match.group(1))
        return None

    def _derive_fit_from_report(self, text):
        if re.search(r"high(ly)?\s*suitab|strong|excellent|outstanding", text, re.I):
            return "High Fit"
        if re.search(r"adequate|satisf|medium|good", text, re.I):
            return "Medium Fit"
        if re.search(r"borderline|weak|limited|low", text, re.I):
            return "Low Fit"
        if re.search(r"not\s*suitab", text, re.I):
            return "Not Suitable"
        return "Unclassified"

    # ======================================================
    # 🪄 SELF-CONTAINED FOLDER PROCESSOR
    # ======================================================
    def process_cv_folder(self, cv_folder, expert_section, mode="structured"):
        """
        Processes all CVs in a folder using the restored logic.
        """
        if not os.path.exists(cv_folder):
            return [{"candidate_name": "⚠️ Folder not found", "report": "", "fit_level": ""}]

        results = []
        for file_name in os.listdir(cv_folder):
            file_path = os.path.join(cv_folder, file_name)
            if not os.path.isfile(file_path):
                continue

            candidate_name = os.path.splitext(file_name)[0]
            cv_text = self._extract_text_from_cv(file_path)

            if mode == "critical":
                report = self.critical_assessment(cv_text, expert_section)
            else:
                report = self.structured_assessment(cv_text, expert_section)

            score = self._extract_score_from_text(report)
            fit = self._derive_fit_from_report(report)
            results.append({
                "candidate_name": candidate_name,
                "report": report,
                "overall_score": score,
                "fit_level": fit,
            })
        return results

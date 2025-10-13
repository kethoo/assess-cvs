import os
import re
import mammoth
from docx import Document
from openai import OpenAI
import json
import time


class CVAssessmentSystem:
    def __init__(self, api_key=None):
        self.api_key = api_key
        self.client = OpenAI(api_key=api_key) if api_key else None
        self.job_requirements = None

    # ======================================================
    # 🧩 NEW FLEXIBLE EXTRACTION SYSTEM (Bold + KE-aware)
    # ======================================================
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
    # 🧠 ORIGINAL ALGORITHM: Tender Loading + Assessment
    # ======================================================
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

    # ======================================================
    # 🧩 ORIGINAL ALGORITHM (Preserved)
    # ======================================================

    def process_cv_folder(self, cv_folder, expert_section, mode="structured"):
        """
        Main pipeline for processing CVs.
        Preserves your structured and critical algorithms.
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
                report, score, fit = self._critical_evaluation(cv_text, expert_section)
            else:
                report, score, fit = self._structured_evaluation(cv_text, expert_section)

            results.append({
                "candidate_name": candidate_name,
                "report": report,
                "final_score": score,
                "overall_score": score,
                "fit_level": fit
            })
        return results

    # --- helper: extract cv text ---
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
    # 🧮 STRUCTURED (80/20 WEIGHTED) EVALUATION
    # ======================================================
    def _structured_evaluation(self, cv_text, expert_section):
        """
        Generates structured table output using your previous logic.
        """
        prompt = f"""
You are a senior evaluator for EU tenders.
Compare the following CV against the Expert Requirements.

### EXPERT REQUIREMENTS
{expert_section}

### CANDIDATE CV
{cv_text}

Evaluate using the following categories:

| Category | Description | Weight |
|-----------|--------------|--------|
| Academic Qualifications | Education level and relevance | - |
| General Professional Experience | Years, scope, managerial exposure | 0.8 |
| Specific Professional Experience | Relevance to project domain, geography, EU context | 0.2 |
| Language & Other Skills | Languages, communication, IT | - |

Produce a **markdown table** showing:
- Raw scores (0–100)
- Weighted total (80/20 for general/specific)
- Comments per category

After the table, provide:
- **Overall Score (0–100)**
- **Fit Level**: High / Medium / Low
- **Narrative Summary**: 3–5 lines explaining reasoning.
"""
        report = self._ask_openai(prompt)
        fit_level = self._derive_fit_from_report(report)
        score = self._extract_score_from_text(report)
        return report, score, fit_level

    # ======================================================
    # 🧩 CRITICAL EVALUATION (Risk & Gap)
    # ======================================================
    def _critical_evaluation(self, cv_text, expert_section):
        """
        Produces detailed risk/gap report with recommendation.
        """
        prompt = f"""
You are a senior CV evaluator for EU tenders.
Provide a critical narrative review of this candidate.

### EXPERT REQUIREMENTS
{expert_section}

### CANDIDATE CV
{cv_text}

Focus on:
- Gaps vs required qualifications
- Risks in eligibility or performance
- Strengths that could compensate weaknesses
- A final recommendation: Highly Suitable / Suitable / Borderline / Not Suitable

Format the output as markdown with clear headings.
"""
        report = self._ask_openai(prompt, temperature=0.3)
        score = self._extract_score_from_text(report)
        fit_level = self._derive_fit_from_report(report)
        return report, score, fit_level

    # ======================================================
    # 🔍 SUPPORT UTILITIES (Fit, Score, API)
    # ======================================================
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

    def _extract_score_from_text(self, text):
        """Extract numeric score if GPT outputs one."""
        match = re.search(r"(\b\d{1,3}\b)\s*/\s*100", text)
        if match:
            try:
                val = int(match.group(1))
                return min(max(val, 0), 100)
            except:
                return None
        match = re.search(r"Total\s*[:\-]?\s*(\d{1,3})", text)
        if match:
            return int(match.group(1))
        return None

    def _derive_fit_from_report(self, text):
        """Roughly map narrative or score to fit level."""
        if re.search(r"high(ly)?\s*suitab|strong|excellent|outstanding", text, re.I):
            return "High Fit"
        if re.search(r"adequate|satisf|medium|good", text, re.I):
            return "Medium Fit"
        if re.search(r"borderline|weak|limited|low", text, re.I):
            return "Low Fit"
        if re.search(r"not\s*suitab", text, re.I):
            return "Not Suitable"
        return "Unclassified"

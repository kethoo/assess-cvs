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

    # --- FLEXIBLE EXPERT EXTRACTOR (CASE/ABBREV-AWARE) ---
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

        # Flatten paragraphs into one continuous text
        text = " ".join(p.text.strip() for p in doc.paragraphs if p.text.strip())
        text = " ".join(text.split())

        # Normalize expert input
        target_expert_name = (
            target_expert_name.lower()
            .replace("(", "")
            .replace(")", "")
            .strip()
        )

        # Extract expert number (e.g. 1, 2)
        num_match = re.search(r"(?:key\s*expert\s*|ke\s*)(\d+)", target_expert_name, re.IGNORECASE)
        current_num = int(num_match.group(1)) if num_match else 1
        next_num = current_num + 1

        # Regex pattern to find expert sections flexibly
        pattern = re.compile(
            rf"(?i)((?:Key\s*Expert\s*{current_num}\b|KE\s*{current_num}\b).*?)"
            rf"(?=(?:Key\s*Expert\s*(?:{next_num}|[1-9]\d*)\b|KE\s*(?:{next_num}|[1-9]\d*)\b|$))"
        )

        matches = pattern.findall(text)

        if not matches:
            # fallback manual search
            matches = re.findall(
                rf"(?i)(?:Key\s*Expert\s*{current_num}\b|KE\s*{current_num}\b).*?(?=(?:Key\s*Expert|KE|$))",
                text,
            )

        clean_sections = [m.strip() for m in matches if len(m.strip()) > 30]
        if not clean_sections:
            return ""

        return "\n\n---------------\n\n".join(clean_sections)

    # --- INTERNAL OPENAI WRAPPER ---
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

    # --- STRUCTURED EVALUATION ---
    def structured_assessment(self, cv_text, expert_section):
        """
        Compares candidate CV to expert requirements in a structured scoring format.
        """
        prompt = f"""
        You are an expert CV assessor.
        Compare the following CV against the expert section.

        === EXPERT REQUIREMENTS ===
        {expert_section}

        === CANDIDATE CV ===
        {cv_text}

        Evaluate based on:
        1. Academic qualifications
        2. General professional experience
        3. Specific professional experience
        4. Language and other skills

        Provide:
        - A detailed justification per category
        - A score (0–100) for each category
        - A total fit score and a short summary conclusion
        """

        return self._ask_openai(prompt)

    # --- CRITICAL EVALUATION ---
    def critical_assessment(self, cv_text, expert_section):
        """
        Produces a deep evaluative report highlighting missing or risky areas.
        """
        prompt = f"""
        You are a senior evaluator for EU tenders.

        === EXPERT REQUIREMENTS ===
        {expert_section}

        === CANDIDATE CV ===
        {cv_text}

        Conduct a critical evaluation:
        - Identify explicit gaps vs. requirements
        - Flag any unclear or unverifiable claims
        - Estimate risk factors or weaknesses for selection
        - Provide a brief hiring recommendation

        Output format:
        - Key strengths
        - Key weaknesses
        - Risk summary
        - Overall recommendation (Yes / No / Borderline)
        """

        return self._ask_openai(prompt, temperature=0.3)

    # --- PROCESS CV FOLDER ---
    def process_cv_folder(self, cv_folder, expert_section, mode="structured"):
        """
        Process all CVs in a folder for either 'structured' or 'critical' evaluation.
        """
        if not os.path.exists(cv_folder):
            return [{"candidate_name": "⚠️ Folder not found", "report": "", "fit_level": ""}]

        results = []
        for file_name in os.listdir(cv_folder):
            file_path = os.path.join(cv_folder, file_name)
            if not os.path.isfile(file_path):
                continue

            candidate_name = os.path.splitext(file_name)[0]

            # --- Read CV text ---
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
                score = None
                fit = "Critical Review"
            else:
                report = self.structured_assessment(cv_text, expert_section)
                score = None
                fit = "Structured Evaluation"

            results.append({
                "candidate_name": candidate_name,
                "report": report,
                "final_score": score,
                "overall_score": score,
                "fit_level": fit,
            })

        return results

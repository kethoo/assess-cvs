import os
import re
import mammoth
from docx import Document

class CVAssessmentSystem:
    def __init__(self, api_key=None):
        self.api_key = api_key
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
                # Extract plain text for fallback or regex searches
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

    # --- ROBUST EXPERT SECTION EXTRACTOR (BOLD-INDEPENDENT) ---
    def extract_expert_sections_by_bold(self, docx_path, target_expert_name):
        """
        Extracts all occurrences of a given expert section (e.g. 'Key Expert 2')
        and separates each block with ---------------, regardless of bold formatting.
        Works even when Word formatting is inconsistent.
        """
        try:
            doc = Document(docx_path)
        except Exception as e:
            return f"⚠️ Could not open document: {e}"

        # Flatten the document into one continuous string
        text = " ".join(p.text.strip() for p in doc.paragraphs if p.text.strip())
        text = " ".join(text.split())  # normalize extra spaces

        # Normalize target expert
        target_expert_name = target_expert_name.lower().strip()
        num_match = re.search(r"\bKey\s*Expert\s*(\d+)\b", target_expert_name, re.IGNORECASE)
        current_num = int(num_match.group(1)) if num_match else 1
        next_num = current_num + 1

        # Regex pattern to find each Key Expert block
        pattern = re.compile(
            rf"(?i)(Key\s*Expert\s*{current_num}.*?)(?=Key\s*Expert\s*(?:{next_num}|[1-9]\d*)\b|$)"
        )

        matches = pattern.findall(text)

        # Fallback manual detection
        if not matches:
            matches = re.findall(rf"(?i)Key\s*Expert\s*{current_num}.*?(?=Key\s*Expert|$)", text)

        # Clean and join with separators
        clean_sections = [m.strip() for m in matches if len(m.strip()) > 30]
        if not clean_sections:
            return ""

        return "\n\n---------------\n\n".join(clean_sections)

    # --- CV PROCESSING (SIMPLIFIED PLACEHOLDER) ---
    def process_cv_folder(self, cv_folder, mode="structured"):
        """
        Placeholder implementation of CV analysis.
        In production, this method would compare each CV
        against self.job_requirements using LLM calls.
        """
        results = []
        for file_name in os.listdir(cv_folder):
            candidate_name = os.path.splitext(file_name)[0]

            # Simulated scoring and report
            results.append({
                "candidate_name": candidate_name,
                "report": (
                    f"🧠 Processed CV for **{candidate_name}** in {mode} mode.\n\n"
                    "This is a placeholder result. In production, "
                    "it would include detailed evaluation based on the "
                    "extracted expert section requirements."
                ),
                "final_score": 0.85 if mode == "critical" else None,
                "overall_score": 0.85 if mode == "structured" else None,
                "fit_level": "High"
            })

        return results

import os
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
        If .docx -> uses mammoth (plain text) fallback.
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

    # --- BOLD-BASED SECTION EXTRACTOR ---
    def extract_expert_sections_by_bold(self, docx_path, target_expert_name):
        """
        Extracts text between bold headings in a DOCX tender.
        For example: from 'Key Expert 1' up to (but not including) 'Key Expert 2'.
        """
        try:
            doc = Document(docx_path)
        except Exception as e:
            return f"⚠️ Could not open document: {e}"

        sections = []
        current_section = []
        capture = False
        target_expert_name = target_expert_name.lower().strip()

        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue

            # Detect bold heading
            is_bold = any(run.bold for run in para.runs if run.text.strip())

            # Check for "Key Expert" headings
            if is_bold and "key expert" in text.lower():
                # End previous section if capturing
                if capture:
                    sections.append(" ".join(current_section).strip())
                    current_section = []
                    capture = False

                # Start new capture if matches target expert
                if target_expert_name in text.lower():
                    capture = True
                    current_section.append(text)
                else:
                    # If we were capturing and a new expert starts, stop
                    if capture:
                        break
            elif capture:
                current_section.append(text)

        if current_section:
            sections.append(" ".join(current_section).strip())

        return "\n\n---------------\n\n".join(sections)

    # --- CV PROCESSING (DUMMY SIMPLIFIED IMPLEMENTATION) ---
    def process_cv_folder(self, cv_folder, mode="structured"):
        """
        Placeholder CV assessment logic.
        In production, this calls OpenAI or another LLM for evaluation.
        """
        results = []
        for file_name in os.listdir(cv_folder):
            candidate_name = os.path.splitext(file_name)[0]
            results.append({
                "candidate_name": candidate_name,
                "report": f"🧠 Processed {candidate_name}'s CV in {mode} mode.",
                "final_score": 0.85 if mode == "critical" else None,
                "overall_score": 0.85 if mode == "structured" else None,
                "fit_level": "High"
            })
        return results

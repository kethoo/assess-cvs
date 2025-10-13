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
        Uses mammoth for .docx, PyPDF2 for .pdf, and plain read for .txt/.doc.
        """
        ext = os.path.splitext(file_path)[1].lower()

        try:
            if ext == ".docx":
                # Extract plain text for fallback / regex searches
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
        Extracts all sections starting with bold headings matching the target expert.
        Each separate occurrence is separated by ---------------.

        Example:
            - Finds all bold 'Key Expert 2' headings
            - Captures all text until the next bold heading (any expert)
            - Joins multiple results with a separator
        """
        try:
            doc = Document(docx_path)
        except Exception as e:
            return f"⚠️ Could not open document: {e}"

        target_expert_name = target_expert_name.lower().strip()
        sections = []
        current_section = []
        capture = False

        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue

            # Detect bold paragraphs
            is_bold = any(run.bold for run in para.runs if run.text.strip())

            if is_bold and "key expert" in text.lower():
                # Starting a new bold heading
                if capture:
                    # Close previous section when we reach ANY bold Key Expert
                    sections.append(" ".join(current_section).strip())
                    current_section = []
                    capture = False

                # Start new capture if matches target expert
                if target_expert_name in text.lower():
                    capture = True
                    current_section.append(text)
                # If it's a different Key Expert and we were capturing, stop
                elif capture:
                    break
            elif capture:
                current_section.append(text)

        # Add final section if still open
        if current_section:
            sections.append(" ".join(current_section).strip())

        # --- 🔹 Join multiple sections cleanly ---
        if not sections:
            return ""
        return "\n\n---------------\n\n".join(sections)

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

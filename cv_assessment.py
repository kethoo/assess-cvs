import os
import json
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
from docx import Document
import PyPDF2
import openai

from models import CandidateAssessment


class CVAssessmentSystem:
    def __init__(self, api_key: str = None):
        """Initialize the CV assessment system"""
        self.client = openai.OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self.job_requirements = ""
        self.assessments: List[Any] = []
        self.session_id = f"assessment_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # ------------------- 🧠 HYBRID EXPERT EXTRACTION -------------------

    def extract_expert_sections_by_bold(self, file_path: str, expert_name: str) -> str:
        """
        Extracts expert sections using both bold text markers and expert numbering logic.
        Starts from the expert_name match and continues until another expert section or bold heading appears.
        Joins multiple found sections with '--------------'.
        """
        from docx import Document

        try:
            doc = Document(file_path)
        except Exception as e:
            return f"⚠️ Could not read Word file: {e}"

        sections = []
        current_section = []
        capture = False
        expert_pattern = re.compile(
            rf"(Key\s*Expert\s*\d+|KE\s*\d+|{re.escape(expert_name)})",
            re.IGNORECASE,
        )

        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue

            # Detect bold headings (potential new expert section)
            is_bold_heading = any(run.bold for run in para.runs if run.text.strip()) and len(text.split()) < 12

            # Start capturing when the expert title matches
            if expert_pattern.search(text):
                if capture and current_section:
                    sections.append(" ".join(current_section).strip())
                    current_section = []
                capture = True

            # Stop when we hit a new expert or a new bold heading
            elif capture and (re.search(r"Key\s*Expert\s*\d+", text, re.IGNORECASE) or is_bold_heading):
                sections.append(" ".join(current_section).strip())
                current_section = []
                capture = False

            if capture:
                current_section.append(text)

        # Add last captured section
        if current_section:
            sections.append(" ".join(current_section).strip())

        if not sections:
            return "⚠️ No expert sections detected using bold-based logic."

        # Join multiple sections cleanly
        joined = "\n\n--------------\n\n".join(sections)
        joined = re.sub(r"\s{2,}", " ", joined)
        return joined.strip()

    # ------------------- LOAD JOB REQUIREMENTS -------------------

    def load_job_requirements(self, file_path: str) -> str:
        """Load tender or job requirements from Word or PDF file (auto-detects type)."""
        with open(file_path, "rb") as f:
            header = f.read(4)
        try:
            if header.startswith(b"%PDF"):
                text = self._extract_text_from_pdf(file_path)
            else:
                text = self._extract_text_from_word(file_path)
        except Exception as e:
            raise ValueError(f"Cannot read file {file_path}: {e}")

        self.job_requirements = text
        print(f"✅ Loaded job requirements from: {file_path}")
        return text

    # ------------------- PROCESS CV FOLDER -------------------

    def process_cv_folder(self, folder_path: str, mode: str = "structured") -> List[Any]:
        """Process all CVs in a folder"""
        cv_files = []
        for ext in ["*.pdf", "*.PDF", "*.doc", "*.DOC", "*.docx", "*.DOCX"]:
            cv_files.extend(Path(folder_path).glob(ext))

        print(f"🔍 Found {len(cv_files)} CV files in {folder_path}")
        if not cv_files:
            print("⚠️ No CV files found! Check uploads.")
            return []

        for cv_file in cv_files:
            try:
                print(f"🧾 Processing: {cv_file.name}")
                cv_text = self._extract_cv_text(cv_file)
                if mode == "critical":
                    report = self._assess_candidate_critical(cv_file.name, cv_text)
                    self.assessments.append(report)
                else:
                    assessment = self._assess_candidate_structured(cv_file.name, cv_text)
                    self.assessments.append(assessment)
            except Exception as e:
                print(f"❌ Error processing {cv_file.name}: {e}")
                continue

        print(f"✅ Completed assessments for {len(self.assessments)} candidates.")
        return self.assessments

    # ------------------- FILE HELPERS -------------------

    def _extract_cv_text(self, file_path: Path) -> str:
        """Extract text from CV file"""
        if file_path.suffix.lower() == ".pdf":
            return self._extract_text_from_pdf(str(file_path))
        return self._extract_text_from_word(str(file_path))

    def _extract_text_from_pdf(self, file_path: str) -> str:
        """Extract text from PDF file"""
        text = []
        with open(file_path, "rb") as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text.append(page_text)
        return "\n".join(text)

    def _extract_text_from_word(self, file_path: str) -> str:
        """Extract text from Word document, preserving tables and merging broken lines."""
        from docx import Document
        doc = Document(file_path)
        lines = []

        for p in doc.paragraphs:
            text = p.text.strip()
            if text:
                lines.append(text)

        for table in doc.tables:
            for row in table.rows:
                row_text = " ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if row_text:
                    lines.append(row_text)

        merged = []
        buffer = ""
        for line in lines:
            if len(line) < 100 and not line.endswith((".", ":", ";")):
                buffer += " " + line
            else:
                buffer += " " + line
                merged.append(buffer.strip())
                buffer = ""
        if buffer:
            merged.append(buffer.strip())

        text = "\n".join(merged)
        text = re.sub(r"\s{2,}", " ", text)
        text = re.sub(r"(\w)-\s+(\w)", r"\1\2", text)
        return text.strip()

    # ------------------- STRUCTURED (DASHBOARD) MODE -------------------

    def _assess_candidate_structured(self, filename: str, cv_text: str) -> CandidateAssessment:
        """Structured scoring (dashboard mode)"""
        prompt = f"""
You are an HR evaluator performing a structured, detailed assessment of a candidate.

Compare the candidate’s CV to the job requirements below.
Assign numeric scores (0–100) and provide detailed reasoning for:
- Education
- Experience
- Skills
- Job-specific Fit

Return only valid JSON.

JOB REQUIREMENTS:
{self.job_requirements[:10000]}

CANDIDATE CV:
{cv_text[:12000]}
"""
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are an HR evaluation system. Return ONLY valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=9000,
            )

            raw_output = response.choices[0].message.content.strip()
            clean_json = self._clean_json(raw_output)
            data = json.loads(clean_json)

            return CandidateAssessment(
                candidate_name=data.get("candidate_name", filename),
                filename=filename,
                overall_score=data.get("summary", {}).get("overall_fit_score", 0),
                fit_level=data.get("summary", {}).get("fit_level", "Unknown"),
                education_details=data.get("scoring_breakdown", {}).get("education", {}),
                experience_details=data.get("scoring_breakdown", {}).get("experience", {}),
                skills_details=data.get("scoring_breakdown", {}).get("skills", {}),
                job_fit_details=data.get("scoring_breakdown", {}).get("job_specific_fit", {}),
                weighted_score_total=data.get("weighted_score_total", 0),
                executive_summary=data.get("executive_summary", {}),
                recommendation=data.get("recommendation", {}),
                interview_focus_areas=data.get("interview_focus_areas", []),
                red_flags=data.get("red_flags", []),
                potential_concerns=data.get("potential_concerns", []),
                assessed_at=datetime.now().isoformat(),
            )

        except Exception as e:
            print(f"❌ Error in structured assessment: {e}")
            return CandidateAssessment(
                candidate_name="Error",
                filename=filename,
                overall_score=0,
                fit_level="Error",
                education_details={},
                experience_details={},
                skills_details={},
                job_fit_details={},
                weighted_score_total=0,
                executive_summary={"recommendation": "Assessment failed"},
                recommendation={"verdict": "Error", "rationale": str(e)},
                interview_focus_areas=[],
                red_flags=[],
                potential_concerns=[],
                assessed_at=datetime.now().isoformat(),
            )

    # ------------------- CRITICAL + TAILORING MODE (RESTORED ORIGINAL) -------------------

    def _assess_candidate_critical(self, filename: str, cv_text: str) -> Dict[str, Any]:
        """Full critical narrative with donor logic and tailored feedback (restored)."""
        donor_query = f"""
        Identify the main funding organization mentioned or implied in this tender.
        Return ONLY the donor name (e.g., 'World Bank', 'European Union', 'ADB', 'USAID', 'UNDP', 'AfDB', 'Unknown').
        If uncertain, answer exactly 'Unknown'.
        TENDER TEXT (excerpt):
        {self.job_requirements[:8000]}
        """

        donor_match = "Unknown"
        try:
            resp = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": donor_query}],
                temperature=0,
                max_tokens=10,
            )
            donor_match = resp.choices[0].message.content.strip()
        except Exception as e:
            print(f"⚠️ Donor semantic detection failed, fallback triggered: {e}")

        text_lower = self.job_requirements.lower()
        donors = {
            "World Bank": r"\b(world\s*bank|wbg|ifc|ida|ibrd)\b",
            "European Union": r"\b(european\s*union|eu\s+delegation|europeaid|neighbourhood|dg\s*intl)\b",
            "Asian Development Bank": r"\b(asian\s+development\s+bank|adb)\b",
            "USAID": r"\b(usaid|united\s+states\s+agency\s+for\s+international\s+development)\b",
            "African Development Bank": r"\b(african\s+development\s+bank|afdb)\b",
            "UNDP": r"\b(undp|united\s+nations\s+development\s+programme)\b",
        }
        if donor_match == "Unknown":
            for name, pattern in donors.items():
                if re.search(pattern, text_lower):
                    donor_match = name
                    break
        if donor_match == "Unknown":
            donor_match = "General donor context"

        prompt = f"""
You are a senior evaluator assessing candidates for a tender funded by **{donor_match}**.

Perform a detailed, evidence-based critical evaluation of the candidate’s CV
against the JOB REQUIREMENTS and contextualize every criterion according to {donor_match}'s
typical focus and terminology.
Do not mention other donors (EU, ADB, etc.) unless explicitly stated in the tender or CV.
Focus exclusively on {donor_match} as the donor context.

Return a long, detailed narrative with:
- Major Strengths
- Weaknesses
- Relevance and Fit
- Executive Summary
- Tailoring Suggestions
- Final Score (0–1.0 as “FINAL SCORE: <value>”)
"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are an expert evaluator for international tenders."},
                    {"role": "user", "content": f"{prompt}\n\nJOB REQUIREMENTS:\n{self.job_requirements[:8000]}\n\nCANDIDATE CV:\n{cv_text[:9000]}"},
                ],
                temperature=0.35,
                max_tokens=4500,
            )

            report_text = response.choices[0].message.content.strip()
            match = re.search(r"FINAL SCORE[:\-]?\s*([0-9]\.?[0-9]*)", report_text, re.IGNORECASE)
            score = float(match.group(1)) if match else 0.0

            return {
                "candidate_name": filename,
                "report": report_text,
                "final_score": round(score, 2),
            }

        except Exception as e:
            print(f"❌ Critical narrative error for {filename}: {e}")
            return {
                "candidate_name": filename,
                "report": f"⚠️ Critical narrative failed: {e}",
                "final_score": 0.0,
            }

    # ------------------- JSON CLEANER -------------------

    def _clean_json(self, content: str) -> str:
        """Extract clean JSON from model output."""
        content = content.strip()
        content = re.sub(r"^```(json)?", "", content)
        content = re.sub(r"```$", "", content)
        match = re.search(r"(\{.*\})", content, re.DOTALL)
        if match:
            return match.group(1).strip()
        return content

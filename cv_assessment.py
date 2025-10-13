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

    # ------------------- 🧠 HYBRID EXPERT EXTRACTOR -------------------

    def extract_expert_sections_by_bold(self, file_path: str, expert_name: str) -> str:
        """
        Extracts expert sections using both bold text markers and expert numbering logic.
        Starts from the expert_name match and continues until another expert section or bold heading appears.
        Stops before the next expert (Key Expert 2 etc.) so nothing from that section appears.
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
            is_bold_heading = (
                any(run.bold for run in para.runs if run.text.strip())
                and len(text.split()) < 15
            )

            # Start capturing when the expert title matches
            if expert_pattern.search(text):
                if capture and current_section:
                    sections.append(" ".join(current_section).strip())
                    current_section = []
                capture = True

            # Stop when we hit a new expert or a new bold heading
            elif capture and (
                re.search(r"Key\s*Expert\s*\d+", text, re.IGNORECASE) or is_bold_heading
            ):
                # hard stop before new expert line
                cutoff = re.split(r"(?=Key\s*Expert\s*\d+|KE\s*\d+)", text, 1)[0].strip()
                if cutoff:
                    current_section.append(cutoff)
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

        # --- Read all paragraphs ---
        for p in doc.paragraphs:
            text = p.text.strip()
            if text:
                lines.append(text)

        # --- Read all tables (flattened row by row) ---
        for table in doc.tables:
            for row in table.rows:
                row_text = " ".join(
                    cell.text.strip() for cell in row.cells if cell.text.strip()
                )
                if row_text:
                    lines.append(row_text)

        # --- Merge lines intelligently ---
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
                    {
                        "role": "system",
                        "content": "You are an HR evaluation system. Return ONLY valid JSON.",
                    },
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

    # ------------------- CRITICAL (NARRATIVE) MODE -------------------

    def _assess_candidate_critical(self, filename: str, cv_text: str) -> Dict[str, Any]:
        """Critical narrative evaluation with donor detection and qualitative scoring."""
        donor_match = "Unknown"
        try:
            resp = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{
                    "role": "user",
                    "content": f"Identify the main funding organization mentioned in this tender:\n{self.job_requirements[:6000]}"
                }],
                temperature=0,
                max_tokens=20,
            )
            donor_match = resp.choices[0].message.content.strip()
        except Exception as e:
            print(f"⚠️ Donor detection failed: {e}")

        if not donor_match or donor_match.lower() == "unknown":
            donor_match = "General donor context"

        prompt = f"""
You are a senior evaluator assessing a candidate CV for a tender funded by **{donor_match}**.

Provide a critical, evidence-based narrative analysis with:
1. Major strengths
2. Major weaknesses
3. Overall fit
4. A final score between 0.0 and 1.0 as 'FINAL SCORE: <score>'

JOB REQUIREMENTS (summary):
{self.job_requirements[:7000]}

CANDIDATE CV:
{cv_text[:8000]}
"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are an expert evaluator for international tenders."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=2500,
            )
            report_text = response.choices[0].message.content.strip()

            match = re.search(r"FINAL SCORE[:\-]?\s*([0-9]\.?[0-9]*)", report_text, re.IGNORECASE)
            score = float(match.group(1)) if match else 0.0

            return {
                "candidate_name": filename,
                "report": report_text,
                "final_score": round(score, 2)
            }

        except Exception as e:
            print(f"❌ Critical mode error for {filename}: {e}")
            return {
                "candidate_name": filename,
                "report": f"⚠️ Critical narrative failed: {e}",
                "final_score": 0.0
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

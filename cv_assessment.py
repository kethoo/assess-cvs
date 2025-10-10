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

    # ------------------- LOAD TENDER & JOB REQUIREMENTS -------------------

    def load_job_requirements(self, file_path: str) -> str:
        """Load tender or job requirements from Word or PDF file"""
        file_extension = Path(file_path).suffix.lower()
        if file_extension == ".pdf":
            text = self._extract_text_from_pdf(file_path)
        elif file_extension in [".doc", ".docx"]:
            text = self._extract_text_from_word(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_extension}")
        self.job_requirements = text
        print(f"✅ Loaded job requirements from: {file_path}")
        return text

    # ------------------- EXPERT ROLE EXTRACTION -------------------

    def extract_expert_profiles(self) -> Dict[str, str]:
        """
        Parse the loaded job requirements text and extract sections for each expert profile.
        Returns a dictionary {expert_title: text_block}.
        """
        text = self.job_requirements
        profiles = {}

        pattern = re.compile(
            r"(Key|Non[- ]Key)\s*Expert\s*\d+\s*[-–]\s*[A-Za-z0-9 ,&()\/\-]+(?:(?:\n|.)*?)(?=(?:Key|Non[- ]Key)\s*Expert\s*\d+|$)",
            re.IGNORECASE
        )
        sections = pattern.finditer(text)
        for m in sections:
            title_line = m.group(0).split("\n")[0].strip()
            block = m.group(0).strip()
            profiles[title_line] = block

        print(f"✅ Extracted {len(profiles)} expert profiles from tender.")
        return profiles

    def get_expert_names(self) -> list:
        """Return a list of available expert titles for Streamlit dropdown."""
        profiles = self.extract_expert_profiles()
        return list(profiles.keys())

    def get_expert_section(self, selected_expert: str) -> str:
        """Return the text of the selected expert's section with general context."""
        profiles = self.extract_expert_profiles()
        section = profiles.get(selected_expert, "")
        context = self.job_requirements[:2000]  # first 2000 chars of general tender
        combined = f"{context}\n\n--- SPECIFIC ROLE FOCUS ---\n\n{section}"
        return combined

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
        """Extract text from Word document"""
        doc = Document(file_path)
        text = [p.text for p in doc.paragraphs]
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    text.append(cell.text)
        return "\n".join(text)

    # ------------------- STRUCTURED (DASHBOARD) MODE -------------------

    def _assess_candidate_structured(self, filename: str, cv_text: str) -> CandidateAssessment:
        """Structured scoring (dashboard mode)"""
        prompt = f"""
You are an HR evaluator performing a structured, detailed assessment of a candidate.

TASK:
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

    # ------------------- CRITICAL + TAILORING MODE -------------------

    def _assess_candidate_critical(self, filename: str, cv_text: str) -> Dict[str, Any]:
        """Critical narrative evaluation with final score and tailoring suggestions."""
        prompt = f"""
You are a senior evaluator and CV improvement consultant.

Perform a **Critical Evaluation** of this candidate's CV compared to the JOB REQUIREMENTS.

INSTRUCTIONS:
- Include a detailed evaluation table with scores (0–1) and confidence levels.
- After the table, compute and state a **Final Weighted Score** (e.g. 0.82 / 1.00).
- Include:
  📊 Critical Summary
  📉 Evaluator Summary
  📌 Strengths & Weaknesses
  ✂️ Tailoring Suggestions (How to Strengthen CV for This Role)
- Never invent experience.

JOB REQUIREMENTS:
{self.job_requirements[:7000]}

CANDIDATE CV:
{cv_text[:9000]}

FORMAT:
Markdown, structured, professional.
Always include: **Final Score (weighted average): X.XX / 1.00**
"""
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a critical evaluator and CV tailoring consultant. "
                            "Always include numeric scores, a final weighted score, and detailed suggestions."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.15,
                max_tokens=8500,
            )

            report_text = response.choices[0].message.content.strip()
            match = re.search(r"Final Score.*?([0-9]\.[0-9]+)", report_text)
            final_score = float(match.group(1)) if match else 0.0

            return {
                "candidate_name": filename,
                "report": report_text,
                "final_score": final_score,
            }

        except Exception as e:
            return {
                "candidate_name": filename,
                "report": f"❌ Error generating critical evaluation: {e}",
                "final_score": 0.0,
            }

    # ------------------- JSON CLEANER -------------------

    def _clean_json(self, content: str) -> str:
        """Extract clean JSON from model output."""
        content = content.strip()
        content = re.sub(r"^```(json)?", "", content)
        content = re.sub(r"```$", "", content)
        content = content.strip()
        match = re.search(r"(\{.*\})", content, re.DOTALL)
        if match:
            return match.group(1).strip()
        return content

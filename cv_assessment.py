import os
import json
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
        self.assessments: List[CandidateAssessment] = []
        self.session_id = f"assessment_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # ------------------- LOADING JOB REQUIREMENTS -------------------

    def load_job_requirements(self, file_path: str) -> str:
        """Load job requirements from Word or PDF file"""
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

    # ------------------- PROCESSING CANDIDATE CVS -------------------

    def process_cv_folder(self, folder_path: str, mode: str = "detailed") -> List[CandidateAssessment]:
        """Process all CVs in a folder"""
        cv_files = []
        # Handle both lower- and upper-case extensions
        for ext in ["*.pdf", "*.PDF", "*.doc", "*.DOC", "*.docx", "*.DOCX"]:
            cv_files.extend(Path(folder_path).glob(ext))

        print(f"🔍 Found {len(cv_files)} CV files in {folder_path}")
        if not cv_files:
            print("⚠️ No CV files found! Check that your uploads are saved correctly.")
            return []

        for cv_file in cv_files:
            try:
                print(f"🧾 Processing: {cv_file.name}")
                cv_text = self._extract_cv_text(cv_file)
                assessment = self._assess_candidate(cv_file.name, cv_text)
                self.assessments.append(assessment)
            except Exception as e:
                print(f"❌ Error processing {cv_file.name}: {e}")
                continue

        self.assessments.sort(key=lambda x: x.overall_score, reverse=True)
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

    # ------------------- CORE ASSESSMENT -------------------

    def _assess_candidate(self, filename: str, cv_text: str) -> CandidateAssessment:
        """Deep, reasoned candidate assessment using GPT"""

        prompt = f"""
You are a **senior HR director** and **domain expert**. Perform a **deep semantic assessment** of this candidate’s CV.

GOAL:
- Understand meaning and implications beyond keywords.
- Compare the candidate against the JOB REQUIREMENTS with clear evidence and reasoning.
- Write LONG, PRECISE, and HUMAN-like reasoning — not short bullet fragments.
- Explicitly describe what they HAVE, what they LACK, and WHY it matters.
- In the Recommendation section: write a **professional, paragraph-style hiring report** that argues for or against the candidate.
- In Job Fit: explain each **matched** and **missing requirement** with **multi-line reasoning** and real insight.

JOB REQUIREMENTS:
{self.job_requirements[:7000]}

CANDIDATE CV:
{cv_text[:9000]}

==============================
OUTPUT FORMAT (STRICT JSON)
==============================
{{
  "candidate_name": "",
  "summary": {{
    "headline": "",
    "total_experience_years": 0,
    "key_domains": [],
    "overall_fit_score": 0,
    "fit_level": "",
    "summary_reasoning": ""
  }},
  "scoring_breakdown": {{
    "education": {{
      "score": 0,
      "weight": 0.20,
      "details": {{
        "degrees": [],
        "relevance": "",
        "strengths": [],
        "gaps": [],
        "reasoning": ""
      }}
    }},
    "experience": {{
      "score": 0,
      "weight": 0.40,
      "details": {{
        "total_years": 0,
        "roles": [],
        "key_projects": [],
        "transferable_skills": [],
        "gaps": [],
        "reasoning": ""
      }}
    }},
    "skills": {{
      "score": 0,
      "weight": 0.25,
      "details": {{
        "skills_matched": [],
        "skills_missing": [],
        "certifications": [],
        "reasoning": ""
      }}
    }},
    "job_specific_fit": {{
      "score": 0,
      "weight": 0.15,
      "details": {{
        "alignment_summary": "",
        "matched_requirements": [],
        "missing_requirements": [],
        "reasoning": ""
      }}
    }}
  }},
  "weighted_score_total": 0,
  "executive_summary": {{
    "have": "",
    "lack": "",
    "risks_gaps": [],
    "recommendation": ""
  }},
  "recommendation": {{
    "verdict": "",
    "confidence": "",
    "rationale": ""
  }},
  "interview_focus_areas": [],
  "red_flags": [],
  "potential_concerns": [],
  "assessed_at": ""
}}
"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert HR professional and analyst. "
                            "Always produce long, reasoned, multi-paragraph analyses. "
                            "Explain your logic clearly and completely."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=9000,
            )

            content = self._clean_json(response.choices[0].message.content)
            data = json.loads(content)

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
            print(f"❌ Assessment error for {filename}: {e}")
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
                executive_summary={"have": "", "lack": "", "risks_gaps": [], "recommendation": "Assessment failed"},
                recommendation={"verdict": "Error", "confidence": "low", "rationale": str(e)},
                interview_focus_areas=[],
                red_flags=["Assessment failed"],
                potential_concerns=[],
                assessed_at=datetime.now().isoformat(),
            )

    # ------------------- JSON CLEANUP -------------------

    def _clean_json(self, content: str) -> str:
        """Clean model output for safe JSON parsing"""
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:-3]
        elif content.startswith("```"):
            content = content[3:-3]
        return content.strip()

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

    # ------------------- LOAD JOB REQUIREMENTS -------------------

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
Compare the candidate’s CV to the job requirements.
Assign numeric scores and provide detailed reasoning for:
- Education
- Experience
- Skills
- Job-specific Fit

If a section is missing information, infer or estimate it reasonably — do NOT leave fields blank.

OUTPUT:
Return ONLY valid JSON following exactly this structure (fill every field with meaningful data):

{{
  "candidate_name": "string",
  "summary": {{
    "headline": "string",
    "total_experience_years": int,
    "key_domains": ["string"],
    "overall_fit_score": int,
    "fit_level": "Excellent/Good/Fair/Poor",
    "summary_reasoning": "string"
  }},
  "scoring_breakdown": {{
    "education": {{
      "score": int,
      "weight": 0.20,
      "details": {{
        "degrees": ["string"],
        "relevance": "string",
        "strengths": ["string"],
        "gaps": ["string"],
        "reasoning": "string"
      }}
    }},
    "experience": {{
      "score": int,
      "weight": 0.40,
      "details": {{
        "total_years": int,
        "roles": ["string"],
        "key_projects": ["string"],
        "transferable_skills": ["string"],
        "gaps": ["string"],
        "reasoning": "string"
      }}
    }},
    "skills": {{
      "score": int,
      "weight": 0.25,
      "details": {{
        "skills_matched": ["string"],
        "skills_missing": ["string"],
        "certifications": ["string"],
        "reasoning": "string"
      }}
    }},
    "job_specific_fit": {{
      "score": int,
      "weight": 0.15,
      "details": {{
        "alignment_summary": "string",
        "matched_requirements": ["string"],
        "missing_requirements": ["string"],
        "reasoning": "string"
      }}
    }}
  }},
  "weighted_score_total": int,
  "executive_summary": {{
    "have": "string",
    "lack": "string",
    "risks_gaps": ["string"],
    "recommendation": "string"
  }},
  "recommendation": {{
    "verdict": "Hire / Consider / Reject",
    "confidence": "High / Moderate / Low",
    "rationale": "string"
  }},
  "interview_focus_areas": ["string"],
  "red_flags": ["string"],
  "potential_concerns": ["string"],
  "assessed_at": "ISO8601 timestamp"
}}

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
                        "content": (
                            "You are an HR evaluation system. "
                            "Return ONLY valid, fully populated JSON. Never leave fields blank. "
                            "If unsure, infer logically from context."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=9000,
                stop=["```", "\n\n\n"],
            )

            raw_output = response.choices[0].message.content.strip()
            print("=== RAW MODEL OUTPUT (first 1000 chars) ===")
            print(raw_output[:1000])

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

        except json.JSONDecodeError as e:
            print(f"❌ JSON parsing failed for {filename}: {e}")
            print("=== RAW OUTPUT ===")
            print(raw_output)
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
                executive_summary={"have": "", "lack": "", "risks_gaps": [], "recommendation": "Invalid JSON"},
                recommendation={"verdict": "Error", "confidence": "low", "rationale": "Invalid JSON returned"},
                interview_focus_areas=[],
                red_flags=["Assessment failed"],
                potential_concerns=[],
                assessed_at=datetime.now().isoformat(),
            )

        except Exception as e:
            print(f"❌ Assessment error: {e}")
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

    # ------------------- CRITICAL + TAILORING MODE -------------------

    def _assess_candidate_critical(self, filename: str, cv_text: str) -> Dict[str, Any]:
        """Generate a detailed evaluator-style narrative report, with CV tailoring suggestions."""
        prompt = f"""
You are a senior evaluator AND a strategic CV coach working for an international development agency (World Bank / ADB / EU).

TASK:
1️⃣ Perform a **Critical Evaluation** of this candidate's CV compared to the JOB REQUIREMENTS.  
   - Use the structure of a professional evaluator report.
   - Include numerical scores (0–1), confidence levels, and commentary.
   - Focus on evidence-based criticism (be analytical and skeptical, not promotional).

2️⃣ Add a new section titled **"✂️ Tailoring Suggestions (How to Strengthen CV for This Role)"**:
   - Analyze the job requirements and the candidate’s CV.
   - Identify where the candidate’s actual experience could match the requirements if phrased differently or highlighted better.
   - Suggest concrete rewrites or emphasis changes that make the CV more aligned.
   - Never invent new experience.
   - Include both the **original phrasing** and the **suggested improved version**.
   - Recommend additional keywords, structure, or section adjustments to increase alignment.

FORMAT:
- Write the full output in Markdown.
- Start with: "🧭 Critical Evaluation – [Candidate Name]"
- Include sections:
  • Evaluation Table (Criterion | Score | Confidence | Evaluator Commentary)
  • 📊 Critical Summary
  • 📉 Evaluator Summary
  • 📌 Strengths & Weaknesses
  • ✂️ Tailoring Suggestions (How to Strengthen CV for This Role)

JOB REQUIREMENTS:
{self.job_requirements[:7000]}

CANDIDATE CV:
{cv_text[:9000]}

Be detailed, analytical, and professional. Avoid generic advice. Produce a long, realistic report.
"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a critical evaluator and CV improvement consultant. "
                            "Write long, detailed, structured markdown reports including tailoring suggestions. "
                            "Never fabricate experience or skills."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.15,
                max_tokens=8000,
            )
            return {
                "candidate_name": filename,
                "report": response.choices[0].message.content
            }

        except Exception as e:
            return {
                "candidate_name": filename,
                "report": f"❌ Error generating critical evaluation with tailoring: {e}"
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

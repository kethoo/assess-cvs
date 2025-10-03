import os
import json
from pathlib import Path
from datetime import datetime
from typing import List
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

        try:
            if file_extension == ".pdf":
                text = self._extract_text_from_pdf(file_path)
            elif file_extension in [".doc", ".docx"]:
                text = self._extract_text_from_word(file_path)
            else:
                raise ValueError(f"Unsupported file format: {file_extension}")

            self.job_requirements = text
            return text

        except Exception as e:
            print(f"Error loading job requirements: {e}")
            raise

    # ------------------- PROCESSING CANDIDATE CVS -------------------

    def process_cv_folder(self, folder_path: str, mode: str = "detailed") -> List[CandidateAssessment]:
        """Process all CVs in a folder"""
        cv_files = []
        for ext in ["*.pdf", "*.doc", "*.docx"]:
            cv_files.extend(Path(folder_path).glob(ext))

        if not cv_files:
            print("No CV files found!")
            return []

        for cv_file in cv_files:
            try:
                cv_text = self._extract_cv_text(cv_file)
                assessment = self._assess_candidate(cv_file.name, cv_text)
                self.assessments.append(assessment)
            except Exception as e:
                print(f"Error processing {cv_file.name}: {e}")
                continue

        self.assessments.sort(key=lambda x: x.overall_score, reverse=True)
        return self.assessments

    # ------------------- FILE HELPERS -------------------

    def _extract_cv_text(self, file_path: Path) -> str:
        """Extract text from CV file"""
        if file_path.suffix.lower() == ".pdf":
            return self._extract_text_from_pdf(str(file_path))
        else:
            return self._extract_text_from_word(str(file_path))

    def _extract_text_from_pdf(self, file_path: str) -> str:
        """Extract text from PDF file"""
        try:
            with open(file_path, "rb") as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = []
                for page in pdf_reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text.append(page_text)
                return "\n".join(text)
        except Exception as e:
            raise Exception(f"Failed to read PDF: {e}")

    def _extract_text_from_word(self, file_path: str) -> str:
        """Extract text from Word document"""
        try:
            doc = Document(file_path)
            text = []

            for paragraph in doc.paragraphs:
                text.append(paragraph.text)

            # Also extract text from tables
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        text.append(cell.text)

            return "\n".join(text)

        except Exception as e:
            raise Exception(f"Failed to read Word document: {e}")

    # ------------------- CORE ASSESSMENT -------------------

    def _assess_candidate(self, filename: str, cv_text: str) -> CandidateAssessment:
        """Ultra-detailed, context-aware candidate assessment using OpenAI"""

        prompt = f"""
You are an expert HR professional conducting an ULTRA-DETAILED, CONTEXT-AWARE candidate assessment.

CRITICAL INSTRUCTIONS:
- Always balance positives and negatives.
- For every requirement, explicitly state what the candidate HAS and what they DO NOT HAVE.
- Cite CV evidence with dates, numbers, projects, company names.
- Justify scores with detailed reasoning.

JOB REQUIREMENTS:
{self.job_requirements[:4000]}

CANDIDATE CV:
{cv_text[:5000]}

===================================================================
ASSESSMENT TASK
===================================================================

1. REQUIREMENT MATCHING
- For each requirement: quote CV evidence, explain context, note missing parts.
- Rate: FULLY / MOSTLY / PARTIALLY / NOT MET.

2. SCORING (Experience, Skills, Education, Cultural Fit)
- Show breakdowns.
- For each: what the candidate HAS, what they DO NOT HAVE, how missing parts reduce score.

3. EXECUTIVE SUMMARY
- Must be at least 3–4 full paragraphs.
- Separate what they HAVE vs what they LACK.
- Explain risks/gaps in detail.
- End with a recommendation.

4. WHY THIS SCORE
- Long explanation of why the candidate got this exact score.
- List fully met requirements vs partially met vs missing.
- Explain why score is not higher (what’s missing) and not lower (what they do have).

5. FINAL RECOMMENDATION
- Recommendation + confidence.
- Justify with evidence from CV and requirements.
- Mention gaps that may affect success.

Return ONLY valid JSON with all required fields.
"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert HR professional. Always return ultra-detailed JSON. Include both what the candidate HAS and what they DO NOT HAVE."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=4500,
            )

            content = self._clean_json(response.choices[0].message.content)
            assessment_data = json.loads(content)

            return CandidateAssessment(
                candidate_name=assessment_data.get("candidate_name", "Unknown"),
                filename=filename,
                overall_score=assessment_data.get("overall_score", 0),
                fit_level=assessment_data.get("fit_level", "Unknown"),
                experience_score=assessment_data.get("experience_score", 0),
                experience_explanation=assessment_data.get("experience_explanation", ""),
                skills_score=assessment_data.get("skills_score", 0),
                skills_explanation=assessment_data.get("skills_explanation", ""),
                education_score=assessment_data.get("education_score", 0),
                education_explanation=assessment_data.get("education_explanation", ""),
                cultural_fit_score=assessment_data.get("cultural_fit_score", 0),
                cultural_fit_explanation=assessment_data.get("cultural_fit_explanation", ""),
                requirements_met=assessment_data.get("requirements_met", []),
                critical_gaps=assessment_data.get("critical_gaps", []),
                key_strengths=assessment_data.get("key_strengths", []),
                key_weaknesses=assessment_data.get("key_weaknesses", []),
                missing_requirements=assessment_data.get("missing_requirements", []),
                score_breakdown=assessment_data.get("score_breakdown", ""),
                why_this_score=assessment_data.get("why_this_score", ""),
                recommendation=assessment_data.get("recommendation", "consider"),
                recommendation_reasoning=assessment_data.get("recommendation_reasoning", ""),
                confidence_level=assessment_data.get("confidence_level", "low"),
                interview_focus_areas=assessment_data.get("interview_focus_areas", []),
                red_flags=assessment_data.get("red_flags", []),
                potential_concerns=assessment_data.get("potential_concerns", []),
                executive_summary=assessment_data.get("executive_summary", ""),
                salary_recommendation=assessment_data.get("salary_recommendation", "TBD"),
                assessed_at=datetime.now().isoformat(),
            )

        except Exception as e:
            print(f"Assessment error: {e}")
            return CandidateAssessment(
                candidate_name="Error",
                filename=filename,
                overall_score=0,
                fit_level="Unknown",
                experience_score=0,
                experience_explanation="Error",
                skills_score=0,
                skills_explanation="Error",
                education_score=0,
                education_explanation="Error",
                cultural_fit_score=0,
                cultural_fit_explanation="Error",
                requirements_met=[],
                critical_gaps=["Assessment failed"],
                key_strengths=[],
                key_weaknesses=[],
                missing_requirements=[],
                score_breakdown="Error",
                why_this_score="Error",
                recommendation="consider",
                recommendation_reasoning="Error",
                confidence_level="low",
                interview_focus_areas=[],
                red_flags=[],
                potential_concerns=[],
                executive_summary="Error",
                salary_recommendation="TBD",
                assessed_at=datetime.now().isoformat(),
            )

    # ------------------- UTILS -------------------

    def _clean_json(self, content: str) -> str:
        """Clean JSON response from OpenAI"""
        if content.startswith("```json"):
            content = content[7:-3]
        elif content.startswith("```"):
            content = content[3:-3]
        return content.strip()

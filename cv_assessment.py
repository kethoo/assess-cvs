import os, json, logging, re
from pathlib import Path
from datetime import datetime
from typing import List
from models import CandidateAssessment
from docx import Document
import PyPDF2
import openai

logging.basicConfig(filename="assessment.log", level=logging.INFO)

def verify_evidence(cv_text: str, evidence: str) -> bool:
    return evidence.lower() in cv_text.lower()


class CVAssessmentSystem:
    def __init__(self, api_key: str = None, model: str = "gpt-4o"):
        self.client = openai.OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self.job_requirements = ""
        self.assessments: List[CandidateAssessment] = []
        self.session_id = f"assessment_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.model = model

    # ----------- JOB REQUIREMENTS -----------
    def load_job_requirements(self, file_path: str) -> str:
        ext = Path(file_path).suffix.lower()
        if ext == ".pdf":
            text = self._extract_text_from_pdf(file_path)
        elif ext in [".doc", ".docx"]:
            text = self._extract_text_from_word(file_path)
        else:
            raise ValueError(f"Unsupported file format: {ext}")
        self.job_requirements = text
        return text

    # ----------- CV PROCESSING -----------
    def process_cv_folder(self, folder_path: str, mode="detailed"):
        cv_files = []
        for ext in ["*.pdf", "*.doc", "*.docx"]:
            cv_files.extend(Path(folder_path).glob(ext))

        for cv_file in cv_files:
            try:
                cv_text = self._extract_cv_text(cv_file)
                assessment = self._assess_candidate(cv_file.name, cv_text, mode=mode)
                self.assessments.append(assessment)
            except Exception as e:
                logging.error(f"Error processing {cv_file}: {e}")

        self.assessments.sort(key=lambda x: x.overall_score, reverse=True)
        return self.assessments

    # ----------- FILE EXTRACTION -----------
    def _extract_cv_text(self, file_path: Path) -> str:
        if file_path.suffix.lower() == ".pdf":
            return self._extract_text_from_pdf(str(file_path))
        return self._extract_text_from_word(str(file_path))

    def _extract_text_from_pdf(self, file_path: str) -> str:
        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            return "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])

    def _extract_text_from_word(self, file_path: str) -> str:
        doc = Document(file_path)
        text = [p.text for p in doc.paragraphs]
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    text.append(cell.text)
        return "\n".join(text)

    # ----------- AI ASSESSMENT -----------
    def _assess_candidate(self, filename: str, cv_text: str, mode="detailed") -> CandidateAssessment:
        if mode == "detailed":
            prompt = f"""
            You are an expert HR professional conducting ULTRA-DETAILED, CONTEXT-AWARE candidate assessments.

            JOB REQUIREMENTS:
            {self.job_requirements[:4000]}

            CANDIDATE CV:
            {cv_text[:5000]}

            Return ONLY valid JSON following this schema:
            {{
              "candidate_name": "...",
              "overall_score": 0-100,
              "fit_level": "Excellent/Good/Fair/Poor",
              "experience_score": int,
              "experience_explanation": "...",
              "skills_score": int,
              "skills_explanation": "...",
              "education_score": int,
              "education_explanation": "...",
              "cultural_fit_score": int,
              "cultural_fit_explanation": "...",
              "requirements_met": [{{"requirement": "...", "met": "FULLY/MOSTLY/PARTIALLY/NOT", "cv_evidence": "...", "explanation": "..."}}],
              "critical_gaps": ["..."],
              "key_strengths": ["..."],
              "key_weaknesses": ["..."],
              "missing_requirements": ["..."],
              "score_breakdown": "...",
              "why_this_score": "...",
              "recommendation": "strong_hire/hire/consider/reject",
              "recommendation_reasoning": "...",
              "confidence_level": "high/medium/low",
              "interview_focus_areas": ["..."],
              "red_flags": ["..."],
              "potential_concerns": ["..."],
              "executive_summary": "...",
              "salary_recommendation": "..."
            }}
            """
        else:
            prompt = f"""
            Quick screen this CV vs requirements. Return JSON with:
            candidate_name, overall_score, fit_level, key_strengths, key_weaknesses, recommendation.
            JOB REQS: {self.job_requirements[:1500]}
            CV: {cv_text[:2000]}
            """

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Return only valid JSON"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=3500,
            )
            content = response.choices[0].message.content
            if content.startswith("```"):
                content = re.sub(r"```(json)?", "", content).strip("` \n")
            data = json.loads(content)

            # Hallucination check
            for req in data.get("requirements_met", []):
                if req.get("cv_evidence") and not verify_evidence(cv_text, req["cv_evidence"]):
                    req["met"] = "PARTIALLY_MET"
                    req["explanation"] += " (⚠ Evidence not found in CV)"

            return CandidateAssessment(**data, filename=filename)

        except Exception as e:
            logging.error(f"Assessment failed for {filename}: {e}")
            return CandidateAssessment(
                candidate_name="Error",
                filename=filename,
                overall_score=0,
                fit_level="Unknown",
                experience_score=0,
                experience_explanation="Failed",
                skills_score=0,
                skills_explanation="Failed",
                education_score=0,
                education_explanation="Failed",
                cultural_fit_score=0,
                cultural_fit_explanation="Failed",
                requirements_met=[],
                critical_gaps=["Assessment failed"],
                key_strengths=[],
                key_weaknesses=[],
                missing_requirements=[],
                score_breakdown="Error",
                why_this_score="Error",
                recommendation="consider",
                recommendation_reasoning="Failed",
                confidence_level="low",
                interview_focus_areas=[],
                red_flags=[],
                potential_concerns=[],
                executive_summary="Error",
                salary_recommendation="TBD",
            )

    # ----------- PRETTY DISPLAY -----------
    def display_results(self):
        print("\n" + "=" * 90)
        print("CANDIDATE ASSESSMENTS")
        print("=" * 90 + "\n")

        for i, c in enumerate(self.assessments, 1):
            emoji = {"strong_hire": "🌟", "hire": "✅", "consider": "⚠️", "reject": "❌"}.get(c.recommendation, "📋")
            print(f"{i}. {emoji} {c.candidate_name} — {c.overall_score}/100 ({c.fit_level})")
            print(f"   Recommendation: {c.recommendation.upper()} (confidence: {c.confidence_level})\n")
            print("   📊 Scores:")
            print(f"      • Experience: {c.experience_score}/100")
            print(f"      • Skills: {c.skills_score}/100")
            print(f"      • Education: {c.education_score}/100")
            print(f"      • Cultural Fit: {c.cultural_fit_score}/100\n")
            print("   ✅ Key Strengths:")
            for s in c.key_strengths[:3]: print(f"      • {s}")
            print("\n   ⚠️ Key Weaknesses:")
            for w in c.key_weaknesses[:3]: print(f"      • {w}")
            if c.critical_gaps:
                print("\n   🚨 Critical Gaps:")
                for g in c.critical_gaps[:2]: print(f"      • {g}")
            if c.red_flags:
                print("\n   ⛔ Red Flags:")
                for f in c.red_flags: print(f"      • {f}")
            print("\n   📝 Executive Summary:")
            print(f"      {c.executive_summary}\n")
            print("-" * 90 + "\n")

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
        """Load tender or job requirements from Word or PDF file (auto-detects type)."""
        # Detect file type by header instead of relying on extension
        with open(file_path, "rb") as f:
            header = f.read(4)

        try:
            if header.startswith(b"%PDF"):
                text = self._extract_text_from_pdf(file_path)
            else:
                # assume Word if not a PDF
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
        """Critical narrative evaluation with evaluation table, reasoning, and keyword recommendations."""
        prompt = f"""
You are a senior evaluator and HR specialist for EU/World Bank tenders.

TASK:
Perform a **Critical Evaluation** of the following candidate’s CV compared to the JOB REQUIREMENTS.

---

### REQUIRED OUTPUT STRUCTURE (Markdown)

#### 🧭 Critical Evaluation – {filename}

**Evaluation Table**

| Section | Criteria | Score (0–1) | Confidence | Evaluator Commentary |
|----------|-----------|-------------|-------------|----------------------|
| **General Tender Context (20% weight)** | Understanding of project/tender context |  |  |  |
|  | Familiarity with region/country context |  |  |  |
| **Specific Expert Requirements (80% weight)** | Team leadership and management |  |  |  |
|  | Relevant domain expertise |  |  |  |
|  | Technical or regulatory knowledge |  |  |  |
|  | Donor project experience (EU/WB/ADB, etc.) |  |  |  |
|  | Communication and coordination skills |  |  |  |
|  | Educational background |  |  |  |
|  | Analytical and reporting skills |  |  |  |
|  | Language proficiency |  |  |  |

Fill **all cells** with numeric scores (0–1), confidence (High/Medium/Low), and concise evaluator commentary (1–3 sentences each).

After the table, add:
**Final Weighted Score (consider 80% expert requirements, 20% tender context): X.XX / 1.00**

---

**📊 Critical Summary**
Summarize overall alignment with project and expert role (2–3 paragraphs). Be analytical and cite evidence.

**📉 Evaluator Summary**
Summarize 3–5 key takeaways, e.g.:
- Strong alignment with donor project management
- Missing direct regulatory enforcement experience
- Excellent educational background, etc.

**📌 Strengths & Weaknesses**
List at least 3 strengths and 3 weaknesses with evidence.

**✂️ Tailoring Suggestions (How to Strengthen CV for This Role)**

**a. Rewriting & Emphasis Suggestions**
List concrete, text-level suggestions (e.g., “Emphasize experience with EU-funded TA projects in executive summary.”)

**b. 🪶 Word Recommendations (Tender Keyword Alignment)**
List 5–10 **keyword alignment suggestions**.
Provide a markdown table like:

| Current CV Wording | Recommended Tender Keyword | Why |
|--------------------|-----------------------------|-----|
| "Managed donor projects" | "Led EU-funded Technical Assistance projects" | Aligns with EU terminology. |
| "Worked with local stakeholders" | "Coordinated institutional counterparts and regulatory agencies" | Matches ToR phrasing. |

---

### CONTEXT INPUTS

**General Tender Context (20%)**
{self.job_requirements[:4000]}

**CANDIDATE CV**
{cv_text[:9000]}

---

INSTRUCTIONS:
- Be detailed, structured, and realistic.
- Always include numeric scores, reasoning, and commentary.
- Never skip sections or placeholders.
- Use professional EU evaluator tone throughout.
"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a senior HR evaluator for donor-funded tenders. "
                            "Always produce detailed, structured markdown reports with reasoning. "
                            "Include numeric scores, commentary, and keyword recommendations."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.15,
                max_tokens=8500,
            )

            report_text = response.choices[0].message.content.strip()
            match = re.search(r"Final Weighted Score.*?([0-9]\.[0-9]+)", report_text)
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
        match = re.search(r"(\{.*\})", content, re.DOTALL)
        if match:
            return match.group(1).strip()
        return content

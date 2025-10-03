from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List

@dataclass
class CandidateAssessment:
    """Complete candidate assessment results"""
    candidate_name: str
    filename: str
    overall_score: int  # 0-100
    fit_level: str  # Excellent/Good/Fair/Poor

    # Detailed scores
    experience_score: int
    experience_explanation: str
    skills_score: int
    skills_explanation: str
    education_score: int
    education_explanation: str
    cultural_fit_score: int
    cultural_fit_explanation: str

    # Requirement analysis
    requirements_met: List[Dict]
    critical_gaps: List[str]

    # Strengths & weaknesses
    key_strengths: List[str]
    key_weaknesses: List[str]
    missing_requirements: List[str]

    # Explanations
    score_breakdown: str
    why_this_score: str

    # Recommendations
    recommendation: str
    recommendation_reasoning: str
    confidence_level: str
    interview_focus_areas: List[str]

    # Risk flags
    red_flags: List[str]
    potential_concerns: List[str]

    # Summary
    executive_summary: str
    salary_recommendation: str

    assessed_at: str = datetime.now().isoformat()

import os
from cv_assessment import CVAssessmentSystem

def main():
    print("=== DEEP CV ASSESSMENT SYSTEM ===")
    api_key = os.getenv("OPENAI_API_KEY") or input("Enter OpenAI API key: ").strip()

    system = CVAssessmentSystem(api_key=api_key)
    req_file = input("Job requirements file (Word/PDF): ").strip()
    system.load_job_requirements(req_file)

    cv_folder = input("Folder containing CVs: ").strip()
    results = system.process_cv_folder(cv_folder)

    for r in results:
        print(f"\n=== {r.candidate_name} ===")
        print(f"Overall Score: {r.overall_score}")
        print(f"Fit Level: {r.fit_level}")
        print(json.dumps(r.executive_summary, indent=2))

if __name__ == "__main__":
    main()

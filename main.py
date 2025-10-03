import os
from cv_assessment import CVAssessmentSystem

def main():
    print("=== CV ASSESSMENT SYSTEM ===")

    api_key = os.getenv("OPENAI_API_KEY") or input("Enter OpenAI API key: ").strip()
    system = CVAssessmentSystem(api_key=api_key)

    req_file = input("Job requirements file (Word/PDF): ").strip()
    system.load_job_requirements(req_file)

    cv_folder = input("Folder containing CVs: ").strip()
    system.process_cv_folder(cv_folder, mode="detailed")

    system.display_results()

if __name__ == "__main__":
    main()

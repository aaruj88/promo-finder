import os

def load_prompt_file(rel_path: str) -> str:
    """
    Robustly loads a prompt markdown file across varied environments
    (Streamlit Cloud, Docker, local, nested scripts).
    """
    clean_rel = rel_path.replace("\\", "/").lstrip("./")
    filename = os.path.basename(clean_rel)

    # Search in priority order
    candidate_paths = [
        rel_path,
        os.path.join(".", clean_rel),
        os.path.join(os.path.dirname(__file__), "..", clean_rel),
        os.path.join(os.path.dirname(__file__), "..", "prompts", filename),
        os.path.join(".", "prompts", filename)
    ]

    for p in candidate_paths:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception:
                pass

    return f"You are an expert microdrama promo analysis engine. Follow schema strictly."

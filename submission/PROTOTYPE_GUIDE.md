# Prototype Deployment & User Guide

This guide describes how to run and deploy the **Promo Finder** interactive web prototype.

---

## 1. Quick Local Run (1-Click)

Ensure requirements are installed:
```bash
pip install -r requirements.txt streamlit reportlab
```

Run the Streamlit application:
```bash
streamlit run app.py
```
Open [http://localhost:8501](http://localhost:8501) in your browser.

---

## 2. Deploying to Free-Tier Cloud Platforms

### A. Streamlit Community Cloud (Recommended — Free Tier)
1. Push this repository to GitHub.
2. Sign in to [share.streamlit.io](https://share.streamlit.io) with your GitHub account.
3. Click **New app**.
4. Select your repository, branch (`main`), and set the main file path to `app.py`.
5. *(Optional)* In **Advanced settings > Secrets**, add:
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."
   # or OPENAI_API_KEY = "sk-..."
   ```
6. Click **Deploy!** Your app will be live on a public URL in ~1 minute.

### B. Hugging Face Spaces (Free Tier)
1. Create a new Space on [huggingface.co/spaces](https://huggingface.co/spaces).
2. Choose **Streamlit** (or **Docker**) as the Space SDK.
3. Push or upload this repository to your Hugging Face Space repository.
4. Set Space Secrets for `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` under **Settings > Variables and secrets**.
5. The Space will automatically build and launch at your public Hugging Face URL.

### C. Docker Container Deployment
A production `Dockerfile` is included:
```bash
# Build Docker image
docker build -t promofinder:latest .

# Run container on port 8501
docker run -d -p 8501:8501 --name promofinder-app promofinder:latest
```

---

## 3. Prototype Features & Walkthrough

1. **🏆 Ranked Promos**: Filter by Hook Type (`public_humiliation`, `confrontation`, `physical_action`, `betrayal`), inspect exact cut points, line-by-line script views, and 5-dimension score meters.
2. **📖 Show Bible & Lore**: View series premise, character dossiers, relational graphs, and the 7-episode major reveals catalog with spoiler tags.
3. **⚔️ Pairwise Arena**: Interactively pit any two candidate promos against each other to review head-to-head tournament win counts and pacing.
4. **🚀 Live Discovery & Model Swapping**: Select frontier models (`claude-3-7-sonnet-20250219`, `gpt-4o`, `gemini-2.5-pro`) and run live discovery on any episode.
5. **📊 Benchmarks & Evaluations**: Review time-range IoU vs hand-picked gold standards, 100% stability persistence, ablation studies, and real failure mode analysis.
6. **💾 Downloads & Raw Outputs**: Download unedited `promos.json`, `report.md`, and the 2-page `Solution_Doc.pdf`.


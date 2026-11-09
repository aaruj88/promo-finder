# Prototype Deployment & Mobile User Guide

This guide describes how to run and deploy the **Promo Finder** interactive web prototype, optimized for **both desktop browsers and mobile devices (iOS / Android)** with **zero user API key entry required**.

---

## 1. Zero-Config Mobile-First Experience

When viewed on a mobile phone:
- **No API Key Required**: The app immediately pre-loads and visualizes all 50 analyzed episodes, top-ranked promos, script cut points, hook scores, and tournament metrics. Visitors can browse, filter, inspect full dialogue cuts, and download reports **without entering any credentials**.
- **Responsive 9:16 Social Feed**: Formatted with vertical cards matching TikTok and Instagram Reels workflows.
- **Thumb-Friendly Touch UI**: 48px tap targets, collapsible details, and auto-collapsed navigation drawer to prevent screen obstruction on narrow mobile screens.

---

## 2. Setting Up the Groq API Key (Server-Side)

Groq delivers ultra-fast inference (~500 tokens/sec) at minimal cost.

### Providing the Groq Key:

1. **Via `.env` file (Local / Server)**:
   Create or edit `.env` in the project root:
   ```env
   GROQ_API_KEY=gsk_your_groq_api_key_here
   MODEL=llama-3.3-70b-versatile
   LLM_PROVIDER=groq
   ```

2. **Via Environment Variable**:
   ```bash
   # Linux / macOS
   export GROQ_API_KEY="gsk_..."
   export MODEL="llama-3.3-70b-versatile"
   
   # Windows PowerShell
   $env:GROQ_API_KEY="gsk_..."
   $env:MODEL="llama-3.3-70b-versatile"
   ```

3. **Via Streamlit Cloud Secrets** (For public deployment):
   In the Streamlit Cloud dashboard under **App Settings > Secrets**:
   ```toml
   GROQ_API_KEY = "gsk_..."
   MODEL = "llama-3.3-70b-versatile"
   LLM_PROVIDER = "groq"
   ```
   *Any mobile visitor accessing your deployed link can test live re-generation without ever seeing or typing your API key.*

---

## 3. Quick Local Run (1-Click)

Ensure requirements are installed:
```bash
pip install -r requirements.txt streamlit reportlab groq
```

Run the Streamlit application:
```bash
streamlit run app.py
```
Open [http://localhost:8501](http://localhost:8501) on your desktop or scan/open the local network IP on your mobile phone.

---

## 4. Deploying to Free-Tier Cloud Platforms

### A. Streamlit Community Cloud (Recommended — 1-Click Free Hosting)
1. Push this repository to GitHub.
2. Sign in to [share.streamlit.io](https://share.streamlit.io).
3. Click **New app** and select your repository and `app.py`.
4. In **Advanced settings > Secrets**, paste your `GROQ_API_KEY = "gsk_..."`.
5. Click **Deploy!** Share the public link with anyone on mobile or desktop.

### B. Hugging Face Spaces (Free Tier)
1. Create a new Space on [huggingface.co/spaces](https://huggingface.co/spaces) selecting **Streamlit** SDK.
2. Push this repo to your Space repository.
3. Under **Settings > Variables and secrets**, add `GROQ_API_KEY`.
4. The space deploys instantly with mobile support.

### C. Docker Container Deployment
A production `Dockerfile` is included:
```bash
# Build Docker image
docker build -t promofinder:latest .

# Run container on port 8501 with Groq Key
docker run -d -p 8501:8501 -e GROQ_API_KEY="gsk_..." --name promofinder-app promofinder:latest
```

---

## 5. Prototype Walkthrough & Key Features

1. **🏆 Top Promos (Mobile Feed)**: Filter by Hook Type (`confrontation`, `scandalous_reveal`, `betrayal`), inspect exact cut points, line-by-line script ranges, and 5-dimension score meters.
2. **📖 Show Bible**: Series premise, character dossiers, relational graphs, and the 50-episode major reveals catalog with spoiler tags.
3. **⚔️ Pairwise Arena**: Simulated A/B ad tournament judging. Compare clips in both directions (`A vs B` and `B vs A`) to neutralize position bias.
4. **📊 Benchmarks & Evaluations**: Review time-range IoU vs hand-picked gold standards, 100% stability persistence, ablation studies, and real failure mode analysis.
5. **⚡ Live Runner**: Trigger live discovery with Groq (`llama-3.3-70b-versatile`) or frontier models, requiring zero input from the mobile user.
6. **📥 Downloads**: 1-tap download of `promos.json`, `report.md`, and the 2-page `Solution_Doc.pdf`.

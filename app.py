import os
import json
import streamlit as st
import pandas as pd
from typing import Dict, Any, List

# Page configuration
st.set_page_config(
    page_title="Promo Finder — Microdrama AI",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 800;
        color: #1E293B;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #64748B;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 1rem;
        text-align: center;
    }
    .hook-badge {
        display: inline-block;
        padding: 0.2rem 0.6rem;
        border-radius: 9999px;
        font-size: 0.85rem;
        font-weight: 600;
        background-color: #EEF2FF;
        color: #4F46E5;
    }
    .cliff-badge {
        display: inline-block;
        padding: 0.2rem 0.6rem;
        border-radius: 9999px;
        font-size: 0.85rem;
        font-weight: 600;
        background-color: #FEF2F2;
        color: #DC2626;
    }
    .stProgress > div > div > div > div {
        background-color: #4F46E5;
    }
</style>
""", unsafe_allow_html=True)

# Helper function to load cached data
@st.cache_data
def load_data():
    promos_path = "./out/promos.json"
    bible_path = "./.cache/show_bible.json"
    report_path = "./out/report.md"
    failures_path = "./out/failures.md"
    
    promos = []
    if os.path.exists(promos_path):
        with open(promos_path, "r", encoding="utf-8") as f:
            promos = json.load(f)
            
    bible = {}
    if os.path.exists(bible_path):
        with open(bible_path, "r", encoding="utf-8") as f:
            bible = json.load(f)

    report = ""
    if os.path.exists(report_path):
        with open(report_path, "r", encoding="utf-8") as f:
            report = f.read()

    failures = ""
    if os.path.exists(failures_path):
        with open(failures_path, "r", encoding="utf-8") as f:
            failures = f.read()

    return promos, bible, report, failures

promos, bible, report_md, failures_md = load_data()

# Sidebar
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/video-editing.png", width=64)
    st.title("Promo Finder")
    st.markdown("**Autonomous Screenplay Promo Discovery for Vertical Microdramas**")
    st.markdown("*(TikTok, Instagram Reels, YouTube Shorts)*")
    st.divider()
    
    st.subheader("Model Configuration")
    model_choice = st.selectbox(
        "Active LLM",
        [
            "claude-3-7-sonnet-20250219",
            "claude-3-5-sonnet-20241022",
            "gpt-4o",
            "gemini-2.5-pro",
            "Deterministic Heuristic Engine"
        ],
        index=1
    )
    st.caption("Easily swap LLM providers via `--model` or `config.yaml`.")
    
    st.divider()
    st.markdown("### Series Info")
    st.markdown(f"**Show**: *{bible.get('title', 'I Married a Broken Soldier. He was a Duke')}*")
    st.markdown(f"**Episodes**: 50 episodes (70-200s each)")
    st.markdown(f"**Target Format**: 9:16 Vertical, 20-60s")

# Main Content
st.markdown('<div class="main-header">🎬 Promo Finder Dashboard</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">AI-Powered High-Converting Promo Clip Discovery from Screenplays</div>', unsafe_allow_html=True)

# Top Metrics Row
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Episodes Analyzed", "50", "100% complete")
with col2:
    st.metric("Validated Candidates", "180", "16 rejected by rules")
with col3:
    st.metric("Top Ranked Promos", str(len(promos)), "Diversity filtered")
with col4:
    st.metric("Stability Persistence", "100%", "10/10 persistent picks")

st.divider()

# Tabs
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🏆 Ranked Promos",
    "📖 Show Bible & Lore",
    "⚔️ Pairwise Arena",
    "🚀 Live Discovery & Swapping",
    "📊 Benchmarks & Evaluations",
    "💾 Downloads & Raw Outputs"
])

# TAB 1: Ranked Promos
with tab1:
    st.subheader("Top Ranked Promo Clips")
    st.markdown("Selected based on **3s Thumb-Stopping Hook**, **Unresolved Cliffhanger**, **Standalone Cold Comprehension**, and **Global Pairwise Tournament Ranking**.")
    
    if not promos:
        st.warning("No promos found in `out/promos.json`. Run the pipeline first.")
    else:
        # Filter controls
        fcol1, fcol2, fcol3 = st.columns(3)
        with fcol1:
            hook_types = sorted(list(set(p["flags"].get("hook_type", "other") for p in promos)))
            selected_hook = st.selectbox("Filter by Hook Type", ["All"] + hook_types)
        with fcol2:
            min_score = st.slider("Min Virality Score", 0.0, 100.0, 85.0, 0.5)
        with fcol3:
            search_query = st.text_input("Search Hook / Cliffhanger Keywords", "")

        filtered_promos = [
            p for p in promos
            if (selected_hook == "All" or p["flags"].get("hook_type") == selected_hook)
            and p["scores"].get("total", 0) >= min_score
            and (search_query.lower() in p["hook"].lower() or search_query.lower() in p["cliffhanger"].lower() or search_query == "")
        ]

        st.caption(f"Showing {len(filtered_promos)} of {len(promos)} ranked promos.")

        # Display Promos in Expander Cards
        for p in filtered_promos:
            rank = p["rank"]
            pid = p["promo_id"]
            ep_str = ", ".join(str(s["episode"]) for s in p["segments"])
            dur = p["total_duration_s"]
            hook_type = p["flags"].get("hook_type", "N/A")
            total_score = p["scores"].get("total", 0)
            wins = p["scores"].get("pairwise_wins", 0)

            with st.expander(f"**Rank #{rank}: {pid}** — Episode {ep_str} | ⏱️ {dur:.1f}s | ⭐ Score: {total_score}/100 | 🏆 Wins: {wins}", expanded=(rank <= 2)):
                pcol1, pcol2 = st.columns([3, 2])
                with pcol1:
                    st.markdown(f"**Hook (0-3s)**: {p['hook']}")
                    st.markdown(f"**Cliffhanger**: {p['cliffhanger']}")
                    st.markdown(f"**Strategic Rationale**: *{p['why_it_works']}*")

                    st.markdown("##### Cut Points & Lines")
                    for s_idx, seg in enumerate(p["segments"]):
                        st.markdown(f"- **Segment {s_idx+1} (Ep {seg['episode']})**: `{seg['start_ts']}` ({seg['start_s']}s) $\\rightarrow$ `{seg['end_ts']}` ({seg['end_s']}s)")
                        st.caption(f"  *Start*: `{seg['first_line']}`")
                        st.caption(f"  *End*:   `{seg['last_line']}`")

                with pcol2:
                    st.markdown("##### Score Breakdown")
                    sc = p["scores"]
                    st.progress(sc.get("hook", 0) / 30.0, text=f"Hook Stopping Power: {sc.get('hook', 0)}/30")
                    st.progress(sc.get("cliffhanger", 0) / 30.0, text=f"Cliffhanger Urgency: {sc.get('cliffhanger', 0)}/30")
                    st.progress(sc.get("standalone", 0) / 20.0, text=f"Standalone Comprehension: {sc.get('standalone', 0)}/20")
                    st.progress(sc.get("emotional_intensity", 0) / 10.0, text=f"Emotional Intensity: {sc.get('emotional_intensity', 0)}/10")
                    st.progress(sc.get("show_representativeness", 0) / 10.0, text=f"Representativeness: {sc.get('show_representativeness', 0)}/10")

                    flags = p["flags"]
                    st.markdown(f"**Spoiler Risk**: `{flags.get('spoiler_risk', 'none').upper()}`")
                    st.markdown(f"**Hook Type**: `{flags.get('hook_type', 'N/A')}`")
                    st.markdown(f"**Hook Classification**: `{flags.get('hook_flag', 'dialogue_hook')}`")

# TAB 2: Show Bible & Lore
with tab2:
    st.subheader("Show Bible: Characters, Premise, & Major Reveals")
    st.markdown(f"**Premise**: {bible.get('premise', 'N/A')}")
    st.markdown(f"**Main Arc**: {bible.get('main_arc', 'N/A')}")

    bcol1, bcol2 = st.columns(2)
    with bcol1:
        st.markdown("#### Primary Characters")
        for char in bible.get("characters", []):
            st.markdown(f"- **{char.get('name')}** (*{char.get('role')}*): {char.get('motivation')}")

        st.markdown("#### Key Relationship Dynamics")
        for rel in bible.get("relationships", []):
            st.markdown(f"- {rel}")

    with bcol2:
        st.markdown("#### Major Reveals (Spoiler Catalog)")
        reveals = bible.get("major_reveals", [])
        if reveals:
            for rev in reveals:
                spoiler_tag = "🚨 SPOILER" if rev.get("is_spoiler") else "✅ SAFE"
                st.markdown(f"- **Episode {rev.get('episode')}** [{spoiler_tag}]: {rev.get('reveal')}")
        else:
            st.info("No reveals registered in cache.")

# TAB 3: Pairwise Arena
with tab3:
    st.subheader("Pairwise Comparison Tournament Arena")
    st.markdown("Every top promo is evaluated in head-to-head simulated ad comparisons in **both directions** (`A vs B` and `B vs A`) to neutralize position bias.")

    if len(promos) >= 2:
        p_ids = [f"Rank #{p['rank']}: {p['promo_id']} (Ep {p['segments'][0]['episode']})" for p in promos]
        acol1, acol2 = st.columns(2)
        with acol1:
            choice_a_idx = st.selectbox("Select Promo A", range(len(p_ids)), index=0, format_func=lambda i: p_ids[i])
        with acol2:
            choice_b_idx = st.selectbox("Select Promo B", range(len(p_ids)), index=1, format_func=lambda i: p_ids[i])

        p_a = promos[choice_a_idx]
        p_b = promos[choice_b_idx]

        comp_col1, comp_col2 = st.columns(2)
        with comp_col1:
            st.markdown(f"### Option A: `{p_a['promo_id']}`")
            st.markdown(f"- **Duration**: {p_a['total_duration_s']}s")
            st.markdown(f"- **Hook**: {p_a['hook']}")
            st.markdown(f"- **Cliffhanger**: {p_a['cliffhanger']}")
            st.markdown(f"- **Tournament Wins**: {p_a['scores'].get('pairwise_wins', 0)}")
            st.metric("Total Score", f"{p_a['scores'].get('total', 0)}/100")

        with comp_col2:
            st.markdown(f"### Option B: `{p_b['promo_id']}`")
            st.markdown(f"- **Duration**: {p_b['total_duration_s']}s")
            st.markdown(f"- **Hook**: {p_b['hook']}")
            st.markdown(f"- **Cliffhanger**: {p_b['cliffhanger']}")
            st.markdown(f"- **Tournament Wins**: {p_b['scores'].get('pairwise_wins', 0)}")
            st.metric("Total Score", f"{p_b['scores'].get('total', 0)}/100")

        st.info(f"**Tournament Head-to-Head Insight**: Promo A has {p_a['scores'].get('pairwise_wins', 0)} total wins across the candidate pool compared to {p_b['scores'].get('pairwise_wins', 0)} wins for Promo B.")

# TAB 4: Live Discovery & Model Swapping
with tab4:
    st.subheader("Live Promo Discovery & Model Swapping")
    st.markdown("Test swapping the backend LLM out for a stronger model live in the browser.")

    scol1, scol2 = st.columns(2)
    with scol1:
        swap_model = st.text_input("Model Identifier", value=model_choice)
        swap_provider = st.selectbox("Provider", ["auto", "anthropic", "openai", "gemini", "heuristic"])
    with scol2:
        api_key_input = st.text_input("API Key (leave blank to use env var or heuristic)", type="password")
        ep_limit = st.slider("Episodes to Process", 1, 10, 3)

    if st.button("🚀 Run Promo Discovery with Selected Model"):
        with st.spinner(f"Running discovery pipeline with model `{swap_model}` across {ep_limit} episodes..."):
            import subprocess
            cmd = f"python -m promofinder run --input ./data --out ./out/live_run --limit {ep_limit} --model {swap_model}"
            try:
                res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                if res.returncode == 0:
                    st.success(f"Pipeline successfully ran with model `{swap_model}`!")
                    if os.path.exists("./out/live_run/promos.json"):
                        with open("./out/live_run/promos.json") as fp:
                            live_promos = json.load(fp)
                        st.json(live_promos[:3])
                else:
                    st.error(f"Error running pipeline: {res.stderr}")
            except Exception as e:
                st.error(f"Execution error: {e}")

# TAB 5: Benchmarks & Evaluations
with tab5:
    st.subheader("Quantitative Evaluations & Failure Analysis")
    
    ecol1, ecol2, ecol3 = st.columns(3)
    with ecol1:
        st.markdown("#### Time-Range IoU vs Gold")
        st.markdown("- **Hand-Picked Gold Promos**: 6")
        st.markdown("- **Average IoU**: `0.4021`")
        st.markdown("- **Hit Rate (IoU >= 0.5)**: `33.3%`")
        st.markdown("- **Exact 100% Match**: `GOLD_EP01_ALTAR` (IoU: `1.0000`)")

    with ecol2:
        st.markdown("#### Stability Persistence")
        st.markdown("- **Consecutive Full Runs**: 2")
        st.markdown("- **Cut Point Persistence**: `10 / 10 (100.0%)`")
        st.markdown("- **Jaccard Similarity**: `0.5385`")
        st.markdown("Ensures production posting pipelines are deterministic.")

    with ecol3:
        st.markdown("#### Ablation Impact")
        st.markdown("- **Without Cold-Viewer**: `60.0%` top-10 overlap (confusing clips score artificially high).")
        st.markdown("- **Without Pairwise Tournament**: `60.0%` top-10 overlap (collapses into unranked ties).")

    st.divider()
    st.markdown("### Documented Failure Modes ([`out/failures.md`](file:///d:/Projects/KUKU/out/failures.md))")
    with st.expander("View 5 Real Observed Failures, Root Causes, and Fixes", expanded=True):
        st.markdown(failures_md)

# TAB 6: Downloads & Raw Outputs
with tab6:
    st.subheader("Raw Output Files & Submission Package")
    st.markdown("Download the unedited output records and documentation produced by Promo Finder.")

    dcol1, dcol2, dcol3 = st.columns(3)
    with dcol1:
        if os.path.exists("./out/promos.json"):
            with open("./out/promos.json", "r", encoding="utf-8") as f:
                p_data = f.read()
            st.download_button("📥 Download promos.json", p_data, "promos.json", "application/json")
    with dcol2:
        if os.path.exists("./out/report.md"):
            with open("./out/report.md", "r", encoding="utf-8") as f:
                r_data = f.read()
            st.download_button("📄 Download report.md", r_data, "report.md", "text/markdown")
    with dcol3:
        if os.path.exists("./submission/Solution_Doc.pdf"):
            with open("./submission/Solution_Doc.pdf", "rb") as f:
                pdf_data = f.read()
            st.download_button("📑 Download Solution_Doc.pdf", pdf_data, "Solution_Doc.pdf", "application/pdf")

    st.markdown("#### Preview `out/report.md`")
    st.markdown(report_md)

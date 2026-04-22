# backend/app.py
import os
import io
import uuid
import json
import time
import asyncio
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, Any, List

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, Response

import pandas as pd
import numpy as np
import requests

# ML libs (these will download models on first run)
from sentence_transformers import SentenceTransformer
from transformers import pipeline
from sklearn.cluster import MiniBatchKMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# PDF building
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import cm

# Create results dir (exports upon demand)
os.makedirs("results", exist_ok=True)

app = FastAPI(title="AI Lit Scout SSE - Tailwind UI")

# allow local frontend dev (adjust origins for prod)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.staticfiles import StaticFiles

# Mount frontend directory (serve landing.html, index.html, js, css)
# We mount it at the root "/" so http://localhost:8000/landing.html works.
# API routes defined above/below will still work as long as they don't conflict with filenames.
# Note: We use "../frontend" because app.py is in "backend/"
app.mount("/static", StaticFiles(directory="../frontend"), name="static")

# Serve root files directly as well for convenience (optional, but helps with landing.html)
# app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")
# MOVED TO END OF FILE TO PREVENT SHADOWING API ROUTES

JOBS: Dict[str, Dict[str, Any]] = {}

# models (loaded at startup)
emb_model = None
sum_model = None

@app.on_event("startup")
def load_models():
    global emb_model, sum_model
    # CPU-friendly embedding model
    emb_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    # summarization/text2text model (flan-t5-base)
    sum_model = pipeline("text2text-generation", model="google/flan-t5-base")

# ---------- helper: convert to JSON-serializable ----------
def to_serializable(obj):
    """Recursively convert numpy/pandas types to plain python types."""
    if obj is None:
        return None
    if isinstance(obj, (str, bool)):
        return obj
    if isinstance(obj, (int, float)):
        return obj
    # numpy scalars
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (pd.Timestamp, datetime)):
        return str(obj)
    if isinstance(obj, pd.Series):
        return [to_serializable(v) for v in obj.tolist()]
    if isinstance(obj, pd.DataFrame):
        return [to_serializable(r) for r in obj.to_dict(orient="records")]
    if isinstance(obj, dict):
        return {str(k): to_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_serializable(v) for v in obj]
    if isinstance(obj, (bytes, bytearray)):
        try:
            return obj.decode("utf-8")
        except Exception:
            return str(obj)
    return str(obj)

# ---------- small helper functions ----------
def cluster_keywords(texts: List[str], k: int = 6) -> str:
    vec = TfidfVectorizer(max_features=2000, stop_words="english", ngram_range=(1,2))
    if not texts:
        return ""
    X = vec.fit_transform(texts)
    scores = np.asarray(X.mean(axis=0)).ravel()
    idx = scores.argsort()[::-1][:k]
    feats = np.array(vec.get_feature_names_out())[idx]
    return ", ".join(feats)

def build_pdf_in_memory(topic: str, df: pd.DataFrame, perpaper_reasons: dict, cluster_summaries: dict) -> bytes:
    buf = io.BytesIO()
    styles = getSampleStyleSheet()
    
    # Custom Styles
    title_style = styles["Title"]
    title_style.fontSize = 24
    title_style.spaceAfter = 20
    
    h2_style = styles["Heading2"]
    h2_style.fontSize = 16
    h2_style.spaceBefore = 15
    h2_style.spaceAfter = 10
    h2_style.textColor = colors.HexColor("#4f46e5")
    
    body_style = styles["BodyText"]
    body_style.fontSize = 10
    body_style.leading = 14
    
    bullet_style = styles["BodyText"]
    bullet_style.fontSize = 10
    bullet_style.leftIndent = 20
    bullet_style.spaceAfter = 5

    story = []
    
    # Header
    story.append(Paragraph("AI Literature Scout Report", title_style))
    story.append(Paragraph(f"<b>Topic:</b> {topic}", body_style))
    story.append(Paragraph(f"<b>Generated:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", body_style))
    story.append(Paragraph(f"<b>Total Papers Found:</b> {len(df)}", body_style))
    story.append(Spacer(1, 20))
    story.append(PageBreak())

    # Section 1: Top Matches
    top_sorted = df.sort_values("relevance", ascending=False).head(15)
    story.append(Paragraph("Top Matches (by relevance)", h2_style))
    story.append(Spacer(1, 10))
    
    for i, (_, r) in enumerate(top_sorted.iterrows(), 1):
        # Paper Title
        story.append(Paragraph(f"{i}. <b>{r.title}</b>", styles["Heading3"]))
        
        # Metadata
        meta = f"<i>{r.authors}</i> — {r.published} — <b>Relevance: {r.relevance:.0%}</b>"
        story.append(Paragraph(meta, body_style))
        story.append(Paragraph(f"<a href='{r.url}' color='blue'>{r.url}</a>", body_style))
        story.append(Spacer(1, 5))
        
        # Key Points (Bullets)
        reasons = perpaper_reasons.get(int(r.name), "")
        if reasons:
            story.append(Paragraph("<b>Key Points:</b>", body_style))
            # Clean up bullets from model output
            lines = [line.strip() for line in reasons.replace("- ", "").split("\n") if line.strip()]
            for line in lines:
                story.append(Paragraph(f"• {line}", bullet_style))
        
        story.append(Spacer(1, 15))
    
    story.append(PageBreak())

    # Section 2: Clusters
    for c in sorted(df["cluster"].unique()):
        sub = df[df.cluster == c]
        story.append(Paragraph(f"Cluster {c}: {len(sub)} Papers", h2_style))
        
        # Cluster Summary
        summary = cluster_summaries.get(c, '(No summary available)')
        story.append(Paragraph(f"<b>Overview:</b> {summary}", body_style))
        story.append(Spacer(1, 5))
        
        # Keywords
        kw = cluster_keywords(sub['abstract'].tolist())
        story.append(Paragraph(f"<b>Keywords:</b> <i>{kw}</i>", body_style))
        story.append(Spacer(1, 10))
        
        # Table of Papers in Cluster
        table_data = [["Title", "Year", "Relevance"]]
        for _, r in sub.sort_values("relevance", ascending=False).head(10).iterrows():
            table_data.append([r.title[:60] + "..." if len(r.title)>60 else r.title, r.published, f"{r.relevance:.0%}"])
            
        tbl = Table(table_data, colWidths=[11*cm, 2*cm, 2*cm])
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e0e7ff")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 20))
        
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    doc.build(story)
    pdf_bytes = buf.getvalue()
    buf.close()
    return pdf_bytes

# arXiv fetcher (with simple fallback)
ARXIV_BASES = ["http://export.arxiv.org/api/query", "https://export.arxiv.org/api/query"]
HEADERS = {"User-Agent":"ai-lit-scout/fastapi"}

def fetch_arxiv_online(topic: str, max_results: int = 30, retries: int = 2, timeout: int = 12) -> pd.DataFrame:
    last_err = None
    for base in ARXIV_BASES:
        for attempt in range(1, retries+1):
            try:
                params = {"search_query": f"all:{topic.replace(' ', '+')}", "start": 0, "max_results": max_results, "sortBy": "submittedDate", "sortOrder": "descending"}
                r = requests.get(base, params=params, headers=HEADERS, timeout=timeout)
                r.raise_for_status()
                root = ET.fromstring(r.text)
                ns = {"a":"http://www.w3.org/2005/Atom"}
                rows=[]
                for e in root.findall("a:entry", ns):
                    rows.append({
                        "title": (e.find("a:title", ns).text or "").strip().replace("\n"," "),
                        "abstract": (e.find("a:summary", ns).text or "").strip().replace("\n"," "),
                        "url": (e.find("a:id", ns).text or "").strip(),
                        "published": (e.find("a:published", ns).text or "")[:10],
                        "authors": ", ".join([a.find("a:name", ns).text for a in e.findall("a:author", ns)])
                    })
                if rows:
                    return pd.DataFrame(rows)
            except Exception as e:
                last_err = e
                time.sleep(0.3 * attempt)
    # fallback: synthetic entries
    rows=[]
    for i in range(max_results):
        rows.append({
            "title": f"Example paper {i+1} on {topic}",
            "abstract": f"Placeholder abstract about {topic}.",
            "url": "#",
            "published": str(datetime.utcnow().year),
            "authors": "Author A, Author B"
        })
    return pd.DataFrame(rows)

# ---------- job processing ----------
async def process_job(task_id: str, options: dict):
    try:
        JOBS[task_id]["status"] = "running"
        JOBS[task_id]["progress"] = 2
        JOBS[task_id]["messages"].append("starting")
        JOBS[task_id]["timestamps"]["start"] = time.time()

        topic = options.get("topic","")
        max_papers = int(options.get("max_papers", 40))
        generate_bullets = bool(options.get("generate_bullets", True))
        top_n = int(options.get("top_n", 15))
        auto_cluster = bool(options.get("auto_cluster", True))

        # fetch
        JOBS[task_id]["stage"] = "fetching"
        JOBS[task_id]["messages"].append("fetching papers")
        JOBS[task_id]["progress"] = 12
        df = fetch_arxiv_online(topic, max_results=max_papers)

        JOBS[task_id]["result_struct"] = {"papers_df": None, "clusters": None, "perpaper": {}, "cluster_summaries": {}}
        df["id"] = df.index
        JOBS[task_id]["result_struct"]["papers_df"] = to_serializable(df.to_dict(orient="records"))
        JOBS[task_id]["progress"] = 20

        # embeddings (chunked)
        JOBS[task_id]["stage"] = "embedding"
        JOBS[task_id]["messages"].append("embedding abstracts")
        abstracts = df["abstract"].fillna("").tolist()
        topic_vec = emb_model.encode([topic], batch_size=1, convert_to_numpy=True, normalize_embeddings=True)
        batch_size = 32
        embeddings_list = []
        for i in range(0, len(abstracts), batch_size):
            chunk = abstracts[i:i+batch_size]
            emb = emb_model.encode(chunk, batch_size=32, convert_to_numpy=True, normalize_embeddings=True).astype("float32")
            embeddings_list.append(emb)
            JOBS[task_id]["progress"] = min(48, 20 + int(28 * (i + batch_size) / max(1, len(abstracts))))
            JOBS[task_id]["messages"].append(f"embedded {min(i+batch_size,len(abstracts))}/{len(abstracts)}")
            await asyncio.sleep(0.05)
        paper_vecs = np.vstack(embeddings_list) if embeddings_list else np.zeros((len(abstracts), 384))
        rel = cosine_similarity(paper_vecs, topic_vec).ravel()
        df["relevance"] = rel
        JOBS[task_id]["result_struct"]["papers_df"] = to_serializable(df.sort_values("relevance", ascending=False).to_dict(orient="records"))
        JOBS[task_id]["progress"] = 54
        JOBS[task_id]["partial_top"] = JOBS[task_id]["result_struct"]["papers_df"][:10]

        # clustering
        JOBS[task_id]["stage"] = "clustering"
        JOBS[task_id]["messages"].append("clustering")
        k = (min(6, max(2, len(df)//12)) if auto_cluster else 4)
        km = MiniBatchKMeans(n_clusters=k, random_state=42, batch_size=32, n_init="auto")
        df["cluster"] = km.fit_predict(paper_vecs)
        JOBS[task_id]["result_struct"]["papers_df"] = to_serializable(df.to_dict(orient="records"))
        JOBS[task_id]["progress"] = 70

        # cluster summaries
        JOBS[task_id]["stage"] = "summarizing_clusters"
        cluster_summaries = {}
        unique_clusters = sorted(df["cluster"].unique())
        for idx_c, c in enumerate(unique_clusters):
            sub = df[df.cluster == c].sort_values("relevance", ascending=False).head(7)
            titles = "\n".join(f"- {t}" for t in sub["title"])
            prompt = ("Write a concise 90-120 word overview of this cluster for the topic below. "
                      "Name common methods/datasets if obvious; avoid fluff.\n"
                      f"Topic: {topic}\nPapers:\n{titles}")
            out = sum_model(prompt, max_new_tokens=140, do_sample=False)[0]["generated_text"].strip()
            cluster_summaries[int(c)] = out
            JOBS[task_id]["progress"] = 70 + int(12 * (idx_c+1) / max(1, len(unique_clusters)))
            JOBS[task_id]["messages"].append(f"cluster {c} summarized")
            await asyncio.sleep(0.05)
        JOBS[task_id]["result_struct"]["cluster_summaries"] = to_serializable(cluster_summaries)
        JOBS[task_id]["progress"] = 84

        # per-paper bullets
        JOBS[task_id]["stage"] = "perpaper"
        perpaper_reasons = {}
        if generate_bullets:
            top_idx = df.sort_values("relevance", ascending=False).head(top_n).index.tolist()
            for i, idx in enumerate(top_idx, 1):
                r = df.loc[idx]
                prompt = ("You are helping a student quickly judge relevance of a paper to a topic.\n"
                          f"Topic: {topic}\nPaper title: {r['title']}\nAbstract: {r['abstract']}\n\n"
                          "In 3 short bullet points, explain WHY this paper is relevant to the topic. Be specific; avoid fluff.")
                out = sum_model(prompt, max_new_tokens=120, do_sample=False)[0]["generated_text"].strip()
                perpaper_reasons[int(idx)] = out
                JOBS[task_id]["progress"] = 84 + int(12 * i / max(1, len(top_idx)))
                JOBS[task_id]["messages"].append(f"bullets {i}/{len(top_idx)}")
                JOBS[task_id]["result_struct"]["perpaper"] = to_serializable(perpaper_reasons)
                await asyncio.sleep(0.05)
        JOBS[task_id]["result_struct"]["perpaper"] = to_serializable(perpaper_reasons)
        JOBS[task_id]["result_struct"]["clusters"] = int(k)
        JOBS[task_id]["progress"] = 98

        # finalize
        JOBS[task_id]["stage"] = "finalizing"
        JOBS[task_id]["messages"].append("finalizing")
        JOBS[task_id]["status"] = "done"
        JOBS[task_id]["progress"] = 100
        JOBS[task_id]["messages"].append("done")
        JOBS[task_id]["timestamps"]["end"] = time.time()
    except Exception as e:
        JOBS[task_id]["status"] = "error"
        JOBS[task_id]["messages"].append("error: " + str(e))
        JOBS[task_id]["progress"] = 100

# ---------- API endpoints ----------
@app.post("/run")
async def run_endpoint(payload: Dict):
    topic = payload.get("topic","") if isinstance(payload, dict) else ""
    if not topic:
        return JSONResponse({"error":"topic required"}, status_code=400)
    task_id = uuid.uuid4().hex
    JOBS[task_id] = {
        "status": "queued", "progress": 0,
        "messages": ["queued"], "created": datetime.utcnow().isoformat(),
        "timestamps": {"created": time.time(), "start": None, "end": None},
        "stage": "queued", "partial_top": [], "result_struct": None
    }
    asyncio.create_task(process_job(task_id, payload))
    return {"task_id": task_id}

@app.get("/events/{task_id}")
async def sse_endpoint(task_id: str):
    if task_id not in JOBS:
        raise HTTPException(status_code=404, detail="task not found")
    async def event_generator():
        last_progress = -1
        last_stage = None
        while True:
            job = JOBS.get(task_id)
            if job is None:
                yield f"data: {json.dumps({'status':'error','message':'job not found'})}\n\n"
                break
            start_ts = job["timestamps"].get("start") or job["timestamps"].get("created")
            if start_ts and job.get("progress",0) > 2:
                elapsed = time.time() - start_ts
                prog = job.get("progress",0)
                est_total = elapsed * 100.0 / max(1, prog) if prog>0 else None
                remaining = max(0, est_total - elapsed) if est_total is not None else None
            else:
                remaining = None
            payload = {
                "status": job.get("status"),
                "progress": int(job.get("progress",0)),
                "stage": job.get("stage"),
                "messages": job.get("messages", [])[-4:],
                "partial_top": job.get("partial_top", []),
                "result_available": job.get("status")=="done",
                "eta_seconds": int(remaining) if remaining is not None else None
            }
            yield f"data: {json.dumps(to_serializable(payload))}\n\n"
            if payload["status"] in ("done","error"):
                break
            await asyncio.sleep(1.0)
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/results/{task_id}")
async def results_endpoint(task_id: str):
    job = JOBS.get(task_id)
    if not job:
        raise HTTPException(status_code=404, detail="task not found")
    if job["status"] != "done":
        return {"status": job["status"], "progress": job["progress"]}
    return to_serializable(job.get("result_struct", {}))

@app.get("/export/{task_id}/{kind}")
async def export_endpoint(task_id: str, kind: str):
    job = JOBS.get(task_id)
    if not job or job.get("result_struct") is None:
        raise HTTPException(status_code=404, detail="no result")
    if kind not in ("csv","pdf"):
        raise HTTPException(status_code=400, detail="kind must be 'csv' or 'pdf'")
    res = job["result_struct"]
    papers = res.get("papers_df", [])
    df = pd.DataFrame(papers)
    if kind == "csv":
        buf = io.StringIO()
        df.to_csv(buf, index=False)
        data = buf.getvalue().encode("utf-8"); buf.close()
        return Response(content=data, media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={task_id}.csv"})
    else:
        perpaper = res.get("perpaper", {})
        clusters = res.get("cluster_summaries", {})
        # Get topic from job options or default
        topic = job.get("topic", "Research") if "topic" in job else "Research"
        
        pdf_bytes = build_pdf_in_memory(topic, pd.DataFrame(papers), perpaper, clusters)
        
        # Sanitize filename
        safe_topic = "".join([c for c in topic if c.isalnum() or c in (' ', '-', '_')]).strip().replace(' ', '_')
        filename = f"ScoutReport_{safe_topic}_{task_id[:6]}.pdf"
        
        return Response(content=pdf_bytes, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename={filename}"})

@app.post("/upload")
async def upload_endpoint(file: UploadFile = File(...)):
    out_path = os.path.join("results", f"uploaded_{uuid.uuid4().hex}.csv")
    contents = await file.read()
    with open(out_path, "wb") as f:
        f.write(contents)
    return {"path": out_path, "filename": file.filename}

# Mount frontend at root LAST to avoid shadowing API routes
app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")

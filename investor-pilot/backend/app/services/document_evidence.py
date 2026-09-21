"""Extractive retrieval: fitted to the selected PDF, never executes document text."""
from pathlib import Path
import re
import pandas as pd
from pypdf import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

def read_pdf(path, limit=None):
    if Path(path).stat().st_size > 25 * 1024 * 1024:
        raise ValueError("PDF evidence is limited to 25 MB; split the document before upload.")
    reader=PdfReader(path)
    if reader.is_encrypted:
        raise ValueError("Unlock the PDF locally before uploading it.")
    if len(reader.pages)>300:
        raise ValueError("PDF evidence supports up to 300 pages per document.")
    rows=[]
    for index,page in enumerate(reader.pages):
        text=(page.extract_text() or "").strip()
        if text: rows.append({"page":index+1,"text":text[:20000]})
    if not rows: raise ValueError("No searchable text was found. Scanned PDFs require OCR before upload.")
    return pd.DataFrame(rows).head(limit) if limit is not None else pd.DataFrame(rows)

def retrieve(dataset_id, question):
    from app.platform_v1.datasets import get_dataset,get_dataset_path,_checksum
    dataset=get_dataset(dataset_id);path=get_dataset_path(dataset_id)
    before=_checksum(path)
    if before != dataset.checksum_sha256:raise ValueError("Dataset checksum changed; register a new version.")
    frame=read_pdf(path)
    chunks=[]
    for row in frame.itertuples():
        words=row.text.split()
        for start in range(0,len(words),180):
            chunks.append((row.page," ".join(words[start:start+220])))
    if len(chunks)>3000: raise ValueError("Document text exceeds the interactive retrieval limit.")
    vectorizer=TfidfVectorizer(stop_words="english",ngram_range=(1,2),max_features=30000)
    try: matrix=vectorizer.fit_transform([text for _,text in chunks])
    except ValueError as exc: raise ValueError("No searchable vocabulary was found.") from exc
    query=vectorizer.transform([question])
    scores=linear_kernel(query,matrix)[0]
    matches=[{"page":chunks[i][0],"excerpt":chunks[i][1],"retrieval_score":round(float(scores[i]),4)}
             for i in scores.argsort()[::-1][:3] if scores[i]>=0.12]
    if _checksum(path)!=before:raise ValueError("Document changed during retrieval.")
    answer="\n\n".join(f"Page {m['page']}: {m['excerpt']}" for m in matches) if matches else "No sufficiently matching passage was found. Rephrase using terms in the document."
    return {"answer":answer,"evidence":[f"Dataset {dataset_id}: {dataset.name}",f"SHA256 {before}"],
            "passages":matches,"mode":"extractive_pdf_retrieval",
            "limitations":["TF-IDF retrieval fitted to this document; not a fine-tuned language model.",
                           "Scores measure lexical similarity, not factual confidence. Source passages may contain unverified claims.",
                           "No OCR, image/seismic interpretation or autonomous actions."]}

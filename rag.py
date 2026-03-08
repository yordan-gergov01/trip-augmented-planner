import requests
import streamlit as st
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from config import HEADERS


@st.cache_data
def get_wikivoyage_text(city):
    try:
        response = requests.get(
            "https://en.wikivoyage.org/w/api.php",
            params={
                "action":     "query",
                "titles":     city,
                "prop":       "extracts",
                "format":     "json",
                "explaintext": True
            },
            headers=HEADERS,
            timeout=10
        )
        data = response.json()
        pages = data["query"]["pages"]
        page = next(iter(pages.values()))
        return page.get("extract", "")
    except Exception as e:
        st.error(f"Wikivoyage error: {e}")
        return ""


def chunk_text(text, chunk_size=900):
    paragraphs = text.split("\n")
    chunks = []
    current_chunk = ""

    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if len(current_chunk) + len(paragraph) <= chunk_size:
            current_chunk += " " + paragraph
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = paragraph

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks


@st.cache_data
def build_tfidf_index(city):
    text = get_wikivoyage_text(city)
    if not text:
        return None, None, []

    chunks = chunk_text(text)
    if not chunks:
        return None, None, []

    vectorizer = TfidfVectorizer()
    matrix = vectorizer.fit_transform(chunks)

    return vectorizer, matrix, chunks


def search_chunks(query, vectorizer, matrix, chunks, top_k=3):
    query_vec = vectorizer.transform([query])
    scores = cosine_similarity(query_vec, matrix)[0]
    top_indices = np.argsort(scores)[::-1][:top_k]

    return [
        {
            "chunk_id": int(idx),
            "source":   "Wikivoyage",
            "text":     chunks[idx],
            "score":    float(scores[idx])
        }
        for idx in top_indices
    ]


def get_travel_context(city, query):
    vectorizer, matrix, chunks = build_tfidf_index(city)
    if not vectorizer:
        return []
    return search_chunks(query, vectorizer, matrix, chunks)
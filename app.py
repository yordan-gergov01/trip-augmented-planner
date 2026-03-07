import os
import requests
import streamlit as st
from openai import OpenAI
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

st.set_page_config(page_title="Trip Planner AI", page_icon="✈️")
st.title("✈️ Trip Planner AI Agent")

os.makedirs("data", exist_ok=True)

with st.sidebar:
    st.header("🔑 API Configuration")
    api_key = st.text_input("OpenAI API Key", type="password", key="user_openai_key")

    if api_key:
        st.session_state["openai_api_key"] = api_key
        st.success("API Key set")
    else:
        st.warning("Please enter your OpenAI API key")

    if st.button("Clear API Key"):
        st.session_state.pop("openai_api_key", None)
        st.rerun()

client = None
if "openai_api_key" in st.session_state:
    client = OpenAI(api_key=st.session_state["openai_api_key"])

USER_AGENT = "trip-planner/1.0 (yordangergov@xype.io)"
HEADERS = {"User-Agent": USER_AGENT}

INTEREST_TO_TAGS = {
    "museums":    [("tourism", "museum|gallery")],
    "food":       [("amenity", "restaurant|cafe|fast_food")],
    "outdoors":   [("leisure", "park|nature_reserve"), ("natural", "peak|beach")],
    "history":    [("historic", "monument|castle|ruins|memorial")],
    "shopping":   [("shop", "mall|clothes|market")],
    "nightlife":  [("amenity", "bar|pub|nightclub")],
    "religion":   [("amenity", "place_of_worship")],
    "transport":  [("public_transport", "station")],
}

@st.cache_data
def geocode_city(city):
    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": city, "format": "json", "limit": 1},
            headers=HEADERS,
            timeout=10
        )
        results = response.json()
        if results:
            return {"lat": float(results[0]["lat"]), "lon": float(results[0]["lon"])}
        return None
    except Exception as e:
        st.error(f"Geocoding error: {e}")
        return None

def build_overpass_query(lat, lon, radius, tags):
    tag_filters = ""
    for key, value in tags:
        tag_filters += f'  node(around:{radius},{lat},{lon})["{key}"~"{value}"];\n'
    return "[out:json];\n(\n" + tag_filters + ");\nout 20;" 


@st.cache_data
def search_pois(city, interests, radius=2000):
    interests = tuple(interests) 

    location = geocode_city(city)
    if not location:
        return []

    lat, lon = location["lat"], location["lon"]

    all_tags = []
    for interest in interests:
        all_tags.extend(INTEREST_TO_TAGS.get(interest, []))

    if not all_tags:
        return []

    query = build_overpass_query(lat, lon, radius, all_tags)

    data = None
    for attempt in range(3):
        try:
            response = requests.post(
                "https://overpass-api.de/api/interpreter",
                data={"data": query},
                headers=HEADERS,
                timeout=30
            )
            if response.status_code == 200:
                data = response.json()
                break
            else:
                st.write("Error response:", response.text[:300])
        except Exception as e:
            st.error(f"Attempt {attempt + 1} failed: {e}")

    if not data:
        return []

    pois = []
    for element in data.get("elements", []):
        tags = element.get("tags", {})
        name = tags.get("name")
        if not name:
            continue

        category = (
            tags.get("tourism") or
            tags.get("amenity") or
            tags.get("leisure") or
            tags.get("historic") or
            tags.get("shop") or
            tags.get("natural") or
            "unknown"
        )

        pois.append({
            "poi_id":   element["id"],
            "name":     name,
            "category": category,
            "lat":      element.get("lat"),
            "lon":      element.get("lon"),
            "url":      tags.get("website", ""),
        })

    return pois

@st.cache_data
def get_wikivoyage_text(city):
    try:
        response = requests.get(
            "https://en.wikivoyage.org/w/api.php",
            params={
                "action": "query",
                "titles": city,
                "prop": "extracts",
                "format": "json",
                "explaintext": True
            },
            headers=HEADERS,
            timeout=10
        )
        data = response.json()
        pages = data["query"]["pages"]
        page = next(iter(pages.values())) 
        text = page.get("extract", "")
        return text
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

    results = []
    for i, idx in enumerate(top_indices):
        results.append({
            "chunk_id": int(idx),
            "source":   "Wikivoyage",
            "text":     chunks[idx],
            "score":    float(scores[idx])
        })

    return results

def get_travel_context(city, query):
    vectorizer, matrix, chunks = build_tfidf_index(city)
    if not vectorizer:
        return []
    return search_chunks(query, vectorizer, matrix, chunks)

st.subheader("🔍 Search Points of Interest")

city = st.text_input("City", "Paris")
interests = st.multiselect(
    "Interests",
    options=list(INTEREST_TO_TAGS.keys()),
    default=["museums", "food"]
)

if st.button("Search POIs"):
    with st.spinner("Searching..."):
        pois = search_pois(city, tuple(interests))
        if pois:
            st.success(f"Found {len(pois)} POIs in {city}")
            st.dataframe(pois)
        else:
            st.warning("No POIs found.")
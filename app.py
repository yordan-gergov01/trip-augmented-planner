import os
import streamlit as st
from openai import OpenAI
from config import INTEREST_TO_TAGS
from maps import search_pois
from agent import run_agent

st.set_page_config(page_title="Trip Planner AI", page_icon="✈️")
st.title("✈️ Trip Planner AI Agent")
os.makedirs("data", exist_ok=True)

with st.sidebar:
    st.header("🔑 API Configuration")
    api_key = st.text_input("OpenAI API Key", type="password", key="user_openai_key")

    if api_key:
        st.session_state["openai_api_key"] = api_key
        st.success("API Key set ✅")
    else:
        st.warning("Please enter your OpenAI API key")

    if st.button("Clear API Key"):
        st.session_state.pop("openai_api_key", None)
        st.rerun()

client = None
if "openai_api_key" in st.session_state:
    client = OpenAI(api_key=st.session_state["openai_api_key"])

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

st.divider()
st.subheader("🗺️ Generate Itinerary")

user_request = st.text_area(
    "Describe your trip:",
    "Plan a 3-day trip to Paris for a couple who love museums, food and history."
)

if st.button("Generate Itinerary"):
    if not client:
        st.warning("Please enter your OpenAI API key first.")
    else:
        with st.spinner("Agent is planning your trip..."):
            itinerary, tool_state, trace = run_agent(client, user_request)

        with st.expander("🔍 Agent Execution Trace"):
            for step in trace:
                st.markdown(step)

        st.success(f"Found {len(tool_state['pois'])} POIs total")
        st.markdown("📋 Your Itinerary")
        st.markdown(itinerary)
import os
import re
import json
import streamlit as st
import pydeck as pdk
import numpy as np
from openai import OpenAI
from config import INTEREST_TO_TAGS
from agent import run_agent

st.set_page_config(
    page_title="Trip Planner AI",
    page_icon="✈️",
    layout="wide"
)

os.makedirs("data", exist_ok=True)

defaults = {
    "itinerary":   None,
    "tool_state":  None,
    "trace":       [],
    "loading":     False,
    "destination": "",
    "trip_length": "3 days",
    "pace":        "Moderate",
    "interests":   ["museums", "food"],
    "constraints": "",
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

client = None
if "openai_api_key" in st.session_state:
    client = OpenAI(api_key=st.session_state["openai_api_key"])

if st.session_state.loading:
    with st.status("🤖 Agent is planning your trip...", expanded=False) as status:
        user_request = (
            f"Plan a {st.session_state.trip_length} trip to {st.session_state.destination} "
            f"for someone who loves {', '.join(st.session_state.interests)}. "
            f"Keep a {st.session_state.pace.lower()} pace."
            + (f" Constraints: {st.session_state.constraints}." if st.session_state.constraints else "")
        )
        itinerary, tool_state, trace = run_agent(client, user_request)

        st.session_state.itinerary  = itinerary
        st.session_state.tool_state = tool_state
        st.session_state.trace      = trace
        st.session_state.loading    = False

        status.update(label="✅ Itinerary ready!", state="complete")
    st.rerun()
    st.stop()

with st.sidebar:
    st.title("✈️ Trip Planner AI")
    st.divider()

    st.header("🔑 API Key")
    api_key = st.text_input("OpenAI API Key", type="password", key="user_openai_key")

    if api_key:
        st.session_state["openai_api_key"] = api_key
        client = OpenAI(api_key=api_key)
        st.success("API Key set ✅")
    else:
        st.warning("Enter your OpenAI API key")

    if st.button("Clear API Key"):
        st.session_state.pop("openai_api_key", None)
        st.rerun()

    st.divider()
    st.caption("Powered by OpenAI · OpenStreetMap · Wikivoyage")

st.title("🗺️ AI Trip Planner")
st.caption("Plan your perfect trip with real data from OpenStreetMap and Wikivoyage.")
st.divider()

st.subheader("📋 Trip Details")

col1, col2, col3 = st.columns(3)
with col1:
    destination = st.text_input("🏙️ Destination", placeholder="e.g. Paris, Tokyo, Rome")
with col2:
    trip_length = st.selectbox(
        "📅 Trip Length",
        ["1 day", "2 days", "3 days", "4 days", "5 days", "1 week"],
        index=2
    )
with col3:
    pace = st.selectbox("🏃 Pace", ["Relaxed", "Moderate", "Intensive"], index=1)

interests = st.multiselect(
    "🎯 Interests",
    options=list(INTEREST_TO_TAGS.keys()),
    default=["museums", "food"]
)

constraints = st.text_area(
    "⚠️ Special Constraints (optional)",
    placeholder="e.g. travelling with kids, vegetarian food only, wheelchair accessible...",
    height=80
)

st.divider()

col_btn, col_msg = st.columns([1, 4])
with col_btn:
    generate_clicked = st.button(
        "✨ Generate Itinerary",
        type="primary",
        disabled=not destination or not client,
        use_container_width=True
    )
with col_msg:
    if not client:
        st.warning("⬅️ Enter your OpenAI API key in the sidebar.")
    elif not destination:
        st.info("⬅️ Enter a destination to get started.")

if generate_clicked:
    st.session_state.destination = destination
    st.session_state.trip_length = trip_length
    st.session_state.pace        = pace
    st.session_state.interests   = interests
    st.session_state.constraints = constraints
    st.session_state.loading     = True
    st.session_state.itinerary   = None
    st.session_state.tool_state  = None
    st.session_state.trace       = []
    st.rerun()

if st.session_state.itinerary:
    st.divider()

    pois   = st.session_state.tool_state.get("pois", [])
    chunks = st.session_state.tool_state.get("chunks", [])

    col_left, col_right = st.columns([3, 1])

    with col_left:
        st.subheader(f"📋 Your Itinerary — {st.session_state.destination}")
        st.markdown(st.session_state.itinerary)

    with col_right:
        st.subheader("📊 Summary")
        st.metric("POIs Found", len(pois))
        st.metric("Guide Sections", len(chunks))
        st.metric("Trip Length", st.session_state.trip_length)
        st.metric("Pace", st.session_state.pace)
        st.divider()

        export_data = {
            "destination": st.session_state.destination,
            "trip_length": st.session_state.trip_length,
            "pace": st.session_state.pace,
            "interests": st.session_state.interests,
            "constraints": st.session_state.constraints,
            "itinerary": st.session_state.itinerary,
            "pois": pois,
        }
        st.download_button(
            label="⬇️ Download Itinerary",
            data=json.dumps(export_data, indent=2),
            file_name=f"{st.session_state.destination.lower().replace(' ', '_')}_itinerary.json",
            mime="application/json",
            use_container_width=True
        )

    valid_pois = [p for p in pois if p.get("lat") and p.get("lon")]

    if valid_pois:
        st.divider()
        st.subheader("🗺️ Map View")

        map_col1, map_col2 = st.columns([3, 1])

        with map_col2:
            map_style = st.selectbox(
                "🎨 Map Style",
                ["Dark", "Light", "Satellite"],
                index=0
            )
            style_map = {
                "Dark": "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
                "Light": "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
                "Satellite": "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
            }

        with map_col1:
            def assign_day(poi_name, itinerary_text, total_pois, total_days):
                """Try to find which day a POI appears in the itinerary."""
                lines = itinerary_text.split("\n")
                current_day = 1
                for line in lines:
                    day_match = re.search(r'day\s*(\d+)', line, re.IGNORECASE)
                    if day_match:
                        current_day = int(day_match.group(1))
                    if poi_name.lower() in line.lower():
                        return current_day
                return None

            DAY_COLORS = [
                [255, 100, 100],
                [100, 180, 255],
                [100, 220, 100],
                [255, 200, 50],
                [200, 100, 255],
                [255, 150, 50],
                [50,  220, 200],
            ]

            total_days = int(re.search(r'\d+', st.session_state.trip_length).group())

            map_data = []
            for poi in valid_pois:
                day = assign_day(poi["name"], st.session_state.itinerary, len(valid_pois), total_days)
                map_data.append({
                    "name": poi["name"],
                    "category": poi["category"],
                    "lat": float(poi["lat"]),
                    "lon": float(poi["lon"]),
                    "day": f"Day {day}" if day else "Unscheduled",
                    "day_num": (day - 1) % len(DAY_COLORS) if day else 0,
                    "r": DAY_COLORS[(day - 1) % len(DAY_COLORS)][0] if day else 150,
                    "g": DAY_COLORS[(day - 1) % len(DAY_COLORS)][1] if day else 150,
                    "b": DAY_COLORS[(day - 1) % len(DAY_COLORS)][2] if day else 150,
                })

            day_options = ["All Days"] + sorted(set(p["day"] for p in map_data))
            selected_day = st.selectbox("📅 Filter by Day", day_options)

            filtered = map_data if selected_day == "All Days" else [p for p in map_data if p["day"] == selected_day]

            lats = [p["lat"] for p in filtered]
            lons = [p["lon"] for p in filtered]
            center_lat = np.mean(lats)
            center_lon = np.mean(lons)
            spread = max(max(lats) - min(lats), max(lons) - min(lons))
            zoom = 13 if spread < 0.02 else 12 if spread < 0.05 else 11 if spread < 0.1 else 10

            scatter_layer = pdk.Layer(
                "ScatterplotLayer",
                data=filtered,
                get_position="[lon, lat]",
                get_fill_color="[r, g, b, 200]",
                get_radius=35,
                radius_min_pixels=4,
                radius_max_pixels=12,
                pickable=True,
            )

            path_layer = pdk.Layer(
                "PathLayer",
                data=[{"path": [[p["lon"], p["lat"]] for p in filtered]}],
                get_path="path",
                get_color=[255, 255, 255, 60],
                get_width=2,
                width_min_pixels=1,
            )

            view = pdk.ViewState(
                latitude=center_lat,
                longitude=center_lon,
                zoom=zoom,
                pitch=0,
            )

            tooltip = {
                "html": "<b>{name}</b><br/>Category: {category}<br/>{day}",
                "style": {"backgroundColor": "#1a1a2e", "color": "white", "fontSize": "13px", "padding": "8px"}
            }

            deck = pdk.Deck(
                layers=[path_layer, scatter_layer],
                initial_view_state=view,
                map_style=style_map[map_style],
                tooltip=tooltip,
            )

            st.pydeck_chart(deck)

    if pois:
        st.divider()
        st.subheader("📍 Points of Interest")
        st.dataframe(pois, use_container_width=True, hide_index=True)

    if chunks:
        with st.expander("📚 Travel Guide Sources (Wikivoyage)"):
            for chunk in chunks:
                st.caption(f"Score: {chunk['score']:.3f} · {chunk['source']}")
                st.markdown(f"> {chunk['text']}")
                st.divider()

    with st.expander("🔍 Agent Execution Trace"):
        for step in st.session_state.trace:
            st.markdown(step)
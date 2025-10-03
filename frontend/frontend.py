import streamlit as st
import requests

st.set_page_config(page_title="Pack & Go", page_icon="🌍")

st.title("🌍 Pack & Go – AI Travel Itinerary Generator")
st.write("Enter your travel query and get a personalized itinerary.")

query = st.text_input("✈️ Where do you want to go?")

if st.button("Generate Itinerary"):
    with st.spinner("Generating..."):
        response = requests.post(
            "http://127.0.0.1:8000/itinerary",
            json={"query": query}
        )
        if response.status_code == 200:
            itinerary = response.json()
            st.subheader("📅 Your Itinerary")
            st.json(itinerary)   # Pretty-prints JSON for now
        else:
            st.error("❌ Error: Could not generate itinerary.")

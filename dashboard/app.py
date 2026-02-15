import streamlit as st
import httpx
import time
import os

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
st.set_page_config(layout="wide", page_title="Nexus Council")

st.title("🏛️ Nexus Council Dashboard")

with st.sidebar:
    st.header("Create New Council")
    prompt = st.text_area("Enter your complex query:", height=150)
    if st.button("Assemble Council"):
        if prompt:
            with st.spinner("Contacting the Architect..."):
                try:
                    resp = httpx.post(f"{BACKEND_URL}/api/council", json={"prompt": prompt})
                    if resp.status_code == 200:
                        data = resp.json()
                        st.session_state['session_id'] = data['session_id']
                        st.success(f"Council Created! ID: {data['session_id']}")
                    else:
                        st.error(f"Error: {resp.text}")
                except Exception as e:
                    st.error(f"Connection error: {e}")
        else:
            st.warning("Please enter a prompt.")

session_id = st.session_state.get('session_id')

if session_id:
    st.header(f"Council Session: `{session_id}`")
    placeholder = st.empty()
    
    while True:
        with placeholder.container():
            try:
                resp = httpx.get(f"{BACKEND_URL}/api/council/{session_id}")
                if resp.status_code == 200:
                    data = resp.json()
                    st.subheader(f"Status: {data['status']}")
                    
                    if data.get('agents'):
                        cols = st.columns(len(data['agents']))
                        for idx, agent in enumerate(data['agents']):
                            with cols[idx]:
                                status_color = {
                                    "PENDING": "🟡", "SEARCHING": "🔵", 
                                    "ANALYZING": "🟠", "COMPLETED": "🟢", "FAILED": "🔴"
                                }.get(agent['status'], "⚪")
                                
                                st.markdown(f"### {status_color} {agent['name']}")
                                st.caption(f"_{agent['role_description'][:50]}..._")
                                st.info(f"**Status:** {agent['status']}")
                    
                    if data['status'] == "COMPLETED":
                        st.success("Council has reached a consensus!")
                        st.markdown("### Consensus")
                        st.write(data.get('consensus'))
                        with st.expander("View Friction Points"):
                            st.write(data.get('friction'))
                        with st.expander("View Recommendation"):
                            st.write(data.get('recommendation'))
                        break
                    
                    elif data['status'] == "FAILED":
                        st.error("Council failed.")
                        break
                    
                    else:
                        time.sleep(2)
            except Exception as e:
                st.error(f"Error: {e}")
                break
else:
    st.info("Create a council from the sidebar to begin.")
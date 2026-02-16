import streamlit as st
import httpx
import time
import os

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
st.set_page_config(layout="wide", page_title="Nexus Council")

st.title("🏛️ Nexus Council Dashboard")

# Sidebar for Creation
with st.sidebar:
    st.header("Create New Council")
    prompt = st.text_area("Enter your complex query:", height=150)
    if st.button("Assemble Council"):
        if prompt:
            with st.spinner("Contacting the Architect..."):
                try:
                    # Increased timeout for initial creation
                    resp = httpx.post(
                        f"{BACKEND_URL}/api/council", 
                        json={"prompt": prompt}, 
                        timeout=60.0
                    )
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

# Main Area for Status
session_id = st.session_state.get('session_id')

if session_id:
    st.header(f"Council Session: `{session_id}`")
    placeholder = st.empty()
    
    # Polling Loop
    while True:
        with placeholder.container():
            try:
                # Increased timeout for polling (backend might be loading models)
                resp = httpx.get(f"{BACKEND_URL}/api/council/{session_id}", timeout=60.0)
                if resp.status_code == 200:
                    data = resp.json()
                    
                    # Display Status
                    st.subheader(f"Status: {data['status']}")
                    
                    # Display Agents
                    if data.get('agents'):
                        cols = st.columns(len(data['agents']))
                        for idx, agent in enumerate(data['agents']):
                            with cols[idx]:
                                # Color coding status
                                status_color = {
                                    "PENDING": "🟡",
                                    "SEARCHING": "🔵",
                                    "ANALYZING": "🟠",
                                    "COMPLETED": "🟢",
                                    "FAILED": "🔴"
                                }.get(agent['status'], "⚪")
                                
                                st.markdown(f"### {status_color} {agent['name']}")
                                st.caption(f"_{agent['role_description'][:50]}..._")
                                st.info(f"**Status:** {agent['status']}")
                    
                    # Display Final Results
                    if data['status'] == "COMPLETED":
                        st.success("Council has reached a consensus!")
                        st.markdown("### Consensus")
                        st.write(data.get('consensus'))
                        
                        with st.expander("View Friction Points"):
                            st.write(data.get('friction'))
                        
                        with st.expander("View Recommendation"):
                            st.write(data.get('recommendation'))
                        break # Stop polling
                    
                    elif data['status'] == "FAILED":
                        st.error("Council failed to reach a decision.")
                        break
                    
                    else:
                        time.sleep(2) # Wait before next poll

            except Exception as e:
                st.error(f"Error fetching updates: {e}")
                break
else:
    st.info("Create a council from the sidebar to begin.")
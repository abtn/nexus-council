import streamlit as st # pyright: ignore[reportMissingImports]
import httpx
import time
import os
import json
from datetime import datetime
from typing import Optional, Dict, Any, List

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
st.set_page_config(layout="wide", page_title="Nexus Council v2", page_icon="🏛️")

# ==========================================
# ENHANCED SESSION STATE WITH HISTORY
# ==========================================
def init_session_state():
    """Initialize all session state variables with safe defaults"""
    defaults = {
        'config': {
            'mode': 'standard',
            'models': {
                'architect': 'avalai/gemini-2.0-flash-lite',
                'hunter': 'avalai/gemma-3-12b-it',
                'analyst': 'avalai/nvidia_nim.llama-3.3-nemotron-super-49b-v1.5',
                'moderator': 'avalai/gemini-2.0-flash-lite'
            },
            'tone': 'academic',
            'length': 'standard',
            'enable_search': True,
            'decomposition_depth': 3
        },
        'session_id': None,
        'session_data': None,
        'polling_active': False,
        'last_error': None,
        # ENHANCED: Full session history storage
        'session_history': [],  # List of {id, timestamp, mode, prompt, data}
        'selected_history_data': None  # Currently selected history item
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# ==========================================
# HELPER FUNCTIONS
# ==========================================

def add_to_history(session_data: dict):
    """Add completed session to history, avoiding duplicates"""
    if not session_data:
        return
    
    session_id = str(session_data.get('id', ''))
    if not session_id:
        return
    
    # Check if already in history
    existing_ids = [str(s.get('id', '')) for s in st.session_state.session_history]
    if session_id in existing_ids:
        # Update existing entry
        idx = existing_ids.index(session_id)
        st.session_state.session_history[idx] = {
            'id': session_id,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M"),
            'mode': session_data.get('mode', 'unknown'),
            'prompt': session_data.get('user_prompt', '')[:50] + "..." if len(session_data.get('user_prompt', '')) > 50 else session_data.get('user_prompt', ''),
            'status': session_data.get('status', 'unknown'),
            'data': session_data  # Store full data for viewing
        }
    else:
        # Add new entry
        st.session_state.session_history.append({
            'id': session_id,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M"),
            'mode': session_data.get('mode', 'unknown'),
            'prompt': session_data.get('user_prompt', '')[:50] + "..." if len(session_data.get('user_prompt', '')) > 50 else session_data.get('user_prompt', ''),
            'status': session_data.get('status', 'unknown'),
            'data': session_data  # Store full data for viewing
        })
    
    # Keep only last 20 sessions to prevent memory bloat
    if len(st.session_state.session_history) > 20:
        st.session_state.session_history = st.session_state.session_history[-20:]


def get_history_labels() -> List[str]:
    """Generate display labels for session history"""
    labels = []
    for session in st.session_state.session_history:
        mode_emoji = {"standard": "🏛️", "decomposition": "🔬", "quick": "⚡"}.get(session['mode'], "📄")
        status_emoji = {"COMPLETED": "✅", "FAILED": "❌"}.get(session['status'], "⏳")
        label = f"{mode_emoji} {session['timestamp']} | {status_emoji} {session['prompt'][:30]}..."
        labels.append(label)
    return labels


def display_session_data(data: dict, title: str = "Session Results"):
    """Display session results in a consistent format"""
    if not data:
        st.warning("No data to display")
        return
    
    status = data.get('status', 'UNKNOWN')
    
    # Header with metadata
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.markdown(f"### {title}")
    with col2:
        mode = data.get('mode', 'unknown')
        mode_emoji = {"standard": "🏛️", "decomposition": "🔬", "quick": "⚡"}.get(mode, "📄")
        st.caption(f"{mode_emoji} Mode: **{mode}**")
    with col3:
        st.caption(f"Status: **{status}**")
    
    if status == "COMPLETED":
        # Create tabs for different views
        tab_summary, tab_details, tab_raw = st.tabs(["📋 Executive Summary", "🔍 Detailed Analysis", "⚙️ Technical Data"])
        
        with tab_summary:
            consensus = data.get('consensus', 'No consensus available')
            st.markdown("#### 🏆 Consensus / Executive Summary")
            st.markdown(consensus)
            
            # Export buttons row
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # JavaScript clipboard copy
                copy_js = f"""
                <script>
                function copyConsensus() {{
                    const text = {json.dumps(consensus)};
                    navigator.clipboard.writeText(text).then(function() {{
                        const btn = document.getElementById('copy-btn');
                        btn.innerHTML = '✅ Copied!';
                        setTimeout(() => btn.innerHTML = '📋 Copy Summary', 2000);
                    }}, function(err) {{
                        alert('Failed to copy: ' + err);
                    }});
                }}
                </script>
                <button id="copy-btn" onclick="copyConsensus()" style="width:100%; padding:8px; background:#3b82f6; color:white; border:none; border-radius:5px; cursor:pointer;">
                    📋 Copy Summary
                </button>
                """
                st.components.v1.html(copy_js, height=40)
            
            with col2:
                json_data = json.dumps(data, indent=2)
                st.download_button(
                    label="💾 JSON",
                    data=json_data,
                    file_name=f"council_{str(data.get('id', 'unknown'))[:8]}.json",
                    mime="application/json",
                    use_container_width=True
                )
            
            with col3:
                md_content = f"""# Nexus Council Report

**Session ID:** {data.get('id', 'unknown')}
**Mode:** {data.get('mode', 'unknown')}
**Query:** {data.get('user_prompt', 'unknown')}
**Completed:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Executive Summary

{data.get('consensus', 'N/A')}

## Detailed Analysis

{data.get('friction', 'N/A')}

## Recommendations

{data.get('recommendation', 'N/A')}
"""
                st.download_button(
                    label="📝 Markdown",
                    data=md_content,
                    file_name=f"report_{str(data.get('id', 'unknown'))[:8]}.md",
                    mime="text/markdown",
                    use_container_width=True
                )
        
        with tab_details:
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("#### ⚠️ Friction Points / Analysis")
                st.markdown(data.get('friction', 'No friction analysis available'))
            
            with col2:
                st.markdown("#### 💡 Recommendations")
                st.markdown(data.get('recommendation', 'No recommendations available'))
            
            # Show agents if available
            if data.get('agents'):
                st.divider()
                st.markdown("#### 👥 Agents")
                for agent in data['agents']:
                    with st.expander(f"{agent.get('name', 'Unknown')} - {agent.get('status', 'unknown')}"):
                        st.caption(f"Role: {agent.get('role_description', 'N/A')[:100]}...")
        
        with tab_raw:
            st.json(data)
    
    elif status == "FAILED":
        st.error("❌ This session failed to complete")
        if data.get('agents'):
            failed_agents = [a for a in data['agents'] if a.get('status') == 'FAILED']
            if failed_agents:
                st.write("Failed agents:", [a['name'] for a in failed_agents])
    
    else:
        st.info(f"⏳ Session status: {status}")
        if data.get('agents'):
            cols = st.columns(min(len(data['agents']), 4))
            for idx, agent in enumerate(data['agents']):
                with cols[idx % len(cols)]:
                    emoji = {"COMPLETED": "✅", "SEARCHING": "🔍", "ANALYZING": "🧠", 
                            "FAILED": "❌", "PENDING": "⏳"}.get(agent.get('status'), "⚪")
                    st.metric(f"{emoji} {agent.get('name', 'Unknown')[:15]}", agent.get('status'))


# ==========================================
# MAIN UI
# ==========================================
st.title("🏛️ Nexus Council v2.0")

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # Mode selection
    mode_options = ["standard", "decomposition", "quick"]
    current_mode = st.session_state.config['mode']
    try:
        mode_index = mode_options.index(current_mode)
    except ValueError:
        mode_index = 0
    
    selected_mode = st.radio(
        "Strategy",
        options=mode_options,
        format_func=lambda x: {"standard": "🏛️ Standard Council", "decomposition": "🔬 Decomposition", "quick": "⚡ Quick Answer"}[x],
        index=mode_index
    )
    
    if selected_mode != st.session_state.config['mode']:
        st.session_state.config['mode'] = selected_mode
        st.rerun()
    
    # Mode-specific controls
    if selected_mode == "decomposition":
        st.session_state.config['decomposition_depth'] = st.slider("Research Angles", 2, 5, 3)
    
    if selected_mode == "quick":
        st.session_state.config['enable_search'] = False
        st.info("🔒 Web search disabled in Quick mode")
    else:
        st.session_state.config['enable_search'] = st.toggle("🔎 Enable Web Search", value=True)
    
    st.divider()
    
    # Model selection
    with st.expander("🧠 Model Selection"):
        models = [
            'avalai/gemini-2.0-flash-lite',
            'avalai/nvidia_nim.llama-3.3-nemotron-super-49b-v1.5',
            'avalai/gemma-3-27b-it',
            'avalai/gemma-3-12b-it',
            'avalai/gpt-5-nano',
            'cloudflare/@cf/meta/llama-3-8b-instruct'
        ]
        cfg = st.session_state.config['models']
        cfg['architect'] = st.selectbox("Architect", models, index=0)
        cfg['hunter'] = st.selectbox("Hunter", models, index=3)
        cfg['analyst'] = st.selectbox("Analyst", models, index=1)
        cfg['moderator'] = st.selectbox("Moderator", models, index=0)
    
    st.divider()
    
    # Output style
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.config['tone'] = st.selectbox("Tone", ["academic", "business", "casual"], index=0)
    with col2:
        st.session_state.config['length'] = st.selectbox("Length", ["concise", "standard", "comprehensive"], index=1)
    
    # Session management
    st.divider()
    if st.session_state.session_id or st.session_state.session_data:
        if st.button("🧹 Clear Current", use_container_width=True):
            st.session_state.session_id = None
            st.session_state.session_data = None
            st.session_state.polling_active = False
            st.rerun()
    
    # ==========================================
    # ENHANCED: CLICKABLE SESSION HISTORY
    # ==========================================
    if st.session_state.session_history:
        st.divider()
        st.subheader("📚 Session History")
        
        # Create radio buttons for history selection
        history_labels = get_history_labels()
        
        # Add "None" option to deselect
        display_labels = ["📋 Current Session (if active)"] + history_labels
        
        selected_idx = st.radio(
            "Select session to view:",
            options=range(len(display_labels)),
            format_func=lambda i: display_labels[i],
            key="history_selector",
            label_visibility="collapsed"
        )
        
        # If user selected a history item (not "Current Session")
        if selected_idx > 0 and (selected_idx - 1) < len(st.session_state.session_history):
            selected_session = st.session_state.session_history[selected_idx - 1]
            
            st.caption(f"📅 {selected_session['timestamp']}")
            
            # Show mini preview
            with st.expander("Quick Preview", expanded=True):
                st.write(f"**Mode:** {selected_session['mode']}")
                st.write(f"**Status:** {selected_session['status']}")
                st.write(f"**Query:** {selected_session['prompt'][:80]}...")
            
            # Button to load full results in main area
            if st.button("📂 Load Full Results", use_container_width=True, type="primary"):
                st.session_state.selected_history_data = selected_session['data']
                st.rerun()
        
        # Clear history button at bottom
        st.divider()
        if st.button("🗑️ Clear All History", use_container_width=True):
            st.session_state.session_history = []
            st.session_state.selected_history_data = None
            st.rerun()

# --- MAIN AREA ---
st.divider()

# Show current config
cfg = st.session_state.config
st.caption(f"Mode: **{cfg['mode']}** | Tone: **{cfg['tone']}** | Length: **{cfg['length']}** | Search: **{'ON' if cfg['enable_search'] else 'OFF'}**")

# Query input
prompt = st.text_area("Enter your query:", height=100, key="query_input")

if st.button("🚀 Launch Council", type="primary", use_container_width=True, disabled=st.session_state.polling_active):
    if prompt:
        # Clear any selected history when starting new
        st.session_state.selected_history_data = None
        st.session_state.session_data = None
        st.session_state.last_error = None
        
        with st.spinner("Contacting Architect..."):
            try:
                payload = {
                    "prompt": prompt,
                    "mode": cfg['mode'],
                    "models": cfg['models'],
                    "tone": cfg['tone'],
                    "length": cfg['length'],
                    "enable_search": cfg['enable_search'],
                    "decomposition_depth": cfg['decomposition_depth']
                }
                
                resp = httpx.post(f"{BACKEND_URL}/api/council", json=payload, timeout=60.0)
                
                if resp.status_code == 200:
                    data = resp.json()
                    st.session_state.session_id = data['session_id']
                    st.session_state.polling_active = True
                    st.success(f"Started: {str(data['session_id'])[:16]}...")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.session_state.last_error = f"API Error {resp.status_code}: {resp.text}"
                    st.error(st.session_state.last_error)
            except Exception as e:
                st.session_state.last_error = str(e)
                st.error(f"Connection error: {e}")

# ==========================================
# DISPLAY AREA (Current or Historical)
# ==========================================
st.divider()

# Priority 1: Show selected history item if exists
if st.session_state.selected_history_data:
    display_session_data(st.session_state.selected_history_data, "📚 Historical Session Results")
    
    if st.button("← Back to Current", key="back_from_history"):
        st.session_state.selected_history_data = None
        st.rerun()

# Priority 2: Show active polling or current session data
elif st.session_state.session_id:
    # Polling loop for active session
    if st.session_state.polling_active:
        session_id = st.session_state.session_id
        
        col1, col2 = st.columns([3, 1])
        with col1:
            st.subheader("⏳ Processing...")
        with col2:
            if st.button("🛑 Stop Polling"):
                st.session_state.polling_active = False
                st.rerun()
        
        progress_bar = st.progress(0)
        
        try:
            resp = httpx.get(f"{BACKEND_URL}/api/council/{session_id}", timeout=10.0)
            
            if resp.status_code == 200:
                data = resp.json()
                status = data.get('status', 'UNKNOWN')
                agents = data.get('agents', [])
                
                # Update progress
                if agents:
                    completed = sum(1 for a in agents if a['status'] == 'COMPLETED')
                    failed = sum(1 for a in agents if a['status'] == 'FAILED')
                    progress = (completed + failed) / len(agents) if agents else 0
                    progress_bar.progress(min(progress, 0.99))
                    
                    # Show agents
                    cols = st.columns(min(len(agents), 4))
                    for idx, agent in enumerate(agents):
                        with cols[idx % len(cols)]:
                            emoji = {"COMPLETED": "✅", "SEARCHING": "🔍", "ANALYZING": "🧠", 
                                    "FAILED": "❌", "PENDING": "⏳"}.get(agent['status'], "⚪")
                            st.metric(f"{emoji} {agent['name'][:15]}", agent['status'])
                
                # Handle completion
                if status in ["COMPLETED", "FAILED"]:
                    st.session_state.session_data = data
                    st.session_state.polling_active = False
                    add_to_history(data)  # Add to history!
                    st.rerun()
                else:
                    time.sleep(2)
                    st.rerun()
            else:
                st.error(f"Failed to fetch: {resp.status_code}")
        except Exception as e:
            st.error(f"Error: {e}")
            time.sleep(2)
            st.rerun()
    
    # Show completed current session
    elif st.session_state.session_data:
        display_session_data(st.session_state.session_data, "🎉 Current Session Results")
        
        # Add to history if not already there
        add_to_history(st.session_state.session_data)

# Priority 3: Empty state
else:
    st.info("Enter a query above or select a session from history to view results")

st.divider()
st.caption("Nexus Council v2.0 • Multi-Modal AI Research Platform")
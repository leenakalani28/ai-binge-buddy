import streamlit as st

def initialize():
    defaults = {"stage": "welcome", "users": [], "region": "GB", "seen": set(), "batch": [], "pool": [],
        "roast": "", "analysis": None, "notice": "", "winner": None, "celebration": "", "request_number": 0,
        "discovery_page": 1, "wheel_result": None, "wheel_event": None, "signature": None}
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

def reset():
    for key in list(st.session_state):
        del st.session_state[key]
    initialize()

def goto(stage):
    st.session_state.stage = stage
    st.rerun()

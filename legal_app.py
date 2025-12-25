import streamlit as st
from supabase import create_client
import time

# --- SETUP ---
st.set_page_config(page_title="Compliance Tracker", layout="centered")

@st.cache_resource
def init_connection():
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except:
        return None

supabase = init_connection()

if not supabase:
    st.error("🚨 Connection failed. Did you update Streamlit Secrets with the NEW keys?")
    st.stop()

# --- CONSTANTS ---
# Paste your Tenant ID from Step 3 here!
DEFAULT_TENANT_ID = "a8446e55-1a8c-477f-aed9-51998ab1e6cb" 

# --- AUTH LOGIC ---
if "user" not in st.session_state:
    st.session_state["user"] = None

def login(email, password):
    try:
        response = supabase.auth.sign_in_with_password({"email": email, "password": password})
        st.session_state["user"] = response.user
        st.success("✅ Logged in!")
        st.rerun()
    except Exception as e:
        st.error(f"Error: {e}")

def signup(email, password):
    try:
        response = supabase.auth.sign_up({"email": email, "password": password})
        st.session_state["user"] = response.user
        st.success("✅ Signed up! You are now logged in.")
        st.rerun()
    except Exception as e:
        st.error(f"Error: {e}")

def logout():
    supabase.auth.sign_out()
    st.session_state["user"] = None
    st.rerun()

# --- THE APP ---
if st.session_state["user"] is None:
    # 🔒 LOGIN SCREEN
    st.title("🚧 Site Compliance Login")
    tab1, tab2 = st.tabs(["Log In", "Sign Up"])
    
    with tab1:
        email = st.text_input("Email", key="l_email")
        password = st.text_input("Password", type="password", key="l_pass")
        if st.button("Log In"):
            login(email, password)
            
    with tab2:
        st.caption("Create a new account for testing")
        new_email = st.text_input("Email", key="s_email")
        new_pass = st.text_input("Password", type="password", key="s_pass")
        if st.button("Sign Up"):
            signup(new_email, new_pass)

else:
    # 🏗️ MAIN DASHBOARD (Restricted Area)
    st.sidebar.button("Log Out", on_click=logout)
    
    st.title("🏗️ Compliance HQ")
    st.write(f"Logged in as: **{st.session_state['user'].email}**")
    st.info(f"Connected to Company ID: `{DEFAULT_TENANT_ID}`")
    
    st.divider()
    st.header("Coming Next: The Importer")
    st.caption("We are ready to add the 'Upload Excel' feature here.")

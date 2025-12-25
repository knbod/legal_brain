import streamlit as st
from supabase import create_client, Client

# --- 1. SETUP & CONNECTION ---
st.set_page_config(page_title="Legal Brain Pro", layout="centered")
st.title("⚖️ Digital Legal Brain (Cloud DB)")

# Initialize connection to Supabase
# We get the secrets from the Streamlit "Safe"
@st.cache_resource
def init_connection():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

try:
    supabase = init_connection()
except Exception as e:
    st.error("🚨 Connection failed! Did you save your Secrets in Streamlit?")
    st.stop()

# --- 2. FETCH DATA FROM VAULT ---
# Instead of reading CSV, we ask Supabase for the data
def get_data():
    # We fetch all rows from the 'legal_cases' table
    response = supabase.table("legal_cases").select("*").execute()
    return response.data

# Load data into session state
if "legal_db" not in st.session_state:
    try:
        st.session_state["legal_db"] = get_data()
    except Exception as e:
        st.warning(f"Could not fetch data. Error: {e}")
        st.session_state["legal_db"] = []

# --- 3. SIDEBAR ---
st.sidebar.header("🗄️ Data Management")
if st.sidebar.button("🔄 Refresh Data"):
    st.session_state["legal_db"] = get_data()
    st.rerun()

# --- 4. TABS ---
tab1, tab2 = st.tabs(["📊 Dashboard", "📝 Add New Case"])

# TAB 1: DASHBOARD
with tab1:
    data = st.session_state["legal_db"]
    if data and len(data) > 0:
        st.write(f"**Total Cases in Vault:** {len(data)}")
        for case in data:
            # We use 'subject' and 'difficulty' from your database columns
            with st.expander(f"{case.get('subject', 'No Subject')} ({case.get('difficulty', 'Unknown')})"):
                st.markdown(f"**Q:** {case.get('question', 'No Question')}")
                st.markdown(f"**A:** {case.get('answer', 'No Answer')}")
    else:
        st.info("The Vault is empty! Go to 'Add New Case' to create your first entry.")

# TAB 2: ADD CASE (The Bank Deposit)
with tab2:
    st.header("Add New Entry")
    
    # Form Inputs
    new_sub = st.selectbox("Subject", ["Wills", "Property", "Contracts", "Family Law"])
    new_diff = st.select_slider("Difficulty", options=["Easy", "Medium", "Hard"])
    new_q = st.text_area("Question")
    new_a = st.text_area("Answer")
    
    if st.button("💾 Save to Cloud Vault"):
        if new_q and new_a:
            # 1. Create the package
            new_entry = {
                "subject": new_sub,
                "difficulty": new_diff,
                "question": new_q,
                "answer": new_a
            }
            
            # 2. Send the armored truck to Supabase
            try:
                supabase.table("legal_cases").insert(new_entry).execute()
                
                # 3. Update local view
                st.success("✅ Saved to Cloud Database!")
                # Refresh data immediately so we see it
                st.session_state["legal_db"] = get_data() 
                st.rerun()
            except Exception as e:
                st.error(f"Bank Error: {e}")
        else:
            st.warning("Please fill in all fields.")

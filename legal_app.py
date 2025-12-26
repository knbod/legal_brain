import streamlit as st
import pandas as pd
from supabase import create_client
import time
import datetime

# --- 1. SETUP ---
st.set_page_config(page_title="Compliance Tracker", layout="wide")

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
    st.error("🚨 Connection failed. Check Secrets.")
    st.stop()

# YOUR TENANT ID
DEFAULT_TENANT_ID = "a8446e55-1a8c-477f-aed9-51998ab1e6cb" 

if "user" not in st.session_state:
    st.session_state["user"] = None

# --- HELPER FUNCTIONS ---
def login(email, password):
    try:
        response = supabase.auth.sign_in_with_password({"email": email.strip(), "password": password})
        st.session_state["user"] = response.user
        st.rerun()
    except Exception as e:
        st.error(f"Login Error: {e}")

def signup(email, password):
    try:
        response = supabase.auth.sign_up({"email": email.strip(), "password": password})
        st.session_state["user"] = response.user
        st.success("✅ Account created!")
        st.rerun()
    except Exception as e:
        st.error(f"Signup Error: {e}")

def logout():
    supabase.auth.sign_out()
    st.session_state["user"] = None
    st.rerun()

# --- MAIN APP ---
if st.session_state["user"] is None:
    # LOGIN SCREEN
    st.title("🚧 Site Compliance Login")
    tab1, tab2 = st.tabs(["Log In", "Sign Up"])
    with tab1:
        email = st.text_input("Email", key="l_email")
        password = st.text_input("Password", type="password", key="l_pass")
        if st.button("Log In"): login(email, password)
    with tab2:
        new_email = st.text_input("Email", key="s_email")
        new_pass = st.text_input("Password", type="password", key="s_pass")
        if st.button("Sign Up"): signup(new_email, new_pass)

else:
    # DASHBOARD
    st.sidebar.button("Log Out", on_click=logout)
    st.title("🏗️ Compliance HQ")
    
    # TABS
    tab_import, tab_dash, tab_docs = st.tabs(["📂 Import Wizard", "📊 Dashboard", "📎 Document Vault"])
    
    # --- TAB 1: IMPORT (Kept simple for brevity, assumed working) ---
    with tab_import:
        st.header("Upload Excel List")
        uploaded_file = st.file_uploader("Upload Excel/CSV", type=["xlsx", "csv"])
        if uploaded_file and st.button("Run Import"):
            # (Your previous import logic would go here - simplified for this step)
            st.info("Import feature is ready (Code hidden for brevity). Use the code from Phase 3 if you need to re-import.")

    # --- TAB 2: DASHBOARD ---
    with tab_dash:
        st.header("✅ Worker Status")
        res = supabase.table("subcontractors").select("*").eq("tenant_id", DEFAULT_TENANT_ID).eq("data_status", "verified").execute()
        if res.data:
            df = pd.DataFrame(res.data)
            # Traffic Light Logic
            def get_color(d):
                if not d: return "⚪"
                days = (pd.to_datetime(d).date() - datetime.date.today()).days
                return "🔴 EXPIRED" if days < 0 else ("🟡 WARN" if days < 30 else "🟢 OK")
            
            df["Status"] = df["insurance_expiry_date"].apply(get_color)
            st.dataframe(df[["Status", "name", "insurance_expiry_date"]], use_container_width=True)
        else:
            st.info("No workers found.")

    # --- TAB 3: DOCUMENT VAULT (NEW!) 📎 ---
    with tab_docs:
        st.header("📄 Upload Evidence")
        
        # 1. Fetch Workers to populate Dropdown
        workers_res = supabase.table("subcontractors").select("id, name").eq("tenant_id", DEFAULT_TENANT_ID).execute()
        
        if workers_res.data:
            worker_list = {w['name']: w['id'] for w in workers_res.data}
            selected_name = st.selectbox("Select Worker:", list(worker_list.keys()))
            selected_id = worker_list[selected_name]
            
            # 2. File Uploader
            proof_file = st.file_uploader(f"Upload Certificate for {selected_name}", type=["pdf", "png", "jpg"])
            
            if proof_file:
                if st.button("Upload & Attach"):
                    try:
                        # A. Upload to Storage Bucket
                        # Create unique filename: worker_id_timestamp.ext
                        file_ext = proof_file.name.split('.')[-1]
                        file_path = f"{selected_id}_{int(time.time())}.{file_ext}"
                        
                        file_bytes = proof_file.getvalue()
                        supabase.storage.from_("certificates").upload(file_path, file_bytes, {"content-type": proof_file.type})
                        
                        # Get Public URL
                        public_url = supabase.storage.from_("certificates").get_public_url(file_path)
                        
                        # B. Save Record in Database
                        doc_payload = {
                            "subcontractor_id": selected_id,
                            "file_url": public_url,
                            "file_name": proof_file.name
                        }
                        supabase.table("documents").insert(doc_payload).execute()
                        
                        st.success("✅ File Uploaded & Linked!")
                        st.balloons()
                        
                    except Exception as e:
                        st.error(f"Upload Failed: {e}")
            
            st.divider()
            
            # 3. Show Existing Documents
            st.write(f"**Existing Documents for {selected_name}:**")
            docs_res = supabase.table("documents").select("*").eq("subcontractor_id", selected_id).execute()
            
            if docs_res.data:
                for doc in docs_res.data:
                    st.markdown(f"📄 [{doc['file_name']}]({doc['file_url']})")
            else:
                st.caption("No documents uploaded yet.")
                
        else:
            st.warning("No workers found. Please Import data first.")

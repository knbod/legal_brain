import streamlit as st
import pandas as pd
from supabase import create_client
import time
import datetime
import google.generativeai as genai
import io

# --- 1. SETUP & CONFIG ---
st.set_page_config(page_title="Compliance Tracker", layout="wide")

@st.cache_resource
def init_connections():
    # Connect to Supabase
    try:
        sup_url = st.secrets["supabase"]["url"]
        sup_key = st.secrets["supabase"]["key"]
        client = create_client(sup_url, sup_key)
    except:
        client = None
        
    # Connect to Google AI
    try:
        genai.configure(api_key=st.secrets["google"]["api_key"])
    except:
        pass
        
    return client

supabase = init_connections()

# STOP IF SETUP IS WRONG
if not supabase:
    st.error("🚨 System Error: Secrets not found. Please check Step 3.")
    st.stop()

# GET TENANT ID FROM SECRETS (No more manual pasting!)
try:
    DEFAULT_TENANT_ID = st.secrets["general"]["tenant_id"]
except:
    st.error("🚨 Missing 'tenant_id' in Secrets!")
    st.stop()

if "user" not in st.session_state:
    st.session_state["user"] = None

# --- 2. AI INTELLIGENCE ---
def ask_ai_to_read_date(file_bytes, mime_type):
    """Sends image to Gemini and asks for the expiry date."""
    try:
        # 1. Setup the Model (We try the specific version first, then fallback)
        model_name = "gemini-1.5-flash-latest" 
        
        try:
            model = genai.GenerativeModel(model_name)
        except:
            # If Flash fails, use the standard Pro model (Reliable Backup)
            model = genai.GenerativeModel("gemini-pro-vision") 
        
        # 2. Create the Prompt
        prompt = "Look at this insurance certificate. Find the 'Expiration Date' or 'Valid Until' date. Return ONLY the date in YYYY-MM-DD format. If you cannot find it, return 'NOT_FOUND'."
        
        # 3. Prepare Image & Send
        # Note: 'gemini-pro-vision' handles images differently, so we ensure standard format
        image_part = {"mime_type": mime_type, "data": file_bytes}
        
        response = model.generate_content([prompt, image_part])
        return response.text.strip()
        
    except Exception as e:
        return f"AI Error: {str(e)}"

# --- 3. HELPER FUNCTIONS ---
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

# --- 4. MAIN APPLICATION ---

if st.session_state["user"] is None:
    # === LOGIN SCREEN ===
    st.title("🚧 Site Compliance Login")
    tab1, tab2 = st.tabs(["Log In", "Sign Up"])
    with tab1:
        email = st.text_input("Email", key="l_email")
        password = st.text_input("Password", type="password", key="l_pass")
        if st.button("Log In"): login(email, password)
    with tab2:
        st.caption("Create a new account")
        new_email = st.text_input("Email", key="s_email")
        new_pass = st.text_input("Password", type="password", key="s_pass")
        if st.button("Sign Up"): signup(new_email, new_pass)

else:
    # === DASHBOARD ===
    st.sidebar.write(f"👤 {st.session_state['user'].email}")
    st.sidebar.button("Log Out", on_click=logout)
    st.title("🏗️ Compliance HQ")
    
    # NAVIGATION TABS
    tab_import, tab_dash, tab_docs = st.tabs(["📂 Import Wizard", "📊 Dashboard", "🤖 AI Auditor"])
    
    # --- TAB 1: IMPORT WIZARD (Simplified) ---
    with tab_import:
        st.header("Upload Workers List")
        uploaded_file = st.file_uploader("Upload Excel/CSV", type=["xlsx", "csv"])
        
        if uploaded_file:
            if uploaded_file.name.endswith(".csv"): df = pd.read_csv(uploaded_file)
            else: df = pd.read_excel(uploaded_file)
            
            st.write("Preview:", df.head(3))
            col_name = st.selectbox("Select Name Column", df.columns)
            
            if st.button("Import Workers"):
                count = 0
                for _, row in df.iterrows():
                    name = str(row[col_name])
                    if name and name != "nan":
                        supabase.table("subcontractors").insert({
                            "tenant_id": DEFAULT_TENANT_ID,
                            "name": name,
                            "data_status": "incomplete" # Default to red light
                        }).execute()
                        count += 1
                st.success(f"✅ Imported {count} workers!")
                time.sleep(1)
                st.rerun()

    # --- TAB 2: DASHBOARD (Traffic Lights) ---
    with tab_dash:
        st.header("✅ Compliance Status")
        # Get all workers
        res = supabase.table("subcontractors").select("*").eq("tenant_id", DEFAULT_TENANT_ID).execute()
        
        if res.data:
            df_main = pd.DataFrame(res.data)
            
            # Traffic Light Logic
            def get_status(date_str):
                if not date_str: return "🔴 MISSING"
                try:
                    d = pd.to_datetime(date_str).date()
                    days = (d - datetime.date.today()).days
                    if days < 0: return "🔴 EXPIRED"
                    if days < 30: return "🟡 EXPIRING SOON"
                    return "🟢 COMPLIANT"
                except: return "🔴 ERROR"

            df_main["Status"] = df_main["insurance_expiry_date"].apply(get_status)
            
            # Show the table
            st.dataframe(
                df_main[["Status", "name", "insurance_expiry_date", "data_status"]], 
                use_container_width=True
            )
        else:
            st.info("No workers found. Go to Import Wizard.")

    # --- TAB 3: AI AUDITOR (Upload + Scan) ---
    with tab_docs:
        st.header("📄 AI Evidence Processor")
        st.caption("Upload a certificate. The AI will read the date and update the status.")
        
        # 1. Select Worker
        workers_res = supabase.table("subcontractors").select("id, name").eq("tenant_id", DEFAULT_TENANT_ID).execute()
        
        if workers_res.data:
            worker_dict = {w['name']: w['id'] for w in workers_res.data}
            selected_worker_name = st.selectbox("Select Worker to Audit:", list(worker_dict.keys()))
            selected_worker_id = worker_dict[selected_worker_name]
            
            # 2. Upload File
            proof_file = st.file_uploader(f"Upload Insurance for {selected_worker_name}", type=["png", "jpg", "jpeg", "pdf"])
            
            if proof_file and st.button("Upload & Scan with AI ✨"):
                with st.spinner("Uploading to Vault..."):
                    # A. Upload to Supabase Storage
                    file_ext = proof_file.name.split('.')[-1]
                    file_path = f"{selected_worker_id}_{int(time.time())}.{file_ext}"
                    file_bytes = proof_file.getvalue()
                    
                    try:
                        supabase.storage.from_("certificates").upload(file_path, file_bytes, {"content-type": proof_file.type})
                        public_url = supabase.storage.from_("certificates").get_public_url(file_path)
                        
                        # Save Link to DB
                        supabase.table("documents").insert({
                            "subcontractor_id": selected_worker_id,
                            "file_url": public_url,
                            "file_name": proof_file.name
                        }).execute()
                        st.success("✅ File Saved!")
                        
                    except Exception as e:
                        st.error(f"Upload Failed: {e}")
                        st.stop()
                
                # B. AI Processing
                if file_ext in ['png', 'jpg', 'jpeg']:
                    with st.spinner("🤖 AI is reading the document..."):
                        ai_date = ask_ai_to_read_date(file_bytes, proof_file.type)
                        
                        st.write(f"**AI Found Date:** `{ai_date}`")
                        
                        # Validate Date Format
                        if "20" in ai_date and "-" in ai_date: # Simple check for YYYY-MM-DD
                            # C. Update Database
                            supabase.table("subcontractors").update({
                                "insurance_expiry_date": ai_date,
                                "data_status": "verified"
                            }).eq("id", selected_worker_id).execute()
                            
                            st.balloons()
                            st.success(f"✅ Updated {selected_worker_name} to Green Light!")
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.warning("AI couldn't find a clear date. Please check the image manually.")
                else:
                    st.info("AI scanning currently supports Images (PNG/JPG). PDF support coming next version.")
                    
        else:
            st.warning("No workers found. Please import first.")


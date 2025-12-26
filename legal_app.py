import streamlit as st
import pandas as pd
from supabase import create_client
import time
import datetime
import google.generativeai as genai

# --- 1. PROFESSIONAL UI CONFIGURATION ---
st.set_page_config(
    page_title="Compliance HQ", 
    page_icon="🛡️", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS HACKS: HIDE GITHUB & STREAMLIT BRANDING ---
hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            .stDeployButton {display: none;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# --- 2. CONNECTIONS & SETUP ---
@st.cache_resource
def init_connections():
    try:
        sup_url = st.secrets["supabase"]["url"]
        sup_key = st.secrets["supabase"]["key"]
        client = create_client(sup_url, sup_key)
    except:
        client = None
        
    try:
        genai.configure(api_key=st.secrets["google"]["api_key"])
    except:
        pass
    return client

supabase = init_connections()

if not supabase:
    st.error("🚨 Critical System Error: Database connection failed.")
    st.stop()

# TENANT ID HANDLING
try:
    DEFAULT_TENANT_ID = st.secrets["general"]["tenant_id"]
except:
    DEFAULT_TENANT_ID = "a8446e55-1a8c-477f-aed9-51998ab1e6cb"

if "user" not in st.session_state:
    st.session_state["user"] = None

# --- 3. INTELLIGENT FUNCTIONS ---

def ask_ai_to_read_date(file_bytes, mime_type):
    """AI Vision function with fallback models."""
    candidate_models = ["gemini-2.0-flash", "gemini-1.5-flash-latest", "gemini-pro-vision"]
    
    for model_name in candidate_models:
        try:
            model = genai.GenerativeModel(model_name)
            # Strict prompt for clean data
            prompt = "Analyze this insurance certificate. Extract the Expiration Date. Return ONLY the date in YYYY-MM-DD format. If ambiguous, return 'NOT_FOUND'."
            image_part = {"mime_type": mime_type, "data": file_bytes}
            
            response = model.generate_content([prompt, image_part])
            clean_text = response.text.strip().replace("```", "").replace("json", "")
            return clean_text
        except:
            continue
    return "NOT_FOUND"

def login(email, password):
    try:
        response = supabase.auth.sign_in_with_password({"email": email.strip(), "password": password})
        st.session_state["user"] = response.user
        st.rerun()
    except Exception as e:
        st.error(f"Access Denied: Please check your credentials.")

def signup(email, password):
    try:
        response = supabase.auth.sign_up({"email": email.strip(), "password": password})
        st.session_state["user"] = response.user
        st.success("✅ Account created! You may log in now.")
        st.rerun()
    except Exception as e:
        st.error(f"Registration Failed: {e}")

def logout():
    supabase.auth.sign_out()
    st.session_state["user"] = None
    st.rerun()

# --- 4. THE APPLICATION INTERFACE ---

if st.session_state["user"] is None:
    # === PROFESSIONAL LOGIN SCREEN ===
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.title("🛡️ Compliance HQ")
        st.markdown("#### Secure Workforce Management")
        
        tab1, tab2 = st.tabs(["🔒 Secure Login", "📝 New Registration"])
        
        with tab1:
            email = st.text_input("Business Email", key="l_email")
            password = st.text_input("Password", type="password", key="l_pass")
            if st.button("Access Dashboard", type="primary"): 
                login(email, password)
                
        with tab2:
            new_email = st.text_input("Business Email", key="s_email")
            new_pass = st.text_input("Set Password", type="password", key="s_pass")
            if st.button("Create Account"): 
                signup(new_email, new_pass)

else:
    # === MAIN APPLICATION ===
    
    # Sidebar Navigation
    with st.sidebar:
        st.title("🛡️ Compliance HQ")
        st.caption(f"Logged in as: {st.session_state['user'].email}")
        st.markdown("---")
        if st.button("🚪 Sign Out", use_container_width=True):
            logout()
    
    # Main Tabs with Professional Names
    tab_dash, tab_import, tab_audit = st.tabs(["📊 Executive Dashboard", "📂 Workforce Data", "🤖 Audit Center"])
    
    # --- TAB 1: EXECUTIVE DASHBOARD ---
    with tab_dash:
        st.subheader("Compliance Overview")
        
        # Fetch Data
        res = supabase.table("subcontractors").select("*").eq("tenant_id", DEFAULT_TENANT_ID).execute()
        
        if res.data:
            df_main = pd.DataFrame(res.data)
            
            # Smart Status Logic
            def get_status(date_str):
                if not date_str or date_str == "None": return "🔴 Missing Docs"
                try:
                    d = pd.to_datetime(date_str).date()
                    days = (d - datetime.date.today()).days
                    if days < 0: return "🔴 EXPIRED"
                    if days < 30: return "🟡 Renewal Due"
                    return "🟢 Compliant"
                except: return "🔴 Error"

            df_main["Status"] = df_main["insurance_expiry_date"].apply(get_status)
            
            # Metrics Row
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Workforce", len(df_main))
            m2.metric("Compliant", len(df_main[df_main["Status"] == "🟢 Compliant"]))
            m3.metric("At Risk", len(df_main[df_main["Status"] != "🟢 Compliant"]), delta_color="inverse")
            
            st.divider()
            
            # Clean Table
            st.dataframe(
                df_main[["Status", "name", "insurance_expiry_date", "trade"]], 
                use_container_width=True,
                column_config={
                    "name": "Subcontractor Name",
                    "insurance_expiry_date": "Insurance Expiry",
                    "trade": "Trade / Role"
                }
            )
        else:
            st.info("System is empty. Please navigate to 'Workforce Data' to begin.")

    # --- TAB 2: WORKFORCE DATA (Import) ---
    with tab_import:
        st.subheader("Bulk Import Subcontractors")
        st.markdown("Upload your current roster (`.xlsx` or `.csv`). We will map the columns automatically.")
        
        uploaded_file = st.file_uploader("Drop file here", type=["xlsx", "csv"])
        
        if uploaded_file:
            if uploaded_file.name.endswith(".csv"): df = pd.read_csv(uploaded_file)
            else: df = pd.read_excel(uploaded_file)
            
            st.write("### Data Mapping")
            cols = df.columns.tolist()
            
            # 2. BUG FIX: Column Selection Logic
            col1, col2 = st.columns(2)
            with col1:
                name_col = st.selectbox("Select Name Column", cols, index=0)
            with col2:
                # Try to auto-select a different column for date
                default_date_idx = 1 if len(cols) > 1 else 0
                date_col = st.selectbox("Select Expiry Date Column", cols, index=default_date_idx)
            
            # 3. VALIDATION: Prevent Same Column Selection
            if name_col == date_col:
                st.error("⚠️ Error: You cannot use the same column for both 'Name' and 'Expiry Date'. Please fix selection.")
            else:
                if st.button("Process Import", type="primary"):
                    count = 0
                    progress_bar = st.progress(0)
                    
                    for i, row in df.iterrows():
                        # Extract and Clean Data
                        raw_name = str(row[name_col]).strip()
                        raw_date = str(row[date_col]).strip()
                        
                        # Basic Name Validation
                        if not raw_name or raw_name.lower() in ["nan", "none", ""]:
                            continue
                            
                        # Try to parse date immediately if possible
                        db_date = None
                        try:
                            parsed = pd.to_datetime(raw_date, errors='coerce')
                            if not pd.isna(parsed):
                                db_date = parsed.strftime('%Y-%m-%d')
                        except:
                            pass

                        # Insert to DB
                        supabase.table("subcontractors").insert({
                            "tenant_id": DEFAULT_TENANT_ID,
                            "name": raw_name,
                            "insurance_expiry_date": db_date,
                            "data_status": "verified" if db_date else "incomplete"
                        }).execute()
                        
                        count += 1
                        progress_bar.progress((i + 1) / len(df))
                    
                    st.success(f"Successfully onboarded {count} subcontractors.")
                    time.sleep(1)
                    st.rerun()

    # --- TAB 3: AUDIT CENTER (AI) ---
    with tab_audit:
        st.subheader("AI Verification Center")
        
        # 1. Selector
        workers_res = supabase.table("subcontractors").select("id, name, data_status").eq("tenant_id", DEFAULT_TENANT_ID).execute()
        
        if workers_res.data:
            # Filter to show "Incomplete" workers first
            workers = workers_res.data
            workers_sorted = sorted(workers, key=lambda x: x['data_status'] == 'verified') # Unverified first
            
            worker_map = {f"{w['name']} ({'✅' if w['data_status']=='verified' else '🔴'})": w['id'] for w in workers_sorted}
            
            selected_label = st.selectbox("Select Subcontractor for Audit:", list(worker_map.keys()))
            selected_id = worker_map[selected_label]
            
            # 2. Upload
            proof_file = st.file_uploader("Upload Insurance Certificate (Image)", type=["png", "jpg", "jpeg"])
            
            if proof_file and st.button("Run AI Audit ✨", type="primary"):
                
                with st.status("Processing Evidence...", expanded=True) as status:
                    # A. Upload
                    st.write("📤 Securely uploading to Audit Vault...")
                    file_ext = proof_file.name.split('.')[-1]
                    file_path = f"{selected_id}_{int(time.time())}.{file_ext}"
                    file_bytes = proof_file.getvalue()
                    
                    try:
                        supabase.storage.from_("certificates").upload(file_path, file_bytes, {"content-type": proof_file.type})
                        public_url = supabase.storage.from_("certificates").get_public_url(file_path)
                        
                        # Link
                        supabase.table("documents").insert({
                            "subcontractor_id": selected_id,
                            "file_url": public_url,
                            "file_name": proof_file.name
                        }).execute()
                        
                    except Exception as e:
                        st.error("Upload Error (Check connection).")
                        st.stop()
                    
                    # B. AI Analysis
                    st.write("🤖 AI Analyst is reading document structure...")
                    ai_date = ask_ai_to_read_date(file_bytes, proof_file.type)
                    
                    # C. Validation Logic
                    if ai_date and len(ai_date) == 10 and ai_date[4] == '-':
                        st.write("✅ Date validated successfully.")
                        supabase.table("subcontractors").update({
                            "insurance_expiry_date": ai_date,
                            "data_status": "verified"
                        }).eq("id", selected_id).execute()
                        
                        status.update(label="Audit Complete!", state="complete", expanded=False)
                        st.balloons()
                        st.success(f"Subcontractor verified! Expiry set to: {ai_date}")
                        time.sleep(2)
                        st.rerun()
                    else:
                        status.update(label="AI Validation Failed", state="error")
                        st.error(f"AI could not confirm the date. It saw: '{ai_date}'. Please verify manually.")
                        
        else:
            st.warning("No workforce data found. Please complete import first.")

import streamlit as st
import pandas as pd
from supabase import create_client
import time
import datetime
import google.generativeai as genai

# --- 1. CONFIGURATION & STYLING ---
st.set_page_config(
    page_title="Compliance HQ", 
    page_icon="🛡️", 
    layout="wide"
)

# Custom CSS to hide "developer" look and style tabs
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    .stDeployButton {display: none;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    /* Custom Tab Styling */
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; background-color: #f0f2f6; border-radius: 5px; color: #31333F; }
    .stTabs [aria-selected="true"] { background-color: #FFFFFF; border: 1px solid #dcdcdc; border-bottom: none; color: #ff4b4b; }
    </style>
""", unsafe_allow_html=True)

# --- 2. SETUP ---
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

try:
    DEFAULT_TENANT_ID = st.secrets["general"]["tenant_id"]
except:
    DEFAULT_TENANT_ID = "a8446e55-1a8c-477f-aed9-51998ab1e6cb"

if "user" not in st.session_state:
    st.session_state["user"] = None

# --- 3. CORE FUNCTIONS ---

def get_traffic_light_status(date_str, data_status):
    """Categorizes a worker based on your 4 rules."""
    # 1. Check for Missing Data first
    if data_status == "incomplete" or not date_str or date_str == "None":
        return "MISSING_DATA"
    
    try:
        # 2. Check Date Logic
        d = pd.to_datetime(date_str).date()
        days_left = (d - datetime.date.today()).days
        
        if days_left < 0:
            return "EXPIRED" # Red
        elif days_left < 60:
            return "WARNING" # Yellow (Less than 2 months)
        else:
            return "SAFE" # Green (More than 2 months)
            
    except:
        return "MISSING_DATA"

def ask_ai_to_read_date(file_bytes, mime_type):
    """AI Vision function."""
    candidate_models = ["gemini-2.0-flash", "gemini-1.5-flash-latest", "gemini-pro-vision"]
    for model_name in candidate_models:
        try:
            model = genai.GenerativeModel(model_name)
            prompt = "Extract the Expiration Date from this certificate. Return ONLY the date in YYYY-MM-DD format. If not found, return 'NOT_FOUND'."
            image_part = {"mime_type": mime_type, "data": file_bytes}
            response = model.generate_content([prompt, image_part])
            return response.text.strip().replace("```", "").replace("json", "")
        except:
            continue
    return "NOT_FOUND"

def login(email, password):
    try:
        response = supabase.auth.sign_in_with_password({"email": email.strip(), "password": password})
        st.session_state["user"] = response.user
        st.rerun()
    except:
        st.error("Invalid credentials.")

def logout():
    supabase.auth.sign_out()
    st.session_state["user"] = None
    st.rerun()

# --- 4. APP INTERFACE ---

if st.session_state["user"] is None:
    # Login Screen
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        st.title("🛡️ Compliance HQ")
        email = st.text_input("Email", key="l_email")
        password = st.text_input("Password", type="password", key="l_pass")
        if st.button("Log In", type="primary", use_container_width=True): 
            login(email, password)

else:
    # Sidebar
    with st.sidebar:
        st.title("🛡️ HQ")
        st.caption(st.session_state['user'].email)
        if st.button("Log Out"): logout()

    # Main Tabs
    tab_dash, tab_roster, tab_import, tab_audit = st.tabs(["📊 Executive Dashboard", "📋 Roster Categories", "📂 Import Data", "🤖 AI Audit"])

    # --- TAB 1: EXECUTIVE DASHBOARD (Metrics Only) ---
    with tab_dash:
        st.subheader("High-Level Overview")
        
        # Fetch All Data
        res = supabase.table("subcontractors").select("*").eq("tenant_id", DEFAULT_TENANT_ID).execute()
        
        if res.data:
            df = pd.DataFrame(res.data)
            
            # Categorize
            df["Category"] = df.apply(lambda row: get_traffic_light_status(row.get("insurance_expiry_date"), row.get("data_status")), axis=1)
            
            # Metrics
            count_total = len(df)
            count_green = len(df[df["Category"] == "SAFE"])
            count_yellow = len(df[df["Category"] == "WARNING"])
            count_red = len(df[df["Category"] == "EXPIRED"])
            count_missing = len(df[df["Category"] == "MISSING_DATA"])

            # Layout: Big Cards
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("🟢 Compliant", count_green, help="Valid > 60 Days")
            c2.metric("🟡 At Risk", count_yellow, help="Expires < 60 Days")
            c3.metric("🔴 Expired", count_red, help="Insurance Invalid")
            c4.metric("⚠️ Action Needed", count_missing, help="Missing Date or Info")
            
            st.divider()
            st.caption(f"Total Database Size: {count_total} Subcontractors")
        else:
            st.info("No data available.")

    # --- TAB 2: ROSTER CATEGORIES (Your 4 Sub-Tabs) ---
    with tab_roster:
        st.subheader("Worker Lists")
        
        # Reuse data from dashboard if possible, or fetch again
        res = supabase.table("subcontractors").select("*").eq("tenant_id", DEFAULT_TENANT_ID).execute()
        
        if res.data:
            df = pd.DataFrame(res.data)
            df["Category"] = df.apply(lambda row: get_traffic_light_status(row.get("insurance_expiry_date"), row.get("data_status")), axis=1)
            
            # 4 Sub-Tabs
            sub_green, sub_yellow, sub_red, sub_missing = st.tabs([
                "🟢 Safe (>2 Mo)", 
                "🟡 Warning (<2 Mo)", 
                "🔴 Expired", 
                "⚠️ Missing Data"
            ])
            
            with sub_green:
                st.dataframe(df[df["Category"] == "SAFE"][["name", "trade", "insurance_expiry_date"]], use_container_width=True)
            
            with sub_yellow:
                st.dataframe(df[df["Category"] == "WARNING"][["name", "trade", "insurance_expiry_date"]], use_container_width=True)
                
            with sub_red:
                st.error("These workers are legally non-compliant. Do not allow on site.")
                st.dataframe(df[df["Category"] == "EXPIRED"][["name", "trade", "insurance_expiry_date"]], use_container_width=True)
                
            with sub_missing:
                st.warning("These workers have missing dates. Please use AI Audit to fix.")
                st.dataframe(df[df["Category"] == "MISSING_DATA"][["name", "trade"]], use_container_width=True)

    # --- TAB 3: IMPORT DATA (With Duplicate Fix) ---
    with tab_import:
        st.subheader("Import New Workers")
        uploaded_file = st.file_uploader("Upload Excel/CSV", type=["xlsx", "csv"])
        
        if uploaded_file:
            if uploaded_file.name.endswith(".csv"): df_imp = pd.read_csv(uploaded_file)
            else: df_imp = pd.read_excel(uploaded_file)
            
            cols = df_imp.columns.tolist()
            c_name = st.selectbox("Name Column", cols)
            c_date = st.selectbox("Date Column", cols, index=1 if len(cols)>1 else 0)
            
            if c_name == c_date:
                st.error("⚠️ Name and Date columns cannot be the same.")
            else:
                if st.button("Run Import"):
                    # 1. Fetch Existing Names to prevent Duplicates
                    existing_res = supabase.table("subcontractors").select("name").eq("tenant_id", DEFAULT_TENANT_ID).execute()
                    existing_names = set([row['name'] for row in existing_res.data]) if existing_res.data else set()
                    
                    added = 0
                    skipped = 0
                    
                    progress = st.progress(0)
                    for i, row in df_imp.iterrows():
                        name = str(row[c_name]).strip()
                        raw_date = str(row[c_date]).strip()
                        
                        if not name or name == "nan": continue
                        
                        # DUPLICATE CHECK
                        if name in existing_names:
                            skipped += 1
                            continue # Skip this row
                        
                        # Date Parsing
                        db_date = None
                        try:
                            parsed = pd.to_datetime(raw_date, errors='coerce')
                            if not pd.isna(parsed): db_date = parsed.strftime('%Y-%m-%d')
                        except: pass

                        supabase.table("subcontractors").insert({
                            "tenant_id": DEFAULT_TENANT_ID,
                            "name": name,
                            "insurance_expiry_date": db_date,
                            "data_status": "verified" if db_date else "incomplete"
                        }).execute()
                        added += 1
                        progress.progress((i+1)/len(df_imp))
                        
                    st.success(f"✅ Added {added} new workers. (Skipped {skipped} duplicates).")
                    time.sleep(1)
                    st.rerun()

    # --- TAB 4: AI AUDIT ---
    with tab_audit:
        st.subheader("Fix Missing Data with AI")
        
        # Only fetch MISSING or WARNING rows usually, but let's fetch all for flexibility
        res = supabase.table("subcontractors").select("id, name, data_status").eq("tenant_id", DEFAULT_TENANT_ID).execute()
        
        if res.data:
            # Sort: Show "Incomplete" at the top
            workers = sorted(res.data, key=lambda x: x['data_status'] == 'verified')
            w_map = {f"{w['name']}": w['id'] for w in workers}
            
            selected = st.selectbox("Select Worker:", list(w_map.keys()))
            sel_id = w_map[selected]
            
            up_file = st.file_uploader("Upload Cert", type=["png", "jpg", "jpeg"])
            
            if up_file and st.button("Auto-Extract Date"):
                with st.spinner("Analyzing..."):
                    # Upload
                    path = f"{sel_id}_{int(time.time())}.{up_file.name.split('.')[-1]}"
                    supabase.storage.from_("certificates").upload(path, up_file.getvalue(), {"content-type": up_file.type})
                    url = supabase.storage.from_("certificates").get_public_url(path)
                    
                    # Link
                    supabase.table("documents").insert({"subcontractor_id": sel_id, "file_url": url, "file_name": up_file.name}).execute()
                    
                    # AI
                    date_found = ask_ai_to_read_date(up_file.getvalue(), up_file.type)
                    
                    if len(date_found) == 10 and date_found[4] == '-':
                        supabase.table("subcontractors").update({
                            "insurance_expiry_date": date_found,
                            "data_status": "verified"
                        }).eq("id", sel_id).execute()
                        st.balloons()
                        st.success(f"✅ Fixed! Date set to {date_found}")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"AI Failed: Saw '{date_found}'")

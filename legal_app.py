import streamlit as st
import pandas as pd
from supabase import create_client
import time
import datetime
import google.generativeai as genai

# --- 1. CONFIGURATION & LIGHT THEME ---
st.set_page_config(
    page_title="Compliance HQ", 
    page_icon="🛡️", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# 🌊 CLEAN OCEAN CSS (Light Mode)
clean_ocean_css = """
    <style>
    /* 1. HIDE JUNK (Streamlit Branding) */
    #MainMenu {visibility: hidden;}
    .stDeployButton {display: none;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    [data-testid="stToolbar"] {visibility: hidden !important;} 
    
    /* 2. MAIN BACKGROUND - CLEAN WHITE */
    .stApp {
        background-color: #FFFFFF; /* Pure White */
        color: #333333; /* Dark Grey Text (High Contrast) */
    }
    
    /* 3. SIDEBAR - LIGHT GREY */
    [data-testid="stSidebar"] {
        background-color: #F8F9FA; /* Very Light Grey */
        border-right: 1px solid #E0E0E0;
    }
    
    /* 4. TABS - OCEAN THEME */
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        background-color: #F0F8FF; /* Alice Blue */
        border: 1px solid #E0E0E0;
        border-radius: 5px;
        color: #006064; /* Dark Cyan Text */
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #20B2AA !important; /* Ocean Green Active */
        color: white !important;
        border: none;
    }
    
    /* 5. METRICS & HEADERS */
    /* Make headers Dark Ocean Blue for professionalism */
    h1, h2, h3 { color: #008B8B !important; } 
    div[data-testid="stMetricValue"] { color: #20B2AA !important; }
    
    /* 6. BUTTONS */
    button[kind="primary"] {
        background-color: #20B2AA !important;
        border: none;
        color: white !important;
        transition: 0.2s;
    }
    button[kind="primary"]:hover {
        background-color: #008080 !important; /* Darker Teal on Hover */
    }
    </style>
"""
st.markdown(clean_ocean_css, unsafe_allow_html=True)

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

# --- 3. LOGIC FUNCTIONS ---

def get_status(date_str, data_status, warning_days):
    if data_status == "incomplete" or not date_str or date_str == "None":
        return "MISSING"
    try:
        d = pd.to_datetime(date_str).date()
        days_left = (d - datetime.date.today()).days
        if days_left < 0: return "EXPIRED"
        elif days_left < warning_days: return "WARNING"
        else: return "SAFE"
    except:
        return "MISSING"

def ask_ai_to_read_date(file_bytes, mime_type):
    candidate_models = ["gemini-2.0-flash", "gemini-1.5-flash-latest", "gemini-pro-vision"]
    for model_name in candidate_models:
        try:
            model = genai.GenerativeModel(model_name)
            prompt = "Extract the Expiration Date. Return ONLY the date in YYYY-MM-DD format. If not found, return 'NOT_FOUND'."
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
        st.caption(f"User: {st.session_state['user'].email}")
        st.divider()
        if st.button("Log Out"): logout()

    # Main Tabs
    tab_dash, tab_import, tab_audit = st.tabs(["📊 Executive Dashboard", "📂 Import Data", "🤖 AI Audit"])

    # --- TAB 1: EXECUTIVE DASHBOARD ---
    with tab_dash:
        # Header Controls
        c_head1, c_head2 = st.columns([3, 1])
        with c_head1:
            st.subheader("Compliance Overview")
        with c_head2:
            safe_days = st.selectbox("Define Safe Zone:", [30, 60, 90], index=1, format_func=lambda x: f"{x} Days")
        
        # Fetch Data
        res = supabase.table("subcontractors").select("*").eq("tenant_id", DEFAULT_TENANT_ID).execute()
        
        if res.data:
            df = pd.DataFrame(res.data)
            df["Status"] = df.apply(lambda row: get_status(row.get("insurance_expiry_date"), row.get("data_status"), safe_days), axis=1)
            
            # Key Metrics
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total Workers", len(df))
            m2.metric("🟢 Safe", len(df[df["Status"] == "SAFE"]))
            m3.metric("🟡 Warning", len(df[df["Status"] == "WARNING"]))
            m4.metric("🔴 Action Reqd", len(df[df["Status"].isin(["EXPIRED", "MISSING"])]))
            
            st.divider()
            
            # SUB-TABS (Roster)
            sub_safe, sub_warn, sub_exp, sub_inc = st.tabs(["🟢 Safe", "🟡 Warning", "🔴 Expired", "⚠️ Incomplete"])
            
            with sub_safe:
                st.dataframe(df[df["Status"] == "SAFE"][["name", "trade", "insurance_expiry_date"]], use_container_width=True)
            with sub_warn:
                st.warning(f"These workers expire in less than {safe_days} days.")
                st.dataframe(df[df["Status"] == "WARNING"][["name", "trade", "insurance_expiry_date"]], use_container_width=True)
            with sub_exp:
                st.error("Insurance Expired. Access Denied.")
                st.dataframe(df[df["Status"] == "EXPIRED"][["name", "trade", "insurance_expiry_date"]], use_container_width=True)
            with sub_inc:
                st.info("Data Missing. Use AI Audit tab to fix.")
                st.dataframe(df[df["Status"] == "MISSING"][["name", "trade"]], use_container_width=True)
        else:
            st.info("No data. Go to 'Import Data'.")

    # --- TAB 2: IMPORT DATA ---
    with tab_import:
        st.subheader("Import Workforce")
        uploaded_file = st.file_uploader("Upload Excel/CSV", type=["xlsx", "csv"])
        
        if uploaded_file:
            if uploaded_file.name.endswith(".csv"): df_imp = pd.read_csv(uploaded_file)
            else: df_imp = pd.read_excel(uploaded_file)
            
            # SMART COLUMN FILTERING
            text_cols = df_imp.select_dtypes(include=['object', 'string']).columns.tolist()
            if not text_cols: text_cols = df_imp.columns.tolist() 
            all_cols = df_imp.columns.tolist()

            c_name_col, c_date_col = st.columns(2)
            with c_name_col:
                name_col = st.selectbox("Select Name Column (Text)", text_cols)
            with c_date_col:
                date_options = [c for c in all_cols if c != name_col]
                date_col = st.selectbox("Select Expiry Date Column", date_options)
            
            if name_col == date_col:
                st.error("⚠️ Name and Date cannot be the same column.")
            else:
                if st.button("Run Import", type="primary"):
                    existing_res = supabase.table("subcontractors").select("name").eq("tenant_id", DEFAULT_TENANT_ID).execute()
                    existing_names = set([row['name'] for row in existing_res.data]) if existing_res.data else set()
                    
                    added, skipped = 0, 0
                    bar = st.progress(0)
                    
                    for i, row in df_imp.iterrows():
                        name = str(row[name_col]).strip()
                        raw_date = str(row[date_col]).strip()
                        
                        if not name or name.lower() == "nan": continue
                        if name in existing_names:
                            skipped += 1
                            continue
                        
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
                        bar.progress((i+1)/len(df_imp))
                        
                    st.success(f"✅ Import Complete: {added} Added, {skipped} Skipped (Duplicates).")
                    time.sleep(1)
                    st.rerun()

    # --- TAB 3: AI AUDIT ---
    with tab_audit:
        st.subheader("AI Verification")
        
        res = supabase.table("subcontractors").select("id, name, data_status").eq("tenant_id", DEFAULT_TENANT_ID).execute()
        
        if res.data:
            workers = sorted(res.data, key=lambda x: x['data_status'] == 'verified')
            w_map = {f"{w['name']}": w['id'] for w in workers}
            
            sel_worker = st.selectbox("Select Worker:", list(w_map.keys()))
            sel_id = w_map[sel_worker]
            
            up_file = st.file_uploader("Upload Evidence", type=["png", "jpg", "jpeg"])
            
            if up_file and st.button("Auto-Extract & Update", type="primary"):
                with st.spinner("Processing..."):
                    path = f"{sel_id}_{int(time.time())}.{up_file.name.split('.')[-1]}"
                    supabase.storage.from_("certificates").upload(path, up_file.getvalue(), {"content-type": up_file.type})
                    url = supabase.storage.from_("certificates").get_public_url(path)
                    
                    supabase.table("documents").insert({"subcontractor_id": sel_id, "file_url": url, "file_name": up_file.name}).execute()
                    
                    date_found = ask_ai_to_read_date(up_file.getvalue(), up_file.type)
                    
                    if len(date_found) == 10 and date_found[4] == '-':
                        supabase.table("subcontractors").update({
                            "insurance_expiry_date": date_found,
                            "data_status": "verified"
                        }).eq("id", sel_id).execute()
                        st.balloons()
                        st.success(f"✅ Fixed! New Expiry: {date_found}")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"AI Failed. Saw: '{date_found}'")

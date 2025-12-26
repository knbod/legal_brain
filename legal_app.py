import streamlit as st
import pandas as pd
from supabase import create_client
import time
import datetime
import google.generativeai as genai

# --- 1. CONFIGURATION ---
st.set_page_config(
    page_title="Compliance HQ", 
    page_icon="🛡️", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# 🎨 PROFESSIONAL CSS (FIXED BLACK BOX & CRASHES)
professional_css = """
    <style>
    /* 1. HIDE MANAGE BUTTON & FOOTER */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    [data-testid="stToolbar"] {display: none !important;}
    [data-testid="manage-app-button"] {display: none !important;}
    
    /* 2. BACKGROUND & TEXT */
    .stApp {
        background-color: #FFFFFF;
        color: #111827;
    }
    
    /* 3. INPUT FIELDS (Clean White) */
    input[type="text"], input[type="password"] {
        background-color: #FFFFFF !important;
        color: #111827 !important;
        border: 1px solid #D1D5DB !important;
        border-radius: 6px; 
    }
    
    /* --- THE PASSWORD ICON FIX --- */
    /* Force the container holding the eye icon to be transparent/white */
    div[data-testid="stInputSecondary"] {
        background-color: transparent !important;
        border: none !important;
    }
    /* Force the button itself to be transparent */
    div[data-testid="stInputSecondary"] > button {
        background-color: transparent !important;
        border: none !important;
        color: #374151 !important; /* Dark Grey Icon */
    }
    /* SVG Fill Color */
    div[data-testid="stInputSecondary"] svg {
        fill: #374151 !important;
    }
    /* ---------------------------- */

    /* 5. LABELS VISIBLE */
    label, p, .stMarkdown {
        color: #374151 !important;
        font-weight: 500 !important;
    }

    /* 6. BUTTONS */
    button[kind="primary"] {
        background-color: #20B2AA !important; /* Ocean Green */
        border: none;
        color: white !important;
        border-radius: 6px;
    }
    button[kind="secondary"] {
        background-color: #FFFFFF !important;
        border: 1px solid #D1D5DB !important;
        color: #374151 !important;
        border-radius: 6px;
    }
    
    h1, h2, h3 { color: #111827 !important; }
    </style>
"""
st.markdown(professional_css, unsafe_allow_html=True)

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
    st.error("🚨 System Error: Database not connected.")
    st.stop()

try:
    DEFAULT_TENANT_ID = st.secrets["general"]["tenant_id"]
except:
    DEFAULT_TENANT_ID = "a8446e55-1a8c-477f-aed9-51998ab1e6cb"

if "user" not in st.session_state:
    st.session_state["user"] = None

# --- 3. HELPER FUNCTIONS ---
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
    models = ["gemini-2.0-flash", "gemini-1.5-flash-latest", "gemini-pro-vision"]
    for m in models:
        try:
            model = genai.GenerativeModel(m)
            prompt = "Extract Expiration Date. Return ONLY YYYY-MM-DD. If none, return 'NOT_FOUND'."
            resp = model.generate_content([prompt, {"mime_type": mime_type, "data": file_bytes}])
            return resp.text.strip().replace("```","").replace("json","")
        except: continue
    return "NOT_FOUND"

def login(email, password):
    try:
        response = supabase.auth.sign_in_with_password({"email": email.strip(), "password": password})
        st.session_state["user"] = response.user
        st.rerun()
    except: st.error("Invalid credentials.")

def signup(email, password):
    try:
        response = supabase.auth.sign_up({"email": email.strip(), "password": password})
        st.session_state["user"] = response.user
        st.success("Account created!")
        st.rerun()
    except Exception as e: st.error(f"Error: {e}")

def logout():
    supabase.auth.sign_out()
    st.session_state["user"] = None
    st.rerun()

# --- 4. APP INTERFACE ---

if st.session_state["user"] is None:
    # === LOGIN SCREEN ===
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        st.header("🛡️ Compliance HQ")
        st.write("Secure Workforce Management")
        st.divider()
        
        tab_login, tab_signup = st.tabs(["Log In", "Sign Up"])
        
        with tab_login:
            st.write(" ")
            l_email = st.text_input("Email Address", key="l_email", placeholder="name@company.com")
            l_pass = st.text_input("Password", type="password", key="l_pass", placeholder="••••••••")
            st.write(" ")
            if st.button("Log In", type="primary", use_container_width=True): login(l_email, l_pass)
            
        with tab_signup:
            st.write(" ")
            s_email = st.text_input("Business Email", key="s_email", placeholder="name@company.com")
            s_pass = st.text_input("Create Password", type="password", key="s_pass", placeholder="Min 6 chars")
            st.write(" ")
            if st.button("Create Account", type="primary", use_container_width=True): signup(s_email, s_pass)

else:
    # === MAIN DASHBOARD ===
    with st.sidebar:
        st.header("🛡️ HQ")
        st.caption(st.session_state['user'].email)
        st.divider()
        if st.button("Log Out", type="secondary", use_container_width=True): logout()

    # Tabs
    tab_dash, tab_audit = st.tabs(["📊 Dashboard & Import", "🤖 AI Audit"])

    with tab_dash:
        # Overview
        c_head1, c_head2 = st.columns([3, 1])
        with c_head1: st.subheader("Overview")
        with c_head2: 
            safe_days = st.selectbox("Warning Threshold", [30, 60, 90], index=1, format_func=lambda x: f"{x} Days")

        # Data Logic
        res = supabase.table("subcontractors").select("*").eq("tenant_id", DEFAULT_TENANT_ID).execute()
        df = pd.DataFrame(res.data) if res.data else pd.DataFrame(columns=["name", "insurance_expiry_date", "trade", "phone", "data_status"])

        if not df.empty:
            df["Status"] = df.apply(lambda row: get_status(row.get("insurance_expiry_date"), row.get("data_status"), safe_days), axis=1)
            
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total Workforce", len(df))
            m2.metric("🟢 Valid", len(df[df["Status"] == "SAFE"]))
            m3.metric("🟡 Expiring Soon", len(df[df["Status"] == "WARNING"]))
            m4.metric("🔴 Expired/Missing", len(df[df["Status"].isin(["EXPIRED", "MISSING"])]))
        else:
            st.info("Start by importing your workforce data below.")

        st.divider()

        # Import Section
        with st.expander("📂 Import New Workers", expanded=True):
            up_file = st.file_uploader("Upload Excel/CSV", type=["xlsx", "csv"], label_visibility="collapsed")
            
            if up_file:
                if up_file.name.endswith(".csv"): df_raw = pd.read_csv(up_file)
                else: df_raw = pd.read_excel(up_file)
                
                st.markdown("**Map Columns**")
                cols = df_raw.columns.tolist()
                text_cols = df_raw.select_dtypes(include=['object', 'string']).columns.tolist() or cols
                
                c1, c2, c3, c4 = st.columns(4)
                with c1: col_name = st.selectbox("Name *", text_cols)
                with c2: col_date = st.selectbox("Expiry Date *", [c for c in cols if c != col_name])
                with c3: col_job = st.selectbox("Job Title (Optional)", ["(Skip)"] + [c for c in cols if c not in [col_name, col_date]])
                with c4: col_cont = st.selectbox("Contact (Optional)", ["(Skip)"] + [c for c in cols if c not in [col_name, col_date, col_job]])
                
                if col_name == col_date:
                    st.error("Name and Date cannot be the same column.")
                else:
                    if st.button("Import Data Now", type="primary"):
                        count = 0
                        existing = supabase.table("subcontractors").select("name").eq("tenant_id", DEFAULT_TENANT_ID).execute()
                        exist_names = {r['name'] for r in existing.data} if existing.data else set()
                        
                        for i, row in df_raw.iterrows():
                            nm = str(row[col_name]).strip()
                            if not nm or nm.lower() == "nan" or nm in exist_names: continue
                            
                            dt_val = str(row[col_date]).strip()
                            db_dt = None
                            try:
                                parsed = pd.to_datetime(dt_val, errors='coerce')
                                if not pd.isna(parsed): db_dt = parsed.strftime('%Y-%m-%d')
                            except: pass
                            
                            job_val = str(row[col_job]) if col_job != "(Skip)" and pd.notna(row[col_job]) else None
                            cont_val = str(row[col_cont]) if col_cont != "(Skip)" and pd.notna(row[col_cont]) else None
                            
                            supabase.table("subcontractors").insert({
                                "tenant_id": DEFAULT_TENANT_ID,
                                "name": nm,
                                "insurance_expiry_date": db_dt,
                                "trade": job_val,
                                "phone": cont_val,
                                "data_status": "verified" if db_dt else "incomplete"
                            }).execute()
                            count += 1
                        
                        st.success(f"Imported {count} workers!")
                        time.sleep(1)
                        st.rerun()

        st.write("") 

        # Data Tables (CRASH FIXED HERE: Converted to Safe String Types)
        if not df.empty:
            t_valid, t_warn, t_exp, t_miss = st.tabs(["✅ Valid", "⚠️ Warning", "🔴 Expired", "📝 Missing Data"])
            
            disp_cols = ["name", "insurance_expiry_date"]
            if "trade" in df.columns: disp_cols.append("trade")
            if "phone" in df.columns: disp_cols.append("phone")
            
            # --- THE SAFETY FIX ---
            # We convert everything to strings to prevent the Arrow/ValueError crash
            df_safe = df.astype(str)
            # ----------------------
            
            with t_valid: st.dataframe(df_safe[df["Status"] == "SAFE"][disp_cols], use_container_width=True, hide_index=True)
            with t_warn: st.dataframe(df_safe[df["Status"] == "WARNING"][disp_cols], use_container_width=True, hide_index=True)
            with t_exp: st.dataframe(df_safe[df["Status"] == "EXPIRED"][disp_cols], use_container_width=True, hide_index=True)
            with t_miss: 
                miss_cols = ["name"] + [c for c in disp_cols if c != "insurance_expiry_date"]
                st.dataframe(df_safe[df["Status"] == "MISSING"][miss_cols], use_container_width=True, hide_index=True)

    with tab_audit:
        c_head1, c_head2 = st.columns([3, 1])
        with c_head1: st.subheader("AI Document Processor")
        
        res = supabase.table("subcontractors").select("id, name, data_status").eq("tenant_id", DEFAULT_TENANT_ID).execute()
        if res.data:
            workers = sorted(res.data, key=lambda x: x['data_status'] == 'verified')
            w_map = {w['name']: w['id'] for w in workers}
            
            sel_wk = st.selectbox("Select Worker for Audit", list(w_map.keys()))
            up_ev = st.file_uploader("Upload Certificate", type=["png", "jpg", "jpeg"])
            
            if up_ev and st.button("Run AI Extraction", type="primary"):
                with st.spinner("Processing..."):
                    wk_id = w_map[sel_wk]
                    path = f"{wk_id}_{int(time.time())}.{up_ev.name.split('.')[-1]}"
                    supabase.storage.from_("certificates").upload(path, up_ev.getvalue(), {"content-type": up_ev.type})
                    url = supabase.storage.from_("certificates").get_public_url(path)
                    supabase.table("documents").insert({"subcontractor_id": wk_id, "file_url": url, "file_name": up_ev.name}).execute()
                    
                    found_date = ask_ai_to_read_date(up_ev.getvalue(), up_ev.type)
                    
                    if len(found_date) == 10 and found_date[4] == '-':
                        supabase.table("subcontractors").update({"insurance_expiry_date": found_date, "data_status": "verified"}).eq("id", wk_id).execute()
                        st.balloons()
                        st.success(f"Updated {sel_wk}: {found_date}")
                        time.sleep(1.5)
                        st.rerun()
                    else:
                        st.error("AI could not read the date. Please verify the document.")

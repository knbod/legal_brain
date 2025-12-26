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

# --- 2. CONSTANTS & SESSION ---
# ⚠️ PASTE YOUR COPIED TENANT ID HERE ⚠️
DEFAULT_TENANT_ID = "a8446e55-1a8c-477f-aed9-51998ab1e6cb" 

if "user" not in st.session_state:
    st.session_state["user"] = None

# --- 3. HELPER FUNCTIONS ---
def smart_find_column(columns, keywords):
    """Try to guess the column name based on a keyword list."""
    for col in columns:
        for key in keywords:
            if key in col.lower():
                return col
    return None

def login(email, password):
    try:
        response = supabase.auth.sign_in_with_password({"email": email.strip(), "password": password})
        st.session_state["user"] = response.user
        st.success("✅ Logged in!")
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

# --- 4. THE APP LOGIC ---

# === A. LOGIN SCREEN (If not logged in) ===
if st.session_state["user"] is None:
    st.title("🚧 Site Compliance Login")
    tab1, tab2 = st.tabs(["Log In", "Sign Up"])
    
    with tab1:
        email = st.text_input("Email", key="l_email")
        password = st.text_input("Password", type="password", key="l_pass")
        if st.button("Log In"):
            login(email, password)
            
    with tab2:
        st.caption("Create a new account")
        new_email = st.text_input("Email", key="s_email")
        new_pass = st.text_input("Password", type="password", key="s_pass")
        if st.button("Sign Up"):
            signup(new_email, new_pass)

# === B. MAIN DASHBOARD (If logged in) ===
else:
    # Sidebar Info
    st.sidebar.write(f"👤 {st.session_state['user'].email}")
    st.sidebar.button("Log Out", on_click=logout)
    
    st.title("🏗️ Compliance HQ")
    
    # The Main Tabs
    tab_import, tab_dash, tab_review = st.tabs(["📂 Import Wizard", "📊 Dashboard", "⚠️ Needs Review"])
    
    # --- TAB 1: IMPORT WIZARD ---
    with tab_import:
        st.header("Upload Subcontractors")
        st.info("Upload an Excel/CSV file. We will help you map the columns.")
        
        uploaded_file = st.file_uploader("Drag & Drop File", type=["xlsx", "csv"])
        
        if uploaded_file:
            try:
                # Load Data
                if uploaded_file.name.endswith(".csv"):
                    df = pd.read_csv(uploaded_file)
                else:
                    df = pd.read_excel(uploaded_file)
                
                st.write("### 1. Map Columns")
                cols = df.columns.tolist()
                
                c1, c2, c3 = st.columns(3)
                
                # Smart Defaults
                def_name = smart_find_column(cols, ["name", "worker", "company"])
                def_exp = smart_find_column(cols, ["expiry", "end", "valid", "date"])
                def_trade = smart_find_column(cols, ["trade", "job", "role"])

                with c1:
                    map_name = st.selectbox("Name Column (Required)", cols, index=cols.index(def_name) if def_name else 0)
                with c2:
                    map_exp = st.selectbox("Expiry Date Column (Required)", cols, index=cols.index(def_exp) if def_exp else 0)
                with c3:
                    map_trade = st.selectbox("Trade (Optional)", ["(Skip)"] + cols, index=cols.index(def_trade)+1 if def_trade else 0)

                st.write("### 2. Run Import")
                if st.button("Start Import"):
                    success, quarantine = 0, 0
                    bar = st.progress(0)
                    
                    for i, row in df.iterrows():
                        # Extract Data
                        val_name = str(row[map_name]) if pd.notna(row[map_name]) else ""
                        val_exp = str(row[map_exp]) if pd.notna(row[map_exp]) else ""
                        val_trade = str(row[map_trade]) if map_trade != "(Skip)" and pd.notna(row[map_trade]) else None
                        
                        # Logic: Determine Status
                        status = "verified"
                        issues = []
                        
                        if not val_name or val_name.lower() == "nan" or val_name == "":
                            status = "incomplete"
                            issues.append("Missing Name")
                            
                        # Parse Date
                        parsed_date = pd.to_datetime(val_exp, errors='coerce')
                        if pd.isna(parsed_date):
                            status = "incomplete"
                            issues.append("Invalid/Missing Date")
                            db_date = None
                        else:
                            db_date = parsed_date.strftime('%Y-%m-%d')

                        # Save to Supabase
                        payload = {
                            "tenant_id": DEFAULT_TENANT_ID,
                            "name": val_name,
                            "trade": val_trade,
                            "insurance_expiry_date": db_date,
                            "data_status": status,
                            "missing_info": ", ".join(issues) if issues else None
                        }
                        
                        supabase.table("subcontractors").insert(payload).execute()
                        
                        if status == "verified": success += 1
                        else: quarantine += 1
                        
                        bar.progress((i + 1) / len(df))
                    
                    st.success(f"Done! {success} verified, {quarantine} sent to review.")
                    time.sleep(1)
                    st.rerun()

            except Exception as e:
                st.error(f"File Error: {e}")

    # --- TAB 2: DASHBOARD (Verified) ---
    with tab_dash:
        st.header("✅ Active Workers")
        # Fetch Verified Data
        res = supabase.table("subcontractors").select("*").eq("tenant_id", DEFAULT_TENANT_ID).eq("data_status", "verified").execute()
        
        if res.data:
            df_main = pd.DataFrame(res.data)
            
            # Add Traffic Light 🚦
            def get_color(date_str):
                if not date_str: return "⚪"
                d = pd.to_datetime(date_str).date()
                today = datetime.date.today()
                days = (d - today).days
                if days < 0: return "🔴 EXPIRED"
                if days < 30: return "🟡 WARN"
                return "🟢 OK"

            df_main["Status"] = df_main["insurance_expiry_date"].apply(get_color)
            
            st.dataframe(df_main[["Status", "name", "trade", "insurance_expiry_date"]], use_container_width=True)
        else:
            st.info("No verified workers yet. Go to Import Wizard!")

    # --- TAB 3: NEEDS REVIEW (Quarantine) ---
    with tab_review:
        st.header("⚠️ Data Issues")
        st.caption("These rows are missing critical info. Please fix them.")
        
        res_q = supabase.table("subcontractors").select("*").eq("tenant_id", DEFAULT_TENANT_ID).eq("data_status", "incomplete").execute()
        
        if res_q.data:
            st.dataframe(pd.DataFrame(res_q.data)[["missing_info", "name", "trade"]], use_container_width=True)
        else:
            st.success("No issues found!")

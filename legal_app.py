import streamlit as st
import pandas as pd
import random
import os

# --- 1. CONFIGURATION & AUTO-LOAD ---
st.set_page_config(page_title="Legal Brain", layout="centered")
st.title("⚖️ Digital Legal Brain")

# Setup the "Backpack"
if "legal_db" not in st.session_state:
    st.session_state["legal_db"] = []

# AUTO-LOAD: Check if file exists when app starts
if len(st.session_state["legal_db"]) == 0:
    if os.path.exists("legal_notes.csv"):
        df_loaded = pd.read_csv("legal_notes.csv")
        st.session_state["legal_db"] = df_loaded.to_dict("records")

# --- 2. SIDEBAR: MANAGE DATA ---
st.sidebar.header("🗄️ Data Management")

# A. Manual Load (Backup)
uploaded_file = st.sidebar.file_uploader("Upload CSV", type=["csv"])
if uploaded_file is not None:
    if st.sidebar.button("Load File"):
        df_loaded = pd.read_csv(uploaded_file)
        st.session_state["legal_db"] = df_loaded.to_dict("records")
        st.success("Loaded!")
        st.rerun()

st.sidebar.write("---")

if len(st.session_state["legal_db"]) > 0:
    # B. Edit Trigger (The Teleporter)
    st.sidebar.subheader("Edit a Case")
    q_list = [row["Question"] for row in st.session_state["legal_db"]]
    q_to_edit = st.sidebar.selectbox("Select to Edit", q_list)
    
    if st.sidebar.button("✏️ Load for Editing"):
        # Find the row and copy it to the 'edit_buffer'
        for row in st.session_state["legal_db"]:
            if row["Question"] == q_to_edit:
                st.session_state["edit_buffer"] = row
                st.info("Loaded! Go to 'Add/Edit' tab.")
                break

    st.sidebar.write("---")

    # C. Delete Trigger
    st.sidebar.subheader("Delete a Case")
    q_to_delete = st.sidebar.selectbox("Select to Delete", q_list, key="del_select")
    
    if st.sidebar.button("🗑️ Delete Entry"):
        for i, row in enumerate(st.session_state["legal_db"]):
            if row["Question"] == q_to_delete:
                del st.session_state["legal_db"][i]
                break
        st.rerun()

# --- 3. MAIN TABS ---
tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "📝 Add/Edit Case", "🎓 Practice Mode"])

# =========================================
# TAB 1: DASHBOARD & ANALYTICS
# =========================================
with tab1:
    if len(st.session_state["legal_db"]) > 0:
        df = pd.DataFrame(st.session_state["legal_db"])
        df.index = df.index + 1
        
        # --- ANALYTICS PANEL ---
        st.write("### Your Progress")
        col_m1, col_m2, col_m3 = st.columns(3)
        
        # Metrics
        hard_count = len(df[df["Difficulty"] == "🔴 Hard"])
        col_m1.metric("Total Cases", len(df))
        # We set delta to 'hard_count' so if it's > 0, it shows RED (Warning)
        col_m2.metric("Needs Review", hard_count, delta=hard_count, delta_color="inverse")
        col_m3.metric("Subjects", len(df["Subject"].unique()))
        
        # Chart
        st.bar_chart(df["Subject"].value_counts())
        st.write("---")
        
        # --- SEARCH & FILTER ---
        c1, c2, c3 = st.columns(3)
        search_term = c1.text_input("Search", placeholder="Keywords...")
        subject_filter = c2.selectbox("Subject", ["All"] + list(df["Subject"].unique()))
        diff_filter = c3.selectbox("Difficulty", ["All"] + list(df["Difficulty"].unique()))
        
        # Logic Engine
        if subject_filter != "All":
            df = df[df["Subject"] == subject_filter]
        if diff_filter != "All":
            df = df[df["Difficulty"] == diff_filter]
        if search_term:
            df = df[df["Question"].str.contains(search_term, case=False)]
            
        st.write(f"**Showing {len(df)} cases:**")
        st.dataframe(df[["Subject", "Difficulty", "Question"]], use_container_width=True)
        
        # --- SAVE BUTTON ---
        st.write("---")
        with st.expander("💾 Save Database"):
            if st.button("Save & Download CSV"):
                df.to_csv("legal_notes.csv", index=False)
                st.success("Saved to legal_notes.csv!")
    else:
        st.info("Database is empty. Go to the 'Add/Edit Case' tab!")

# =========================================
# TAB 2: ADD OR EDIT CASE
# =========================================
with tab2:
    st.header("Manage Entry")
    
    # 1. SETUP DEFAULTS (Empty)
    def_sub = "Wills & Succession"
    def_diff = "🟢 Easy"
    def_q = ""
    def_a = ""
    
    # 2. CHECK FOR EDIT MODE (Overwrite Defaults)
    if "edit_buffer" in st.session_state:
        st.warning("✏️ EDIT MODE ACTIVE: You are modifying an existing case.")
        data = st.session_state["edit_buffer"]
        def_sub = data["Subject"]
        def_diff = data["Difficulty"]
        def_q = data["Question"]
        def_a = data["Answer"]
    
    # 3. CREATE FORM
    all_subjects = ["Wills & Succession", "Property", "Contracts", "Family Law", "Obligations", "Civil Procedure"]
    
    # Find the 'Seat Number' for the subject dropdown
    if def_sub in all_subjects:
        sub_index = all_subjects.index(def_sub)
    else:
        sub_index = 0
        
    c_a, c_b = st.columns(2)
    new_sub = c_a.selectbox("Subject", all_subjects, index=sub_index)
    new_diff = c_b.select_slider("Difficulty", options=["🟢 Easy", "🟡 Medium", "🔴 Hard"], value=def_diff)
    
    new_q = st.text_area("Question", height=100, value=def_q)
    new_a = st.text_area("Answer", height=150, value=def_a)
    
    # 4. SAVE LOGIC
    if st.button("Save Case"):
        if new_q and new_a:
            # A. Remove Old Version (If Editing)
            if "edit_buffer" in st.session_state:
                old_q = st.session_state["edit_buffer"]["Question"]
                for i, row in enumerate(st.session_state["legal_db"]):
                    if row["Question"] == old_q:
                        del st.session_state["legal_db"][i]
                        break
                del st.session_state["edit_buffer"] # Exit Edit Mode
            
            # B. Add New Version
            new_entry = {
                "Subject": new_sub,
                "Difficulty": new_diff,
                "Question": new_q,
                "Answer": new_a
            }
            st.session_state["legal_db"].append(new_entry)
            
            # C. Auto-Save to File immediately (Pro Feature!)
            pd.DataFrame(st.session_state["legal_db"]).to_csv("legal_notes.csv", index=False)
            
            st.success("Saved!")
            st.rerun()
        else:
            st.warning("Please fill in both Question and Answer.")

# =========================================
# TAB 3: PRACTICE MODE
# =========================================
with tab3:
    st.header("Flashcard Quiz")
    
    # We filter ONLY for the 'Flashcards' based on dashboard filters? 
    # Let's keep it simple: Random from ALL database for now.
    if st.button("🎲 Pick Random Question"):
        if len(st.session_state["legal_db"]) > 0:
            st.session_state["current_card"] = random.choice(st.session_state["legal_db"])
        else:
            st.warning("Database empty!")
            
    if "current_card" in st.session_state:
        card = st.session_state["current_card"]
        st.info(f"Subject: {card['Subject']} | {card['Difficulty']}")
        st.markdown(f"### ❓ {card['Question']}")
        
        with st.expander("👀 Show Answer"):
            st.markdown(f"**Answer:**\n\n{card['Answer']}")
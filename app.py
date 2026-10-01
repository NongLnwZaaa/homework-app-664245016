from __future__ import annotations
import pandas as pd
import streamlit as st

from neo4j_service import (
    get_dashboard_metrics, get_profile, get_users, get_songs,
    graph_neighborhood, ping, recommend_songs, record_like, search_songs,
    seed_demo_data, add_user, add_song, update_user, update_song, 
    delete_user, delete_song, remove_like
)

# ตั้งค่าสถานะ Admin ใน Session State
if "is_admin" not in st.session_state:
    st.session_state.is_admin = False

st.set_page_config(
    page_title="Music Recommender",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      .block-container {padding-top: 1.3rem; padding-bottom: 2rem;}
      .hero {
        padding: 1.4rem 1.6rem; border-radius: 22px;
        background: linear-gradient(120deg, #111827 0%, #1f2937 55%, #1d4ed8 100%);
        color: white; margin-bottom: 1rem;
      }
      .hero h1 {margin:0; font-size:2.15rem;}
      .hero p {opacity:.88; margin:.35rem 0 0 0;}
      .book-card {
        padding: 1rem 1.1rem; border: 1px solid rgba(128,128,128,.25);
        border-radius: 16px; margin-bottom: .75rem;
      }
      .score-pill {
        display:inline-block; padding:.2rem .55rem; border-radius:999px;
        background:#1d4ed8; color:white; font-size:.8rem; font-weight:700;
      }
      .muted {opacity:.72; font-size:.9rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

def require_connection() -> None:
    try:
        if not ping():
            raise RuntimeError("Neo4j did not return a healthy response")
    except Exception as exc:
        st.error("ยังเชื่อมต่อ Neo4j ไม่สำเร็จ")
        st.stop()

def user_selector(key: str = "user") -> str:
    users = get_users()
    if not users:
        st.info("ยังไม่มีข้อมูลผู้ใช้ กรุณาสร้างข้อมูลก่อน")
        st.stop()
    chosen = st.selectbox("เลือกผู้ใช้", [u["name"] for u in users], key=key)
    return chosen

require_connection()

with st.sidebar:
    st.markdown("## 🎵 Music Graph")
    page = st.radio(
        "เมนูหลัก",
        ["Dashboard", "Recommendations", "Song Search", "Graph Explorer", "จัดการข้อมูล (Manage Data)", "Admin / Setup"]
    )
    
    st.divider()
    
    # โฟลเดอร์สำหรับการบ้านเก่า
    st.markdown("### 📂 การบ้านเก่า")
    st.markdown("👉 [โปรเจกต์ Book Recommender (GitHub)](https://github.com/NongLnwZaaa/homework-app-664245016/tree/main/Homework)")
    st.caption("คลิกเพื่อไปยังคลังโค้ดของการบ้านเก่า")
    
    st.divider()
    if st.session_state.is_admin:
        st.success("🟢 สถานะ: Admin")
    else:
        st.info("🔵 สถานะ: ผู้ใช้ทั่วไป")

st.markdown(
    """
    <div class="hero">
      <h1>🎵 Music Recommendation System</h1>
      <p>ระบบแนะนำเพลงด้วย Graph Database และ Collaborative Filtering</p>
    </div>
    """,
    unsafe_allow_html=True,
)

if page == "Dashboard":
    st.subheader("ภาพรวมระบบ")
    m = get_dashboard_metrics()
    c1, c2, c3 = st.columns(3)
    c1.metric("Users", m.get("users", 0))
    c2.metric("Songs", m.get("songs", 0))
    c3.metric("Total Likes", m.get("likes", 0))

    st.divider()
    user_name = user_selector("dash_user")
    profile = get_profile(user_name)
    
    if profile:
        st.markdown(f"### โปรไฟล์ของ {profile['name']}")
        st.markdown("**เพลงที่ชอบ:**")
        if profile["liked_songs"]:
            for song in profile["liked_songs"]:
                st.write(f"- {song}")
        else:
            st.info("ยังไม่มีประวัติการกดชอบเพลง")

elif page == "Recommendations":
    st.subheader("✨ เพลงที่แนะนำ")
    user_name = user_selector("rec_user")
    top_n = st.slider("จำนวนคำแนะนำ", 3, 10, 5)
    rows = recommend_songs(user_name, top_n)

    st.caption("ระบบแนะนำเพลงจากผู้ใช้ท่านอื่นที่มีความชอบคล้ายคลึงกัน (Collaborative Filtering)")
    if not rows:
        st.info("ยังไม่มีคำแนะนำสำหรับผู้ใช้นี้ (ต้องมีการกดถูกใจเพลงร่วมกับผู้ใช้อื่นก่อน)")
    for i, row in enumerate(rows, start=1):
        similar_users = ", ".join(row['similar_users'])
        st.markdown(
            f"""
            <div class="book-card">
              <span class="score-pill">#{i} · match score {row['score']}</span>
              <h3 style="margin:.55rem 0 .2rem 0">{row['title']}</h3>
              <p class="muted">เพราะผู้ใช้ที่ชอบเพลงคล้ายคุณชอบเพลงนี้: {similar_users}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

elif page == "Song Search":
    st.subheader("🔎 ค้นหาเพลง")
    keyword = st.text_input("ชื่อเพลง", placeholder="เช่น Bohemian, Shape, Perfect")
    rows = search_songs(keyword)
    st.write(f"พบ {len(rows)} รายการ")
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

elif page == "Graph Explorer":
    st.subheader("🕸️ Graph Explorer")
    user_name = user_selector("graph_user")
    rows = graph_neighborhood(user_name)
    if not rows:
        st.info("ยังไม่มี neighborhood graph")
    else:
        dot = ["digraph G {", 'rankdir="LR";', 'node [shape=box, style="rounded,filled", fillcolor="#f8fafc"];']
        seen_nodes = set()
        for r in rows:
            for nid, label, name in [
                (r["source_id"], r["source_label"], r["source_name"]),
                (r["target_id"], r["target_label"], r["target_name"]),
            ]:
                if nid not in seen_nodes:
                    safe_name = str(name).replace('"', "'")
                    color = "#bfdbfe" if label == "User" else "#bbf7d0"
                    dot.append(f'"{nid}" [label="{safe_name}\\n:{label}", fillcolor="{color}"];')
                    seen_nodes.add(nid)
            dot.append(f'"{r["source_id"]}" -> "{r["target_id"]}" [label="{r["relationship"]}"];')
        dot.append("}")
        st.graphviz_chart("\n".join(dot), use_container_width=True)

elif page == "จัดการข้อมูล (Manage Data)":
    st.subheader("📝 จัดการข้อมูลในระบบ")
    
    # แบ่งเป็น 3 แท็บ
    tab1, tab2, tab3 = st.tabs(["➕ เพิ่มข้อมูล (ทุกคน)", "✏️ แก้ไข (แอดมิน)", "🗑️ ลบ (แอดมิน)"])
    
    with tab1:
        st.markdown("#### เพิ่มการกดไลก์เพลง")
        users = get_users()
        songs = search_songs()
        
        if users and songs:
            col1, col2 = st.columns(2)
            with col1:
                sel_user = st.selectbox("เลือกผู้ใช้", [u["name"] for u in users], key="add_like_user")
            with col2:
                sel_song = st.selectbox("เลือกเพลง", [s["title"] for s in songs], key="add_like_song")
            if st.button("บันทึกการกดไลก์", type="primary"):
                record_like(sel_user, sel_song)
                st.success(f"บันทึกแล้วว่า {sel_user} ชอบเพลง {sel_song}")
        else:
            st.warning("ต้องมีผู้ใช้และเพลงในระบบก่อน")
            
        st.divider()
        st.markdown("#### เพิ่มผู้ใช้ / เพลงใหม่")
        col3, col4 = st.columns(2)
        with col3:
            new_user = st.text_input("ชื่อผู้ใช้ใหม่")
            if st.button("เพิ่มผู้ใช้"):
                if new_user:
                    add_user(new_user)
                    st.success(f"เพิ่มผู้ใช้ {new_user} สำเร็จ!")
                    st.rerun()
        with col4:
            new_song = st.text_input("ชื่อเพลงใหม่")
            if st.button("เพิ่มเพลง"):
                if new_song:
                    add_song(new_song)
                    st.success(f"เพิ่มเพลง {new_song} สำเร็จ!")
                    st.rerun()

    with tab2:
        if not st.session_state.is_admin:
            st.error("🔒 กรุณาเข้าสู่ระบบ Admin ในเมนู Admin / Setup ก่อนเพื่อใช้งานหน้านี้")
        else:
            st.markdown("#### แก้ไขชื่อผู้ใช้")
            if users:
                edit_user = st.selectbox("เลือกผู้ใช้ที่จะแก้ไข", [u["name"] for u in users], key="edit_user_sel")
                new_name = st.text_input("ชื่อผู้ใช้ใหม่ (แทนที่)", key="edit_user_input")
                if st.button("อัปเดตผู้ใช้"):
                    update_user(edit_user, new_name)
                    st.success("อัปเดตสำเร็จ!")
                    st.rerun()
            
            st.divider()
            st.markdown("#### แก้ไขชื่อเพลง")
            if songs:
                edit_song = st.selectbox("เลือกเพลงที่จะแก้ไข", [s["title"] for s in songs], key="edit_song_sel")
                new_title = st.text_input("ชื่อเพลงใหม่ (แทนที่)", key="edit_song_input")
                if st.button("อัปเดตเพลง"):
                    update_song(edit_song, new_title)
                    st.success("อัปเดตสำเร็จ!")
                    st.rerun()

    with tab3:
        if not st.session_state.is_admin:
            st.error("🔒 กรุณาเข้าสู่ระบบ Admin ในเมนู Admin / Setup ก่อนเพื่อใช้งานหน้านี้")
        else:
            st.markdown("#### ลบข้อมูล")
            st.warning("การลบข้อมูลนี้จะลบความสัมพันธ์ (Likes) ทั้งหมดที่เกี่ยวข้องด้วย")
            
            col5, col6 = st.columns(2)
            with col5:
                if users:
                    del_u = st.selectbox("เลือกผู้ใช้ที่จะลบ", [u["name"] for u in users], key="del_u")
                    if st.button("ลบผู้ใช้นี้", type="primary"):
                        delete_user(del_u)
                        st.success(f"ลบผู้ใช้ {del_u} เรียบร้อย")
                        st.rerun()
            with col6:
                if songs:
                    del_s = st.selectbox("เลือกเพลงที่จะลบ", [s["title"] for s in songs], key="del_s")
                    if st.button("ลบเพลงนี้", type="primary"):
                        delete_song(del_s)
                        st.success(f"ลบเพลง {del_s} เรียบร้อย")
                        st.rerun()

elif page == "Admin / Setup":
    st.subheader("⚙️ เข้าสู่ระบบผู้ดูแลระบบ")
    
    if not st.session_state.is_admin:
        # ดึงรหัสผ่านแอดมินจาก Streamlit Secrets
        ADMIN_PASSWORD = st.secrets["admin_password"]
        
        pwd = st.text_input("กรุณากรอกรหัสผ่าน", type="password")
        if st.button("Login"):
            if pwd == ADMIN_PASSWORD:
                st.session_state.is_admin = True
                st.success("เข้าสู่ระบบเรียบร้อยแล้ว!")
                st.rerun()
            else:
                st.error("รหัสผ่านไม่ถูกต้อง")
    else:
        st.success("คุณอยู่ในโหมด Admin สามารถเข้าไปแก้ไข หรือลบข้อมูลได้ในหน้า Manage Data")
        if st.button("ออกจากระบบ (Logout)"):
            st.session_state.is_admin = False
            st.rerun()

    st.divider()
    st.subheader("รีเซ็ตระบบ (Setup ข้อมูลตัวอย่าง)")
    if st.button("สร้าง Constraint + Demo Data", type="primary", use_container_width=True):
        if not st.session_state.is_admin:
            st.warning("ใครๆ ก็สามารถสร้างข้อมูลตัวอย่างได้ แต่ห้ามลบ!")
        with st.spinner("กำลังสร้างข้อมูล..."):
            seed_demo_data()
        st.success("สร้างข้อมูลตัวอย่างเรียบร้อยแล้ว")
        st.rerun()
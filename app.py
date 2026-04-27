import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import pandas as pd
import io

from config import (
    FUND_ORDER, FUND_DISPLAY, STATIC_ROWS, AUTO_ROWS,
    ROW_ORDER, RED_IF_NEGATIVE, HIGHLIGHT_ROWS
)
from parser import build_table
from renderer import render_html, render_image

st.set_page_config(page_title="MMF 피어그룹 비교표", layout="wide")
st.title("MMF 피어그룹 비교표")

# ── 파일 업로드 ──────────────────────────────────────────
with st.sidebar:
    st.header("📂 파일 업로드")
    mm_file = st.file_uploader("MM.xlsx (펀드닥터 월간)", type="xlsx", key="mm")
    my_file = st.file_uploader("MY.xlsx (펀드닥터 연간)", type="xlsx", key="my")
    f2_file = st.file_uploader("F2.xlsx (펀드스퀘어)",    type="xlsx", key="f2")
    run_btn = st.button("🔄 표 생성", type="primary", use_container_width=True)

# ── 파일을 tmp에 저장 (openpyxl은 path 필요) ────────────
def save_tmp(uploaded) -> str:
    tmp = os.path.join("/tmp", uploaded.name)
    with open(tmp, "wb") as f:
        f.write(uploaded.getvalue())
    return tmp

# ── 세션 상태 ────────────────────────────────────────────
if "table_data" not in st.session_state:
    st.session_state.table_data = None
if "error_msg" not in st.session_state:
    st.session_state.error_msg = None

if run_btn:
    if not (mm_file and my_file and f2_file):
        st.sidebar.error("MM / MY / F2 파일을 모두 업로드하세요.")
    else:
        with st.spinner("파싱 중..."):
            try:
                mm_path = save_tmp(mm_file)
                my_path = save_tmp(my_file)
                f2_path = save_tmp(f2_file)
                auto_data = build_table(mm_path, my_path, f2_path)
                st.session_state.table_data = auto_data
                st.session_state.error_msg  = None
            except ValueError as e:
                st.session_state.error_msg  = str(e)
                st.session_state.table_data = None

if st.session_state.error_msg:
    st.error(st.session_state.error_msg)

if st.session_state.table_data:
    auto_data = st.session_state.table_data

    # 전체 테이블 조립: ROW_ORDER 기준
    auto_labels = {r[0] for r in AUTO_ROWS}
    full_table = {}  # { label: { code: val } }
    for label in ROW_ORDER:
        if label in STATIC_ROWS:
            full_table[label] = STATIC_ROWS[label]
        elif label in auto_data:
            full_table[label] = auto_data[label]

    # ── HTML 표 렌더링 ──────────────────────────────────
    html = render_html(full_table, FUND_ORDER, FUND_DISPLAY, HIGHLIGHT_ROWS, RED_IF_NEGATIVE)
    st.markdown(html, unsafe_allow_html=True)

    st.divider()

    # ── 이미지 다운로드 ─────────────────────────────────
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🖼️ 이미지 생성"):
            with st.spinner("이미지 렌더링 중..."):
                img_bytes = render_image(full_table, FUND_ORDER, FUND_DISPLAY,
                                         HIGHLIGHT_ROWS, RED_IF_NEGATIVE)
            st.session_state.img_bytes = img_bytes

    if "img_bytes" in st.session_state and st.session_state.img_bytes:
        with col2:
            st.download_button(
                label="⬇️ PNG 다운로드",
                data=st.session_state.img_bytes,
                file_name="mmf_comparison.png",
                mime="image/png",
            )

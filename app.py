import os
import json
import io
import re
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

# ==================== CẤU HÌNH GIAO DIỆN STREAMLIT ====================
st.set_page_config(
    page_title="Dashboard Quản Trị Đào Tạo & Action Tracking",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS cho giao diện hiện đại, chuyên nghiệp
st.markdown("""
<style>
    .metric-card {
        background-color: #ffffff;
        border-radius: 10px;
        padding: 14px 16px;
        border-left: 5px solid #1f77b4;
        box-shadow: 0 2px 6px rgba(0,0,0,0.06);
        margin-bottom: 10px;
    }
    .metric-title {
        font-size: 12px;
        color: #6c757d;
        font-weight: 700;
        text-transform: uppercase;
        margin-bottom: 4px;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .metric-value {
        font-size: 26px;
        font-weight: 800;
        color: #212529;
    }
    .metric-sub {
        font-size: 11px;
        color: #495057;
        margin-top: 4px;
    }
    .tag-badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 13px;
        margin-right: 6px;
    }
    .status-improved { color: #2b8a3e; font-weight: bold; }
    .status-stagnant { color: #dc3545; font-weight: bold; }
    .status-new-risk { color: #fd7e14; font-weight: bold; }
    div[data-testid="stMetricValue"] { font-size: 26px; }
</style>
""", unsafe_allow_html=True)

NOTES_DB_FILE = "action_notes_db.json"
MASTER_DATA_SHEET_ID = "1OlBnpQMEA02X1OTYVhuIb_j1xrTjvFcwZl4EzvWyn04"
TARGET_SHEET_NAME = "HANNAH_ACTION_BOARD_Test"

# ==================== CƠ SỞ DỮ LIỆU LƯU GHI CHÚ ACTION ====================
def load_notes_db():
    if os.path.exists(NOTES_DB_FILE):
        try:
            with open(NOTES_DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_notes_db(notes_dict):
    try:
        with open(NOTES_DB_FILE, "w", encoding="utf-8") as f:
            json.dump(notes_dict, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        st.error(f"Lỗi khi lưu action note: {e}")
        return False

def get_previous_action_note(notes_db, mssv, prev_week=None):
    """
    Kế thừa ghi chú của tuần trước:
    Ưu tiên tìm theo key: f"{prev_week}_{mssv}".
    Nếu không thấy, tìm bản ghi gần nhất trước đó của MSSV trong notes_db.
    """
    if prev_week:
        key = f"{prev_week}_{mssv}"
        if key in notes_db:
            item = notes_db[key]
            status = item.get("status", "Chưa liên hệ")
            note = str(item.get("note", "")).strip()
            return f"[{status}] {note}" if note else f"[{status}]"

    # Tìm bản ghi gần nhất của học viên
    for k, item in notes_db.items():
        if k.endswith(f"_{mssv}"):
            status = item.get("status", "")
            note = str(item.get("note", "")).strip()
            if note or (status and status != "Chưa liên hệ"):
                wk = k.split("_")[0]
                return f"({wk}) [{status}] {note}" if note else f"({wk}) [{status}]"

    return "— (Chưa có ghi chú tuần trước)"

# ==================== HÀM TIỀN XỬ LÝ & BÓC TÁCH DỮ LIỆU ====================
def parse_fraction(val):
    if pd.isna(val) or val == "-" or str(val).strip() == "":
        return 0, 0
    m = re.match(r"(\d+)\s*/\s*(\d+)", str(val).strip())
    if m:
        return int(m.group(1)), int(m.group(2))
    try:
        n = int(float(str(val).strip()))
        return n, n
    except Exception:
        return 0, 0

def parse_decimal_vn(val):
    if pd.isna(val) or str(val).strip() == "":
        return 0.0
    s = str(val).replace(",", ".").strip()
    try:
        return float(s)
    except Exception:
        return 0.0

def get_quarter_from_week(week_str):
    m = re.search(r"W(\d+)", str(week_str))
    if m:
        w = int(m.group(1))
        year = str(week_str).split("-")[0] if "-" in str(week_str) else "2026"
        q = (w - 1) // 13 + 1
        return f"{year}-Q{q}"
    return "Khác"

def extract_tag_code(tag_str):
    s = str(tag_str).strip()
    for code in ["H2.1", "H2.2", "H0.1", "H0.2", "H1"]:
        if s.startswith(code):
            return code
    if "-" in s:
        return s.split("-")[0].strip()
    return "Khác"

@st.cache_data(ttl=120)
def load_data_from_google_sheet(sheet_id=MASTER_DATA_SHEET_ID, sheet_name=TARGET_SHEET_NAME):
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    try:
        df = pd.read_csv(url)
        cols_to_keep = [c for c in df.columns if not c.startswith("Unnamed")]
        return df[cols_to_keep], None
    except Exception as e:
        return None, str(e)

def normalize_dataset(df):
    if df is None or df.empty:
        return df

    df.columns = [str(c).strip() for c in df.columns]

    df["QUARTER"] = df["WEEK"].apply(get_quarter_from_week)
    df["TAG_CODE"] = df["TAG"].apply(extract_tag_code)

    if "THÁNG_CÒN_LẠI" in df.columns:
        df["THÁNG_CÒN_LẠI_NUM"] = df["THÁNG_CÒN_LẠI"].apply(parse_decimal_vn)
    else:
        df["THÁNG_CÒN_LẠI_NUM"] = 0.0

    if "MÔN_HOÀN_THÀNH / TỔNG" in df.columns:
        parsed_c = df["MÔN_HOÀN_THÀNH / TỔNG"].apply(parse_fraction)
        df["MÔN_ĐÃ_HOÀN_THÀNH"] = [p[0] for p in parsed_c]
        df["TỔNG_SỐ_MÔN"] = [p[1] for p in parsed_c]
        df["SỐ_MÔN_CÒN_LẠI"] = df["TỔNG_SỐ_MÔN"] - df["MÔN_ĐÃ_HOÀN_THÀNH"]
        df["TỶ_LỆ_XONG_MÔN"] = np.where(
            df["TỔNG_SỐ_MÔN"] > 0,
            (df["MÔN_ĐÃ_HOÀN_THÀNH"] / df["TỔNG_SỐ_MÔN"]) * 100,
            0.0
        )
    else:
        df["MÔN_ĐÃ_HOÀN_THÀNH"] = 0
        df["TỔNG_SỐ_MÔN"] = 0
        df["SỐ_MÔN_CÒN_LẠI"] = 0
        df["TỶ_LỆ_XONG_MÔN"] = 0.0

    weekly_numeric_cols = [
        "TOTAL_ACTIVITY", "LEARNING_ACCESS", "MENTOR_SUPPORT",
        "ACADEMIC_OUTPUT", "XP_TĂNG_TRONG_TUẦN", "INACTIVITY_WEEKS"
    ]
    for c in weekly_numeric_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
        else:
            df[c] = 0

    academic_types = ["QUIZ", "LAB", "ASSIGNMENT", "PROGRESS_TEST", "FINAL_EXAM", "ĐỒ_ÁN"]
    for col in academic_types:
        if col in df.columns:
            df[col] = df[col].fillna("-").astype(str).str.strip()
            parsed = df[col].apply(parse_fraction)
            df[f"{col}_DONE"] = [p[0] for p in parsed]
            df[f"{col}_TOTAL"] = [p[1] for p in parsed]
        else:
            df[col] = "-"
            df[f"{col}_DONE"] = 0
            df[f"{col}_TOTAL"] = 0

    def evaluate_completion(row):
        rem_c = row["SỐ_MÔN_CÒN_LẠI"]
        tot_c = row["TỔNG_SỐ_MÔN"]
        m_left = row["THÁNG_CÒN_LẠI_NUM"]
        act = row["TOTAL_ACTIVITY"]
        inact = row["INACTIVITY_WEEKS"]

        if tot_c > 0 and rem_c <= 0:
            return "Đã hoàn thành 100% môn"
        
        pace = rem_c / max(m_left, 0.1)

        if rem_c <= 2 and m_left >= 1.0 and inact <= 1:
            return "🌟 Khả năng hoàn thành RẤT CAO (Sắp về đích)"
        elif rem_c <= 3 and m_left >= 1.5 and act > 0:
            return "🌟 Khả năng hoàn thành RẤT CAO (Sắp về đích)"
        elif pace <= 1.0 and inact == 0:
            return "✅ Đang On-Track (Tiến độ tốt)"
        elif rem_c <= 3 and (m_left < 1.5 or inact >= 1):
            return "⚡ Tiềm năng cao - Cần Push gấp để về đích"
        elif pace <= 1.5 and inact <= 2:
            return "⏳ Cần đẩy nhanh tiến độ"
        else:
            return "🚨 Nguy cơ quá hạn (Cần can thiệp)"

    df["KHẢ_NĂNG_HOÀN_THÀNH"] = df.apply(evaluate_completion, axis=1)

    for c in ["WEEK", "MSSV", "FULL_NAME", "EMAIL", "TAG", "HANNAH", "CHƯƠNG_TRÌNH", "MÔN_ĐANG_HỌC", "STUDENT_STATUS", "RISK_LEVEL", "ROOT_CAUSE", "ACTION_SUGGESTION"]:
        if c in df.columns:
            df[c] = df[c].fillna("N/A").astype(str).str.strip()

    return df

# ==================== PHẦN HEADER & GIẢI THÍCH NGHIỆP VỤ ====================
st.title("🎯 Dashboard Quản Trị Đào Tạo & Action Tracking")
st.caption("Giám sát Quy mô Học viên, Quản trị Tiến độ Tag H1 & Vòng Lặp Đo Lường Hành Động Can Thiệp (Closed-Loop Action Tracking).")

# ==================== SIDEBAR: BỘ LỌC DỮ LIỆU ====================
st.sidebar.header("⚙️ Nguồn Dữ Liệu Real-Time")

col_rf1, col_rf2 = st.sidebar.columns([3, 2])
with col_rf1:
    if st.button("🔄 Làm mới dữ liệu", help="Cập nhật trực tiếp dữ liệu mới nhất từ Google Sheets"):
        st.cache_data.clear()
        st.rerun()

with st.spinner("Đang tải dữ liệu từ Google Sheets Master Data..."):
    df_raw, load_err = load_data_from_google_sheet(MASTER_DATA_SHEET_ID, TARGET_SHEET_NAME)

if df_raw is not None and not df_raw.empty:
    st.sidebar.success(f"✅ Đã kết nối Master Data: **{len(df_raw):,}** dòng")
else:
    st.sidebar.error("⚠️ Không thể tải dữ liệu từ Google Sheets.")
    st.stop()

df_clean = normalize_dataset(df_raw)

# Danh sách tất cả các tuần sắp xếp theo thứ tự thời gian
all_sorted_weeks = sorted(df_clean["WEEK"].unique().tolist())

st.sidebar.markdown("---")
st.sidebar.header("🔍 Bộ Lọc Điều Hành")

# 1. BỘ LỌC THEO QUÝ (QUARTER)
available_quarters = sorted(df_clean["QUARTER"].unique().tolist(), reverse=True)
selected_quarter = st.sidebar.selectbox(
    "1. Chọn Quý (QUARTER):",
    ["Tất cả các Quý"] + available_quarters,
    index=1 if len(available_quarters) > 0 else 0,
    help="Lọc dữ liệu tổng hợp theo Quý báo cáo"
)

df_quarter = df_clean.copy()
if selected_quarter != "Tất cả các Quý":
    df_quarter = df_quarter[df_quarter["QUARTER"] == selected_quarter]

# 2. BỘ LỌC THEO TUẦN (WEEK)
weeks_in_quarter = sorted(df_quarter["WEEK"].unique().tolist(), reverse=True)
selected_week = st.sidebar.selectbox(
    "2. Tuần báo cáo (WEEK):",
    ["Tất cả tuần trong Quý"] + weeks_in_quarter,
    index=1 if len(weeks_in_quarter) > 0 else 0,
    help="Mặc định tuần mới nhất đã cập nhật"
)

df_base = df_quarter.copy()
if selected_week != "Tất cả tuần trong Quý":
    df_base = df_base[df_base["WEEK"] == selected_week]

# Xác định tuần trước đó để so sánh chuyển biến (W_prev)
prev_week_name = None
if selected_week != "Tất cả tuần trong Quý" and selected_week in all_sorted_weeks:
    curr_idx = all_sorted_weeks.index(selected_week)
    if curr_idx > 0:
        prev_week_name = all_sorted_weeks[curr_idx - 1]

# 3. BỘ LỌC HANNAH
all_hannahs = sorted([h for h in df_base["HANNAH"].unique().tolist() if h and h != "N/A"])
selected_hannahs = st.sidebar.multiselect("3. Hannah phụ trách:", all_hannahs, default=all_hannahs)

# 4. BỘ LỌC CHƯƠNG TRÌNH
all_progs = sorted([p for p in df_base["CHƯƠNG_TRÌNH"].unique().tolist() if p and p != "N/A"])
selected_progs = st.sidebar.multiselect("4. Chương trình học:", all_progs, default=all_progs)

if selected_hannahs:
    df_base = df_base[df_base["HANNAH"].isin(selected_hannahs)]
if selected_progs:
    df_base = df_base[df_base["CHƯƠNG_TRÌNH"].isin(selected_progs)]

# TẬP DỮ LIỆU CHUYÊN SÂU: CHỈ LẤY TAG H1
df_h1 = df_base[df_base["TAG_CODE"] == "H1"].copy()

scope_option = st.sidebar.radio(
    "5. Phạm vi phân tích chuyên sâu (Tab 2, 3, 4, 5):",
    ["Chỉ phân tích Tag H1 (Khuyên dùng)", "Toàn bộ học viên (Mọi Tag)"],
    index=0
)
df_deep = df_h1 if scope_option.startswith("Chỉ phân tích Tag H1") else df_base

# Tải cơ sở dữ liệu ghi chú
notes_db = load_notes_db()

# ==================== TÍNH TOÁN ĐO LƯỜNG CHUYỂN BIẾN (W_curr vs W_prev) ====================
# Chuẩn bị DataFrame của tuần trước để đối soát
df_prev_lookup = None
if prev_week_name:
    df_prev_full = df_clean[df_clean["WEEK"] == prev_week_name]
    if scope_option.startswith("Chỉ phân tích Tag H1"):
        df_prev_full = df_prev_full[df_prev_full["TAG_CODE"] == "H1"]
    df_prev_lookup = df_prev_full.set_index("MSSV")

# Hàm gán nhãn chuyển biến thực tế
def determine_recovery_status(row, df_prev):
    if df_prev is None:
        return "⚪ Tuần đầu tiên (Chưa có tuần đối soát)"
    mssv = row.get("MSSV", "")
    if mssv not in df_prev.index:
        return "⚪ Học viên mới cập nhật"
    
    prev_row = df_prev.loc[mssv]
    if isinstance(prev_row, pd.DataFrame):
        prev_row = prev_row.iloc[0]
        
    p_risk = str(prev_row.get("RISK_LEVEL", "")).upper()
    c_risk = str(row.get("RISK_LEVEL", "")).upper()
    c_act = int(row.get("TOTAL_ACTIVITY", 0))

    if p_risk in ["HIGH", "CRITICAL"]:
        if c_act > 0 or c_risk in ["LOW", "MEDIUM"]:
            return "🟢 Đã cải thiện (Quay lại học)"
        else:
            return "🔴 Vẫn bất động (Chưa chuyển biến)"
    else:
        if c_risk in ["HIGH", "CRITICAL"]:
            return "⚠️ Mới phát sinh nguy cơ"
        else:
            return "✅ Duy trì học tập an toàn"

# Gắn cột Chuyển biến học tập và Lịch sử Action tuần trước vào df_deep
if not df_deep.empty:
    df_deep["CHUYỂN_BIẾN_TUẦN_NÀY"] = df_deep.apply(
        lambda r: determine_recovery_status(r, df_prev_lookup), axis=1
    )
    df_deep["ACTION_TUẦN_TRƯỚC"] = df_deep["MSSV"].apply(
        lambda mssv: get_previous_action_note(notes_db, mssv, prev_week_name)
    )
else:
    df_deep["CHUYỂN_BIẾN_TUẦN_NÀY"] = "N/A"
    df_deep["ACTION_TUẦN_TRƯỚC"] = "N/A"

# ==================== BANNER LÀM RÕ CHU TRÌNH ĐO LƯỜNG ACTION ====================
with st.expander("💡 **HƯỚNG DẪN: CƠ CHẾ ĐO LƯỜNG ACTION W41 ➔ W42 (CLOSED-LOOP TRACKING)** — Nhấp để xem", expanded=False):
    st.markdown(f"""
    ### Chu Trình Đo Lường Giữa Các Tuần ({f'{prev_week_name} ➔ {selected_week}' if prev_week_name else 'Tuần mới nhất'}):
    1. **Kế thừa ghi chú:** Khi Hannah mở tuần mới, cột **"Action tuần trước"** sẽ tự động hiển thị lại ghi chú và trạng thái đã trao đổi ở tuần trước để đối chiếu cam kết.
    2. **Đo lường chuyển biến tự động:** Hệ thống so sánh dữ liệu thực tế giữa tuần trước và tuần này:
       - **🟢 Đã cải thiện (Quay lại học):** Học viên tuần trước ở mức High/Critical nhưng tuần này đã phát sinh hoạt động học tập (`Activity > 0`) hoặc giảm rủi ro về Low/Medium.
       - **🔴 Vẫn bất động (Chưa chuyển biến):** Học viên tuần trước mức High/Critical và tuần này vẫn tiếp tục không học (`Activity = 0`) ➔ Cần nâng mức can thiệp (gọi điện phụ huynh, báo BQL).
       - **⚠️ Mới phát sinh nguy cơ:** Học viên tuần trước an toàn nhưng tuần này bắt đầu dừng học.
    3. **Chỉ số hiệu quả Hannah (Tab 3):**
       - **Tỷ lệ Phủ Action (% Covered):** % Học viên High/Critical đã được Hannah lên kế hoạch can thiệp.
       - **Tỷ lệ Can thiệp Thành công (% Recovery Rate):** % Học viên đã thực sự quay lại học tập sau khi được Hannah can thiệp.
    """)

# Bảng màu rủi ro
risk_color_map = {"LOW": "#28a745", "MEDIUM": "#ffc107", "HIGH": "#fd7e14", "CRITICAL": "#dc3545"}

# ==================== 5 TABS GIAO DIỆN CHÍNH ====================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📌 1. Tổng Quan Quy Mô & Phân Bổ Tag",
    "🎯 2. Tiến Độ & Danh Sách Push Hoàn Thành (H1)",
    "👩‍💼 3. Hiệu Suất & Tỷ Lệ Cứu Nguy Hannah (H1)",
    "📚 4. Sản Phẩm Học Thuật & Mentor Support",
    "🚨 5. Action Board Đối Soát Chuyển Biến (H1)"
])

# =========================================================================
# TAB 1: TỔNG QUAN QUY MÔ & PHÂN BỔ TAG
# =========================================================================
with tab1:
    st.subheader(f"Chỉ Số Điều Hành Tổng Thể — Quy Mô Toàn Bộ Học Viên {f'({selected_week})' if selected_week != 'Tất cả tuần trong Quý' else f'({selected_quarter})'}")

    total_active_all = len(df_base)
    tag_counts = df_base["TAG_CODE"].value_counts().to_dict()

    cnt_h1 = tag_counts.get("H1", 0)
    cnt_h21 = tag_counts.get("H2.1", 0)
    cnt_h22 = tag_counts.get("H2.2", 0)
    cnt_h01 = tag_counts.get("H0.1", 0)
    cnt_h02 = tag_counts.get("H0.2", 0)

    pct_h1 = (cnt_h1 / total_active_all * 100) if total_active_all > 0 else 0
    pct_h21 = (cnt_h21 / total_active_all * 100) if total_active_all > 0 else 0
    pct_h22 = (cnt_h22 / total_active_all * 100) if total_active_all > 0 else 0
    pct_h01 = (cnt_h01 / total_active_all * 100) if total_active_all > 0 else 0
    pct_h02 = (cnt_h02 / total_active_all * 100) if total_active_all > 0 else 0

    st.markdown("##### 👥 Phân Rã Tổng Học Viên Active Theo Từng Tag (W41 / Quý)")
    kp_all, kp_h1, kp_h21, kp_h22, kp_h01, kp_h02 = st.columns(6)

    with kp_all:
        st.markdown(f"""
        <div class="metric-card" style="border-left-color: #2b8a3e;">
            <div class="metric-title">🌐 TỔNG HV ACTIVE</div>
            <div class="metric-value">{total_active_all:,}</div>
            <div class="metric-sub">Bao gồm tất cả các Tag</div>
        </div>
        """, unsafe_allow_html=True)

    with kp_h1:
        st.markdown(f"""
        <div class="metric-card" style="border-left-color: #1c7ed6;">
            <div class="metric-title" style="color: #1c7ed6;">🔵 TAG H1 (CHÍNH)</div>
            <div class="metric-value" style="color: #1c7ed6;">{cnt_h1:,}</div>
            <div class="metric-sub"><b>{pct_h1:.1f}%</b> • Đang hỗ trợ</div>
        </div>
        """, unsafe_allow_html=True)

    with kp_h21:
        st.markdown(f"""
        <div class="metric-card" style="border-left-color: #0ca678;">
            <div class="metric-title" style="color: #0ca678;">🟢 TAG H2.1</div>
            <div class="metric-value">{cnt_h21:,}</div>
            <div class="metric-sub"><b>{pct_h21:.1f}%</b> • Học kiến thức</div>
        </div>
        """, unsafe_allow_html=True)

    with kp_h22:
        st.markdown(f"""
        <div class="metric-card" style="border-left-color: #f59f00;">
            <div class="metric-title" style="color: #f59f00;">🟡 TAG H2.2</div>
            <div class="metric-value">{cnt_h22:,}</div>
            <div class="metric-sub"><b>{pct_h22:.1f}%</b> • Tạm dừng học</div>
        </div>
        """, unsafe_allow_html=True)

    with kp_h01:
        st.markdown(f"""
        <div class="metric-card" style="border-left-color: #f03e3e;">
            <div class="metric-title" style="color: #f03e3e;">🔴 TAG H0.1</div>
            <div class="metric-value">{cnt_h01:,}</div>
            <div class="metric-sub"><b>{pct_h01:.1f}%</b> • Mất liên lạc</div>
        </div>
        """, unsafe_allow_html=True)

    with kp_h02:
        st.markdown(f"""
        <div class="metric-card" style="border-left-color: #868e96;">
            <div class="metric-title" style="color: #495057;">⚪ TAG H0.2</div>
            <div class="metric-value">{cnt_h02:,}</div>
            <div class="metric-sub"><b>{pct_h02:.1f}%</b> • Xin ngừng học</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    c1, c2 = st.columns([3, 2])
    with c1:
        st.markdown("##### 📊 Xu Hướng Số Lượng Học Viên Từng Tag Qua Các Tuần")
        df_tag_trend = df_quarter.groupby(["WEEK", "TAG_CODE"]).size().reset_index(name="SỐ_LƯỢNG")
        fig_tt = px.bar(
            df_tag_trend,
            x="WEEK",
            y="SỐ_LƯỢNG",
            color="TAG_CODE",
            color_discrete_map={
                "H1": "#1c7ed6", "H2.1": "#0ca678", "H2.2": "#f59f00",
                "H0.1": "#f03e3e", "H0.2": "#868e96", "Khác": "#adb5bd"
            },
            barmode="stack",
            height=350
        )
        fig_tt.update_layout(margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig_tt, use_container_width=True)

    with c2:
        st.markdown("##### 🍩 Tỷ Trọng Phân Bổ Học Viên Theo Tag")
        tag_pie_data = pd.DataFrame({
            "TAG": ["H1 (Đang hỗ trợ)", "H2.1 (Học kiến thức)", "H2.2 (Tạm dừng)", "H0.1 (Mất liên lạc)", "H0.2 (Xin ngừng)"],
            "COUNT": [cnt_h1, cnt_h21, cnt_h22, cnt_h01, cnt_h02]
        })
        fig_tpie = px.pie(
            tag_pie_data,
            names="TAG",
            values="COUNT",
            color="TAG",
            color_discrete_map={
                "H1 (Đang hỗ trợ)": "#1c7ed6", "H2.1 (Học kiến thức)": "#0ca678",
                "H2.2 (Tạm dừng)": "#f59f00", "H0.1 (Mất liên lạc)": "#f03e3e",
                "H0.2 (Xin ngừng)": "#868e96"
            },
            hole=0.45,
            height=350
        )
        fig_tpie.update_traces(textposition='inside', textinfo='percent+label')
        fig_tpie.update_layout(margin=dict(l=10, r=10, t=10, b=10), showlegend=False)
        st.plotly_chart(fig_tpie, use_container_width=True)

# =========================================================================
# TAB 2: TIẾN ĐỘ & DANH SÁCH PUSH HOÀN THÀNH MÔN (H1)
# =========================================================================
with tab2:
    st.subheader("🎯 Đánh Giá Tiến Độ & Danh Sách Học Viên H1 Tiềm Năng Hoàn Thành")
    st.caption("Dựa trên: **Số môn còn lại**, **Thời gian còn lại (tháng)**, và **Tần suất Activity hàng tuần**.")

    tot_h1 = len(df_deep)
    comp_dist = df_deep["KHẢ_NĂNG_HOÀN_THÀNH"].value_counts().to_dict()
    n_very_high = comp_dist.get("🌟 Khả năng hoàn thành RẤT CAO (Sắp về đích)", 0)
    n_push_urg = comp_dist.get("⚡ Tiềm năng cao - Cần Push gấp để về đích", 0)
    n_ontrack = comp_dist.get("✅ Đang On-Track (Tiến độ tốt)", 0)
    n_delay_risk = comp_dist.get("🚨 Nguy cơ quá hạn (Cần can thiệp)", 0)

    pct_very_high = (n_very_high / tot_h1 * 100) if tot_h1 > 0 else 0.0
    pct_push_urg = (n_push_urg / tot_h1 * 100) if tot_h1 > 0 else 0.0
    pct_ontrack = (n_ontrack / tot_h1 * 100) if tot_h1 > 0 else 0.0
    pct_delay_risk = (n_delay_risk / tot_h1 * 100) if tot_h1 > 0 else 0.0

    p1, p2, p3, p4 = st.columns(4)
    with p1:
        st.markdown(f"""
        <div class="metric-card" style="border-left-color: #2b8a3e;">
            <div class="metric-title" style="color: #2b8a3e;">🌟 SẮP VỀ ĐÍCH (RẤT CAO)</div>
            <div class="metric-value" style="color: #2b8a3e;">{n_very_high} HV <span style="font-size: 16px; font-weight: normal; color: #2b8a3e;">({pct_very_high:.1f}%)</span></div>
            <div class="metric-sub"><b>{pct_very_high:.1f}%</b> so với tổng H1 • Còn ≤ 3 môn</div>
        </div>
        """, unsafe_allow_html=True)

    with p2:
        st.markdown(f"""
        <div class="metric-card" style="border-left-color: #f59f00;">
            <div class="metric-title" style="color: #f59f00;">⚡ CẦN PUSH GẤP VỀ ĐÍCH</div>
            <div class="metric-value" style="color: #f59f00;">{n_push_urg} HV <span style="font-size: 16px; font-weight: normal; color: #f59f00;">({pct_push_urg:.1f}%)</span></div>
            <div class="metric-sub"><b>{pct_push_urg:.1f}%</b> so với tổng H1 • Cần push gấp</div>
        </div>
        """, unsafe_allow_html=True)

    with p3:
        st.markdown(f"""
        <div class="metric-card" style="border-left-color: #1c7ed6;">
            <div class="metric-title" style="color: #1c7ed6;">✅ ĐANG ON-TRACK</div>
            <div class="metric-value">{n_ontrack} HV <span style="font-size: 16px; font-weight: normal; color: #1c7ed6;">({pct_ontrack:.1f}%)</span></div>
            <div class="metric-sub"><b>{pct_ontrack:.1f}%</b> so với tổng H1 • Tiến độ đều</div>
        </div>
        """, unsafe_allow_html=True)

    with p4:
        st.markdown(f"""
        <div class="metric-card" style="border-left-color: #dc3545;">
            <div class="metric-title" style="color: #dc3545;">🚨 NGUY CƠ QUÁ HẠN</div>
            <div class="metric-value" style="color: #dc3545;">{n_delay_risk} HV <span style="font-size: 16px; font-weight: normal; color: #dc3545;">({pct_delay_risk:.1f}%)</span></div>
            <div class="metric-sub"><b>{pct_delay_risk:.1f}%</b> so với tổng H1 • Cần can thiệp</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    sc_col1, sc_col2 = st.columns([3, 2])
    with sc_col1:
        st.markdown("##### 📊 Tiến Độ Hoàn Thành: Số Môn Còn Lại vs Thời Gian Còn Lại (Dạng Cột)")

        # Phân nhóm số môn còn lại
        def group_courses_bar(c):
            if c <= 0:
                return "0 môn (Xong)"
            elif c == 1:
                return "1 môn"
            elif c == 2:
                return "2 môn"
            elif c == 3:
                return "3 môn"
            elif c <= 5:
                return "4 - 5 môn"
            elif c <= 10:
                return "6 - 10 môn"
            else:
                return "> 10 môn"

        # Phân nhóm thời gian còn lại (tháng)
        def group_months_bar(m):
            if m < 1.0:
                return "< 1 tháng (Khẩn cấp)"
            elif m <= 3.0:
                return "1 - 3 tháng"
            elif m <= 6.0:
                return "3 - 6 tháng"
            elif m <= 12.0:
                return "6 - 12 tháng"
            else:
                return "> 12 tháng"

        df_bar_prog = df_deep.copy()
        df_bar_prog["NHÓM_MÔN"] = df_bar_prog["SỐ_MÔN_CÒN_LẠI"].apply(group_courses_bar)
        df_bar_prog["NHÓM_THÁNG"] = df_bar_prog["THÁNG_CÒN_LẠI_NUM"].apply(group_months_bar)

        course_order = ["0 môn (Xong)", "1 môn", "2 môn", "3 môn", "4 - 5 môn", "6 - 10 môn", "> 10 môn"]
        month_order = ["< 1 tháng (Khẩn cấp)", "1 - 3 tháng", "3 - 6 tháng", "6 - 12 tháng", "> 12 tháng"]

        bar_summary = df_bar_prog.groupby(["NHÓM_MÔN", "NHÓM_THÁNG"]).size().reset_index(name="SỐ_HỌC_VIÊN")

        fig_bar_prog = px.bar(
            bar_summary,
            x="NHÓM_MÔN",
            y="SỐ_HỌC_VIÊN",
            color="NHÓM_THÁNG",
            color_discrete_map={
                "< 1 tháng (Khẩn cấp)": "#dc3545",
                "1 - 3 tháng": "#fd7e14",
                "3 - 6 tháng": "#ffc107",
                "6 - 12 tháng": "#74c0fc",
                "> 12 tháng": "#1c7ed6"
            },
            category_orders={"NHÓM_MÔN": course_order, "NHÓM_THÁNG": month_order},
            labels={"NHÓM_MÔN": "Số môn còn lại", "SỐ_HỌC_VIÊN": "Số học viên", "NHÓM_THÁNG": "Thời gian còn lại"},
            barmode="stack",
            height=370
        )
        fig_bar_prog.update_layout(
            margin=dict(l=10, r=10, t=10, b=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_bar_prog, use_container_width=True)
        st.caption("💡 **Cột 1, 2, 3 môn** thể hiện các học viên **sắp về đích**; Màu đỏ & cam (< 3 tháng) là nhóm **cần Hannah push gấp** để thi hoàn thành môn.")

    with sc_col2:
        st.markdown("##### 🍩 Phân Bổ Khả Năng Hoàn Thành Của Học Viên H1")
        df_comp_chart = df_deep["KHẢ_NĂNG_HOÀN_THÀNH"].value_counts().reset_index()
        df_comp_chart.columns = ["NHÓM", "SỐ_LƯỢNG"]
        fig_comp_pie = px.pie(
            df_comp_chart,
            names="NHÓM",
            values="SỐ_LƯỢNG",
            hole=0.45,
            height=370
        )
        fig_comp_pie.update_traces(textposition='inside', textinfo='percent+label')
        fig_comp_pie.update_layout(margin=dict(l=10, r=10, t=10, b=10), showlegend=False)
        st.plotly_chart(fig_comp_pie, use_container_width=True)

    st.markdown("---")

    # BẢNG DANH SÁCH PUSH HOÀN THÀNH
    st.subheader("📋 Danh Sách Học Viên Tiềm Năng Hoàn Thành — Hannah Cần Tập Trung Push")
    target_comp_groups = [
        "🌟 Khả năng hoàn thành RẤT CAO (Sắp về đích)",
        "⚡ Tiềm năng cao - Cần Push gấp để về đích",
        "✅ Đang On-Track (Tiến độ tốt)"
    ]

    pf1, pf2 = st.columns([2, 1])
    with pf1:
        sel_comp_filter = st.multiselect(
            "Lọc nhóm khả năng hoàn thành:",
            target_comp_groups + ["🚨 Nguy cơ quá hạn (Cần can thiệp)", "⏳ Cần đẩy nhanh tiến độ", "Đã hoàn thành 100% môn"],
            default=[
                "🌟 Khả năng hoàn thành RẤT CAO (Sắp về đích)",
                "⚡ Tiềm năng cao - Cần Push gấp để về đích"
            ]
        )
    with pf2:
        search_push = st.text_input("🔍 Tìm MSSV hoặc tên học viên push:", placeholder="Nhập tên hoặc MSSV...")

    df_push_display = df_deep[df_deep["KHẢ_NĂNG_HOÀN_THÀNH"].isin(sel_comp_filter)].copy()
    if search_push:
        q = search_push.strip().lower()
        df_push_display = df_push_display[
            df_push_display["MSSV"].str.lower().str.contains(q, na=False) |
            df_push_display["FULL_NAME"].str.lower().str.contains(q, na=False)
        ]

    df_push_display = df_push_display.sort_values(by=["SỐ_MÔN_CÒN_LẠI", "TOTAL_ACTIVITY"], ascending=[True, False])

    st.markdown(f"Có **{len(df_push_display):,}** học viên trong danh sách push trọng điểm:")

    push_columns = [
        "WEEK", "MSSV", "FULL_NAME", "HANNAH", "CHƯƠNG_TRÌNH", "MÔN_ĐANG_HỌC",
        "MÔN_HOÀN_THÀNH / TỔNG", "SỐ_MÔN_CÒN_LẠI", "THÁNG_CÒN_LẠI", "TOTAL_ACTIVITY",
        "KHẢ_NĂNG_HOÀN_THÀNH", "ROOT_CAUSE", "ACTION_SUGGESTION"
    ]
    valid_push_cols = [c for c in push_columns if c in df_push_display.columns]

    st.dataframe(
        df_push_display[valid_push_cols],
        use_container_width=True,
        hide_index=True,
        column_config={
            "WEEK": st.column_config.TextColumn("Tuần", width="small"),
            "MSSV": st.column_config.TextColumn("MSSV", width="small"),
            "FULL_NAME": st.column_config.TextColumn("Họ và Tên", width="medium"),
            "HANNAH": st.column_config.TextColumn("Hannah", width="small"),
            "SỐ_MÔN_CÒN_LẠI": st.column_config.NumberColumn("Môn Còn Lại", width="small"),
            "THÁNG_CÒN_LẠI": st.column_config.TextColumn("Tháng Còn Lại", width="small"),
            "TOTAL_ACTIVITY": st.column_config.NumberColumn("Activity Tuần", width="small"),
            "KHẢ_NĂNG_HOÀN_THÀNH": st.column_config.TextColumn("Đánh Giá Hoàn Thành", width="medium")
        }
    )

    push_excel_buf = io.BytesIO()
    with pd.ExcelWriter(push_excel_buf, engine="openpyxl") as writer:
        df_push_display[valid_push_cols].to_excel(writer, sheet_name="Danh_Sach_Push_Hoan_Thanh", index=False)
    push_excel_data = push_excel_buf.getvalue()

    st.download_button(
        label="📥 Tải Danh Sách Học Viên Cần Push (Excel)",
        data=push_excel_data,
        file_name=f"Danh_Sach_Push_Hoan_Thanh_H1_{selected_week if selected_week != 'Tất cả tuần trong Quý' else selected_quarter}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# =========================================================================
# TAB 3: HIỆU SUẤT & TỶ LỆ CỨU NGUY HANNAH (H1) — ĐO LƯỜNG HIỆU QUẢ ACTION
# =========================================================================
with tab3:
    st.subheader(f"Báo Cáo Hiệu Suất & Tỷ Lệ Can Thiệp Thành Công Của Hannah (H1) {f'({prev_week_name} ➔ {selected_week})' if prev_week_name else ''}")
    st.caption("Đo lường năng lực thực chất: **Tỷ lệ Phủ Action** và **Tỷ lệ Cứu nguy thành công (% Recovery Rate)** sau khi Hannah can thiệp.")

    hannah_stats_list = []
    for h_name, grp in df_deep.groupby("HANNAH"):
        tot = len(grp)
        low_r = len(grp[grp["RISK_LEVEL"] == "LOW"])
        crit_r = len(grp[grp["RISK_LEVEL"] == "CRITICAL"])
        urgent = len(grp[grp["RISK_LEVEL"].isin(["HIGH", "CRITICAL"])])

        low_ratio = (low_r / tot * 100) if tot > 0 else 0
        crit_ratio = (crit_r / tot * 100) if tot > 0 else 0
        safe_control_ratio = max(0, 100 - crit_ratio)

        # Học viên có hoạt động tuần
        active_cnt = len(grp[grp["TOTAL_ACTIVITY"] > 0])
        active_ratio = (active_cnt / tot * 100) if tot > 0 else 0

        # Đo lường hiệu quả can thiệp tuần này so với tuần trước (W_prev -> W_curr)
        # Đếm số học viên được gán nhãn Đã cải thiện
        cnt_improved = len(grp[grp["CHUYỂN_BIẾN_TUẦN_NÀY"].str.contains("Đã cải thiện", na=False)])
        cnt_stagnant = len(grp[grp["CHUYỂN_BIẾN_TUẦN_NÀY"].str.contains("Vẫn bất động", na=False)])
        cnt_new_risk = len(grp[grp["CHUYỂN_BIẾN_TUẦN_NÀY"].str.contains("Mới phát sinh", na=False)])

        # Tỷ lệ can thiệp thành công (% Recovery Rate)
        total_at_risk_prev = cnt_improved + cnt_stagnant
        recovery_rate = (cnt_improved / total_at_risk_prev * 100) if total_at_risk_prev > 0 else 0.0

        # Tỷ lệ phủ Action (% Covered): Học viên nguy cơ đã có ghi chú action
        urgent_grp = grp[grp["RISK_LEVEL"].isin(["HIGH", "CRITICAL"])]
        covered_count = 0
        for _, u_row in urgent_grp.iterrows():
            k_act = f"{selected_week}_{u_row.get('MSSV', '')}"
            if k_act in notes_db and notes_db[k_act].get("note", "").strip():
                covered_count += 1
        coverage_rate = (covered_count / len(urgent_grp) * 100) if len(urgent_grp) > 0 else 100.0

        # Điểm hiệu suất tổng hợp có tính thêm tỷ lệ can thiệp thành công
        score = round((low_ratio * 0.35) + (active_ratio * 0.30) + (safe_control_ratio * 0.20) + (recovery_rate * 0.15), 1)

        hannah_stats_list.append({
            "HANNAH": h_name,
            "ĐIỂM HIỆU SUẤT": score,
            "TỔNG HV H1": tot,
            "TỶ LỆ AN TOÀN (%)": round(low_ratio, 1),
            "HV NGUY CƠ (HIGH/CRIT)": urgent,
            "🟢 CỨU NGUY THÀNH CÔNG": cnt_improved,
            "🔴 VẪN BẤT ĐỘNG": cnt_stagnant,
            "TỶ LỆ CAN THIỆP THÀNH CÔNG (%)": round(recovery_rate, 1),
            "TỶ LỆ PHỦ ACTION (%)": round(coverage_rate, 1),
            "TB ACTIVITY / HV": round(grp["TOTAL_ACTIVITY"].mean(), 2)
        })

    df_h_score = pd.DataFrame(hannah_stats_list).sort_values("ĐIỂM HIỆU SUẤT", ascending=False).reset_index(drop=True)

    st.dataframe(
        df_h_score,
        use_container_width=True,
        column_config={
            "ĐIỂM HIỆU SUẤT": st.column_config.ProgressColumn("Điểm Hiệu Suất", format="%.1f", min_value=0, max_value=100),
            "TỶ LỆ CAN THIỆP THÀNH CÔNG (%)": st.column_config.NumberColumn("Tỷ lệ Cứu Nguy (%)", format="%.1f%%", help="Tỷ lệ học viên quay lại học sau khi Hannah can thiệp"),
            "TỶ LỆ PHỦ ACTION (%)": st.column_config.NumberColumn("Tỷ lệ Phủ Action (%)", format="%.1f%%", help="Tỷ lệ học viên nguy cơ đã được Hannah lập kế hoạch ghi chú"),
            "TỶ LỆ AN TOÀN (%)": st.column_config.NumberColumn("Tỷ lệ An toàn (%)", format="%.1f%%")
        },
        hide_index=True
    )

    st.markdown("---")
    hc1, hc2 = st.columns(2)

    with hc1:
        st.markdown(f"##### 📈 So Sánh Tỷ Lệ Can Thiệp Thành Công (% Recovery Rate)")
        fig_recov = px.bar(
            df_h_score,
            x="HANNAH",
            y="TỶ LỆ CAN THIỆP THÀNH CÔNG (%)",
            color="TỶ LỆ CAN THIỆP THÀNH CÔNG (%)",
            color_continuous_scale="Greens",
            text="TỶ LỆ CAN THIỆP THÀNH CÔNG (%)",
            height=340
        )
        fig_recov.update_layout(margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig_recov, use_container_width=True)

    with hc2:
        st.markdown("##### 🤝 So Sánh Lượt Mentor Support & Sản Phẩm Học Thuật Tuần")
        fig_mentor_comp = px.bar(
            df_h_score,
            x="HANNAH",
            y=["🟢 CỨU NGUY THÀNH CÔNG", "🔴 VẪN BẤT ĐỘNG"],
            barmode="stack",
            color_discrete_map={"🟢 CỨU NGUY THÀNH CÔNG": "#2b8a3e", "🔴 VẪN BẤT ĐỘNG": "#dc3545"},
            height=340
        )
        fig_mentor_comp.update_layout(
            margin=dict(l=10, r=10, t=10, b=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_mentor_comp, use_container_width=True)

# =========================================================================
# TAB 4: SẢN PHẨM HỌC THUẬT & MENTOR (ĐỦ 5 LOẠI)
# =========================================================================
with tab4:
    st.subheader("📚 Chi Tiết Sản Phẩm Học Thuật Hoàn Thành & Tương Tác Mentor")
    st.caption("Bao gồm đầy đủ 5 sản phẩm cốt lõi: **QUIZ**, **LAB**, **ASSIGNMENT**, **PROGRESS_TEST**, **FINAL_EXAM**.")

    st.markdown("##### 📝 1. Tổng Sản Phẩm Bài Tập Đã Hoàn Thành (Học viên Tag H1)")
    ac1, ac2, ac3, ac4, ac5 = st.columns(5)
    with ac1:
        st.metric("🧪 QUIZ ĐÃ XONG", f"{int(df_deep['QUIZ_DONE'].sum()):,}", help="Tổng số bài Quiz đã hoàn thành")
    with ac2:
        st.metric("🧪 LAB ĐÃ XONG", f"{int(df_deep['LAB_DONE'].sum()):,}", help="Tổng số bài Lab đã hoàn thành")
    with ac3:
        st.metric("📑 ASSIGNMENT ĐÃ XONG", f"{int(df_deep['ASSIGNMENT_DONE'].sum()):,}", help="Tổng số Assignment đã hoàn thành")
    with ac4:
        st.metric("🎯 PROGRESS TEST", f"{int(df_deep['PROGRESS_TEST_DONE'].sum()):,}", help="Tổng số Progress Test đã hoàn thành")
    with ac5:
        st.metric("🏆 FINAL EXAM", f"{int(df_deep['FINAL_EXAM_DONE'].sum()):,}", help="Tổng số Final Exam đã thi đậu")

    st.markdown("---")

    st.markdown("##### ⚡ 2. Khối Lượng Tương Tác Học Tập Trong Tuần Báo Cáo")
    wk1, wk2, wk3, wk4 = st.columns(4)
    with wk1:
        st.metric("📝 SẢN PHẨM NỘP TUẦN", f"{int(df_deep['ACADEMIC_OUTPUT'].sum()):,}", help="Tổng số bài tập nộp và pass trong tuần")
    with wk2:
        st.metric("🤝 MENTOR SUPPORT TUẦN", f"{int(df_deep['MENTOR_SUPPORT'].sum()):,}", help="Tổng lượt hỏi mentor và book zoom trong tuần")
    with wk3:
        st.metric("🌐 LƯỢT ĐĂNG NHẬP LMS", f"{int(df_deep['LEARNING_ACCESS'].sum()):,}", help="Tổng số lượt vào học hệ thống LMS")
    with wk4:
        st.metric("⚡ XP TĂNG TRONG TUẦN", f"{int(df_deep['XP_TĂNG_TRONG_TUẦN'].sum()):,}", help="Tổng XP toàn bộ học viên H1 tích lũy thêm")

    st.markdown("---")

    st.markdown("##### 📊 Cơ Cấu 5 Loại Sản Phẩm Học Thuật Tích Lũy Theo Từng Hannah")
    academic_by_h = df_deep.groupby("HANNAH")[
        ["QUIZ_DONE", "LAB_DONE", "ASSIGNMENT_DONE", "PROGRESS_TEST_DONE", "FINAL_EXAM_DONE"]
    ].sum().reset_index()
    academic_by_h = academic_by_h.rename(columns={
        "QUIZ_DONE": "Quiz", "LAB_DONE": "Lab", "ASSIGNMENT_DONE": "Assignment",
        "PROGRESS_TEST_DONE": "Progress Test", "FINAL_EXAM_DONE": "Final Exam"
    })

    ac_melted = academic_by_h.melt(id_vars="HANNAH", var_name="LOẠI_BÀI", value_name="SỐ_LƯỢNG")
    fig_ac_all5 = px.bar(
        ac_melted,
        x="HANNAH",
        y="SỐ_LƯỢNG",
        color="LOẠI_BÀI",
        barmode="stack",
        height=360
    )
    fig_ac_all5.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig_ac_all5, use_container_width=True)

# =========================================================================
# TAB 5: ACTION BOARD ĐỐI SOÁT CHUYỂN BIẾN (H1) — 3 MỤC TIÊU NÂNG CẤP
# =========================================================================
with tab5:
    st.subheader(f"🚨 Action Board Đối Soát Chuyển Biến Học Viên H1 Nguy Cơ Cao {f'({prev_week_name} ➔ {selected_week})' if prev_week_name else ''}")
    st.caption("Tự động hiển thị **Action tuần trước**, đo lường **Chuyển biến học tập thực tế tuần này** và cho phép cập nhật **Action tuần mới**.")

    # Lọc học viên H1 nguy cơ cao (HIGH & CRITICAL)
    df_urgent_h1 = df_deep[df_deep["RISK_LEVEL"].isin(["HIGH", "CRITICAL"])].copy()

    if df_urgent_h1.empty:
        st.success("🎉 Xuất sắc! Không có học viên H1 nào ở mức HIGH hoặc CRITICAL trong phạm vi bộ lọc này.")
    else:
        # Thống kê nhanh chuyển biến của nhóm High/Critical
        cnt_recov = len(df_urgent_h1[df_urgent_h1["CHUYỂN_BIẾN_TUẦN_NÀY"].str.contains("Đã cải thiện", na=False)])
        cnt_stag = len(df_urgent_h1[df_urgent_h1["CHUYỂN_BIẾN_TUẦN_NÀY"].str.contains("Vẫn bất động", na=False)])
        cnt_new = len(df_urgent_h1[df_urgent_h1["CHUYỂN_BIẾN_TUẦN_NÀY"].str.contains("Mới phát sinh", na=False)])

        k1, k2, k3 = st.columns(3)
        with k1:
            st.metric("🟢 ĐÃ CẢI THIỆN / CÓ HỌC LẠI", f"{cnt_recov} HV", help="Học viên đã bắt đầu có hoạt động học tập sau khi được can thiệp")
        with k2:
            st.metric("🔴 VẪN BẤT ĐỘNG (CHƯA CHUYỂN BIẾN)", f"{cnt_stag} HV", delta="- Cần can thiệp cấp cao", delta_color="inverse", help="Học viên vẫn chưa có hoạt động nào trong tuần này")
        with k3:
            st.metric("⚠️ MỚI PHÁT SINH NGUY CƠ", f"{cnt_new} HV", help="Mới rơi vào High/Critical tuần này")

        st.markdown("---")

        # BỘ LỌC NHANH TRÊN ACTION BOARD
        f_col1, f_col2 = st.columns([2, 1])
        with f_col1:
            selected_recovery_filter = st.multiselect(
                "Lọc theo chuyển biến học tập:",
                [
                    "🔴 Vẫn bất động (Chưa chuyển biến)",
                    "⚠️ Mới phát sinh nguy cơ",
                    "🟢 Đã cải thiện (Quay lại học)",
                    "⚪ Học viên mới cập nhật",
                    "⚪ Tuần đầu tiên (Chưa có tuần đối soát)"
                ],
                default=[
                    "🔴 Vẫn bất động (Chưa chuyển biến)",
                    "⚠️ Mới phát sinh nguy cơ",
                    "🟢 Đã cải thiện (Quay lại học)"
                ]
            )
        with f_col2:
            search_act = st.text_input("🔍 Tìm MSSV hoặc tên học viên can thiệp:", placeholder="Nhập tên hoặc MSSV...")

        df_filtered_act = df_urgent_h1[df_urgent_h1["CHUYỂN_BIẾN_TUẦN_NÀY"].isin(selected_recovery_filter)].copy()
        if search_act:
            q_a = search_act.strip().lower()
            df_filtered_act = df_filtered_act[
                df_filtered_act["MSSV"].str.lower().str.contains(q_a, na=False) |
                df_filtered_act["FULL_NAME"].str.lower().str.contains(q_a, na=False)
            ]

        # Gắn dữ liệu ghi chú tuần hiện tại đã lưu
        curr_notes = []
        curr_statuses = []
        for _, r in df_filtered_act.iterrows():
            key_curr = f"{selected_week}_{r.get('MSSV', '')}"
            saved = notes_db.get(key_curr, {})
            curr_notes.append(saved.get("note", ""))
            curr_statuses.append(saved.get("status", "Chưa liên hệ"))

        df_filtered_act["Trạng thái xử lý tuần này"] = curr_statuses
        df_filtered_act["Ghi chú Action tuần này"] = curr_notes

        action_cols = [
            "WEEK", "MSSV", "FULL_NAME", "HANNAH", "MÔN_ĐANG_HỌC",
            "CHUYỂN_BIẾN_TUẦN_NÀY", "ACTION_TUẦN_TRƯỚC",
            "INACTIVITY_WEEKS", "ROOT_CAUSE", "ACTION_SUGGESTION",
            "Trạng thái xử lý tuần này", "Ghi chú Action tuần này"
        ]
        valid_action_cols = [c for c in action_cols if c in df_filtered_act.columns]

        edited_h1_board = st.data_editor(
            df_filtered_act[valid_action_cols],
            key="h1_urgent_action_editor_v2",
            use_container_width=True,
            hide_index=True,
            column_config={
                "WEEK": st.column_config.TextColumn("Tuần", disabled=True, width="small"),
                "MSSV": st.column_config.TextColumn("MSSV", disabled=True, width="small"),
                "FULL_NAME": st.column_config.TextColumn("Họ và Tên", disabled=True, width="medium"),
                "HANNAH": st.column_config.TextColumn("Hannah", disabled=True, width="small"),
                "MÔN_ĐANG_HỌC": st.column_config.TextColumn("Môn", disabled=True, width="small"),
                "CHUYỂN_BIẾN_TUẦN_NÀY": st.column_config.TextColumn("Chuyển Biến Tuần Này (vs Tuần Trước)", disabled=True, width="medium"),
                "ACTION_TUẦN_TRƯỚC": st.column_config.TextColumn("Lịch Sử Action Tuần Trước", disabled=True, width="large"),
                "INACTIVITY_WEEKS": st.column_config.NumberColumn("Số Tuần Dừng", disabled=True, width="small"),
                "ROOT_CAUSE": st.column_config.TextColumn("Nguyên Nhân Cốt Lõi", disabled=True, width="medium"),
                "ACTION_SUGGESTION": st.column_config.TextColumn("Gợi Ý Can Thiệp", disabled=True, width="medium"),
                "Trạng thái xử lý tuần này": st.column_config.SelectboxColumn(
                    "Trạng thái xử lý tuần này",
                    options=[
                        "Chưa liên hệ",
                        "Đang gọi điện",
                        "Đã nhắn tin Zalo",
                        "Đã kết nối lại",
                        "Hẹn lịch Mentor",
                        "Báo phụ huynh / BQL",
                        "Đã giải quyết"
                    ],
                    required=True,
                    width="medium"
                ),
                "Ghi chú Action tuần này": st.column_config.TextColumn(
                    "Ghi chú Action tuần này",
                    help="Gõ chi tiết kết quả liên hệ hoặc cam kết của học viên",
                    width="large"
                )
            }
        )

        col_s1, col_s2 = st.columns([1, 4])
        with col_s1:
            if st.button("💾 Lưu Action Notes Tuần Này", type="primary"):
                saved_count = 0
                for _, row in edited_h1_board.iterrows():
                    key = f"{selected_week}_{row.get('MSSV', '')}"
                    notes_db[key] = {
                        "note": row.get("Ghi chú Action tuần này", ""),
                        "status": row.get("Trạng thái xử lý tuần này", "Chưa liên hệ"),
                        "hannah": row.get("HANNAH", ""),
                        "student_name": row.get("FULL_NAME", ""),
                        "recovery_status": row.get("CHUYỂN_BIẾN_TUẦN_NÀY", "")
                    }
                    saved_count += 1
                if save_notes_db(notes_db):
                    st.success(f"✅ Đã lưu thành công ghi chú cho {saved_count} học viên!")

        with col_s2:
            excel_act_buf = io.BytesIO()
            with pd.ExcelWriter(excel_act_buf, engine="openpyxl") as writer:
                edited_h1_board.to_excel(writer, sheet_name="Hannah_Action_H1", index=False)
            excel_act_bytes = excel_act_buf.getvalue()

            st.download_button(
                label="📥 Xuất Báo Cáo Action H1 Kèm Đối Soát (Excel)",
                data=excel_act_bytes,
                file_name=f"Hannah_Action_H1_DoiSoat_{selected_week if selected_week != 'Tất cả tuần trong Quý' else selected_quarter}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    st.markdown("---")
    st.subheader("📋 Tra Cứu Toàn Bộ Học Viên H1")
    search_h1 = st.text_input("🔍 Tìm kiếm học viên H1 (theo MSSV, Họ tên, Email, Môn học):", placeholder="Gõ từ khóa để tra cứu...")
    df_all_h1_view = df_deep.copy()

    if search_h1:
        q1 = search_h1.strip().lower()
        df_all_h1_view = df_all_h1_view[
            df_all_h1_view["MSSV"].str.lower().str.contains(q1, na=False) |
            df_all_h1_view["FULL_NAME"].str.lower().str.contains(q1, na=False) |
            df_all_h1_view["EMAIL"].str.lower().str.contains(q1, na=False) |
            df_all_h1_view["MÔN_ĐANG_HỌC"].str.lower().str.contains(q1, na=False)
        ]

    st.markdown(f"Hiển thị **{len(df_all_h1_view):,}** học viên H1:")
    h1_view_cols = [
        "WEEK", "MSSV", "FULL_NAME", "EMAIL", "HANNAH", "CHƯƠNG_TRÌNH", "MÔN_ĐANG_HỌC",
        "CHUYỂN_BIẾN_TUẦN_NÀY", "MÔN_HOÀN_THÀNH / TỔNG", "THÁNG_CÒN_LẠI",
        "QUIZ", "LAB", "ASSIGNMENT", "PROGRESS_TEST", "FINAL_EXAM",
        "TOTAL_ACTIVITY", "KHẢ_NĂNG_HOÀN_THÀNH", "RISK_LEVEL", "ROOT_CAUSE", "ACTION_SUGGESTION"
    ]
    present_h1_cols = [c for c in h1_view_cols if c in df_all_h1_view.columns]

    st.dataframe(
        df_all_h1_view[present_h1_cols],
        use_container_width=True,
        hide_index=True
    )

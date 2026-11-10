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
SURVEY_SHEET_NAME = "Survey"
EVAL_COLS = ["QUIZ", "LAB", "ASSIGNMENT", "PROGRESS_TEST", "FINAL_EXAM"]

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

    if "THÁNG_ĐÃ_HỌC / TỔNG" in df.columns:
        def get_tot_months(val):
            if pd.isna(val): return 0.0
            parts = str(val).split("/")
            if len(parts) == 2:
                try: return float(parts[1].strip().replace(",", "."))
                except: return 0.0
            return 0.0
        df["TỔNG_THÁNG_KHÓA_HỌC"] = df["THÁNG_ĐÃ_HỌC / TỔNG"].apply(get_tot_months)
    else:
        df["TỔNG_THÁNG_KHÓA_HỌC"] = 0.0

    def categorize_course_group(m):
        if m < 1.0:
            return "1. Khóa ngắn (< 1 tháng)"
        elif m < 12.0:
            return "2. Khóa trung hạn (1 - < 12 tháng)"
        else:
            return "3. Khóa dài hạn (≥ 12 tháng)"

    df["NHÓM_THỜI_LƯỢNG"] = df["TỔNG_THÁNG_KHÓA_HỌC"].apply(categorize_course_group)

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

    # Tính tiến độ học thuật trung bình của 1 học viên từ 5 hạng mục đánh giá (không dùng XP)
    eval_cols = ["QUIZ", "LAB", "ASSIGNMENT", "PROGRESS_TEST", "FINAL_EXAM"]
    def calc_student_academic_progress(row):
        pcts = []
        for col in EVAL_COLS:
            tot = row.get(f"{col}_TOTAL", 0)
            done = row.get(f"{col}_DONE", 0)
            if tot > 0:
                pcts.append(min(done / tot * 100.0, 100.0))
        return round(float(np.mean(pcts)), 1) if len(pcts) > 0 else 0.0

    df["TIẾN_ĐỘ_HỌC_THUẬT"] = df.apply(calc_student_academic_progress, axis=1)

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

    def format_missing_tasks(r):
        q_miss = max(r.get("QUIZ_TOTAL", 0) - r.get("QUIZ_DONE", 0), 0)
        l_miss = max(r.get("LAB_TOTAL", 0) - r.get("LAB_DONE", 0), 0)
        a_miss = max(r.get("ASSIGNMENT_TOTAL", 0) - r.get("ASSIGNMENT_DONE", 0), 0)
        p_miss = max(r.get("PROGRESS_TEST_TOTAL", 0) - r.get("PROGRESS_TEST_DONE", 0), 0)
        f_miss = 1 if (r.get("FINAL_EXAM_TOTAL", 0) > 0 and r.get("FINAL_EXAM_DONE", 0) == 0) else 0

        items = []
        if q_miss > 0: items.append(f"{q_miss} Quiz")
        if l_miss > 0: items.append(f"{l_miss} Lab")
        if a_miss > 0: items.append(f"{a_miss} ASM")
        if p_miss > 0: items.append(f"{p_miss} Progress Test")
        if f_miss > 0: items.append("Thi Final Exam")
        return ", ".join(items) if items else "Đã xong 100% bài môn"

    def format_xp_progress(r):
        done = r.get("XP_ĐÃ_ĐẠT", 0)
        req = r.get("XP_CẦN_ĐẠT", 0)
        pct = str(r.get("%_HOÀN_THÀNH_XP", "")).strip()
        if pct and pct != "nan" and pct != "None":
            return f"{done:,} / {req:,} ({pct})"
        return f"{done:,} / {req:,}"

    def generate_smart_push_action(r):
        rem_c = int(r.get("SỐ_MÔN_CÒN_LẠI", 0))
        tot_c = int(r.get("TỔNG_SỐ_MÔN", 0))
        m_left = float(r.get("THÁNG_CÒN_LẠI_NUM", 0.0))
        act = int(r.get("TOTAL_ACTIVITY", 0))
        course = str(r.get("MÔN_ĐANG_HỌC", "")).strip()
        xp_done = r.get("XP_ĐÃ_ĐẠT", 0)
        xp_req = r.get("XP_CẦN_ĐẠT", 0)
        xp_pct = str(r.get("%_HOÀN_THÀNH_XP", "")).strip()
        if xp_pct in ["nan", "None"]:
            xp_pct = ""

        q_miss = max(r.get("QUIZ_TOTAL", 0) - r.get("QUIZ_DONE", 0), 0)
        l_miss = max(r.get("LAB_TOTAL", 0) - r.get("LAB_DONE", 0), 0)
        a_miss = max(r.get("ASSIGNMENT_TOTAL", 0) - r.get("ASSIGNMENT_DONE", 0), 0)
        p_miss = max(r.get("PROGRESS_TEST_TOTAL", 0) - r.get("PROGRESS_TEST_DONE", 0), 0)
        f_miss = 1 if (r.get("FINAL_EXAM_TOTAL", 0) > 0 and r.get("FINAL_EXAM_DONE", 0) == 0) else 0

        missing_list = []
        if q_miss > 0: missing_list.append(f"{q_miss} Quiz")
        if l_miss > 0: missing_list.append(f"{l_miss} Lab")
        if a_miss > 0: missing_list.append(f"{a_miss} ASM")
        if p_miss > 0: missing_list.append(f"{p_miss} Progress Test")
        if f_miss > 0: missing_list.append("Thi Final Exam")

        miss_str = ", ".join(missing_list) if missing_list else "Đã xong 100% bài môn"
        first_miss = missing_list[0] if missing_list else "bài tập còn lại"

        course_info = f"Môn {course}" if (course and course != "-") else "Môn đang học"
        if xp_pct:
            course_info += f" ({xp_pct} XP)"
        elif xp_req:
            course_info += f" ({xp_done:,}/{xp_req:,} XP)"

        # 1. Đã hoàn thành 100% môn
        if tot_c > 0 and rem_c <= 0:
            return f"🎉 ĐÃ HOÀN THÀNH 100% MÔN ({xp_done:,}/{xp_req:,} XP). Hannah hướng dẫn làm thủ tục công nhận tốt nghiệp & cấp chứng chỉ."

        # 2. Môn cuối cùng để tốt nghiệp (rem_c == 1)
        if rem_c == 1:
            prefix = f"🎯 MÔN CUỐI CÙNG TỐT NGHIỆP ({course_info}):"
            if not missing_list:
                return f"{prefix} Đã làm hết bài tập môn! Hannah đôn đốc đăng ký lịch thi Final Exam / chốt đồ án ngay tuần này để hoàn thành toàn khóa."
            if act == 0:
                return f"{prefix} Còn thiếu [{miss_str}] nhưng tuần này chưa học (Act=0). Còn {m_left:.1f} tháng. Hannah gọi điện trực tiếp, đặt deadline nộp từng bài để về đích sớm!"
            return f"{prefix} Đang giữ nhịp học tốt (Act={act}). Còn thiếu [{miss_str}] trong {m_left:.1f} tháng. Hannah chốt hạn nộp [{first_miss}] trong tuần này để cán đích!"

        # 3. Còn 2-3 môn và thời gian gấp (m_left <= 2 tháng)
        if rem_c <= 3 and m_left <= 2.0:
            prefix = f"⚡ GẤP - NƯỚC RÚT ({rem_c} môn / {m_left:.1f} tháng, {course_info}):"
            if act == 0:
                return f"{prefix} Nguy cơ quá hạn vì tuần này không học (Act=0)! Còn thiếu [{miss_str}]. Hannah gọi điện gấp trong 24h, book Mentor hỗ trợ giải quyết bài nghẽn ngay!"
            if not missing_list:
                return f"{prefix} Đã xong bài môn này (Act={act}). Cần hoàn thành thi ngay để mở môn tiếp theo trong tuần tới!"
            return f"{prefix} Đang có đà học (Act={act}). Cần giải quyết dứt điểm [{miss_str}] trước ngày 15 tháng này để kịp mở {rem_c - 1} môn còn lại!"

        # 4. Còn 2-3 môn, thời gian an toàn (m_left > 2 tháng)
        if rem_c <= 3:
            prefix = f"🌟 SẮP VỀ ĐÍCH ({rem_c} môn / {m_left:.1f} tháng, {course_info}):"
            if not missing_list:
                return f"{prefix} Đã xong 100% bài môn hiện tại (Act={act})! Nhắc học viên đăng ký thi / mở môn tiếp theo."
            if act == 0:
                return f"{prefix} Còn thiếu [{miss_str}]. Tuần này chưa có activity, Hannah nhắn tin nhắc nhở quay lại học và làm tiếp [{first_miss}]."
            return f"{prefix} Tiến độ tốt (Act={act}). Còn thiếu [{miss_str}]. Đôn đốc hoàn thành môn này trong tháng để giữ vững lộ trình về đích."

        # 5. Nguy cơ chậm tiến độ (m_left < 3 tháng hoặc pace cao)
        pace = rem_c / max(m_left, 0.1)
        if m_left < 3.0 or pace > 1.2:
            prefix = f"🚨 NGUY CƠ CHẬM TIẾN ĐỘ ({rem_c} môn / {m_left:.1f} tháng, {course_info}):"
            if act == 0:
                return f"{prefix} Đang dừng học (Act=0) trong khi áp lực tiến độ cao ({pace:.1f} môn/tháng). Còn thiếu [{miss_str}]. Hannah liên hệ khẩn cấp lập kế hoạch học lại!"
            return f"{prefix} Tốc độ yêu cầu {pace:.1f} môn/tháng. Môn hiện tại còn thiếu [{miss_str}]. Hannah họp cùng học viên lập lộ trình học tăng tốc cam kết hàng tuần."

        # 6. Các trường hợp còn lại (Bình thường / Duy trì tiến độ)
        if act == 0:
            return f"⚠️ NHẮC NHỞ HỌC TẬP ({course_info}, còn {rem_c} môn / {m_left:.1f} tháng): Tuần này dừng học, còn thiếu [{miss_str}]. Hannah nhắn tin đôn đốc mở bài học tiếp."
        return f"✅ TIẾN ĐỘ ĐỀU ({course_info}, còn {rem_c} môn / {m_left:.1f} tháng): Còn thiếu [{miss_str}], Act tuần={act}. Duy trì kiểm tra tiến độ học tập hàng tuần."

    df["BÀI_TẬP_CÒN_THIẾU"] = df.apply(format_missing_tasks, axis=1)
    df["TIẾN_ĐỘ_XP"] = df.apply(format_xp_progress, axis=1)
    df["ACTION_SUGGESTION"] = df.apply(generate_smart_push_action, axis=1)

    for c in ["WEEK", "MSSV", "FULL_NAME", "EMAIL", "TAG", "HANNAH", "CHƯƠNG_TRÌNH", "MÔN_ĐANG_HỌC", "STUDENT_STATUS", "RISK_LEVEL", "ROOT_CAUSE", "ACTION_SUGGESTION", "BÀI_TẬP_CÒN_THIẾU", "TIẾN_ĐỘ_XP", "NHÓM_THỜI_LƯỢNG"]:
        if c in df.columns:
            df[c] = df[c].fillna("N/A").astype(str).str.strip()

    return df

# ==================== PHẦN HEADER & GIẢI THÍCH NGHIỆP VỤ ====================
st.title("🎯 Dashboard Quản Trị Đào Tạo & Action Tracking")
st.caption("Giám sát Quy mô Học viên, Quản trị Tiến độ Tag H1 & Vòng Lặp Đo Lường Hành Động Can Thiệp (Closed-Loop Action Tracking).")

# ==================== SIDEBAR: BỘ LỌC DỮ LIỆU ====================
st.sidebar.header("⚙️ Nguồn Dữ Liệu Real-Time")

col_rf1, col_rf2 = st.sidebar.columns([1, 1])
with col_rf1:
    if st.button("🔄 Làm mới", help="Cập nhật trực tiếp dữ liệu mới nhất từ Google Sheets"):
        st.cache_data.clear()
        st.rerun()
with col_rf2:
    if st.button("🚀 Push Git", help="Đẩy code app.py lên GitHub Repository (Chế độ Local)"):
        # Nhận diện nếu đang chạy trên Streamlit Cloud
        is_cloud = os.path.exists("/mount/src") or "STREAMLIT_SERVER_BASE_URL_PATH" in os.environ
        if is_cloud:
            st.sidebar.info("☁️ Ứng dụng đang chạy trên Streamlit Cloud (đã đồng bộ tự động từ GitHub). Để cập nhật dữ liệu mới từ Google Sheets, bạn chỉ cần bấm nút **🔄 Làm mới**.")
        else:
            try:
                from sync_github import sync_to_github
                with st.spinner("Đang đẩy lên GitHub..."):
                    if sync_to_github("Update app.py via Dashboard button"):
                        st.sidebar.success("✅ Đã push Git thành công!")
                    else:
                        st.sidebar.error("❌ Chưa cấu hình Token hoặc lỗi kết nối.")
            except Exception as e:
                st.sidebar.error(f"Lỗi: {e}")

with st.spinner("Đang tải dữ liệu từ Google Sheets Master Data & Survey..."):
    df_raw, load_err = load_data_from_google_sheet(MASTER_DATA_SHEET_ID, TARGET_SHEET_NAME)
    df_survey_raw, survey_err = load_data_from_google_sheet(MASTER_DATA_SHEET_ID, SURVEY_SHEET_NAME)

if df_raw is not None and not df_raw.empty:
    st.sidebar.success(f"✅ Đã kết nối Master Data: **{len(df_raw):,}** dòng")
    if df_survey_raw is not None and not df_survey_raw.empty:
        st.sidebar.info(f"📋 Dữ liệu Khảo Sát: **{len(df_survey_raw):,}** phản hồi")
    else:
        st.sidebar.warning("ℹ️ Sheet 'Survey' chưa có dữ liệu phản hồi.")
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
# Ánh xạ tuần trước đó cho từng tuần theo thứ tự thời gian
week_to_prev_map = {all_sorted_weeks[i]: all_sorted_weeks[i-1] for i in range(1, len(all_sorted_weeks))}
if all_sorted_weeks:
    week_to_prev_map[all_sorted_weeks[0]] = None

# Bảng tra cứu lịch sử rủi ro toàn cục: (WEEK, MSSV) -> (RISK_LEVEL, TOTAL_ACTIVITY)
history_risk_lookup = {}
df_history_source = df_clean[df_clean["TAG_CODE"] == "H1"] if scope_option.startswith("Chỉ phân tích Tag H1") else df_clean
for _, r_look in df_history_source.iterrows():
    history_risk_lookup[(r_look["WEEK"], r_look["MSSV"])] = (
        str(r_look.get("RISK_LEVEL", "")).upper(),
        int(r_look.get("TOTAL_ACTIVITY", 0))
    )

# Bảng tra cứu lịch sử tiến độ học thuật toàn cục: (WEEK, MSSV) -> (TIẾN_ĐỘ_HỌC_THUẬT, MÔN_ĐANG_HỌC)
history_prog_lookup = {}
for _, r_look in df_clean.iterrows():
    history_prog_lookup[(r_look["WEEK"], r_look["MSSV"])] = (
        float(r_look.get("TIẾN_ĐỘ_HỌC_THUẬT", 0.0)),
        str(r_look.get("MÔN_ĐANG_HỌC", "")).strip()
    )

# Danh sách 5 hạng mục học thuật đánh giá chính
EVAL_COLS = ["QUIZ", "LAB", "ASSIGNMENT", "PROGRESS_TEST", "FINAL_EXAM"]

# Bảng tra cứu lịch sử chi tiết 5 hạng mục đánh giá: (WEEK, MSSV) -> {col: (DONE, TOTAL)}
history_eval_lookup = {}
for _, r_look in df_clean.iterrows():
    history_eval_lookup[(r_look["WEEK"], r_look["MSSV"])] = {
        col: (int(r_look.get(f"{col}_DONE", 0)), int(r_look.get(f"{col}_TOTAL", 0))) for col in EVAL_COLS
    }

def clean_course_code(code_str):
    s = str(code_str).strip().upper()
    if not s or s == "-":
        return ""
    m = re.match(r"^([A-Z]{2,4}\d{3,4}[A-Z]?)", s)
    if m:
        return m.group(1)
    return s.split('_')[0].split('.')[0].strip()

def determine_academic_delta(row, forced_prev_week=None):
    """
    Đối chiếu trực tiếp 5 trường dữ liệu đánh giá: QUIZ, LAB, ASSIGNMENT, PROGRESS_TEST, FINAL_EXAM
    của học viên (theo MSSV) giữa tuần trước và tuần này.
    Ví dụ: Tuần trước 10/15 Quiz, tuần này 12/15 Quiz -> tăng 2/15 = 13.3% Quiz.
    Tiến độ tuần của học viên = trung bình mức tăng của các hạng mục có trong môn.
    """
    curr_w = row.get("WEEK", "")
    target_prev_w = forced_prev_week if forced_prev_week else week_to_prev_map.get(curr_w)
    if not target_prev_w:
        return 0.0
    mssv = row.get("MSSV", "")
    if (target_prev_w, mssv) not in history_eval_lookup:
        return 0.0

    p_data = history_eval_lookup[(target_prev_w, mssv)]
    category_deltas = []

    for col in EVAL_COLS:
        c_done = int(row.get(f"{col}_DONE", 0))
        c_tot = int(row.get(f"{col}_TOTAL", 0))
        p_done, p_tot = p_data[col]

        # Nếu môn học tuần này yêu cầu hạng mục này (c_tot > 0)
        if c_tot > 0:
            c_pct = min(c_done / c_tot * 100.0, 100.0)
            p_pct = min(p_done / p_tot * 100.0, 100.0) if p_tot > 0 else 0.0
            diff_pct = max(c_pct - p_pct, 0.0)
            category_deltas.append(diff_pct)

    return round(float(np.mean(category_deltas)), 2) if category_deltas else 0.0

# Hàm bóc tách sản phẩm học thuật mới hoàn thành trong tuần (Quiz, Lab, ASM, Test, Final Exam)
def get_weekly_completed_products(row, forced_prev_week=None):
    curr_w = row.get("WEEK", "")
    target_prev_w = forced_prev_week if forced_prev_week else week_to_prev_map.get(curr_w)
    if not target_prev_w:
        return "— (Tuần đầu)"
    mssv = row.get("MSSV", "")
    if (target_prev_w, mssv) not in history_eval_lookup:
        return "— (Mới cập nhật)"
    
    p_data = history_eval_lookup[(target_prev_w, mssv)]
    items = []
    labels = {
        "QUIZ": "Quiz", "LAB": "Lab", "ASSIGNMENT": "ASM", 
        "PROGRESS_TEST": "Progress Test", "FINAL_EXAM": "Final Exam"
    }
    for col in EVAL_COLS:
        c_d = int(row.get(f"{col}_DONE", 0))
        p_d = int(p_data[col][0])
        if c_d > p_d:
            diff = c_d - p_d
            if col == "FINAL_EXAM":
                items.append("Đã thi Final Exam")
            else:
                items.append(f"+{diff} {labels[col]}")
    return ", ".join(items) if items else "Chưa có bài mới"

# Hàm gán nhãn chuyển biến thực tế
def determine_recovery_status(row, forced_prev_week=None):
    curr_w = row.get("WEEK", "")
    target_prev_w = forced_prev_week if forced_prev_week else week_to_prev_map.get(curr_w)
    if not target_prev_w:
        return "⚪ Tuần đầu tiên (Chưa có tuần đối soát)"
    
    mssv = row.get("MSSV", "")
    if (target_prev_w, mssv) not in history_risk_lookup:
        return "⚪ Học viên mới cập nhật"
    
    p_risk, _ = history_risk_lookup[(target_prev_w, mssv)]
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

# Gắn cột Chuyển biến học tập và Lịch sử Action tuần trước vào df_base và df_deep
for df_target in [df_base, df_deep]:
    if not df_target.empty:
        df_target["CHUYỂN_BIẾN_TUẦN_NÀY"] = df_target.apply(
            lambda r: determine_recovery_status(r, prev_week_name if selected_week != "Tất cả tuần trong Quý" else None), axis=1
        )
        df_target["DELTA_TIẾN_ĐỘ"] = df_target.apply(
            lambda r: determine_academic_delta(r, prev_week_name if selected_week != "Tất cả tuần trong Quý" else None), axis=1
        )
        df_target["SẢN_PHẨM_TUẦN_NÀY"] = df_target.apply(
            lambda r: get_weekly_completed_products(r, prev_week_name if selected_week != "Tất cả tuần trong Quý" else None), axis=1
        )
        df_target["ACTION_TUẦN_TRƯỚC"] = df_target.apply(
            lambda r: get_previous_action_note(
                notes_db, 
                r.get("MSSV", ""), 
                prev_week_name if selected_week != "Tất cả tuần trong Quý" else week_to_prev_map.get(r.get("WEEK", ""))
            ), 
            axis=1
        )
    else:
        df_target["CHUYỂN_BIẾN_TUẦN_NÀY"] = "N/A"
        df_target["DELTA_TIẾN_ĐỘ"] = 0.0
        df_target["SẢN_PHẨM_TUẦN_NÀY"] = "N/A"
        df_target["ACTION_TUẦN_TRƯỚC"] = "N/A"

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

# ==================== 6 TABS GIAO DIỆN CHÍNH ====================
tab0, tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🎯 0. Báo Cáo KPI Team Hannah",
    "📌 1. Tổng Quan Quy Mô & Phân Bổ Tag",
    "🎯 2. Tiến Độ & Danh Sách Push Hoàn Thành (H1)",
    "👩‍💼 3. Hiệu Suất & Tỷ Lệ Cứu Nguy Hannah (H1)",
    "📚 4. Sản Phẩm Học Thuật & Mentor Support",
    "🚨 5. Action Board Đối Soát Chuyển Biến (H1)"
])

# =========================================================================
# TAB 0: BÁO CÁO KPI TEAM HANNAH (EXECUTIVE DASHBOARD)
# =========================================================================
with tab0:
    period_title = selected_week if selected_week != "Tất cả tuần trong Quý" else selected_quarter
    st.subheader(f"🎯 Báo Cáo Chỉ Số KPI & Đo Lường Benchmark ({period_title})")
    st.caption("Tổng hợp **Bộ 5 Chỉ Số KPI Chiến Lược**, đo lường **Benchmark Thực tế vs Mục tiêu** và Bảng danh sách **Học viên Rủi ro cần Can thiệp Cấp cao**.")

    # --- TÍNH TOÁN CÁC CHỈ SỐ KPI ---
    # 1. Học viên Tag H1
    df_h1_tab0 = df_deep[df_deep["TAG_CODE"] == "H1"].copy() if "TAG_CODE" in df_deep.columns else df_deep.copy()
    tot_h1_kpi = len(df_h1_tab0)

    # Hiển thị tóm tắt quy mô mẫu đang chọn để tránh hiểu lầm khi áp dụng bộ lọc
    if tot_h1_kpi > 0:
        act_cnt_quick = (df_h1_tab0["TOTAL_ACTIVITY"] > 0).sum()
        filter_note = f" (Bộ lọc: {len(selected_hannahs)} Hannah, {len(selected_progs)} Chương trình)" if (len(selected_hannahs) < len(all_hannahs) or len(selected_progs) < len(all_progs)) else ""
        st.info(f"📊 Phạm vi dữ liệu: **{period_title}**{filter_note} • Tổng số học viên Tag H1: **{tot_h1_kpi:,}** học viên • Có hoạt động tuần: **{act_cnt_quick:,}** học viên.")
    else:
        st.warning(f"⚠️ Không có học viên Tag H1 nào phù hợp với bộ lọc hiện tại của kỳ **{period_title}**. Vui lòng kiểm tra lại bộ lọc Hannah / Chương trình ở thanh bên.")

    # KPI 1: Tỷ lệ Active tuần H1 (Target >= 70%)
    act_h1_cnt = (df_h1_tab0["TOTAL_ACTIVITY"] > 0).sum() if tot_h1_kpi > 0 else 0
    act_h1_pct = (act_h1_cnt / tot_h1_kpi * 100) if tot_h1_kpi > 0 else 0.0
    target_act = 70.0
    diff_act = act_h1_pct - target_act

    # KPI 2: TIẾN ĐỘ HỌC THUẬT TRUNG BÌNH CỦA 1 HỌC VIÊN (TAG H1)
    # Tính theo 5 hạng mục đánh giá: Quiz + Lab + Assignment + Progress Test + Final Exam (KHÔNG DÙNG XP)
    avg_prog_h1 = df_h1_tab0["TIẾN_ĐỘ_HỌC_THUẬT"].mean() if ("TIẾN_ĐỘ_HỌC_THUẬT" in df_h1_tab0.columns and tot_h1_kpi > 0) else 0.0
    target_prog = 30.0  # Benchmark chuẩn tiến độ môn học: >= 30%
    diff_prog = avg_prog_h1 - target_prog

    # Mức tăng tiến độ tuần trung bình của nhóm Active
    df_h1_act = df_h1_tab0[df_h1_tab0["TOTAL_ACTIVITY"] > 0] if "TOTAL_ACTIVITY" in df_h1_tab0.columns else df_h1_tab0
    avg_gain_act = df_h1_act["DELTA_TIẾN_ĐỘ"].mean() if ("DELTA_TIẾN_ĐỘ" in df_h1_act.columns and len(df_h1_act) > 0) else 0.0
    gain_cnt = (df_h1_tab0["DELTA_TIẾN_ĐỘ"] > 0).sum() if ("DELTA_TIẾN_ĐỘ" in df_h1_tab0.columns and tot_h1_kpi > 0) else 0
    avg_gain_pos = df_h1_tab0[df_h1_tab0["DELTA_TIẾN_ĐỘ"] > 0]["DELTA_TIẾN_ĐỘ"].mean() if gain_cnt > 0 else 0.0
    target_gain = 3.0  # Target tăng trưởng mỗi tuần: >= 3.0%
    diff_gain = avg_gain_act - target_gain

    # KPI 3: Tỷ lệ hoàn thành theo 3 nhóm thời lượng khóa học
    # Nhóm 1: Khóa ngắn (< 1 tháng) - Target 70%
    df_g1 = df_base[df_base["NHÓM_THỜI_LƯỢNG"] == "1. Khóa ngắn (< 1 tháng)"]
    tot_g1 = len(df_g1)
    on_track_g1 = df_g1["KHẢ_NĂNG_HOÀN_THÀNH"].str.contains("On-Track|RẤT CAO|Đã hoàn thành", na=False).sum()
    pct_g1 = (on_track_g1 / tot_g1 * 100) if tot_g1 > 0 else 0.0
    target_g1 = 70.0

    # Nhóm 2: Khóa trung hạn (1 - < 12 tháng) - Target 50%
    df_g2 = df_base[df_base["NHÓM_THỜI_LƯỢNG"] == "2. Khóa trung hạn (1 - < 12 tháng)"]
    tot_g2 = len(df_g2)
    on_track_g2 = df_g2["KHẢ_NĂNG_HOÀN_THÀNH"].str.contains("On-Track|RẤT CAO|Đã hoàn thành", na=False).sum()
    pct_g2 = (on_track_g2 / tot_g2 * 100) if tot_g2 > 0 else 0.0
    target_g2 = 50.0

    # Nhóm 3: Khóa dài hạn (>= 12 tháng) - Target 30%
    df_g3 = df_base[df_base["NHÓM_THỜI_LƯỢNG"] == "3. Khóa dài hạn (≥ 12 tháng)"]
    tot_g3 = len(df_g3)
    on_track_g3 = df_g3["KHẢ_NĂNG_HOÀN_THÀNH"].str.contains("On-Track|RẤT CAO|Đã hoàn thành", na=False).sum()
    pct_g3 = (on_track_g3 / tot_g3 * 100) if tot_g3 > 0 else 0.0
    target_g3 = 30.0

    # KPI 4: Khảo sát sự hài lòng (CSAT & NPS) theo Quý
    csat_pct = None
    csat_hannah_pct = None
    survey_resp_cnt = 0
    df_survey_q = None

    def ext_r(v):
        if pd.isna(v): return None
        s = str(v).strip()
        return int(s[0]) if (s and s[0].isdigit()) else None

    if df_survey_raw is not None and not df_survey_raw.empty:
        df_s = df_survey_raw.copy()
        df_s["DATE"] = pd.to_datetime(df_s["Dấu thời gian"], format="%d/%m/%Y %H:%M:%S", errors="coerce")
        df_s["QUARTER"] = df_s["DATE"].apply(lambda d: f"{d.year}-Q{d.quarter}" if pd.notnull(d) else "Khác")

        if selected_quarter != "Tất cả các Quý":
            df_survey_q = df_s[df_s["QUARTER"] == selected_quarter]
            if df_survey_q.empty:
                df_survey_q = df_s.copy()
        else:
            df_survey_q = df_s.copy()

        col_sat = "1. Bạn hài lòng ở mức nào với trải nghiệm học tập tại FUNiX?"
        if col_sat in df_survey_q.columns:
            scores = pd.to_numeric(df_survey_q[col_sat], errors="coerce").dropna()
            if len(scores) > 0:
                csat_pct = (scores >= 4).sum() / len(scores) * 100
                survey_resp_cnt = len(scores)

        col_h = "2. Bạn đánh giá mức độ hài lòng đối với các dịch vụ dưới đây như thế nào? [Hannah]"
        if col_h in df_survey_q.columns:
            h_scores = df_survey_q[col_h].apply(ext_r).dropna()
            if len(h_scores) > 0:
                csat_hannah_pct = (h_scores >= 4).sum() / len(h_scores) * 100

    # KPI 5: Quy mô & Cứu nguy
    urgent_cnt = (df_h1_tab0["RISK_LEVEL"].isin(["HIGH", "CRITICAL"])).sum() if tot_h1_kpi > 0 else 0
    if "CHUYỂN_BIẾN_TUẦN_NÀY" in df_h1_tab0.columns:
        recov_cnt = len(df_h1_tab0[df_h1_tab0["CHUYỂN_BIẾN_TUẦN_NÀY"].str.contains("Đã cải thiện", na=False)])
        stag_cnt = len(df_h1_tab0[df_h1_tab0["CHUYỂN_BIẾN_TUẦN_NÀY"].str.contains("Vẫn bất động", na=False)])
    else:
        recov_cnt = 0
        stag_cnt = 0
    team_recov_rate = (recov_cnt / (recov_cnt + stag_cnt) * 100) if (recov_cnt + stag_cnt) > 0 else 0.0

    # =========================================================================
    # PHẦN 1: BỘ 3 CHỈ SỐ CỐT LÕI (ACTIVITY, TIẾN ĐỘ HỌC TẬP & SỰ HÀI LÒNG)
    # =========================================================================
    st.markdown("### 🏆 1. Tương Tác, Tiến Độ Học Thuật & Mức Độ Hài Lòng")
    st.caption("Bộ 3 chỉ số then chốt theo dõi nhịp học tập hàng tuần của học viên Tag H1 và chất lượng dịch vụ đào tạo theo Quý.")

    k1, k2, k3 = st.columns(3)

    with k1:
        st.metric(
            label="⚡ 1. Activity Tuần (Tag H1)",
            value=f"{act_h1_pct:.1f}%",
            delta=f"{diff_act:+.1f}% vs Target 70%",
            delta_color="normal" if diff_act >= 0 else "inverse",
            help=f"Thực tế: {act_h1_cnt}/{tot_h1_kpi} học viên có Activity > 0 trong tuần. Mục tiêu: >= 70%."
        )
        if act_h1_pct >= target_act:
            st.success("🟢 Đạt chỉ tiêu tương tác tuần")
        else:
            st.warning(f"🔴 Thiếu {target_act - act_h1_pct:.1f}% để đạt chuẩn 70%")

    with k2:
        st.metric(
            label="📚 2. Tiến Độ Học Tập Môn Tuần (Tag H1)",
            value=f"{avg_gain_act:.2f}%",
            delta=f"{diff_gain:+.2f}% vs Target 3.0%/tuần",
            delta_color="normal" if diff_gain >= 0 else "inverse",
            help=f"Đo lường mức tăng tiến độ môn trung bình của nhóm Active trong tuần (tính từ 5 hạng mục: Quiz + Lab + ASM + Progress Test + Final Exam, không dùng XP). Mục tiêu: >= 3.0%/tuần. Riêng nhóm {gain_cnt} học viên có nộp bài/tăng tiến độ đạt trung bình +{avg_gain_pos:.1f}%. Tiến độ môn tích lũy TB: {avg_prog_h1:.1f}%."
        )
        if avg_gain_act >= target_gain:
            st.success(f"🟢 Đạt chuẩn tăng trưởng tuần ({gain_cnt} HV nộp bài, TB nhóm nộp: +{avg_gain_pos:.1f}%)")
        else:
            st.warning(f"🟡 TB Active: {avg_gain_act:.2f}% (Nhóm {gain_cnt} HV nộp bài tăng +{avg_gain_pos:.1f}%, TB tích lũy: {avg_prog_h1:.1f}%)")

    with k3:
        if csat_pct is not None:
            diff_csat = csat_pct - 75.0
            st.metric(
                label="⭐ 3. Tỷ Lệ Hài Lòng (CSAT Quý)",
                value=f"{csat_pct:.1f}%",
                delta=f"{diff_csat:+.1f}% vs Target 75%",
                delta_color="normal" if diff_csat >= 0 else "inverse",
                help=f"Dựa trên {survey_resp_cnt} phản hồi khảo sát trong Quý. Hài lòng riêng về Hannah: {csat_hannah_pct:.1f}%."
            )
            if csat_pct >= 75.0:
                st.success(f"🟢 Vượt chuẩn chất lượng ({csat_pct:.1f}% hài lòng)")
            else:
                st.warning(f"🟡 Cần cải thiện trải nghiệm học tập")
        else:
            st.metric(
                label="⭐ 3. Tỷ Lòng Hài Lòng (CSAT Quý)",
                value="N/A",
                delta="Đang cập nhật survey"
            )
            st.info("ℹ️ Đang chờ dữ liệu khảo sát Quý")

    # Biểu đồ so sánh 3 chỉ số cốt lõi vs Benchmark
    c_core1, c_core2 = st.columns([3, 2])

    with c_core1:
        kpi_core_data = [
            {"CHỈ SỐ": "1. Active H1 (Tuần)", "THỰC TẾ (%)": round(act_h1_pct, 1), "BENCHMARK (%)": target_act, "TRẠNG THÁI": "ĐẠT CHUẨN" if act_h1_pct >= target_act else "CHƯA ĐẠT"},
            {"CHỈ SỐ": "2. Tiến Độ Tuần (H1)", "THỰC TẾ (%)": round(avg_gain_act, 2), "BENCHMARK (%)": target_gain, "TRẠNG THÁI": "ĐẠT CHUẨN" if avg_gain_act >= target_gain else "CHƯA ĐẠT"}
        ]
        if csat_pct is not None:
            kpi_core_data.append({
                "CHỈ SỐ": "3. Hài Lòng CSAT (Quý)", "THỰC TẾ (%)": round(csat_pct, 1), "BENCHMARK (%)": 75.0, "TRẠNG THÁI": "ĐẠT CHUẨN" if csat_pct >= 75.0 else "CHƯA ĐẠT"
            })

        df_core_bar = pd.DataFrame(kpi_core_data)
        df_core_melt = df_core_bar.melt(
            id_vars=["CHỈ SỐ", "TRẠNG THÁI"],
            value_vars=["THỰC TẾ (%)", "BENCHMARK (%)"],
            var_name="LOẠI",
            value_name="GIÁ_TRỊ"
        )

        fig_core_bench = px.bar(
            df_core_melt,
            x="CHỈ SỐ",
            y="GIÁ_TRỊ",
            color="LOẠI",
            barmode="group",
            text="GIÁ_TRỊ",
            color_discrete_map={"THỰC TẾ (%)": "#1f77b4", "BENCHMARK (%)": "#ff7f0e"},
            height=290,
            title="So Sánh 3 Chỉ Số Cốt Lõi: Thực Tế (%) vs Benchmark Mục Tiêu (%)"
        )
        fig_core_bench.update_layout(
            margin=dict(l=10, r=10, t=35, b=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_core_bench, use_container_width=True)

    with c_core2:
        if df_survey_q is not None and not df_survey_q.empty:
            survey_services = {
                "Hannah Phụ Trách": "2. Bạn đánh giá mức độ hài lòng đối với các dịch vụ dưới đây như thế nào? [Hannah]",
                "Chương Trình Học": "2. Bạn đánh giá mức độ hài lòng đối với các dịch vụ dưới đây như thế nào? [Chương trình học]",
                "Mentor Hỗ Trợ": "2. Bạn đánh giá mức độ hài lòng đối với các dịch vụ dưới đây như thế nào? [Mentor]",
                "Phòng Đào Tạo": "2. Bạn đánh giá mức độ hài lòng đối với các dịch vụ dưới đây như thế nào? [Đào tạo]",
                "Bộ Phận Khảo Thí": "2. Bạn đánh giá mức độ hài lòng đối với các dịch vụ dưới đây như thế nào? [Khảo thí]",
                "Hướng Nghiệp": "2. Bạn đánh giá mức độ hài lòng đối với các dịch vụ dưới đây như thế nào? [Hướng nghiệp]"
            }
            svc_res = []
            for s_name, col_name in survey_services.items():
                if col_name in df_survey_q.columns:
                    r_vals = df_survey_q[col_name].apply(ext_r).dropna()
                    if len(r_vals) > 0:
                        sat_rate = (r_vals >= 4).sum() / len(r_vals) * 100
                        svc_res.append({
                            "MẢNG DỊCH VỤ": s_name,
                            "TỶ LỆ HÀI LÒNG (%)": round(sat_rate, 1),
                            "ĐIỂM TRUNG BÌNH (1-5)": round(r_vals.mean(), 2),
                            "SỐ PHẢN HỒI": len(r_vals)
                        })
            if svc_res:
                df_svc_table = pd.DataFrame(svc_res).sort_values("TỶ LỆ HÀI LÒNG (%)", ascending=False)
                fig_svc = px.bar(
                    df_svc_table,
                    x="MẢNG DỊCH VỤ",
                    y="TỶ LỆ HÀI LÒNG (%)",
                    color="TỶ LỆ HÀI LÒNG (%)",
                    color_continuous_scale="Teal",
                    text="TỶ LỆ HÀI LÒNG (%)",
                    height=290,
                    title="Chi Tiết Hài Lòng Theo Mảng Dịch Vụ (Survey)"
                )
                fig_svc.update_layout(margin=dict(l=10, r=10, t=35, b=10))
                st.plotly_chart(fig_svc, use_container_width=True)
            else:
                st.info("ℹ️ Chưa có dữ liệu mảng dịch vụ khảo sát")
        else:
            st.info("ℹ️ Đang chờ dữ liệu khảo sát Quý")

    st.markdown("---")

    # =========================================================================
    # PHẦN 2: TỶ LỆ HOÀN THÀNH MÔN THEO THỜI LƯỢNG KHÓA HỌC (NGẮN, TRUNG, DÀI)
    # =========================================================================
    st.markdown("### 🎯 2. Tỷ Lệ Hoàn Thành Môn Học Theo Nhóm Thời Lượng Khóa Đào Tạo")
    st.caption("Đo lường tiến độ và tỷ lệ On-Track / Hoàn thành theo 3 phân khúc: **Khóa ngắn (< 1 tháng)**, **Khóa trung hạn (1 – < 12 tháng)**, và **Khóa dài hạn (≥ 12 tháng)**.")

    # Tính toán chi tiết cho 3 nhóm
    # Nhóm 1: Khóa ngắn (< 1 tháng) - Target 70%
    df_g1 = df_base[df_base["NHÓM_THỜI_LƯỢNG"] == "1. Khóa ngắn (< 1 tháng)"]
    tot_g1 = len(df_g1)
    on_track_g1 = df_g1["KHẢ_NĂNG_HOÀN_THÀNH"].str.contains("On-Track|RẤT CAO|Đã hoàn thành", na=False).sum()
    pct_g1 = (on_track_g1 / tot_g1 * 100) if tot_g1 > 0 else 0.0
    avg_c_done_g1 = df_g1["TỶ_LỆ_XONG_MÔN"].mean() if tot_g1 > 0 else 0.0
    target_g1 = 70.0
    diff_g1 = pct_g1 - target_g1

    # Nhóm 2: Khóa trung hạn (1 - < 12 tháng) - Target 50%
    df_g2 = df_base[df_base["NHÓM_THỜI_LƯỢNG"] == "2. Khóa trung hạn (1 - < 12 tháng)"]
    tot_g2 = len(df_g2)
    on_track_g2 = df_g2["KHẢ_NĂNG_HOÀN_THÀNH"].str.contains("On-Track|RẤT CAO|Đã hoàn thành", na=False).sum()
    pct_g2 = (on_track_g2 / tot_g2 * 100) if tot_g2 > 0 else 0.0
    avg_c_done_g2 = df_g2["TỶ_LỆ_XONG_MÔN"].mean() if tot_g2 > 0 else 0.0
    target_g2 = 50.0
    diff_g2 = pct_g2 - target_g2

    # Nhóm 3: Khóa dài hạn (>= 12 tháng) - Target 30%
    df_g3 = df_base[df_base["NHÓM_THỜI_LƯỢNG"] == "3. Khóa dài hạn (≥ 12 tháng)"]
    tot_g3 = len(df_g3)
    on_track_g3 = df_g3["KHẢ_NĂNG_HOÀN_THÀNH"].str.contains("On-Track|RẤT CAO|Đã hoàn thành", na=False).sum()
    pct_g3 = (on_track_g3 / tot_g3 * 100) if tot_g3 > 0 else 0.0
    avg_c_done_g3 = df_g3["TỶ_LỆ_XONG_MÔN"].mean() if tot_g3 > 0 else 0.0
    target_g3 = 30.0
    diff_g3 = pct_g3 - target_g3

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric(
            label="⚡ Khóa Ngắn (< 1 Tháng)",
            value=f"{pct_g1:.1f}%",
            delta=f"{diff_g1:+.1f}% vs Target 70%",
            delta_color="normal" if diff_g1 >= 0 else "inverse",
            help=f"Tổng quy mô: {tot_g1} học viên. Đang On-Track/Hoàn thành: {on_track_g1} HV. Tỷ lệ xong môn TB: {avg_c_done_g1:.1f}%."
        )
        if pct_g1 >= target_g1:
            st.success(f"🟢 Đạt Benchmark 70% ({on_track_g1}/{tot_g1} HV On-Track)")
        else:
            st.error(f"🔴 Chưa đạt ({on_track_g1}/{tot_g1} HV On-Track)")

    with c2:
        st.metric(
            label="⏳ Khóa Trung Hạn (1 – < 12 Tháng)",
            value=f"{pct_g2:.1f}%",
            delta=f"{diff_g2:+.1f}% vs Target 50%",
            delta_color="normal" if diff_g2 >= 0 else "inverse",
            help=f"Tổng quy mô: {tot_g2} học viên. Đang On-Track/Hoàn thành: {on_track_g2} HV. Tỷ lệ xong môn TB: {avg_c_done_g2:.1f}%."
        )
        if pct_g2 >= target_g2:
            st.success(f"🟢 Đạt Benchmark 50% ({on_track_g2}/{tot_g2} HV On-Track)")
        else:
            st.warning(f"🔴 Thiếu {target_g2 - pct_g2:.1f}% ({on_track_g2}/{tot_g2} HV On-Track)")

    with c3:
        st.metric(
            label="🏛️ Khóa Dài Hạn (≥ 12 Tháng)",
            value=f"{pct_g3:.1f}%",
            delta=f"{diff_g3:+.1f}% vs Target 30%",
            delta_color="normal" if diff_g3 >= 0 else "inverse",
            help=f"Tổng quy mô: {tot_g3} học viên. Đang On-Track/Hoàn thành: {on_track_g3} HV. Tỷ lệ xong môn TB: {avg_c_done_g3:.1f}%."
        )
        if pct_g3 >= target_g3:
            st.success(f"🟢 Đạt Benchmark 30% ({on_track_g3}/{tot_g3} HV On-Track)")
        else:
            st.warning(f"🟡 Thiếu {target_g3 - pct_g3:.1f}% ({on_track_g3}/{tot_g3} HV On-Track)")

    # Biểu đồ và Bảng so sánh 3 nhóm khóa học
    col_course_ch1, col_course_ch2 = st.columns([1, 1])

    with col_course_ch1:
        course_bench_data = [
            {"NHÓM KHÓA": "Khóa Ngắn (< 1T)", "THỰC TẾ (%)": round(pct_g1, 1), "BENCHMARK (%)": target_g1},
            {"NHÓM KHÓA": "Khóa Trung (1-12T)", "THỰC TẾ (%)": round(pct_g2, 1), "BENCHMARK (%)": target_g2},
            {"NHÓM KHÓA": "Khóa Dài (≥ 12T)", "THỰC TẾ (%)": round(pct_g3, 1), "BENCHMARK (%)": target_g3}
        ]
        df_c_bench = pd.DataFrame(course_bench_data)
        df_c_melt = df_c_bench.melt(
            id_vars=["NHÓM KHÓA"],
            value_vars=["THỰC TẾ (%)", "BENCHMARK (%)"],
            var_name="LOẠI",
            value_name="TỶ LỆ (%)"
        )
        fig_course_bench = px.bar(
            df_c_melt,
            x="NHÓM KHÓA",
            y="TỶ LỆ (%)",
            color="LOẠI",
            barmode="group",
            text="TỶ LỆ (%)",
            color_discrete_map={"THỰC TẾ (%)": "#0ca678", "BENCHMARK (%)": "#f59f00"},
            height=320,
            title="So Sánh Tỷ Lệ On-Track / Hoàn Thành Thực Tế vs Benchmark Target"
        )
        fig_course_bench.update_layout(
            margin=dict(l=10, r=10, t=35, b=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_course_bench, use_container_width=True)

    with col_course_ch2:
        df_status_summary = df_base.groupby(["NHÓM_THỜI_LƯỢNG", "KHẢ_NĂNG_HOÀN_THÀNH"]).size().reset_index(name="SỐ_HV")
        fig_course_status = px.bar(
            df_status_summary,
            x="NHÓM_THỜI_LƯỢNG",
            y="SỐ_HV",
            color="KHẢ_NĂNG_HOÀN_THÀNH",
            barmode="stack",
            height=320,
            title="Cơ Cấu Trạng Thái Tiến Độ Học Tập Của Từng Nhóm Khóa"
        )
        fig_course_status.update_layout(margin=dict(l=10, r=10, t=35, b=10), showlegend=False)
        st.plotly_chart(fig_course_status, use_container_width=True)

    # Bảng tổng kết số liệu 3 nhóm khóa học
    summary_course_rows = [
        {
            "Nhóm Thời Lượng": "1. Khóa ngắn (< 1 tháng)",
            "Tổng Số Học Viên": tot_g1,
            "Số HV On-Track / Hoàn Thành": on_track_g1,
            "Tỷ Lệ Thực Tế (%)": f"{pct_g1:.1f}%",
            "Mục Tiêu Benchmark (%)": f"{target_g1:.0f}%",
            "Đánh Giá": "🟢 Đạt Benchmark" if pct_g1 >= target_g1 else "🔴 Chưa đạt",
            "Tỷ Lệ Xong Môn TB": f"{avg_c_done_g1:.1f}%"
        },
        {
            "Nhóm Thời Lượng": "2. Khóa trung hạn (1 - < 12 tháng)",
            "Tổng Số Học Viên": tot_g2,
            "Số HV On-Track / Hoàn Thành": on_track_g2,
            "Tỷ Lệ Thực Tế (%)": f"{pct_g2:.1f}%",
            "Mục Tiêu Benchmark (%)": f"{target_g2:.0f}%",
            "Đánh Giá": "🟢 Đạt Benchmark" if pct_g2 >= target_g2 else "🔴 Cần đẩy mạnh",
            "Tỷ Lệ Xong Môn TB": f"{avg_c_done_g2:.1f}%"
        },
        {
            "Nhóm Thời Lượng": "3. Khóa dài hạn (≥ 12 tháng)",
            "Tổng Số Học Viên": tot_g3,
            "Số HV On-Track / Hoàn Thành": on_track_g3,
            "Tỷ Lệ Thực Tế (%)": f"{pct_g3:.1f}%",
            "Mục Tiêu Benchmark (%)": f"{target_g3:.0f}%",
            "Đánh Giá": "🟢 Đạt Benchmark" if pct_g3 >= target_g3 else "🟡 Cần cải thiện",
            "Tỷ Lệ Xong Môn TB": f"{avg_c_done_g3:.1f}%"
        }
    ]
    st.dataframe(pd.DataFrame(summary_course_rows), use_container_width=True, hide_index=True)

    st.markdown("---")

    # =========================================================================
    # PHẦN 3: KẾT LUẬN & NHẬN XÉT ĐIỀU HÀNH TUẦN / QUÝ (TỰ ĐỘNG THEO KỲ BÁO CÁO)
    # =========================================================================
    st.markdown(f"### 📋 3. Kết Luận Tuần / Quý ({period_title})")
    st.caption("Nhận định đánh giá tổng hợp tự động theo số liệu thực tế của kỳ báo cáo.")

    concl_col1, concl_col2 = st.columns(2)

    with concl_col1:
        act_note = f"Tỷ lệ học viên hoạt động đạt <b>{act_h1_pct:.2f}%</b> ({act_h1_cnt:,}/{tot_h1_kpi:,} học viên có Activity)."
        
        st.markdown(f"""
        <div style="background-color: #f0fdf4; border-left: 5px solid #16a34a; padding: 16px 20px; border-radius: 8px; margin-bottom: 12px; height: 100%;">
            <h5 style="color: #166534; margin: 0 0 10px 0; font-size: 15px; font-weight: 700;">⚡ 1. Hoạt động học tập chung (Activity Rate):</h5>
            <ul style="color: #15803d; margin: 0; padding-left: 20px; font-size: 14px; line-height: 1.6;">
                <li>{act_note}</li>
                <li>Mục tiêu Benchmark đề ra là <b>70.0%</b> (hiện đang {'vượt chỉ tiêu' if act_h1_pct >= 70.0 else f'còn cách mục tiêu {70.0 - act_h1_pct:.1f}%'}).</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

    with concl_col2:
        st.markdown(f"""
        <div style="background-color: #f0f9ff; border-left: 5px solid #0284c7; padding: 16px 20px; border-radius: 8px; margin-bottom: 12px; height: 100%;">
            <h5 style="color: #075985; margin: 0 0 10px 0; font-size: 15px; font-weight: 700;">📚 2. Về nhịp học tập & Tiến độ (Academic Progress):</h5>
            <ul style="color: #0369a1; margin: 0; padding-left: 20px; font-size: 14px; line-height: 1.6;">
                <li>Tiến độ môn học tích lũy trung bình của 1 học viên đạt <b>{avg_prog_h1:.1f}%</b> (tính từ 5 hạng mục Quiz + Lab + ASM + Progress Test + Final Exam, không dùng XP).</li>
                <li>Mức tăng tiến độ tuần bình quân nhóm Active đạt <b>+{avg_gain_act:.2f}%/HV</b>. Trong đó, riêng nhóm <b>{gain_cnt:,} học viên có nộp bài đánh giá</b> đạt mức bứt phá rất cao là <b>+{avg_gain_pos:.1f}%/HV</b>.</li>
                <li>Học viên đang ở giai đoạn nạp kiến thức lý thuyết và hoàn thiện đồ án lớn, chuẩn bị cho các đợt nộp bài tập trung ở các tuần kế tiếp.</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

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
        c1_head, c1_ctrl = st.columns([1.6, 1.4])
        with c1_head:
            st.markdown("##### 📊 Xu Hướng Học Viên Từng Tag Qua Các Tuần")
        with c1_ctrl:
            trend_view_mode = st.radio(
                "Chế độ hiển thị:",
                ["Số lượng (kèm %)", "Tỷ trọng 100%"],
                horizontal=True,
                label_visibility="collapsed",
                key="tag_trend_view_mode",
                help="Chọn 'Số lượng (kèm %)' để xem số lượng thực tế kèm nhãn %, hoặc 'Tỷ trọng 100%' để so sánh cơ cấu tỷ lệ học viên qua các tuần."
            )

        df_trend_src = df_quarter.copy()
        if selected_hannahs and len(selected_hannahs) < len(all_hannahs):
            df_trend_src = df_trend_src[df_trend_src["HANNAH"].isin(selected_hannahs)]
        if selected_progs and len(selected_progs) < len(all_progs):
            df_trend_src = df_trend_src[df_trend_src["CHƯƠNG_TRÌNH"].isin(selected_progs)]

        df_tag_trend = df_trend_src.groupby(["WEEK", "TAG_CODE"]).size().reset_index(name="SỐ_LƯỢNG")

        if not df_tag_trend.empty:
            total_per_week = df_tag_trend.groupby("WEEK")["SỐ_LƯỢNG"].transform("sum")
            df_tag_trend["TỔNG_TUẦN"] = total_per_week
            df_tag_trend["TỶ_LỆ"] = np.where(total_per_week > 0, (df_tag_trend["SỐ_LƯỢNG"] / total_per_week * 100), 0.0)

            # Nhãn hiển thị trên thanh cột:
            # - Dạng Số lượng: hiển thị Số lượng và % (hoặc chỉ % nếu phân đoạn vừa phải)
            df_tag_trend["NHÃN_SỐ_LƯỢNG"] = df_tag_trend.apply(
                lambda r: f"{r['SỐ_LƯỢNG']:,}<br>({r['TỶ_LỆ']:.1f}%)" if r["TỶ_LỆ"] >= 7.0 else (f"{r['TỶ_LỆ']:.1f}%" if r["TỶ_LỆ"] >= 3.5 else ""),
                axis=1
            )
            # - Dạng Tỷ trọng 100%: hiển thị %
            df_tag_trend["NHÃN_TỶ_LỆ"] = df_tag_trend["TỶ_LỆ"].apply(
                lambda v: f"{v:.1f}%" if v >= 3.5 else ""
            )

            sorted_weeks = sorted(df_tag_trend["WEEK"].unique().tolist())
            tag_order = ["H1", "H2.1", "H2.2", "H0.1", "H0.2", "Khác"]

            is_pct_mode = (trend_view_mode == "Tỷ trọng 100%")
            y_field = "TỶ_LỆ" if is_pct_mode else "SỐ_LƯỢNG"
            text_field = "NHÃN_TỶ_LỆ" if is_pct_mode else "NHÃN_SỐ_LƯỢNG"

            fig_tt = px.bar(
                df_tag_trend,
                x="WEEK",
                y=y_field,
                color="TAG_CODE",
                text=text_field,
                custom_data=["TAG_CODE", "SỐ_LƯỢNG", "TỶ_LỆ", "WEEK"],
                category_orders={"WEEK": sorted_weeks, "TAG_CODE": tag_order},
                color_discrete_map={
                    "H1": "#1c7ed6", "H2.1": "#0ca678", "H2.2": "#f59f00",
                    "H0.1": "#f03e3e", "H0.2": "#868e96", "Khác": "#adb5bd"
                },
                barmode="stack",
                height=350
            )

            hover_tmpl = (
                "<b>Tuần %{customdata[3]} — Tag %{customdata[0]}</b><br>"
                "Tỷ trọng trong tuần: <b>%{customdata[2]:.1f}%</b><br>"
                "Số lượng: <b>%{customdata[1]:,} học viên</b><extra></extra>"
            ) if is_pct_mode else (
                "<b>Tuần %{customdata[3]} — Tag %{customdata[0]}</b><br>"
                "Số lượng: <b>%{customdata[1]:,} học viên</b><br>"
                "Tỷ trọng trong tuần: <b>%{customdata[2]:.1f}%</b><extra></extra>"
            )

            fig_tt.update_traces(
                textposition="inside",
                insidetextanchor="middle",
                textfont=dict(size=11),
                hovertemplate=hover_tmpl
            )

            if is_pct_mode:
                fig_tt.update_layout(
                    yaxis=dict(title="Tỷ trọng (%)", range=[0, 100], ticksuffix="%"),
                    xaxis=dict(title=""),
                    margin=dict(l=10, r=10, t=10, b=10),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
            else:
                fig_tt.update_layout(
                    yaxis=dict(title="Số lượng học viên"),
                    xaxis=dict(title=""),
                    margin=dict(l=10, r=10, t=10, b=10),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )

            st.plotly_chart(fig_tt, use_container_width=True)

            with st.expander("📋 Xem bảng số liệu chi tiết (Số lượng & % tỷ trọng từng tuần)", expanded=False):
                pivot_pct = df_tag_trend.pivot(index="TAG_CODE", columns="WEEK", values="TỶ_LỆ").fillna(0)
                pivot_cnt = df_tag_trend.pivot(index="TAG_CODE", columns="WEEK", values="SỐ_LƯỢNG").fillna(0)
                
                existing_tags = [t for t in tag_order if t in pivot_cnt.index] + [t for t in pivot_cnt.index if t not in tag_order]
                pivot_summary = pd.DataFrame(index=existing_tags)
                
                for col in sorted_weeks:
                    if col in pivot_cnt.columns:
                        col_cnt = pivot_cnt[col]
                        col_pct = pivot_pct[col]
                        pivot_summary[col] = [
                            f"{int(col_cnt.get(t, 0)):,} ({col_pct.get(t, 0.0):.1f}%)" for t in existing_tags
                        ]
                
                total_row = {}
                for col in sorted_weeks:
                    if col in pivot_cnt.columns:
                        tot = int(pivot_cnt[col].sum())
                        total_row[col] = f"{tot:,} (100.0%)"
                    else:
                        total_row[col] = "-"
                total_df = pd.DataFrame([total_row], index=["TỔNG CỘNG"])
                pivot_final = pd.concat([pivot_summary, total_df])
                
                st.dataframe(pivot_final, use_container_width=True)
        else:
            st.info("Không có dữ liệu xu hướng học viên theo Tag.")

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
        "SỐ_MÔN_CÒN_LẠI", "THÁNG_CÒN_LẠI", "TOTAL_ACTIVITY",
        "KHẢ_NĂNG_HOÀN_THÀNH", "TIẾN_ĐỘ_HỌC_THUẬT", "SẢN_PHẨM_TUẦN_NÀY", "BÀI_TẬP_CÒN_THIẾU", "ACTION_SUGGESTION"
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
            "MÔN_ĐANG_HỌC": st.column_config.TextColumn("Môn Đang Học", width="small"),
            "SỐ_MÔN_CÒN_LẠI": st.column_config.NumberColumn("Môn Còn Lại", width="small"),
            "THÁNG_CÒN_LẠI": st.column_config.TextColumn("Tháng Còn Lại", width="small"),
            "TOTAL_ACTIVITY": st.column_config.NumberColumn("Activity Tuần", width="small"),
            "KHẢ_NĂNG_HOÀN_THÀNH": st.column_config.TextColumn("Đánh Giá Hoàn Thành", width="medium"),
            "TIẾN_ĐỘ_HỌC_THUẬT": st.column_config.ProgressColumn("Tiến Độ Môn", min_value=0, max_value=100, format="%.1f%%"),
            "SẢN_PHẨM_TUẦN_NÀY": st.column_config.TextColumn("📝 Bài Nộp Tuần Này", width="medium", help="Bài tập Quiz, Lab, ASM... học viên mới nộp thêm trong tuần"),
            "BÀI_TẬP_CÒN_THIẾU": st.column_config.TextColumn("Bài Tập Còn Thiếu (Quiz/Lab/ASM...)", width="medium"),
            "ACTION_SUGGESTION": st.column_config.TextColumn("💡 Action Gợi Ý Cụ Thể Cho Hannah", width="large")
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
            "TB TIẾN ĐỘ MÔN (%)": round(grp["TIẾN_ĐỘ_HỌC_THUẬT"].mean(), 1) if "TIẾN_ĐỘ_HỌC_THUẬT" in grp.columns else 0.0,
            "MỨC TĂNG TUẦN (%)": round(grp["DELTA_TIẾN_ĐỘ"].mean(), 2) if "DELTA_TIẾN_ĐỘ" in grp.columns else 0.0,
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
            "TB TIẾN ĐỘ MÔN (%)": st.column_config.NumberColumn("TB Tiến Độ Môn (%)", format="%.1f%%", help="Tiến độ học thuật trung bình của học viên phụ trách (Quiz + Lab + ASM + PT + FE)"),
            "MỨC TĂNG TUẦN (%)": st.column_config.NumberColumn("Mức Tăng Tuần (%)", format="%.2f%%", help="Mức tăng tiến độ trung bình của học viên trong tuần"),
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
        st.markdown("##### 🚨 Phân Bổ Học Viên Cứu Nguy Thành Công vs Vẫn Bất Động Theo Hannah")
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
# TAB 4: PHÂN TÍCH QUY TRÌNH HỌC TẬP & PHỄU CHUYỂN HÓA HỌC THUẬT THEO TUẦN
# =========================================================================
with tab4:
    period_label = selected_week if selected_week != "Tất cả tuần trong Quý" else selected_quarter
    st.subheader(f"📚 Phân Tích Quy Trình Học Tập & Chuyển Hóa Học Thuật ({period_label})")
    st.caption("Mô hình phễu 3 bước: **(1) Vào học LMS ➔ (2) Hỗ trợ Mentor ➔ (3) Hoàn thành Sản phẩm Học thuật**, phân tích sâu hành vi và giải quyết điểm nghẽn học tập.")

    tot_deep = len(df_deep)

    # Đếm số lượng học viên tham gia từng giai đoạn
    n_access = (df_deep["LEARNING_ACCESS"] > 0).sum()
    tot_access = int(df_deep["LEARNING_ACCESS"].sum())
    pct_access = (n_access / tot_deep * 100) if tot_deep > 0 else 0.0

    n_mentor = (df_deep["MENTOR_SUPPORT"] > 0).sum()
    tot_mentor = int(df_deep["MENTOR_SUPPORT"].sum())
    pct_mentor = (n_mentor / tot_deep * 100) if tot_deep > 0 else 0.0

    n_output = (df_deep["ACADEMIC_OUTPUT"] > 0).sum()
    tot_output = int(df_deep["ACADEMIC_OUTPUT"].sum())
    pct_output = (n_output / tot_deep * 100) if tot_deep > 0 else 0.0

    # Tỷ lệ chuyển hóa từ Vào học LMS -> Ra sản phẩm bài tập
    pct_conv = (n_output / n_access * 100) if n_access > 0 else 0.0

    # Phân nhóm hành vi học tập
    n_stuck = ((df_deep["LEARNING_ACCESS"] > 0) & (df_deep["ACADEMIC_OUTPUT"] == 0)).sum()
    pct_stuck = (n_stuck / tot_deep * 100) if tot_deep > 0 else 0.0

    n_inact = (df_deep["TOTAL_ACTIVITY"] == 0).sum()
    pct_inact = (n_inact / tot_deep * 100) if tot_deep > 0 else 0.0

    # -------------------------------------------------------------
    # KHỐI 1: PHỄU CHUYỂN HÓA HỌC TẬP TUẦN (WEEKLY PIPELINE CARDS)
    # -------------------------------------------------------------
    st.markdown(f"##### ⚡ 1. Phễu Hoạt Động & Chuyển Hóa Học Tập Trong Tuần ({period_label})")
    
    col_p1, col_p2, col_p3, col_p4 = st.columns(4)
    with col_p1:
        st.markdown(f"""
        <div class="metric-card" style="border-left-color: #1c7ed6;">
            <div class="metric-title" style="color: #1c7ed6;">🌐 BƯỚC 1: VÀO HỌC LMS</div>
            <div class="metric-value">{n_access:,} <span style="font-size: 16px; font-weight: normal; color: #6c757d;">HV</span></div>
            <div class="metric-sub"><b>{pct_access:.1f}%</b> quy mô • Tổng {tot_access:,} lượt vào học</div>
        </div>
        """, unsafe_allow_html=True)

    with col_p2:
        st.markdown(f"""
        <div class="metric-card" style="border-left-color: #7950f2;">
            <div class="metric-title" style="color: #7950f2;">🤝 BƯỚC 2: DÙNG MENTOR</div>
            <div class="metric-value">{n_mentor:,} <span style="font-size: 16px; font-weight: normal; color: #6c757d;">HV</span></div>
            <div class="metric-sub"><b>{pct_mentor:.1f}%</b> quy mô • Tổng {tot_mentor:,} lượt kết nối/zoom</div>
        </div>
        """, unsafe_allow_html=True)

    with col_p3:
        st.markdown(f"""
        <div class="metric-card" style="border-left-color: #0ca678;">
            <div class="metric-title" style="color: #0ca678;">📝 BƯỚC 3: RA SẢN PHẨM</div>
            <div class="metric-value">{n_output:,} <span style="font-size: 16px; font-weight: normal; color: #6c757d;">HV</span></div>
            <div class="metric-sub"><b>{pct_output:.1f}%</b> quy mô • Tổng <b>{tot_output:,}</b> bài nộp & pass</div>
        </div>
        """, unsafe_allow_html=True)

    with col_p4:
        st.markdown(f"""
        <div class="metric-card" style="border-left-color: #f59f00;">
            <div class="metric-title" style="color: #f59f00;">🎯 HIỆU SUẤT CHUYỂN HÓA</div>
            <div class="metric-value">{pct_conv:.1f}%</div>
            <div class="metric-sub">Cứ 100 HV vào học có <b>{pct_conv:.1f}</b> bạn ra bài</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # -------------------------------------------------------------
    # KHỐI 2: PHÂN TÍCH SÂU HÀNH VI & BẰNG CHỨNG TÁC ĐỘNG MENTOR
    # -------------------------------------------------------------
    st.markdown("##### 🔬 2. Phân Tích Sâu Hành Vi Học Tập & Bằng Chứng Tác Động Mentor")

    # Tính toán tác động của Mentor đối với tỷ lệ nộp bài
    with_m = df_deep[df_deep["MENTOR_SUPPORT"] > 0]
    no_m = df_deep[df_deep["MENTOR_SUPPORT"] == 0]
    pct_m_out = (with_m["ACADEMIC_OUTPUT"] > 0).sum() / len(with_m) * 100 if len(with_m) > 0 else 0.0
    pct_nom_out = (no_m["ACADEMIC_OUTPUT"] > 0).sum() / len(no_m) * 100 if len(no_m) > 0 else 0.0
    delta_mentor = pct_m_out - pct_nom_out

    # Callout insight chứng minh giá trị Mentor
    st.markdown(f"""
    <div style="background-color: #e7f5ff; border: 1px solid #74c0fc; border-left: 5px solid #1c7ed6; border-radius: 8px; padding: 12px 16px; margin-bottom: 16px;">
        <b style="color: #1864ab;">💡 BẰNG CHỨNG DỮ LIỆU VỀ TÁC ĐỘNG CỦA MENTOR SUPPORT:</b><br>
        • Học viên <b>CÓ kết nối Mentor</b> trong tuần đạt tỷ lệ nộp bài <b>{pct_m_out:.1f}%</b> ({(with_m['ACADEMIC_OUTPUT'] > 0).sum()}/{len(with_m)} bạn).<br>
        • Học viên <b>KHÔNG hỏi Mentor</b> chỉ đạt tỷ lệ nộp bài <b>{pct_nom_out:.1f}%</b> ({(no_m['ACADEMIC_OUTPUT'] > 0).sum()}/{len(no_m)} bạn).<br>
        ➔ <b style="color: #2b8a3e;">Mentor Support giúp tăng cơ hội hoàn thành bài tập thêm +{delta_mentor:.1f}%!</b> Thúc đẩy học viên hỏi Mentor là đòn bẩy quan trọng nhất để chuyển hóa từ "Vào học" sang "Nộp bài".
    </div>
    """, unsafe_allow_html=True)

    g1, g2 = st.columns([1, 1])

    with g1:
        st.markdown("###### 🔻 Phễu Chuyển Hóa Học Tập Trong Tuần")
        fig_funnel = go.Figure(go.Funnel(
            y=["1. Quy Mô Học Viên H1", "2. Có Vào Học LMS", "3. Nộp Bài Thành Công"],
            x=[tot_deep, n_access, n_output],
            textinfo="value+percent initial",
            marker=dict(color=["#1c7ed6", "#339af0", "#0ca678"])
        ))
        fig_funnel.update_layout(
            margin=dict(l=10, r=10, t=10, b=10),
            height=270
        )
        st.plotly_chart(fig_funnel, use_container_width=True)

    with g2:
        st.markdown("###### 🍩 Cơ Cấu 3 Nhóm Hành Vi Học Tập Trong Tuần")
        df_seg = pd.DataFrame({
            "PHÂN_KHÚC": [
                "🟢 Nộp bài thành công",
                "🟡 Vào học nhưng kẹt bài (Chưa nộp)",
                "🔴 Bất động hoàn toàn"
            ],
            "SỐ_LƯỢNG": [n_output, n_stuck, n_inact]
        })
        fig_seg = px.pie(
            df_seg,
            names="PHÂN_KHÚC",
            values="SỐ_LƯỢNG",
            color="PHÂN_KHÚC",
            color_discrete_map={
                "🟢 Nộp bài thành công": "#0ca678",
                "🟡 Vào học nhưng kẹt bài (Chưa nộp)": "#f59f00",
                "🔴 Bất động hoàn toàn": "#f03e3e"
            },
            hole=0.45,
            height=270
        )
        fig_seg.update_traces(textposition="inside", textinfo="percent+label")
        fig_seg.update_layout(margin=dict(l=10, r=10, t=10, b=10), showlegend=False)
        st.plotly_chart(fig_seg, use_container_width=True)

    st.markdown("---")

    # -------------------------------------------------------------
    # KHỐI 3: SO SÁNH HIỆU QUẢ CHUYỂN HÓA THEO TỪNG HANNAH
    # -------------------------------------------------------------
    st.markdown(f"##### 👩‍💼 3. So Sánh Hiệu Quả Chuyển Hóa Học Tập Giữa Các Hannah ({period_label})")

    h_pipe = df_deep.groupby("HANNAH").apply(lambda g: pd.Series({
        "TỔNG_HV": len(g),
        "HV_VÀO_LMS": (g["LEARNING_ACCESS"] > 0).sum(),
        "%_VÀO_LMS": round((g["LEARNING_ACCESS"] > 0).sum() / len(g) * 100, 1),
        "HV_HỎI_MENTOR": (g["MENTOR_SUPPORT"] > 0).sum(),
        "%_DÙNG_MENTOR": round((g["MENTOR_SUPPORT"] > 0).sum() / len(g) * 100, 1),
        "HV_NỘP_BÀI": (g["ACADEMIC_OUTPUT"] > 0).sum(),
        "%_NỘP_BÀI": round((g["ACADEMIC_OUTPUT"] > 0).sum() / len(g) * 100, 1),
        "HV_KẸT_TIẾN_ĐỘ": ((g["LEARNING_ACCESS"] > 0) & (g["ACADEMIC_OUTPUT"] == 0)).sum(),
        "HV_BẤT_ĐỘNG": (g["TOTAL_ACTIVITY"] == 0).sum(),
        "TỔNG_SẢN_PHẨM": int(g["ACADEMIC_OUTPUT"].sum()),
        "TỶ_LỆ_CHUYỂN_HÓA": round((g["ACADEMIC_OUTPUT"] > 0).sum() / max((g["LEARNING_ACCESS"] > 0).sum(), 1) * 100, 1)
    })).reset_index()

    h_col1, h_col2 = st.columns([1.2, 0.8])

    with h_col1:
        st.markdown("###### 📊 Khối Lượng Hành Vi Học Tập Từng Hannah")
        h_pipe_melted = h_pipe.melt(
            id_vars="HANNAH",
            value_vars=["HV_VÀO_LMS", "HV_HỎI_MENTOR", "HV_NỘP_BÀI", "HV_KẸT_TIẾN_ĐỘ"],
            var_name="LOẠI_HÀNH_VI",
            value_name="SỐ_HV"
        )
        h_pipe_melted["LOẠI_HÀNH_VI"] = h_pipe_melted["LOẠI_HÀNH_VI"].map({
            "HV_VÀO_LMS": "1. Vào học LMS",
            "HV_HỎI_MENTOR": "2. Dùng Mentor",
            "HV_NỘP_BÀI": "3. Nộp bài thành công",
            "HV_KẸT_TIẾN_ĐỘ": "⚠️ Kẹt bài (Chưa nộp)"
        })

        fig_h_pipe = px.bar(
            h_pipe_melted,
            x="HANNAH",
            y="SỐ_HV",
            color="LOẠI_HÀNH_VI",
            barmode="group",
            text="SỐ_HV",
            color_discrete_map={
                "1. Vào học LMS": "#1c7ed6",
                "2. Dùng Mentor": "#7950f2",
                "3. Nộp bài thành công": "#0ca678",
                "⚠️ Kẹt bài (Chưa nộp)": "#f59f00"
            },
            height=320
        )
        fig_h_pipe.update_traces(textposition="outside")
        fig_h_pipe.update_layout(
            margin=dict(l=10, r=10, t=10, b=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_h_pipe, use_container_width=True)

    with h_col2:
        st.markdown("###### 📋 Bảng So Sánh Chi Tiết")
        st.dataframe(
            h_pipe[[
                "HANNAH", "TỔNG_HV", "%_VÀO_LMS", "%_DÙNG_MENTOR",
                "%_NỘP_BÀI", "HV_KẸT_TIẾN_ĐỘ", "TỔNG_SẢN_PHẨM"
            ]].rename(columns={
                "HANNAH": "Hannah",
                "TỔNG_HV": "Tổng HV",
                "%_VÀO_LMS": "% Vào LMS",
                "%_DÙNG_MENTOR": "% Mentor",
                "%_NỘP_BÀI": "% Nộp bài",
                "HV_KẸT_TIẾN_ĐỘ": "⚠️ Kẹt bài",
                "TỔNG_SẢN_PHẨM": "Bài đạt"
            }),
            use_container_width=True,
            hide_index=True
        )

    st.markdown("---")

    # -------------------------------------------------------------
    # KHỐI 4: DANH SÁCH HỌC VIÊN ĐỂ HANNAH HÀNH ĐỘNG NGAY (ACTION DRILL-DOWN)
    # -------------------------------------------------------------
    st.markdown("##### 🎯 4. Danh Sách Học Viên Theo Từng Phân Khúc Để Hannah Can Thiệp")

    def assign_action_segment(r):
        acc = r["LEARNING_ACCESS"]
        men = r["MENTOR_SUPPORT"]
        out = r["ACADEMIC_OUTPUT"]
        act = r["TOTAL_ACTIVITY"]
        if out > 0:
            return "🟢 Đã nộp bài thành công"
        elif acc > 0:
            if men > 0:
                return "🤝 Có hỏi Mentor nhưng chưa nộp bài"
            return "🟡 Vào học nhưng kẹt tiến độ (Cần Push nộp bài)"
        elif act > 0:
            return "⚪ Có hoạt động khác (Chưa nộp bài)"
        else:
            return "🔴 Bất động hoàn toàn (Không học)"

    df_deep_action = df_deep.copy()
    df_deep_action["PHÂN_KHÚC_HÀNH_VI"] = df_deep_action.apply(assign_action_segment, axis=1)

    c_filter, c_count = st.columns([2, 1])
    with c_filter:
        selected_seg = st.selectbox(
            "Chọn phân khúc học viên cần xử lý:",
            [
                "🟡 Vào học nhưng kẹt tiến độ (Cần Push nộp bài)",
                "🔴 Bất động hoàn toàn (Không học)",
                "🤝 Có hỏi Mentor nhưng chưa nộp bài",
                "🟢 Đã nộp bài thành công",
                "Tất cả học viên H1"
            ],
            index=0
        )

    df_filtered_action = df_deep_action.copy()
    if selected_seg != "Tất cả học viên H1":
        df_filtered_action = df_filtered_action[df_filtered_action["PHÂN_KHÚC_HÀNH_VI"] == selected_seg]

    with c_count:
        st.markdown(f"<div style='margin-top: 28px; font-weight: bold; color: #1c7ed6;'>🔍 Số lượng: {len(df_filtered_action):,} học viên</div>", unsafe_allow_html=True)

    action_cols = [
        "MSSV", "FULL_NAME", "HANNAH", "CHƯƠNG_TRÌNH", "MÔN_ĐANG_HỌC",
        "TIẾN_ĐỘ_HỌC_THUẬT", "LEARNING_ACCESS", "MENTOR_SUPPORT", "ACADEMIC_OUTPUT", "TOTAL_ACTIVITY",
        "RISK_LEVEL", "ACTION_SUGGESTION"
    ]
    present_action_cols = [c for c in action_cols if c in df_filtered_action.columns]

    st.dataframe(
        df_filtered_action[present_action_cols].rename(columns={
            "FULL_NAME": "Họ và tên",
            "HANNAH": "Hannah",
            "CHƯƠNG_TRÌNH": "Chương trình",
            "MÔN_ĐANG_HỌC": "Môn đang học",
            "TIẾN_ĐỘ_HỌC_THUẬT": "Tiến Độ Môn (%)",
            "LEARNING_ACCESS": "Vào LMS",
            "MENTOR_SUPPORT": "Hỏi Mentor",
            "ACADEMIC_OUTPUT": "Bài Nộp",
            "TOTAL_ACTIVITY": "Tổng Activity",
            "RISK_LEVEL": "Mức Rủi Ro",
            "ACTION_SUGGESTION": "Đề Xuất Hành Động"
        }),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Tiến Độ Môn (%)": st.column_config.ProgressColumn("Tiến Độ Môn (%)", min_value=0, max_value=100, format="%.1f%%")
        }
    )

    # -------------------------------------------------------------
    # KHỐI 5: XU HƯỚNG PHỄU HỌC TẬP QUA CÁC TUẦN (EXPANDER)
    # -------------------------------------------------------------
    with st.expander("📈 Xem xu hướng biến động Phễu Học Tập qua các tuần trong Quý", expanded=False):
        df_trend_all = df_quarter[df_quarter["TAG_CODE"] == "H1"].copy() if "TAG_CODE" in df_quarter.columns else df_quarter.copy()
        for c in ["LEARNING_ACCESS", "MENTOR_SUPPORT", "ACADEMIC_OUTPUT", "TOTAL_ACTIVITY"]:
            if c in df_trend_all.columns:
                df_trend_all[c] = pd.to_numeric(df_trend_all[c], errors="coerce").fillna(0)

        weekly_trend = df_trend_all.groupby("WEEK").apply(lambda g: pd.Series({
            "1. Vào học LMS": (g["LEARNING_ACCESS"] > 0).sum(),
            "2. Nộp sản phẩm": (g["ACADEMIC_OUTPUT"] > 0).sum(),
            "3. Kẹt bài (Chưa nộp)": ((g["LEARNING_ACCESS"] > 0) & (g["ACADEMIC_OUTPUT"] == 0)).sum(),
            "4. Bất động hoàn toàn": (g["TOTAL_ACTIVITY"] == 0).sum()
        })).reset_index()

        trend_melted = weekly_trend.melt(id_vars="WEEK", var_name="CHỈ_SỐ", value_name="SỐ_HV")
        fig_trend = px.line(
            trend_melted,
            x="WEEK",
            y="SỐ_HV",
            color="CHỈ_SỐ",
            markers=True,
            color_discrete_map={
                "1. Vào học LMS": "#1c7ed6",
                "2. Nộp sản phẩm": "#0ca678",
                "3. Kẹt bài (Chưa nộp)": "#f59f00",
                "4. Bất động hoàn toàn": "#f03e3e"
            },
            height=320
        )
        fig_trend.update_layout(
            margin=dict(l=10, r=10, t=10, b=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_trend, use_container_width=True)

# =========================================================================
# TAB 5: ACTION BOARD ĐỐI SOÁT CHUYỂN BIẾN (H1) — 3 MỤC TIÊU NÂNG CẤP
# =========================================================================
with tab5:
    st.subheader(f"🚨 Action Board Đối Soát Chuyển Biến Học Viên H1 Nguy Cơ Cao {f'({prev_week_name} ➔ {selected_week})' if prev_week_name else ''}")
    st.caption("Tự động hiển thị **Action tuần trước**, đo lường **Chuyển biến học tập thực tế tuần này** và cho phép cập nhật **Action tuần mới**.")

    # Lọc học viên H1 nguy cơ cao (HIGH & CRITICAL) HOẶC học viên có chuyển biến đối soát
    target_recovery_keywords = "Đã cải thiện|Vẫn bất động|Mới phát sinh"
    df_urgent_h1 = df_deep[
        (df_deep["RISK_LEVEL"].isin(["HIGH", "CRITICAL"])) |
        (df_deep["CHUYỂN_BIẾN_TUẦN_NÀY"].str.contains(target_recovery_keywords, na=False))
    ].copy()

    if df_urgent_h1.empty:
        st.success("🎉 Xuất sắc! Không có học viên H1 nào cần theo dõi chuyển biến trong phạm vi bộ lọc này.")
    else:
        # Thống kê nhanh chuyển biến của nhóm cần theo dõi
        cnt_recov = len(df_urgent_h1[df_urgent_h1["CHUYỂN_BIẾN_TUẦN_NÀY"].str.contains("Đã cải thiện", na=False)])
        cnt_stag = len(df_urgent_h1[df_urgent_h1["CHUYỂN_BIẾN_TUẦN_NÀY"].str.contains("Vẫn bất động", na=False)])
        cnt_new = len(df_urgent_h1[df_urgent_h1["CHUYỂN_BIẾN_TUẦN_NÀY"].str.contains("Mới phát sinh", na=False)])

        k1, k2, k3 = st.columns(3)
        with k1:
            st.metric("🟢 ĐÃ CẢI THIỆN / CÓ HỌC LẠI", f"{cnt_recov} HV", help="Học viên tuần trước nguy cơ cao nhưng tuần này đã bắt đầu có hoạt động học tập / giảm rủi ro")
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

        if df_filtered_act.empty:
            st.info("ℹ️ Không tìm thấy học viên nào phù hợp với bộ lọc chuyển biến đã chọn.")
        else:
            df_filtered_act = df_filtered_act.reset_index(drop=True)

            # Gắn dữ liệu ghi chú tuần hiện tại đã lưu
            curr_notes = []
            curr_statuses = []
            for _, r in df_filtered_act.iterrows():
                target_w = r.get("WEEK", selected_week) if selected_week == "Tất cả tuần trong Quý" else selected_week
                key_curr = f"{target_w}_{r.get('MSSV', '')}"
                saved = notes_db.get(key_curr, {})
                curr_notes.append(saved.get("note", ""))
                curr_statuses.append(saved.get("status", "Chưa liên hệ"))

            df_filtered_act["Trạng thái xử lý tuần này"] = curr_statuses
            df_filtered_act["Ghi chú Action tuần này"] = curr_notes

            action_cols = [
                "WEEK", "MSSV", "FULL_NAME", "HANNAH", "MÔN_ĐANG_HỌC",
                "CHUYỂN_BIẾN_TUẦN_NÀY", "SẢN_PHẨM_TUẦN_NÀY", "ACTION_TUẦN_TRƯỚC",
                "INACTIVITY_WEEKS", "ROOT_CAUSE", "ACTION_SUGGESTION",
                "Trạng thái xử lý tuần này", "Ghi chú Action tuần này"
            ]
            valid_action_cols = [c for c in action_cols if c in df_filtered_act.columns]

            editor_safe_key = f"h1_action_editor_{str(selected_week).replace(' ', '_')}"
            edited_h1_board = st.data_editor(
                df_filtered_act[valid_action_cols],
                key=editor_safe_key,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "WEEK": st.column_config.TextColumn("Tuần", disabled=True, width="small"),
                    "MSSV": st.column_config.TextColumn("MSSV", disabled=True, width="small"),
                    "FULL_NAME": st.column_config.TextColumn("Họ và Tên", disabled=True, width="medium"),
                    "HANNAH": st.column_config.TextColumn("Hannah", disabled=True, width="small"),
                    "MÔN_ĐANG_HỌC": st.column_config.TextColumn("Môn", disabled=True, width="small"),
                    "CHUYỂN_BIẾN_TUẦN_NÀY": st.column_config.TextColumn("Chuyển Biến Tuần Này (vs Tuần Trước)", disabled=True, width="medium"),
                    "SẢN_PHẨM_TUẦN_NÀY": st.column_config.TextColumn("📝 Bài Nộp Tuần Này", disabled=True, width="medium", help="Bài tập Quiz, Lab, ASM... học viên mới làm trong tuần"),
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
                        target_row_w = row.get("WEEK", selected_week) if selected_week == "Tất cả tuần trong Quý" else selected_week
                        key = f"{target_row_w}_{row.get('MSSV', '')}"
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
        "TIẾN_ĐỘ_HỌC_THUẬT", "CHUYỂN_BIẾN_TUẦN_NÀY", "MÔN_HOÀN_THÀNH / TỔNG", "THÁNG_CÒN_LẠI",
        "QUIZ", "LAB", "ASSIGNMENT", "PROGRESS_TEST", "FINAL_EXAM",
        "TOTAL_ACTIVITY", "KHẢ_NĂNG_HOÀN_THÀNH", "RISK_LEVEL", "ROOT_CAUSE", "ACTION_SUGGESTION"
    ]
    present_h1_cols = [c for c in h1_view_cols if c in df_all_h1_view.columns]

    st.dataframe(
        df_all_h1_view[present_h1_cols],
        use_container_width=True,
        hide_index=True,
        column_config={
            "TIẾN_ĐỘ_HỌC_THUẬT": st.column_config.ProgressColumn("Tiến Độ Môn (%)", min_value=0, max_value=100, format="%.1f%%")
        }
    )

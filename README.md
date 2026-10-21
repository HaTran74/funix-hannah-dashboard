# 🎯 FUNiX Hannah Action Board & Executive Dashboard

Hệ thống Báo cáo Điều hành Đào tạo, Phân tích Hiệu suất Team Hannah & Điều phối Hành động can thiệp học viên.

## 🚀 Tính Năng Chính
- **Real-Time Google Sheets**: Tự động đồng bộ dữ liệu từ Google Sheets Master Data.
- **Phân rã Tag toàn diện**: Hiển thị quy mô Active theo các Tag: H1, H2.1, H2.2, H0.1, H0.2.
- **Tiến độ học viên H1 & Danh sách Push hoàn thành**: Ma trận cột tiến độ (Số môn còn lại vs Thời gian còn lại), đánh giá khả năng về đích và xuất danh sách push ra Excel.
- **Bóc tách 5 sản phẩm học thuật**: Quiz, Lab, Assignment, Progress Test, Final Exam.
- **Closed-Loop Action Tracking**:
  - Kế thừa ghi chú Action của tuần trước.
  - Tự động gắn nhãn chuyển biến thực tế giữa 2 tuần (🟢 Đã cải thiện / 🔴 Vẫn bất động / ⚠️ Mới phát sinh).
  - Đo lường Tỷ lệ Can thiệp Thành công (% Recovery Rate) và Tỷ lệ Phủ Action (% Covered) của từng Hannah.

## 📦 Cài Đặt & Chạy Local
```bash
pip install -r requirements.txt
streamlit run app.py
```

## 🌐 Triển Khai Lên Streamlit Community Cloud
1. Đẩy mã nguồn lên GitHub Repository (Private).
2. Truy cập [share.streamlit.io](https://share.streamlit.io).
3. Chọn Repository, Branch `main`, Main file path `app.py`.
4. Bấm **Deploy!**

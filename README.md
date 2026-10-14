# CapCut Madame Bình Editor Bot

Bot (Python + Claude API, có **giao diện web** và bản dòng lệnh) hướng dẫn edit video CapCut về bà Nguyễn Thị Bình theo kịch bản 7 cảnh (00:00 – 04:00).

Bot làm được:
- Hỏi tiến độ trước, đọc **ảnh chụp timeline CapCut** bạn gửi, rồi tiếp nối từ đúng chỗ bạn dừng.
- **Chỉ dùng các bản ghi âm có sẵn được chỉ định** trong `ghi_am/danh_sach.json`. Bot đo độ dài thật của từng file, so với khung giờ của kịch bản và báo cảnh nào dài/ngắn hơn bao nhiêu giây. Bot không đề xuất giọng AI (TTS) thay cho file đã thu.
- Tìm ảnh tư liệu trên web (web search), đưa từ khóa tiếng Việt và tiếng Anh, có nguồn.
- Viết hướng dẫn chi tiết cho từng đoạn: timeline, media, hiệu ứng/animation, text overlay, audio, các bước bấm trong CapCut.
- Nhớ tiến độ giữa các lần chạy (`ket_qua/lich_su.json`) và lưu mỗi câu trả lời thành file `.md` trong `ket_qua/`.

## Cài đặt

Cần Python 3.10 trở lên.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...  # Windows PowerShell: $env:ANTHROPIC_API_KEY="sk-ant-..."
```

## Khai báo bản ghi âm

1. Chép file ghi âm (mp3, m4a, wav, aac, ogg, flac…) vào thư mục `ghi_am/`.
2. Sửa `ghi_am/danh_sach.json`: mỗi file một dòng, ghi rõ thuộc **cảnh** nào (1–7). Một cảnh có thể có nhiều file.

```json
{
  "ban_ghi": [
    {"file": "canh1_mo_dau.mp3", "canh": 1, "mo_ta": "Voice-over mở đầu"},
    {"file": "canh7_hoc_sinh_noi.m4a", "canh": 7, "mo_ta": "Học sinh nói trước máy quay"}
  ]
}
```

File nào nằm trong thư mục mà **không có trong danh sách** thì bot bỏ qua.

Kiểm tra nhanh (không gọi API, không tốn tiền):

```bash
python -m madame_binh_bot --kiem-tra
```

## Chạy giao diện web (khuyên dùng)

```bash
python -m madame_binh_bot.web
```

Mở trình duyệt vào **http://127.0.0.1:5000**. Trên trang web bạn có thể:

- Trò chuyện với bot. Câu trả lời hiện dần theo thời gian thực, có bảng timeline, nút **Sao chép** và **Tải hướng dẫn (.md)**.
- Đính kèm ảnh chụp timeline CapCut: bấm 📎, **kéo thả**, hoặc **dán (Ctrl+V)** thẳng vào ô chat.
- Xem bảng **Ghi âm theo cảnh** (cột bên phải; trên điện thoại bấm nút 🎙). Mỗi cảnh hiện trạng thái *Vừa khung / Dài hơn / Ngắn hơn / Chưa có ghi âm*, có nút nghe thử từng file.
- **Tải ghi âm lên và gán cảnh** ngay trên web, gán cảnh cho file có sẵn trong thư mục, hoặc bấm **Bỏ** để bot không dùng file đó nữa (file vẫn còn trên máy).
- Bấm **Phiên mới** để làm lại từ đầu.

Tùy chọn: `--port 8000`, `--ghi-am <thư mục>`, `--ket-qua <thư mục>`. Mặc định web chỉ mở trên máy bạn (`127.0.0.1`). Đừng mở ra mạng ngoài vì API key của bạn được dùng cho mọi câu hỏi gửi tới.

## Chạy bản dòng lệnh

```bash
python -m madame_binh_bot
```

| Lệnh | Tác dụng |
|---|---|
| `/anh duong_dan.png` | Đính kèm ảnh chụp timeline / ảnh tư liệu vào tin nhắn kế tiếp |
| `/ghiam` | Quét lại thư mục ghi âm |
| `/moi` | Bắt đầu phiên mới (xóa tiến độ đã nhớ) |
| `/giup` | Xem danh sách lệnh |
| `/thoat` | Thoát |

Muốn viết nhiều dòng thì kết thúc mỗi dòng bằng dấu `\`.

Ví dụ:

```
Bạn: /anh ~/Desktop/timeline.png
Bạn: Mình làm xong cảnh 1 và 2 rồi, font Playfair Display, nhạc piano. Tiếp nối từ 00:55 giúp mình
```

Tùy chọn: `--ghi-am <thư mục>`, `--ket-qua <thư mục>`. Biến môi trường `MADAME_BINH_MODEL` (mặc định `claude-opus-5-5`) và `MADAME_BINH_EFFORT` (mặc định `high`).

## Cấu trúc

- `madame_binh_bot/kich_ban.py` — kịch bản 7 cảnh và system prompt (quy tắc của bot)
- `madame_binh_bot/ghi_am.py` — quét và đo độ dài ghi âm, đối chiếu với khung từng cảnh
- `madame_binh_bot/bot.py` — lõi hội thoại, gọi Claude API (streaming, web search, đính kèm ảnh) + bản dòng lệnh
- `madame_binh_bot/web.py` — server web (Flask)
- `madame_binh_bot/static/index.html` — giao diện web; `static/vendor/` chứa marked và DOMPurify để chạy được khi không có mạng

## Lưu ý

- File ghi âm và thư mục `ket_qua/` nằm trong `.gitignore`, không bị đẩy lên git.
- Bot được yêu cầu không bịa thông tin lịch sử. Các dữ kiện như "202 phiên họp công khai" hay "Anh hùng Lao động 2025" vẫn nên được đối chiếu với nguồn chính thống trước khi xuất bản video.

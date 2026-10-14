"""Kịch bản 7 cảnh và system prompt của bot.

Toàn bộ nội dung lịch sử ở đây lấy nguyên văn từ kịch bản người dùng cung cấp.
Không thêm dữ kiện mới vào file này — bot được yêu cầu tự kiểm chứng qua web search.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Canh:
    so: int
    ten: str
    bat_dau: float  # giây
    ket_thuc: float  # giây
    noi_dung: str
    text_man_hinh: list[str] = field(default_factory=list)
    voice_over: str = ""

    @property
    def thoi_luong(self) -> float:
        return self.ket_thuc - self.bat_dau


def mmss(giay: float) -> str:
    giay = max(0.0, giay)
    phut, du = divmod(giay, 60)
    if abs(du - round(du)) < 0.05:
        return f"{int(phut):02d}:{int(round(du)):02d}"
    return f"{int(phut):02d}:{du:04.1f}"


KICH_BAN: list[Canh] = [
    Canh(
        1, "Mở đầu từ bức ảnh lịch sử", 0, 25,
        "- 00:00–00:03: Ảnh tư liệu bà Nguyễn Thị Bình đặt bút ký Hiệp định Paris. Zoom in chậm + "
        "Ken Burns effect nhẹ. Nhạc nền nhẹ nhàng (piano/string).\n"
        "- 00:03–00:18: Chuyển sang chân dung bà → toàn cảnh bàn hội nghị. Text nguồn ảnh góc dưới phải.\n"
        "- 00:18–00:25: Học sinh xuất hiện nhìn thẳng máy quay nói đoạn thoại cuối.",
        ["MADAME BÌNH", "Nguyễn Thị Bình và những đóng góp cho hòa bình"],
        "Một người phụ nữ Việt Nam trong tà áo dài, ngồi giữa một hội nghị quốc tế và đặt bút ký vào "
        "văn kiện lịch sử. Đó là bà Nguyễn Thị Bình, thường được biết đến với tên gọi Madame Bình. "
        "Tìm hiểu về bà, em muốn kể câu chuyện về trí tuệ, bản lĩnh và sự tận tâm của người phụ nữ Việt Nam.",
    ),
    Canh(
        2, "Tuổi trẻ và truyền thống gia đình", 25, 55,
        "- Hiện chân dung + tên thật + ngày sinh nổi bật.\n"
        "- Bản đồ đơn giản đánh dấu Điện Bàn, Quảng Nam + chân dung Phan Châu Trinh.\n"
        "- Cảnh học sinh đọc tư liệu (ghi chú “Hình minh họa”).",
        ["Nguyễn Thị Châu Sa", "26/05/1927", "Quê gốc Điện Bàn, Quảng Nam"],
        "Bà Nguyễn Thị Bình tên thật là Nguyễn Thị Châu Sa, sinh ngày 26 tháng 5 năm 1927. Quê gốc của "
        "bà ở vùng đất Điện Bàn, Quảng Nam; bà là cháu ngoại của nhà yêu nước Phan Châu Trinh…",
    ),
    Canh(
        3, "Bản lĩnh trước thử thách", 55, 85,
        "- Hiện mốc 1951.\n"
        "- Cận cảnh tay học sinh ghi chép + gạch chân “tiếp tục hoạt động”.\n"
        "- Chuyển sang sân trường yên bình.",
        ["1951", "Bị bắt khi hoạt động cách mạng", "Tiếp tục cống hiến sau tù đày"],
    ),
    Canh(
        4, "Trí tuệ tại Hội nghị Paris", 85, 130,
        "- Ảnh tư liệu bà tại bàn đàm phán + trả lời báo chí.\n"
        "- Số “202” nổi bật lớn.\n"
        "- Cảnh học sinh thảo luận nhóm.",
        ["1969", "Bộ trưởng Ngoại giao Chính phủ Cách mạng lâm thời",
         "Hội nghị Paris 1968–1973", "202 phiên họp công khai"],
    ),
    Canh(
        5, "Dấu mốc 27/01/1973", 130, 175,
        "- Giữ ảnh ký Hiệp định Paris 8–10 giây.\n"
        "- Morph từ cây bút lịch sử → cây bút học sinh đang viết.",
        ["27/01/1973", "Ký Hiệp định Paris",
         "Người phụ nữ duy nhất trong các đại diện ký hiệp định"],
    ),
    Canh(
        6, "Tiếp tục cống hiến sau chiến tranh", 175, 210,
        "- Ảnh Bộ trưởng Giáo dục, Phó Chủ tịch nước, Anh hùng Lao động 2025.\n"
        "- Nối sang học sinh trong lớp học.",
        ["Bộ trưởng Bộ Giáo dục 1976–1987", "Phó Chủ tịch nước 1992–2002", "Anh hùng Lao động 2025"],
    ),
    Canh(
        7, "Từ nhân vật lịch sử đến những người phụ nữ quanh em", 210, 240,
        "- Học sinh nói trực tiếp trước máy quay.\n"
        "- Chèn clip thực tế: mẹ làm việc nhà, bà đọc sách, cô giáo giảng bài.",
        ["Trân trọng đóng góp của phụ nữ", "Lắng nghe và ghi nhận"],
    ),
]

CANH_THEO_SO = {c.so: c for c in KICH_BAN}

LOI_CHAO = (
    "Chào bạn! Tôi là CapCut Madame Bình Editor Bot. Bạn đã làm đến phần nào rồi? "
    "Hãy mô tả project hiện tại hoặc gửi timeline để tôi tiếp nối chính xác nhé."
)


def kich_ban_markdown() -> str:
    phan = []
    for c in KICH_BAN:
        khoi = [f"**Cảnh {c.so}: {c.ten}** ({mmss(c.bat_dau)} – {mmss(c.ket_thuc)}, {c.thoi_luong:g} giây)",
                c.noi_dung]
        if c.text_man_hinh:
            khoi.append("- Text trên màn hình: “" + " / ".join(c.text_man_hinh) + "”")
        if c.voice_over:
            khoi.append(f"- Voice-over: “{c.voice_over}”")
        phan.append("\n".join(khoi))
    return "\n\n".join(phan)


SYSTEM_PROMPT = f"""Bạn là **CapCut Madame Bình Editor Bot** – chuyên gia edit video CapCut, chuyên làm video lịch sử giáo dục về bà Nguyễn Thị Bình (Madame Bình). Luôn trả lời bằng tiếng Việt.

## NHIỆM VỤ
1. Kiểm tra tiến độ người dùng đã làm đến đâu (hỏi rõ, hoặc đọc screenshot timeline CapCut, danh sách clip/ảnh/audio họ gửi).
2. Phân tích "khung xương" (structure) và ý tưởng người dùng đã làm.
3. Tiếp nối chính xác từ chỗ người dùng dừng lại; không làm lại từ đầu trừ khi được yêu cầu.
4. Tìm và đề xuất ảnh tư liệu lịch sử chất lượng cao (dùng công cụ web_search), kèm nguồn và cách tải.
5. Đề xuất animation, transition, text overlay, hiệu ứng phù hợp từng cảnh trong CapCut.
6. Viết hướng dẫn edit cực kỳ chi tiết, từng bước, theo đúng timeline CapCut (giây chính xác).
7. Chia voice-over theo cảnh.

## KỊCH BẢN – TUÂN THỦ 100%
{kich_ban_markdown()}

## BẢN GHI ÂM – QUY TẮC BẮT BUỘC
- Người dùng đã thu sẵn các bản ghi âm. Bot nhận "BÁO CÁO GHI ÂM" do chương trình tự quét (tên file, cảnh được chỉ định, độ dài thật). Báo cáo mới nhất luôn là nguồn đúng.
- CHỈ dùng các file đã được chỉ định cho từng cảnh trong báo cáo. Không tự gán file "không được chỉ định" vào cảnh nào, không đổi file giữa các cảnh.
- KHÔNG đề xuất TTS / AI Voice / ElevenLabs thay thế cho bản ghi âm đã có. Chỉ khi một cảnh không có file nào được chỉ định thì báo rõ "Cảnh X chưa có ghi âm" và hỏi người dùng muốn thu thêm hay để trống (chỉ nhạc nền).
- Căn timeline theo độ dài THẬT của file ghi âm. Nếu ghi âm dài/ngắn hơn khung thời gian kịch bản, nói rõ chênh lệch bao nhiêu giây và đưa phương án cụ thể trong CapCut (ví dụ: Speed 1.05x–1.1x không đổi cao độ, cắt khoảng lặng bằng Split, kéo dài ảnh/clip minh họa, hoặc dời mốc cảnh sau) — để người dùng chọn, không tự ý đổi kịch bản.
- Ghi rõ đặt file ở track nào, bắt đầu ở giây nào, kết thúc ở giây nào; gợi ý Volume, Fade in/out, giảm nhạc nền (ducking) khi có giọng nói.

## QUY TẮC HOẠT ĐỘNG
1. Luôn hỏi tiến độ trước nếu chưa biết: đã làm đến cảnh nào, đã có clip/ảnh/audio nào trong project, muốn tiếp nối từ giây thứ mấy.
2. Khi tiếp nối: chỉ làm phần còn lại; giữ nguyên style, màu, font, nhạc nền người dùng đã chọn; đề xuất animation cụ thể có trong CapCut (Zoom In Slow, Fade, Slide Left, Ken Burns, Text Pop, Typewriter…).
3. Tìm ảnh: đưa từ khóa tìm chính xác (tiếng Việt + tiếng Anh); ưu tiên ảnh tư liệu có nguồn rõ ràng (TTXVN/Vietnam News Agency, Bảo tàng Lịch sử Quốc gia, Bảo tàng Phụ nữ Việt Nam, báo chính thống, kho lưu trữ quốc tế, Wikimedia Commons có giấy phép). Chỉ đưa đường link mà bạn thực sự tìm thấy qua web_search; không bịa link. Ghi chú bản quyền và dòng "Nguồn ảnh: …" để đặt góc dưới phải. Hướng dẫn tải và import vào CapCut (Import → chọn file / kéo thả vào Media).
4. Mỗi câu trả lời hướng dẫn edit phải có, cho từng đoạn:
   - Timeline chính xác (giây bắt đầu – kết thúc)
   - Loại media cần dùng
   - Hiệu ứng + animation cụ thể trong CapCut
   - Text overlay (nội dung + vị trí + font gợi ý)
   - Voice-over / audio (file ghi âm nào, đặt ở đâu)
   - Bước thực hiện trong CapCut (bấm vào đâu, kéo thả thế nào)
   Nên trình bày bằng bảng timeline + danh sách bước đánh số.
5. Phong cách: chi tiết, rõ ràng, dễ làm theo; ưu tiên chính xác lịch sử và sự trang trọng.
6. Không bao giờ bịa thông tin về bà Nguyễn Thị Bình. Với các dữ kiện như số phiên họp, danh hiệu, năm giữ chức vụ, nếu cần khẳng định thì kiểm chứng bằng web_search từ nguồn chính thống và nêu nguồn; nếu nguồn mâu thuẫn với kịch bản, báo cho người dùng thay vì tự sửa.
7. Cảnh có học sinh hoặc người thân: nhắc ghi chú "Hình minh họa" khi cần, và xin phép người xuất hiện trong clip.
8. Nếu người dùng gửi ảnh chụp màn hình timeline, đọc kỹ các track, mốc thời gian, tên clip trước khi trả lời; nói rõ bạn thấy gì và chỗ nào chưa đọc rõ.
"""

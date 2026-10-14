"""Giao diện dòng lệnh của CapCut Madame Bình Editor Bot.

Chạy:  python -m madame_binh_bot
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import sys
from datetime import datetime
from pathlib import Path

import anthropic

from .ghi_am import bao_cao
from .kich_ban import LOI_CHAO, SYSTEM_PROMPT

MODEL = os.environ.get("MADAME_BINH_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("MADAME_BINH_EFFORT", "high")
MAX_TOKENS = 64000
# Số lần tối đa tiếp tục một lượt bị tạm dừng (pause_turn) khi web search chạy lâu
MAX_TIEP_TUC = 5
DUOI_ANH = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".webp": "image/webp", ".gif": "image/gif"}

TOOLS = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 8}]

HUONG_DAN_LENH = """Lệnh:
  /anh <đường_dẫn> [...]   đính kèm ảnh chụp timeline / ảnh tư liệu vào tin nhắn tiếp theo
  /ghiam                   quét lại thư mục ghi âm và xem báo cáo
  /moi                     bắt đầu phiên mới (xóa lịch sử đã lưu)
  /giup                    xem lại danh sách lệnh
  /thoat                   thoát
Gõ nội dung bình thường để trò chuyện với bot. Kết thúc dòng bằng \\ để xuống dòng."""


class Bot:
    def __init__(self, thu_muc_ghi_am: Path, thu_muc_ket_qua: Path):
        self.client = anthropic.Anthropic()
        self.thu_muc_ghi_am = thu_muc_ghi_am
        self.thu_muc_ket_qua = thu_muc_ket_qua
        self.file_lich_su = thu_muc_ket_qua / "lich_su.json"
        self.messages: list[dict] = []
        self.bao_cao_da_gui = ""
        self.anh_cho: list[Path] = []
        self._tai_lich_su()

    # ---------- lưu / tải phiên ----------
    def _tai_lich_su(self) -> None:
        if not self.file_lich_su.exists():
            return
        try:
            du_lieu = json.loads(self.file_lich_su.read_text(encoding="utf-8"))
            self.messages = du_lieu["messages"]
            self.bao_cao_da_gui = du_lieu.get("bao_cao_da_gui", "")
        except (json.JSONDecodeError, KeyError) as e:
            print(f"(Không đọc được lịch sử cũ, bắt đầu phiên mới: {e})")

    def _luu_lich_su(self) -> None:
        self.thu_muc_ket_qua.mkdir(parents=True, exist_ok=True)
        self.file_lich_su.write_text(
            json.dumps({"messages": self.messages, "bao_cao_da_gui": self.bao_cao_da_gui},
                       ensure_ascii=False, indent=1),
            encoding="utf-8",
        )

    def _luu_cau_tra_loi(self, van_ban: str) -> Path:
        self.thu_muc_ket_qua.mkdir(parents=True, exist_ok=True)
        p = self.thu_muc_ket_qua / f"huong_dan_{datetime.now():%Y%m%d_%H%M%S}.md"
        p.write_text(van_ban, encoding="utf-8")
        return p

    def phien_moi(self) -> None:
        self.messages = []
        self.bao_cao_da_gui = ""
        self.anh_cho = []
        if self.file_lich_su.exists():
            self.file_lich_su.unlink()

    # ---------- dựng tin nhắn ----------
    def _khoi_anh(self, p: Path) -> dict:
        media = DUOI_ANH.get(p.suffix.lower()) or mimetypes.guess_type(p.name)[0]
        if media not in DUOI_ANH.values():
            raise ValueError(f"{p.name}: chỉ hỗ trợ PNG, JPG, WEBP, GIF")
        return {"type": "image",
                "source": {"type": "base64", "media_type": media,
                           "data": base64.standard_b64encode(p.read_bytes()).decode()}}

    def _dung_tin_nhan(self, van_ban: str) -> tuple[list[dict], str]:
        noi_dung: list[dict] = []
        bc = bao_cao(self.thu_muc_ghi_am)
        if bc != self.bao_cao_da_gui:
            # Chỉ gửi lại khi thư mục ghi âm thay đổi để giữ lịch sử gọn
            noi_dung.append({"type": "text", "text": f"<bao_cao_ghi_am>\n{bc}\n</bao_cao_ghi_am>"})
        for p in self.anh_cho:
            noi_dung.append(self._khoi_anh(p))
        noi_dung.append({"type": "text", "text": van_ban})
        return noi_dung, bc

    # ---------- gọi API ----------
    def hoi(self, van_ban: str) -> None:
        try:
            noi_dung, bc = self._dung_tin_nhan(van_ban)
        except (OSError, ValueError) as e:
            print(f"Lỗi đính kèm ảnh: {e}")
            return

        so_tin_truoc = len(self.messages)
        self.messages.append({"role": "user", "content": noi_dung})
        cac_doan: list[str] = []
        try:
            for _ in range(MAX_TIEP_TUC + 1):
                msg = self._goi_mot_luot()
                if msg.stop_reason == "refusal":
                    print("\n[Bot từ chối yêu cầu này. Hãy thử diễn đạt lại.]")
                    del self.messages[so_tin_truoc:]
                    return
                khoi = [b.to_dict() for b in msg.content]
                if self.messages[-1]["role"] == "assistant":
                    # Lượt tiếp nối sau pause_turn: nối vào cùng một lượt trả lời
                    self.messages[-1]["content"].extend(khoi)
                else:
                    self.messages.append({"role": "assistant", "content": khoi})
                cac_doan += [b.text for b in msg.content if b.type == "text"]
                if msg.stop_reason != "pause_turn":
                    break
            if msg.stop_reason == "max_tokens":
                print("\n[Câu trả lời bị cắt vì quá dài – gõ “tiếp tục” để bot viết nốt.]")
        except anthropic.AuthenticationError:
            del self.messages[so_tin_truoc:]
            print("\nLỗi xác thực: kiểm tra biến môi trường ANTHROPIC_API_KEY.")
            return
        except anthropic.RateLimitError:
            del self.messages[so_tin_truoc:]
            print("\nĐang bị giới hạn tốc độ (429). Đợi một lát rồi gửi lại.")
            return
        except anthropic.APIStatusError as e:
            del self.messages[so_tin_truoc:]
            print(f"\nLỗi API {e.status_code}: {e.message}")
            return
        except anthropic.APIConnectionError:
            del self.messages[so_tin_truoc:]
            print("\nMất kết nối tới API. Kiểm tra mạng rồi gửi lại.")
            return

        self.bao_cao_da_gui = bc
        self.anh_cho = []
        self._luu_lich_su()
        p = self._luu_cau_tra_loi("".join(cac_doan))
        print(f"\n\n(Đã lưu hướng dẫn: {p})")

    def _goi_mot_luot(self):
        with self.client.beta.messages.stream(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=self.messages,
            tools=TOOLS,
            thinking={"type": "adaptive"},
            output_config={"effort": EFFORT},
            cache_control={"type": "ephemeral"},
            # Nếu model chính từ chối, API tự chạy lại trên model dự phòng phù hợp
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        ) as stream:
            for event in stream:
                if event.type == "text":
                    print(event.text, end="", flush=True)
                elif event.type == "content_block_start" and event.content_block.type == "server_tool_use":
                    print("\n[đang tìm kiếm trên web…]", flush=True)
            return stream.get_final_message()


def doc_dong(nhac: str) -> str:
    """Đọc một tin nhắn, cho phép nhiều dòng bằng cách kết thúc dòng với dấu \\."""
    dong = input(nhac)
    cac_dong = []
    while dong.endswith("\\"):
        cac_dong.append(dong[:-1])
        dong = input("... ")
    cac_dong.append(dong)
    return "\n".join(cac_dong).strip()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="madame_binh_bot", description="CapCut Madame Bình Editor Bot")
    ap.add_argument("--ghi-am", default="ghi_am", help="thư mục chứa bản ghi âm + danh_sach.json (mặc định: ghi_am)")
    ap.add_argument("--ket-qua", default="ket_qua", help="thư mục lưu hướng dẫn và lịch sử (mặc định: ket_qua)")
    ap.add_argument("--kiem-tra", action="store_true", help="chỉ in báo cáo ghi âm rồi thoát (không gọi API)")
    args = ap.parse_args(argv)

    thu_muc_ghi_am = Path(args.ghi_am)
    if args.kiem_tra:
        print(bao_cao(thu_muc_ghi_am))
        return 0

    bot = Bot(thu_muc_ghi_am, Path(args.ket_qua))
    print(bao_cao(thu_muc_ghi_am))
    print()
    if bot.messages:
        print("(Đã tải phiên trước – bot nhớ tiến độ cũ. Gõ /moi để làm lại từ đầu.)\n")
    print(f"Bot: {LOI_CHAO}\n")
    print(HUONG_DAN_LENH + "\n")

    while True:
        try:
            van_ban = doc_dong("Bạn: ")
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not van_ban:
            continue
        lenh, _, con_lai = van_ban.partition(" ")
        if lenh == "/thoat":
            return 0
        if lenh == "/giup":
            print(HUONG_DAN_LENH)
        elif lenh == "/ghiam":
            print(bao_cao(thu_muc_ghi_am))
        elif lenh == "/moi":
            bot.phien_moi()
            print(f"Đã bắt đầu phiên mới.\nBot: {LOI_CHAO}")
        elif lenh == "/anh":
            for ten in con_lai.split():
                p = Path(ten).expanduser()
                if p.is_file() and p.suffix.lower() in DUOI_ANH:
                    bot.anh_cho.append(p)
                else:
                    print(f"Bỏ qua {ten}: không thấy file ảnh PNG/JPG/WEBP/GIF")
            print(f"Đang chờ gửi {len(bot.anh_cho)} ảnh – gõ tin nhắn kèm theo (vd: “đây là timeline của mình”).")
        else:
            print("\nBot: ", end="", flush=True)
            bot.hoi(van_ban)
            print()


if __name__ == "__main__":
    sys.exit(main())

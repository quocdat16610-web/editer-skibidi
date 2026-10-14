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
from collections.abc import Generator, Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

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
# Giới hạn kích thước mỗi ảnh của API
ANH_TOI_DA = 5 * 1024 * 1024

TOOLS = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 8}]

HUONG_DAN_LENH = """Lệnh:
  /anh <đường_dẫn> [...]   đính kèm ảnh chụp timeline / ảnh tư liệu vào tin nhắn tiếp theo
  /ghiam                   quét lại thư mục ghi âm và xem báo cáo
  /moi                     bắt đầu phiên mới (xóa lịch sử đã lưu)
  /giup                    xem lại danh sách lệnh
  /thoat                   thoát
Gõ nội dung bình thường để trò chuyện với bot. Kết thúc dòng bằng \\ để xuống dòng."""


@dataclass
class Anh:
    ten: str
    media_type: str
    du_lieu: bytes

    @classmethod
    def tu_file(cls, p: Path) -> "Anh":
        media = DUOI_ANH.get(p.suffix.lower()) or mimetypes.guess_type(p.name)[0]
        if media not in DUOI_ANH.values():
            raise ValueError(f"{p.name}: chỉ hỗ trợ PNG, JPG, WEBP, GIF")
        return cls(p.name, media, p.read_bytes())

    def khoi(self) -> dict:
        if self.media_type not in DUOI_ANH.values():
            raise ValueError(f"{self.ten}: chỉ hỗ trợ PNG, JPG, WEBP, GIF")
        if len(self.du_lieu) > ANH_TOI_DA:
            raise ValueError(f"{self.ten}: ảnh lớn hơn 5 MB, hãy giảm kích thước rồi gửi lại")
        return {"type": "image",
                "source": {"type": "base64", "media_type": self.media_type,
                           "data": base64.standard_b64encode(self.du_lieu).decode()}}


class Bot:
    """Lõi hội thoại, dùng chung cho bản dòng lệnh và bản web.

    `hoi()` là generator trả về các sự kiện dạng dict:
      {"type": "text", "text": ...}      đoạn chữ bot đang viết
      {"type": "search"}                 bot bắt đầu tìm kiếm trên web
      {"type": "notice", "text": ...}    thông báo phụ (bị cắt do quá dài…)
      {"type": "error", "text": ...}     lỗi – lượt hỏi bị hủy, lịch sử không đổi
      {"type": "done", "file": ...}      xong, đã lưu hướng dẫn vào file
    """

    def __init__(self, thu_muc_ghi_am: Path, thu_muc_ket_qua: Path):
        self.client = anthropic.Anthropic()
        self.thu_muc_ghi_am = thu_muc_ghi_am
        self.thu_muc_ket_qua = thu_muc_ket_qua
        self.file_lich_su = thu_muc_ket_qua / "lich_su.json"
        self.messages: list[dict] = []
        self.bao_cao_da_gui = ""
        self.loi_tai_lich_su = ""
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
            self.loi_tai_lich_su = f"Không đọc được lịch sử cũ, bắt đầu phiên mới: {e}"

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
        if self.file_lich_su.exists():
            self.file_lich_su.unlink()

    def hoi_thoai_hien_thi(self) -> list[dict]:
        """Lịch sử rút gọn để hiển thị: [{"role", "text", "so_anh"}]."""
        ket_qua = []
        for m in self.messages:
            khoi = m["content"] if isinstance(m["content"], list) else [{"type": "text", "text": m["content"]}]
            chu = [k["text"] for k in khoi
                   if k.get("type") == "text" and not k["text"].startswith("<bao_cao_ghi_am>")]
            so_anh = sum(1 for k in khoi if k.get("type") == "image")
            ket_qua.append({"role": m["role"], "text": "".join(chu), "so_anh": so_anh})
        return ket_qua

    # ---------- dựng tin nhắn ----------
    def _dung_tin_nhan(self, van_ban: str, anh: list[Anh]) -> tuple[list[dict], str]:
        noi_dung: list[dict] = []
        bc = bao_cao(self.thu_muc_ghi_am)
        if bc != self.bao_cao_da_gui:
            # Chỉ gửi lại khi thư mục ghi âm thay đổi để giữ lịch sử gọn
            noi_dung.append({"type": "text", "text": f"<bao_cao_ghi_am>\n{bc}\n</bao_cao_ghi_am>"})
        for a in anh:
            noi_dung.append(a.khoi())
        noi_dung.append({"type": "text", "text": van_ban})
        return noi_dung, bc

    # ---------- gọi API ----------
    def hoi(self, van_ban: str, anh: list[Anh] | None = None) -> Iterator[dict]:
        try:
            noi_dung, bc = self._dung_tin_nhan(van_ban, anh or [])
        except (OSError, ValueError) as e:
            yield {"type": "error", "text": f"Lỗi đính kèm ảnh: {e}"}
            return

        so_tin_truoc = len(self.messages)
        self.messages.append({"role": "user", "content": noi_dung})
        cac_doan: list[str] = []
        loi = ""
        try:
            for _ in range(MAX_TIEP_TUC + 1):
                msg = yield from self._goi_mot_luot()
                if msg.stop_reason == "refusal":
                    loi = "Bot từ chối yêu cầu này. Hãy thử diễn đạt lại."
                    break
                khoi = [b.to_dict() for b in msg.content]
                if self.messages[-1]["role"] == "assistant":
                    # Lượt tiếp nối sau pause_turn: nối vào cùng một lượt trả lời
                    self.messages[-1]["content"].extend(khoi)
                else:
                    self.messages.append({"role": "assistant", "content": khoi})
                cac_doan += [b.text for b in msg.content if b.type == "text"]
                if msg.stop_reason != "pause_turn":
                    break
        except anthropic.AuthenticationError:
            loi = "Lỗi xác thực: kiểm tra biến môi trường ANTHROPIC_API_KEY."
        except anthropic.RateLimitError:
            loi = "Đang bị giới hạn tốc độ (429). Đợi một lát rồi gửi lại."
        except anthropic.APIStatusError as e:
            loi = f"Lỗi API {e.status_code}: {e.message}"
        except anthropic.APIConnectionError:
            loi = "Mất kết nối tới API. Kiểm tra mạng rồi gửi lại."
        except GeneratorExit:
            # Người dùng đóng trang giữa chừng: bỏ lượt hỏi dang dở
            del self.messages[so_tin_truoc:]
            raise

        if loi:
            del self.messages[so_tin_truoc:]
            yield {"type": "error", "text": loi}
            return

        if msg.stop_reason == "max_tokens":
            yield {"type": "notice", "text": "Câu trả lời bị cắt vì quá dài – gõ “tiếp tục” để bot viết nốt."}
        self.bao_cao_da_gui = bc
        self._luu_lich_su()
        p = self._luu_cau_tra_loi("".join(cac_doan))
        yield {"type": "done", "file": str(p)}

    def _goi_mot_luot(self) -> Generator[dict, None, Any]:
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
                    yield {"type": "text", "text": event.text}
                elif event.type == "content_block_start" and event.content_block.type == "server_tool_use":
                    yield {"type": "search"}
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
    if bot.loi_tai_lich_su:
        print(f"({bot.loi_tai_lich_su})")
    print(bao_cao(thu_muc_ghi_am))
    print()
    if bot.messages:
        print("(Đã tải phiên trước – bot nhớ tiến độ cũ. Gõ /moi để làm lại từ đầu.)\n")
    print(f"Bot: {LOI_CHAO}\n")
    print(HUONG_DAN_LENH + "\n")
    anh_cho: list[Path] = []

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
            anh_cho = []
            print(f"Đã bắt đầu phiên mới.\nBot: {LOI_CHAO}")
        elif lenh == "/anh":
            for ten in con_lai.split():
                p = Path(ten).expanduser()
                if p.is_file() and p.suffix.lower() in DUOI_ANH:
                    anh_cho.append(p)
                else:
                    print(f"Bỏ qua {ten}: không thấy file ảnh PNG/JPG/WEBP/GIF")
            print(f"Đang chờ gửi {len(anh_cho)} ảnh – gõ tin nhắn kèm theo (vd: “đây là timeline của mình”).")
        else:
            try:
                anh = [Anh.tu_file(p) for p in anh_cho]
            except (OSError, ValueError) as e:
                print(f"Lỗi đính kèm ảnh: {e}")
                continue
            print("\nBot: ", end="", flush=True)
            for su_kien in bot.hoi(van_ban, anh):
                if su_kien["type"] == "text":
                    print(su_kien["text"], end="", flush=True)
                elif su_kien["type"] == "search":
                    print("\n[đang tìm kiếm trên web…]", flush=True)
                elif su_kien["type"] in ("notice", "error"):
                    print(f"\n[{su_kien['text']}]")
                elif su_kien["type"] == "done":
                    anh_cho = []
                    print(f"\n\n(Đã lưu hướng dẫn: {su_kien['file']})")
            print()


if __name__ == "__main__":
    sys.exit(main())

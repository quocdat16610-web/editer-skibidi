"""Giao diện web của CapCut Madame Bình Editor Bot.

Chạy:  python -m madame_binh_bot.web     rồi mở http://127.0.0.1:5000
"""

from __future__ import annotations

import argparse
import json
import threading
from pathlib import Path

from flask import Flask, Response, abort, jsonify, request, send_from_directory, stream_with_context

from . import ghi_am
from .bot import ANH_TOI_DA, DUOI_ANH, Anh, Bot
from .kich_ban import CANH_THEO_SO, KICH_BAN, LOI_CHAO, mmss

THU_MUC_TINH = Path(__file__).parent / "static"


def tao_app(thu_muc_ghi_am: Path, thu_muc_ket_qua: Path) -> Flask:
    app = Flask(__name__, static_folder=None)
    # Ảnh chụp timeline + file ghi âm tải lên
    app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024
    bot = Bot(thu_muc_ghi_am, thu_muc_ket_qua)
    # Một phiên hội thoại dùng chung – chỉ cho một câu hỏi chạy tại một thời điểm
    khoa = threading.Lock()

    def loi(thong_bao: str, ma: int = 400):
        return jsonify({"loi": thong_bao}), ma

    @app.get("/")
    def trang_chu():
        return send_from_directory(THU_MUC_TINH, "index.html")

    @app.get("/vendor/<path:ten>")
    def thu_vien(ten: str):
        return send_from_directory(THU_MUC_TINH / "vendor", ten)

    @app.get("/api/trang-thai")
    def trang_thai():
        return jsonify({
            "loi_chao": LOI_CHAO,
            "lich_su": bot.hoi_thoai_hien_thi(),
            "canh": [{"so": c.so, "ten": c.ten, "bat_dau": mmss(c.bat_dau), "ket_thuc": mmss(c.ket_thuc)}
                     for c in KICH_BAN],
            "dang_tra_loi": khoa.locked(),
            "canh_bao": bot.loi_tai_lich_su,
        })

    @app.post("/api/hoi")
    def hoi():
        van_ban = (request.form.get("van_ban") or "").strip()
        tep_anh = request.files.getlist("anh")
        if not van_ban and not tep_anh:
            return loi("Hãy nhập nội dung hoặc đính kèm ảnh")
        if not van_ban:
            van_ban = "Đây là ảnh chụp project/timeline CapCut của mình."
        anh = []
        for t in tep_anh:
            media = t.mimetype if t.mimetype in DUOI_ANH.values() else DUOI_ANH.get(Path(t.filename or "").suffix.lower())
            if not media:
                return loi(f"{t.filename}: chỉ hỗ trợ ảnh PNG, JPG, WEBP, GIF")
            du_lieu = t.read()
            if len(du_lieu) > ANH_TOI_DA:
                return loi(f"{t.filename}: ảnh lớn hơn 5 MB, hãy giảm kích thước rồi gửi lại")
            anh.append(Anh(t.filename or "anh", media, du_lieu))

        if not khoa.acquire(blocking=False):
            return loi("Bot đang trả lời câu trước, đợi xong rồi gửi tiếp nhé", 409)

        def su_kien():
            try:
                for e in bot.hoi(van_ban, anh):
                    if e["type"] == "done":
                        e["file"] = Path(e["file"]).name
                    yield f"data: {json.dumps(e, ensure_ascii=False)}\n\n"
            finally:
                khoa.release()

        return Response(stream_with_context(su_kien()), mimetype="text/event-stream",
                        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.post("/api/phien-moi")
    def phien_moi():
        if not khoa.acquire(blocking=False):
            return loi("Bot đang trả lời, đợi xong rồi hãy làm lại từ đầu", 409)
        try:
            bot.phien_moi()
        finally:
            khoa.release()
        return jsonify({"ok": True})

    @app.get("/api/huong-dan/<path:ten>")
    def tai_huong_dan(ten: str):
        if not ten.startswith("huong_dan_") or not ten.endswith(".md"):
            abort(404)
        return send_from_directory(thu_muc_ket_qua.resolve(), ten, as_attachment=True)

    # ---------- ghi âm ----------
    @app.get("/api/ghi-am")
    def ds_ghi_am():
        return jsonify(ghi_am.tom_tat(thu_muc_ghi_am))

    @app.get("/api/ghi-am/file/<path:ten>")
    def nghe_ghi_am(ten: str):
        try:
            ten = ghi_am.ten_an_toan(ten)
        except ValueError:
            abort(404)
        return send_from_directory(thu_muc_ghi_am.resolve(), ten)

    @app.post("/api/ghi-am/tai-len")
    def tai_len_ghi_am():
        tep = request.files.get("file")
        if tep is None or not tep.filename:
            return loi("Chưa chọn file ghi âm")
        try:
            canh = int(request.form.get("canh", "0") or 0)
        except ValueError:
            canh = 0
        if canh not in CANH_THEO_SO:
            return loi("Hãy chọn cảnh từ 1 đến 7")
        try:
            ten = ghi_am.luu_file_tai_len(thu_muc_ghi_am, tep.filename, tep.read(),
                                          ghi_de=request.form.get("ghi_de") == "1")
            ghi_am.chi_dinh(thu_muc_ghi_am, ten, canh, request.form.get("mo_ta", "").strip())
        except FileExistsError as e:
            return loi(str(e), 409)
        except ValueError as e:
            return loi(str(e))
        return jsonify(ghi_am.tom_tat(thu_muc_ghi_am))

    @app.post("/api/ghi-am/chi-dinh")
    def chi_dinh_ghi_am():
        du_lieu = request.get_json(silent=True) or {}
        try:
            ghi_am.chi_dinh(thu_muc_ghi_am, str(du_lieu.get("file", "")), int(du_lieu.get("canh", 0)),
                            str(du_lieu.get("mo_ta", "")).strip())
        except (ValueError, TypeError) as e:
            return loi(str(e))
        return jsonify(ghi_am.tom_tat(thu_muc_ghi_am))

    @app.post("/api/ghi-am/bo-chi-dinh")
    def bo_chi_dinh_ghi_am():
        du_lieu = request.get_json(silent=True) or {}
        try:
            ghi_am.bo_chi_dinh(thu_muc_ghi_am, str(du_lieu.get("file", "")))
        except ValueError as e:
            return loi(str(e))
        return jsonify(ghi_am.tom_tat(thu_muc_ghi_am))

    return app


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="madame_binh_bot.web", description="Giao diện web của Madame Bình Editor Bot")
    ap.add_argument("--ghi-am", default="ghi_am", help="thư mục ghi âm (mặc định: ghi_am)")
    ap.add_argument("--ket-qua", default="ket_qua", help="thư mục lưu kết quả (mặc định: ket_qua)")
    ap.add_argument("--host", default="127.0.0.1", help="mặc định chỉ mở trên máy này")
    ap.add_argument("--port", type=int, default=5000)
    args = ap.parse_args(argv)
    app = tao_app(Path(args.ghi_am), Path(args.ket_qua))
    print(f"Mở trình duyệt: http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, threaded=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

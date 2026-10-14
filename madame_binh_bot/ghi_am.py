"""Quét các bản ghi âm đã được chỉ định và đối chiếu với khung thời gian kịch bản."""

from __future__ import annotations

import json
import shutil
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path

from .kich_ban import CANH_THEO_SO, KICH_BAN, mmss

DUOI_AUDIO = {".mp3", ".m4a", ".aac", ".wav", ".ogg", ".opus", ".flac", ".wma", ".mp4", ".mov"}
FILE_CAU_HINH = "danh_sach.json"
# Chênh lệch nhỏ hơn mức này coi như vừa khung (giây)
DUNG_SAI = 1.0


@dataclass
class BanGhi:
    file: str
    canh: int
    mo_ta: str
    thoi_luong: float | None  # None = không đọc được
    ton_tai: bool
    loi: str = ""


def do_thoi_luong(duong_dan: Path) -> tuple[float | None, str]:
    """Trả về (số giây, lỗi). Thử mutagen → ffprobe → wave."""
    try:
        import mutagen

        f = mutagen.File(duong_dan)
        if f is not None and getattr(f, "info", None) and f.info.length:
            return float(f.info.length), ""
    except Exception:
        pass

    if shutil.which("ffprobe"):
        try:
            out = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(duong_dan)],
                capture_output=True, text=True, timeout=30,
            )
            if out.returncode == 0 and out.stdout.strip():
                return float(out.stdout.strip()), ""
        except (subprocess.SubprocessError, ValueError):
            pass

    if duong_dan.suffix.lower() == ".wav":
        try:
            with wave.open(str(duong_dan)) as w:
                return w.getnframes() / float(w.getframerate()), ""
        except (wave.Error, EOFError) as e:
            return None, f"không đọc được WAV: {e}"

    return None, "không đọc được độ dài (cài mutagen hoặc ffmpeg)"


def doc_cau_hinh(thu_muc: Path) -> list[dict]:
    p = thu_muc / FILE_CAU_HINH
    if not p.exists():
        return []
    du_lieu = json.loads(p.read_text(encoding="utf-8"))
    ds = du_lieu.get("ban_ghi", []) if isinstance(du_lieu, dict) else du_lieu
    ket_qua = []
    for i, muc in enumerate(ds):
        if not isinstance(muc, dict) or "file" not in muc or "canh" not in muc:
            raise ValueError(f"{p}: mục thứ {i + 1} cần có 'file' và 'canh'")
        if int(muc["canh"]) not in CANH_THEO_SO:
            raise ValueError(f"{p}: '{muc['file']}' gán cho cảnh {muc['canh']} – chỉ có cảnh 1–7")
        ket_qua.append(muc)
    return ket_qua


def quet(thu_muc: Path) -> tuple[list[BanGhi], list[str]]:
    """Trả về (các bản ghi được chỉ định, các file audio có trong thư mục nhưng không được chỉ định)."""
    cau_hinh = doc_cau_hinh(thu_muc)
    ban_ghi: list[BanGhi] = []
    da_chi_dinh: set[str] = set()
    for muc in cau_hinh:
        ten = muc["file"]
        da_chi_dinh.add(ten)
        p = thu_muc / ten
        if not p.is_file():
            ban_ghi.append(BanGhi(ten, int(muc["canh"]), muc.get("mo_ta", ""), None, False, "không tìm thấy file"))
            continue
        dai, loi = do_thoi_luong(p)
        ban_ghi.append(BanGhi(ten, int(muc["canh"]), muc.get("mo_ta", ""), dai, True, loi))

    khong_chi_dinh = sorted(
        p.name for p in thu_muc.iterdir()
        if p.is_file() and p.suffix.lower() in DUOI_AUDIO and p.name not in da_chi_dinh
    ) if thu_muc.is_dir() else []
    return ban_ghi, khong_chi_dinh


def bao_cao(thu_muc: Path) -> str:
    """Báo cáo dạng Markdown gửi kèm cho bot (và in cho người dùng)."""
    try:
        ban_ghi, khong_chi_dinh = quet(thu_muc)
    except (ValueError, json.JSONDecodeError) as e:
        return f"BÁO CÁO GHI ÂM: lỗi đọc `{FILE_CAU_HINH}` – {e}"

    if not ban_ghi:
        dong = [f"BÁO CÁO GHI ÂM (thư mục `{thu_muc}`): chưa có bản ghi nào được chỉ định trong `{FILE_CAU_HINH}`."]
        if khong_chi_dinh:
            dong.append("File audio có trong thư mục nhưng chưa được chỉ định (KHÔNG dùng): " + ", ".join(khong_chi_dinh))
        return "\n".join(dong)

    dong = [f"BÁO CÁO GHI ÂM (thư mục `{thu_muc}`) – chỉ dùng các file dưới đây, đúng cảnh được chỉ định:", "",
            "| Cảnh | Khung kịch bản | File | Mô tả | Độ dài thật | Ghi chú |",
            "|---|---|---|---|---|---|"]
    for c in KICH_BAN:
        cua_canh = [b for b in ban_ghi if b.canh == c.so]
        khung = f"{mmss(c.bat_dau)}–{mmss(c.ket_thuc)} ({c.thoi_luong:g}s)"
        if not cua_canh:
            dong.append(f"| {c.so} | {khung} | — | — | — | Chưa có ghi âm được chỉ định |")
            continue
        for b in cua_canh:
            dai = f"{b.thoi_luong:.1f}s" if b.thoi_luong is not None else "?"
            dong.append(f"| {c.so} | {khung} | `{b.file}` | {b.mo_ta or '—'} | {dai} | {b.loi or 'OK'} |")

    dong += ["", "Đối chiếu tổng độ dài ghi âm với khung từng cảnh:"]
    for c in KICH_BAN:
        cua_canh = [b for b in ban_ghi if b.canh == c.so and b.thoi_luong is not None]
        if not cua_canh:
            continue
        tong = sum(b.thoi_luong for b in cua_canh)
        lech = tong - c.thoi_luong
        if lech > DUNG_SAI:
            danh_gia = f"DÀI HƠN khung {lech:.1f}s"
        elif lech < -DUNG_SAI:
            danh_gia = f"ngắn hơn khung {-lech:.1f}s (còn chỗ cho nhạc/hình)"
        else:
            danh_gia = "vừa khung"
        dong.append(f"- Cảnh {c.so}: ghi âm {tong:.1f}s / khung {c.thoi_luong:g}s → {danh_gia}")

    if khong_chi_dinh:
        dong += ["", "File audio có trong thư mục nhưng KHÔNG được chỉ định (không dùng): " + ", ".join(khong_chi_dinh)]
    return "\n".join(dong)

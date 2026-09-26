"""Measure end-to-end response latency of generate_answer(), split by stage.

Chạy: ``venv\\Scripts\\python notebooks\\do_latency.py`` từ gốc project.
GỌI API THẬT: 10 câu x 2 cấu hình x 2 lượt = 40 lượt sinh câu trả lời (~$0.30).
Không đi qua ragas_store.json — mục tiêu là đo thời gian nên luôn gọi thật.

Đo bằng cách bọc (monkeypatch) các hàm trong lúc chạy, không sửa code trong src/:
  (1)  retrieval_gate_s : src.generation.hybrid_search (gate chỉ là một phép so sánh ngay sau)
  (1b) rerank_s         : src.reranking.rerank — chỉ có ở rerank=True
  (2)  api_s            : client.messages.create
  (3)  total_s          : từ lúc gọi generate_answer đến lúc nó trả về
"""

from __future__ import annotations

import json
import logging
import os
import platform
import socket
import ssl
import statistics
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")
logging.basicConfig(level=logging.WARNING)

import numpy as np  # noqa: E402

import src.generation as gen  # noqa: E402
import src.reranking as rr  # noqa: E402
from src.evaluation import _uses_deprecated, load_questions  # noqa: E402
from src.generation import PRICE_PER_MTOK_IN, PRICE_PER_MTOK_OUT  # noqa: E402
from src.vectorstore import CHROMA_DIR, PROJECT_ROOT  # noqa: E402

OUT_PATH = PROJECT_ROOT / "data" / "Evaluation" / "latency_results.json"

# Phủ đủ 5 nhóm; lý do chọn từng câu ghi trong báo cáo.
QUESTION_IDS = ["Q001", "Q006", "Q012", "Q020", "Q023", "Q024", "Q015", "Q018", "Q028", "Q031"]
ROUNDS = 2
FLAG_RATIO = 0.20  # chênh lệch lượt 1 vs lượt 2 vượt 20% thì báo

# --------------------------------------------------------------------------- #
# Bộ đo
# --------------------------------------------------------------------------- #
timer: dict[str, float] = {}


def _timed(name, fn):
    def wrapper(*args, **kwargs):
        t0 = time.perf_counter()
        try:
            return fn(*args, **kwargs)
        finally:
            timer[name] = timer.get(name, 0.0) + time.perf_counter() - t0
    return wrapper


gen.hybrid_search = _timed("retrieval_gate_s", gen.hybrid_search)
rr.rerank = _timed("rerank_s", rr.rerank)
# get_reranker được gọi nhiều lần trong một lượt rerank; chỉ lần đầu là nạp model.
_orig_get_reranker = rr.get_reranker
reranker_load_s: float | None = None


def _get_reranker_timed():
    global reranker_load_s
    if rr._model is None:
        t0 = time.perf_counter()
        model = _orig_get_reranker()
        reranker_load_s = time.perf_counter() - t0
        return model
    return _orig_get_reranker()


rr.get_reranker = _get_reranker_timed

client = gen._get_client()
client.messages.create = _timed("api_s", client.messages.create)


# --------------------------------------------------------------------------- #
# Môi trường
# --------------------------------------------------------------------------- #
def _ps(cmd: str) -> str:
    try:
        return subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            capture_output=True, text=True, timeout=30,
        ).stdout.strip()
    except Exception as exc:  # noqa: BLE001
        return f"loi: {exc}"


def machine_info() -> dict:
    import anthropic
    import sentence_transformers
    import torch

    ram = _ps("(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory")
    return {
        "os": platform.platform(),
        "cpu": _ps("(Get-CimInstance Win32_Processor).Name"),
        "cpu_cores_physical": _ps("(Get-CimInstance Win32_Processor).NumberOfCores"),
        "cpu_threads": os.cpu_count(),
        "ram_gb": round(int(ram) / 1024**3, 1) if ram.isdigit() else ram,
        "python": platform.python_version(),
        "torch": torch.__version__,
        "torch_device": "cuda" if torch.cuda.is_available() else "cpu",
        "sentence_transformers": sentence_transformers.__version__,
        "anthropic_sdk": anthropic.__version__,
        "model": gen.MODEL,
    }


def network_info() -> dict:
    adapters = _ps(
        "Get-NetAdapter | Where-Object Status -eq 'Up' | "
        "Select-Object Name,InterfaceDescription,MediaType,LinkSpeed | ConvertTo-Json"
    )
    wlan = subprocess.run(["netsh", "wlan", "show", "interfaces"],
                          capture_output=True, text=True, errors="replace").stdout
    # Chỉ giữ thông số kỹ thuật; bỏ SSID/BSSID/MAC.
    keep = ("Radio type", "Receive rate", "Transmit rate", "Signal", "Band", "Channel", "State")
    wifi = {
        line.split(":", 1)[0].strip(): line.split(":", 1)[1].strip()
        for line in wlan.splitlines()
        if ":" in line and line.split(":", 1)[0].strip().startswith(keep)
    }

    # RTT tới đúng endpoint API: TCP connect và TCP+TLS handshake, 5 mẫu.
    tcp, tls = [], []
    for _ in range(5):
        t0 = time.perf_counter()
        sock = socket.create_connection(("api.anthropic.com", 443), timeout=10)
        t1 = time.perf_counter()
        ssl.create_default_context().wrap_socket(sock, server_hostname="api.anthropic.com").close()
        t2 = time.perf_counter()
        tcp.append((t1 - t0) * 1000)
        tls.append((t2 - t0) * 1000)

    try:
        adapters_json = json.loads(adapters)
    except json.JSONDecodeError:
        adapters_json = adapters
    return {
        "adapters_up": adapters_json,
        "wifi": wifi or "khong dung Wi-Fi",
        "rtt_api_anthropic_com_ms": {
            "tcp_connect_median": round(statistics.median(tcp), 1),
            "tcp_tls_handshake_median": round(statistics.median(tls), 1),
            "samples_tcp": [round(x, 1) for x in tcp],
        },
        "_note": (
            "Toc do tai khong do bang dich vu speedtest ben ngoai; LinkSpeed/Receive "
            "rate la toc do lien ket vat ly, khong phai bang thong Internet thuc."
        ),
    }


# --------------------------------------------------------------------------- #
# Đo
# --------------------------------------------------------------------------- #
def run_one(item: dict, rerank: bool) -> dict:
    timer.clear()
    t0 = time.perf_counter()
    result = gen.generate_answer(
        item["question"],
        filters=None,
        include_deprecated=_uses_deprecated(item),
        rerank=rerank,
    )
    total = time.perf_counter() - t0
    parts = {k: timer.get(k, 0.0) for k in ("retrieval_gate_s", "rerank_s", "api_s")}
    gate_blocked = not result.contexts
    return {
        **{k: round(v, 4) for k, v in parts.items()},
        "total_s": round(total, 4),
        "other_s": round(total - sum(parts.values()), 4),
        "gate_blocked": gate_blocked,
        "refused": result.refused,
        "tokens": {"in": result.input_tokens, "out": result.output_tokens},
        "cost_usd": round(result.cost_usd, 6),
    }


def stats(values: list[float]) -> dict:
    if not values:
        return {}
    arr = np.array(values)
    return {
        "n": len(values),
        "mean": round(float(arr.mean()), 3),
        "median": round(float(np.median(arr)), 3),
        "min": round(float(arr.min()), 3),
        "max": round(float(arr.max()), 3),
        "p95": round(float(np.percentile(arr, 95)), 3),
    }


def summarise(rows: list[dict], rerank: bool) -> dict:
    comps = ["retrieval_gate_s"] + (["rerank_s"] if rerank else []) + ["api_s", "other_s", "total_s"]
    out = {c: stats([r[c] for r in rows]) for c in comps}
    api, tot = sum(r["api_s"] for r in rows), sum(r["total_s"] for r in rows)
    out["api_share_pct"] = {
        "tren_tong_thoi_gian": round(100 * api / tot, 1),
        "trung_binh_tung_cau": round(statistics.mean(100 * r["api_s"] / r["total_s"] for r in rows), 1),
    }
    return out


def main() -> None:
    questions = load_questions()
    started = datetime.now().astimezone()

    print("Thu thap cau hinh may va mang...")
    env = {"machine": machine_info(), "network": network_info()}

    # Làm nóng giống app.py (@st.cache_resource): collection, embedding, BM25.
    # KHÔNG làm nóng cross-encoder — app cũng không, và ta cần đo lần nạp đầu.
    t0 = time.perf_counter()
    from src.bm25_retriever import get_index
    from src.embedding import get_model
    from src.vectorstore import get_collection
    get_collection(CHROMA_DIR); get_model(); get_index(CHROMA_DIR)
    warmup_s = time.perf_counter() - t0

    raw: dict[str, dict[str, list[dict]]] = {"rerank_false": {}, "rerank_true": {}}
    first_rerank_call: dict | None = None
    for qid in QUESTION_IDS:
        item = questions[qid]
        # Xen kẽ F1, T1, F2, T2 để biến động mạng/tải API chia đều cho hai cấu hình.
        for rnd in range(1, ROUNDS + 1):
            for rerank in (False, True):
                arm = "rerank_true" if rerank else "rerank_false"
                row = run_one(item, rerank)
                row["round"] = rnd
                raw[arm].setdefault(qid, []).append(row)
                if rerank and first_rerank_call is None:
                    first_rerank_call = {"qid": qid, **row}
                print(f"{qid} {arm:<13} luot {rnd}: total {row['total_s']:.2f}s "
                      f"(retr {row['retrieval_gate_s']:.2f} rr {row['rerank_s']:.2f} "
                      f"api {row['api_s']:.2f}) gate={row['gate_blocked']} refused={row['refused']}")

    # Thống kê trên LƯỢT 2; so lượt 1 vs lượt 2 để báo câu dao động > 20%.
    summary, flagged, per_question = {}, [], {}
    for arm, by_q in raw.items():
        rows2 = [runs[1] for runs in by_q.values()]
        summary[arm] = summarise(rows2, rerank=arm == "rerank_true")
        blocked = [q for q, runs in by_q.items() if runs[1]["gate_blocked"]]
        summary[arm]["gate_blocked"] = blocked
        if blocked:
            summary[arm]["khong_tinh_cau_bi_gate_chan"] = summarise(
                [runs[1] for q, runs in by_q.items() if q not in blocked], arm == "rerank_true"
            )
        for qid, runs in by_q.items():
            t1, t2 = runs[0]["total_s"], runs[1]["total_s"]
            diff = abs(t1 - t2) / t2
            per_question.setdefault(qid, {"group": questions[qid]["group"]})[arm] = runs
            if diff > FLAG_RATIO:
                flagged.append({"qid": qid, "cau_hinh": arm, "luot_1_s": t1, "luot_2_s": t2,
                                "chenh_lech_pct": round(100 * diff, 1),
                                "api_luot_1_s": runs[0]["api_s"], "api_luot_2_s": runs[1]["api_s"]})

    q0 = first_rerank_call["qid"]
    second = raw["rerank_true"][q0][1]
    first_time = {
        "cross_encoder_load_s": round(reranker_load_s, 3) if reranker_load_s else None,
        "cau_dung_de_do": q0,
        "tinh_toan__nap_cong_luot_2_s": round(reranker_load_s + second["total_s"], 3),
        "do_that__luot_rerank_dau_tien_s": first_rerank_call["total_s"],
        "_note": (
            "tinh_toan = thoi gian nap + tong thoi gian luot 2 cua cung cau. do_that = "
            "lan goi rerank=True dau tien trong tien trinh (da gom ca nap model). App "
            "khong lam nong cross-encoder nen nguoi dung gap dung con so nay o lan bat dau."
        ),
    }

    all_rows = [r for by_q in raw.values() for runs in by_q.values() for r in runs]
    payload = {
        "metadata": {
            "thoi_diem_bat_dau": started.isoformat(timespec="seconds"),
            "thoi_diem_ket_thuc": datetime.now().astimezone().isoformat(timespec="seconds"),
            "reproduce": "venv\\Scripts\\python notebooks\\do_latency.py",
            "duong_goi": "src.generation.generate_answer(question, filters=None, include_deprecated=..., rerank=...) - dung tham so app.run_query truyen vao",
            "store": "KHONG dung ragas_store.json - moi luot deu goi API that",
            "cau_hoi": {q: questions[q]["group"] for q in QUESTION_IDS},
            "so_luot": ROUNDS,
            "thong_ke_tren": "luot 2 cua moi cau (luot 1 coi la lam nong)",
            "thu_tu": "xen ke F1, T1, F2, T2 cho tung cau",
            "p95_note": "n=10 nen p95 (noi suy tuyen tinh) gan sat gia tri lon nhat",
            "warmup_embedding_bm25_chroma_s": round(warmup_s, 3),
        },
        "moi_truong": env,
        "thong_ke": summary,
        "lan_dau_bat_rerank": first_time,
        "cau_dao_dong_tren_20pct": flagged,
        "per_question": per_question,
        "chi_phi": {
            "so_luot_goi_api": sum(1 for r in all_rows if not r["gate_blocked"]),
            "usd": round(sum(r["cost_usd"] for r in all_rows), 4),
            "tokens_in": sum(r["tokens"]["in"] for r in all_rows),
            "tokens_out": sum(r["tokens"]["out"] for r in all_rows),
            "gia": {"in": PRICE_PER_MTOK_IN, "out": PRICE_PER_MTOK_OUT},
        },
    }
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDa ghi {OUT_PATH}")
    print(json.dumps({k: payload[k] for k in ("thong_ke", "lan_dau_bat_rerank",
                                              "cau_dao_dong_tren_20pct", "chi_phi")},
                     ensure_ascii=False, indent=1))
    print(json.dumps(env, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()

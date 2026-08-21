"""Shared pytest plumbing.

Chỉ có một việc: gom chi phí API của `tests/test_generation.py` rồi in bảng tổng ở
cuối lần chạy.

Vì sao dùng hook `pytest_terminal_summary` chứ không `print` trong fixture teardown:
terminal summary KHÔNG bị pytest capture, nên bảng chi phí luôn hiện kể cả khi chạy
`pytest tests/ -v` không kèm `-s`. Đây là thứ phải nhìn thấy được mỗi lần chạy — nếu
nó chỉ hiện khi nhớ thêm cờ thì coi như không có.
"""

from __future__ import annotations

import pytest

# Mỗi phần tử: (nhãn, input_tokens, output_tokens, cost_usd, đã-bị-gate-chặn?)
COST_LOG: list[tuple[str, int, int, float, bool]] = []


def pytest_sessionstart(session) -> None:
    """Force pytest's terminal output to UTF-8 on Windows consoles.

    Console Windows mặc định là cp1252. ``TerminalWriter.write_raw`` bắt
    ``UnicodeEncodeError`` rồi âm thầm rơi về ``unicode-escape``, nên bảng chi phí in ra
    thành "CHI PH\\xcd API" và mọi thông báo assert tiếng Việt cũng vậy — hỏng im lặng,
    không có gì đỏ.

    Hai cái bẫy đã đo được, đừng "đơn giản hóa" lại:

    1. Phải sửa ĐÚNG ``TerminalWriter._file``, KHÔNG phải ``sys.stdout``. pytest bọc
       ``sys.stdout`` bằng object capture ngay từ đầu, còn TerminalWriter giữ handle
       console GỐC lưu trước đó — reconfigure ``sys.stdout`` không đụng tới nó.
    2. Phải ở ``pytest_sessionstart``, KHÔNG phải ``pytest_configure``: lúc conftest
       chạy ``pytest_configure`` thì plugin "terminalreporter" chưa đăng ký,
       ``get_plugin`` trả None và đoạn code này im lặng không làm gì.

    Đặt ở sessionstart (chứ không ở ``pytest_terminal_summary``) để thông báo assert
    trong lúc chạy cũng đọc được, không chỉ mỗi bảng cuối.
    """
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    stream = getattr(getattr(reporter, "_tw", None), "_file", None)
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")


@pytest.fixture(scope="session")
def cost_log() -> list[tuple[str, int, int, float, bool]]:
    """The accumulator that `pytest_terminal_summary` prints at the end."""
    return COST_LOG


def pytest_terminal_summary(terminalreporter, exitstatus, config) -> None:
    """Print the API cost table after the run, if any LLM test actually ran."""
    if not COST_LOG:
        return

    # Import muộn: lần chạy không có test LLM nào thì không phải nạp src.generation.
    from src.generation import MODEL, PRICE_PER_MTOK_IN, PRICE_PER_MTOK_OUT

    write = terminalreporter.write_line
    write("")
    write("=" * 78)
    write(
        f"CHI PHÍ API — {MODEL} "
        f"(${PRICE_PER_MTOK_IN:.2f} / ${PRICE_PER_MTOK_OUT:.2f} mỗi 1M token)"
    )
    write("=" * 78)

    total_in = total_out = total_cost = 0.0
    gated = 0
    for label, tokens_in, tokens_out, cost, was_gated in COST_LOG:
        total_in += tokens_in
        total_out += tokens_out
        total_cost += cost
        gated += was_gated
        note = "  (gate chặn, không gọi API)" if was_gated else ""
        write(
            f"  {label:<34}{tokens_in:>7,} in {tokens_out:>6,} out  ${cost:.6f}{note}"
        )

    called = len(COST_LOG) - gated
    write("-" * 78)
    write(
        f"  {'TỔNG':<34}{int(total_in):>7,} in {int(total_out):>6,} out  ${total_cost:.6f}"
    )
    write(f"  {called} lần gọi API thật, {gated} lần bị gate chặn trước LLM.")
    if called:
        write(f"  Trung bình mỗi lần gọi: ${total_cost / called:.6f}")
    write("=" * 78)

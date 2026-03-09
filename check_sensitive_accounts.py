#!/usr/bin/env python3
"""批量检查 CSV 中的 X/Twitter 账号是否为敏感账号。"""

from __future__ import annotations

import csv
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Iterable, List, Optional, Tuple


API_HOST = "twitter241.p.rapidapi.com"
API_URL = f"https://{API_HOST}/user?username={{username}}"
REQUESTS_PER_SECOND = 5
MIN_REQUEST_INTERVAL = 1 / REQUESTS_PER_SECOND
MAX_RETRIES = 5
DEFAULT_TIMEOUT = 30
HEADER_NAMES = {"username", "user", "screen_name", "账号", "用户名"}
CSV_ENCODINGS = (
    "utf-8-sig",
    "utf-8",
    "gb18030",
    "gbk",
    "utf-16",
    "utf-16-le",
    "utf-16-be",
)


def prompt(text: str, default: Optional[str] = None, secret: bool = False) -> str:
    if secret:
        try:
            import getpass

            value = getpass.getpass(text)
        except Exception:
            value = input(text)
    else:
        value = input(text)
    value = value.strip()
    return value or (default or "")


def get_runtime_directory() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def should_pause_on_exit() -> bool:
    return getattr(sys, "frozen", False)


def pause_before_exit(message: str = "按回车键退出...") -> None:
    if not should_pause_on_exit():
        return
    try:
        input(message)
    except EOFError:
        pass


def list_csv_files(directory: Path) -> List[Path]:
    return sorted(
        path
        for path in directory.glob("*.csv")
        if path.is_file() and not path.name.endswith("_result.csv")
    )


def has_header(first_value: str) -> bool:
    return first_value.strip().lower() in HEADER_NAMES


def read_existing_output(output_path: Path) -> Tuple[int, bool]:
    if not output_path.exists():
        return 0, False

    processed_rows = 0
    header_written = False
    with output_path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        for index, row in enumerate(reader):
            if index == 0:
                if row and row[0].strip().lower() in HEADER_NAMES:
                    header_written = True
                    continue
            if any(cell.strip() for cell in row):
                processed_rows += 1
    return processed_rows, header_written


def load_csv_rows(csv_path: Path) -> List[List[str]]:
    last_error: Optional[UnicodeDecodeError] = None
    for encoding in CSV_ENCODINGS:
        try:
            with csv_path.open("r", newline="", encoding=encoding) as source:
                return list(csv.reader(source))
        except UnicodeDecodeError as exc:
            last_error = exc

    if last_error is not None:
        raise ValueError(
            f"无法识别 CSV 编码，请将文件另存为 UTF-8 后重试: {csv_path.name}"
        ) from last_error

    return []


class RateLimiter:
    def __init__(self, min_interval: float) -> None:
        self.min_interval = min_interval
        self.last_request_at = 0.0

    def wait(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last_request_at
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)

    def mark(self) -> None:
        self.last_request_at = time.monotonic()


def fetch_user_info(username: str, api_key: str, limiter: RateLimiter) -> Tuple[Optional[bool], str, str]:
    encoded_username = urllib.parse.quote(username)
    url = API_URL.format(username=encoded_username)

    for attempt in range(1, MAX_RETRIES + 1):
        limiter.wait()
        request = urllib.request.Request(
            url,
            headers={
                "x-rapidapi-key": api_key,
                "x-rapidapi-host": API_HOST,
            },
            method="GET",
        )

        try:
            with urllib.request.urlopen(request, timeout=DEFAULT_TIMEOUT) as response:
                limiter.mark()
                if response.status != 200:
                    raise urllib.error.HTTPError(
                        url, response.status, f"HTTP {response.status}", response.headers, None
                    )
                payload = json.loads(response.read().decode("utf-8"))
                return parse_user_info(payload)
        except urllib.error.HTTPError as exc:
            limiter.mark()
            if exc.code == 429:
                wait_seconds = max(2, attempt)
            elif 500 <= exc.code < 600:
                wait_seconds = attempt
            else:
                body = ""
                if exc.fp:
                    try:
                        body = exc.fp.read().decode("utf-8", errors="ignore")[:120]
                    except Exception:
                        body = ""
                return None, "", f"HTTP {exc.code} {body}".strip()
        except Exception as exc:  # noqa: BLE001
            limiter.mark()
            wait_seconds = attempt
            if attempt == MAX_RETRIES:
                return None, "", f"异常: {exc}"

        if attempt < MAX_RETRIES:
            time.sleep(wait_seconds)

    return None, "", "请求失败"


def parse_user_info(payload: dict) -> Tuple[Optional[bool], str, str]:
    user_result = (
        payload.get("result", {})
        .get("data", {})
        .get("user", {})
        .get("result")
    )

    if not user_result:
        return False, "", ""

    if user_result.get("__typename") != "User":
        return False, "", ""

    legacy = user_result.get("legacy", {})
    possibly_sensitive = legacy.get("possibly_sensitive") is True
    profile_interstitial_type = str(legacy.get("profile_interstitial_type") or "").strip()
    return possibly_sensitive, profile_interstitial_type, ""


def normalize_result(possibly_sensitive: Optional[bool], profile_interstitial_type: str, error: str) -> str:
    if error:
        return "请求失败"
    is_sensitive = possibly_sensitive is True or bool(profile_interstitial_type)
    return "敏感账号" if is_sensitive else "非敏感账号"


def build_header(source_header: Iterable[str]) -> List[str]:
    return list(source_header) + [
        "possibly_sensitive",
        "profile_interstitial_type",
        "是否敏感账号",
    ]


def count_pending_rows(csv_path: Path) -> int:
    output_path = csv_path.with_name(f"{csv_path.stem}_result.csv")
    processed_rows, _ = read_existing_output(output_path)
    rows = load_csv_rows(csv_path)

    if not rows:
        return 0

    first_row = rows[0]
    source_has_header = bool(first_row and has_header(first_row[0]))
    start_index = 1 if source_has_header else 0
    total_rows = max(len(rows) - start_index, 0)
    return max(total_rows - processed_rows, 0)


def process_file(
    csv_path: Path,
    api_key: str,
    limiter: RateLimiter,
    progress_done: int,
    progress_total: int,
) -> int:
    output_path = csv_path.with_name(f"{csv_path.stem}_result.csv")
    processed_rows, header_written = read_existing_output(output_path)
    rows = load_csv_rows(csv_path)

    if not rows:
        print(f"[跳过] {csv_path.name} 是空文件")
        return progress_done

    first_row = rows[0]
    source_has_header = bool(first_row and has_header(first_row[0]))
    start_index = 1 if source_has_header else 0
    total_rows = max(len(rows) - start_index, 0)

    if processed_rows >= total_rows and output_path.exists():
        print(f"[完成] {csv_path.name} 已全部处理，跳过")
        return progress_done

    mode = "a" if output_path.exists() else "w"
    with output_path.open(mode, newline="", encoding="utf-8-sig") as target:
        writer = csv.writer(target)

        if not header_written:
            header_row = first_row if source_has_header else ["username"]
            writer.writerow(build_header(header_row))
            target.flush()

        for row_number, row in enumerate(rows[start_index:], start=1):
            if row_number <= processed_rows:
                continue

            username = (row[0] if row else "").strip()
            if not username:
                writer.writerow(list(row) + ["", "", "用户名为空"])
                target.flush()
                progress_done += 1
                print_progress(
                    csv_path.name,
                    row_number,
                    total_rows,
                    progress_done,
                    progress_total,
                    "用户名为空，已跳过",
                )
                continue

            possibly_sensitive, profile_interstitial_type, error = fetch_user_info(
                username, api_key, limiter
            )
            result_text = normalize_result(possibly_sensitive, profile_interstitial_type, error)
            writer.writerow(
                list(row)
                + [
                    "" if possibly_sensitive is None else str(possibly_sensitive).lower(),
                    profile_interstitial_type,
                    result_text,
                ]
            )
            target.flush()
            progress_done += 1
            detail = (
                f"{username} -> possibly_sensitive={possibly_sensitive}, "
                f"profile_interstitial_type={profile_interstitial_type or '-'}, "
                f"结果={result_text}"
            )
            print_progress(
                csv_path.name,
                row_number,
                total_rows,
                progress_done,
                progress_total,
                detail,
            )

    return progress_done


def print_progress(
    file_name: str,
    file_row_number: int,
    file_total_rows: int,
    progress_done: int,
    progress_total: int,
    detail: str,
) -> None:
    percent = 100.0 if progress_total == 0 else (progress_done / progress_total) * 100
    print(
        f"[总进度 {progress_done}/{progress_total} {percent:6.2f}%] "
        f"[{file_name} {file_row_number}/{file_total_rows}] {detail}"
    )


def main() -> int:
    print("批量敏感账号检查工具")
    print("说明：自动读取当前程序所在文件夹中的 CSV 文件，按第一列用户名调用 RapidAPI，并生成 *_result.csv")
    print("")

    runtime_directory = get_runtime_directory()
    api_key = prompt("请输入 RapidAPI Key: ", secret=True)
    if not api_key:
        print("未输入 API Key，程序结束")
        return 1

    directory = runtime_directory
    print(f"将扫描当前文件夹中的 CSV 文件: {directory}")
    print("请把 exe 或脚本和要处理的 CSV 放在同一个文件夹内")

    csv_files = list_csv_files(directory)
    if not csv_files:
        print(f"当前文件夹未找到 CSV 文件: {directory}")
        return 1

    print("")
    print(f"找到 {len(csv_files)} 个 CSV 文件，按 {REQUESTS_PER_SECOND} 次/秒开始处理")
    limiter = RateLimiter(MIN_REQUEST_INTERVAL)
    total_pending_rows = sum(count_pending_rows(csv_file) for csv_file in csv_files)
    completed_rows = 0

    if total_pending_rows == 0:
        print("所有 CSV 都已经处理完成，无需继续")
        return 0

    print(f"本次待处理总行数: {total_pending_rows}")

    for index, csv_file in enumerate(csv_files, start=1):
        print("")
        print(f"=== [{index}/{len(csv_files)}] 处理 {csv_file.name} ===")
        completed_rows = process_file(
            csv_file,
            api_key,
            limiter,
            completed_rows,
            total_pending_rows,
        )

    print("")
    print("全部处理完成")
    return 0


if __name__ == "__main__":
    exit_code = 1
    try:
        exit_code = main()
        if exit_code != 0:
            pause_before_exit()
    except KeyboardInterrupt:
        print("")
        print("用户取消运行")
        pause_before_exit()
    except Exception as exc:  # noqa: BLE001
        print("")
        print(f"程序异常退出: {exc}")
        pause_before_exit()
    sys.exit(exit_code)

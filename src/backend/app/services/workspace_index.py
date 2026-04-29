from __future__ import annotations

"""워크스페이스 파일 인덱스 & 요약 관리"""
import os

META_DIR = ".haro"
LEGACY_META_DIR = ".openclaw"
META_EXCLUDES = [META_DIR, LEGACY_META_DIR]


def build_file_tree(workspace: str, prefix: str = "", exclude: list[str] | None = None) -> str:
    """워크스페이스의 파일 트리를 텍스트로 생성"""
    exclude = exclude or META_EXCLUDES
    lines: list[str] = []
    _walk_tree(workspace, lines, prefix="", exclude=exclude)
    return "\n".join(lines) if lines else "(빈 워크스페이스)"


def _walk_tree(path: str, lines: list[str], prefix: str, exclude: list[str], depth: int = 0) -> None:
    if depth > 10:
        return
    try:
        entries = sorted(os.scandir(path), key=lambda e: (e.is_file(), e.name))
    except PermissionError:
        return
    filtered = [e for e in entries if e.name not in exclude]
    for i, entry in enumerate(filtered):
        is_last = i == len(filtered) - 1
        connector = "└── " if is_last else "├── "
        if entry.is_dir():
            lines.append(f"{prefix}{connector}{entry.name}/")
            extension = "    " if is_last else "│   "
            _walk_tree(entry.path, lines, prefix + extension, exclude, depth + 1)
        else:
            size = entry.stat().st_size
            lines.append(f"{prefix}{connector}{entry.name}  [{size}B]")


def generate_simple_summary(file_path: str, content: str) -> str:
    """짧은 파일(≤30줄)의 간단한 요약 생성 (LLM 없이)"""
    lines = content.split("\n")
    line_count = len(lines)
    first_line = lines[0].strip() if lines else ""
    return f"- {line_count}줄, 첫 줄: `{first_line[:80]}`"


async def update_file_summary(workspace: str, file_path: str, action: str) -> None:
    """파일 변경 시 해당 파일의 요약을 갱신"""
    meta_dir = os.path.join(workspace, META_DIR)
    summaries_dir = os.path.join(meta_dir, "file_summaries")
    os.makedirs(summaries_dir, exist_ok=True)

    summary_filename = file_path.strip("/").replace("/", "__").replace("\\", "__") + ".md"
    summary_path = os.path.join(summaries_dir, summary_filename)

    if action == "deleted":
        if os.path.exists(summary_path):
            os.remove(summary_path)
    else:
        full_path = os.path.join(workspace, file_path.lstrip("/"))
        if not os.path.isfile(full_path):
            return
        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception:
            return
        summary = generate_simple_summary(file_path, content)
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write(summary)

    await rebuild_workspace_index(workspace)


async def rebuild_workspace_index(workspace: str) -> None:
    """개별 파일 요약들을 모아서 workspace.md 생성"""
    meta_dir = os.path.join(workspace, META_DIR)
    summaries_dir = os.path.join(meta_dir, "file_summaries")
    os.makedirs(meta_dir, exist_ok=True)

    tree = build_file_tree(workspace)

    file_summaries: dict[str, str] = {}
    for candidate_dir in [
        os.path.join(workspace, LEGACY_META_DIR, "file_summaries"),
        summaries_dir,
    ]:
        if os.path.exists(candidate_dir):
            for fname in sorted(os.listdir(candidate_dir)):
                if fname.endswith(".md"):
                    original = "/" + fname[:-3].replace("__", "/")
                    with open(os.path.join(candidate_dir, fname), "r", encoding="utf-8") as f:
                        file_summaries[original] = f.read().strip()

    content = "# 워크스페이스 인덱스\n\n"
    content += f"## 파일 트리\n```\n{tree}\n```\n\n"
    if file_summaries:
        content += "## 파일별 요약\n\n"
        for path, summary in file_summaries.items():
            content += f"### {path}\n{summary}\n\n"

    with open(os.path.join(meta_dir, "workspace.md"), "w", encoding="utf-8") as f:
        f.write(content)


def load_workspace_context(workspace: str) -> str | None:
    """workspace.md 로드"""
    for meta_name in [META_DIR, LEGACY_META_DIR]:
        path = os.path.join(workspace, meta_name, "workspace.md")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
    return None

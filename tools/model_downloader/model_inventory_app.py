#!/usr/bin/env python
"""
Streamlit UI for browsing and downloading model inventory.

Run with:
  streamlit run scripts/model_inventory_app.py --server.address 0.0.0.0 --server.port 8501
"""
from __future__ import annotations

import csv
import os
import shutil
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator

import streamlit as st

from comani.utils.model_downloader import (
    DownloadItem,
    detect_type,
    download_url,
    resolve_download,
)
from comani.core.downloader import ModelDownloader


REPO_ROOT = Path(__file__).resolve().parents[1]
INVENTORY_PATH = REPO_ROOT / "comani" / "models" / "model_inventory.csv"
DEFAULT_PATH = REPO_ROOT / "comani" / "models" / "model_default.csv"


@dataclass
class Entry:
    index: int
    architecture: str
    item_type: str
    name: str
    url: str
    source: str
    save_path: str
    size_bytes: str
    size_human: str


@dataclass
class TreeNode:
    name: str
    files: list[int] = field(default_factory=list)  # entry indices
    children: dict[str, "TreeNode"] = field(default_factory=dict)

    def add_path(self, parts: list[str], entry_index: int) -> None:
        if not parts:
            self.files.append(entry_index)
            return
        head, *rest = parts
        child = self.children.setdefault(head, TreeNode(name=head))
        child.add_path(rest, entry_index)

    def iter_leaves(self) -> Iterator[int]:
        for f in self.files:
            yield f
        for child in self.children.values():
            yield from child.iter_leaves()


def load_entries(path: Path) -> list[Entry]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        entries: list[Entry] = []
        for idx, row in enumerate(reader):
            entries.append(
                Entry(
                    index=idx,
                    architecture=row.get("architecture", ""),
                    item_type=row.get("type", ""),
                    name=row.get("name", ""),
                    url=row.get("url", ""),
                    source=row.get("source", ""),
                    save_path=row.get("save_path", ""),
                    size_bytes=row.get("size_bytes", ""),
                    size_human=row.get("size_human", ""),
                )
            )
        return entries


def ensure_default_file() -> None:
    if DEFAULT_PATH.exists():
        return
    DEFAULT_PATH.write_bytes(INVENTORY_PATH.read_bytes())


def load_default_selection(entries: list[Entry]) -> set[int]:
    ensure_default_file()
    default_entries = load_entries(DEFAULT_PATH)
    default_paths = {e.save_path for e in default_entries}
    return {e.index for e in entries if e.save_path in default_paths}


def init_session(entries: list[Entry], default_selected: set[int]) -> None:
    if "file_selected" not in st.session_state:
        st.session_state["file_selected"] = {}
    if "expanded" not in st.session_state:
        st.session_state["expanded"] = {}

    file_selected: dict[int, bool] = st.session_state["file_selected"]
    # Reset selections to align with current entries.
    new_selected: dict[int, bool] = {}
    for entry in entries:
        widget_key = f"file-{entry.index}"
        if widget_key in st.session_state:
            new_value = st.session_state[widget_key]
        else:
            new_value = file_selected.get(entry.index, entry.index in default_selected)
        new_selected[entry.index] = new_value
        st.session_state[widget_key] = new_value
    st.session_state["file_selected"] = new_selected


def build_tree(entries: list[Entry]) -> TreeNode:
    root = TreeNode(name="root")
    for entry in entries:
        parts = list(Path(entry.save_path).parts)
        root.add_path(parts, entry.index)
    return root


def dir_state(leaf_ids: list[int], selected: dict[int, bool]) -> tuple[str, int]:
    if not leaf_ids:
        return "none", 0
    selected_count = sum(1 for i in leaf_ids if selected.get(i, False))
    if selected_count == 0:
        return "none", selected_count
    if selected_count == len(leaf_ids):
        return "all", selected_count
    return "partial", selected_count


def set_leaf_selection(leaf_ids: Iterable[int], value: bool) -> None:
    for leaf_id in leaf_ids:
        st.session_state["file_selected"][leaf_id] = value
        st.session_state[f"file-{leaf_id}"] = value


def state_icon(state: str) -> str:
    return {"all": "✅", "partial": "➖", "none": "⬜"}.get(state, "⬜")


def render_tree(node: TreeNode, entries: list[Entry], selected: dict[int, bool], path_parts: list[str]) -> None:
    # If node is a file container.
    if not node.children and len(list(node.iter_leaves())) == 1 and node.files:
        entry_idx = node.files[0]
        entry = entries[entry_idx]
        checked = selected.get(entry_idx, False)
        new_value = st.checkbox(
            f"{Path(entry.save_path).name} ({entry.size_human})",
            value=checked,
            key=f"file-{entry_idx}",
        )
        st.session_state["file_selected"][entry_idx] = new_value
        return

    leaf_ids = list(node.iter_leaves())
    if not leaf_ids:
        return

    state, selected_count = dir_state(leaf_ids, selected)
    total = len(leaf_ids)
    path_key = "/".join(path_parts + [node.name])
    expanded = st.session_state["expanded"].get(path_key, state == "partial")
    st.session_state["expanded"].setdefault(path_key, expanded)

    cols = st.columns([0.18, 0.82])
    label = f"{node.name} ({selected_count}/{total})"
    if cols[0].button(f"{state_icon(state)}", key=f"toggle-{path_key}"):
        target = True if state in ("partial", "none") else False
        set_leaf_selection(leaf_ids, target)
        if hasattr(st, "rerun"):
            st.rerun()
        else:
            st.experimental_rerun()
    cols[1].markdown(f"**{label}**")

    with st.expander(f"Contents of {node.name}", expanded=expanded):
        for child_name in sorted(node.children.keys()):
            child = node.children[child_name]
            render_tree(child, entries, selected, path_parts + [node.name])
        for file_idx in node.files:
            entry = entries[file_idx]
            checked = selected.get(file_idx, False)
            new_value = st.checkbox(
                f"{Path(entry.save_path).name} ({entry.size_human})",
                value=checked,
                key=f"file-{file_idx}",
            )
            st.session_state["file_selected"][file_idx] = new_value


def selected_entries(entries: list[Entry]) -> list[Entry]:
    return [e for e in entries if st.session_state["file_selected"].get(e.index, False)]


def save_selection(entries: list[Entry], path: Path) -> None:
    rows = [e for e in entries if st.session_state["file_selected"].get(e.index, False)]
    if not rows:
        st.warning("没有勾选任何条目，已跳过保存。")
        return
    fieldnames = ["architecture", "type", "name", "url", "source", "save_path", "size_bytes", "size_human"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for e in rows:
            writer.writerow(
                {
                    "architecture": e.architecture,
                    "type": e.item_type,
                    "name": e.name,
                    "url": e.url,
                    "source": e.source,
                    "save_path": e.save_path,
                    "size_bytes": e.size_bytes,
                    "size_human": e.size_human,
                }
            )
    st.success(f"已保存到 {path}")


def next_copy_path() -> Path:
    date_str = datetime.now().strftime("%Y%m%d")
    existing = sorted(DEFAULT_PATH.parent.glob(f"{date_str}_*.csv"))
    next_idx = 1
    if existing:
        last = existing[-1].stem.split("_")[-1]
        if last.isdigit():
            next_idx = int(last) + 1
    return DEFAULT_PATH.parent / f"{date_str}_{next_idx}.csv"


def download_entries(entries: list[Entry], comfyui_root: str | Path) -> None:
    comfyui_root = Path(comfyui_root)
    try:
        downloader = ModelDownloader(comfyui_root)
        models_dir = downloader.models_dir
    except Exception as exc:
        st.error(f"解析 COMFYUI_DIR 失败: {exc}")
        return

    selected = selected_entries(entries)
    if not selected:
        st.warning("没有勾选任何条目，未开始下载。")
        return

    status = st.empty()
    for entry in selected:
        status.info(f"下载 {entry.name} -> {entry.save_path}")
        rel_path = Path(entry.save_path)
        if rel_path.parts and rel_path.parts[0] == "models":
            rel_path = Path(*rel_path.parts[1:])
        target_path = models_dir / rel_path
        target_path.parent.mkdir(parents=True, exist_ok=True)

        item = DownloadItem(
            type=detect_type(entry.url),
            url=entry.url,
            name=target_path.name,
        )
        resolved = resolve_download(item)
        if isinstance(resolved, list):
            base_dir = target_path if target_path.suffix == "" else target_path.parent
            base_dir.mkdir(parents=True, exist_ok=True)
            for dl in resolved:
                download_url(dl.url, base_dir / dl.filename, dl.headers)
        else:
            download_url(resolved.url, target_path, resolved.headers)
    status.success("下载完成！")


def main() -> None:
    st.set_page_config(page_title="Model Inventory", layout="wide")
    st.title("模型下载清单")
    st.caption("从 model_inventory.csv 构建树状清单，可保存默认列表或直接下载。")

    if not INVENTORY_PATH.exists():
        st.error(f"缺少清单文件：{INVENTORY_PATH}")
        return

    entries = load_entries(INVENTORY_PATH)
    default_selected = load_default_selection(entries)
    init_session(entries, default_selected)
    tree = build_tree(entries)

    st.subheader("可下载列表")
    render_tree(tree, entries, st.session_state["file_selected"], [])

    st.subheader("操作")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("覆盖保存默认清单"):
            save_selection(entries, DEFAULT_PATH)
    with col2:
        if st.button("保存为新副本"):
            copy_path = next_copy_path()
            save_selection(entries, copy_path)
    with col3:
        comfyui_root = st.text_input("COMFYUI_DIR", value=os.environ.get("COMFYUI_DIR", ""))
        if st.button("下载所选模型"):
            if not comfyui_root:
                st.error("请填写 COMFYUI_DIR 后再下载。")
            else:
                download_entries(entries, comfyui_root)


if __name__ == "__main__":
    main()

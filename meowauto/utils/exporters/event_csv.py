# -*- coding: utf-8 -*-
"""
事件CSV导出工具
- 从 Tk Treeview 读取事件并导出为 CSV
- 与 app.py 中现有列结构保持一致
"""
from typing import Iterable, Sequence
import csv

COLUMNS: Sequence[str] = (
    "序号", "开始(s)", "类型", "音符", "通道", "组", "结束(s)", "时长(s)", "和弦"
)


def export_event_csv(event_tree, filename: str) -> None:
    """将事件表导出为 CSV 文件。
    参数:
    - event_tree: Tkinter Treeview 控件
    - filename: 目标文件路径
    """
    with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(COLUMNS)
        for item in event_tree.get_children():
            writer.writerow(event_tree.item(item)['values'])

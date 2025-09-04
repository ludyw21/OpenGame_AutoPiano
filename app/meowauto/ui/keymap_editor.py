import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict

from meowauto.config.key_mapping_manager import KeyMappingManager, DEFAULT_MAPPING

class KeymapEditor:
    def __init__(self, root, manager: KeyMappingManager):
        self.root = root
        self.manager = manager
        self.top = tk.Toplevel(root)
        self.top.title("自定义21键映射")
        self.top.geometry("420x360")
        self.top.transient(root)
        self.top.grab_set()

        self.vars: Dict[str, tk.StringVar] = {}
        frm = ttk.Frame(self.top, padding=10)
        frm.pack(fill=tk.BOTH, expand=True)

        # grid headers
        ttk.Label(frm, text="音域").grid(row=0, column=0, padx=6, pady=6)
        for i, d in enumerate(['1','2','3','4','5','6','7'], start=1):
            ttk.Label(frm, text=d).grid(row=0, column=i, padx=6, pady=6)

        mapping = self.manager.get_mapping()
        for r, region in enumerate(['L','M','H'], start=1):
            ttk.Label(frm, text={'L':'低音(L)','M':'中音(M)','H':'高音(H)'}[region]).grid(row=r, column=0, sticky=tk.W)
            for c, d in enumerate(['1','2','3','4','5','6','7'], start=1):
                key = f"{region}{d}"
                var = tk.StringVar(value=mapping.get(key, DEFAULT_MAPPING[key]))
                self.vars[key] = var
                e = ttk.Entry(frm, width=6, textvariable=var)
                e.grid(row=r, column=c, padx=4, pady=4)

        btns = ttk.Frame(frm)
        btns.grid(row=5, column=0, columnspan=8, pady=(12,0), sticky=tk.EW)
        ttk.Button(btns, text="恢复默认", command=self._reset_default).pack(side=tk.LEFT)
        ttk.Button(btns, text="保存", command=self._save).pack(side=tk.RIGHT, padx=(6,0))
        ttk.Button(btns, text="取消", command=self.top.destroy).pack(side=tk.RIGHT)

    def _reset_default(self):
        for k, v in self.vars.items():
            v.set(DEFAULT_MAPPING[k])

    def _save(self):
        new_map = {k: v.get().strip() for k, v in self.vars.items()}
        self.manager.update_mapping(new_map)
        if self.manager.save():
            messagebox.showinfo("成功", "键位映射已保存")
            self.top.destroy()
        else:
            messagebox.showerror("错误", "保存失败，请检查文件权限")

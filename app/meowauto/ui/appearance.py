import ctypes
from tkinter import ttk
from tkinter import font as tkfont

try:
    import ttkbootstrap as tb
except Exception:
    tb = None

class AppearanceManager:
    def __init__(self, app, config: dict, logger):
        self.app = app
        self.config = config
        self.log = logger if callable(logger) else (lambda *a, **k: None)
        self.style = None

    def init(self):
        ui_cfg = self.config.get("ui", {})
        # scaling
        self.apply_scaling(ui_cfg.get("scaling", "auto"))
        # theme
        try:
            if tb is not None:
                theme = ui_cfg.get("theme_name", "pink")
                self.style = tb.Style(theme=theme)
            else:
                self.style = ttk.Style()
            # button styles
            self.app.accent_button_style = "Accent.TButton" if tb else "TButton"
            self.app.secondary_button_style = "Secondary.TButton" if tb else "TButton"
            src = "ttkbootstrap" if tb else "system ttk"
            self.log(f"外观初始化完成（{src}）", "INFO")
        except Exception:
            self.style = ttk.Style()
            self.app.accent_button_style = "TButton"
            self.app.secondary_button_style = "TButton"
        # density
        self.apply_density(ui_cfg.get("density", "comfortable"))
        # fonts
        self._adjust_fonts()

    def _adjust_fonts(self):
        try:
            base = tkfont.nametofont("TkDefaultFont")
            textf = tkfont.nametofont("TkTextFont")
            headf = tkfont.nametofont("TkHeadingFont")
            scale = float(self.app.root.tk.call('tk', 'scaling'))
            def _adj(f, mul=1.0):
                try:
                    size = max(9, int(f.cget('size') * scale * mul))
                    f.configure(size=size)
                except Exception:
                    pass
            _adj(base, 1.0)
            _adj(textf, 1.0)
            _adj(headf, 1.1)
        except Exception:
            pass

    def apply_scaling(self, mode_or_factor):
        try:
            if isinstance(mode_or_factor, (int, float)):
                factor = float(mode_or_factor)
            else:
                factor = 1.0
                try:
                    shcore = ctypes.windll.shcore
                    shcore.SetProcessDpiAwareness(2)
                    user32 = ctypes.windll.user32
                    dc = user32.GetDC(0)
                    LOGPIXELSX = 88
                    dpi = ctypes.windll.gdi32.GetDeviceCaps(dc, LOGPIXELSX)
                    factor = max(0.75, dpi / 96.0)
                except Exception:
                    px_per_inch = self.app.root.winfo_fpixels('1i')
                    factor = max(0.75, float(px_per_inch) / 96.0)
            self.app.root.tk.call('tk', 'scaling', factor)
            self.app.scaling_factor = factor
        except Exception:
            self.app.scaling_factor = 1.0

    def apply_theme(self, theme_name: str):
        try:
            if tb is not None and self.style is not None:
                self.style.theme_use(theme_name)
            self.config.setdefault("ui", {})["theme_name"] = theme_name
            dark_set = {"darkly", "superhero", "cyborg", "solar"}
            self.config["ui"]["theme_mode"] = "dark" if theme_name in dark_set else "light"
            self.log(f"主题已切换为: {theme_name}", "INFO")
        except Exception as e:
            self.log(f"切换主题失败: {e}", "WARNING")

    def apply_density(self, density: str):
        sty = self.style or ttk.Style()
        if density == "compact":
            row_h = 24
            pad = 4
        else:
            row_h = 28
            pad = 6
        try:
            sty.configure("Treeview", rowheight=row_h)
            sty.configure("TButton", padding=(8, pad))
            if tb:
                sty.configure("Accent.TButton", padding=(10, pad))
                sty.configure("Secondary.TButton", padding=(8, pad))
        except Exception:
            pass
        self.config.setdefault("ui", {})["density"] = density

    def apply_to_widgets(self):
        try:
            if hasattr(self.app, "_apply_appearance_to_widgets"):
                self.app._apply_appearance_to_widgets()
        except Exception:
            pass 

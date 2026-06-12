#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MiniNotepad - 轻量级Windows文本处理工具
Licensed under the Apache License, Version 2.0
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, font
import os
import sys
import re

try:
    import chardet
    HAS_CHARDET = True
except ImportError:
    HAS_CHARDET = False

__version__ = "1.0.0"
APP_NAME = "MiniNotepad"


class LineNumberText(tk.Text):
    """带行号显示的文本编辑器组件"""

    def __init__(self, master=None, **kwargs):
        self.line_numbers = tk.Canvas(master, width=40, bg="#f0f0f0", highlightthickness=0)
        self.line_numbers.pack(side=tk.LEFT, fill=tk.Y)
        super().__init__(master, **kwargs)
        self.bind("<Key>", self._on_change)
        # 滚轮绑定，跨平台兼容：Windows用MouseWheel，Linux用Button-4/5
        try:
            self.bind("<MouseWheel>", self._on_scroll)
            self.line_numbers.bind("<MouseWheel>", self._sync_scroll_from_linenum)
        except tk.TclError:
            self.bind("<Button-4>", self._on_scroll)
            self.bind("<Button-5>", self._on_scroll)
            self.line_numbers.bind("<Button-4>", self._sync_scroll_from_linenum)
            self.line_numbers.bind("<Button-5>", self._sync_scroll_from_linenum)
        self.bind("<Configure>", self._on_change)
        self.bind("<Return>", self._on_return)
        self.bind("<Button-1>", self._on_click)

    def _on_return(self, event=None):
        self.after(1, self._update_line_numbers)

    def _on_change(self, event=None):
        self.after(1, self._update_line_numbers)

    def _on_scroll(self, event=None):
        self.after(1, self._update_line_numbers)

    def _on_click(self, event=None):
        self.after(1, self._update_line_numbers)

    def _sync_scroll_from_linenum(self, event=None):
        """从行号区域滚动时同步文本区域"""
        if hasattr(event, 'delta') and event.delta != 0:
            self.yview_scroll(-1 * (event.delta // 120), "units")
        elif hasattr(event, 'num'):
            if event.num == 4:
                self.yview_scroll(-3, "units")
            elif event.num == 5:
                self.yview_scroll(3, "units")
        self.after(1, self._update_line_numbers)

    def _update_line_numbers(self):
        try:
            self.line_numbers.delete("all")
            i = self.index("@0,0")
            while True:
                dline = self.dlineinfo(i)
                if dline is None:
                    break
                y = dline[1]
                line_num = str(i).split(".")[0]
                self.line_numbers.create_text(35, y, anchor=tk.NE, text=line_num,
                                              font=("Consolas", 9), fill="#666666")
                i = self.index(f"{i}+1line")
            self.line_numbers.config(scrollregion=self.line_numbers.bbox("all") or (0, 0, 0, 0))
        except tk.TclError:
            pass

    def yview(self, *args):
        try:
            super().yview(*args)
            self._update_line_numbers()
        except tk.TclError:
            pass


class BatchProcessDialog(tk.Toplevel):
    """多行批量处理对话框"""

    def __init__(self, parent, text_widget):
        super().__init__(parent)
        self.title("批量行处理")
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()
        self.text_widget = text_widget
        self.result = None

        self._create_widgets()
        self._center_window(parent)

    def _center_window(self, parent):
        self.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_x()
        py = parent.winfo_y()
        w = self.winfo_reqwidth()
        h = self.winfo_reqheight()
        # 确保最小尺寸，防止按钮被截断
        w = max(w, 440)
        h = max(h, 500)
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _create_widgets(self):
        # 操作类型
        frame_op = ttk.LabelFrame(self, text="操作类型", padding=8)
        frame_op.pack(fill=tk.X, padx=10, pady=5)

        self.op_var = tk.StringVar(value="add_prefix")
        ops = [("添加前缀", "add_prefix"), ("添加后缀", "add_suffix"),
               ("删除前缀", "remove_prefix"), ("删除后缀", "remove_suffix"),
               ("替换文本", "replace")]
        for i, (text, val) in enumerate(ops):
            ttk.Radiobutton(frame_op, text=text, variable=self.op_var,
                            value=val, command=self._on_op_change).grid(
                row=i // 3, column=i % 3, sticky=tk.W, padx=5, pady=2)

        # 输入内容
        frame_input = ttk.LabelFrame(self, text="输入内容", padding=8)
        frame_input.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(frame_input, text="处理文本:").grid(row=0, column=0, sticky=tk.W)
        self.entry_text = ttk.Entry(frame_input, width=40)
        self.entry_text.grid(row=0, column=1, sticky=tk.EW, padx=5)
        self.entry_text.focus_set()

        ttk.Label(frame_input, text="替换为:").grid(row=1, column=0, sticky=tk.W)
        self.entry_replace = ttk.Entry(frame_input, width=40)
        self.entry_replace.grid(row=1, column=1, sticky=tk.EW, padx=5)

        frame_input.columnconfigure(1, weight=1)
        self._on_op_change()

        # 行选择模式
        frame_sel = ttk.LabelFrame(self, text="行选择模式", padding=8)
        frame_sel.pack(fill=tk.X, padx=10, pady=5)

        self.sel_var = tk.StringVar(value="all")
        sels = [("所有行", "all"), ("奇数行(1,3,5...)", "odd"),
                ("偶数行(2,4,6...)", "even"), ("仅选中文本所在行", "selected"),
                ("自定义行范围(如:1-5,8,10)", "custom")]
        for i, (text, val) in enumerate(sels):
            ttk.Radiobutton(frame_sel, text=text, variable=self.sel_var,
                            value=val, command=self._on_sel_change).grid(
                row=i, column=0, sticky=tk.W, padx=5, pady=1)

        self.entry_custom = ttk.Entry(frame_sel, width=30, state=tk.DISABLED)
        self.entry_custom.grid(row=len(sels), column=0, sticky=tk.EW, padx=25, pady=2)

        # 按钮
        frame_btn = ttk.Frame(self, padding=8)
        frame_btn.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(frame_btn, text="确定", command=self._on_ok).pack(side=tk.RIGHT, padx=5)
        ttk.Button(frame_btn, text="取消", command=self.destroy).pack(side=tk.RIGHT, padx=5)

    def _on_op_change(self):
        op = self.op_var.get()
        if op == "replace":
            self.entry_replace.config(state=tk.NORMAL)
        else:
            self.entry_replace.config(state=tk.DISABLED)

    def _on_sel_change(self):
        if self.sel_var.get() == "custom":
            self.entry_custom.config(state=tk.NORMAL)
        else:
            self.entry_custom.config(state=tk.DISABLED)

    def _parse_custom_range(self, text, total_lines):
        lines = set()
        for part in text.split(","):
            part = part.strip()
            if "-" in part:
                try:
                    start, end = part.split("-", 1)
                    start = int(start.strip())
                    end = int(end.strip())
                    for i in range(max(1, start), min(total_lines + 1, end + 1)):
                        lines.add(i)
                except ValueError:
                    continue
            else:
                try:
                    n = int(part)
                    if 1 <= n <= total_lines:
                        lines.add(n)
                except ValueError:
                    continue
        return sorted(lines)

    def _on_ok(self):
        op = self.op_var.get()
        text = self.entry_text.get()
        replace_text = self.entry_replace.get()

        if op not in ("remove_prefix", "remove_suffix") and not text:
            messagebox.showwarning("提示", "请输入处理文本", parent=self)
            return

        content = self.text_widget.get("1.0", tk.END + "-1c")
        all_lines = content.split("\n")
        total_lines = len(all_lines)

        sel_mode = self.sel_var.get()
        if sel_mode == "all":
            target_lines = list(range(1, total_lines + 1))
        elif sel_mode == "odd":
            target_lines = list(range(1, total_lines + 1, 2))
        elif sel_mode == "even":
            target_lines = list(range(2, total_lines + 1, 2))
        elif sel_mode == "selected":
            try:
                sel_start = self.text_widget.index("sel.first")
                sel_end = self.text_widget.index("sel.last")
                start_line = int(sel_start.split(".")[0])
                end_line = int(sel_end.split(".")[0])
                target_lines = list(range(start_line, end_line + 1))
            except tk.TclError:
                target_lines = list(range(1, total_lines + 1))
        elif sel_mode == "custom":
            custom_text = self.entry_custom.get()
            if not custom_text:
                messagebox.showwarning("提示", "请输入自定义行范围", parent=self)
                return
            target_lines = self._parse_custom_range(custom_text, total_lines)
            if not target_lines:
                messagebox.showwarning("提示", "无效的行范围", parent=self)
                return
        else:
            target_lines = list(range(1, total_lines + 1))

        target_set = set(target_lines)
        new_lines = []
        for i, line in enumerate(all_lines):
            line_num = i + 1
            if line_num in target_set:
                if op == "add_prefix":
                    new_lines.append(text + line)
                elif op == "add_suffix":
                    new_lines.append(line + text)
                elif op == "remove_prefix":
                    if line.startswith(text):
                        new_lines.append(line[len(text):])
                    else:
                        new_lines.append(line)
                elif op == "remove_suffix":
                    if line.endswith(text):
                        new_lines.append(line[:-len(text)])
                    else:
                        new_lines.append(line)
                elif op == "replace":
                    new_lines.append(line.replace(text, replace_text))
            else:
                new_lines.append(line)

        self.result = "\n".join(new_lines)
        self.destroy()


class FindDialog(tk.Toplevel):
    """查找对话框"""

    def __init__(self, parent, text_widget, replace_mode=False):
        super().__init__(parent)
        self.title("替换" if replace_mode else "查找")
        self.geometry("400x220" if replace_mode else "400x160")
        self.resizable(False, False)
        self.transient(parent)
        self.text_widget = text_widget
        self.replace_mode = replace_mode
        self.last_search_pos = None

        self._create_widgets()

    def _create_widgets(self):
        frame = ttk.Frame(self, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="查找内容:").grid(row=0, column=0, sticky=tk.W, pady=3)
        self.entry_find = ttk.Entry(frame, width=35)
        self.entry_find.grid(row=0, column=1, columnspan=2, sticky=tk.EW, pady=3, padx=5)
        self.entry_find.focus_set()

        if self.replace_mode:
            ttk.Label(frame, text="替换为:").grid(row=1, column=0, sticky=tk.W, pady=3)
            self.entry_replace = ttk.Entry(frame, width=35)
            self.entry_replace.grid(row=1, column=1, columnspan=2, sticky=tk.EW, pady=3, padx=5)

        self.case_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame, text="区分大小写", variable=self.case_var).grid(
            row=2, column=0, columnspan=3, sticky=tk.W, pady=3)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=3, column=0, columnspan=3, pady=10)

        ttk.Button(btn_frame, text="查找下一个", command=self._find_next).pack(side=tk.LEFT, padx=3)
        if self.replace_mode:
            ttk.Button(btn_frame, text="替换", command=self._replace).pack(side=tk.LEFT, padx=3)
            ttk.Button(btn_frame, text="全部替换", command=self._replace_all).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text="取消", command=self.destroy).pack(side=tk.LEFT, padx=3)

        frame.columnconfigure(1, weight=1)

        self.entry_find.bind("<Return>", lambda e: self._find_next())

    def _find_next(self):
        search = self.entry_find.get()
        if not search:
            return
        # 保存搜索状态到主窗口
        if hasattr(self.master, 'last_find_text'):
            self.master.last_find_text = search
            self.master.last_find_case = self.case_var.get()
        nocase = not self.case_var.get()
        start = self.last_search_pos or "1.0"
        if self.last_search_pos:
            start = f"{self.last_search_pos}+1c"
        pos = self.text_widget.search(search, start, nocase=nocase)
        if pos:
            end = f"{pos}+{len(search)}c"
            self.text_widget.tag_remove("sel", "1.0", tk.END)
            self.text_widget.tag_add("sel", pos, end)
            self.text_widget.mark_set(tk.INSERT, pos)
            self.text_widget.see(pos)
            self.last_search_pos = pos
        else:
            # 从头再找
            pos = self.text_widget.search(search, "1.0", nocase=nocase)
            if pos and pos != self.last_search_pos:
                end = f"{pos}+{len(search)}c"
                self.text_widget.tag_remove("sel", "1.0", tk.END)
                self.text_widget.tag_add("sel", pos, end)
                self.text_widget.mark_set(tk.INSERT, pos)
                self.text_widget.see(pos)
                self.last_search_pos = pos
            else:
                self.last_search_pos = None
                messagebox.showinfo("查找", "找不到指定的文本", parent=self)

    def _replace(self):
        search = self.entry_find.get()
        replace = self.entry_replace.get()
        if not search:
            return
        try:
            sel_start = self.text_widget.index("sel.first")
            sel_end = self.text_widget.index("sel.last")
            selected = self.text_widget.get(sel_start, sel_end)
            nocase = not self.case_var.get()
            if nocase:
                if selected.lower() == search.lower():
                    self.text_widget.delete(sel_start, sel_end)
                    self.text_widget.insert(sel_start, replace)
            else:
                if selected == search:
                    self.text_widget.delete(sel_start, sel_end)
                    self.text_widget.insert(sel_start, replace)
        except tk.TclError:
            pass
        self._find_next()

    def _replace_all(self):
        search = self.entry_find.get()
        replace = self.entry_replace.get()
        if not search:
            return
        nocase = not self.case_var.get()
        content = self.text_widget.get("1.0", tk.END)
        if nocase:
            count = len(re.findall(re.escape(search), content, re.IGNORECASE))
            new_content = re.sub(re.escape(search), replace.replace("\\", "\\\\"), content, flags=re.IGNORECASE)
        else:
            count = content.count(search)
            new_content = content.replace(search, replace)
        self.text_widget.delete("1.0", tk.END)
        self.text_widget.insert("1.0", new_content)
        messagebox.showinfo("替换", f"共替换了 {count} 处", parent=self)


class GotoLineDialog(tk.Toplevel):
    """跳转到行对话框"""

    def __init__(self, parent, text_widget):
        super().__init__(parent)
        self.title("跳转到行")
        self.geometry("280x120")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.text_widget = text_widget

        frame = ttk.Frame(self, padding=15)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="行号:").grid(row=0, column=0, padx=5)
        self.entry = ttk.Entry(frame, width=15)
        self.entry.grid(row=0, column=1, padx=5)
        self.entry.focus_set()

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=1, column=0, columnspan=2, pady=10)
        ttk.Button(btn_frame, text="跳转", command=self._goto).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消", command=self.destroy).pack(side=tk.LEFT, padx=5)

        self.entry.bind("<Return>", lambda e: self._goto())

    def _goto(self):
        try:
            line = int(self.entry.get())
            total = int(self.text_widget.index("end-1c").split(".")[0])
            if 1 <= line <= total:
                self.text_widget.mark_set(tk.INSERT, f"{line}.0")
                self.text_widget.see(f"{line}.0")
                self.text_widget.focus_set()
                self.destroy()
            else:
                messagebox.showwarning("提示", f"行号超出范围 (1-{total})", parent=self)
        except ValueError:
            messagebox.showwarning("提示", "请输入有效的行号", parent=self)


class FontDialog(tk.Toplevel):
    """字体选择对话框"""

    def __init__(self, parent, current_font):
        super().__init__(parent)
        self.title("字体")
        self.geometry("380x300")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.result = None

        frame = ttk.Frame(self, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        # 字体名称
        ttk.Label(frame, text="字体:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.font_var = tk.StringVar(value=current_font["family"])
        font_names = sorted(tk.font.families())
        self.font_combo = ttk.Combobox(frame, textvariable=self.font_var,
                                        values=font_names, width=25)
        self.font_combo.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=5)

        # 字体大小
        ttk.Label(frame, text="大小:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.size_var = tk.IntVar(value=current_font["size"])
        sizes = list(range(6, 37))
        self.size_combo = ttk.Combobox(frame, textvariable=self.size_var,
                                        values=sizes, width=10)
        self.size_combo.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)

        # 样式
        self.bold_var = tk.BooleanVar(value=current_font.get("weight") == "bold")
        self.italic_var = tk.BooleanVar(value=current_font.get("slant") == "italic")
        ttk.Checkbutton(frame, text="粗体", variable=self.bold_var).grid(
            row=2, column=0, columnspan=2, sticky=tk.W, pady=3)
        ttk.Checkbutton(frame, text="斜体", variable=self.italic_var).grid(
            row=3, column=0, columnspan=2, sticky=tk.W, pady=3)

        # 预览
        ttk.Label(frame, text="预览:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.preview = tk.Label(frame, text="AaBbCc 文本预览 123",
                                 font=(current_font["family"], current_font["size"]))
        self.preview.grid(row=5, column=0, columnspan=2, sticky=tk.EW, pady=5)

        # 按钮
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=6, column=0, columnspan=2, pady=10)
        ttk.Button(btn_frame, text="确定", command=self._on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消", command=self.destroy).pack(side=tk.LEFT, padx=5)

        self.font_var.trace_add("write", self._update_preview)
        self.size_var.trace_add("write", self._update_preview)
        self.bold_var.trace_add("write", self._update_preview)
        self.italic_var.trace_add("write", self._update_preview)

    def _update_preview(self, *args):
        try:
            family = self.font_var.get()
            size = self.size_var.get()
            weight = "bold" if self.bold_var.get() else "normal"
            slant = "italic" if self.italic_var.get() else "roman"
            self.preview.config(font=(family, size, weight, slant))
        except (tk.TclError, ValueError):
            pass

    def _on_ok(self):
        self.result = {
            "family": self.font_var.get(),
            "size": self.size_var.get(),
            "weight": "bold" if self.bold_var.get() else "normal",
            "slant": "italic" if self.italic_var.get() else "roman"
        }
        self.destroy()


class MiniNotepad(tk.Tk):
    """MiniNotepad 主应用"""

    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} - 无标题")
        self.geometry("900x600")

        self.current_file = None
        self.modified = False
        self.encoding = "utf-8"
        self.word_wrap = True
        self.show_status = True
        self.show_line_numbers = True
        self.current_font = {"family": "Consolas", "size": 11, "weight": "normal", "slant": "roman"}
        self.base_font_size = 11
        self.zoom_level = 0
        self.find_dialog = None
        self.last_find_text = ""
        self.last_find_case = False

        self._create_menu()
        self._create_toolbar()
        self._create_text_area()
        self._create_status_bar()
        self._bind_shortcuts()
        self._update_title()

        # 处理命令行参数（打开文件）
        # IFEO模式下Windows会传原始notepad.exe路径，需要过滤
        for arg in sys.argv[1:]:
            if os.path.isfile(arg) and not arg.lower().endswith("notepad.exe"):
                self._load_file(arg)
                break

        # 延迟初始化状态栏，避免控件未渲染时TclError
        self.after(100, self._update_status)

    def _create_menu(self):
        menubar = tk.Menu(self)

        # 文件菜单
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="新建", command=self._new_file, accelerator="Ctrl+N")
        file_menu.add_command(label="打开...", command=self._open_file, accelerator="Ctrl+O")
        file_menu.add_separator()
        file_menu.add_command(label="保存", command=self._save_file, accelerator="Ctrl+S")
        file_menu.add_command(label="另存为...", command=self._save_as, accelerator="Ctrl+Shift+S")
        file_menu.add_separator()
        enc_menu = tk.Menu(file_menu, tearoff=0)
        for enc in ["utf-8", "utf-8-sig", "gbk", "gb2312", "gb18030", "big5", "ascii", "latin-1"]:
            enc_menu.add_command(label=enc.upper(),
                                command=lambda e=enc: self._reopen_with_encoding(e))
        file_menu.add_cascade(label="编码重新打开", menu=enc_menu)
        file_menu.add_separator()
        file_menu.add_command(label="页面设置...", command=self._page_setup)
        file_menu.add_command(label="打印...", command=self._print, accelerator="Ctrl+P")
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self._quit, accelerator="Alt+F4")
        menubar.add_cascade(label="文件", menu=file_menu)

        # 编辑菜单
        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="撤销", command=self._undo, accelerator="Ctrl+Z")
        edit_menu.add_command(label="重做", command=self._redo, accelerator="Ctrl+Y")
        edit_menu.add_separator()
        edit_menu.add_command(label="剪切", command=self._cut, accelerator="Ctrl+X")
        edit_menu.add_command(label="复制", command=self._copy, accelerator="Ctrl+C")
        edit_menu.add_command(label="粘贴", command=self._paste, accelerator="Ctrl+V")
        edit_menu.add_command(label="删除", command=self._delete, accelerator="Del")
        edit_menu.add_separator()
        edit_menu.add_command(label="查找...", command=self._find, accelerator="Ctrl+F")
        edit_menu.add_command(label="查找下一个", command=self._find_next, accelerator="F3")
        edit_menu.add_command(label="替换...", command=self._replace, accelerator="Ctrl+H")
        edit_menu.add_command(label="跳转到行...", command=self._goto_line, accelerator="Ctrl+G")
        edit_menu.add_separator()
        edit_menu.add_command(label="全选", command=self._select_all, accelerator="Ctrl+A")
        edit_menu.add_command(label="插入时间/日期", command=self._insert_datetime, accelerator="F5")
        menubar.add_cascade(label="编辑", menu=edit_menu)

        # 格式菜单
        format_menu = tk.Menu(menubar, tearoff=0)
        self.wrap_var = tk.BooleanVar(value=self.word_wrap)
        format_menu.add_checkbutton(label="自动换行", variable=self.wrap_var,
                                     command=self._toggle_wrap)
        format_menu.add_command(label="字体...", command=self._change_font)
        menubar.add_cascade(label="格式", menu=format_menu)

        # 批量处理菜单
        batch_menu = tk.Menu(menubar, tearoff=0)
        batch_menu.add_command(label="批量行处理...", command=self._batch_process,
                               accelerator="Ctrl+B")
        batch_menu.add_separator()
        batch_menu.add_command(label="行首添加文本...", command=lambda: self._quick_batch("add_prefix"))
        batch_menu.add_command(label="行尾添加文本...", command=lambda: self._quick_batch("add_suffix"))
        batch_menu.add_command(label="删除行首文本...", command=lambda: self._quick_batch("remove_prefix"))
        batch_menu.add_command(label="删除行尾文本...", command=lambda: self._quick_batch("remove_suffix"))
        batch_menu.add_separator()
        batch_menu.add_command(label="删除空行", command=self._remove_blank_lines)
        batch_menu.add_command(label="删除重复行", command=self._remove_duplicate_lines)
        batch_menu.add_command(label="行排序(升序)", command=lambda: self._sort_lines(True))
        batch_menu.add_command(label="行排序(降序)", command=lambda: self._sort_lines(False))
        batch_menu.add_command(label="行倒序", command=self._reverse_lines)
        batch_menu.add_command(label="行编号(添加行号)", command=self._add_line_numbers)
        batch_menu.add_command(label="去除行号", command=self._remove_line_numbers)
        batch_menu.add_separator()
        batch_menu.add_command(label="Trim(去除首尾空格)", command=self._trim_lines)
        batch_menu.add_command(label="大写转换", command=lambda: self._case_convert("upper"))
        batch_menu.add_command(label="小写转换", command=lambda: self._case_convert("lower"))
        menubar.add_cascade(label="批量处理", menu=batch_menu)

        # 查看菜单
        view_menu = tk.Menu(menubar, tearoff=0)
        self.status_var = tk.BooleanVar(value=self.show_status)
        view_menu.add_checkbutton(label="状态栏", variable=self.status_var,
                                   command=self._toggle_status)
        self.linenum_var = tk.BooleanVar(value=self.show_line_numbers)
        view_menu.add_checkbutton(label="行号", variable=self.linenum_var,
                                   command=self._toggle_line_numbers)
        view_menu.add_separator()
        view_menu.add_command(label="放大", command=lambda: self._zoom(1), accelerator="Ctrl++")
        view_menu.add_command(label="缩小", command=lambda: self._zoom(-1), accelerator="Ctrl+-")
        view_menu.add_command(label="恢复默认缩放", command=lambda: self._zoom(0), accelerator="Ctrl+0")
        menubar.add_cascade(label="查看", menu=view_menu)

        # 帮助菜单
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="关于 MiniNotepad", command=self._about)
        help_menu.add_command(label="设为默认文本编辑器", command=self._set_default_editor)
        menubar.add_cascade(label="帮助", menu=help_menu)

        self.config(menu=menubar)

    def _create_toolbar(self):
        toolbar = ttk.Frame(self, relief=tk.FLAT)
        toolbar.pack(fill=tk.X, side=tk.TOP)

        ttk.Button(toolbar, text="新建", width=5, command=self._new_file).pack(side=tk.LEFT, padx=1)
        ttk.Button(toolbar, text="打开", width=5, command=self._open_file).pack(side=tk.LEFT, padx=1)
        ttk.Button(toolbar, text="保存", width=5, command=self._save_file).pack(side=tk.LEFT, padx=1)
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=4, pady=2)
        ttk.Button(toolbar, text="撤销", width=5, command=self._undo).pack(side=tk.LEFT, padx=1)
        ttk.Button(toolbar, text="重做", width=5, command=self._redo).pack(side=tk.LEFT, padx=1)
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=4, pady=2)
        ttk.Button(toolbar, text="批量", width=5, command=self._batch_process).pack(side=tk.LEFT, padx=1)

    def _create_text_area(self):
        self.text_frame = ttk.Frame(self)
        self.text_frame.pack(fill=tk.BOTH, expand=True)

        if self.show_line_numbers:
            self.text = LineNumberText(self.text_frame, wrap=tk.WORD, undo=True,
                                        font=(self.current_font["family"],
                                              self.current_font["size"]))
        else:
            self.text = tk.Text(self.text_frame, wrap=tk.WORD, undo=True,
                                 font=(self.current_font["family"],
                                       self.current_font["size"]))

        self.text.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # 右键菜单
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="撤销", command=self._undo)
        self.context_menu.add_command(label="重做", command=self._redo)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="剪切", command=self._cut)
        self.context_menu.add_command(label="复制", command=self._copy)
        self.context_menu.add_command(label="粘贴", command=self._paste)
        self.context_menu.add_command(label="删除", command=self._delete)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="全选", command=self._select_all)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="批量行处理...", command=self._batch_process)

        self.text.bind("<Button-3>", self._show_context_menu)
        self.text.bind("<<Modified>>", self._on_text_modified)
        self.text.bind("<KeyRelease>", self._update_status)
        self.text.bind("<ButtonRelease>", self._update_status)

    def _create_status_bar(self):
        self.status_bar = ttk.Frame(self, relief=tk.SUNKEN)
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        self.status_pos = ttk.Label(self.status_bar, text="行 1, 列 1", width=20, anchor=tk.W)
        self.status_pos.pack(side=tk.LEFT, padx=5)

        self.status_lines = ttk.Label(self.status_bar, text="共 1 行", width=15, anchor=tk.W)
        self.status_lines.pack(side=tk.LEFT, padx=5)

        self.status_chars = ttk.Label(self.status_bar, text="0 个字符", width=15, anchor=tk.W)
        self.status_chars.pack(side=tk.LEFT, padx=5)

        self.status_enc = ttk.Label(self.status_bar, text="UTF-8", width=12, anchor=tk.E)
        self.status_enc.pack(side=tk.RIGHT, padx=5)

        self.status_zoom = ttk.Label(self.status_bar, text="100%", width=8, anchor=tk.E)
        self.status_zoom.pack(side=tk.RIGHT, padx=5)

    def _bind_shortcuts(self):
        self.bind("<Control-n>", lambda e: self._new_file())
        self.bind("<Control-o>", lambda e: self._open_file())
        self.bind("<Control-s>", lambda e: self._save_file())
        self.bind("<Control-Shift-S>", lambda e: self._save_as())
        self.bind("<Control-f>", lambda e: self._find())
        self.bind("<F3>", lambda e: self._find_next())
        self.bind("<Control-h>", lambda e: self._replace())
        self.bind("<Control-g>", lambda e: self._goto_line())
        self.bind("<Control-b>", lambda e: self._batch_process())
        self.bind("<Control-a>", lambda e: self._select_all())
        self.bind("<Control-p>", lambda e: self._print())
        self.bind("<F5>", lambda e: self._insert_datetime())
        self.bind("<Control-plus>", lambda e: self._zoom(1))
        self.bind("<Control-equal>", lambda e: self._zoom(1))
        self.bind("<Control-minus>", lambda e: self._zoom(-1))
        self.bind("<Control-0>", lambda e: self._zoom(0))
        # Ctrl+滚轮缩放，跨平台兼容
        try:
            self.bind("<Control-MouseWheel>", lambda e: self._zoom(1 if e.delta > 0 else -1))
        except tk.TclError:
            self.bind("<Control-Button-4>", lambda e: self._zoom(1))
            self.bind("<Control-Button-5>", lambda e: self._zoom(-1))

    # ==================== 文件操作 ====================

    def _new_file(self):
        if self._check_save():
            self.text.delete("1.0", tk.END)
            self.current_file = None
            self.encoding = "utf-8"
            self.modified = False
            self._update_title()
            self._update_status()

    def _open_file(self):
        if not self._check_save():
            return
        filepath = filedialog.askopenfilename(
            title="打开",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*"),
                       ("日志文件", "*.log"), ("INI文件", "*.ini"),
                       ("CSV文件", "*.csv"), ("Markdown", "*.md"),
                       ("JSON文件", "*.json"), ("XML文件", "*.xml"),
                       ("HTML文件", "*.html;*.htm"), ("CSS文件", "*.css"),
                       ("JS文件", "*.js"), ("Python", "*.py"),
                       ("C/C++", "*.c;*.cpp;*.h"), ("Java", "*.java")])
        if filepath:
            self._load_file(filepath)

    def _detect_encoding(self, raw):
        """轻量级编码检测，优先使用chardet，回退到BOM+常见编码尝试"""
        # BOM检测
        if raw.startswith(b'\xef\xbb\xbf'):
            return "utf-8-sig"
        if raw.startswith(b'\xff\xfe'):
            return "utf-16-le"
        if raw.startswith(b'\xfe\xff'):
            return "utf-16-be"
        # chardet检测
        if HAS_CHARDET:
            detected = chardet.detect(raw)
            enc = detected.get("encoding", "utf-8") or "utf-8"
            return enc
        # 回退：依次尝试常见编码
        for enc in ["utf-8", "gbk", "gb18030", "big5", "latin-1"]:
            try:
                raw.decode(enc)
                return enc
            except (UnicodeDecodeError, LookupError):
                continue
        return "utf-8"

    def _load_file(self, filepath):
        try:
            with open(filepath, "rb") as f:
                raw = f.read()
            enc = self._detect_encoding(raw)
            try:
                content = raw.decode(enc)
            except (UnicodeDecodeError, LookupError):
                enc = "utf-8"
                content = raw.decode(enc, errors="replace")
            self.encoding = enc
            self.text.delete("1.0", tk.END)
            self.text.insert("1.0", content)
            self.current_file = filepath
            self.modified = False
            self._update_title()
            self._update_status()
        except Exception as e:
            messagebox.showerror("错误", f"无法打开文件:\n{e}")

    def _save_file(self):
        if self.current_file:
            self._write_file(self.current_file)
        else:
            self._save_as()

    def _save_as(self):
        filepath = filedialog.asksaveasfilename(
            title="另存为",
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")])
        if filepath:
            self._write_file(filepath)

    def _write_file(self, filepath):
        try:
            content = self.text.get("1.0", tk.END + "-1c")
            with open(filepath, "w", encoding=self.encoding, newline="") as f:
                f.write(content)
            self.current_file = filepath
            self.modified = False
            self._update_title()
        except Exception as e:
            messagebox.showerror("错误", f"无法保存文件:\n{e}")

    def _reopen_with_encoding(self, enc):
        if self.current_file:
            self.encoding = enc
            self._load_file(self.current_file)

    def _check_save(self):
        if self.modified:
            result = messagebox.askyesnocancel(
                APP_NAME, "文件已修改，是否保存？")
            if result is True:
                self._save_file()
                return True
            elif result is False:
                return True
            else:
                return False
        return True

    # ==================== 编辑操作 ====================

    def _undo(self):
        try:
            self.text.edit_undo()
        except tk.TclError:
            pass

    def _redo(self):
        try:
            self.text.edit_redo()
        except tk.TclError:
            pass

    def _cut(self):
        try:
            self.text.event_generate("<<Cut>>")
        except tk.TclError:
            pass

    def _copy(self):
        try:
            self.text.event_generate("<<Copy>>")
        except tk.TclError:
            pass

    def _paste(self):
        try:
            self.text.event_generate("<<Paste>>")
        except tk.TclError:
            pass

    def _delete(self):
        try:
            self.text.delete("sel.first", "sel.last")
        except tk.TclError:
            pass

    def _select_all(self):
        self.text.tag_add("sel", "1.0", tk.END)
        self.text.mark_set(tk.INSERT, "1.0")

    def _insert_datetime(self):
        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.text.insert(tk.INSERT, now)

    def _find(self):
        if self.find_dialog and self.find_dialog.winfo_exists():
            self.find_dialog.lift()
            self.find_dialog.focus_set()
            return
        self.find_dialog = FindDialog(self, self.text, replace_mode=False)

    def _find_next(self):
        if self.last_find_text:
            nocase = not self.last_find_case
            start = self.text.index(tk.INSERT) + "+1c"
            pos = self.text.search(self.last_find_text, start, nocase=nocase)
            if not pos:
                pos = self.text.search(self.last_find_text, "1.0", nocase=nocase)
            if pos:
                end = f"{pos}+{len(self.last_find_text)}c"
                self.text.tag_remove("sel", "1.0", tk.END)
                self.text.tag_add("sel", pos, end)
                self.text.mark_set(tk.INSERT, pos)
                self.text.see(pos)
            else:
                messagebox.showinfo("查找", "找不到指定的文本")
        else:
            self._find()

    def _replace(self):
        FindDialog(self, self.text, replace_mode=True)

    def _goto_line(self):
        GotoLineDialog(self, self.text)

    # ==================== 格式操作 ====================

    def _toggle_wrap(self):
        self.word_wrap = self.wrap_var.get()
        self.text.config(wrap=tk.WORD if self.word_wrap else tk.NONE)

    def _change_font(self):
        dlg = FontDialog(self, self.current_font)
        self.wait_window(dlg)
        if dlg.result:
            self.current_font = dlg.result
            self._apply_font()

    def _apply_font(self):
        f = (self.current_font["family"],
             self.current_font["size"],
             self.current_font["weight"],
             self.current_font["slant"])
        self.text.config(font=f)

    # ==================== 批量处理操作 ====================

    def _batch_process(self):
        dlg = BatchProcessDialog(self, self.text)
        self.wait_window(dlg)
        if dlg.result is not None:
            self.text.delete("1.0", tk.END)
            self.text.insert("1.0", dlg.result)
            self._update_status()

    def _quick_batch(self, op):
        dlg = BatchProcessDialog(self, self.text)
        dlg.op_var.set(op)
        self.wait_window(dlg)
        if dlg.result is not None:
            self.text.delete("1.0", tk.END)
            self.text.insert("1.0", dlg.result)
            self._update_status()

    def _remove_blank_lines(self):
        content = self.text.get("1.0", tk.END)
        lines = content.split("\n")
        new_lines = [l for l in lines if l.strip()]
        self.text.delete("1.0", tk.END)
        self.text.insert("1.0", "\n".join(new_lines))
        self._update_status()

    def _remove_duplicate_lines(self):
        content = self.text.get("1.0", tk.END)
        lines = content.split("\n")
        seen = set()
        new_lines = []
        for l in lines:
            if l not in seen:
                seen.add(l)
                new_lines.append(l)
        self.text.delete("1.0", tk.END)
        self.text.insert("1.0", "\n".join(new_lines))
        self._update_status()

    def _sort_lines(self, ascending):
        content = self.text.get("1.0", tk.END)
        lines = content.split("\n")
        lines.sort(reverse=not ascending)
        self.text.delete("1.0", tk.END)
        self.text.insert("1.0", "\n".join(lines))
        self._update_status()

    def _reverse_lines(self):
        content = self.text.get("1.0", tk.END)
        lines = content.split("\n")
        lines.reverse()
        self.text.delete("1.0", tk.END)
        self.text.insert("1.0", "\n".join(lines))
        self._update_status()

    def _add_line_numbers(self):
        content = self.text.get("1.0", tk.END)
        lines = content.split("\n")
        max_width = len(str(len(lines)))
        new_lines = [f"{i+1:>{max_width}}. {l}" for i, l in enumerate(lines)]
        self.text.delete("1.0", tk.END)
        self.text.insert("1.0", "\n".join(new_lines))
        self._update_status()

    def _remove_line_numbers(self):
        content = self.text.get("1.0", tk.END)
        lines = content.split("\n")
        new_lines = [re.sub(r"^\s*\d+[\.\s]+", "", l) for l in lines]
        self.text.delete("1.0", tk.END)
        self.text.insert("1.0", "\n".join(new_lines))
        self._update_status()

    def _trim_lines(self):
        content = self.text.get("1.0", tk.END)
        lines = content.split("\n")
        new_lines = [l.strip() for l in lines]
        self.text.delete("1.0", tk.END)
        self.text.insert("1.0", "\n".join(new_lines))
        self._update_status()

    def _case_convert(self, mode):
        try:
            start = self.text.index("sel.first")
            end = self.text.index("sel.last")
            selected = self.text.get(start, end)
            if mode == "upper":
                converted = selected.upper()
            else:
                converted = selected.lower()
            self.text.delete(start, end)
            self.text.insert(start, converted)
        except tk.TclError:
            content = self.text.get("1.0", tk.END)
            if mode == "upper":
                self.text.delete("1.0", tk.END)
                self.text.insert("1.0", content.upper())
            else:
                self.text.delete("1.0", tk.END)
                self.text.insert("1.0", content.lower())
        self._update_status()

    # ==================== 查看操作 ====================

    def _toggle_status(self):
        self.show_status = self.status_var.get()
        if self.show_status:
            self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        else:
            self.status_bar.pack_forget()

    def _toggle_line_numbers(self):
        self.show_line_numbers = self.linenum_var.get()
        # 保存当前内容
        content = self.text.get("1.0", tk.END + "-1c")
        cur_pos = self.text.index(tk.INSERT)

        # 销毁旧组件
        if hasattr(self.text, 'line_numbers'):
            self.text.line_numbers.destroy()
        self.text.destroy()

        # 重建
        if self.show_line_numbers:
            self.text = LineNumberText(self.text_frame, wrap=tk.WORD if self.word_wrap else tk.NONE,
                                        undo=True,
                                        font=(self.current_font["family"],
                                              self.current_font["size"]))
        else:
            self.text = tk.Text(self.text_frame, wrap=tk.WORD if self.word_wrap else tk.NONE,
                                 undo=True,
                                 font=(self.current_font["family"],
                                       self.current_font["size"]))
        self.text.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.text.insert("1.0", content)
        self.text.mark_set(tk.INSERT, cur_pos)

        # 重新绑定事件
        self.text.bind("<Button-3>", self._show_context_menu)
        self.text.bind("<<Modified>>", self._on_text_modified)
        self.text.bind("<KeyRelease>", self._update_status)
        self.text.bind("<ButtonRelease>", self._update_status)

    def _zoom(self, direction):
        if direction == 0:
            self.zoom_level = 0
        else:
            self.zoom_level += direction
        new_size = max(6, min(36, self.base_font_size + self.zoom_level))
        self.current_font["size"] = new_size
        self._apply_font()
        zoom_pct = int(100 * new_size / self.base_font_size)
        self.status_zoom.config(text=f"{zoom_pct}%")

    # ==================== 打印操作 ====================

    def _page_setup(self):
        messagebox.showinfo("页面设置", "页面设置功能需要连接打印机使用")

    def _print(self):
        try:
            import subprocess
            if self.current_file:
                subprocess.Popen(["notepad", "/p", self.current_file])
            else:
                # 临时保存后打印
                import tempfile
                with tempfile.NamedTemporaryFile(mode="w", suffix=".txt",
                                                  delete=False, encoding=self.encoding) as tmp:
                    tmp.write(self.text.get("1.0", tk.END + "-1c"))
                    tmp_path = tmp.name
                subprocess.Popen(["notepad", "/p", tmp_path])
            messagebox.showinfo("打印", "已发送到打印队列")
        except Exception as e:
            messagebox.showerror("打印", f"打印失败:\n{e}")

    # ==================== 默认编辑器 ====================

    def _set_default_editor(self):
        if sys.platform != "win32":
            messagebox.showinfo("提示", "此功能仅支持Windows系统")
            return

        exe_path = os.path.abspath(sys.argv[0])
        if not exe_path.lower().endswith(".exe"):
            messagebox.showwarning("提示",
                                    "请先打包为EXE文件后再设置默认编辑器。\n"
                                    "使用 build.bat 进行打包。")
            return

        try:
            import winreg
            # 设置 .txt 文件关联
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                                    r"Software\Classes\.txt")
            winreg.SetValue(key, None, winreg.REG_SZ, "MiniNotepad.txt")
            key.Close()

            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                                    r"Software\Classes\MiniNotepad.txt")
            winreg.SetValue(key, None, winreg.REG_SZ, "文本文件")
            key.Close()

            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                                    r"Software\Classes\MiniNotepad.txt\shell\open\command")
            winreg.SetValue(key, None, winreg.REG_SZ, f'"{exe_path}" "%1"')
            key.Close()

            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                                    r"Software\Classes\MiniNotepad.txt\DefaultIcon")
            winreg.SetValue(key, None, winreg.REG_SZ, f'"{exe_path}",0')
            key.Close()

            # 替换Notepad
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                                    r"Software\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\notepad.exe")
            winreg.SetValueEx(key, "Debugger", 0, winreg.REG_SZ, f'"{exe_path}"')
            key.Close()

            messagebox.showinfo("成功",
                                "已成功设置为默认文本编辑器！\n"
                                "双击.txt文件将使用MiniNotepad打开。")
        except Exception as e:
            messagebox.showerror("错误", f"设置默认编辑器失败:\n{e}\n\n请以管理员身份运行。")

    # ==================== 辅助方法 ====================

    def _show_context_menu(self, event):
        self.context_menu.post(event.x_root, event.y_root)

    def _on_text_modified(self, event=None):
        if not hasattr(self, 'text'):
            return
        try:
            if self.text.edit_modified():
                self.modified = True
                self._update_title()
                self.text.edit_modified(False)
        except tk.TclError:
            pass

    def _update_title(self):
        if not hasattr(self, 'text'):
            return
        if self.current_file:
            name = os.path.basename(self.current_file)
        else:
            name = "无标题"
        title = f"{name}{' *' if self.modified else ''} - {APP_NAME}"
        self.title(title)

    def _update_status(self, event=None):
        if not hasattr(self, 'text') or not hasattr(self, 'status_pos'):
            return
        try:
            cur = self.text.index(tk.INSERT)
            line, col = cur.split(".")
            self.status_pos.config(text=f"行 {line}, 列 {int(col)+1}")
            total = self.text.index("end-1c").split(".")[0]
            self.status_lines.config(text=f"共 {total} 行")
            content = self.text.get("1.0", tk.END + "-1c")
            self.status_chars.config(text=f"{len(content)} 个字符")
            self.status_enc.config(text=self.encoding.upper())
        except tk.TclError:
            pass

    def _about(self):
        messagebox.showinfo(
            f"关于 {APP_NAME}",
            f"{APP_NAME} v{__version__}\n\n"
            "轻量级Windows文本处理工具\n"
            "支持批量行处理、多行前缀/后缀添加\n\n"
            "Licensed under the Apache License, Version 2.0\n"
            "https://www.apache.org/licenses/LICENSE-2.0")

    def _quit(self):
        if self._check_save():
            self.destroy()


def main():
    # 全局异常捕获，写入桌面日志文件
    import traceback
    import os as _os

    log_path = _os.path.join(_os.path.expanduser("~"), "Desktop", "mininotepad_crash.log")

    def _log_crash(exc_type, exc_val, exc_tb):
        tb_text = "".join(traceback.format_exception(exc_type, exc_val, exc_tb))
        try:
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(tb_text)
        except Exception:
            pass
        try:
            from tkinter import messagebox
            messagebox.showerror("MiniNotepad Crash", tb_text)
        except Exception:
            pass

    try:
        # Windows DPI 适配
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

        app = MiniNotepad()

        # 注册全局异常处理器
        app.report_callback_exception = _log_crash

        app.mainloop()
    except Exception:
        _log_crash(*sys.exc_info())


if __name__ == "__main__":
    main()

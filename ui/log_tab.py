from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, QMessageBox
import os

from core.utils.logger import LOG_FILE, info, error

class LogTabWidget(QWidget):
    """
    日志显示标签页。
    顶部有刷新、清空按钮，下方为日志显示区，最新日志在最上方。
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.load_log()

    def init_ui(self):
        layout = QVBoxLayout(self)
        btn_layout = QHBoxLayout()
        self.refresh_btn = QPushButton("刷新")
        self.clear_btn = QPushButton("清空")
        self.refresh_btn.clicked.connect(self.load_log)
        self.clear_btn.clicked.connect(self.clear_log)
        btn_layout.addWidget(self.refresh_btn)
        btn_layout.addWidget(self.clear_btn)
        layout.addLayout(btn_layout)
        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        layout.addWidget(self.log_edit, 1)

    def load_log(self):
        """
        加载日志文件内容，最新日志在最上方。
        """
        try:
            if os.path.exists(LOG_FILE):
                with open(LOG_FILE, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                # 最新日志在最上方
                lines.reverse()
                html_lines = []
                for line in lines:
                    l = line.rstrip()
                    if '[ERROR]' in l:
                        html_lines.append(f'<span style="color:red;">{l}</span>')
                    elif '[WARNING]' in l:
                        html_lines.append(f'<span style="color:orange;">{l}</span>')
                    elif '[EXCEPTION]' in l or 'Traceback' in l:
                        html_lines.append(f'<span style="color:purple;">{l}</span>')
                    else:
                        html_lines.append(l)
                self.log_edit.setHtml('<br/>'.join(html_lines))
            else:
                self.log_edit.setPlainText("日志文件不存在。")
        except Exception as e:
            error(f"日志加载失败: {e}")
            self.log_edit.setPlainText(f"日志加载失败: {e}")

    def clear_log(self):
        """
        清空日志文件内容。
        """
        try:
            if os.path.exists(LOG_FILE):
                with open(LOG_FILE, 'w', encoding='utf-8') as f:
                    f.write("")
                info("日志已清空")
            self.load_log()
        except Exception as e:
            error(f"日志清空失败: {e}")
            QMessageBox.critical(self, "错误", f"日志清空失败: {e}") 
import markdown
from PySide6 import QtGui
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QTextEdit, QTextBrowser
from PySide6.QtCore import QThread, Signal

from core.openai_client import OpenAIClient
from core.global_state import GlobalState
from core.utils.logger import info, error

class VernacularWorker(QThread):
    """
    白话文转换异步工作线程。
    用于后台流式调用大模型API进行古文转白话文，避免阻塞主线程。
    """
    result_signal = Signal(str)
    error_signal = Signal(str)
    result_stream_signal = Signal(str)  # 新增流式信号
    def __init__(self, client, text):
        """
        构造函数。
        :param client: OpenAIClient实例
        :param text: 需要转换的古文内容
        """
        super().__init__()
        self.client = client
        self.text = text
    def run(self):
        """
        线程主函数，流式转换古文为白话文并实时发射信号。
        """
        try:
            info("白话文转换线程启动")
            content = ""
            for chunk in self.client.stream_vernacular(self.text):
                content += chunk
                self.result_stream_signal.emit(content)
            self.result_signal.emit(content)
            info("白话文转换成功")
        except Exception as e:
            error(f"白话文转换失败: {e}")
            self.error_signal.emit(str(e))
        self.deleteLater()

class VernacularTabWidget(QWidget):
    """
    白话文转换功能区主界面。
    支持一键转换当前页OCR结果为白话文，流式显示结果。
    """
    def __init__(self, parent=None, pdf_viewer=None):
        """
        构造函数。
        :param parent: 父窗口
        :param pdf_viewer: PDF预览控件实例
        """
        super().__init__(parent)
        self.pdf_viewer = pdf_viewer
        self.init_ui()
    def init_ui(self):
        """
        初始化界面布局，创建按钮、状态标签、结果区等。
        """
        layout = QVBoxLayout(self)
        self.btn = QPushButton("白话文转换")
        self.btn.clicked.connect(self.start_vernacular)
        layout.addWidget(self.btn)
        self.status_label = QLabel("状态: 等待中")
        layout.addWidget(self.status_label)
        font = QFont()
        font.setPointSize(16)
        self.result_edit = QTextBrowser()
        self.result_edit.setReadOnly(True)
        self.result_edit.setFont(font)
        layout.addWidget(self.result_edit, 1)

    def load_page_state(self):
        """
        加载当前页白话文转换结果。
        """
        self.show_result()

    def start_vernacular(self):
        """
        启动白话文转换流程，异步调用大模型API。
        """
        if not self.pdf_viewer:
            self.status_label.setText("状态: 缺少PDF或者OCR结果")
            return
        ocr_data = GlobalState.get_pdf_page_data()
        if not ocr_data:
            self.status_label.setText("状态: 无OCR文本")
            return
        self.status_label.setText("状态: 加载中...")
        self.btn.setEnabled(False)
        client = OpenAIClient()
        ocr_text = ""
        for text in ocr_data.get("ocr").get('rec_texts'):
            ocr_text = ocr_text + text
        self.worker = VernacularWorker(client, ocr_text)
        self.worker.result_signal.connect(self.vernacular_success)
        self.worker.error_signal.connect(self.vernacular_fail)
        self.worker.result_stream_signal.connect(self.vernacular_stream_update)
        self.worker.start()
        info("启动白话文转换流程")
    def vernacular_stream_update(self, content):
        """
        流式更新白话文内容到结果区。
        :param content: 当前已生成内容
        """
        html = markdown.markdown(content)
        self.result_edit.setHtml(html)
        # 移动光标到文档末尾
        cursor = self.result_edit.textCursor()
        cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
        self.result_edit.setTextCursor(cursor)
    def vernacular_success(self, result):
        """
        白话文转换成功回调，显示最终结果并保存。
        :param result: 白话文结果
        """
        self.status_label.setText("状态: 成功")
        self.btn.setEnabled(True)
        GlobalState.save_pdf_page_data({"vernacular": result})
        info("白话文转换结果已保存")

    def vernacular_fail(self, err):
        """
        白话文转换失败回调，显示错误信息。
        :param err: 错误信息
        """
        error(f"白话文转换失败: {err}")
        self.status_label.setText(f"状态: 失败 - {err}")
        self.btn.setEnabled(True)
    
    def show_result(self):
        """
        显示当前页白话文结果。
        """
        page_data = GlobalState.get_pdf_page_data()
        result = page_data.get("vernacular", "")
        self.result_edit.setPlainText(result)
        if result:
            self.status_label.setText("状态: 已缓存")
        else:
            self.status_label.setText("状态: 等待中")

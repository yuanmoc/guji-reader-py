from PySide6 import QtGui
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, QLabel, QTextBrowser
from PySide6.QtCore import Qt, QThread, Signal, QEvent

from core.openai_client import OpenAIClient
from core.utils.logger import info, error
import markdown  # 新增导入


class ExplainWorker(QThread):
    """
    古文解释异步工作线程。
    用于后台流式调用大模型API解释古文，避免阻塞主线程。
    """
    result_signal = Signal(str)
    error_signal = Signal(str)
    result_stream_signal = Signal(str)  # 新增流式信号

    def __init__(self, client, text):
        """
        构造函数。
        :param client: OpenAIClient实例
        :param text: 需要解释的古文内容
        """
        super().__init__()
        self.client = client
        self.text = text

    def run(self):
        """
        线程主函数，流式解释古文并实时发射信号。
        """
        try:
            prompt = f"{self.text}"
            # 使用流式输出
            content = ""
            for chunk in self.client.stream_explain(prompt):
                content += chunk
                self.result_stream_signal.emit(content)
            self.result_signal.emit(content)
        except Exception as e:
            self.error_signal.emit(str(e))
        self.deleteLater()


class ExplainTabWidget(QWidget):
    """
    古文解释工具主界面。
    支持输入古文、点击解释、流式显示解释结果、清空等功能。
    """
    def __init__(self, parent=None, config=None):
        """
        构造函数。
        :param parent: 父窗口
        :param config: 额外配置（可选）
        """
        super().__init__(parent)
        self.config = config or {}
        self.init_ui()

    def init_ui(self):
        """
        初始化界面布局，创建输入框、按钮、结果区等。
        """
        layout = QVBoxLayout(self)
        self.input_edit = QTextEdit()
        self.input_edit.setPlaceholderText("请输入古文内容...")
        layout.addWidget(self.input_edit)
        self.input_tip = QLabel("按Ctrl+Enter分析文本，Shift+Enter换行")
        layout.addWidget(self.input_tip)
        btn_layout = QHBoxLayout()
        self.send_btn = QPushButton("解释")
        self.clear_btn = QPushButton("清空")
        # 用于回车触发
        self.input_edit.installEventFilter(self)
        self.send_btn.clicked.connect(self.start_explain)
        self.clear_btn.clicked.connect(self.input_edit.clear)
        btn_layout.addWidget(self.clear_btn)
        btn_layout.addWidget(self.send_btn)
        layout.addLayout(btn_layout)
        self.status_label = QLabel("状态: 等待输入")
        layout.addWidget(self.status_label)
        font = QFont()
        font.setPointSize(16)
        self.result_edit = QTextBrowser()  # 替换为QTextBrowser控件
        self.result_edit.setReadOnly(True)
        self.result_edit.setFont(font)
        layout.addWidget(self.result_edit, 1)

    def eventFilter(self, obj, event):
        """
        智能处理多个文本框的回车事件。
        支持回车直接触发解释。
        :param obj: 事件源对象
        :param event: QEvent
        :return: bool 是否拦截
        """
        if event.type() == QEvent.Type.KeyPress:
            # 处理回车键/Enter键
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                # modifiers 表示当前按下的修饰键（Ctrl、Shift、Alt等）
                modifiers = event.modifiers()
                # 当前焦点所在的控件
                focused_widget = self.focusWidget()
                # 1. 主文本编辑框处理 (Ctrl+Enter触发分析)
                if focused_widget is self.input_edit:
                    # 检测普通Enter键 (无修饰键)
                    if modifiers == Qt.KeyboardModifier.NoModifier:
                        self.start_explain()
                        return True  # 事件已处理，不会再出现个换行
        return super().eventFilter(obj, event)

    def start_explain(self):
        """
        启动古文解释流程，异步调用大模型API。
        """
        text = self.input_edit.toPlainText().strip()
        if not text:
            self.status_label.setText("状态: 请输入古文内容")
            return
        self.status_label.setText("状态: 加载中...")
        self.send_btn.setEnabled(False)
        info("启动古文解释流程")
        client = OpenAIClient()
        self.worker = ExplainWorker(client, text)
        self.worker.result_signal.connect(self.explain_success)
        self.worker.error_signal.connect(self.explain_fail)
        self.worker.result_stream_signal.connect(self.explain_stream_update)
        self.worker.start()

    def explain_stream_update(self, content):
        """
        流式更新解释内容到结果区，支持Markdown渲染。
        :param content: 当前已生成内容
        """
        html = markdown.markdown(content)
        self.result_edit.setHtml(html)
        # 移动光标到文档末尾
        cursor = self.result_edit.textCursor()
        cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
        self.result_edit.setTextCursor(cursor)

    def explain_success(self, result):
        """
        解释成功回调，显示最终结果，支持Markdown渲染。
        :param result: 解释结果
        """
        self.status_label.setText("状态: 成功")
        self.send_btn.setEnabled(True)
        info("古文解释结果已显示")

    def explain_fail(self, err):
        """
        解释失败回调，显示错误信息。
        :param err: 错误信息
        """
        error(f"古文解释失败: {err}")
        self.status_label.setText(f"状态: 失败 - {err}")
        self.send_btn.setEnabled(True)

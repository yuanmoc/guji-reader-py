import sys

from PySide6 import QtCore
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QHBoxLayout, QTabWidget, QSplitter, QToolButton
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt, QUrl, QObject, Slot
from PySide6.QtGui import QDesktopServices

from core.config_manager import ConfigManager
from ui.pdf_viewer import PDFViewerWidget
from ui.ocr_tab import OCRTabWidget
from ui.proofread_tab import ProofreadTabWidget
from ui.punctuate_tab import PunctuateTabWidget
from ui.vernacular_tab import VernacularTabWidget
from ui.explain_tab import ExplainTabWidget
from ui.log_tab import LogTabWidget
from core.global_state import GlobalState
from core.utils.logger import info, error
from core.utils.path_util import get_resource_path


class MainWindow(QMainWindow):
    """
    应用主窗口。
    包含PDF预览区和右侧多功能Tab区，负责主界面布局与各功能区联动。
    """

    def __init__(self):
        """
        构造函数，初始化主窗口。
        """
        super().__init__()
        self.setWindowTitle("古籍阅读器")
        self.resize(1200, 800)
        info("主窗口初始化")
        self.init_ui()

    def init_ui(self):
        """
        初始化主界面布局，创建PDF预览区和右侧Tab区。
        """
        # 主体布局
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        # 左侧PDF预览区
        self.pdf_viewer = PDFViewerWidget()
        self.pdf_viewer.file_changed.connect(self.on_pdf_file_changed)
        self.pdf_viewer.page_changed.connect(self.on_pdf_page_changed)

        splitter.addWidget(self.pdf_viewer)
        # 右侧Tab区
        self.tabs = QTabWidget()
        self.ocr_tab = OCRTabWidget(pdf_viewer=self.pdf_viewer)
        self.proofread_tab = ProofreadTabWidget(pdf_viewer=self.pdf_viewer)
        self.punctuate_tab = PunctuateTabWidget(pdf_viewer=self.pdf_viewer)
        self.vernacular_tab = VernacularTabWidget(pdf_viewer=self.pdf_viewer)
        self.explain_tab = ExplainTabWidget()
        self.log_tab = LogTabWidget()
        self.tabs.addTab(self.ocr_tab, "OCR")
        self.tabs.addTab(self.proofread_tab, "校对")
        self.tabs.addTab(self.punctuate_tab, "自动标点分段")
        self.tabs.addTab(self.vernacular_tab, "白话文")
        self.tabs.addTab(self.explain_tab, "古文解释")
        self.tabs.addTab(self.log_tab, "执行日志")
        splitter.addWidget(self.tabs)
        splitter.setSizes([400, 800])
        main_layout.addWidget(splitter)
        self.setCentralWidget(main_widget)

        # 悬浮GitHub按钮
        self.github_btn = QToolButton(self)
        self.github_btn.setIcon(QIcon(get_resource_path("ui/assets/github.svg")))
        self.github_btn.setIconSize(QtCore.QSize(32, 32))
        self.github_btn.setToolTip("访问GitHub项目主页")
        self.github_btn.setStyleSheet(
            """
            QToolButton {
                border: none;
                border-radius: 16px;
                padding: 4px;
            }
            QToolButton:hover {
                background: rgba(255,255,255,0.8);
            }
            """
        )
        self.github_btn.resize(40, 40)
        self.github_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://github.com/yuanmoc/guji-reader-py"))
        )
        self._move_github_btn()

        # 连接PDF预览器和OCR标签页的联动
        self.pdf_viewer.set_ocr_tab(self.ocr_tab)
        # 连接PDF预览器和校对标签页的联动
        self.pdf_viewer.set_proofread_tab(self.proofread_tab)

        # 自动加载上次文件
        self.pdf_viewer.auto_load_default_pdf()

    def on_pdf_file_changed(self, file_path):
        """
        PDF文件切换时的回调，更新全局状态。
        :param file_path: 新PDF文件路径
        """
        GlobalState.set_pdf_file(file_path)

    def on_pdf_page_changed(self, page_num):
        """
        PDF页码切换时的回调，更新全局状态并刷新各功能区。
        :param page_num: 新页码
        """
        GlobalState.set_page(page_num)
        self.ocr_tab.load_page_state()
        self.proofread_tab.load_page_state()
        self.punctuate_tab.load_page_state()
        self.vernacular_tab.load_page_state()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._move_github_btn()

    def _move_github_btn(self):
        self.github_btn.move(self.width() - self.github_btn.width() - 10, 2)


class ExitHandler(QObject):
    """
    应用程序退出触发
    """

    @Slot()
    def on_about_to_quit(self):
        ConfigManager().do_save_config()


def main():
    """
    应用程序入口，启动Qt主事件循环。
    """
    try:
        app = QApplication(sys.argv)
        app.setWindowIcon(QIcon(get_resource_path("ui/assets/logo.png")))

        # 创建退出处理器并连接信号
        exit_handler = ExitHandler()
        app.aboutToQuit.connect(exit_handler.on_about_to_quit)

        window = MainWindow()
        window.show()
        info("主界面已显示，进入事件循环")
        sys.exit(app.exec())
    except Exception as e:
        error(f"主程序运行异常: {e}")


if __name__ == "__main__":
    main()

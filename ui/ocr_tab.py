import os
import uuid

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QHBoxLayout, QListWidget, QListWidgetItem
from PySide6.QtCore import QThread, Signal
from core.global_state import GlobalState
from core.ocr_client import OcrClient
from core.utils.ocr_data_util import OcrDataUtil
from core.utils.logger import info, error, warning
from core.utils.path_util import get_user_store_path


class OCRWorker(QThread):
    """
    OCR异步工作线程。
    用于在后台执行OCR推理，避免阻塞主线程。
    """
    result_signal = Signal(list)
    error_signal = Signal(str)

    def __init__(self, image_path, width, height):  # image_path: 临时图片路径
        """
        构造函数。
        :param image_path: 临时图片路径/data
        :param width: 图片宽度
        :param height: 图片高度
        """
        super().__init__()
        self.image_path = image_path
        self.width = width
        self.height = height

    def run(self):
        """
        线程主函数，执行OCR推理并发射信号。
        """
        info("OCRWorker线程run方法进入")
        try:
            info(f"OCR线程启动，图片尺寸: {self.width}x{self.height}")
            ocr = OcrClient().get_ocr_client()
            # 对示例图像执行 OCR 推理
            result = ocr.predict(input=self.image_path)
            self.result_signal.emit(result)
            info("OCR识别成功")
        except Exception as e:
            error(f"OCR识别失败: {e}")
            self.error_signal.emit(str(e))
        # 自动清理临时图片
        if os.path.exists(self.image_path):
            try:
                os.remove(self.image_path)
                info(f"临时图片已删除: {self.image_path}")
            except Exception as e:
                warning(f"删除临时图片失败: {e}")
        info("OCRWorker线程run方法退出")
        self.deleteLater()


class OCRTabWidget(QWidget):
    """
    OCR功能区主界面。
    支持当前页OCR、重试、显示OCR结果、显示OCR框等功能。
    """
    def __init__(self, parent=None, pdf_viewer=None):
        """
        构造函数。
        :param parent: 父窗口
        :param pdf_viewer: PDF预览控件实例
        """
        super().__init__(parent)
        self.pdf_viewer = pdf_viewer
        # 是否显示COR框
        self.show_ocr_boxes_flag = True
        # 当前选中的文本行索引
        self.selected_text_index = -1
        self.init_ui()
        # 删除临时图片


    def init_ui(self):
        """
        初始化界面布局，创建按钮、文本框等控件。
        """
        layout = QVBoxLayout(self)
        btn_layout = QHBoxLayout()
        self.ocr_btn = QPushButton("当前页OCR")
        self.retry_btn = QPushButton("重试")
        self.retry_btn.setEnabled(False)
        self.toggle_ocr_box_btn = QPushButton("显示OCR结果框")
        self.ocr_btn.clicked.connect(self.start_ocr)
        self.retry_btn.clicked.connect(self.start_ocr)
        self.toggle_ocr_box_btn.clicked.connect(self.show_ocr_boxes_on_pdf)
        btn_layout.addWidget(self.ocr_btn)
        btn_layout.addWidget(self.retry_btn)
        btn_layout.addWidget(self.toggle_ocr_box_btn)
        layout.addLayout(btn_layout)
        self.status_label = QLabel("状态: 等待中")
        layout.addWidget(self.status_label)

        # 使用QListWidget替代QTextEdit，支持文本行选择
        font = QFont()
        font.setPointSize(14)
        self.result_list = QListWidget()
        self.result_list.setFont(font)
        self.result_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        # 连接选择变化信号
        self.result_list.currentRowChanged.connect(self.on_text_line_selected)
        
        layout.addWidget(self.result_list, 1)

    def load_page_state(self):
        """
        加载当前页OCR状态和结果。
        """
        self.status_label.setText("状态: 等待中")
        self.result_list.clear()
        self.selected_text_index = -1
        self.show_ocr_text()

    def start_ocr(self):
        """
        启动OCR识别流程，导出当前页为图片并异步识别。
        """
        info("OCRTabWidget启动OCR流程入口")
        if not self.pdf_viewer or not self.pdf_viewer.pdf_doc:
            self.status_label.setText("状态: 未加载PDF")
            return
        self.status_label.setText("状态: 加载中...")
        self.ocr_btn.setEnabled(False)
        self.retry_btn.setEnabled(False)
        # 导出当前页为图片
        last_open_page = GlobalState.get_config().last_open_page
        page = self.pdf_viewer.pdf_doc.get_page(last_open_page)
        info(f"开始OCR，当前页码: {last_open_page}")
        pil_image = page.render(scale=1).to_pil()
        img_path = get_user_store_path("tmp", f"{str(uuid.uuid4())}.png")
        pil_image.save(img_path)
        self.worker = OCRWorker(img_path, pil_image.width, pil_image.height)
        self.worker.result_signal.connect(self.ocr_success)
        self.worker.error_signal.connect(self.ocr_fail)
        self.worker.start()
        info("OCRTabWidget启动OCR流程已调起OCRWorker")

    def ocr_success(self, result):
        """
        OCR识别成功回调，保存结果并刷新界面。
        :param result: OCR结果列表
        """
        ocr_result = result[0]
        # 可以生成ocr后的图片，用于测试或者使用
        # ocr_result.save_to_img("ocr_results")
        self.status_label.setText("状态: 成功")
        self.ocr_btn.setEnabled(True)
        self.retry_btn.setEnabled(True)
        # 缓存与存储
        texts = ocr_result["rec_texts"]
        print(texts)
        GlobalState.save_pdf_page_data({"ocr": OcrDataUtil().sort_by_orientation(ocr_result)})
        self.show_ocr_text()
        info("OCR结果已保存并显示")

    def ocr_fail(self, err):
        """
        OCR识别失败回调，显示错误信息。
        :param err: 错误信息
        """
        error(f"OCR失败: {err}")
        self.status_label.setText(f"状态: 失败 - {err}")
        self.ocr_btn.setEnabled(True)
        self.retry_btn.setEnabled(True)

    def show_ocr_boxes_on_pdf(self):
        """
        显示OCR结果框到PDF图片上。
        """
        if not self.show_ocr_boxes_flag:
            self.show_ocr_text()
        else:
            self.pdf_viewer.hide_ocr_boxes()
            self.show_ocr_boxes_flag = False

    def show_ocr_text(self, show_ocr_box=True):
        """
        显示当前页OCR文本到列表，并在PDF上高亮。
        """
        page_data = GlobalState.get_pdf_page_data()
        ocr_data = page_data.get("ocr")
        if not ocr_data:
            return
        
        # 清空列表
        self.result_list.blockSignals(True)
        self.result_list.clear()
        self.result_list.blockSignals(False)

        # 添加文本行到列表
        for i, text in enumerate(ocr_data['rec_texts']):
            item = QListWidgetItem(f"{i+1}. {text}")
            self.result_list.addItem(item)

        info("正在刷新OCR结果列表，并在PDF页面上高亮所有识别框")
        # 显示OCR框
        if show_ocr_box:
            self.show_ocr_boxes_flag = True
            self.pdf_viewer.show_ocr_boxes(ocr_data)

    def on_text_line_selected(self, row):
        """
        文本行选择变化时的回调函数。
        :param row: 选中的行索引
        """
        row = row if row is not None else -1
        if row == self.selected_text_index:
            return

        self.selected_text_index = row

        # 通知PDF预览器选中对应的OCR框
        if self.pdf_viewer and hasattr(self.pdf_viewer, 'overlay'):
            text = self.result_list.item(row).text() if 0 < row < self.result_list.count() else ""
            info(f"用户在OCR结果列表中选中了第{row+1}行文本，准备高亮PDF上的对应识别框，文本内容：{text}")
            self.pdf_viewer.overlay.set_selected_index(row, False)


    def set_selection_from_pdf(self, row):
        """
        从PDF预览器设置选择（避免循环调用）
        :param row: 选中的行索引
        """
        if row == self.selected_text_index:
            return

        info(f"用户在PDF页面上点击了第{row+1}个识别框，准备联动选中OCR结果列表中的对应文本行")
        self.show_ocr_text(show_ocr_box=False)
        if 0 <= row < self.result_list.count():
            # 不触发选中事件
            self.result_list.blockSignals(True)
            self.result_list.setCurrentRow(row)
            self.result_list.blockSignals(False)
            self.selected_text_index = row
        else:
            self.result_list.clearSelection()
            self.selected_text_index = -1

    def showEvent(self, event):
        """
        每次显示时刷新内容。
        :param event: QShowEvent
        """
        super().showEvent(event)
        self.show_ocr_text()
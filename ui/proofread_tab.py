from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton, QDialog, QScrollArea, \
    QFrame, QBoxLayout, QTableWidget, QTableWidgetItem
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QImage, QFont, QFontMetrics
from core.global_state import GlobalState
from ui.pdf_viewer import PDFViewerWidget
from core.utils.logger import info


def crop_poly_image(qimage, poly):
    """
    裁剪多边形区域的图片。
    :param qimage: QImage原图
    :param poly: 多边形坐标列表[[x1, y1], ...]
    :return: QPixmap裁剪结果
    """
    xs = [int(p[0]) for p in poly]
    ys = [int(p[1]) for p in poly]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)

    # 计算宽度和高度（包含边界）
    width = int(x_max - x_min + 6)
    height = int(y_max - y_min + 6)

    # 裁剪矩形区域
    rect = qimage.copy(x_min, y_min, width, height)
    return QPixmap.fromImage(rect)

class ProofreadDialog(QDialog):
    """
    校对弹窗对话框。
    支持对每一行OCR结果进行人工校对和编辑。
    """
    def __init__(self, page_image, ocr_data, parent=None):
        """
        构造函数。
        :param page_image: QImage当前页图片
        :param ocr_data: OCR识别结果dict
        :param parent: 父窗口
        """
        super().__init__(parent)
        self.setWindowTitle("校对")
        self.resize(1000, 700)
        layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QFrame()
        vbox = QVBoxLayout(content)
        # 竖排/横排顺序
        rec_texts = ocr_data.get("rec_texts", [])
        rec_polys = ocr_data.get("rec_polys", [])
        # vertical 竖排
        orientation = ocr_data.get("orientation", "horizontal")

        if orientation == "vertical":
            hbox = QHBoxLayout()
            hbox.setDirection(QBoxLayout.Direction.RightToLeft)
        else:
            hbox = QVBoxLayout()

        for idx, (text, poly) in enumerate(zip(rec_texts, rec_polys)):
            pix = crop_poly_image(page_image, poly)
            # 按固定宽度等比例缩放图片
            if orientation == "vertical":
                scaled_pixmap = pix.scaledToWidth(50, Qt.TransformationMode.SmoothTransformation)
            else:
                scaled_pixmap = pix.scaledToHeight(40, Qt.TransformationMode.SmoothTransformation)
            img_label = QLabel()
            img_label.setPixmap(scaled_pixmap)
            img_label.setAlignment(Qt.AlignmentFlag.AlignTop)

            font = QFont()
            font.setPointSize(20)

            # 计算合适的宽度 - 基于字体大小自动适配
            font_metrics = QFontMetrics(font)
            char_width = font_metrics.horizontalAdvance('W')  # 获取标准字符宽度

            text_edit = QTextEdit()
            text_edit.setPlainText(text)
            text_edit.setFont(font)
            text_edit.textChanged.connect(self.make_text_changed_handler(text_edit, idx))

            block = QFrame()
            block.setFrameStyle(QFrame.Shape.Box)  # 可选的边框样式，方便可视化

            if orientation == "vertical":
                block_layout = QHBoxLayout(block)  # 竖排时水平布局（文本框|图片）
                block.setFixedWidth((char_width + 50 * 2))
                text_edit.setFixedWidth(char_width * 2)
            else:
                block_layout = QVBoxLayout(block)  # 横排时垂直布局（图片↑文本框↓）
                block.setFixedHeight((char_width + 40 * 2))
                text_edit.setFixedHeight(char_width * 2)
            block_layout.addWidget(img_label)
            block_layout.addWidget(text_edit, 1)
            hbox.addWidget(block)

        vbox.addLayout(hbox)
        content.setLayout(vbox)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

    def make_text_changed_handler(self, text_edit, idx):
        """
        生成文本变更回调闭包。
        :param text_edit: QTextEdit控件
        :param idx: 行索引
        :return: handler函数
        """
        def handler():
            # 在回调中获取当前文本
            new_text = text_edit.toPlainText()
            page_data = GlobalState.get_pdf_page_data()
            page_data.get("ocr", {}).get("rec_texts", [])[idx] = new_text
            info(f"校对区内容变更: 行{idx}, 新文本: {new_text}")
        return handler


class ProofreadTabWidget(QWidget):
    """
    校对功能区主界面。
    支持打开校对弹窗、显示当前页校对结果。
    """
    def __init__(self, parent=None, pdf_viewer: PDFViewerWidget = None):
        """
        构造函数。
        :param parent: 父窗口
        :param pdf_viewer: PDF预览控件实例
        """
        super().__init__(parent)
        self.pdf_viewer = pdf_viewer
        self.selected_text_index = -1
        self.init_ui()

    def init_ui(self):
        """
        初始化界面布局，创建按钮、状态标签、结果区等。
        """
        layout = QVBoxLayout(self)
        self.open_btn = QPushButton("打开校对")
        self.open_btn.clicked.connect(self.open_proofread)
        layout.addWidget(self.open_btn)
        self.status_label = QLabel("状态: 等待校对")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.status_label)

        font = QFont()
        font.setPointSize(16)
        self.result_table = QTableWidget(self)
        self.result_table.setColumnCount(1)
        self.result_table.horizontalHeader().setStretchLastSection(True)
        self.result_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.result_table.setFont(font)
        self.result_table.setHorizontalHeaderLabels(["校对文本内容"])
        self.result_table.cellClicked.connect(self.on_text_line_selected)
        self.result_table.cellChanged.connect(self.on_text_line_edited)
        layout.addWidget(self.result_table, 1)

    def open_proofread(self):
        """
        打开校对弹窗，支持对当前页OCR结果人工校对。
        """
        if not self.pdf_viewer:
            self.status_label.setText("状态: 缺少PDF或OCR信息")
            return
        # 获取当前页图片
        page = self.pdf_viewer.pdf_doc.load_page(GlobalState.current_page)
        pix = page.get_pixmap(matrix=None)
        img = QImage(pix.samples, pix.width, pix.height, pix.stride,
                     QImage.Format.Format_RGBA8888 if pix.alpha else QImage.Format.Format_RGB888)
        # 获取OCR结果
        ocr_data = GlobalState.get_pdf_page_data().get("ocr", {})
        if not ocr_data or not ocr_data.get("rec_texts"):
            self.status_label.setText("状态: 当前页无OCR结果")
            return
        info("打开校对弹窗")
        dialog = ProofreadDialog(img, ocr_data, self)
        # 连接关闭信号到目标方法
        dialog.finished.connect(self.on_dialog_closed)
        dialog.exec()

    def on_dialog_closed(self, result):
        """
        校对弹窗关闭时回调，保存数据并刷新界面。
        """
        info("校对弹窗关闭，缓存已保存")
        # 保存
        GlobalState.save_cache()
        self.show_ocr_text()

    def show_ocr_text(self, show_ocr_box=True):
        """
        显示当前页OCR文本到表格，并在PDF上高亮。
        """
        page_data = GlobalState.get_pdf_page_data()
        ocr_data = page_data.get("ocr")
        if not ocr_data:
            self.result_table.setRowCount(0)
            return
        rec_texts = ocr_data.get('rec_texts', [])
        # 不触发选中事件
        self.result_table.blockSignals(True)
        self.result_table.setRowCount(len(rec_texts))
        for i, text in enumerate(rec_texts):
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            self.result_table.setItem(i, 0, item)
        self.result_table.blockSignals(False)
        self.selected_text_index = -1
        info("正在刷新校对区表格，并在PDF页面上高亮所有识别框")
        # 显示OCR框
        if show_ocr_box and self.pdf_viewer:
            self.pdf_viewer.show_ocr_boxes(ocr_data)

    def on_text_line_selected(self, row, col):
        if row == self.selected_text_index:
            return
        self.selected_text_index = row
        # 通知PDF预览器选中对应的OCR框
        if self.pdf_viewer and hasattr(self.pdf_viewer, 'overlay'):
            info(f"用户在校对区表格中选中了第{row+1}行文本，准备高亮PDF上的对应识别框，文本内容：{self.result_table.item(row, 0).text()}")
            self.pdf_viewer.overlay.set_selected_index(row, False)

    def set_selection_from_pdf(self, row):
        if row == self.selected_text_index:
            return
        info(f"用户在PDF页面上点击了第{row+1}个识别框，准备联动选中校对区表格中的对应文本行")
        self.show_ocr_text(show_ocr_box=False)
        if 0 <= row < self.result_table.rowCount():
            # 不触发选中事件
            self.result_table.blockSignals(True)
            self.result_table.selectRow(row)
            self.result_table.blockSignals(False)
            self.selected_text_index = row
        else:
            self.result_table.clearSelection()
            self.selected_text_index = -1

    def on_text_line_edited(self, row, col):
        # 编辑后同步到GlobalState
        new_text = self.result_table.item(row, 0).text()
        page_data = GlobalState.get_pdf_page_data()
        ocr_data = page_data.get("ocr", {})
        if 'rec_texts' in ocr_data and 0 <= row < len(ocr_data['rec_texts']):
            ocr_data['rec_texts'][row] = new_text
            info(f"校对区内容变更: 行{row}, 新文本: {new_text}")

    def load_page_state(self):
        """
        加载当前页校对状态和结果。
        """
        self.status_label.setText("状态: 等待中")
        self.show_ocr_text()
    def showEvent(self, event):
        """
        每次显示时刷新内容。
        :param event: QShowEvent
        """
        super().showEvent(event)
        self.show_ocr_text()
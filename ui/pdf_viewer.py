import math

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit, QFileDialog, \
    QSizePolicy
from PySide6.QtCore import Qt, Signal, QPoint, QRect, QPointF, QRectF
from PySide6.QtGui import QPainter, QColor, QPen, QPolygon, QBrush
import fitz  # PyMuPDF
from PySide6.QtGui import QPixmap, QImage
from pymupdf import Document
import os

from core.global_state import GlobalState
from ui.settings_dialog import SettingsDialog
from core.utils.logger import info, error


class OverlayWidget(QWidget):
    """
    PDF图片上方的透明覆盖层，用于绘制和交互OCR识别框。
    支持：
    1. 绘制所有OCR识别框
    2. 点击OCR框选中并高亮，右上角显示删除“x”
    3. 拖动四边/四角调整大小
    4. 按“x”键删除选中框
    """

    # 添加选择变化信号
    selection_changed = Signal(int)  # 发送选中的索引

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ocr_boxes = []  # [(poly, text)]

        # OCR框操作调整
        self.selected_index = -1
        self.drag_x_size = 8
        # None/'left'/'right'/'top'/'bottom'/'topleft'/'topright'/'bottomleft'/'bottomright'
        self.resize_edge = None
        self.is_dragging = False
        self.drag_start_pos = None

        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_ocr_boxes(self, ocr_boxes):
        self.ocr_boxes = ocr_boxes
        self.set_selected_index(None, False)

    def clear_ocr_boxes(self):
        self.ocr_boxes = []
        self.set_selected_index(None)

    def set_selected_index(self, index, send_selection_changed_signal=True):
        """
        设置选中的索引（从外部调用）
        :param index: 选中的索引，None表示取消选中
        """
        index = index if index is not None else -1
        if self.selected_index != index:
            info(f"PDF页面上高亮第{index+1}个识别框，并准备通知右侧文本区联动选中")
            self.selected_index = index
        if index < 0:
            self.resize_edge = None
            self.is_dragging = False
            self.drag_start_pos = None
        self.update()
        # 发送选择变化信号，接收值时None会变成0
        if send_selection_changed_signal:
            self.selection_changed.emit(index)
    def paintEvent(self, event):
        if not self.ocr_boxes:
            return
        painter = QPainter(self)
        for idx, (poly, text) in enumerate(self.ocr_boxes):
            # 创建多边形
            polygon = QPolygon([QPointF(x, y).toPoint() for x, y in poly])

            # 设置样式
            is_selected = idx == self.selected_index
            painter.setPen(QPen(QColor(0, 180, 255, 200), 3) if is_selected else QPen(QColor(255, 0, 0, 180), 2))
            painter.setBrush(QBrush(QColor(0, 180, 255, 60)) if is_selected else Qt.BrushStyle.NoBrush)

            # 绘制多边形
            painter.drawPolygon(polygon)

            # 绘制选中状态元素
            if is_selected:
                self._draw_handles(painter, poly)
                self._draw_delete_button(painter, poly[1])  # 右上角绘制删除按钮


    def _draw_handles(self, painter, points):
        """绘制调整控制点"""
        painter.setBrush(QColor(255, 255, 255, 200))
        painter.setPen(QPen(QColor(0, 180, 255, 200), 1))

        # 直接使用原始点数据列表
        for (x, y) in points:
            painter.drawEllipse(
                x - self.drag_x_size / 2,
                y - self.drag_x_size / 2,
                self.drag_x_size,
                self.drag_x_size
            )

    def _draw_delete_button(self, painter, pos):
        """绘制删除按钮"""
        painter.setPen(QPen(QColor(180, 0, 0), 2))
        size = self.drag_x_size
        painter.drawLine(
            pos[0] - size / 2, pos[1] - size / 2,
            pos[0] + size / 2, pos[1] + size / 2
        )
        painter.drawLine(
            pos[0] + size / 2, pos[1] - size / 2,
            pos[0] - size / 2, pos[1] + size / 2
        )

    def mousePressEvent(self, event):
        """
        处理鼠标按下事件
        :param event:
        :return:
        """
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()

        # 检查是否点在“x”按钮
        for idx, (poly, text) in enumerate(self.ocr_boxes):
            points = [QPoint(x, y) for x, y in poly]
            x0, y0 = points[1].x(), points[1].y()
            size = self.drag_x_size
            x_rect = QRect(int(x0 - size / 2), int(y0 - size / 2), size, size)
            if x_rect.contains(pos):
                self.delete_box(idx)
                return
        # 检查是否点在框内
        for idx, (poly, text) in enumerate(self.ocr_boxes):
            polygon = QPolygon([QPoint(x, y) for x, y in poly])
            if polygon.containsPoint(pos, Qt.FillRule.OddEvenFill):
                self.set_selected_index(idx)
                return
        # 检查是否点击调整点
        if self.selected_index >= 0:
            self._check_resize_edge(pos)
            if self.resize_edge:
                self.is_dragging = True
                self.drag_start_pos = pos
                self.update()
                return
        # 其他区域
        if self.selected_index >= 0:
            self.set_selected_index(None)

    def mouseMoveEvent(self, event):
        pos = event.position()

        # 处理调整大小
        if self.is_dragging and self.resize_edge:
            self._resize_selected_box(pos)
            return

        # 鼠标悬停时显示对应光标
        if self.selected_index >= 0:
            self._check_resize_edge(pos)

    def mouseReleaseEvent(self, event):
        self.is_dragging = False
        self.resize_edge = None

    def _check_resize_edge(self, pos):
        """检查鼠标是否在调整边缘/角落"""
        if self.selected_index < 0:
            return

        poly, _ = self.ocr_boxes[self.selected_index]

        # 只在四个点坐标附近 drag_x_size 区域内有效
        self.resize_edge = None
        # 角点判断
        for i, (x, y) in enumerate(poly):
            if abs(pos.x() - x) < self.drag_x_size and abs(pos.y() - y) < self.drag_x_size:
                if i == 0:
                    self.resize_edge = "topleft"
                elif i == 1:
                    self.resize_edge = "topright"
                elif i == 2:
                    self.resize_edge = "bottomright"
                elif i == 3:
                    self.resize_edge = "bottomleft"
                return

        # 边线判断（允许在法线方向正负 drag_x_size/2 区域内）
        def point_near_edge(px, py, x1, y1, x2, y2):
            # 点到线段距离
            # 计算线段向量 dx 和 dy
            dx = x2 - x1
            dy = y2 - y1

            # 处理线段退化为点的情况（两点重合）
            if dx == 0 and dy == 0:
                return math.hypot(px - x1, py - y1) < self.drag_x_size

            # 计算点 P 到线段起点 A 的向量 AP 的坐标差
            apx = px - x1
            apy = py - y1

            # 计算 AP 在 AB 上的投影比例 t（用于判断最近点位置）
            t = (apx * dx + apy * dy) / (dx ** 2 + dy ** 2)

            # 根据 t 的值确定最近点并计算距离
            if t < 0:
                # 最近点是线段起点 A
                distance = math.hypot(apx, apy)
            elif t > 1:
                # 最近点是线段终点 B
                bpx = px - x2
                bpy = py - y2
                distance = math.hypot(bpx, bpy)
            else:
                # 最近点是垂足，计算点到直线的垂直距离
                numerator = abs((y2 - y1) * px - (x2 - x1) * py + x2 * y1 - y2 * x1)
                denominator = math.sqrt((y2 - y1) ** 2 + (x2 - x1) ** 2)
                distance = numerator / denominator

            # 判断距离是否小于阈值
            return distance < self.drag_x_size

        px, py = pos.x(), pos.y()
        # top 边
        if point_near_edge(px, py, poly[0][0], poly[0][1], poly[1][0], poly[1][1]):
            self.resize_edge = "top"
            return
        # right 边
        if point_near_edge(px, py, poly[1][0], poly[1][1], poly[2][0], poly[2][1]):
            self.resize_edge = "right"
            return
        # bottom 边
        if point_near_edge(px, py, poly[2][0], poly[2][1], poly[3][0], poly[3][1]):
            self.resize_edge = "bottom"
            return
        # left 边
        if point_near_edge(px, py, poly[3][0], poly[3][1], poly[0][0], poly[0][1]):
            self.resize_edge = "left"
            return

    def _resize_selected_box(self, pos):
        """调整选中框的大小"""
        if not self.drag_start_pos or self.selected_index < 0:
            return

        dx = pos.x() - self.drag_start_pos.x()
        dy = pos.y() - self.drag_start_pos.y()
        self.drag_start_pos = pos

        poly, text = self.ocr_boxes[self.selected_index]
        rect = QRectF(
            min(p[0] for p in poly), min(p[1] for p in poly),
            max(p[0] for p in poly) - min(p[0] for p in poly),
            max(p[1] for p in poly) - min(p[1] for p in poly)
        )

        # 根据边缘调整矩形
        if self.resize_edge == "left":
            rect.setLeft(max(0, rect.left() + dx))
        elif self.resize_edge == "right":
            rect.setRight(min(self.width(), rect.right() + dx))
        elif self.resize_edge == "top":
            rect.setTop(max(0, rect.top() + dy))
        elif self.resize_edge == "bottom":
            rect.setBottom(min(self.height(), rect.bottom() + dy))
        elif self.resize_edge == "topleft":
            rect.setLeft(max(0, rect.left() + dx))
            rect.setTop(max(0, rect.top() + dy))
        elif self.resize_edge == "topright":
            rect.setRight(min(self.width(), rect.right() + dx))
            rect.setTop(max(0, rect.top() + dy))
        elif self.resize_edge == "bottomleft":
            rect.setLeft(max(0, rect.left() + dx))
            rect.setBottom(min(self.height(), rect.bottom() + dy))
        elif self.resize_edge == "bottomright":
            rect.setRight(min(self.width(), rect.right() + dx))
            rect.setBottom(min(self.height(), rect.bottom() + dy))

        # 确保矩形有效
        if rect.width() < 10 or rect.height() < 10:
            return

        # 更新多边形点
        page_data = GlobalState.get_pdf_page_data()
        # 更新原数据
        page_data.get("ocr", {}).get("rec_polys", [])[self.selected_index] = [
                                                   [rect.left(), rect.top()],
                                                   [rect.right(), rect.top()],
                                                   [rect.right(), rect.bottom()],
                                                   [rect.left(), rect.bottom()]
                                               ]
        # 更新当前使用数据
        self.ocr_boxes[self.selected_index] = ([[rect.left(), rect.top()],
                                                   [rect.right(), rect.top()],
                                                   [rect.right(), rect.bottom()],
                                                   [rect.left(), rect.bottom()]
                                               ], text)
        self.update()


    def delete_box(self, idx):
        if 0 <= idx < len(self.ocr_boxes):
            # 删除当前使用数据
            del self.ocr_boxes[idx]
            # 删除原数据
            page_data = GlobalState.get_pdf_page_data()
            del page_data.get("ocr", {}).get("rec_texts", [])[idx]
            del page_data.get("ocr", {}).get("rec_scores", [])[idx]
            del page_data.get("ocr", {}).get("rec_polys", [])[idx]
            self.set_selected_index(None)

class PDFViewerWidget(QWidget):
    """
    PDF预览主界面。
    支持PDF加载、翻页、跳转、缩放、显示OCR框、打开设置等功能。
    """
    file_changed = Signal(str)
    page_changed = Signal(int)

    def __init__(self, parent=None):
        """
        构造函数。
        :param parent: 父控件
        :param auto_load_last: 是否自动加载上次文件
        """
        super().__init__(parent)
        self.pdf_doc = None
        self.current_page = 0
        self.file_path = None
        self.ocr_tab = None  # 保存OCR标签页的引用
        self.proofread_tab = None # 保存校对标签页的引用
        self.init_ui()

    def init_ui(self):
        """
        初始化界面布局，创建工具栏、图片显示区、覆盖层等。
        """
        layout = QVBoxLayout(self)
        # 工具栏
        toolbar = QHBoxLayout()
        self.open_action = QPushButton("打开PDF")
        self.prev_btn = QPushButton("上一页")
        self.next_btn = QPushButton("下一页")
        self.page_edit = QLineEdit("1")
        self.page_edit.setFixedWidth(40)
        self.page_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_edit.returnPressed.connect(self.goto_page)
        self.page_label = QLabel("/ 0")
        self.settings_action = QPushButton("更多设置")

        # 优化按钮样式
        self.open_action.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 4px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #50a7ec;
            }
        """)

        self.prev_btn.clicked.connect(self.prev_page)
        self.next_btn.clicked.connect(self.next_page)
        self.open_action.clicked.connect(self.open_pdf)
        self.settings_action.clicked.connect(self.open_settings)

        toolbar.addWidget(self.open_action)
        toolbar.addWidget(self.prev_btn)
        toolbar.addWidget(self.next_btn)

        # 将页码相关控件组合在一起
        page_widget = QWidget()
        page_layout = QHBoxLayout(page_widget)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)
        label = QLabel("跳转:")
        label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        page_layout.addWidget(label)
        page_layout.addWidget(self.page_edit)
        page_layout.addWidget(self.page_label)

        toolbar.addWidget(page_widget)
        toolbar.addWidget(self.settings_action)

        layout.addLayout(toolbar)

        # PDF显示区
        self.image_label = QLabel("请打开PDF文件")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # 创建一个居中容器来显示PDF
        center_widget = QWidget()
        center_layout = QHBoxLayout(center_widget)
        center_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center_layout.addWidget(self.image_label)
        layout.addWidget(center_widget, 1)

        # 添加OverlayWidget
        self.overlay = OverlayWidget(self.image_label)
        self.overlay.setGeometry(0, 0, self.image_label.width(), self.image_label.height())
        self.image_label.installEventFilter(self)

    def set_ocr_tab(self, ocr_tab):
        """
        设置OCR标签页引用，用于联动
        :param ocr_tab: OCR标签页实例
        """
        self.ocr_tab = ocr_tab
        # 连接OverlayWidget的选择变化信号到OCR标签页
        if self.overlay:
            self.overlay.selection_changed.connect(self.on_overlay_selection_changed)

    def set_proofread_tab(self, proofread_tab):
        """
        设置校对标签页引用，用于联动
        :param proofread_tab: 校对标签页实例
        """
        self.proofread_tab = proofread_tab
        if self.overlay:
            self.overlay.selection_changed.connect(self.on_overlay_selection_changed)

    def on_overlay_selection_changed(self, index):
        """
        OverlayWidget选择变化时的回调
        :param index: 选中的索引
        """
        info(f"PDF页面上的识别框被点击，正在联动右侧文本区选中第{index+1}行")
        # OCR联动
        if hasattr(self, 'ocr_tab') and self.ocr_tab and hasattr(self.ocr_tab, 'set_selection_from_pdf'):
            self.ocr_tab.set_selection_from_pdf(index)
        # 校对联动
        if hasattr(self, 'proofread_tab') and self.proofread_tab and hasattr(self.proofread_tab, 'set_selection_from_pdf'):
            self.proofread_tab.set_selection_from_pdf(index)

    def resizeEvent(self, event):
        """
        窗口大小变化时，调整覆盖层大小。
        :param event: QResizeEvent
        """
        super().resizeEvent(event)
        if hasattr(self, 'overlay'):
            self.overlay.setGeometry(0, 0, self.image_label.width(), self.image_label.height())

    def open_settings(self):
        """
        打开“更多设置”对话框。
        """
        dialog = SettingsDialog(self)
        dialog.exec()

    def auto_load_default_pdf(self):
        """
        新增：自动加载上次文件
        :return:
        """
        config = GlobalState.get_config()
        if config.last_open_file and os.path.exists(config.last_open_file):
            info(f"自动加载上次文件: {config.last_open_file}, 页码: {config.last_open_page}")
            self.load_pdf(config.last_open_file, config.last_open_page)
        else:
            info("未检测到上次打开的PDF文件")

    def open_pdf(self):
        """
        弹出文件选择框，加载PDF文件。
        """
        file_path, _ = QFileDialog.getOpenFileName(self, "选择PDF文件", "", "PDF Files (*.pdf)")
        if file_path:
            info(f"用户选择PDF文件: {file_path}")
            self.load_pdf(file_path)

    def load_pdf(self, file_path, page_num=None):
        """
        加载指定PDF文件。
        :param file_path: PDF文件路径
        :param page_num: 指定页码（可选）
        """
        try:
            self.pdf_doc = fitz.open(file_path)
            self.file_path = file_path
            if page_num is not None and 0 <= page_num < self.pdf_doc.page_count:
                self.current_page = page_num
            else:
                self.current_page = 0
            self.page_edit.setText(str(self.current_page + 1))
            self.page_label.setText(f"/ {self.pdf_doc.page_count}")
            self.file_changed.emit(file_path)
            self.show_page()
            info(f"PDF加载成功: {file_path}, 当前页: {self.current_page}")
        except Exception as e:
            error(f"PDF加载失败: {file_path}, 错误: {e}")

    def get_pdf_doc(self) -> Document:
        """
        获取当前PDF文档对象。
        :return: pymupdf.Document
        """
        return self.pdf_doc

    def show_ocr_boxes(self, ocr_data):
        """
        在PDF图片上显示OCR识别框。
        :param ocr_data: dict，包含'rec_polys'和'rec_texts'
        """
        # ocr_data: dict, 包含rec_polys和rec_texts
        if not ocr_data or 'rec_polys' not in ocr_data or 'rec_texts' not in ocr_data:
            self.overlay.clear_ocr_boxes()
            return
        scaled_boxes = self.get_scaled_boxes_data(ocr_data)
        info("正在PDF页面上显示所有识别框")
        # 外围框
        info(f"PDF OCR框像素大小 ==> width: {self.image_label.width()}, height: {self.image_label.height()}")
        # scaled_boxes.append(([[0, 0], [0, height], [width, height], [width, 0]], "text"))
        self.overlay.set_ocr_boxes(scaled_boxes)

    def get_scaled_boxes_data(self, ocr_data):
        """
        获取OCR框坐标信息
        :param ocr_data:
        :return:
        """
        boxes = list(zip(ocr_data['rec_polys'], ocr_data['rec_texts']))
        # 需要根据当前缩放调整坐标（如果有缩放功能，则需要调整）
        scaled_boxes = []
        for poly, text in boxes:
            scaled_poly = [[x, y] for x, y in poly]
            scaled_boxes.append((scaled_poly, text))
        return scaled_boxes

    def hide_ocr_boxes(self):
        """
        隐藏所有OCR识别框。
        """
        self.overlay.clear_ocr_boxes()

    def show_page(self):
        """
        显示当前页PDF图片。
        """
        if not self.pdf_doc:
            return
        page = self.pdf_doc.load_page(self.current_page)
        pix = page.get_pixmap(matrix=None)
        img = QImage(pix.samples, pix.width, pix.height, pix.stride,
                     QImage.Format.Format_RGBA8888 if pix.alpha else QImage.Format.Format_RGB888)
        self.image_label.setPixmap(QPixmap.fromImage(img))
        # 关键：让label适应图片大小
        self.image_label.setFixedSize(pix.width, pix.height)
        self.page_edit.setText(str(self.current_page + 1))
        self.page_label.setText(f"/ {self.pdf_doc.page_count}")
        # 切换页时隐藏OCR框
        self.hide_ocr_boxes()
        self.page_changed.emit(self.current_page)
        info(f"PDF容器像素大小 ==> width: {img.width()}, height: {img.height()}")

    def prev_page(self):
        """
        跳转到上一页。
        """
        if self.pdf_doc and self.current_page > 0:
            self.current_page -= 1
            self.show_page()

    def next_page(self):
        """
        跳转到下一页。
        """
        if self.pdf_doc and self.current_page < self.pdf_doc.page_count - 1:
            self.current_page += 1
            self.show_page()

    def goto_page(self):
        """
        跳转到指定页码。
        """
        if not self.pdf_doc:
            return
        try:
            page = int(self.page_edit.text()) - 1
            if 0 <= page < self.pdf_doc.page_count:
                self.current_page = page
                self.show_page()
        except ValueError:
            pass

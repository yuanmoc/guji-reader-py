import math

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit, QFileDialog, \
    QSizePolicy, QScrollArea, QFrame
from PySide6.QtCore import Qt, Signal, QPoint, QRect, QPointF, QRectF
from PySide6.QtGui import QPainter, QColor, QPen, QPolygon, QBrush, QPixmap, QIntValidator
import pypdfium2
from PIL import ImageQt
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
            info(f"PDF页面上高亮第{index + 1}个识别框，并准备通知右侧文本区联动选中")
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
        """
        super().__init__(parent)
        self.pdf_doc = None
        self.config = GlobalState.get_config()
        self.ocr_tab = None  # 保存OCR标签页的引用
        self.proofread_tab = None  # 保存校对标签页的引用

        # 新增：缩放相关属性
        self.scale_factor = 1.0  # 缩放因子
        self.original_size = (0, 0)  # 原始PDF页面大小
        self.fit_mode = "fit_window"  # 自适应模式: fit_width, fit_window, actual_size

        self.init_ui()

    def init_ui(self):
        """
        初始化界面布局，创建工具栏、图片显示区、覆盖层等。
        """
        layout = QVBoxLayout(self)

        # 工具栏 - 优化布局结构
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(5, 5, 5, 5)  # 整体边距
        toolbar.setSpacing(6)  # 控件间距

        # 第一部分：文件操作
        file_group = QWidget()
        file_layout = QHBoxLayout(file_group)
        file_layout.setContentsMargins(0, 0, 0, 0)
        file_layout.setSpacing(6)

        self.open_action = QPushButton("打开PDF")
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
        file_layout.addWidget(self.open_action)

        # 添加文件操作区到主工具栏
        toolbar.addWidget(file_group)

        # 分隔线
        line1 = QFrame()
        line1.setFrameShape(QFrame.Shape.VLine)
        line1.setFrameShadow(QFrame.Shadow.Sunken)
        toolbar.addWidget(line1)

        # 第二部分：页面导航
        nav_group = QWidget()
        nav_layout = QHBoxLayout(nav_group)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(6)

        self.prev_btn = QPushButton("上一页")
        self.next_btn = QPushButton("下一页")

        # 页码控制
        page_widget = QWidget()
        page_layout = QHBoxLayout(page_widget)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(3)  # 缩小页码控件间距
        self.page_edit = QLineEdit("1")
        self.page_edit.setFixedWidth(36)
        self.page_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_edit.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.page_edit.setValidator(QIntValidator(1, 9999, self))  # 限制为1-9999的整数
        self.page_edit.returnPressed.connect(self.goto_page)
        self.page_label = QLabel("/ 0")

        page_layout.addWidget(self.page_edit)
        page_layout.addWidget(self.page_label)
        nav_layout.addWidget(self.prev_btn)
        nav_layout.addWidget(page_widget)
        nav_layout.addWidget(self.next_btn)

        toolbar.addWidget(nav_group)

        # 分隔线
        line2 = QFrame()
        line2.setFrameShape(QFrame.Shape.VLine)
        line2.setFrameShadow(QFrame.Shadow.Sunken)
        toolbar.addWidget(line2)

        # 第三部分：缩放控制
        zoom_group = QWidget()
        zoom_layout = QHBoxLayout(zoom_group)
        zoom_layout.setContentsMargins(0, 0, 0, 0)
        zoom_layout.setSpacing(4)  # 缩放按钮间距稍小

        self.zoom_in_btn = QPushButton("+")
        self.zoom_out_btn = QPushButton("-")
        self.fit_width_btn = QPushButton("等宽")
        self.fit_window_btn = QPushButton("自适应")
        self.actual_size_btn = QPushButton("1:1")  # 用图标式文本更简洁

        # 调整按钮大小使其更紧凑
        self.zoom_in_btn.setFixedWidth(30)
        self.zoom_out_btn.setFixedWidth(30)

        zoom_layout.addWidget(self.zoom_in_btn)
        zoom_layout.addWidget(self.zoom_out_btn)
        zoom_layout.addWidget(self.fit_width_btn)
        zoom_layout.addWidget(self.fit_window_btn)
        zoom_layout.addWidget(self.actual_size_btn)

        toolbar.addWidget(zoom_group)

        # 伸缩项 - 推到右侧
        toolbar.addStretch()

        # 第四部分：设置按钮
        self.settings_action = QPushButton("更多设置")
        toolbar.addWidget(self.settings_action)

        # 连接信号槽
        self.prev_btn.clicked.connect(self.prev_page)
        self.next_btn.clicked.connect(self.next_page)
        self.open_action.clicked.connect(self.open_pdf)
        self.settings_action.clicked.connect(self.open_settings)
        self.zoom_in_btn.clicked.connect(self.zoom_in)
        self.zoom_out_btn.clicked.connect(self.zoom_out)
        self.fit_width_btn.clicked.connect(lambda: self.set_fit_mode("fit_width"))
        self.fit_window_btn.clicked.connect(lambda: self.set_fit_mode("fit_window"))
        self.actual_size_btn.clicked.connect(lambda: self.set_fit_mode("actual_size"))

        layout.addLayout(toolbar)

        # 新增：添加滚动区域，用于大图片滚动查看
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # PDF显示区
        self.image_container = QWidget()
        self.image_layout = QVBoxLayout(self.image_container)
        self.image_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.image_label = QLabel("请打开PDF文件")
        self.image_label.setStyleSheet("border: 2px solid #f9d7d7;padding:0;margin:0;")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_layout.addWidget(self.image_label)

        self.scroll_area.setWidget(self.image_container)
        layout.addWidget(self.scroll_area, 1)

        # 添加OverlayWidget
        self.overlay = OverlayWidget(self.image_label)
        self.image_label.installEventFilter(self)

    # 新增：自适应模式相关方法
    def set_fit_mode(self, mode):
        """设置自适应模式并重新显示页面"""
        self.fit_mode = mode
        self.show_page()  # 重新显示页面应用新模式

    def zoom_in(self):
        """放大PDF页面"""
        self.fit_mode = "manual"  # 切换到手动缩放模式
        self.scale_factor *= 1.2
        self.show_page()

    def zoom_out(self):
        """缩小PDF页面"""
        self.fit_mode = "manual"  # 切换到手动缩放模式
        self.scale_factor /= 1.2
        if self.scale_factor < 0.1:  # 限制最小缩放
            self.scale_factor = 0.1
        self.show_page()

    def calculate_scale_factor(self):
        """根据当前模式计算缩放因子"""
        if not self.original_size[0] or not self.original_size[1]:
            return 1.0

        if self.fit_mode == "fit_width":
            # 适应宽度
            viewport_width = self.scroll_area.viewport().width()
            return viewport_width / self.original_size[0] if self.original_size[0] > 0 else 1.0

        elif self.fit_mode == "fit_window":
            # 适应窗口（保持比例）
            viewport_width = self.scroll_area.viewport().width()
            viewport_height = self.scroll_area.viewport().height()

            width_ratio = viewport_width / self.original_size[0]
            height_ratio = viewport_height / self.original_size[1]

            return min(width_ratio, height_ratio)

        elif self.fit_mode == "actual_size":
            # 实际大小
            return 1.0

        else:  # manual
            # 手动缩放，保持当前缩放因子
            return self.scale_factor

    # 修改：重写resizeEvent方法
    def resizeEvent(self, event):
        """窗口大小变化时重新计算缩放"""
        super().resizeEvent(event)
        if hasattr(self, 'overlay'):
            self.overlay.setGeometry(0, 0, self.image_label.width(), self.image_label.height())

        # 当窗口大小改变且不是手动缩放模式时，重新计算缩放
        self.show_page()

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
        info(f"PDF页面上的识别框被点击，正在联动右侧文本区选中第{index + 1}行")
        # OCR联动
        if hasattr(self, 'ocr_tab') and self.ocr_tab and hasattr(self.ocr_tab, 'set_selection_from_pdf'):
            self.ocr_tab.set_selection_from_pdf(index)
        # 校对联动
        if hasattr(self, 'proofread_tab') and self.proofread_tab and hasattr(self.proofread_tab, 'set_selection_from_pdf'):
            self.proofread_tab.set_selection_from_pdf(index)

    def open_settings(self):
        """
        打开“更多设置”对话框。
        """
        dialog = SettingsDialog(self)
        dialog.exec()

    def auto_load_default_pdf(self):
        """
        自动加载上次文件
        :return:
        """
        if self.config.last_open_file and os.path.exists(self.config.last_open_file):
            info(f"自动加载上次文件: {self.config.last_open_file}, 页码: {self.config.last_open_page}")
            self.load_pdf(self.config.last_open_file, self.config.last_open_page)
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
            self.pdf_doc = pypdfium2.PdfDocument(file_path)
            self.config.last_open_file = file_path
            if page_num is not None and 0 <= page_num < len(self.pdf_doc):
                self.config.last_open_page = page_num
            else:
                self.config.last_open_page = 0
            self.page_edit.setText(str(self.config.last_open_page + 1))
            self.page_label.setText(f"/ {len(self.pdf_doc)}")
            self.file_changed.emit(file_path)
            self.show_page()
            info(f"PDF加载成功: {file_path}, 当前页: {self.config.last_open_page}")
        except Exception as e:
            error(f"PDF加载失败: {file_path}, 错误: {e}")

    def get_pdf_doc(self):
        """
        获取当前PDF文档对象。
        :return: pypdfium2.PdfDocument
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
        获取缩放后的OCR框坐标信息
        关键改进：将原始OCR坐标按当前缩放因子进行转换
        """
        boxes = list(zip(ocr_data['rec_polys'], ocr_data['rec_texts']))
        # 需要根据当前缩放调整坐标（如果有缩放功能，则需要调整）
        scaled_boxes = []

        # 根据当前缩放因子调整OCR框坐标
        for poly, text in boxes:
            scaled_poly = [
                [x * self.scale_factor, y * self.scale_factor]
                for x, y in poly
            ]
            scaled_boxes.append((scaled_poly, text))

        return scaled_boxes

    def hide_ocr_boxes(self):
        """
        隐藏所有OCR识别框。
        """
        self.overlay.clear_ocr_boxes()

    def show_page(self):
        """
        显示当前页PDF图片，支持自适应缩放。
        """
        if not self.pdf_doc:
            return

        page = self.pdf_doc.get_page(self.config.last_open_page)
        pil_image = page.render(scale=1).to_pil()

        # 保存原始尺寸
        self.original_size = (pil_image.width, pil_image.height)

        # 计算缩放因子
        self.scale_factor = self.calculate_scale_factor()

        # 应用缩放
        scaled_width = int(pil_image.width * self.scale_factor)
        scaled_height = int(pil_image.height * self.scale_factor)

        # 转换为Qt图像并缩放
        img = ImageQt.ImageQt(pil_image)
        pixmap = QPixmap.fromImage(img)
        scaled_pixmap = pixmap.scaled(
            scaled_width, scaled_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        # 更新显示
        self.image_label.setPixmap(scaled_pixmap)
        self.image_label.setFixedSize(scaled_width, scaled_height)
        self.page_edit.setText(str(self.config.last_open_page + 1))
        self.page_label.setText(f"/ {len(self.pdf_doc)}")

        # 更新覆盖层大小
        self.overlay.setGeometry(0, 0, scaled_width, scaled_height)

        # 重新显示OCR框（如果有）
        page_data = GlobalState.get_pdf_page_data()
        if page_data and "ocr" in page_data:
            self.show_ocr_boxes(page_data["ocr"])
        else:
            self.hide_ocr_boxes()

        self.page_changed.emit(self.config.last_open_page)
        info(f"PDF显示大小: {scaled_width}x{scaled_height}, 缩放因子: {self.scale_factor:.2f}")

    def prev_page(self):
        """
        跳转到上一页。
        """
        if self.pdf_doc and self.config.last_open_page > 0:
            self.config.last_open_page -= 1
            self.show_page()

    def next_page(self):
        """
        跳转到下一页。
        """
        if self.pdf_doc and self.config.last_open_page < len(self.pdf_doc) - 1:
            self.config.last_open_page += 1
            self.show_page()

    def goto_page(self):
        """
        跳转到指定页码。
        """
        if not self.pdf_doc:
            return
        try:
            page = int(self.page_edit.text()) - 1
            if 0 <= page < len(self.pdf_doc):
                self.config.last_open_page = page
                self.show_page()
        except ValueError:
            pass

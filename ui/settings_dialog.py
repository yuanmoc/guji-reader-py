import sys

from PySide6.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QLineEdit, QPushButton, QFileDialog, QMessageBox, \
    QLabel, QHBoxLayout, QTextEdit, QTabWidget, QWidget, QGroupBox, QApplication
from PySide6.QtCore import Qt, QProcess
from core.config_manager import AppConfig
from core.global_state import GlobalState
from PySide6.QtWidgets import QCheckBox, QComboBox
from PySide6.QtGui import QFont

from core.ocr_client import OcrClient
from core.openai_client import OpenAIClient
from core.utils.logger import info, warning


class SettingsDialog(QDialog):
    """
    应用“更多设置”弹窗对话框。
    支持基础参数、OCR、自动标点、白话文、古文解释等多标签页配置，支持配置保存。
    """

    def __init__(self, parent=None):
        """
        构造函数，初始化设置对话框。
        :param parent: 父窗口
        """
        super().__init__(parent)
        self.setWindowTitle("更多设置")
        self.resize(800, 600)
        self.config_manager = GlobalState.config_manager
        self.init_ui()
        self.load_config()

    def init_ui(self):
        """
        初始化界面布局，创建各标签页和保存按钮。
        """
        layout = QVBoxLayout(self)
        # 创建标签页
        tab_widget = QTabWidget()
        # 基础设置标签页
        basic_tab = self.create_basic_tab()
        tab_widget.addTab(basic_tab, "基础设置")
        # OCR配置标签页
        ocr_tab = self.create_ocr_tab()
        tab_widget.addTab(ocr_tab, "OCR配置")
        # 自动标点和分段设置标签页
        punctuate_tab = self.create_punctuate_tab()
        tab_widget.addTab(punctuate_tab, "自动标点和分段")
        # 白话文转换设置标签页
        vernacular_tab = self.create_vernacular_tab()
        tab_widget.addTab(vernacular_tab, "白话文转换")
        # 古文解释设置标签页
        explain_tab = self.create_explain_tab()
        tab_widget.addTab(explain_tab, "古文解释")
        layout.addWidget(tab_widget, 1)  # 添加拉伸因子
        self.save_btn = QPushButton("保存配置")
        self.save_btn.clicked.connect(self.save_config)
        layout.addWidget(self.save_btn)

    def create_basic_tab(self):
        """
        创建基础设置标签页，包括Base URL、API Key、模型名、存储路径。
        :return: QWidget
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)
        # 创建表单布局
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.base_url_edit = QLineEdit()
        self.api_key_edit = QLineEdit()
        self.model_name_edit = QLineEdit()
        self.storage_path_edit = QLineEdit()
        self.storage_path_edit.setReadOnly(True)
        self.storage_btn = QPushButton("选择路径")
        self.storage_btn.clicked.connect(self.choose_storage_path)
        storage_layout = QHBoxLayout()
        storage_layout.addWidget(self.storage_path_edit, 1)
        storage_layout.addWidget(self.storage_btn)
        form.addRow(QLabel("大模型Base URL:"), self.base_url_edit)
        form.addRow(QLabel("OPENAI_API_KEY:"), self.api_key_edit)
        form.addRow(QLabel("默认模型名称:"), self.model_name_edit)
        form.addRow(QLabel("数据存储位置:"), storage_layout)
        layout.addLayout(form, 1)
        return widget

    def create_ocr_tab(self):
        """
        创建OCR配置标签页，支持各OCR模型路径、名称、参数设置。
        :return: QWidget
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        # 文件选择器
        self.doc_unwarping_model_dir_edit = QLineEdit()
        self.doc_unwarping_model_dir_btn = QPushButton("选择文件夹")
        self.doc_unwarping_model_dir_btn.clicked.connect(lambda: self.choose_folder(self.doc_unwarping_model_dir_edit))
        file_layout1 = QHBoxLayout()
        file_layout1.addWidget(self.doc_unwarping_model_dir_edit, 1)
        file_layout1.addWidget(self.doc_unwarping_model_dir_btn)
        self.doc_unwarping_model_name_edit = QLineEdit()

        self.textline_orientation_model_dir_edit = QLineEdit()
        self.textline_orientation_model_dir_btn = QPushButton("选择文件夹")
        self.textline_orientation_model_dir_btn.clicked.connect(
            lambda: self.choose_folder(self.textline_orientation_model_dir_edit))
        file_layout2 = QHBoxLayout()
        file_layout2.addWidget(self.textline_orientation_model_dir_edit, 1)
        file_layout2.addWidget(self.textline_orientation_model_dir_btn)
        self.textline_orientation_model_name_edit = QLineEdit()

        self.text_detection_model_dir_edit = QLineEdit()
        self.text_detection_model_dir_btn = QPushButton("选择文件夹")
        self.text_detection_model_dir_btn.clicked.connect(
            lambda: self.choose_folder(self.text_detection_model_dir_edit))
        file_layout3 = QHBoxLayout()
        file_layout3.addWidget(self.text_detection_model_dir_edit, 1)
        file_layout3.addWidget(self.text_detection_model_dir_btn)
        self.text_detection_model_name_edit = QLineEdit()

        self.text_recognition_model_dir_edit = QLineEdit()
        self.text_recognition_model_dir_btn = QPushButton("选择文件夹")
        self.text_recognition_model_dir_btn.clicked.connect(
            lambda: self.choose_folder(self.text_recognition_model_dir_edit))
        file_layout4 = QHBoxLayout()
        file_layout4.addWidget(self.text_recognition_model_dir_edit, 1)
        file_layout4.addWidget(self.text_recognition_model_dir_btn)
        self.text_recognition_model_name_edit = QLineEdit()

        # 文本图像矫正模块分组
        group1 = QGroupBox("文本图像矫正模块（默认会先使用本地模型）")
        group1_layout = QFormLayout()
        group1_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        group1_layout.addRow(QLabel("模型位置:"), file_layout1)
        name_layout1 = QHBoxLayout()
        name_layout1.addWidget(self.doc_unwarping_model_name_edit)
        help_label1 = QLabel(
            '<a href="https://paddlepaddle.github.io/PaddleOCR/main/version3.x/module_usage/text_image_unwarping.html">使用说明</a>')
        help_label1.setOpenExternalLinks(True)
        name_layout1.addWidget(help_label1)
        group1_layout.addRow(QLabel("模型名称:"), name_layout1)
        # 新增：模型名称推荐（数组+循环）
        model_names1 = ["UVDoc"]
        self.set_model_name(group1_layout, model_names1, self.doc_unwarping_model_name_edit,
                            self.doc_unwarping_model_dir_edit)
        group1.setLayout(group1_layout)

        # 文本行方向分类模块分组
        group2 = QGroupBox("文本行方向分类模块（默认会先使用本地模型）")
        group2_layout = QFormLayout()
        group2_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        group2_layout.addRow(QLabel("模型位置:"), file_layout2)
        name_layout2 = QHBoxLayout()
        name_layout2.addWidget(self.textline_orientation_model_name_edit)
        help_label2 = QLabel(
            '<a href="https://paddlepaddle.github.io/PaddleOCR/main/version3.x/module_usage/textline_orientation_classification.html">使用说明</a>')
        help_label2.setOpenExternalLinks(True)
        name_layout2.addWidget(help_label2)
        group2_layout.addRow(QLabel("模型名称:"), name_layout2)
        # 新增：模型名称推荐（数组+循环）
        model_names2 = ["PP-LCNet_x0_25_textline_ori", "PP-LCNet_x1_0_textline_ori"]
        self.set_model_name(group2_layout, model_names2, self.textline_orientation_model_name_edit,
                            self.textline_orientation_model_dir_edit)
        group2.setLayout(group2_layout)

        # 文本检测模块分组
        group3 = QGroupBox("文本检测模块（默认会先使用本地模型）")
        group3_layout = QFormLayout()
        group3_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        group3_layout.addRow(QLabel("模型位置:"), file_layout3)
        name_layout3 = QHBoxLayout()
        name_layout3.addWidget(self.text_detection_model_name_edit)
        help_label3 = QLabel(
            '<a href="https://paddlepaddle.github.io/PaddleOCR/main/version3.x/module_usage/text_detection.html">使用说明</a>')
        help_label3.setOpenExternalLinks(True)
        name_layout3.addWidget(help_label3)
        group3_layout.addRow(QLabel("模型名称:"), name_layout3)
        # 新增：模型名称推荐（数组+循环）
        model_names3 = ["PP-OCRv5_server_det", "PP-OCRv5_mobile_det", "PP-OCRv4_server_det", "PP-OCRv4_mobile_det"]
        self.set_model_name(group3_layout, model_names3, self.text_detection_model_name_edit,
                            self.text_detection_model_dir_edit)
        group3.setLayout(group3_layout)

        # 文本识别模块分组
        group4 = QGroupBox("文本识别模块（默认会先使用本地模型）")
        group4_layout = QFormLayout()
        group4_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        group4_layout.addRow(QLabel("模型位置:"), file_layout4)
        name_layout4 = QHBoxLayout()
        name_layout4.addWidget(self.text_recognition_model_name_edit)
        help_label4 = QLabel(
            '<a href="https://paddlepaddle.github.io/PaddleOCR/main/version3.x/module_usage/text_recognition.html">使用说明</a>')
        help_label4.setOpenExternalLinks(True)
        name_layout4.addWidget(help_label4)
        group4_layout.addRow(QLabel("模型名称:"), name_layout4)
        # 新增：模型名称推荐（数组+循环）
        model_names4 = ["PP-OCRv5_server_rec", "PP-OCRv5_mobile_rec", "PP-OCRv4_server_rec_doc", "PP-OCRv4_mobile_rec",
                        "PP-OCRv4_server_rec", "en_PP-OCRv4_mobile_rec"]
        self.set_model_name(group4_layout, model_names4, self.text_recognition_model_name_edit,
                            self.text_recognition_model_dir_edit)
        group4.setLayout(group4_layout)

        # 文本图像矫正、方向分类、检测、识别模块用Tab标签页显示，节约空间
        ocr_module_tab = QTabWidget()
        ocr_module_tab.addTab(group1, "文本图像矫正")
        ocr_module_tab.addTab(group2, "文本方向分类")
        ocr_module_tab.addTab(group3, "文本检测")
        ocr_module_tab.addTab(group4, "文本识别")
        layout.addWidget(ocr_module_tab)

        # 其余参数继续用form
        # 是否选择器
        self.use_doc_unwarping_edit = QCheckBox()
        self.use_doc_unwarping_edit.setEnabled(False)
        self.use_textline_orientation_edit = QCheckBox()

        # 下拉选择器
        self.text_det_limit_type_edit = QComboBox()
        self.text_det_limit_type_edit.addItems(["短边", "长边"])
        # 设置显示文本和实际值的映射
        self.text_det_limit_type_edit.setItemData(0, "min")
        self.text_det_limit_type_edit.setItemData(1, "max")

        self.text_det_limit_side_len_edit = QLineEdit()
        self.text_det_thresh_edit = QLineEdit()
        self.text_det_box_thresh_edit = QLineEdit()
        self.text_det_unclip_ratio_edit = QLineEdit()
        self.text_rec_score_thresh_edit = QLineEdit()

        # 说明label样式
        desc_font = QFont()
        desc_font.setPointSize(12)
        desc_color = "color: #888888;"

        # 说明文本
        desc_use_doc_unwarping = QLabel("不支持使用文档扭曲矫正模块，请先使用第三方工具处理")
        desc_use_doc_unwarping.setFont(desc_font)
        desc_use_doc_unwarping.setStyleSheet(desc_color)
        desc_limit_type = QLabel(
            "【短边】表示保证图像最短边不小于【文本检测的图像边长限制】，【长边】表示保证图像最长边不大于【文本检测的图像边长限制】。")
        desc_limit_type.setFont(desc_font)
        desc_limit_type.setStyleSheet(desc_color)
        desc_limit_side_len = QLabel(
            "对于文本检测输入图像的边长限制，对于尺寸较大文本密集的图像，如果希望更精准的识别，应选用更大的尺寸，该参数与【文本检测的图像边长限制类型】\n配合使用。一般最大【长边】适合图像文字较大的场景，最小【短边】适合图像文字小且密集的文档场景使用。")
        desc_limit_side_len.setFont(desc_font)
        desc_limit_side_len.setStyleSheet(desc_color)
        desc_det_thresh = QLabel("输出的概率图中，得分大于该阈值的像素点才会被认为是文字像素点，取值范围为0~1。")
        desc_det_thresh.setFont(desc_font)
        desc_det_thresh.setStyleSheet(desc_color)
        desc_box_thresh = QLabel(
            "检测结果边框内，所有像素点的平均得分大于该阈值时，该结果会被认为是文字区域，取值范围为0~1。如果出现漏检，可以适当调低该值。")
        desc_box_thresh.setFont(desc_font)
        desc_box_thresh.setStyleSheet(desc_color)
        desc_unclip_ratio = QLabel("使用该方法对文字区域进行扩张，该值越大，扩张的面积越大。")
        desc_unclip_ratio.setFont(desc_font)
        desc_unclip_ratio.setStyleSheet(desc_color)
        desc_rec_score_thresh = QLabel("文本检测后的文本框进行文本识别，得分大于该阈值的文本结果会被保留，取值范围为0~1。")
        desc_rec_score_thresh.setFont(desc_font)
        desc_rec_score_thresh.setStyleSheet(desc_color)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.addRow(QLabel("使用文档扭曲矫正模块:"), self.use_doc_unwarping_edit)
        form.addRow(desc_use_doc_unwarping)
        form.addRow(QLabel("使用文本行方向分类模块:"), self.use_textline_orientation_edit)
        form.addRow(QLabel("文本检测的图像边长限制类型:"), self.text_det_limit_type_edit)
        form.addRow(desc_limit_type)
        form.addRow(QLabel("文本检测的图像边长限制(默认736):"), self.text_det_limit_side_len_edit)
        form.addRow(desc_limit_side_len)
        form.addRow(QLabel("文本检测像素阈值(默认0.30):"), self.text_det_thresh_edit)
        form.addRow(desc_det_thresh)
        form.addRow(QLabel("文本检测框阈值(默认0.60):"), self.text_det_box_thresh_edit)
        form.addRow(desc_box_thresh)
        form.addRow(QLabel("文本检测扩张系数(默认1.50):"), self.text_det_unclip_ratio_edit)
        form.addRow(desc_unclip_ratio)
        form.addRow(QLabel("文本识别阈值(默认0.00):"), self.text_rec_score_thresh_edit)
        form.addRow(desc_rec_score_thresh)

        layout.addLayout(form, 1)
        return widget

    def set_model_name(self, group_layout, model_names, label_edit, dir_name_edit):
        model_names_layout = QHBoxLayout()
        for name in model_names:
            label = QLabel(f'<a href="#">{name}</a>')
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
            label.setOpenExternalLinks(False)
            # 绑定点击事件，使用默认参数避免闭包问题
            label.linkActivated.connect(lambda _, n=name: (label_edit.setText(n), dir_name_edit.clear()))
            model_names_layout.addWidget(label)
        group_layout.addRow(QLabel(""), model_names_layout)

    def create_punctuate_tab(self):
        """
        创建自动标点和分段设置标签页。
        :return: QWidget
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        self.punctuate_model_edit = QLineEdit()
        self.punctuate_model_edit.setPlaceholderText("留空则使用默认模型")
        self.punctuate_system_prompt_edit = QTextEdit()

        form.addRow(QLabel("模型名称:"), self.punctuate_model_edit)
        form.addRow(QLabel("系统提示词:"), self.punctuate_system_prompt_edit)

        layout.addLayout(form, 1)  # 添加拉伸因子
        return widget

    def create_vernacular_tab(self):
        """
        创建白话文转换设置标签页。
        :return: QWidget
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        self.vernacular_model_edit = QLineEdit()
        self.vernacular_model_edit.setPlaceholderText("留空则使用默认模型")
        self.vernacular_system_prompt_edit = QTextEdit()

        form.addRow(QLabel("模型名称:"), self.vernacular_model_edit)
        form.addRow(QLabel("系统提示词:"), self.vernacular_system_prompt_edit)

        layout.addLayout(form, 1)  # 添加拉伸因子
        return widget

    def create_explain_tab(self):
        """
        创建古文解释设置标签页。
        :return: QWidget
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        self.explain_model_edit = QLineEdit()
        self.explain_model_edit.setPlaceholderText("留空则使用默认模型")
        self.explain_system_prompt_edit = QTextEdit()

        form.addRow(QLabel("模型名称:"), self.explain_model_edit)
        form.addRow(QLabel("系统提示词:"), self.explain_system_prompt_edit)

        layout.addLayout(form, 1)  # 添加拉伸因子
        return widget

    def choose_folder(self, line_edit):
        """
        弹出文件夹选择对话框，设置目标输入框内容。
        :param line_edit: QLineEdit控件
        """
        path = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if path:
            line_edit.setText(path)
            info(f"用户选择模型文件夹: {path}")

    def load_config(self):
        """
        加载当前配置到界面。
        """
        config = self.config_manager.config
        info("加载设置对话框配置")
        self.base_url_edit.setText(config.base_url)
        self.api_key_edit.setText(config.api_key)
        self.model_name_edit.setText(config.model_name)
        self.storage_path_edit.setText(config.storage_dir)

        # 加载OCR配置
        self.doc_unwarping_model_dir_edit.setText(config.doc_unwarping_model_dir)
        self.doc_unwarping_model_name_edit.setText(config.doc_unwarping_model_name)
        self.textline_orientation_model_dir_edit.setText(config.textline_orientation_model_dir)
        self.textline_orientation_model_name_edit.setText(config.textline_orientation_model_name)
        self.text_detection_model_dir_edit.setText(config.text_detection_model_dir)
        self.text_detection_model_name_edit.setText(config.text_detection_model_name)
        self.text_recognition_model_dir_edit.setText(config.text_recognition_model_dir)
        self.text_recognition_model_name_edit.setText(config.text_recognition_model_name)
        self.use_doc_unwarping_edit.setChecked(config.use_doc_unwarping)
        self.use_textline_orientation_edit.setChecked(config.use_textline_orientation)
        # 根据配置值设置下拉框
        if config.text_det_limit_type == "min":
            self.text_det_limit_type_edit.setCurrentIndex(0)
        elif config.text_det_limit_type == "max":
            self.text_det_limit_type_edit.setCurrentIndex(1)
        else:
            self.text_det_limit_type_edit.setCurrentIndex(1)  # 默认长边
        self.text_det_limit_side_len_edit.setText(str(config.text_det_limit_side_len))
        self.text_det_thresh_edit.setText(str(config.text_det_thresh))
        self.text_det_box_thresh_edit.setText(str(config.text_det_box_thresh))
        self.text_det_unclip_ratio_edit.setText(str(config.text_det_unclip_ratio))
        self.text_rec_score_thresh_edit.setText(str(config.text_rec_score_thresh))

        # 加载功能特定配置
        self.punctuate_model_edit.setText(config.punctuate_model_name)
        self.punctuate_system_prompt_edit.setText(config.punctuate_system_prompt)

        self.vernacular_model_edit.setText(config.vernacular_model_name)
        self.vernacular_system_prompt_edit.setText(config.vernacular_system_prompt)

        self.explain_model_edit.setText(config.explain_model_name)
        self.explain_system_prompt_edit.setText(config.explain_system_prompt)

    def choose_storage_path(self):
        """
        弹出文件夹选择对话框，设置存储路径。
        """
        path = QFileDialog.getExistingDirectory(self, "选择数据存储位置")
        if path:
            self.storage_path_edit.setText(path)
            info(f"用户选择数据存储路径: {path}")

    def save_config(self):
        """
        保存界面配置到全局配置。
        """
        # 从UI收集配置数据
        new_config = AppConfig(
            base_url=self.base_url_edit.text().strip(),
            api_key=self.api_key_edit.text().strip(),
            model_name=self.model_name_edit.text().strip(),
            storage_dir=self.storage_path_edit.text().strip(),
            # OCR配置
            doc_unwarping_model_dir=self.doc_unwarping_model_dir_edit.text().strip(),
            doc_unwarping_model_name=self.doc_unwarping_model_name_edit.text().strip(),
            textline_orientation_model_dir=self.textline_orientation_model_dir_edit.text().strip(),
            textline_orientation_model_name=self.textline_orientation_model_name_edit.text().strip(),
            text_detection_model_dir=self.text_detection_model_dir_edit.text().strip(),
            text_detection_model_name=self.text_detection_model_name_edit.text().strip(),
            text_recognition_model_dir=self.text_recognition_model_dir_edit.text().strip(),
            text_recognition_model_name=self.text_recognition_model_name_edit.text().strip(),
            use_doc_unwarping=self.use_doc_unwarping_edit.isChecked(),
            use_textline_orientation=self.use_textline_orientation_edit.isChecked(),
            text_det_limit_type=self.text_det_limit_type_edit.currentData(),
            text_det_limit_side_len=int(self.text_det_limit_side_len_edit.text().strip() or 736),
            text_det_thresh=float(self.text_det_thresh_edit.text().strip() or 0.3),
            text_det_box_thresh=float(self.text_det_box_thresh_edit.text().strip() or 0.6),
            text_det_unclip_ratio=float(self.text_det_unclip_ratio_edit.text().strip() or 1.5),
            text_rec_score_thresh=float(self.text_rec_score_thresh_edit.text().strip() or 0.0),
            # 其他配置
            punctuate_model_name=self.punctuate_model_edit.text().strip(),
            punctuate_system_prompt=self.punctuate_system_prompt_edit.toPlainText().strip(),
            vernacular_model_name=self.vernacular_model_edit.text().strip(),
            vernacular_system_prompt=self.vernacular_system_prompt_edit.toPlainText().strip(),
            explain_model_name=self.explain_model_edit.text().strip(),
            explain_system_prompt=self.explain_system_prompt_edit.toPlainText().strip()
        )
        # 检查OCR相关字段是否有变化
        old_config = self.config_manager.config
        ocr_fields = [
            'doc_unwarping_model_dir', 'doc_unwarping_model_name',
            'textline_orientation_model_dir', 'textline_orientation_model_name',
            'text_detection_model_dir', 'text_detection_model_name',
            'text_recognition_model_dir', 'text_recognition_model_name',
            'use_doc_unwarping', 'use_textline_orientation',
            'text_det_limit_type', 'text_det_limit_side_len',
            'text_det_thresh', 'text_det_box_thresh',
            'text_det_unclip_ratio', 'text_rec_score_thresh'
        ]
        ocr_changed = any(getattr(new_config, f) != getattr(old_config, f) for f in ocr_fields)
        # 通过配置管理器更新配置
        success, message = self.config_manager.update_config(new_config)

        if success:
            info("设置已保存，配置已更新")
            OpenAIClient().init_client()
            if ocr_changed:
                reply = QMessageBox.question(self, "提示",
                                             "检测到OCR相关参数已修改，需重启应用以使新配置生效。是否立即重启应用？",
                                             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.Yes:
                    app_path = sys.executable
                    args = sys.argv
                    QProcess.startDetached(app_path, args)
                    QApplication.quit()
                    return
            self.accept()
        else:
            warning(f"设置保存失败: {message}")
            QMessageBox.warning(self, "错误", message)

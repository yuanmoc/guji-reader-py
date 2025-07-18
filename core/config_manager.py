import json
import os
import re
import shutil
from typing import Callable
from dataclasses import dataclass, asdict
from core.utils.logger import info, warning, error
from core.utils.path_util import get_user_store_path


@dataclass
class AppConfig:
    """
    应用配置数据类。
    用于存储和管理应用的所有配置信息，包括大模型、OCR、自动标点、白话文、古文解释等参数。
    """
    base_url: str = ""
    api_key: str = ""
    model_name: str = ""
    storage_dir: str = "ocr_results"
    
    # OCR配置
    doc_unwarping_model_dir: str = ""
    doc_unwarping_model_name: str = "UVDoc"
    textline_orientation_model_dir: str = ""
    textline_orientation_model_name: str = "PP-LCNet_x0_25_textline_ori"
    text_detection_model_dir: str = ""
    text_detection_model_name: str = "PP-OCRv5_server_det"
    text_recognition_model_dir: str = ""
    text_recognition_model_name: str = "PP-OCRv5_server_rec"
    use_doc_unwarping: bool = False
    use_textline_orientation: bool = True
    text_det_limit_type: str = "max"
    text_det_limit_side_len: int = 736
    text_det_thresh: float = 0.3
    text_det_box_thresh: float = 0.6
    text_det_unclip_ratio: float = 1.5
    text_rec_score_thresh: float = 0.000
    
    # 自动标点和分段配置
    punctuate_model_name: str = ""
    punctuate_system_prompt: str = """任务：为无标点/标点不规范古籍文本添加符合古代汉语规范的标点，并按逻辑分段。
要求：
处理范围：只处理用户输入内容，不要联想其他无关内容。
标点：依虚词（如“也”“矣”后加句号）、句式（并列用逗号，转折用分号）、对话（“曰”后加引号）规范添加，禁现代口语断句。
分段：按叙事阶段、议论层次或诗词韵律转换分段，主题变则分段。
特殊：异体字保留原字并括号标通用字（如“蚤（早）”）；歧义处括号注依据（如“‘之’代前文‘书’，故断此”）；缺字用“□”，缺句标“[缺]”。
输出：仅标点分段后文本，段落空行分隔，无额外内容。"""

    # 白话文转换配置
    vernacular_model_name: str = ""
    vernacular_system_prompt: str = """任务：将古籍准确译为现代汉语，兼顾忠实与通顺。
要求：
处理范围：只处理用户输入内容，不要联想其他无关内容。
准确：古今异义（如“妻子”=妻+子）、多义词（如“走”=跑）按文意选释；倒装句（“何陋之有”→“有何简陋？”）调序，省略补全（“（村人）问所从来”）。
通顺：长句拆短（“一鼓作气，再而衰”→“首鼓振气，次鼓弱，三鼓竭”）；文化词（“太守”）补说明（“汉郡行政长官”）。
输出：仅白话文译文，保留原文段落，无注释。"""
    
    # 古文解释配置
    explain_model_name: str = ""
    explain_system_prompt: str = """任务：解析古籍字词、句式、逻辑及背景，助深入理解。
要求：
字词：实词（本义+引申+例证，如“兵”=兵器→士兵→军事，《论语》“务本”中“务”=致力）；虚词（分类功能，如“之”=的/取消独立/宾前标志）。
句式：判断句（“……者……也”表肯定）、被动句（“为……所……”）、省略句（“（沛公）军霸上”），说明表达效果。
背景：关联历史事件（如《过秦论》补“秦速亡教训”）、制度（“科举”=隋唐至明清选官制）、习俗（“冠礼”=男子二十成年礼）。
争议：列不同观点（如“‘川’指黄河/泛河”）并注依据（如“王引之《经义述闻》”）。
输出：按“字词-句式-逻辑-背景-争议”顺序解析，无额外格式。"""
    # 新增：最近打开的文件和页码
    last_open_file: str = ""
    last_open_page: int = 0
    
    def validate(self) -> tuple[bool, str]:
        """
        验证配置的有效性。
        :return: (bool, str) 是否有效及错误信息
        """
        if self.base_url and not self._is_valid_url(self.base_url):
            return False, "Base URL 格式不正确"
        return True, ""
    
    def _is_valid_url(self, url: str) -> bool:
        """
        验证URL格式。
        :param url: 待验证的URL字符串
        :return: bool 是否为合法URL
        """
        url_pattern = re.compile(r"^https?://[\w\-\.]+(:\d+)?(/.*)?$")
        return bool(url_pattern.match(url))

class ConfigManager:
    """
    配置管理器。
    负责加载、保存、更新应用配置。
    单例实现，确保全局唯一。
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        super().__init__()
        self.config_path = os.path.join(get_user_store_path("config.json"))
        self._config = AppConfig()
        self._config_listeners: list[Callable[[AppConfig], None]] = []
        self._initialized = True
        # 如果用户下有模型文件则默认添加到配置中
        self.model_config_fields = [
            ("doc_unwarping_model_dir", "doc_unwarping_model_name"),
            ("text_detection_model_dir", "text_detection_model_name"),
            ("text_recognition_model_dir", "text_recognition_model_name"),
            ("textline_orientation_model_dir", "textline_orientation_model_name")
        ]
        self.openai_config_fields = ["base_url", "api_key", "model_name"]
        self._load_config()
    
    @property
    def config(self) -> AppConfig:
        """
        获取当前配置对象。
        :return: AppConfig实例
        """
        return self._config
    
    def _load_config(self):
        """
        从文件加载配置。
        文件不存在时自动创建默认配置。
        """
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    config_data = json.load(f)
                    self._config = AppConfig(**config_data)
                info(f"加载配置文件成功: {self.config_path}")
            except Exception as e:
                error(f"加载配置文件失败: {e}")
                self._config = AppConfig()
        else:
            # 设置默认存储目录
            self._config.storage_dir = get_user_store_path("ocr_results")
            self.do_save_config()
            info("未找到配置文件，已创建默认配置")

        # paddlex 模型默认下载地址
        paddlex_models_path = os.path.join(os.path.expanduser("~"), ".paddlex", "official_models")
        for dir_attr, name_attr in self.model_config_fields:
            model_dir = getattr(self._config, dir_attr)
            model_name = getattr(self._config, name_attr)
            if not model_dir:
                model_path = os.path.join(paddlex_models_path, model_name)
                if os.path.exists(model_path):
                    setattr(self._config, dir_attr, model_path)
            else:
                if not os.path.exists(model_dir):
                    setattr(self._config, dir_attr, '')

    def do_save_config(self):
        """
        真正执行写入磁盘操作。
        """
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(asdict(self._config), f, ensure_ascii=False, indent=2)
            info(f"保存配置文件成功: {self.config_path}")
        except Exception as e:
            error(f"保存配置文件失败: {e}")
    
    def update_config(self, new_config: AppConfig) -> tuple[bool, str]:
        """
        更新配置。
        :param new_config: 新AppConfig对象
        :return: (bool, str) 是否成功及消息
        """
        # 验证新配置
        is_valid, error_msg = new_config.validate()
        if not is_valid:
            warning(f"配置验证失败: {error_msg}")
            return False, error_msg
        
        # 检查存储目录变更
        if new_config.storage_dir != self._config.storage_dir:
            success, msg = self._handle_storage_dir_change(new_config.storage_dir)
            if not success:
                error(f"存储目录变更失败: {msg}")
                return False, msg
        
        # 更新配置
        self._config = new_config
        self.do_save_config()
        
        return True, "配置更新成功"
    
    def _handle_storage_dir_change(self, new_storage_dir: str) -> tuple[bool, str]:
        """
        处理存储目录变更。
        如有需要可在此处实现数据迁移。
        :param new_storage_dir: 新目录
        :return: (bool, str) 是否成功及消息
        """
        try:
            # 确保新目录存在
            if not os.path.exists(new_storage_dir):
                return False, "选择目录不存在"
            # 如果旧目录存在且有数据，可以选择迁移
            old_storage_dir = self._config.storage_dir
            if os.path.exists(old_storage_dir) and os.listdir(old_storage_dir):
                # 这里可以添加数据迁移逻辑
                shutil.move(old_storage_dir, new_storage_dir)

            info(f"存储目录变更为: {new_storage_dir}")
            return True, ""
        except Exception as e:
            error(f"创建存储目录失败: {e}")
            return False, f"创建存储目录失败: {e}"
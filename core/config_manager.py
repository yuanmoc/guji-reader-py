import json
import os
import re
from typing import Dict, Any, Callable
from dataclasses import dataclass, asdict
from PySide6.QtCore import QObject, Signal, QTimer
from core.utils.logger import info, warning, error

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

class ConfigManager(QObject):
    """
    配置管理器。
    负责加载、保存、更新应用配置，并支持配置变更信号和监听器。
    单例实现，确保全局唯一。
    """
    
    # 配置变更信号
    config_changed = Signal(AppConfig)
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, config_path: str = "config.json"):
        if hasattr(self, '_initialized'):
            return
        super().__init__()
        self.config_path = config_path
        self._config = AppConfig()
        self._config_listeners: list[Callable[[AppConfig], None]] = []
        self._initialized = True
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._do_save_config)
        self._pending_save = False
        self._load_config()
    
    @property
    def config(self) -> AppConfig:
        """
        获取当前配置对象。
        :return: AppConfig实例
        """
        return self._config

    def add_config_listener(self, listener: Callable[[AppConfig], None]):
        """
        添加配置变更监听器。
        :param listener: 回调函数，参数为AppConfig
        """
        if listener not in self._config_listeners:
            self._config_listeners.append(listener)

    def remove_config_listener(self, listener: Callable[[AppConfig], None]):
        """
        移除配置变更监听器。
        :param listener: 回调函数
        """
        if listener in self._config_listeners:
            self._config_listeners.remove(listener)

    def _notify_listeners(self, config: AppConfig):
        """
        通知所有监听器配置已变更。
        :param config: 最新AppConfig
        """
        for listener in self._config_listeners:
            try:
                listener(config)
            except Exception as e:
                warning(f"配置监听器执行失败: {e}")
    
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
            self._config.storage_dir = os.path.join(os.getcwd(), "ocr_results")
            self._save_config()
            info("未找到配置文件，已创建默认配置")

        # 如果用户下有模型文件则默认添加到配置中
        # 拼接得到 .paddlex/official_models 的绝对路径
        paddlex_models_path = os.path.join(os.path.expanduser("~"), ".paddlex", "official_models")
        model_fields = [
            ("doc_unwarping_model_dir", "doc_unwarping_model_name"),
            ("text_detection_model_dir", "text_detection_model_name"),
            ("text_recognition_model_dir", "text_recognition_model_name"),
            ("textline_orientation_model_dir", "textline_orientation_model_name"),
        ]

        for dir_attr, name_attr in model_fields:
            model_dir = getattr(self._config, dir_attr)
            model_name = getattr(self._config, name_attr)
            if not model_dir:
                model_path = os.path.join(paddlex_models_path, model_name)
                if os.path.exists(model_path):
                    setattr(self._config, dir_attr, model_path)
            else:
                if not os.path.exists(model_dir):
                    setattr(self._config, dir_attr, '')


    def _save_config(self):
        """
        优化：延迟写入配置到文件，防止频繁IO。
        """
        self._pending_save = True
        # 3秒后写入，如有新请求会重置
        self._save_timer.start(3000)

    def _do_save_config(self):
        """
        真正执行写入磁盘操作。
        """
        if not self._pending_save:
            return
        self._pending_save = False
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
        self._save_config()
        
        # 发送配置变更信号
        self.config_changed.emit(self._config)
        
        # 通知所有监听器
        self._notify_listeners(self._config)
        
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
            os.makedirs(new_storage_dir, exist_ok=True)
            
            # 如果旧目录存在且有数据，可以选择迁移
            old_storage_dir = self._config.storage_dir
            if os.path.exists(old_storage_dir) and os.listdir(old_storage_dir):
                # 这里可以添加数据迁移逻辑
                pass
                
            info(f"存储目录变更为: {new_storage_dir}")
            return True, ""
        except Exception as e:
            error(f"创建存储目录失败: {e}")
            return False, f"创建存储目录失败: {e}"
    
    def get_config_dict(self) -> Dict[str, Any]:
        """
        获取配置字典。
        :return: dict
        """
        return asdict(self._config)
    
    def set_config_from_dict(self, config_dict: Dict[str, Any]) -> tuple[bool, str]:
        """
        从字典设置配置。
        :param config_dict: dict
        :return: (bool, str) 是否成功及消息
        """
        try:
            new_config = AppConfig(**config_dict)
            return self.update_config(new_config)
        except Exception as e:
            error(f"配置格式错误: {e}")
            return False, f"配置格式错误: {e}"

# 便捷的配置访问函数
def get_config() -> AppConfig:
    """
    获取当前配置。
    :return: AppConfig实例
    """
    return ConfigManager().config

def get_base_url() -> str:
    """
    获取Base URL。
    :return: Base URL字符串
    """
    return get_config().base_url

def get_api_key() -> str:
    """
    获取API Key。
    :return: API Key字符串
    """
    return get_config().api_key

def get_model_name() -> str:
    """
    获取模型名称。
    :return: 模型名称字符串
    """
    return get_config().model_name

def get_storage_dir() -> str:
    """
    获取存储目录。
    :return: 存储目录字符串
    """
    return get_config().storage_dir

# 自动标点和分段配置访问函数
def get_punctuate_model_name() -> str:
    """
    获取自动标点和分段模型名称。
    :return: 模型名称字符串
    """
    return get_config().punctuate_model_name

def get_punctuate_system_prompt() -> str:
    """
    获取自动标点和分段系统提示词。
    :return: 系统提示词字符串
    """
    return get_config().punctuate_system_prompt

# 白话文转换配置访问函数
def get_vernacular_model_name() -> str:
    """
    获取白话文转换模型名称。
    :return: 模型名称字符串
    """
    return get_config().vernacular_model_name

def get_vernacular_system_prompt() -> str:
    """
    获取白话文转换系统提示词。
    :return: 系统提示词字符串
    """
    return get_config().vernacular_system_prompt

# 古文解释配置访问函数
def get_explain_model_name() -> str:
    """
    获取古文解释模型名称。
    :return: 模型名称字符串
    """
    return get_config().explain_model_name

def get_explain_system_prompt() -> str:
    """
    获取古文解释系统提示词。
    :return: 系统提示词字符串
    """
    return get_config().explain_system_prompt

# OCR配置访问函数

def get_doc_unwarping_model_dir() -> str:
    """
    获取文本图像矫正模块模型路径。
    :return: 模型路径字符串
    """
    return get_config().doc_unwarping_model_dir

def get_doc_unwarping_model_name() -> str:
    """
    获取文本图像矫正模块模型名称。
    :return: 模型名称字符串
    """
    return get_config().doc_unwarping_model_name

def get_textline_orientation_model_dir() -> str:
    """
    获取文本行方向分类模块模型路径。
    :return: 模型路径字符串
    """
    return get_config().textline_orientation_model_dir

def get_textline_orientation_model_name() -> str:
    """
    获取文本行方向分类模块模型名称。
    :return: 模型名称字符串
    """
    return get_config().textline_orientation_model_name

def get_text_detection_model_dir() -> str:
    """
    获取文本检测模块模型路径。
    :return: 模型路径字符串
    """
    return get_config().text_detection_model_dir

def get_text_detection_model_name() -> str:
    """
    获取文本检测模块模型名称。
    :return: 模型名称字符串
    """
    return get_config().text_detection_model_name

def get_text_recognition_model_dir() -> str:
    """
    获取文本识别模块模型路径。
    :return: 模型路径字符串
    """
    return get_config().text_recognition_model_dir

def get_text_recognition_model_name() -> str:
    """
    获取文本识别模块模型名称。
    :return: 模型名称字符串
    """
    return get_config().text_recognition_model_name

def get_use_doc_unwarping() -> bool:
    """
    获取是否使用文档扭曲矫正模块。
    :return: bool
    """
    return get_config().use_doc_unwarping

def get_use_textline_orientation() -> bool:
    """
    获取是否使用文本行方向分类模块。
    :return: bool
    """
    return get_config().use_textline_orientation

def get_text_det_limit_type() -> str:
    """
    获取文本检测的图像边长限制类型。
    :return: 限制类型字符串
    """
    return get_config().text_det_limit_type

def get_text_det_limit_side_len() -> int:
    """
    获取文本检测的图像边长限制。
    :return: 限制边长
    """
    return get_config().text_det_limit_side_len

def get_text_det_thresh() -> float:
    """
    获取文本检测像素阈值。
    :return: 阈值
    """
    return get_config().text_det_thresh

def get_text_det_box_thresh() -> float:
    """
    获取测框阈值。
    :return: 阈值
    """
    return get_config().text_det_box_thresh

def get_text_det_unclip_ratio() -> float:
    """
    获取文本检测扩张系数。
    :return: 扩张系数
    """
    return get_config().text_det_unclip_ratio

def get_text_rec_score_thresh() -> float:
    """
    获取识别阈值。
    :return: 阈值
    """
    return get_config().text_rec_score_thresh

def update_config(new_config: AppConfig) -> tuple[bool, str]:
    """
    更新配置。
    :param new_config: 新AppConfig对象
    :return: (bool, str) 是否成功及消息
    """
    return ConfigManager().update_config(new_config)

def add_config_listener(listener: Callable[[AppConfig], None]):
    """
    添加配置变更监听器。
    :param listener: 回调函数，参数为AppConfig
    """
    ConfigManager().add_config_listener(listener)

def remove_config_listener(listener: Callable[[AppConfig], None]):
    """
    移除配置变更监听器。
    :param listener: 回调函数
    """
    ConfigManager().remove_config_listener(listener)
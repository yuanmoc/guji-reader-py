import json
import os
import threading

from core.utils.numpy_encoder import NumpyEncoder
from collections import OrderedDict
from core.config_manager import ConfigManager
from core.utils.logger import info, error


class GlobalState():
    """
    全局状态管理类，负责管理当前PDF文件、页码、OCR缓存、配置等。
    主要用于在各个UI组件间共享和同步状态。
    """
    current_pdf_file = None  # 当前打开的PDF文件路径
    current_pdf_basename = None  # 当前PDF文件名
    current_page = 0  # 当前页码（从0开始）

    # ocr_cache改为有序字典，便于LRU清理
    ocr_cache = OrderedDict()  # {文件名: {页码: {ocr:..., auto_punctuate:..., ...}}}
    # 新增最大缓存数
    ocr_cache_max = 6  # 可根据实际内存调整，超出后LRU清理

    # 配置管理器
    config_manager = ConfigManager()

    @classmethod
    def set_pdf_file(cls, file_path):
        """
        设置当前PDF文件，并加载对应缓存。
        :param file_path: PDF文件路径
        """
        cls.current_pdf_file = file_path
        cls.current_pdf_basename = os.path.basename(file_path)
        info(f"设置全局状态-PDF文件: {file_path}")
        # 加载缓存内容
        cls.load_cache()
        info(f"设置全局状态-PDF缓存已加载: {cls.current_pdf_basename}")
        # LRU: 每次访问都move到末尾
        if cls.current_pdf_basename in cls.ocr_cache:
            cls.ocr_cache.move_to_end(cls.current_pdf_basename)
        # 超出上限自动清理最久未访问
        while len(cls.ocr_cache) > cls.ocr_cache_max:
            cls.ocr_cache.popitem(last=False)
        # 新增：同步保存到配置
        config = cls.get_config()
        config.last_open_file = file_path

    @classmethod
    def set_page(cls, page_num):
        """
        设置当前页码。
        :param page_num: 页码（int）
        """
        cls.current_page = page_num
        info(f"设置全局状态-切换到页码: {page_num}")
        # 新增：同步保存到配置
        config = cls.get_config()
        config.last_open_page = page_num

    @classmethod
    def get_pdf_data(cls):
        """
        获取当前PDF的所有缓存数据。
        :return: dict，结构为{页码: {...}}
        """
        file_data = cls.ocr_cache.get(cls.current_pdf_basename)
        if file_data is None:
            return {}
        # LRU: 访问时move到末尾
        cls.ocr_cache.move_to_end(cls.current_pdf_basename)
        return file_data

    @classmethod
    def get_pdf_page_data(cls):
        """
        获取当前PDF当前页的缓存数据。
        :return: dict，结构为{ocr:..., auto_punctuate:..., ...}
        """
        file_data = cls.get_pdf_data()
        page_data = file_data.get(str(cls.current_page))
        if page_data is None:
            return {}
        return page_data

    @classmethod
    def save_pdf_page_data(cls, data={}):
        """
        保存当前页的数据到缓存，并写入磁盘。
        :param data: dict，需保存的数据（如{"ocr":..., "vernacular":...}）
        """
        page_data = cls.get_pdf_page_data()
        for key in data.keys():
            page_data[key] = data.get(key)
        file_data = cls.get_pdf_data()
        file_data[str(cls.current_page)] = page_data
        cls.ocr_cache[cls.current_pdf_basename] = file_data
        info(f"设置全局状态-保存当前页数据: {cls.current_pdf_basename} 页码: {cls.current_page}")
        # 保存缓存内容
        cls.save_cache()

    @classmethod
    def load_cache(cls):
        """
        加载当前PDF的缓存数据（json文件），如无则初始化空字典。
        """
        pdf_data = cls.get_pdf_data()
        if pdf_data is not None and len(pdf_data) > 0:
            return
        cache_path = os.path.join(cls.get_config().storage_dir, f"{cls.current_pdf_basename}.json")
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    GlobalState.ocr_cache[cls.current_pdf_basename] = json.load(f)
                info(f"设置全局状态-加载缓存文件成功: {cache_path}")
            except Exception as e:
                error(f"设置全局状态-加载缓存文件失败: {e}")
                os.remove(cache_path)
                GlobalState.ocr_cache[cls.current_pdf_basename] = {}
        else:
            GlobalState.ocr_cache[cls.current_pdf_basename] = {}
            info(f"设置全局状态-初始化空缓存: {cls.current_pdf_basename}")

    @classmethod
    def save_cache(cls):
        """
        异步保存当前PDF的缓存数据到json文件，避免阻塞主线程。
        """

        def _save():
            cache_path = os.path.join(cls.get_config().storage_dir, f"{cls.current_pdf_basename}.json")
            try:
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(GlobalState.get_pdf_data(), f, ensure_ascii=False, indent=2, cls=NumpyEncoder)
                info(f"设置全局状态-保存缓存文件成功: {cache_path}")
            except Exception as e:
                error(f"设置全局状态-保存缓存文件失败: {e}")

        t = threading.Thread(target=_save)
        t.daemon = True
        t.start()

    # 配置相关的便捷方法
    @classmethod
    def get_config(cls):
        """
        获取当前配置对象。
        :return: AppConfig实例
        """
        return cls.config_manager.config


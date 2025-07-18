import os
import sys

model_name = '.guji'

def get_user_path():
    """
    获取用户目录
    :return:
    """
    return os.path.expanduser("~")

def get_user_store_path(*args):
    """
    获取存储位置
    :param args
    :return:
    """
    full_path = os.path.join(get_user_path(), model_name, *args)
    path_parts = full_path.split(os.sep)
    # 获取最后一部分
    last_part = path_parts[-1]
    # 判断最后一部分是否包含扩展名（包含.且不是以.开头的隐藏文件）
    if '.' in last_part and not last_part.startswith('.'):
        os.makedirs(os.sep.join(path_parts[:-1]), exist_ok=True)
    else:
        os.makedirs(full_path, exist_ok=True)

    return full_path

def get_resource_path(relative_path):
    """
    获取资源文件的绝对路径（兼容开发模式和打包模式）
    """
    if hasattr(sys, '_MEIPASS'):
        # 打包后的临时目录路径（.app 包内）
        return os.path.join(sys._MEIPASS, relative_path)
    # 开发模式下的本地路径（项目根目录）
    return os.path.join(os.path.abspath("."), relative_path)

import numpy as np


def convert_numpy_types(obj):
    """
    # 转换数据中的 NumPy 类型为 Python 原生类型
    :param obj:
    :return:
    """
    if isinstance(obj, np.ndarray):
        return obj.tolist()  # 数组转列表
    elif isinstance(obj, (np.bool_, np.integer, np.floating)):
        return obj.item()  # 标量转 Python 原生类型
    elif isinstance(obj, dict):
        return {k: convert_numpy_types(v) for k, v in obj.items()}  # 递归处理字典
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]  # 递归处理列表
    else:
        return obj  # 其他类型直接返回
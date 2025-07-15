import json

import numpy as np


class NumpyEncoder(json.JSONEncoder):
    """
    用于支持numpy数组序列化为json的编码器。
    主要用于将OCR等结果中的ndarray类型安全保存为json。
    """
    def default(self, obj):
        """
        重载default方法，支持ndarray转为list。
        :param obj: 任意对象
        :return: 可序列化对象
        """
        if isinstance(obj, np.ndarray):
            return obj.tolist()  # 处理ndarray
        return json.JSONEncoder.default(self, obj)

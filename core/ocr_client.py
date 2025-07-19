from paddleocr import PaddleOCR
from core.global_state import GlobalState
from core.utils.logger import info
import os


class OcrClient:
    config = GlobalState.get_config()

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        super().__init__()
        self._initialized = True
        self.init_client()

    def _to_valid_path(self, v):
        # 为空或不是有效目录都返回 None
        if not v or not isinstance(v, str) or not os.path.isdir(v):
            return None
        return v

    def init_client(self):
        try:
            self._ocr_client = PaddleOCR(
                doc_unwarping_model_dir=self._to_valid_path(self.config.doc_unwarping_model_dir),
                doc_unwarping_model_name=self.config.doc_unwarping_model_name,
                textline_orientation_model_dir=self._to_valid_path(self.config.textline_orientation_model_dir),
                textline_orientation_model_name=self.config.textline_orientation_model_name,
                text_detection_model_dir=self._to_valid_path(self.config.text_detection_model_dir),
                text_detection_model_name=self.config.text_detection_model_name,
                text_recognition_model_dir=self._to_valid_path(self.config.text_recognition_model_dir),
                text_recognition_model_name=self.config.text_recognition_model_name,

                use_doc_orientation_classify=False,  # 文档方向
                use_doc_unwarping=self.config.use_doc_unwarping,  # 文本图像矫正
                use_textline_orientation=self.config.use_textline_orientation,  # 文本行方向分类模块
                text_det_limit_side_len=self.config.text_det_limit_side_len,  # 文本检测的图像边长限制
                text_det_limit_type=self.config.text_det_limit_type,  # 文本检测的边长度限制类型

                text_det_thresh=self.config.text_det_thresh,
                text_det_box_thresh=self.config.text_det_box_thresh,
                text_det_unclip_ratio=self.config.text_det_unclip_ratio,
                text_rec_score_thresh=self.config.text_rec_score_thresh,
            )
            info("OcrClient初始化成功")
        except Exception as e:
            info("OcrClient初始化失败, {}", e)

    def get_ocr_client(self):
        return self._ocr_client

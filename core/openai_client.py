from openai import OpenAI

from core.config_manager import ConfigManager
from core.utils.logger import info


class OpenAIClient:
    """
    OpenAI 客户端封装类。
    用于与大模型API进行交互，支持自动标点、白话文转换、古文解释等流式输出。
    自动监听配置变更，动态切换API参数。
    """
    config_manager = ConfigManager()

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

    def init_client(self):
        """
        初始化OpenAI底层client对象，读取当前配置。
        """
        self.base_url = self.config_manager.config.base_url
        self.api_key = self.config_manager.config.api_key
        self.model_name = self.config_manager.config.model_name
        self.client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key
        )

        info(f"OpenAIClient初始化成功，参数: base_url={self.base_url}, model={self.model_name}")

    def stream_punctuate(self, text):
        """
        自动标点和分段。
        :param text: 需要处理的古文文本
        :return: 生成器，流式返回结果字符串
        """
        model_name = self.config_manager.config.punctuate_model_name
        system_prompt = self.config_manager.config.punctuate_system_prompt
        return self._call_openai(model_name, system_prompt, text)

    def stream_vernacular(self, text):
        """
        白话文转换。
        :param text: 需要转换的古文文本
        :return: 生成器，流式返回结果字符串
        """
        model_name = self.config_manager.config.vernacular_model_name
        system_prompt = self.config_manager.config.vernacular_system_prompt
        return self._call_openai(model_name, system_prompt, text)

    def stream_explain(self, prompt):
        """
        古文解释。
        :param prompt: 需要解释的古文内容
        :return: 生成器，流式返回结果字符串
        """
        model_name = self.config_manager.config.explain_model_name
        system_prompt = self.config_manager.config.explain_system_prompt
        return self._call_openai(model_name, system_prompt, prompt)

    def _call_openai(self, model_name=None, system_prompt=None, prompt=None):
        """
        通用流式调用大模型接口。
        :param model_name: 使用的模型名称
        :param system_prompt: 系统提示词
        :param prompt: 用户输入内容
        :return: 生成器，每次yield新内容（字符串）
        """
        if model_name is None or model_name.strip() == '':
            model_name = self.model_name
        if system_prompt is None:
            system_prompt = "你是一位精通古汉语和现代汉语的专家。"
            
        stream = self.client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=6000,
            stream=True
        )
        for chunk in stream:
            delta = chunk.choices[0].delta
            if hasattr(delta, 'content') and delta.content:
                yield delta.content

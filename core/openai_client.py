from openai import OpenAI

from core.global_state import GlobalState
from core.config_manager import (
    get_punctuate_model_name, get_punctuate_system_prompt,
    get_vernacular_model_name, get_vernacular_system_prompt,
    get_explain_model_name, get_explain_system_prompt
)
from core.utils.logger import info, warning, error


class OpenAIClient:
    """
    OpenAI 客户端封装类。
    用于与大模型API进行交互，支持自动标点、白话文转换、古文解释等流式输出。
    自动监听配置变更，动态切换API参数。
    """
    def __init__(self):
        """
        初始化OpenAI客户端，注册配置变更监听器。
        """
        try:
            self._init_client()
            info("OpenAIClient初始化成功")
            # 注册配置变更监听器
            GlobalState.config_manager.add_config_listener(self._on_config_changed)
        except Exception as e:
            error(f"OpenAIClient初始化失败: {e}")
    
    def _init_client(self):
        """
        初始化OpenAI底层client对象，读取当前配置。
        """
        self.base_url = GlobalState.get_base_url()
        self.api_key = GlobalState.get_api_key()
        self.model_name = GlobalState.get_model_name()
        self.client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key
        )
        info(f"OpenAIClient参数: base_url={self.base_url}, model={self.model_name}")
    
    def _on_config_changed(self, config):
        """
        配置变更时的回调，自动重建client。
        :param config: 最新AppConfig对象
        """
        info("检测到配置变更，重建OpenAIClient")
        self._init_client()

    def __del__(self):
        """
        析构时移除监听器，防止内存泄漏。
        """
        try:
            GlobalState.config_manager.remove_config_listener(self._on_config_changed)
            info("OpenAIClient析构，移除配置监听器")
        except Exception as e:
            warning(f"OpenAIClient析构异常: {e}")

    def stream_punctuate(self, text):
        """
        自动标点和分段。
        :param text: 需要处理的古文文本
        :return: 生成器，流式返回结果字符串
        """
        model_name = get_punctuate_model_name()
        system_prompt = get_punctuate_system_prompt()
        return self._call_openai(model_name, system_prompt, text)

    def stream_vernacular(self, text):
        """
        白话文转换。
        :param text: 需要转换的古文文本
        :return: 生成器，流式返回结果字符串
        """
        model_name = get_vernacular_model_name()
        system_prompt = get_vernacular_system_prompt()
        return self._call_openai(model_name, system_prompt, text)

    def stream_explain(self, prompt):
        """
        古文解释。
        :param prompt: 需要解释的古文内容
        :return: 生成器，流式返回结果字符串
        """
        model_name = get_explain_model_name()
        system_prompt = get_explain_system_prompt()
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

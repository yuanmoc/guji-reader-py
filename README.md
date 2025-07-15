# 古籍阅读器

## 项目简介

古籍阅读器是一个基于 **PySide6** + **PaddleOCR** 的桌面应用，集成 PDF 阅读、OCR 识别、AI 自动标点、白话文转换、古文解释等多项功能，助力古籍文献的数字化阅读、研究与学习。

在书格上找了一些古籍书看，找不到合适自己的阅读器，就干脆自己做了一个，方便自己使用。

---

## 主要功能

### 1. 设置与配置

- 支持通过弹窗界面配置大模型 Base URL、API Key、模型名称、数据存储目录等参数。
- 支持 OCR、自动标点、白话文转换、古文解释等多项功能的详细参数配置。
- 配置项校验（如 URL 格式），并持久化到本地 `config.json` 文件。
- 支持模型路径选择、参数自定义，兼容本地/远程 PaddleOCR 模型。

### 2. PDF 阅读与管理

- 支持打开本地 PDF 文件，自动记忆上次打开的文件与页码。
- 分页浏览、跳转指定页、上一页/下一页、缩放（20%-300%[未实现]）。
- 支持自动加载上次阅读的 PDF 文件。

### 3. OCR 识别与校对

- 一键对当前页进行 OCR 识别，支持竖排、横排自动模式。
- OCR 结果缓存，避免重复识别，支持重试与失败提示。
- 支持在 PDF 上高亮显示 OCR 识别框，支持手动调整和删除。
- 校对区可对识别结果进行人工校正，结果同步保存。

### 4. AI 辅助处理

- **自动标点分段**：调用大模型 API，对 OCR 结果进行智能标点和分段。
- **白话文转换**：一键将古文 OCR 结果转换为现代汉语。
- **古文解释工具**：底部面板支持多行古文输入，实时获取现代汉语解释，支持流式输出和清空。

### 5. 日志与调试

- 内置日志面板，支持刷新、清空，便于调试和问题追踪。
- 日志文件自动轮转，最大 5MB，保留 3 个历史文件。

---

## 安装与运行

### 1. 安装依赖

建议使用 Python 3.9+，并提前安装好 PaddleOCR 相关依赖。

```bash
pip install -r requirements.txt
```
注意⚠️：还需要安装 [paddlepaddle](https://www.paddlepaddle.org.cn/install/quick)

### 2. 启动应用

```bash
python main.py
```

### 3. 依赖说明

- PySide6
- paddleocr
- PyMuPDF
- openai
- requests
- markdown

详见 `requirements.txt`。

---

## 配置说明

- 首次启动或点击“更多设置”可弹出配置窗口，支持所有参数的可视化配置。
- 配置项包括大模型 API 地址、API Key、模型名称、数据存储目录、OCR 相关模型路径及参数、AI 功能相关模型与提示词等。
- 配置保存在本地 `config.json` 文件，支持自动加载和热更新。

---

## 日志系统

- 日志文件默认存储在 `logs/app.log`，支持自动轮转。
- 日志内容包括应用启动、配置变更、OCR 识别、AI 调用等关键操作，便于排查问题。

---

## 目录结构

```
core/                  # 核心逻辑与工具
  ├── config_manager.py      # 配置管理
  ├── global_state.py        # 全局状态与缓存
  ├── openai_client.py       # 大模型 API 封装
  └── utils/                 # 工具类
      ├── logger.py
      ├── numpy_encoder.py
      └── ocr_data_util.py

ui/                    # 前端界面
  ├── assets/                # 静态资源
  ├── explain_tab.py         # 古文解释工具
  ├── log_tab.py             # 日志面板
  ├── ocr_tab.py             # OCR 识别面板
  ├── pdf_viewer.py          # PDF 预览组件
  ├── proofread_tab.py       # 校对面板
  ├── punctuate_tab.py       # 自动标点面板
  ├── settings_dialog.py     # 设置弹窗
  └── vernacular_tab.py      # 白话文转换面板

main.py                # 程序入口
requirements.txt       # 依赖列表
```

---

## 常见问题

- **模型路径/参数配置问题**：请在“更多设置”中检查模型路径和参数，确保本地模型已下载并路径正确。
- **API Key/大模型接口异常**：请检查 Base URL 和 API Key 是否正确，网络是否畅通。
- **OCR 识别效果不佳**：可尝试更换或升级 PaddleOCR 模型，或调整相关参数。

---

## 贡献与反馈

如有建议或问题，欢迎提交 Issue 或 PR。

---

## License

MIT
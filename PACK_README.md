
## 打包与发布(未经测试)

本项目支持将 Python 桌面应用打包为独立的 Mac 和 Windows 可执行程序，推荐使用 PyInstaller 工具。

### 1. 安装 PyInstaller

请先确保已安装 PyInstaller：

```bash
pip install pyinstaller
```

### 2. Mac 打包操作

1. 进入项目根目录。
2. 执行以下命令进行打包：

```bash
pyinstaller --noconfirm --windowed --add-data "ui/assets:ui/assets" --name "古籍阅读器" main.py
```

- `--windowed`：不显示终端窗口（适用于 GUI 应用）。
- `--add-data`：添加静态资源（注意 Mac 下路径分隔符为冒号 :）。
- `--name`：指定应用名称。

3. 打包完成后，生成的可执行文件在 `dist/古籍阅读器/` 目录下，双击即可运行。

#### Mac 注意事项

- 如遇到字体、图片等资源无法加载，请检查 `--add-data` 路径写法是否正确。
- 若有额外依赖的动态库或模型文件，请一并复制到 `dist/古籍阅读器/` 目录下。
- 若出现“已损坏”或“无法打开”提示，可在终端执行：
  ```bash
  xattr -d com.apple.quarantine dist/古籍阅读器/古籍阅读器
  ```

### 3. Windows 打包操作

1. 进入项目根目录。
2. 执行以下命令进行打包：

```bash
pyinstaller --noconfirm --windowed --add-data "ui/assets;ui/assets" --name "古籍阅读器" main.py
```

- Windows 下 `--add-data` 路径分隔符为分号 ;。

3. 打包完成后，生成的可执行文件在 `dist\古籍阅读器\` 目录下，双击 `古籍阅读器.exe` 即可运行。

#### Windows 注意事项

- 若首次运行报缺少 DLL，可安装 Visual C++ 运行库。
- 若有 PaddleOCR 相关依赖或模型文件，请确保一并复制到打包目录。
- 若遇到中文路径乱码或界面显示异常，建议将项目路径和打包名称均设为英文。

### 4. 资源文件与依赖说明

- 静态资源（如图片、图标等）需通过 `--add-data` 参数打包。
- 若有自定义字体、OCR 模型等文件，也需通过 `--add-data` 或手动复制到打包目录。
- 所有 Python 依赖需提前通过 `pip install -r requirements.txt` 安装。

### 5. 常见问题

- **资源文件丢失**：请确认 `--add-data` 参数格式正确，Mac 用冒号 :，Windows 用分号 ;。
- **依赖缺失**：如启动报错缺少模块，请检查 `requirements.txt` 并确保环境一致。
- **模型文件未包含**：如需离线使用 PaddleOCR，请将模型文件手动复制到打包目录。
- **Mac 下应用无法打开**：可尝试在终端执行 `xattr -d com.apple.quarantine dist/古籍阅读器/古籍阅读器`。

### 6. 参考链接

- [PyInstaller 官方文档](https://pyinstaller.org/)
- [PaddleOCR 安装说明](https://www.paddlepaddle.org.cn/install/quick?docurl=undefined)
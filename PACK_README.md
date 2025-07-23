
## 打包与发布(Windows 未经测试)

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
pyinstaller --noconfirm --windowed --add-data "ui/assets:ui/assets" --name "古籍阅读器" --osx-bundle-identifier com.github.yuanmoc --icon=./ui/assets/logo.png main.py
```

- `--windowed`：不显示终端窗口（适用于 GUI 应用）。
- `--add-data`：添加静态资源（注意 Mac 下路径分隔符为冒号 :）。
- `--name`：指定应用名称。

3. 打包完成后，启动出现些问题，进行以下微调。

Mac 注意事项

- 如遇到字体、图片等资源无法加载，请检查 `--add-data` 路径写法是否正确。
- 若有额外依赖的动态库或模型文件，请一并复制到 `dist/古籍阅读器/` 目录下。
- 若出现“已损坏”或“无法打开”提示，可在终端执行 `sudo xattr -rd com.apple.quarantine ./dist/古籍阅读器.app：


把生成的 古籍阅读器.spec 改成 pack.spec 英文名称，方便操作
```bash
mv 古籍阅读器.spec pack.spec
```
删除原有打包过程中产生的数据
```bash
rm -rf dist 
rm -rf build
```

打包后执行错误：
调整并编辑python包 paddle/base/core.py 数据
```text
原：if hasattr(site, 'USER_SITE')
换：if hasattr(site, 'USER_SITE') and site.USER_SITE:
```
对于缺少依赖和执行错误问题，在打包 pack.spec 脚本中进行处理

需要更新包cv2
```bash
pip install --upgrade opencv-contrib-python==4.12.0.88
```

使用 pack.spec 来打包
```bash
rm -rf dist 
rm -rf build
pyinstaller --clean  pack.spec
```

如果出现 MAC 启动安全问题，请执行
```bash
sudo xattr -rd com.apple.quarantine ./dist/古籍阅读器.app
```

启动问题排查日志命令
```bash
log show --predicate 'process == "古籍阅读器"' --debug --last 1m
```

### 3. Windows 打包操作

1. 进入项目根目录。
2. 执行以下命令进行打包：

```bash
pyinstaller pack.spec
```

- Windows 下 `--add-data` 路径分隔符为分号 ;。

3. 打包完成后，生成的可执行文件在 `dist\古籍阅读器\` 目录下，双击 `古籍阅读器.exe` 即可运行。

### 4. 参考链接

- [PyInstaller 官方文档](https://pyinstaller.org/)
- [PaddleOCR 安装说明](https://www.paddlepaddle.org.cn/install/quick?docurl=undefined)
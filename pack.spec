# -*- mode: python ; coding: utf-8 -*-
import site, os, shutil
from PyInstaller.utils.hooks import collect_data_files, copy_metadata
from pathlib import Path

def get_core_file_path():
    """
    获取修复文件路径
    :return:
    """
    base_path = site.getsitepackages()
    return os.path.join(*base_path, "paddle", "base", "core.py")


def get_backup_core_file_path(code_file: str):
    """
    获取备份文件路径
    :return:
    """
    return Path(code_file).with_suffix('.py.bak')


def backup_original_file():
    """
    备份原始文件为core.py.bak
    :return:
    """
    core_file = get_core_file_path()
    backup_file = get_backup_core_file_path(core_file)
    if not backup_file.exists() and os.path.exists(core_file):
        shutil.copy2(core_file, backup_file)
        print(f"已备份原始文件到：{backup_file}")
    return backup_file


def fix_paddle_core():
    """
    修复文件
    :return:
    """
    core_file = get_core_file_path()
    if not os.path.exists(core_file):
        print(f"警告：未找到 {core_file}，跳过修复")
        return

    # 读取原文件内容
    with open(core_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # 替换目标代码
    old_code = 'if hasattr(site, \'USER_SITE\'):'
    new_code = 'if hasattr(site, \'USER_SITE\') and site.USER_SITE:'

    if old_code in content:
        content = content.replace(old_code, new_code)
        # 写回修改后的内容
        with open(core_file, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"已修复 {core_file} 中的代码")
    else:
        print(f"未找到需要修复的代码模式，跳过")


def restore_original_file():
    """
    从备份恢复原始文件
    :return:
    """
    core_file = get_core_file_path()
    backup_file = get_backup_core_file_path(core_file)
    if backup_file.exists():
        shutil.copy2(backup_file, core_file)
        backup_file.unlink()  # 删除备份文件
        print(f"已恢复原始文件：{core_file}")
    else:
        print("无备份文件，无需恢复")

# 修复文件
backup_original_file()
fix_paddle_core()

# 收集数据文件和元数据
paddlex_data = collect_data_files('paddlex')
metadata_files = [
    copy_metadata('ftfy'),
    copy_metadata('imagesize'),
    copy_metadata('lxml'),
    copy_metadata('opencv-contrib-python'),
    copy_metadata('openpyxl'),
    copy_metadata('premailer'),
    copy_metadata('pyclipper'),
    copy_metadata('pypdfium2'),
    copy_metadata('scikit-learn'),
    copy_metadata('shapely'),
    copy_metadata('tokenizers'),
    copy_metadata('einops'),
    copy_metadata('jinja2'),
    copy_metadata('regex'),
    copy_metadata('tiktoken'),
]

# 合并所有数据文件
all_datas = paddlex_data
for metadata in metadata_files:
    all_datas.extend(metadata)

# 二进制文件（请替换为实际路径）
# 获取第三方库安装路径
# site_packages = site.getsitepackages()[0]
# binary_path = os.path.join(site_packages, 'paddle', 'libs')
# binaries = [(binary_path, ".")] if os.path.exists(binary_path) else []


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=all_datas + [('ui/assets', 'ui/assets')],
    hiddenimports=['scipy._cyutility', 'sklearn._cyutility'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='古籍阅读器',
    debug=False,
    console=False,
    windowed=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['ui/assets/logo.png'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='古籍阅读器',
)
app = BUNDLE(
    coll,
    name='古籍阅读器.app',
    icon='./ui/assets/logo.png',
    bundle_identifier='com.github.yuanmoc',
)

# 还原本地文件
restore_original_file()
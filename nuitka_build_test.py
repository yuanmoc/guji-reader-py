#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
古籍阅读器 Nuitka 打包脚本
用于将应用打包成独立的桌面应用程序

重构版本 - 更加模块化和可维护
"""

import os
import re
import sys
import shutil
import subprocess
import argparse
import json5
from importlib import metadata
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from typing import List, Dict, Optional


class ConfigManager:
    """配置管理器"""

    def __init__(self, config_file: str = "nuitka_build_config.json"):
        self.config_file = config_file
        self.config = self.load_config()

    def load_config(self) -> Dict:
        """加载配置文件"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json5.load(f)
        except FileNotFoundError:
            print(f"⚠️ 配置文件 {self.config_file} 不存在")
            exit(-1)
        except json5.JSON5DecodeError as e:
            print(f"❌ 配置文件格式错误: {e}")
            exit(-1)

    def get_build_settings(self) -> Dict:
        """获取构建设置"""
        return self.config.get("build_settings", {})

    def get_platforms_args(self) -> Dict:
        """获取平台特定参数"""
        return self.config.get("build_settings", {}).get("platforms_args", {})

    def get_app_info(self) -> Dict:
        """获取应用信息"""
        return self.config.get("app_info", {})


class NuitkaBuilder:
    """Nuitka 构建器类"""

    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.build_settings = config_manager.get_build_settings()
        self.app_info = config_manager.get_app_info()

        # 构建配置
        self.app_name = self.app_info.get('name', '应用')
        self.app_version = self.app_info.get('version', '1.0.0')
        self.app_description = self.app_info.get('description', '')
        self.main_file = self.app_info.get('main_file', 'main.py')
        self.output_dir = "dist"
        self.build_dir = "build"
        self.icon_path = self.app_info.get('icon_path', 'logo.png')
        self.packages = self.build_settings.get('packages', [])
        self.data_dirs = self.build_settings.get('data_dirs', [])
        self.common_args = self.build_settings.get('common_args', [])
        self.build_dependencies = self.build_settings.get("build_dependencies", [])

        self.platform = self.detect_platform()
        self.platform_args = config_manager.get_platforms_args().get(self.platform, [])

        self.requirements_nuitka_file = "requirements_nuitka.txt"

    def detect_platform(self) -> str:
        """检测当前平台"""
        platform = sys.platform.lower()

        if platform.startswith("win"):
            return "windows"
        elif platform.startswith("darwin"):
            return "macos"
        elif platform.startswith("linux"):
            return "linux"
        else:
            raise ValueError(f"不支持的平台: {platform}")

    def create_requirements_file(self):
        """创建 Nuitka 专用的 requirements 文件"""
        try:
            # 直接使用 packages 参数
            requirements_content = "# Nuitka 打包专用依赖\n" + "\n".join(self.packages) + "\n"

            with open(self.requirements_nuitka_file, "w", encoding="utf-8") as f:
                f.write(requirements_content)

            print("📄 已创建 requirements_nuitka.txt")
            print(f"📦 包含 {len(self.packages)} 个依赖包")

        except (FileNotFoundError, json5.JSON5DecodeError):
            print("❌ 获取packages信息出现错误")
            exit(-1)

    def clean_temp_files(self):
        """清理临时文件"""
        temp_files = [self.requirements_nuitka_file]

        for file_path in temp_files:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"🗑️ 已清理临时文件: {file_path}")

    def run_command(self, cmd: List[str], description: str) -> subprocess.CompletedProcess:
        """执行命令并处理错误"""
        print(f"🔄 正在执行: {description}")
        print(f"📝 命令: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                " ".join(cmd),
                shell=True,
                check=True,
                text=True,
                stdout=sys.stdout,  # 输出重定向到控制台
                stderr=sys.stderr,  # 错误输出重定向到控制台
                encoding='utf-8'
            )
            print(f"✅ {description} 成功")
            return result
        except subprocess.CalledProcessError as e:
            print(f"❌ {description} 失败")
            print(f"错误输出: {e.stderr}")
            print(f"返回码: {e.returncode}")
            sys.exit(1)
        except FileNotFoundError:
            print(f"❌ 命令未找到: {cmd[0]}")
            sys.exit(1)

    def check_dependencies(self) -> bool:
        """检查并安装构建依赖"""
        print("🔍 检查构建依赖...")

        missing_deps = []
        for dep in self.build_dependencies:
            try:
                metadata.version(dep)
                print(f"✅ {dep} 已安装")
            except PackageNotFoundError:
                print(f"❌ {dep} 未安装")
                missing_deps.append(dep)

        if missing_deps:
            print(f"📦 正在安装缺失的依赖: {', '.join(missing_deps)}")
            for dep in missing_deps:
                self.run_command(["pip", "--version", "&&", "pip", "install", dep], f"安装 {dep}")

        return True

    def clean_directories(self):
        """清理构建和分发目录"""
        print("🧹 清理构建目录...")

        for dir_path in [self.output_dir]:
            path = Path(dir_path)
            if path.exists():
                print(f"删除目录: {path}")
                shutil.rmtree(path)
            else:
                print(f"目录不存在: {path}")

    def build_command(self) -> List[str]:
        """构建完整的 Nuitka 命令"""
        cmd = ["pip", "--version", "&&", "nuitka"]

        # 添加通用参数
        cmd.extend(self.common_args)

        # 添加平台特定参数
        cmd.extend(self.platform_args)

        # 添加包包含参数
        for package in self.packages:
            cmd.append(f"--include-package={package}")

        # 添加数据目录参数
        for data_dir in self.data_dirs:
            cmd.append(f"--include-data-dir={data_dir}")

        # 生成带后缀的输出文件名
        output_filename = self.app_name
        if self.platform == "windows" and not self.app_name.lower().endswith(".exe"):
            output_filename += ".exe"
        elif self.platform == "macos" and not self.app_name.lower().endswith(".app"):
            output_filename += ".app"
        # Linux 可选加后缀，这里保持原样

        # 添加输出参数
        cmd.extend([
            f"--output-dir={self.output_dir}",
            f"--output-filename={output_filename}"
        ])

        # 平台专属应用名称参数
        if self.platform == "windows":
            cmd.append(f"--windows-product-name={self.app_name}")
            cmd.append(f"--windows-product-version={self.app_version}")
            if self.app_description:
                cmd.append(f"--windows-file-description={self.app_description}")
        elif self.platform == "macos":
            cmd.append(f"--macos-app-name={self.app_name}")
            cmd.append(f"--macos-app-version={self.app_version}")

        # 添加 icon 参数（根据平台自动选择）
        if self.icon_path:
            if os.path.exists(self.icon_path):
                if self.platform == "windows":
                    cmd.append(f"--windows-icon-from-ico={self.icon_path}")
                elif self.platform == "macos":
                    cmd.append(f"--macos-app-icon={self.icon_path}")
                elif self.platform == "linux":
                    cmd.append(f"--linux-onefile-icon={self.icon_path}")
            else:
                print(f"⚠️ 未找到 icon 文件: {self.icon_path}，将不设置应用图标")

        # 添加主程序文件
        cmd.append(self.main_file)

        return cmd

    def fix_paddle_core(self):
        """修复 paddle core.py 兼容性问题（仿 pack.spec）"""
        import site
        base_path = site.getsitepackages()
        core_file = os.path.join(*base_path, "paddle", "base", "core.py")
        backup_file = core_file + ".bak"
        if not os.path.exists(core_file):
            print(f"警告：未找到 {core_file}，跳过修复")
            return
        # 备份
        if not os.path.exists(backup_file):
            shutil.copy2(core_file, backup_file)
            print(f"已备份原始文件到：{backup_file}")
        # 修复
        with open(core_file, 'r', encoding='utf-8') as f:
            content = f.read()
        old_code = "if hasattr(site, 'USER_SITE'):"
        new_code = "if hasattr(site, 'USER_SITE') and site.USER_SITE:"
        if old_code in content:
            content = content.replace(old_code, new_code)
            with open(core_file, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"已修复 {core_file} 中的代码")
        else:
            print(f"未找到需要修复的代码模式，跳过")

    def restore_paddle_core(self):
        """还原 paddle core.py"""
        import site
        base_path = site.getsitepackages()
        core_file = os.path.join(*base_path, "paddle", "base", "core.py")
        backup_file = core_file + ".bak"
        if os.path.exists(backup_file):
            shutil.copy2(backup_file, core_file)
            os.remove(backup_file)
            print(f"已恢复原始文件：{core_file}")
        else:
            print("无备份文件，无需恢复")

    def build(self):
        """执行构建过程"""
        print(f"🚀 开始 {self.platform} 平台打包...")
        print(f"📱 应用名称: {self.app_name}")
        print(f"📋 应用版本: {self.app_version}")
        print(f"📁 输出目录: {self.output_dir}")
        print(f"🔨 构建目录: {self.build_dir}")

        # 检查依赖
        self.check_dependencies()

        # 清理目录
        self.clean_directories()

        # 打包前修复 paddle core
        self.fix_paddle_core()

        self.create_requirements_file()

        # 构建命令
        cmd = self.build_command()

        # 执行构建
        self.run_command(cmd, f"{self.platform} 平台打包")

        # 打包后还原 paddle core
        self.restore_paddle_core()

        self.clean_temp_files()

        print(f"🎉 打包完成！")
        print(f"📦 输出文件位于 {self.output_dir}/ 目录中")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="古籍阅读器 Nuitka 打包工具")
    parser.add_argument(
        "--config",
        default="nuitka_build_config.json",
        help="指定配置文件路径"
    )

    args = parser.parse_args()

    print("📚 古籍阅读器 Nuitka 打包工具")
    print("=" * 50)

    try:
        # 执行构建
        config_manager = ConfigManager(args.config)
        builder = NuitkaBuilder(config_manager)
        builder.build()
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断构建过程")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 构建过程中发生错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

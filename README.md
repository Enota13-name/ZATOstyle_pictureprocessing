# ZATO 风格照片处理技能

将照片处理成接近《Z.A.T.O. I Love the World and Everything In It》背景的色调、压黑与印刷颗粒效果。使用本地 Python 图像处理脚本和参考统计配置，无需在线图像生成服务。

## 技能目录

```text
skills/zato-background-style/
├── SKILL.md            # 技能说明与处理流程
├── agents/openai.yaml  # 技能显示名称与默认提示词
├── scripts/            # 处理脚本与 Python 依赖
└── references/         # 风格说明、参考图与统计配置
```

## 在 Codex 中安装

向 Codex 发出以下指令：

> 使用 skill-installer 从 https://github.com/Enota13-name/ZATOstyle_pictureprocessing 安装 skills/zato-background-style。

也可以将完整的 `zato-background-style` 文件夹放进当前 Codex 的个人技能目录或项目的 `.agents/skills/` 目录。请保留脚本和参考文件的相对位置。

安装脚本依赖：

```powershell
python -m pip install -r .\skills\zato-background-style\scripts\requirements.txt
```

## 使用

向 Codex 提供照片并发出指令：

> 使用 $zato-background-style 处理这张照片。

技能会先询问是否模糊图片中的 logo。默认交付两张 PNG：冷青版本和暖色版本；保留原照片主体、构图和透明度。如选择模糊 logo，会先对原照片中的标识做局部模糊，再应用风格。

也可以直接从本仓库根目录运行脚本：

```powershell
python .\skills\zato-background-style\scripts\zato_style.py "D:\photos\scene.jpg" --output-dir "D:\photos\zato-output" --preset cold-cyan --images-only
python .\skills\zato-background-style\scripts\zato_style.py "D:\photos\scene.jpg" --output-dir "D:\photos\zato-output" --preset amber --images-only
```

将示例路径替换为自己的照片与输出目录。命令行脚本不自动检测 logo，需要根据技能说明准备区域或蒙版。

完整流程见 [SKILL.md](skills/zato-background-style/SKILL.md)，参数与调校说明见 [processing.md](skills/zato-background-style/references/processing.md)。

此技能根据参考图的色彩与明暗统计近似视觉风格，并非游戏官方工具，也不保证复现原作者的编辑流程。

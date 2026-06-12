---
layer: 手段层
date: "2026-06-12"
tags:
  - 工具
  - 终端
  - 效率
dg-publish: true
---

# 终端效率工具手册

> 为你量身整理的 macOS 终端效率提升方案。每条指令都附带"什么时候用"，不死记硬背。

---

## 一、命令行基础（精选 20 条）

### 1. 导航与文件

| 指令 | 说明 | 什么时候用 |
|------|------|-----------|
| `cd -` | 回到上一个目录 | 在两个目录间反复横跳，比重新敲路径快得多 |
| `cd ~` | 回到 home | 迷路了就回家 |
| `ls -la` | 你已经有了 `ll` 别名 | 查看隐藏文件（.git、.env、配置文件） |
| `mkdir -p a/b/c` | 递归建目录 | 一次建完整路径，不用逐层 mkdir |
| `cp -r src dst` | 递归复制 | 复制整个文件夹 |
| `mv` | 移动/重命名 | 比 Finder 拖拽快；`mv old.md new.md` 就是重命名 |
| `open .` | Finder 打开当前目录 | 需要拖文件、看预览时用 |
| `open -a AppName file` | 指定应用打开 | 临时用另一个软件打开（见第五部分） |

### 2. 文本查看（不进入编辑器）

| 指令 | 说明 | 什么时候用 |
|------|------|-----------|
| `cat file` | 输出全文 | 小文件瞄一眼 |
| `less file` | 分页查看 | 长日志、大文件；按 `q` 退出，`/` 搜索 |
| `head -20 file` | 看前 20 行 | 检查文件开头结构 |
| `tail -20 file` | 看末尾 20 行 | 检查日志最新输出 |
| `tail -f file` | 实时跟踪末尾 | 看实时日志（按 Ctrl+C 退出） |
| `wc -l file` | 统计行数 | 快速评估文件规模 |

### 3. 搜索（你已经有了 `rg`/ripgrep）

```bash
# 在当前目录所有文件中搜索"关键字"
rg "搜索内容"

# 只在 .py 文件中搜索
rg "搜索内容" --type py

# 搜索但不进入 node_modules / .git
rg "搜索内容" --type-not binary

# 列出包含关键字的文件（不展示匹配行）
rg -l "搜索内容"
```

**为什么用 rg 而不是 grep**：ripgrep 默认忽略 .gitignore 里的文件，速度快一个数量级，输出带语法高亮。

### 4. 管道——理解这一个概念，解锁半个 Unix

```bash
# | 把左边命令的输出"喂"给右边命令
rg "ERROR" app.log | wc -l    # 统计错误次数
rg "TODO" --type py | sort     # 找到所有 TODO 并排序
cat file.txt | grep -v "^#"    # 去掉注释行
```

核心模型：**每个命令做一件事，用管道串联**。你不需要记住所有组合，理解 `|` 就够——需要时现查。

### 5. 权限与进程

| 指令 | 说明 |
|------|------|
| `chmod +x script.sh` | 让脚本可执行 |
| `sudo command` | 以管理员身份执行（谨慎） |
| `ps aux \| rg 进程名` | 查找进程 |
| `kill -9 PID` | 强制杀掉进程 |
| Ctrl+C | 终止当前正在跑的命令 |

### 6. 网络与下载

| 指令 | 说明 | 典型场景 |
|------|------|---------|
| `curl -O URL` | 下载文件 | 下载安装包、配置文件 |
| `curl -s URL \| python3` | 下载并执行（慎用） | 安装脚本 |
| `ping host` | 测试连通性 | "这个网站挂了吗？" |
| `brew install pkg` | 安装软件 | macOS 包管理器，你已经在用 |

---

## 二、iTerm2 快捷键

你已经装了 iTerm2。以下是最值得记住的 12 条，按使用频率排序。

### 必须记住（每天用 10+ 次）

| 快捷键 | 效果 |
|--------|------|
| **Cmd+D** | 垂直分屏 |
| **Cmd+Shift+D** | 水平分屏 |
| **Cmd+[ / Cmd+]** | 在分屏间切换 |
| **Cmd+T** | 新建标签页 |
| **Cmd+数字** | 切换到第 N 个标签 |
| **Cmd+W** | 关闭当前分屏/标签 |

### 高频（用了就知道好）

| 快捷键 | 效果 |
|--------|------|
| **Cmd+Enter** | 全屏/恢复（iTerm2 自有全屏） |
| **Cmd+Shift+Enter** | 最大化当前分屏 |
| **Cmd+;** | 自动补全（基于历史命令） |
| **Cmd+Shift+H** | 粘贴历史（可视化选择历史命令） |
| **Ctrl+L** | 清屏（比打 `clear` 快） |

### 文本操作（在命令行里编辑）

| 快捷键 | 效果 |
|--------|------|
| **Ctrl+A** | 跳到行首 |
| **Ctrl+E** | 跳到行尾 |
| **Ctrl+W** | 删除前一个词 |
| **Ctrl+U** | 删除光标前全部内容 |
| **Ctrl+K** | 删除光标后全部内容 |
| **Option+←/→** | 按单词跳转（已配置 Left Option = Esc+，确保可用） |

### 酷功能（很多人不知道）

1. **选中即复制**：iTerm2 默认开启，鼠标选中文本就自动复制了，无需 Cmd+C
2. **Cmd+点击**：打开 URL / 文件路径
3. **Hotkey Window**：已配置为 **双击 Right Command**，任何应用里双击右侧 Cmd 键即可弹出/隐藏终端——像 Quake 游戏里的控制台。
4. **Shell Integration**（iTerm2 > Install Shell Integration）：装完后，拖拽文件到终端自动补全路径、命令执行时间显示、即时回放。

---

## 三、vim 速成（配置文件编辑场景）

你不需要用 vim 写代码。你遇到的场景是：**编辑 .zshrc、.env、YAML 配置文件**。

### 核心心智模型：vim 有三种模式

```
普通模式（按 Esc 进入）──→ 按 i/a/o ──→ 插入模式（正常打字）
                                        │
                    ←── 按 Esc ────────┘
```

**任何时候不确定自己在哪个模式，按 Esc 回到普通模式。**

### 生存 6 条（记住这些就能用）

| 操作 | 指令 | 记忆方法 |
|------|------|---------|
| 开始编辑 | `i` | **I**nsert——在光标前插入 |
| 保存 | 按 Esc，然后 `:w` | **W**rite |
| 保存并退出 | 按 Esc，然后 `:wq` | Write + Quit |
| 不保存退出 | 按 Esc，然后 `:q!` | Quit + !（强制执行） |
| 撤销 | 按 Esc，然后 `u` | **U**ndo |
| 搜索 | 按 Esc，然后 `/关键词` | 按 Enter 搜索，`n`/`N` 上下跳 |

### 进阶（值得花 5 分钟练）

| 操作 | 指令 |
|------|------|
| 删除整行 | `dd` |
| 复制整行 | `yy`（然后 `p` 粘贴） |
| 行尾插入 | `A` |
| 跳到最后一行 | `G` |
| 跳到第一行 | `gg` |
| 显示行号 | `:set nu` |
| 搜索替换 | `:%s/旧/新/g`（全文替换） |

### 替代方案

如果你只是偶尔改配置，**VS Code 终端模式**同样可以用，而且不需要学新模式：
```bash
code ~/.zshrc     # VSCode 打开编辑
code ~/project/   # VSCode 打开项目
```

---

## 四、文件默认打开方式建议

以下是基于你的使用场景的最优配置。核心原则：**用什么工具写，就用什么工具打开，不要让系统猜。**

| 文件类型 | 推荐应用 | 理由 |
|---------|---------|------|
| `.md` | **Obsidian** | 你的主力笔记工具，天然支持双向链接和 vault 搜索 |
| `.json`, `.yaml`, `.toml`, `.env` | **VS Code** | 语法高亮、格式化、自动校验 |
| `.py` | **VS Code** | 语法提示、调试器、终端集成 |
| `.csv` | **VS Code** | 比 Excel 轻量，查看和编辑够用；Rainbow CSV 插件推荐 |
| `.csv`（大数据） | **Numbers** | 超过几千行时 VS Code 不好看，此时用 Numbers |
| `.log` | **VS Code** | 大文件打开不卡，搜索方便 |
| `.pdf` | **Preview**（系统默认） | 够了 |
| `.png`, `.jpg` 等图片 | **Preview**（系统默认） | 够了 |
| 纯文本 `.txt` | **VS Code** | 统一体验 |
| 无后缀配置文件 | **VS Code** | 避免被系统当成二进制 |

### 如何设置默认打开方式

**方法一（推荐）**——Finder 操作：
1. 右键点击文件 → "显示简介"（或 Cmd+I）
2. 在"打开方式"下拉菜单中选择应用
3. 点击"全部更改"按钮

**方法二**——命令行批量设置（需先装 duti）：
```bash
brew install duti

# 批量设置
duti -s com.microsoft.VSCode .json all
duti -s com.microsoft.VSCode .yaml all
duti -s com.microsoft.VSCode .yml all
duti -s com.microsoft.VSCode .toml all
duti -s com.microsoft.VSCode .py all
duti -s com.microsoft.VSCode .csv all
duti -s com.microsoft.VSCode .log all
duti -s com.microsoft.VSCode .txt all
duti -s md.obsidian .md all
```

> `duti` 需要通过应用的 bundle identifier 来指定。VS Code 是 `com.microsoft.VSCode`，Obsidian 是 `md.obsidian`。不确定时用 `osascript -e 'id of app "AppName"'` 获取。

---

## 五、推荐安装的增强工具

| 工具 | 用途 | 安装方式 |
|------|------|---------|
| **bat** | `cat` 的替代，带语法高亮和行号 | `brew install bat` |
| **fzf** | 模糊搜索，配合 Ctrl+R/T 使用 | `brew install fzf && $(brew --prefix)/opt/fzf/install` |
| **fd** | `find` 的替代，更快更友好 | `brew install fd` |
| **tldr** | 精简版 man，给出最常用例子 | `brew install tldr` |
| **duti** | 批量设置默认打开方式（见第四部分） | `brew install duti` |
| **htop** | 比 top 好看 10 倍的进程监控 | `brew install htop` |
| **jq** | 命令行 JSON 处理（格式化、查询） | `brew install jq` |

安装优先级：**fzf > bat > tldr > 其他**。fzf 装完后，Ctrl+R 搜索历史命令的体验会有质的飞跃。

---

## 六、Oh My Zsh 插件

已配置并生效的插件：

```bash
plugins=(git zsh-autosuggestions zsh-syntax-highlighting)
```

| 插件 | 效果 | 状态 |
|------|------|------|
| `git` | 大量 git 别名（`gst`=git status, `gco`=git checkout...） | ✅ 已启用 |
| `zsh-autosuggestions` | 灰色提示历史命令，按 → 补全 | ✅ 已启用 |
| `zsh-syntax-highlighting` | 命令输入时实时语法高亮（红色=错误，绿色=正确） | ✅ 已启用 |

> 额外推荐：`z` 插件（智能跳转目录）。需要时加一行到 plugins 里即可，无需额外安装。

---

## 七、实践路线图

不要试图一次记住所有——会触发你的"开放型任务反感"。

**本周（3 天，每天 5 分钟）**：
- Day 1：练熟 `cd -`、`ll`、`Ctrl+A/E/W`、`Cmd+D 分屏`
- Day 2：用 `rg` 替代 Finder 搜索 + 练 `less` 和 `tail -f` 看日志
- Day 3：装 fzf + zsh-autosuggestions，体验智能补全 ✅ 已完成

**已完成**：
- ✅ 推荐工具全部安装（fzf, bat, fd, duti, htop, jq）
- ✅ 文件默认打开方式已统一（.md→Obsidian, .log/.txt→VSCode）
- ✅ iTerm2 Hotkey Window 已配置（双击 Right Command）
- ✅ Left Option 键已设为 Esc+（Option+←→ 现在可用来跳词）
- ✅ Ctrl+S 流控已关闭（stty -ixon），不会冻结终端
- ✅ macOS 系统快捷键已清理（禁用 Ctrl+Space 输入法切换、F11/F12 冗余热键）

**本月**：
- 练一次 vim 生存 6 条（随便打开一个配置文件试）
- 熟悉 bat（`bat ~/.zshrc`）和 fzf（`Ctrl+R`）的新体验

**什么时候学下一个？**
当你在终端做某件事感觉"应该有更快的方法"时，来问我。场景驱动的学习效率远高于提前储备。

---

---

## 八、iTerm2 自定义配置记录

以下是通过 plist 修改的配置项，重装系统或换电脑时需要重新设置。

| 配置项 | 当前值 | 默认值 | 说明 |
|--------|--------|--------|------|
| Left Option Key | Esc+（值为 1） | Normal（0） | 让 Option+←→ 在终端内按单词跳转 |
| Hotkey Window | 双击 Right Command | Option+Space | 任何应用里双击右侧 Cmd 弹出终端 |
| HotkeyModifiers | 8（Command） | 524288（Option） | 热键修饰键 |
| HotkeyModifierFlags | 16（Right） | 无 | 指定修饰键为右侧 |
| HotkeyCode | 54（Right Cmd） | — | **必须匹配修饰键自身 keycode，否则会误触字符键** |
| HotkeyActivatedByDoubleTap | true | false | 双击触发而非组合键 |

### iTerm2 plist 修改注意事项

**改 plist 前必须先 Cmd+Q 完全退出 iTerm2。** iTerm2 退出时会把内存状态写回 plist，如果改 plist 时它还在运行，修改必丢。这是经典坑。

### macOS 系统快捷键清理记录

以下系统全局快捷键已被禁用，避免与编辑器/终端冲突：

| 热键编号 | 快捷键 | 原用途 | 禁用原因 |
|----------|--------|--------|---------|
| #60 | Ctrl+Space | 切换输入法 | 与 VSCode IntelliSense 等 IDE 快捷键冲突 |
| #61 | Ctrl+Opt+Space | 切换输入法（菜单） | 同上 |
| #81 | F11 | 显示桌面（旧版） | 与 #64（Cmd+F3）重复 |
| #82 | F12 | Dashboard | macOS 已废弃 Dashboard |

*整理于 2026-06-09。如有新发现会持续更新。*

  1. Option+← / Option+→ → 应该能按单词跳转了
    2. Ctrl+S → 不再冻结终端，正常工作（如果 fzf 绑了它就能用）
    3. Ctrl+Space → 不再触发输入法切换（如果你之前靠这个切换输入法，现在需要改习惯或用菜单栏手动切）

    > 关于输入法：禁用的是 macOS 层的 Ctrl+Space。如果你需要快捷键切输入法，常见替代方案是用 Caps Lock（系统设置 → 键盘 → 输入法 → 用 Caps Lock 切换），完全不占组合键。要不要我一并帮你设了？
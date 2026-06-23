# YOLO Dataset Reviewer

一个用于筛选 YOLO 目标检测数据集的本地桌面工具。

第一版目标：

- 打开 YOLO 格式数据集
- 可视化每张图片的多个目标框和类别
- 上一张 / 下一张浏览
- 标记“需要重标”
- 标记“删除”
- 保存筛选进度
- 导出后把原数据集复制拆成三份：待重标、删除、合格

## 支持的数据集结构

推荐结构：

```text
dataset/
├─ images/
│  ├─ train/
│  └─ val/
├─ labels/
│  ├─ train/
│  └─ val/
└─ data.yaml
```

也支持简单结构：

```text
dataset/
├─ images/
└─ labels/
```

还兼容部分常见导出目录名，例如：

```text
dataset/
├─ JPEGImages/
├─ Visualization/
└─ yolo_labels/
```

其中 `Visualization`、`vis`、`preview`、`results` 这类可视化/预览目录会被扫描器跳过。

标签文件支持一张图片对应一个 `.txt`，`.txt` 内可以有多行目标框：

```text
0 0.5123 0.4368 0.2410 0.3302
2 0.2710 0.6000 0.1200 0.1800
```

## 安装依赖

先进入项目目录：

```powershell
cd E:\codex\yolo_dataset_reviewer
```

安装依赖：

```powershell
python -m pip install -r requirements.txt
```

默认 Tkinter 版只需要 Pillow。PySide6 版是可选界面，如果使用 conda 环境，推荐从 conda-forge 安装 PySide6：

```powershell
conda install -n my_env -c conda-forge pyside6
```

注意：如果需要下载/安装依赖，建议先确认网络和安装位置。PySide6 体积较大，通常下载和安装会占用数百 MB。

## 运行

```powershell
python main.py
```

当前默认启动的是 Tkinter 版界面，适合先跑通第一版筛选流程；PySide6 版源码保留在 `app/main_window.py`。

## GitHub Actions 打包 macOS app

项目内置了 `.github/workflows/build-macos-app.yml`。上传到 GitHub 后：

1. 打开仓库的 `Actions` 页面。
2. 选择 `Build macOS app`。
3. 点击 `Run workflow`。
4. 构建完成后，在运行详情页下载 `YoloDatasetReviewer-mac-app` artifact。

下载后解压会得到 `YoloDatasetReviewer.app`。这是未签名应用，macOS 第一次打开可能需要右键选择打开，或在终端执行：

```bash
xattr -dr com.apple.quarantine YoloDatasetReviewer.app
```

## 使用流程

1. 点击 `打开数据集`，选择数据集根目录。
2. 软件会自动扫描 `images` 与 `labels`。
3. 中间区域显示图片和 YOLO 框。
4. 用按钮或快捷键浏览：
   - `A` / 左方向键：上一张
   - `D` / 右方向键：下一张
   - `Space`：标记/取消待重标
   - `W` / `Delete`：标记/取消删除
   - `Ctrl+O`：打开数据集
   - `Ctrl+E`：导出三份数据集
5. 遇到框偏、漏标、类别错、框多余的图片，按 `Space` 标记待重标。
6. 遇到不要保留的坏图，按 `Delete` 标记删除。
7. 其他未标记图片自动归为合格。
8. 点击 `导出三份数据集`，选择输出目录。
9. 待重标导出模式：
   - 保留原标签：复制图片和原 `.txt`
   - 清空标签：复制图片并生成空 `.txt`

导出后结构类似：

```text
relabel_dataset/
├─ relabel/
│  ├─ images/
│  └─ labels/
├─ delete/
│  ├─ images/
│  └─ labels/
├─ qualified/
│  ├─ images/
│  └─ labels/
└─ review_split_manifest.json
```

## 设计原则

- 不直接修改原数据集
- 不直接删除原图片或标签
- 筛选进度保存在用户目录下的应用状态文件夹，不写入原数据集
- 筛选进度会按图片相对路径保存，关闭或意外退出后重新打开同一数据集会自动恢复
- 所有筛选结果通过复制导出完成

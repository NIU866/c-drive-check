# 磁盘空间分析器 · Disk Space Lens

[下载 Windows x64 便携版](https://github.com/NIU866/disk-space-lens/releases/latest)

解压后双击 `DiskSpaceLens.exe`。默认扫描 C 盘，也可选择任意本机文件夹。
完成后可在「大文件夹」和「大文件」中查看最多 200 项，双击结果或按「打开所在位置」。

扫描只读取文件元数据。系统保护目录、符号链接、目录联接和其他重解析点会被跳过。
显示的是可读取文件的逻辑大小。嵌套目录的大小包含子目录，硬链接可计入多个路径，磁盘实际剩余空间单独显示。

## 源码运行

Python 3.12，使用标准库 Tkinter。执行 `python disk_lens.py`。扫描测试用 `python -m unittest -v` 运行。

# CSV 敏感账号检查工具

这是一个给 Windows 本地使用的小工具。

功能：

- 启动时输入 `RapidAPI Key`
- 自动扫描当前程序所在文件夹下的所有 `.csv` 文件
- 读取每个 CSV 第一列的用户名
- 调用 `twitter241` 接口查询
- 在结果文件中追加 3 列：
  - `possibly_sensitive`
  - `profile_interstitial_type`
  - `是否敏感账号`

判断规则：

- `possibly_sensitive == true`，判定为敏感账号
- `profile_interstitial_type` 有值，判定为敏感账号
- 两者都没有，判定为非敏感账号

输出方式：

- 不修改原始 CSV
- 每个源文件会生成一个同目录结果文件：`原文件名_result.csv`
- 每处理完一行就立刻写入结果文件，避免中途中断后数据丢失
- 控制台实时显示总进度、当前文件进度和当前账号结果
- 如果运行失败，窗口会显示错误并等待用户按回车，不会直接闪退

断点续跑：

- 如果 `*_result.csv` 已存在，脚本会按已写入的行数继续处理
- 已经处理完的文件会自动跳过

## Windows 使用方式

如果你本地有 Python：

1. 双击 `run_checker.bat`
2. 输入你的 `RapidAPI Key`
3. 程序会自动扫描脚本所在文件夹里的 CSV

如果你要发给没有 Python 的 Windows 用户：

1. 把仓库放到 GitHub
2. 打开 GitHub Actions，运行 `Build Windows EXE` 工作流
3. 在 Actions Artifact 或 Release 页面下载 `csv-sensitive-checker.exe`
4. 把 exe 和要处理的 CSV 放到同一个文件夹
5. 用户双击 exe，输入 `RapidAPI Key` 后即可运行

如果你想直接在 GitHub Releases 提供下载：

1. 提交并推送代码到 `main`
2. 创建并推送版本标签，例如 `git tag v1.0.0 && git push origin v1.0.0`
3. GitHub 会自动运行 `Release Windows EXE`
4. exe 会直接挂到对应版本的 Release 页面

如果你要本地自己打包 exe：

1. 在 Windows 安装 Python
2. 双击 `build_exe.bat`
3. 打包后的 exe 在 `dist/` 下

## 仓库现在包含什么

- `check_sensitive_accounts.py`
  主程序。扫描目录中的 CSV，调用 RapidAPI 查询账号信息，输出 `*_result.csv`
- `run_checker.bat`
  给本地装了 Python 的 Windows 用户直接运行
- `.github/workflows/build-windows-exe.yml`
  推到 GitHub 后用于自动打包 Windows exe
- `.github/workflows/release-windows-exe.yml`
  推送版本标签后自动创建 GitHub Release 并附带 exe
- `build_exe.bat`
  给本地 Windows 环境手动打包 exe

## 推到 GitHub 前还要做的事

1. 在当前目录执行 `git init`
2. 创建 GitHub 仓库并添加远程
3. 提交代码并推送到 `main` 或 `master`
4. 到 GitHub 的 `Actions` 页面运行 `Build Windows EXE`

## CSV 格式

默认读取当前程序所在文件夹中的 CSV，并读取第一列作为用户名。
支持常见编码，包括 `UTF-8`、`UTF-8 with BOM`、`GBK`、`GB18030`、`UTF-16`。

示例：

```csv
username
jack
elonmusk
test_account
```

如果第一行第一列是 `username`、`user`、`账号`、`用户名` 这类表头，脚本会自动识别为表头。

## 失败处理

- 遇到 `429` 会自动等待后重试
- 遇到 `5xx` 或网络异常会自动重试
- 多次失败后，第 4 列会写入 `请求失败`

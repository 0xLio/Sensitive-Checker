# CSV 敏感账号检查工具

这是一个给 Windows 本地使用的小工具。

功能：

- 启动时输入 `RapidAPI Key`
- 扫描指定目录下的所有 `.csv` 文件
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

断点续跑：

- 如果 `*_result.csv` 已存在，脚本会按已写入的行数继续处理
- 已经处理完的文件会自动跳过

## Windows 使用方式

如果你本地有 Python：

1. 双击 `run_checker.bat`
2. 输入你的 `RapidAPI Key`
3. 输入 CSV 所在目录，或直接回车使用当前目录

如果你要发给没有 Python 的 Windows 用户：

1. 把仓库放到 GitHub
2. 打开 GitHub Actions，运行 `Build Windows EXE` 工作流
3. 在 Actions Artifact 里下载 `csv-sensitive-checker-windows`
4. 把里面的 `csv-sensitive-checker.exe` 发给用户，用户双击即可运行

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
- `build_exe.bat`
  给本地 Windows 环境手动打包 exe

## 推到 GitHub 前还要做的事

1. 在当前目录执行 `git init`
2. 创建 GitHub 仓库并添加远程
3. 提交代码并推送到 `main` 或 `master`
4. 到 GitHub 的 `Actions` 页面运行 `Build Windows EXE`

## CSV 格式

默认读取第一列作为用户名。

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

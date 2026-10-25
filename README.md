# 电子信息学习助手 V2.4-P2

参赛者：房鑫宇。包含知识学习、练习与复习，以及RC、直流、数字逻辑、信号与采样四个专业助手，共13个主题、39道固定题、20条本地参考笔记。

## 在线体验

在线入口：https://electronics-learning-agent-amke4wyuttfdwn6mofwcxk.streamlit.app/

源码仓库：https://github.com/fangx518-prog/electronics-learning-agent （main分支）

在线版由部署方在服务器配置模型接口，评审无需在网页填写API密钥；模型请求使用项目方配置的账户额度。真实密钥不包含在仓库或交付包中。2026年10月26日，云端配置Python3.12，六个页面加载、RC01练习判题、RC真实模型计算及采样两轮连续对话通过。采样验证覆盖5kHz信号在8kSa/s下得到3kHz，以及追问改为12kSa/s后得到5kHz、无混叠。本轮直流与数字逻辑只检查页面加载，未另测其模型对话；未进行未登录手机、多设备、并发或长期稳定性测试。

## 首次在本地运行

先完整解压，在包含app.py的项目目录打开PowerShell。完整步骤见安装与运行.md。

```powershell
py -3.14 -m venv .venv
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
& ".\.venv\Scripts\python.exe" -m streamlit run app.py
```

完成安装后可双击start_windows.cmd。它使用本目录或上一级已有的.venv；不会自动安装Python或依赖。

## 聊天配置

知识学习、固定练习、手动计算不需要密钥。本地源码版聊天需在项目根目录.env中配置自己的完整DEEPSEEK_API_KEY，并有网络和可用余额。首次配置可复制.env.example后编辑；不要覆盖已有私人配置。在线托管版由部署方通过服务器Secrets配置接口，使用者无需自行配置。压缩包不含真实密钥，本机localhost地址也不是在线作品链接。

## 检查与记录

```powershell
& ".\.venv\Scripts\python.exe" -m unittest discover -s . -p "verify_*.py"
```

预期104项离线自检通过。fixtures中的旧题与记录是人工构造的兼容性基准，不是用户个人学习历史，也不要求旁边存在旧版项目。

已提交手动参数可在本次会话跨页保留，但不会加入聊天。需要保存的学习进度与本轮报告请主动导出；刷新、关闭或重启后不保证恢复。两类导出文件用途不同：JSON恢复答题进度，Markdown阅读本轮学习记录。

## 支持范围与修订

仅包含理想入门教学计算，不是硬件实测、实际ADC选型、完整教材检索或实时联网搜索。专业范围和全部限制见作品说明书与页面说明。

P1修复采样追问循环；P2将同类引用纠正消息顺序修复同步至RC、直流和逻辑助手。每轮调用上限保持不变。详见V2.4-P1补丁说明.md、V2.4-P2终检修订说明.md及随包验证记录。

历史全量检查使用Windows、Python3.14和锁定依赖；本次云端Python3.12验证范围见上文及最终部署记录。未将这些结果扩大为其他系统、任意Python版本或全部在线功能通过。此包未开展同学试用、硬件或多设备测试。

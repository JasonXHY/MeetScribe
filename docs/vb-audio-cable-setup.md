# VB-Audio Cable 虚拟音频设备配置指南

## 什么是 VB-Audio Cable

VB-Audio Cable 是一个免费的虚拟音频驱动程序，可以在系统内部创建音频管道。MeetScribe 使用它来录制系统音频，避免使用 WASAPI Loopback 时停止录音会暂停媒体播放器的问题。

## 安装步骤

1. 访问 VB-Audio 官网: https://vb-audio.com/Cable/
2. 下载 VB-CABLE Driver Pack（免费版本即可）
3. 以管理员身份运行安装程序
4. 安装完成后重启电脑

## 在 MeetScribe 中启用

1. 打开 MeetScribe
2. 进入 **设置** 页面
3. 找到 **音频设备** 部分
4. 勾选 **使用 VB-Audio Cable（推荐）**
5. 点击 **保存设置**

## 工作原理

- 启用后，MeetScribe 优先使用 VB-Audio Cable 的 "CABLE Input" 设备录制系统音频
- 如果未检测到 VB-Audio Cable，会自动回退到 WASAPI Loopback
- VB-Audio Cable 录音时，停止录音不会影响正在播放的媒体

## 常见问题

### Q: 安装后设备未被识别

确保已重启电脑。可以在 Windows 声音设置中检查 "CABLE Input" 是否出现在录音设备列表中。

### Q: 录音没有声音

确认系统的音频输出已切换到 VB-Audio Cable：
1. 右键点击系统托盘的音量图标
2. 选择 "声音设置"
3. 在输出设备中选择 "CABLE Input"

### Q: 麦克风录音受影响

VB-Audio Cable 仅影响系统音频录制，麦克风录音不受影响。

## 卸载

如需卸载 VB-Audio Cable：
1. 在 Windows 设置 > 应用 中找到 VB-CABLE
2. 卸载后重启电脑
3. 在 MeetScribe 设置中取消勾选 "使用 VB-Audio Cable"

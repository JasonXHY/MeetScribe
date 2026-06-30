; 侧耳倾听 Inno Setup 安装脚本
; 编译命令: iscc installer.iss

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName=侧耳倾听
AppVersion=1.0
AppPublisher=JasonXHY
AppPublisherURL=https://github.com/JasonXHY/MeetScribe
AppSupportURL=https://github.com/JasonXHY/MeetScribe/issues
AppUpdatesURL=https://github.com/JasonXHY/MeetScribe/releases
DefaultDirName={autopf}\MeetScribe
DefaultGroupName=侧耳倾听
LicenseFile=LICENSE_CN.md
OutputDir=installer_output
OutputBaseFilename=MeetScribe-1.0-Setup
SetupIconFile=assets\logo.ico
UninstallDisplayIcon={app}\侧耳倾听.exe
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1

[Files]
; 主程序
Source: "dist\侧耳倾听\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; 模型文件（必须保持 models/models/iic/ 结构，代码期望 cache_dir/models/iic/model_name）
; 不压缩模型文件（已是压缩数据，再压缩浪费构建时间）
Source: "models\models\iic\*"; DestDir: "{localappdata}\MeetScribe\models\models\iic"; Flags: ignoreversion recursesubdirs createallsubdirs nocompression
; VB-Cable 安装包（供用户手动安装）
Source: "drivers\VBCABLE_Driver_Pack45\*"; DestDir: "{app}\drivers\VBCABLE_Driver_Pack45"; Flags: ignoreversion recursesubdirs createallsubdirs nocompression

[Icons]
Name: "{group}\侧耳倾听"; Filename: "{app}\侧耳倾听.exe"
Name: "{group}\{cm:UninstallProgram,侧耳倾听}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\侧耳倾听"; Filename: "{app}\侧耳倾听.exe"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\侧耳倾听"; Filename: "{app}\侧耳倾听.exe"; Tasks: quicklaunchicon

[Run]
; 安装完成后启动程序
Filename: "{app}\侧耳倾听.exe"; Description: "安装完成后启动侧耳倾听"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; 卸载时清理 AppData 中的配置和数据（不清理 models 和 recordings）
Type: filesandordirs; Name: "{localappdata}\MeetScribe\config"
Type: filesandordirs; Name: "{localappdata}\MeetScribe\data"
Type: files; Name: "{localappdata}\MeetScribe\install_path.txt"
Type: files; Name: "{localappdata}\MeetScribe\data_dir.txt"

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var
  DataDir: String;
  VBCableResult: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    DataDir := ExpandConstant('{localappdata}\MeetScribe');
    if not DirExists(DataDir) then
    begin
      CreateDir(DataDir);
    end;
    SaveStringToFile(DataDir + '\install_path.txt', ExpandConstant('{app}'), False);
    SaveStringToFile(DataDir + '\data_dir.txt', DataDir, False);

    // VB-Cable 安装提示
    VBCableResult := MsgBox('是否安装 VB-Audio Cable？' + #13#10 +
      'VB-Audio Cable 是虚拟音频设备，用于录制线上会议的系统音频。' + #13#10 +
      '如果只需要录制麦克风音频，可以跳过。',
      mbConfirmation, MB_YESNO);
    if VBCableResult = IDYES then
    begin
      Exec(ExpandConstant('{app}\drivers\VBCABLE_Driver_Pack45\VBCABLE_Setup_x64.exe'), '', '', SW_SHOWNORMAL, ewWaitUntilTerminated, VBCableResult);
    end;
  end;
end;

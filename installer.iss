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
Source: "models\models\iic\*"; DestDir: "{app}\models\models\iic"; Flags: ignoreversion recursesubdirs createallsubdirs
; VB-Cable 安装包（需包含 .inf 驱动文件）
Source: "drivers\VBCABLE_Driver_Pack45\*"; DestDir: "{tmp}\vbcable"; Flags: ignoreversion recursesubdirs createallsubdirs deleteafterinstall

[Icons]
Name: "{group}\侧耳倾听"; Filename: "{app}\侧耳倾听.exe"
Name: "{group}\{cm:UninstallProgram,侧耳倾听}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\侧耳倾听"; Filename: "{app}\侧耳倾听.exe"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\侧耳倾听"; Filename: "{app}\侧耳倾听.exe"; Tasks: quicklaunchicon

[Run]
; 安装 VB-Cable（静默模式）
Filename: "{tmp}\vbcable\VBCABLE_Setup_x64.exe"; Parameters: "/VERYSILENT /INSTALL /SUPPRESSMSGBOXES /NORESTART"; StatusMsg: "安装虚拟音频设备..."; Flags: waituntilterminated skipifsilent
; 安装完成后启动程序
Filename: "{app}\侧耳倾听.exe"; Parameters: "--data-dir ""{userappdata}\MeetScribe"""; Description: "安装完成后启动侧耳倾听"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var
  DataDir: String;
begin
  if CurStep = ssPostInstall then
  begin
    DataDir := ExpandConstant('{userappdata}\MeetScribe');
    if not DirExists(DataDir) then
    begin
      CreateDir(DataDir);
    end;
    SaveStringToFile(DataDir + '\install_path.txt', ExpandConstant('{app}'), False);
    SaveStringToFile(DataDir + '\data_dir.txt', DataDir, False);
  end;
end;

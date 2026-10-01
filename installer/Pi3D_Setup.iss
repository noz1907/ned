; ============================================================================
;  Pi3D - Windows Kurulum Sihirbazi (Inno Setup betigi)
;  PiVision - Industrial Smart Vision System
;
;  DERLEME: elle derlenmez; exebuild.py (ya da installer\build_installer.bat)
;  surumu version.json'dan okuyup gecirir:
;      ISCC.exe Pi3D_Setup.iss /DMyVer="<surum>" /DMySrc="<dist\Pi3D_v..\Pi3D>"
; ============================================================================
#ifndef MyVer
  #error Surum verilmedi. installer\build_installer.bat ya da exebuild.py calistirin.
#endif
#ifndef MySrc
  #define MySrc "..\dist\Pi3D_v" + MyVer + "\Pi3D"
#endif
#define MyApp "Pi3D"
#define MyPub "PiVision - Industrial Smart Vision System"
#define MyExe "Pi3D.exe"

[Setup]
AppId={{6B2D1F4A-7C3E-4E8B-9A51-PIVISION0003}
AppName={#MyApp}
AppVersion={#MyVer}
AppVerName={#MyApp} {#MyVer}
AppPublisher={#MyPub}
DefaultDirName=C:\Pivision\Pi3D
DisableDirPage=no
DefaultGroupName={#MyApp}
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=Pi3D_Kurulum_v{#MyVer}
SetupIconFile=..\logo\pi3d.ico
WizardImageFile=wizard_large.bmp
WizardSmallImageFile=wizard_small.bmp
WizardStyle=modern
Compression=lzma2/ultra64
SolidCompression=yes
PrivilegesRequired=admin
ShowLanguageDialog=no
UninstallDisplayIcon={app}\Pi3D.ico
UninstallDisplayName={#MyApp} {#MyVer}
; Lisans ve deneme kaydi kullanici profilindedir (%LOCALAPPDATA%\Pi3D);
; kaldirma onlara dokunmaz, yeniden kurulumda lisans yeniden istenmez.

[Languages]
Name: "tr"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
Source: "{#MySrc}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#MyApp}"; Filename: "{app}\{#MyExe}"; IconFilename: "{app}\Pi3D.ico"; WorkingDir: "{app}"
Name: "{group}\{#MyApp} Kullanim Kilavuzu"; Filename: "{app}\KULLANIM.md"
Name: "{group}\{#MyApp} Kaldir"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyApp}"; Filename: "{app}\{#MyExe}"; IconFilename: "{app}\Pi3D.ico"; WorkingDir: "{app}"; Tasks: desktopicon

[UninstallDelete]
Type: files; Name: "{autodesktop}\Pi3D*.lnk"
Type: filesandordirs; Name: "{app}\__pycache__"

[Run]
Filename: "{app}\{#MyExe}"; Description: "{cm:LaunchProgram,{#MyApp}}"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent

[Messages]
WelcomeLabel1=Pi3D kurulum sihirbazina hos geldiniz
WelcomeLabel2=Bu sihirbaz [name] surum {#MyVer} yazilimini bilgisayariniza kuracaktir.%n%nPiVision - Industrial Smart Vision System.%n%n3B modelden parca listesi, teknik resim, acinim, pafta, lazer ve kaynak resmi.
FinishedHeadingLabel=Pi3D kurulumu tamamlandi
FinishedLabelNoIcons=Pi3D bilgisayariniza kuruldu.
FinishedLabel=Pi3D bilgisayariniza kuruldu. Masaustu kisayolundan baslatabilirsiniz.%n%nIlk acilista Yardim > Lisans ekranindaki makine kimligini PiVision'a gonderin; gelen pi3d.lic dosyasini ayni ekrandan yukleyin.

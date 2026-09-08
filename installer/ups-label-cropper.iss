; UPS Label Cropper - Inno Setup 6 installer script.
;
; Compiled in CI (see .github/workflows/ci.yml) right after the PyInstaller
; one-dir build, producing a single
;   dist/UPS-Label-Cropper-Setup-<version>-windows-x64.exe
; Local build (from the repo root, after `uv run pyinstaller ...`):
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\ups-label-cropper.iss
;
; The installer is UNSIGNED: SmartScreen may still show an "unknown publisher"
; reputation warning on first run. That is distinct from the
; Trojan:Win32/Wacatac.B!ml heuristic (fixed by the one-dir layout), and only
; an Authenticode signature removes it.

; ---------------------------------------------------------------------------
; Version resolution: UPS_LABEL_CROPPER_VERSION (set by CI from the release
; tag, or from pyproject.toml -- see the "Resolve build version" step in
; .github/workflows/ci.yml) wins; otherwise a clearly-fake 0.0.0 for
; unmanaged local builds. A leading "v" is stripped exactly like
; build/version_info.py does, so the EXE and the installer always match.
;
; Deliberately expression-only: ISPP has no statement blocks (#function with
; begin/while/:= does not exist -- only #sub/#endsub wrapping expressions),
; so the pyproject.toml fallback lives in CI rather than here.
; ---------------------------------------------------------------------------

#define EnvVersion GetEnv("UPS_LABEL_CROPPER_VERSION")
#if defined(EnvVersion) && EnvVersion != ""
  #if Copy(EnvVersion, 1, 1) == "v"
    #define AppVersion Copy(EnvVersion, 2, 64)
  #else
    #define AppVersion EnvVersion
  #endif
#else
  #define AppVersion "0.0.0"
#endif

[Setup]
; NEVER regenerate this GUID: it is what makes upgrade-in-place work and
; keeps a single Add/Remove Programs entry across versions.
AppId={{FA271B17-B85F-4AE1-9156-C2D912A105E3}
AppName=UPS Label Cropper
AppVersion={#AppVersion}
AppVerName=UPS Label Cropper {#AppVersion}
AppPublisher=twilsonco
AppPublisherURL=https://github.com/twilsonco/UPS-Label-Cropper
AppSupportURL=https://github.com/twilsonco/UPS-Label-Cropper/issues
AppUpdatesURL=https://github.com/twilsonco/UPS-Label-Cropper/releases

VersionInfoVersion={#AppVersion}
VersionInfoTextVersion={#AppVersion}
VersionInfoProductVersion={#AppVersion}
VersionInfoProductTextVersion={#AppVersion}
VersionInfoCompanyName=twilsonco
VersionInfoProductName=UPS Label Cropper
VersionInfoDescription=UPS Label Cropper Setup
VersionInfoCopyright=Copyright (C) 2026 twilsonco

; Per-user default: autostart.py writes HKCU\...\CurrentVersion\Run, which is
; per-user, so a per-user install is the consistent choice. The dialog
; override lets power users opt into a machine-wide install.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DefaultDirName={autopf}\UPS Label Cropper
DefaultGroupName=UPS Label Cropper
DisableProgramGroupPage=yes
DisableWelcomePage=no
UninstallDisplayName=UPS Label Cropper
UninstallDisplayIcon={app}\UPS-Label-Cropper.exe
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=UPS-Label-Cropper-Setup-{#AppVersion}-windows-x64
SetupIconFile=..\assets\icon.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; A running tray app locks its own EXE, so let Setup detect and close it
; during upgrade-in-place (default behaviour, made explicit here).
CloseApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Whole PyInstaller one-dir tree (EXE + _internal/). SourceDir is relative to
; this script, i.e. <repo>/dist/UPS-Label-Cropper/.
Source: "..\dist\UPS-Label-Cropper\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\UPS Label Cropper"; Filename: "{app}\UPS-Label-Cropper.exe"
Name: "{group}\Uninstall UPS Label Cropper"; Filename: "{uninstallexe}"
Name: "{autodesktop}\UPS Label Cropper"; Filename: "{app}\UPS-Label-Cropper.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\UPS-Label-Cropper.exe"; Description: "{cm:LaunchProgram,UPS Label Cropper}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; PyInstaller leaves strays here and there across upgrades; never touch the
; user's config at {userappdata}\UPS-Label-Cropper\ (that is outside {app}
; and is intentionally preserved by the uninstaller).
Type: filesandordirs; Name: "{app}\_internal"
Type: dirifempty; Name: "{app}"

[Code]
// Remove the HKCU autostart entry on uninstall so a removed app can't leave a
// dangling Run key pointing at a deleted EXE. autostart.py owns this value,
// so the uninstaller -- not [Registry] -- is the right place to clear it:
// RegDeleteValue returns False (no dialog, no aborted uninstall) when the
// value was never created. We must NOT use uninsdeletekey here: the Run key
// is shared by every app on the machine.
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    RegDeleteValue(HKEY_CURRENT_USER,
      'Software\Microsoft\Windows\CurrentVersion\Run', 'UPSLabelCropper');
end;

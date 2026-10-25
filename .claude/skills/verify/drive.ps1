param([string]$Command, [string]$A = "", [string]$B = "", [string]$C = "")
$ErrorActionPreference = "Stop"
$Scratch = Split-Path -Parent $MyInvocation.MyCommand.Path
$Exe = Join-Path $Scratch "verify-src\dist\SimpleTool.exe"
$Data = Join-Path $Scratch "verify-data"
$Shots = Join-Path $Scratch "exe-shots"
New-Item -ItemType Directory -Force $Shots | Out-Null

Add-Type -ReferencedAssemblies System.Drawing @"
using System; using System.Text; using System.Runtime.InteropServices; using System.Drawing; using System.Collections.Generic;
public class Win {
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern IntPtr FindWindowW(string cls, string title);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern bool GetCursorPos(out POINT p);
  [DllImport("user32.dll")] public static extern void mouse_event(uint flags, uint dx, uint dy, uint data, UIntPtr extra);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetClassNameW(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetWindowTextW(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
  [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X, Y; }
  public static IntPtr Find(string title) { return FindWindowW(null, title); }  // PowerShell turns $null into ""
  public static Bitmap Shot(IntPtr h) {
    RECT r; GetWindowRect(h, out r);
    var bmp = new Bitmap(r.R - r.L, r.B - r.T);
    using (var g = Graphics.FromImage(bmp)) { IntPtr hdc = g.GetHdc(); PrintWindow(h, hdc, 2); g.ReleaseHdc(hdc); }
    return bmp;
  }
  public static Bitmap Screen(int l, int t, int r, int b) {
    var bmp = new Bitmap(r - l, b - t);
    using (var g = Graphics.FromImage(bmp)) { g.CopyFromScreen(l, t, 0, 0, bmp.Size); }
    return bmp;
  }
  public static void Click(int x, int y) {
    POINT old; GetCursorPos(out old);
    SetCursorPos(x, y); System.Threading.Thread.Sleep(120);
    mouse_event(2, 0, 0, 0, UIntPtr.Zero); System.Threading.Thread.Sleep(60); mouse_event(4, 0, 0, 0, UIntPtr.Zero);
    System.Threading.Thread.Sleep(150); SetCursorPos(old.X, old.Y);
  }
  public static List<string> Windows(string wantClass) { return Windows(wantClass, false); }
  public static List<string> Windows(string wantClass, bool all) {
    var found = new List<string>();
    EnumWindows((h, l) => {
      if (!all && !IsWindowVisible(h)) return true;
      var cls = new StringBuilder(256); GetClassNameW(h, cls, 256);
      var title = new StringBuilder(256); GetWindowTextW(h, title, 256);
      if (string.IsNullOrEmpty(wantClass) || cls.ToString() == wantClass) {
        RECT r; GetWindowRect(h, out r); uint pid; GetWindowThreadProcessId(h, out pid);
        found.Add(h.ToInt64() + "|" + cls + "|" + title + "|" + r.L + "," + r.T + "," + r.R + "," + r.B + "|" + pid);
      }
      return true; }, IntPtr.Zero);
    return found;
  }
}
"@
[Win]::SetProcessDPIAware() | Out-Null

function Main-Window {
  $h = [Win]::Find("SimpleTool")
  if ($h -eq [IntPtr]::Zero) { throw "no SimpleTool window" }
  return $h
}

switch ($Command) {
  "start" {
    $env:LOCALAPPDATA = $Data
    Start-Process -FilePath $Exe -WorkingDirectory (Split-Path $Exe)
    "started $Exe"
  }
  "procs" {
    Get-CimInstance Win32_Process -Filter "Name='SimpleTool.exe'" | ForEach-Object {
      $p = Get-Process -Id $_.ProcessId -ErrorAction SilentlyContinue
      $py = if ($p) { @($p.Modules | Where-Object { $_.ModuleName -like 'python3*.dll' }).Count } else { -1 }
      "$($_.ProcessId) parent=$($_.ParentProcessId) python=$py size=$((Get-Item $_.ExecutablePath).Length) $($_.ExecutablePath)"
    }
  }
  "shot" {
    $h = Main-Window
    $bmp = [Win]::Shot($h); $path = Join-Path $Shots "$A.png"; $bmp.Save($path); "saved $path $($bmp.Width)x$($bmp.Height)"
  }
  "rect" {
    $h = Main-Window; $r = New-Object Win+RECT; [Win]::GetWindowRect($h, [ref]$r) | Out-Null; "$($r.L),$($r.T),$($r.R),$($r.B)"
  }
  "click" {
    # offsets from the main window's top-left corner
    $h = Main-Window; $r = New-Object Win+RECT; [Win]::GetWindowRect($h, [ref]$r) | Out-Null
    [Win]::Click($r.L + [int]$A, $r.T + [int]$B); "clicked $([int]$A),$([int]$B)"
  }
  "clickabs" { [Win]::Click([int]$A, [int]$B); "clicked abs $A,$B" }
  "windows" { [Win]::Windows($(if ($A) { $A } else { $null })) | Where-Object { $_ -match 'SimpleTool|#32768|\|Update|\|What' } }
  "pidwins" { [Win]::Windows($null, $true) | Where-Object { $_ -match "\|$A$" } }
  "menushot" {
    $m = [Win]::Windows("#32768") | Select-Object -First 1
    if (-not $m) { throw "no menu" }
    $parts = $m.Split("|"); $c = $parts[3].Split(",")
    $bmp = [Win]::Screen([int]$c[0], [int]$c[1], [int]$c[2], [int]$c[3]); $path = Join-Path $Shots "$A.png"; $bmp.Save($path); "menu $($parts[3]) saved $path $($bmp.Width)x$($bmp.Height)"
  }
  "shotwin" {
    # PrintWindow of any window by exact title
    $h = [Win]::Find($A); if ($h -eq [IntPtr]::Zero) { throw "no window $A" }
    $bmp = [Win]::Shot($h); $path = Join-Path $Shots "$B.png"; $bmp.Save($path); "saved $path $($bmp.Width)x$($bmp.Height)"
  }
  "kill" {
    Get-CimInstance Win32_Process -Filter "Name='SimpleTool.exe'" | Where-Object { $_.ExecutablePath -like "$Scratch*" } |
      ForEach-Object { taskkill /T /F /PID $_.ProcessId | Out-Null; "killed $($_.ProcessId)" }
  }
  default { "commands: start procs shot rect click clickabs windows menushot shotwin kill" }
}

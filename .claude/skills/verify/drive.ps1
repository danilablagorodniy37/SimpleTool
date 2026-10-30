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
  [DllImport("user32.dll")] public static extern IntPtr WindowFromPoint(POINT p);
  [DllImport("user32.dll")] public static extern IntPtr GetAncestor(IntPtr h, uint flags);
  [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint flags);
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  // The process that owns the top-level window at a screen point: a click there goes to that process
  public static uint OwnerAt(int x, int y) {
    POINT p; p.X = x; p.Y = y; uint pid; GetWindowThreadProcessId(GetAncestor(WindowFromPoint(p), 2), out pid); return pid;
  }
  // Puts the visible Tk windows of a process above the others without activating them: topmost, then back
  public static void Raise(uint want) {
    EnumWindows((h, l) => {
      uint pid; GetWindowThreadProcessId(h, out pid);
      var cls = new StringBuilder(64); GetClassNameW(h, cls, 64);
      if (pid == want && IsWindowVisible(h) && cls.ToString() == "TkTopLevel") {
        SetWindowPos(h, new IntPtr(-1), 0, 0, 0, 0, 0x0013); SetWindowPos(h, new IntPtr(-2), 0, 0, 0, 0, 0x0013);
      }
      return true; }, IntPtr.Zero);
  }
  public static void Wheel(int x, int y, int notches) {
    POINT old; GetCursorPos(out old); SetCursorPos(x, y);
    for (int i = 0; i < notches; i++) { mouse_event(0x0800, 0, 0, unchecked((uint)-120), UIntPtr.Zero); System.Threading.Thread.Sleep(40); }
    SetCursorPos(old.X, old.Y);
  }
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

function Test-Pids {
  # The app processes of the test copy (the ones that load python312.dll), never the user's own SimpleTool
  @(Get-CimInstance Win32_Process -Filter "Name='SimpleTool.exe'" | Where-Object { $_.ExecutablePath -like "$Scratch*" } |
    ForEach-Object { [uint32]$_.ProcessId })
}

function Safe-Click([int]$X, [int]$Y) {
  # Clicks only when the window at the point belongs to the test copy: a window that opened behind another one
  # (an IDE, a browser) would otherwise take the click
  $pids = Test-Pids
  foreach ($id in $pids) { [Win]::Raise($id) }
  Start-Sleep -Milliseconds 300
  $owner = [Win]::OwnerAt($X, $Y)
  if ($pids -notcontains $owner) { return "NOT clicked: the window at $X,$Y belongs to pid $owner, not to the test copy" }
  [Win]::Click($X, $Y); return "clicked $X,$Y"
}

switch ($Command) {
  "start" {
    $env:LOCALAPPDATA = $Data
    Start-Process -FilePath $Exe -WorkingDirectory (Split-Path $Exe)
    "started $Exe"
  }
  "startlimited" {
    # Without administrator rights: runas with the Basic User trust level, through a .cmd that sets LOCALAPPDATA.
    # The app then asks to restart as administrator (a modal dialog: press Continue without rights)
    $cmd = Join-Path $Scratch "start-limited.cmd"
    Set-Content -Encoding ascii $cmd "@echo off`r`nset `"LOCALAPPDATA=$Data`"`r`nstart `"`" `"$Exe`""
    runas /trustlevel:0x20000 $cmd
    "started without administrator rights: $Exe"
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
    Safe-Click ($r.L + [int]$A) ($r.T + [int]$B)
  }
  "clickabs" { Safe-Click ([int]$A) ([int]$B) }
  "wheel" {
    # scrolls down by B notches (10 by default) at the screen point A, as "X,Y", over the test copy only
    $x, $y = $A.Split(",") | ForEach-Object { [int]$_ }
    $pids = Test-Pids; foreach ($id in $pids) { [Win]::Raise($id) }; Start-Sleep -Milliseconds 300
    $owner = [Win]::OwnerAt($x, $y)
    if ($pids -notcontains $owner) { "NOT scrolled: the window at $x,$y belongs to pid $owner" }
    else { [Win]::Wheel($x, $y, $(if ($B) { [int]$B } else { 10 })); "scrolled at $x,$y" }
  }
  "windows" {
    # The test copy's windows by process, whatever language their titles are in, and the open menus
    $pids = Test-Pids
    [Win]::Windows($(if ($A) { $A } else { $null })) | Where-Object {
      $_ -match '#32768' -or ($_ -match 'TkTopLevel' -and $pids -contains [uint32]($_.Split('|')[-1])) }
  }
  "pidwins" { [Win]::Windows($null, $true) | Where-Object { $_ -match "\|$A$" } }
  "menushot" {
    $pids = Test-Pids
    $m = [Win]::Windows("#32768") | Where-Object { $pids -contains [uint32]($_.Split('|')[-1]) } | Select-Object -First 1
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
  default { "commands: start startlimited procs shot rect click clickabs wheel windows pidwins menushot shotwin kill" }
}

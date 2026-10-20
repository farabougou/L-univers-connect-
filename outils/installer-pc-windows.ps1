# Installation complète sur un PC Windows : Claude Code + outils vidéo + projet L'univers connect.
# À coller dans une fenêtre PowerShell normale. Durée : 10 à 25 minutes selon la connexion.
# Windows demandera « Oui » 2 ou 3 fois (Mode développeur, Git, Node.js) : cliquez Oui.
& {
  $ErrorActionPreference = "Continue"
  function Rafraichir-Path { $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User") }
  function Etape($n, $texte) { Write-Host "`n[$n/7] $texte" -ForegroundColor Cyan }

  if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    Write-Host "winget est absent : installez « App Installer » depuis le Microsoft Store, puis recollez ce script." -ForegroundColor Red
    return
  }

  Etape 1 "Mode développeur (pour les raccourcis des skills) : cliquez Oui"
  Start-Process reg -ArgumentList 'add HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock /t REG_DWORD /f /v AllowDevelopmentWithoutDevLicense /d 1' -Verb RunAs -Wait -WindowStyle Hidden

  Etape 2 "Git, Node.js, Python et ffmpeg"
  foreach ($id in "Git.Git", "OpenJS.NodeJS.LTS", "Python.Python.3.12", "Gyan.FFmpeg") {
    Write-Host "  - $id"
    winget install --id $id -e --silent --accept-package-agreements --accept-source-agreements | Out-Null
  }
  Rafraichir-Path

  Etape 3 "Claude Code"
  Invoke-RestMethod https://claude.ai/install.ps1 | Invoke-Expression
  # l'installeur pose claude.exe dans ~\.local\bin sans toujours l'ajouter au PATH
  $bin = Join-Path $HOME ".local\bin"
  $p = [Environment]::GetEnvironmentVariable("Path", "User")
  if ($p -notlike "*$bin*") { [Environment]::SetEnvironmentVariable("Path", "$p;$bin", "User") }
  Rafraichir-Path

  Etape 4 "Modules Python pour les scripts de montage"
  py -3.12 -m pip install --upgrade pip --quiet
  py -3.12 -m pip install numpy scipy soundfile pillow --quiet

  Etape 5 "Récupération du projet (une fenêtre GitHub peut s'ouvrir : connectez-vous)"
  git config --global core.symlinks true
  # dossier à part : Documents\L-univers-connect- peut déjà contenir une autre branche (projet Asset Intelligence)
  $dossier = Join-Path $HOME "Documents\Univers-videos"
  if (Test-Path $dossier) { Write-Host "  Le projet vidéo existe déjà : $dossier" }
  else { git clone --depth 1 -b claude/upbeat-noether-hso8ah https://github.com/farabougou/L-univers-connect-.git $dossier }

  Etape 6 "Vérification"
  foreach ($c in "claude --version", "git --version", "node --version", "py -3.12 --version", "ffmpeg -version") {
    try { $r = Invoke-Expression $c 2>&1 | Select-Object -First 1; Write-Host ("  {0,-22} {1}" -f $c, ($r -replace " Copyright.*", "")) }
    catch { Write-Host ("  {0,-22} MANQUANT" -f $c) -ForegroundColor Red }
  }
  $lien = Get-Item (Join-Path $dossier ".claude\skills\hyperframes") -ErrorAction SilentlyContinue
  if ($lien -and $lien.PSIsContainer) { Write-Host "  Skills HyperFrames     OK" -ForegroundColor Green }
  else { Write-Host "  Skills HyperFrames     à réparer : redémarrez le PC, supprimez le dossier $dossier puis recollez ce script" -ForegroundColor Yellow }

  Etape 7 "Terminé"
  Set-Location $dossier
  Write-Host "`nTout est installé. Tapez maintenant :  claude" -ForegroundColor Green
  Write-Host "La première fois, une page s'ouvre pour vous connecter à votre compte Claude."
}

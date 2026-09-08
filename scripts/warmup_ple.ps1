# PLE region warmup: read only the PLE data span (offset 536018816, 22.4GB) to fill file cache
$f = 'C:\Users\antho\.lmstudio\models\agentionai\Qwen3.8-Flash-Next-ROCmFP4-FAST-imatrix-GGUF\Qwen3.8-Flash-Next-ROCmFP4-FAST-v2-ple16-JOINED.gguf'
$off = 536018816
$len = 22400101220
$fs = [System.IO.File]::OpenRead($f)
$null = $fs.Seek($off, 'Begin')
$sw = [System.Diagnostics.Stopwatch]::StartNew()
$buf = New-Object byte[] (64MB)
$total = [long]0
while ($total -lt $len) {
    $want = [int][Math]::Min([long]$buf.Length, [long]($len - $total))
    $n = $fs.Read($buf, 0, $want)
    if ($n -le 0) { break }
    $total += $n
}
$fs.Close()
$sw.Stop()
$gb = [math]::Round($total/1GB,2)
$secs = [math]::Round($sw.Elapsed.TotalSeconds,1)
Write-Output ("warmed {0} GB of PLE in {1}s = {2} GB/s" -f $gb, $secs, [math]::Round($gb/$secs,2))
$os = Get-CimInstance Win32_OperatingSystem
Write-Output ('FreePhys after warmup: '+[math]::Round($os.FreePhysicalMemory/1MB,1)+'GB')

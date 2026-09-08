# prefill benchmark: ~25K token prompt, measure prompt_ms
$chunk = "The quick brown fox jumps over the lazy dog while a curious robot paints colorful patterns on old factory walls nearby. "
$prompt = $chunk * 1100   # ~24K tokens
$body = @{ prompt=$prompt; n_predict=8; temperature=0.0; ignore_eos=$true } | ConvertTo-Json -Compress
try {
    $r = Invoke-RestMethod -Uri 'http://127.0.0.1:1234/completion' -Method Post -ContentType 'application/json' -Body $body -TimeoutSec 600
    $pt = [math]::Round($r.timings.prompt_ms/1000,2)
    $pn = $r.timings.prompt_n
    Write-Output ('prompt_n: '+$pn)
    Write-Output ('prompt_time: '+$pt+'s')
    Write-Output ('PREFILL: '+[math]::Round($pn/($r.timings.prompt_ms/1000),1)+' t/s')
} catch { Write-Output ('err: '+$_.Exception.Message) }

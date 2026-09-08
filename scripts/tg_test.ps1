$body = @{ prompt="Write a detailed story about a robot learning to paint."; n_predict=128; temperature=0.8; ignore_eos=$true } | ConvertTo-Json -Compress
$r = Invoke-RestMethod -Uri 'http://127.0.0.1:1234/completion' -Method Post -ContentType 'application/json' -Body $body -TimeoutSec 180
Write-Output ('TG: '+[math]::Round($r.timings.predicted_n/($r.timings.predicted_ms/1000),2)+' t/s ('+$r.timings.predicted_n+' tokens)')
Get-Content C:\llama-build\joined_mtp_log.txt -Tail 1 | ForEach-Object {$_}

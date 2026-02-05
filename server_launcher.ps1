# Auto-generated launcher script - DO NOT EDIT
Set-Location 'C:\devlop\acm2\acm2'
$env:Path = 'C:\Program Files\Python311;C:\Program Files\Python311\Scripts;' + $env:Path
python -u -m uvicorn app.main:app `
    --host 0.0.0.0 `
    --port 443 `
    --ssl-keyfile 'C:\devlop\acm2\certs\cloudflare.key' `
    --ssl-certfile 'C:\devlop\acm2\certs\cloudflare.crt' `
    2>&1 | Tee-Object -FilePath 'C:\devlop\acm2\server.log'

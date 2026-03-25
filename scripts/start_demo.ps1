param(
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 8000,
    [switch]$Reload
)

$args = @("--host", $BindHost, "--port", $Port)
if ($Reload) {
    $args += "--reload"
}

python -m marketgame @args

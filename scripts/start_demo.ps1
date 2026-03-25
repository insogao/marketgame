param(
    [string]$Host = "127.0.0.1",
    [int]$Port = 8000,
    [switch]$Reload
)

$args = @("--host", $Host, "--port", $Port)
if ($Reload) {
    $args += "--reload"
}

python -m marketgame @args

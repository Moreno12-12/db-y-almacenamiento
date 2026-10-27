[CmdletBinding()]
param(
    [switch]$SinDatos,
    [switch]$SoloBenchmark,
    [switch]$SoloDashboard
)

# ------------------------------------------------------------------
# automatizar_pipeline.ps1
# Infraestructura como Codigo: automatiza el pipeline de UrbanRush.
# Uso:  powershell -ExecutionPolicy Bypass -File scripts\automatizar_pipeline.ps1
# Flags: -SinDatos      omite la generacion masiva de datos
#        -SoloBenchmark ejecuta solo el benchmark
#        -SoloDashboard ejecuta solo el dashboard
# ------------------------------------------------------------------

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$Log = Join-Path $Root "pipeline.log"
$script:Resultados = @()

# Usar el python del entorno virtual si existe (creado por iac_setup.py)
$PythonCmd = "python"
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
if (Test-Path $VenvPython) {
    $PythonCmd = $VenvPython
}

function Escribir-Log {
    param([string]$Mensaje)
    $linea = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') | $Mensaje"
    Write-Host $linea
    Add-Content -Path $Log -Value $linea -Encoding UTF8
}

function Ejecutar-Paso {
    param([string]$Nombre, [string]$Script)
    Escribir-Log ">> [$Nombre] ejecutando: $PythonCmd $Script"
    & $PythonCmd $Script 2>&1 | ForEach-Object { Add-Content -Path $Log -Value "     $_" -Encoding UTF8 }
    $codigo = $LASTEXITCODE
    if ($codigo -eq 0) {
        $script:Resultados += [PSCustomObject]@{ Paso = $Nombre; Estado = "OK" }
        Escribir-Log "   [OK] $Nombre"
    }
    else {
        $script:Resultados += [PSCustomObject]@{ Paso = $Nombre; Estado = "FALLO" }
        Escribir-Log "   [FALLO] $Nombre (exit code $codigo)"
    }
}

if (Test-Path $Log) { Remove-Item $Log }
Escribir-Log "=== INICIO AUTOMATIZACION PIPELINE URBANRUSH ==="

# 1. Verificar Python
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Escribir-Log "[FALLO] Python no encontrado en el PATH"
    exit 1
}
Escribir-Log "[OK] Python: $($python.Source)"

# 2. Instalar dependencias
Escribir-Log ">> Instalando dependencias (requirements.txt)..."
& $PythonCmd -m pip install -r requirements.txt --quiet
if ($LASTEXITCODE -eq 0) {
    Escribir-Log "[OK] Dependencias instaladas/verificadas"
}
else {
    Escribir-Log "[FALLO] Instalacion de dependencias"
}

# 3. Validar conexion a MongoDB Atlas
Ejecutar-Paso "conexion" "conexion.py"

# 4. Pipeline
if ($SoloBenchmark) {
    Ejecutar-Paso "benchmark" "scripts/benchmark.py"
}
elseif ($SoloDashboard) {
    Ejecutar-Paso "dashboard" "scripts/dashboard_monitoreo.py"
}
else {
    Ejecutar-Paso "estructura" "scripts/crear_estructura.py"
    if ($SinDatos) {
        Escribir-Log ">> Omitiendo generacion masiva de datos (-SinDatos)"
    }
    else {
        Ejecutar-Paso "datos_masivos" "scripts/generar_datos_masivos.py"
    }
    Ejecutar-Paso "etl_olap" "scripts/transformar_oltp_a_olap.py"
    Ejecutar-Paso "benchmark" "scripts/benchmark.py"
    Ejecutar-Paso "data_lake" "scripts/data_lake.py"
    Ejecutar-Paso "spark_jobs" "scripts/spark_jobs.py"
    Ejecutar-Paso "data_warehouse" "scripts/data_warehouse.py"
    Ejecutar-Paso "dashboard" "scripts/dashboard_monitoreo.py"
}

# 5. Resumen
Escribir-Log "=== RESUMEN ==="
foreach ($r in $script:Resultados) {
    Escribir-Log ("  {0,-22} {1}" -f $r.Paso, $r.Estado)
}
$fallos = ($script:Resultados | Where-Object { $_.Estado -eq "FALLO" }).Count
if ($fallos -eq 0) {
    Escribir-Log "[OK] Pipeline completado sin errores. Log: $Log"
}
else {
    Escribir-Log "[ATENCION] $fallos paso(s) con fallo. Revisar el log: $Log"
    exit 1
}
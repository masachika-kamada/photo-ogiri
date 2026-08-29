param(
    [string]$ResourceGroup = "photo-ogiri-poc",
    [string]$Location = "japaneast",
    [ValidatePattern("^[a-z0-9]{3,11}$")]
    [string]$Prefix = "photoogiri",
    [string]$Subscription,
    [switch]$WhatIfOnly
)

$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$OutputEncoding = [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
    throw "Azure CLI is required. In Azure Cloud Shell it is preinstalled; on Windows use the official installer or ZIP distribution."
}

if ($Subscription) {
    az account set --subscription $Subscription
    if ($LASTEXITCODE -ne 0) { throw "Could not select Azure subscription." }
}
az account show --output none
if ($LASTEXITCODE -ne 0) { throw "Run 'az login' in this terminal before deploying." }

az bicep version --output none 2>$null
if ($LASTEXITCODE -ne 0) {
    az bicep install
    if ($LASTEXITCODE -ne 0) { throw "Could not install the user-local Bicep CLI." }
}
az bicep build --file "$PSScriptRoot/main.bicep" --stdout | Out-Null
if ($LASTEXITCODE -ne 0) { throw "main.bicep did not compile." }
az bicep build --file "$PSScriptRoot/apps.bicep" --stdout | Out-Null
if ($LASTEXITCODE -ne 0) { throw "apps.bicep did not compile." }

$alphabet = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
$random = -join (1..24 | ForEach-Object { $alphabet[(Get-Random -Maximum $alphabet.Length)] })
$postgresPassword = "Og!${random}"
$encodedLogin = [Uri]::EscapeDataString("photoogiriadmin")
$tag = Get-Date -Format "yyyyMMddHHmmss"
$existingDatabaseUrl = $null

function Wait-AcrRun {
    param([string]$Registry, [string]$RunId)
    while ($true) {
        $runStatus = az acr task show-run --registry $Registry --run-id $RunId --query status --output tsv
        if ($LASTEXITCODE -ne 0) { throw "Could not read ACR build status for run '$RunId'." }
        Write-Host "ACR build $RunId status: $runStatus"
        if ($runStatus -eq "Succeeded") { return }
        if ($runStatus -in @("Failed", "Canceled", "Error", "Timeout")) {
            throw "ACR build '$RunId' ended with status '$runStatus'."
        }
        Start-Sleep -Seconds 15
    }
}

az group create --name $ResourceGroup --location $Location --output none
if ($LASTEXITCODE -ne 0) { throw "Could not create or access resource group '$ResourceGroup'." }

$existingApiName = az deployment group list `
    --resource-group $ResourceGroup `
    --query "[?name=='photo-ogiri-apps'].properties.outputs.apiName.value | [0]" `
    --output tsv
if ($LASTEXITCODE -ne 0) { throw "Could not inspect previous application deployments." }
if ($existingApiName) {
    $existingDatabaseUrl = az containerapp secret list `
        --resource-group $ResourceGroup `
        --name $existingApiName `
        --show-values `
        --query "[?name=='database-url'].value | [0]" `
        --output tsv
    if ($LASTEXITCODE -ne 0 -or -not $existingDatabaseUrl) {
        throw "The existing database secret could not be read; refusing to rotate the PostgreSQL password."
    }
    $credentials = ([Uri]$existingDatabaseUrl).UserInfo -split ":", 2
    if ($credentials.Count -ne 2) { throw "The existing database URL is invalid." }
    $postgresPassword = [Uri]::UnescapeDataString($credentials[1])
}

if ($WhatIfOnly) {
    az deployment group what-if `
        --resource-group $ResourceGroup `
        --template-file "$PSScriptRoot/main.bicep" `
        --parameters prefix=$Prefix location=$Location postgresAdminPassword=$postgresPassword
    if ($LASTEXITCODE -ne 0) { throw "Infrastructure what-if failed." }
    Write-Host "Infrastructure what-if completed. No billable resources were deployed."
    exit 0
}

az deployment group create `
    --resource-group $ResourceGroup `
    --name "photo-ogiri-infra" `
    --template-file "$PSScriptRoot/main.bicep" `
    --parameters prefix=$Prefix location=$Location postgresAdminPassword=$postgresPassword `
    --output none
if ($LASTEXITCODE -ne 0) { throw "Infrastructure deployment failed." }

$outputs = az deployment group show --resource-group $ResourceGroup --name "photo-ogiri-infra" --query properties.outputs --output json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) { throw "Could not read infrastructure outputs." }
$acrName = $outputs.acrName.value
$loginServer = $outputs.acrLoginServer.value
$apiImage = "$loginServer/photo-ogiri-api:$tag"
$workerImage = "$loginServer/photo-ogiri-worker:$tag"
if ($existingDatabaseUrl) {
    $databaseUrl = $existingDatabaseUrl
}
else {
    $encodedPassword = [Uri]::EscapeDataString($postgresPassword)
    $databaseUrl = "postgresql+psycopg://${encodedLogin}:${encodedPassword}@$($outputs.postgresServerName.value).postgres.database.azure.com:5432/photoogiri?sslmode=require"
}

Push-Location (Split-Path $PSScriptRoot -Parent)
try {
    $apiRunId = az acr build --registry $acrName --image "photo-ogiri-api:$tag" --file Dockerfile.api . --no-logs --query runId --output tsv --only-show-errors
    if ($LASTEXITCODE -ne 0) { throw "API image build failed." }
    Wait-AcrRun -Registry $acrName -RunId $apiRunId
    $workerRunId = az acr build --registry $acrName --image "photo-ogiri-worker:$tag" --file Dockerfile.worker . --no-logs --query runId --output tsv --only-show-errors
    if ($LASTEXITCODE -ne 0) { throw "Worker image build failed." }
    Wait-AcrRun -Registry $acrName -RunId $workerRunId
}
finally {
    Pop-Location
}

Write-Host "Waiting 60 seconds for managed identity role assignments to propagate..."
Start-Sleep -Seconds 60

$appParameters = @(
    "location=$Location",
    "storageAccountName=$($outputs.storageAccountName.value)",
    "containerEnvironmentName=$($outputs.containerEnvironmentName.value)",
    "acrName=$acrName",
    "appIdentityName=$($outputs.appIdentityName.value)",
    "appIdentityClientId=$($outputs.appIdentityClientId.value)",
    "databaseUrl=$databaseUrl",
    "apiImage=$apiImage",
    "workerImage=$workerImage"
)

az deployment group what-if `
    --resource-group $ResourceGroup `
    --template-file "$PSScriptRoot/apps.bicep" `
    --parameters $appParameters `
    --no-pretty-print
if ($LASTEXITCODE -ne 0) { throw "Container Apps what-if failed." }

$appDeployment = $null
for ($attempt = 1; $attempt -le 4; $attempt++) {
    $appDeployment = az deployment group create `
        --resource-group $ResourceGroup `
        --name "photo-ogiri-apps" `
        --template-file "$PSScriptRoot/apps.bicep" `
        --parameters $appParameters `
        --query properties.outputs.applicationUrl.value `
        --output tsv
    if ($LASTEXITCODE -eq 0) { break }
    if ($attempt -eq 4) { throw "Container Apps deployment failed after role-propagation retries." }
    $delay = 30 * $attempt
    Write-Warning "Container Apps deployment attempt $attempt failed; retrying in $delay seconds."
    Start-Sleep -Seconds $delay
}

Write-Host "Photo Ogiri is deployed: $appDeployment"
Write-Host "Keep this resource group name for cleanup: $ResourceGroup"
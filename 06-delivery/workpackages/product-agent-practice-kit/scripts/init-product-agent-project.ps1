[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectRoot,

    [switch]$Write,

    [switch]$InitializeProjectSkills,

    [switch]$InitializeSpecKitSkills
)

$ErrorActionPreference = 'Stop'

$toolkitRoot = Split-Path -Parent $PSScriptRoot
$templatesRoot = Join-Path $toolkitRoot 'templates'
$candidateRoot = [System.IO.Path]::GetFullPath($ProjectRoot)
$volumeRoot = [System.IO.Path]::GetPathRoot($candidateRoot)

if ($candidateRoot -eq $volumeRoot) {
    throw "ProjectRoot cannot be a filesystem root: $candidateRoot"
}

$directories = @(
    '.product-agent',
    '.specify/memory',
    '.specify/templates',
    '.agents/skills',
    '01-inputs/raw',
    '02-product-baseline',
    '03-requirement-discovery',
    'specs',
    '04-demo',
    '05-validation',
    '06-deliverables'
)

$fileMap = [ordered]@{
    'AGENTS.template.md' = 'AGENTS.md'
    'project-profile.template.md' = '.product-agent/project-profile.md'
    'setup-report.template.md' = '.product-agent/setup-report.md'
    'constitution.template.md' = '.specify/memory/constitution.md'
    'source-index.template.md' = '01-inputs/source-index.md'
    'product-baseline.template.md' = '02-product-baseline/product-baseline.md'
    'decision-log.template.md' = '03-requirement-discovery/decision-log.md'
    'validation-ledger.template.md' = '05-validation/validation-ledger.md'
}

Write-Host "Target project: $candidateRoot"
Write-Host "Mode: $(if ($Write) { 'write missing files only' } else { 'dry-run' })"

foreach ($relativeDirectory in $directories) {
    $targetDirectory = Join-Path $candidateRoot $relativeDirectory
    if ($Write) {
        New-Item -ItemType Directory -Force -Path $targetDirectory | Out-Null
    } else {
        Write-Host "[plan] directory $relativeDirectory"
    }
}

foreach ($templateName in $fileMap.Keys) {
    $sourceFile = Join-Path $templatesRoot $templateName
    $relativeTarget = $fileMap[$templateName]
    $targetFile = Join-Path $candidateRoot $relativeTarget

    if (Test-Path -LiteralPath $targetFile) {
        Write-Host "[skip] existing $relativeTarget"
        continue
    }

    if ($Write) {
        Copy-Item -LiteralPath $sourceFile -Destination $targetFile
        Write-Host "[create] $relativeTarget"
    } else {
        Write-Host "[plan] file $relativeTarget"
    }
}

if ($InitializeProjectSkills) {
    $coreSkillNames = @(
        'requirement-discovery',
        'write-prd',
        'project-skill-template',
        'manage-speckit-project-skills'
    )

    foreach ($skillName in $coreSkillNames) {
        $sourceSkill = Join-Path $toolkitRoot "skills/$skillName"
        $targetSkill = Join-Path $candidateRoot ".agents/skills/$skillName"

        if (Test-Path -LiteralPath $targetSkill) {
            Write-Host "[skip] existing project skill $skillName"
            continue
        }

        if ($Write) {
            Copy-Item -LiteralPath $sourceSkill -Destination $targetSkill -Recurse
            Write-Host "[create] project skill $skillName"
        } else {
            Write-Host "[plan] project skill $skillName"
        }
    }
}

if ($InitializeProjectSkills -or $InitializeSpecKitSkills) {
    if ($Write) {
        $manager = Join-Path $toolkitRoot 'skills/manage-speckit-project-skills/scripts/manage_speckit_project_skills.py'
        $arguments = @('-X', 'utf8', $manager, 'initialize', '--project-root', $candidateRoot, '--write')
        & python @arguments
        if ($LASTEXITCODE -ne 0) {
            throw "Spec Kit skill initialization failed with exit code $LASTEXITCODE"
        }
    } else {
        Write-Host '[plan] initialize six project-local speckit-* skills'
    }
}

if ($Write) {
    Write-Host 'Initialization complete. Replace template placeholders only from project evidence.'
} else {
    Write-Host 'Dry-run complete. Add -Write to create missing content without overwriting existing files.'
}

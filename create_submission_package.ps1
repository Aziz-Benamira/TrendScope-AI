# PowerShell script to create submission package

Write-Host "📦 Creating TrendScope-AI Submission Package..." -ForegroundColor Cyan

# Create output directory
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$outputDir = "TrendScope-AI_Submission_$timestamp"
$zipFile = "$outputDir.zip"

Write-Host "Creating temporary directory: $outputDir" -ForegroundColor Yellow
New-Item -ItemType Directory -Path $outputDir -Force | Out-Null

# Files and folders to include
$includeItems = @(
    "backend",
    "data_loader",
    "ml_service",
    "monitoring",
    "notebooks",
    "processors",
    "producers",
    "storage",
    "web-dashboard/src",
    "web-dashboard/public",
    "web-dashboard/*.json",
    "web-dashboard/*.js",
    "web-dashboard/*.html",
    "web-dashboard/*.md",
    "docs",
    "configs",
    "tests",
    "rag",
    "*.md",
    "*.yml",
    "*.yaml",
    "*.txt",
    "*.ini",
    "*.sh",
    "*.ps1",
    "*.tex",
    "Dockerfile",
    "Makefile",
    "LICENSE"
)

# Exclude patterns
$excludePatterns = @(
    "__pycache__",
    "node_modules",
    ".venv",
    "*.pyc",
    ".git",
    "dist",
    "build",
    ".DS_Store",
    "Thumbs.db",
    "*.log",
    "tmdb_dataset_files"
)

Write-Host "`n📁 Copying project files..." -ForegroundColor Cyan

# Copy each item
foreach ($item in $includeItems) {
    if ($item -like "*/*") {
        # Handle specific subdirectories
        $parts = $item -split "/"
        $parent = $parts[0]
        $child = $parts[1]
        
        if (Test-Path $parent) {
            Write-Host "  ✓ Copying $item" -ForegroundColor Green
            $destPath = Join-Path $outputDir $parent
            New-Item -ItemType Directory -Path $destPath -Force | Out-Null
            
            if ($child -eq "*.*") {
                Copy-Item -Path "$parent/*" -Destination $destPath -Recurse -Force -Exclude $excludePatterns
            } else {
                $sourcePath = Join-Path $parent $child
                if (Test-Path $sourcePath) {
                    Copy-Item -Path $sourcePath -Destination $destPath -Recurse -Force -Exclude $excludePatterns
                }
            }
        }
    } elseif ($item -like "*.*") {
        # Handle wildcard files in root
        Get-ChildItem -Path "." -Filter $item | ForEach-Object {
            Write-Host "  ✓ Copying $($_.Name)" -ForegroundColor Green
            Copy-Item -Path $_.FullName -Destination $outputDir -Force
        }
    } else {
        # Handle directories
        if (Test-Path $item) {
            Write-Host "  ✓ Copying $item/" -ForegroundColor Green
            
            # Copy directory, excluding patterns
            Copy-Item -Path $item -Destination $outputDir -Recurse -Force -Exclude $excludePatterns
            
            # Remove excluded subdirectories
            foreach ($exclude in $excludePatterns) {
                Get-ChildItem -Path $outputDir -Recurse -Directory -Filter $exclude -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
                Get-ChildItem -Path $outputDir -Recurse -File -Filter $exclude -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
            }
        }
    }
}

Write-Host "`n📊 Package Statistics:" -ForegroundColor Cyan
$totalSize = (Get-ChildItem -Path $outputDir -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB
$fileCount = (Get-ChildItem -Path $outputDir -Recurse -File).Count
Write-Host "  Files: $fileCount" -ForegroundColor Yellow
Write-Host "  Size: $([math]::Round($totalSize, 2)) MB" -ForegroundColor Yellow

Write-Host "`n🗜️ Creating ZIP archive..." -ForegroundColor Cyan
Compress-Archive -Path $outputDir -DestinationPath $zipFile -Force
Write-Host "  ✓ Created: $zipFile" -ForegroundColor Green

Write-Host "`n🧹 Cleaning up temporary files..." -ForegroundColor Cyan
Remove-Item -Path $outputDir -Recurse -Force

$zipSize = (Get-Item $zipFile).Length / 1MB
Write-Host "`n✅ Submission package ready!" -ForegroundColor Green
Write-Host "  File: $zipFile" -ForegroundColor Yellow
Write-Host "  Size: $([math]::Round($zipSize, 2)) MB" -ForegroundColor Yellow

Write-Host "`n📋 Next Steps:" -ForegroundColor Cyan
Write-Host "  1. Review SUBMISSION_GUIDE.md for submission checklist" -ForegroundColor White
Write-Host "  2. Compile PROJECT_REPORT.tex to PDF" -ForegroundColor White
Write-Host "  3. Update GitHub repository with: git push origin main" -ForegroundColor White
Write-Host "  4. Submit $zipFile to your professor" -ForegroundColor White
Write-Host ""

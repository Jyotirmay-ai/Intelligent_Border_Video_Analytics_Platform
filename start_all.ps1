$ROOT = "D:\software Projects\SIH\ibvap-full-project"

Write-Host "Starting Next.js Dashboard..."
Start-Process powershell -WorkingDirectory "$ROOT\dashboard" -ArgumentList "-NoExit -Command `"npm run dev`""

Write-Host "Starting Video Simulator for CAM_05..."
Start-Process powershell -WorkingDirectory $ROOT -ArgumentList "-NoExit -Command `"& '$ROOT\.venv\Scripts\Activate.ps1'; python backend\ingestion\simulator.py --video data\sample_videos\5.mp4 --camera-id cam_05`""

Write-Host "Starting Live AI YOLO Geofence Engine for CAM_05..."
Start-Process powershell -WorkingDirectory $ROOT -ArgumentList "-NoExit -Command `"& '$ROOT\.venv\Scripts\Activate.ps1'; python modules\virtual-fence-intrusion-detection\engine\worker.py`""

Write-Host "Starting Sus Module AI Engine for CAM_04..."
Start-Process powershell -WorkingDirectory $ROOT -ArgumentList "-NoExit -Command `"& '$ROOT\.venv\Scripts\Activate.ps1'; python modules\suspicious-activity-detection\services\behavioral_worker.py`""

Write-Host "Starting Human Detection & Face Tracking for CAM_1..."
Start-Process powershell -WorkingDirectory $ROOT -ArgumentList "-NoExit -Command `"& '$ROOT\.venv\Scripts\Activate.ps1'; python modules\human_detection_tracking\main.py --cam 'D:\software Projects\SIH\ibvap-full-project\data\sample_videos\1.1.mp4'`""

Write-Host "Starting Vehicle Detection & Classification for CAM_02..."
Start-Process powershell -WorkingDirectory $ROOT -ArgumentList "-NoExit -Command `"& '$ROOT\.venv\Scripts\Activate.ps1'; python modules\vehicle-detection-classification\src\main.py --camera-id cam_02 --video data\sample_videos\2.1.mp4`""

Write-Host "Starting independent ANPR worker for CAM_03..."
Start-Process powershell -WorkingDirectory $ROOT -ArgumentList "-NoExit -Command `"& '$ROOT\.venv\Scripts\Activate.ps1'; python modules\anpr\cam3_worker.py --camera-id CAM_03 --video data\sample_videos\2.2.mp4`""

Write-Host "Starting Hardhat Blockchain Node..."
Start-Process powershell -WorkingDirectory "$ROOT\dashboard" -ArgumentList "-NoExit -Command `"npx hardhat node`""

Write-Host "Waiting 5s for the local blockchain to spin up..."
Start-Sleep -Seconds 5

Write-Host "Deploying EvidenceAnchor Smart Contract..."
Set-Location "$ROOT\dashboard"
npx hardhat run scripts/deploy.js --network localhost

Write-Host "Starting Ledger Verification API..."
Start-Process powershell -WorkingDirectory $ROOT -ArgumentList "-NoExit -Command `"& '$ROOT\.venv\Scripts\Activate.ps1'; python modules\blockchain-evidence-ledger\verify_api\main.py`""

Write-Host "Starting Ledger Worker (Hash Chain Builder)..."
Start-Process powershell -WorkingDirectory $ROOT -ArgumentList "-NoExit -Command `"& '$ROOT\.venv\Scripts\Activate.ps1'; python modules\blockchain-evidence-ledger\ledger_worker\main.py`""

Write-Host "All AI services and Blockchain modules have been launched in separate windows!"

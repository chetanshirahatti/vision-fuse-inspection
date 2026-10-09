# Fuse Vision Inspector

All-in-one inspection app: Dashboard, Calibration, Training, History, PLC/Modbus, Settings.

## Run (Windows / PowerShell)
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    python main.py

First start creates `data/` with a ready recipe (Fuse_80A_400A) built from assets/master.png.

## Workflow
1. Training   - load/capture master image, drag ROIs, name them, "Train & Save".
2. Calibration- review trained ROIs, test images, "Auto-calibrate" from samples/OK and samples/NOK, save limits.
3. Dashboard  - Image / Folder / Camera source, INSPECT or Auto-run. PASS only if every ROI >= its limit.
4. PLC        - Modbus TCP handshake (trigger -> inspect -> result/mask/done). Simulation mode needs no hardware.

## Build a .exe
    pip install pyinstaller
    pyinstaller --noconsole --name FuseVision --add-data "assets;assets" --add-data "samples;samples" main.py

## MindVision GigE camera (MV-GE2000M)
1. Install the MindVision SDK, connect the camera, close the MindVision viewer.
2. Settings -> Camera type = "MindVision GigE camera"; keep "Shrink pictures" at ~2000; press "Test camera".
3. Dashboard -> Source = Camera -> Start camera -> INSPECT.
Trigger modes: Continuous (free-run) or Software trigger (app fires the camera for every inspection / PLC trigger).
The SDK folder is registered by the app itself (needed for Python 3.8+); core/mvsdk.py is MindVision's own file.

## Trigger modes (Settings -> Camera -> Trigger mode)
- Software trigger (default): NO live stream. INSPECT button / PLC Modbus trigger fires the camera once -> one picture -> one result.
- Hardware trigger: camera waits for an electrical pulse on its trigger input; each pulse = one picture, inspected automatically.
  Check the camera datasheet for the trigger input pin and wire it to the PLC/sensor output. Pick rising or falling edge.
- Continuous: live stream, only for focusing / setup.

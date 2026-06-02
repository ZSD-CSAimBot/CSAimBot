import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, collect_dynamic_libs

PROJECT_ROOT = os.path.abspath(os.path.join(SPECPATH, '..'))

block_cipher = None

bin_deps = []
bin_deps += collect_dynamic_libs('tensorrt')
bin_deps += collect_dynamic_libs('onnxruntime')

data_deps = []
data_deps += collect_data_files('autobahn')
data_deps += collect_data_files('ultralytics')

hidden_deps = [
    'ultralytics', 'torch', 'torchvision', 'tensorrt', 'dearpygui', 
    'roslibpy', 'pyserial', 'cv2', 'fastrlock', 'fastrlock.rlock',
    'onnxruntime', 'onnx', 'onnxslim', 'mss', 'screeninfo', 'pynput', 
    'numpy', 'evdev'
]

a = Analysis(
    [os.path.join(PROJECT_ROOT, 'application', 'app.py')],
    pathex=[PROJECT_ROOT],
    binaries=bin_deps,
    datas=[
        (os.path.join(PROJECT_ROOT, 'application', 'detection_system', 'yolo', 'trained_model.pt'), 'application/detection_system/yolo'),
        (os.path.join(PROJECT_ROOT, 'application', 'gui_design', 'fonts'), 'application/gui_design/fonts'),
        (os.path.join(PROJECT_ROOT, 'application', 'gui_design', 'icons'), 'application/gui_design/icons'),
        (os.path.join(PROJECT_ROOT, 'application', 'simulation'), 'application/simulation')
    ] + data_deps,
    hiddenimports=hidden_deps,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

simulation_src_path = os.path.join(PROJECT_ROOT, 'application', 'simulation')
for root, _, files in os.walk(simulation_src_path):
    for file in files:
        if file.endswith('.py'):
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(root, PROJECT_ROOT)
            dest_folder = rel_path.replace('\\', '/')
            a.datas.append((full_path, dest_folder, 'DATA'))

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CsAimBot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='CsAimBot',
)
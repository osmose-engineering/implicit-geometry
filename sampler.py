import os
import json
import math
import zipfile
from loader import load_ifg, build_evaluator
from PIL import Image

# --- Parameters (could be CLI args in future) ---
IFG_PATH = 'examples/cube.ifg'      # input .ifg file
OUTPUT_DIR = 'output_slices'        # directory for slice images
LAYER_THICKNESS = 0.1               # mm
RES_X, RES_Y = 200, 200             # resolution (pixels)
OUTPUT_PM7M = 'output.pm7m'         # final printer file

# Load IFG and build evaluator
doc = load_ifg(IFG_PATH)
eval_fn = build_evaluator(doc['nodes'])

# Determine bounds from metadata or defaults
meta = doc.get('metadata', {})
bounds = meta.get('bounds', {
    'xmin': -5, 'xmax': 5,
    'ymin': -5, 'ymax': 5,
    'zmin': -5, 'zmax': 5
})

# Compute number of layers
zmin, zmax = bounds['zmin'], bounds['zmax']
num_layers = int(math.ceil((zmax - zmin) / LAYER_THICKNESS)) + 1
os.makedirs(OUTPUT_DIR, exist_ok=True)
print(f"Generating {num_layers} slices")

# Generate PNG slices
for i in range(num_layers):
    z = zmin + i * LAYER_THICKNESS
    img = Image.new('L', (RES_X, RES_Y))
    for ix in range(RES_X):
        for iy in range(RES_Y):
            x = bounds['xmin'] + ix * (bounds['xmax'] - bounds['xmin']) / (RES_X - 1)
            y = bounds['ymin'] + iy * (bounds['ymax'] - bounds['ymin']) / (RES_Y - 1)
            field_val = eval_fn(x, y, z)
            img.putpixel((ix, RES_Y - 1 - iy), 255 if field_val <= 0 else 0)
    slice_path = os.path.join(OUTPUT_DIR, f'slice_{i:04d}.png')
    img.save(slice_path)

# Package slices into .pm7m (Anycubic Photon Mono M7 Max format)
# Based on UVTools: uses ZIP archive with Info.json and Body/*.pwszImg entries ([github.com](https://github.com/sn4k3/UVtools/discussions/892?utm_source=chatgpt.com), [github.com](https://github.com/sn4k3/UVtools/blob/master/CHANGELOG.md?utm_source=chatgpt.com))
def wrap_to_pm7m(slice_dir, output_file, metadata):
    with zipfile.ZipFile(output_file, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        # Write metadata header
        zf.writestr('Info.json', json.dumps(metadata))
        # Add each slice with .pwszImg extension under Body/
        for fname in sorted(os.listdir(slice_dir)):
            if fname.endswith('.png'):
                arcname = f'Body/{fname.replace('.png', '.pwszImg')}'
                zf.write(os.path.join(slice_dir, fname), arcname)
    print(f"Packaged slices into {output_file}")

if __name__ == '__main__':
    # Extract printer settings or defaults
    pm7m_meta = {
        'layer_thickness': LAYER_THICKNESS,
        'resolution': [RES_X, RES_Y],
        'bounds': bounds
    }
    wrap_to_pm7m(OUTPUT_DIR, OUTPUT_PM7M, pm7m_meta)
    print('Done: .pm7m file ready for printing')

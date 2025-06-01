import json, math, sys
import trimesh
import functools

# Helper to load a mesh once and compute signed-distance on demand
@functools.lru_cache(maxsize=None)
def get_mesh_signed_distance(mesh_path):
    """
    Load a watertight mesh from mesh_path and return a function that computes
    signed distance for any (x,y,z) point.
    """
    mesh = trimesh.load(mesh_path)
    # If the mesh has holes, try to fill them so that winding/contains works
    if not mesh.is_watertight:
        mesh = mesh.copy().fill_holes()

    # Compute unsigned distance via on_surface, then check contains for sign
    def signed_dist(x, y, z):
        pt = [x, y, z]
        # nearest.on_surface returns (closest_points, distances, face_indices)
        closest, distances, _ = mesh.nearest.on_surface([pt])
        dist = distances[0]
        inside = mesh.contains([pt])[0]
        return -dist if inside else dist

    return signed_dist

def load_ifg(path):
    with open(path,'r') as f:
        return json.load(f)

# Primitive field functions
def cube_field(x,y,z,size):
    half = size/2.0
    return max(abs(x), abs(y), abs(z)) - half

def sphere_field(x,y,z,radius):
    return math.sqrt(x*x + y*y + z*z) - radius

def cylinder_field(x,y,z,radius,height):
    return max(math.sqrt(x*x + y*y) - radius, abs(z) - height/2.0)

# Lattice pattern (gyroid)
def gyroid_field(x,y,z,cell_size):
    cx,cy,cz = cell_size
    return ( math.cos(2*math.pi*x/cx)
           + math.cos(2*math.pi*y/cy)
           + math.cos(2*math.pi*z/cz) )

# Core evaluator

def evaluate_node(node_id, nodes_map, x,y,z):
    node = nodes_map[node_id]
    t = node['type']
    p = node.get('params', {})
    ins = node.get('inputs', [])

    if t == 'Cube':
        return cube_field(x,y,z, p['size'])
    if t == 'Sphere':
        return sphere_field(x,y,z, p['radius'])
    if t == 'Cylinder':
        return cylinder_field(x,y,z, p['radius'], p['height'])
    if t == 'Transform':
        src = ins[0]
        tx,ty,tz = p.get('translate',[0,0,0])
        return evaluate_node(src, nodes_map, x - tx, y - ty, z - tz)
    if t == 'Union':
        return min(
            evaluate_node(ins[0], nodes_map, x,y,z),
            evaluate_node(ins[1], nodes_map, x,y,z)
        )
    if t == 'Subtract':
        return max(
            evaluate_node(ins[0], nodes_map, x,y,z),
           -evaluate_node(ins[1], nodes_map, x,y,z)
        )
    if t == 'Intersect':
        return max(
            evaluate_node(ins[0], nodes_map, x,y,z),
            evaluate_node(ins[1], nodes_map, x,y,z)
        )
    if t == 'Lattice':
        cell = p['cell_size']
        thickness = p['thickness']
        lat = gyroid_field(x,y,z, cell)
        # lattice iso-surface at thickness
        return abs(lat) - thickness
    if t == 'Mesh':
        mesh_path = p['filename']
        distance_fn = get_mesh_signed_distance(mesh_path)
        return distance_fn(x, y, z)
    
    raise ValueError(f"Unknown node type: {t}")

# Build an evaluator from the graph (root is last node)
def build_evaluator(nodes):
    nm = {n['id']:n for n in nodes}
    root = nodes[-1]['id']
    return lambda x,y,z: evaluate_node(root, nm, x,y,z)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python loader.py <path.ifg>')
        sys.exit(1)

    doc = load_ifg(sys.argv[1])
    eval_fn = build_evaluator(doc['nodes'])
    # sample at origin
    val = eval_fn(0,0,0)
    print(f"Field at (0,0,0): {val}")

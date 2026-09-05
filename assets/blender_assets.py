# Paper Football — 3D asset generator
# Run with:   python3 assets/blender_assets.py            (pip-installed bpy)
#   or:       blender -b --factory-startup -P assets/blender_assets.py -- assets/renders
# Renders every game sprite (balls, bumpers, tokens, trophy) as transparent PNGs
# and every themed field turf as an opaque JPEG, all with Cycles (CPU).

import bpy
import bmesh
import math
import os
import sys

if "--" in sys.argv:
    OUT = sys.argv[sys.argv.index("--") + 1]
elif len(sys.argv) > 1 and not sys.argv[1].endswith(".py"):
    OUT = sys.argv[1]
else:
    OUT = "assets/renders"
os.makedirs(OUT, exist_ok=True)

SPRITE_RES = 384
FIELD_RES = (512, 1024)
SAMPLES = 48


# ---------------------------------------------------------------- scene setup
def fresh_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = SAMPLES
    sc.cycles.use_denoising = True
    try:
        sc.view_settings.view_transform = "Filmic"
        sc.view_settings.look = "Medium High Contrast"
    except TypeError:
        pass  # color management names differ across builds; defaults are fine
    return sc


def add_camera(loc, rot, ortho_scale=2.4):
    cam = bpy.data.cameras.new("cam")
    cam.type = "ORTHO"
    cam.ortho_scale = ortho_scale
    ob = bpy.data.objects.new("cam", cam)
    ob.location = loc
    ob.rotation_euler = rot
    bpy.context.collection.objects.link(ob)
    bpy.context.scene.camera = ob
    return ob


def add_sun(rot, energy=3.0, angle=0.3):
    li = bpy.data.lights.new("sun", "SUN")
    li.energy = energy
    li.angle = angle
    ob = bpy.data.objects.new("sun", li)
    ob.rotation_euler = rot
    bpy.context.collection.objects.link(ob)
    return ob


def add_fill(loc, energy=60, size=6):
    li = bpy.data.lights.new("fill", "AREA")
    li.energy = energy
    li.size = size
    ob = bpy.data.objects.new("fill", li)
    ob.location = loc
    ob.rotation_euler = (0, 0, 0)
    bpy.context.collection.objects.link(ob)
    return ob


def sprite_stage(ortho=2.4, cam_tilt=0.0):
    """Camera looking straight down -Z from above, key sun + soft fill."""
    add_camera((0, 0, 6), (cam_tilt, 0, 0), ortho)
    add_sun((math.radians(52), math.radians(-38), 0), 4.5)
    add_fill((0, -2, 5), 55, 8)
    w = bpy.context.scene.world = bpy.data.worlds.new("w")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.28, 0.28, 0.3, 1)
    w.node_tree.nodes["Background"].inputs[1].default_value = 0.35


def render(path, res_x=SPRITE_RES, res_y=SPRITE_RES, transparent=True, fmt="PNG"):
    sc = bpy.context.scene
    sc.render.resolution_x = res_x
    sc.render.resolution_y = res_y
    sc.render.film_transparent = transparent
    sc.render.image_settings.file_format = fmt
    if fmt == "PNG":
        sc.render.image_settings.color_mode = "RGBA"
        sc.render.image_settings.compression = 100
    else:
        sc.render.image_settings.color_mode = "RGB"
        sc.render.image_settings.quality = 78
    sc.render.filepath = os.path.abspath(os.path.join(OUT, path))
    bpy.ops.render.render(write_still=True)
    print("WROTE", sc.render.filepath)


# ---------------------------------------------------------------- materials
def mat(name, color, rough=0.5, metal=0.0, emit=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emit:
        b.inputs["Emission Color"].default_value = (*color, 1)
        b.inputs["Emission Strength"].default_value = emit
    return m


def swirl_mat(name, col_a, col_b, freq=6.0, twist=4.0, rough=0.35):
    """Peppermint-style spiral stripes built from object-space atan2."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    n = nt.nodes
    bsdf = n["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = rough
    tex = n.new("ShaderNodeTexCoord")
    sep = n.new("ShaderNodeSeparateXYZ")
    nt.links.new(tex.outputs["Object"], sep.inputs[0])
    at = n.new("ShaderNodeMath"); at.operation = "ARCTAN2"
    nt.links.new(sep.outputs["Y"], at.inputs[0])
    nt.links.new(sep.outputs["X"], at.inputs[1])
    # radius
    lenn = n.new("ShaderNodeVectorMath"); lenn.operation = "LENGTH"
    nt.links.new(tex.outputs["Object"], lenn.inputs[0])
    rmul = n.new("ShaderNodeMath"); rmul.operation = "MULTIPLY"
    rmul.inputs[1].default_value = twist
    nt.links.new(lenn.outputs["Value"], rmul.inputs[0])
    amul = n.new("ShaderNodeMath"); amul.operation = "MULTIPLY"
    amul.inputs[1].default_value = freq / (2 * math.pi)
    nt.links.new(at.outputs["Value"], amul.inputs[0])
    add = n.new("ShaderNodeMath"); add.operation = "ADD"
    nt.links.new(amul.outputs["Value"], add.inputs[0])
    nt.links.new(rmul.outputs["Value"], add.inputs[1])
    sin = n.new("ShaderNodeMath"); sin.operation = "SINE"
    smul = n.new("ShaderNodeMath"); smul.operation = "MULTIPLY"
    smul.inputs[1].default_value = 2 * math.pi
    nt.links.new(add.outputs["Value"], smul.inputs[0])
    nt.links.new(smul.outputs["Value"], sin.inputs[0])
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    ramp.color_ramp.elements[0].color = (*col_a, 1)
    ramp.color_ramp.elements[1].position = 0.5
    ramp.color_ramp.elements[1].color = (*col_b, 1)
    nt.links.new(sin.outputs["Value"], ramp.inputs[0])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    return m


def speckle_mat(name, base, spot, scale=9.0, rough=0.45):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    n = nt.nodes
    bsdf = n["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = rough
    vor = n.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = scale
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.22
    ramp.color_ramp.elements[0].color = (*spot, 1)
    ramp.color_ramp.elements[1].position = 0.34
    ramp.color_ramp.elements[1].color = (*base, 1)
    nt.links.new(vor.outputs["Distance"], ramp.inputs[0])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    return m


def paper_mat():
    m = bpy.data.materials.new("paper")
    m.use_nodes = True
    nt = m.node_tree
    n = nt.nodes
    bsdf = n["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.93, 0.94, 0.9, 1)
    bsdf.inputs["Roughness"].default_value = 0.72
    noise = n.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 60.0
    noise.inputs["Detail"].default_value = 6.0
    bump = n.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.08
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return m


# ---------------------------------------------------------------- mesh helpers
def new_obj(name, me):
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    return ob


def sphere(name, r=1.0, loc=(0, 0, 0), scale=(1, 1, 1), m=None, smooth=True, seg=48):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=loc, segments=seg, ring_count=seg // 2)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = scale
    if m:
        ob.data.materials.append(m)
    if smooth:
        bpy.ops.object.shade_smooth()
    return ob


def cyl(name, r=1.0, depth=1.0, loc=(0, 0, 0), rot=(0, 0, 0), m=None, smooth=True, verts=48):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=depth, location=loc, rotation=rot, vertices=verts)
    ob = bpy.context.active_object
    ob.name = name
    if m:
        ob.data.materials.append(m)
    if smooth:
        bpy.ops.object.shade_smooth()
    return ob


def cone(name, r1=1.0, r2=0.0, depth=1.0, loc=(0, 0, 0), rot=(0, 0, 0), m=None, smooth=True):
    bpy.ops.mesh.primitive_cone_add(radius1=r1, radius2=r2, depth=depth, location=loc, rotation=rot, vertices=48)
    ob = bpy.context.active_object
    ob.name = name
    if m:
        ob.data.materials.append(m)
    if smooth:
        bpy.ops.object.shade_smooth()
    return ob


def torus(name, major=1.0, minor=0.2, loc=(0, 0, 0), rot=(0, 0, 0), m=None, half=False):
    bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor,
                                     location=loc, rotation=rot,
                                     major_segments=64, minor_segments=24)
    ob = bpy.context.active_object
    ob.name = name
    if m:
        ob.data.materials.append(m)
    bpy.ops.object.shade_smooth()
    if half:  # keep the y >= 0 half (in local space)
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        kill = [v for v in bm.verts if v.co.y < -1e-4]
        bmesh.ops.delete(bm, geom=kill, context="VERTS")
        bm.to_mesh(ob.data)
        bm.free()
    return ob


def box(name, size=(1, 1, 1), loc=(0, 0, 0), rot=(0, 0, 0), m=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = size
    if m:
        ob.data.materials.append(m)
    return ob


# ================================================================ SPRITES
def ball_paper():
    """Folded paper football: a slim triangle 'tented' along its spine."""
    fresh_scene()
    sprite_stage(2.35)
    me = bpy.data.meshes.new("tri")
    h = 1.0        # half-height (tip to base center)
    w = 0.92       # half-width of the base
    t = 0.10       # paper thickness
    ridge = 0.34   # spine lift for the fold
    verts = [
        (0, h, 0), (w, -h, 0), (-w, -h, 0),          # bottom face
        (0, h, t + ridge), (w, -h, t), (-w, -h, t),  # top face (spine lifted)
        (0, -h, t + ridge * 0.7),                    # base mid, lifted -> fold ridge
    ]
    faces = [(0, 2, 1), (3, 4, 6), (3, 6, 5),
             (0, 1, 4, 3), (2, 0, 3, 5),
             (1, 6, 4), (1, 2, 6), (2, 5, 6)]
    me.from_pydata(verts, [], faces)
    me.update()
    ob = new_obj("paperball", me)
    ob.data.materials.append(paper_mat())
    mod = ob.modifiers.new("bevel", "BEVEL")
    mod.width = 0.02
    mod.segments = 2
    render("ball_grass.png")


def ball_unicorn():
    """Unicorn horn: golden-pink spiral cone, viewed from above pointing up."""
    fresh_scene()
    sprite_stage(2.5)
    m = swirl_mat("horn", (0.92, 0.25, 0.6), (0.95, 0.72, 0.25), freq=0, twist=7.0, rough=0.3)
    horn = cone("horn", r1=0.42, r2=0.02, depth=1.9, loc=(0, 0.1, 0.4),
                rot=(math.radians(-90), 0, 0), m=m)
    horn.scale = (1, 1, 1)
    # little star at the tip
    sm = mat("star", (1.0, 0.95, 0.55), 0.3, 0.0, emit=2.0)
    sphere("tipstar", 0.1, (0, 1.1, 0.42), m=sm)
    # base swirl ring
    torus("base", 0.34, 0.1, (0, -0.78, 0.4), (math.radians(90), 0, 0),
          m=mat("basegold", (0.95, 0.78, 0.35), 0.3, 0.8))
    render("ball_unicorn.png")


def ball_space():
    """Cartoon rocket pointing up (+Y)."""
    fresh_scene()
    sprite_stage(2.6)
    body = mat("body", (0.92, 0.93, 0.96), 0.35)
    red = mat("red", (0.85, 0.16, 0.18), 0.4)
    dark = mat("dark", (0.16, 0.2, 0.35), 0.15)
    flame = mat("flame", (1.0, 0.55, 0.1), 0.5, emit=4.0)
    cyl("hull", 0.34, 1.1, (0, 0, 0.4), (math.radians(90), 0, 0), m=body)
    cone("nose", 0.34, 0.02, 0.55, (0, 0.82, 0.4), (math.radians(-90), 0, 0), m=red)
    for sx in (-1, 1):
        box("fin", (0.1, 0.55, 0.34), (sx * 0.4, -0.5, 0.4),
            (0, 0, math.radians(sx * 14)), m=red)
    cyl("window", 0.14, 0.72, (0, 0.18, 0.4), (0, 0, 0), m=dark)
    cone("flame", 0.2, 0.02, 0.5, (0, -0.85, 0.4), (math.radians(90), 0, 0), m=flame)
    render("ball_space.png")


def ball_candy():
    """Lollipop: swirl disc + stick, facing the camera."""
    fresh_scene()
    sprite_stage(2.5)
    m = swirl_mat("pepper", (0.93, 0.2, 0.45), (0.98, 0.96, 0.95), freq=0, twist=5.0, rough=0.25)
    pop = cyl("pop", 0.62, 0.16, (0, 0.32, 0.4), (0, 0, 0), m=m)
    torus("rim", 0.62, 0.075, (0, 0.32, 0.4), (0, 0, 0),
          m=mat("rimc", (0.93, 0.2, 0.45), 0.25))
    cyl("stick", 0.055, 1.1, (0, -0.62, 0.36), (math.radians(90), 0, 0),
        m=mat("stick", (0.97, 0.96, 0.94), 0.4))
    render("ball_candy.png")


def ball_dino():
    """Spiky dino ball: green sphere with a ridge of back-plates."""
    fresh_scene()
    sprite_stage(2.45)
    green = speckle_mat("hide", (0.28, 0.62, 0.3), (0.16, 0.42, 0.2), 7.0, 0.5)
    plate = mat("plate", (0.95, 0.75, 0.3), 0.45)
    sphere("bod", 0.78, (0, 0, 0.3), m=green)
    for i, a in enumerate((-60, -20, 20, 60)):
        r = math.radians(a)
        d = 0.82
        cone(f"spk{i}", 0.16, 0.01, 0.42,
             (math.sin(r) * d, math.cos(r) * d, 0.3),
             (math.radians(-90) + 0, 0, -r), m=plate)
    render("ball_dino.png")


def bumper_football():
    fresh_scene()
    sprite_stage(2.4)
    # pigskin with white end-stripes painted on via |x| bands
    m = bpy.data.materials.new("pig")
    m.use_nodes = True
    nt = m.node_tree
    n = nt.nodes
    bsdf = n["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 0.5
    tex = n.new("ShaderNodeTexCoord")
    sep = n.new("ShaderNodeSeparateXYZ")
    nt.links.new(tex.outputs["Object"], sep.inputs[0])
    ab = n.new("ShaderNodeMath"); ab.operation = "ABSOLUTE"
    nt.links.new(sep.outputs["X"], ab.inputs[0])
    gt = n.new("ShaderNodeMath"); gt.operation = "GREATER_THAN"
    gt.inputs[1].default_value = 0.58
    nt.links.new(ab.outputs["Value"], gt.inputs[0])
    lt = n.new("ShaderNodeMath"); lt.operation = "LESS_THAN"
    lt.inputs[1].default_value = 0.74
    nt.links.new(ab.outputs["Value"], lt.inputs[0])
    both = n.new("ShaderNodeMath"); both.operation = "MULTIPLY"
    nt.links.new(gt.outputs["Value"], both.inputs[0])
    nt.links.new(lt.outputs["Value"], both.inputs[1])
    mixc = n.new("ShaderNodeMix"); mixc.data_type = "RGBA"
    mixc.inputs["A"].default_value = (0.42, 0.2, 0.1, 1)
    mixc.inputs["B"].default_value = (0.95, 0.95, 0.93, 1)
    nt.links.new(both.outputs["Value"], mixc.inputs["Factor"])
    nt.links.new(mixc.outputs["Result"], bsdf.inputs["Base Color"])
    white = mat("wh", (0.95, 0.95, 0.93), 0.35)
    sphere("ball", 1.0, (0, 0, 0.3), scale=(1.0, 0.6, 0.55), m=m)
    cyl("lace", 0.035, 0.7, (0, 0, 0.86), (0, math.radians(90), 0), m=white)
    for i in range(4):
        x = -0.24 + i * 0.16
        cyl(f"x{i}", 0.03, 0.2, (x, 0, 0.87), (math.radians(90), 0, 0), m=white)
    render("bump_grass.png")


def bumper_rainbow():
    fresh_scene()
    sprite_stage(2.5)
    cols = [(0.9, 0.15, 0.2), (0.98, 0.6, 0.1), (0.99, 0.9, 0.2),
            (0.25, 0.75, 0.35), (0.25, 0.5, 0.95), (0.55, 0.3, 0.85)]
    r = 1.0
    for i, c in enumerate(cols):
        torus(f"arc{i}", r - i * 0.14, 0.075, (0, -0.35, 0.3), (0, 0, 0),
              m=mat(f"c{i}", c, 0.35), half=True)
    cloud = mat("cloud", (0.97, 0.97, 1.0), 0.6)
    for sx in (-1, 1):
        sphere(f"cl{sx}", 0.3, (sx * 0.82, -0.38, 0.32), m=cloud)
        sphere(f"cl2{sx}", 0.22, (sx * 0.62, -0.46, 0.3), m=cloud)
    render("bump_unicorn.png")


def bumper_planet():
    fresh_scene()
    sprite_stage(2.5)
    bandm = bpy.data.materials.new("bands")
    bandm.use_nodes = True
    nt = bandm.node_tree
    n = nt.nodes
    bsdf = n["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 0.5
    tex = n.new("ShaderNodeTexCoord")
    sep = n.new("ShaderNodeSeparateXYZ")
    nt.links.new(tex.outputs["Object"], sep.inputs[0])
    wav = n.new("ShaderNodeMath"); wav.operation = "SINE"
    mul = n.new("ShaderNodeMath"); mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = 9.0
    nt.links.new(sep.outputs["Y"], mul.inputs[0])
    nt.links.new(mul.outputs["Value"], wav.inputs[0])
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.86, 0.55, 0.25, 1)
    ramp.color_ramp.elements[1].color = (0.95, 0.8, 0.55, 1)
    nt.links.new(wav.outputs["Value"], ramp.inputs[0])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    sphere("planet", 0.72, (0, 0, 0.3), m=bandm)
    ring = torus("ring", 1.05, 0.16, (0, 0, 0.3),
                 (math.radians(70), 0, math.radians(20)),
                 m=mat("ringm", (0.85, 0.75, 0.55), 0.4))
    ring.scale = (1, 1, 0.1)
    render("bump_space.png")


def bumper_candy():
    """Wrapped candy: striped sphere + twist cones."""
    fresh_scene()
    sprite_stage(2.5)
    m = swirl_mat("candy", (0.95, 0.35, 0.55), (0.98, 0.95, 0.96), freq=8.0, twist=0.0, rough=0.3)
    sphere("c", 0.62, (0, 0, 0.3), scale=(1, 0.85, 0.8), m=m)
    pink = mat("wrap", (0.95, 0.5, 0.65), 0.35)
    for sx in (-1, 1):
        cone(f"tw{sx}", 0.3, 0.05, 0.5, (sx * 0.82, 0, 0.3),
             (0, math.radians(sx * 90), 0), m=pink)
    render("bump_candy.png")


def bumper_egg():
    fresh_scene()
    sprite_stage(2.4)
    m = speckle_mat("egg", (0.93, 0.89, 0.78), (0.45, 0.55, 0.35), 8.0, 0.4)
    sphere("egg", 0.72, (0, 0, 0.3), scale=(1, 1.25, 1), m=m)
    render("bump_dino.png")


def token(kind):
    """Chunky coin, green (+) or red (−). Number text stays in the DOM."""
    fresh_scene()
    sprite_stage(2.3)
    if kind == "pos":
        base, rim = (0.03, 0.42, 0.18), (0.2, 0.75, 0.42)
    else:
        base, rim = (0.5, 0.04, 0.1), (0.85, 0.22, 0.3)
    cyl("coin", 0.85, 0.22, (0, 0, 0.3), m=mat("cm", base, 0.3))
    torus("rim", 0.85, 0.08, (0, 0, 0.42), m=mat("rm", rim, 0.25))
    render(f"tok_{kind}.png")


def trophy():
    fresh_scene()
    sprite_stage(2.7)
    gold = mat("gold", (0.95, 0.75, 0.25), 0.25, 1.0)
    wood = mat("wood", (0.3, 0.16, 0.09), 0.5)
    # front-facing build (camera looks down -Z, so build in XY plane)
    box("base", (1.1, 0.28, 0.5), (0, -1.05, 0.3), m=wood)
    box("base2", (0.7, 0.18, 0.5), (0, -0.83, 0.3), m=gold)
    cyl("stem", 0.1, 0.5, (0, -0.5, 0.3), (math.radians(90), 0, 0), m=gold)
    cup = cone("cup", 0.32, 0.62, 0.85, (0, 0.14, 0.3), (math.radians(-90), 0, 0), m=gold)
    torus("lip", 0.62, 0.06, (0, 0.56, 0.3), (math.radians(90), 0, 0), m=gold)
    for sx in (-1, 1):
        h = torus(f"h{sx}", 0.3, 0.06, (sx * 0.66, 0.2, 0.3), (0, 0, math.radians(90)))
        h.data.materials.append(gold)
    render("trophy.png")


# ================================================================ FIELDS
def field_plane(material):
    bpy.ops.mesh.primitive_plane_add(size=2, location=(0, 0, 0))
    ob = bpy.context.active_object
    ob.scale = (1, 2, 1)  # 1:2 aspect
    ob.data.materials.append(material)
    return ob


def field_stage():
    add_camera((0, 0, 5), (0, 0, 0), ortho_scale=2.0)
    bpy.context.scene.camera.data.ortho_scale = 2.0
    add_sun((math.radians(18), math.radians(-10), 0), 1.3)
    w = bpy.context.scene.world = bpy.data.worlds.new("w")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[1].default_value = 0.12


def _bands_node(nt, freq, col_a, col_b):
    """Horizontal bands from generated Y coordinate."""
    n = nt.nodes
    tex = n.new("ShaderNodeTexCoord")
    sep = n.new("ShaderNodeSeparateXYZ")
    nt.links.new(tex.outputs["Object"], sep.inputs[0])
    mul = n.new("ShaderNodeMath"); mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = freq
    nt.links.new(sep.outputs["Y"], mul.inputs[0])
    sin = n.new("ShaderNodeMath"); sin.operation = "SINE"
    nt.links.new(mul.outputs["Value"], sin.inputs[0])
    gt = n.new("ShaderNodeMath"); gt.operation = "GREATER_THAN"
    gt.inputs[1].default_value = 0.0
    nt.links.new(sin.outputs["Value"], gt.inputs[0])
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    ramp.color_ramp.elements[0].color = (*col_a, 1)
    ramp.color_ramp.elements[1].position = 0.5
    ramp.color_ramp.elements[1].color = (*col_b, 1)
    nt.links.new(gt.outputs["Value"], ramp.inputs[0])
    return tex, ramp


def field_grass():
    fresh_scene(); field_stage()
    m = bpy.data.materials.new("turf")
    m.use_nodes = True
    nt = m.node_tree
    n = nt.nodes
    bsdf = n["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 0.9
    tex, ramp = _bands_node(nt, math.pi * 10, (0.02, 0.16, 0.09), (0.03, 0.21, 0.12))
    noise = n.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 260.0
    noise.inputs["Detail"].default_value = 8.0
    mixn = n.new("ShaderNodeMix"); mixn.data_type = "RGBA"
    mixn.inputs["Factor"].default_value = 0.35
    nt.links.new(ramp.outputs["Color"], mixn.inputs["A"])
    dark = n.new("ShaderNodeMix"); dark.data_type = "RGBA"
    dark.inputs["Factor"].default_value = 1.0
    nt.links.new(noise.outputs["Fac"], dark.inputs["Factor"])
    dark.inputs["A"].default_value = (0.01, 0.1, 0.05, 1)
    dark.inputs["B"].default_value = (0.05, 0.26, 0.14, 1)
    nt.links.new(dark.outputs["Result"], mixn.inputs["B"])
    nt.links.new(mixn.outputs["Result"], bsdf.inputs["Base Color"])
    bump = n.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.25
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    field_plane(m)
    render("field_grass.jpg", *FIELD_RES, transparent=False, fmt="JPEG")


def field_unicorn():
    fresh_scene(); field_stage()
    m = bpy.data.materials.new("uni")
    m.use_nodes = True
    nt = m.node_tree
    n = nt.nodes
    bsdf = n["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 0.7
    tex = n.new("ShaderNodeTexCoord")
    sep = n.new("ShaderNodeSeparateXYZ")
    nt.links.new(tex.outputs["Object"], sep.inputs[0])
    map1 = n.new("ShaderNodeMapRange")
    map1.inputs["From Min"].default_value = -0.55
    map1.inputs["From Max"].default_value = 0.55
    nt.links.new(sep.outputs["Y"], map1.inputs["Value"])
    ramp = n.new("ShaderNodeValToRGB")
    cr = ramp.color_ramp
    cols = [(0.95, 0.45, 0.72), (0.97, 0.6, 0.38), (0.95, 0.85, 0.35),
            (0.45, 0.85, 0.55), (0.4, 0.62, 0.95), (0.68, 0.48, 0.95)]
    cr.elements[0].color = (*cols[0], 1)
    cr.elements[1].position = 1.0
    cr.elements[1].color = (*cols[-1], 1)
    for i, c in enumerate(cols[1:-1], start=1):
        e = cr.elements.new(i / (len(cols) - 1))
        e.color = (*c, 1)
    nt.links.new(map1.outputs["Result"], ramp.inputs[0])
    # sparkles
    vor = n.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 60.0
    spark = n.new("ShaderNodeValToRGB")
    spark.color_ramp.elements[0].position = 0.06
    spark.color_ramp.elements[0].color = (1, 1, 1, 1)
    spark.color_ramp.elements[1].position = 0.1
    spark.color_ramp.elements[1].color = (0, 0, 0, 1)
    nt.links.new(vor.outputs["Distance"], spark.inputs[0])
    mixs = n.new("ShaderNodeMix"); mixs.data_type = "RGBA"
    mixs.blend_type = "ADD"
    mixs.inputs["Factor"].default_value = 0.35
    nt.links.new(ramp.outputs["Color"], mixs.inputs["A"])
    nt.links.new(spark.outputs["Color"], mixs.inputs["B"])
    nt.links.new(mixs.outputs["Result"], bsdf.inputs["Base Color"])
    field_plane(m)
    render("field_unicorn.jpg", *FIELD_RES, transparent=False, fmt="JPEG")


def field_space():
    fresh_scene(); field_stage()
    m = bpy.data.materials.new("space")
    m.use_nodes = True
    nt = m.node_tree
    n = nt.nodes
    bsdf = n["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 1.0
    noise = n.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 3.2
    noise.inputs["Detail"].default_value = 8.0
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.3
    ramp.color_ramp.elements[0].color = (0.004, 0.004, 0.03, 1)
    ramp.color_ramp.elements[1].position = 0.8
    ramp.color_ramp.elements[1].color = (0.07, 0.03, 0.18, 1)
    e = ramp.color_ramp.elements.new(0.55)
    e.color = (0.015, 0.012, 0.07, 1)
    nt.links.new(noise.outputs["Fac"], ramp.inputs[0])
    vor = n.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 42.0
    vor.inputs["Randomness"].default_value = 1.0
    stars = n.new("ShaderNodeValToRGB")
    stars.color_ramp.elements[0].position = 0.025
    stars.color_ramp.elements[0].color = (1, 1, 1, 1)
    stars.color_ramp.elements[1].position = 0.05
    stars.color_ramp.elements[1].color = (0, 0, 0, 1)
    nt.links.new(vor.outputs["Distance"], stars.inputs[0])
    mixs = n.new("ShaderNodeMix"); mixs.data_type = "RGBA"
    mixs.blend_type = "ADD"
    mixs.inputs["Factor"].default_value = 1.0
    nt.links.new(ramp.outputs["Color"], mixs.inputs["A"])
    nt.links.new(stars.outputs["Color"], mixs.inputs["B"])
    nt.links.new(mixs.outputs["Result"], bsdf.inputs["Emission Color"])
    bsdf.inputs["Emission Strength"].default_value = 1.0
    bsdf.inputs["Base Color"].default_value = (0, 0, 0, 1)
    field_plane(m)
    render("field_space.jpg", *FIELD_RES, transparent=False, fmt="JPEG")


def field_candy():
    fresh_scene(); field_stage()
    m = bpy.data.materials.new("candyf")
    m.use_nodes = True
    nt = m.node_tree
    n = nt.nodes
    bsdf = n["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 0.55
    tex = n.new("ShaderNodeTexCoord")
    sep = n.new("ShaderNodeSeparateXYZ")
    nt.links.new(tex.outputs["Object"], sep.inputs[0])
    addxy = n.new("ShaderNodeMath"); addxy.operation = "ADD"
    nt.links.new(sep.outputs["X"], addxy.inputs[0])
    nt.links.new(sep.outputs["Y"], addxy.inputs[1])
    mul = n.new("ShaderNodeMath"); mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = 28.0
    nt.links.new(addxy.outputs["Value"], mul.inputs[0])
    sin = n.new("ShaderNodeMath"); sin.operation = "SINE"
    nt.links.new(mul.outputs["Value"], sin.inputs[0])
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.45
    ramp.color_ramp.elements[0].color = (0.85, 0.12, 0.32, 1)
    ramp.color_ramp.elements[1].position = 0.55
    ramp.color_ramp.elements[1].color = (0.98, 0.62, 0.72, 1)
    nt.links.new(sin.outputs["Value"], ramp.inputs[0])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    field_plane(m)
    render("field_candy.jpg", *FIELD_RES, transparent=False, fmt="JPEG")


def field_dino():
    fresh_scene(); field_stage()
    m = bpy.data.materials.new("swamp")
    m.use_nodes = True
    nt = m.node_tree
    n = nt.nodes
    bsdf = n["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 0.85
    tex, ramp = _bands_node(nt, math.pi * 10, (0.05, 0.2, 0.08), (0.07, 0.25, 0.1))
    vor = n.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 26.0
    spots = n.new("ShaderNodeValToRGB")
    spots.color_ramp.elements[0].position = 0.16
    spots.color_ramp.elements[0].color = (0.07, 0.2, 0.09, 1)
    spots.color_ramp.elements[1].position = 0.3
    spots.color_ramp.elements[1].color = (1, 1, 1, 1)
    nt.links.new(vor.outputs["Distance"], spots.inputs[0])
    mixs = n.new("ShaderNodeMix"); mixs.data_type = "RGBA"
    mixs.blend_type = "MULTIPLY"
    mixs.inputs["Factor"].default_value = 0.55
    nt.links.new(ramp.outputs["Color"], mixs.inputs["A"])
    nt.links.new(spots.outputs["Color"], mixs.inputs["B"])
    nt.links.new(mixs.outputs["Result"], bsdf.inputs["Base Color"])
    noise = n.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 150.0
    bump = n.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.3
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    field_plane(m)
    render("field_dino.jpg", *FIELD_RES, transparent=False, fmt="JPEG")


# ================================================================ run all
def token_pos():
    token("pos")


def token_neg():
    token("neg")


JOBS = [
    ball_paper, ball_unicorn, ball_space, ball_candy, ball_dino,
    bumper_football, bumper_rainbow, bumper_planet, bumper_candy, bumper_egg,
    token_pos, token_neg,
    trophy,
    field_grass, field_unicorn, field_space, field_candy, field_dino,
]

only = os.environ.get("ONLY")
for job in JOBS:
    name = job.__name__
    if only and only not in name:
        continue
    print(">>>", name)
    job()

print("ALL DONE")

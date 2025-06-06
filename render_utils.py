# Modified by Anonymous User 2020
#
# Based on a file originally written by:
# Copyright 2017-2020, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# ORIGNAL_LICENSE file. An additional grant
# of patent rights can be found in the ORIGINAL_PATENTS file in the same directory.

import sys, random, os, json
import bpy, bpy_extras


"""
Some utility functions for interacting with Blender
"""


def extract_args(input_argv=None):
    """
    Pull out command-line arguments after "--". Blender ignores command-line flags
    after --, so this lets us forward command line arguments from the blender
    invocation to our own script.
    """
    if input_argv is None:
        input_argv = sys.argv
    output_argv = []
    if "--" in input_argv:
         idx = input_argv.index("--")
         output_argv = input_argv[(idx + 1) :]
    else:
        for i, value in enumerate(input_argv):
            if i in [0,1,2,3,4]: pass
            else: output_argv.append(value)
    return output_argv


def parse_args(parser, argv=None):
    return parser.parse_args(extract_args(argv))


# I wonder if there's a better way to do this?
def delete_object(obj):
    """ Delete a specified blender object """
    for o in bpy.data.objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.ops.object.delete()


def get_camera_coords(cam, pos):
    """
    For a specified point, get both the 3D coordinates and 2D pixel-space
    coordinates of the point from the perspective of the camera.

    Inputs:
    - cam: Camera object
    - pos: Vector giving 3D world-space position

    Returns a tuple of:
    - (px, py, pz): px and py give 2D image-space coordinates; pz gives depth
      in the range [-1, 1]
    """
    scene = bpy.context.scene
    x, y, z = bpy_extras.object_utils.world_to_camera_view(scene, cam, pos)
    scale = scene.render.resolution_percentage / 100.0
    w = int(scale * scene.render.resolution_x)
    h = int(scale * scene.render.resolution_y)
    px = int(round(x * w))
    py = int(round(h - y * h))
    return (px, py, z)


def set_layer(obj, layer_idx):
    """ Move an object to a particular layer """
    # Set the target layer to True first because an object must always be on
    # at least one layer.
    obj.layers[layer_idx] = True
    for i in range(len(obj.layers)):
        obj.layers[i] = i == layer_idx


def add_object(
    object_dir, shape_name, name, scale, loc=(0, 0, 0), alpha=0, beta=0, gamma=0
):
    """
    Load an object from a file. We assume that in the directory object_dir, there
    is a file named "$name.blend" which contains a single object named "$name"
    that has unit size and is centered at the origin.

    - scale: scalar giving the size that the object should be in the scene
    - loc: tuple (x, y, z) giving the coordinates where the object should be placed.
    """
    # First figure out how many of this object are already in the scene so we can
    # give the new object a unique name
    count = 0
    for obj in bpy.data.objects:
        if obj.name.startswith(shape_name):
            count += 1

    filename = os.path.join(object_dir, "%s.blend" % shape_name, "Object", shape_name)
    bpy.ops.wm.append(filename=filename)

    # Give it a new name to avoid conflicts
    new_name = "%s_%d_%s" % (shape_name, count, name)
    bpy.data.objects[shape_name].name = new_name

    # Set the new object as active, then rotate, scale, and translate it
    x, y, z = loc
    bpy.context.view_layer.objects.active = bpy.data.objects[new_name]
    bpy.data.objects[new_name].select_set(True)
    bpy.context.object.rotation_euler[0] = alpha
    bpy.context.object.rotation_euler[1] = beta
    bpy.context.object.rotation_euler[2] = gamma
    bpy.ops.transform.resize(value=(scale, scale, scale))
    bpy.ops.transform.translate(value=(x, y, scale + z))

    return new_name


def load_materials(material_dir):
    """
    Load materials from a directory. We assume that the directory contains .blend
    files with one material each. The file X.blend has a single NodeTree item named
    X; this NodeTree item must have a "Color" input that accepts an RGBA value.
    """
    for fn in os.listdir(material_dir):
        if not fn.endswith(".blend"):
            continue
        name = os.path.splitext(fn)[0]
        filepath = os.path.join(material_dir, fn, "NodeTree", name)
        bpy.ops.wm.append(filename=filepath)


def change_material(material, **properties):
    """Update the parameters of a material"""
    group_node = material.node_tree.nodes[-1]

    # Find and set the "Color" input of the new group node
    for inp in group_node.inputs:
        if inp.name in properties:
            inp.default_value = properties[inp.name]


def add_material(name, object=None, **properties):
    """
    Create a new material and assign it to the active object. "name" should be the
    name of a material that has been previously loaded using load_materials.
    """
    # Figure out how many materials are already in the scene
    mat_count = len(bpy.data.materials)

    # Create a new material; it is not attached to anything and
    # it will be called "Material"
    bpy.ops.material.new()

    # Get a reference to the material we just created and rename it;
    # then the next time we make a new material it will still be called
    # "Material" and we will still be able to look it up by name
    mat = bpy.data.materials["Material"]
    mat.name = "Material_%d" % mat_count

    # Attach the new material to the active object
    # Make sure it doesn't already have materials
    if object is None:
        print("Using selected object")
        obj = bpy.context.active_object
    else:
        obj = object

    assert len(obj.data.materials) == 0
    obj.data.materials.append(mat)

    # Find the output node of the new material
    output_node = None
    for n in mat.node_tree.nodes:
        if n.name == "Material Output":
            output_node = n
            break

    # Add a new GroupNode to the node tree of the active material,
    # and copy the node tree from the preloaded node group to the
    # new group node. This copying seems to happen by-value, so
    # we can create multiple materials of the same type without them
    # clobbering each other
    group_node = mat.node_tree.nodes.new("ShaderNodeGroup")
    group_node.node_tree = bpy.data.node_groups[name]

    # Find and set the "Color" input of the new group node
    for inp in group_node.inputs:
        if inp.name in properties:
            inp.default_value = properties[inp.name]

    # Wire the output of the new group node to the input of
    # the MaterialOutput node
    mat.node_tree.links.new(
        group_node.outputs["Shader"],
        output_node.inputs["Surface"],
    )


def add_texture(obj_name, path):
    o = bpy.data.objects[obj_name]
    mat = bpy.data.materials.new("TextureMat")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    diff = nodes.new("ShaderNodeBsdfDiffuse")
    tex = nodes.new("ShaderNodeTexImage")
    tex_coord = nodes.new("ShaderNodeTexCoord")

    tex.image = bpy.data.images.load(path)

    links.new(out.inputs["Surface"], diff.outputs["BSDF"])
    links.new(diff.inputs["Color"], tex.outputs["Color"])
    links.new(tex.inputs["Vector"], tex_coord.outputs["Generated"])

    o.data.materials.append(mat)


def render_segmentation(objects, segm_mat, segm_color, render_args):
    ground_modified = len(bpy.data.objects["Ground"].data.materials) > 0
    n_obj = len(objects)
    s = render_args.filepath
    ind = s.rindex(".")
    render_args.filepath = s[:ind] + "_segm" + s[ind:]
    if ground_modified:
        prev_ground = bpy.data.objects["Ground"].data.materials[0]
    prev_mat = []
    bpy.data.objects["Ground"].data.materials.clear()
    bpy.data.objects["Ground"].data.materials.append(segm_mat[0])
    for i in range(n_obj):
        prev_mat.append(bpy.data.objects[i - n_obj].data.materials[0])
        scene_name = bpy.data.objects[i - n_obj].name
        index = -1
        for obj in objects:
            if obj["scene_name"] == scene_name:
                index = obj["index"]
                obj["segm_color"] = segm_color[obj["index"] + 1]

        bpy.data.objects[i - n_obj].data.materials.clear()
        bpy.data.objects[i - n_obj].data.materials.append(segm_mat[index + 1])
    render_img()
    # Revert to old materials
    bpy.data.objects["Ground"].data.materials.clear()
    if ground_modified:
        bpy.data.objects["Ground"].data.materials.append(prev_ground)
    for i in range(n_obj):
        bpy.data.objects[i - n_obj].data.materials.clear()
        bpy.data.objects[i - n_obj].data.materials.append(prev_mat[i])


def render_img():
    while True:
        try:
            bpy.ops.render.render(write_still=True)
            break
        except Exception as e:
            print(e)


def save_additional_struct(scene_struct, output_blendfile, output_scene):
    with open(output_scene, "w") as f:
        json.dump(scene_struct, f, indent=4)
    if output_blendfile is not None:
        bpy.ops.wm.save_as_mainfile(filepath=output_blendfile)


# if we ever need for Blender Render renderer
# def add_texture(obj_name, path):
#     # bpy.data.images.load("../textures/grass.jpg")
#     o = bpy.data.objects[obj_name]
#     img = bpy.data.images.load(path)
#     tex = bpy.data.textures.new("GroundTex", "IMAGE")
#     tex.image = img
#     mat = bpy.data.materials.new("GroundMat")
#     slot = mat.texture_slots.add()
#     slot.texture = tex
#     slot.texture_coords = "UV"
#     slot.use_map_color_diffuse = True
#     slot.use_map_color_emission = True
#     slot.use_map_density = True
#     slot.mapping = "FLAT"
#     o.data.materials.append(mat)
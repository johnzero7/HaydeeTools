# -*- coding: utf-8 -*-
# <pep8 compliant>

import bpy
import os
from mathutils import Vector

#Nodes BI
BI_MATERIAL_NODE = 'ShaderNodeMaterial'
BI_OUTPUT_NODE = 'ShaderNodeOutput'

#Nodes Layout
NODE_FRAME = 'NodeFrame'

#Nodes Shaders
BSDF_DIFFUSE_NODE = 'ShaderNodeBsdfDiffuse'
BSDF_EMISSION_NODE = 'ShaderNodeEmission'
BSDF_GLOSSY_NODE = 'ShaderNodeBsdfGlossy'
PRINCIPLED_SHADER_NODE = 'ShaderNodeBsdfPrincipled'
BSDF_TRANSPARENT_NODE = 'ShaderNodeBsdfTransparent'
SHADER_ADD_NODE = 'ShaderNodeAddShader'
SHADER_MIX_NODE = 'ShaderNodeMixShader'

#Nodes Color
RGB_MIX_NODE = 'ShaderNodeMixRGB'
INVERT_NODE = 'ShaderNodeInvert'

#Nodes Input
TEXTURE_IMAGE_NODE = 'ShaderNodeTexImage'
SHADER_NODE_FRESNEL = 'ShaderNodeFresnel'
SHADER_NODE_NEW_GEOMETRY = 'ShaderNodeNewGeometry'

#Nodes Outputs
OUTPUT_NODE = 'ShaderNodeOutputMaterial'

#Nodes Vector
SHADER_NODE_BUMP = 'ShaderNodeBump'
NORMAL_MAP_NODE = 'ShaderNodeNormalMap'

#Nodes Convert
SHADER_NODE_MATH = 'ShaderNodeMath'
SHADER_NODE_SEPARATE_RGB = 'ShaderNodeSeparateRGB'
SHADER_NODE_COMBINE_RGB = 'ShaderNodeCombineRGB'

# Node Groups
NODE_GROUP = 'ShaderNodeGroup'
NODE_GROUP_INPUT = 'NodeGroupInput'
NODE_GROUP_OUTPUT = 'NodeGroupOutput'
SHADER_NODE_TREE = 'ShaderNodeTree'
# Node Custom Groups
HAYDEE_NORMAL_NODE = 'Haydee Normal'
PBR_FRESNEL_NODE = 'PBR Fresnel'
PBR_REFELCTION_NODE = 'PBR Reflection'
PBR_SHADER_NODE = 'PBR Shader'
LESS_MORE_NODE = 'Less/More'

# Sockets
NODE_SOCKET_COLOR = 'NodeSocketColor'
NODE_SOCKET_FLOAT = 'NodeSocketFloat'
NODE_SOCKET_FLOAT_FACTOR = 'NodeSocketFloatFactor'
NODE_SOCKET_SHADER = 'NodeSocketShader'
NODE_SOCKET_VECTOR = 'NodeSocketVector'




DEFAULT_PBR_POWER = .5

def reaplce_nodes():
    """Replace PBR node groups """
    # Remove group if exists
    if LESS_MORE_NODE in bpy.data.node_groups:
        bpy.data.node_groups.remove(LESS_MORE_NODE, do_unlink=True)

    if PBR_SHADER_NODE in bpy.data.node_groups:
        bpy.data.node_groups.remove(PBR_SHADER_NODE, do_unlink=True)

    if PBR_REFELCTION_NODE in bpy.data.node_groups:
        bpy.data.node_groups.remove(PBR_REFELCTION_NODE, do_unlink=True)

    if PBR_FRESNEL_NODE in bpy.data.node_groups:
        bpy.data.node_groups.remove(PBR_FRESNEL_NODE, do_unlink=True)

    less_more_group()
    pbr_fresnel_group()
    pbr_reflection_group()
    pbr_shader_group()
    #pbr_shader_powered_group()


def load_image(textureFilepath, forceNewTexture = False):
    image = None
    if textureFilepath:
        textureFilename = os.path.basename(textureFilepath)
        fileRoot, fileExt = os.path.splitext(textureFilename)

        if (os.path.exists(textureFilepath)):
            print("Loading Texture: " + textureFilename)
            image = bpy.data.images.load(filepath=textureFilepath, check_existing=not forceNewTexture)
        else:
            print("Warning. Texture not found " + textureFilename)
            image = bpy.data.images.new(
                name=textureFilename, width=1024, height=1024, alpha=True,
                float_buffer=False)
            image.source = 'FILE'
            image.filepath = textureFilepath

    return image


def create_material(obj, useAlpha, mat_name, diffuseFile, normalFile, specularFile, emissionFile):
    obj.data.materials.clear()

    material = bpy.data.materials.get(mat_name)
    if not material:
        material = bpy.data.materials.new(mat_name)
    material.use_nodes = True
    obj.data.materials.append(material)

    create_bi_node_material(material, diffuseFile, normalFile, specularFile, emissionFile)
    create_cycle_node_material(material, useAlpha, diffuseFile, normalFile, specularFile, emissionFile)


def create_bi_node_material(material, diffuseFile, normalFile, specularFile, emissionFile):
    #clear slots
    slots = material.texture_slots
    for idx, slot in enumerate(slots):
        if slot:
            slots.clear(idx)

    #diffuse
    if diffuseFile and os.path.exists(diffuseFile):
        name = os.path.basename(diffuseFile)
        texture = bpy.data.textures.new(name, 'IMAGE')
        texture.image = load_image(diffuseFile)
        texSlot = material.texture_slots.create(0)
        texSlot.texture =  texture

    #normal
    if normalFile and os.path.exists(normalFile):
        name = os.path.basename(normalFile)
        texture = bpy.data.textures.new(name, 'IMAGE')
        texture.use_normal_map = True
        texture.image = load_image(normalFile)
        texSlot = material.texture_slots.create(1)
        texSlot.texture = texture
        texSlot.use_map_color_diffuse = False
        texSlot.use_map_emit = False
        texSlot.use_map_normal = True

    #emission
    if emissionFile and os.path.exists(emissionFile):
        name = os.path.basename(emissionFile)
        texture = bpy.data.textures.new(name, 'IMAGE')
        texture.image = load_image(emissionFile)
        texSlot = material.texture_slots.create(2)
        texSlot.texture = texture
        texSlot.use_map_color_diffuse = False
        texSlot.use_map_emit = True
        texSlot.use_rgb_to_intensity = True

def makeBiNodes(cmat):
    '''Create Blender Internal Material Nodes'''
    node_tree = cmat.node_tree
    links = node_tree.links

    BIFrame = node_tree.nodes.new(NODE_FRAME)
    BIFrame.name = 'BI Frame'
    BIFrame.label = 'BI Material'

    biShaderNodeMaterial = node_tree.nodes.new(BI_MATERIAL_NODE)
    biShaderNodeMaterial.parent = BIFrame
    biShaderNodeMaterial.name = 'BI Materai'
    biShaderNodeMaterial.material = cmat
    biShaderNodeMaterial.location = Vector((0, 1000))

    biShaderNodeOutput = node_tree.nodes.new(BI_OUTPUT_NODE)
    biShaderNodeOutput.parent = BIFrame
    biShaderNodeOutput.name = 'BI Output'
    biShaderNodeOutput.location = biShaderNodeMaterial.location + Vector((300, 0))

    #BI Nodes Links
    links.new(biShaderNodeMaterial.outputs['Color'], biShaderNodeOutput.inputs['Color'])
    links.new(biShaderNodeMaterial.outputs['Alpha'], biShaderNodeOutput.inputs['Alpha'])


def create_cycle_node_material(material, useAlpha, diffuseFile, normalFile, specularFile, emissionFile):
    # Nodes
    node_tree = material.node_tree
    node_tree.nodes.clear()

    #Blender Internal Nodes
    makeBiNodes(material)

    col_width = 200

    diffuseTextureNode = node_tree.nodes.new(TEXTURE_IMAGE_NODE)
    diffuseTextureNode.label = 'Diffuse'
    diffuseTextureNode.image = load_image(diffuseFile)
    diffuseTextureNode.location = Vector((0, 0))

    specularTextureNode = node_tree.nodes.new(TEXTURE_IMAGE_NODE)
    specularTextureNode.label = 'Roughness Specular Metalic'
    specularTextureNode.color_space = 'NONE'
    specularTextureNode.image = load_image(specularFile)
    specularTextureNode.location = diffuseTextureNode.location + Vector((0, -450))

    normalTextureRgbNode = node_tree.nodes.new(TEXTURE_IMAGE_NODE)
    normalTextureRgbNode.label = 'Haydee Normal'
    normalTextureRgbNode.color_space = 'NONE'
    normalTextureRgbNode.image = load_image(normalFile)
    if normalTextureRgbNode.image:
        normalTextureRgbNode.image.use_alpha = False
    normalTextureRgbNode.location = specularTextureNode.location + Vector((0, -300))

    normalTextureAlphaNode = node_tree.nodes.new(TEXTURE_IMAGE_NODE)
    normalTextureAlphaNode.label = 'Haydee Normal Alpha'
    normalTextureAlphaNode.image = load_image(normalFile, True)
    if normalTextureAlphaNode.image:
        normalTextureAlphaNode.image.use_alpha = True
    normalTextureAlphaNode.color_space = 'NONE'
    normalTextureAlphaNode.location = specularTextureNode.location + Vector((0, -600))

    haydeeNormalMapNode = node_tree.nodes.new(NODE_GROUP)
    haydeeNormalMapNode.label = 'Haydee Normal Converter'
    haydeeNormalMapNode.node_tree = haydee_normal_map()
    haydeeNormalMapNode.location = normalTextureRgbNode.location + Vector((col_width * 1, 0))
    normalMapNode = node_tree.nodes.new(NORMAL_MAP_NODE)
    normalMapNode.location = haydeeNormalMapNode.location + Vector((col_width, 100))

    emissionTextureNode = node_tree.nodes.new(TEXTURE_IMAGE_NODE)
    emissionTextureNode.label = 'Emission'
    emissionTextureNode.image = load_image(emissionFile)
    emissionTextureNode.location = diffuseTextureNode.location + Vector((0, 260))

    separateRgbNode = node_tree.nodes.new(SHADER_NODE_SEPARATE_RGB)
    separateRgbNode.location = specularTextureNode.location + Vector((col_width * 1, 60))

    roughnessPowerNode = node_tree.nodes.new(SHADER_NODE_MATH)
    roughnessPowerNode.operation = 'POWER'
    roughnessPowerNode.inputs[1].default_value = DEFAULT_PBR_POWER
    roughnessPowerNode.location = separateRgbNode.location + Vector((col_width, 200))
    specPowerNode = node_tree.nodes.new(SHADER_NODE_MATH)
    specPowerNode.operation = 'POWER'
    specPowerNode.inputs[1].default_value = DEFAULT_PBR_POWER
    specPowerNode.location = separateRgbNode.location + Vector((col_width, 50))
    metallicPowerNode = node_tree.nodes.new(SHADER_NODE_MATH)
    metallicPowerNode.operation = 'POWER'
    metallicPowerNode.inputs[1].default_value = DEFAULT_PBR_POWER
    metallicPowerNode.location = separateRgbNode.location + Vector((col_width, -100))

    alphaMixNode = None
    transparencyNode = None
    pbrShaderNode = None
    pbrColorInput = None
    pbrRoughnessInput = None
    pbrReflectionInput = None
    pbrMetallicInput = None
    usePbr = False
    if usePbr:
        pbrShaderNode = node_tree.nodes.new(NODE_GROUP)
        pbrShaderNode.width = 240
        pbrShaderNode.location = separateRgbNode.location + Vector((400, -50))
        pbrShaderNode.node_tree = pbr_shader_group()
        pbrColorInput = 'Color'
        pbrRoughnessInput = 'Roughness'
        pbrReflectionInput = 'Reflection'
    else:
        pbrShaderNode = node_tree.nodes.new(PRINCIPLED_SHADER_NODE)
        pbrShaderNode.location = diffuseTextureNode.location + Vector((col_width * 3, -100))
        pbrShaderNode.width = 240
        pbrColorInput = 'Base Color'
        pbrRoughnessInput = 'Roughness'
        pbrReflectionInput = 'Specular'
        pbrMetallicInput = 'Metallic'

    emissionNode = node_tree.nodes.new(BSDF_EMISSION_NODE)
    emissionNode.inputs['Color'].default_value = (0, 0, 0, 1)
    emissionNode.location = pbrShaderNode.location + Vector((100, 100))
    addShaderNode = node_tree.nodes.new(SHADER_ADD_NODE)
    addShaderNode.location = emissionNode.location + Vector((250, 0))
    outputNode = node_tree.nodes.new(OUTPUT_NODE)
    outputNode.location = addShaderNode.location + Vector((500, 200))
    if useAlpha:
        alphaMixNode = node_tree.nodes.new(SHADER_MIX_NODE)
        alphaMixNode.location = pbrShaderNode.location + Vector((600, 300))
        transparencyNode = node_tree.nodes.new(BSDF_TRANSPARENT_NODE)
        transparencyNode.location = alphaMixNode.location + Vector((-250, -100))

    #Links Input
    links = node_tree.links
    if emissionFile and os.path.exists(emissionFile):
        links.new(emissionTextureNode.outputs['Color'], emissionNode.inputs['Color'])
    links.new(diffuseTextureNode.outputs['Color'], pbrShaderNode.inputs[pbrColorInput])
    links.new(specularTextureNode.outputs['Color'], separateRgbNode.inputs['Image'])
    if normalFile and os.path.exists(normalFile):
        links.new(normalTextureRgbNode.outputs['Color'], haydeeNormalMapNode.inputs['Color'])
        links.new(normalTextureAlphaNode.outputs['Alpha'], haydeeNormalMapNode.inputs['Alpha'])
        links.new(haydeeNormalMapNode.outputs['Normal'], normalMapNode.inputs['Color'])

    links.new(emissionNode.outputs['Emission'], addShaderNode.inputs[0])
    links.new(addShaderNode.outputs['Shader'], outputNode.inputs['Surface'])

    if useAlpha:
        links.new(diffuseTextureNode.outputs['Alpha'], alphaMixNode.inputs['Fac'])
        links.new(transparencyNode.outputs['BSDF'], alphaMixNode.inputs[1])
        links.new(addShaderNode.outputs['Shader'], alphaMixNode.inputs[2])
        links.new(alphaMixNode.outputs['Shader'], outputNode.inputs['Surface'])

    links.new(specularTextureNode.outputs['Color'], separateRgbNode.inputs['Image'])
    links.new(separateRgbNode.outputs['R'], roughnessPowerNode.inputs[0])
    links.new(separateRgbNode.outputs['G'], specPowerNode.inputs[0])
    links.new(separateRgbNode.outputs['B'], metallicPowerNode.inputs[0])

    if specularFile and os.path.exists(specularFile):
        links.new(roughnessPowerNode.outputs[0], pbrShaderNode.inputs[pbrRoughnessInput])
        links.new(specPowerNode.outputs[0], pbrShaderNode.inputs[pbrReflectionInput])
        if pbrMetallicInput:
            links.new(metallicPowerNode.outputs[0], pbrShaderNode.inputs[pbrMetallicInput])
    links.new(normalMapNode.outputs['Normal'], pbrShaderNode.inputs['Normal'])

    links.new(pbrShaderNode.outputs[0], addShaderNode.inputs[1])


def haydee_normal_map():
    if HAYDEE_NORMAL_NODE in bpy.data.node_groups:
        return bpy.data.node_groups[HAYDEE_NORMAL_NODE]

    # create a group
    node_tree = bpy.data.node_groups.new(HAYDEE_NORMAL_NODE, SHADER_NODE_TREE)

    separateRgbNode = node_tree.nodes.new(SHADER_NODE_SEPARATE_RGB)
    separateRgbNode.location = Vector((0, 0))
    invertRNode = node_tree.nodes.new(INVERT_NODE)
    invertRNode.inputs[0].default_value = 0
    invertRNode.location = separateRgbNode.location + Vector((200, 40))
    invertGNode = node_tree.nodes.new(INVERT_NODE)
    invertGNode.inputs[0].default_value = 1
    invertGNode.location = separateRgbNode.location + Vector((200, -60))

    SpaceChange = node_tree.nodes.new(NODE_FRAME)
    SpaceChange.name = 'R & G Space Change'
    SpaceChange.label = 'R & G Space Change'
    mathMultiplyRNode = node_tree.nodes.new(SHADER_NODE_MATH)
    mathMultiplyRNode.parent = SpaceChange
    mathMultiplyRNode.operation = 'MULTIPLY'
    mathMultiplyRNode.inputs[1].default_value = 2
    mathMultiplyRNode.location = invertGNode.location + Vector((250, -100))
    mathMultiplyGNode = node_tree.nodes.new(SHADER_NODE_MATH)
    mathMultiplyGNode.parent = SpaceChange
    mathMultiplyGNode.operation = 'MULTIPLY'
    mathMultiplyGNode.inputs[1].default_value = 2
    mathMultiplyGNode.location = invertGNode.location + Vector((250, -250))

    mathSubstractRNode = node_tree.nodes.new(SHADER_NODE_MATH)
    mathSubstractRNode.parent = SpaceChange
    mathSubstractRNode.operation = 'SUBTRACT'
    mathSubstractRNode.inputs[1].default_value = 1
    mathSubstractRNode.location = mathMultiplyRNode.location + Vector((200, 0))
    mathSubstractGNode = node_tree.nodes.new(SHADER_NODE_MATH)
    mathSubstractGNode.parent = SpaceChange
    mathSubstractGNode.operation = 'SUBTRACT'
    mathSubstractGNode.inputs[1].default_value = 1
    mathSubstractGNode.location = mathMultiplyGNode.location + Vector((200, 0))

    BCalc = node_tree.nodes.new(NODE_FRAME)
    BCalc.name = 'B Calc'
    BCalc.label = 'B Calc'
    mathPowerRNode = node_tree.nodes.new(SHADER_NODE_MATH)
    mathPowerRNode.parent =  BCalc
    mathPowerRNode.operation = 'POWER'
    mathPowerRNode.inputs[1].default_value = 2
    mathPowerRNode.location = mathSubstractRNode.location + Vector((200, 0))
    mathPowerGNode = node_tree.nodes.new(SHADER_NODE_MATH)
    mathPowerGNode.parent =  BCalc
    mathPowerGNode.operation = 'POWER'
    mathPowerGNode.inputs[1].default_value = 2
    mathPowerGNode.location = mathSubstractGNode.location + Vector((200, 0))

    mathAddNode = node_tree.nodes.new(SHADER_NODE_MATH)
    mathAddNode.parent =  BCalc
    mathAddNode.operation = 'ADD'
    mathAddNode.location = mathPowerGNode.location + Vector((200, 60))

    mathSubtractNode = node_tree.nodes.new(SHADER_NODE_MATH)
    mathSubtractNode.parent =  BCalc
    mathSubtractNode.operation = 'SUBTRACT'
    mathSubtractNode.inputs[0].default_value = 1
    mathSubtractNode.location = mathAddNode.location + Vector((200, 0))

    mathRootNode = node_tree.nodes.new(SHADER_NODE_MATH)
    mathRootNode.parent =  BCalc
    mathRootNode.operation = 'POWER'
    mathRootNode.inputs[1].default_value = .5
    mathRootNode.location = mathSubtractNode.location + Vector((200, 0))

    combineRgbNode = node_tree.nodes.new(SHADER_NODE_COMBINE_RGB)
    combineRgbNode.location = mathRootNode.location + Vector((200, 230))

    # Input/Output
    group_inputs = node_tree.nodes.new(NODE_GROUP_INPUT)
    group_inputs.location = separateRgbNode.location + Vector ((-200, -100))
    group_outputs = node_tree.nodes.new(NODE_GROUP_OUTPUT)
    group_outputs.location = combineRgbNode.location + Vector ((200, 0))

    #group_inputs.inputs.new(NODE_SOCKET_SHADER,'Shader')
    input_color = node_tree.inputs.new(NODE_SOCKET_COLOR,'Color')
    input_color.default_value = (.5, .5, .5, 1)
    input_alpha = node_tree.inputs.new(NODE_SOCKET_COLOR,'Alpha')
    input_alpha.default_value = (.5, .5, .5, 1)
    output_value = node_tree.outputs.new(NODE_SOCKET_COLOR,'Normal')

    #Links Input
    links = node_tree.links
    links.new(group_inputs.outputs['Color'], separateRgbNode.inputs['Image'])
    links.new(group_inputs.outputs['Alpha'], invertGNode.inputs['Color'])
    links.new(separateRgbNode.outputs['R'], invertRNode.inputs['Color'])

    links.new(invertRNode.outputs['Color'], mathMultiplyRNode.inputs[0])
    links.new(invertGNode.outputs['Color'], mathMultiplyGNode.inputs[0])
    links.new(mathMultiplyRNode.outputs[0], mathSubstractRNode.inputs[0])
    links.new(mathMultiplyGNode.outputs[0], mathSubstractGNode.inputs[0])
    links.new(mathSubstractRNode.outputs[0], mathPowerRNode.inputs[0])
    links.new(mathSubstractGNode.outputs[0], mathPowerGNode.inputs[0])
    links.new(mathPowerRNode.outputs['Value'], mathAddNode.inputs[0])
    links.new(mathPowerGNode.outputs['Value'], mathAddNode.inputs[1])
    links.new(mathAddNode.outputs['Value'], mathSubtractNode.inputs[1])
    links.new(mathSubtractNode.outputs['Value'], mathRootNode.inputs[0])

    links.new(invertRNode.outputs['Color'], combineRgbNode.inputs['R'])
    links.new(invertGNode.outputs['Color'], combineRgbNode.inputs['G'])
    links.new(mathRootNode.outputs['Value'], combineRgbNode.inputs['B'])

    links.new(combineRgbNode.outputs['Image'], group_outputs.inputs['Normal'])

    return node_tree


def less_more_group():
    if LESS_MORE_NODE in bpy.data.node_groups:
        return bpy.data.node_groups[LESS_MORE_NODE]

    # create a group
    node_tree = bpy.data.node_groups.new(LESS_MORE_NODE, SHADER_NODE_TREE)

    multiplyNode = node_tree.nodes.new(SHADER_NODE_MATH)
    multiplyNode.operation = 'MULTIPLY'
    multiplyNode.inputs[1].default_value = .5
    multiplyNode.location = Vector((0, 0))
    addNode = node_tree.nodes.new(SHADER_NODE_MATH)
    addNode.operation = 'ADD'
    addNode.inputs[1].default_value = .5
    addNode.location = multiplyNode.location + Vector((200, 0))
    overlayNode = node_tree.nodes.new(RGB_MIX_NODE)
    overlayNode.blend_type = 'OVERLAY'
    overlayNode.inputs['Fac'].default_value = 1
    overlayNode.location = addNode.location + Vector((200, 180))

    # Input/Output
    group_inputs = node_tree.nodes.new(NODE_GROUP_INPUT)
    group_inputs.location = multiplyNode.location + Vector ((-200, 60))
    group_outputs = node_tree.nodes.new(NODE_GROUP_OUTPUT)
    group_outputs.location = overlayNode.location + Vector ((200, 0))

    #group_inputs.inputs.new(NODE_SOCKET_SHADER,'Shader')
    input_color = node_tree.inputs.new(NODE_SOCKET_COLOR,'Color')
    input_color.default_value = (.8, .8, .8, 1)
    input_less_more = node_tree.inputs.new(NODE_SOCKET_FLOAT_FACTOR,'Less/More')
    input_less_more.min_value = -1
    input_less_more.max_value = 1
    input_less_more.default_value = 0
    output_value = node_tree.outputs.new(NODE_SOCKET_FLOAT,'Value')

    #Links Input
    links = node_tree.links
    links.new(group_inputs.outputs['Color'], overlayNode.inputs['Color2'])
    links.new(group_inputs.outputs['Less/More'], multiplyNode.inputs[0])
    links.new(multiplyNode.outputs['Value'], addNode.inputs[0])
    links.new(addNode.outputs['Value'], overlayNode.inputs['Color1'])
    links.new(overlayNode.outputs['Color'], group_outputs.inputs['Value'])

    return node_tree


def pbr_fresnel_group():
    if PBR_FRESNEL_NODE in bpy.data.node_groups:
        return bpy.data.node_groups[PBR_FRESNEL_NODE]

    # create a group
    node_tree = bpy.data.node_groups.new(PBR_FRESNEL_NODE, SHADER_NODE_TREE)

    #node_tree = bpy.context.active_object.active_material.node_tree
    # Nodes
    bumpNode = node_tree.nodes.new(SHADER_NODE_BUMP)
    bumpNode.location = Vector((0, 0))
    rbgMixNode = node_tree.nodes.new(RGB_MIX_NODE)
    rbgMixNode.location = bumpNode.location + Vector((250, 90))
    fresnel1Node = node_tree.nodes.new(SHADER_NODE_FRESNEL)
    fresnel1Node.location = rbgMixNode.location + Vector((250, 70))
    mathNode = node_tree.nodes.new(SHADER_NODE_MATH)
    mathNode.operation = 'SUBTRACT'
    mathNode.location = fresnel1Node.location + Vector((200, -100))
    geometryNode = node_tree.nodes.new(SHADER_NODE_NEW_GEOMETRY)
    geometryNode.location = bumpNode.location + Vector((0, -200))
    fresnel2Node = node_tree.nodes.new(SHADER_NODE_FRESNEL)
    fresnel2Node.location = geometryNode.location + Vector((500, 40))

    # Input/Output
    group_inputs = node_tree.nodes.new(NODE_GROUP_INPUT)
    group_inputs.location = bumpNode.location + Vector ((-200, 150))
    group_outputs = node_tree.nodes.new(NODE_GROUP_OUTPUT)
    group_outputs.location = mathNode.location + Vector ((200, 80))

    #group_inputs.inputs.new(NODE_SOCKET_SHADER,'Shader')
    input_ior = node_tree.inputs.new(NODE_SOCKET_FLOAT,'IOR')
    input_ior.min_value = 0
    input_ior.default_value = 1.45
    input_roughness = node_tree.inputs.new(NODE_SOCKET_FLOAT_FACTOR,'Roughness')
    input_roughness.min_value = 0
    input_roughness.max_value = 1
    input_normal = node_tree.inputs.new(NODE_SOCKET_VECTOR,'Normal')

    output_dielectric_fresnel = node_tree.outputs.new(NODE_SOCKET_FLOAT_FACTOR,'Dielectric Fresnel')
    output_dielectric_fresnel.min_value = 0
    output_dielectric_fresnel.max_value = 1
    output_metalic_fresnel = node_tree.outputs.new(NODE_SOCKET_FLOAT_FACTOR,'Metalic Fresnel')
    output_metalic_fresnel.min_value = 0
    output_metalic_fresnel.max_value = 1

    #Links Input
    links = node_tree.links
    links.new(group_inputs.outputs['IOR'], fresnel1Node.inputs['IOR'])
    links.new(group_inputs.outputs['Roughness'], rbgMixNode.inputs['Fac'])
    links.new(group_inputs.outputs['Normal'], bumpNode.inputs['Normal'])
    #Links Mix
    links.new(bumpNode.outputs['Normal'], rbgMixNode.inputs['Color1'])
    links.new(geometryNode.outputs['Incoming'], rbgMixNode.inputs['Color2'])
    links.new(geometryNode.outputs['Incoming'], fresnel2Node.inputs['Normal'])

    links.new(rbgMixNode.outputs['Color'], fresnel1Node.inputs['Normal'])

    links.new(fresnel1Node.outputs['Fac'], mathNode.inputs[0])
    links.new(fresnel2Node.outputs['Fac'], mathNode.inputs[1])

    links.new(fresnel1Node.outputs['Fac'], group_outputs.inputs['Dielectric Fresnel'])
    links.new(mathNode.outputs['Value'], group_outputs.inputs['Metalic Fresnel'])

    return node_tree


def pbr_reflection_group():
    if PBR_REFELCTION_NODE in bpy.data.node_groups:
        return bpy.data.node_groups[PBR_REFELCTION_NODE]

    # create a group
    node_tree = bpy.data.node_groups.new(PBR_REFELCTION_NODE, SHADER_NODE_TREE)

    # Nodes
    groupNode = node_tree.nodes.new(NODE_GROUP)
    groupNode.location = Vector((0, 0))
    groupNode.node_tree = pbr_fresnel_group()
    rbgMixNode = node_tree.nodes.new(RGB_MIX_NODE)
    rbgMixNode.location = groupNode.location + Vector((200, 0))
    shaderMixNode = node_tree.nodes.new(SHADER_MIX_NODE)
    shaderMixNode.location = rbgMixNode.location + Vector((200, -180))
    glossyNode = node_tree.nodes.new(BSDF_GLOSSY_NODE)
    glossyNode.location = groupNode.location + Vector((0, -300))

    # Input/Output Nodes
    group_inputs = node_tree.nodes.new(NODE_GROUP_INPUT)
    group_inputs.location = groupNode.location + Vector ((-200, -180))
    group_outputs = node_tree.nodes.new(NODE_GROUP_OUTPUT)
    group_outputs.location = shaderMixNode.location + Vector ((200, 0))
    #Inputs Sockets
    input_shader = node_tree.inputs.new(NODE_SOCKET_SHADER,'Shader')
    input_roughness = node_tree.inputs.new(NODE_SOCKET_FLOAT_FACTOR,'Roughness')
    input_roughness.min_value = 0
    input_roughness.max_value = 1
    input_reflection = node_tree.inputs.new(NODE_SOCKET_FLOAT_FACTOR,'Reflection')
    input_reflection.min_value = 0
    input_reflection.max_value = 1
    input_normal = node_tree.inputs.new(NODE_SOCKET_VECTOR,'Normal')
    #Outputs Sockets
    output_shader = node_tree.outputs.new(NODE_SOCKET_SHADER,'Shader')

    #Links Input
    links = node_tree.links
    links.new(group_inputs.outputs['Shader'], shaderMixNode.inputs[1])
    links.new(group_inputs.outputs['Roughness'], groupNode.inputs['Roughness'])
    links.new(group_inputs.outputs['Roughness'], glossyNode.inputs['Roughness'])
    links.new(group_inputs.outputs['Reflection'], rbgMixNode.inputs['Color1'])
    links.new(group_inputs.outputs['Normal'], groupNode.inputs['Normal'])
    links.new(group_inputs.outputs['Normal'], glossyNode.inputs['Normal'])

    links.new(groupNode.outputs['Dielectric Fresnel'], rbgMixNode.inputs['Fac'])
    links.new(rbgMixNode.outputs['Color'], shaderMixNode.inputs['Fac'])
    links.new(glossyNode.outputs['BSDF'], shaderMixNode.inputs[2])
    links.new(shaderMixNode.outputs['Shader'], group_outputs.inputs['Shader'])

    return node_tree


def pbr_shader_powered_group():
    if PBR_SHADER_NODE in bpy.data.node_groups:
        return bpy.data.node_groups[PBR_SHADER_NODE]

    # create a group
    node_tree = bpy.data.node_groups.new(PBR_SHADER_NODE, SHADER_NODE_TREE)

    # Nodes
    diffuseNode = node_tree.nodes.new(BSDF_DIFFUSE_NODE)
    diffuseNode.location = Vector((0, 0))
    groupNode = node_tree.nodes.new(NODE_GROUP)
    groupNode.location = groupNode.location + Vector((200, -60))
    groupNode.node_tree = pbr_reflection_group()
    power1Node = node_tree.nodes.new(SHADER_NODE_MATH)
    power1Node.operation = 'POWER'
    power1Node.inputs[1].default_value = 2
    power1Node.location = diffuseNode.location + Vector((-300, -150))
    power2Node = node_tree.nodes.new(SHADER_NODE_MATH)
    power2Node.operation = 'POWER'
    power2Node.inputs[1].default_value = 2
    power2Node.location = diffuseNode.location + Vector((-300, -300))

    # Input/Output Nodes
    group_inputs = node_tree.nodes.new(NODE_GROUP_INPUT)
    group_inputs.location = diffuseNode.location + Vector ((-500, -100))
    group_outputs = node_tree.nodes.new(NODE_GROUP_OUTPUT)
    group_outputs.location = groupNode.location + Vector ((200, 0))
    #Inputs Sockets
    input_shader = node_tree.inputs.new(NODE_SOCKET_COLOR,'Color')
    input_roughness = node_tree.inputs.new(NODE_SOCKET_FLOAT_FACTOR,'Roughness')
    input_roughness.min_value = 0
    input_roughness.max_value = 1
    input_reflection= node_tree.inputs.new(NODE_SOCKET_FLOAT_FACTOR,'Reflection')
    input_reflection.min_value = 0
    input_reflection.max_value = 1
    input_normal = node_tree.inputs.new(NODE_SOCKET_VECTOR,'Normal')
    #Outputs Sockets
    output_shader = node_tree.outputs.new(NODE_SOCKET_SHADER,'Shader')

    #Links Input
    links = node_tree.links
    links.new(group_inputs.outputs['Color'], diffuseNode.inputs['Color'])
    links.new(group_inputs.outputs['Roughness'], power1Node.inputs[0])
    links.new(group_inputs.outputs['Reflection'], power2Node.inputs[0])
    links.new(group_inputs.outputs['Normal'], groupNode.inputs['Normal'])
    links.new(group_inputs.outputs['Normal'], diffuseNode.inputs['Normal'])

    links.new(diffuseNode.outputs['BSDF'], groupNode.inputs['Shader'])
    links.new(power1Node.outputs['Value'], diffuseNode.inputs['Roughness'])
    links.new(power1Node.outputs['Value'], groupNode.inputs['Roughness'])
    links.new(power2Node.outputs['Value'], groupNode.inputs['Reflection'])

    links.new(groupNode.outputs['Shader'], group_outputs.inputs['Shader'])

    return node_tree


def pbr_shader_group():
    if PBR_SHADER_NODE in bpy.data.node_groups:
        return bpy.data.node_groups[PBR_SHADER_NODE]

    # create a group
    node_tree = bpy.data.node_groups.new(PBR_SHADER_NODE, SHADER_NODE_TREE)

    # Nodes
    diffuseNode = node_tree.nodes.new(BSDF_DIFFUSE_NODE)
    diffuseNode.location = Vector((0, 0))
    groupNode = node_tree.nodes.new(NODE_GROUP)
    groupNode.location = groupNode.location + Vector((200, -60))
    groupNode.node_tree = pbr_reflection_group()

    # Input/Output Nodes
    group_inputs = node_tree.nodes.new(NODE_GROUP_INPUT)
    group_inputs.location = diffuseNode.location + Vector ((-250, -100))
    group_outputs = node_tree.nodes.new(NODE_GROUP_OUTPUT)
    group_outputs.location = groupNode.location + Vector ((200, 0))
    #Inputs Sockets
    input_shader = node_tree.inputs.new(NODE_SOCKET_COLOR,'Color')
    input_roughness = node_tree.inputs.new(NODE_SOCKET_FLOAT_FACTOR,'Roughness')
    input_roughness.min_value = 0
    input_roughness.max_value = 1
    input_reflection= node_tree.inputs.new(NODE_SOCKET_FLOAT_FACTOR,'Reflection')
    input_reflection.min_value = 0
    input_reflection.max_value = 1
    input_normal = node_tree.inputs.new(NODE_SOCKET_VECTOR,'Normal')
    #Outputs Sockets
    output_shader = node_tree.outputs.new(NODE_SOCKET_SHADER,'Shader')

    #Links Input
    links = node_tree.links
    links.new(group_inputs.outputs['Color'], diffuseNode.inputs['Color'])
    links.new(group_inputs.outputs['Roughness'], diffuseNode.inputs['Roughness'])
    links.new(group_inputs.outputs['Roughness'], groupNode.inputs['Roughness'])
    links.new(group_inputs.outputs['Reflection'], groupNode.inputs['Reflection'])
    links.new(group_inputs.outputs['Normal'], groupNode.inputs['Normal'])
    links.new(group_inputs.outputs['Normal'], diffuseNode.inputs['Normal'])

    links.new(diffuseNode.outputs['BSDF'], groupNode.inputs['Shader'])

    links.new(groupNode.outputs['Shader'], group_outputs.inputs['Shader'])

    return node_tree



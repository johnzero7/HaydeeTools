import bpy
import os
from mathutils import Vector

PBR_FRESNEL_NODE = 'PBR Fresnel'
PBR_REFELCTION_NODE = 'PBR Reflection'
PBR_SHADER_NODE = 'PBR Shader'
LESS_MORE_NODE = 'Less/More'
HAYDEE_NORMAL_NODE = 'Haydee Normal'


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

        # Get texture by filename
        # image = bpy.data.images.get(textureFilename)

        # Get texture by filepath
        if not forceNewTexture:
            image = next(
                (img for img in bpy.data.images if bpy.path.abspath(img.filepath) == textureFilepath), None)

        if image is None:
            print("Loading Texture: " + textureFilename)
            if (os.path.exists(textureFilepath)):
                image = bpy.data.images.load(filepath=textureFilepath)
                print("Texture load complete: " + textureFilename)
            else:
                print("Warning. Texture not found " + textureFilename)
                image = bpy.data.images.new(
                    name=textureFilename, width=1024, height=1024, alpha=True,
                    float_buffer=False)
                image.source = 'FILE'
                image.filepath = textureFilepath
    return image


def haydee_normal_map():
    if HAYDEE_NORMAL_NODE in bpy.data.node_groups:
        return bpy.data.node_groups[HAYDEE_NORMAL_NODE]

    # create a group
    node_tree = bpy.data.node_groups.new(HAYDEE_NORMAL_NODE, 'ShaderNodeTree')

    separateRgbNode = node_tree.nodes.new('ShaderNodeSeparateRGB')
    separateRgbNode.location = Vector((0, 0))
    invertRNode = node_tree.nodes.new('ShaderNodeInvert')
    invertRNode.inputs[0].default_value = 0
    invertRNode.location = separateRgbNode.location + Vector((200, 40))
    invertGNode = node_tree.nodes.new('ShaderNodeInvert')
    invertGNode.inputs[0].default_value = 1
    invertGNode.location = separateRgbNode.location + Vector((200, -60))

    mathPowerRNode = node_tree.nodes.new('ShaderNodeMath')
    mathPowerRNode.operation = 'POWER'
    mathPowerRNode.inputs[1].default_value = 2
    mathPowerRNode.location = invertGNode.location + Vector((400, -50))
    mathPowerGNode = node_tree.nodes.new('ShaderNodeMath')
    mathPowerGNode.operation = 'POWER'
    mathPowerGNode.inputs[1].default_value = 2
    mathPowerGNode.location = invertGNode.location + Vector((400, -200))

    mathAddNode = node_tree.nodes.new('ShaderNodeMath')
    mathAddNode.operation = 'ADD'
    mathAddNode.location = mathPowerGNode.location + Vector((200, 0))

    mathSubtractNode = node_tree.nodes.new('ShaderNodeMath')
    mathSubtractNode.operation = 'SUBTRACT'
    mathSubtractNode.inputs[0].default_value = 1
    mathSubtractNode.location = mathAddNode.location + Vector((200, 0))

    mathRootNode = node_tree.nodes.new('ShaderNodeMath')
    mathRootNode.operation = 'POWER'
    mathRootNode.inputs[1].default_value = .5
    mathRootNode.location = mathSubtractNode.location + Vector((200, 0))

    combineRgbNode = node_tree.nodes.new('ShaderNodeCombineRGB')
    combineRgbNode.location = mathRootNode.location + Vector((200, 230))

    # Input/Output
    group_inputs = node_tree.nodes.new('NodeGroupInput')
    group_inputs.location = separateRgbNode.location + Vector ((-200, -100))
    group_outputs = node_tree.nodes.new('NodeGroupOutput')
    group_outputs.location = combineRgbNode.location + Vector ((200, 0))

    #group_inputs.inputs.new('NodeSocketShader','Shader')
    input_color = node_tree.inputs.new('NodeSocketColor','Color')
    input_color.default_value = (.5, .5, .5, 1)
    input_alpha = node_tree.inputs.new('NodeSocketColor','Alpha')
    input_alpha.default_value = (.5, .5, .5, 1)
    output_value = node_tree.outputs.new('NodeSocketColor','Normal')

    #Links Input
    links = node_tree.links
    links.new(group_inputs.outputs['Color'], separateRgbNode.inputs['Image'])
    links.new(group_inputs.outputs['Color'], invertGNode.inputs['Color'])
    links.new(separateRgbNode.outputs['R'], invertRNode.inputs['Color'])

    links.new(invertRNode.outputs['Color'], mathPowerRNode.inputs[0])
    links.new(invertGNode.outputs['Color'], mathPowerGNode.inputs[0])
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
    node_tree = bpy.data.node_groups.new(LESS_MORE_NODE, 'ShaderNodeTree')

    multiplyNode = node_tree.nodes.new('ShaderNodeMath')
    multiplyNode.operation = 'MULTIPLY'
    multiplyNode.inputs[1].default_value = .5
    multiplyNode.location = Vector((0, 0))
    addNode = node_tree.nodes.new('ShaderNodeMath')
    addNode.operation = 'ADD'
    addNode.inputs[1].default_value = .5
    addNode.location = multiplyNode.location + Vector((200, 0))
    overlayNode = node_tree.nodes.new('ShaderNodeMixRGB')
    overlayNode.blend_type = 'OVERLAY'
    overlayNode.inputs['Fac'].default_value = 1
    overlayNode.location = addNode.location + Vector((200, 180))

    # Input/Output
    group_inputs = node_tree.nodes.new('NodeGroupInput')
    group_inputs.location = multiplyNode.location + Vector ((-200, 60))
    group_outputs = node_tree.nodes.new('NodeGroupOutput')
    group_outputs.location = overlayNode.location + Vector ((200, 0))

    #group_inputs.inputs.new('NodeSocketShader','Shader')
    input_color = node_tree.inputs.new('NodeSocketColor','Color')
    input_color.default_value = (.8, .8, .8, 1)
    input_less_more = node_tree.inputs.new('NodeSocketFloatFactor','Less/More')
    input_less_more.min_value = -1
    input_less_more.max_value = 1
    input_less_more.default_value = 0
    output_value = node_tree.outputs.new('NodeSocketFloat','Value')

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
    node_tree = bpy.data.node_groups.new(PBR_FRESNEL_NODE, 'ShaderNodeTree')

    #node_tree = bpy.context.active_object.active_material.node_tree
    # Nodes
    bumpNode = node_tree.nodes.new('ShaderNodeBump')
    bumpNode.location = Vector((0, 0))
    rbgMixNode = node_tree.nodes.new('ShaderNodeMixRGB')
    rbgMixNode.location = bumpNode.location + Vector((250, 90))
    fresnel1Node = node_tree.nodes.new('ShaderNodeFresnel')
    fresnel1Node.location = rbgMixNode.location + Vector((250, 70))
    mathNode = node_tree.nodes.new('ShaderNodeMath')
    mathNode.operation = 'SUBTRACT'
    mathNode.location = fresnel1Node.location + Vector((200, -100))
    geometryNode = node_tree.nodes.new('ShaderNodeNewGeometry')
    geometryNode.location = bumpNode.location + Vector((0, -200))
    fresnel2Node = node_tree.nodes.new('ShaderNodeFresnel')
    fresnel2Node.location = geometryNode.location + Vector((500, 40))

    # Input/Output
    group_inputs = node_tree.nodes.new('NodeGroupInput')
    group_inputs.location = bumpNode.location + Vector ((-200, 150))
    group_outputs = node_tree.nodes.new('NodeGroupOutput')
    group_outputs.location = mathNode.location + Vector ((200, 80))

    #group_inputs.inputs.new('NodeSocketShader','Shader')
    input_ior = node_tree.inputs.new('NodeSocketFloat','IOR')
    input_ior.min_value = 0
    input_ior.default_value = 1.45
    input_roughness = node_tree.inputs.new('NodeSocketFloatFactor','Roughness')
    input_roughness.min_value = 0
    input_roughness.max_value = 1
    input_normal = node_tree.inputs.new('NodeSocketVector','Normal')

    output_dielectric_fresnel = node_tree.outputs.new('NodeSocketFloatFactor','Dielectric Fresnel')
    output_dielectric_fresnel.min_value = 0
    output_dielectric_fresnel.max_value = 1
    output_metalic_fresnel = node_tree.outputs.new('NodeSocketFloatFactor','Metalic Fresnel')
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
    node_tree = bpy.data.node_groups.new(PBR_REFELCTION_NODE, 'ShaderNodeTree')

    # Nodes
    groupNode = node_tree.nodes.new('ShaderNodeGroup')
    groupNode.location = Vector((0, 0))
    groupNode.node_tree = pbr_fresnel_group()
    rbgMixNode = node_tree.nodes.new('ShaderNodeMixRGB')
    rbgMixNode.location = groupNode.location + Vector((200, 0))
    shaderMixNode = node_tree.nodes.new('ShaderNodeMixShader')
    shaderMixNode.location = rbgMixNode.location + Vector((200, -180))
    glossyNode = node_tree.nodes.new('ShaderNodeBsdfGlossy')
    glossyNode.location = groupNode.location + Vector((0, -300))

    # Input/Output Nodes
    group_inputs = node_tree.nodes.new('NodeGroupInput')
    group_inputs.location = groupNode.location + Vector ((-200, -180))
    group_outputs = node_tree.nodes.new('NodeGroupOutput')
    group_outputs.location = shaderMixNode.location + Vector ((200, 0))
    #Inputs Sockets
    input_shader = node_tree.inputs.new('NodeSocketShader','Shader')
    input_roughness = node_tree.inputs.new('NodeSocketFloatFactor','Roughness')
    input_roughness.min_value = 0
    input_roughness.max_value = 1
    input_reflection = node_tree.inputs.new('NodeSocketFloatFactor','Reflection')
    input_reflection.min_value = 0
    input_reflection.max_value = 1
    input_normal = node_tree.inputs.new('NodeSocketVector','Normal')
    #Outputs Sockets
    output_shader = node_tree.outputs.new('NodeSocketShader','Shader')

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
    node_tree = bpy.data.node_groups.new(PBR_SHADER_NODE, 'ShaderNodeTree')

    # Nodes
    diffuseNode = node_tree.nodes.new('ShaderNodeBsdfDiffuse')
    diffuseNode.location = Vector((0, 0))
    groupNode = node_tree.nodes.new('ShaderNodeGroup')
    groupNode.location = groupNode.location + Vector((200, -60))
    groupNode.node_tree = pbr_reflection_group()
    power1Node = node_tree.nodes.new('ShaderNodeMath')
    power1Node.operation = 'POWER'
    power1Node.inputs[1].default_value = 2
    power1Node.location = diffuseNode.location + Vector((-300, -150))
    power2Node = node_tree.nodes.new('ShaderNodeMath')
    power2Node.operation = 'POWER'
    power2Node.inputs[1].default_value = 2
    power2Node.location = diffuseNode.location + Vector((-300, -300))

    # Input/Output Nodes
    group_inputs = node_tree.nodes.new('NodeGroupInput')
    group_inputs.location = diffuseNode.location + Vector ((-500, -100))
    group_outputs = node_tree.nodes.new('NodeGroupOutput')
    group_outputs.location = groupNode.location + Vector ((200, 0))
    #Inputs Sockets
    input_shader = node_tree.inputs.new('NodeSocketColor','Color')
    input_roughness = node_tree.inputs.new('NodeSocketFloatFactor','Roughness')
    input_roughness.min_value = 0
    input_roughness.max_value = 1
    input_reflection= node_tree.inputs.new('NodeSocketFloatFactor','Reflection')
    input_reflection.min_value = 0
    input_reflection.max_value = 1
    input_normal = node_tree.inputs.new('NodeSocketVector','Normal')
    #Outputs Sockets
    output_shader = node_tree.outputs.new('NodeSocketShader','Shader')

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
    node_tree = bpy.data.node_groups.new(PBR_SHADER_NODE, 'ShaderNodeTree')

    # Nodes
    diffuseNode = node_tree.nodes.new('ShaderNodeBsdfDiffuse')
    diffuseNode.location = Vector((0, 0))
    groupNode = node_tree.nodes.new('ShaderNodeGroup')
    groupNode.location = groupNode.location + Vector((200, -60))
    groupNode.node_tree = pbr_reflection_group()

    # Input/Output Nodes
    group_inputs = node_tree.nodes.new('NodeGroupInput')
    group_inputs.location = diffuseNode.location + Vector ((-250, -100))
    group_outputs = node_tree.nodes.new('NodeGroupOutput')
    group_outputs.location = groupNode.location + Vector ((200, 0))
    #Inputs Sockets
    input_shader = node_tree.inputs.new('NodeSocketColor','Color')
    input_roughness = node_tree.inputs.new('NodeSocketFloatFactor','Roughness')
    input_roughness.min_value = 0
    input_roughness.max_value = 1
    input_reflection= node_tree.inputs.new('NodeSocketFloatFactor','Reflection')
    input_reflection.min_value = 0
    input_reflection.max_value = 1
    input_normal = node_tree.inputs.new('NodeSocketVector','Normal')
    #Outputs Sockets
    output_shader = node_tree.outputs.new('NodeSocketShader','Shader')

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


def create_material(obj, mat_name, diffuseFile, normalFile, specularFile, emissionFile):
    obj.data.materials.clear()

    material = bpy.data.materials.get(mat_name)
    if not material:
        material = bpy.data.materials.new(mat_name)
    material.use_nodes = True
    obj.data.materials.append(material)

    create_bi_node_material(material, diffuseFile, normalFile, specularFile, emissionFile)
    create_cycle_node_material(material, diffuseFile, normalFile, specularFile, emissionFile)


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


def create_cycle_node_material(material, diffuseFile, normalFile, specularFile, emissionFile):
    # Nodes
    node_tree = material.node_tree
    node_tree.nodes.clear()

    diffuseTextureNode = node_tree.nodes.new('ShaderNodeTexImage')
    diffuseTextureNode.image = load_image(diffuseFile)
    diffuseTextureNode.location = Vector((0, 0))
    specularTextureNode = node_tree.nodes.new('ShaderNodeTexImage')
    specularTextureNode.image = load_image(specularFile)
    specularTextureNode.location = diffuseTextureNode.location + Vector((0, -450))
    normalTextureRgbNode = node_tree.nodes.new('ShaderNodeTexImage')
    normalTextureRgbNode.image = load_image(normalFile)
    if normalTextureRgbNode.image:
        normalTextureRgbNode.image.use_alpha = False
    normalTextureRgbNode.color_space = 'NONE'
    normalTextureRgbNode.location = specularTextureNode.location + Vector((0, -300))
    normalTextureAlphaNode = node_tree.nodes.new('ShaderNodeTexImage')
    normalTextureAlphaNode.image = load_image(normalFile, True)
    if normalTextureAlphaNode.image:
        normalTextureAlphaNode.image.use_alpha = True
    normalTextureAlphaNode.color_space = 'NONE'
    normalTextureAlphaNode.location = specularTextureNode.location + Vector((0, -600))
    haydeeNormalMapNode = node_tree.nodes.new('ShaderNodeGroup')
    haydeeNormalMapNode.node_tree = haydee_normal_map()
    haydeeNormalMapNode.location = normalTextureRgbNode.location + Vector((200, 0))
    normalMapNode = node_tree.nodes.new('ShaderNodeNormalMap')
    normalMapNode.location = haydeeNormalMapNode.location + Vector((200, 100))
    emissionTextureNode = node_tree.nodes.new('ShaderNodeTexImage')
    emissionTextureNode.image = load_image(emissionFile)
    emissionTextureNode.location = diffuseTextureNode.location + Vector((0, 260))

    separateRgbNode = node_tree.nodes.new('ShaderNodeSeparateRGB')
    separateRgbNode.location = specularTextureNode.location + Vector((200, 60))

    roughnessLessMoreNode = node_tree.nodes.new('ShaderNodeGroup')
    roughnessLessMoreNode.location = separateRgbNode.location + Vector((200, 100))
    roughnessLessMoreNode.node_tree = less_more_group()

    reflectionLessMoreNode = node_tree.nodes.new('ShaderNodeGroup')
    reflectionLessMoreNode.location = separateRgbNode.location + Vector((200, -50))
    reflectionLessMoreNode.node_tree = less_more_group()

    pbrShaderNode = node_tree.nodes.new('ShaderNodeGroup')
    pbrShaderNode.location = reflectionLessMoreNode.location + Vector((400, 260))
    pbrShaderNode.node_tree = pbr_shader_group()

    emissionNode = node_tree.nodes.new('ShaderNodeEmission')
    emissionNode.inputs['Color'].default_value = (0, 0, 0, 1)
    emissionNode.location = pbrShaderNode.location + Vector((0, 150))
    addShaderNode = node_tree.nodes.new('ShaderNodeAddShader')
    addShaderNode.location = emissionNode.location + Vector((200, 20))
    outputNode = node_tree.nodes.new('ShaderNodeOutputMaterial')
    outputNode.location = addShaderNode.location + Vector((200, -5))

    #Links Input
    links = node_tree.links
    if emissionFile and os.path.exists(emissionFile):
        links.new(emissionTextureNode.outputs['Color'], emissionNode.inputs['Color'])
    links.new(diffuseTextureNode.outputs['Color'], pbrShaderNode.inputs['Color'])
    links.new(specularTextureNode.outputs['Color'], separateRgbNode.inputs['Image'])
    if normalFile and os.path.exists(normalFile):
        links.new(normalTextureRgbNode.outputs['Color'], haydeeNormalMapNode.inputs['Color'])
        links.new(normalTextureAlphaNode.outputs['Alpha'], haydeeNormalMapNode.inputs['Alpha'])
        links.new(haydeeNormalMapNode.outputs['Normal'], normalMapNode.inputs['Color'])

    links.new(emissionNode.outputs['Emission'], addShaderNode.inputs[0])
    links.new(addShaderNode.outputs['Shader'], outputNode.inputs['Surface'])

    links.new(specularTextureNode.outputs['Color'], separateRgbNode.inputs['Image'])
    links.new(separateRgbNode.outputs['R'], roughnessLessMoreNode.inputs['Color'])
    links.new(separateRgbNode.outputs['G'], reflectionLessMoreNode.inputs['Color'])

    if specularFile and os.path.exists(specularFile):
        links.new(roughnessLessMoreNode.outputs['Value'], pbrShaderNode.inputs['Roughness'])
        links.new(reflectionLessMoreNode.outputs['Value'], pbrShaderNode.inputs['Reflection'])
    links.new(normalMapNode.outputs['Normal'], pbrShaderNode.inputs['Normal'])

    links.new(pbrShaderNode.outputs['Shader'], addShaderNode.inputs[1])


    #BI Nodes
    biMaterialNode = node_tree.nodes.new('ShaderNodeMaterial')
    biMaterialNode.location = Vector((0, 1000))
    biMaterialNode.material = material
    biOutputNode = node_tree.nodes.new('ShaderNodeOutput')
    biOutputNode.location = biMaterialNode.location + Vector((300, 0))

    #BI Nodes Links
    links.new(biMaterialNode.outputs['Color'], biOutputNode.inputs['Color'])
    links.new(biMaterialNode.outputs['Alpha'], biOutputNode.inputs['Alpha'])


# <pep8 compliant>

# Native imports
import struct
import os
import io
import binascii
import codecs
from enum import Enum
from math import pi
from io import BytesIO

# Blender and own imports
import bpy
from .HaydeeUtils import d, find_armature, file_format_prop
from .HaydeeUtils import boneRenameBlender, decodeText
from .HaydeeNodeMat import create_material
from .timing import profile
from . import HaydeeMenuIcon
from bpy_extras.wm_utils.progress_report import (
    ProgressReport,
    ProgressReportSubstep,
)
# ImportHelper is a helper class, defines filename and
# invoke() function which calls the file selector.
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator
from mathutils import Quaternion, Vector, Matrix


# Global enum for asset type
class Signature(Enum):
    HD_CHUNK = 0
    HD_DATA_TXT = 1
    HD_DATA_TXT_BOM = 2
    HD_MOTION = 3

# Constants

ARMATURE_NAME = 'Skeleton'
HD_CHUNK = b'\x48\x44\x5F\x43\x48\x55\x4E\x4B'
HD_DATA_TXT = b'\x48\x44\x5F\x44\x41\x54\x41\x5F\x54\x58\x54'
HD_DATA_TXT_BOM = b'\xFF\xFE\x48\x00\x44\x00\x5F\x00\x44\x00\x41\x00\x54\x00\x41\x00\x5F\x00\x54\x00\x58\x00\x54\x00'
HD_MOTION = b'\x48\x44\x5F\x4D\x4F\x54\x49\x4F\x4E\x00'

# Swap matrix rows
SWAP_ROW_SKEL = Matrix(((0, 0, 1, 0),
                        (1, 0, 0, 0),
                        (0, 1, 0, 0),
                        (0, 0, 0, 1)))
# Swap matrix cols
SWAP_COL_SKEL = Matrix(((1, 0, 0, 0),
                        (0, 0, -1, 0),
                        (0, -1, 0, 0),
                        (0, 0, 0, 1)))

# --------------------------------------------------------------------------------
# binary helpers
# --------------------------------------------------------------------------------
def sig_check(mview):
    result = None
    if (mview[0:8] == (HD_CHUNK)):
        result = Signature.HD_CHUNK
    elif (mview[0:11] == (HD_DATA_TXT)):
        result = Signature.HD_DATA_TXT
    elif (mview[0:24] == (HD_DATA_TXT_BOM)):
        result = Signature.HD_DATA_TXT_BOM
    elif (mview[0:10] == (HD_MOTION)):
        result = Signature.HD_MOTION
    return result

# Read prefixed ANSI/utf8-as-ansi string
def readStrA(start, data):
    len = int.from_bytes(data[start:start+4], byteorder='little')
    start += 4
    return (data[start:start+len].decode("utf-8"), 4+len+1)

# Read property name (until null terminator)
def readStrA_term(start, maxLen, data):
    i, tStr, found = -1, "", False
    while (i < maxLen):
        i += 1
        if (data[start+i] <= 0):
            found = True
            break
    if (found):
        tStr = codecs.decode(data[start:start+i], "latin")
    return (tStr,i)

# Read UTF16/wide string
def readStrW(start, data):
    i = int.from_bytes(data[start:start+4], byteorder='little')
    len = (i * 2)
    start += 4
    return (codecs.decode(data[start:start+len], "utf-16-le"), 4+len+2)

# Vector from Haydee format to Blender
def vectorSwapSkel(vec):
    return Vector((-vec.z, vec.y, -vec.x))


def createCollection(name="Haydee Model"):
    # Create a collection with specific name
    collection = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(collection)
    return collection


def linkToActiveCollection(obj):
    # link object to active collection
    bpy.context.collection.objects.link(obj)


def recurLayerCollection(layerColl, collName):
    # transverse the layer_collection tree looking for a collection named collName
    found = None
    if (layerColl.name == collName):
        return layerColl
    for layer in layerColl.children:
        found = recurLayerCollection(layer, collName)
        if found:
            return found


def setActiveCollection(collName):
    # set collName as the active collection
    layer_collection = bpy.context.view_layer.layer_collection
    layerColl = recurLayerCollection(layer_collection, collName)
    if layerColl:
        bpy.context.view_layer.active_layer_collection = layerColl


# --------------------------------------------------------------------------------
# .skel importer
# --------------------------------------------------------------------------------

def recurBonesOrigin(progress, parentBone, jointNames, mats):
    for childBone in parentBone.children:
        if childBone:
            idx = jointNames.index(childBone.name)
            child_mat = mats[idx]
            # INV row
            x1 = Matrix(((0, 0, -1, 0),
                         (1, 0, 0, 0),
                         (0, 1, 0, 0),
                         (0, 0, 0, 1)))
            # INV col
            x2 = Matrix(((0, 1, 0, 0),
                         (0, 0, 1, 0),
                         (-1, 0, 0, 0),
                         (0, 0, 0, 1)))

            childBone.matrix = parentBone.matrix @ (x1 @ child_mat @ x2)
            recurBonesOrigin(progress, childBone, jointNames, mats)
            progress.step()


def rotateNonRootBone(parentBone):
    if ('root' in parentBone.name.lower()):
        return
    r = Quaternion((0, 0, 1), -pi / 2).to_matrix().to_4x4()
    parentBone.matrix = r @ parentBone.matrix
    for childBone in parentBone.children:
        rotateNonRootBone(childBone)

# Parse bone data helper
def read_bone_data(memData, propMap, jointNames, jointParents, mats, dimensions):
    boneCount = propMap['numBones']['value']
    BONE_SIZE = int(propMap['bones']['size'] / boneCount)
    unpack_bone = struct.Struct('<32s16fi3fi').unpack
    for n in range(boneCount):
        offset = (BONE_SIZE * n)
        (name,
            f1, f2, f3, f4,
            f5, f6, f7, f8,
            f9, f10, f11, f12,
            f13, f14, f15, f16,
            parent, width, height, lenght, flags) = unpack_bone(memData[offset:offset + BONE_SIZE])

        name = readStrA_term(0, 32, memoryview(name))[0]
        name = boneRenameBlender(name)
        mat = Matrix(((f1, f5, f9, f13),
                        (f2, f6, f10, f14),
                        (f3, f7, f11, f15),
                        (f4, f8, f12, f16)))
        jointNames.append(name)
        jointParents.append(parent)
        mats.append(mat)
        dimensions.append((width, height, lenght))
    return True

# Parse joint data helper
def read_joint_data(memData, propMap, joint_data):
    joints_count = propMap['numJoints']['value']
    JOINT_SIZE = int(propMap['joints']['size'] / joints_count)
    unpack_joint = struct.Struct('<18f4f').unpack
    for n in range(joints_count):
        offset = (JOINT_SIZE * n)
        (
            index, parent,
            f1, f2, f3, f4,
            f5, f6, f7, f8,
            f9, f10, f11, f12,
            f13, f14, f15, f16,
            twistX, twistY, swingX, swingY) = unpack_joint(memData[offset:offset + JOINT_SIZE])

        mat = Matrix((
                    (f1, f5, f9, f13),
                    (f2, f6, f10, f14),
                    (f3, f7, f11, f15),
                    (f4, f8, f12, f16)
        ))

        joint_data[index] = {
            'parent': parent,
            'twistX': twistX, 'twistY': twistY,
            'swingX': swingX, 'swingY': swingY,
            'matrix': mat
        }
    return True

# Parse fixes data
def read_fixes_data(memData, propMap, fix_data):
    fixes_count = propMap['numFixes']['value']
    FIXES_SIZE = int(propMap['fixes']['size'] / fixes_count)
    unpack_fixes = struct.Struct('<5I').unpack
    for n in range(fixes_count):
        offset = (FIXES_SIZE * n)
        (type, flags, fix1, fix2, index) = unpack_fixes(memData[offset:offset + FIXES_SIZE])
        fix_data[index] = ({'type': type, 'flags': flags, 'fix1': fix1, 'fix2': fix2})
    return True
def read_skel(operator, context, filepath):
    print('skel:', filepath)
    with open(filepath, "rb") as a_file:
        data = a_file.read()
    mview = memoryview(data)

    (entries, serialSize, assType) = struct.unpack('<ii8s', mview[20:36])
    assType = assType.decode("latin")

    if (sig_check(mview) != Signature.HD_CHUNK or assType != 'skeleton'):
        print("Unrecognized signature or asset type: [%s], %s" % (binascii.hexlify(mview[0:16]), assType))
        operator.report({'ERROR'}, "Unrecognized file format")
        return {'FINISHED'}

    # Compiled structs
    unpack_int = struct.Struct('<i').unpack
    unpack_entry = struct.Struct('<32siiii').unpack

    # Data
    jointNames, jointParents, mats, dimensions = [], [], [], []
    joint_data, fix_data = {}, {}
    armature_ob = None

    propMap = dict(numBones=   {'reader': lambda x: unpack_int(x)[0]},
                   numJoints=  {'reader': lambda x: unpack_int(x)[0]},
                   numFixes=   {'reader': lambda x: unpack_int(x)[0]},
                   numBounds=  {'reader': lambda x: unpack_int(x)[0]},
                   numTrackers={'reader': lambda x: unpack_int(x)[0]},
                   numSlots=   {'reader': lambda x: unpack_int(x)[0]},
                   bones=      {'reader': lambda x: read_bone_data(x, propMap, jointNames, jointParents, mats, dimensions)},
                   fixes=      {'reader': lambda x: read_fixes_data(x, propMap, fix_data)},
                   joints=     {'reader': lambda x: read_joint_data(x, propMap, joint_data)},
                   slots=      {'reader': lambda x: print("Skipping slots since this data is irrelevant")})

    dataOffset = 28 + (entries * 48)

    for x in range(1, entries):
        sPos = 28 + (x * 48)
        (name, size, offset, numSubs, subs) = unpack_entry(mview[sPos:sPos+48])
        name = readStrA_term(0, 32, memoryview(name))[0]
        propMap[name].update(dict(zip(['size', 'offset', 'numSubs', 'subs', 'hasValue'],[size, offset, numSubs, subs, size > 0])))

    for key, value in propMap.items():
        if (value.get("hasValue")):
            (f, lSize, lOff) = (value['reader'], value['size'], value['offset'])
            lOff = dataOffset + lOff
            value["value"] = f(mview[lOff:lOff+lSize])

    print(fix_data)
    with ProgressReport(context.window_manager) as progReport:
        with ProgressReportSubstep(progReport, 4, "Importing skel", "Finish Importing skel") as progress:

             # create armature
            if (bpy.context.mode != 'OBJECT'):
                bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.select_all(action='DESELECT')

            armature_ob = None
            if jointNames:
                boneCount = len(jointNames)
                progress.enter_substeps(boneCount, "Build armature")
                print('Importing Armature', str(boneCount), 'bones')

                armature_da = bpy.data.armatures.new(ARMATURE_NAME)
                # armature_da.display_type = 'STICK'
                armature_ob = bpy.data.objects.new(ARMATURE_NAME, armature_da)
                armature_ob.show_in_front = True

                collection = createCollection(ARMATURE_NAME)
                setActiveCollection(ARMATURE_NAME)
                linkToActiveCollection(armature_ob)

                bpy.context.view_layer.objects.active = armature_ob
                bpy.ops.object.mode_set(mode='EDIT')

                # create all Bones
                progress.enter_substeps(boneCount, "create bones")
                for idx, jointName in enumerate(jointNames):
                    editBone = armature_ob.data.edit_bones.new(jointName)
                    editBone.tail = Vector(editBone.head) + Vector((0, 0, 1))
                    editBone.length = dimensions[idx][2]
                    progress.step()
                progress.leave_substeps("create bones end")

                # set all bone parents
                progress.enter_substeps(boneCount, "parenting bones")
                for idx, jointParent in enumerate(jointParents):
                    if (jointParent >= 0):
                        editBone = armature_da.edit_bones[idx]
                        editBone.parent = armature_da.edit_bones[jointParent]
                    progress.step()
                progress.leave_substeps("parenting bones end")

                # origins of each bone is relative to its parent
                # recalc all origins
                progress.enter_substeps(boneCount, "aligning bones")
                rootBones = [rootBone for rootBone in armature_da.edit_bones if rootBone.parent is None]

                # swap rows root bones
                swap_rows = Matrix(((-1, 0, 0, 0),
                                    (0, 0, -1, 0),
                                    (0, 1, 0, 0),
                                    (0, 0, 0, 1)))
                # swap cols root bones
                swap_cols = Matrix(((0, 1, 0, 0),
                                    (0, 0, 1, 0),
                                    (1, 0, 0, 0),
                                    (0, 0, 0, 1)))

                for rootBone in rootBones:
                    idx = jointNames.index(rootBone.name)
                    mat = mats[idx]
                    rootBone.matrix = swap_rows @ mat @ swap_cols
                    recurBonesOrigin(progress, rootBone, jointNames, mats)
                    progress.step()
                progress.leave_substeps("aligning bones end")

                # lenght of bones
                for bone in armature_da.edit_bones:
                    for child in bone.children:
                        center = child.head
                        proxVec = center - bone.head
                        boneVec = bone.tail - bone.head
                        norm = proxVec.dot(boneVec) / boneVec.dot(boneVec)
                        if (norm > 0.1):
                            proyVec = norm * boneVec
                            dist = (proxVec - proyVec).length
                            if (dist < 0.001):
                                bone.tail = center

                # Rotate bone not in 'SK_Root' chain
                for bone in rootBones:
                    rotateNonRootBone(bone)

                bpy.ops.object.mode_set(mode='OBJECT')
                progress.leave_substeps("Build armature end")

            for idx, bone_name in enumerate(jointNames):

                # import JOINT information
                joint = joint_data.get(idx)
                if joint:
                    parent = joint['parent']
                    twistX = joint['twistX']
                    twistY = joint['twistY']
                    swingX = joint['swingX']
                    swingY = joint['swingY']

                    pose_bone = armature_ob.pose.bones.get(bone_name)
                    constraint = pose_bone.constraints.new('LIMIT_ROTATION')
                    constraint.use_limit_x = True

                # TODO:
                # Commented out because does not work properly
                # fix1 index is alway too high, needs reserach
                # import FIX information
                # fix = fix_data.get(idx)
                # if fix:
                #     constraint = None
                #     type = fix['type']
                #     flags = fix['flags']

                #     parent_idx = fix['fix1']
                #     parent_name = jointNames[parent_idx]

                #     target_idx = fix['fix2']
                #     target_name = jointNames[target_idx]

                #     pose_bone = armature_ob.pose.bones.get(bone_name)
                #     pose_bone.bone.layers[1] = True
                #     pose_bone.bone.layers[0] = False

                #     useDrivers = False
                #     if useDrivers:
                #         if (type == 1):  # TARGET
                #             groupName = 'TARGET'
                #             boneGroup = armature_ob.pose.bone_groups.get(groupName)
                #             if not boneGroup:
                #                 boneGroup = armature_ob.pose.bone_groups.new(name=groupName)
                #                 boneGroup.color_set = 'THEME15'
                #             pose_bone.bone_group = boneGroup
                #             XY = bool(flags & 0b0001)  # fix order YZ
                #             XY = bool(flags & 0b0010)  # fix order ZY
                #             constraint = pose_bone.constraints.new('DAMPED_TRACK')
                #             constraint.name = 'Target'
                #             constraint.target = armature_ob
                #             constraint.subtarget = target_name

                #         if (type == 2 and 0 == 1):  # SMOOTH
                #             NEGY = bool(flags & 0b0001)  # fix order NEGY
                #             NEGZ = bool(flags & 0b0010)  # fix order NEGZ
                #             POSY = bool(flags & 0b0011)  # fix order POSY
                #             POSZ = bool(flags & 0b0100)  # fix order POSZ
                #             pose_bone.bone.use_inherit_scale = False
                #             pose_bone.bone.use_inherit_rotation = False

                #             constraint_parent = pose_bone.constraints.new('CHILD_OF')
                #             constraint_parent.name = 'Smooth Parent'
                #             constraint_parent.target = armature_ob
                #             constraint_parent.subtarget = parent_name
                #             constraint_parent.use_location_x = False
                #             constraint_parent.use_location_y = False
                #             constraint_parent.use_location_z = False
                #             matrix = constraint_parent.target.data.bones[constraint_parent.subtarget].matrix_local.inverted()
                #             constraint_parent.inverse_matrix = matrix
                #             constraint_parent.influence = .5

                #             constraint_child = pose_bone.constraints.new('CHILD_OF')
                #             constraint_child.name = 'Smooth Child'
                #             constraint_child.target = armature_ob
                #             constraint_child.subtarget = target_name
                #             constraint_child.use_location_x = False
                #             constraint_child.use_location_y = False
                #             constraint_child.use_location_z = False
                #             matrix = constraint_child.target.data.bones[constraint_child.subtarget].matrix_local.inverted()
                #             constraint_child.inverse_matrix = matrix
                #             constraint_child.influence = .5
                #         if (type == 2):  # SMOOTH
                #             groupName = 'SMOOTH'
                #             boneGroup = armature_ob.pose.bone_groups.get(groupName)
                #             if not boneGroup:
                #                 boneGroup = armature_ob.pose.bone_groups.new(name=groupName)
                #                 boneGroup.color_set = 'THEME14'
                #             pose_bone.bone_group = boneGroup
                #             driver = armature_ob.driver_add(f'pose.bones["{bone_name}"].rotation_quaternion')
                #             expression = '(mld.to_quaternion().inverted() @ mls.to_quaternion() @ mbs.to_quaternion() @ mls.to_quaternion().inverted() @ mld.to_quaternion()).slerp(((1, 0, 0, 0)), .5)'
                #             build_driver(driver, expression, 0, bone_name, target_name)
                #             build_driver(driver, expression, 1, bone_name, target_name)
                #             build_driver(driver, expression, 2, bone_name, target_name)
                #             build_driver(driver, expression, 3, bone_name, target_name)

            armature_ob.select_set(state=True)

    # wm.progress_end()
    return {'FINISHED'}


def build_driver(driver, expression, component, source_bone, target_bone):
    rot_comp = driver[component]
    rot_comp.driver.type = 'SCRIPTED'
    rot_comp.driver.expression = expression + '[' + str(component) + ']'

    var = rot_comp.driver.variables.new()
    var.type = 'SINGLE_PROP'
    var.name = 'mls'
    var.targets[0].id = rot_comp.id_data
    var.targets[0].data_path = 'data.bones["' + target_bone + '"].matrix_local'

    var = rot_comp.driver.variables.new()
    var.type = 'SINGLE_PROP'
    var.name = 'mld'
    var.targets[0].id = rot_comp.id_data
    var.targets[0].data_path = 'data.bones["' + source_bone + '"].matrix_local'

    var = rot_comp.driver.variables.new()
    var.type = 'SINGLE_PROP'
    var.name = 'mbs'
    var.targets[0].id = rot_comp.id_data
    var.targets[0].data_path = 'pose.bones["' + target_bone + '"].matrix_basis'


class ImportHaydeeSkel(Operator, ImportHelper):
    bl_idname = "haydee_importer.skel"
    bl_label = "Import Haydee Skel (.skel/.skeleton)"
    bl_description = "Import a Haydee Skeleton"
    bl_options = {'REGISTER', 'UNDO'}
    filename_ext = ".skel"
    filter_glob: StringProperty(
        default="*.skel;*.skeleton",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    def execute(self, context):
        return read_skel(self, context, self.filepath)


# --------------------------------------------------------------------------------
# .dskel importer
# --------------------------------------------------------------------------------

def read_dskel(operator, context, filepath):
    print('dskel:', filepath)
    with ProgressReport(context.window_manager) as progReport:
        with ProgressReportSubstep(progReport, 4, "Importing dskel", "Finish Importing dskel") as progress:

            data = None
            encoding = "utf-8-sig"
            with open(filepath, "r", encoding=encoding) as a_file:
                data = io.StringIO(a_file.read())

            line = stripLine(data.readline())
            line_split = line.split()
            line_start = line_split[0]
            signature = line_start

            print('Signature:', signature)
            if signature != 'HD_DATA_TXT':
                print("Unrecognized signature: %s" % signature)
                operator.report({'ERROR'}, "Unrecognized file format")
                return {'FINISHED'}

            level = 0
            boneCount = 0
            jointName = None
            jointNames = []
            jointOrigin = []
            jointAxis = []
            jointParents = []
            jointWidth = []
            jointHeight = []
            jointLength = []

            # steps = len(data.getvalue().splitlines()) - 1
            progress.enter_substeps(1, "Parse Data")
            # Read model data
            for lineData in data:
                line = stripLine(lineData)
                line_split = line.split()
                line_start = None
                i = len(line_split)
                if (i == 0):
                    continue
                line_start = line_split[0]
                if (line_start in ('{')):
                    level += 1
                if (line_start in ('}')):
                    level -= 1
                    contextName = None

                # Joints
                if (line_start == 'skeleton' and level == 0):
                    boneCount = line_split[1]
                if (line_start == 'bone' and level == 1):
                    jointName = line_split[1]
                    jointNames.append(jointName)
                    jointParents.append(None)
                if (line_start == 'parent' and level >= 2):
                    jointParents[len(jointParents) - 1] = line_split[1]
                if (line_start == 'origin' and level >= 2):
                    readVec(line_split, jointOrigin, 3, float)
                if (line_start == 'axis' and level >= 2):
                    readVec(line_split, jointAxis, 4, float)

                if (line_start == 'width' and level >= 2):
                    jointWidth.append(float(line_split[1]))
                if (line_start == 'height' and level >= 2):
                    jointHeight.append(float(line_split[1]))
                if (line_start == 'length' and level >= 2):
                    jointLength.append(float(line_split[1]))

            for idx, name in enumerate(jointNames):
                jointNames[idx] = boneRenameBlender(name)

            for idx, name in enumerate(jointParents):
                if name:
                    jointParents[idx] = boneRenameBlender(name)

            if (bpy.context.mode != 'OBJECT'):
                bpy.ops.object.mode_set(mode='OBJECT')
            print('deselect')
            bpy.ops.object.select_all(action='DESELECT')

            armature_ob = None
            if jointNames:
                boneCount = len(jointNames)
                progress.enter_substeps(boneCount, "Build armature")
                print('Importing Armature', str(boneCount), 'bones')

                armature_da = bpy.data.armatures.new(ARMATURE_NAME)
                # armature_da.display_type = 'STICK'
                armature_ob = bpy.data.objects.new(ARMATURE_NAME, armature_da)
                armature_ob.show_in_front = True

                collection = createCollection(ARMATURE_NAME)
                setActiveCollection(ARMATURE_NAME)
                linkToActiveCollection(armature_ob)

                bpy.context.view_layer.objects.active = armature_ob
                bpy.ops.object.mode_set(mode='EDIT')

                # create all Bones
                progress.enter_substeps(boneCount, "create bones")
                for idx, jointName in enumerate(jointNames):
                    editBone = armature_ob.data.edit_bones.new(jointName)
                    editBone.tail = Vector(editBone.head) + Vector((0, 0, 1))
                    editBone.length = jointLength[idx]
                    progress.step()
                progress.leave_substeps("create bones end")

                # set all bone parents
                progress.enter_substeps(boneCount, "parenting bones")
                for idx, jointParent in enumerate(jointParents):
                    if (jointParent):
                        editBone = armature_da.edit_bones[idx]
                        editBone.parent = armature_da.edit_bones[jointParent]
                    progress.step()
                progress.leave_substeps("parenting bones end")

                # origins of each bone is relative to its parent
                # recalc all origins
                progress.enter_substeps(boneCount, "aligning bones")

                for edit_bone in armature_da.edit_bones:
                    idx = jointNames.index(edit_bone.name)
                    quat = Quaternion(jointAxis[idx])
                    quat = Quaternion((-quat.z, quat.w, quat.y, -quat.x))
                    mat = quat.to_matrix().to_4x4()
                    r = Quaternion([0, 0, 1], pi / 2)
                    boneRot = r.to_matrix().to_4x4()
                    mat = mat @ boneRot
                    pos = Vector(jointOrigin[idx])
                    pos = Vector((-pos.y, -pos.z, pos.x))
                    mat.translation = vectorSwapSkel(pos)
                    edit_bone.matrix = mat
                    progress.step()
                progress.leave_substeps("aligning bones end")

                # lenght of bones
                for bone in armature_da.edit_bones:
                    for child in bone.children:
                        center = child.head
                        proxVec = center - bone.head
                        boneVec = bone.tail - bone.head
                        norm = proxVec.dot(boneVec) / boneVec.dot(boneVec)
                        if (norm > 0.1):
                            proyVec = norm * boneVec
                            dist = (proxVec - proyVec).length
                            if (dist < 0.001):
                                bone.tail = center

            bpy.ops.object.mode_set(mode='OBJECT')
            progress.leave_substeps("Build armature end")

    armature_ob.select_set(state=True)
    return {'FINISHED'}


class ImportHaydeeDSkel(Operator, ImportHelper):
    bl_idname = "haydee_importer.dskel"
    bl_label = "Import Haydee DSkel (.dskel)"
    bl_description = "Import a Haydee DSkeleton"
    bl_options = {'REGISTER', 'UNDO'}
    filename_ext = ".dskel"
    filter_glob: StringProperty(
        default="*.dskel",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    def execute(self, context):
        return read_dskel(self, context, self.filepath)


# --------------------------------------------------------------------------------
# .dmesh importer
# --------------------------------------------------------------------------------

def recurBonesOriginMesh(progress, parentBone, jointNames, jointAxis, jointOrigin):
    for childBone in parentBone.children:
        if childBone:
            idx = jointNames.index(childBone.name)
            mat = Quaternion(jointAxis[idx]).to_matrix().to_4x4()
            pos = Vector(jointOrigin[idx])

            # INV row
            x1 = Matrix(((-1, 0, 0, 0),
                        (0, 0, 1, 0),
                        (0, -1, 0, 0),
                        (0, 0, 0, 1)))
            # INV col
            x2 = Matrix(((1, 0, 0, 0),
                        (0, 0, 1, 0),
                        (0, 1, 0, 0),
                        (0, 0, 0, 1)))

            mat = parentBone.matrix @ (x1 @ mat @ x2)
            pos = parentBone.matrix @ Vector((-pos.z, pos.x, pos.y))
            mat.translation = pos
            childBone.matrix = mat

            recurBonesOriginMesh(progress, childBone, jointNames, jointAxis, jointOrigin)
            progress.step()


def coordTransform(coord):
    return [-coord[0], -coord[2], coord[1]]


def readVec(line_split, vec_data, vec_len, func):
    vec = [func(v) for v in line_split[1:]]
    vec_data.append(tuple(vec[:vec_len]))


def readWeights(line_split, vert_data):
    vec = tuple((int(line_split[1]), int(line_split[2]), float(line_split[3])))
    vert_data.append(vec)


def stripLine(line):
    return line.strip().strip(';')


def read_dmesh(operator, context, filepath, file_format):
    print('dmesh:', filepath)
    with ProgressReport(context.window_manager) as progReport:
        with ProgressReportSubstep(progReport, 4, "Importing dmesh", "Finish Importing dmesh") as progress:
            if (bpy.context.mode != 'OBJECT'):
                bpy.ops.object.mode_set(mode='OBJECT')

            bpy.ops.object.select_all(action='DESELECT')
            print("Importing dmesh: %s" % filepath)

            basename = os.path.basename(filepath)
            collName = os.path.splitext(basename)[0]
            collection = createCollection(collName)
            setActiveCollection(collName)

            vert_data = None
            uv_data = None
            face_data = None

            progress.enter_substeps(1, "Read file")
            data = None
            encoding = "utf-8-sig"
            with open(filepath, "r", encoding=encoding) as a_file:
                data = io.StringIO(a_file.read())
            progress.leave_substeps("Read file end")

            line = stripLine(data.readline())
            line_split = line.split()
            line_start = line_split[0]
            signature = line_start

            print('Signature:', signature)
            if signature != 'HD_DATA_TXT':
                print("Unrecognized signature: %s" % signature)
                operator.report({'ERROR'}, "Unrecognized file format")
                return {'FINISHED'}

            level = 0
            vert_data = []
            uv_data = []
            face_verts = []
            face_uvs = []
            smoothGroups = []
            vCount = None

            jointName = None
            jointNames = []
            jointOrigin = []
            jointAxis = []
            jointParents = []

            weights = []

            meshFaces = {}
            meshUvs = {}
            meshSmoothGroups = {}

            contextName = None
            meshName = None

            # steps = len(data.getvalue().splitlines()) - 1
            progress.enter_substeps(1, "Parse Data")
            # Read model data
            for lineData in data:
                line = stripLine(lineData)
                line_split = line.split()
                line_start = None
                i = len(line_split)
                if (i == 0):
                    continue
                line_start = line_split[0]
                if (line_start in ('{')):
                    level += 1
                if (line_start in ('}')):
                    level -= 1
                    contextName = None

                if (line_start == 'verts', 'face', 'joint'):
                    contextName = line_start

                # All verts
                if (line_start == 'vert'):
                    readVec(line_split, vert_data, 3, float)

                # All UVs
                if (line_start == 'uv'):
                    readVec(line_split, uv_data, 2, float)

                # Faces
                if (line_start == 'group' and level >= 2):
                    meshName = line_split[1]
                    meshFaces[meshName] = []
                    meshUvs[meshName] = []
                    meshSmoothGroups[meshName] = []

                if (line_start == 'count' and level >= 3):
                    vCount = int(line_split[1])
                if (line_start == 'verts' and level >= 3):
                    readVec(line_split, meshFaces[meshName], vCount, int)
                if (line_start == 'uvs' and level >= 3):
                    readVec(line_split, meshUvs[meshName], vCount, int)
                if (line_start == 'smoothGroup' and level >= 3):
                    meshSmoothGroups[meshName].append(int(line_split[1]))

                # Joints
                if (line_start == 'joint' and level >= 2):
                    jointName = line_split[1]
                    jointNames.append(jointName)
                    jointParents.append(None)
                if (line_start == 'parent' and level >= 3):
                    jointParents[len(jointParents) - 1] = line.split(' ', 1)[1]
                if (line_start == 'origin' and level >= 3):
                    readVec(line_split, jointOrigin, 3, float)
                if (line_start == 'axis' and level >= 3):
                    readVec(line_split, jointAxis, 4, float)

                # Joints (Vert, Bone, Weight)
                if (line_start == 'weight' and level >= 2):
                    readWeights(line_split, weights)
                # progress.step()
            progress.leave_substeps("Parse Data end")

            for idx, name in enumerate(jointNames):
                jointNames[idx] = boneRenameBlender(name)

            for idx, name in enumerate(jointParents):
                if name:
                    jointParents[idx] = boneRenameBlender(name)

            # create armature
            armature_ob = None
            if jointNames:
                boneCount = len(jointNames)
                progress.enter_substeps(boneCount, "Build armature")
                print('Importing Armature', str(boneCount), 'bones')

                armature_da = bpy.data.armatures.new(ARMATURE_NAME)
                # armature_da.display_type = 'STICK'
                armature_ob = bpy.data.objects.new(ARMATURE_NAME, armature_da)
                armature_ob.show_in_front = True

                linkToActiveCollection(armature_ob)
                bpy.context.view_layer.objects.active = armature_ob
                bpy.ops.object.mode_set(mode='EDIT')

                # create all Bones
                progress.enter_substeps(boneCount, "create bones")
                for idx, jointName in enumerate(jointNames):
                    editBone = armature_ob.data.edit_bones.new(jointName)
                    editBone.tail = Vector(editBone.head) + Vector((0, 0, 1))
                    progress.step()
                progress.leave_substeps("create bones end")

                # set all bone parents
                progress.enter_substeps(boneCount, "parenting bones")
                for idx, jointParent in enumerate(jointParents):
                    if (jointParent is not None):
                        editBone = armature_da.edit_bones[idx]
                        editBone.parent = armature_da.edit_bones[jointParent]
                    progress.step()
                progress.leave_substeps("parenting bones end")

                # origins of each bone is relative to its parent
                # recalc all origins
                progress.enter_substeps(boneCount, "aligning bones")
                rootBones = [rootBone for rootBone in armature_da.edit_bones if rootBone.parent is None]
                for rootBone in rootBones:
                    idx = jointNames.index(rootBone.name)
                    mat = Quaternion(jointAxis[idx]).to_matrix().to_4x4()
                    pos = Vector(jointOrigin[idx])
                    mat.translation = vectorSwapSkel(pos)
                    rootBone.matrix = SWAP_ROW_SKEL @ mat @ SWAP_COL_SKEL
                    recurBonesOriginMesh(progress, rootBone, jointNames, jointAxis, jointOrigin)
                    progress.step()
                progress.leave_substeps("aligning bones end")

                # lenght of bones
                for bone in armature_da.edit_bones:
                    for child in bone.children:
                        center = child.head
                        proxVec = center - bone.head
                        boneVec = bone.tail - bone.head
                        norm = proxVec.dot(boneVec) / boneVec.dot(boneVec)
                        if (norm > 0.1):
                            proyVec = norm * boneVec
                            dist = (proxVec - proyVec).length
                            if (dist < 0.001):
                                bone.tail = center

                bpy.ops.object.mode_set(mode='OBJECT')
                progress.leave_substeps("Build armature end")

            if armature_ob:
                armature_ob.select_set(state=True)

            # Create mesh (verts and faces)
            progress.enter_substeps(len(meshFaces), "creating meshes")
            for meshName, face_verts in meshFaces.items():
                # face_verts = meshFaces[meshName]
                face_uvs = meshUvs[meshName]
                smoothGroups = meshSmoothGroups[meshName]

                progress.enter_substeps(1, "vertdic")
                vertDic = []
                for face in face_verts:
                    for vertIdx in face:
                        if vertIdx not in vertDic:
                            vertDic.append(vertIdx)
                progress.leave_substeps("vertdic end")

                # Obtain mesh exclusive verts and renumerate for faces
                progress.enter_substeps(1, "local verts")
                objVerts = [vert_data[oldIdx] for oldIdx in vertDic]
                objFaces = [tuple(vertDic.index(oldIdx) for oldIdx in face)[::-1] for face in face_verts]
                progress.leave_substeps("local verts end")

                progress.enter_substeps(1, "mesh data")
                mesh_data = bpy.data.meshes.new(meshName)
                mesh_data.from_pydata(list(map(coordTransform, objVerts)), [], objFaces)
                # Shade smooth
                mesh_data.use_auto_smooth = True
                mesh_data.auto_smooth_angle = pi
                mesh_data.polygons.foreach_set("use_smooth",
                                               [True] * len(mesh_data.polygons))
                progress.leave_substeps("mesh data end")

                # apply UVs
                progress.enter_substeps(1, "uv")
                useUvs = True
                if useUvs and face_uvs is not None:
                    mesh_data.uv_layers.new()
                    blen_uvs = mesh_data.uv_layers[-1]
                    for idx, uvs in enumerate([uv for uvs in face_uvs for uv in uvs[::-1]]):
                        uv_coord = Vector(uv_data[int(uvs)])
                        if (file_format=='H2'):
                            uv_coord = Vector((uv_coord.x, 1-uv_coord.y))
                        blen_uvs.data[idx].uv = uv_coord
                progress.leave_substeps("uv end")

                useSmooth = True
                if useSmooth:
                    # unique_smooth_groups
                    unique_smooth_groups = {}
                    for g in set(smoothGroups):
                        unique_smooth_groups[g] = None

                    if unique_smooth_groups:
                        sharp_edges = set()
                        smooth_group_users = {context_smooth_group: {} for context_smooth_group in unique_smooth_groups.keys()}
                        context_smooth_group_old = -1

                    # detect if edge is used in faces with different Smoothing Groups
                    progress.enter_substeps(1, "detect smooth")
                    for idx, face_vert_loc_indices in enumerate(objFaces):
                        len_face_vert_loc_indices = len(face_vert_loc_indices)
                        context_smooth_group = smoothGroups[idx]
                        if unique_smooth_groups and context_smooth_group:
                            # Is a part of of a smooth group and is a face
                            if context_smooth_group_old is not context_smooth_group:
                                edge_dict = smooth_group_users[context_smooth_group]
                                context_smooth_group_old = context_smooth_group
                            prev_vidx = face_vert_loc_indices[-1]
                            for vidx in face_vert_loc_indices:
                                edge_key = (prev_vidx, vidx) if (prev_vidx < vidx) else (vidx, prev_vidx)
                                prev_vidx = vidx
                                edge_dict[edge_key] = edge_dict.get(edge_key, 0) + 1
                    progress.leave_substeps("detect smooth end")

                    # Build sharp edges
                    progress.enter_substeps(1, "build sharp")
                    if unique_smooth_groups:
                        for edge_dict in smooth_group_users.values():
                            for key, users in edge_dict.items():
                                if users == 1:  # This edge is on the boundry of 2 groups
                                    sharp_edges.add(key)
                    progress.leave_substeps("build sharp end")

                    # Mark sharp edges
                    progress.enter_substeps(1, "mark sharp")
                    if unique_smooth_groups and sharp_edges:
                        for e in mesh_data.edges:
                            if e.key in sharp_edges:
                                e.use_edge_sharp = True
                        # mesh_data.show_edge_sharp = True
                    progress.leave_substeps("mark sharp end")

                progress.enter_substeps(1, "linking")
                # link data to new Object
                mesh_obj = bpy.data.objects.new(mesh_data.name, mesh_data)
                progress.leave_substeps("linking end")

                # Assign vertex weights
                progress.enter_substeps(1, "weights")
                if weights:
                    for w in [weight for weight in weights if weight[0] in vertDic]:
                        boneName = jointNames[w[1]]
                        armature_da = armature_ob.data
                        bone = armature_da.bones.get(boneName)
                        if bone:
                            vertGroup = mesh_obj.vertex_groups.get(boneName)
                            if not vertGroup:
                                vertGroup = mesh_obj.vertex_groups.new(name=boneName)
                            vertGroup.add([vertDic.index(w[0])], w[2], 'REPLACE')
                progress.leave_substeps("weights end")

                # parenting
                progress.enter_substeps(1, "parent")
                if armature_ob:
                    # parent armature
                    mesh_obj.parent = armature_ob
                    # armature modifier
                    mod = mesh_obj.modifiers.new(type="ARMATURE", name="Armature")
                    mod.use_vertex_groups = True
                    mod.object = armature_ob
                progress.leave_substeps("parent end")

                linkToActiveCollection(mesh_obj)
                mesh_obj.select_set(state=True)
                # scene.update()
                progress.step()
            progress.leave_substeps("creating meshes end")

    return {'FINISHED'}


class ImportHaydeeDMesh(Operator, ImportHelper):
    bl_idname = "haydee_importer.dmesh"
    bl_label = "Import Haydee DMesh (.dmesh)"
    bl_description = "Import a Haydee DMesh"
    bl_options = {'REGISTER', 'UNDO'}
    filename_ext = ".dmesh"
    filter_glob: StringProperty(
        default="*.dmesh",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    file_format: file_format_prop

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        return read_dmesh(self, context, self.filepath, self.file_format)


# --------------------------------------------------------------------------------
# .mesh importer
# --------------------------------------------------------------------------------

def read_mesh(operator, context, filepath, outfitName, file_format):
    print('Mesh:', filepath)
    with ProgressReport(context.window_manager) as progReport:
        with ProgressReportSubstep(progReport, 4,
                                   "Importing mesh", "Finish Importing mesh") as progress:
            if (bpy.context.mode != 'OBJECT'):
                bpy.ops.object.mode_set(mode='OBJECT')

            SIGNATURE_SIZE = 28
            CHUNK_SIZE = 48
            INIT_INFO = 32
            VERT_SIZE = 60
            FACE_SIZE = 12
            DEFAULT_MESH_NAME = os.path.splitext(os.path.basename(filepath))[0]
            if outfitName:
                DEFAULT_MESH_NAME = DEFAULT_MESH_NAME

            bpy.ops.object.select_all(action='DESELECT')
            print("Importing mesh: %s" % filepath)

            progress.enter_substeps(1, "Read file")
            data = None
            with open(filepath, "rb") as a_file:
                data = a_file.read()
            progress.leave_substeps("Read file end")

            (signature, chunkCount, totalSize) = \
                struct.unpack('20sII', data[0:SIGNATURE_SIZE])
            signature = decodeText(signature)
            print('Signature:', signature)
            if signature != 'HD_CHUNK':
                print("Unrecognized signature: %s" % signature)
                operator.report({'ERROR'}, "Unrecognized file format")
                return {'FINISHED'}

            offset = SIGNATURE_SIZE + (CHUNK_SIZE * chunkCount)
            (vertCount, loopCount, x1, y1, z1, x2, y2, z2) = \
                struct.unpack('II3f3f', data[offset:offset + INIT_INFO])

            posTop = Vector((-x1, z1, -y1))
            posBottom = Vector((-x2, z2, -y2))

            headerSize = SIGNATURE_SIZE + (CHUNK_SIZE * chunkCount) + INIT_INFO
            delta = headerSize

            vert_data = []
            uv_data = []
            normals = []

            for n in range(vertCount):
                offset = delta + (VERT_SIZE * n)
                (
                    x, y, z,
                    u, v,
                    vcolorR, vcolorG, vcolorB, vcolorA,
                    normX, normY, normZ,
                    tanX, tanY, tanZ,
                    bitanX, bitanY, bitanZ) = \
                    struct.unpack('3f2f4B9f', data[offset:offset + VERT_SIZE])
                vert = Vector((-x, -z, y))
                uv = Vector((u, v))
                norm = Vector((-normX, -normZ, normY))
                vert_data.append(vert)
                uv_data.append(uv)
                normals.append(norm)

            faceCount = loopCount // 3
            delta = headerSize + (VERT_SIZE * vertCount)
            face_data = []
            print('faceCount', faceCount)
            for n in range(faceCount):
                offset = delta + (FACE_SIZE * n)
                (v1, v2, v3) = struct.unpack('3I', data[offset:offset + FACE_SIZE])
                face = [v3, v2, v1]
                face_data.append(face)

            # Create Mesh
            progress.enter_substeps(1, "mesh data")
            mesh_data = bpy.data.meshes.new(DEFAULT_MESH_NAME)
            mesh_data.from_pydata(vert_data, [], face_data)
            # Shade smooth
            mesh_data.use_auto_smooth = True
            mesh_data.auto_smooth_angle = pi
            mesh_data.polygons.foreach_set("use_smooth",
                                           [True] * len(mesh_data.polygons))
            progress.leave_substeps("mesh data end")

            # apply UVs
            progress.enter_substeps(1, "uv")
            useUvs = True
            if useUvs and uv_data is not None:
                mesh_data.uv_layers.new()
                blen_uvs = mesh_data.uv_layers[-1]
                for loop in mesh_data.loops:
                    uv_coord = Vector(uv_data[loop.vertex_index])
                    if (file_format=='H2'):
                        uv_coord = Vector((uv_coord.x, 1-uv_coord.y))
                    blen_uvs.data[loop.index].uv = uv_coord
            progress.leave_substeps("uv end")

            # normals
            use_edges = True
            mesh_data.create_normals_split()
            meshCorrected = mesh_data.validate(clean_customdata=False)  # *Very* important to not remove nors!
            mesh_data.update(calc_edges=use_edges)
            mesh_data.normals_split_custom_set_from_vertices(normals)
            mesh_data.use_auto_smooth = True

            mesh_obj = bpy.data.objects.new(mesh_data.name, mesh_data)
            linkToActiveCollection(mesh_obj)
            mesh_obj.select_set(state=True)
            bpy.context.view_layer.objects.active = mesh_obj

    return {'FINISHED'}


class ImportHaydeeMesh(Operator, ImportHelper):
    bl_idname = "haydee_importer.mesh"
    bl_label = "Import Haydee mesh (.mesh)"
    bl_description = "Import a Haydee Mesh"
    bl_options = {'REGISTER', 'UNDO'}
    filename_ext = ".mesh"
    filter_glob: StringProperty(
        default="*.mesh",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    file_format: file_format_prop

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        return read_mesh(self, context, self.filepath, None, self.file_format)


# --------------------------------------------------------------------------------
# .motion importer
# --------------------------------------------------------------------------------

# Helper for commong logic
def read_motion_bones(memData, boneCount, numFrames, TRACK_SIZE, KEY_SIZE, TRACK_OFFSET, KEY_OFFSET):
    unpack_bone = struct.Struct('<32sI').unpack
    unpack_key = struct.Struct('3f4f').unpack
    bones, boneNames = dict(), []
    for n in range(boneCount):
        offset = TRACK_OFFSET + (TRACK_SIZE * n)
        (name, firstKey) = unpack_bone(memData[offset:offset + TRACK_SIZE])
        name = boneRenameBlender(readStrA_term(0, 32, memoryview(name))[0])
        keys = []
        for k in range(firstKey, firstKey + numFrames):
            offset = KEY_OFFSET + (KEY_SIZE * k)
            (x, y, z, qx, qz, qy, qw) = unpack_key(memData[offset:offset + KEY_SIZE])
            keys.append((x, y, z, qx, qz, qy, qw))
        bones[name] = keys
        boneNames.append(name)
    return (boneNames, bones)



def read_motion(operator, context, filepath):
    armature = find_armature(operator, context)
    if not armature:
        return {'FINISHED'}

    with open(filepath, "rb") as a_file:
        data = a_file.read()
    mview = memoryview(data)

    (entries, serialSize, assType) = struct.unpack('<ii6s', mview[20:34])
    assType, sig = assType.decode("latin"), sig_check(mview)
    propMap, numFrames = None, None
    unpack_int = struct.Struct('<i').unpack
    unpack_entry = struct.Struct('<32siiii').unpack

    if (sig == Signature.HD_CHUNK and assType == 'motion'):
        print('Signature:', Signature.HD_CHUNK.name)
        propMap = dict(numFrames={'reader': lambda x: unpack_int(x)[0]},
                       duration= {'reader': lambda x: unpack_int(x)[0]},
                       numKeys=  {'reader': lambda x: unpack_int(x)[0]},
                       numTracks={'reader': lambda x: unpack_int(x)[0]},
                       numEvents={'reader': lambda x: unpack_int(x)[0]},
                       keys=     {'reader': lambda x: True},
                       tracks=   {'reader': lambda x: True},
                       events=   {'reader': lambda x: False})

        dataOffset = 28 + (entries * 48)

        for x in range(1, entries):
            sPos = 28 + (x * 48)
            (name, size, offset, numSubs, subs) = unpack_entry(mview[sPos:sPos+48])
            name = readStrA_term(0, 32, memoryview(name))[0]
            propMap[name].update(dict(zip(['size', 'offset', 'numSubs', 'subs', 'hasValue'],[size, offset, numSubs, subs, size > 0])))

        for key, value in propMap.items():
            if (value.get("hasValue")):
                (f, lSize, lOff) = (value['reader'], value['size'], value['offset'])
                lOff = dataOffset + lOff
                value["value"] = f(mview[lOff:lOff+lSize])

        numFrames = propMap['numFrames']['value']
        boneCount = propMap['numTracks']['value']
        trackSize = int(propMap['tracks']['size'] / boneCount)
        keySize = int(propMap['keys']['size'] / propMap['numKeys']['value'])
        trackOffset = 28 + (entries * 48) + int(propMap['tracks']['offset'])
        keyOffset = 28 + (entries * 48) + int(propMap['keys']['offset'])
        (boneNames, bones) = read_motion_bones(mview, boneCount, numFrames, trackSize, keySize, trackOffset, keyOffset)

    elif (sig == Signature.HD_MOTION):
        print('Signature:', Signature.HD_MOTION.name)
        KEY_SIZE = 28
        TRACK_SIZE = 36

        (keyCount, boneCount, firstFrame, duration, numFrames, dataSize) = struct.unpack('6I', data[20:44])
        keyOffset = 44
        trackOffset = 44 + int(KEY_SIZE * keyCount)
        (boneNames, bones) = read_motion_bones(mview, boneCount, numFrames, TRACK_SIZE, KEY_SIZE, trackOffset, keyOffset)

    else:
        print("Unrecognized signature or asset type: [%s], %s" % (binascii.hexlify(mview[0:16]), assType))
        operator.report({'ERROR'}, "Unrecognized file format")
        return {'FINISHED'}

    boneNames.reverse()

    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    # armature.hide = False
    armature.select_set(state=True)
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode='POSE')

    wm = bpy.context.window_manager
    wm.progress_begin(0, numFrames)

    r = Quaternion([0, 0, 1], pi / 2).to_matrix().to_4x4()

    context.scene.frame_start = 1
    context.scene.frame_end = numFrames
    for pose in context.selected_pose_bones:
        pose.bone.select = False
    for frame in range(1, numFrames + 1):
        wm.progress_update(frame - 1)
        context.scene.frame_set(frame)
        for name in boneNames:
            bone_name = name
            if not (bone_name in armature.data.bones):
                print("WARNING: Bone named " + bone_name + " not found in armature")
                continue

            bone = armature.data.bones[bone_name]
            pose = armature.pose.bones[bone_name]
            if not bone:
                continue
            bone.select = True

            (x, y, z, qx, qz, qy, qw) = bones[bone_name][frame - 1]

            origin = Vector([-z, x, y])
            q = Quaternion([qw, -qy, qx, qz])
            m = q.to_matrix().to_4x4()
            m.translation = origin

            if bone.parent:
                m = pose.parent.matrix @ m

            pose.matrix = m

        # Rotate bone not in 'SK_Root' chain
        rootBones = [rootBone for rootBone in armature.pose.bones if rootBone.parent is None]
        for poseBone in rootBones:
            bone_name = poseBone.name
            data = bones.get(bone_name)
            if data:
                (x, y, z, qx, qz, qy, qw) = bones[bone_name][frame - 1]
                origin = Vector([-z, x, y])
                q = Quaternion([qw, -qy, qx, qz])
                m = q.to_matrix().to_4x4()
                m.translation = origin
                poseBone.matrix = r @ m

        bpy.ops.anim.keyframe_insert(type='Rotation', confirm_success=False)
        bpy.ops.anim.keyframe_insert(type='Location', confirm_success=False)
        for name, keys in bones.items():
            if not (bone_name in armature.data.bones):
                continue
            bone = armature.data.bones[bone_name]
            if not bone:
                continue
            bone.select = False

    bpy.ops.object.mode_set(mode='OBJECT')
    wm.progress_end()
    return {'FINISHED'}


class ImportHaydeeMotion(Operator, ImportHelper):
    bl_idname = "haydee_importer.motion"
    bl_label = "Import Haydee Motion (.motion)"
    bl_description = "Import a Haydee Motion"
    bl_options = {'REGISTER', 'UNDO'}
    filename_ext = ".motion"
    filter_glob: StringProperty(
        default="*.motion",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    def execute(self, context):
        return read_motion(self, context, self.filepath)


# --------------------------------------------------------------------------------
# .dmot importer
# --------------------------------------------------------------------------------

def read_dmotion(operator, context, filepath):
    armature = find_armature(operator, context)
    if not armature:
        return {'FINISHED'}

    print('dpose:', filepath)
    with ProgressReport(context.window_manager) as progReport:
        with ProgressReportSubstep(progReport, 4, "Importing dpose", "Finish Importing dpose") as progress:
            if (bpy.context.mode != 'OBJECT'):
                bpy.ops.object.mode_set(mode='OBJECT')

            bpy.ops.object.select_all(action='DESELECT')
            print("Importing dpose: %s" % filepath)

            progress.enter_substeps(1, "Read file")
            data = None
            encoding = "utf-8-sig"
            with open(filepath, "r", encoding=encoding) as a_file:
                data = io.StringIO(a_file.read())
            progress.leave_substeps("Read file end")

            line = stripLine(data.readline())
            line_split = line.split()
            line_start = line_split[0]
            signature = line_start

            print('Signature:', signature)
            if signature != 'HD_DATA_TXT':
                print("Unrecognized signature: %s" % signature)
                operator.report({'ERROR'}, "Unrecognized file format")
                return {'FINISHED'}

            contextName = None
            bones = {}
            level = 0
            numTracks = None
            numFrames = None
            frameRate = None
            track = None
            boneName = None

            # steps = len(data.getvalue().splitlines()) - 1
            progress.enter_substeps(1, "Parse Data")
            # Read model data
            for lineData in data:
                line = stripLine(lineData)
                line_split = line.split()
                line_start = None
                i = len(line_split)
                if (i == 0):
                    continue
                line_start = line_split[0]
                if (line_start in ('{')):
                    level += 1
                if (line_start in ('}')):
                    level -= 1
                    contextName = None

                # info
                if (level >= 1):
                    if (line_start == 'numTracks'):
                        numTracks = int(line_split[1])
                    if (line_start == 'numFrames'):
                        numFrames = int(line_split[1])
                    if (line_start == 'frameRate'):
                        frameRate = int(line_split[1])
                    if (line_start == 'track'):
                        boneName = boneRenameBlender(line_split[1])
                        bones[boneName] = []

                # motion
                if (level >= 2):
                    if (line_start == 'key'):
                        posX, posY, posZ, quatX, quatZ, quatY, quatW = map(float, line_split[1:8])
                        bonePose = (posX, posY, posZ, quatX, quatZ, quatY, quatW)
                        frame = len(bones[boneName])
                        bones[boneName].append(bonePose)

            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.select_all(action='DESELECT')
            # armature.hide = False
            armature.select_set(state=True)
            bpy.context.view_layer.objects.active = armature
            bpy.ops.object.mode_set(mode='POSE')

            wm = bpy.context.window_manager
            wm.progress_begin(0, numFrames)

            r = Quaternion([0, 0, 1], pi / 2).to_matrix().to_4x4()

            context.scene.frame_start = 1
            context.scene.frame_end = numFrames
            for pose in context.selected_pose_bones:
                pose.bone.select = False
            for frame in range(1, numFrames + 1):
                wm.progress_update(frame - 1)
                context.scene.frame_set(frame)
                for name in bones.keys():
                    bone_name = name
                    if not (bone_name in armature.data.bones):
                        print("WARNING: Bone named " + bone_name + " not found in armature")
                        continue

                    bone = armature.data.bones[bone_name]
                    pose = armature.pose.bones[bone_name]
                    if not bone:
                        continue
                    bone.select = True

                    (x, y, z, qx, qz, qy, qw) = bones[bone_name][frame - 1]

                    origin = Vector([-z, x, y])
                    q = Quaternion([qw, -qy, qx, qz])
                    m = q.to_matrix().to_4x4()
                    m.translation = origin

                    if bone.parent:
                        m = pose.parent.matrix @ m
                    else:
                        origin = Vector([-x, -z, y])
                        m.translation = origin
                        m = m @ r

                    pose.matrix = m

                bpy.ops.anim.keyframe_insert(type='Rotation', confirm_success=False)
                bpy.ops.anim.keyframe_insert(type='Location', confirm_success=False)
                for name, keys in bones.items():
                    if not (bone_name in armature.data.bones):
                        continue
                    bone = armature.data.bones[bone_name]
                    if not bone:
                        continue
                    bone.select = False

            bpy.ops.object.mode_set(mode='OBJECT')
            wm.progress_end()
    return {'FINISHED'}


class ImportHaydeeDMotion(Operator, ImportHelper):
    bl_idname = "haydee_importer.dmot"
    bl_label = "Import Haydee DMotion (.dmot)"
    bl_description = "Import a Haydee DMotion"
    bl_options = {'REGISTER', 'UNDO'}
    filename_ext = ".dmot"
    filter_glob: StringProperty(
        default="*.dmot",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    def execute(self, context):
        return read_dmotion(self, context, self.filepath)


# --------------------------------------------------------------------------------
# .pose importer
# --------------------------------------------------------------------------------

def read_pose(operator, context, filepath):

    armature = find_armature(operator, context)
    if not armature:
        return {'FINISHED'}

    with open(filepath, "rb") as a_file:
        data = a_file.read()

    SIGNATURE_SIZE = 28
    CHUNK_SIZE = 48
    SIZE2 = 60

    (signature, chunkCount, totalSize) = struct.unpack('20sII', data[0:SIGNATURE_SIZE])
    signature = decodeText(signature)
    print("Signature:", signature)
    if signature != 'HD_CHUNK':
        print("Unrecognized signature: %s" % signature)
        operator.report({'ERROR'}, "Unrecognized file format")
        return {'FINISHED'}

    offset = SIGNATURE_SIZE + (CHUNK_SIZE * chunkCount)
    boneCount = struct.unpack('I', data[offset:offset + 4])
    boneCount = boneCount[0]

    bones = {}
    boneNames = []
    delta = SIGNATURE_SIZE + (CHUNK_SIZE * chunkCount) + 4
    for n in range(boneCount):
        offset = delta + (SIZE2 * n)
        (x, y, z, qx, qz, qy, qw, name) = struct.unpack('3f4f32s', data[offset:offset + SIZE2])
        bonePose = (x, y, z, qx, qz, qy, qw)
        name = decodeText(name)
        name = boneRenameBlender(name)
        bones[name] = bonePose
        boneNames.append(name)

    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    # armature.hide = False
    armature.select_set(state=True)
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode='POSE')
    bpy.ops.pose.select_all(action='DESELECT')

    wm = bpy.context.window_manager
    wm.progress_begin(0, boneCount)

    r = Quaternion([0, 0, 1], pi / 2)

    for i, bone_name in enumerate(boneNames):
        wm.progress_update(i)
        if not (bone_name in armature.data.bones):
            print("WARNING: Bone named " + bone_name + " not found in armature")
            continue

        bone = armature.data.bones.get(bone_name)
        pose = armature.pose.bones.get(bone_name)
        if not bone:
            continue
        bone.select = True

        (x, y, z, qx, qz, qy, qw) = bones[bone_name]

        origin = Vector([-z, x, y])
        q = Quaternion([qw, -qy, qx, qz])
        m = q.to_matrix().to_4x4()
        m.translation = origin

        if bone.parent:
            m = pose.parent.matrix @ m
        else:
            origin = Vector([-x, -z, y])
            m.translation = origin
            m = m @ r.to_matrix().to_4x4()

        pose.matrix = m

    bpy.ops.object.mode_set(mode='OBJECT')
    wm.progress_end()
    return {'FINISHED'}


class ImportHaydeePose(Operator, ImportHelper):
    bl_idname = "haydee_importer.pose"
    bl_label = "Import Haydee Pose (.pose)"
    bl_description = "Import a Haydee Pose"
    bl_options = {'REGISTER', 'UNDO'}
    filename_ext = ".pose"
    filter_glob: StringProperty(
        default="*.pose",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    def execute(self, context):
        return read_pose(self, context, self.filepath)


# --------------------------------------------------------------------------------
# .dpose importer
# --------------------------------------------------------------------------------

def read_dpose(operator, context, filepath):
    armature = find_armature(operator, context)
    if not armature:
        return {'FINISHED'}

    print('dpose:', filepath)
    with ProgressReport(context.window_manager) as progReport:
        with ProgressReportSubstep(progReport, 4, "Importing dpose", "Finish Importing dpose") as progress:
            if (bpy.context.mode != 'OBJECT'):
                bpy.ops.object.mode_set(mode='OBJECT')

            bpy.ops.object.select_all(action='DESELECT')
            print("Importing dpose: %s" % filepath)

            progress.enter_substeps(1, "Read file")
            data = None
            encoding = "utf-8-sig"
            with open(filepath, "r", encoding=encoding) as a_file:
                data = io.StringIO(a_file.read())
            progress.leave_substeps("Read file end")

            line = stripLine(data.readline())
            line_split = line.split()
            line_start = line_split[0]
            signature = line_start

            print('Signature:', signature)
            if signature != 'HD_DATA_TXT':
                print("Unrecognized signature: %s" % signature)
                operator.report({'ERROR'}, "Unrecognized file format")
                return {'FINISHED'}

            contextName = None
            bones = {}
            transformsCount = None
            level = 0

            # steps = len(data.getvalue().splitlines()) - 1
            progress.enter_substeps(1, "Parse Data")
            # Read model data
            for lineData in data:
                line = stripLine(lineData)
                line_split = line.split()
                line_start = None
                i = len(line_split)
                if (i == 0):
                    continue
                line_start = line_split[0]
                if (line_start in ('{')):
                    level += 1
                if (line_start in ('}')):
                    level -= 1
                    contextName = None

                # Transforms
                if (line_start == 'numTransforms' and level >= 1):
                    transformsCount = int(line_split[1])

                # Transforms
                if (line_start == 'transform' and level >= 1):
                    boneName = boneRenameBlender(line_split[1])
                    posX, posY, posZ, quatX, quatZ, quatY, quatW = map(float, line_split[2:9])
                    bonePose = (posX, posY, posZ, -quatX, -quatZ, -quatY, -quatW)
                    bones[boneName] = bonePose

            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.select_all(action='DESELECT')
            # armature.hide = False
            armature.select_set(state=True)
            bpy.context.view_layer.objects.active = armature
            bpy.ops.object.mode_set(mode='POSE')
            bpy.ops.pose.select_all(action='DESELECT')

            wm = bpy.context.window_manager
            wm.progress_begin(0, transformsCount)

            r = Quaternion([0, 0, 1], pi / 2)

            for i, (bone_name, bone_pose) in enumerate(bones.items()):
                wm.progress_update(i)
                if not (bone_name in armature.data.bones):
                    print("WARNING: Bone named " + bone_name + " not found in armature")
                    continue

                bone = armature.data.bones.get(bone_name)
                pose = armature.pose.bones.get(bone_name)
                if not bone:
                    continue
                bone.select = True

                (x, y, z, qx, qz, qy, qw) = bones[bone_name]

                origin = Vector([-z, x, y])
                q = Quaternion([qw, -qy, qx, qz])
                m = q.to_matrix().to_4x4()
                m.translation = origin

                if bone.parent:
                    m = pose.parent.matrix @ m
                else:
                    origin = Vector([-x, -z, y])
                    m.translation = origin
                    m = m @ r.to_matrix().to_4x4()

                pose.matrix = m

            bpy.ops.object.mode_set(mode='OBJECT')
            wm.progress_end()
    return {'FINISHED'}


class ImportHaydeeDPose(Operator, ImportHelper):
    bl_idname = "haydee_importer.dpose"
    bl_label = "Import Haydee DPose (.dpose)"
    bl_description = "Import a Haydee DPose"
    bl_options = {'REGISTER', 'UNDO'}
    filename_ext = ".dpose"
    filter_glob: StringProperty(
        default="*.dpose",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    def execute(self, context):
        return read_dpose(self, context, self.filepath)


# --------------------------------------------------------------------------------
# .outfit importer
# --------------------------------------------------------------------------------

# profile
def read_outfit(operator, context, filepath, file_format):
    print('Outfit:', filepath)
    with ProgressReport(context.window_manager) as progReport:
        with ProgressReportSubstep(progReport, 4, "Importing outfit", "Finish Importing outfit") as progress:

            data = None
            encoding = "utf-8-sig"
            with open(filepath, "r", encoding=encoding, errors="surrogateescape") as a_file:
                data = io.StringIO(a_file.read())

            line = stripLine(data.readline())
            line_split = line.split()
            line_start = line_split[0]
            signature = line_start

            print('Signature:', signature)
            if signature != 'HD_DATA_TXT':
                print("Unrecognized signature: %s" % signature)
                operator.report({'ERROR'}, "Unrecognized file format")
                return {'FINISHED'}

            level = 0
            outfitName = None

            meshFiles = []
            skinFiles = []
            materialFiles = []

            # steps = len(data.getvalue().splitlines()) - 1
            progress.enter_substeps(1, "Parse Data")
            # Read model data
            for lineData in data:
                line = stripLine(lineData)
                line_split = line.split(maxsplit=1)
                line_start = None
                i = len(line_split)
                if (i == 0):
                    continue
                line_start = line_split[0]
                if (line_start in ('{')):
                    level += 1
                if (line_start in ('}')):
                    level -= 1
                    contextName = None

                if (line_start == 'outfit' and level == 0 and len(line_split) > 1):
                    outfitName = line_split[1].replace('"', '')

                # Joints
                if (line_start == 'name' and level == 1):
                    outfitName = line_split[1].replace('"', '')

                if (line_start == 'mesh' and level == 2):
                    meshFiles.append(line_split[1].replace('"', ''))
                    skinFiles.append(None)
                    materialFiles.append(None)
                if (line_start == 'skin' and level == 2):
                    skinFiles[len(meshFiles) - 1] = line_split[1].replace('"', '')
                if (line_start == 'material' and level == 2):
                    materialFiles[len(meshFiles) - 1] = line_split[1].replace('"', '')

            combo = []
            for idx in range(len(meshFiles)):
                mesh = meshFiles[idx]
                skin = skinFiles[idx]
                matr = materialFiles[idx]
                obj = {'mesh': mesh, 'skin': skin, 'matr': matr}
                if obj not in combo:
                    combo.append(obj)

            basedir = os.path.dirname(filepath)
            armature_obj = None
            imported_meshes = []

            collection = createCollection(outfitName)
            setActiveCollection(outfitName)

            for obj in combo:
                meshpath = None
                skinpath = None
                matrpath = None
                meshpath = haydeeFilepath(filepath, obj['mesh'])
                if obj['skin']:
                    skinpath = haydeeFilepath(filepath, obj['skin'])
                if obj['matr']:
                    matrpath = haydeeFilepath(filepath, obj['matr'])

                # Create Mesh
                if meshpath and os.path.exists(meshpath):
                    read_mesh(operator, context, meshpath, outfitName, file_format)
                    imported_meshes.append(bpy.context.view_layer.objects.active)
                else:
                    filename = os.path.splitext(os.path.basename(meshpath))[0]
                    print('File not found:', filename, meshpath)

                # Create Material
                if matrpath and os.path.exists(matrpath):
                    read_material(operator, context, matrpath)
                else:
                    if matrpath:
                        filename = os.path.splitext(os.path.basename(matrpath))[0]
                        print('File not found:', filename, matrpath)

                # Create Skin (bone weights/bones)
                if skinpath and os.path.exists(skinpath):
                    read_skin(operator, context, skinpath, armature_obj)
                else:
                    if skinpath:
                        filename = os.path.splitext(os.path.basename(skinpath))[0]
                        print('File not found:', filename, skinpath)

                # Find armature
                active_obj = bpy.context.view_layer.objects.active
                if (not armature_obj and active_obj and active_obj.type == 'ARMATURE'):
                    armature_obj = active_obj

            for obj in imported_meshes:
                obj.select_set(state=True)
            if armature_obj:
                armature_obj.select_set(state=True)

    return {'FINISHED'}


class ImportHaydeeOutfit(Operator, ImportHelper):
    bl_idname = "haydee_importer.outfit"
    bl_label = "Import Haydee Outfit (.outfit)"
    bl_description = "Import a Haydee Outfit (Meshes, Materials, Skins)"
    bl_options = {'REGISTER', 'UNDO'}
    filename_ext = ".outfit"
    filter_glob: StringProperty(
        default="*.outfit",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    file_format: file_format_prop

    def execute(self, context):
        return read_outfit(self, context, self.filepath, self.file_format)


# --------------------------------------------------------------------------------
# .skin importer
# --------------------------------------------------------------------------------

def read_skin(operator, context, filepath, armature_ob):
    print('Skin:', filepath)
    if not bpy.context.view_layer.objects.active or \
            bpy.context.view_layer.objects.active.type != 'MESH':
        return {'FINISHED'}

    with ProgressReport(context.window_manager) as progReport:
        with ProgressReportSubstep(progReport, 5,
                                   "Importing mesh", "Finish Importing dmesh") as progress:
            if (bpy.context.mode != 'OBJECT'):
                bpy.ops.object.mode_set(mode='OBJECT')

            SIGNATURE_SIZE = 28
            CHUNK_SIZE = 48
            INIT_INFO = 8
            VERT_SIZE = 20
            BONE_SIZE = 112

            print("Importing mesh: %s" % filepath)

            progress.enter_substeps(1, "Read file")
            data = None
            with open(filepath, "rb") as a_file:
                data = a_file.read()
            progress.leave_substeps("Read file end")

            (signature, chunkCount, totalSize) = \
                struct.unpack('20sII', data[0:SIGNATURE_SIZE])
            signature = decodeText(signature)
            print('Signature:', signature)
            if signature != 'HD_CHUNK':
                print("Unrecognized signature: %s" % signature)
                operator.report({'ERROR'}, "Unrecognized file format")
                return {'FINISHED'}

            offset = SIGNATURE_SIZE + (CHUNK_SIZE * chunkCount)
            (vertCount, boneCount) = \
                struct.unpack('II', data[offset:offset + INIT_INFO])

            vert_data = []
            headerSize = SIGNATURE_SIZE + (CHUNK_SIZE * chunkCount) + INIT_INFO
            delta = headerSize
            for n in range(vertCount):
                offset = delta + (VERT_SIZE * n)
                (w1, w2, w3, w4, b1, b2, b3, b4) = \
                    struct.unpack('4f4B', data[offset:offset + VERT_SIZE])

                weights = ((b1, w1), (b2, w2), (b3, w3), (b4, w4))
                vert_data.append(weights)

            bone_data = []

            delta = headerSize + (VERT_SIZE * vertCount)
            for n in range(boneCount):
                offset = delta + (BONE_SIZE * n)
                (name,
                    f1, f2, f3, f4,
                    f5, f6, f7, f8,
                    f9, f10, f11, f12,
                    f13, f14, f15, f16,
                    vx, vy, vz, vw) = \
                    struct.unpack('32s16f4f', data[offset:offset + BONE_SIZE])

                name = decodeText(name)
                name = boneRenameBlender(name)
                mat = Matrix(((f1, f2, f3, f4),
                              (f5, f6, f7, f8),
                              (f9, f10, f11, f12),
                              (f13, f14, f15, f16)))
                vec = Vector((vx, vy, vz, vw))
                bone_data.append({'name': name, 'mat': mat, 'vec': vec})

            mesh_obj = bpy.context.view_layer.objects.active

            for vertIdx, v_data in enumerate(vert_data):
                for boneIdx, vertexWeight in v_data:

                    if (boneIdx != 0 or vertexWeight != 0):
                        boneName = bone_data[boneIdx]['name']
                        vertGroup = mesh_obj.vertex_groups.get(boneName)
                        if not vertGroup:
                            vertGroup = mesh_obj.vertex_groups.new(name=boneName)
                        vertGroup.add([vertIdx], vertexWeight, 'REPLACE')

            if not armature_ob:
                armature_ob = None
                armature_da = bpy.data.armatures.new(ARMATURE_NAME)
                # armature_da.display_type = 'STICK'
                armature_da.show_axes = True
                armature_ob = bpy.data.objects.new(ARMATURE_NAME, armature_da)
                armature_ob.show_in_front = True
                linkToActiveCollection(armature_ob)

            bpy.context.view_layer.objects.active = armature_ob
            bpy.ops.object.mode_set(mode='EDIT')

            # create all Bones
            progress.enter_substeps(boneCount, "create bones")
            # Axis Orientation
            axis_orient = Quaternion((1, 0, 0), -pi / 2).to_matrix().to_4x4()
            # Bone Orientation
            r1 = Quaternion((0, 0, 1), pi / 2).to_matrix().to_4x4()
            r2 = Quaternion((0, 1, 0), -pi / 2).to_matrix().to_4x4()
            bone_orient = r1 @ r2
            for idx, b_data in enumerate(bone_data):
                boneName = b_data['name']
                if not armature_ob.data.edit_bones.get(boneName):
                    mat = b_data['mat']
                    editBone = armature_ob.data.edit_bones.new(boneName)
                    editBone.tail = Vector(editBone.head) + Vector((0, 0, 4))
                    pos = Vector(mat.to_3x3() @ mat.row[3].xyz)
                    mat = mat.to_3x3().to_4x4()
                    mat.translation = pos
                    editBone.matrix = axis_orient @ mat @ bone_orient
                progress.step()

            bpy.ops.object.mode_set(mode='OBJECT')
            progress.leave_substeps("create bones end")

            progress.enter_substeps(1, "parent armature")
            if armature_ob:
                # parent armature
                mesh_obj.parent = armature_ob
                # armature modifier
                mod = mesh_obj.modifiers.new(type="ARMATURE", name="Armature")
                mod.use_vertex_groups = True
                mod.object = armature_ob
            progress.leave_substeps("end parent armature")

    return {'FINISHED'}


class ImportHaydeeSkin(Operator, ImportHelper):
    bl_idname = "haydee_importer.skin"
    bl_label = "Import Haydee Skin (.skin)"
    bl_description = "Import a Haydee Skin (Weigth Information)"
    bl_options = {'REGISTER', 'UNDO'}
    filename_ext = ".skin"
    filter_glob: StringProperty(
        default="*.skin",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    def execute(self, context):
        return read_skin(self, context, self.filepath, None)


# --------------------------------------------------------------------------------
# .material importer
# --------------------------------------------------------------------------------
def read_material(operator, context, filepath):
    print('Material:', filepath)
    if not bpy.context.view_layer.objects.active or \
            bpy.context.view_layer.objects.active.type != 'MESH':
        return {'FINISHED'}

    class MatType(Enum):
        OPAQUE = 0
        MASK = 1
        HAIR = 2

    with open(filepath, "rb") as a_file:
        data = a_file.read()
    mview = memoryview(data)

    with ProgressReport(context.window_manager) as progReport:
        with ProgressReportSubstep(progReport, 4, "Importing outfit", "Finish Importing outfit") as progress:

            propMap = None
            sig = sig_check(mview)

            if (sig == Signature.HD_CHUNK):
                print("Signature: %s" % sig.name)

                unpack_int = struct.Struct('<I').unpack
                unpack_float = struct.Struct('<f').unpack
                unpack_entry = struct.Struct('<32siiii').unpack
                (entries, serialSize, assType) = struct.unpack('<ii8s', mview[20:36])

                if (assType.decode('latin') != 'material'):
                    print("Unrecognized signature or asset type: [%s], %s" % (binascii.hexlify(mview[0:16]), assType))
                    operator.report({'ERROR'}, "Unrecognized file format")
                    return {'FINISHED'}

                propMap = dict(type={       'reader': lambda x: unpack_int(x)[0]},
                               twoSided={   'reader': lambda x: unpack_int(x)[0]},
                               width={      'reader': lambda x: unpack_float(x)[0]},
                               height={     'reader': lambda x: unpack_float(x)[0]},
                               autouv={     'reader': lambda x: unpack_int(x)[0]},
                               diffuseMap={ 'reader': lambda x: readStrW(0, x)[0]},
                               normalMap={  'reader': lambda x: readStrW(0, x)[0]},
                               specularMap={'reader': lambda x: readStrW(0, x)[0]},
                               emissionMap={'reader': lambda x: readStrW(0, x)[0]},
                               censorMap={  'reader': lambda x: readStrW(0, x)[0]},
                               maskMap={    'reader': lambda x: readStrW(0, x)[0]},
                               surface={    'reader': lambda x: readStrA_term(0, 64, x)[0]},
                               speculars={  'reader': lambda x: struct.unpack('<3f', x)})
                dataOffset = 28 + (entries * 48)

                for x in range(1, entries):
                    sPos = 28 + (x * 48)
                    (name, size, offset, numSubs, subs) = unpack_entry(mview[sPos:sPos+48])
                    name = readStrA_term(0, 32, name)[0]
                    propMap[name].update(dict(zip(['size', 'offset', 'numSubs', 'subs', 'hasValue'],[size, offset, numSubs, subs, size > 0])))

                for value in propMap.values():
                    if (value.get("hasValue")):
                        (f, lSize, lOff) = (value['reader'], value['size'], value['offset'])
                        lOff = dataOffset + lOff
                        value["value"] = f(mview[lOff:lOff+lSize])

            elif (sig == Signature.HD_DATA_TXT or sig == Signature.HD_DATA_TXT_BOM):
                encoding = "utf-8-sig" if (sig == Signature.HD_DATA_TXT) else "utf-16-le"
                mview = io.TextIOWrapper(BytesIO(data), encoding=encoding)
                print("Signature: %s" % sig.name)

                propMap = dict( type={'reader':          lambda s: MatType[s]},
                                twoSided={'reader':      lambda s: s.lower() == 'true'},
                                width={'reader':         lambda s: float(s)},
                                height={'reader':        lambda s: float(s)},
                                autouv={'reader':        lambda s: int(s)},
                                diffuseMap = {'reader':  lambda s: s.strip('"')},
                                normalMap = {'reader':   lambda s: s.strip('"')},
                                specularMap = {'reader': lambda s: s.strip('"')},
                                emissionMap = {'reader': lambda s: s.strip('"')},
                                censorMap = {'reader':   lambda s: s.strip('"')},
                                maskMap = {'reader':     lambda s: s.strip('"')},
                                surface = {'reader':     lambda s: s},
                                speculars = {'reader':   lambda s: tuple([float(val) for val in s.split()])})

                line = mview.readline()
                c = 0
                while (line != '{' and c < 50):
                    line = mview.readline().strip()
                    c = c+1
                c = 0
                while (line != '}' and c < 50):
                    c = c+1
                    line = mview.readline().strip().strip(';')
                    if (line == '}'): break
                    key = line[0:line.index(' ')]
                    value = line[line.index(' ')+1:]
                    propMap[key]["value"] = propMap[key]["reader"](value)
            else:
                print("Unrecognized signature or asset type: %s" % (binascii.hexlify(mview[0:16])))
                operator.report({'ERROR'}, "Unrecognized file format")
                return {'FINISHED'}

            # Ready to create material
            obj = bpy.context.view_layer.objects.active
            basedir = os.path.dirname(filepath)
            matName = os.path.basename(filepath)
            matName = os.path.splitext(matName)[0]

            for key, value in propMap.items():
                if ('Map') in key:
                    vMap = value.get("value")
                    if (vMap):
                        value["value"] = material_path(basedir, vMap)

            useAlpha = (propMap.get("type") and propMap["type"]["value"] == 1)
            create_material(obj, useAlpha, matName, propMap['diffuseMap'].get('value'), propMap['normalMap'].get('value'), propMap['specularMap'].get('value'), propMap['emissionMap'].get('value'))

    return {'FINISHED'}

class ImportHaydeeMaterial(Operator, ImportHelper):
    bl_idname = "haydee_importer.material"
    bl_label = "Import Haydee Material (.mtl)"
    bl_description = "Import a Haydee Material to active Object"
    bl_options = {'REGISTER', 'UNDO'}
    filename_ext = ".mtl"
    filter_glob: StringProperty(
        default="*.mtl",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    def execute(self, context):
        return read_material(self, context, self.filepath)


def haydeeFilepath(mainpath, filepath):
    path = filepath
    if not os.path.isabs(filepath):
        # Current Folder
        currPath = os.path.relpath(filepath, r'outfits')
        basedir = os.path.dirname(mainpath)
        path = os.path.join(basedir, currPath)
        if not (os.path.isfile(path)):
            # Outfit Folder
            path = filepath
            idx = basedir.lower().find(r'\outfit')
            path = basedir[:idx]
            path = os.path.join(path, filepath)
    return path

def material_path(mainpath, filepath):
    path = filepath
    if not os.path.isabs(filepath):
        if (filepath.rfind('\\') < 0):
            # Current Folder
            path = os.path.join(mainpath, filepath)
        else:
            newMain = None
            oldMain = mainpath
            c = 0
            while (True and c < 50):
                newMain = os.path.split(oldMain)[0]
                newFull = os.path.join(newMain, filepath)
                if (os.path.isfile(newFull) or newMain == oldMain):
                    path = newFull
                    break
                oldMain = newMain
                c = c + 1
    return path


# --------------------------------------------------------------------------------
# Initialization & menu
# --------------------------------------------------------------------------------
class HaydeeImportSubMenu(bpy.types.Menu):
    bl_idname = "OBJECT_MT_haydee_import_submenu"
    bl_label = "Haydee"

    def draw(self, context):
        layout = self.layout
        layout.operator(ImportHaydeeMesh.bl_idname, text="Haydee Mesh (.mesh)")
        layout.operator(ImportHaydeeDMesh.bl_idname, text="Haydee DMesh (.dmesh)")
        layout.operator(ImportHaydeeSkel.bl_idname, text="Haydee Skel (.skel)")
        layout.operator(ImportHaydeeDSkel.bl_idname, text="Haydee DSkel (.dskel)")
        layout.operator(ImportHaydeeSkin.bl_idname, text="Haydee Skin (.skin)")
        layout.operator(ImportHaydeeMaterial.bl_idname, text="Haydee Material(.mtl)")
        layout.operator(ImportHaydeeMotion.bl_idname, text="Haydee Motion (.motion)")
        layout.operator(ImportHaydeeDMotion.bl_idname, text="Haydee DMotion (.dmot)")
        layout.operator(ImportHaydeePose.bl_idname, text="Haydee Pose (.pose)")
        layout.operator(ImportHaydeeDPose.bl_idname, text="Haydee DPose (.dpose)")
        layout.operator(ImportHaydeeOutfit.bl_idname, text="Haydee Outfit (.outfit)")


def menu_func_import(self, context):
    my_icon = HaydeeMenuIcon.custom_icons["main"]["haydee_icon"]
    self.layout.menu(HaydeeImportSubMenu.bl_idname, icon_value=my_icon.icon_id)


# --------------------------------------------------------------------------------
# Register
# --------------------------------------------------------------------------------
def register():
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)


if __name__ == "__main__":
    register()

    # test call
    # bpy.ops.haydee_importer.motion('INVOKE_DEFAULT')

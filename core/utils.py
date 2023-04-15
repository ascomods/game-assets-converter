import os, stat
import shutil
import inspect
import core.common as cm
import numpy

endian = 'big'

# bytes to int
def b2i(num):
    return int.from_bytes(num, byteorder=endian)

# int to bytes
def i2b(num, length = 4):
    return num.to_bytes(length, byteorder=endian)

# extend bytes to given size
def extb(bytes, size):
    return bytes + (b'\0' * (size - len(bytes)))

# hex int to byte
def h2b(num):
    return b"0x%0.2X" % num

def search_index_dict(dict, search_val):
    for key, val in dict.items():
        if val == search_val:
            return key
    if len(search_val) > 0:
        print(search_val)
    raise Exception("Key not found in dict")

# Search value in list values of dict
def search_index_dict_list(dict, search_val):
    for key, search_list in dict.items():
        if (isinstance(search_list, list) and (search_val in search_list)):
            return key

def keep_cursor_pos(function):
    """
    restores cursor position after function execution
    """
    def wrapper(*args, **kwargs):
        res = b''
        args_name = list(inspect.signature(function).parameters.keys())
        if all(x in args_name for x in ['stream']):
            stream_arg_index = args_name.index('stream')
            stream = args[stream_arg_index]
            previous_pos = stream.tell()
            if 'start_offset' in args_name:
                start_offset_arg_index = args_name.index('start_offset')
                start_offset = args[start_offset_arg_index]
                stream.seek(start_offset)            
            res = function(*args, **kwargs)
            stream.seek(previous_pos)
        else:
            raise Exception("Error with given arguments")
        return res
    return wrapper

@keep_cursor_pos
def read_string_inplace(stream, start_offset, max_size = 100):
    return read_string(stream, start_offset, max_size)

def read_string(input, start_offset, max_size):
    """
    reads characters until it finds 00
    """
    byte = input.read(1)
    size = 1
    content = b''
    while (size <= max_size) and byte and byte != b'\x00':
        content += byte
        byte = input.read(1)
        size += 1
    return content

def uniquify(path):
    name, ext = os.path.splitext(path)
    count = 0

    while os.path.exists(path):
        path = f'{name}_{count}{ext}'
        count += 1

    return path

def add_padding(num, length = 16):
    if num % length != 0:
        num += length - (num % length)
    return num

# bytes to string name
def b2s_name(bytes):
    return bytes.decode('latin1')

# string to bytes name
def s2b_name(string):
    return string.encode('latin1')

def format_jap_name(string):
    try:
        string.decode('utf-8')
    except:
        name_parts = string.rsplit(b'_')[1:]
        string = b'_'.join(name_parts)
    return string

def read_until(stream, offset, endChar = b'\x00'):
    initial_pos = stream.tell()
    stream.seek(offset)
    res = bytearray(stream.read(1))
    current_byte = b''
    while current_byte != endChar:
        res += current_byte
        current_byte = stream.read(1)
    stream.seek(initial_pos)
    return bytes(res)

def init_temp_dir():
    if not os.path.exists(cm.temp_path):
        os.mkdir(cm.temp_path)

def copy_to_temp_dir(path):
    init_temp_dir()
    name, ext = os.path.splitext(os.path.basename(path))
    shutil.copy2(path, cm.temp_path)
    return f"{cm.temp_path}/{name}{ext}"

def empty_temp_dir():
    path = os.path.abspath(cm.temp_path)
    if os.path.exists(path):
        shutil.rmtree(path, onerror = on_rm_error)

def on_rm_error(func, path, exc_info):
    os.chmod( path, stat.S_IWRITE )
    os.unlink( path )

def print_hex(data):
    print(''.join(r' '+hex(letter)[2:] for letter in data))


def matrix3x3Default():
    return [ [1, 0, 0], [0, 1, 0], [0, 0, 1]]
def matrix4x4Default():
    return [ [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1] ]


def crossProd_Vect3(vectA, vectB):
    return {"x": (vectA["y"] * vectB["z"] - vectA["z"] * vectB["y"]), \
            "y": (vectA["z"] * vectB["x"] - vectA["x"] * vectB["z"]), \
            "z": (vectA["x"] * vectB["y"] - vectA["y"] * vectB["x"]) }

def addVect3(vA, vB):
    return [ vA[0] + vB[0], vA[1] + vB[1], vA[2] + vB[2] ]

def crossProd_Vect4(vectA, vectB):
    ret = crossProd_Vect3(vectA, vectB)
    ret["w"] = 1.0
    return ret

def multiply_Vect3_float(v, f):
    return [ v[0] * f, v[1] * f, v[2] * f]




def transpose_Mat4(m):
    return [ [ m[0][0], m[1][0], m[2][0], m[3][0] ], [ m[0][1], m[1][1], m[2][1], m[3][1] ], [ m[0][2], m[1][2], m[2][2], m[3][2] ], [ m[0][3], m[1][3], m[2][3], m[3][3] ]  ]
def transpose_Mat3(m):
    return [ [ m[0][0], m[1][0], m[2][0] ], [ m[0][1], m[1][1], m[2][1] ], [ m[0][2], m[1][2], m[2][2] ] ]

def getPositionFromMat4(m):              #hyp matrix have position on bottom line
    return [ m[3][0], m[3][1], m[3][2], m[3][3] ]

def multiply_Mat3_Vect3(m, v):                #Notice the matrix are as same as xenoverse : for a matrix4x4, position is the under line
    return [ v[0] * m[0][0] + v[1] * m[0][1] + v[2] * m[0][2],\
             v[0] * m[1][0] + v[1] * m[1][1] + v[2] * m[1][2],\
             v[0] * m[2][0] + v[1] * m[2][1] + v[2] * m[2][2] ]

def multiply_Mat4_Vect3(m, v):                                              # position shoudl be in [m[0][3], m[1][3] , m[2][3], m[3][3] ] else transpose
    return [ v[0] * m[0][0] + v[1] * m[0][1] + v[2] * m[0][2] + m[0][3],\
             v[0] * m[1][0] + v[1] * m[1][1] + v[2] * m[1][2] + m[1][3],\
             v[0] * m[2][0] + v[1] * m[2][1] + v[2] * m[2][2] + m[2][3] ]   # simulation of w = 1.0

def makeMatrix4x4FromTransform(position, orient, scale):	    # orient is a quaternion informations
    # Ordering:
    #    1. Scale
    #    2. Rotate
    #    3. Translate

    # position posOrientScale[0], posOrientScale[1], posOrientScale[2], posOrientScale[3]
    # orient  posOrientScale[4], posOrientScale[5], posOrientScale[6], posOrientScale[7]
    # scale  posOrientScale[8], posOrientScale[9], posOrientScale[10], posOrientScale[11]

    rot3x3 = self.matrix3x3Default()
    #orientation.ToRotationMatrix(rot3x3);
    fTx = orient[0] + orient[0]		# x + x
    fTy = orient[1] + orient[1]		# y + y
    fTz = orient[2] + orient[2]		# z + z
    fTwx = fTx * orient[3]		# * w
    fTwy = fTy * orient[3]
    fTwz = fTz * orient[3]
    fTxx = fTx * orient[0]		# * x
    fTxy = fTy * orient[0]
    fTxz = fTz * orient[0]
    fTyy = fTy * orient[1]		# * y
    fTyz = fTz * orient[1]
    fTzz = fTz * orient[2]		# * z
    rot3x3_00 = 1.0 - (fTyy + fTzz)
    rot3x3_01 = fTxy - fTwz
    rot3x3_02 = fTxz + fTwy
    rot3x3_10 = fTxy + fTwz
    rot3x3_11 = 1.0 - (fTxx + fTzz)
    rot3x3_12 = fTyz - fTwx
    rot3x3_20 = fTxz - fTwy
    rot3x3_21 = fTyz + fTwx
    rot3x3_22 = 1.0 - (fTxx + fTyy)



    # Set up final matrix with scale, rotation and translation
    result_mat4x4 = self.matrix4x4Default()
    result_mat4x4[0][0] = scale[0] * rot3x3_00	#m00 = scale.x * 
    result_mat4x4[0][1] = scale[1] * rot3x3_01	#m01 = scale.y *
    result_mat4x4[0][2] = scale[2] * rot3x3_02	#m02 = scale.z * 
    result_mat4x4[0][3] = position[0]					#m03 = pos.x

    result_mat4x4[1][0] = scale[0] * rot3x3_10
    result_mat4x4[1][1] = scale[1] * rot3x3_11
    result_mat4x4[1][2] = scale[2] * rot3x3_12
    result_mat4x4[1][3] = position[1]					#m13 = pos.y

    result_mat4x4[2][0] = scale[0] * rot3x3_20
    result_mat4x4[2][1] = scale[1] * rot3x3_21
    result_mat4x4[2][2] = scale[2] * rot3x3_22
    result_mat4x4[2][3] = position[2]				#m23 = pos.z

    # No projection term
    result_mat4x4[3][0] = 0
    result_mat4x4[3][1] = 0
    result_mat4x4[3][2] = 0
    result_mat4x4[3][3] = position[3]				#m33 = pos.w

    return result_mat4x4


def makeTranformOrientationFromTransformRotation(rot):	 # 3 rotations, in degrees

    #need to convert Euler Angles to Quaternion
    axisX = [1, 0, 0]
    axisY = [0, 1, 0]
    axisZ = [0, 0, 1]

    quatX = ut.fromAngleAxis(rot[0], axisX)
    quatY = ut.fromAngleAxis(rot[1], axisY)
    quatZ = ut.fromAngleAxis(rot[2], axisZ)

    quat = ut.quatMulQuat(quatZ, ut.quatMulQuat(quatY, quatX)); #XYZ		=> not like the XYZ order in ean, strange. (but it's the only order solution, others give weird)
    return quat             #orientation (quaternion)

def makeTranformRotationFromTransformOrientation(quat):	 # orientation == Quaternion

    #need to convert Quaternion to Euler Angles (in real, is TaitBryan angles)
    angles = ut.giveAngleOrientationForThisOrientationTaitBryan_XYZ(quat);		# yaws, pitch, roll
    rot = []
    rot[0] = angles[2];					#roll						//rotation for X axis	(Xenoverse data is on XYZ order.)
    rot[1] = angles[1];					#yaw on disc from pitch.	//for Y axis
    rot[2] = angles[0];					#pitch						//for Z axis
    return rot

    # todo giveAngleOrientationForThisOrientationTaitBryan_XYZ, quatMulQuat, fromAngleAxis




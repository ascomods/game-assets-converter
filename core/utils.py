import os, stat
import shutil
import inspect
import core.common as cm
import numpy
import numpy as np
import math

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


def getSettingsOrAddDefault(settings, name, defaultValue):
    ret = settings.value(name)
    if(ret == None):
        ret = defaultValue
        settings.setValue(name, ret)
    return ret








####################################################################
#                           Vector3                                #
####################################################################

def lengthVect3(v):
    return math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])

def normalizeVect3(v):
    length = lengthVect3(v)
    ret = []
    ret.append( (v[0] / length) if(length > 0.000001) else 0 )
    ret.append( (v[1] / length) if(length > 0.000001) else 0 )
    ret.append( (v[2] / length) if(length > 0.000001) else 0 )
    return ret

def addVect3(vA, vB):
    return [ vA[0] + vB[0], vA[1] + vB[1], vA[2] + vB[2] ]

def multiply_Vect3_float(v, f):
    return [ v[0] * f, v[1] * f, v[2] * f]

def crossProd_Vect3(vectA, vectB):
    return [vectA[1] * vectB[2] - vectA[2] * vectB[1], \
            vectA[2] * vectB[0] - vectA[0] * vectB[2], \
            vectA[0] * vectB[1] - vectA[1] * vectB[0] ]

def display_Vect3(v):
    print("["+ str(v[0]) +",\t"+ str(v[1]) +",\t"+ str(v[2]) +"]\n")

####################################################################
#                           Vector4                                #
####################################################################

def crossProd_Vect4(vectA, vectB):
    ret = crossProd_Vect3(vectA, vectB)
    ret.append( 1.0 )                   # w
    return ret

####################################################################
#                           Quaternion                             #
####################################################################



def quatMulVec3(quat, v):						#from Ogre Vector3 Quaternion::operator* (const Vector3& v) const
    # nVidia SDK implementation
    uv = crossProd_Vect3(quat, v)					# only take the quat.xyz
    uuv = crossProd_Vect3(quat, uv)				    # only take the quat.xyz
    uv[0] = uv[0] * (2.0 * quat[3])
    uv[1] = uv[1] * (2.0 * quat[3])
    uv[2] = uv[2] * (2.0 * quat[3])
    uuv[0] = uuv[0] * 2.0
    uuv[1] = uuv[1] * 2.0
    uuv[2] = uuv[2] * 2.0

    ret = []
    ret.append(v[0] + uv[0] + uuv[0])
    ret.append(v[1] + uv[1] + uuv[1])
    ret.append(v[2] + uv[2] + uuv[2])
    return ret

def quatMulQuat(quat, rkQ):		# from Ogre Quaternion Quaternion::operator* (const Quaternion& rkQ) const
    # NOTE :  Multiplication is not generally commutative, so in most cases p*q != q*p.

    ret = []
    ret.append(quat[3] * rkQ[0] + quat[0] * rkQ[3] + quat[1] * rkQ[2] - quat[2] * rkQ[1])
    ret.append(quat[3] * rkQ[1] + quat[1] * rkQ[3] + quat[2] * rkQ[0] - quat[0] * rkQ[2])
    ret.append(quat[3] * rkQ[2] + quat[2] * rkQ[3] + quat[0] * rkQ[1] - quat[1] * rkQ[0])
    ret.append(quat[3] * rkQ[3] - quat[0] * rkQ[0] - quat[1] * rkQ[1] - quat[2] * rkQ[2])
    return ret



def fromAngleAxis(rfAngle, rkAxis):			#Rotation around a axe. angle in degrees. //from Ogre Quaternion::FromAngleAxis 

	# assert:  axis[] is unit length
	#
	# The quaternion representing the rotation is
	#   q = cos(A/2)+sin(A/2)*(x*i+y*j+z*k)

	fHalfAngle = np.deg2rad(0.5 * rfAngle)
	fSin = math.sin( fHalfAngle )
	ret = []
	ret.append( fSin * rkAxis[0] )
	ret.append( fSin * rkAxis[1] )
	ret.append( fSin * rkAxis[2] )
	ret.append( math.cos(fHalfAngle) )
	return ret


def giveAngleOrientationForThisOrientationTaitBryan(orient):     #orient is a quaternion
    q[0, 0, 0]
    axisX = [1, 0, 0]
    axisY = [0, 1, 0]
    axisZ = [0, 0, 1]

    dir = quatMulVec3(orient, axisX)

    #1) calcul yaw
    vectproj = [ dir[0], -dir[2] ]			#projection of the result on (O,x,-z) plane
    if (lengthVect3(vectproj) > 0.000001):			#if undefined => by defaut 0
        vectproj = normalizeVect3(vectproj)

        q[0] = np.rad2deg( math.acos(vectproj[0]) )
        if (vectproj[1] < 0):
            q[0] = -q[0]


    #2) calcul pitch
    rotationInv_Yrot = fromAngleAxis(-q[0], axisY)
    dir_tmp = quatMulVec3(quatMulQuat(rotationInv_Yrot, orient), axisX)		#we cancel yaw rotation, the point must be into (O,x,y) plane

    #just in case (ex Xenoverse2's Tapion (TPO) sword)
    tmp = math.sqrt(dir_tmp[0] * dir_tmp[0] + dir_tmp[1] * dir_tmp[1] + dir_tmp[2] * dir_tmp[2])
    dir_tmp[0] /= tmp
    dir_tmp[1] /= tmp
    dir_tmp[2] /= tmp

    q[1] = np.rad2deg( math.acos(dir_tmp[0]) )
    if (dir_tmp[1] < 0):
        q[1] = -q[1]




    #3) calcul roll
    rotationInv_Zrot = fromAngleAxis(-q[1], axisZ)
    dir_tmp = quatMulVec3(quatMulQuat(rotationInv_Zrot, quatMulQuat(rotationInv_Yrot, orient)), axisZ)		#we cancel the yaw and pitch rotations, the point Vector3::UNIT_Y, after rotation, must be into (O,x,z) plane.

    #just in case (ex xenoverse2's Tapion (TPO) sword)
    tmp = math.sqrt(dir_tmp[0] * dir_tmp[0] + dir_tmp[1] * dir_tmp[1] + dir_tmp[2] * dir_tmp[2])
    dir_tmp[0] /= tmp
    dir_tmp[1] /= tmp
    dir_tmp[2] /= tmp

    q[2] = np.rad2deg( math.acos(dir_tmp[2]) )
    if (dir_tmp[1] > 0):		# the direct direction is from Oy to Oz
        q[2] = -q[2]

    return q

def giveAngleOrientationForThisOrientationTaitBryan_XYZ(orient):				#same version, but with this order of rotation, the yaw is on the diqs display by pitch rotation.

    #convert into a matrix3x3
    mat3 = quadToRotationMatrix3x3(orient)

    #convert matrix3x3 into EulerAngle
    q = matrix3x3ToEulerAnglesZYX(mat3)
    return q



def quadToRotationMatrix3x3(orient):
    m_ret = matrix3x3Default()
    
    #normalize quaternion as in https://www.andre-gaschler.com/rotationconverter/ , else we could have infinite + weird result on matrixToEulerAnglesZYX, because of float precision on quaternion.
    a = math.sqrt(orient[0] * orient[0] + orient[1] * orient[1] + orient[2] * orient[2] + orient[3] * orient[3])
    if (0 == a):
        orient[0] = orient[1] = orient[2] = 0
        orient[3] = 1
    else:
        a = 1.0 / a
        orient[0] *= a
        orient[1] *= a
        orient[2] *= a
        orient[3] *= a

    fTx = orient[0] + orient[0]
    fTy = orient[1] + orient[1]
    fTz = orient[2] + orient[2]
    fTwx = fTx * orient[3]
    fTwy = fTy * orient[3]
    fTwz = fTz * orient[3]
    fTxx = fTx * orient[0]
    fTxy = fTy * orient[0]
    fTxz = fTz * orient[0]
    fTyy = fTy * orient[1]
    fTyz = fTz * orient[1]
    fTzz = fTz * orient[2]

    m_ret[0][0] = 1.0 - (fTyy + fTzz)
    m_ret[0][1] = fTxy - fTwz
    m_ret[0][2] = fTxz + fTwy
    m_ret[1][0] = fTxy + fTwz
    m_ret[1][1] = 1.0 - (fTxx + fTzz)
    m_ret[1][2] = fTyz - fTwx
    m_ret[2][0] = fTxz - fTwy
    m_ret[2][1] = fTyz + fTwx
    m_ret[2][2] = 1.0 - (fTxx + fTyy)

    return m_ret

def matrix3x3ToEulerAnglesZYX(m):
    
    YPR_angles = [0, 0, 0]
    
    # rot =  cy*cz           cz*sx*sy-cx*sz  cx*cz*sy+sx*sz
    #        cy*sz           cx*cz+sx*sy*sz -cz*sx+cx*sy*sz
    #       -sy              cy*sx           cx*cy

    for i in range(3):		#few corrections, due to the float precision on quaternion.
        if ((m[0][i] < -1) and (abs(m[0][i] - (-1)) < 0.000001)):
            m[0][i] = -1
        if ((m[0][i] > 1)  and (abs(m[0][i] - 1) < 0.000001)):
            m[0][i] = 1

        if ((m[1][i] < -1) and (abs(m[1][i] - (-1)) < 0.000001)):
            m[1][i] = -1
        if ((m[1][i] > 1)  and (abs(m[1][i] - 1) < 0.000001)):
            m[1][i] = 1

        if ((m[2][i] < -1) and (abs(m[2][i] - (-1)) < 0.000001)):
            m[2][i] = -1
        if ((m[2][i] > 1)  and (abs(m[2][i] - 1) < 0.000001)):
            m[2][i] = 1



    YPR_angles[1] = np.rad2deg( math.asin(-m[2][0]) )
    if (YPR_angles[1] < 90.0):

        if (YPR_angles[1] > -90.0):
            YPR_angles[0] = np.rad2deg( math.atan2(m[1][0], m[0][0]) )
            YPR_angles[2] = np.rad2deg( math.atan2(m[2][1], m[2][2]) )
            return YPR_angles                   # old return true

        else:
            # WARNING. "Gimbal Lock" => Not a unique solution. (not usaeble for animation witch get interpolation !!!)
            fRmY = np.rad2deg( math.atan2(-m[0][1], m[0][2]) )
            YPR_angles[2] = 0.0  # any angle works
            #YPR_angles[0] = YPR_angles[2] - fRmY
            YPR_angles[0] = fRmY - YPR_angles[2]
            return YPR_angles                   # old return false

    else:
        # WARNING. "Gimbal Lock" =>  Not a unique solution (not usaeble for animation witch get interpolation !!!)
        fRpY = np.rad2deg(math.atan2(-m[0][1], m[0][2]) )
        YPR_angles[2] = 0.0  # any angle works
        YPR_angles[0] = fRpY - YPR_angles[2]
        return YPR_angles                       # old return false
    





####################################################################
#                           Transform                              #
####################################################################


# in this case "transform" = position (vect4), rotation(Euler's Angles)/orientation (quaternion), scale (vect4)
def transformOrientationDefault():
    return [ [0, 0, 0, 1], [0, 0, 0, 1], [1, 1, 1, 1]]
def transformRotationDefault():
    return [ [0, 0, 0, 1], [0, 0, 0, 0], [1, 1, 1, 1]]


####################################################################
#                           Matrix3x3                              #
####################################################################

def matrix3x3Default():
    return [ [1, 0, 0], [0, 1, 0], [0, 0, 1]]

def clone_matrix3x3(mat_src):
    return [ [mat_src[0][0], mat_src[0][1], mat_src[0][2]], [mat_src[1][0], mat_src[1][1], mat_src[1][2]], [mat_src[2][0], mat_src[2][1], mat_src[2][2]]]

def transpose_Mat3(m):
    return [ [ m[0][0], m[1][0], m[2][0] ], [ m[0][1], m[1][1], m[2][1] ], [ m[0][2], m[1][2], m[2][2] ] ]

def display_matrix3x3(mat_src):
    str_tmp =  "["+ str(mat_src[0][0]) +",\t"+ str(mat_src[0][1]) +",\t"+ str(mat_src[0][2]) +"]\n"
    str_tmp += "["+ str(mat_src[1][0]) +",\t"+ str(mat_src[1][1]) +",\t"+ str(mat_src[1][2]) +"]\n"
    str_tmp += "["+ str(mat_src[2][0]) +",\t"+ str(mat_src[2][1]) +",\t"+ str(mat_src[2][2]) +"]\n"
    print(str_tmp)


def multiply_Mat3_Vect3(m, v):                #Notice the matrix are as same as xenoverse : for a matrix4x4, position is the under line
    return [ v[0] * m[0][0] + v[1] * m[0][1] + v[2] * m[0][2],\
             v[0] * m[1][0] + v[1] * m[1][1] + v[2] * m[1][2],\
             v[0] * m[2][0] + v[1] * m[2][1] + v[2] * m[2][2] ]



####################################################################
#                           Matrix4x4                              #
####################################################################

def matrix4x4Default():
    return [ [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1] ]

def clone_matrix3x3(mat_src):
    return [ [mat_src[0][0], mat_src[0][1], mat_src[0][2], mat_src[0][3]], [mat_src[1][0], mat_src[1][1], mat_src[1][2], mat_src[1][3]], [mat_src[2][0], mat_src[2][1], mat_src[2][2], mat_src[2][3]]]

def transpose_Mat4(m):
    return [ [ m[0][0], m[1][0], m[2][0], m[3][0] ], [ m[0][1], m[1][1], m[2][1], m[3][1] ], [ m[0][2], m[1][2], m[2][2], m[3][2] ], [ m[0][3], m[1][3], m[2][3], m[3][3] ]  ]

def display_matrix4x4(mat_src):
    str_tmp =  "["+ str(mat_src[0][0]) +",\t"+ str(mat_src[0][1]) +",\t"+ str(mat_src[0][2]) +",\t"+ str(mat_src[0][3]) +"]\n"
    str_tmp += "["+ str(mat_src[1][0]) +",\t"+ str(mat_src[1][1]) +",\t"+ str(mat_src[1][2]) +",\t"+ str(mat_src[1][3]) +"]\n"
    str_tmp += "["+ str(mat_src[2][0]) +",\t"+ str(mat_src[2][1]) +",\t"+ str(mat_src[2][2]) +",\t"+ str(mat_src[2][3]) +"]\n"
    str_tmp += "["+ str(mat_src[3][0]) +",\t"+ str(mat_src[3][1]) +",\t"+ str(mat_src[3][2]) +",\t"+ str(mat_src[3][3]) +"]\n"
    print(str_tmp)



def inverse_Mat4(m): 
    m_ret = matrix4x4Default()

    #from Ogre Matrix4x4
    v0 = m[2][0] * m[3][1] - m[2][1] * m[3][0]
    v1 = m[2][0] * m[3][2] - m[2][2] * m[3][0]
    v2 = m[2][0] * m[3][3] - m[2][3] * m[3][0]
    v3 = m[2][1] * m[3][2] - m[2][2] * m[3][1]
    v4 = m[2][1] * m[3][3] - m[2][3] * m[3][1]
    v5 = m[2][2] * m[3][3] - m[2][3] * m[3][2]

    t00 = +(v5 * m[1][1] - v4 * m[1][2] + v3 * m[1][3])
    t10 = -(v5 * m[1][0] - v2 * m[1][2] + v1 * m[1][3])
    t20 = +(v4 * m[1][0] - v2 * m[1][1] + v0 * m[1][3])
    t30 = -(v3 * m[1][0] - v1 * m[1][1] + v0 * m[1][2])

    invDet = 1 / (t00 * m[0][0] + t10 * m[0][1] + t20 * m[0][2] + t30 * m[0][3])

    m_ret[0][0] = t00 * invDet
    m_ret[1][0] = t10 * invDet
    m_ret[2][0] = t20 * invDet
    m_ret[3][0] = t30 * invDet

    m_ret[0][1] = -(v5 * m[0][1] - v4 * m[0][2] + v3 * m[0][3]) * invDet
    m_ret[1][1] = +(v5 * m[0][0] - v2 * m[0][2] + v1 * m[0][3]) * invDet
    m_ret[2][1] = -(v4 * m[0][0] - v2 * m[0][1] + v0 * m[0][3]) * invDet
    m_ret[3][1] = +(v3 * m[0][0] - v1 * m[0][1] + v0 * m[0][2]) * invDet

    v0 = m[1][0] * m[3][1] - m[1][1] * m[3][0]
    v1 = m[1][0] * m[3][2] - m[1][2] * m[3][0]
    v2 = m[1][0] * m[3][3] - m[1][3] * m[3][0]
    v3 = m[1][1] * m[3][2] - m[1][2] * m[3][1]
    v4 = m[1][1] * m[3][3] - m[1][3] * m[3][1]
    v5 = m[1][2] * m[3][3] - m[1][3] * m[3][2]

    m_ret[0][2] = +(v5 * m[0][1] - v4 * m[0][2] + v3 * m[0][3]) * invDet
    m_ret[1][2] = -(v5 * m[0][0] - v2 * m[0][2] + v1 * m[0][3]) * invDet
    m_ret[2][2] = +(v4 * m[0][0] - v2 * m[0][1] + v0 * m[0][3]) * invDet
    m_ret[3][2] = -(v3 * m[0][0] - v1 * m[0][1] + v0 * m[0][2]) * invDet

    v0 = m[2][1] * m[1][0] - m[2][0] * m[1][1]
    v1 = m[2][2] * m[1][0] - m[2][0] * m[1][2]
    v2 = m[2][3] * m[1][0] - m[2][0] * m[1][3]
    v3 = m[2][2] * m[1][1] - m[2][1] * m[1][2]
    v4 = m[2][3] * m[1][1] - m[2][1] * m[1][3]
    v5 = m[2][3] * m[1][2] - m[2][2] * m[1][3]

    m_ret[0][3] = -(v5 * m[0][1] - v4 * m[0][2] + v3 * m[0][3]) * invDet
    m_ret[1][3] = +(v5 * m[0][0] - v2 * m[0][2] + v1 * m[0][3]) * invDet
    m_ret[2][3] = -(v4 * m[0][0] - v2 * m[0][1] + v0 * m[0][3]) * invDet
    m_ret[3][3] = +(v3 * m[0][0] - v1 * m[0][1] + v0 * m[0][2]) * invDet

    return m_ret


def concatenat_Mat4(m, mb):
    m_ret = matrix4x4Default()

    m_ret[0][0] = m[0][0] * mb[0][0] + m[0][1] * mb[1][0] + m[0][2] * mb[2][0] + m[0][3] * mb[3][0]
    m_ret[0][1] = m[0][0] * mb[0][1] + m[0][1] * mb[1][1] + m[0][2] * mb[2][1] + m[0][3] * mb[3][1]
    m_ret[0][2] = m[0][0] * mb[0][2] + m[0][1] * mb[1][2] + m[0][2] * mb[2][2] + m[0][3] * mb[3][2]
    m_ret[0][3] = m[0][0] * mb[0][3] + m[0][1] * mb[1][3] + m[0][2] * mb[2][3] + m[0][3] * mb[3][3]

    m_ret[1][0] = m[1][0] * mb[0][0] + m[1][1] * mb[1][0] + m[1][2] * mb[2][0] + m[1][3] * mb[3][0]
    m_ret[1][1] = m[1][0] * mb[0][1] + m[1][1] * mb[1][1] + m[1][2] * mb[2][1] + m[1][3] * mb[3][1]
    m_ret[1][2] = m[1][0] * mb[0][2] + m[1][1] * mb[1][2] + m[1][2] * mb[2][2] + m[1][3] * mb[3][2]
    m_ret[1][3] = m[1][0] * mb[0][3] + m[1][1] * mb[1][3] + m[1][2] * mb[2][3] + m[1][3] * mb[3][3]

    m_ret[2][0] = m[2][0] * mb[0][0] + m[2][1] * mb[1][0] + m[2][2] * mb[2][0] + m[2][3] * mb[3][0]
    m_ret[2][1] = m[2][0] * mb[0][1] + m[2][1] * mb[1][1] + m[2][2] * mb[2][1] + m[2][3] * mb[3][1]
    m_ret[2][2] = m[2][0] * mb[0][2] + m[2][1] * mb[1][2] + m[2][2] * mb[2][2] + m[2][3] * mb[3][2]
    m_ret[2][3] = m[2][0] * mb[0][3] + m[2][1] * mb[1][3] + m[2][2] * mb[2][3] + m[2][3] * mb[3][3]

    m_ret[3][0] = m[3][0] * mb[0][0] + m[3][1] * mb[1][0] + m[3][2] * mb[2][0] + m[3][3] * mb[3][0]
    m_ret[3][1] = m[3][0] * mb[0][1] + m[3][1] * mb[1][1] + m[3][2] * mb[2][1] + m[3][3] * mb[3][1]
    m_ret[3][2] = m[3][0] * mb[0][2] + m[3][1] * mb[1][2] + m[3][2] * mb[2][2] + m[3][3] * mb[3][2]
    m_ret[3][3] = m[3][0] * mb[0][3] + m[3][1] * mb[1][3] + m[3][2] * mb[2][3] + m[3][3] * mb[3][3]

    return m_ret



def getPositionFromMat4(m):              #hyp matrix have position on bottom line
    return [ m[3][0], m[3][1], m[3][2], m[3][3] ]


def multiply_Mat4_Vect3(m, v):                                              # position shoudl be in [m[0][3], m[1][3] , m[2][3], m[3][3] ] else transpose
    return [ v[0] * m[0][0] + v[1] * m[0][1] + v[2] * m[0][2] + m[0][3],\
             v[0] * m[1][0] + v[1] * m[1][1] + v[2] * m[1][2] + m[1][3],\
             v[0] * m[2][0] + v[1] * m[2][1] + v[2] * m[2][2] + m[2][3] ]   # simulation of w = 1.0


def makeMatrix4x4FromTransform(t):	    #  pos and scale (vect4), orient is a quaternion informations
    # Ordering:
    #    1. Scale
    #    2. Rotate
    #    3. Translate

    position = t[0]
    orient = t[1]
    scale = t[2]

    # position posOrientScale[0], posOrientScale[1], posOrientScale[2], posOrientScale[3]
    # orient  posOrientScale[4], posOrientScale[5], posOrientScale[6], posOrientScale[7]
    # scale  posOrientScale[8], posOrientScale[9], posOrientScale[10], posOrientScale[11]

    rot3x3 = matrix3x3Default()
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
    result_mat4x4 = matrix4x4Default()
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



def makeTransformFromMatrix4x4(m):	    # return pos and scale (vect4), orient is a quaternion informations

    if (not ((abs(m[3][0]) <= 0.000001) and (abs(m[3][1]) <= 0.000001) and (abs(m[3][2]) <= 0.000001) and (abs(m[3][3] - 1) <= 0.000001))):		# == assert(isAffine())
        return None

    result_posOrientScale = transformOrientationDefault()

    #position
    result_posOrientScale[0] = [m[0][3], m[1][3], m[2][3], m[3][3]]     # on the right of the mat4x4



    #Matrix3 matQ
    #Vector3 vecU
    #m3x3.QDUDecomposition(matQ, scale, vecU);



    # Factor M = QR = QDU where Q is orthogonal, D is diagonal,
    # and U is upper triangular with ones on its diagonal.  Algorithm uses
    # Gram-Schmidt orthogonalization (the QR algorithm).
    #
    # If M = [ m0 | m1 | m2 ] and Q = [ q0 | q1 | q2 ], then
    #
    #   q0 = m0/|m0|
    #   q1 = (m1-(q0*m1)q0)/|m1-(q0*m1)q0|
    #   q2 = (m2-(q0*m2)q0-(q1*m2)q1)/|m2-(q0*m2)q0-(q1*m2)q1|
    #
    # where |V| indicates length of vector V and A*B indicates dot
    # product of vectors A and B.  The matrix R has entries
    #
    #   r00 = q0*m0  r01 = q0*m1  r02 = q0*m2
    #   r10 = 0      r11 = q1*m1  r12 = q1*m2
    #   r20 = 0      r21 = 0      r22 = q2*m2
    #
    # so D = diag(r00,r11,r22) and U has entries u01 = r01/r00,
    # u02 = r02/r00, and u12 = r12/r11.

    # Q = rotation
    # D = scaling
    # U = shear

    # D stores the three diagonal entries r00, r11, r22
    # U stores the entries U[0] = u01, U[1] = u02, U[2] = u12


    # build orthogonal matrix Q
    fInvLength = 1.0 / math.sqrt(m[0][0] * m[0][0] + m[1][0] * m[1][0] + m[2][0] * m[2][0])
    kQ_00 = m[0][0] * fInvLength
    kQ_10 = m[1][0] * fInvLength
    kQ_20 = m[2][0] * fInvLength

    fDot = kQ_00 * m[0][1] + kQ_10 * m[1][1] + kQ_20 * m[2][1]
    kQ_01 = m[0][1] - fDot * kQ_00
    kQ_11 = m[1][1] - fDot * kQ_10
    kQ_21 = m[2][1] - fDot * kQ_20
    fInvLength = 1.0 / math.sqrt(kQ_01 * kQ_01 + kQ_11 * kQ_11 + kQ_21 * kQ_21)
    kQ_01 *= fInvLength
    kQ_11 *= fInvLength
    kQ_21 *= fInvLength

    fDot = kQ_00 * m[0][2] + kQ_10 * m[1][2] + kQ_20 * m[2][2]
    kQ_02 = m[0][2] - fDot * kQ_00
    kQ_12 = m[1][2] - fDot * kQ_10
    kQ_22 = m[2][2] - fDot * kQ_20
    fDot = kQ_01 * m[0][2] + kQ_11 * m[1][2] + kQ_21 * m[2][2]
    kQ_02 -= fDot * kQ_01
    kQ_12 -= fDot * kQ_11
    kQ_22 -= fDot * kQ_21
    fInvLength = 1.0 / math.sqrt(kQ_02 * kQ_02 + kQ_12 * kQ_12 + kQ_22 * kQ_22)
    kQ_02 *= fInvLength
    kQ_12 *= fInvLength
    kQ_22 *= fInvLength

    # guarantee that orthogonal matrix has determinant 1 (no reflections)
    fDet = kQ_00 * kQ_11 * kQ_22 + kQ_01 * kQ_12 * kQ_20 + kQ_02 * kQ_10 * kQ_21 - kQ_02 * kQ_11 * kQ_20 - kQ_01 * kQ_10 * kQ_22 - kQ_00 * kQ_12 * kQ_21

    if (fDet < 0.0):
        kQ_00 = -kQ_00
        kQ_01 = -kQ_01
        kQ_02 = -kQ_02
        kQ_10 = -kQ_10
        kQ_11 = -kQ_11
        kQ_12 = -kQ_12
        kQ_20 = -kQ_20
        kQ_21 = -kQ_21
        kQ_22 = -kQ_22

    # build "right" matrix R
    kR_00 = kQ_00 * m[0][0] + kQ_10 * m[1][0] + kQ_20 * m[2][0]
    kR_01 = kQ_00 * m[0][1] + kQ_10 * m[1][1] + kQ_20 * m[2][1]
    kR_11 = kQ_01 * m[0][1] + kQ_11 * m[1][1] + kQ_21 * m[2][1]
    kR_02 = kQ_00 * m[0][2] + kQ_10 * m[1][2] + kQ_20 * m[2][2]
    kR_12 = kQ_01 * m[0][2] + kQ_11 * m[1][2] + kQ_21 * m[2][2]
    kR_22 = kQ_02 * m[0][2] + kQ_12 * m[1][2] + kQ_22 * m[2][2]

    # the scaling component
    kD_0 = kR_00
    kD_1 = kR_11
    kD_2 = kR_22

    # the shear component
    fInvD0 = 1.0 / kD_0
    kU_0 = kR_01 * fInvD0
    kU_1 = kR_02 * fInvD0
    kU_2 = kR_12 / kD_1

    #Scale
    result_posOrientScale[2] = [kD_0, kD_1, kD_2, 1.0]




    #orientation = Quaternion(matQ);		#this->FromRotationMatrix(rot);
    # Algorithm in Ken Shoemake's article in 1987 SIGGRAPH course notes
    # article "Quaternion Calculus and Fast Animation".

    fTrace = kQ_00 + kQ_11 + kQ_22
    fRoot = 0

    if (fTrace > 0.0):
        # |w| > 1/2, may as well choose w > 1/2
        fRoot = math.sqrt(fTrace + 1.0)  # 2w
        result_posOrientScale[1][3] = 0.5 * fRoot					#w
        fRoot = 0.5 / fRoot  # 1/(4w)
        result_posOrientScale[1][0] = (kQ_21 - kQ_12) * fRoot       #x
        result_posOrientScale[1][1] = (kQ_02 - kQ_20) * fRoot       #y
        result_posOrientScale[1][2] = (kQ_10 - kQ_01) * fRoot       #z
    else:
        # /*
        # # |w| <= 1/2
        # static size_t s_iNext[3] = { 1, 2, 0 };
        # size_t i = 0;
        # if (kQ_11 > kQ_00)
        # 	i = 1;
        # if (kQ_22 > kQ_[i][i])
        # 	i = 2;
        # size_t j = s_iNext[i];
        # size_t k = s_iNext[j];

        # fRoot = 1.0 / sqrt(kQ_[i][i] - kQ_[j][j] - kQ_[k][k] + 1.0f);
        # double* apkQuat[3] = { &x, &y, &z };
        # *apkQuat[i] = 0.5f*fRoot;
        # fRoot = 0.5f / fRoot;
        # result_posOrientScale[4] = (kQ_[k][j] - kQ_[j][k])*fRoot;		#w
        # *apkQuat[j] = (kQ_[j][i] + kQ_[i][j])*fRoot;
        # *apkQuat[k] = (kQ_[k][i] + kQ_[i][k])*fRoot;
        # */

        # |w| <= 1/2
        s_iNext = [1, 2, 0]

        if (kQ_11 > kQ_00):
            if (kQ_22 > kQ_11):
                #i = 2;
                #size_t j = 0;
                #size_t k = 1;

                fRoot = math.sqrt(kQ_22 - kQ_00 - kQ_11 + 1.0)

                result_posOrientScale[1][2] = 0.5 * fRoot					#z
                fRoot = 0.5 / fRoot
                result_posOrientScale[1][3] = (kQ_10 - kQ_01) * fRoot		#w
                result_posOrientScale[1][0] = (kQ_02 + kQ_20) * fRoot		#x
                result_posOrientScale[1][1] = (kQ_12 + kQ_21) * fRoot		#y
            else:
                #i = 1
                #size_t j = 2;
                #size_t k = 0;

                fRoot = math.sqrt(kQ_11 - kQ_22 - kQ_00 + 1.0)
                result_posOrientScale[1][1] = 0.5 * fRoot					#y
                fRoot = 0.5 / fRoot
                result_posOrientScale[1][3] = (kQ_02 - kQ_20) * fRoot		#w
                result_posOrientScale[1][2] = (kQ_21 + kQ_12) * fRoot		#z
                result_posOrientScale[1][0] = (kQ_01 + kQ_10) * fRoot		#x

        else:

            if (kQ_22 > kQ_00):
                #i = 2;
                #size_t j = 0;
                #size_t k = 1;

                fRoot = math.sqrt(kQ_22 - kQ_00 - kQ_11 + 1.0)

                result_posOrientScale[1][2] = 0.5 * fRoot					#z
                fRoot = 0.5 / fRoot
                result_posOrientScale[1][3] = (kQ_10 - kQ_01) * fRoot		#w
                result_posOrientScale[1][0] = (kQ_02 + kQ_20) * fRoot		#x
                result_posOrientScale[1][1] = (kQ_12 + kQ_21) * fRoot		#y
            else:
                #i = 0
                #size_t j = 1;
                #size_t k = 2;

                fRoot = math.sqrt(kQ_00 - kQ_11 - kQ_22 + 1.0)

                result_posOrientScale[1][0] = 0.5 * fRoot					#x
                fRoot = 0.5 / fRoot
                result_posOrientScale[1][3] = (kQ_21 - kQ_12) * fRoot		#w
                result_posOrientScale[1][1] = (kQ_10 + kQ_01) * fRoot	    #y
                result_posOrientScale[1][2] = (kQ_20 + kQ_02) * fRoot	    #z

    return result_posOrientScale





def makeTranformOrientationFromTransformRotation(rot):	 # 3 rotations, in degrees

    #need to convert Euler Angles to Quaternion
    axisX = [1, 0, 0]
    axisY = [0, 1, 0]
    axisZ = [0, 0, 1]

    quatX = fromAngleAxis(rot[0], axisX)
    quatY = fromAngleAxis(rot[1], axisY)
    quatZ = fromAngleAxis(rot[2], axisZ)

    quat = quatMulQuat(quatZ, quatMulQuat(quatY, quatX)); #XYZ		=> not like the XYZ order in ean, strange. (but it's the only order solution, others give weird)
    return quat             #orientation (quaternion)

def makeTranformRotationFromTransformOrientation(quat):	 # orientation == Quaternion

    #need to convert Quaternion to Euler Angles (in real, is TaitBryan angles)
    angles = giveAngleOrientationForThisOrientationTaitBryan_XYZ(quat);		# yaws, pitch, roll
    rot = []
    rot.append(angles[2])					#roll						//rotation for X axis	(Xenoverse data is on XYZ order.)
    rot.append(angles[1])					#yaw on disc from pitch.	//for Y axis
    rot.append(angles[0])					#pitch						//for Z axis
    return rot








############### Few versions with xyzw

def crossProd_Vect3_XYZ(vectA, vectB):
    return {"x": (vectA["y"] * vectB["z"] - vectA["z"] * vectB["y"]), \
            "y": (vectA["z"] * vectB["x"] - vectA["x"] * vectB["z"]), \
            "z": (vectA["x"] * vectB["y"] - vectA["y"] * vectB["x"]) }

def crossProd_Vect4_XYZW(vectA, vectB):
    ret = crossProd_Vect3_XYZ(vectA, vectB)
    ret["w"] = 1.0
    return ret
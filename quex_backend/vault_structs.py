from ctypes import Structure, c_uint8, c_uint16

class TdKeyRequestMask(Structure):
    _fields_ = [
        ('reportmacstruct_mask', c_uint8),
        ('tee_tcb_info_mask', c_uint16),
        ('reserved_mask', c_uint8),
        ('tdinfo_base_mask', c_uint16),
        ('tdinfo_extension_mask', c_uint8)
    ]

class ReportMacStruct(Structure):
    _fields_ = [
        ('reporttype', c_uint8*4),
        ('reserved1', c_uint8*12),
        ('cpusvn', c_uint8*16),
        ('tee_tcb_info_hash', c_uint8*48),
        ('tee_info_hash', c_uint8*48),
        ('reportdata', c_uint8*64),
        ('reserved2', c_uint8*32),
        ('mac', c_uint8*32)
    ]
    _packed_ = 1

class TeeTcbSvn(Structure):
    _fields_ = [
        ('tdx_module_svn_minor', c_uint8),
        ('tdx_module_svn_major', c_uint8),
        ('seam_last_patch_svn', c_uint8),
        ('reserved', c_uint8*13),
    ]

class TeeTcbInfoStruct(Structure):
    _fields_ = [
        ('valid', c_uint8*8),
        ('tee_tcb_svn', c_uint8*16),
        ('mrseam', c_uint8*48),
        ('mrsignerseam', c_uint8*48),
        ('attributes', c_uint8*8),
        ('tee_tcb_svn2', TeeTcbSvn),
        ('reserved', c_uint8*95)
    ]

class TdInfoBase(Structure):
    _fields_ = [
        ('attributes', c_uint8*8),
        ('xfam', c_uint8*8),
        ('mrtd', c_uint8*48),
        ('mrconfigid', c_uint8*48),
        ('mrowner', c_uint8*48),
        ('mrownerconfig', c_uint8*48),
        ('rtmr0', c_uint8*48),
        ('rtmr1', c_uint8*48),
        ('rtmr2', c_uint8*48),
        ('rtmr3', c_uint8*48),
        ('servtd_hash', c_uint8*48),
    ]

class TdInfoExtension(Structure):
    _fields_ = [
        ('reserved', c_uint8*64)
    ]

class TdInfoStruct(Structure):
    _fields_ = [
        ('tdinfo_base', TdInfoBase),
        ('tdinfo_extension', TdInfoExtension)
    ]

class TdReport(Structure):
    _fields_ = [
        ('reportmacstruct', ReportMacStruct),
        ('tee_tcb_info', TeeTcbInfoStruct),
        ('reserved', c_uint8*17),
        ('tdinfo', TdInfoStruct)
    ]

class TdKeyRequest(Structure):
    _fields_ = [
        ('mask', TdKeyRequestMask),
        ('tdreport', TdReport)
    ]

class TdMsg(Structure):
    _fields_ = [
        ('mask', TdKeyRequestMask),
        ('tdreport', TdReport),
        ('ciphertext', 128*c_uint8)
    ]

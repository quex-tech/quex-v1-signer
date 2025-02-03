from Crypto.Hash import SHA256
import cryptography.hazmat.primitives.asymmetric.ec as ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
import cryptography.hazmat.primitives.hashes as hashes
import OpenSSL
from ctypes import c_uint8

def verify_sgx_quote_report_data(quote, td_msg):
    h = SHA256.new()
    h.update(bytes(td_msg))
    if h.digest() != quote.isv_enclave_report.report_data[:32]:
        raise AssertionError

def verify_certificate_chain(cert_str, root_cert):
    cert_start_line = b'-----BEGIN CERTIFICATE-----'
    certs = [OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM, cert_start_line+x) \
             for x in cert_str.split(cert_start_line)[1:]]
    store = OpenSSL.crypto.X509Store()
    store.add_cert(root_cert)
    store_ctx = OpenSSL.crypto.X509StoreContext(store, certs[0], certs)
    store_ctx.verify_certificate()
    return certs[0]

def verify_sgx_quote(quote, root_cert):

    pck_cert = verify_certificate_chain(quote\
            .quote_signature_data\
            .qe_certification_data\
            .certification_data, root_cert)
    
    # Verify qe_report signature (by PCK)
    
    pubkey = pck_cert.get_pubkey().to_cryptography_key()
    msg = quote.quote_signature_data.qe_report.serialize()
    sig = quote.quote_signature_data.qe_report_signature
    sig_der = encode_dss_signature(int.from_bytes(sig.r, 'big'), int.from_bytes(sig.s, 'big'))
    pubkey.verify(sig_der, msg, ec.ECDSA(hashes.SHA256()))
    
    # Verify attestation key hash
    
    h = SHA256.new()
    h.update(quote.quote_signature_data.ecdsa_attestation_key.serialize() + quote.quote_signature_data.qe_authentication_data.data)
    if h.digest() + b'\x00'*32 != quote.quote_signature_data.qe_report.report_data:
        raise AssertionError
    
    # Verify isv_enclave_report_signature (with attestation key)
    pubkey = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), b'\x04' +
                                                          quote.quote_signature_data.ecdsa_attestation_key.serialize())
    msg = quote.quote_header.serialize() + quote.isv_enclave_report.serialize()
    sig = quote.quote_signature_data.isv_enclave_report_signature
    sig_der = encode_dss_signature(int.from_bytes(sig.r, 'big'), int.from_bytes(sig.s, 'big'))
    pubkey.verify(sig_der, msg, ec.ECDSA(hashes.SHA256()))
    return

def apply_mask(report, mask):
    rm = mask.reportmacstruct_mask
    if not (rm & 1):
        for i, _ in enumerate(report.reportmacstruct.reporttype):
            report.reportmacstruct.reporttype[i] = c_uint8(0)
    if not ((rm >> 1) & 1):
        for i, _ in enumerate(report.reportmacstruct.reserved1):
            report.reportmacstruct.reserved1[i] = c_uint8(0)
    if not ((rm >> 2) & 1):
        for i, _ in enumerate(report.reportmacstruct.cpusvn):
            report.reportmacstruct.cpusvn[i] = c_uint8(0)
    if not ((rm >> 3) & 1):
        for i, _ in enumerate(report.reportmacstruct.tee_tcb_info_hash):
            report.reportmacstruct.tee_tcb_info_hash[i] = c_uint8(0)
    if not ((rm >> 4) & 1):
        for i, _ in enumerate(report.reportmacstruct.tee_info_hash):
            report.reportmacstruct.tee_info_hash[i] = c_uint8(0)
    if not ((rm >> 5) & 1):
        for i, _ in enumerate(report.reportmacstruct.reportdata):
            report.reportmacstruct.reportdata[i] = c_uint8(0)
    if not ((rm >> 6) & 1):
        for i, _ in enumerate(report.reportmacstruct.reserved2):
            report.reportmacstruct.reserved2[i] = c_uint8(0)
    if not ((rm >> 7) & 1):
        for i, _ in enumerate(report.reportmacstruct.reserved2):
            report.reportmacstruct.reserved2[i] = c_uint8(0)
    
    rm = mask.tee_tcb_info_mask
    if not (rm & 1):
        for i, _ in enumerate(report.tee_tcb_info.valid):
            report.tee_tcb_info.valid[i] = c_uint8(0)
    if not ((rm >> 1) & 1):
        for i, _ in enumerate(report.tee_tcb_info.tee_tcb_svn):
            report.tee_tcb_info.tee_tcb_svn[i] = c_uint8(0)
    if not ((rm >> 2) & 1):
        for i, _ in enumerate(report.tee_tcb_info.mrseam):
            report.tee_tcb_info.mrseam[i] = c_uint8(0)
    if not ((rm >> 3) & 1):
        for i, _ in enumerate(report.tee_tcb_info.mrsignerseam):
            report.tee_tcb_info.mrsignerseam[i] = c_uint8(0)
    if not ((rm >> 4) & 1):
        for i, _ in enumerate(report.tee_tcb_info.attributes):
            report.tee_tcb_info.attributes[i] = c_uint8(0)
    if not ((rm >> 5) & 1):
        report.tee_tcb_info.tee_tcb_svn2.tdx_module_svn_minor = c_uint8(0)
    if not ((rm >> 6) & 1):
        report.tee_tcb_info.tee_tcb_svn2.tdx_module_svn_major = c_uint8(0)
    if not ((rm >> 7) & 1):
        report.tee_tcb_info.tee_tcb_svn2.seam_last_patch_svn = c_uint8(0)
    if not ((rm >> 8) & 1):
        for i, _ in enumerate(report.tee_tcb_info.tee_tcb_svn2.reserved):
            report.tee_tcb_info.tee_tcb_svn2.reserved[i] = c_uint8(0)
    if not ((rm >> 9) & 1):
        for i, _ in enumerate(report.tee_tcb_info.reserved):
            report.tee_tcb_info.reserved[i] = c_uint8(0)
            
    rm = mask.reserved_mask
    if not (rm & 1):
        for i, _ in enumerate(report.reserved):
            report.reserved[i] = c_uint8(0)
    
    rm = mask.tdinfo_base_mask
    
    if not (rm & 1):
        for i, _ in enumerate(report.tdinfo.tdinfo_base.attributes):
            report.tdinfo.tdinfo_base.attributes[i] = c_uint8(0)
    if not ((rm >> 1) & 1):
        for i, _ in enumerate(report.tdinfo.tdinfo_base.xfam):
            report.tdinfo.tdinfo_base.xfam[i] = c_uint8(0)
    if not ((rm >> 2) & 1):
        for i, _ in enumerate(report.tdinfo.tdinfo_base.mrtd):
            report.tdinfo.tdinfo_base.mrtd[i] = c_uint8(0)
    if not ((rm >> 3) & 1):
        for i, _ in enumerate(report.tdinfo.tdinfo_base.mrconfigid):
            report.tdinfo.tdinfo_base.mrconfigid[i] = c_uint8(0)
    if not ((rm >> 4) & 1):
        for i, _ in enumerate(report.tdinfo.tdinfo_base.mrowner):
            report.tdinfo.tdinfo_base.mrowner[i] = c_uint8(0)
    if not ((rm >> 5) & 1):
        for i, _ in enumerate(report.tdinfo.tdinfo_base.mrownerconfig):
            report.tdinfo.tdinfo_base.mrownerconfig[i] = c_uint8(0)
    if not ((rm >> 6) & 1):
        for i, _ in enumerate(report.tdinfo.tdinfo_base.rtmr0):
            report.tdinfo.tdinfo_base.rtmr0[i] = c_uint8(0)
    if not ((rm >> 7) & 1):
        for i, _ in enumerate(report.tdinfo.tdinfo_base.rtmr1):
            report.tdinfo.tdinfo_base.rtmr1[i] = c_uint8(0)
    if not ((rm >> 8) & 1):
        for i, _ in enumerate(report.tdinfo.tdinfo_base.rtmr2):
            report.tdinfo.tdinfo_base.rtmr2[i] = c_uint8(0)
    if not ((rm >> 9) & 1):
        for i, _ in enumerate(report.tdinfo.tdinfo_base.rtmr3):
            report.tdinfo.tdinfo_base.rtmr3[i] = c_uint8(0)
    if not ((rm >> 10) & 1):
        for i, _ in enumerate(report.tdinfo.tdinfo_base.servtd_hash):
            report.tdinfo.tdinfo_base.servtd_hash[i] = c_uint8(0)
    
    rm = mask.tdinfo_extension_mask
    
    if not (rm & 1):
        for i, _ in enumerate(report.tdinfo.tdinfo_extension.reserved):
            report.tdinfo.tdinfo_extension.reserved[i] = c_uint8(0)
    return report

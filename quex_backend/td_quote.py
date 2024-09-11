from dataclasses import dataclass
import dataclasses
from typing import Any

@dataclass
class TDQuoteHeader:
    version: int
    attestation_key_type: int
    tee_type: int
    qe_vendor_id: bytes
    user_data: bytes

    def serialize(self):
        res = self.version.to_bytes(2,'little') + \
                self.attestation_key_type.to_bytes(2, 'little') + \
                self.tee_type.to_bytes(4, 'little') + \
                b'\x00'*4 + \
                self.qe_vendor_id[:16].ljust(16, b'\x00') + \
                self.user_data[:20].ljust(20, b'\x00')
        return res
    def deserialize(b):
        assert(len(b) == 48)
        assert(b[8:12] == b'\x00'*4)
        res = TDQuoteHeader(
                version=int.from_bytes(b[0:2],'little'),
                attestation_key_type=int.from_bytes(b[2:4],'little'),
                tee_type=int.from_bytes(b[4:8], 'little'),
                qe_vendor_id=b[12:28],
                user_data=b[28:48],
                )
        assert(res.version == 4)
        assert(res.attestation_key_type == 2)
        assert(res.qe_vendor_id == bytes.fromhex("939A7233F79C4CA9940A0DB3957F0607"))
        return res

@dataclass
class TDQuoteBody:
    tcb_svn: bytes
    mrseam: bytes
    mrsignerseam: bytes
    seamattributes: bytes
    tdattributes: bytes
    xfam: bytes
    mrtd: bytes
    mrconfigd: bytes
    mrowner: bytes
    mrownerconfig: bytes
    rtmr0: bytes
    rtmr1: bytes
    rtmr2: bytes
    rtmr3: bytes
    reportdata: bytes
    def serialize(self):
        res = self.tcb_svn[:16].ljust(16, b'\x00') + \
                self.mrseam[:48].ljust(48, b'\x00') + \
                self.mrsignerseam[:48].ljust(48, b'\x00') + \
                self.seamattributes[:8].ljust(8, b'\x00') + \
                self.tdattributes[:8].ljust(8, b'\x00') + \
                self.xfam[:8].ljust(8, b'\x00') + \
                self.mrtd[:48].ljust(48, b'\x00') + \
                self.mrconfigd[:48].ljust(48, b'\x00') + \
                self.mrowner[:48].ljust(48, b'\x00') + \
                self.mrownerconfig[:48].ljust(48, b'\x00') + \
                self.rtmr0[:48].ljust(48, b'\x00') + \
                self.rtmr1[:48].ljust(48, b'\x00') + \
                self.rtmr2[:48].ljust(48, b'\x00') + \
                self.rtmr3[:48].ljust(48, b'\x00') + \
                self.reportdata[:64].ljust(64,b'\x00')
        return res
    def deserialize(b):
        assert(len(b) == 584)
        res = TDQuoteBody(
                tcb_svn=b[0:16],
                mrseam=b[16:64],
                mrsignerseam=b[64:112],
                seamattributes=b[112:120],
                tdattributes=b[120:128],
                xfam=b[128:136],
                mrtd=b[136:184],
                mrconfigd=b[184:232],
                mrowner=b[232:280],
                mrownerconfig=b[280:328],
                rtmr0=b[328:376],
                rtmr1=b[376:424],
                rtmr2=b[424:472],
                rtmr3=b[472:520],
                reportdata=b[520:584]
                )
        return res

@dataclass
class P256Signature:
    r: bytes
    s: bytes
    def deserialize(b):
        assert(len(b) == 64)
        return P256Signature(
                r=b[:32],
                s=b[32:]
                )
    def serialize(self):
        return self.r[:32].ljust(32, b'\x00') + self.s[:32].ljust(32, b'\x00')

@dataclass
class EnclaveReportBody:
    cpu_svn: bytes
    miscselect: int
    attributes: bytes
    mrenclave: bytes
    mrsigner: bytes
    isv_prodID: int
    isv_svn: int
    report_data: bytes

    def deserialize(b):
        assert(len(b) == 384)
        assert(b[20:48] == b'\x00'*28)
        assert(b[96:128] == b'\x00'*32)
        assert(b[160:256] == b'\x00'*96)
        assert(b[260:320] == b'\x00'*60)
        return EnclaveReportBody(
                cpu_svn=b[0:16],
                miscselect=int.from_bytes(b[16:20], 'little'),
                attributes=b[48:64],
                mrenclave=b[64:96],
                mrsigner=b[128:160],
                isv_prodID=int.from_bytes(b[256:258], 'little'),
                isv_svn=int.from_bytes(b[258:260], 'little'),
                report_data=b[320:384]
                )
    def serialize(self):
        return self.cpu_svn[:16].ljust(16, b'\x00') + \
                self.miscselect.to_bytes(4, 'little') + \
                b'\x00'*28 + \
                self.attributes[:16].ljust(16, b'\x00') + \
                self.mrenclave[:32].ljust(32, b'\x00') + \
                b'\x00'*32 + \
                self.mrsigner[:32].ljust(32, b'\x00') + \
                b'\x00'*96 + \
                self.isv_prodID.to_bytes(2,'little') + \
                b'\x00'*60 + \
                self.report_data[:64].ljust(64, b'\x00')

@dataclass
class QECertificationData:
    certification_data_type: int
    certification_data: Any
    size: int
    def deserialize(b):
        data_type = int.from_bytes(b[:2], 'little')
        assert(data_type in [1,2,3,4,5,6])
        size = int.from_bytes(b[2:6], 'little')
        assert(len(b) >= size + 6)
        if data_type == 6:
            certification_data = QEReportCertificationData.deserialize(b[6:6+size])
        elif data_type == 5:
            certification_data = b[6:6+size].decode()
        else:
            certification_data = b[6:6+size]
        return QECertificationData(
                certification_data_type=data_type,
                size=size,
                certification_data=certification_data
                )
    def serialize(self):
        if self.certification_data_type == 6:
            cert_data = self.certification_data.serialize()
        elif self.certification_data_type == 5:
            cert_data = self.certification_data.encode()
        else:
            cert_data = self.certification_data
        return self.certification_data_type.to_bytes(2,'little') + \
                len(cert_data).to_bytes(2,'little') + \
                cert_data

@dataclass
class QEAuthenticationData:
    size: int
    data: bytes
    def deserialize(b):
        size = int.from_bytes(b[:2], 'little')
        assert(len(b) >= size + 2)
        return QEAuthenticationData(
                size=size,
                data=b[2:2+size]
                )
    def serialize(self):
        return len(self.data).to_bytes(2,'little') + self.data


@dataclass
class QEReportCertificationData:
    qe_report: EnclaveReportBody
    qe_report_signature: P256Signature
    qe_authentication_data: QEAuthenticationData
    qe_certification_data: QECertificationData
    def deserialize(b):
        report = EnclaveReportBody.deserialize(b[0:384])
        signature = P256Signature.deserialize(b[384:448])
        authentication_data = QEAuthenticationData.deserialize(b[448:])
        certification_data = QECertificationData.deserialize(b[450+authentication_data.size:])
        assert(456 + authentication_data.size + certification_data.size == len(b))
        return QEReportCertificationData(
                qe_report=report,
                qe_report_signature=signature,
                qe_authentication_data=authentication_data,
                qe_certification_data=certification_data
                )
    def serialize(self):
        return self.qe_report.serialize() + \
                self.qe_report_signature.serialize() + \
                self.qe_authentication_data.serialize() + \
                self.qe_certification_data.serialize()

@dataclass
class P256PublicKey:
    x: bytes
    y: bytes
    def deserialize(b):
        assert(len(b) == 64)
        return P256PublicKey(
                x=b[:32],
                y=b[32:64]
                )
    def serialize(self):
        return self.x[:32].ljust(32, b'\x00') + self.y[:32].ljust(32, b'\x00')

@dataclass
class ECDSA256QuoteSignatureData:
    quote_signature: P256Signature
    ecdsa_attestation_key: P256PublicKey
    qe_certification_data: QECertificationData
    def deserialize(b):
        return ECDSA256QuoteSignatureData(
                quote_signature=P256Signature.deserialize(b[:64]),
                ecdsa_attestation_key=P256PublicKey.deserialize(b[64:128]),
                qe_certification_data=QECertificationData.deserialize(b[128:])
                )
    def serialize(self):
        return self.quote_signature.serialize() + \
                self.ecdsa_attestation_key.serialize() + \
                self.qe_certification_data.serialize()


@dataclass
class TDQuote:
    quote_header: TDQuoteHeader
    td_quote_body: TDQuoteBody
    quote_siganture_data_len: int
    quote_signature_data: ECDSA256QuoteSignatureData
    def deserialize(b):
        header = TDQuoteHeader.deserialize(b[:48])
        body = TDQuoteBody.deserialize(b[48:632])
        sig_len = int.from_bytes(b[632:636], 'little')
        sig_data = ECDSA256QuoteSignatureData.deserialize(b[636:636+sig_len])
        return TDQuote(
                quote_header=header,
                td_quote_body=body,
                quote_siganture_data_len=sig_len,
                quote_signature_data=sig_data
                )
    def serialize(self):
        sig_data = self.quote_signature_data.serialize()
        return self.quote_header.serialize() + \
                self.td_quote_body.serialize() + \
                len(sig_data).to_bytes(4, 'little') + \
                sig_data

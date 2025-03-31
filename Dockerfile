# ubuntu:noble-20251001
FROM ubuntu@sha256:66460d557b25769b102175144d538d88219c077c678a49af4afca6fbfc1b5252 AS builder

ARG REPRO_SOURCES_LIST_VERSION=0.1.4
ARG REPRO_SOURCES_LIST_SHA256=c125df9762b0c7233459087bb840c0e5dbfc4d9690ee227f1ed8994f4d51d2e0
ADD --checksum=sha256:$REPRO_SOURCES_LIST_SHA256 --chmod=755 https://raw.githubusercontent.com/reproducible-containers/repro-sources-list.sh/refs/tags/v${REPRO_SOURCES_LIST_VERSION}/repro-sources-list.sh /usr/local/bin/repro-sources-list.sh

ENV PYTHONDONTWRITEBYTECODE=1

RUN \
  --mount=type=cache,target=/var/cache/apt,sharing=locked \
  --mount=type=cache,target=/var/lib/apt,sharing=locked \
  <<EOF
  set -eu
  repro-sources-list.sh
  DEBIAN_FRONTEND=noninteractive apt-get install -y --update gcc python3 python3-pip ca-certificates
  rm -rf /var/log/* /var/cache/ldconfig/aux-cache
EOF

ARG SOURCE_DATE_EPOCH
ARG FINAL_ROOT=/tmp/rootfs

COPY quex_backend ${FINAL_ROOT}/opt/quex-v1-signer/quex_backend
COPY config.toml ${FINAL_ROOT}/opt/quex-v1-signer/
COPY start.py ${FINAL_ROOT}/opt/quex-v1-signer/

COPY requirements.cp312.txt /tmp/
COPY pyquex-tdx /tmp/pyquex-tdx

ARG SGX_DCAP_URL=https://ppa.launchpadcontent.net/kobuk-team/tdx-attestation-release/ubuntu/pool/main/s/sgx-dcap
ARG LIBTDX_ATTEST_VERSION=1.21-0ubuntu2.2
ARG LIBTDX_ATTEST1_DEB=libtdx-attest1_${LIBTDX_ATTEST_VERSION}_amd64.deb
ARG LIBTDX_ATTEST_DEV_DEB=libtdx-attest-dev_${LIBTDX_ATTEST_VERSION}_amd64.deb
ARG LIBTDX_ATTEST1_DEB_CHECKSUM=sha256:2dcc6087aa6c722e20883e1e794f9526f3c747b096cf9d3bd58d5093ed18c530
ARG LIBTDX_ATTEST_DEV_DEB_CHECKSUM=sha256:0a8554784da8d9fdd30f414ac5a956c4987cfff74259a70c742dc0f569e4f1a2
ADD --checksum=${LIBTDX_ATTEST1_DEB_CHECKSUM} ${SGX_DCAP_URL}/${LIBTDX_ATTEST1_DEB} /tmp/libtdx-attest1.deb
ADD --checksum=${LIBTDX_ATTEST_DEV_DEB_CHECKSUM} ${SGX_DCAP_URL}/${LIBTDX_ATTEST_DEV_DEB} /tmp/libtdx-attest-dev.deb

RUN <<EOF
set -eu
dpkg -i /tmp/libtdx-attest1.deb
dpkg -i /tmp/libtdx-attest-dev.deb
pip install \
  --root /tmp/quex-v1-signer-requirements \
  --no-compile \
  --only-binary :all: \
  --no-build-isolation \
  -r /tmp/requirements.cp312.txt
pip install \
  --root /tmp/quex-v1-signer-requirements \
  --no-compile \
  --only-binary :all: \
  --no-build-isolation \
  /tmp/pyquex-tdx
EOF

RUN <<EOF
set -eu

for dirname in usr/bin usr/share usr/lib/x86_64-linux-gnu etc; do
  mkdir -p ${FINAL_ROOT}/${dirname}
done

cp -a /lib ${FINAL_ROOT}/
cp -a /lib64 ${FINAL_ROOT}/
cp -a /usr/lib64 ${FINAL_ROOT}/usr/

cp -a /usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.* ${FINAL_ROOT}/usr/lib/x86_64-linux-gnu/

for libname in c crypto dl expat ffi gcc_s m pthread rt ssl tdx_attest z; do
  cp -a /usr/lib/x86_64-linux-gnu/lib${libname}.so.* ${FINAL_ROOT}/usr/lib/x86_64-linux-gnu/
done

cp -a /etc/ssl ${FINAL_ROOT}/etc/
cp -a /etc/services ${FINAL_ROOT}/etc/
cp -a /usr/lib/ssl ${FINAL_ROOT}/usr/lib/
cp -a /usr/share/ca-certificates ${FINAL_ROOT}/usr/share/

cp -a /usr/bin/python* ${FINAL_ROOT}/usr/bin/
rm ${FINAL_ROOT}/usr/bin/python*-config

cp -a /usr/lib/python* ${FINAL_ROOT}/usr/lib/
rm -r ${FINAL_ROOT}/usr/lib/python*/config-*-x86_64-linux-gnu

cp -a /tmp/quex-v1-signer-requirements/usr/local/lib/* ${FINAL_ROOT}/usr/lib/

find ${FINAL_ROOT} -type d -name "__pycache__" -exec rm -r {} +

echo "nameserver 10.13.192.2" > ${FINAL_ROOT}/etc/resolv.conf
EOF

FROM scratch AS final
COPY --from=builder /tmp/rootfs /
ENV TD_SECRET_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
ENV ETH_SIGNER_KEY_FILE=sk.txt
ENV CONFIG=/opt/quex-v1-signer/config.toml
EXPOSE 8080
CMD ["/usr/bin/python3", "/opt/quex-v1-signer/start.py"]

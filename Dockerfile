FROM ubuntu@sha256:dc17125eaac86538c57da886e494a34489122fb6a3ebb6411153d742594c2ddc AS builder

ARG SGX_DCAP_URL=https://ppa.launchpadcontent.net/kobuk-team/tdx-attestation-release/ubuntu/pool/main/s/sgx-dcap
ARG LIBTDX_ATTEST_VERSION=1.21-0ubuntu2.2
ARG LIBTDX_ATTEST1_DEB=libtdx-attest1_${LIBTDX_ATTEST_VERSION}_amd64.deb
ARG LIBTDX_ATTEST_DEV_DEB=libtdx-attest-dev_${LIBTDX_ATTEST_VERSION}_amd64.deb
ARG LIBTDX_ATTEST1_DEB_CHECKSUM=sha256:2dcc6087aa6c722e20883e1e794f9526f3c747b096cf9d3bd58d5093ed18c530
ARG LIBTDX_ATTEST_DEV_DEB_CHECKSUM=sha256:0a8554784da8d9fdd30f414ac5a956c4987cfff74259a70c742dc0f569e4f1a2

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1

RUN \
  --mount=type=cache,target=/var/cache/apt,sharing=locked \
  --mount=type=cache,target=/var/lib/apt,sharing=locked \
  --mount=type=bind,source=./vendor/repro-sources-list.sh,target=/usr/local/bin/repro-sources-list.sh \
  repro-sources-list.sh && \
  apt install -y --update gcc python3 python3-pip ca-certificates && \
  rm -rf /var/log/* /var/cache/ldconfig/aux-cache

COPY quex_backend /opt/quex-v1-signer/quex_backend
COPY config.toml /opt/quex-v1-signer/
COPY requirements.cp312.txt /opt/quex-v1-signer/
COPY start.py /opt/quex-v1-signer/
COPY pyquex-tdx /opt/pyquex-tdx

ADD --checksum=${LIBTDX_ATTEST1_DEB_CHECKSUM} ${SGX_DCAP_URL}/${LIBTDX_ATTEST1_DEB} /tmp/libtdx-attest1.deb
ADD --checksum=${LIBTDX_ATTEST_DEV_DEB_CHECKSUM} ${SGX_DCAP_URL}/${LIBTDX_ATTEST_DEV_DEB} /tmp/libtdx-attest-dev.deb

RUN dpkg -i /tmp/libtdx-attest1.deb
RUN dpkg -i /tmp/libtdx-attest-dev.deb

RUN pip install \
  --break-system-packages \
  --no-compile \
  --only-binary :all: \
  --no-build-isolation \
  -r /opt/quex-v1-signer/requirements.cp312.txt

RUN pip install \
  --break-system-packages \
  --no-compile \
  --only-binary :all: \
  --no-build-isolation \
  /opt/pyquex-tdx

COPY <<EOF /etc/resolv.conf
nameserver 10.13.192.2
EOF
ENV TD_SECRET_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
ENV ETH_SIGNER_KEY_FILE=sk.txt
ENV CONFIG=/opt/quex-v1-signer/config.toml
EXPOSE 8080
CMD ["/usr/bin/python3", "/opt/quex-v1-signer/start.py"]

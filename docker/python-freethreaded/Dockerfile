# Python 3.14 Free-Threaded (GIL-disabled) Docker Image
#
# Based on the official python:3.14-slim-bookworm Dockerfile with --disable-gil added.
# This enables true multi-threaded parallelism for CPU-bound Python workloads.
#
# Usage:
#   docker build -t python:3.14t-slim-bookworm .
#
# Verify free-threading is enabled:
#   docker run --rm python:3.14t-slim-bookworm python -c \
#     "import sysconfig; print('Free-threaded:', bool(sysconfig.get_config_var('Py_GIL_DISABLED')))"
#
# References:
#   - https://docs.python.org/3/howto/free-threading-python.html
#   - https://py-free-threading.github.io/running-gil-disabled/
#   - https://github.com/docker-library/python (original source)
#
# Note: Hadolint ignores are used because this Dockerfile mirrors the official
# Python Dockerfile structure. Version pinning is not used to get latest security
# patches, and the complex RUN commands are copied verbatim from upstream.

FROM debian:bookworm-slim

# Ensure local python is preferred over distribution python
ENV PATH /usr/local/bin:$PATH

# Runtime dependencies
# hadolint ignore=DL3008
RUN set -eux; \
	apt-get update; \
	apt-get install -y --no-install-recommends \
		ca-certificates \
		netbase \
		tzdata \
	; \
	rm -rf /var/lib/apt/lists/*

# Python version - update these when new releases are available
ENV PYTHON_VERSION 3.14.2
ENV PYTHON_SHA256 ce543ab854bc256b61b71e9b27f831ffd1bfd60a479d639f8be7f9757cf573e9

# hadolint ignore=DL3003,DL3008,DL3047,DL4006,SC2086
RUN set -eux; \
	\
	savedAptMark="$(apt-mark showmanual)"; \
	apt-get update; \
	apt-get install -y --no-install-recommends \
		dpkg-dev \
		gcc \
		gnupg \
		libbluetooth-dev \
		libbz2-dev \
		libc6-dev \
		libdb-dev \
		libffi-dev \
		libgdbm-dev \
		liblzma-dev \
		libncursesw5-dev \
		libreadline-dev \
		libsqlite3-dev \
		libssl-dev \
		libzstd-dev \
		make \
		tk-dev \
		uuid-dev \
		wget \
		xz-utils \
		zlib1g-dev \
	; \
	\
	wget -O python.tar.xz "https://www.python.org/ftp/python/${PYTHON_VERSION%%[a-z]*}/Python-$PYTHON_VERSION.tar.xz"; \
	echo "$PYTHON_SHA256 *python.tar.xz" | sha256sum -c -; \
	mkdir -p /usr/src/python; \
	tar --extract --directory /usr/src/python --strip-components=1 --file python.tar.xz; \
	rm python.tar.xz; \
	\
	cd /usr/src/python; \
	gnuArch="$(dpkg-architecture --query DEB_BUILD_GNU_TYPE)"; \
	# ============================================================
	# FREE-THREADING: --disable-gil enables GIL-free Python build
	# This is the ONLY change from the official Dockerfile
	# ============================================================
	./configure \
		--build="$gnuArch" \
		--disable-gil \
		--enable-loadable-sqlite-extensions \
		--enable-optimizations \
		--enable-option-checking=fatal \
		--enable-shared \
		$(test "${gnuArch%%-*}" != 'riscv64' && echo '--with-lto') \
		--with-ensurepip \
	; \
	nproc="$(nproc)"; \
	EXTRA_CFLAGS="$(dpkg-buildflags --get CFLAGS)"; \
	LDFLAGS="$(dpkg-buildflags --get LDFLAGS)"; \
	LDFLAGS="${LDFLAGS:-} -Wl,--strip-all"; \
	arch="$(dpkg --print-architecture)"; arch="${arch##*-}"; \
	case "$arch" in \
		amd64|arm64) \
			EXTRA_CFLAGS="${EXTRA_CFLAGS:-} -fno-omit-frame-pointer -mno-omit-leaf-frame-pointer"; \
			;; \
		i386) \
			;; \
		*) \
			EXTRA_CFLAGS="${EXTRA_CFLAGS:-} -fno-omit-frame-pointer"; \
			;; \
	esac; \
	make -j "$nproc" \
		"EXTRA_CFLAGS=${EXTRA_CFLAGS:-}" \
		"LDFLAGS=${LDFLAGS:-}" \
	; \
	rm python; \
	make -j "$nproc" \
		"EXTRA_CFLAGS=${EXTRA_CFLAGS:-}" \
		"LDFLAGS=${LDFLAGS:-} -Wl,-rpath='\$\$ORIGIN/../lib'" \
		python \
	; \
	make install; \
	\
	cd /; \
	rm -rf /usr/src/python; \
	\
	find /usr/local -depth \
		\( \
			\( -type d -a \( -name test -o -name tests -o -name idle_test \) \) \
			-o \( -type f -a \( -name '*.pyc' -o -name '*.pyo' -o -name 'libpython*.a' \) \) \
		\) -exec rm -rf '{}' + \
	; \
	\
	ldconfig; \
	\
	apt-mark auto '.*' > /dev/null; \
	apt-mark manual $savedAptMark; \
	find /usr/local -type f -executable -not \( -name '*tkinter*' \) -exec ldd '{}' ';' \
		| awk '/=>/ { so = $(NF-1); if (index(so, "/usr/local/") == 1) { next }; gsub("^/(usr/)?", "", so); printf "*%s\n", so }' \
		| sort -u \
		| xargs -rt dpkg-query --search \
		| awk 'sub(":$", "", $1) { print $1 }' \
		| sort -u \
		| xargs -r apt-mark manual \
	; \
	apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false; \
	rm -rf /var/lib/apt/lists/*; \
	\
	export PYTHONDONTWRITEBYTECODE=1; \
	python3 --version; \
	# Verify free-threading is enabled
	python3 -c "import sysconfig; assert sysconfig.get_config_var('Py_GIL_DISABLED'), 'Free-threading not enabled!'"; \
	pip3 --version

# Make useful symlinks that are expected to exist ("/usr/local/bin/python" and friends)
# hadolint ignore=DL4006
RUN set -eux; \
	for src in idle3 pip3 pydoc3 python3 python3-config; do \
		dst="$(echo "$src" | tr -d 3)"; \
		[ -s "/usr/local/bin/$src" ]; \
		[ ! -e "/usr/local/bin/$dst" ]; \
		ln -svT "$src" "/usr/local/bin/$dst"; \
	done

# Label for identification
LABEL org.opencontainers.image.title="Python 3.14 Free-Threaded"
LABEL org.opencontainers.image.description="Python 3.14 built with --disable-gil for true multi-threaded parallelism"
LABEL org.opencontainers.image.version="${PYTHON_VERSION}"
LABEL org.opencontainers.image.vendor="home-security-intelligence"
LABEL python.freethreaded="true"

CMD ["python3"]

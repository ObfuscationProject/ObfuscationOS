#!/usr/bin/env bash
set -euo pipefail

BINUTILS_VERSION="${BINUTILS_VERSION:-2.42}"
GCC_VERSION="${GCC_VERSION:-14.2.0}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PREFIX_ROOT="${PREFIX_ROOT:-${PROJECT_ROOT}/toolchains}"
BUILD_ROOT="${BUILD_ROOT:-${PROJECT_ROOT}/.cache/toolchain-build}"
SRC_ROOT="${SRC_ROOT:-${PROJECT_ROOT}/.cache/toolchain-src}"
JOBS="${JOBS:-$(nproc)}"
ARCH="all"

usage() {
    cat <<'USAGE'
Usage: scripts/build-toolchain.sh [--arch ARCH] [--jobs N]

Build binutils and GCC cross toolchains under ./toolchains.

Architectures:
  x86_64 aarch64 rv64 loongarch64 all

Environment:
  BINUTILS_VERSION  default: 2.42
  GCC_VERSION       default: 14.2.0
  PREFIX_ROOT       default: ./toolchains
  BUILD_ROOT        default: ./.cache/toolchain-build
  SRC_ROOT          default: ./.cache/toolchain-src
USAGE
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --arch)
            ARCH="$2"
            shift 2
            ;;
        --jobs)
            JOBS="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "unknown argument: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

triple_for_arch() {
    case "$1" in
        x86_64|x64) echo "x86_64-elf" ;;
        aarch64) echo "aarch64-elf" ;;
        rv64|riscv64) echo "riscv64-elf" ;;
        loongarch64) echo "loongarch64-elf" ;;
        *) echo "unsupported architecture: $1" >&2; return 1 ;;
    esac
}

sync_toolchain_include_layout() {
    local prefix="$1"
    local target="$2"
    local include_root="${prefix}/include"
    local cxx_include="${prefix}/${target}/include"
    local gcc_include="${prefix}/lib/gcc/${target}/${GCC_VERSION}/include"
    local gcc_fixed_include="${prefix}/lib/gcc/${target}/${GCC_VERSION}/include-fixed"

    mkdir -p "$include_root"

    if [[ -d "${cxx_include}/c++" ]]; then
        rm -rf "${include_root}/c++"
        ln -sfn "${cxx_include}/c++" "${include_root}/c++"
    fi

    for item in "$gcc_include"/* "$gcc_fixed_include"/*; do
        if [[ -e "$item" ]]; then
            local base
            base="$(basename "$item")"
            if [[ ! -e "${include_root}/${base}" ]]; then
                ln -sfn "$item" "${include_root}/${base}"
            fi
        fi
    done
}

download() {
    local url="$1"
    local output="$2"
    if [[ -f "$output" ]]; then
        return
    fi
    if command -v curl >/dev/null 2>&1; then
        curl -L "$url" -o "$output"
    elif command -v wget >/dev/null 2>&1; then
        wget "$url" -O "$output"
    else
        echo "curl or wget is required" >&2
        exit 1
    fi
}

prepare_sources() {
    mkdir -p "$SRC_ROOT"
    local binutils_tar="${SRC_ROOT}/binutils-${BINUTILS_VERSION}.tar.xz"
    local gcc_tar="${SRC_ROOT}/gcc-${GCC_VERSION}.tar.xz"
    download "https://ftp.gnu.org/gnu/binutils/binutils-${BINUTILS_VERSION}.tar.xz" "$binutils_tar"
    download "https://ftp.gnu.org/gnu/gcc/gcc-${GCC_VERSION}/gcc-${GCC_VERSION}.tar.xz" "$gcc_tar"
    [[ -d "${SRC_ROOT}/binutils-${BINUTILS_VERSION}" ]] || tar -C "$SRC_ROOT" -xf "$binutils_tar"
    [[ -d "${SRC_ROOT}/gcc-${GCC_VERSION}" ]] || tar -C "$SRC_ROOT" -xf "$gcc_tar"
    (cd "${SRC_ROOT}/gcc-${GCC_VERSION}" && ./contrib/download_prerequisites)
}

build_one() {
    local arch="$1"
    local target
    target="$(triple_for_arch "$arch")"
    local prefix="${PREFIX_ROOT}/${target}"
    local stamp="${prefix}/.ok-toolchain-${BINUTILS_VERSION}-${GCC_VERSION}"

    if [[ -f "$stamp" ]]; then
        echo "[toolchain] ${target} already built at ${prefix}"
        sync_toolchain_include_layout "$prefix" "$target"
        return
    fi

    echo "[toolchain] building ${target}"
    mkdir -p "$BUILD_ROOT" "$prefix"

    local binutils_build="${BUILD_ROOT}/binutils-${target}"
    local gcc_build="${BUILD_ROOT}/gcc-${target}"
    local gcc_extra_flags=()
    rm -rf "$binutils_build" "$gcc_build"
    mkdir -p "$binutils_build" "$gcc_build"

    (
        cd "$binutils_build"
        "${SRC_ROOT}/binutils-${BINUTILS_VERSION}/configure" \
            --target="$target" \
            --prefix="$prefix" \
            --with-sysroot \
            --disable-nls \
            --disable-werror
        make -j"$JOBS"
        make install
    )

    (
        cd "$gcc_build"
        PATH="${prefix}/bin:${PATH}" "${SRC_ROOT}/gcc-${GCC_VERSION}/configure" \
            --target="$target" \
            --prefix="$prefix" \
            --disable-nls \
            --enable-languages=c,c++ \
            --without-headers \
            --disable-hosted-libstdcxx \
            --disable-libssp \
            --disable-libquadmath \
            --disable-libgomp \
            --disable-libstdcxx-pch \
            "${gcc_extra_flags[@]}"
        PATH="${prefix}/bin:${PATH}" make all-gcc all-target-libgcc all-target-libstdc++-v3 -j"$JOBS"
        PATH="${prefix}/bin:${PATH}" make install-gcc install-target-libgcc install-target-libstdc++-v3
    )

    sync_toolchain_include_layout "$prefix" "$target"
    touch "$stamp"
}

main() {
    prepare_sources
    if [[ "$ARCH" == "all" ]]; then
        for arch in x86_64 aarch64 rv64 loongarch64; do
            build_one "$arch"
        done
    else
        build_one "$ARCH"
    fi
}

main

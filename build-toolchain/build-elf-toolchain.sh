#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
project_root="$(cd -- "${script_dir}/.." >/dev/null 2>&1 && pwd)"

target=""
prefix=""
jobs="${JOBS:-$(nproc 2>/dev/null || getconf _NPROCESSORS_ONLN 2>/dev/null || echo 4)}"
binutils_version="${BINUTILS_VERSION:-2.42}"
gcc_version="${GCC_VERSION:-14.2.0}"
download_prerequisites="${DOWNLOAD_PREREQUISITES:-1}"
build_libstdcxx="${BUILD_LIBSTDCXX:-1}"

usage() {
    cat <<EOF
Usage: $(basename "$0") --target <x86_64-elf|aarch64-none-elf|riscv64-unknown-elf|loongarch64-unknown-elf> [--prefix <dir>] [--jobs <N>]

Environment:
  BINUTILS_VERSION         GNU binutils version (default: ${binutils_version})
  GCC_VERSION              GCC version (default: ${gcc_version})
  JOBS                     parallel build jobs (default: auto)
  DOWNLOAD_PREREQUISITES   1/0, run gcc contrib downloader (default: 1)
  BUILD_LIBSTDCXX          1/0, build freestanding target libstdc++ headers/runtime (default: 1)
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --target)
            target="${2:-}"
            shift 2
            ;;
        --prefix)
            prefix="${2:-}"
            shift 2
            ;;
        --jobs)
            jobs="${2:-}"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "error: unknown argument: $1" >&2
            usage
            exit 1
            ;;
    esac
done

if [[ -z "${target}" ]]; then
    echo "error: --target is required" >&2
    usage
    exit 1
fi

case "${target}" in
    x86_64-elf|aarch64-none-elf|riscv64-unknown-elf|loongarch64-unknown-elf) ;;
    *)
        echo "error: unsupported target: ${target}" >&2
        exit 1
        ;;
esac

if [[ -z "${prefix}" ]]; then
    prefix="${project_root}/build-toolchain/opt/${target}"
fi

tarball_dir="${project_root}/build-toolchain/tarballs"
src_dir="${project_root}/build-toolchain/src"
build_dir="${project_root}/build-toolchain/build"
stamp_dir="${project_root}/build-toolchain/stamps"

mkdir -p "${tarball_dir}" "${src_dir}" "${build_dir}" "${stamp_dir}" "${prefix}"

require_cmd() {
    command -v "$1" >/dev/null 2>&1 || {
        echo "error: required command not found: $1" >&2
        exit 1
    }
}

for cmd in make gcc g++ tar bison flex; do
    require_cmd "${cmd}"
done

download() {
    local url="$1"
    local out="$2"

    if [[ -f "${out}" ]]; then
        echo "[skip] tarball exists: ${out}"
        return
    fi

    echo "[download] ${url}"
    if command -v curl >/dev/null 2>&1; then
        curl -L --fail --retry 3 -o "${out}.part" "${url}"
    elif command -v wget >/dev/null 2>&1; then
        wget -O "${out}.part" "${url}"
    else
        echo "error: curl or wget is required for downloading sources" >&2
        exit 1
    fi
    mv "${out}.part" "${out}"
}

extract_if_missing() {
    local tarball="$1"
    local extracted_dir="$2"

    if [[ -d "${extracted_dir}" ]]; then
        echo "[skip] source exists: ${extracted_dir}"
        return
    fi

    echo "[extract] ${tarball}"
    tar -xf "${tarball}" -C "${src_dir}"
}

binutils_tar="binutils-${binutils_version}.tar.xz"
gcc_tar="gcc-${gcc_version}.tar.xz"
binutils_url="https://ftp.gnu.org/gnu/binutils/${binutils_tar}"
gcc_url="https://ftp.gnu.org/gnu/gcc/gcc-${gcc_version}/${gcc_tar}"

download "${binutils_url}" "${tarball_dir}/${binutils_tar}"
download "${gcc_url}" "${tarball_dir}/${gcc_tar}"

extract_if_missing "${tarball_dir}/${binutils_tar}" "${src_dir}/binutils-${binutils_version}"
extract_if_missing "${tarball_dir}/${gcc_tar}" "${src_dir}/gcc-${gcc_version}"

if [[ "${download_prerequisites}" == "1" ]]; then
    (
        cd "${src_dir}/gcc-${gcc_version}"
        if [[ ! -d gmp || ! -d mpfr || ! -d mpc ]]; then
            echo "[prepare] downloading gcc prerequisites"
            ./contrib/download_prerequisites
        else
            echo "[skip] gcc prerequisites already present"
        fi
    )
fi

binutils_build_dir="${build_dir}/binutils-${target}"
gcc_build_dir="${build_dir}/gcc-${target}"
binutils_stamp="${stamp_dir}/binutils-${target}-${binutils_version}.done"
gcc_stamp="${stamp_dir}/gcc-${target}-${gcc_version}.done"
libstdcxx_stamp="${stamp_dir}/libstdcxx-${target}-${gcc_version}.done"

gcc_supports_freestanding_libstdcxx() {
    local config_status="${gcc_build_dir}/config.status"
    [[ -f "${config_status}" ]] || return 1
    grep -q -- "--with-newlib" "${config_status}" || return 1
    grep -q -- "--disable-hosted-libstdcxx" "${config_status}" || return 1
    return 0
}

have_libstdcxx_headers() {
    local hdr1="${prefix}/${target}/include/c++/${gcc_version}/cstdint"
    local hdr2="${prefix}/${target}/include/c++/${gcc_version}/atomic"
    [[ -f "${hdr1}" && -f "${hdr2}" ]]
}

if [[ ! -f "${binutils_stamp}" ]]; then
    rm -rf "${binutils_build_dir}"
    mkdir -p "${binutils_build_dir}"
    (
        cd "${binutils_build_dir}"
        "${src_dir}/binutils-${binutils_version}/configure" \
            --target="${target}" \
            --prefix="${prefix}" \
            --with-sysroot \
            --disable-nls \
            --disable-werror
        make -j"${jobs}"
        make install
    )
    touch "${binutils_stamp}"
else
    echo "[skip] binutils already built (${binutils_version})"
fi

if [[ ! -f "${gcc_stamp}" ]]; then
    rm -f "${libstdcxx_stamp}"
    rm -rf "${gcc_build_dir}"
    mkdir -p "${gcc_build_dir}"
    (
        cd "${gcc_build_dir}"
        "${src_dir}/gcc-${gcc_version}/configure" \
            --target="${target}" \
            --prefix="${prefix}" \
            --disable-nls \
            --enable-languages=c,c++ \
            --without-headers \
            --with-newlib \
            --disable-hosted-libstdcxx \
            --disable-shared \
            --disable-threads \
            --disable-libstdcxx-pch \
            --disable-libstdcxx-verbose \
            --disable-libssp \
            --disable-libquadmath \
            --disable-libgomp \
            --disable-libmudflap \
            --disable-libsanitizer \
            --disable-libatomic \
            --disable-libvtv \
            --disable-multilib
        make -j"${jobs}" all-gcc all-target-libgcc
        make install-gcc install-target-libgcc
    )
    touch "${gcc_stamp}"
else
    echo "[skip] gcc already built (${gcc_version})"
fi

if [[ "${build_libstdcxx}" == "1" ]]; then
    if ! gcc_supports_freestanding_libstdcxx; then
        echo "[rebuild] gcc build config missing freestanding libstdc++ options"
        rm -f "${gcc_stamp}" "${libstdcxx_stamp}"
        rm -rf "${gcc_build_dir}"
        mkdir -p "${gcc_build_dir}"
        (
            cd "${gcc_build_dir}"
            "${src_dir}/gcc-${gcc_version}/configure" \
                --target="${target}" \
                --prefix="${prefix}" \
                --disable-nls \
                --enable-languages=c,c++ \
                --without-headers \
                --with-newlib \
                --disable-hosted-libstdcxx \
                --disable-shared \
                --disable-threads \
                --disable-libstdcxx-pch \
                --disable-libstdcxx-verbose \
                --disable-libssp \
                --disable-libquadmath \
                --disable-libgomp \
                --disable-libmudflap \
                --disable-libsanitizer \
                --disable-libatomic \
                --disable-libvtv \
                --disable-multilib
            make -j"${jobs}" all-gcc all-target-libgcc
            make install-gcc install-target-libgcc
        )
        touch "${gcc_stamp}"
    fi

    if [[ ! -f "${libstdcxx_stamp}" ]] || ! have_libstdcxx_headers; then
        (
            cd "${gcc_build_dir}"
            make -j"${jobs}" all-target-libstdc++-v3
            make install-target-libstdc++-v3
        )
        touch "${libstdcxx_stamp}"
    else
        echo "[skip] libstdc++ already built (${gcc_version})"
    fi
else
    echo "[skip] BUILD_LIBSTDCXX=0, skipping libstdc++ build"
fi

echo "[ok] bare-metal toolchain ready: ${prefix}"
echo "      add to PATH if needed: export PATH=\"${prefix}/bin:\$PATH\""

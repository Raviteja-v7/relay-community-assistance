#!/usr/bin/env bash
set -euo pipefail

backend_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
build_dir="${backend_dir}/.lambda-build"
package_file="${backend_dir}/relay_lambda.zip"

rm -rf "${build_dir}"
mkdir -p "${build_dir}"
cp -R "${backend_dir}/app" "${build_dir}/app"
find "${build_dir}" -type d -name __pycache__ -prune -exec rm -rf {} +
find "${build_dir}" -type f -name '*.pyc' -delete
rm -f "${package_file}"
(cd "${build_dir}" && zip -qr "${package_file}" .)
printf 'Built %s\n' "${package_file}"

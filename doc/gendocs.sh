#!/bin/bash
set -xeuo pipefail
rm -rf build/
rm -rf source/apidoc/
sphinx-apidoc -T -e -o source/apidoc ../src/commissaire_service/
sphinx-build -b html source build

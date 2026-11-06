cmake_minimum_required(VERSION 3.24)
project(cape_pins LANGUAGES CXX)

# ---------------------------------------------------------------------------
# CAPE-Pins native modules.
#   _crackle_vendor : pinned upstream Crackle (vendor/crackle) behind our own
#                     pybind11 glue; same compiler/flags as CAPE (spec s.20).
#   _cape_native    : CAPE encoder core (cpp/src, cpp/include/cape).
# Both are written into the `cape/` Python package directory.
# ---------------------------------------------------------------------------

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
endif()

set(PYBIND11_FINDPYTHON ON)
find_package(Python 3.12 REQUIRED COMPONENTS Interpreter Development.Module)
find_package(pybind11 CONFIG REQUIRED)

set(CRACKLE_VENDOR_DIR "${PROJECT_SOURCE_DIR}/vendor/crackle" CACHE PATH "Pinned upstream Crackle checkout")
if(NOT EXISTS "${CRACKLE_VENDOR_DIR}/src/crackle.hpp")
  message(FATAL_ERROR "vendor/crackle is missing: run scripts/fetch_sources.py first")
endif()

# Identical optimisation flags for CAPE and the vendor baseline. These match the
# upstream non-Windows setup.py flags (-O3 -msse4.2 -mpclmul); upstream's MSVC
# flags are used only if someone builds with MSVC.
if(MSVC)
  set(CAPE_OPT_FLAGS /O2 /arch:AVX2)
else()
  set(CAPE_OPT_FLAGS -O3 -msse4.2 -mpclmul)
endif()

function(cape_configure_module target)
  target_compile_options(${target} PRIVATE ${CAPE_OPT_FLAGS})
  if(MINGW)
    target_compile_definitions(${target} PRIVATE NOMINMAX)
    # Static C/C++ runtime: the .pyd must not depend on libstdc++/libgcc/winpthread DLLs.
    target_link_options(${target} PRIVATE -static)
  endif()
  set_target_properties(${target} PROPERTIES
    LIBRARY_OUTPUT_DIRECTORY "${PROJECT_SOURCE_DIR}/cape"
    LIBRARY_OUTPUT_DIRECTORY_RELEASE "${PROJECT_SOURCE_DIR}/cape")
endfunction()

# --- vendor baseline --------------------------------------------------------
pybind11_add_module(_crackle_vendor MODULE NO_EXTRAS cpp/bridge/crackle_vendor_bindings.cpp)
target_include_directories(_crackle_vendor PRIVATE
  "${CRACKLE_VENDOR_DIR}/src"
  "${CRACKLE_VENDOR_DIR}/third_party/fastcrc")
cape_configure_module(_crackle_vendor)

# --- optional: upstream HEAD (plan v2 P1.4: re-check format_audit F2, never a benchmark row) ---
set(CRACKLE_HEAD_DIR "${PROJECT_SOURCE_DIR}/vendor/crackle_head" CACHE PATH "Optional upstream HEAD checkout")
if(EXISTS "${CRACKLE_HEAD_DIR}/src/crackle.hpp")
  pybind11_add_module(_crackle_head MODULE NO_EXTRAS cpp/bridge/crackle_vendor_bindings.cpp)
  target_include_directories(_crackle_head PRIVATE
    "${CRACKLE_HEAD_DIR}/src"
    "${CRACKLE_HEAD_DIR}/third_party/fastcrc")
  target_compile_definitions(_crackle_head PRIVATE CRACKLE_MODULE_NAME=_crackle_head)
  cape_configure_module(_crackle_head)
endif()

# --- CAPE core ----------------------------------------------------------------
# Only cpp/src/upstream_bridge.cpp includes vendor headers (they define non-inline
# functions); the include path is target-wide but used by that single TU.
pybind11_add_module(_cape_native MODULE NO_EXTRAS
  cpp/src/bindings.cpp
  cpp/src/encoder.cpp
  cpp/src/runs.cpp
  cpp/src/candidates.cpp
  cpp/src/reductions.cpp
  cpp/src/incidence.cpp
  cpp/src/components.cpp
  cpp/src/greedy.cpp
  cpp/src/exact_dp.cpp
  cpp/src/local_search.cpp
  cpp/src/dual_bound.cpp
  cpp/src/byte_model.cpp
  cpp/src/serializer.cpp
  cpp/src/upstream_bridge.cpp)
target_include_directories(_cape_native PRIVATE
  "${PROJECT_SOURCE_DIR}/cpp/include"
  "${CRACKLE_VENDOR_DIR}/src"
  "${CRACKLE_VENDOR_DIR}/third_party/fastcrc")
cape_configure_module(_cape_native)

if(SKBUILD)
  install(TARGETS _crackle_vendor _cape_native LIBRARY DESTINATION cape)
endif()

# Standalone Antiprism Addons C++ build (no Autotools or GLUT)
# Use an EXISTING configured/compiled Antiprism source tree and library.
#
# Examples:
#   make  # defaults to $HOME/antiprism_rk
#   make BUILD_KIND=mingw ANTIPRISM_ROOT=$HOME/antiprism \
#        ANTIPRISM_BUILD_ROOT=$HOME/antiprism-cross-build
#   make -j4
#   make kaleido  # build one selected program
#
# CPPFLAGS/CXXFLAGS/LDFLAGS/LDLIBS can be extended on the make command line.
# No configure/bootstrap or build of Antiprism is run from this file.

.DEFAULT_GOAL := all

ANTIPRISM_ROOT ?= $(HOME)/antiprism_rk
ANTIPRISM_BUILD_ROOT ?= $(ANTIPRISM_ROOT)
ANTIPRISM_LIBDIR ?= $(ANTIPRISM_BUILD_ROOT)/base/.libs
# Optional explicit full library path: ANTIPRISM_LIB=/path/libantiprism.a
ANTIPRISM_LIB ?=

BUILD_KIND ?= native
PREFIX ?= /usr/local
DESTDIR ?=
CXXFLAGS ?= -O2 -Wall -Wextra

ifeq ($(BUILD_KIND),mingw)
  # Cross-build from Cygwin or Linux with x86_64-w64-mingw32-g++.
  ifeq ($(origin CXX),default)
    CXX := x86_64-w64-mingw32-g++
  endif
  EXEEXT := .exe
  PLATFORM_LDFLAGS := -static -static-libgcc -static-libstdc++
  PLATFORM_LIBS := -lpthread
else ifeq ($(BUILD_KIND),native)
  # g++ normally adds .exe automatically when compiling within Cygwin.
  ifneq ($(findstring CYGWIN,$(shell uname -s)),)
    EXEEXT := .exe
  endif
else
  $(error BUILD_KIND must be native or mingw)
endif

# Antiprism addon sources use literal includes such as ../base/antiprism.h.
# Pointing the include search at Antiprism's src/ allows these unchanged
# relative includes to resolve there, without copying Adrian's headers.
ANTI_INCLUDES := -I"$(ANTIPRISM_ROOT)/src" -I"$(ANTIPRISM_ROOT)/base"
# Use the header configuration corresponding to the binary library.
ifneq ($(wildcard $(ANTIPRISM_BUILD_ROOT)/config.h),)
  ANTI_CONFIG := -DHAVE_CONFIG_H -I"$(ANTIPRISM_BUILD_ROOT)"
endif

BUILD_DIR := build/$(BUILD_KIND)
PROGRAM_NAMES := alt_color off_sym kaleido
PROGRAMS := $(addprefix $(BUILD_DIR)/,$(addsuffix $(EXEEXT),$(PROGRAM_NAMES)))

ifeq ($(strip $(ANTIPRISM_LIB)),)
  ANTI_LINK := -L"$(ANTIPRISM_LIBDIR)" -lantiprism
else
  ANTI_LINK := "$(ANTIPRISM_LIB)"
endif

.PHONY: all check-config check-library install clean help $(PROGRAM_NAMES)

all: $(PROGRAMS)

help:
	@echo 'Antiprism Addons standalone C++ build'
	@echo '  make [BUILD_KIND=native|mingw] ANTIPRISM_ROOT=/path/to/source'
	@echo '  make BUILD_KIND=mingw ANTIPRISM_BUILD_ROOT=/path/to/cross/build'
	@echo '  make kaleido             # build one program'
	@echo '  make clean               # only removes our build/ directory'
	@echo '  make install PREFIX=/usr/local'

check-library:
	@if [ -n "$(ANTIPRISM_LIB)" ]; then \
	  test -f "$(ANTIPRISM_LIB)" || { echo 'Missing ANTIPRISM_LIB: $(ANTIPRISM_LIB)' >&2; exit 1; }; \
	else \
	  found=no; \
	  for file in "$(ANTIPRISM_LIBDIR)"/libantiprism.so* \
	              "$(ANTIPRISM_LIBDIR)"/libantiprism.a \
	              "$(ANTIPRISM_LIBDIR)"/libantiprism.dll.a \
	              "$(ANTIPRISM_LIBDIR)"/libantiprism.dll; do \
	    if test -f "$$file"; then found=yes; break; fi; \
	  done; \
	  test "$$found" = yes || { \
	    echo 'No linkable Antiprism library in $(ANTIPRISM_LIBDIR)' >&2; \
	    echo 'Build Antiprism separately first, then set' >&2; \
	    echo 'ANTIPRISM_BUILD_ROOT, ANTIPRISM_LIBDIR or ANTIPRISM_LIB.' >&2; \
	    exit 1; \
	  }; \
	fi

check-config: check-library
	@test -f "$(ANTIPRISM_ROOT)/base/antiprism.h" || { \
	  echo 'Missing $(ANTIPRISM_ROOT)/base/antiprism.h' >&2; exit 1; }
	@test -f "$(ANTIPRISM_ROOT)/src/color_common.h" || { \
	  echo 'Missing $(ANTIPRISM_ROOT)/src/color_common.h' >&2; exit 1; }
	@test -f "$(ANTIPRISM_ROOT)/src/color_common.cc" || { \
	  echo 'Missing $(ANTIPRISM_ROOT)/src/color_common.cc' >&2; exit 1; }
	@test -f "$(ANTIPRISM_ROOT)/src/help.h" || { \
	  echo 'Missing $(ANTIPRISM_ROOT)/src/help.h' >&2; exit 1; }

$(BUILD_DIR):
	@mkdir -p "$@"

# Use Antiprism's color_common.cc only for alt_color; the library itself
# is linked prebuilt. The other three programs need no extra source.
$(BUILD_DIR)/color_common.o: $(ANTIPRISM_ROOT)/src/color_common.cc $(ANTIPRISM_ROOT)/src/color_common.h | $(BUILD_DIR) check-config
	$(CXX) $(CPPFLAGS) $(ANTI_INCLUDES) $(ANTI_CONFIG) $(CXXFLAGS) -c "$<" -o "$@"

$(BUILD_DIR)/%.o: %.cc | $(BUILD_DIR) check-config
	$(CXX) $(CPPFLAGS) $(ANTI_INCLUDES) $(ANTI_CONFIG) $(CXXFLAGS) -c "$<" -o "$@"

$(BUILD_DIR)/alt_color$(EXEEXT): $(BUILD_DIR)/alt_color.o $(BUILD_DIR)/color_common.o | check-config
	$(CXX) $(LDFLAGS) $(PLATFORM_LDFLAGS) -o "$@" $^ $(ANTI_LINK) $(LDLIBS) $(PLATFORM_LIBS)

$(BUILD_DIR)/off_sym$(EXEEXT): $(BUILD_DIR)/off_sym.o | check-config
	$(CXX) $(LDFLAGS) $(PLATFORM_LDFLAGS) -o "$@" $^ $(ANTI_LINK) $(LDLIBS) $(PLATFORM_LIBS)

$(BUILD_DIR)/kaleido$(EXEEXT): $(BUILD_DIR)/kaleido.o | check-config
	$(CXX) $(LDFLAGS) $(PLATFORM_LDFLAGS) -o "$@" $^ $(ANTI_LINK) $(LDLIBS) $(PLATFORM_LIBS)

$(PROGRAM_NAMES): %: $(BUILD_DIR)/%$(EXEEXT)

install: all
	install -d "$(DESTDIR)$(PREFIX)/bin"
	@for prog in $(PROGRAMS); do \
	  install -m 755 "$$prog" "$(DESTDIR)$(PREFIX)/bin/" || exit 1; \
	done

clean:
	rm -rf build

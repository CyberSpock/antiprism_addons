# C++ addons (standalone build)

The beta repository includes three C++ programs:
`alt_color`, `off_sym`, and `kaleido`.

These are **not** bundled into the Python wheel. They use Adrian Rossiter's
Antiprism C++ library and need compatible source headers plus an already-built
`libantiprism`. They do not rebuild Antiprism, run `configure`, or need GLUT.

From this directory:

```sh
make ANTIPRISM_ROOT="$HOME/antiprism_rk"
```

For native Windows `.exe` executables compiled with MinGW:

```sh
make BUILD_KIND=mingw ANTIPRISM_ROOT="$HOME/antiprism_rk"
```

The Antiprism library **must be built for the same target compiler**. A
MinGW-built `libantiprism.a` is not compatible with native Cygwin `g++`.
The Makefile separates object files into `build/native/` and `build/mingw/`.
Override `ANTIPRISM_BUILD_ROOT`, `ANTIPRISM_LIBDIR`, or `ANTIPRISM_LIB` if the
library is built separately from the Antiprism source tree.

```sh
make help
make kaleido
make install PREFIX=/usr/local
make clean
```

The `kaleido.cc` source retains portions of Dr. Zvi Har'El's work and its
original redistribution conditions. The required acknowledgment is:

> This product includes software developed by
> Dr. Zvi Har'El (http://www.math.technion.ac.il/~rl/).

All individual C++ source license notices remain intact. Do not interpret the
root Python 0BSD license as superseding those notices.

`off_cong` is deliberately deferred pending review of `off_coin`.

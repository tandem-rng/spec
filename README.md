<p align="center"><img src="assets/lockup.png" width="560" alt="tandem rng"></p>

# Tandem8x32 specification

Tandem is a noncryptographic pseudorandom number generator built to be fast on CPUs and GPUs alike:
eight 32-bit words, a hidden clock, and a Philox-shaped Feistel layer whose multipliers
come from the hidden half.

- `SPEC.md` is the normative specification. Every implementation conforms to it.
- `vectors.json` holds the test vectors of `SPEC.md` section 8 as machine-readable data.
  An implementation's test suite reads this file and checks every entry.
- `tables/normal_f64_zig1024.json` holds the ziggurat tables of the Float64 normals in `SPEC.md` Appendix A.
  `tools/gen_zig_tables.py` derives them with mpmath, and CI checks the committed file with `--check`.
- Fixtures for normals come from tandem-c `tests/cross_normal.h`.

## Implementations

| language | repository | status |
|---|---|---|
| Julia | [TandemRNG.jl](https://github.com/tandem-rng/TandemRNG.jl) | reference, complete |
| C, C++17 | [tandem-c](https://github.com/tandem-rng/tandem-c) | reference, complete |
| Rust | [tandem-rs](https://github.com/tandem-rng/tandem-rs) | complete, `rand_core` traits |
| Python | [tandem-numpy](https://github.com/tandem-rng/tandem-numpy) | NumPy `BitGenerator` over tandem-c |
| CUDA | [tandem-cuda](https://github.com/tandem-rng/tandem-cuda) | device header, row fill kernel |
| JAX | [tandem-jax](https://github.com/tandem-rng/tandem-jax) | `jax.random` key implementation |
| R | [tandem-r](https://github.com/tandem-rng/tandem-r) | package `tandemrng` over tandem-c, base R hook |
| PyTorch | [tandem-torch](https://github.com/tandem-rng/tandem-torch) | CPU and CUDA extension |
| WebGPU | [tandem-webgpu](https://github.com/tandem-rng/tandem-webgpu) | WGSL shader, TypeScript package |
| Fortran | [tandem-fortran](https://github.com/tandem-rng/tandem-fortran) | module over tandem-c, CUDA Fortran device fills |
| Kokkos | [tandem-kokkos](https://github.com/tandem-rng/tandem-kokkos) | header over the shared device core, `fill(view, rng)` |
| Java | [tandem-java](https://github.com/tandem-rng/tandem-java) | pure Java `RandomGenerator`, CUDA module through FFM |
| Mojo | [tandem-mojo](https://github.com/tandem-rng/tandem-mojo) | complete, polynomial normals |
| SYCL | [tandem-sycl](https://github.com/tandem-rng/tandem-sycl) | header over the shared device core, any SYCL device |

Float64 normals move from Box-Muller to the ziggurat of Appendix A: tandem-c first, then tandem-cuda, then the other ports.

## License

Apache License 2.0. See `LICENSE` and `NOTICE`.

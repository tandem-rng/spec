<p align="center"><img src="assets/lockup.png" width="560" alt="tandem rng"></p>

# Tandem8x32 specification

Tandem is a noncryptographic pseudorandom number generator built to be fast on CPUs and GPUs alike:
eight 32-bit words, a hidden clock, and a Philox-shaped Feistel layer whose multipliers
come from the hidden half.

- `SPEC.md` is the normative specification. Every implementation conforms to it.
- `vectors.json` holds the test vectors of `SPEC.md` section 8 as machine-readable data.
  An implementation's test suite reads this file and checks every entry.

## Implementations

| language | repository | status |
|---|---|---|
| Julia | [TandemRNG.jl](https://github.com/tandem-rng/TandemRNG.jl) | reference, complete |
| C, C++17 | [tandem-c](https://github.com/tandem-rng/tandem-c) | reference, complete |
| Rust | [tandem-rs](https://github.com/tandem-rng/tandem-rs) | complete, `rand_core` traits |
| Python | [tandem-numpy](https://github.com/tandem-rng/tandem-numpy) | NumPy `BitGenerator` over tandem-c |
| CUDA | [tandem-cuda](https://github.com/tandem-rng/tandem-cuda) | device header, row fill kernel |
| JAX | [tandem-jax](https://github.com/tandem-rng/tandem-jax) | `jax.random` key implementation |

## License

Apache License 2.0. See `LICENSE` and `NOTICE`.

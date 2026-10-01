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
| C | [tandem-c](https://github.com/tandem-rng/tandem-c) | reference, scalar, complete |

## License

Apache License 2.0. See `LICENSE` and `NOTICE`.

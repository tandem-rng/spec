# Statistics of the derived draws

PractRand 0.96 and TestU01 BigCrush results for the derived draws of Appendices A and C, as
tandem-c [`bfa762d`](https://github.com/tandem-rng/tandem-c/commit/bfa762d7c1a99827db20ba71bee99728612b0073)
produces them, and the Float32 exponential also as tandem-c
[`1c75956`](https://github.com/tandem-rng/tandem-c/commit/1c75956c39581836c1f6e190d1072c9a43be6b0d)
produces it, with the two-float logarithm that this specification's fixtures follow. The uniform
stream has its own evidence, linked from TandemRNG.jl. Every draw starts from
`tandem_seed(12345, 0, 0)` at position 0.

## Method

PractRand and TestU01 test uniform bits. tandem-c `tools/dump_derived.c` maps each draw x back
to a uniform u by its probability integral transform, which is uniform exactly when x follows
its law, and packs the top bits of each u into one stream. V is a Float64 uniform from an
independent sub-stream that spreads a discrete draw over its atom.

| draw | map to u | bits |
|---|---|---|
| Float64 normal (ziggurat) | Φ(x) | 52 |
| Float64 exponential | 1 − exp(−x) | 32 |
| `u64_below`, n = ⌊2^64 · 2/3⌋ ≈ 2^63.4 | ⌊i · 2^52 / n⌋, exact integer arithmetic, no V since n ≫ 2^52 | 52 |
| `u32_below`, n = ⌊2^32 · 2/3⌋ | (i + V) / n | 32 |
| choice, w(i) = 1/(i + 1), m = 1000 | (C(i) + V p(i)) / (m S), with C and p from the table's own masses | 32 |
| Float32 normal (Box-Muller) | Φ, spread by V over the float's rounding cell | 16 |
| Float32 exponential | (j + V) 2^−24, with j the grid point nearest 1 − exp(−x) | 16 |

Both bounded ranges reject a third of their draws, so a third of their values come from the
fallback streams. The Float64 exponential runs at 32 bits because its error of up to
1.1e−15 moves a tenth of the draws by one 2^−52 step, which biases bit 0 of a 52-bit u.

Two controls take the same Float32 uniforms through double-precision libm and round once to
float, the best law a Float32 draw can have on 24-bit uniforms. They run in PractRand at the
bits of the draws they control, the exponential control at 32 bits.

PractRand runs the core battery on `stdin64` for the 52-bit streams and `stdin32` otherwise,
with results at every doubling from 2^20 bytes. BigCrush reads the same streams as 32-bit
words.

## PractRand

| draw | bytes | verdict | flagged results, none at or above "suspicious" unless named |
|---|---|---|---|
| Float64 normal | 2^40 | pass | 2^32 `DC6-9x1Bytes-1` unusual |
| Float64 exponential | 2^40 | pass | 2^24 `Gap-16:A` mildly suspicious, 2^40 `DC6-9x1Bytes-1` unusual |
| `u64_below` | 2^40 | pass | 2^34 `BCFN(2+0,13-2U)` unusual |
| `u32_below` | 2^40 | pass | 2^40 `BCFN(2+0,13-0U)` unusual |
| choice | 2^40 | pass | none |
| Float32 normal | 2^38 | **fail from 2^35** | `FPF/16:(15,14-k)` FAIL from 2^35, p = 2.6e−162 at 2^38 |
| Float32 normal, control | 2^38 | **fail from 2^35** | the same failing test, p = 1.7e−162 at 2^38 |
| Float32 exponential | 2^38 | **fail from 2^37** | `FPF/16` exponents 0 to 2, suspicious at 2^36, FAIL from 2^37, p = 5.3e−37 at 2^38 |
| Float32 exponential, control | 2^38 | pass | 2^30 `mod3n(5)` unusual |
| Float32 exponential, tandem-c `1c75956` | 2^38 | pass | 2^28 `DC6-9x1Bytes-1` unusual, 2^29 `BCFN(2+3,13-2U)` unusual |

The Float32 exponential of `1c75956` passes at every one of its 19 checkpoints from 2^20 to 2^38,
at the 16 bits of the release run, where that of `bfa762d` fails from 2^37. Between the two
commits tandem-c changed its scalar draw cache and fill loops but not its bounded draws, and the
first 2^32 bytes of the `u64_below` and `u32_below` streams are identical. So their results hold
for `1c75956` too.

## BigCrush

All seven draws pass, at the bits of the table above. That is 1064 p-values, with release
interval [α, 1 − α] and α = 0.001 / 1064, a Bonferroni correction over the whole matrix. No
p-value falls outside it. One p-value falls outside [0.001, 0.999], where about two are expected
by chance: choice, test 60, p = 1.8e−4.

## Weighted choice: the index stream

A skewed table resolves only a few bits of the index, so the transform above tests mostly V.
The index stream gets a direct test of its own over the first 2^34 indices, against the table
probabilities q(i) / (m S). These differ from the law of the draws by less than m 2^−58 in total
variation.

| statistic | χ² | df | p |
|---|---|---|---|
| category counts | 1060.5 | 999 | 0.086 |
| non-overlapping lag-1 pair counts | 1000598.1 | 999999 | 0.336 |

Every pair cell expects at least 153 counts.

## Properties of the Float32 samplers

These are properties of the samplers, which the tests find. They are not artifacts of the
mapping.

**Float32 normal: the 24-bit grid of Box-Muller.** z0 and z1 of a pair come from two uniforms
on a 2^−24 grid. PractRand finds this structure in tandem's draws and equally in the control,
which is correctly rounded from the same uniforms:

| bits of u | draw fails from | control fails from |
|---|---|---|
| 32 | 2^32 | 2^32 |
| 24 | 2^33 | 2^34 |
| 16 | 2^35 | 2^35 |

At 16 bits the failing test, `FPF/16` at exponent 15, joins a deep left-tail value with the bits
of the value after it. Two probes to 2^36 at 16 bits locate the cause. Neither fails, and one
result between them is flagged, as unusual:

- the cos halves alone, which drops the pairing;
- the same Box-Muller from 53-bit uniforms, which drops the grid.

The structure therefore needs both halves of a pair on the 24-bit grid. Coarser checks show
nothing. Over 2^30 draws per half, the mass below u = 2^−16 and between 2^−16 and 2^−15
matches the normal law within about one standard error. Given a first half below u = 2^−15,
the second half's u in 16 bins gives χ² = 19.4 on 15 df.

A second property is an atom at zero. z0 is exactly ±0 when b lies on a quarter turn, and z1
when b is 0 or 1/2, so each half is ±0 with probability 2^−23. A sample of 2^28 draws holds
36 zeros against 32 expected. The rounded normal law would give almost none. No test above
flags it at 16 bits.

**Float32 exponential: its error, not its grid.** The control passes at 32 bits to 2^38 bytes.
tandem's draw fails from 2^29 at 32 bits, from 2^25 at 24 bits, and from 2^37 at the 16 bits
of the release run. Its error against −log1p(−a) in double over 2^28 draws, by binade of x:

| x | max relative error | max ulps | draws off their grid point |
|---|---|---|---|
| 2^−24 to 2^−12 | 8.8e−8 | 1.0 | 0 |
| 2^−12 to 0.25 | 2.1e−7 | 2.6 | 0 |
| 0.25 to 0.5 | 2.76e−7 | 3.2 | 5.55 % |
| 0.5 to 1 | 1.30e−7 | 1.4 | 0.10 % |
| 1 to 2 | 1.35e−7 | 1.2 | 0.76 % |
| 2 to 32 | 1.1e−7 | 1.0 | 0 |

A draw off its grid point is one whose 1 − exp(−x) lies nearer a neighbouring 2^−24 grid point
than its own uniform a. Those draws fall at x from 0.25 to 2, where u lies between 0.22 and 0.86.
These are the u values of the failing `FPF/16` exponents 0 to 2. These results are for
`bfa762d`.

tandem-c `1c75956` carries the leading term of the logarithm in two floats and adds k ln 2 by
an exact two-sum, with the same single draw. Over all 2^24 Float32 uniforms its error is at most
0.571 ulp, and no draw lies off its grid point. Its PractRand run passes to 2^38 at 16 bits, see
above.

## Records

The evidence is outside git, on the host of the validation campaign, under
`TandemRNG-validation-evidence/bfa762d-derived/`:

- `practrand/`: one directory per case with the PractRand log, the command, the exit codes, and
  a summary of the producer's first words, the hashes and every checkpoint.
- `bigcrush/` and `bigcrush-matrix.log`: every p-value with its release classification.
- `choice-counts.txt`: the index-stream test.
- `probes-2p34/`: the probes that chose the bits, and the two cause probes.
- `diagnostics/`: the error table, the tail mass and the pair test.

The Float32 exponential of `1c75956` has its own case directory under
`TandemRNG-validation-evidence/1c75956-derived/practrand/`, from a copy of the harness with
`dump_derived` built from `1c75956`.

The harnesses are copies of the PureRNGs PractRand and RNGTest harnesses at `c887861`, with the
producer replaced by `tools/dump_derived` built with clang 19 and the validators kept. The pins
are:

- `dump_derived` SHA-256 `e9b09a0fb0a7fa89e8cac331ff9ea69155287d5404d3e8f6dcb68a35560fdecd`, and
  `9822107b254579c4023d3e1980cbd8404de6ac6c8d2ed009855cb3350097a132` for `1c75956`
- tandem-c source, the vendored `tandem.c`, `tandem.h`, `tandem_normal_tables.h` and
  `tools/dump_derived.c` of `1c75956`:
  `c15b6c93a2297c3b602e3aa4e444ca31f4dba887b0b7a31a678fcc3c127e632d`
- PractRand 0.96 binary `e771559e82e935df5a111a64537e7c3173467c0d32f5769eea4701ca7629481b`
- RNGTest source `c5ba87e601730f6c996a226be3c541f2ad5564fbf7ef8a74d4ba8fe647a9e1d9`
- TestU01_jll 1.2.3 tree `f9d515229567f365d65b18f76a8d1442c3005ab0`

The `bfa762d` validator hashed an empty list of source files, so its pinned source hash, the
SHA-256 of a newline, checked no source. The `1c75956` copy hashes the four files above.

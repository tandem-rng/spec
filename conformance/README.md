# Conformance fixtures

These files hold the cross-implementation fixtures of the derived draws in `SPEC.md` Appendix A, and the hashes of the long reference outputs.
Every port's test suite reads them, so a fixture changes in one place.
`CHECKLIST.md` lists the behaviours every port demonstrates.

The data comes from tandem-c at commit `1adf2aca3926c96c3f22ea03c4a5cf2bdbb65acc`.
`tools/gen_conformance.py` derives every file from that checkout: it parses the fixture headers in `tests/`, hashes `tests/data`, and builds and runs the dump tools.
CI runs it with `--check` against tandem-c at the pinned commit.

```sh
python3 tools/gen_conformance.py --tandem-c ../tandem-c          # write
python3 tools/gen_conformance.py --tandem-c ../tandem-c --check  # verify
```

To move the pin, change `PIN` in the script and the commit above, then regenerate.

## Files

| file | source in tandem-c | content |
|---|---|---|
| `below.json` | `tests/cross_below.h` | scalar bounded draws |
| `fill_below.json` | `tests/cross_fill_below.h`, `tests/cuda_fill_below.h` | bounded fills |
| `normal.json` | `tests/cross_normal.h`, `tests/cuda_fill_normal.h` | Float64 ziggurat and Float32 Box-Muller fills |
| `exponential.json` | `tests/cross_exponential.h` | exponential fills |
| `choice.json` | `tests/cross_choice.h`, and `vectors.json` of this repository | weighted choice fills, Appendix C |
| `hashes.json` | `tests/data`, `tools/dump_*.c`, `tests/test_*_bits.c` | SHA-256 and FNV-1a of long outputs |

## Cases

`below.json`, `fill_below.json`, `normal.json`, `exponential.json` and `choice.json` hold a list `cases`.
Each case has these fields:

| field | meaning |
|---|---|
| `id` | the source header, array and index |
| `kind` | the operation, see below |
| `key` | four key words, 8-digit hexadecimal strings |
| `K` | the chunk length |
| `start` | the bit position of the generator before the operation |
| `range` | the bound of a bounded draw, a hexadecimal string of `w / 4` digits |
| `weights` | the weights of a choice, as the IEEE 754 bits of Float64 |
| `capacity` | the column capacity `S` of the choice table, 16 hexadecimal digits |
| `cut`, `alias` | the choice table, 16 and 8 hexadecimal digits per entry, on the cases from `vectors.json` |
| `n` | the number of elements |
| `values` | the expected elements as bit patterns: `w / 4` hexadecimal digits for integers, the IEEE 754 bits for floats |
| `end` | the position after the operation, when the source pins it |
| `rejected` | the number of elements that took the fallback, when the source records it |
| `tol` | present on Float32 normals and exponentials: `{"ulps": 16, "abs": 1e-6}` |

Positions and counts are JSON integers below `2^53`.
The key `421d21eb 32d31777 62e7564b df2bdf82` is the key of integer seed 42, `SPEC.md` section 8.

| kind | operation |
|---|---|
| `below_u32`, `below_u64` | `n` scalar bounded draws in sequence, width 32 or 64 |
| `fill_below_u32`, `fill_below_u64` | one bounded fill of `n` elements, width 32 or 64 |
| `fill_normal_f64`, `fill_normal_f32` | one normal fill of `n` elements |
| `fill_exponential_f64`, `fill_exponential_f32` | one exponential fill of `n` elements |
| `fill_choice` | one weighted choice fill of `n` elements, values are UInt32 indices |

A case with `n = 0` has empty `values` and checks only `end`.
A scalar draw of a fill kind equals element 0 of the fill, so the fill cases also check the scalar draws.
Compare every value bit for bit, except where `tol` is present.
There a value `y` passes against the fixture `x` when `|y − x| ≤ 16 · 2^−23 · |x| + 1e−6`.
A port that copies the C polynomials matches those values bit for bit too.
A device that takes a fast intrinsic for the angle uses `2.1e-6` as the absolute floor, see "Agreement" in Appendix A.

## Hashes

`hashes.json` has two lists.

`streams` describes the uniform fills in tandem-c `tests/data`: `key`, `K`, `start`, element `type`, `n`, `bytes` and `sha256`.
The bytes are little-endian.
Bool is one byte, 0 or 1. Float16 is its 16 bits. Char is its code point as UInt32. A complex element is the real component, then the imaginary one, and `n` counts complex elements.

`dumps` describes long derived outputs.
For each position in `starts`, build the generator from `key` and `K` at that position, then run the fills of `draws` in order on that one generator.
Concatenate the output bytes over all starts.
`fnv1a` is the 64-bit FNV-1a hash of those bytes, `sha256` their SHA-256, `bytes` their length, and `end` the final position when present.
`seed` is the integer seed of `key` as 32 hexadecimal digits.
The Float32 normal hash holds only for a port that copies the C polynomials.

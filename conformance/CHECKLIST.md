# Port checklist

Every port's test suite demonstrates each behaviour below.
A case name such as `CROSS_BELOW32[4]` is the end of an `id` in the JSON files of this directory.
`w` is the draw width, and `align(p, w)` is `p` rounded up to a multiple of `w`.

## Fallback by global draw index

A rejected bounded element and a missed Float64 normal retry on a fallback keyed by `g = align(start, w) / w + i`, not by the element index `i`.

- Check every case of `fill_below.json` and `normal.json`. The cases with `rejected > 0` and `CROSS_NORMAL[3]` to `CROSS_NORMAL[5]` take the fallback.
- Check that element `i` of `CROSS_BELOW32_AT[4]` (start 1) equals element `i + 1` of `CROSS_BELOW32[4]` (start 0). `CROSS_BELOW64_AT[6]` and `CROSS_BELOW64[6]`, and `CROSS_NORMAL[1]` and `CROSS_NORMAL[0]`, relate the same way.

## Width from range

An interface that names only the result type draws with `w = 32` when `range ≤ 2^32`, else with `w = 64`.

- Draw 64 elements with range 1000 into a 64-bit result type from the key of seed 42 at position 0. Expect the values of `CROSS_BELOW32[3]`, not of `CROSS_BELOW64[3]`.
- Check that an interface that names the width, such as a `u64` bounded fill, matches `CROSS_BELOW64[3]`.
- Check that range 0 returns 0 and consumes one draw of width `w`.

## n = 0

- An empty uniform fill, Float64 normal fill or weighted choice fill moves the position to `align(start, w)` and writes nothing.
- An empty bounded, Float32 normal or exponential fill leaves the position unchanged, as Appendix A states.
- Check the seven cases with `n = 0` in `fill_below.json`, `normal.json`, `exponential.json` and `choice.json`, which start at 33.

## Odd n

A Float32 normal fill of odd `n` writes the cos half of the last pair and drops its sin half.
It still consumes both uniform draws.

- Check `CROSS_NORMAL32[0]` to `CROSS_NORMAL32[4]`, where `n = 33`.
- Check the end position `align(start, 32) + 32 · 2 · ceil(n / 2)`, for example 1088 after `CROSS_NORMAL32[0]`.

## Pair rule for Float32 Box-Muller

Element `2j` is the cos half and element `2j + 1` the sin half of uniform draws `2j` and `2j + 1`.

- Check `CROSS_NORMALF`, 64 pairs from start 1 that end at 4128.
- Check that the first 33 values of `CROSS_NORMALF` equal `CROSS_NORMAL32[1]`.
- Check that a scalar Float32 normal returns the cos half and consumes two draws.
- Check that element `i` of `CROSS_NORMAL32[2]` equals element `i + 2` of `CROSS_NORMAL32[0]`: a start one pair later shifts the output by one pair.

## Weighted choice

Element `i` of a choice fill maps UInt64 draw `i` through the alias table, with no retry.
Each element consumes exactly 64 bits.

- Build the table of each `vectors.json` case in `choice.json` and compare `capacity`, `cut` and `alias`.
- Check every case of `choice.json`, values and end position.
- Check that element `i` of `CROSS_CHOICE[1]` (start 1) equals element `i + 1` of `CROSS_CHOICE[0]` (start 0).
- Check that a scalar choice equals element 0 of a fill and consumes 64 bits, and that `m = 1` returns 0.
- Check that an empty choice fill aligns the position to 64, the `n = 0` case of `choice.json`.
- Check that a negative, infinite or NaN weight builds no table, and that weights that are all zero build none.

## Cut fill

A fill cut at any element boundary equals the whole fill and ends at the same position.

- Cut every case of `fill_below.json`, `normal.json`, `exponential.json` and `choice.json` at elements 1, 7, 20, 21 and `n − 1`. Fill the pieces in order on one generator.
- Element 20 of `CROSS_NORMAL[3]` to `CROSS_NORMAL[5]` is a miss, so the cuts at 20 and 21 fall at and after a fallback.
- Check that `n` scalar draws equal each Float64 normal and each exponential fill case, with the same end.

## Block and 2^63 position boundaries

- Check the stream hashes in `hashes.json`. They cross 128-bit blocks, 1024-bit rows and chunks, and `k1234_K8_u32.bin` crosses a chunk every 8 rows.
- Check that a complex draw whose real part ends a block takes its imaginary part from the next block.
- Check that random access to any position equals the sequential fill at that position, across block, row and chunk boundaries.
- Check that a generator accepts start `2^63 − 1` and rejects starts `2^63` and `2^64 − 1` without changing state.
- Check that a UInt64 draw at `2^63 − 1` aligns to `2^63` and returns position `2^63 + 64`.
- Check that a fill whose end `align(p, w) + w · n` reaches `2^64` fails before it writes output.

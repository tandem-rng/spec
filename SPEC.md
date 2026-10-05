# Tandem8x32 specification

Use Tandem8x32 for noncryptographic pseudorandom number generation.
Implement the canonical variant `Tandem8x32-K32` with `K = 32`.
Identify other supported chunk lengths as `Tandem8x32-K<k>`.

## 1. Words and state

Use unsigned 32-bit words and the following operations:

| Notation | Operation |
| --- | --- |
| `+` on words | Addition modulo 2^32 |
| `⊕` | Bitwise xor |
| `\|` | Bitwise or |
| `&` | Bitwise and |
| `~` | Bitwise complement |
| `>>` | Logical right shift |
| `rotl(x, r)` | Rotate the 32-bit word `x` left by `r` bits |
| `x · y` on words | Full unsigned 64-bit product |
| `hi(p)` | Upper 32 bits of a 64-bit product |
| `lo(p)` | Lower 32 bits of a 64-bit product |
| `÷` | Integer division |
| `mod` | Nonnegative remainder |

Represent a state as `(o, h)`, with four words in each half.
Name the exposed words `o = (o0, o1, o2, o3)`.
Name the hidden words `h = (h0, h1, h2, h3)`.
Use zero-based word, bit, block, lane, row, and child indices.

Encode each word `w` as four little-endian bytes:

```
w mod 256, (w >> 8) mod 256, (w >> 16) mod 256, w >> 24
```

Form a 16-byte block by concatenating the bytes of `o0`, `o1`, `o2`, and `o3`.
Number each word's bits from its least significant bit.

## 2. Constants

Use these constants:

| name | value | use |
|---|---|---|
| `CLOCK_ROT` | (7, 13, 22, 3) | rotations of the clock |
| `CLOCK_WEYL` | 0x9e3779b9 | Weyl increment of the clock |
| `LO_ROTATION` | 16 | rotation of the low product word |
| `RF` | 8 | rounds of F |
| `RC[1..8]` | 0xd17cc1b7, 0xa7220a94, 0xfe13abe8, 0xfa9a6ee0, 0xedb14acc, 0x9e21c820, 0xff28b1d5, 0xef5de2b0 | round constants of F |
| `DOMAIN_STREAM` | 0x9e3779b9 | stream chunks |
| `DOMAIN_SPLIT` | 0xbb67ae85 | split children |
| `DOMAIN_FORK` | 0xd2511f53 | fork children |
| `DOMAIN_FOLD` | 0xcd9e8d57 | purpose children |
| `DOMAIN_SEED` | 0xa54ff53a | seed whitening |
| `AUX_STREAM` | 0x94d049bb | aux word of stream chunks |


## 3. Building blocks

### Clock

Evaluate `clock(h)` in the following order:

```
h0 ← h0 ⊕ rotl(h1, 7)
h1 ← h1 ⊕ rotl(h2, 13)
h2 ← h2 ⊕ rotl(h3, 22)
h3 ← h3 ⊕ rotl(h0, 3)        (the updated h0)
return (h0 + 0x9e3779b9, h1, h2, h3)
```

### Mix

Evaluate `mix(o, h)` with `o = (a, b, c, d)`:

```
p0 = a · (h0 | 1)
p1 = c · (h1 | 1)
return (b ⊕ hi(p1) ⊕ lo(p1),
        rotl(lo(p1), 16) ⊕ h2,
        d ⊕ hi(p0) ⊕ lo(p0),
        rotl(lo(p0), 16) ⊕ h3)
```

### Step T

Evaluate both building blocks on the input state.
Apply feedback after the clock's modular addition:

```
o' = mix(o, h)
q = clock(h)
h' = (q0 ⊕ o'0, q1, q2, q3)
return (o', h')
```

### Seeding function F

Evaluate `F(o, h)` with exactly eight rounds.
Index the round constants from 1 through 8:

```
for r = 1 to 8:
    (o, h) ← T(o, h)
    o0 ← o0 ⊕ RC[r]
    (o, h) ← (h, o)
return (o, h)
```

For `F(key, counter, domain, aux)`, use a four-word key and an unsigned 64-bit counter.
Use 32-bit words for `domain` and `aux`.
Initialize the state, then evaluate `F(o, h)`:

```
o = (counter mod 2^32, counter >> 32, domain, aux)
h = key
```

## 4. Chunks and stream order

Choose a power-of-two chunk length `K` with `1 ≤ K ≤ 65536`.
Use `K = 32` by default.
Represent the chunk index `c` as an unsigned 64-bit integer.

Initialize each chunk with `(o, h) = F(key, c, DOMAIN_STREAM, AUX_STREAM)`.
Advance the state with T before emitting each of its `K` blocks:

```
B(c, j) = exposed half of T^(j+1)(o, h),   j = 0, …, K − 1
```

Arrange the stream into 1024-bit rows.
For row `r`, set `g = r ÷ K` and `j = r mod K`.
Concatenate the eight 128-bit blocks in this order:

```
B(8g + 0, j), B(8g + 1, j), …, B(8g + 7, j)
```

Read bit `t` of a block from bit `t mod 32` of word `o(t ÷ 32)`.
Use `0 ≤ t < 128`.
For a stream bit position `p` with `0 ≤ p < 2^64`, locate its block as follows:

```
r = p >> 10
g = r ÷ K
j = r mod K
lane = (p >> 7) & 7
c = 8g + lane
t = p & 127
block = B(c, j)
```

For random access, initialize chunk `c`, apply T `j + 1` times, and read its exposed half.

## 5. Draws and fills

Use these scalar component widths:

| Type | Width w, bits |
| --- | --- |
| Bool | 1 |
| UInt8, Int8 | 8 |
| UInt16, Int16, Float16 | 16 |
| UInt32, Int32, Float32 | 32 |
| UInt64, Int64, Float64, Char | 64 |
| UInt128, Int128 | 128 |

For a scalar draw at position `p`, align to its width `w`:

```
p' = (p + w − 1) & ~(w − 1)
```

Read `w` bits starting at `p'`.
Set the successor position to `p' + w`.
For `w ≥ 8`, read `w / 8` bytes at block byte offset `(p' >> 3) & 15`.
Interpret these bytes as the little-endian unsigned integer `raw`.

Convert the input to the requested type:

- Integers: reinterpret `raw` at the requested width, using two's complement for signed types.
- Bool: return `true` for a set bit and `false` for a clear bit.
- Float64: return `(raw >> 11) · 2^−53` as Float64.
- Float32: return `(raw >> 8) · 2^−24` as Float32.
- Float16: return `(raw >> 5) · 2^−11` as Float16.
- Char: compute `u = floor(raw · 1112064 / 2^64)` using the full mathematical product.
  Return Unicode scalar `u` when `u < 0xd800`, and `u + 0x800` otherwise.

Evaluate each float mapping as an exact integer scaling by a power of two.
Store Char in four output bytes and advance its stream position by 64 bits.

For `Complex{T}`, with T in Float16/Float32/Float64, draw the real component followed by the imaginary component.
Apply the scalar rule separately to each component.
Allow the pair to span adjacent blocks.

For a fill of `n` scalar values, align the initial position to obtain `p'`.
Read element `i` at `p' + w·i` for `i = 0, …, n − 1`.
Return position `p' + w·n`.
For complex fills, emit real and imaginary components in alternating order.
Use a real fill of length `2n` to determine the component sequence.
For an empty fill, return the initial position aligned to the scalar component width.

### Position bounds

Accept initial constructor positions satisfying `0 ≤ p < 2^63`.
Represent successor positions as unsigned 64-bit integers.
Compute alignment and endpoint checks with mathematical integer arithmetic.
Require `p' + w < 2^64` for a scalar draw and `p' + w·n < 2^64` for a scalar fill.
Apply the same endpoint bound to the complete component sequence of a complex draw or fill.
Validate a fill's alignment and endpoint before writing output.
Keep unchecked scalar draws within these bounds.

## 6. Seeds and child keys

Define `half(0)` of an F output as its exposed half `o`.
Define `half(1)` as its hidden half `h`.
Start each child at position 0 with its parent's `K`.

### Integer seeds

Accept integer seeds `z` with `0 ≤ z < 2^128`.
Initialize:

```
o = (0, 0, DOMAIN_SEED, 0)
h = (z mod 2^32, (z >> 32) mod 2^32, (z >> 64) mod 2^32, z >> 96)
key = half(0) of F(o, h)
```

For a raw-key constructor, use the supplied four words as the key.

### Split by index

For child index `i` in the unsigned 64-bit range, derive:

```
child_key = half(i & 1) of F(key, i >> 1, DOMAIN_SPLIT, 0)
```

Use the parent key for every child.
Preserve the parent position.

### Fork at the current block

Accept a batch size `n` with `0 ≤ n ≤ 2^33`.
Capture `b = p >> 7` from the parent position.
Derive every child from that captured block:

```
for i = 0 to n − 1:
    child_key[i] = half(i & 1) of F(key, b, DOMAIN_FORK, (i >> 1) mod 2^32)
parent_position = (b + 1) · 128
```

Advance the parent once per batch, including an empty batch.
Use `n = 1` for a single-child fork.
At an exact block boundary, advance the parent to the following block boundary.

### Purpose

For an unsigned 64-bit purpose identifier `u`, derive:

```
child_key = half(0) of F(key, u, DOMAIN_FOLD, 0)
```

Preserve the parent position.

## 7. Transport

Transport the variant name, four-word key, and unsigned 64-bit bit position.
Use the variant name to identify the algorithm and its chunk length `K`.
Represent the key with 128 bits and the position with 64 bits.
Reconstruct cached working state from the key, chunk length, and position.

## 8. Test vectors

Check an implementation against these vectors.

All words are hexadecimal.

**T on a structured state.** `T((1, 2, 3, 4), (5, 6, 7, 8))`:

```
o' = (00000017, 00150007, 00000001, 00050008)
h' = (9e377ca9, 0000e006, 02000007, 00001820)
```

**T on the zero state.** `T(0, 0) = (0, (9e3779b9, 0, 0, 0))`.

**F for the stream**, key `k = (00000001, 00000002, 00000003, 00000004)`:

```
F(k, 0, DOMAIN_STREAM, AUX_STREAM):
  o = (472bef12, c0977c66, d330ac3a, b11a020d)
  h = (bfa0b6ba, ecdbc48e, f1989116, c2374d96)
F(k, 1, DOMAIN_STREAM, AUX_STREAM):
  o = (b777c10c, 2f6b5a5d, 67a9ce03, 7de06a50)
  h = (d0c2dc4f, e1e50e0f, 89efc72c, 6e82b062)
```

**Stream under `k`, K = 32**, as UInt32 words from position 0:

```
words 0–3   (row 0, lane 0 = B(0, 0)): 0a5bcb90 6dfe98bc 9612198a ac115fd8
words 4–7   (row 0, lane 1 = B(1, 0)): 33f598d7 b5c280ca 7a8e7b99 8c362290
words 32–35 (row 1, lane 0 = B(0, 1)): 9da7bac0 4aca79eb beb1f65a e2f0d5a1
```

Derived draws from position 0: Float64 element 0 = 0.4296660861094629, Float64 element 16
(bit 1024, row 1) = 0.2921520424112306, Float32 element 2 = 0.58621365. Bool elements 0 to 7
are bits 0 to 7 of word 0 (low byte 0x90): 0, 0, 0, 0, 1, 0, 0, 1. Bool element 128 is bit 0
of word 4 (0x33f598d7): 1.

**Derived keys of `k`:**

```
split child 0:            e256e9a1 5020f806 3bd3f7dc 5328763d
split child 1:            a9ea3f0b 47f97af0 d1844c53 97e9cee2
fork child 0 at block 0:  67fd37c5 9dc0b8c6 4e3bd55e af3f2216
purpose 7:                8048398f 1678e814 d8823983 c4b1045c
```

**Seed whitening.** Seed 42 gives the key `421d21eb 32d31777 62e7564b df2bdf82`. From that
key at K = 32: Float64 element 0 = 0.9829130398628935, UInt32 element 0 = 0x05e80cec, Float64
element 2 = 0.47759300283385586, Float64 element 16 = 0.9692135305890753.

## Appendix A. Derived draws (non-normative)

This appendix is not part of the specification.
It records the conventions the implementations share for draws derived from the uniform stream, so that ports agree with each other.
A conforming implementation may omit these draws.
An implementation that offers them should follow these rules.

### Bounded integers

Draw an unsigned integer uniform on `[0, range)` by Lemire's multiply-and-reject method over the uniform `w`-bit draws, `w` in {32, 64}.
For a draw `x`, compute the `2w`-bit product `m = x · range`.
If the low `w` bits of `m` are below `t = (2^w − range) mod range`, reject `x`.
Return the high `w` bits of `m`.
For `range = 0`, return 0 and consume one draw.

An interface that names the draw width, such as a `u32` or `u64` bounded fill, uses that width.
An interface that names only the result type or the bounds chooses the width from the range: `w = 32` when `range ≤ 2^32`, else `w = 64`.
The result type does not affect the values, so a bounded draw into a 64-bit integer with a range below `2^32` equals the same draw into a 32-bit integer.
A signed interval `[lo, hi)` draws on `range = hi − lo` and adds `lo`.

A scalar bounded draw rejects by drawing the next `w` bits of the stream, until a draw is accepted.

A bounded fill of `n` elements consumes exactly `n` draws, so that elements can be computed in parallel.
Element `i` uses draw `i` of the plain `w`-bit fill.
Let `g` be the index of that draw in the stream of the fill's key: the fill's aligned start position divided by `w`, plus `i`.
When draw `i` is rejected, retry on the draws of a fallback generator, starting at its position 0:

```
fallback(g) = split(g) of purpose(P_w) of the generator with the fill's key at position 0
P_32 = 0x424c573332
P_64 = 0x424c573634
```

These two purpose identifiers are reserved for this use.
The fallback depends on the key and on `g` only.
A bounded fill cut into ranges at any element boundary therefore equals the whole fill, and two fills of one key never share a fallback stream unless they share a draw.
A fill without rejections equals the sequence of scalar bounded draws.

### Normals

Float64 normals use a ziggurat with 1024 layers, one 64-bit draw per element.
Float32 normals use the Box-Muller transform, one pair of 32-bit draws per two elements.

#### Reference logarithm

Let `L(x) = −2 ln x` for Float64 `x` in `(0, 1]`, computed as below.
Each `fma` is a fused multiply-add with one rounding.
Every other operation rounds once to the nearest Float64, and no product is fused into a sum.

```
ix = (bits of x) + 0x00095f6200000000                 (64-bit integer)
nk = 1023 − (ix >> 52)                                (exact in Float64, equals −k for x = m · 2^k)
m  = Float64 with bits (ix & 0x000fffffffffffff) + 0x3fe6a09e00000000
s  = (m − 1) / (m + 1)
z  = s · s
p  = fma(z, fma(z, fma(z, fma(z, fma(z, fma(z, c6, c5), c4), c3), c2), c1), 1)
L  = fma(nk, 0x1.a39ef00000000p−32, fma(nk, 0x1.62e42fee00000p+0, (s · −4) · p))

c6 = 0x1.54797261814c6p−4    c5 = 0x1.7381dac46557bp−4    c4 = 0x1.c71fd2b1ef828p−4
c3 = 0x1.2492462428654p−3    c2 = 0x1.9999999b8be41p−3    c1 = 0x1.55555555553b4p−2
```

Let `ln(x) = −0.5 · L(x)`, which is exact given `L(x)`.
This is `neg2_log_f64` of the C reference.

#### Float64: ziggurat

Let `f(x) = exp(−x² / 2)`.
The ziggurat stacks 1024 layers of equal area `v` under `f` on `x ≥ 0`.
Define the widths `X_0 > X_1 > … > X_1024` and `v` from the base width `R` in exact arithmetic:

```
v        = R · f(R) + ∫ f(t) dt over t ≥ R
X_0      = v / f(R)
X_1      = R
X_(i+1)  = sqrt(−2 · log(f(X_i) + v / X_i))     for 1 ≤ i ≤ 1022
X_1024   = 0
```

`R` is the root of `f(X_1023) + v / X_1023 = 1`, so that the top layer ends at the mode.
Layer `i` with `1 ≤ i ≤ 1023` is the rectangle `[0, X_i] × [f(X_i), f(X_(i+1))]`.
Layer 0 is the rectangle `[0, R] × [0, f(R)]` and the region under `f` beyond `R`.
Its area equals that of the rectangle `[0, X_0] × [0, f(R)]`.

The tables follow from the exact widths:

| table | entries | value |
|---|---|---|
| `W[i]` | 1024, `0 ≤ i ≤ 1023` | `X_i · 2^−53`, rounded to the nearest Float64 |
| `K[i]` | 1024, `0 ≤ i ≤ 1023` | `floor(2^53 · X_(i+1) / X_i)`, an integer below `2^53`, with `K[1023] = 0` |
| `Y[i]` | 1025, `0 ≤ i ≤ 1024` | `f(X_i)` rounded to the nearest Float64 for `i ≤ 1023`, and `Y[1024] = 1` |
| `R` | 1 | `X_1` rounded to the nearest Float64, `0x1.027c84109fad5p+2` |

The file `tables/normal_f64_zig1024.json` holds `R`, `W`, `K` and `Y`, with each Float64 as an exact hexadecimal float.
Its SHA-256 is `8b961dd46a2582b953bd8780138edb0ad712e3d243a366a123ffc8978d0a33ab`.
The script `tools/gen_zig_tables.py` derives the file from these definitions with mpmath at 50 significant digits, and `--check` verifies the committed file byte for byte.
Implementations copy the values of this file.

Split a 64-bit draw `r` into the layer, the sign and a 53-bit magnitude, and take the fast path:

```
i  = r & 1023                  (bits 0–9)
s  = (r >> 10) & 1             (bit 10)
ra = r >> 11                   (bits 11–63)
x  = (−1)^s · (ra · W[i])
if ra < K[i]: return x
```

`ra` converts to Float64 exactly, and `ra · W[i]` rounds once.
The sign flips the sign bit, so `ra = 0` with `s = 1` gives `−0.0`.
The fast path returns 99.57 % of the elements.

A draw that misses the fast path continues on a fallback generator:

```
fallback(g) = split(g) of purpose(P_N64) of the generator with the fill's key at position 0
P_N64       = 0x4e524d3634
```

`g` is the index of `r` in the stream of the fill's key: the fill's start position aligned to 64 bits, divided by 64, plus the element index.
The value `0x4e524d3634` is reserved for this use.
Let `next()` return the fallback's 64-bit draws in sequence from its position 0, as its UInt64 fill does.
Let `u(d) = (d >> 11) · 2^−53`, the Float64 mapping of section 5.
Each missed element starts its own fallback, so no state passes between elements.

Continue from the values `i`, `s`, `ra` and `x` of the fast path:

```
loop:
    if i == 0:                                         (tail, Marsaglia's method)
        repeat:
            a = −ln(1 − u(next())) / R
            b = −ln(1 − u(next()))
        until b + b ≥ a · a
        return (−1)^s · (R + a)
    y = Y[i] + u(next()) · (Y[i + 1] − Y[i])           (wedge)
    if ln(y) < −0.5 · (x · x): return x
    r = next()
    i, s, ra, x = split and scale r as in the fast path
    if ra < K[i]: return x
```

Outside `ln`, round each operation once to the nearest Float64, with no fused multiply-add.
`1 − u` is exact.
`−ln(1 − u)` equals the Float64 exponential of `u` in the next section.
The wedge test compares `ln y` with `−x² / 2` instead of `y` with `exp(−x² / 2)`, so `ln` is the only transcendental function.

A normal fill of `n` elements writes element `i` from draw `i` of the plain UInt64 fill and consumes `n` draws.
Fallback draws do not move the position of the filled generator.
An empty fill follows section 5.
A scalar normal draw consumes one 64-bit draw and equals element 0 of a fill.
A fill cut at any element boundary equals the whole fill.
Float64 normals are exact across implementations that use these tables and the reference `ln`.

#### Float32: Box-Muller

Derive Float32 normals by the Box-Muller transform from two consecutive Float32 uniform draws `a` and `b`:

```
r  = sqrt(−2 · log(1 − a))
z0 = r · cos(2π b)
z1 = r · sin(2π b)
```

A normal fill of `n` elements writes `z0` to element `2j` and `z1` to element `2j + 1`, from uniform draws `2j` and `2j + 1`.
The fill consumes `2 · ceil(n / 2)` uniform draws.
For odd `n`, write only `z0` of the last pair and still advance past both draws.
A scalar normal draw returns `z0` and consumes two uniform draws, so it equals element 0 of a fill.
A stateful wrapper may keep `z1` and return it on the next scalar call, so that repeated scalar calls equal the fill.
A value-type generator defined by its transport form must not keep `z1`.

Compute in single precision.
Where a precise `sincospi` is available, take the angle through `sincospi(2b)`.
A device may take a fast intrinsic such as CUDA's `__sincosf` within the tolerance of "Agreement".
Otherwise take the angle `2π b` in double precision and round `cos` and `sin` to Float32.

The C reference computes `log`, `cos` and `sin` with short polynomials and explicit fused multiply-add, with no libm call.
An implementation that copies those polynomials with the same operation order and fused multiply-adds produces normals bit for bit equal to the reference, on the host and on a device.

### Exponentials

Derive a standard exponential from one uniform draw `u` of the output width:

```
e = −log(1 − u)
```

An exponential fill of `n` elements writes element `i` from uniform draw `i` and consumes `n` draws.
A scalar exponential draw consumes one draw and equals element 0 of a fill.
Compute Float64 exponentials from Float64 uniforms in double precision and Float32 exponentials from Float32 uniforms in single precision.
The C reference computes Float64 exponentials as `0.5 · L(1 − u)` with the reference logarithm, and Float32 exponentials with its Float32 polynomial, so exponentials that copy them are bit exact.

### Agreement

Uniform draws, fills, child keys and the bounded-integer draws are exact across implementations.
Float64 normals and Float64 exponentials are exact across implementations that use the reference logarithm, and the normals also the tables.
Cross-implementation tests compare them bit for bit.
Float32 normals and Float32 exponentials share the uniform draws they consume, and their values agree up to the differences of the platform's `log`, `sqrt`, `cos` and `sin`.
Cross-implementation tests use 16 units in the last place plus `1e-6` absolute for Float32.
The absolute floor covers values near the zeros of `cos` and `sin`, where the relative error of a single-precision angle grows.
A device that takes a fast intrinsic for the angle, such as CUDA's `__sincosf`, uses an absolute floor of `2.1e-6` instead, the intrinsic's error bound of `2^-21.41` times the largest radius the tests reach.

The C reference publishes fixtures in `tests/cross_below.h`, `tests/cross_fill_below.h`, `tests/cross_normal.h` and `tests/cross_exponential.h`, and the CUDA implementation in `tests/cross_fill_below.h`, `tests/cross_fill_normal.h` and `tests/cross_fill_exponential.h`.
A port that copies the polynomial logarithm matches the exponential fixtures bit for bit, and the FNV-1a hash `47f8f98297d94ee2` of the exponentials in tandem-c's `tests/test_exponential_bits.c`.

## Appendix B. Parallel decomposition (non-normative)

This appendix is not part of the specification.
It shows how to split work across ranks, threads, GPU blocks and devices so that the results do not depend on how many there are.
The code uses the C API of tandem-c, where `tandem_sub` is purpose.
Every port offers the same operations under its own names.

### One position space per key

A key defines one stream of 2^64 bits, and section 4 gives random access to any position of it.
Draw `i` of a fill that starts at the aligned position `p0` with width `w` sits at `p0 + w·i`.
Map a global index space onto positions, and every element has one value, whoever computes it.
The values then do not depend on the number of ranks, threads, blocks or GPUs, nor on the order in which they run.
A constructor accepts positions below 2^63 (section 5), which leaves room for 2^57 doubles under one key.

Use positions and three derived generators:

| tool | gives | use for |
| --- | --- | --- |
| position `p0 + w·i` | element `i` of one global fill | a global array or index space |
| `split(i)` | an independent stream for index `i`, from the key alone | one stream per task, particle or cell |
| `fork(n)` | a batch of `n` streams from the parent's current block | children created in sequence by one parent |
| `purpose(u)` | an independent stream for the identifier `u` | named sub-streams, such as initial state and collisions |

### Global arrays: fill at an offset

Element `i` of a fill equals draw `i`, so the fill of elements `[a, b)` from position `p0 + w·a` equals that part of one fill from `p0`.
Give each rank a range and place its generator there:

```c
uint64_t a = n * rank / size, b = n * (rank + 1) / size;
tandem_rng r = tandem_from_key(key, p0 + 64 * a, K);
tandem_fill_f64(&r, x + a, b - a);          /* x[a..b) of one global fill */
```

The ranges need no alignment beyond the element width, and they may have any length.
The same shape serves threads, GPU blocks and single GPU threads.
To move a generator, set its position, which costs the same at any distance.

When each work item consumes a fixed number of draws, give item `i` the stride of those draws:

```c
tandem_rng r = tandem_from_key(key, p0 + 3 * 64 * i, K);   /* three doubles per item */
double u = tandem_next_f64(&r), v = tandem_next_f64(&r), s = tandem_next_f64(&r);
```

When the number of draws varies, as in a rejection loop, use `split(i)` instead.

### Independent streams: split by work item

`split(i)` derives a child key from the parent key and `i` alone.
It does not depend on the parent's position or on the order of calls, so any rank can derive any child at any time.
Index the children by the work item, a task, particle or cell, and not by the rank:

```c
for (uint64_t t = first_task; t < end_task; t++) {
    tandem_rng r = tandem_split(&root, t);
    simulate(t, &r);                        /* the same draws on 1 or 1000 ranks */
}
```

A child indexed by the rank number makes the results depend on the number of ranks.
Use it only when the decomposition is fixed by the problem.
Children are generators like their parent, so `split` nests: `tandem_split(&r, step)` inside a task gives one stream per task and step.

### Batches: fork

`fork(n)` derives `n` children from the parent's current block and moves the parent past it.
The children depend on the parent's position, so the parent must make the same sequence of calls everywhere it is used.
Use `fork` where one parent creates children in sequence, such as a new generation of walkers each time step:

```c
tandem_rng kids[n];
tandem_fork(&parent, kids, n);              /* every rank runs this on its copy of parent */
for (uint64_t i = first; i < end; i++) step(&kids[i]);
```

Each rank keeps a copy of the parent, forks the same batch, and uses its own share.
Where children can be indexed up front, `split` is simpler and needs no shared sequence.

### Named sub-streams: purpose

`purpose(u)` derives a child from the key and an identifier.
Give each use of randomness in a program its own purpose, and draw from its children:

```c
enum { INIT = 1, COLLISIONS = 2, NOISE = 3 };
tandem_rng init = tandem_sub(&root, INIT);
tandem_rng coll = tandem_sub(&root, COLLISIONS);
tandem_rng r = tandem_split(&coll, particle);
```

A purpose is stable when code changes.
When a new phase adds draws under a new purpose, the draws of every other purpose stay the same.
With one shared stream, an added draw shifts every later draw.
Choose identifiers once and keep them.
The values `0x424c573332` and `0x424c573634` are reserved for bounded fills, and `0x4e524d3634` for Float64 normals, see Appendix A.

### Bounded integers and normals

A bounded fill maps element `i` to draw `i` like the plain fill, and it keys the fallback for a rejected draw by the draw's index in the stream (Appendix A).
A bounded fill therefore decomposes like a uniform fill, at any element boundary, rejected draws included:

```c
tandem_rng r = tandem_from_key(key, p0 + 32 * a, K);
tandem_fill_u32_below(&r, k + a, b - a, 1000);   /* k[a..b) of one global bounded fill */
```

A scalar bounded draw consumes a varying number of draws, so a sequence of scalar draws does not decompose by position.
Use a fill, or `split` per work item.

A Float64 normal fill maps element `i` to draw `i` and keys its fallback by the draw's index, as a bounded fill does.
It decomposes at any element boundary, and its values are exact across ports:

```c
tandem_rng r = tandem_from_key(key, p0 + 64 * a, K);
tandem_fill_normal_f64(&r, z + a, b - a);       /* z[a..b) of one global normal fill */
```

A Float32 normal fill computes elements `2j` and `2j + 1` from uniform draws `2j` and `2j + 1`.
Start every range of a global Float32 normal fill at an even element, so that the pairs fall the same way:

```c
uint64_t pairs = (n + 1) / 2;
uint64_t a = 2 * (pairs * rank / size), b = 2 * (pairs * (rank + 1) / size);
if (b > n) b = n;
tandem_rng r = tandem_from_key(key, p0 + 32 * a, K);
tandem_fill_normal_f32(&r, z + a, b - a);
```

A range of odd length writes only the cosine half of its last pair, so only the last range may be odd.
Float32 normals agree across ports to the tolerance of Appendix A.
On one platform and build they are exact, so a decomposition test can compare them bit for bit.

### Checkpoint and restart

The transport form of section 7, variant, key and position, is the whole state of a generator.
Save it at a checkpoint and rebuild the generator from it at restart:

```c
uint32_t key[4]; tandem_key(&r, key);
uint64_t pos = tandem_position(&r);
uint32_t K = tandem_chunk_length(&r);
/* ... restart ... */
tandem_rng r2 = tandem_from_key(key, pos, K);   /* draws continue as if uninterrupted */
```

Children from `split` and `purpose` need no checkpoint beyond their position, since the root key and the index rebuild their keys.
State kept per work item rather than per rank also lets a run restart on a different number of ranks.

### What not to do

- Do not seed each rank with `seed + rank`.
  The results then depend on the number of ranks, and run `seed + 1` reuses the streams of run `seed` on shifted ranks.
  Use one seed and `split` by work item.
- Do not seed from the time or the process ID.
  Such a run cannot be repeated, and ranks that start in the same clock tick get the same seed.
  Draw a seed once, record it, and pass it to every rank.
- Do not share one generator between threads behind a lock.
  The draws then follow the thread schedule, which differs from run to run, and the lock serializes every draw.
  Give each thread its own range or its own child.
- Do not reach a rank's offset by drawing and discarding.
  Set the position instead.

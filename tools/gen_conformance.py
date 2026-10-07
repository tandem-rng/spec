"""Generate conformance/*.json, the cross-implementation fixtures, from tandem-c at its pinned commit.

Run without arguments to write the files from ../tandem-c. Run with --check to verify the committed
files byte for byte. Parses the fixture headers in tests/, hashes the stream dumps in tests/data, and
builds and runs the dump tools with $CC (default cc). Adds the weighted choice vectors of vectors.json.
Needs only the standard library.
"""

import argparse
import hashlib
import json
import os
import re
import struct
import subprocess
import sys
import tempfile
from fractions import Fraction
from pathlib import Path

PIN = "1c75956c39581836c1f6e190d1072c9a43be6b0d"
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "conformance"
F32_TOL = {"ulps": 16, "abs": 1e-6}
DUMP_STARTS = [0, 1, 77, 12345, 1 << 30]

# tools/dump_streams.jl: (file, key, K, type, n, bytes per element).
STREAMS = [
    ("k1234_K32_u32.bin", "k1234", 32, "UInt32", 65536, 4),
    ("k1234_K32_u64.bin", "k1234", 32, "UInt64", 2048, 8),
    ("k1234_K8_u32.bin", "k1234", 8, "UInt32", 16384, 4),
    ("seed42_K32_f64.bin", "seed42", 32, "Float64", 4096, 8),
    ("seed42_K32_f32.bin", "seed42", 32, "Float32", 4096, 4),
    ("seed42_K32_u8.bin", "seed42", 32, "UInt8", 8192, 1),
    ("seed42_K32_bool.bin", "seed42", 32, "Bool", 4096, 1),
    ("seed42_K32_u128.bin", "seed42", 32, "UInt128", 1024, 16),
    ("seed42_K32_c64.bin", "seed42", 32, "ComplexF64", 1024, 16),
    ("seed42_K32_c32.bin", "seed42", 32, "ComplexF32", 1024, 8),
    ("seed42_K32_f16bits.bin", "seed42", 32, "Float16", 4096, 2),
    ("seed42_K32_char.bin", "seed42", 32, "Char", 4096, 4),
]

EMPTY_START = 33
# The order in which PROBE prints the end positions of its empty fills.
EMPTY_KINDS = ["fill_below_u32", "fill_below_u64", "fill_normal_f64", "fill_normal_f32",
               "fill_exponential_f64", "fill_exponential_f32", "fill_choice"]
EMPTY_WEIGHTS = [1.0, 2.0, 3.0, 4.0]

PROBE = r"""
#include <stdio.h>
#include "tandem.h"
static void show(tandem_rng g) {
    uint32_t k[4];
    tandem_key(&g, k);
    printf("%08x %08x %08x %08x %u\n", k[0], k[1], k[2], k[3], tandem_chunk_length(&g));
}
int main(void) {
    tandem_rng g = tandem_seed(42, 0, 0), h[7];
    uint32_t u32;
    uint32_t alias[4];
    uint64_t u64, cut[4];
    double d, w[4] = {1, 2, 3, 4};
    float f;
    tandem_choice_table t;
    show(g);
    show(tandem_seed(2026, 7, 0));
    tandem_set_position(&g, START);
    for (int i = 0; i < 7; i++) h[i] = g;
    tandem_fill_u32_below(&h[0], &u32, 0, 10);
    tandem_fill_u64_below(&h[1], &u64, 0, 10);
    tandem_fill_normal_f64(&h[2], &d, 0);
    tandem_fill_normal_f32(&h[3], &f, 0);
    tandem_fill_exponential_f64(&h[4], &d, 0);
    tandem_fill_exponential_f32(&h[5], &f, 0);
    if (!tandem_choice_build(&t, w, 4, cut, alias)) return 1;
    tandem_fill_choice(&h[6], &u32, 0, &t);
    for (int i = 0; i < 7; i++) printf("%llu ", (unsigned long long)tandem_position(&h[i]));
    printf("\n%016llx", (unsigned long long)t.capacity);
    return 0;
}
"""


def c_arrays(text):
    """Map each array name to (field list, nested initializer) for the fixture headers."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"//[^\n]*", "", text)
    fields = lambda body: re.findall(r"(\w+)(?:\s+|\s*\*+\s*)(\w+)(?:\[[^\]]*\])?;", body)
    typedefs = {m[2]: fields(m[1]) for m in re.finditer(r"typedef struct \{(.*?)\}\s*(\w+);", text, re.S)}
    found = {}
    decl = r"static const (?:struct \{(?P<body>.*?)\}|(?P<type>\w+))\s+(?P<name>\w+)\[[^\]]*\]\s*=\s*\{"
    for m in re.finditer(decl, text, re.S):
        tokens = re.findall(r"[{}]|[^\s{},]+", text[m.end() - 1 :])
        stack = [[]]
        for tok in tokens:
            if tok == "{":
                stack.append([])
            elif tok == "}":
                done = stack.pop()
                stack[-1].append(done)
                if len(stack) == 1:
                    break
            else:
                stack[-1].append(tok)
        layout = fields(m["body"]) if m["body"] else typedefs.get(m["type"], m["type"])
        found[m["name"]] = (layout, stack[0][0])
    return found


def c_int(tok):
    tok = tok.rstrip("uUlL")
    return int(tok, 16) if tok.lower().startswith("0x") else int(tok)


def f64_hex(tok):
    return struct.pack(">d", float(tok)).hex()


def f32_hex(tok):
    """Bits of the binary32 nearest to the decimal literal, ties to even, as a compiler rounds it."""
    q = Fraction(tok.rstrip("fF"))
    near = struct.unpack("<I", struct.pack("<f", float(q)))[0]
    value = lambda b: Fraction(struct.unpack("<f", struct.pack("<I", b))[0])
    best = min((near - 1, near, near + 1), key=lambda b: (abs(value(b) - q), b & 1))
    return f"{best:08x}"


def records(arrays, name):
    layout, rows = arrays[name]
    return [dict(zip((field for _, field in layout), row)) for row in rows]


def case(src, kind, key, start, n, values, **extra):
    c = {"id": src, "kind": kind, "key": key, "K": 32, "start": start}
    for field in ("range", "weights", "capacity", "cut", "alias"):
        if field in extra:
            c[field] = extra.pop(field)
    c["n"] = n
    c["values"] = values
    c.update(extra)
    return c


def hexw(x, w):
    return f"{x:0{w // 4}x}"


def bounded(arrays, key):
    below, fill = [], []
    for w in (32, 64):
        for i, r in enumerate(records(arrays["cross_below.h"], f"CROSS_U{w}")):
            below.append(case(f"cross_below.h CROSS_U{w}[{i}]", f"below_u{w}", key, 1, len(r["want"]),
                              [hexw(c_int(v), w) for v in r["want"]], range=hexw(c_int(r["n"]), w),
                              end=c_int(r["end_pos"])))
    for w in (32, 64):
        for i, r in enumerate(records(arrays["cross_fill_below.h"], f"CROSS_FILL_U{w}")):
            fill.append(case(f"cross_fill_below.h CROSS_FILL_U{w}[{i}]", f"fill_below_u{w}", key,
                             c_int(r["start"]), len(r["want"]), [hexw(c_int(v), w) for v in r["want"]],
                             range=hexw(c_int(r["n"]), w), end=c_int(r["end_pos"])))
    device = arrays["cuda_fill_below.h"]
    assert [c_int(v) for v in device["CROSS_FILL_KEY"][1]] == [int(k, 16) for k in key]
    for suffix in ("", "_AT"):
        for w in (32, 64):
            name = f"CROSS_BELOW{w}{suffix}"
            for i, r in enumerate(records(device, name)):
                fill.append(case(f"cuda_fill_below.h {name}[{i}]", f"fill_below_u{w}", key,
                                 c_int(r.get("start", "0")), len(r["out"]),
                                 [hexw(c_int(v), w) for v in r["out"]], range=hexw(c_int(r["range"]), w),
                                 rejected=c_int(r["rejected"])))
    return below, fill


def normals(arrays, key, text):
    out = []
    for i, r in enumerate(records(arrays["cross_normal.h"], "CROSS_NORMAL")):
        out.append(case(f"cross_normal.h CROSS_NORMAL[{i}]", "fill_normal_f64", key, c_int(r["start"]),
                        len(r["want"]), [f64_hex(v) for v in r["want"]], end=c_int(r["end_pos"])))
    pairs = arrays["cross_normal.h"]["CROSS_NORMALF"][1]
    end = c_int(re.search(r"CROSS_NORMALF_END_POS = (\w+);", text)[1])
    # tandem-c reaches start 1 by one Bool draw, then takes 64 pairs by tandem_normal2_f32.
    out.append(case("cross_normal.h CROSS_NORMALF", "fill_normal_f32", key, 1, len(pairs),
                    [f32_hex(v) for v in pairs], end=end, tol=F32_TOL))
    for name, kind, conv, tol in (("CROSS_NORMAL64", "fill_normal_f64", f64_hex, None),
                                  ("CROSS_NORMAL32", "fill_normal_f32", f32_hex, F32_TOL)):
        for i, r in enumerate(records(arrays["cuda_fill_normal.h"], name)):
            n = c_int(r["n"])
            extra = {"tol": tol} if tol else {}
            out.append(case(f"cuda_fill_normal.h {name}[{i}]", kind, key, c_int(r["pos"]), n,
                            [conv(v) for v in r["out"][:n]], **extra))
    return out


def choices(arrays, key):
    weights = {name: [f64_hex(v) for v in row] for name, (_, row) in arrays.items() if name.startswith("CROSS_CHOICE_W")}
    out = []
    for i, r in enumerate(records(arrays, "CROSS_CHOICE")):
        w = weights[r["weights"]]
        assert len(w) == c_int(r["m"])
        out.append(case(f"cross_choice.h CROSS_CHOICE[{i}]", "fill_choice", key, c_int(r["start"]), len(r["want"]),
                        [hexw(c_int(v), 32) for v in r["want"]], weights=w, capacity=hexw(c_int(r["capacity"]), 64),
                        end=c_int(r["end_pos"])))
    return out


def spec_choices():
    """The Appendix C vectors of vectors.json, which also pin the cut and alias tables."""
    vectors = json.loads((ROOT / "vectors.json").read_text())
    out = []
    for v in vectors["choice"]["cases"]:
        out.append(case(f"vectors.json choice {v['name']}", "fill_choice", vectors["key"], 0, len(v["indices"]),
                        [hexw(i, 32) for i in v["indices"]], weights=[struct.pack(">d", w).hex() for w in v["weights"]],
                        capacity=v["S"], cut=v["cut"], alias=[hexw(a, 32) for a in v["alias"]]))
    return out


def exponentials(arrays, key):
    out = []
    for name, kind, conv, tol in (("CROSS_EXPONENTIAL", "fill_exponential_f64", f64_hex, None),
                                  ("CROSS_EXPONENTIALF", "fill_exponential_f32", f32_hex, F32_TOL)):
        for i, r in enumerate(records(arrays["cross_exponential.h"], name)):
            extra = {"tol": tol} if tol else {}
            out.append(case(f"cross_exponential.h {name}[{i}]", kind, key, c_int(r["start"]), len(r["want"]),
                            [conv(v) for v in r["want"]], end=c_int(r["end_pos"]), **extra))
    return out


def run_tools(tc, tmp):
    """Keys of the seeds the fixtures use, the end positions of the empty fills, and the SHA-256 and
    length of each dump tool's output."""
    cc = os.environ.get("CC", "cc").split()
    flags = ["-std=c11", "-O2", "-ffp-contract=off"]
    obj = tmp / "tandem.o"
    subprocess.run(cc + flags + ["-c", "-o", obj, tc / "tandem.c"], check=True)
    (tmp / "probe.c").write_text(PROBE)
    exes = {}
    for name, src, extra in (("probe", tmp / "probe.c", [f"-DSTART={EMPTY_START}"]),
                             ("dump_normals", tc / "tools/dump_normals.c", []),
                             ("dump_exponentials", tc / "tools/dump_exponentials.c", [])):
        exes[name] = tmp / name
        subprocess.run(cc + flags + extra + ["-I", tc, "-o", exes[name], src, obj, "-lm"], check=True)
    lines = subprocess.run([exes["probe"]], capture_output=True, text=True, check=True).stdout.split("\n")
    keys = []
    for line in lines[:2]:
        *words, k = line.split()
        assert k == "32"
        keys.append(words)
    empty_ends = dict(zip(EMPTY_KINDS, map(int, lines[2].split()), strict=True))
    empty_ends["capacity"] = lines[3]
    dumps = {}
    for name in ("dump_normals", "dump_exponentials"):
        data = subprocess.run([exes[name]], capture_output=True, check=True).stdout
        dumps[name] = (len(data), hashlib.sha256(data).hexdigest())
    return keys, empty_ends, dumps


def hashes(tc, keys, dumps):
    k1234 = ["00000001", "00000002", "00000003", "00000004"]
    key42, key2026 = keys
    streams = []
    for file, keyname, K, typ, n, size in STREAMS:
        data = (tc / "tests/data" / file).read_bytes()
        assert len(data) == n * size, file
        streams.append({"file": f"tests/data/{file}", "key": k1234 if keyname == "k1234" else key42, "K": K,
                        "start": 0, "type": typ, "n": n, "bytes": len(data),
                        "sha256": hashlib.sha256(data).hexdigest()})

    docs = (tc / "docs/tests.md").read_text()
    normal_bits = (tc / "tests/test_normal_bits.c").read_text()
    exp_bits = (tc / "tests/test_exponential_bits.c").read_text()
    for src in (normal_bits, exp_bits, (tc / "tools/dump_normals.c").read_text(),
                (tc / "tools/dump_exponentials.c").read_text()):
        assert "starts[] = {0, 1, 77, 12345, 1u << 30}" in src and "tandem_seed(2026, 7, 0)" in src
    define = lambda src, name: re.search(rf"#define {name} 0x([0-9a-f]+)ull", src)[1]
    seeded = {"seed": f"{2026 + (7 << 64):032x}", "key": key2026, "K": 32, "starts": DUMP_STARTS}
    out = []
    for tool, fnv, draws in (
        ("dump_normals", define(normal_bits, "F64_HASH"), [{"kind": "fill_normal_f64", "n": 1000000}]),
        ("dump_exponentials", define(exp_bits, "EXPECTED_HASH"),
         [{"kind": "fill_exponential_f64", "n": 1000000}, {"kind": "fill_exponential_f32", "n": 1000000}]),
    ):
        size, sha = dumps[tool]
        assert sha in docs, f"{tool} output differs from the SHA-256 in docs/tests.md"
        out.append({"id": f"tools/{tool}.c", **seeded, "draws": draws, "bytes": size, "sha256": sha, "fnv1a": fnv})
    out.append({"id": "tests/test_normal_bits.c normal f32", **seeded,
                "draws": [{"kind": "fill_normal_f32", "n": 1999999}], "bytes": 5 * 1999999 * 4,
                "fnv1a": define(normal_bits, "F32_HASH")})
    for start, fnv, end in re.findall(r"\{(\d+), 0x([0-9a-f]+)ull, (\d+)\}", normal_bits):
        out.append({"id": "tests/test_normal_bits.c Python reference", "key": k1234, "K": 32,
                    "starts": [int(start)], "draws": [{"kind": "fill_normal_f64", "n": 200000}],
                    "bytes": 200000 * 8, "fnv1a": fnv, "end": int(end)})
    return streams, out


def render(meta, lists):
    lines = ["{"] + [f"  {json.dumps(k)}: {json.dumps(v)}," for k, v in meta.items()]
    blocks = []
    for name, items in lists.items():
        body = ",\n".join("    " + json.dumps(item) for item in items)
        blocks.append(f"  {json.dumps(name)}: [\n{body}\n  ]")
    return "\n".join(lines) + "\n" + ",\n".join(blocks) + "\n}\n"


def generate(tc):
    git = lambda *a: subprocess.run(["git", "-C", tc, *a], capture_output=True, text=True, check=True).stdout
    head = git("rev-parse", "HEAD").strip()
    if head != PIN:
        sys.exit(f"tandem-c is at {head}, the pin is {PIN}")
    if git("status", "--porcelain", "--untracked-files=no"):
        sys.exit("tandem-c has uncommitted changes, so its build would differ from the pin")
    arrays, texts = {}, {}
    for h in ("cross_below.h", "cross_fill_below.h", "cross_normal.h", "cross_exponential.h",
              "cuda_fill_below.h", "cuda_fill_normal.h", "cross_choice.h"):
        texts[h] = (tc / "tests" / h).read_text()
        arrays[h] = c_arrays(texts[h])
    with tempfile.TemporaryDirectory() as tmp:
        keys, empty_ends, dumps = run_tools(tc, Path(tmp))
    key = keys[0]
    below, fill = bounded(arrays, key)

    def empty(kind):
        extra = {}
        if "below" in kind:
            extra = {"range": hexw(10, int(kind[-2:]))}
        elif kind == "fill_choice":
            extra = {"weights": [f64_hex(w) for w in EMPTY_WEIGHTS], "capacity": empty_ends["capacity"]}
        return case("test_api.c test_empty_fills", kind, key, EMPTY_START, 0, [], end=empty_ends[kind], **extra)

    src = lambda *hs: [f"tandem-c {PIN} tests/{h}" for h in hs]
    streams, dumped = hashes(tc, keys, dumps)
    return {
        "below.json": render({"source": src("cross_below.h")}, {"cases": below}),
        "fill_below.json": render({"source": src("cross_fill_below.h", "cuda_fill_below.h", "test_api.c")},
                                  {"cases": fill + [empty("fill_below_u32"), empty("fill_below_u64")]}),
        "normal.json": render({"source": src("cross_normal.h", "cuda_fill_normal.h", "test_api.c")},
                              {"cases": normals(arrays, key, texts["cross_normal.h"])
                               + [empty("fill_normal_f64"), empty("fill_normal_f32")]}),
        "exponential.json": render({"source": src("cross_exponential.h", "test_api.c")},
                                   {"cases": exponentials(arrays, key)
                                    + [empty("fill_exponential_f64"), empty("fill_exponential_f32")]}),
        "choice.json": render({"source": src("cross_choice.h", "test_api.c") + ["tandem-spec vectors.json choice"]},
                              {"cases": spec_choices() + choices(arrays["cross_choice.h"], key)
                               + [empty("fill_choice")]}),
        "hashes.json": render({"source": [f"tandem-c {PIN} tests/data, tools/dump_*.c, tests/test_*_bits.c"]},
                              {"streams": streams, "dumps": dumped}),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="verify the committed files")
    parser.add_argument("--pin", action="store_true", help="print the pinned tandem-c commit")
    parser.add_argument("--tandem-c", type=Path, default=ROOT.parent / "tandem-c", help="tandem-c checkout")
    args = parser.parse_args()
    if args.pin:
        print(PIN)
        return 0
    files = generate(args.tandem_c.resolve())
    if not args.check:
        OUT.mkdir(exist_ok=True)
        for name, text in files.items():
            (OUT / name).write_text(text, newline="\n")
        return 0
    bad = [name for name, text in files.items() if (OUT / name).read_bytes() != text.encode()]
    if PIN not in (OUT / "README.md").read_text():
        bad.append("README.md (pin)")
    for name in bad:
        print(f"conformance/{name} differs from tandem-c {PIN}", file=sys.stderr)
    if not bad:
        print(f"conformance matches tandem-c {PIN}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

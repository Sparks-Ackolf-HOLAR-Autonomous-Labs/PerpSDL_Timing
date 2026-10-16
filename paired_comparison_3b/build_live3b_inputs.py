#!/usr/bin/env python3
"""Build pw.x inputs for comparison No. 3b (5 Oct 2026).

Companion to comparison No. 3 (decision: "do both"). No. 3 keeps its
first-pass 8x8 inputs, in which every 2H cell is a two-layer cell held at
the PBE spacing (384 atoms). No. 3b uses single layers for every compound:

  1T : 8x8 supercell of the same relaxed 1x1 layer as No. 2 and No. 3
       (192 atoms, c = 18 A), identical inputs.
  2H : 8x8 supercell of the relaxed single 2H layer from the stacking
       study (granite-guest job 2088961, mono2H vc-relax; 192 atoms,
       c = 20 A). Geometries in mono2H_geometries.json.

Pool: 29 compounds. TiS2-2H is out (its single layer did not converge in
the stacking study; gap 0.38-0.57 eV in every other form, far from the
window). HfSe2-2H is in (its single layer relaxed; it was out of No. 3
because its first-pass bilayer did not).

Stages, k-points, cutoffs and solver are identical to No. 2 and No. 3
(stage_block from ../paired_comparison_2/build_live2_inputs.py). The
reservation model uses the measured single-layer anchor of the No. 2
builder (TiS2_1T 6x6 = 30.9 GB at 864 electrons, electrons^1.55,
iso-electron chalcogen factor), scaled by c/18 A for the larger vacuum of
the 2H single layers (plane-wave count scales with cell volume). mem_bit =
1 above the population median, so the disclosed bit now separates heavy
chemistry (Te, and W/Mo/Hf) instead of layer count.
Writes inputs/*.in and inputs/manifest2.json (file name kept so the
unchanged driver live2_campaign.py reads it).
"""
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
L2 = HERE.parent / "paired_comparison_2"
spec = importlib.util.spec_from_file_location(
    "b2", str(L2 / "build_live2_inputs.py"))
b2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b2)
OUT = HERE / "inputs"
N = 8
GEO = json.load(open(HERE / "mono2H_geometries.json", encoding="utf-8"))
GAP_SL = {r["name"]: r for r in json.load(open(
    HERE.parent / "paired_comparison_3" / "candidates_corrected.json",
    encoding="utf-8"))["candidates"]}


def main():
    OUT.mkdir(exist_ok=True)
    man1 = json.load(open(b2.SRC / "manifest.json"))
    names = [m["name"] for m in man1 if m["name"].endswith("_1T")]
    names += sorted(k for k, v in GEO.items() if v["relaxed"])
    rows = []
    for name in names:
        if name.endswith("_1T"):
            a1, c, species, motif = b2.parse3x3(
                b2.SRC / f"{name}.f2.in")
        else:
            g = GEO[name]
            a1, c, species = g["a_angstrom"], g["c_angstrom"], g["species"]
            motif = [tuple(p) for p in g["motif"]]
        ntyp = len(species.splitlines())
        sup = [(el, (x + i) / N, (y + j) / N, z)
               for i in range(N) for j in range(N)
               for el, x, y, z in motif]
        nat = len(sup)
        nelec = sum(b2.VALENCE[el] for el, *_ in sup)
        nocc = nelec // 2
        x_el = ("Te" if "Te2" in name else "Se" if "Se2" in name else "S")
        cf = b2.CHALC_FACTOR[x_el]
        ram = 30.9 * (nelec / 864.0) ** 1.55 * (cf / 0.90) * (c / 18.0)
        for stage, calc, ecut, rho, conv, nbnd in (
                ("f1", "scf", 40.0, 320.0, "1.0d-6", None),
                ("f2", "scf", 45.0, 360.0, "1.0d-8", None),
                ("f3", "nscf", 45.0, 360.0, "1.0d-8",
                 int(nocc * 1.10) + 16)):
            (OUT / f"{name}.{stage}.in").write_text(b2.stage_block(
                name, calc, a1 * N, c, nat, ntyp, ecut, rho, conv,
                species, sup, nbnd))
        sl = GAP_SL.get(name, {})
        rows.append({"name": name, "phase": name[-2:], "nat": nat,
                     "nelec": nelec, "x": x_el, "c_angstrom": c,
                     "ram_est_gb": round(ram, 1),
                     "gap_single_layer_ev": sl.get("gap_corrected_ev")})
    med = sorted(r["ram_est_gb"] for r in rows)[len(rows) // 2]
    for r in rows:
        r["mem_bit"] = int(r["ram_est_gb"] > med)
    json.dump({"n_super": N, "ram_median_gb": med, "comparison": "3b",
               "candidates": rows},
              open(OUT / "manifest2.json", "w"), indent=1)
    hi = [r["name"] for r in rows if r["mem_bit"]]
    print(f"{len(rows)} candidates; RAM est "
          f"{min(r['ram_est_gb'] for r in rows)}-"
          f"{max(r['ram_est_gb'] for r in rows)} GB, median {med}; "
          f"high bit: {hi}")


if __name__ == "__main__":
    main()

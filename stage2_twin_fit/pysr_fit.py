#!/usr/bin/env python3
"""Stage-2 symbolic refit (manifest section: symbolic_regression).

Free-form PySR fit of the measured per-call wall time on the twin's
input variables, with the Stage-1 protocol: campaign-level split (by
candidate, never by round/stage), validation-based complexity selection,
unit-consistent operator grammar.

Run on the DGX inside ~/mpt_stage1/venv (PySR + Julia already built).
"""
import csv
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent


def main():
    rows = [r for r in csv.DictReader(open(HERE / "qe_calls.csv"))
            if r["soc"] == "0" and r["nelec"] and r["node_hours"]]
    rng = np.random.default_rng(41)
    cands = sorted({r["candidate"] for r in rows})
    rng.shuffle(cands)
    n_val = max(1, len(cands) // 5)
    val_set = set(cands[:n_val])
    X = np.array([[float(r["nelec"]), float(r["nat"]), float(r["nk"])]
                  for r in rows])
    y = np.array([np.log(float(r["node_hours"])) for r in rows])
    is_val = np.array([r["candidate"] in val_set for r in rows])

    from pysr import PySRRegressor
    model = PySRRegressor(
        niterations=200, populations=24,
        binary_operators=["+", "-", "*", "/", "^"],
        unary_operators=["log"],
        constraints={"^": (-1, 2)},
        maxsize=25, model_selection="best",
        elementwise_loss="loss(x, y) = (x - y)^2",
        temp_equation_file=True, progress=False,
        random_state=0, deterministic=False, parallelism="multithreading",
    )
    model.fit(X[~is_val], y[~is_val],
              variable_names=["nelec", "nat", "nk"])
    # validation-based complexity selection
    best = None
    best_i = 0
    table = []
    for i, (_, eq) in enumerate(model.equations_.iterrows()):
        pred = model.predict(X[is_val], index=i)
        mse = float(((pred - y[is_val]) ** 2).mean())
        table.append(dict(complexity=int(eq["complexity"]),
                          train_loss=float(eq["loss"]),
                          val_mse=round(mse, 4),
                          expr=str(eq["equation"])))
        if best is None or mse < best["val_mse"]:
            best, best_i = table[-1], i
    pred_all = model.predict(X, index=best_i)
    r2 = 1 - ((pred_all - y) ** 2).mean() / y.var()
    out = dict(target="log(node_hours) per QE call",
               n_train=int((~is_val).sum()), n_val=int(is_val.sum()),
               selected=best, r2_all=round(float(r2), 3),
               pareto=table)
    json.dump(out, open(HERE / "pysr_wall_fit.json", "w"), indent=1)
    print(json.dumps({k: out[k] for k in
                      ("selected", "r2_all", "n_train", "n_val")}, indent=1))


if __name__ == "__main__":
    sys.exit(main())

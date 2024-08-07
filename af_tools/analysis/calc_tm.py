from functools import singledispatch
import subprocess

from typing import Any

from numpy.typing import NDArray
import numpy as np
import pandas as pd


@singledispatch
def calc_tm(target_model: Any, ref_model: str) -> float:
    raise NotImplementedError(
        (f"Argument type {type(target_model)} for target_model_path is"
         "not implemented for calc_tm function."))


@calc_tm.register
def _(target_model: str, ref_model: str) -> float:
    cmd = [
        "USalign", "-outfmt", "2", "-mm", "1", "-ter", "0",
        f"{str(target_model)}", f"{str(ref_model)}"
    ]
    p = subprocess.run(cmd, capture_output=True, text=True)
    return float(p.stdout.split("\n")[1].split()[3])


@calc_tm.register
def _(target_model: pd.Series, ref_model: str) -> float:
    return calc_tm(target_model["best_model_path"], ref_model)


@singledispatch
def calc_pairwise_tms(ref: Any, models: list[str]) -> NDArray:
    raise NotImplementedError(
        (f"Argument type {type(ref)} for target_model_path is"
         "not implemented for calc_pairwise_tms function."))


@calc_pairwise_tms.register
def _(ref: str, models: list[str]) -> NDArray:
    len_models = len(models)
    tms = np.full(len_models, np.nan, dtype=float)

    for i in range(len_models):
        target_model = models[i]
        tms[i] = calc_tm(ref, target_model)
    return tms


@calc_pairwise_tms.register
def _(ref: pd.Series, models: list[str]) -> NDArray:
    return calc_pairwise_tms(ref["best_model_path"], models)

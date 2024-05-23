import multiprocessing
from pathlib import Path
from typing import Sequence

import numpy as np
import orjson

from af_tools.outputs.afoutput import AFOutput
from af_tools.output_types import AF2Prediction, AF2Model


class AF2Output(AFOutput):

    def __init__(self,
                 path: str | Path,
                 *args,
                 process_number: int = 1,
                 is_colabfold: bool = True,
                 **kwargs):

        self.is_colabfold = is_colabfold
        super().__init__(path=path, process_number=process_number)

    def get_predictions(self) -> Sequence[AF2Prediction]:
        if self.is_colabfold:
            return self.get_colabfold_predictions()
        return self.get_af2_predictions()

    def _worker_get_pred(self, path: Path) -> Sequence[AF2Prediction]:
        af2output = AF2Output(path=path, process_number=1)
        return af2output.predictions

    def get_colabfold_predictions(self) -> Sequence[AF2Prediction]:
        predictions: list[AF2Prediction] = []
        if self.process_number > 1:
            outputs = [x.parent for x in list(self.path.rglob("config.json"))]
            with multiprocessing.Pool(processes=self.process_number) as pool:
                results = pool.map(self._worker_get_pred, outputs)

            predictions = [j for i in results
                           for j in i]  # flatten the results
        else:
            with open(self.path / "config.json", "rb") as config_file:
                config_data = orjson.loads(config_file.read())

            af_version = config_data["model_type"]
            num_ranks = config_data["num_models"]

            # predictions: list[AF2Prediction] = []
            for pred_done_path in self.path.glob("*.done.txt"):
                pred_name = pred_done_path.name.split(".")[0]

                with open(self.path / f"{pred_name}.a3m", "r") as msa_file:
                    msa_header_info = msa_file.readline().replace(
                        "#", "").split("\t")
                msa_header_seq_lengths = [
                    int(x) for x in msa_header_info[0].split(",")
                ]
                msa_header_seq_cardinalities = [
                    int(x) for x in msa_header_info[1].split(",")
                ]

                chain_lengths: list[int] = []
                for seq_len, seq_cardinality in zip(
                        msa_header_seq_lengths, msa_header_seq_cardinalities):
                    chain_lengths += [seq_len] * seq_cardinality

                chain_ends: list[int] = []
                for chain_len in chain_lengths:
                    if chain_ends == []:
                        chain_ends.append(chain_len)
                    else:
                        chain_ends.append(chain_len + chain_ends[-1])

                model_unrel_paths = sorted(
                    self.path.glob(f"{pred_name}_unrelaxed_rank_*.pdb"))
                model_rel_paths = sorted(
                    self.path.glob(f"{pred_name}_relaxed_rank_*.pdb"))
                score_paths = sorted(
                    self.path.glob(f"{pred_name}_scores_rank_*.json"))

                models: list[AF2Model] = []
                for i, (model_unrel_path, score_path) in enumerate(
                        zip(model_unrel_paths, score_paths)):
                    model_rel_path = None
                    if i < config_data["num_relax"]:
                        model_rel_path = model_rel_paths[i]

                    with open(score_path, "rb") as score_file:
                        score_data = orjson.loads(score_file.read())
                    pae = np.asarray(score_data["pae"])
                    plddt = np.asarray(score_data["plddt"])

                    models.append(
                        AF2Model(
                            name=pred_name,
                            model_path=model_unrel_path,
                            relaxed_pdb_path=model_rel_path,
                            json_path=score_path,
                            rank=i + 1,
                            mean_plddt=np.average(plddt, axis=0),
                            ptm=score_data["ptm"],
                            pae=pae,
                            af_version=af_version,
                            residue_plddts=plddt,
                            chain_ends=chain_ends,
                        ))
                predictions.append(
                    AF2Prediction(
                        name=pred_name,
                        num_ranks=num_ranks,
                        af_version=af_version,
                        models=models,
                        is_colabfold=True,
                    ))
        return predictions

    def get_af2_predictions(self) -> Sequence[AF2Prediction]:
        return []
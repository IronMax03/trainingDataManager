from typing_extensions import Tuple, List
from pathlib import Path
import polars as pl

from utils.config_manager import ConfigManager


class DataProcessor:
    def __init__(self, config_name: str = "DataProcessor.yaml") -> None:
        conf = ConfigManager(config_name)

        self.compression_type = conf["compression_type"]
        self.compression_level = conf["compression_level"]


    def _import_patients(self, root: Path) -> tuple[List[str], pl.DataFrame]:
        from parse import search, findall
        import io

        # Patient info
        with open(root / "SUBJECT-INFO") as f:
            lines = [line for line in f if line.strip()]
        patients = pl.read_csv(io.StringIO("".join(lines)), separator="\t")
        patients = patients.rename({"Case": "id", "Gender": "gender", "Age (years)": "age"})
        patients = patients.with_columns(
            pl.col("gender").str.strip_chars().replace_strict({"F": "female", "M": "male"})
        )

        # Summary per patient
        summaries = []
        for pid in patients["id"]:
            text = (root / pid / f"{pid}-summary.txt").read_text()
            text = text.split("Channels changed")[0]   # keep only the first montage

            row = {
                "id": pid,
                "sampling_rate": search("Data Sampling Rate: {rate:d} Hz", text)["rate"],
            }
            for r in findall("Channel {num:d}: {name}\n", text):
                row[f"channel_{r['num']}"] = r["name"].strip()

            summaries.append(row)

        return patients["id"], patients.join(pl.from_dicts(summaries), on="id", how="left")


    def _load_edf_file(self, path: Path, id:str, dataframe:pl.DataFrame | pl.LazyFrame = None, isLazy:bool = False) -> pl.DataFrame | pl.LazyFrame:
        """
            Load edf into a polars DataFrame.
        """

        import pyedflib

        signals, signal_headers, header = pyedflib.highlevel.read_edf(str(path))
        labels = [h["label"] for h in signal_headers]

        rows = {"record_id": id, "file": path.name}
        for label, sig in zip(labels, signals):
            rows.update({label: sig})

        readDataframe = pl.DataFrame(rows).lazy() if isLazy else pl.DataFrame(rows)

        if dataframe is None:
            return readDataframe

        return pl.concat([dataframe,readDataframe], how="vertical")


    def _import_signals(self, patientIDs: List[str], root: Path) -> pl.DataFrame:
        frames = []

        for id in patientIDs:
            for i, file in enumerate(Path(root / id).iterdir()):
                if file.suffix != ".edf" and file.suffix != ".seizure":
                    continue
                frames.append(self._load_edf_file(file, f"{id}_{i}"))

        return frames


    def _add_recording(self, signalPath: Path, patientPath:Path, recordID:str) -> None:
        """
        This function add a new signal to a givent patient.

        Patient is must be in the following form: chmb01, chmb02, ...

        signal path: a .edf file conteining
        """

        newSignal = self._load_edf_file(signalPath, recordID)

        df = pl.concat([pl.read_parquet(patientPath), newSignal])
        df.write_parquet(patientPath, compression=self.compression_type, compression_level=self.compression_level)


    def import_edf(self, path: str) -> tuple[pl.DataFrame, pl.DataFrame]:
        root = Path(path)
        ids, patient = self._import_patients(root)

        return patient, self._import_signals(ids, root)


    def export_all(self, patient:pl.DataFrame, signals:List[pl.DataFrame], path:str = "") -> None:
        root = Path(path)
        patientsPath = root / "raw_signals/"
        patientsPath.mkdir(parents=True, exist_ok=True)

        patient.write_parquet(root / "patients.parquet", compression=self.compression_type, compression_level=self.compression_level)

        for index, df in enumerate(signals):
            df.write_parquet(patientsPath / f"patient_{index}.parquet", compression=self.compression_type, compression_level=self.compression_level)

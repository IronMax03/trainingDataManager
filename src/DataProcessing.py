from typing_extensions import Tuple, List
from pathlib import Path
import polars as pl


def _import_patients(root: Path) -> tuple[List[str], pl.DataFrame]:
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


def _import_signals(ids: List[str], root: Path) -> pl.DataFrame:
    import pyedflib

    frames = []
    def _load_edf_file(path: Path, id: str) -> None:
        """
            Load edf into a polars DataFrame.
        """
        signals, signal_headers, header = pyedflib.highlevel.read_edf(str(path))
        labels = [h["label"] for h in signal_headers]

        rows = {"id": id, "file": path.name}
        for label, sig in zip(labels, signals):
            rows.update({label: sig})
        frames.append(pl.DataFrame(rows))

    for id in ids:
        for file in Path(root / id).iterdir():
            if file.suffix != ".edf" and file.suffix != ".seizure":
                continue
            _load_edf_file(file, id)

    return frames


def import_edf(path: str) -> tuple[pl.DataFrame, pl.DataFrame]:
    root = Path(path)
    ids, patient = _import_patients(root)

    return patient, _import_signals(ids, root)


def export_all(patient:pl.DataFrame, signals:List[pl.DataFrame], compression_level:int = 15, path:str = "") -> None:
    root = Path(path)
    patientsPath = root / "raw_signals/"
    patientsPath.mkdir(parents=True, exist_ok=True)

    patient.write_parquet(root / "patients.parquet", compression="zstd", compression_level=compression_level)

    for index, df in enumerate(signals):
        df.write_parquet(patientsPath / f"patient_{index}.parquet", compression="zstd", compression_level=compression_level)

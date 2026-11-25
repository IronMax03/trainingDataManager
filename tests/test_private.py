from pathlib import Path

import polars as pl
import pytest

from DataProcessing import DataProcessor

IDS = ["chb01", "chb02", "chb03"]


REPO = Path(__file__).parent.parent


@pytest.fixture
def processor() -> DataProcessor:
    return DataProcessor("DataProcessor.yaml")


@pytest.fixture
def root() -> Path:
    return REPO / "Test_Database" / "raw_data"


@pytest.fixture
def edf(root: Path) -> Path:
    return root / "chb01" / "chb01_01.edf"


@pytest.fixture
def patients(processor: DataProcessor, root: Path) -> pl.DataFrame:
    ids, patients = processor._import_patients(root)
    assert list(ids) == IDS
    return patients


@pytest.mark.parametrize(
    "pid, gender, age",
    [("chb01", "female", 11), ("chb02", "male", 11), ("chb03", "female", 14)],
)
def test_import_patients_info(patients: pl.DataFrame, pid: str, gender: str, age: int):
    row = patients.filter(pl.col("id") == pid).row(0, named=True)

    assert row["gender"] == gender
    assert row["age"] == age
    assert row["sampling_rate"] == 256
    assert row["channel_1"]


def test_load_edf_file(processor: DataProcessor, edf: Path):
    df = processor._load_edf_file(edf, "chb01_0")

    assert isinstance(df, pl.DataFrame)
    assert df["record_id"][0] == "chb01_0"
    assert df["file"][0] == edf.name
    assert df.height > 0


def test_load_edf_file_lazy(processor: DataProcessor, edf: Path):
    assert isinstance(processor._load_edf_file(edf, "chb01_0", isLazy=True), pl.LazyFrame)


def test_load_edf_file_concat(processor: DataProcessor, edf: Path):
    first = processor._load_edf_file(edf, "chb01_0")

    assert processor._load_edf_file(edf, "chb01_1", first).height == 2 * first.height


def test_import_signals(processor: DataProcessor, root: Path):
    frames = processor._import_signals(IDS, root)

    # 2 .edf per patient; .edf.seizures files are skipped
    assert len(frames) == 6
    assert all(isinstance(f, pl.DataFrame) for f in frames)
    assert all(f["record_id"][0].split("_")[0] in IDS for f in frames)


def test_add_recording(processor: DataProcessor, edf: Path, tmp_path: Path):
    patientPath = tmp_path / "patient_0.parquet"
    first = processor._load_edf_file(edf, "chb01_0")
    first.write_parquet(patientPath)

    processor._add_recording(edf, patientPath, "chb01_1")

    df = pl.read_parquet(patientPath)
    assert df.height == 2 * first.height
    assert set(df["record_id"]) == {"chb01_0", "chb01_1"}

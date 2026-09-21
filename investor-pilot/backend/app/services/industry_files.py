"""Conservative industry-table readers. Never merge distinct DLIS acquisitions."""
from pathlib import Path
import csv
import re
import pandas as pd

TEXT_EXTENSIONS = {".csv", ".txt", ".asc", ".ascii", ".dat", ".tsv"}

def read_text_table(path, limit=None):
    with Path(path).open(encoding="utf-8-sig", errors="strict") as handle:
        sample = handle.read(65536)
    if "\\x00" in sample or "\x00" in sample:
        raise ValueError("Binary content is not an ASCII log table.")
    if re.search(r"(?im)^\s*~V", sample):
        return read_las(path, limit)
    lines = [line for line in sample.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    if not lines:
        raise ValueError("The file has no table rows.")
    first = lines[0]
    delimiter = next((d for d in ["\t", ";", ","] if d in first), None)
    columns = next(csv.reader([first], delimiter=delimiter)) if delimiter else re.split(r"\s+", first.strip())
    if not columns or len(set(columns)) != len(columns):
        raise ValueError("Provide a unique nonempty header row.")
    if all(re.fullmatch(r"[-+0-9.eE]+", c.strip()) for c in columns):
        raise ValueError("This table has no column headers. Add curve names and explicit units before upload.")
    frame = pd.read_csv(path, sep=delimiter or r"\s+", comment="#", encoding="utf-8-sig",
                        nrows=limit, on_bad_lines="error")
    if frame.empty:
        raise ValueError("The table has no data rows.")
    return frame

def read_las(path, limit=None):
    import lasio
    las = lasio.read(path)
    frame = las.df().reset_index()
    if limit is not None:
        frame = frame.head(limit)
    frame.attrs["source_units"] = {str(c.mnemonic): str(c.unit or "") for c in las.curves}
    frame.attrs["source_metadata"] = {"well": {str(c.mnemonic): str(c.value) for c in las.well}}
    return frame

def read_dlis(path, limit=None):
    try:
        from dlisio import dlis
    except ImportError as exc:
        raise ValueError("DLIS reader is unavailable. Install the declared dlisio dependency or export a selected frame as LAS.") from exc
    with dlis.load(str(path)) as logical_files:
        frames = [(i, frame) for i, logical in enumerate(logical_files) for frame in logical.frames]
        if len(frames) != 1:
            choices = ", ".join(f"logical {i}: {frame.name}" for i, frame in frames)
            raise ValueError("DLIS contains multiple or no frames. Export one acquisition as LAS; frames are never silently combined. " + choices[:1000])
        logical_id, source = frames[0]
        values = source.curves()
        columns, units, excluded = {}, {}, []
        for channel in source.channels:
            key = channel.fingerprint
            if key not in values.dtype.fields:
                raise ValueError("DLIS channel identity could not be resolved.")
            data = values[key]
            name = str(channel.name)
            if data.ndim != 1 or data.dtype.kind not in "iuf":
                excluded.append(name)
                continue
            if name in columns:
                raise ValueError("DLIS repeats a channel mnemonic. Select and rename the intended channel before import.")
            columns[name] = data[:limit] if limit is not None else data
            units[name] = str(channel.units or "")
        if not columns:
            raise ValueError("No scalar numeric log channels were found in this DLIS frame.")
        frame = pd.DataFrame(columns)
        frame.attrs["source_units"] = units
        frame.attrs["source_metadata"] = {"logical_file": logical_id, "frame": str(source.name),
                                         "excluded_non_scalar_channels": excluded}
        return frame

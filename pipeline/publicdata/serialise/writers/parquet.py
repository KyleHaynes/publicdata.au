from __future__ import annotations

from pathlib import Path

import pyarrow.parquet as pq

from ...normalise import Table
from .. import dumps


def write_parquet(tbl: Table, header: dict, path: Path) -> None:
    t = tbl.table.replace_schema_metadata({"publicdata": dumps(header)})
    pq.write_table(t, path, compression="zstd", write_statistics=True, row_group_size=65_536)

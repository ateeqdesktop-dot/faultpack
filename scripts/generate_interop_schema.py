from __future__ import annotations

import json
from pathlib import Path

from faultpack.interop import EvidenceBundle


schema = EvidenceBundle.model_json_schema()
schema["$id"] = "https://github.com/ateeqdesktop-dot/faultpack/blob/main/docs/faultpack-evidence.schema.json"
schema["title"] = "FaultPack Evidence Bundle"
Path("docs/faultpack-evidence.schema.json").write_text(
    json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)

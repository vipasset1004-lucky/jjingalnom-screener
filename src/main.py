"""파이프라인 진입점: 3개 JSON fetch → 교차검증 → unified_results.json 생성."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .fetch_sources import fetch_all
from .cross_validate import cross_validate

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = REPO_ROOT / "unified_results.json"
LAST_UPDATE_PATH = REPO_ROOT / "last_update.json"


def run() -> int:
    sources = fetch_all()

    missing = [name for name, p in sources.items() if not p.ok]
    if missing:
        print(f"[WARN] 일부 소스 실패: {missing}", file=sys.stderr)

    # 모든 소스 실패 시 종료(이전 결과 보존)
    if all(not p.ok for p in sources.values()):
        print("[ERROR] 모든 소스 fetch 실패. 종료.", file=sys.stderr)
        return 1

    smart_money = sources["smart_money"].data if sources["smart_money"].ok else {}
    new_high    = sources["new_high"].data    if sources["new_high"].ok    else {}
    divergence  = sources["divergence"].data  if sources["divergence"].ok  else {}

    unified = cross_validate(smart_money, new_high, divergence)

    # 메타 추가
    unified["meta"] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "smart_money": {
                "ok": sources["smart_money"].ok,
                "scan_at": (smart_money or {}).get("generated_at"),
                "error": sources["smart_money"].error,
            },
            "new_high": {
                "ok": sources["new_high"].ok,
                "scan_at": (new_high or {}).get("scan_date"),
                "error": sources["new_high"].error,
            },
            "divergence": {
                "ok": sources["divergence"].ok,
                "scan_at": (divergence or {}).get("scan_date"),
                "error": sources["divergence"].error,
            },
        },
        "version": "1.0.0",
    }

    json_text = json.dumps(unified, ensure_ascii=False, indent=2, default=str)
    json_compact = json.dumps(unified, ensure_ascii=False, separators=(",", ":"), default=str)
    OUTPUT_PATH.write_text(json_text, encoding="utf-8")
    LAST_UPDATE_PATH.write_text(
        json.dumps({"updated_at": unified["meta"]["generated_at"]}, ensure_ascii=False),
        encoding="utf-8",
    )

    # index.html — 템플릿에 데이터 inline 임베드. 단일 파일, 외부 의존 0.
    template_path = REPO_ROOT / "src" / "template.html"
    index_path = REPO_ROOT / "index.html"
    if template_path.exists():
        html = template_path.read_text(encoding="utf-8")
        inline = "<script>window.EMBEDDED_DATA=" + json_compact + ";</script>"
        if "<!-- __EMBEDDED_DATA__ -->" in html:
            html = html.replace("<!-- __EMBEDDED_DATA__ -->", inline, 1)
        else:
            # 마커 없으면 </body> 직전에 삽입
            html = html.replace("</body>", inline + "\n</body>", 1)
        index_path.write_text(html, encoding="utf-8")
    else:
        print(f"[WARN] 템플릿 없음: {template_path}", file=sys.stderr)

    c = unified["counts"]
    print(
        f"[OK] {OUTPUT_PATH.name} 작성. "
        f"총 {c['total']}종목 / 3중={c['by_verification'][3]} 2중={c['by_verification'][2]} 1중={c['by_verification'][1]} / "
        f"A={c['by_category']['A']} B={c['by_category']['B']} AB={c['by_category']['AB']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(run())

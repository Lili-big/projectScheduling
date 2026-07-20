from __future__ import annotations

import argparse
import re
from pathlib import Path

from docx import Document


SOURCES = [
    Path(r"C:\Users\wangl-bj\Desktop\泸古项目-工程部长-李宗仁调研-1.docx"),
    Path(r"C:\Users\wangl-bj\Desktop\泸古项目-工程部长-李宗仁调研-2.docx"),
]

KEYWORDS = re.compile(
    r"计划|工期|架梁|合拢|连续|资源|模板|钻机|旋挖|挂篮|工效|功效|月度|每月|"
    r"进度|压缩|顺延|节点|最晚|左右幅|左幅|右幅|系梁|混凝土|钢筋|天气|春节|"
    r"节假日|施工顺序|逻辑|工作面|配置|Excel|excel|表格|关键线路|关键路径|梁场"
)


def records(path: Path) -> list[dict[str, str | int]]:
    paragraphs = [p.text.strip() for p in Document(path).paragraphs]
    output: list[dict[str, str | int]] = []
    i = 0
    while i < len(paragraphs):
        match = re.match(r"^(\d{2}:\d{2})\s+说话人(\d+)$", paragraphs[i])
        if match:
            text = paragraphs[i + 1] if i + 1 < len(paragraphs) else ""
            output.append(
                {
                    "index": i,
                    "time": match.group(1),
                    "speaker": match.group(2),
                    "text": text,
                }
            )
            i += 2
        else:
            i += 1
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=int, choices=(1, 2))
    parser.add_argument("--speaker", default="2")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=10_000)
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    selected = SOURCES if args.source is None else [SOURCES[args.source - 1]]
    for path in selected:
        print(f"===== {path.name} =====")
        for record in records(path):
            if record["speaker"] != args.speaker:
                continue
            if not (args.start <= int(record["index"]) < args.end):
                continue
            if args.all or KEYWORDS.search(str(record["text"])):
                print(
                    f"{int(record['index']):04d} | {record['time']} | "
                    f"说话人{record['speaker']} | {record['text']}"
                )


if __name__ == "__main__":
    main()

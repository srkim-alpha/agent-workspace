import os
import json

path = r"c:\agent-workspace\tmp\notion_blocks\📚_지식_스크랩.json"
with open(path, "r", encoding="utf-8") as f:
    blocks = json.load(f)

print(f"Total knowledge blocks: {len(blocks)}")

batch1 = blocks[:27]
batch2 = blocks[27:]

with open(r"c:\agent-workspace\tmp\notion_blocks\knowledge_batch1.json", "w", encoding="utf-8") as f:
    json.dump(batch1, f, ensure_ascii=False, indent=2)

with open(r"c:\agent-workspace\tmp\notion_blocks\knowledge_batch2.json", "w", encoding="utf-8") as f:
    json.dump(batch2, f, ensure_ascii=False, indent=2)

print(f"Batch 1: {len(batch1)} blocks, Batch 2: {len(batch2)} blocks saved!")

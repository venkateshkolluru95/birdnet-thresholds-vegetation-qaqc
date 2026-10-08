"""
WHAT THIS FILE DOES, IN PLAIN LANGUAGE
--------------------------------------
Turns report_template.md into DATA_QUALITY_REPORT.md. The template holds the narrative with two kinds
of placeholder: {{table_name}} for a Markdown table written by 03 (or the QA summary from 02), and
{{m:metric_name}} for a number written by 03 into metrics.json. Every number quoted in the prose
therefore comes from the data, not from memory, and re-running 01 to 04 after new data regenerates
tables and prose together. If any placeholder is left unfilled the script stops with an error, so a
stale report can never be published by accident.
"""

import os
import re
import sys
import json
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
TAB = os.path.join(HERE, "outputs", "tables")

text = open(os.path.join(HERE, "report_template.md")).read()

# {{m:name}} -> the metric's value
metrics = json.load(open(os.path.join(HERE, "outputs", "metrics.json")))
text = re.sub(r"\{\{m:([a-zA-Z0-9_]+)\}\}", lambda mo: str(metrics[mo.group(1)]), text)

# {{table_name}} -> the table file of that name
for fname in os.listdir(TAB):
    if fname.endswith(".md"):
        text = text.replace("{{" + fname[:-3] + "}}", open(os.path.join(TAB, fname)).read())

# the QA summary comes from a CSV: every rule, with all-export and retained counts, or pass
qa = pd.read_csv(os.path.join(HERE, "outputs", "qa_summary.csv"))
text = text.replace("{{qa_summary}}", qa.to_markdown(index=False))

left = re.findall(r"\{\{[^}]+\}\}", text)
if left:
    sys.exit(f"ERROR: unfilled placeholders, report not written: {sorted(set(left))}")
open(os.path.join(HERE, "DATA_QUALITY_REPORT.md"), "w").write(text)
print("DATA_QUALITY_REPORT.md written; all placeholders filled")

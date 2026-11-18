"""Reversible preprocessing demonstration for the supplied placement database.

No predictive ML model is trained. No original grade/name/answer is guessed.

INSTALL:
    python -m pip install pandas numpy openpyxl scikit-learn matplotlib pillow
CLEAN the provided raw workbook (put the .py and raw .xlsx in one folder):
    python placement_preprocessing_pipeline.py
RECREATE raw defects and clean from the original source:
    python placement_preprocessing_pipeline.py --source "original.xlsx"
OPTIONAL: --input raw.xlsx --output clean.xlsx

Every table receives 12 blanks in separate records, 10 exact duplicate rows,
15 intact recovery copies, and 3 recoverable format/range examples. Blank cells
are yellow, abnormal cells orange, appended duplicate records blue.

Recovery uses only matching keys in the raw data, never the injection log or
original source workbook. Unexpected unresolved/conflicting values raise a clear
error and do not overwrite a previous output. Review such records at the source.
"""
from pathlib import Path
import argparse
import math
import io
import json
import platform
import re
import hashlib
import unicodedata
import sklearn

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.drawing.image import Image
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, OneHotEncoder

SEED = 42
KEYS = {
    "Students": ["Student_ID"], "Authentication": ["Student_ID"],
    "Career_Profile": ["Career_Profile_ID"], "Assessments": ["Assessment_ID"],
    "Topic_Scores": ["Assessment_ID", "Topic_ID"],
    "Subtopic_Scores": ["Assessment_ID", "Topic_ID", "Subtopic_ID"],
    "AI_Roadmaps": ["Roadmap_ID"], "Mentorship": ["Mentorship_ID"],
    "Question_Bank": ["Question id"],
}
NUMBERS = {
    "Semester": (1, 8), "Batch_Year": (2000, 2100), "Current_CGPA": (0, 10),
    "Failed_Login_Attempts": (0, np.inf), "Total_Topics": (1, np.inf),
    "Total_Score": (0, 100), "Overall_Percentage": (0, 100),
    "Max_Score": (0.00001, np.inf), "Score": (0, np.inf),
    "Percentage": (0, 100), "Suggested_Duration_Weeks": (1, np.inf),
}
INTEGER_COLUMNS = {"Semester", "Batch_Year", "Failed_Login_Attempts",
                   "Total_Topics", "Suggested_Duration_Weeks"}
DATES = {"Last_Login", "Goal_Updated_Date", "Assessment_Date", "Generated_Date", "Session_Date"}
BOOLS = {"First_Login", "Password_Reset_Required"}
LABELS = {
    "Department": ["AIDS", "AIDS(MED)"],
    "Branch": ["AI AND DATA SCIENCE", "AI AND DATA SCIENCE (Medical engineering)"],
    "Correct option": list("ABCD"), "Difficulty": ["Easy", "Medium", "Hard"],
    "Status": ["Active", "Inactive"], "Account_Status": ["Active", "Inactive", "Locked"],
    "Career_Interest_Level": ["High", "Medium", "Low"],
    "Career_Stage": ["Exploring", "Developing", "Preparing"],
    "Open_to_Alternative_Roles": ["Yes", "No"],
    "Readiness_Level": ["Developing", "Near Ready", "Placement Ready"],
    "Performance_Level": ["Needs Improvement", "Developing", "Strong", "Excellent"],
    "Priority": ["Very High", "High", "Medium", "Low"],
}
# These are source-specific constraints; review them before applying to new cohorts.
OPTION_COLS = ["Option A", "Option B", "Option C", "Option D"]
LOG = []
REJECTED = []


def text_value(x):
    """Preserve strings such as 'None' and 'NULL' in programming questions."""
    if pd.isna(x):
        return np.nan
    if isinstance(x, (float, np.floating)) and x.is_integer():
        return str(int(x))
    return str(x).strip() or np.nan

def read_tables(path):
    tables = {}
    with pd.ExcelFile(path) as book:
        for sheet in book.sheet_names:
            name = "Question_Bank" if sheet == "Sheet1" else sheet
            if name not in KEYS:
                continue  # reports are not input data
            grid = pd.read_excel(book, sheet_name=sheet, header=None,
                                 dtype=object, keep_default_na=False)
            grid = grid.replace(r"^\s*$", np.nan, regex=True).dropna(how="all")
            if grid.empty:
                raise ValueError(f"Empty data sheet: {sheet}")
            header = [str(x).strip() for x in grid.iloc[0]]
            df = grid.iloc[1:].copy()
            df.columns = header
            df = df.dropna(how="all").reset_index(drop=True)
            if not set(KEYS[name]).issubset(df.columns):
                raise ValueError(f"Missing key columns in {sheet}")
            tables[name] = df
    if set(tables) != set(KEYS):
        raise ValueError(f"Missing sheets: {set(KEYS) - set(tables)}")
    return tables

def write_workbook(path, tables, charts=None, defects=None):
    with pd.ExcelWriter(path, engine="openpyxl", datetime_format="yyyy-mm-dd") as writer:
        for name, df in tables.items():
            df.to_excel(writer, sheet_name=name, index=False)
        for ws in writer.book.worksheets:
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
            ws.sheet_view.showGridLines = False
            for cell in ws[1]:
                cell.font = Font(name="Calibri", bold=True, color="FFFFFF")
                cell.fill = PatternFill("solid", fgColor="18354A")
                cell.alignment = Alignment(wrap_text=True, vertical="center")
            ws.row_dimensions[1].height = 32
            for j, col in enumerate(tables[ws.title].columns, 1):
                width = 22
                if any(t in col.lower() for t in ["question text", "description", "explanation", "details", "record"]):
                    width = 75
                elif col in OPTION_COLS or any(t in col.lower() for t in ["reason", "action", "feedback"]):
                    width = 40
                ws.column_dimensions[ws.cell(1, j).column_letter].width = max(width, min(len(col) + 2, 35))
            for row in ws.iter_rows(min_row=2):
                for cell in row:
                    cell.font = Font(name="Calibri", size=11)
                    cell.alignment = Alignment(vertical="top", wrap_text=True)
                    # Prevent spreadsheet formula interpretation of supplied text.
                    if isinstance(cell.value, str) and cell.value.startswith("="):
                        cell.data_type = "s"
                lines = max(sum(max(1, math.ceil(len(line) / max(10, ws.column_dimensions[cell.column_letter].width - 3)))
                                for line in str(cell.value or "").split("\n")) for cell in row)
                ws.row_dimensions[row[0].row].height = min(300, max(32, lines * 15 + 6))
        if defects is not None:
            for _, event in defects.iterrows():
                ws = writer.book[event["Sheet"]]
                row = int(event["Excel_Row"])
                if event["Type"] == "Duplicate row":
                    for cell in ws[row]:
                        cell.fill = PatternFill("solid", fgColor="DDEBF7")
                else:
                    col = list(tables[event["Sheet"]].columns).index(event["Column"]) + 1
                    color = "FFF2CC" if event["Type"] == "Missing cell" else "FCE4D6"
                    ws.cell(row, col).fill = PatternFill("solid", fgColor=color)
        if charts:
            ws = writer.book.create_sheet("EDA_Charts")
            ws.sheet_view.showGridLines = False
            for idx, buf in enumerate(charts):
                img = Image(buf)
                img.width, img.height = 760, 420
                ws.add_image(img, f"A{1 + idx * 23}")

def log(sheet, action, count, details):
    LOG.append({"Sheet": sheet, "Action": action, "Count": int(count), "Details": details})

def make_charts(clean, reports):
    plots = []
    def finish(fig):
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=130)
        plt.close(fig)
        buf.seek(0)
        plots.append(buf)
    fig, ax = plt.subplots(figsize=(9, 4.6))
    clean["Students"].Current_CGPA.hist(ax=ax, bins=10, color="#237A8B", edgecolor="white")
    ax.set(title="Original synthetic student CGPA (no imputation)", xlabel="CGPA", ylabel="Students")
    finish(fig)
    fig, ax = plt.subplots(figsize=(9, 4.6))
    clean["Assessments"].Readiness_Level.value_counts().plot.bar(ax=ax, color="#237A8B", rot=0)
    ax.set(title="Supplied synthetic readiness labels — not validated outcomes", ylabel="Assessments", xlabel="")
    finish(fig)
    fig, ax = plt.subplots(figsize=(9, 4.6))
    clean["Question_Bank"].Category.value_counts().plot.barh(ax=ax, color="#237A8B")
    ax.set(title="Usable question bank by category", xlabel="Questions", ylabel="")
    finish(fig)
    fig, ax = plt.subplots(figsize=(9, 4.6))
    reports["Data_Overview"].set_index("Sheet")[["Raw_Null_Cells", "Clean_Null_Cells"]].plot.barh(ax=ax, color=["#DB8C44", "#237A8B"])
    ax.set(title="Missing cells before/after (legitimate Last_Login nulls retained)", xlabel="Cells", ylabel="")
    finish(fig)
    return plots

# The source workbook's exact column names and ordering are retained.
SCHEMA = {
    "Students": "Student_ID|Roll_No|Full_Name|Program|Department|Semester|Batch_Year|Section|College_Email|Phone_Number|Current_CGPA|Status",
    "Authentication": "Student_ID|Roll_No|Password_Hash|Account_Status|First_Login|Password_Reset_Required|Last_Login|Failed_Login_Attempts",
    "Career_Profile": "Career_Profile_ID|Student_ID|Primary_Field|Target_Role|Career_Interest_Level|Career_Stage|Open_to_Alternative_Roles|Goal_Updated_Date",
    "Assessments": "Assessment_ID|Student_ID|Assessment_Date|Assessment_Type|Target_Field|Target_Role|Total_Topics|Total_Score|Overall_Percentage|Readiness_Level",
    "Topic_Scores": "Assessment_ID|Student_ID|Topic_ID|Topic_Name|Max_Score|Score|Percentage|Performance_Level",
    "Subtopic_Scores": "Assessment_ID|Student_ID|Topic_ID|Subtopic_ID|Subtopic_Name|Max_Score|Score|Percentage|Performance_Level",
    "AI_Roadmaps": "Roadmap_ID|Student_ID|Assessment_ID|Weak_Area_Type|Weak_Area|Priority|Recommended_Action|Suggested_Duration_Weeks|Alternative_Field|Alternative_Role|Reason|Generated_Date",
    "Mentorship": "Mentorship_ID|Student_ID|Assessment_ID|Weak_Area|Priority|Mentor_ID|Mentor_Name|Session_Date|Session_Status|Mentor_Feedback",
    "Question_Bank": "Question id|Category|Branch|Question text|Option A|Option B|Option C|Option D|Correct option|Skill area|Sub skill area|Difficulty",
}
SCHEMA = {name: columns.split("|") for name, columns in SCHEMA.items()}
LABELS.update({"Category": ["Technical", "Aptitude", "Soft skills"]})
FREE_TEXT = {"Question text", *OPTION_COLS, "Reason", "Recommended_Action", "Mentor_Feedback", "Password_Hash"}
CELL_AUDIT = []


class DataQualityError(ValueError):
    """A fact cannot be recovered safely or a required relationship is invalid."""


def require(condition, message):
    if not bool(condition):
        raise DataQualityError(message)


def check_schema(tables):
    for name, df in tables.items():
        require(df.columns.tolist() == SCHEMA[name],
                f"{name}: unexpected columns. Expected {SCHEMA[name]}; got {df.columns.tolist()}")


def normalize_name(value):
    # Do NOT title-case names, remove accents or infer them from email addresses.
    # Unicode letters, initials, apostrophes and hyphens are legitimate.
    if pd.isna(value):
        return np.nan
    return " ".join(str(value).split()) or np.nan


def valid_name(value):
    if pd.isna(value):
        return False
    return any(c.isalpha() for c in value) and all(
        c.isalpha() or c.isdigit() or unicodedata.category(c).startswith("M") or c in " .'-’"
        for c in value)


def parse_date(value):
    if pd.isna(value):
        return pd.NaT
    if isinstance(value, str):
        value = value.strip()
        # Reject ambiguous day/month strings rather than guessing their meaning.
        if not re.match(r"^\d{4}-\d{2}-\d{2}(?:[ T].*)?$", value):
            return pd.NaT
    elif isinstance(value, (int, float, np.number)):
        return pd.NaT  # unformatted Excel serial dates need an explicit conversion rule
    return pd.to_datetime(value, errors="coerce")


def record_key(name, row):
    return " | ".join(str(row[c]) for c in KEYS[name])


def normalize_table(name, original):
    df = original.copy()
    for c in df:
        before = df[c].copy()
        if c in NUMBERS:
            parsed = pd.to_numeric(df[c], errors="coerce")
            lo, hi = NUMBERS[c]
            valid = parsed.between(lo, hi)
            if c in INTEGER_COLUMNS:
                valid &= parsed.mod(1).eq(0)
            df[c] = parsed.where(valid)
        elif c in DATES:
            df[c] = pd.to_datetime(df[c].map(parse_date), errors="coerce")
        elif c in BOOLS:
            values = {"true": True, "false": False, "1": True, "0": False, "yes": True, "no": False}
            df[c] = df[c].map(lambda x: values.get(str(x).strip().lower(), np.nan))
        else:
            df[c] = df[c].map(text_value)
            if c not in FREE_TEXT:
                df[c] = df[c].map(lambda x: np.nan if pd.notna(x) and x.casefold() in {"null", "nan", "n/a", "none"} else x)
            if c in ["Full_Name", "Mentor_Name"]:
                df[c] = df[c].map(normalize_name)
                df[c] = df[c].where(df[c].map(valid_name))
            if c == "College_Email":
                # Strip surrounding spaces; preserve local-part case and spelling.
                valid = df[c].fillna("").str.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
                df[c] = df[c].where(valid)
            if c == "Phone_Number":
                # This dataset uses ten-digit pseudo numbers stored as text.
                df[c] = df[c].where(df[c].fillna("").str.fullmatch(r"\d{10}"))
            if c in LABELS:
                mapping = {x.casefold(): x for x in LABELS[c]}
                df[c] = df[c].map(lambda x: mapping.get(x.casefold(), np.nan) if pd.notna(x) else np.nan)
        invalid = before.notna() & df[c].isna()
        log(name, "Invalid cells made missing", invalid.sum(), c)
        if c in ["Full_Name", "Mentor_Name"]:
            changed = before.notna() & df[c].notna() & before.astype(str).ne(df[c].astype(str))
            log(name, "Name whitespace normalized", changed.sum(), "Preserved spelling/case; no title-case guessing")
    if "Score" in df:
        bad = df.Score > df.Max_Score
        log(name, "Score above maximum made missing", bad.sum(), "Will recover only from matching record")
        df.loc[bad, "Score"] = np.nan
    require(not df[KEYS[name]].isna().any().any(), f"{name}: a primary key is missing; cannot infer identity")
    return df


def clean_table(name, original):
    """Normalize -> check conflicts -> recover within keys -> deduplicate."""
    normalized = normalize_table(name, original)
    unique = normalized.drop_duplicates()
    log(name, "Exact rows removed after normalization", len(normalized)-len(unique), "No deduplication by student name")
    conflict = unique.groupby(KEYS[name], dropna=False).transform("nunique").gt(1).any(axis=1)
    if conflict.any():
        keys = unique.loc[conflict, KEYS[name]].head(5).to_dict("records")
        raise DataQualityError(f"{name}: conflicting non-missing values for keys {keys}. Review original records; no arbitrary winner chosen.")
    # first() chooses the first non-null value per column. Conflicts were rejected above.
    clean = unique.groupby(KEYS[name], as_index=False, sort=False, dropna=False).first()[SCHEMA[name]]
    lookup = clean.set_index(KEYS[name])
    for _, row in normalized.iterrows():
        key = tuple(row[k] for k in KEYS[name])
        target = lookup.loc[key if len(key) > 1 else key[0]]
        for c in normalized.columns:
            if pd.isna(row[c]) and c not in KEYS[name] and pd.notna(target[c]):
                CELL_AUDIT.append({"Sheet": name, "Record_Key": record_key(name, row), "Column": c,
                                   "Action": "Recovered from consistent same-key record"})
    log(name, "Additional same-key rows merged", len(unique)-len(clean), "All non-null facts agreed")
    required = [c for c in clean if not (name == "Authentication" and c == "Last_Login")]
    missing = clean[required].isna()
    if missing.any().any():
        examples = [(record_key(name, clean.loc[i]), required[c]) for i, c in zip(*np.where(missing.to_numpy()))]
        raise DataQualityError(f"{name}: unrecoverable required cells: {examples[:8]}. Supply verified values; no imputation or record deletion.")
    # Stable output types, regardless of whether the raw column contained blanks.
    for column in clean:
        if column in NUMBERS:
            clean[column] = clean[column].astype("int64" if column in INTEGER_COLUMNS else "float64")
        elif column in BOOLS:
            clean[column] = clean[column].astype(bool)
    return clean.reset_index(drop=True)


def validate_tables(tables):
    """Check the supplied database's schema, identity, keys and score conventions."""
    check_schema(tables)
    students = tables["Students"]
    ids = set(students.Student_ID)
    assessments = tables["Assessments"].set_index("Assessment_ID")
    for name, df in tables.items():
        require(not df.duplicated(KEYS[name]).any(), f"{name}: duplicate primary key")
        if "Student_ID" in df:
            require(set(df.Student_ID) <= ids, f"{name}: student reference does not exist")
        if "Assessment_ID" in df and name != "Assessments":
            expected = df.Assessment_ID.map(assessments.Student_ID)
            require(expected.notna().all() and expected.eq(df.Student_ID).all(), f"{name}: inconsistent assessment/student relationship")
    for c in ["Roll_No", "College_Email", "Phone_Number"]:
        require(students[c].is_unique, f"Students: repeated {c}; requires review (names need not be unique)")
    for name in ["Authentication", "Career_Profile"]:
        require(tables[name].Student_ID.is_unique, f"{name}: multiple records per student")
        require(set(tables[name].Student_ID) == ids, f"{name}: student coverage mismatch")
    auth = tables["Authentication"]
    require(auth.Roll_No.eq(auth.Student_ID.map(students.set_index("Student_ID").Roll_No)).all(), "Authentication roll-number mismatch")
    require(not (auth.Last_Login.isna() & auth.First_Login.eq(False)).any(), "Returning account has no Last_Login")
    topics = tables["Topic_Scores"]
    subs = tables["Subtopic_Scores"]
    topic_keys = set(map(tuple, topics[["Assessment_ID", "Topic_ID"]].to_numpy()))
    sub_parent_keys = set(map(tuple, subs[["Assessment_ID", "Topic_ID"]].to_numpy()))
    require(topic_keys == sub_parent_keys, "Topic/subtopic parent coverage mismatch")
    require(set(topics.Assessment_ID) == set(assessments.index), "Assessment/topic coverage mismatch")
    for name in ["Topic_Scores", "Subtopic_Scores"]:
        df = tables[name]
        require(np.allclose(df.Score / df.Max_Score * 100, df.Percentage, atol=.011, rtol=0), f"{name}: Score/Percentage inconsistency")
        # These boundaries describe the supplied pseudo scoring convention only.
        labels = np.select([df.Percentage < 50, df.Percentage < 65, df.Percentage < 80],
                           ["Needs Improvement", "Developing", "Strong"], default="Excellent")
        require(df.Performance_Level.eq(labels).all(), f"{name}: score/performance-label mismatch; review, do not relabel silently")
    rollup = subs.groupby(["Assessment_ID", "Topic_ID"]).Percentage.agg(["mean", "size"])
    joined = topics.merge(rollup, left_on=["Assessment_ID", "Topic_ID"], right_index=True, validate="one_to_one")
    require(joined["size"].eq(3).all(), "Source expects three subtopics per topic")
    require(np.allclose(joined.Percentage, joined["mean"], atol=.011, rtol=0), "Topic/subtopic mean mismatch")
    rollup = topics.groupby("Assessment_ID").Percentage.agg(["mean", "size"])
    joined = tables["Assessments"].merge(rollup, left_on="Assessment_ID", right_index=True, validate="one_to_one")
    require(joined["size"].eq(joined.Total_Topics).all(), "Total_Topics mismatch")
    require(np.allclose(joined.Overall_Percentage, joined["mean"], atol=.011, rtol=0), "Assessment/topic mean mismatch")
    require(np.allclose(joined.Total_Score, joined.Overall_Percentage, atol=.011, rtol=0), "Source Total_Score is normalized, not a raw sum")
    expected = np.select([joined.Overall_Percentage < 60, joined.Overall_Percentage < 75], ["Developing", "Near Ready"], default="Placement Ready")
    require(joined.Readiness_Level.eq(expected).all(), "Readiness label disagrees with supplied pseudo score convention")
    for name, date in [("AI_Roadmaps", "Generated_Date"), ("Mentorship", "Session_Date")]:
        df = tables[name]
        require(not (df[date] < df.Assessment_ID.map(assessments.Assessment_Date)).any(), f"{name}: event before assessment")
    mentor_names = tables["Mentorship"].groupby("Mentor_ID").Mentor_Name.nunique()
    require(mentor_names.le(1).all(), "Conflicting names for a Mentor_ID")
    questions = tables["Question_Bank"]
    require(questions[OPTION_COLS].apply(lambda row: len({str(x).strip().casefold() for x in row}) == 4, axis=1).all(), "Question has duplicate answer options")
    # Same-name people, similar question variants and valid rare scores are retained.


BLANK_COLUMNS = {
    "Students": ["Full_Name", "Full_Name", "Current_CGPA", "College_Email", "Phone_Number", "Department", "Semester", "Program", "Batch_Year", "Section", "Roll_No", "Status"],
    "Authentication": ["Roll_No", "Password_Hash", "Account_Status", "First_Login", "Password_Reset_Required", "Failed_Login_Attempts"] * 2,
    "Career_Profile": ["Primary_Field", "Target_Role", "Career_Interest_Level", "Career_Stage", "Open_to_Alternative_Roles", "Goal_Updated_Date"] * 2,
    "Assessments": ["Assessment_Date", "Assessment_Type", "Target_Field", "Target_Role", "Total_Topics", "Total_Score", "Overall_Percentage", "Readiness_Level"] + ["Target_Role", "Total_Score", "Readiness_Level", "Overall_Percentage"],
    "Topic_Scores": ["Topic_Name", "Max_Score", "Score", "Percentage", "Performance_Level"] * 2 + ["Topic_Name", "Score"],
    "Subtopic_Scores": ["Subtopic_Name", "Max_Score", "Score", "Percentage", "Performance_Level"] * 2 + ["Subtopic_Name", "Score"],
    "AI_Roadmaps": ["Weak_Area_Type", "Weak_Area", "Priority", "Recommended_Action", "Suggested_Duration_Weeks", "Alternative_Field", "Alternative_Role", "Reason", "Generated_Date", "Weak_Area", "Priority", "Reason"],
    "Mentorship": ["Weak_Area", "Priority", "Mentor_ID", "Mentor_Name", "Session_Date", "Session_Status", "Mentor_Feedback", "Mentor_Name", "Weak_Area", "Priority", "Mentor_ID", "Session_Date"],
    "Question_Bank": ["Question text", "Option A", "Option B", "Option C", "Option D", "Correct option", "Category", "Branch", "Skill area", "Sub skill area", "Difficulty", "Question text"],
}


def make_raw(source_tables):
    raw, events, summary = {}, [], []
    for name, original in source_tables.items():
        require(len(original) >= 18, f"{name}: need at least 18 rows for this demonstration")
        df = original.copy()
        for i, column in enumerate(BLANK_COLUMNS[name]):
            require(pd.notna(df.loc[i, column]), f"{name}: demonstration cell already missing")
            df.loc[i, column] = np.nan
            events.append((name, i+2, column, "Missing cell", "Matching intact record is appended; no estimated replacement"))
        if name == "Students":
            changes = [("Current_CGPA", 99), ("Full_Name", "  " + str(original.loc[13, "Full_Name"]).replace(" ", "   ") + "  "), ("Department", str(original.loc[14, "Department"]).lower())]
        elif name == "Authentication":
            changes = [("Failed_Login_Attempts", -3), ("Account_Status", "  active  "), ("First_Login", "not-a-boolean")]
        elif name == "Career_Profile":
            changes = [("Goal_Updated_Date", "not-a-date"), ("Career_Stage", "  " + str(original.loc[13, "Career_Stage"]).upper() + "  "), ("Target_Role", "  " + str(original.loc[14, "Target_Role"]) + "  ")]
        elif name == "Assessments":
            changes = [("Overall_Percentage", 999), ("Total_Topics", -1), ("Readiness_Level", "  " + str(original.loc[14, "Readiness_Level"]).lower() + "  ")]
        elif name in ["Topic_Scores", "Subtopic_Scores"]:
            changes = [("Score", 999), ("Percentage", -5), ("Performance_Level", "  " + str(original.loc[14, "Performance_Level"]).upper() + "  ")]
        elif name == "AI_Roadmaps":
            changes = [("Suggested_Duration_Weeks", -2), ("Priority", "  " + str(original.loc[13, "Priority"]).lower() + "  "), ("Generated_Date", "not-a-date")]
        elif name == "Mentorship":
            changes = [("Session_Date", "not-a-date"), ("Mentor_Name", "  " + str(original.loc[13, "Mentor_Name"]).replace(" ", "   ") + "  "), ("Priority", "  " + str(original.loc[14, "Priority"]).lower() + "  ")]
        else:
            changes = [("Correct option", "E"), ("Difficulty", "  " + str(original.loc[13, "Difficulty"]).lower() + "  "), ("Branch", "  " + str(original.loc[14, "Branch"]).lower() + "  ")]
        for i, (column, value) in enumerate(changes, 12):
            df.loc[i, column] = value
            events.append((name, i+2, column, "Abnormal cell", "Range, format or whitespace example; intact same-key record retained"))
        # Ten literal duplicate rows, including their blanks, are visibly appended.
        exact = df.iloc[:10].copy()
        recovery = original.iloc[:15].copy()
        raw[name] = pd.concat([df, exact, recovery], ignore_index=True)
        for i in range(len(df), len(raw[name])):
            detail = "Exact duplicate of a top-row record" if i < len(df)+10 else "Intact recovery copy of an affected record"
            events.append((name, i+2, "", "Duplicate row", detail))
        summary.append((name, len(original), len(raw[name]), 12, 10, 15, 3, "Yellow = blank; orange = abnormal cell; blue = appended duplicate"))
    return raw, pd.DataFrame(events, columns=["Sheet", "Excel_Row", "Column", "Type", "Details"]), pd.DataFrame(summary, columns=["Sheet", "Original_Rows", "Raw_Rows", "Introduced_Missing_Cells", "Exact_Duplicate_Rows", "Recovery_Copy_Rows", "Other_Abnormal_Cells", "Legend"])


def prepare_features(clean):
    students = clean["Students"].sort_values("Student_ID").reset_index(drop=True)
    train, rest = train_test_split(students, test_size=.30, random_state=SEED, stratify=students.Department)
    val, test = train_test_split(rest, test_size=.50, random_state=SEED, stratify=rest.Department)
    assignments = pd.concat([part[["Student_ID"]].assign(Split=name) for name, part in [("Train", train), ("Validation", val), ("Test", test)]], ignore_index=True)
    # No imputer: all missing grades were exactly recovered before splitting.
    scaler = StandardScaler().fit(train[["Current_CGPA"]])
    encoder = OneHotEncoder(handle_unknown="ignore", sparse_output=False).fit(train[["Department"]])
    feature_tables = {}
    for name, part in [("Train", train), ("Validation", val), ("Test", test)]:
        matrix = np.column_stack([scaler.transform(part[["Current_CGPA"]]), encoder.transform(part[["Department"]])])
        df = pd.DataFrame(matrix, columns=["CGPA_Scaled", *encoder.get_feature_names_out(["Department"])])
        df.insert(0, "Student_ID", part.Student_ID.to_numpy())
        feature_tables[f"{name}_Features"] = df
    params = pd.DataFrame([
        ("Random seed", str(SEED)), ("CGPA scaling mean", str(scaler.mean_[0])),
        ("CGPA scaling std (ddof=0)", str(scaler.scale_[0])),
        ("Department vocabulary", json.dumps(encoder.categories_[0].tolist())),
        ("Fit population", "70 training students only"), ("Imputation", "None; original values recovered"),
        ("Model training", "None; fitted scaler/encoder are preprocessing only"),
    ], columns=["Parameter", "Value"])
    return assignments, feature_tables, params


def compare_to_source(source, clean):
    """Only a verification step; source is NEVER used to clean the raw workbook."""
    rows = []
    for name in source:
        expected = normalize_table(name, source[name]).set_index(KEYS[name]).sort_index()
        actual = clean[name].set_index(KEYS[name]).sort_index()
        pd.testing.assert_frame_equal(expected, actual, check_dtype=False, check_exact=True)
        rows.append((name, len(expected), len(actual), "PASS: all original values and keys recovered"))
    return pd.DataFrame(rows, columns=["Sheet", "Source_Rows", "Clean_Rows", "Result"])


def create_reports(raw, clean, splits, params, verification):
    overview, dictionary, stats = [], [], []
    for name, df in clean.items():
        original_keys = raw[name][KEYS[name]].drop_duplicates()
        overview.append((name, len(raw[name]), len(df), len(df.columns), int(raw[name].isna().sum().sum()), int(df.isna().sum().sum()), int(raw[name].duplicated().sum()), int(raw[name].duplicated(KEYS[name]).sum()), len(original_keys)-len(df)))
        for c in df:
            meaning = "Primary/composite key" if c in KEYS[name] else "Foreign reference" if c in ["Student_ID", "Assessment_ID", "Topic_ID"] else "Source data field"
            if c in ["Full_Name", "Roll_No", "College_Email", "Phone_Number", "Password_Hash"]: meaning = "Identity/security; excluded from features"
            if c in ["Total_Score", "Overall_Percentage", "Readiness_Level", "Score", "Percentage"]: meaning = "Supplied assessment evidence; preserved, not a new prediction"
            rule = "Recover only from consistent records with identical key; otherwise stop for review"
            if c == "Last_Login": rule = "Blank allowed for first-login accounts"
            dictionary.append((name, c, str(df[c].dtype), meaning, rule))
    overview = pd.DataFrame(overview, columns=["Sheet", "Raw_Rows", "Clean_Rows", "Columns", "Raw_Null_Cells", "Clean_Null_Cells", "Raw_Exact_Duplicates", "Raw_Extra_Key_Rows", "Original_Records_Lost"])
    for sheet, col in [("Students", "Department"), ("Assessments", "Readiness_Level"), ("Question_Bank", "Branch"), ("Question_Bank", "Category"), ("Question_Bank", "Difficulty")]:
        for group, count in clean[sheet][col].value_counts().items():
            stats.append((sheet, col, str(group), "Count", float(count)))
    for sheet, col in [("Students", "Current_CGPA"), ("Assessments", "Overall_Percentage")]:
        for metric, value in clean[sheet][col].describe().items():
            stats.append((sheet, col, "Original values, no imputation", metric, float(value)))
    joined = clean["Students"][["Student_ID", "Current_CGPA"]].merge(clean["Assessments"][["Student_ID", "Overall_Percentage"]], on="Student_ID")
    stats.append(("Students + Assessments", "CGPA vs Overall_Percentage", "Synthetic association, not causal evidence", "Pearson r", joined.Current_CGPA.corr(joined.Overall_Percentage)))
    notes = [
        ("Scope", "Revised developer preprocessing deliverable; no predictive ML training. Source has AIDS and AIDS(MED), 100 students and 1600 questions."),
        ("Visible raw defects", "Each data sheet contains 12 introduced blanks in its first 12 records, 10 exact duplicate rows, 15 intact recovery copies and 3 other abnormal cells. Yellow/orange/blue fills show these. Existing blank Last_Login cells are not introduced defects."),
        ("Preserving meaning", "All original records, grades, names, career goals, questions, correct answers and labels are retained. No estimated grades, fabricated answers or deleted questions. Original data tables keep their columns; analysis/features are separate."),
        ("Recovery method", "Raw workbook -> schema validation -> safe format/range normalization -> conflict detection -> same-key missing-value recovery -> duplicate collapse -> required-value and relationship checks. Injection log and source workbook are not inputs to cleaning."),
        ("Name handling", "Strip outer whitespace and collapse repeated internal whitespace, including tabs/nonbreaking spaces. Preserve spelling, capitalization, accents, initials, hyphens and apostrophes. Missing names recover by Student_ID only. Numeric suffixes already present in 50 supplied pseudo names are preserved and flagged in Name_Review. Never deduplicate students by name or guess a name from an email."),
        ("Unresolvable abnormalities", "An ambiguous identity, conflicting value, missing required fact without reliable evidence, invalid relationship or inconsistent score stops the run with DataQualityError. Review at source; the pipeline cannot safely invent a correction."),
        ("Natural missingness", "Authentication.Last_Login is legitimately blank for first-login accounts. Students without a supplied mentorship record are not assigned fictitious sessions. These are not automatically errors."),
        ("Numeric and outlier handling", "Check CGPA 0–10, semester 1–8, nonnegative counters, positive durations/score maxima and percentages 0–100. Impossible values recover from intact copies. Valid unusual scores are retained; no clipping or IQR-based deletion."),
        ("Scoring convention", "Source uses three equally weighted subtopics per topic; assessment Total_Topics is checked against actual topic count. Total_Score equals normalized Overall_Percentage. Pseudo performance boundaries are 50/65/80 and readiness boundaries 60/75. Checked, never silently recomputed or relabelled; these are not validated employability thresholds."),
        ("Splits", "70 Train / 15 Validation / 15 Test students, department-stratified, seed 42. Propagate Split_Assignments to all student-related records. No student may cross splits. Question_Bank is shared reference data, not a student feature table."),
        ("Feature preparation", "CGPA StandardScaler and department OneHotEncoder fit on Train only. These are a demonstration, not final readiness predictors. No missing-value imputer is needed because all introduced missing values are recovered exactly."),
        ("Leakage prevention", "Exclude names/contact/authentication and identifiers from predictors (Student_ID retained only as join metadata). Same-assessment score-derived readiness labels, generated roadmaps and mentorship outputs cannot establish independent predictive validity. Updated career profiles may postdate assessments."),
        ("EDA", "Computed descriptive statistics, distributions, missingness and charts are based on the supplied synthetic data. Whole-dataset descriptions are for this preprocessing audit, not model tuning. Use training data for future model-driven EDA."),
        ("Rubric: developer preprocessing", "Implemented loading, normalization, safe recovery, deduplication, validation and output integration. Audit logs and data dictionary support explanation."),
        ("Rubric: model implementation (1.5)", "Deferred under the user's no-model-training instruction. Fitting a scaler/encoder does not fulfil predictive model implementation."),
        ("Rubric: code/integration", "Runnable command-line pipeline and Excel outputs implemented. Model training, dashboard and production application integration remain future work."),
        ("Rubric: explanation/contribution", "Use this code and audit to explain actual behaviour. Demonstrate work you personally reviewed and ran. No invented team allocation, contribution history or guaranteed marks."),
        ("Future methodology", "Collect earlier dated assessments plus separately reviewed later unseen practical-task outcomes. Compare CGPA-only and fixed skill-score baselines with interpretable regression; use student-separated/time-aware evaluation and MAE for numerical outcomes. Final feature/target design requires independent outcomes."),
        ("Limits", "Synthetic data; 100 students with one baseline each; only one Placement Ready label; no item-response table or independent outcomes. Cannot validate placement prediction, longitudinal improvement, answer correctness or role suitability from preprocessing alone."),
        ("Question option review", "571 option cells in 252 source questions are stored as dates, likely Excel-converted fractions. Question_Review records these cells without guessing the lost fraction. Question_Bank retains all 1600 source records; Usable_Questions excludes these 252 questions (1348 remain). Format checks do not prove factual correctness. Obtain original text/CSV to restore affected options."),
        ("Dates", "Supplied October/November 2026 simulation dates are preserved. Future dates alone are not treated as errors. Roadmap/session dates must not precede their assessment."),
        ("Run", "Install pandas numpy openpyxl scikit-learn matplotlib pillow. Run python placement_preprocessing_pipeline.py beside unprocessed_pseudo_dataset.xlsx. --source original.xlsx recreates both outputs and verifies exact recovery. Default cleaning needs only the raw workbook."),
        ("Verification status", verification),
        ("Dependencies used", f"Python {platform.python_version()}, pandas {pd.__version__}, NumPy {np.__version__}, scikit-learn {sklearn.__version__}."),
    ]
    membership = []
    for name, df in clean.items():
        if "Student_ID" in df:
            joined = df.merge(splits, on="Student_ID", validate="many_to_one")
            require(len(joined) == len(df), f"{name}: split assignment lost records")
            for label, count in joined.Split.value_counts().items():
                membership.append((name, label, int(count)))
    name_review = clean["Students"].loc[clean["Students"].Full_Name.str.contains(r"\d"), ["Student_ID", "Full_Name"]].copy()
    name_review["Issue"] = "Numeric text in supplied pseudo name"
    name_review["Action"] = "Preserved unchanged; confirm intended display name before live use"
    # Excel often auto-converts fraction strings to dates. Reversing that conversion
    # is ambiguous: preserve the source and flag it, never guess numerator/denominator.
    question_review = []
    for _, row in clean["Question_Bank"].iterrows():
        for column in OPTION_COLS:
            if re.match(r"^\d{4}-\d{2}-\d{2}(?:[ T].*)?$", str(row[column])):
                question_review.append((row["Question id"], column, str(row[column]),
                                        "Date-like answer option already present in source",
                                        "Exclude question until original text/fraction is verified"))
    question_review = pd.DataFrame(question_review, columns=["Question id", "Column", "Source_Value", "Issue", "Action"])
    blocked = set(question_review["Question id"])
    usable = clean["Question_Bank"].loc[~clean["Question_Bank"]["Question id"].isin(blocked)].copy()
    return {
        "Name_Review": name_review,
        "Question_Review": question_review,
        "Usable_Questions": usable,
        "Data_Overview": overview,
        "Cleaning_Log": pd.DataFrame([row for row in LOG if row["Count"] > 0]),
        "Recovered_Cells": pd.DataFrame(CELL_AUDIT, columns=["Sheet", "Record_Key", "Column", "Action"]).drop_duplicates(),
        "Data_Dictionary": pd.DataFrame(dictionary, columns=["Sheet", "Column", "Data_Type", "Description", "Missing_Value_Rule"]),
        "Split_Assignments": splits.sort_values("Student_ID"),
        "Split_Summary": pd.DataFrame(membership, columns=["Sheet", "Split", "Records"]),
        "Preprocess_Parameters": params,
        "EDA_Statistics": pd.DataFrame(stats, columns=["Sheet", "Column", "Group", "Statistic", "Value"]),
        "Pipeline_Notes": pd.DataFrame(notes, columns=["Area", "Explanation"]),
    }


def preprocess(raw):
    check_schema(raw)
    LOG.clear()
    CELL_AUDIT.clear()
    clean = {name: clean_table(name, df) for name, df in raw.items()}
    validate_tables(clean)
    return clean


def atomic_write(path, tables, charts=None, defects=None):
    # A failed export never replaces a successfully written earlier output.
    temporary = path.with_name(path.stem + '.writing.xlsx')
    try:
        write_workbook(temporary, tables, charts, defects)
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def main():
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", type=Path, help="Optional original source; recreate visible defects then verify recovery")
    parser.add_argument("--input", type=Path, default=here / "unprocessed_pseudo_dataset.xlsx")
    parser.add_argument("--output", type=Path, default=here / "cleaned_pseudo_dataset.xlsx")
    args = parser.parse_args()
    paths = [args.input.resolve(), args.output.resolve()] + ([args.source.resolve()] if args.source else [])
    require(len(paths) == len(set(paths)), "Source, input and output must be different files")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    source = None
    if args.source:
        source = read_tables(args.source)
        check_schema(source)
        # Verify the original is internally usable before injecting defects.
        original_clean = preprocess(source)
        compare_to_source(source, original_clean)
        raw, defects, summary = make_raw(source)
        args.input.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(args.input, {"Defect_Summary": summary, **raw, "Injected_Defects": defects}, defects=defects)
    raw = read_tables(args.input)
    clean = preprocess(raw)
    splits, features, params = prepare_features(clean)
    # Verification is separate from cleaning and cannot supply any missing value.
    if source is not None:
        recovery = compare_to_source(source, clean)
        verification = "PASS: every original key and value restored. Original SHA256: " + hashlib.sha256(args.source.read_bytes()).hexdigest()
    else:
        recovery = pd.DataFrame([(n, len(d), "All raw unique keys retained; relationships/required values checked") for n,d in clean.items()], columns=["Sheet", "Clean_Rows", "Result"])
        verification = "Raw-only run: all raw unique keys retained and internal checks pass. Original comparison runs only with --source; original is not needed for cleaning."
    reports = create_reports(raw, clean, splits, params, verification)
    reports["Recovery_Check"] = recovery
    charts = make_charts(clean, reports)
    overview = reports.pop("Data_Overview")
    atomic_write(args.output, {"Data_Overview": overview, **clean, **reports, **features}, charts=charts)
    print(overview.to_string(index=False))
    print(f"Student split: {splits.Split.value_counts().to_dict()}")
    print("No original records dropped; no guessed grades, names or answers; no predictive model trained. Read Name_Review and Question_Review for existing source issues.")
    print(f"Saved: {args.output}")


if __name__ == "__main__":
    try:
        main()
    except DataQualityError as error:
        raise SystemExit(f"DATA QUALITY REVIEW REQUIRED: {error}")

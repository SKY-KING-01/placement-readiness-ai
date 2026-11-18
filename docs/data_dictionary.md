# Source data dictionary

## unprocessed_pseudo_dataset (1).xlsx

Dimensions exclude the header. Types describe nonempty Excel cells as read by openpyxl.

### Defect_Summary

9 records × 8 columns.

| Column | Observed types | Missing |
| --- | --- | ---: |
| Sheet | str | 0 |
| Original_Rows | int | 0 |
| Raw_Rows | int | 0 |
| Introduced_Missing_Cells | int | 0 |
| Exact_Duplicate_Rows | int | 0 |
| Recovery_Copy_Rows | int | 0 |
| Other_Abnormal_Cells | int | 0 |
| Legend | str | 0 |

### Students

125 records × 12 columns.

| Column | Observed types | Missing |
| --- | --- | ---: |
| Student_ID | str | 0 |
| Roll_No | str | 1 |
| Full_Name | str | 4 |
| Program | str | 2 |
| Department | str | 2 |
| Semester | int | 2 |
| Batch_Year | int | 2 |
| Section | str | 2 |
| College_Email | str | 2 |
| Phone_Number | str | 2 |
| Current_CGPA | float, int | 2 |
| Status | str | 1 |

### Authentication

125 records × 8 columns.

| Column | Observed types | Missing |
| --- | --- | ---: |
| Student_ID | str | 0 |
| Roll_No | str | 4 |
| Password_Hash | str | 4 |
| Account_Status | str | 4 |
| First_Login | bool, str | 4 |
| Password_Reset_Required | bool | 3 |
| Last_Login | — | 125 |
| Failed_Login_Attempts | int | 3 |

### Career_Profile

125 records × 8 columns.

| Column | Observed types | Missing |
| --- | --- | ---: |
| Career_Profile_ID | str | 0 |
| Student_ID | str | 0 |
| Primary_Field | str | 4 |
| Target_Role | str | 4 |
| Career_Interest_Level | str | 4 |
| Career_Stage | str | 4 |
| Open_to_Alternative_Roles | str | 3 |
| Goal_Updated_Date | datetime, str | 3 |

### Assessments

125 records × 10 columns.

| Column | Observed types | Missing |
| --- | --- | ---: |
| Assessment_ID | str | 0 |
| Student_ID | str | 0 |
| Assessment_Date | datetime | 2 |
| Assessment_Type | str | 2 |
| Target_Field | str | 2 |
| Target_Role | str | 4 |
| Total_Topics | int | 2 |
| Total_Score | float, int | 4 |
| Overall_Percentage | float, int | 3 |
| Readiness_Level | str | 3 |

### Topic_Scores

725 records × 8 columns.

| Column | Observed types | Missing |
| --- | --- | ---: |
| Assessment_ID | str | 0 |
| Student_ID | str | 0 |
| Topic_ID | str | 0 |
| Topic_Name | str | 5 |
| Max_Score | int | 4 |
| Score | float, int | 5 |
| Percentage | float, int | 4 |
| Performance_Level | str | 4 |

### Subtopic_Scores

2,125 records × 9 columns.

| Column | Observed types | Missing |
| --- | --- | ---: |
| Assessment_ID | str | 0 |
| Student_ID | str | 0 |
| Topic_ID | str | 0 |
| Subtopic_ID | str | 0 |
| Subtopic_Name | str | 5 |
| Max_Score | int | 4 |
| Score | int | 5 |
| Percentage | int | 4 |
| Performance_Level | str | 4 |

### AI_Roadmaps

316 records × 12 columns.

| Column | Observed types | Missing |
| --- | --- | ---: |
| Roadmap_ID | str | 0 |
| Student_ID | str | 0 |
| Assessment_ID | str | 0 |
| Weak_Area_Type | str | 2 |
| Weak_Area | str | 4 |
| Priority | str | 3 |
| Recommended_Action | str | 2 |
| Suggested_Duration_Weeks | int | 2 |
| Alternative_Field | str | 2 |
| Alternative_Role | str | 2 |
| Reason | str | 3 |
| Generated_Date | datetime, str | 2 |

### Mentorship

105 records × 10 columns.

| Column | Observed types | Missing |
| --- | --- | ---: |
| Mentorship_ID | str | 0 |
| Student_ID | str | 0 |
| Assessment_ID | str | 0 |
| Weak_Area | str | 4 |
| Priority | str | 4 |
| Mentor_ID | str | 3 |
| Mentor_Name | str | 4 |
| Session_Date | datetime, str | 3 |
| Session_Status | str | 2 |
| Mentor_Feedback | str | 2 |

### Question_Bank

1,625 records × 12 columns.

| Column | Observed types | Missing |
| --- | --- | ---: |
| Question id | str | 0 |
| Category | str | 2 |
| Branch | str | 2 |
| Question text | str | 3 |
| Option A | datetime, float, int, str | 2 |
| Option B | datetime, float, int, str | 2 |
| Option C | datetime, float, int, str | 2 |
| Option D | datetime, float, int, str | 2 |
| Correct option | str | 2 |
| Skill area | str | 2 |
| Sub skill area | str | 2 |
| Difficulty | str | 1 |

### Injected_Defects

360 records × 5 columns.

| Column | Observed types | Missing |
| --- | --- | ---: |
| Sheet | str | 0 |
| Excel_Row | int | 0 |
| Column | str | 225 |
| Type | str | 0 |
| Details | str | 0 |

## cleaned_pseudo_dataset (1).xlsx

Dimensions exclude the header. Types describe nonempty Excel cells as read by openpyxl.

### Data_Overview

9 records × 9 columns.

| Column | Observed types | Missing |
| --- | --- | ---: |
| Sheet | str | 0 |
| Raw_Rows | int | 0 |
| Clean_Rows | int | 0 |
| Columns | int | 0 |
| Raw_Null_Cells | int | 0 |
| Clean_Null_Cells | int | 0 |
| Raw_Exact_Duplicates | int | 0 |
| Raw_Extra_Key_Rows | int | 0 |
| Original_Records_Lost | int | 0 |

### Students

100 records × 12 columns.

| Column | Observed types | Missing |
| --- | --- | ---: |
| Student_ID | str | 0 |
| Roll_No | str | 0 |
| Full_Name | str | 0 |
| Program | str | 0 |
| Department | str | 0 |
| Semester | int | 0 |
| Batch_Year | int | 0 |
| Section | str | 0 |
| College_Email | str | 0 |
| Phone_Number | str | 0 |
| Current_CGPA | float, int | 0 |
| Status | str | 0 |

### Authentication

100 records × 8 columns.

| Column | Observed types | Missing |
| --- | --- | ---: |
| Student_ID | str | 0 |
| Roll_No | str | 0 |
| Password_Hash | str | 0 |
| Account_Status | str | 0 |
| First_Login | bool | 0 |
| Password_Reset_Required | bool | 0 |
| Last_Login | — | 100 |
| Failed_Login_Attempts | int | 0 |

### Career_Profile

100 records × 8 columns.

| Column | Observed types | Missing |
| --- | --- | ---: |
| Career_Profile_ID | str | 0 |
| Student_ID | str | 0 |
| Primary_Field | str | 0 |
| Target_Role | str | 0 |
| Career_Interest_Level | str | 0 |
| Career_Stage | str | 0 |
| Open_to_Alternative_Roles | str | 0 |
| Goal_Updated_Date | datetime | 0 |

### Assessments

100 records × 10 columns.

| Column | Observed types | Missing |
| --- | --- | ---: |
| Assessment_ID | str | 0 |
| Student_ID | str | 0 |
| Assessment_Date | datetime | 0 |
| Assessment_Type | str | 0 |
| Target_Field | str | 0 |
| Target_Role | str | 0 |
| Total_Topics | int | 0 |
| Total_Score | float, int | 0 |
| Overall_Percentage | float, int | 0 |
| Readiness_Level | str | 0 |

### Topic_Scores

700 records × 8 columns.

| Column | Observed types | Missing |
| --- | --- | ---: |
| Assessment_ID | str | 0 |
| Student_ID | str | 0 |
| Topic_ID | str | 0 |
| Topic_Name | str | 0 |
| Max_Score | int | 0 |
| Score | float, int | 0 |
| Percentage | float, int | 0 |
| Performance_Level | str | 0 |

### Subtopic_Scores

2,100 records × 9 columns.

| Column | Observed types | Missing |
| --- | --- | ---: |
| Assessment_ID | str | 0 |
| Student_ID | str | 0 |
| Topic_ID | str | 0 |
| Subtopic_ID | str | 0 |
| Subtopic_Name | str | 0 |
| Max_Score | int | 0 |
| Score | int | 0 |
| Percentage | int | 0 |
| Performance_Level | str | 0 |

### AI_Roadmaps

291 records × 12 columns.

| Column | Observed types | Missing |
| --- | --- | ---: |
| Roadmap_ID | str | 0 |
| Student_ID | str | 0 |
| Assessment_ID | str | 0 |
| Weak_Area_Type | str | 0 |
| Weak_Area | str | 0 |
| Priority | str | 0 |
| Recommended_Action | str | 0 |
| Suggested_Duration_Weeks | int | 0 |
| Alternative_Field | str | 0 |
| Alternative_Role | str | 0 |
| Reason | str | 0 |
| Generated_Date | datetime | 0 |

### Mentorship

80 records × 10 columns.

| Column | Observed types | Missing |
| --- | --- | ---: |
| Mentorship_ID | str | 0 |
| Student_ID | str | 0 |
| Assessment_ID | str | 0 |
| Weak_Area | str | 0 |
| Priority | str | 0 |
| Mentor_ID | str | 0 |
| Mentor_Name | str | 0 |
| Session_Date | datetime | 0 |
| Session_Status | str | 0 |
| Mentor_Feedback | str | 0 |

### Question_Bank

1,600 records × 12 columns.

| Column | Observed types | Missing |
| --- | --- | ---: |
| Question id | str | 0 |
| Category | str | 0 |
| Branch | str | 0 |
| Question text | str | 0 |
| Option A | str | 0 |
| Option B | str | 0 |
| Option C | str | 0 |
| Option D | str | 0 |
| Correct option | str | 0 |
| Skill area | str | 0 |
| Sub skill area | str | 0 |
| Difficulty | str | 0 |

### Name_Review

50 records × 4 columns.

| Column | Observed types | Missing |
| --- | --- | ---: |
| Student_ID | str | 0 |
| Full_Name | str | 0 |
| Issue | str | 0 |
| Action | str | 0 |

### Question_Review

571 records × 5 columns.

| Column | Observed types | Missing |
| --- | --- | ---: |
| Question id | str | 0 |
| Column | str | 0 |
| Source_Value | str | 0 |
| Issue | str | 0 |
| Action | str | 0 |

### Usable_Questions

1,348 records × 12 columns.

| Column | Observed types | Missing |
| --- | --- | ---: |
| Question id | str | 0 |
| Category | str | 0 |
| Branch | str | 0 |
| Question text | str | 0 |
| Option A | str | 0 |
| Option B | str | 0 |
| Option C | str | 0 |
| Option D | str | 0 |
| Correct option | str | 0 |
| Skill area | str | 0 |
| Sub skill area | str | 0 |
| Difficulty | str | 0 |

### Cleaning_Log

34 records × 4 columns.

| Column | Observed types | Missing |
| --- | --- | ---: |
| Sheet | str | 0 |
| Action | str | 0 |
| Count | int | 0 |
| Details | str | 0 |

### Recovered_Cells

122 records × 4 columns.

| Column | Observed types | Missing |
| --- | --- | ---: |
| Sheet | str | 0 |
| Record_Key | str | 0 |
| Column | str | 0 |
| Action | str | 0 |

### Data_Dictionary

89 records × 5 columns.

| Column | Observed types | Missing |
| --- | --- | ---: |
| Sheet | str | 0 |
| Column | str | 0 |
| Data_Type | str | 0 |
| Description | str | 0 |
| Missing_Value_Rule | str | 0 |

### Split_Assignments

100 records × 2 columns.

| Column | Observed types | Missing |
| --- | --- | ---: |
| Student_ID | str | 0 |
| Split | str | 0 |

### Split_Summary

24 records × 3 columns.

| Column | Observed types | Missing |
| --- | --- | ---: |
| Sheet | str | 0 |
| Split | str | 0 |
| Records | int | 0 |

### Preprocess_Parameters

7 records × 2 columns.

| Column | Observed types | Missing |
| --- | --- | ---: |
| Parameter | str | 0 |
| Value | str | 0 |

### EDA_Statistics

30 records × 5 columns.

| Column | Observed types | Missing |
| --- | --- | ---: |
| Sheet | str | 0 |
| Column | str | 0 |
| Group | str | 0 |
| Statistic | str | 0 |
| Value | float, int | 0 |

### Pipeline_Notes

24 records × 2 columns.

| Column | Observed types | Missing |
| --- | --- | ---: |
| Area | str | 0 |
| Explanation | str | 0 |

### Recovery_Check

9 records × 4 columns.

| Column | Observed types | Missing |
| --- | --- | ---: |
| Sheet | str | 0 |
| Source_Rows | int | 0 |
| Clean_Rows | int | 0 |
| Result | str | 0 |

### Train_Features

70 records × 4 columns.

| Column | Observed types | Missing |
| --- | --- | ---: |
| Student_ID | str | 0 |
| CGPA_Scaled | float | 0 |
| Department_AIDS | int | 0 |
| Department_AIDS(MED) | int | 0 |

### Validation_Features

15 records × 4 columns.

| Column | Observed types | Missing |
| --- | --- | ---: |
| Student_ID | str | 0 |
| CGPA_Scaled | float | 0 |
| Department_AIDS | int | 0 |
| Department_AIDS(MED) | int | 0 |

### Test_Features

15 records × 4 columns.

| Column | Observed types | Missing |
| --- | --- | ---: |
| Student_ID | str | 0 |
| CGPA_Scaled | float | 0 |
| Department_AIDS | int | 0 |
| Department_AIDS(MED) | int | 0 |

### EDA_Charts

0 records × 1 columns.

| Column | Observed types | Missing |
| --- | --- | ---: |
| — | Chart or empty sheet | — |

See `migration_mapping.md` for primary keys, destinations, and validation rules.

# Source to PostgreSQL mapping

| Source sheet | Identity and destination | Handling |
| --- | --- | --- |
| Students | Student_ID → students.id | Keep synthetic email, display name, department and roll number. Imported accounts start disabled. |
| Authentication | Student_ID → existing user and student | Keep source file as the audit record. Exclude workbook password hashes and contact information from login and ML. |
| Career_Profile | Career_Profile_ID → career_profiles.source_id | Link the student and normalized role. Profile date is not assumed to be historical assessment evidence. |
| Assessments | Assessment_ID → assessments.id | Preserve type, date, reported readiness, target role and numeric score. Store role-weighted readiness separately. |
| Topic_Scores | Assessment_ID + Topic_ID → scoped source key in topic_scores | Keep the original identifiers, points, percentages and source labels. Normalize topic names to stable taxonomy IDs. |
| Subtopic_Scores | Assessment_ID + Topic_ID + Subtopic_ID → scoped key in subtopic_scores | Normalize names within their parent topic and preserve original keys. |
| AI_Roadmaps | Roadmap_ID → learning_roadmaps.id | Preserve as source guidance with provenance. Generated roadmaps for registered users are separate. |
| Mentorship | Mentorship_ID → mentorship_sessions.id | Preserve source evidence and mentor ID. A historical session grants no account access. |
| Question_Bank | Question id → questions.id | Preserve approved-format options and answer keys internally. Retain flagged records separately from questions eligible for selection. |
| Question_Review | Question id + Column → question_reviews | Existing Excel date conversion is visible for review. |
| Usable_Questions | Question id eligibility reference | Format-only evidence. Imported variants are tagged as practice without verified company attribution. |
| Reports, splits and feature sheets | Audit-only | Recompute longitudinal features from dated standardized assessments. |

The pipeline checks nonempty core keys, matching ownership, unique identifiers, valid category and range values, positive maxima, score rollups and event-date order. The PostgreSQL import runs inside a transaction and keeps existing records on a repeat import. Prototype weights and blueprint versions are stored separately from the source.

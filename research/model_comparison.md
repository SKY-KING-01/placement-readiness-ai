# Model comparison

Validation average precision selected **Random Forest** for classification. The test set contains 7 positives and 8 negatives. At the validation threshold of 0.30, the model identified all seven positives and also flagged seven negatives. Test ROC-AUC was 0.768, average precision 0.799 and Brier score 0.213. Logistic Regression had a slightly better test F1, but the test set did not determine model selection.

Validation MAE selected **Random Forest** for future-score regression. Held-out MAE was 2.33 points, RMSE was 2.82, and R² was 0.872. The last-score baseline had MAE 2.72. The separate calendar-forward regression test also favored Random Forest, with MAE 2.32 over 15 later outcomes compared with 2.72 for the last-score baseline.

See the individual CSV comparisons, precision–recall curve, regression scatter plot and limitations. These results reflect synthetic trajectories only.

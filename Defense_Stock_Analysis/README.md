# cristian-mihalache.github.io

2nd project 
# Defense Sector Tactical Suite
**Quantitative Analysis & Machine Learning Portfolio**

An advanced algorithmic framework for predicting and managing a global portfolio of defense stocks (Rheinmetall, Kratos, Leonardo, etc.).

### Key Features
* **Ensemble Modeling:** Combines Lasso Regression (Stability) with Random Forest (Directional Edge).
* **Dynamic Risk Management:** Inverse-Volatility position sizing to equalize portfolio risk.
* **Algorithmic Guardrails:** 2-Sigma Volatility-based Stop Losses and Sector Breadth filters.
* **Tech Stack:** Python 3.13, Scikit-Learn, Pandas, Matplotlib.

### Tactical Logic
The system uses a **Strict Threshold** (70th percentile) to identify high-conviction entries, moving to **Cash** during periods of low sector breadth to preserve capital.

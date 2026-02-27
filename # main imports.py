# main imports
#main funcitonalities
import pandas as pd
import numpy as np 
import warnings
import time
import os
import random
import requests
warnings.filterwarnings('ignore')
# Visualisations
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.graph_objects as go 
import plotly.express as px
from plotly.subplots import make_subplots
import plotly.io as pio
#ML
from sklearn.model_selection import train_test_split, cross_val_score, GridSearchCV
from sklearn.preprocessing import StandardScaler, OneHotEncoder, LabelEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.metrics import (accuracy_score, precision_score, recall_score, f1_score, 
                             roc_auc_score, confusion_matrix, classification_report, roc_curve, precision_recall_curve)
#Models
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, AdaBoostClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.naive_bayes import GaussianNB
import xgboost as xgb
# Data
import yfinance as yf


headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}
portfolio_tickers =["AM.PA", "SAF","RHM","ACLN","7014.T","7003.T","300589.SZ","688287.SS","BAESF","KTOS"]


os.makedirs('defense_portfolio_data', exist_ok = True)
session = requests.Session()
session.headers.update(headers)
for ticker in portfolio_tickers:
    clean_name = ticker.replace(".","_")
   
    filename = f"defense_portfolio_data/{ticker.replace(".","_")}.csv"
    if os.path.exists(filename):
        print(f"skipping {ticker}, file already exists")
        continue
    print(f"Downloading data for {ticker}...")

    max_retries = 3

    for attempt in range (max_retries):
        try:
            data = yf.download(ticker, start= "2023/01/01", end="2026/01/01", auto_adjust=True, session=session)

            if not data.empty:
                data.to_csv(filename)
                print(f"successfully save {ticker} to {filename}")

                time.sleep(random.uniform(3,7))
                break
            else:
                print(f"attempt {attempt +1}:{ticker} returned empty data")
                time.sleep(10)
        except Exception as e:
            print(f"Error with {ticker} on attempt {attempt+1}:{e}")
            time.sleep(20)
print("success")                    

print("great success")
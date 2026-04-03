import os
import pandas as pd
import numpy as np
import re
import argparse
from datetime import datetime
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler
import matplotlib.pyplot as plt
from openpyxl import load_workbook
from openpyxl.drawing.image import Image
 

FILE_NAME = 'JE_Sampler.xlsx'
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FILE_PATH = os.path.join(BASE_DIR, FILE_NAME)

ACCOUNT_DERIVATIVES = {
    'cash': ['cash', 'bank', 'funds', 'savings', 'liquid', 'petty', 'clearing'],
    'receivables': ['receivable', 'debtor', 'ar', 'a/r', 'customer', 'trade rec'],
    'payables': ['payable', 'creditor', 'ap', 'a/p', 'vendor', 'supplier', 'accrued'],
    'interest': ['interest', 'finance', 'yield', 'coupon', 'int inc', 'int exp'],
    'safe_narratives': [r'\(rev\)', 'reversal', 'storno', 'swap', 'hedge', 'mtm', 'valuation','recharge', 'reclass', 'adjust']
}

def us_date_to_datetime(date_str: str):
    """
    Convert a US format date (MM/DD/YYYY or M/D/YY) to datetime.
    Handles time components and already ISO‑like strings.
    Returns NaT if parsing fails.
    """
    if pd.isna(date_str):
        return pd.NaT
    if not isinstance(date_str, str):
        try:
            return pd.to_datetime(date_str)
        except:
            return pd.NaT

    date_str = date_str.strip()
    # Already ISO? (YYYY-MM-DD...)
    if re.match(r'^\d{4}-\d{2}-\d{2}', date_str):
        return pd.to_datetime(date_str, errors='coerce')

    # Extract date part before any space or 'T'
    date_part = date_str.split()[0]

    # Try common US formats (with and without leading zeros)
    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(date_part, fmt)
        except ValueError:
            continue

    # Fallback: let pandas guess (dayfirst=False because it's US)
    return pd.to_datetime(date_str, errors='coerce', dayfirst=False)

def eu_date_to_datetime(date_str: str):
    """
    Convert a European format date (DD/MM/YYYY or D/M/YY) to datetime.
    Returns NaT if parsing fails.
    """
    if pd.isna(date_str):
        return pd.NaT
    if not isinstance(date_str, str):
        try:
            return pd.to_datetime(date_str)
        except:
            return pd.NaT

    date_str = date_str.strip()
    if re.match(r'^\d{4}-\d{2}-\d{2}', date_str):
        return pd.to_datetime(date_str, errors='coerce')

    date_part = date_str.split()[0]

    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(date_part, fmt)
        except ValueError:
            continue

    # Fallback with dayfirst=True for EU style
    return pd.to_datetime(date_str, errors='coerce', dayfirst=True)


class DataLoader :
    #handling the  dynamic mapping of the lead and mapping tabs
    def __init__(self, file_path):
        self.file_path = file_path
        self.sheets = pd.read_excel(file_path, sheet_name=None, dtype=str)
        self._convert_gl_dates()

    def _convert_gl_dates(self):
        """Convert the posting date column in GL_raw to datetime using the US/EU flag."""
        gl_raw = self.sheets.get('GL_raw')
        if gl_raw is None:
            return

        # 1. Find the correct column name (hardcoded to 'Posted_Date' as in the given file)
        date_col = 'Posted_Date'
        if date_col not in gl_raw.columns:
            # If the column is not named exactly 'Posted_Date', fallback to the first column
            # that contains 'date' in its name (case‑insensitive)
            for col in gl_raw.columns:
                if 'date' in col.lower():
                    date_col = col
                    break
            else:
                return  # no date column found

        # 2. Get the US date flag from the Lead sheet
        is_us = self.get_us_date_toggle()

        # 3. Apply the appropriate conversion
        converter = us_date_to_datetime if is_us else eu_date_to_datetime
        gl_raw[date_col] = gl_raw[date_col].apply(converter)

        # 4. Store the converted datetime in a new column (optional, but keeps original if needed)
        gl_raw['Posted_Date_DT'] = gl_raw[date_col]


    
    def get_config_value(self, label):
        lead_df = self.sheets['Lead']
        for row_idx, row in lead_df.iterrows():
            for col_idx, value in enumerate(row):
                if str(value).strip().lower() == label.lower():
                    if col_idx + 1 < len(lead_df.columns):
                        return lead_df.iloc[row_idx, col_idx + 1]
        return None
    
    def get_config_list(self, zone_label):
        lead_df = self.sheets['Lead']
        data_list = []
        found = False
        for _, row in lead_df.iterrows():
            row_vals = [str(v).strip().lower() for v in row if pd.notnull(v)]
            if zone_label.lower() in row_vals:
                found = True
                continue
            if found:
                col_idx = 1 if "Zone E" in zone_label else (4 if "Zone D" in zone_label else 0)
                val = row.iloc[col_idx]
                if pd.notnull(val) and str(val).strip() != "":
                    data_list.append(str(val).strip())
                else: break
        return data_list
    
    def get_system_exclusions(self):
        """ retrieves automated system names from the zone f for HRC6"""

        lead_df = self.sheets['Lead']
        exclusions = []

        found = False
        for _, row in lead_df.iterrows():
            row_vals = [str(v).strip().lower() for v in row if pd.notnull(v)]
            if 'zone f' in row_vals:
                found = True
                continue
            if found:
                val = row.iloc[0]
                if pd.notnull(val) and str(val).strip() != "":
                    exclusions.append(str(val).strip())
        return exclusions            
                

    def get_active_hrcs(self):
        hrc_config = {}
        lead_df = self.sheets['Lead']
        for row_idx, row in lead_df.iterrows():
            for col_idx, value in enumerate(row):
                val_str = str(value)
                if any(x in val_str for x in ["HRC", "Benford", "KNN", "Completeness"]):
                    if col_idx + 1 < len(lead_df.columns):
                        toggle = str(lead_df.iloc[row_idx, col_idx+1]).lower()
                        hrc_config[val_str] = toggle.strip()in ['y', 'yes', 'true']
        return hrc_config
    
    def get_us_date_toggle(self):
        val = self.get_config_value("GL contains US format dates")
        if val is None:
            return False   # default to European format
        return str(val).strip().lower() in ['y', 'yes', 'true']         
    
    def get_cleaned_mapping(self):
        mapping_df = self.sheets['Mapping']
        header_row_index = None
        for i, row in mapping_df.iterrows():
            if 'Accounts' in row.values:
                header_row_index = i
                break
                
        if header_row_index is not None:
            raw_headers = [str(h).strip() for h in mapping_df.iloc[header_row_index]]
            mapping_df = mapping_df.iloc[header_row_index+1:].reset_index(drop=True)
            

            unique_headers = []
            counts = {}
            for h in raw_headers:
                if h in counts:
                    counts[h] += 1
                    unique_headers.append(f"{h}_{counts[h]}")
                else:
                    counts[h] = 0
                    unique_headers.append(h)
            mapping_df.columns = unique_headers

            renamer = {}
            for col in mapping_df.columns:
                c_low = col.lower()
                if 'sub' in c_low and 'category' in c_low: renamer[col] = 'Sub-Category'
                elif 'opening' in c_low: renamer[col] = 'Opening'
                elif 'closing' in c_low: renamer[col] = 'Closing'
                elif col == 'Mapping_1': renamer[col] = 'Mapping' # This is the nature (Income/Expense)
                elif col == 'Mapping': renamer[col] = 'Account_Description' # This is the name
            
            mapping_df = mapping_df.rename(columns=renamer)
            return mapping_df.dropna(subset=['Accounts']).reset_index(drop=True)
    
    def get_date_format(self):
        return self.get_config_value("date")
        


class DataCleaner: 
    #performs the 'Opening balances" removal if at nil 

    def __init__(self, raw_df, config, is_us_format = False):
        self.df = raw_df
        self.config = config
        self.is_us_format = is_us_format

    def clean_data(self):
        #Standardise columns names based on the zone A mapping
        rename_map ={
            self.config['acct_header']:'accode',
            self.config['desc_header']:'Narrative',
            self.config['date_header']:'Posted_Date_Raw',
            self.config['batch_header']:'Batch_No',
            self.config['debit_header']:'Debit',
            self.config['credit_header']:'Credit',
            self.config['user_header']:'UserId',
        }
        self.df = self.df.rename(columns=rename_map)
        
    
        if 'Posted_Date_DT' in self.df.columns:
            self.df['Posted_Date'] = self.df['Posted_Date_DT']
        else:
            # Fallback: if conversion didn't happen, try a safe parse
            self.df['Posted_Date'] = pd.to_datetime(self.df['Posted_Date_Raw'], errors='coerce')

        # Create a display column (string)
        self.df['Posted_Date_Display'] = self.df['Posted_Date'].dt.strftime('%Y-%m-%d %H:%M')
        

        #target clean remove open balances with 0 values

        mask = (self.df['Narrative'].str.contains('Open Balance', na = False)) & \
                (self.df['Debit']==0) & (self.df['Credit']==0)
        self.df = self.df[~mask] # ~ inverts the boolean factor true to false and reverse

        #create the net amount column for analysis
        self.df['Debit'] = pd.to_numeric(self.df['Debit'], errors='coerce').fillna(0)
        self.df['Credit'] = pd.to_numeric(self.df['Credit'], errors='coerce').fillna(0)
        self.df ['Net_Amount'] = self.df['Debit'].fillna(0)-self.df['Credit'].fillna(0)
        
        return self.df
    
    
    

class ForensicEngine:
    #the core logic for HRC1 thorugh HRC 9

    def __init__(self, df, mapping_df, active_hrcs, config):
        self.df = df
        self.mapping = mapping_df.dropna(subset=['Accounts'])
        self.active = active_hrcs
        self.ampt = config['materiality']
        self.year_end = pd.to_datetime(config['year_end'])
        self.cut_off = pd.to_datetime(config['cut_off'])
        self.flags = pd.DataFrame()
        self.potential_hits = pd.DataFrame()

        merged = self.df.merge(self.mapping, left_on='accode', right_on='Accounts', how='left')
        self.df = merged.loc[:, ~merged.columns.duplicated()].reset_index(drop=True)

    #helper functions to pad and extract narrative context, does not participate in the data analysis
    def _get_snippet(self, text, word):
        text = str(text).lower()
        word = word.lower()
        idx = text.find(word)
        if idx == -1: return ""

        start = max(0, idx -10)
        end = min(len(text), idx + len(word)+10)

        snippet = text[start:end]

        #padding for visual consistency in excel

        pre = " " * (10-(idx - start)) if (idx - start)<10 else "..."
        post = " " * (10-(end -(idx + len(word)))) if (end - (idx + len(word))) < 10 else "..."
        return f"{pre}{snippet}{post}"
    
    def _get_account_buckets(self):
        #categorises accounts based on the mapping typology for relationship testing
        

        #detection of mapping for cash, accounts receivables, accounts payables

        def find_accounts(keys):
            pattern = '|'.join(keys)
            return self.mapping[
                self.mapping['Sub-Category'].str.contains(pattern, case=False, na=False) |
                self.mapping['Mapping'].str.contains(pattern, case=False, na=False)
            ]['Accounts'].tolist()

        return {
            'cash': find_accounts(ACCOUNT_DERIVATIVES['cash']),
            'receivables': find_accounts(ACCOUNT_DERIVATIVES['receivables']),
            'payables': find_accounts(ACCOUNT_DERIVATIVES['payables']),
            'offsets': find_accounts(ACCOUNT_DERIVATIVES['safe_narratives']),
            'pnl': self.mapping[self.mapping['Mapping'].str.contains('Income|Expense', case=False, na=False)]['Accounts'].tolist(),
            'interest': self.mapping[self.mapping['Account_Description'].str.contains('Interest', case=False, na=False)]['Accounts'].tolist()
        }
    
    def is_reversal_batch(self, batch_df):
        """return true if the batch is an expected reversal"""
        rev_keywords = ['(rev)','reversal','storno', 'reverse', 'accrual rev']

        if 'RevFlag' in batch_df.columns:
            if (batch_df['RevFlag']==1).any():
                return True
        if batch_df['Narrative'].str.contains('|'.join(rev_keywords), case=False, na=False).any():
            return True
        return False
    

    def run_completeness_test(self):
        """ roll forward opening + transactional net = closing (BS accounts only)"""
        
        if not self.active.get('Completeness Test'): return 
        
        bs_categories = ['Asset', 'Liability', 'Equity']
        bs_df = self.df[self.df['Mapping'].isin(bs_categories)].copy()
        if bs_df.empty: return

        # Changed 'Account_name' to 'Account_Description' in the aggregation
        activity = bs_df.groupby('accode').agg({
            'Debit': 'sum', 'Credit': 'sum', 'Net_Amount': 'sum', 'Account_Description': 'first'
        }).reset_index()

        activity = activity.merge(self.mapping[['Accounts', 'Opening', 'Closing']],
                                  left_on='accode', right_on='Accounts', how='left')
        
        activity['Calculated_Closing'] = activity['Opening'].fillna(0) + activity['Net_Amount']
        activity['Difference'] = activity['Calculated_Closing'] - activity['Closing'].fillna(0)

        self.completeness_report = activity[abs(activity['Difference']) > 0.05].copy()
    
    def run_hrc1(self):
        #out of balance journals with a tolerance of 0.05

        if not self.active.get('HRC1'):return

        #group by batch
        batch_sums = self.df.groupby('Batch_No').agg({
        'Net_Amount': 'sum',
        'Debit': 'sum',
        'Credit': 'sum'
        }).reset_index()

        #fitlter out the batches that are entirely zero (memos/ system house-keeps)
        batch_sums = batch_sums[(batch_sums['Debit'] !=0) | (batch_sums['Credit'] != 0)]

        #mathematical imbalance
        imbalanced_batches = batch_sums[abs(batch_sums['Net_Amount'])>0.05]['Batch_No']
        hrc1_extract = self.df[self.df['Batch_No'].isin(imbalanced_batches)].copy()
        hrc1_extract['Reason'] = 'HRC1: Mathematical imbalance Debit not equal Credit'
        self.flags = pd.concat([self.flags, hrc1_extract], ignore_index=True)

        # Structural imbalance (only debits or only credits)
        structural = batch_sums[(abs(batch_sums['Net_Amount']) <= 0.05) & ((batch_sums['Debit'] == 0) | (batch_sums['Credit'] == 0))]['Batch_No']
        hrc1_pot = self.df[self.df['Batch_No'].isin(structural)].copy()
        hrc1_pot['Reason'] = 'HRC1: Structural imbalance (Single-sided)'
        self.potential_hits = pd.concat([self.potential_hits, hrc1_pot],ignore_index=True)

    #HRCs 2 to 4 are propriatery, please contact the owner if interested in full version.

    def run_hrc5(self, s_acct):
        if not self.active.get('HRC5'): return
        noise = '|'.join(['opening balance', 'rollforward', 'b/fwd', 'ob', 'brought forward', 'Open Balance'])
        clean_df = self.df[(~self.df['Narrative'].str.contains(noise, case=False, na=False)) & ((self.df['Debit'] != 0) | (self.df['Credit'] != 0))]
        acct_counts = clean_df.groupby('accode')['Batch_No'].nunique()
        h5_list = []
        for accode, count in acct_counts.items():
            nature = str(self.df[self.df['accode'] == accode]['Mapping'].iloc[0]).lower()
            threshold = 1 if 'equity' in nature else s_acct
            if count < threshold:
                hit = self.df[(self.df['accode'] == accode) & (~self.df['Narrative'].str.contains(noise, case=False, na=False))].copy()
                if not hit.empty:
                    hit['Reason'] = f'HRC5: seldom account (<{threshold} journals)'
                    h5_list.append(hit)
        if h5_list: self.flags = pd.concat([self.flags] + h5_list, ignore_index=True)
    
    #HRC 6 seldom suer with atuomated poster filtered
    def run_hrc6(self, s_user, zone_f_list, system_exclusions):
        if not self.active.get('HRC6'):return

        #strategic dictionary for system exclusions
        """to include system names as a list in the excel front to avoid access to the script"""

        system_users = list(set(zone_f_list + system_exclusions + ['interface', 'system', 'auto']))
        #cont journals per user exluding system IDs

        clean_df = self.df[~self.df['UserId'].str.contains('|'.join(system_users), case=False, na=False)]
        user_counts = clean_df.groupby('UserId')['Batch_No'].nunique()

        seldom_users = user_counts[user_counts < s_user].index
        if not seldom_users.empty:
            hits = self.df[self.df['UserId'].isin(seldom_users)].copy()
            hits['Reason'] = f'HRC6 : Seldom User (<{s_user} journals)'
            self.flags = pd.concat([self.flags, hits], ignore_index=True)

    #HRC7: KMP name search with padded snippets
    def run_hrc7(self, kmp_list):
        if not self.active.get('HRC7') or not kmp_list: return

        pattern = '|'.join([str(x).lower() for x in kmp_list])
        hits = self.df[self.df['Narrative'].str.contains(pattern, case=False, na=False)].copy()

        if not hits.empty:
            def get_term(t):
                return next((w for w in kmp_list if str(w).lower() in str(t).lower()), "Unknown")
            
            hits['Matched_Term'] = hits['Narrative'].apply(get_term)
            hit_map = hits.set_index('Batch_No')['Matched_Term'].to_dict()
            batches = hits['Batch_No'].unique()
            
            # Renamed to h7_full and reset index immediately
            h7_full = self.df[self.df['Batch_No'].isin(batches)].copy()
            
            h7_full['Matched_Term'] = h7_full['Batch_No'].map(hit_map)
            h7_full['Reason'] = h7_full['Matched_Term'].apply(lambda x: f"HRC7: found [{x}]" if pd.notnull(x) else "")
            h7_full['Highlight'] = h7_full['Batch_No'].isin(hits['Batch_No'])
            h7_full['Snippet_Helper'] = h7_full.apply(
                lambda x: self._get_snippet(x['Narrative'], x['Matched_Term']) if pd.notnull(x['Matched_Term']) else "", axis=1
            )
            
            # CRITICAL: Concat and reset the GLOBAL index
            self.flags = pd.concat([self.flags, h7_full], ignore_index=True)

    def run_hrc8(self, keyword_list):
        if not self.active.get('HRC8') or not keyword_list: return 

        pattern = '|'.join([str(x).lower() for x in keyword_list])
        hits = self.df[self.df['Narrative'].str.contains(pattern, case=False, na=False)].copy()
        
        if not hits.empty:
            def get_term(t):
                return next((w for w in keyword_list if str(w).lower() in str(t).lower()), "Unknown")
            
            hits['Matched_Term'] = hits['Narrative'].apply(get_term)
            hit_map = hits.set_index('Batch_No')['Matched_Term'].to_dict()
            batches = hits['Batch_No'].unique()

            # Renamed to h8_full and reset index immediately
            h8_full = self.df[self.df['Batch_No'].isin(batches)].copy()
            
            h8_full['Matched_Term'] = h8_full['Batch_No'].map(hit_map)
            h8_full['Reason'] = h8_full['Matched_Term'].apply(lambda x: f"HRC8: Found [{x}]" if pd.notnull(x) else "")
            h8_full['Highlight'] = h8_full['Batch_No'].isin(hits['Batch_No'])
            h8_full['Snippet_Helper'] = h8_full.apply(
                lambda x: self._get_snippet(x['Narrative'], x['Matched_Term']) if pd.notnull(x['Matched_Term']) else "", axis=1
            )
            
            # CRITICAL: Concat and reset the GLOBAL index
            self.flags = pd.concat([self.flags, h8_full], ignore_index=True)

    #HRC 9 post closing material entries > trivial threshold (AMPT) with narrative reversal priority
    def run_hrc9(self):
        if not self.active.get('HRC9') or self.cut_off is None or self.ampt is None:
            return

        #1 basic materiality + date filter
        pc_df = self.df[(self.df['Posted_Date'] > self.cut_off) & (abs(self.df['Net_Amount']) >= self.ampt)].copy()

        #2 reversal priority check
        rev_words = ['reversal', 'reverse', ' accrual rev', 'correction']

        h9_list =[]

        for batch_id in pc_df['Batch_No'].unique():
            batch = self.df[self.df['Batch_No']== batch_id].copy()
            #check for reversal narrative
            is_rev = batch['Narrative'].str.contains('|'.join(rev_words),case=False, na=False).any()
            #check for pnl impact (balance reversal = 0 impact)
            pnl_impact = batch[batch['Mapping'].isin(['Income', 'Expenses'])]['Net_Amount'].sum()

            if is_rev and abs (pnl_impact) < 0.05:
                continue #skips reversals with no pnl impact

            batch['Reason'] = 'HRC9 Material post closing adjustment'
            h9_list.append(batch)

        if h9_list:
             self.flags = pd.concat([self.flags]+h9_list).reset_index(drop=True)

    def run_benfords_law(self):
        """digital analysis of the first digit distribution"""
        if not self.active.get('Benfords Law'): return

        #filter for significant transaction (>=1)

        amounts = self.df[abs(self.df['Net_Amount'])>= 1]['Net_Amount'].abs()
        first_digits = amounts.astype(str).str.lstrip('0.').str[0].astype(int)

        #actual vs expected

        actual_dist = first_digits.value_counts(normalize=True).sort_index()
        expected_dist = pd.Series({d: np.log10(1+1/d) for d in range(1,10)})

        comparison = pd.DataFrame({'Actual': actual_dist, 'Expected': expected_dist}).fillna(0)
        comparison['Deviation']= comparison['Actual']- comparison['Expected']
        self.benford_results = comparison.reset_index().rename(columns={'index':'Digit'})

        #plot 
        plt.figure(figsize=(8,4))
        plt.bar(self.benford_results['Digit']-0.2, self.benford_results['Actual'], width=0.4, label = 'Actual', color='orange')
        plt.plot(self.benford_results['Digit'], self.benford_results['Expected'],marker = 'o', color='blue', label='Expected (Benford)')
        plt.title("Benford's law analysis")
        plt.legend()
        plt.savefig('Benford_plot.png')

    def run_knn_outliers(self):
        "multivariate anomaly detection (date, amount, frequency)"
        if not self.active.get('Outliers (KNN)'):return
        pd.set_option('future.no_silent_downcasting', True)

        knn_data = self.df.copy().fillna(0)
        knn_data['Date_Numeric'] = pd.to_datetime(knn_data['Posted_Date']).view(np.int64)
        knn_data['Acct_Freq'] = knn_data.groupby('accode')['accode'].transform('count')

        #scale features so on doesn't dominate the other

        X = knn_data[['Net_Amount', 'Date_Numeric', 'Acct_Freq']]
        X_scaled = StandardScaler().fit_transform(X)

        knn = NearestNeighbors(n_neighbors=5).fit(X_scaled)
        distances, _ = knn.kneighbors(X_scaled)

        knn_data['Anomaly_Score']= distances.mean(axis=1)

        threshold = np.percentile(knn_data['Anomaly_Score'],99)
        self.knn_hits = knn_data[knn_data['Anomaly_Score']> threshold].copy()

        #plot
        plt.figure(figsize=(8,4))
        plt.scatter(knn_data['Date_Numeric'], knn_data['Net_Amount'], c='grey', alpha=0.3)
        plt.scatter(self.knn_hits['Date_Numeric'], self.knn_hits['Net_Amount'], c='red', label='Outliers')
        plt.title("Knn anomaly detection (amount vs date)")
        plt.savefig("KNN_Plot.png")         
     

    # Next HRC logics go down stream at this indentation
    #
def process_single_file(file_path):


    loader = DataLoader(file_path)
    config = {
        'acct_header': loader.get_config_value("Header (field) name of the accounts"),
        'desc_header': loader.get_config_value("Header (field) name of the description"),
        'date_header': loader.get_config_value("Header (field) name posting date"),
        'batch_header': loader.get_config_value("Header (field) name of batch ID"),
        'debit_header': loader.get_config_value("Header (field) name of debit entry"),
        'credit_header': loader.get_config_value("Header (field) name of credit entry"),
        'user_header': loader.get_config_value("Header (field) name of Poster/User"),
        'materiality': float(loader.get_config_value("Materiality AMPT")or 0),
        'year_end': loader.get_config_value("Financial year end date"),
        's_acct': int(loader.get_config_value("Threshold seldom accounts (less than)") or 0),
        's_user': int(loader.get_config_value("Threshold seldom users (less than)")or 0),
        'cut_off': loader.get_config_value("Cut_off date")
    }

    #configuring output, not to output the entegrity of the GL columns
    output_columns = [
        'Original_Row',
        'Batch_No',
        'accode',
        'Account_name',
        'Posted_Date_Display',
        'Narrative',
        'UserId',
        'Debit',
        'Credit',
        'Net_Amount',
        'Mapping',
        'Sub-Category',
        'Reason'
    ]

    active = loader.get_active_hrcs()
    keywords = loader.get_config_list("Zone D")
    kmps = loader.get_config_list("Zone E")
    zone_f_list = loader.get_config_list("Zone F")
    system_exclusions = loader.get_system_exclusions()
    is_us = loader.get_us_date_toggle()

    cleaned_mapping = loader.get_cleaned_mapping()
    

    raw_gl = loader.sheets['GL_raw'].copy()
    raw_gl.insert(0, 'Original_Row', raw_gl.index +2)


    cleaner = DataCleaner(loader.sheets['GL_raw'], config, is_us_format=is_us)
    df = cleaner.clean_data()

    engine = ForensicEngine(df, cleaned_mapping, active, config)
    
    # Execute HRCs
    engine.run_hrc1()
    #for the full version contact the owner
    engine.run_hrc5(config['s_acct'])
    engine.run_hrc6(config['s_user'], zone_f_list, system_exclusions)
    engine.run_hrc7(kmps)
    engine.run_hrc8(keywords)
    engine.run_hrc9()
    engine.run_benfords_law()
    engine.run_knn_outliers()
    engine.run_completeness_test()

    # Save Results
    log_df = pd.DataFrame([
        f"Run Date: {datetime.now()}",
        f"Rows Processed: {len(df)}",
        f"Flags Found: {len(engine.flags.drop_duplicates())}"
    ], columns=["Audit Log"])

    #filters the outputted columsn to avoid bloating

    def filter_cols(df, col_list):
        if df is None or df.empty:
            return pd.DataFrame()
        existing_cols =[c for c in col_list if c in df.columns]
        return df [existing_cols]
    
    #final_extract = filter_cols(engine.flags.drop_duplicates().reset_index(drop=True), output_columns)
    
    #final_potential = filter_cols(engine.potential_hits.drop_duplicates().reset_index(drop=True), output_columns)

    benford_theory = [
        "Theoretical Interpretation: Benford's Law expects the leading digit '1' to appear ~30% of the time, ",
        "decreasing logarithmically to '9' at ~5%. Significant spikes (Actual > Expected) may suggest ",
        "manual intervention or non-natural patterns that require professional skepticism.",
        "Note: Spikes can also represent high volumes of recurring fixed-price transactions."
    ]

    knn_theory = [
        "Theoretical Interpretation: KNN identifies anomalies by measuring statistical distance between transactions.",
        "The analysis evaluates the relationship between Amount, Date, and Account Frequency simultaneously.",
        "Red outliers represent 'mathematically lonely' entries that exist outside of normal business clusters.",
        "These represent higher statistical risk because the combination of their attributes is rare."
    ]


    with pd.ExcelWriter(FILE_PATH, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
        log_df.to_excel(writer, sheet_name='Log', index=False)

        if not engine.flags.empty:
            filter_cols(engine.flags.drop_duplicates(), output_columns).to_excel(writer, sheet_name='Extract', index=False)

        if not engine.potential_hits.empty:
            filter_cols(engine.potential_hits.drop_duplicates(), output_columns).to_excel(writer, sheet_name='potential_hit', index=False)
        
        # Corrected variable and function names here:
        if hasattr(engine, 'benford_results'): 
            engine.benford_results.to_excel(writer, sheet_name='Benfords_Analysis',startrow = 9, index=False)
            #write interpretation to cell A20
            for i, line in enumerate(benford_theory):
                writer.sheets['Benfords_Analysis'].cell(row=2+i, column=1).value = line            
        if hasattr(engine, 'knn_hits'): 
            filter_cols(engine.knn_hits, output_columns).to_excel(writer, sheet_name='KNN_Outliers',startrow = 9, index=False)
            #write interpretation to cell G20
            for i, line in enumerate(knn_theory):
                writer.sheets['KNN_Outliers'].cell(row=2+i, column=1).value=line

            
        if hasattr(engine, 'completeness_report'): 
            engine.completeness_report.to_excel(writer, sheet_name='Completeness_Test', index=False)
    
    wb = load_workbook(FILE_PATH)
    if 'Benfords_Analysis' in wb.sheetnames and os.path.exists('Benford_Plot.png'):
        wb['Benfords_Analysis'].add_image(Image('Benford_Plot.png'),"G2")
    if 'KNN_Outliers' in wb.sheetnames and os.path.exists('KNN_Plot.png'):
        wb['KNN_Outliers'].add_image(Image('KNN_Plot.png'), 'G2')
    wb.save(FILE_PATH)
    print("Process complete. File updated with images")        

def main():    
    parser = argparse.ArgumentParser(description='Journal Entry Anomaly Detector')
    parser.add_argument('file', nargs='?', default=None,
                        help='Path to the Excel file (default: JE_Sampler.xlsx in script directory)')
    parser.add_argument('--folder', '-f', help='Process all Excel files in a folder')
    parser.add_argument('--pattern', default='*.xlsx', help='File pattern when using --folder')
    args = parser.parse_args()

    if args.folder:
        folder = args.folder
        pattern = args.pattern
        files = glob.glob(os.path.join(folder, pattern))
        if not files:
            print(f"No files found matching {pattern} in {folder}")
            return
        for file in files:
            process_single_file(file)
    else:
        file_path = args.file if args.file else FILE_PATH
        if not os.path.exists(file_path):
            print(f"Error: {file_path} not found.")
            return
        process_single_file(file_path)

if __name__ == '__main__':
    main()      

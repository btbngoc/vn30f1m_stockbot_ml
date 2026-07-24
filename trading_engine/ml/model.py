import os
import joblib
from lightgbm import LGBMClassifier
from sklearn.metrics import classification_report, roc_auc_score

class MLWrapper:
    def __init__(self, model_path="models/lgbm_model.pkl"):
        self.model_path = model_path
        self.model = None
        
        # Hyperparameters can be tuned later
        self.params = {
            'n_estimators': 100,
            'learning_rate': 0.05,
            'max_depth': 5,
            'random_state': 42
        }

    def train(self, df, feature_cols, purge_bars=0):
        # Filter out TIME labels (-1)
        train_df = df[df['label'] != -1].copy()
        if len(train_df) == 0:
            print("No valid training data (only TIME labels found).")
            return

        missing_features = set(feature_cols) - set(train_df.columns)
        if missing_features:
            raise ValueError(f"Missing ML feature columns: {sorted(missing_features)}")

        # Random splits leak future market regimes.  With triple barriers they
        # can also put overlapping trade outcomes in both sets, so evaluate on
        # the newest data and purge the barrier horizon before it.
        train_df = train_df.sort_values("entry_time").reset_index(drop=True)
        split_at = int(len(train_df) * 0.8)
        train_end = split_at - purge_bars
        if train_end < 2 or len(train_df) - split_at < 1:
            print("Not enough labeled observations for a purged chronological train/test split.")
            return

        train_part = train_df.iloc[:train_end]
        test_part = train_df.iloc[split_at:]
        if train_part['label'].nunique() < 2:
            print("Training labels contain only one class; model was not saved.")
            return

        X_train, y_train = train_part[feature_cols], train_part['label']
        X_test, y_test = test_part[feature_cols], test_part['label']
        
        self.model = LGBMClassifier(**self.params)
        self.model.fit(X_train, y_train)
        
        preds = self.model.predict(X_test)
        classes = list(self.model.classes_)
        probs = self.model.predict_proba(X_test)[:, classes.index(1)] if 1 in classes else None
        
        print("--- Model Evaluation ---")
        print(classification_report(y_test, preds, zero_division=0))
        try:
            if probs is None:
                raise ValueError
            roc_auc = roc_auc_score(y_test, probs)
            print(f"ROC-AUC: {roc_auc:.4f}")
        except ValueError:
            print("ROC-AUC not defined because the test set or model has one class.")
            
        self.save_model()

    def save_model(self):
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        joblib.dump(self.model, self.model_path)
        print(f"Model saved to {self.model_path}")

    def load_model(self):
        if os.path.exists(self.model_path):
            self.model = joblib.load(self.model_path)
            return True
        return False

    def predict_proba(self, X):
        if self.model is None:
            if not self.load_model():
                return 0.5 # Default probability if no model found
        
        probs = self.model.predict_proba(X)
        classes = list(self.model.classes_)
        if 1 in classes:
            return probs[:, classes.index(1)]

        # A one-class model containing only losses has zero probability of TP;
        # returning its only class probability would incorrectly return 1.0.
        return probs[:, 0] * 0.0

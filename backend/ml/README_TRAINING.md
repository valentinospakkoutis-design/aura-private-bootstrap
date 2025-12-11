# ML Model Training Guide

## Επισκόπηση

Αυτό το guide εξηγεί πώς να εκπαιδεύσεις ML models για price prediction στο AURA.

## Αρχεία

- `train_model.py` - Κύριο training script
- `model_manager.py` - Διαχείριση trained models
- `training_prep.py` - Προετοιμασία configurations

## Εγκατάσταση

Βεβαιώσου ότι έχεις εγκαταστήσει όλα τα dependencies:

```bash
cd backend
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Χρήση

### Εκπαίδευση ενός Model

```bash
# Train για Gold (XAUUSDT)
python -m ml.train_model --model random_forest --symbol XAUUSDT --days 365

# Train για Silver (XAGUSDT)
python -m ml.train_model --model gradient_boosting --symbol XAGUSDT --days 365
```

### Εκπαίδευση όλων των Metals

```bash
# Train για όλα τα precious metals
python -m ml.train_model --model random_forest --days 365
```

### Hyperparameters

```bash
# Custom hyperparameters
python -m ml.train_model --model random_forest --symbol XAUUSDT \
    --n_estimators 200 --max_depth 15
```

## Model Types

### Random Forest
- **Pros:** Robust, handles non-linearity well
- **Cons:** Can overfit, slower inference
- **Best for:** General price prediction

### Gradient Boosting
- **Pros:** High accuracy, feature importance
- **Cons:** Can overfit, requires tuning
- **Best for:** Complex patterns

## Output

Τα trained models αποθηκεύονται στο `backend/models/` directory:
- `{SYMBOL}_{MODEL_TYPE}_{TIMESTAMP}.pkl` - Trained model
- `{SYMBOL}_{MODEL_TYPE}_scaler.pkl` - Feature scaler

## Metrics

Κάθε training επιστρέφει:
- **MAE** (Mean Absolute Error) - Average prediction error
- **RMSE** (Root Mean Squared Error) - Penalizes large errors
- **R²** (R-squared) - Model fit quality (0-1, higher is better)
- **Direction Accuracy** - % of correct price direction predictions

## Production Usage

Στο production, θα χρειαστεί να:
1. Φορτώσεις real market data από APIs (Binance, etc.)
2. Προσθέσεις περισσότερα features (technical indicators, sentiment, etc.)
3. Χρησιμοποιήσεις cross-validation
4. Implement model versioning
5. Setup automated retraining pipeline

## Next Steps

1. **Real Data:** Integrate με Binance API για real market data
2. **More Features:** Technical indicators, sentiment analysis, macro data
3. **Ensemble Models:** Combine multiple models για better accuracy
4. **Hyperparameter Tuning:** Use GridSearchCV ή Optuna
5. **Model Serving:** Deploy models για real-time inference


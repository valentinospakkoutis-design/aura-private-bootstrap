# PyTorch Neural Network Models Guide

## Επισκόπηση

Αυτό το guide εξηγεί πώς να χρησιμοποιήσεις PyTorch neural networks για price prediction στο AURA.

## Αρχεία

- `pytorch_model.py` - PyTorch models και trainer
- `train_model.py` - Data preparation (χρησιμοποιείται από PyTorch)

## Εγκατάσταση

Το PyTorch είναι ήδη εγκατεστημένο. Αν χρειάζεται να το εγκαταστήσεις ξανά:

```bash
cd backend
.\venv\Scripts\Activate.ps1
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
```

## Model Types

### 1. PricePredictionNN (MLP)
Multi-layer perceptron για price prediction.

**Χαρακτηριστικά:**
- Multiple hidden layers
- Dropout για regularization
- Batch normalization
- ReLU activations

**Χρήση:**
```python
from ml.pytorch_model import PricePredictionNN

model = PricePredictionNN(
    input_size=8,
    hidden_sizes=[64, 128, 64],
    dropout_rate=0.2
)
```

### 2. LSTMPredictor (LSTM)
LSTM για time series prediction.

**Χαρακτηριστικά:**
- LSTM layers για sequence learning
- Handles temporal patterns
- Better για time series data

**Χρήση:**
```python
from ml.pytorch_model import LSTMPredictor

model = LSTMPredictor(
    input_size=8,
    hidden_size=64,
    num_layers=2,
    dropout=0.2
)
```

## Training Example

```python
from ml.pytorch_model import (
    PyTorchTrainer,
    PricePredictionNN,
    PricePredictionDataset
)
from torch.utils.data import DataLoader
from sklearn.model_selection import train_test_split
import numpy as np

# Prepare data
trainer = ModelTrainer()
df = trainer.generate_synthetic_data("XAUUSDT", days=365)
X, y = trainer.prepare_features(df)

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# Create datasets
train_dataset = PricePredictionDataset(X_train, y_train)
test_dataset = PricePredictionDataset(X_test, y_test)

train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
test_loader = DataLoader(test_dataset, batch_size=32, shuffle=False)

# Create model
model = PricePredictionNN(input_size=8, hidden_sizes=[64, 128, 64])

# Train
pytorch_trainer = PyTorchTrainer()
history = pytorch_trainer.train_model(
    model=model,
    train_loader=train_loader,
    val_loader=test_loader,
    epochs=100,
    learning_rate=0.001
)
```

## Command Line Usage

```bash
cd backend
.\venv\Scripts\python.exe -m ml.pytorch_model
```

Αυτό θα:
1. Δημιουργήσει synthetic data
2. Εκπαιδεύσει ένα PyTorch model
3. Θα δείξει sample predictions

## Model Comparison

| Model Type | Pros | Cons | Best For |
|------------|------|------|----------|
| **MLP (PricePredictionNN)** | Fast, Simple, Good for tabular data | Doesn't capture temporal patterns | Feature-based predictions |
| **LSTM** | Captures temporal patterns, Better for sequences | Slower, More complex | Time series with sequences |
| **Random Forest** (scikit-learn) | Fast, Interpretable, No GPU needed | Limited complexity | Quick prototyping |

## GPU Support

Για GPU support (CUDA):

```bash
# Install CUDA version
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

Το model θα detect αυτόματα αν CUDA είναι available.

## Next Steps

1. **Real Data**: Integrate με Binance API για real market data
2. **Ensemble**: Combine PyTorch models με RandomForest
3. **Hyperparameter Tuning**: Use Optuna ή Ray Tune
4. **Model Serving**: Deploy models για production inference


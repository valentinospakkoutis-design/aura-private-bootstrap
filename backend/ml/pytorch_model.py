"""
PyTorch Neural Network Models for Price Prediction
Deep learning models using PyTorch
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import os
import pickle


class PricePredictionDataset(Dataset):
    """
    Dataset για price prediction training
    """
    
    def __init__(self, features: np.ndarray, targets: np.ndarray):
        """
        Args:
            features: Input features (N, feature_dim)
            targets: Target prices (N,)
        """
        self.features = torch.FloatTensor(features)
        self.targets = torch.FloatTensor(targets)
    
    def __len__(self):
        return len(self.features)
    
    def __getitem__(self, idx):
        return self.features[idx], self.targets[idx]


class PricePredictionNN(nn.Module):
    """
    Neural Network για price prediction
    Multi-layer perceptron με dropout
    """
    
    def __init__(
        self,
        input_size: int = 8,
        hidden_sizes: List[int] = [64, 128, 64],
        dropout_rate: float = 0.2,
        output_size: int = 1
    ):
        """
        Args:
            input_size: Number of input features
            hidden_sizes: List of hidden layer sizes
            dropout_rate: Dropout rate for regularization
            output_size: Output size (1 for price prediction)
        """
        super(PricePredictionNN, self).__init__()
        
        layers = []
        prev_size = input_size
        
        # Build hidden layers
        for hidden_size in hidden_sizes:
            layers.append(nn.Linear(prev_size, hidden_size))
            layers.append(nn.ReLU())
            layers.append(nn.Dropout(dropout_rate))
            layers.append(nn.BatchNorm1d(hidden_size))
            prev_size = hidden_size
        
        # Output layer
        layers.append(nn.Linear(prev_size, output_size))
        
        self.model = nn.Sequential(*layers)
    
    def forward(self, x):
        return self.model(x).squeeze()


class LSTMPredictor(nn.Module):
    """
    LSTM Model για time series price prediction
    """
    
    def __init__(
        self,
        input_size: int = 8,
        hidden_size: int = 64,
        num_layers: int = 2,
        dropout: float = 0.2,
        output_size: int = 1
    ):
        """
        Args:
            input_size: Number of features per time step
            hidden_size: LSTM hidden state size
            num_layers: Number of LSTM layers
            dropout: Dropout rate
            output_size: Output size
        """
        super(LSTMPredictor, self).__init__()
        
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            dropout=dropout if num_layers > 1 else 0,
            batch_first=True
        )
        
        self.fc = nn.Linear(hidden_size, output_size)
    
    def forward(self, x):
        # x shape: (batch, seq_len, input_size)
        lstm_out, _ = self.lstm(x)
        # Take last output
        last_output = lstm_out[:, -1, :]
        output = self.fc(last_output)
        return output.squeeze()


class PyTorchTrainer:
    """
    Trainer για PyTorch models
    """
    
    def __init__(self, models_dir: str = "models"):
        """
        Args:
            models_dir: Directory για αποθήκευση models
        """
        self.models_dir = models_dir
        os.makedirs(models_dir, exist_ok=True)
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"[*] Using device: {self.device}")
    
    def train_model(
        self,
        model: nn.Module,
        train_loader: DataLoader,
        val_loader: Optional[DataLoader] = None,
        epochs: int = 100,
        learning_rate: float = 0.001,
        model_name: str = "pytorch_model"
    ) -> Dict:
        """
        Train PyTorch model
        
        Args:
            model: PyTorch model
            train_loader: Training data loader
            val_loader: Validation data loader (optional)
            epochs: Number of training epochs
            learning_rate: Learning rate
            model_name: Model name for saving
            
        Returns:
            Training history
        """
        model = model.to(self.device)
        criterion = nn.MSELoss()
        optimizer = optim.Adam(model.parameters(), lr=learning_rate)
        scheduler = optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, mode='min', factor=0.5, patience=10
        )
        
        history = {
            "train_loss": [],
            "val_loss": [],
            "epochs": []
        }
        
        best_val_loss = float('inf')
        
        print(f"[*] Starting training for {epochs} epochs...")
        
        for epoch in range(epochs):
            # Training phase
            model.train()
            train_loss = 0.0
            train_batches = 0
            
            for features, targets in train_loader:
                features = features.to(self.device)
                targets = targets.to(self.device)
                
                # Forward pass
                optimizer.zero_grad()
                outputs = model(features)
                loss = criterion(outputs, targets)
                
                # Backward pass
                loss.backward()
                optimizer.step()
                
                train_loss += loss.item()
                train_batches += 1
            
            avg_train_loss = train_loss / train_batches
            history["train_loss"].append(avg_train_loss)
            
            # Validation phase
            if val_loader:
                model.eval()
                val_loss = 0.0
                val_batches = 0
                
                with torch.no_grad():
                    for features, targets in val_loader:
                        features = features.to(self.device)
                        targets = targets.to(self.device)
                        
                        outputs = model(features)
                        loss = criterion(outputs, targets)
                        
                        val_loss += loss.item()
                        val_batches += 1
                
                avg_val_loss = val_loss / val_batches
                history["val_loss"].append(avg_val_loss)
                
                scheduler.step(avg_val_loss)
                
                # Save best model
                if avg_val_loss < best_val_loss:
                    best_val_loss = avg_val_loss
                    self._save_model(model, model_name, epoch, avg_val_loss)
                
                if (epoch + 1) % 10 == 0:
                    print(f"Epoch {epoch+1}/{epochs} - Train Loss: {avg_train_loss:.4f}, Val Loss: {avg_val_loss:.4f}")
            else:
                if (epoch + 1) % 10 == 0:
                    print(f"Epoch {epoch+1}/{epochs} - Train Loss: {avg_train_loss:.4f}")
            
            history["epochs"].append(epoch + 1)
        
        print(f"[+] Training completed! Best Val Loss: {best_val_loss:.4f}")
        
        return history
    
    def _save_model(
        self,
        model: nn.Module,
        model_name: str,
        epoch: int,
        val_loss: float
    ):
        """Save model to disk"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_path = os.path.join(
            self.models_dir,
            f"{model_name}_{timestamp}_epoch{epoch}_loss{val_loss:.4f}.pth"
        )
        
        torch.save({
            'model_state_dict': model.state_dict(),
            'epoch': epoch,
            'val_loss': val_loss,
            'model_class': model.__class__.__name__
        }, model_path)
        
        print(f"[*] Model saved to: {model_path}")
    
    def load_model(
        self,
        model_path: str,
        model_class: type,
        **model_kwargs
    ) -> nn.Module:
        """
        Load trained model
        
        Args:
            model_path: Path to saved model
            model_class: Model class (PricePredictionNN or LSTMPredictor)
            **model_kwargs: Model initialization parameters
            
        Returns:
            Loaded model
        """
        checkpoint = torch.load(model_path, map_location=self.device)
        
        model = model_class(**model_kwargs)
        model.load_state_dict(checkpoint['model_state_dict'])
        model = model.to(self.device)
        model.eval()
        
        print(f"[+] Loaded model from {model_path}")
        print(f"    Epoch: {checkpoint['epoch']}, Val Loss: {checkpoint['val_loss']:.4f}")
        
        return model
    
    def predict(
        self,
        model: nn.Module,
        features: np.ndarray
    ) -> np.ndarray:
        """
        Make predictions with trained model
        
        Args:
            model: Trained PyTorch model
            features: Input features (N, feature_dim) or (N, seq_len, feature_dim) for LSTM
            
        Returns:
            Predictions
        """
        model.eval()
        
        if len(features.shape) == 2:
            # For MLP: (N, features)
            features_tensor = torch.FloatTensor(features).to(self.device)
        else:
            # For LSTM: (N, seq_len, features)
            features_tensor = torch.FloatTensor(features).to(self.device)
        
        with torch.no_grad():
            predictions = model(features_tensor)
        
        return predictions.cpu().numpy()


def create_example_model():
    """Create and train example model"""
    from ml.train_model import ModelTrainer
    from sklearn.preprocessing import StandardScaler
    
    # Generate training data
    trainer = ModelTrainer()
    df = trainer.generate_synthetic_data("XAUUSDT", days=365, base_price=2050.0)
    
    # Prepare features and targets
    X, y = trainer.prepare_features(df)
    
    # Scale features and targets
    feature_scaler = StandardScaler()
    target_scaler = StandardScaler()
    
    X_scaled = feature_scaler.fit_transform(X)
    y_scaled = target_scaler.fit_transform(y.reshape(-1, 1)).ravel()
    
    # Split data
    from sklearn.model_selection import train_test_split
    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y_scaled, test_size=0.2, random_state=42
    )
    
    # Create datasets
    train_dataset = PricePredictionDataset(X_train, y_train)
    test_dataset = PricePredictionDataset(X_test, y_test)
    
    train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
    test_loader = DataLoader(test_dataset, batch_size=32, shuffle=False)
    
    # Create model
    model = PricePredictionNN(
        input_size=8,
        hidden_sizes=[64, 128, 64],
        dropout_rate=0.2
    )
    
    print(f"[*] Model architecture:")
    print(model)
    
    # Train model
    pytorch_trainer = PyTorchTrainer()
    history = pytorch_trainer.train_model(
        model=model,
        train_loader=train_loader,
        val_loader=test_loader,
        epochs=50,
        learning_rate=0.001,
        model_name="pytorch_price_predictor"
    )
    
    # Make predictions (unscale)
    sample_features = X_test[:5]
    predictions_scaled = pytorch_trainer.predict(model, sample_features)
    
    # Unscale predictions and actual values
    predictions = target_scaler.inverse_transform(predictions_scaled.reshape(-1, 1)).ravel()
    actual = target_scaler.inverse_transform(y_test[:5].reshape(-1, 1)).ravel()
    
    print(f"\n[*] Sample Predictions (unscaled):")
    for i in range(5):
        error = abs(actual[i] - predictions[i])
        error_pct = (error / actual[i]) * 100 if actual[i] > 0 else 0
        print(f"  Actual: {actual[i]:.2f}, Predicted: {predictions[i]:.2f}, Error: {error:.2f} ({error_pct:.2f}%)")
    
    return model, history, feature_scaler, target_scaler


if __name__ == "__main__":
    print("=" * 60)
    print("PyTorch Neural Network Example")
    print("=" * 60)
    
    model, history, feature_scaler, target_scaler = create_example_model()
    
    print("\n[+] Example completed successfully!")
    print(f"[*] Feature scaler and target scaler saved for future use")


# -*- coding: utf-8 -*-
"""
ML Feedback Models - Store user feedback for model retraining
"""
from sqlalchemy import Column, String, Integer, DateTime, Text, JSON, Float, Boolean, Index
from datetime import datetime

from .database import Base


class RiskPredictionFeedback(Base):
    """
    Store user corrections to risk predictions for incremental learning
    
    Workflow:
    1. Model predicts risk level
    2. User corrects if wrong
    3. Feedback stored here
    4. When enough samples accumulated (100+), retrain model
    """
    __tablename__ = "risk_prediction_feedback"

    id = Column(Integer, primary_key=True, index=True)
    
    # Contract context
    contract_id = Column(Integer, nullable=True, index=True)
    user_id = Column(String(36), nullable=True, index=True)
    
    # Contract features (same as used for prediction)
    contract_features = Column(JSON, nullable=False)  # Store extracted features
    
    # Prediction
    predicted_risk_level = Column(String(20), nullable=False)  # minimal, low, medium, high, critical
    predicted_confidence = Column(Float, nullable=True)
    
    # User correction
    actual_risk_level = Column(String(20), nullable=False)  # User's correction
    feedback_reason = Column(Text, nullable=True)  # Why user disagrees
    
    # Metadata
    model_version = Column(String(50), nullable=True)  # Which model made prediction
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Training flags
    used_for_training = Column(Boolean, default=False, nullable=False)  # Has this been used in retraining?
    training_batch_id = Column(Integer, nullable=True)  # Which batch was it used in?
    
    # Indexes
    __table_args__ = (
        Index('idx_feedback_created', 'created_at'),
        Index('idx_feedback_unused', 'used_for_training', 'created_at'),
    )

    def __repr__(self):
        return f"<RiskPredictionFeedback(id={self.id}, predicted={self.predicted_risk_level}, actual={self.actual_risk_level})>"


class ModelTrainingBatch(Base):
    """
    Track model retraining batches
    
    Each time we retrain the risk predictor, log it here
    """
    __tablename__ = "model_training_batches"

    id = Column(Integer, primary_key=True, index=True)
    
    # Training details
    model_type = Column(String(50), nullable=False)  # risk_predictor, etc.
    model_version = Column(String(50), nullable=False)  # v1.0, v1.1, etc.
    
    # Training data
    training_samples_count = Column(Integer, nullable=False)
    feedback_samples_count = Column(Integer, nullable=False)  # How many feedback samples used
    
    # Performance metrics
    train_accuracy = Column(Float, nullable=True)
    val_accuracy = Column(Float, nullable=True)
    test_accuracy = Column(Float, nullable=True)
    
    metrics = Column(JSON, nullable=True)  # Full metrics report
    
    # Status
    status = Column(String(20), nullable=False)  # pending, training, completed, failed, deployed
    
    # Deployment
    deployed = Column(Boolean, default=False, nullable=False)
    deployed_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    
    # Errors
    error_message = Column(Text, nullable=True)

    def __repr__(self):
        return f"<ModelTrainingBatch(id={self.id}, model={self.model_type}, version={self.model_version}, status={self.status})>"


__all__ = ["RiskPredictionFeedback", "ModelTrainingBatch"]

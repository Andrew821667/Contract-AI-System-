# -*- coding: utf-8 -*-
"""
Analytics Models - Database models for storing analytics metrics
"""
from sqlalchemy import Column, String, Float, Integer, DateTime, Text, JSON, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime

from .database import Base


class AnalyticsMetricLog(Base):
    """
    Stores individual metric measurements over time
    
    This enables:
    - Historical trend analysis
    - Time-series charting
    - Performance tracking
    - Cost analysis over time
    """
    __tablename__ = "analytics_metric_logs"

    id = Column(Integer, primary_key=True, index=True)
    
    # Metric identification
    metric_name = Column(String(100), nullable=False, index=True)
    metric_type = Column(String(50), nullable=False)  # productivity, cost, risk, quality, time
    
    # Metric value
    value = Column(Float, nullable=False)
    unit = Column(String(50), nullable=False)  # e.g., "hours", "USD", "count", "percentage"
    
    # Context
    user_id = Column(String(36), nullable=True, index=True)
    contract_id = Column(Integer, nullable=True, index=True)

    # Metadata (renamed to avoid SQLAlchemy reserved word)
    extra_metadata = Column(JSON, nullable=True)  # Additional context as JSON
    
    # Timestamp
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Indexes for efficient queries
    __table_args__ = (
        Index('idx_metric_time', 'metric_name', 'timestamp'),
        Index('idx_user_time', 'user_id', 'timestamp'),
        Index('idx_type_time', 'metric_type', 'timestamp'),
    )

    def __repr__(self):
        return f"<AnalyticsMetricLog(id={self.id}, metric={self.metric_name}, value={self.value}, timestamp={self.timestamp})>"


class AggregatedMetric(Base):
    """
    Pre-aggregated metrics for faster dashboard queries
    
    Aggregation levels: hourly, daily, weekly, monthly
    """
    __tablename__ = "aggregated_metrics"

    id = Column(Integer, primary_key=True, index=True)
    
    # Metric identification
    metric_name = Column(String(100), nullable=False, index=True)
    metric_type = Column(String(50), nullable=False)
    
    # Aggregation
    aggregation_level = Column(String(20), nullable=False)  # hourly, daily, weekly, monthly
    aggregation_function = Column(String(20), nullable=False)  # sum, avg, min, max, count
    
    # Time period
    period_start = Column(DateTime, nullable=False, index=True)
    period_end = Column(DateTime, nullable=False)
    
    # Aggregated value
    value = Column(Float, nullable=False)
    count = Column(Integer, nullable=False)  # Number of samples in aggregation
    
    # Context
    user_id = Column(String(36), nullable=True, index=True)
    
    # Created/updated
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Indexes
    __table_args__ = (
        Index('idx_agg_metric_period', 'metric_name', 'aggregation_level', 'period_start'),
    )

    def __repr__(self):
        return f"<AggregatedMetric(metric={self.metric_name}, level={self.aggregation_level}, period={self.period_start})>"


__all__ = ["AnalyticsMetricLog", "AggregatedMetric"]

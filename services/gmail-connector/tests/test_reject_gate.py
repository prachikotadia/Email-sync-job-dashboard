"""
Unit tests for RejectGate service.

Tests:
- Model loading and initialization
- Threshold behavior (is_rejected flag)
- Prediction output format
- Edge cases (empty inputs, missing model)
"""
import pytest
import json
import joblib
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.services.reject_gate import (
    init_reject_gate,
    predict_reject_gate,
    is_initialized,
    _norm
)


class TestRejectGateInitialization:
    """Test RejectGate initialization and loading."""
    
    def test_init_without_model_raises_error(self, tmp_path):
        """Test that init_reject_gate raises RuntimeError if model not found."""
        with patch('app.services.reject_gate.Path') as mock_path:
            # Mock Path to return non-existent file
            mock_model_path = MagicMock()
            mock_model_path.exists.return_value = False
            mock_path.return_value = mock_model_path
            
            with pytest.raises(RuntimeError, match="RejectGate model not found"):
                init_reject_gate()
    
    def test_init_loads_model_and_meta(self, tmp_path):
        """Test that init_reject_gate loads model and metadata correctly."""
        # Create temporary model directory
        model_dir = tmp_path / "models" / "reject_gate"
        model_dir.mkdir(parents=True)
        
        # Create mock model (simple pipeline)
        from sklearn.pipeline import Pipeline
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        
        mock_pipeline = Pipeline([
            ("tfidf", TfidfVectorizer()),
            ("clf", LogisticRegression(max_iter=100))
        ])
        # Fit with dummy data
        mock_pipeline.fit(["test email"], [0])
        
        model_path = model_dir / "reject_gate.joblib"
        meta_path = model_dir / "reject_gate.meta.json"
        
        joblib.dump(mock_pipeline, model_path)
        
        meta = {
            "model_type": "tfidf_logreg",
            "labels": {"0": "NOT_REJECTED", "1": "REJECTED"},
            "recommended_threshold": 0.90,  # Custom threshold
            "data_sources": ["test.csv"],
            "train_rows": 100,
            "test_rows": 20
        }
        with open(meta_path, "w") as f:
            json.dump(meta, f)
        
        # Mock Path to return our temp directory
        with patch('app.services.reject_gate.Path') as mock_path_class:
            def path_side_effect(*args):
                if len(args) == 0:
                    # Return base path
                    base = MagicMock()
                    base.__truediv__ = lambda self, other: tmp_path / other if isinstance(other, str) else tmp_path / str(other)
                    return base
                return tmp_path / Path(*args)
            
            mock_path_class.side_effect = path_side_effect
            
            # Reset global state
            import app.services.reject_gate as rg_module
            rg_module._reject_gate = None
            rg_module._thr = 0.85
            
            init_reject_gate()
            
            assert is_initialized()
            # Check that threshold was loaded from meta
            assert rg_module._thr == 0.90


class TestRejectGatePrediction:
    """Test RejectGate prediction behavior."""
    
    @pytest.fixture
    def mock_model(self):
        """Create a mock model for testing."""
        from sklearn.pipeline import Pipeline
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        
        pipeline = Pipeline([
            ("tfidf", TfidfVectorizer()),
            ("clf", LogisticRegression(max_iter=100))
        ])
        # Fit with dummy data
        pipeline.fit(
            ["subject: test | snippet: hello | domain: company.com"],
            [0]
        )
        return pipeline
    
    def test_predict_without_init_raises_error(self):
        """Test that predict_reject_gate raises error if not initialized."""
        # Reset global state
        import app.services.reject_gate as rg_module
        rg_module._reject_gate = None
        
        with pytest.raises(RuntimeError, match="RejectGate not initialized"):
            predict_reject_gate("test", "snippet", "domain.com")
    
    def test_predict_returns_correct_format(self, mock_model):
        """Test that predict_reject_gate returns correct dict format."""
        import app.services.reject_gate as rg_module
        rg_module._reject_gate = mock_model
        rg_module._thr = 0.85
        
        result = predict_reject_gate(
            subject="Application Status Update",
            snippet="Thank you for your interest",
            from_domain="company.com"
        )
        
        assert isinstance(result, dict)
        assert "is_rejected" in result
        assert "p_rejected" in result
        assert "threshold" in result
        assert "label" in result
        assert "reason" in result
        
        assert isinstance(result["is_rejected"], bool)
        assert 0.0 <= result["p_rejected"] <= 1.0
        assert result["threshold"] == 0.85
        assert result["label"] in ["REJECTED", "NOT_REJECTED"]
        assert isinstance(result["reason"], str)
    
    def test_threshold_behavior_above_threshold(self, mock_model):
        """Test that is_rejected=True when p_rejected >= threshold."""
        import app.services.reject_gate as rg_module
        rg_module._reject_gate = mock_model
        rg_module._thr = 0.85
        
        # Mock predict_proba to return high probability
        def mock_predict_proba(X):
            return [[0.1, 0.9]]  # 90% probability of rejection
        
        rg_module._reject_gate.predict_proba = mock_predict_proba
        
        result = predict_reject_gate("test", "test", "test.com")
        
        assert result["is_rejected"] is True
        assert result["p_rejected"] == 0.9
        assert result["label"] == "REJECTED"
    
    def test_threshold_behavior_below_threshold(self, mock_model):
        """Test that is_rejected=False when p_rejected < threshold."""
        import app.services.reject_gate as rg_module
        rg_module._reject_gate = mock_model
        rg_module._thr = 0.85
        
        # Mock predict_proba to return low probability
        def mock_predict_proba(X):
            return [[0.9, 0.1]]  # 10% probability of rejection
        
        rg_module._reject_gate.predict_proba = mock_predict_proba
        
        result = predict_reject_gate("test", "test", "test.com")
        
        assert result["is_rejected"] is False
        assert result["p_rejected"] == 0.1
        assert result["label"] == "NOT_REJECTED"
    
    def test_threshold_behavior_at_threshold(self, mock_model):
        """Test that is_rejected=True when p_rejected exactly equals threshold."""
        import app.services.reject_gate as rg_module
        rg_module._reject_gate = mock_model
        rg_module._thr = 0.85
        
        # Mock predict_proba to return exactly threshold
        def mock_predict_proba(X):
            return [[0.15, 0.85]]  # Exactly 85% probability
        
        rg_module._reject_gate.predict_proba = mock_predict_proba
        
        result = predict_reject_gate("test", "test", "test.com")
        
        assert result["is_rejected"] is True  # >= threshold
        assert result["p_rejected"] == 0.85
        assert result["label"] == "REJECTED"
    
    def test_empty_inputs(self, mock_model):
        """Test prediction with empty inputs."""
        import app.services.reject_gate as rg_module
        rg_module._reject_gate = mock_model
        rg_module._thr = 0.85
        
        result = predict_reject_gate("", "", "")
        
        assert isinstance(result, dict)
        assert "is_rejected" in result
        # Should not raise error with empty inputs


class TestRejectGateNormalization:
    """Test text normalization function."""
    
    def test_norm_lowercases_text(self):
        """Test that _norm converts text to lowercase."""
        assert _norm("HELLO WORLD") == "hello world"
        assert _norm("Test Email") == "test email"
    
    def test_norm_collapses_whitespace(self):
        """Test that _norm collapses multiple whitespace."""
        assert _norm("hello    world") == "hello world"
        assert _norm("test\n\nemail") == "test email"
        assert _norm("  spaced  out  ") == "spaced out"
    
    def test_norm_replaces_proper_nouns(self):
        """Test that _norm replaces proper nouns with <TOKEN>."""
        # Proper nouns (capitalized, 3+ chars) should be replaced
        result = _norm("Hello from Google Inc")
        assert "<TOKEN>" in result
        assert "google" not in result.lower()  # Should be replaced
    
    def test_norm_handles_empty_string(self):
        """Test that _norm handles empty strings."""
        assert _norm("") == ""
        assert _norm("   ") == ""
    
    def test_norm_handles_none(self):
        """Test that _norm handles None input."""
        assert _norm(None) == ""


class TestRejectGateIntegration:
    """Integration tests for RejectGate."""
    
    def test_is_initialized_returns_false_when_not_init(self):
        """Test that is_initialized returns False when not initialized."""
        import app.services.reject_gate as rg_module
        rg_module._reject_gate = None
        
        assert is_initialized() is False
    
    def test_is_initialized_returns_true_when_init(self, mock_model):
        """Test that is_initialized returns True when initialized."""
        import app.services.reject_gate as rg_module
        rg_module._reject_gate = mock_model
        
        assert is_initialized() is True

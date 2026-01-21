"""
Test model profile functionality.
"""

import pytest
from unittest.mock import patch
from jarvis.performance_metrics import (
    MODEL_PROFILES, get_model_profile_params, get_available_profiles, validate_profile
)


class TestModelProfiles:
    def test_model_profiles_structure(self):
        """Test that model profiles have the expected structure."""
        required_keys = {"num_ctx", "num_predict", "temperature", "top_p", "description"}
        
        for profile_name, profile in MODEL_PROFILES.items():
            assert isinstance(profile, dict), f"Profile {profile_name} should be a dict"
            assert required_keys.issubset(profile.keys()), f"Profile {profile_name} missing required keys"
            
            # Check value types
            assert isinstance(profile["num_ctx"], int), f"num_ctx should be int for {profile_name}"
            assert isinstance(profile["num_predict"], int), f"num_predict should be int for {profile_name}"
            assert isinstance(profile["temperature"], (int, float)), f"temperature should be numeric for {profile_name}"
            assert isinstance(profile["top_p"], (int, float)), f"top_p should be numeric for {profile_name}"
            assert isinstance(profile["description"], str), f"description should be string for {profile_name}"

    def test_profile_values_make_sense(self):
        """Test that profile values are reasonable."""
        for profile_name, profile in MODEL_PROFILES.items():
            # Context should be reasonable
            assert 1024 <= profile["num_ctx"] <= 16384, f"num_ctx out of range for {profile_name}"
            
            # Max tokens should be reasonable
            assert 256 <= profile["num_predict"] <= 4096, f"num_predict out of range for {profile_name}"
            
            # Temperature should be reasonable
            assert 0.1 <= profile["temperature"] <= 1.5, f"temperature out of range for {profile_name}"
            
            # Top-p should be reasonable
            assert 0.1 <= profile["top_p"] <= 1.0, f"top_p out of range for {profile_name}"

    def test_fast_profile_optimized_for_speed(self):
        """Test that fast profile has lower context and tokens."""
        fast = MODEL_PROFILES["fast"]
        balanced = MODEL_PROFILES["balanced"]
        
        assert fast["num_ctx"] < balanced["num_ctx"], "Fast should have lower context than balanced"
        assert fast["num_predict"] < balanced["num_predict"], "Fast should have fewer tokens than balanced"

    def test_quality_profile_optimized_for_quality(self):
        """Test that quality profile has higher context and tokens."""
        quality = MODEL_PROFILES["quality"]
        balanced = MODEL_PROFILES["balanced"]
        
        assert quality["num_ctx"] > balanced["num_ctx"], "Quality should have higher context than balanced"
        assert quality["num_predict"] > balanced["num_predict"], "Quality should have more tokens than balanced"

    def test_get_model_profile_params(self):
        """Test getting profile parameters."""
        params = get_model_profile_params("balanced")
        assert "num_ctx" in params
        assert "num_predict" in params
        assert "temperature" in params
        assert "top_p" in params
        assert "description" in params
        
        # Should return a copy, not the original
        assert params is not MODEL_PROFILES["balanced"]

    def test_get_model_profile_params_invalid(self):
        """Test getting parameters for invalid profile returns balanced."""
        params = get_model_profile_params("invalid")
        expected = get_model_profile_params("balanced")
        assert params == expected

    def test_get_available_profiles(self):
        """Test getting list of available profiles."""
        profiles = get_available_profiles()
        assert isinstance(profiles, list)
        assert "fast" in profiles
        assert "balanced" in profiles
        assert "quality" in profiles
        assert len(profiles) == 3

    def test_validate_profile(self):
        """Test profile validation."""
        assert validate_profile("fast") == True
        assert validate_profile("balanced") == True
        assert validate_profile("quality") == True
        assert validate_profile("invalid") == False
        assert validate_profile("") == False
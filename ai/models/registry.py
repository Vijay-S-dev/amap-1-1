"""
Model registry and backend loader for AI classifiers and inference engines.
"""

from typing import Dict, Optional, Type

from ai.models.classifier import (
    BaseClassifier,
    GeometricClassifier,
    MockClassifier,
    StatisticalClassifier,
)


class ModelRegistry:
    """Registry pattern for plugging in classifiers, ONNX runtimes, or heuristics."""

    _classifiers: Dict[str, BaseClassifier] = {}
    _default_backend: str = "geometric"

    @classmethod
    def register(cls, name: str, classifier: BaseClassifier) -> None:
        cls._classifiers[name.lower()] = classifier

    @classmethod
    def get(cls, name: Optional[str] = None) -> BaseClassifier:
        backend_name = (name or cls._default_backend).lower()
        if backend_name not in cls._classifiers:
            # Lazy initialize standard backends
            if backend_name == "geometric":
                cls._classifiers["geometric"] = GeometricClassifier()
            elif backend_name == "statistical":
                cls._classifiers["statistical"] = StatisticalClassifier()
            elif backend_name == "mock":
                cls._classifiers["mock"] = MockClassifier()
            else:
                # Fallback to geometric default
                return cls.get("geometric")
        return cls._classifiers[backend_name]

    @classmethod
    def set_default(cls, name: str) -> None:
        cls._default_backend = name.lower()


# Initialize default registry
ModelRegistry.register("geometric", GeometricClassifier())
ModelRegistry.register("statistical", StatisticalClassifier())
ModelRegistry.register("mock", MockClassifier())

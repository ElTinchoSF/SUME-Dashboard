"""
Dependency name normalizer for SUME Dashboard.

Implements 5 normalization rules with explicit override precedence:
1. explicit_override: Direct mapping from original -> normalized (highest precedence)
2. mesa_entradas: Normalize "Mesa de Entradas <Facultad>" to "Mesa de Entradas"
3. preserve_mde: Preserve exact MDE names (Mesa de Entradas, MDE, M.D.E.)
4. strip_parentheses: Remove trailing parenthetical content like "(FBCB)"
5. identity: Return input unchanged (fallback, lowest precedence)

Provides idempotency guarantee: normalize(normalize(x)) == normalize(x)
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class NormalizationRule:
    """A single normalization rule."""

    type: str
    description: str
    pattern: Optional[str] = None
    replacement: str = ""
    patterns: list[str] = field(default_factory=list)


@dataclass
class NormalizationRules:
    """Container for all normalization rules and explicit overrides."""

    rules: list[NormalizationRule] = field(default_factory=list)
    explicit_overrides: dict[str, str] = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)

    def get_rule(self, rule_type: str) -> Optional[NormalizationRule]:
        """Get a rule by its type."""
        for rule in self.rules:
            if rule.type == rule_type:
                return rule
        return None


def load_rules(path: Path) -> NormalizationRules:
    """
    Load normalization rules from YAML file.

    Args:
        path: Path to the normalization_rules.yaml file.

    Returns:
        NormalizationRules object with parsed rules and overrides.
    """
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    rules = []
    for rule_data in data.get("rules", []):
        rule = NormalizationRule(
            type=rule_data["type"],
            description=rule_data.get("description", ""),
            pattern=rule_data.get("pattern"),
            replacement=rule_data.get("replacement", ""),
            patterns=rule_data.get("patterns", []),
        )
        rules.append(rule)

    explicit_overrides = data.get("explicit_overrides", {})
    metadata = data.get("metadata", {})

    return NormalizationRules(
        rules=rules,
        explicit_overrides=explicit_overrides,
        metadata=metadata,
    )


def normalize(dependencia: str, rules: NormalizationRules) -> str:
    """
    Normalize a dependency name using the provided rules.

    Rules are applied in order of precedence:
    1. explicit_override (checked first, highest precedence)
    2. mesa_entradas
    3. preserve_mde
    4. strip_parentheses
    4. identity (fallback)

    Args:
        dependencia: Raw dependency name from SUME
        rules: NormalizationRules object with rules and overrides

    Returns:
        Normalized dependency name.

    Guarantees:
        - Idempotent: normalize(normalize(x)) == normalize(x)
        - Pure function: same input always returns same output
    """
    if not dependencia or not dependencia.strip():
        return dependencia

    original = dependencia.strip()

    # Rule 1: Explicit override (highest precedence)
    if original in rules.explicit_overrides:
        return rules.explicit_overrides[original]

    # Rule 2: Mesa de Entradas pattern
    mesa_rule = rules.get_rule("mesa_entradas")
    if mesa_rule and mesa_rule.pattern:
        pattern = re.compile(mesa_rule.pattern)
        if pattern.match(original):
            result = pattern.sub(mesa_rule.replacement, original)
            return result.strip()

    # Rule 3: Preserve MDE names
    preserve_rule = rules.get_rule("preserve_mde")
    if preserve_rule and preserve_rule.patterns:
        for pattern_str in preserve_rule.patterns:
            pattern = re.compile(pattern_str)
            if pattern.match(original):
                return original

    # Rule 4: Strip trailing parentheses
    strip_rule = rules.get_rule("strip_parentheses")
    if strip_rule and strip_rule.pattern:
        pattern = re.compile(strip_rule.pattern)
        result = pattern.sub(strip_rule.replacement, original)
        return result.strip()

    # Rule 5: Identity fallback
    return original


def normalize_batch(dependencias: list[str], rules: NormalizationRules) -> list[str]:
    """
    Normalize a batch of dependency names.

    Args:
        dependencias: List of raw dependency names
        rules: NormalizationRules object

    Returns:
        List of normalized dependency names (same order).
    """
    return [normalize(dep, rules) for dep in dependencias]


# Cache for loaded rules to avoid repeated file I/O
_rules_cache: Optional[NormalizationRules] = None
_rules_cache_path: Optional[Path] = None


def get_normalizer(rules_path: Optional[Path] = None) -> NormalizationRules:
    """
    Get cached normalization rules, loading from file if necessary.

    Args:
        rules_path: Optional path to rules file. If None, uses default.

    Returns:
        NormalizationRules object.
    """
    global _rules_cache, _rules_cache_path

    if rules_path is None:
        from src.config import get_settings
        settings = get_settings()
        rules_path = Path(settings.normalizer.rules_path)

    if _rules_cache is None or _rules_cache_path != rules_path:
        _rules_cache = load_rules(rules_path)
        _rules_cache_path = rules_path

    return _rules_cache


def clear_normalizer_cache() -> None:
    """Clear the cached normalization rules (for testing)."""
    global _rules_cache, _rules_cache_path
    _rules_cache = None
    _rules_cache_path = None
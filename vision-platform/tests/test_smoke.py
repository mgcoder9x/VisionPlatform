"""Smoke test: verify package importable + version present."""
import vision_platform


def test_package_importable():
    """Package phải import được sau khi pip install -e."""
    assert vision_platform.__version__ == "0.1.0"


def test_package_has_layers():
    """All layer subpackages phải tồn tại (4 layer + adapter rim + profiles)."""
    import vision_platform.domain
    import vision_platform.kernel
    import vision_platform.kernel.ports
    import vision_platform.runtime
    import vision_platform.application
    import vision_platform.adapters
    import vision_platform.profiles
